"""Red tests for issue #27 (task sheet v18): atomic storage append + short,
secret-safe ``error`` codes.

Tests-only round. No production change accompanies this file; the red tests
here describe the DESIRED behaviour (sheet §3/§4) and are expected to FAIL
until the separate implementation round lands.

Injection points
----------------
* Task A injects at the atomic-commit call the implementation is expected to
  use for the same-directory temp-file + ``os.replace`` write (``os.replace``,
  or ``storage.<alias>`` if it is imported directly). A1 is therefore RED on
  current code, which appends directly with ``"a"`` and never calls
  ``os.replace``.
* Task B injects at ``call_llm._post`` (the existing transport seam) and
  asserts the frozen, secret-free ``error`` vocabulary
  (``structural-constraints.md §5``).

Offline and deterministic: no network, no real sleep, no real model call. All
files live under ``tmp_path``.
"""
import json
import os
import re

import pytest

from src import call_llm, storage


def _record(call_id="abc123", **overrides):
    rec = {
        "call_id": call_id,
        "amount": 350,
        "category": "food",
        "total": 350.0,
        "budget_limit": 1000.0,
        "decided_at": "2026-11-12T00:00:00Z",
    }
    rec.update(overrides)
    return rec


@pytest.fixture
def data_path(monkeypatch, tmp_path):
    path = tmp_path / "data" / "records.jsonl"
    monkeypatch.setattr(storage, "DATA_PATH", path)
    return path


@pytest.fixture
def log(monkeypatch, tmp_path):
    """Redirect LOG_PATH to tmp so the REAL log file is the subject under test.

    ``_append_log`` is intentionally NOT patched: B1/B2 must prove the secret
    never reaches the file the application actually writes.
    """
    path = tmp_path / "logs" / "llm_calls.jsonl"
    monkeypatch.setattr(call_llm, "LOG_PATH", path)
    monkeypatch.setattr(call_llm, "BASE_URL", "http://example.invalid")
    monkeypatch.setattr(call_llm, "API_KEY", "test-key")
    return path


# ---------------------------------------------------------------------------
# Task A - atomic storage append
# ---------------------------------------------------------------------------

def test_a1_failed_commit_leaves_original_bytes(data_path, monkeypatch):
    """A1 (expected RED): a mid-write failure must not change the existing file.

    Inject at the atomic-commit call (``os.replace``, or ``storage.<alias>``).
    Current code appends directly and never commits atomically, so the half
    line survives and the byte comparison fails.
    """
    storage.append_validated(_record(call_id="seed"))
    before = data_path.read_bytes()

    target = storage if hasattr(storage, "replace") else os
    def _boom(src, dst):
        raise OSError("simulated mid-write failure")

    monkeypatch.setattr(target, "replace", _boom)

    second = _record(call_id="second", amount=50, total=400.0)
    with pytest.raises(storage.StorageError):
        storage.append_validated(second)

    after = data_path.read_bytes()
    assert after == before, (
        "original file changed after a failed commit; "
        "actual suffix=%r" % (after[len(before):],)
    )
    assert after.splitlines()[-1] == before.splitlines()[-1]


def test_a2_normal_append_one_object_per_line(data_path):
    """A2 (anchor): a normal append produces exactly one JSON object per line."""
    storage.append_validated(_record(call_id="a"))
    storage.append_validated(_record(call_id="b", amount=50, total=400.0))
    lines = data_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["call_id"] for line in lines] == ["a", "b"]


def test_a3_reader_fails_closed_on_partial_line(data_path):
    """A3 (anchor): the reader still fails closed on a partial final line."""
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text('{"call_id": "x", "amount": 3', encoding="utf-8")
    with pytest.raises(storage.StorageError):
        list(storage.iter_records())


# ---------------------------------------------------------------------------
# Task B - short, secret-safe ``error``
# ---------------------------------------------------------------------------

def _only_line(path):
    assert path.exists(), "log file was not created at %s" % (path,)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, "expected exactly one log line at %s, got %d" % (
        path, len(lines)
    )
    return json.loads(lines[0])


def test_b1_transport_failure_short_label_no_credential(log, monkeypatch):
    """B1 (expected RED): transport error is a short label, never the raw text."""
    def boom(payload):
        raise call_llm.LlmTransportError(
            "transport: read timed out to https://user:pass@gw.example/v1?key=sk-secret"
        )

    monkeypatch.setattr(call_llm, "_post", boom)

    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("hotpot last night cost 350")

    rec = _only_line(log)
    assert rec["error"] == "transport: read timeout (LlmTransportError)"
    text = log.read_text(encoding="utf-8")
    assert "sk-secret" not in text
    assert "user:pass" not in text
    assert "https://" not in text


def test_b2_http_failure_short_label_body_not_copied(log, monkeypatch):
    """B2 (expected RED): HTTP error is a short label; the body is not copied."""
    def boom(payload):
        raise call_llm.LlmTransportError(
            "http 503: secret body",
            status_code=503,
            body="sk-secret and https://gw/x",
        )

    monkeypatch.setattr(call_llm, "_post", boom)

    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("hotpot last night cost 350")

    rec = _only_line(log)
    assert rec["error"] == "http 503 (LlmTransportError)"
    text = log.read_text(encoding="utf-8")
    assert "sk-secret" not in text
    assert "https://" not in text


_VOCAB = re.compile(
    r"(not_json|http \d{3} \([A-Za-z]+\)|transport: [a-z ]+ \([A-Za-z]+\))"
)


def _error_from_transport(monkeypatch, exc):
    log = []
    monkeypatch.setattr(call_llm, "_append_log", log.append)
    monkeypatch.setattr(call_llm, "BASE_URL", "http://example.invalid")
    monkeypatch.setattr(call_llm, "API_KEY", "test-key")
    monkeypatch.setattr(call_llm, "_post", lambda payload: (_ for _ in ()).throw(exc))
    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("x")
    return log[0]["error"]


def test_b3_error_vocabulary_is_closed(monkeypatch):
    """B3 (expected RED): the ``error`` vocabulary is closed.

    This uses the in-memory ``_append_log`` replacement on purpose: it tests
    the error-value vocabulary, not file secrecy (B1/B2 own the on-disk check).
    """
    transport = _error_from_transport(
        monkeypatch,
        call_llm.LlmTransportError(
            "transport: read timed out to https://user:pass@gw.example/v1?key=sk-secret"
        ),
    )
    http = _error_from_transport(
        monkeypatch,
        call_llm.LlmTransportError(
            "http 503: secret body",
            status_code=503,
            body="sk-secret and https://gw/x",
        ),
    )
    assert re.fullmatch(_VOCAB, transport), transport
    assert re.fullmatch(_VOCAB, http), http
    assert re.fullmatch(_VOCAB, "not_json")


def test_b4_config_failure_keeps_short_code(log, monkeypatch):
    """B4 (anchor): configuration failure keeps its existing short code."""
    monkeypatch.setattr(call_llm, "BASE_URL", "")
    monkeypatch.setattr(call_llm, "API_KEY", "")

    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("x")

    rec = _only_line(log)
    assert rec["error"] == "config: missing base url or key"
    assert rec["request_made"] is False
