"""Smoke test for the call_llm transport seam (task sheet v2 §2/§3; role D).

Offline and deterministic: _post is monkeypatched, _append_log is redirected to
a tmp file. No network access.
"""
import json

import pytest

from src import call_llm, pipeline, policy_core


@pytest.fixture
def captured_log(monkeypatch, tmp_path):
    lines = []
    monkeypatch.setattr(call_llm, "_append_log", lines.append)
    monkeypatch.setattr(call_llm, "BASE_URL", "http://example.invalid")
    monkeypatch.setattr(call_llm, "API_KEY", "test-key")
    return lines


def test_seam_returns_parsed_object_and_logs_once(captured_log, monkeypatch):
    monkeypatch.setattr(call_llm, "_post", lambda payload: '{"amount": 350, "category": "food"}')
    result = call_llm.extract("hotpot 350")
    assert result == {"amount": 350, "category": "food"}
    assert len(captured_log) == 1
    rec = captured_log[0]
    assert set(rec) >= {"input", "raw", "parsed"}


def test_seam_non_json_is_logged_then_reraised(captured_log, monkeypatch):
    monkeypatch.setattr(call_llm, "_post", lambda payload: "not json")
    with pytest.raises(json.JSONDecodeError):
        call_llm.extract("x")
    assert len(captured_log) == 1
    assert captured_log[0]["error"] == "not_json"


def test_seam_transport_error_logs_once(captured_log, monkeypatch):
    def boom(payload):
        raise call_llm.LlmTransportError("transport: boom")

    monkeypatch.setattr(call_llm, "_post", boom)
    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("x")
    assert len(captured_log) == 1
    assert captured_log[0]["input"] == "x"


def test_config_error_logs_once(captured_log, monkeypatch):
    monkeypatch.setattr(call_llm, "BASE_URL", "")
    monkeypatch.setattr(call_llm, "API_KEY", "")
    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("x")
    assert len(captured_log) == 1
    assert captured_log[0]["error"] == "config: missing base url or key"


def test_post_raises_on_malformed_envelope(monkeypatch):
    class FakeResp:
        status_code = 200

        def json(self):
            return {"unexpected": True}

    monkeypatch.setattr(call_llm.requests, "post", lambda *a, **kw: FakeResp())
    monkeypatch.setattr(call_llm, "BASE_URL", "http://example.invalid")
    monkeypatch.setattr(call_llm, "API_KEY", "k")
    with pytest.raises(call_llm.LlmTransportError):
        call_llm._post({})


@pytest.mark.parametrize(
    "raw,spent,budget,expected_error,expected_review",
    [
        ({"amount": -1, "category": "food"}, 0.0, 1000.0, "policy:amount", False),
        ({"amount": 350, "category": "Food"}, 0.0, 1000.0, "policy:category", True),
        ({"amount": 20, "category": "food"}, 990.0, 1000.0, "policy:budget", True),
    ],
    ids=["inv001-amount", "inv002-category", "inv003-budget"],
)
def test_policy_rejection_writes_one_review_line(
    captured_log, monkeypatch, tmp_path,
    raw, spent, budget, expected_error, expected_review,
):
    review_path = tmp_path / "review.jsonl"
    monkeypatch.setattr(pipeline, "REVIEW_PATH", review_path)
    monkeypatch.setattr(call_llm, "extract", lambda text: raw)

    with pytest.raises(policy_core.PolicyError) as exc:
        pipeline.process("x", spent, budget)
    assert exc.value.code == expected_error

    lines = review_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert set(record) == {"error", "amount", "category", "spent", "total", "review"}
    assert record["error"] == expected_error
    assert record["review"] is expected_review
    assert captured_log == []

