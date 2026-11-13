"""Offline tests for src/storage.py (task sheet v4 §2, §7 acceptance 3 & 4).

Every test redirects storage.DATA_PATH into tmp_path, never data/records.jsonl.
No network access.
"""
import json

import pytest

from src import policy_core, storage


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


def test_append_validated_rejects_unknown_private_key(data_path):
    with pytest.raises(storage.StorageError):
        storage.append_validated(_record(**{"__call_id__": "x"}))
    assert not data_path.exists()


@pytest.mark.parametrize("bad_category", ["", None, 123])
def test_append_validated_rejects_non_string_category(data_path, bad_category):
    with pytest.raises(storage.StorageError):
        storage.append_validated(_record(category=bad_category))


def test_current_total_raises_on_non_numeric_amount(data_path):
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(
        json.dumps({"call_id": "x", "amount": "350"}) + "\n", encoding="utf-8"
    )
    with pytest.raises(storage.StorageError):
        storage.current_total()


def test_current_total_sums_amounts(data_path):
    storage.append_validated(_record(call_id="a", amount=100, total=100.0))
    storage.append_validated(_record(call_id="b", amount=50, total=150.0))
    assert storage.current_total() == 150.0


def test_current_total_zero_when_absent(data_path):
    assert storage.current_total() == 0.0


def test_iter_records_yields_stored_records(data_path):
    storage.append_validated(_record(call_id="a"))
    storage.append_validated(_record(call_id="b", total=700.0))
    assert [r["call_id"] for r in storage.iter_records()] == ["a", "b"]


def test_iter_records_malformed_line_raises(data_path):
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(storage.StorageError):
        list(storage.iter_records())


def _seed(data_path, amount, call_id="seed"):
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(
        json.dumps(_record(call_id=call_id, amount=amount, total=float(amount))) + "\n",
        encoding="utf-8",
    )


def test_append_validated_direct_overbudget_is_policy_rejection(data_path):
    rec = _record(call_id="over", amount=999999, total=999999.0, budget_limit=1000.0)
    with pytest.raises(policy_core.PolicyError) as exc:
        storage.append_validated(rec)
    assert exc.value.code == "policy:budget"
    assert not data_path.exists()


def test_append_validated_direct_negative_amount_is_policy_rejection(data_path):
    with pytest.raises(policy_core.PolicyError) as exc:
        storage.append_validated(_record(amount=-1, total=-1.0))
    assert exc.value.code == "policy:amount"
    assert not data_path.exists()


def test_append_validated_direct_bad_category_is_policy_rejection(data_path):
    with pytest.raises(policy_core.PolicyError) as exc:
        storage.append_validated(_record(category="Food"))
    assert exc.value.code == "policy:category"
    assert not data_path.exists()


def test_append_validated_underreported_spent_is_storage_error(data_path):
    _seed(data_path, 500)
    before = data_path.read_text(encoding="utf-8")
    rec = _record(call_id="under", amount=600, total=600.0, budget_limit=1000.0)
    with pytest.raises(storage.StorageError, match="below persisted"):
        storage.append_validated(rec, expected_spent=0)
    assert data_path.read_text(encoding="utf-8") == before


def test_append_validated_overreported_spent_writes(data_path):
    _seed(data_path, 500)
    rec = _record(call_id="over", amount=100, total=800.0, budget_limit=1000.0)
    storage.append_validated(rec, expected_spent=700)
    assert len(data_path.read_text(encoding="utf-8").splitlines()) == 2


def test_append_validated_expected_spent_equal_to_persisted_writes(data_path):
    _seed(data_path, 500)
    rec = _record(call_id="eq", amount=100, total=600.0, budget_limit=1000.0)
    storage.append_validated(rec, expected_spent=500)
    assert len(data_path.read_text(encoding="utf-8").splitlines()) == 2


def test_append_validated_arithmetic_inconsistency_is_storage_error(data_path):
    with pytest.raises(storage.StorageError, match="total inconsistent"):
        storage.append_validated(
            _record(call_id="bad", amount=100, total=101.0, budget_limit=1000.0),
            expected_spent=0,
        )
    assert not data_path.exists()


def test_append_validated_decimal_sum_is_not_rejected_by_float_error(data_path):
    _seed(data_path, 0.1)
    rec = _record(call_id="dec", amount=0.2, total=0.3, budget_limit=1.0)
    storage.append_validated(rec, expected_spent=0.1)
    assert len(data_path.read_text(encoding="utf-8").splitlines()) == 2


def test_append_validated_none_expected_spent_uses_persisted(data_path):
    _seed(data_path, 500)
    rec = _record(call_id="none", amount=100, total=600.0, budget_limit=1000.0)
    storage.append_validated(rec, expected_spent=None)
    assert len(data_path.read_text(encoding="utf-8").splitlines()) == 2


def test_append_validated_rejects_non_numeric_expected_spent(data_path):
    with pytest.raises(storage.StorageError, match="expected_spent must be a number"):
        storage.append_validated(_record(), expected_spent=True)


@pytest.mark.parametrize("bad_line", [
    json.dumps({"call_id": ["x"], "amount": 100}),
    json.dumps({"call_id": "", "amount": 100}),
    json.dumps({"amount": 100}),
])
def test_stored_call_id_must_be_non_empty_string(data_path, bad_line):
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(bad_line + "\n", encoding="utf-8")
    with pytest.raises(storage.StorageError, match="call_id must be a non-empty string"):
        list(storage.iter_records())
    with pytest.raises(storage.StorageError, match="call_id must be a non-empty string"):
        storage.current_total()


def test_append_validated_rejects_non_serialisable_field(data_path):
    with pytest.raises(storage.StorageError, match="not JSON-serialisable"):
        storage.append_validated(_record(decided_at=set()))
    assert not data_path.exists()


def test_storage_has_no_network_import():
    assert "requests" not in storage.__dict__


def test_policy_core_does_not_import_storage():
    import src.policy_core as mod

    assert "storage" not in mod.__dict__
