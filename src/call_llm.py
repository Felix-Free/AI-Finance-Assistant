"""The ONLY place in this project that calls the model.

Why a single entry point: it makes "log every call" a structural guarantee
rather than a habit. Nothing else may import `requests` for model calls.

Token measurement (NFR-002):

Source: the gateway response's `usage` object, mapped to
        {"input": usage.prompt_tokens, "output": usage.completion_tokens,
         "total": usage.total_tokens}
Missing data is recorded as null and is never estimated or zero-filled.
`request_made` is false only when no HTTP request was attempted (missing base url or key).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import uuid

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = (os.environ.get("LLM_BASE_URL") or "").rstrip("/")
API_KEY = os.environ.get("LLM_API_KEY") or ""
MODEL = os.environ.get("LLM_MODEL", "CS5351/DeepSeek-V4-Flash")

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
LOG_PATH = _REPO_ROOT / "logs" / "llm_calls.jsonl"

_SESSION_ID = uuid.uuid4().hex

SYSTEM_PROMPT = (
    "You extract a spending record from one sentence. "
    'Return ONLY a JSON object with keys: "amount" (number), "category" (string). '
    'If the sentence is not a spending record, return {"error": "not_a_record"}. '
    "Do not explain. Do not add keys."
)


class LlmTransportError(RuntimeError):
    """Raised when the model call itself fails (network, auth, quota, protocol).

    Optional ``status_code`` / ``body`` carry HTTP details so the caller can
    log them without re-reading the response.
    """

    def __init__(self, message, status_code=None, body=None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _new_call_id() -> str:
    """Per actual LLM API call. Full uuid4 hex (32 chars), no truncation."""
    return uuid.uuid4().hex


def _new_request_id() -> str:
    """Per user request. Full uuid4 hex (32 chars); one request may span calls."""
    return uuid.uuid4().hex


def session_id() -> str:
    """Session id: generated once per process run and shared by every call."""
    return _SESSION_ID


_USAGE_KEYS = (
    ("input", "prompt_tokens"),
    ("output", "completion_tokens"),
    ("total", "total_tokens"),
)


def _map_usage(raw_usage: dict) -> dict:
    """Map a gateway ``usage`` object to {input,output,total}; unknown -> None.

    Never estimates or zero-fills: a missing or non-int source value stays None.
    """
    mapped = {}
    for dest, source in _USAGE_KEYS:
        value = raw_usage.get(source)
        mapped[dest] = value if isinstance(value, int) and not isinstance(value, bool) else None
    return mapped


def _usage_source(tokens) -> str:
    """Classify a tokens dict: all present -> gateway, some -> partial, none -> missing."""
    if tokens is None:
        return "missing"
    present = [v for v in tokens.values() if v is not None]
    if len(present) == len(tokens):
        return "gateway"
    if present:
        return "partial"
    return "missing"


def _append_log(record: dict) -> None:
    """Fail-closed: if we cannot log the call, the call must not be used."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:  # pragma: no cover - environment failure
        raise LlmTransportError(f"cannot write call log: {exc}") from exc


def _post(payload: dict):
    """Perform the HTTP call and return ``(content, usage)``.

    ``usage`` is ``{"input":.., "output":.., "total":..}`` (each ``int`` or
    ``None``) or ``None`` when the envelope carries no ``usage`` object. Module-level
    (not a closure) so a test can replace it with monkeypatch.

    Raises LlmTransportError on any transport or protocol failure: network
    error, non-200 status, or a response envelope that cannot be parsed into
    {"choices": [{"message": {"content": <str>}}]}. Protocol failures must
    never escape as KeyError / IndexError / ValueError.
    """
    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise LlmTransportError("transport: %s" % exc) from exc

    if resp.status_code != 200:
        raise LlmTransportError(
            "http %s" % resp.status_code,
            status_code=resp.status_code,
            body=resp.text[:500],
        )

    try:
        envelope = resp.json()
    except ValueError as exc:
        raise LlmTransportError(
            "protocol: cannot parse response json: %s" % exc
        ) from exc

    try:
        content = envelope["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmTransportError(
            "protocol: malformed response envelope: %r" % (exc,)
        ) from exc

    if not isinstance(content, str):
        raise LlmTransportError(
            "protocol: content is not a string: %r" % (type(content).__name__,)
        )

    raw_usage = envelope.get("usage")
    usage = _map_usage(raw_usage) if isinstance(raw_usage, dict) else None
    return content, usage


def extract(text: str, request_id=None) -> dict:
    """Call the model once and return the UNVALIDATED parsed JSON object.

    ``request_id`` is a keyword with a default so ``extract(text)`` keeps
    working; when omitted a fresh id is generated for this call.

    The returned dict is raw model output and is NOT trusted. The caller MUST
    pass it to policy_core.validate_record() before anything may be stored; it
    must never be persisted directly. It carries the private key
    ``"__call_id__"`` (transport metadata) which the caller MUST pop before
    validation; it is never data and never stored.

    Exactly one line is appended to logs/llm_calls.jsonl on every path
    (config, transport / non-200, protocol / non-JSON, success): log first, then
    raise or return. Every line carries ``call_id``, ``request_id``,
    ``session_id``, ``tokens``, ``usage_source`` and ``request_made``. If the
    log cannot be written, the result is not returned (fail-closed).

    Raises LlmTransportError on transport / protocol failure, and
    json.JSONDecodeError when the model returns something that is not JSON
    (logged, then re-raised; the caller decides whether that becomes a
    rejection).
    """
    call_id = _new_call_id()
    if request_id is None:
        request_id = _new_request_id()
    session = session_id()

    def _line(**extra) -> dict:
        base = {
            "input": text,
            "raw": None,
            "parsed": None,
            "error": None,
            "call_id": call_id,
            "request_id": request_id,
            "session_id": session,
            "tokens": None,
            "usage_source": "missing",
            "request_made": True,
        }
        base.update(extra)
        return base

    if not BASE_URL or not API_KEY:
        _append_log(_line(
            request_made=False, usage_source="missing",
            error="config: missing base url or key",
        ))
        raise LlmTransportError("LLM_BASE_URL / LLM_API_KEY missing (.env)")

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    try:
        raw, usage = _post(payload)
    except LlmTransportError as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code is not None:
            body = (getattr(exc, "body", "") or "")[:120]
            error = "http %s: %s" % (status_code, body)
        else:
            error = str(exc)
        _append_log(_line(
            request_made=True, usage_source="missing", error=error,
        ))
        raise

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Log the failure, then let the caller decide (do not swallow).
        _append_log(_line(
            request_made=True, usage_source="missing",
            raw=raw, parsed=None, error="not_json",
        ))
        raise

    tokens = usage
    _append_log(_line(
        request_made=True, tokens=tokens, usage_source=_usage_source(tokens),
        raw=raw, parsed=parsed,
    ))
    if isinstance(parsed, dict):
        parsed["__call_id__"] = call_id
    return parsed


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) or "昨晚吃火锅花了 350"
    print(f"[model] {MODEL}")
    print(f"[input] {text}")
    result = extract(text)
    print(f"[parsed] {result}")
    print("[log]   logs/llm_calls.jsonl (appended)")
