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
    assert result["amount"] == 350
    assert result["category"] == "food"
    call_id = result["__call_id__"]
    assert isinstance(call_id, str) and len(call_id) == 12
    int(call_id, 16)  # raises ValueError if not 12-char hex
    assert len(captured_log) == 1
    rec = captured_log[0]
    assert set(rec) >= {"input", "raw", "parsed", "call_id"}
    assert rec["call_id"] == call_id


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
    assert "call_id" in captured_log[0]


def test_config_error_logs_once(captured_log, monkeypatch):
    monkeypatch.setattr(call_llm, "BASE_URL", "")
    monkeypatch.setattr(call_llm, "API_KEY", "")
    with pytest.raises(call_llm.LlmTransportError):
        call_llm.extract("x")
    assert len(captured_log) == 1
    assert captured_log[0]["error"] == "config: missing base url or key"
    assert "call_id" in captured_log[0]


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
    def fake_extract(text):
        return dict(raw, __call_id__="abc123def456")
    monkeypatch.setattr(call_llm, "extract", fake_extract)

    with pytest.raises(policy_core.PolicyError) as exc:
        pipeline.process("x", spent, budget)
    assert exc.value.code == expected_error

    lines = review_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert set(record) == {"call_id", "error", "amount", "category",
                           "spent", "total", "review"}
    assert record["call_id"] == "abc123def456"
    assert record["error"] == expected_error
    assert record["review"] is expected_review
    assert captured_log == []



def test_seam_success_call_id_joins_log_and_record(captured_log, monkeypatch):
    monkeypatch.setattr(
        call_llm, "_post",
        lambda payload: '{"amount": 350, "category": "food"}',
    )
    record = pipeline.process("hotpot 350", 0.0, 1000.0)
    assert set(record) == {"amount", "category", "total"}
    assert "__call_id__" not in record
    assert len(captured_log) == 1
    assert record["amount"] == 350


def test_process_without_call_id_raises_storage_error(captured_log, monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "REVIEW_PATH", tmp_path / "review.jsonl")
    monkeypatch.setattr(
        call_llm, "extract",
        lambda text: {"amount": 350, "category": "food"},
    )
    from src import storage

    with pytest.raises(storage.StorageError):
        pipeline.process("x", 0.0, 1000.0)


def test_rejection_write_failure_raises_storage_error_not_policy(
    captured_log, monkeypatch, tmp_path,
):
    from src import storage

    blocked = tmp_path / "adir"
    blocked.mkdir()
    monkeypatch.setattr(pipeline, "REVIEW_PATH", blocked)
    monkeypatch.setattr(
        call_llm, "extract",
        lambda text: {"amount": 350, "category": "Food", "__call_id__": "abc123def456"},
    )
    with pytest.raises(storage.StorageError) as exc:
        pipeline.process("x", 0.0, 1000.0)
    assert not isinstance(exc.value, policy_core.PolicyError)


def test_private_key_is_popped_before_validation(captured_log, monkeypatch, tmp_path):
    seen = {}

    def spy_validate(raw, spent, budget):
        seen["raw"] = dict(raw)
        return {"amount": raw.get("amount"), "category": raw.get("category"),
                "total": 0.0}

    monkeypatch.setattr(pipeline.policy_core, "validate_record", spy_validate)
    monkeypatch.setattr(
        call_llm, "extract",
        lambda text: {"amount": 350, "category": "food", "__call_id__": "abc123def456"},
    )
    pipeline.process("x", 0.0, 1000.0)
    assert "__call_id__" not in seen["raw"]
