"""Smoke test for the call_llm transport seam (task sheet v2 §2/§3; role D).

Offline and deterministic: _post is monkeypatched, _append_log is redirected to
a tmp file. No network access.
"""
import json

import pytest

from src import call_llm, pipeline, policy_core, storage


@pytest.fixture
def captured_log(monkeypatch, tmp_path):
    lines = []
    monkeypatch.setattr(call_llm, "_append_log", lines.append)
    monkeypatch.setattr(call_llm, "BASE_URL", "http://example.invalid")
    monkeypatch.setattr(call_llm, "API_KEY", "test-key")
    monkeypatch.setattr(storage, "DATA_PATH", tmp_path / "data" / "records.jsonl")
    return lines


def test_seam_returns_parsed_object_and_logs_once(captured_log, monkeypatch):
    monkeypatch.setattr(call_llm, "_post", lambda payload: ('{"amount": 350, "category": "food"}', None))
    result = call_llm.extract("hotpot 350")
    assert result["amount"] == 350
    assert result["category"] == "food"
    call_id = result["__call_id__"]
    assert isinstance(call_id, str) and len(call_id) == 32
    int(call_id, 16)  # raises ValueError if not 32-char hex
    assert len(captured_log) == 1
    rec = captured_log[0]
    assert set(rec) >= {"input", "raw", "parsed", "call_id"}
    assert rec["call_id"] == call_id


def test_seam_non_json_is_logged_then_reraised(captured_log, monkeypatch):
    monkeypatch.setattr(call_llm, "_post", lambda payload: ("not json", None))
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
    def fake_extract(text, request_id=None):
        return dict(raw, __call_id__="abc123def456")
    monkeypatch.setattr(call_llm, "extract", fake_extract)

    with pytest.raises(policy_core.PolicyError) as exc:
        pipeline.process("x", spent, budget)
    assert exc.value.code == expected_error

    lines = review_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert set(record) == {"call_id", "request_id", "error", "amount",
                           "category", "spent", "total", "review"}
    assert record["call_id"] == "abc123def456"
    assert record["error"] == expected_error
    assert record["review"] is expected_review
    assert captured_log == []



def test_seam_success_call_id_joins_log_and_record(captured_log, monkeypatch):
    monkeypatch.setattr(
        call_llm, "_post",
        lambda payload: ('{"amount": 350, "category": "food"}', None),
    )
    record = pipeline.process("hotpot 350", 0.0, 1000.0)
    assert set(record) == set(storage.REQUIRED_FIELDS)
    assert "__call_id__" not in record
    assert record["amount"] == 350
    assert record["category"] == "food"
    assert record["total"] == 350.0
    assert record["budget_limit"] == 1000.0
    assert len(captured_log) == 1
    assert record["call_id"] == captured_log[0]["call_id"]
    stored = list(storage.iter_records())
    assert len(stored) == 1
    assert stored[0] == record


def test_process_without_call_id_raises_storage_error(captured_log, monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "REVIEW_PATH", tmp_path / "review.jsonl")
    monkeypatch.setattr(
        call_llm, "extract",
        lambda text, request_id=None: {"amount": 350, "category": "food"},
    )

    with pytest.raises(storage.StorageError):
        pipeline.process("x", 0.0, 1000.0)


def test_rejection_write_failure_raises_storage_error_not_policy(
    captured_log, monkeypatch, tmp_path,
):
    blocked = tmp_path / "adir"
    blocked.mkdir()
    monkeypatch.setattr(pipeline, "REVIEW_PATH", blocked)
    monkeypatch.setattr(
        call_llm, "extract",
        lambda text, request_id=None: {"amount": 350, "category": "Food", "__call_id__": "abc123def456"},
    )
    with pytest.raises(storage.StorageError) as exc:
        pipeline.process("x", 0.0, 1000.0)
    assert not isinstance(exc.value, policy_core.PolicyError)


def test_private_key_is_popped_before_validation(captured_log, monkeypatch, tmp_path):
    seen = {}

    def spy_validate(raw, spent, budget):
        seen["raw"] = dict(raw)
        return {"amount": raw.get("amount"), "category": raw.get("category"),
                "total": spent + raw.get("amount")}

    monkeypatch.setattr(pipeline.policy_core, "validate_record", spy_validate)
    monkeypatch.setattr(
        call_llm, "extract",
        lambda text, request_id=None: {"amount": 350, "category": "food", "__call_id__": "abc123def456"},
    )
    pipeline.process("x", 0.0, 1000.0)
    assert "__call_id__" not in seen["raw"]


def test_process_reads_running_total_from_storage(captured_log, monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DATA_PATH", tmp_path / "records.jsonl")
    storage.append_validated({
        "call_id": "seed00000001", "amount": 990, "category": "food",
        "total": 990.0, "budget_limit": 1000.0, "decided_at": "2026-11-12T00:00:00Z",
    })
    monkeypatch.setattr(
        call_llm, "extract",
        lambda text, request_id=None: {"amount": 20, "category": "food", "__call_id__": "abc123def456"},
    )
    with pytest.raises(policy_core.PolicyError) as exc:
        pipeline.process("x", budget_limit=1000.0)
    assert exc.value.code == "policy:budget"


def test_process_without_spent_passes_persisted_as_expected_spent(
    captured_log, monkeypatch, tmp_path,
):
    monkeypatch.setattr(storage, "DATA_PATH", tmp_path / "records.jsonl")
    storage.append_validated({
        "call_id": "seed00000001", "amount": 500, "category": "food",
        "total": 500.0, "budget_limit": 1000.0, "decided_at": "2026-11-12T00:00:00Z",
    })
    seen = {}
    real = storage.append_validated

    def spy(record, expected_spent=None):
        seen["expected_spent"] = expected_spent
        return real(record, expected_spent=expected_spent)

    monkeypatch.setattr(storage, "append_validated", spy)
    monkeypatch.setattr(
        call_llm, "extract",
        lambda text, request_id=None: {"amount": 100, "category": "food", "__call_id__": "abc123def456"},
    )
    pipeline.process("x", budget_limit=1000.0)
    assert seen["expected_spent"] == 500.0
    assert storage.current_total() == 600.0


def test_process_explicit_spent_over_budget_is_policy_not_storage_error(
    captured_log, monkeypatch, tmp_path,
):
    monkeypatch.setattr(storage, "DATA_PATH", tmp_path / "records.jsonl")
    monkeypatch.setattr(pipeline, "REVIEW_PATH", tmp_path / "review.jsonl")
    monkeypatch.setattr(
        call_llm, "extract",
        lambda text, request_id=None: {"amount": 20, "category": "food", "__call_id__": "abc123def456"},
    )
    with pytest.raises(policy_core.PolicyError) as exc:
        pipeline.process("x", 990.0, 1000.0)
    assert exc.value.code == "policy:budget"
    assert not isinstance(exc.value, storage.StorageError)


def test_process_default_budget_limit_is_1000(captured_log, monkeypatch):
    monkeypatch.setattr(
        call_llm, "extract",
        lambda text, request_id=None: {"amount": 350, "category": "food", "__call_id__": "abc123def456"},
    )
    record = pipeline.process("x")
    assert record["budget_limit"] == 1000.0


def test_decided_at_is_utc_iso_seconds(captured_log, monkeypatch):
    from datetime import datetime
    monkeypatch.setattr(
        call_llm, "extract",
        lambda text, request_id=None: {"amount": 350, "category": "food", "__call_id__": "abc123def456"},
    )
    record = pipeline.process("x")
    parsed = datetime.fromisoformat(record["decided_at"])
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0
    assert parsed.microsecond == 0


def test_storage_error_from_persist_propagates(captured_log, monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DATA_PATH", tmp_path / "records.jsonl")
    storage.append_validated({
        "call_id": "abc123def456", "amount": 1, "category": "food",
        "total": 1.0, "budget_limit": 1000.0, "decided_at": "2026-11-12T00:00:00Z",
    })
    monkeypatch.setattr(
        call_llm, "extract",
        lambda text, request_id=None: {"amount": 350, "category": "food", "__call_id__": "abc123def456"},
    )
    with pytest.raises(storage.StorageError):
        pipeline.process("x", 0.0, 1000.0)


def test_rejection_is_evidence_only_never_persisted(captured_log, monkeypatch, tmp_path):
    review_path = tmp_path / "review.jsonl"
    data_path = tmp_path / "data" / "records.jsonl"
    monkeypatch.setattr(pipeline, "REVIEW_PATH", review_path)
    monkeypatch.setattr(storage, "DATA_PATH", data_path)
    monkeypatch.setattr(
        call_llm, "_post",
        lambda payload: ('{"amount": 350, "category": "Food"}', None),
    )

    with pytest.raises(policy_core.PolicyError) as exc:
        pipeline.process("x", 0.0, 1000.0)
    assert exc.value.code == "policy:category"

    # (a) exactly one review line
    review_lines = review_path.read_text(encoding="utf-8").splitlines()
    assert len(review_lines) == 1
    rejection = json.loads(review_lines[0])

    # (b) storage untouched / never created
    assert not data_path.exists()

    # (c) call line exists and carries a non-empty call_id == rejection's
    assert len(captured_log) == 1
    call_line = captured_log[0]
    assert rejection["call_id"]
    assert rejection["call_id"] == call_line["call_id"]

    # (d) rejection carries the request_id generated for this process() call
    assert rejection["request_id"] == call_line["request_id"]
    assert rejection["request_id"]


def test_request_id_generated_once_per_process(captured_log, monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "REVIEW_PATH", tmp_path / "review.jsonl")
    monkeypatch.setattr(storage, "DATA_PATH", tmp_path / "records.jsonl")
    monkeypatch.setattr(
        call_llm, "_post",
        lambda payload: ('{"amount": 350, "category": "food"}', None),
    )
    record = pipeline.process("x", 0.0, 1000.0)
    first = captured_log[0]
    assert isinstance(first["request_id"], str) and len(first["request_id"]) == 32
    int(first["request_id"], 16)
    assert record["call_id"] == first["call_id"]
    assert first["request_id"] not in record.values()

    pipeline.process("y", 350.0, 1000.0)
    second = captured_log[1]
    assert second["request_id"] != first["request_id"]
    assert second["session_id"] == first["session_id"]
