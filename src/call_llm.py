"""The ONLY place in this project that calls the model.

Why a single entry point: it makes "log every call" a structural guarantee
rather than a habit. Nothing else may import `requests` for model calls.
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

LOG_PATH = pathlib.Path("logs/llm_calls.jsonl")

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
    """Correlation id joining the call line to its rejection line (12 hex chars)."""
    return uuid.uuid4().hex[:12]


def _append_log(record: dict) -> None:
    """Fail-closed: if we cannot log the call, the call must not be used."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:  # pragma: no cover - environment failure
        raise LlmTransportError(f"cannot write call log: {exc}") from exc


def _post(payload: dict) -> str:
    """Perform the HTTP call and return the model's raw response string.

    Module-level (not a closure) so a test can replace it with monkeypatch.

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
    return content


def extract(text: str) -> dict:
    """Call the model once and return the UNVALIDATED parsed JSON object.

    The returned dict is raw model output and is NOT trusted. The caller MUST
    pass it to policy_core.validate_record() before anything may be stored; it
    must never be persisted directly. It carries the private key
    ``"__call_id__"`` (transport metadata) which the caller MUST pop before
    validation; it is never data and never stored.

    Exactly one line is appended to logs/llm_calls.jsonl on every path
    (success, non-JSON content, HTTP non-200, transport failure): log first,
    then raise or return. Every line carries ``call_id``. If the log cannot be
    written, the result is not returned (fail-closed).

    Raises LlmTransportError on transport / protocol failure, and
    json.JSONDecodeError when the model returns something that is not JSON
    (logged, then re-raised; the caller decides whether that becomes a
    rejection).
    """
    call_id = _new_call_id()

    if not BASE_URL or not API_KEY:
        _append_log({"input": text, "call_id": call_id,
                     "error": "config: missing base url or key"})
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
        raw = _post(payload)
    except LlmTransportError as exc:
        log_record = {"input": text, "call_id": call_id, "error": str(exc)}
        status_code = getattr(exc, "status_code", None)
        if status_code is not None:
            log_record["error"] = "http %s" % status_code
            log_record["body"] = getattr(exc, "body", "")
        _append_log(log_record)
        raise

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Log the failure, then let the caller decide (do not swallow).
        _append_log({"input": text, "call_id": call_id, "raw": raw,
                     "parsed": None, "error": "not_json"})
        raise

    _append_log({"input": text, "call_id": call_id, "raw": raw,
                 "parsed": parsed})
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
