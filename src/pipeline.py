"""End-to-end pipeline: model proposes, policy_core disposes.

Execution order (runtime-policy-catalog.md §3):

1) parse + log (RP-004 / RP-001)  -> call_llm.extract(text)
2) invariants (RP-003 / RP-005 / RP-006) -> policy_core.validate_record(...)
3) pass -> return the validated record (persistence is out of scope here).

No silent try/except, no retry, no IO outside logs/. Never imports requests.
"""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

from src import call_llm, policy_core, storage

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
REVIEW_PATH = _REPO_ROOT / "logs" / "review.jsonl"


def _append_rejection(record: dict) -> None:
    """Append exactly one rejection line. Fail-closed: raise StorageError on failure.

    Business fields (amount/category/spent/total) are forced to ``None`` so a
    review line never carries user amounts; only ids, the safe ``error`` code and
    ``review`` survive. The failure message is safe (no path / raw OSError text).
    """
    for field in ("amount", "category", "spent", "total"):
        record[field] = None
    try:
        REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
        with REVIEW_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:  # pragma: no cover - environment failure
        raise storage.StorageError("review write failed") from exc


def process(text: str, spent=None, budget_limit: float = 1000.0) -> dict:
    """Parse one sentence, validate it, persist it, and return the stored record.

    ``call_llm.extract`` returns an UNVALIDATED parse carrying the private
    transport key ``"__call_id__"``. It is popped here, before validation, so
    the record passed to ``policy_core.validate_record`` never contains it.

    When ``spent`` is None the running total is read from ``storage`` so that
    INV-003 is checked against what has actually been persisted. The caller's
    ``spent`` is advisory only: the persisted total is always the authoritative
    validation input, and a stale (low or high) value never decides the budget.

    Every policy rejection (INV-001, INV-002, INV-003) appends exactly one line
    to logs/review.jsonl carrying ``error`` = the ORIGINAL rejection code and
    the same ``call_id`` as the call line, then re-raises. The ``review`` field
    keeps the distinction: False for amount, True for category/budget.
    logs/llm_calls.jsonl is untouched (RP-004 preserved: exactly one line per
    model call, written by call_llm.extract).
    ``LlmTransportError`` propagates unchanged and is never retried.

    INV-003 support: a validated record is appended via the internal storage
    path so the persisted total is authoritative under the lock; a
    ``StorageError`` from persistence propagates (never a fake success).
    Rejections are evidence, not state: they are logged to logs/review.jsonl and
    are never persisted.
    """
    request_id = call_llm._new_request_id()
    raw = call_llm.extract(text, request_id=request_id)
    call_id = raw.pop("__call_id__", None) if isinstance(raw, dict) else None
    if not isinstance(call_id, str) or not call_id:
        raise storage.StorageError("missing call_id from model client")

    # ``spent`` is advisory only: the persisted total is the authoritative
    # validation input. A stale low or high caller value never decides the
    # budget (and never raises StorageError by itself).
    persisted = storage.current_total()

    # C's rule: rejections are evidence, not state — they are written to
    # logs/review.jsonl only and are NEVER passed to storage.
    try:
        validated = policy_core.validate_record(raw, persisted, budget_limit)
    except policy_core.PolicyError as exc:
        _append_rejection({
            "call_id": call_id,
            "request_id": request_id,
            "error": exc.code,
            "amount": None,
            "category": None,
            "spent": None,
            "total": None,
            "review": exc.review,
        })
        raise

    decided_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = {
        "call_id": call_id,
        "amount": validated["amount"],
        "category": validated["category"],
        "total": validated["total"],
        "budget_limit": budget_limit,
        "decided_at": decided_at,
    }
    # The pre-check above is only advisory; storage re-reads the persisted total
    # under the lock and recomputes the authoritative total. A lock-time budget
    # rejection is a PolicyError and gets exactly one review line; a
    # StorageError propagates unchanged with no review.
    try:
        return storage._append_from_pipeline(record)
    except policy_core.PolicyError as exc:
        _append_rejection({
            "call_id": call_id,
            "request_id": request_id,
            "error": exc.code,
            "amount": None,
            "category": None,
            "spent": None,
            "total": None,
            "review": exc.review,
        })
        raise
