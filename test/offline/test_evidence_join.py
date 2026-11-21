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

import concurrent.futures
import json
import pathlib
import tempfile
import threading
import uuid

import pytest
import requests

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
    "payload,expected_error,expected_review,budget_limit",
    [
        ('{"amount": -1, "category": "food"}', "policy:amount", False, 1000.0),
        ('{"amount": 350, "category": "Food"}', "policy:category", True, 1000.0),
        ('{"amount": 20, "category": "food"}', "policy:budget", True, 110.0),
    ],
    ids=["inv001-amount", "inv002-category", "inv003-budget"],
)
def test_rejection_joins_review_and_leaves_storage_unchanged(
    isolated, monkeypatch, payload, expected_error, expected_review, budget_limit,
):
    # Prior record established by a REAL acceptance (persisted spend == 100).
    seed = _seed_record(isolated, monkeypatch)
    assert seed["amount"] == 100
    before = storage.DATA_PATH.read_bytes()

    # Continue from the persisted total: budget case trips for real at limit 110.
    spent = storage.current_total() if expected_error == "policy:budget" else 0.0
    monkeypatch.setattr(call_llm, "_post", _fake_post(payload))

    with pytest.raises(policy_core.PolicyError) as exc:
        pipeline.process("x", spent=spent, budget_limit=budget_limit)
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

    # Business fields are redacted even though all three policy reasons are retained.
    assert all(review[field] is None for field in ("amount", "category", "spent", "total"))


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

    # Snapshot the ledger directory so residue from the failed append is provable.
    ledger_parent = storage.DATA_PATH.parent
    before_files = {p.name for p in ledger_parent.iterdir()}

    monkeypatch.setattr(
        call_llm, "_post", _fake_post('{"amount": 5, "category": "food"}'),
    )

    orig_mkstemp = tempfile.mkstemp
    target_dir = str(ledger_parent)
    target_prefix = storage.DATA_PATH.name + "."
    hits = []

    def blocking_mkstemp(*args, **kwargs):
        if (
            kwargs.get("dir") == target_dir
            and kwargs.get("prefix") == target_prefix
            and kwargs.get("suffix") == ".tmp"
        ):
            hits.append("mkstemp")
            raise OSError("simulated append-open failure")
        return orig_mkstemp(*args, **kwargs)

    monkeypatch.setattr(tempfile, "mkstemp", blocking_mkstemp)
    with pytest.raises(storage.StorageError) as exc:
        pipeline.process("y", spent=100.0, budget_limit=1000.0)

    # Exactly one fault injection for the records-file temp create.
    assert len(hits) == 1, hits
    assert isinstance(exc.value.__cause__, OSError)
    assert str(exc.value.__cause__) == "simulated append-open failure"
    assert storage.DATA_PATH.read_bytes() == before
    # No temp-file residue left behind in the ledger directory.
    after_files = {p.name for p in ledger_parent.iterdir()}
    assert after_files == before_files
    assert not any(
        name.startswith(target_prefix) and name.endswith(".tmp")
        for name in after_files
    )
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


# ---------------------------------------------------------------------------
# Log redaction: the user text and the model's raw response are never written
# verbatim; only a length descriptor is kept. Proven by synthetic markers
# (URL / credential / path / CJK) that must be absent from the COMPLETE log.
# ---------------------------------------------------------------------------

_URL_MARKER = "https://示例.example/支付?token=abc"
_CRED_MARKER = "sk-synthetic-DEADBEEF0123456789"
_PATH_MARKER = "/home/synthetic/private/家长账单.json"
_RAW_PAYLOAD = '{"amount":8421.37,"category":"food"} '


def _sensitive_text():
    return (
        "我在 " + _URL_MARKER + " 用凭证 " + _CRED_MARKER
        + " 保存到 " + _PATH_MARKER + " 买了晚饭"
    )


def _assert_markers_absent(blob):
    for marker in (_URL_MARKER, _CRED_MARKER, _PATH_MARKER, "8421.37", "food"):
        assert marker not in blob


def _redacted(text):
    return "redacted:len=" + str(len(text))


def test_acceptance_log_redacts_input_and_raw(isolated, monkeypatch):
    text = _sensitive_text()
    monkeypatch.setattr(
        call_llm, "_post",
        _fake_post(_RAW_PAYLOAD,
                   {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
    )

    record = pipeline.process(text, spent=0.0, budget_limit=10000.0)

    stored = _read_jsonl(storage.DATA_PATH)
    assert len(stored) == 1
    assert stored[0] == record
    assert record["amount"] == 8421.37
    assert record["category"] == "food"
    assert record["budget_limit"] == 10000.0
    assert record["total"] == 8421.37
    _assert_call_id(record["call_id"])

    # No review line: a valid record is accepted, not flagged.
    assert _read_jsonl(pipeline.REVIEW_PATH) == []

    calls = _read_jsonl(call_llm.LOG_PATH)
    assert len(calls) == 1
    line = calls[0]
    assert set(line) == TEN_KEYS

    # Redaction: only a length descriptor survives for input and raw.
    assert line["input"] == _redacted(text)
    assert line["raw"] == _redacted(_RAW_PAYLOAD)
    assert line["parsed"] is None
    assert line["error"] is None

    # Correlation survives redaction.
    _assert_call_id(line["call_id"])
    _assert_call_id(line["request_id"])
    assert record["call_id"] == line["call_id"]

    # The COMPLETE log (every key, every line) carries no marker.
    _assert_markers_absent(call_llm.LOG_PATH.read_text(encoding="utf-8"))
    _assert_markers_absent(json.dumps(calls, ensure_ascii=False))


def test_rejection_log_redacts_and_writes_original_policy_code(isolated, monkeypatch):
    text = _sensitive_text()
    monkeypatch.setattr(call_llm, "_post", _fake_post(_RAW_PAYLOAD))

    # 8421.37 exceeds a 1-unit budget: real INV-003 rejection.
    with pytest.raises(policy_core.PolicyError) as exc:
        pipeline.process(text, spent=0.0, budget_limit=1.0)
    assert exc.value.code == "policy:budget"
    assert exc.value.review is True

    # Rejection is evidence, not state.
    assert _read_jsonl(storage.DATA_PATH) == []

    reviews = _read_jsonl(pipeline.REVIEW_PATH)
    assert len(reviews) == 1
    review = reviews[0]

    calls = _read_jsonl(call_llm.LOG_PATH)
    assert len(calls) == 1
    line = calls[0]

    assert set(line) == TEN_KEYS
    assert line["input"] == _redacted(text)
    assert line["raw"] == _redacted(_RAW_PAYLOAD)
    assert line["parsed"] is None
    assert line["error"] is None

    # Exactly eight keys on the review line; joins the llm log by both ids.
    assert set(review) == {
        "call_id", "request_id", "error",
        "amount", "category", "spent", "total", "review",
    }
    _assert_call_id(review["call_id"])
    _assert_call_id(review["request_id"])
    assert review["call_id"] == line["call_id"]
    assert review["request_id"] == line["request_id"]

    # ORIGINAL policy code survives; the four numeric fields are null.
    assert review["error"] == "policy:budget"
    assert review["review"] is True
    assert review["amount"] is None
    assert review["category"] is None
    assert review["spent"] is None
    assert review["total"] is None

    # No marker leaks into either evidence file.
    _assert_markers_absent(call_llm.LOG_PATH.read_text(encoding="utf-8"))
    _assert_markers_absent(pipeline.REVIEW_PATH.read_text(encoding="utf-8"))


def test_malformed_response_logs_short_not_json_and_redacts_texts(isolated, monkeypatch):
    text = _sensitive_text()
    # A real malformed Unicode string: not parseable JSON, so json raises.
    malformed = "无效 " + _CRED_MARKER + _PATH_MARKER
    monkeypatch.setattr(call_llm, "_post", _fake_post(malformed))

    with pytest.raises(json.JSONDecodeError):
        pipeline.process(text, spent=0.0, budget_limit=1000.0)

    assert _read_jsonl(storage.DATA_PATH) == []
    assert _read_jsonl(pipeline.REVIEW_PATH) == []

    calls = _read_jsonl(call_llm.LOG_PATH)
    assert len(calls) == 1
    line = calls[0]
    assert set(line) == TEN_KEYS

    assert line["error"] == "not_json"
    assert line["parsed"] is None
    assert line["input"] == _redacted(text)
    assert line["raw"] == _redacted(malformed)
    _assert_call_id(line["call_id"])
    _assert_call_id(line["request_id"])

    _assert_markers_absent(call_llm.LOG_PATH.read_text(encoding="utf-8"))
    assert not pipeline.REVIEW_PATH.exists()


_SYNTHETIC_CONTENT = '{"amount":10,"category":"food"}'


def _coordinate_extraction(monkeypatch):
    real_extract = call_llm.extract
    lock = threading.Lock()
    barrier = threading.Barrier(2, timeout=8)

    monkeypatch.setattr(call_llm, "_post", _fake_post(_SYNTHETIC_CONTENT))

    def coordinated(text, request_id=None):
        with lock:
            result = real_extract(text, request_id=request_id)
        barrier.wait()
        return result

    monkeypatch.setattr(call_llm, "extract", coordinated)


@pytest.mark.parametrize(("limit", "broken_review"), [(120, False), (110, False), (110, True)])
def test_concurrent_pipeline_budget_uses_persisted_total(isolated, monkeypatch, limit, broken_review):
    seed = _seed_record(isolated, monkeypatch)
    assert seed["amount"] == 100
    hits = []
    if broken_review:
        review_path = pathlib.Path(pipeline.REVIEW_PATH)
        orig_open = pathlib.Path.open

        def broken_open(path_self, mode="r", *args, **kwargs):
            if pathlib.Path(path_self) == review_path and "a" in mode:
                hits.append(path_self)
                raise OSError("simulated review append failure")
            return orig_open(path_self, mode, *args, **kwargs)

        monkeypatch.setattr(pathlib.Path, "open", broken_open)
    _coordinate_extraction(monkeypatch)

    def run(_):
        try:
            return pipeline.process("coffee", spent=100, budget_limit=limit)
        except (policy_core.PolicyError, storage.StorageError) as exc:
            return exc

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))

    stored = _read_jsonl(storage.DATA_PATH)
    assert stored[0] == seed
    ok = [r for r in results if isinstance(r, dict)]
    errs = [r for r in results if isinstance(r, Exception)]
    assert sorted(r["total"] for r in stored[1:]) == ([110, 120] if limit == 120 else [110])
    assert sorted(r["total"] for r in ok) == sorted(r["total"] for r in stored[1:])
    assert len(ok) == len(stored) - 1
    assert {r["call_id"] for r in ok} == {r["call_id"] for r in stored[1:]}
    calls = _read_jsonl(call_llm.LOG_PATH)
    assert len(calls) == 3
    assert len({c["call_id"] for c in calls}) == 3
    assert {r["call_id"] for r in ok} <= {c["call_id"] for c in calls[1:]}
    assert len({c["request_id"] for c in calls[1:]}) == 2

    if limit == 120:
        assert not errs and _read_jsonl(pipeline.REVIEW_PATH) == []
        return
    assert len(errs) == 1
    if broken_review:
        assert isinstance(errs[0], storage.StorageError)
        assert len(hits) == 1
        assert _read_jsonl(pipeline.REVIEW_PATH) == []
        return
    exc = errs[0]
    assert isinstance(exc, policy_core.PolicyError)
    assert exc.code == "policy:budget" and exc.review is True
    reviews = _read_jsonl(pipeline.REVIEW_PATH)
    assert len(reviews) == 1
    review = reviews[0]
    assert review["error"] == "policy:budget" and review["review"] is True
    loser = {c["call_id"] for c in calls[1:]} - {r["call_id"] for r in ok}
    assert {review["call_id"]} == loser
    assert review["request_id"] == next(c["request_id"] for c in calls if c["call_id"] == review["call_id"])
    assert all(review[f] is None for f in ("amount", "category", "spent", "total"))


def test_phase4_stale_high_spent_uses_fresh_total(isolated, monkeypatch):
    _seed_record(isolated, monkeypatch)
    monkeypatch.setattr(call_llm, "_post", _fake_post(_SYNTHETIC_CONTENT))
    record = pipeline.process("coffee", spent=9999, budget_limit=110)
    assert record["total"] == 110.0
    assert _read_jsonl(storage.DATA_PATH)[1]["call_id"] == record["call_id"]


@pytest.mark.parametrize("site", ["ledger", "review"])
def test_public_storage_error_redacts_io_details(isolated, monkeypatch, site):
    _seed_record(isolated, monkeypatch)
    before = storage.DATA_PATH.read_bytes()
    monkeypatch.setattr(call_llm, "_post", _fake_post('{"amount": 10.25, "category": "food"}'))
    markers = ("/mock/private/ledger", "https://audit.invalid/token",
               "SYNTH_AUDIT_CREDENTIAL", "SYNTH_RESPONSE_BODY", "10.25", "food")
    fault = OSError(" ".join(markers))
    hits = []

    if site == "ledger":
        orig = tempfile.mkstemp

        def raiser(*a, **kw):
            if kw.get("dir") == str(storage.DATA_PATH.parent) and kw.get("prefix") == storage.DATA_PATH.name + ".":
                hits.append("ledger")
                raise fault
            return orig(*a, **kw)

        monkeypatch.setattr(tempfile, "mkstemp", raiser)
        budget = 200
    else:
        orig = pathlib.Path.open

        def raiser(self, mode="r", *a, **kw):
            if self == pipeline.REVIEW_PATH and "a" in mode:
                hits.append("review")
                raise fault
            return orig(self, mode, *a, **kw)

        monkeypatch.setattr(pathlib.Path, "open", raiser)
        budget = 101

    with pytest.raises(storage.StorageError) as exc:
        pipeline.process("audit", spent=100, budget_limit=budget)

    assert len(hits) == 1, hits
    assert storage.DATA_PATH.read_bytes() == before
    assert not pipeline.REVIEW_PATH.exists() or pipeline.REVIEW_PATH.stat().st_size == 0
    text = str(exc.value)
    assert text
    for marker in markers + (str(storage.DATA_PATH), str(pipeline.REVIEW_PATH)):
        assert marker not in text
    log_text = call_llm.LOG_PATH.read_text(encoding="utf-8")
    for marker in markers[:4]:
        assert marker not in log_text


_FAKE_MARKER = "合成异常响应体-42-" + _CRED_MARKER


class _FakeResponse:
    def __init__(self, status, content):
        self.status_code = status
        self.encoding = "utf-8"
        self._content = content

    @property
    def text(self):
        return self._content.decode("utf-8")

    def json(self):
        return json.loads(self.text)


def _failure_post(kind):
    if kind == "timeout":
        def _p(payload):
            raise requests.exceptions.ReadTimeout("read timeout " + _FAKE_MARKER)
        return _p
    if kind == "http":
        return lambda payload: _FakeResponse(503, _FAKE_MARKER.encode("utf-8"))
    if kind == "protocol":
        body = '{"body": "%s", "choices": []}' % _FAKE_MARKER
        return lambda payload: _FakeResponse(200, body.encode("utf-8"))
    raise AssertionError("unknown kind")


@pytest.mark.parametrize(
    "kind,error,request_made,makes_request",
    [
        ("config", "config: missing base url or key", False, False),
        ("timeout", "transport: read timeout (LlmTransportError)", True, True),
        ("http", "http 503 (LlmTransportError)", True, True),
        ("protocol", "transport: other (LlmTransportError)", True, True),
    ],
    ids=["config-missing-key", "transport-read-timeout", "http-503", "protocol-missing-choices"],
)
def test_transport_failure_redacts_and_logs_one_line(
    isolated, monkeypatch, kind, error, request_made, makes_request,
):
    text = "8421.37 food " + _sensitive_text()
    request_id = uuid.uuid4().hex
    seen = []

    def spy_post(*args, **kwargs):
        seen.append(args)
        return _failure_post(kind)(None)

    monkeypatch.setattr(call_llm.requests, "post", spy_post)
    if kind == "config":
        monkeypatch.setattr(call_llm, "API_KEY", "")

    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract(text, request_id=request_id)

    assert len(seen) == (1 if makes_request else 0)

    blob = call_llm.LOG_PATH.read_text(encoding="utf-8")
    lines = blob.splitlines()
    assert len(lines) == 1
    line = json.loads(lines[0])

    assert set(line) == TEN_KEYS
    assert line["error"] == error
    assert line["request_made"] is request_made
    assert line["parsed"] is None
    assert line["input"] == _redacted(text)
    assert line["request_id"] == request_id
    _assert_call_id(line["call_id"])

    # raw: None when no response text existed; EXACT length descriptor when a
    # response text was supplied to the log contract (http / protocol).
    if kind in ("config", "timeout"):
        assert line["raw"] is None
    else:
        body = _failure_post(kind)(None).text
        assert line["raw"] == _redacted(body)

    for marker in (_FAKE_MARKER, _URL_MARKER, _PATH_MARKER, _CRED_MARKER, "8421.37", "food"):
        assert marker not in blob
    decoded = json.dumps(line, ensure_ascii=False)
    for marker in (_FAKE_MARKER, _URL_MARKER, _PATH_MARKER, _CRED_MARKER, "8421.37", "food"):
        assert marker not in decoded
