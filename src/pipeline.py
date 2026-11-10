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

from src import call_llm, policy_core

REVIEW_PATH = pathlib.Path("logs/review.jsonl")


def _append_review(record: dict) -> None:
    """Append exactly one review line. Fail-closed: raise if it cannot be written."""
    try:
        REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
        with REVIEW_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:  # pragma: no cover - environment failure
        raise policy_core.PolicyError(
            "cannot write review log: %s" % exc,
            code="policy:budget", review=True,
        ) from exc


def process(text: str, spent: float, budget_limit: float) -> dict:
    """Parse one sentence, validate it, and return the normalised record.

    ``call_llm.extract`` returns an UNVALIDATED parse. It is passed straight to
    ``policy_core.validate_record``; nothing here trusts the model output.

    Every policy rejection (INV-001, INV-002, INV-003) appends exactly one line
    to logs/review.jsonl carrying ``error`` = the rejection code, then re-raises.
    The ``review`` field keeps the distinction: False for amount, True for
    category/budget. logs/llm_calls.jsonl is untouched (RP-004 preserved:
    exactly one line per model call, written by call_llm.extract).
    ``LlmTransportError`` propagates unchanged and is never retried.
    """
    raw = call_llm.extract(text)

    try:
        return policy_core.validate_record(raw, spent, budget_limit)
    except policy_core.PolicyError as exc:
        amount = raw.get("amount") if isinstance(raw, dict) else None
        category = raw.get("category") if isinstance(raw, dict) else None
        try:
            total = spent + amount
        except TypeError:
            total = None
        _append_review({
            "error": exc.code,
            "amount": amount,
            "category": category,
            "spent": spent,
            "total": total,
            "review": exc.review,
        })
        raise
