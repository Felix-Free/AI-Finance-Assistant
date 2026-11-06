"""The ONLY place in this project that calls the model.

Why a single entry point: it makes "log every call" a structural guarantee
rather than a habit. Nothing else may import `requests` for model calls.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

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
    """Raised when the model call itself fails (network, auth, quota)."""


def _append_log(record: dict) -> None:
    """Fail-closed: if we cannot log the call, the call must not be used."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:  # pragma: no cover - environment failure
        raise LlmTransportError(f"cannot write call log: {exc}") from exc


def extract(text: str) -> dict:
    """Call the model once and return the parsed JSON object.

    Raises LlmTransportError on transport failure, and json.JSONDecodeError
    when the model returns something that is not JSON (the caller decides
    whether that becomes a rejection).
    """
    if not BASE_URL or not API_KEY:
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
        _append_log({"input": text, "error": f"transport: {exc}"})
        raise LlmTransportError(str(exc)) from exc

    if resp.status_code != 200:
        _append_log({"input": text, "error": f"http {resp.status_code}",
                     "body": resp.text[:500]})
        raise LlmTransportError(f"HTTP {resp.status_code}: {resp.text[:300]}")

    raw = resp.json()["choices"][0]["message"]["content"]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Log the failure, then let the caller decide (do not swallow).
        _append_log({"input": text, "raw": raw, "parsed": None,
                     "error": "not_json"})
        raise

    _append_log({"input": text, "raw": raw, "parsed": parsed})
    return parsed


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) or "昨晚吃火锅花了 350"
    print(f"[model] {MODEL}")
    print(f"[input] {text}")
    result = extract(text)
    print(f"[parsed] {result}")
    print("[log]   logs/llm_calls.jsonl (appended)")
