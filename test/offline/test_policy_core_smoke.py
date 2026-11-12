"""Smoke tests for src/policy_core.py (task sheet v2 §5; role D).

These are SMOKE tests only. The exhaustive boundary suite belongs to the
verification role (test/offline/test_invariants.py, owned by E) and is not
duplicated here. Each test fails if the corresponding guard is removed.
"""
import math

import pytest

from src.policy_core import (
    PolicyError,
    enforce_amount,
    enforce_budget,
    enforce_category,
    validate_record,
)


@pytest.mark.parametrize(
    "bad", [-1, 0, 0.005, 100.001, "350", None, True, float("nan"), float("inf")]
)
def test_inv001_rejects_invalid_amount(bad):
    with pytest.raises(PolicyError) as exc:
        enforce_amount(bad)
    assert exc.value.code == "policy:amount"
    assert exc.value.review is False


def test_inv001_accepts_boundary_and_returns_unchanged():
    assert enforce_amount(0.01) == 0.01
    assert isinstance(enforce_amount(350), int)


def test_inv001_rejects_minus_zero_point_zero_one():
    with pytest.raises(PolicyError) as exc:
        enforce_amount(-0.01)
    assert exc.value.code == "policy:amount"


def test_inv001_never_returns_decimal():
    result = enforce_amount(350)
    assert not hasattr(result, "as_tuple")


@pytest.mark.parametrize("bad", ["Food", "餐饮", "meal", "", None, 1])
def test_inv002_rejects_out_of_vocabulary(bad):
    with pytest.raises(PolicyError) as exc:
        enforce_category(bad)
    assert exc.value.code == "policy:category"
    assert exc.value.review is True


@pytest.mark.parametrize(
    "good",
    ["food", "transport", "shopping", "entertainment",
     "housing", "utilities", "health", "other"],
)
def test_inv002_accepts_every_whitelisted_category(good):
    assert enforce_category(good) == good


def test_inv003_equality_is_allowed():
    assert enforce_budget(spent=990, amount=10, limit=1000) == 1000


def test_inv003_over_budget_rejected_with_review():
    with pytest.raises(PolicyError) as exc:
        enforce_budget(spent=990, amount=10.01, limit=1000)
    assert exc.value.code == "policy:budget"
    assert exc.value.review is True


def test_validate_record_stops_at_first_failure():
    with pytest.raises(PolicyError) as exc:
        validate_record({"amount": -1, "category": "Food"}, 0.0, 1000.0)
    assert exc.value.code == "policy:amount"


def test_validate_record_rejects_non_dict():
    with pytest.raises(PolicyError) as exc:
        validate_record([1, 2], 0.0, 1000.0)
    assert exc.value.code == "policy:amount"
    assert exc.value.review is False


def test_validate_record_returns_normalised_record():
    record = validate_record({"amount": 350, "category": "food"}, 0.0, 1000.0)
    assert record == {"amount": 350, "category": "food", "total": 350.0}


def test_policy_core_has_no_io_imports():
    import src.policy_core as mod

    assert "requests" not in (mod.__dict__)
