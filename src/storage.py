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
from decimal import Decimal
from typing import Iterator

from src import policy_core

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


def _non_serialisable_field(record: dict):
    """Name the first field whose value json.dumps cannot encode; None if unknown."""
    for field in record:
        try:
            json.dumps(record[field], ensure_ascii=False)
        except TypeError:
            return field
    return None


def _check_stored_call_id(stored: dict) -> None:
    """A stored call_id must be a non-empty string; corrupt state is a StorageError."""
    call_id = stored.get("call_id")
    if not isinstance(call_id, str) or not call_id:
        raise StorageError(
            "call_id must be a non-empty string: got %r" % type(call_id).__name__
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
                if not isinstance(stored, dict):
                    raise StorageError(
                        "stored line is not an object: got %r"
                        % type(stored).__name__
                    )
                _check_stored_call_id(stored)
                ids.add(stored["call_id"])
    except OSError as exc:  # pragma: no cover - environment failure
        raise StorageError("cannot read %s: %s" % (DATA_PATH, exc)) from exc
    return ids


def append_validated(record: dict, expected_spent=None) -> None:
    """Re-check the record against the persisted state, then append one JSON line.

    INV-001/002/003 are re-run here by calling ``policy_core`` guards; storage
    never re-implements a threshold. ``expected_spent`` is a numeric validation
    parameter (never a persisted field): when supplied it must not be below the
    persisted cumulative spend, because under-reporting prior spend would let a
    record slip past the cumulative budget guard. ``expected_spent=None`` uses
    the persisted cumulative spend as the effective spend.

    Rejections keep role C's error semantics: a rule violation raises
    ``PolicyError`` with the original ``policy:*`` code; under-reported spend,
    arithmetic inconsistency and IO failures raise ``StorageError``. On any
    failure the file is left unchanged.
    """
    _validate_record(record)
    if record["call_id"] in _existing_call_ids():
        raise StorageError("duplicate call_id")
    if expected_spent is not None and not _is_number(expected_spent):
        raise StorageError(
            "expected_spent must be a number, got %r"
            % type(expected_spent).__name__
        )
    persisted = current_total()
    if expected_spent is None:
        effective = persisted
    else:
        effective = expected_spent
        if effective < persisted:
            raise StorageError(
                "expected_spent below persisted cumulative spend: %r < %r"
                % (effective, persisted)
            )
    policy_core.enforce_amount(record["amount"])
    policy_core.enforce_category(record["category"])
    policy_core.enforce_budget(effective, record["amount"], record["budget_limit"])
    if (Decimal(str(record["total"]))
            != Decimal(str(effective)) + Decimal(str(record["amount"]))):
        raise StorageError(
            "total inconsistent with expected_spent + amount: %r != %r + %r"
            % (record["total"], effective, record["amount"])
        )
    try:
        line = json.dumps(record, ensure_ascii=False)
    except TypeError:
        field = _non_serialisable_field(record)
        raise StorageError(
            "record is not JSON-serialisable: field %r has type %r"
            % (field, type(record.get(field)).__name__)
        ) from None
    try:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DATA_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
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
                    stored = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise StorageError(
                        "malformed line in %s: %s" % (DATA_PATH, exc)
                    ) from exc
                if not isinstance(stored, dict):
                    raise StorageError(
                        "stored line is not an object: got %r"
                        % type(stored).__name__
                    )
                _check_stored_call_id(stored)
                yield stored
    except OSError as exc:  # pragma: no cover - environment failure
        raise StorageError("cannot read %s: %s" % (DATA_PATH, exc)) from exc
