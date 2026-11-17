"""Token-usage capture tests for src/call_llm.py (task sheet v5.1 §3, Task A).

Offline and deterministic: _post is monkeypatched, _append_log is captured in
memory. No network access. Covers the six paths in the sheet's table plus the
cross-path consistency guard (sheet §5).
"""
import json

import pytest

from src import call_llm

NINE = {
    "call_id", "request_id", "session_id", "tokens", "usage_source",
    "request_made",
}
ORIGINAL_FOUR = {"input", "raw", "parsed", "error"}
TEN = (ORIGINAL_FOUR | NINE)


@pytest.fixture
def log(monkeypatch):
    lines = []
    monkeypatch.setattr(call_llm, "_append_log", lines.append)
    monkeypatch.setattr(call_llm, "BASE_URL", "http://example.invalid")
    monkeypatch.setattr(call_llm, "API_KEY", "test-key")
    return lines


def _ok_post(usage):
    return lambda payload: ('{"amount": 350, "category": "food"}', usage)


# --- per-path coverage ----------------------------------------------------

def test_config_failure_no_request(log, monkeypatch):
    monkeypatch.setattr(call_llm, "BASE_URL", "")
    monkeypatch.setattr(call_llm, "API_KEY", "")
    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("x")
    assert len(log) == 1
    rec = log[0]
    assert rec["request_made"] is False
    assert rec["usage_source"] == "missing"
    assert rec["tokens"] is None
    assert rec["error"] == "config: missing base url or key"


def test_transport_failure_request_made_no_usage(log, monkeypatch):
    def boom(payload):
        raise call_llm.LlmTransportError("transport: boom")

    monkeypatch.setattr(call_llm, "_post", boom)
    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("x")
    rec = log[0]
    assert rec["request_made"] is True
    assert rec["usage_source"] == "missing"
    assert rec["tokens"] is None


def test_non_200_request_made_no_usage(log, monkeypatch):
    class FakeResp:
        status_code = 500
        text = "err"

        def json(self):
            return {}

    monkeypatch.setattr(call_llm.requests, "post", lambda *a, **kw: FakeResp())
    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("x")
    rec = log[0]
    assert rec["request_made"] is True
    assert rec["tokens"] is None
    assert rec["usage_source"] == "missing"
    assert rec["error"] == "http 500: err"


def test_malformed_envelope_request_made_no_usage(log, monkeypatch):
    def bad(payload):
        raise call_llm.LlmTransportError("protocol: malformed response envelope")

    monkeypatch.setattr(call_llm, "_post", bad)
    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("x")
    rec = log[0]
    assert rec["request_made"] is True
    assert rec["tokens"] is None
    assert rec["usage_source"] == "missing"


def test_non_json_request_made_no_usage(log, monkeypatch):
    monkeypatch.setattr(call_llm, "_post", lambda payload: ("not json", None))
    with pytest.raises(json.JSONDecodeError):
        call_llm.extract("x")
    rec = log[0]
    assert rec["request_made"] is True
    assert rec["tokens"] is None
    assert rec["usage_source"] == "missing"
    assert rec["error"] == "not_json"


def test_success_without_usage(log, monkeypatch):
    monkeypatch.setattr(call_llm, "_post", _ok_post(None))
    call_llm.extract("x")
    rec = log[0]
    assert rec["request_made"] is True
    assert rec["tokens"] is None
    assert rec["usage_source"] == "missing"


def test_success_with_full_usage(log, monkeypatch):
    usage = {"input": 12, "output": 5, "total": 17}
    monkeypatch.setattr(call_llm, "_post", _ok_post(usage))
    call_llm.extract("x")
    rec = log[0]
    assert rec["request_made"] is True
    assert rec["usage_source"] == "gateway"
    assert rec["tokens"] == {"input": 12, "output": 5, "total": 17}


def test_success_with_partial_usage_keeps_known_values(log, monkeypatch):
    usage = {"input": 12, "output": None, "total": None}
    monkeypatch.setattr(call_llm, "_post", _ok_post(usage))
    call_llm.extract("x")
    rec = log[0]
    assert rec["request_made"] is True
    assert rec["usage_source"] == "partial"
    assert rec["tokens"] == {"input": 12, "output": None, "total": None}


# --- field contract -------------------------------------------------------

def test_all_ten_fields_present_on_success(log, monkeypatch):
    monkeypatch.setattr(call_llm, "_post",
                        _ok_post({"input": 1, "output": 2, "total": 3}))
    call_llm.extract("x")
    assert set(log[0]) == TEN


def test_failure_line_has_exactly_ten_keys(log, monkeypatch):
    def boom(payload):
        raise call_llm.LlmTransportError("transport: boom")

    monkeypatch.setattr(call_llm, "_post", boom)
    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("x")
    # raw/parsed/error are present (null where they do not apply), never dropped
    assert set(log[0]) == TEN


def test_ids_are_32_hex(log, monkeypatch):
    monkeypatch.setattr(call_llm, "_post", _ok_post(None))
    call_llm.extract("x")
    rec = log[0]
    for key in ("call_id", "request_id", "session_id"):
        assert isinstance(rec[key], str) and len(rec[key]) == 32
        int(rec[key], 16)


def test_session_id_stable_across_calls_request_id_differs(log, monkeypatch):
    monkeypatch.setattr(call_llm, "_post", _ok_post(None))
    call_llm.extract("a")
    call_llm.extract("b")
    assert log[0]["session_id"] == log[1]["session_id"] == call_llm.session_id()
    assert log[0]["request_id"] != log[1]["request_id"]
    assert log[0]["call_id"] != log[1]["call_id"]


def test_explicit_request_id_is_used(log, monkeypatch):
    monkeypatch.setattr(call_llm, "_post", _ok_post(None))
    call_llm.extract("a", request_id="r" * 32)
    assert log[0]["request_id"] == "r" * 32


def test_one_line_per_call_on_success(log, monkeypatch):
    monkeypatch.setattr(call_llm, "_post", _ok_post({"input": 1, "output": 2, "total": 3}))
    call_llm.extract("x")
    call_llm.extract("y")
    assert len(log) == 2


# --- _post usage mapping --------------------------------------------------

def _resp(envelope):
    class FakeResp:
        status_code = 200
        text = ""

        def json(self):
            return envelope

    return FakeResp()


def test_post_maps_usage(monkeypatch):
    env = {"choices": [{"message": {"content": "{}"}}],
           "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}}
    monkeypatch.setattr(call_llm.requests, "post", lambda *a, **kw: _resp(env))
    monkeypatch.setattr(call_llm, "BASE_URL", "http://example.invalid")
    monkeypatch.setattr(call_llm, "API_KEY", "k")
    content, usage = call_llm._post({})
    assert content == "{}"
    assert usage == {"input": 7, "output": 3, "total": 10}


def test_post_without_usage_returns_none(monkeypatch):
    env = {"choices": [{"message": {"content": "{}"}}]}
    monkeypatch.setattr(call_llm.requests, "post", lambda *a, **kw: _resp(env))
    monkeypatch.setattr(call_llm, "BASE_URL", "http://example.invalid")
    monkeypatch.setattr(call_llm, "API_KEY", "k")
    content, usage = call_llm._post({})
    assert usage is None


def test_post_partial_usage_unknown_keys_none(monkeypatch):
    env = {"choices": [{"message": {"content": "{}"}}],
           "usage": {"prompt_tokens": 7}}
    monkeypatch.setattr(call_llm.requests, "post", lambda *a, **kw: _resp(env))
    monkeypatch.setattr(call_llm, "BASE_URL", "http://example.invalid")
    monkeypatch.setattr(call_llm, "API_KEY", "k")
    _, usage = call_llm._post({})
    assert usage == {"input": 7, "output": None, "total": None}


def test_post_non_int_usage_becomes_null(monkeypatch):
    env = {"choices": [{"message": {"content": "{}"}}],
           "usage": {"prompt_tokens": "7", "completion_tokens": 3, "total_tokens": True}}
    monkeypatch.setattr(call_llm.requests, "post", lambda *a, **kw: _resp(env))
    monkeypatch.setattr(call_llm, "BASE_URL", "http://example.invalid")
    monkeypatch.setattr(call_llm, "API_KEY", "k")
    _, usage = call_llm._post({})
    assert usage == {"input": None, "output": 3, "total": None}


# --- cross-path consistency guard (sheet §5) ------------------------------

def _assert_consistent(rec):
    request_made = rec["request_made"]
    source = rec["usage_source"]
    tokens = rec["tokens"]
    if request_made is False:
        assert rec["error"].startswith("config")
    if source == "gateway":
        assert isinstance(tokens, dict)
        assert all(isinstance(v, int) and not isinstance(v, bool)
                   for v in tokens.values())
        assert len(tokens) == 3
    elif source == "partial":
        assert isinstance(tokens, dict)
        present = [v for v in tokens.values() if v is not None]
        missing = [v for v in tokens.values() if v is None]
        assert present and missing
    elif source == "missing":
        assert tokens is None
    else:
        raise AssertionError("unknown usage_source %r" % (source,))


def test_every_path_is_consistent(log, monkeypatch):
    cases = []

    # config (request_made False)
    monkeypatch.setattr(call_llm, "BASE_URL", "")
    monkeypatch.setattr(call_llm, "API_KEY", "")
    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("x")
    cases.append(log[0])

    # reset config
    monkeypatch.setattr(call_llm, "BASE_URL", "http://example.invalid")
    monkeypatch.setattr(call_llm, "API_KEY", "test-key")

    # transport (request_made True, missing)
    def boom(payload):
        raise call_llm.LlmTransportError("transport: boom")

    monkeypatch.setattr(call_llm, "_post", boom)
    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("x")
    cases.append(log[1])

    # success full
    monkeypatch.setattr(call_llm, "_post", _ok_post({"input": 1, "output": 2, "total": 3}))
    call_llm.extract("x")
    cases.append(log[2])

    # success partial
    monkeypatch.setattr(call_llm, "_post", _ok_post({"input": 1, "output": None, "total": None}))
    call_llm.extract("x")
    cases.append(log[3])

    # success without usage
    monkeypatch.setattr(call_llm, "_post", _ok_post(None))
    call_llm.extract("x")
    cases.append(log[4])

    for rec in cases:
        assert set(rec) == TEN
        _assert_consistent(rec)

    assert [c["request_made"] for c in cases] == [False, True, True, True, True]


def test_every_path_key_set_is_exactly_ten(log, monkeypatch):
    cases = []

    # 1. config (no request)
    monkeypatch.setattr(call_llm, "BASE_URL", "")
    monkeypatch.setattr(call_llm, "API_KEY", "")
    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("x")
    cases.append(("config", log[-1]))
    monkeypatch.setattr(call_llm, "BASE_URL", "http://example.invalid")
    monkeypatch.setattr(call_llm, "API_KEY", "test-key")

    # 2. non-200
    class FakeResp:
        status_code = 503
        text = "busy"

        def json(self):
            return {}

    monkeypatch.setattr(call_llm.requests, "post", lambda *a, **kw: FakeResp())
    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("x")
    cases.append(("non-200", log[-1]))

    # 3. malformed envelope (protocol)
    def proto(payload):
        raise call_llm.LlmTransportError("protocol: malformed response envelope")

    monkeypatch.setattr(call_llm, "_post", proto)
    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("x")
    cases.append(("protocol", log[-1]))

    # 4. non-JSON
    monkeypatch.setattr(call_llm, "_post", lambda payload: ("not json", None))
    with pytest.raises(json.JSONDecodeError):
        call_llm.extract("x")
    cases.append(("non-json", log[-1]))

    # 5. success without usage
    monkeypatch.setattr(call_llm, "_post", _ok_post(None))
    call_llm.extract("x")
    cases.append(("success-no-usage", log[-1]))

    # 6. success with full usage
    monkeypatch.setattr(call_llm, "_post",
                        _ok_post({"input": 1, "output": 2, "total": 3}))
    call_llm.extract("x")
    cases.append(("success-full", log[-1]))

    for name, rec in cases:
        assert set(rec) == TEN, "%s key set: %r" % (name, set(rec))
