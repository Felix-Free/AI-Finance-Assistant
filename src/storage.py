"""Append-only persistence for validated records.

This module is the ONLY place that writes validated records to disk. It is a
downstream consumer of ``policy_core``: the dependency direction is
pipeline -> storage, never policy_core -> storage.

Fail-closed: a record that cannot be validated or written raises
``StorageError``; it is never silently dropped and success is never faked.
"""
from __future__ import annotations

import json
import pathlib
from typing import Iterator

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_PATH = _REPO_ROOT / "data" / "records.jsonl"

REQUIRED_FIELDS = (
    "call_id",
    "amount",
    "category",
    "total",
    "budget_limit",
    "decided_at",
)

_NUMERIC_FIELDS = ("amount", "total", "budget_limit")


class StorageError(RuntimeError):
    """Raised when a validated record cannot be persisted. Never a policy rejection."""


def _is_number(value) -> bool:
    """True for int/float but not bool (bool is an int subclass)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_record(record: dict) -> None:
    """Re-validate a record before it reaches disk; any problem is a StorageError."""
    if not isinstance(record, dict):
        raise StorageError("record must be a dict, got %r" % type(record).__name__)
    for field in REQUIRED_FIELDS:
        if field not in record:
            raise StorageError("missing required field %r" % (field,))
    unknown = set(record) - set(REQUIRED_FIELDS)
    if unknown:
        raise StorageError("unexpected field(s): %r" % sorted(unknown))
    call_id = record["call_id"]
    if not isinstance(call_id, str) or not call_id:
        raise StorageError("call_id must be a non-empty str, got %r" % (call_id,))
    category = record["category"]
    if not isinstance(category, str) or not category:
        raise StorageError("category must be a non-empty str, got %r" % (category,))
    for field in _NUMERIC_FIELDS:
        if not _is_number(record[field]):
            raise StorageError(
                "%s must be a number, got %r"
                % (field, type(record[field]).__name__)
            )


def _existing_call_ids() -> set:
    """Collect call_ids already stored; malformed lines are a StorageError."""
    ids = set()
    if not DATA_PATH.exists():
        return ids
    try:
        with DATA_PATH.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    stored = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise StorageError(
                        "malformed line in %s: %s" % (DATA_PATH, exc)
                    ) from exc
                if isinstance(stored, dict) and "call_id" in stored:
                    ids.add(stored["call_id"])
    except OSError as exc:  # pragma: no cover - environment failure
        raise StorageError("cannot read %s: %s" % (DATA_PATH, exc)) from exc
    return ids


def append_validated(record: dict) -> None:
    """Re-validate inside and append exactly one JSON line; fail-closed on any problem."""
    _validate_record(record)
    if record["call_id"] in _existing_call_ids():
        raise StorageError("duplicate call_id")
    try:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DATA_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise StorageError("cannot write %s: %s" % (DATA_PATH, exc)) from exc


def current_total() -> float:
    """INV-003 support: sum of stored amounts; 0.0 when nothing is stored yet."""
    total = 0.0
    for record in iter_records():
        amount = record.get("amount") if isinstance(record, dict) else None
        if not _is_number(amount):
            raise StorageError(
                "stored record has no numeric amount: %r"
                % (record.get("call_id") if isinstance(record, dict) else record,)
            )
        total += amount
    return total


def iter_records() -> Iterator[dict]:
    """Read-only helper: yield stored records; a malformed line is a StorageError."""
    if not DATA_PATH.exists():
        return
    try:
        with DATA_PATH.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise StorageError(
                        "malformed line in %s: %s" % (DATA_PATH, exc)
                    ) from exc
    except OSError as exc:  # pragma: no cover - environment failure
        raise StorageError("cannot read %s: %s" % (DATA_PATH, exc)) from exc
