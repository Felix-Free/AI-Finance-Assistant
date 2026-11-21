"""Evidence-join tests (Phase 2, owner: role E).

These drive the REAL ``pipeline.process`` -> ``call_llm.extract`` path with a faked
transport seam (``call_llm._post``) and a faked gateway ``usage`` object, so every
assertion below is about the wiring that actually ships, not a re-implementation.

Contract verified (role C; ``runtime-policy-catalog.md`` §5, invariants.md §2):

  * acceptance path : llm_calls.call_id == data/records.jsonl.call_id, same non-empty value
  * rejection path  : llm_calls.call_id == logs/review.jsonl.call_id, same non-empty value,
                      and the review line carries the ORIGINAL policy:* error code
  * rejection path  : the rejection writes NO bytes to data/records.jsonl (byte-identical)
  * every call line : exactly ten keys, on success and on every failure path
  * tokens/usage    : gateway / partial / missing / not-requested (request_made=false)
  * fail-closed     : all three append-open sites raise instead of faking success

Deterministic and offline: ``_post`` is monkeypatched, every path lives under
``tmp_path``. No network access. Traces NFR-006 / RP-004 / RP-007.
"""
from __future__ import annotations

import json
import pathlib
import tempfile

import pytest

from src import call_llm, pipeline, policy_core, storage

pytestmark = pytest.mark.offline

TEN_KEYS = {
    "input",
    "raw",
    "parsed",
    "error",
    "call_id",
    "request_id",
    "session_id",
    "tokens",
    "usage_source",
    "request_made",
}


def _read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _assert_call_id(value):
    assert isinstance(value, str) and value
    int(value, 16)  # 32-char uuid4 hex; raises ValueError otherwise
    assert len(value) == 32


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Point the call log, the rejection log and the records file at tmp_path."""
    monkeypatch.setattr(call_llm, "LOG_PATH", tmp_path / "logs" / "llm_calls.jsonl")
    monkeypatch.setattr(pipeline, "REVIEW_PATH", tmp_path / "logs" / "review.jsonl")
    monkeypatch.setattr(storage, "DATA_PATH", tmp_path / "data" / "records.jsonl")
    monkeypatch.setattr(call_llm, "BASE_URL", "http://example.invalid")
    monkeypatch.setattr(call_llm, "API_KEY", "test-key")
    return tmp_path


def _fake_post(content, usage=None):
    return lambda payload: (content, usage)


def _seed_record(isolated, monkeypatch):
    """Run ONE real acceptance through the pipeline to establish a prior stored record."""
    monkeypatch.setattr(
        call_llm, "_post",
        _fake_post('{"amount": 100, "category": "food"}',
                   {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}),
    )
    record = pipeline.process("seed 100", spent=0.0, budget_limit=1000.0)
    return record


# ---------------------------------------------------------------------------
# Acceptance
# ---------------------------------------------------------------------------

def test_acceptance_call_id_joins_record(isolated, monkeypatch):
    monkeypatch.setattr(
        call_llm, "_post",
        _fake_post('{"amount": 350, "category": "food"}',
                   {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
    )
    record = pipeline.process("hotpot last night cost 350", spent=0.0, budget_limit=1000.0)

    calls = _read_jsonl(call_llm.LOG_PATH)
    assert len(calls) == 1
    stored = _read_jsonl(storage.DATA_PATH)
    assert len(stored) == 1
    assert stored[0] == record

    _assert_call_id(record["call_id"])
    _assert_call_id(calls[0]["call_id"])
    _assert_call_id(calls[0]["request_id"])
    assert record["call_id"] == calls[0]["call_id"]
    assert set(calls[0]) == TEN_KEYS


# ---------------------------------------------------------------------------
# Rejections: three invariants, each isolated and byte-compared against a
# real prior record.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "payload,expected_error,expected_review",
    [
        ('{"amount": -1, "category": "food"}', "policy:amount", False),
        ('{"amount": 350, "category": "Food"}', "policy:category", True),
        ('{"amount": 20, "category": "food"}', "policy:budget", True),
    ],
    ids=["inv001-amount", "inv002-category", "inv003-budget"],
)
def test_rejection_joins_review_and_leaves_storage_unchanged(
    isolated, monkeypatch, payload, expected_error, expected_review,
):
    # Prior record established by a REAL acceptance (spent becomes 900 -> budget case trips).
    seed = _seed_record(isolated, monkeypatch)
    assert seed["amount"] == 100
    before = storage.DATA_PATH.read_bytes()

    # For the budget case, continue from the persisted 100 with strong pressure.
    spent = 990.0 if expected_error == "policy:budget" else 0.0
    monkeypatch.setattr(call_llm, "_post", _fake_post(payload))

    with pytest.raises(policy_core.PolicyError) as exc:
        pipeline.process("x", spent=spent, budget_limit=1000.0)
    assert exc.value.code == expected_error
    assert exc.value.review is expected_review

    calls = _read_jsonl(call_llm.LOG_PATH)
    reviews = _read_jsonl(pipeline.REVIEW_PATH)
    assert len(reviews) == 1
    review = reviews[0]

    # Join: same non-empty call_id bridges the two evidence files.
    _assert_call_id(review["call_id"])
    _assert_call_id(review["request_id"])
    assert review["call_id"] == calls[-1]["call_id"]
    assert review["request_id"] == calls[-1]["request_id"]
    assert review["error"] == expected_error
    assert review["review"] is expected_review

    # Exactly one call line per model attempt (seed + this attempt == 2).
    assert len(calls) == 2
    assert set(calls[-1]) == TEN_KEYS

    # Rejection is evidence, not state: data/records.jsonl bytes unchanged.
    assert storage.DATA_PATH.read_bytes() == before


# ---------------------------------------------------------------------------
# Ten-key contract across a success line and a config-failure line
# ---------------------------------------------------------------------------

def test_every_log_line_has_exactly_ten_keys(isolated, monkeypatch):
    # success line
    monkeypatch.setattr(
        call_llm, "_post",
        _fake_post('{"amount": 1, "category": "food"}',
                   {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}),
    )
    pipeline.process("ok", spent=0.0, budget_limit=1000.0)

    # config-failure line: no base url -> one line, then raise
    monkeypatch.setattr(call_llm, "BASE_URL", "")
    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("cfg")

    lines = _read_jsonl(call_llm.LOG_PATH)
    assert len(lines) == 2
    for line in lines:
        assert set(line) == TEN_KEYS


# ---------------------------------------------------------------------------
# Usage: complete / partial / missing / not-requested
# ---------------------------------------------------------------------------

def test_usage_complete_is_gateway(isolated, monkeypatch):
    monkeypatch.setattr(
        call_llm, "_post",
        _fake_post('{"amount": 1, "category": "food"}',
                   {"input": 7, "output": 3, "total": 10}),
    )
    pipeline.process("ok", spent=0.0, budget_limit=1000.0)
    line = _read_jsonl(call_llm.LOG_PATH)[0]
    assert line["tokens"] == {"input": 7, "output": 3, "total": 10}
    assert line["usage_source"] == "gateway"
    assert line["request_made"] is True
    assert set(line) == TEN_KEYS


def test_usage_partial_keeps_missing_as_none(isolated, monkeypatch):
    monkeypatch.setattr(
        call_llm, "_post",
        _fake_post('{"amount": 1, "category": "food"}',
                   {"input": 7, "output": None, "total": None}),
    )
    pipeline.process("ok", spent=0.0, budget_limit=1000.0)
    line = _read_jsonl(call_llm.LOG_PATH)[0]
    assert line["tokens"] == {"input": 7, "output": None, "total": None}
    assert line["usage_source"] == "partial"
    assert set(line) == TEN_KEYS


def test_usage_missing_when_envelope_has_no_usage(isolated, monkeypatch):
    monkeypatch.setattr(call_llm, "_post", _fake_post('{"amount": 1, "category": "food"}', None))
    pipeline.process("ok", spent=0.0, budget_limit=1000.0)
    line = _read_jsonl(call_llm.LOG_PATH)[0]
    assert line["tokens"] is None
    assert line["usage_source"] == "missing"
    assert line["request_made"] is True
    assert set(line) == TEN_KEYS


def test_usage_not_requested_when_config_missing(isolated, monkeypatch):
    called = {"n": 0}

    def _spy(payload):
        called["n"] += 1
        raise AssertionError("_post must not be called without config")

    monkeypatch.setattr(call_llm, "_post", _spy)
    monkeypatch.setattr(call_llm, "BASE_URL", "")
    monkeypatch.setattr(call_llm, "API_KEY", "")

    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("cfg")

    assert called["n"] == 0
    line = _read_jsonl(call_llm.LOG_PATH)[0]
    assert line["request_made"] is False
    assert line["tokens"] is None
    assert line["usage_source"] == "missing"
    assert line["raw"] is None and line["parsed"] is None
    assert set(line) == TEN_KEYS


# ---------------------------------------------------------------------------
# Fail-closed: each append-open site raises; prior bytes stay untouched.
# A valid prior record exists first so "unchanged" is meaningful.
# ---------------------------------------------------------------------------

def _block_append(monkeypatch, target):
    """Make ``Path.open(target, 'a', ...)`` raise OSError; restore via monkeypatch."""
    orig_open = pathlib.Path.open
    target = pathlib.Path(target)

    def blocked(path_self, mode="r", *args, **kwargs):
        if pathlib.Path(path_self) == target and "a" in mode:
            raise OSError("simulated append-open failure")
        return orig_open(path_self, mode, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "open", blocked)


def test_accept_append_open_failure_raises_and_keeps_old_bytes(isolated, monkeypatch):
    seed = _seed_record(isolated, monkeypatch)
    assert seed["call_id"]
    before = storage.DATA_PATH.read_bytes()

    monkeypatch.setattr(
        call_llm, "_post", _fake_post('{"amount": 5, "category": "food"}'),
    )
    _block_append(monkeypatch, storage.DATA_PATH)

    orig_mkstemp = tempfile.mkstemp
    target_dir = storage.DATA_PATH.parent
    target_prefix = storage.DATA_PATH.name + "."

    def blocking_mkstemp(*args, **kwargs):
        if kwargs.get("dir") == str(target_dir) and kwargs.get("prefix") == target_prefix:
            raise OSError("simulated append-open failure")
        return orig_mkstemp(*args, **kwargs)

    monkeypatch.setattr(tempfile, "mkstemp", blocking_mkstemp)
    with pytest.raises(storage.StorageError) as exc:
        pipeline.process("y", spent=100.0, budget_limit=1000.0)

    assert isinstance(exc.value.__cause__, OSError)
    assert str(exc.value.__cause__) == "simulated append-open failure"
    assert storage.DATA_PATH.read_bytes() == before
    # No policy review line: a storage write failure is not a policy rejection.
    assert not pipeline.REVIEW_PATH.exists()


def test_rejection_append_open_failure_raises_storage_error(isolated, monkeypatch):
    seed = _seed_record(isolated, monkeypatch)
    assert seed["call_id"]
    before = storage.DATA_PATH.read_bytes()

    monkeypatch.setattr(call_llm, "_post", _fake_post('{"amount": 350, "category": "Food"}'))
    _block_append(monkeypatch, pipeline.REVIEW_PATH)
    with pytest.raises(storage.StorageError) as exc:
        pipeline.process("x", spent=0.0, budget_limit=1000.0)
    assert not isinstance(exc.value, policy_core.PolicyError)

    assert storage.DATA_PATH.read_bytes() == before


def test_call_log_append_open_failure_raises_and_persists_nothing(isolated, monkeypatch):
    seed = _seed_record(isolated, monkeypatch)
    assert seed["call_id"]
    before = storage.DATA_PATH.read_bytes()

    monkeypatch.setattr(
        call_llm, "_post", _fake_post('{"amount": 5, "category": "food"}'),
    )
    _block_append(monkeypatch, call_llm.LOG_PATH)
    with pytest.raises(call_llm.LlmTransportError):
        pipeline.process("y", spent=100.0, budget_limit=1000.0)

    # Fail-closed: the unlogged result never reaches storage.
    assert storage.DATA_PATH.read_bytes() == before
    assert not pipeline.REVIEW_PATH.exists()
