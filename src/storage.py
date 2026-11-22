"""Append-only persistence for validated records.

This module is the ONLY place that writes validated records to disk. It is a
downstream consumer of ``policy_core``: the dependency direction is
pipeline -> storage, never policy_core -> storage.

Fail-closed: a record that cannot be validated or written raises
``StorageError``; it is never silently dropped and success is never faked.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import pathlib
import shutil
import tempfile
from decimal import Decimal
from typing import Any, Iterator, Optional, Set, cast

from src import policy_core

logger = logging.getLogger(__name__)

_fcntl: Optional[Any]
try:  # POSIX advisory file lock (cross-process)
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - non-POSIX
    _fcntl = None

_msvcrt: Optional[Any]
try:  # Windows file lock (cross-process)
    import msvcrt as _msvcrt
except ImportError:
    _msvcrt = None

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

# Controlled internal marker: only the pipeline can select the authoritative
# persisted-total path. It is not a hard security boundary (module-private).
_PIPELINE_ORIGIN = object()


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
        raise StorageError("call_id must be a non-empty string")
    category = record["category"]
    if not isinstance(category, str) or not category:
        raise StorageError("category must be a non-empty string")
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
    ids: Set[str] = set()
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
                    raise StorageError("malformed line in storage") from exc
                if not isinstance(stored, dict):
                    raise StorageError("stored line is not an object")
                _check_stored_call_id(stored)
                ids.add(stored["call_id"])
    except OSError as exc:  # pragma: no cover - environment failure
        raise StorageError("storage read failed") from exc
    return ids


def _acquire(fh) -> None:
    """Take an exclusive lock on an open lock file (blocking)."""
    if _fcntl is not None:
        _fcntl.flock(fh.fileno(), _fcntl.LOCK_EX)
    elif _msvcrt is not None:  # pragma: no cover - Windows
        _msvcrt.locking(fh.fileno(), _msvcrt.LK_LOCK, 1)
    else:  # pragma: no cover - no OS lock available
        raise StorageError(
            "no OS file lock available (fcntl/msvcrt); refusing an unsafe append"
        )


def _release(fh) -> None:
    """Release the exclusive lock taken by ``_acquire``."""
    if _fcntl is not None:
        _fcntl.flock(fh.fileno(), _fcntl.LOCK_UN)
    elif _msvcrt is not None:  # pragma: no cover - Windows
        _msvcrt.locking(fh.fileno(), _msvcrt.LK_UNLCK, 1)
    else:  # pragma: no cover - unreachable: _acquire refuses without an OS lock
        return


def _best_effort_warning(message: str) -> None:
    """Log a teardown problem without ever letting logging failure escape."""
    try:
        logger.warning(message)
    except Exception:  # pragma: no cover - logging must never mask the result
        pass


@contextlib.contextmanager
def _locked():
    """Exclusive lock across read -> duplicate check -> budget check -> write -> replace.

    Uses a same-directory sidecar lock file ``<data>.lock`` so writers in other
    processes are serialised too (POSIX ``flock`` / Windows ``msvcrt.locking``,
    both blocking). There is no process-local fallback: if neither OS lock is
    available the append fails closed with ``StorageError`` before any temp file
    is created.
    """
    lock_path = DATA_PATH.with_name(DATA_PATH.name + ".lock")
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fh = lock_path.open("a+b")
    except OSError as exc:
        raise StorageError("cannot acquire storage lock") from exc
    try:
        _acquire(fh)
    except StorageError:
        try:
            fh.close()
        except Exception:
            pass
        raise
    except OSError as exc:
        try:
            fh.close()
        except Exception:
            pass
        raise StorageError("cannot acquire storage lock") from exc
    try:
        yield
    finally:
        try:
            try:
                _release(fh)
            except Exception:
                _best_effort_warning("storage lock release failed")
        finally:
            try:
                fh.close()
            except Exception:
                _best_effort_warning("storage lock close failed")


def _write_record_locked(record: dict) -> None:
    """Atomically append one JSON line; caller must hold the storage lock.

    The existing bytes and the new line are written to a same-directory
    temporary file, flushed and ``fsync``-ed, then committed with
    ``os.replace``. A failed commit leaves the original file byte-identical.
    Messages never carry a path or raw ``OSError`` text.
    """
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
        fd, tmp_name = tempfile.mkstemp(
            dir=str(DATA_PATH.parent),
            prefix=DATA_PATH.name + ".",
            suffix=".tmp",
        )
    except OSError as exc:
        raise StorageError("storage write failed") from exc
    tmp = pathlib.Path(tmp_name)
    try:
        fh = os.fdopen(fd, "wb")
    except Exception as exc:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise StorageError("storage write failed") from exc
    try:
        with fh:
            if DATA_PATH.exists():
                with DATA_PATH.open("rb") as src:
                    shutil.copyfileobj(src, fh)
            fh.write((line + "\n").encode("utf-8"))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, DATA_PATH)
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise StorageError("storage write failed") from exc


def append_validated(record: dict, expected_spent=None, *, origin=None):
    """Re-check the record against the persisted state, then append one JSON line.

    INV-001/002/003 are re-run here by calling ``policy_core`` guards; storage
    never re-implements a threshold. ``expected_spent`` is a numeric validation
    parameter (never a persisted field): when supplied it must not be below the
    persisted cumulative spend, because under-reporting prior spend would let a
    record slip past the cumulative budget guard. ``expected_spent=None`` uses
    the persisted cumulative spend as the effective spend.

    ``origin`` is a controlled internal marker: when it is the private
    ``_PIPELINE_ORIGIN`` sentinel (only the pipeline passes it), the record goes
    through the authoritative persisted-total path
    (``_append_from_pipeline``). Any other value keeps the direct semantics
    below unchanged, so external callers cannot opt into the pipeline path.

    Rejections keep role C's error semantics: a rule violation raises
    ``PolicyError`` with the original ``policy:*`` code; under-reported spend,
    arithmetic inconsistency and IO failures raise ``StorageError``. Every
    validation failure rejects before any byte is written, so the file is
    unchanged. The append itself is atomic: the existing bytes and the new line
    are written to a same-directory temporary file, flushed and ``fsync``-ed,
    then committed with ``os.replace``. A failed commit leaves the original
    file byte-identical; readers therefore never see a partially written line.
    """
    if origin is _PIPELINE_ORIGIN:
        return _append_from_pipeline(record)
    _validate_record(record)
    with _locked():
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
                raise StorageError("expected_spent below persisted cumulative spend")
        policy_core.enforce_amount(record["amount"])
        policy_core.enforce_category(record["category"])
        policy_core.enforce_budget(effective, record["amount"], record["budget_limit"])
        if (Decimal(str(record["total"]))
                != Decimal(str(effective)) + Decimal(str(record["amount"]))):
            raise StorageError("total inconsistent with expected_spent + amount")
        _write_record_locked(record)


def _append_from_pipeline(record: dict) -> dict:
    """Internal pipeline path: the persisted total is authoritative.

    The pipeline pre-checks with ``current_total()``, but that read is only
    advisory. Under the lock we re-read ``persisted`` and recompute
    ``total = persisted + amount`` so a stale caller value never decides the
    budget. Over budget raises ``PolicyError`` (``policy:budget``) before any
    byte is written. Returns the canonical record that was written, so the
    caller sees the locked total.
    """
    _validate_record(record)
    with _locked():
        if record["call_id"] in _existing_call_ids():
            raise StorageError("duplicate call_id")
        persisted = current_total()
        policy_core.enforce_amount(record["amount"])
        policy_core.enforce_category(record["category"])
        total = policy_core.enforce_budget(
            persisted, record["amount"], record["budget_limit"]
        )
        canonical = dict(record)
        canonical["total"] = total
        _write_record_locked(canonical)
        return canonical


def current_total() -> float:
    """INV-003 support: sum of stored amounts; 0.0 when nothing is stored yet."""
    total = 0.0
    for record in iter_records():
        amount = record.get("amount") if isinstance(record, dict) else None
        if not _is_number(amount):
            raise StorageError("stored record has no numeric amount")
        amount = cast(float, amount)
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
                    raise StorageError("malformed line in storage") from exc
                if not isinstance(stored, dict):
                    raise StorageError("stored line is not an object")
                _check_stored_call_id(stored)
                yield stored
    except OSError as exc:  # pragma: no cover - environment failure
        raise StorageError("storage read failed") from exc
