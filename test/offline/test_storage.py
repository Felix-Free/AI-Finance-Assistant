"""Offline tests for src/storage.py (task sheet v4 §2, §7 acceptance 3 & 4).

Every test redirects storage.DATA_PATH into tmp_path, never data/records.jsonl.
No network access.
"""
import json

import pytest

from src import storage


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


def test_append_validated_writes_one_line(data_path):
    storage.append_validated(_record())
    lines = data_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["call_id"] == "abc123"


def test_append_validated_creates_parent_directory(data_path):
    assert not data_path.parent.exists()
    storage.append_validated(_record())
    assert data_path.exists()


def test_append_validated_rejects_duplicate_call_id(data_path):
    storage.append_validated(_record())
    before = data_path.read_text(encoding="utf-8")
    with pytest.raises(storage.StorageError, match="duplicate call_id"):
        storage.append_validated(_record())
    assert data_path.read_text(encoding="utf-8") == before


def test_append_validated_rejects_missing_call_id(data_path):
    rec = _record()
    del rec["call_id"]
    with pytest.raises(storage.StorageError):
        storage.append_validated(rec)
    assert not data_path.exists()


@pytest.mark.parametrize("bad_call_id", ["", None, 123])
def test_append_validated_rejects_non_string_call_id(data_path, bad_call_id):
    with pytest.raises(storage.StorageError):
        storage.append_validated(_record(call_id=bad_call_id))


@pytest.mark.parametrize("field", ["amount", "total", "budget_limit"])
@pytest.mark.parametrize("bad", ["350", None, True])
def test_append_validated_rejects_non_numeric_fields(data_path, field, bad):
    with pytest.raises(storage.StorageError):
        storage.append_validated(_record(**{field: bad}))


def test_append_validated_rejects_missing_required_field(data_path):
    rec = _record()
    del rec["decided_at"]
    with pytest.raises(storage.StorageError):
        storage.append_validated(rec)


def test_current_total_sums_amounts(data_path):
    storage.append_validated(_record(call_id="a", amount=100))
    storage.append_validated(_record(call_id="b", amount=50))
    assert storage.current_total() == 150.0


def test_current_total_zero_when_absent(data_path):
    assert storage.current_total() == 0.0


def test_iter_records_yields_stored_records(data_path):
    storage.append_validated(_record(call_id="a"))
    storage.append_validated(_record(call_id="b"))
    assert [r["call_id"] for r in storage.iter_records()] == ["a", "b"]


def test_iter_records_malformed_line_raises(data_path):
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(storage.StorageError):
        list(storage.iter_records())


def test_storage_has_no_network_import():
    assert "requests" not in storage.__dict__


def test_policy_core_does_not_import_storage():
    import src.policy_core as mod

    assert "storage" not in mod.__dict__
