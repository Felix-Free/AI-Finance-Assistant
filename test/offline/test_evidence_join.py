"""Evidence-join tests — SKELETON handed to role E (Phase 2).

Owner of this file: role E. Role D created only the skeleton so the assertions are agreed
before both sides write their own version. Every test below is skipped on purpose; E replaces
`pytest.skip(...)` with real assertions (or deletes the skip) once the pipeline wiring is merged.

Contract being verified (role C, approved 2026-11-12):

  * acceptance path : llm_calls.call_id == data/records.jsonl.call_id, same non-empty value
  * rejection path  : llm_calls.call_id == logs/review.jsonl.call_id, same non-empty value
  * rejection path  : the rejection writes NO line to data/records.jsonl
  * every log line  : exactly ten keys (see the log contract in AGENTS.md / structural-constraints §5)

How to exercise it deterministically: monkeypatch `call_llm._post` (the transport seam) and
`storage.DATA_PATH` + `pipeline.REVIEW_PATH` into `tmp_path`, so nothing touches the real logs.
"""
from __future__ import annotations

import json

import pytest

from src import call_llm, pipeline, storage

pytestmark = pytest.mark.skip(
    reason="skeleton: role E replaces each skip with assertions (Phase 2 handoff)"
)

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


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Point the call log, the rejection log and the records file at tmp_path."""
    monkeypatch.setattr(call_llm, "LOG_PATH", tmp_path / "logs" / "llm_calls.jsonl")
    monkeypatch.setattr(pipeline, "REVIEW_PATH", tmp_path / "logs" / "review.jsonl")
    monkeypatch.setattr(storage, "DATA_PATH", tmp_path / "data" / "records.jsonl")
    return tmp_path


def test_acceptance_call_id_joins_record(isolated, monkeypatch):
    """E: stub _post to return a valid record; then assert the join."""
    # monkeypatch.setattr(call_llm, "_post", lambda payload: ('{"amount": 350, "category": "food"}', None))
    # record = pipeline.process("hotpot last night cost 350", spent=0.0, budget_limit=1000.0)
    # calls = _read_jsonl(call_llm.LOG_PATH)
    # assert len(calls) == 1
    # assert record["call_id"] == calls[0]["call_id"]
    # assert record["call_id"]
    pytest.skip("TODO (E): acceptance-path join assertion")


def test_rejection_call_id_joins_review_line(isolated, monkeypatch):
    """E: stub _post to return an out-of-vocabulary category; then assert the join."""
    # monkeypatch.setattr(call_llm, "_post", lambda payload: ('{"amount": 350, "category": "Food"}', None))
    # with pytest.raises(policy_core.PolicyError):
    #     pipeline.process("hotpot", spent=0.0, budget_limit=1000.0)
    # calls = _read_jsonl(call_llm.LOG_PATH); reviews = _read_jsonl(pipeline.REVIEW_PATH)
    # assert len(reviews) == 1
    # assert reviews[0]["call_id"] == calls[0]["call_id"] != ""
    pytest.skip("TODO (E): rejection-path join assertion")


def test_rejection_writes_no_record(isolated, monkeypatch):
    """E: a rejection must leave data/records.jsonl untouched."""
    # ... trigger a rejection ...
    # assert not storage.DATA_PATH.exists()   # or: file content unchanged
    pytest.skip("TODO (E): rejection must not persist a record")


def test_every_log_line_has_exactly_ten_keys(isolated, monkeypatch):
    """E: the key set is identical on a success line and on a config-failure line."""
    # success:  monkeypatch _post -> ('{"amount":1,"category":"food"}', {"input":1,"output":1,"total":2})
    # failure:  monkeypatch base url empty -> LlmTransportError raised, still one line written
    # for line in _read_jsonl(call_llm.LOG_PATH):
    #     assert set(line) == TEN_KEYS
    pytest.skip("TODO (E): exact key set on every path")
