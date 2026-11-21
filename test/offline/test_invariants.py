"""Exhaustive boundary suite for the three approved invariants (owner: role E).

Deterministic and network-free: these tests exercise src/policy_core.py only and
touch no files, no model gateway and no environment. They verify C's specs in
docs/architecture/invariants.md (§2) against D's implementation:

  INV-001  amount  : finite, > 0, at most two decimals   -> policy:amount,   review=False
  INV-002  category: exact match in the code whitelist   -> policy:category, review=True
  INV-003  budget  : spent + amount must not exceed limit -> policy:budget,  review=True

Every rejection asserts the ORIGINAL error code and the review flag. The three
negative cases below are each independently selectable, one per guard, so a
snapshot that removes a single guard turns exactly its own negative test red:

  test_inv001_rejects_negative_amount            (amount guard)
  test_inv002_rejects_unknown_category           (category guard)
  test_inv003_rejects_one_cent_over_budget       (budget guard)

The existing D smoke suite (test_policy_core_smoke.py) is intentionally not
duplicated here; this file covers the approved argument boundaries and
positive/negative pairs only.
"""

import math

import pytest

from src.policy_core import (
    CATEGORY_WHITELIST,
    PolicyError,
    enforce_amount,
    enforce_budget,
    enforce_category,
    validate_record,
)


# ---------------------------------------------------------------------------
# INV-001 — amount must be a finite positive number with at most two decimals
# ---------------------------------------------------------------------------

@pytest.mark.offline
def test_inv001_rejects_negative_amount():
    """INV-001 negative: -0.01 (just below the positive boundary) is rejected.

    This case is isolated on purpose: disabling the amount guard makes the
    record flow through and this test goes red.
    """
    with pytest.raises(PolicyError) as exc:
        enforce_amount(-0.01)
    assert exc.value.code == "policy:amount"
    assert exc.value.review is False


@pytest.mark.offline
@pytest.mark.parametrize(
    "bad",
    [
        0,          # not positive
        0.0,        # not positive
        -1,         # negative
        0.005,      # three decimals
        100.001,    # three decimals
        "350",      # non-numeric string
        None,       # missing
        True,       # bool is not a money amount
        math.nan,   # not finite
        math.inf,   # not finite
        -math.inf,  # not finite
    ],
)
def test_inv001_rejects_invalid_amount(bad):
    """INV-001: every non-finite / non-positive / >2-decimal / non-numeric value is rejected."""
    with pytest.raises(PolicyError) as exc:
        enforce_amount(bad)
    assert exc.value.code == "policy:amount"
    assert exc.value.review is False


@pytest.mark.offline
@pytest.mark.parametrize(
    "good, expected_kind",
    [
        (0.01, float),   # lowest positive value with two decimals
        (0.10, float),   # exactly two decimals
        (1, int),        # whole amount, stays int
        (350, int),      # whole amount, stays int
        (999.99, float), # large two-decimal amount
    ],
)
def test_inv001_accepts_boundary_amount_and_returns_unchanged(good, expected_kind):
    """INV-001 positive: valid amounts pass through unchanged and keep their kind."""
    result = enforce_amount(good)
    assert result == good
    assert isinstance(result, expected_kind)
    assert not hasattr(result, "as_tuple")  # never returns a Decimal


# ---------------------------------------------------------------------------
# INV-002 — category must be in the code-defined closed whitelist (exact)
# ---------------------------------------------------------------------------

@pytest.mark.offline
def test_inv002_rejects_unknown_category():
    """INV-002 negative: an unknown category is rejected and flagged for review.

    This case is isolated on purpose: disabling the category guard makes the
    record flow through and this test goes red.
    """
    with pytest.raises(PolicyError) as exc:
        enforce_category("groceries")
    assert exc.value.code == "policy:category"
    assert exc.value.review is True


@pytest.mark.offline
@pytest.mark.parametrize(
    "bad",
    [
        "Food",   # wrong case: matching is exact/case-sensitive
        "FOOD",   # wrong case
        "餐饮",    # not in the English vocabulary
        "meal",   # not a whitelist value
        "",       # empty string
        " food",  # leading space breaks exact match
        "food ",  # trailing space breaks exact match
        None,     # missing
        1,        # non-string
    ],
)
def test_inv002_rejects_out_of_vocabulary(bad):
    """INV-002: exact-match rule — anything not byte-identical to a whitelist value fails."""
    with pytest.raises(PolicyError) as exc:
        enforce_category(bad)
    assert exc.value.code == "policy:category"
    assert exc.value.review is True


@pytest.mark.offline
def test_inv002_accepts_every_implemented_category():
    """INV-002 positive: every value present in the code whitelist is accepted.

    Iterating CATEGORY_WHITELIST tracks the code rather than hardcoding a list.
    The SET MEMBERSHIP is still pending confirmation (PD-002 / INV-PENDING-01);
    what is approved and tested here is the EXACT-MATCH rule: each member is
    accepted verbatim, and every non-member is rejected (above).
    """
    assert CATEGORY_WHITELIST  # the whitelist is not empty
    for category in CATEGORY_WHITELIST:
        assert enforce_category(category) == category


# ---------------------------------------------------------------------------
# INV-003 — cumulative spend must not exceed the budget (equality allowed)
# ---------------------------------------------------------------------------

@pytest.mark.offline
def test_inv003_rejects_one_cent_over_budget():
    """INV-003 negative: one cent over the limit is rejected and flagged for review.

    This case is isolated on purpose: disabling the budget guard makes the
    record flow through and this test goes red.
    """
    with pytest.raises(PolicyError) as exc:
        enforce_budget(spent=990, amount=10.01, limit=1000)
    assert exc.value.code == "policy:budget"
    assert exc.value.review is True


@pytest.mark.offline
@pytest.mark.parametrize(
    "spent, amount, limit, expected_total",
    [
        (0.0, 999.99, 1000.0, 999.99),   # limit - 0.01: accepted
        (990.0, 10.0, 1000.0, 1000.0),   # exactly the limit: accepted (equality)
        (0.0, 1000.0, 1000.0, 1000.0),   # single record exactly at the limit
        (500.0, 500.0, 1000.0, 1000.0),  # cumulative equality (two halves)
    ],
)
def test_inv003_accepts_up_to_the_limit(spent, amount, limit, expected_total):
    """INV-003 positive: any total <= limit is accepted, including exact equality."""
    assert enforce_budget(spent=spent, amount=amount, limit=limit) == expected_total


@pytest.mark.offline
@pytest.mark.parametrize(
    "spent, amount, limit",
    [
        (0.0, 1000.01, 1000.0),   # limit + 0.01: rejected
        (990.0, 10.01, 1000.0),   # limit + 0.01 accumulated: rejected
        (1000.0, 0.01, 1000.0),   # already at the limit, any positive amount exceeds
    ],
)
def test_inv003_rejects_over_the_limit(spent, amount, limit):
    """INV-003 negative: any total > limit is rejected; proves cumulative, not per-record."""
    with pytest.raises(PolicyError) as exc:
        enforce_budget(spent=spent, amount=amount, limit=limit)
    assert exc.value.code == "policy:budget"
    assert exc.value.review is True


# ---------------------------------------------------------------------------
# validate_record — order INV-001 -> INV-002 -> INV-003, first failure wins
# ---------------------------------------------------------------------------

@pytest.mark.offline
def test_validate_record_reports_amount_failure_first():
    """INV-001 fires before INV-002 when both are violated."""
    with pytest.raises(PolicyError) as exc:
        validate_record({"amount": -1, "category": "Food"}, spent=0.0, budget_limit=1000.0)
    assert exc.value.code == "policy:amount"
    assert exc.value.review is False


@pytest.mark.offline
def test_validate_record_reports_category_failure_before_budget():
    """INV-002 fires before INV-003 when both are violated."""
    with pytest.raises(PolicyError) as exc:
        validate_record({"amount": 20, "category": "Food"}, spent=990.0, budget_limit=1000.0)
    assert exc.value.code == "policy:category"
    assert exc.value.review is True


@pytest.mark.offline
def test_validate_record_reports_budget_failure():
    """INV-003 fires when amount and category are valid but the budget is exceeded."""
    with pytest.raises(PolicyError) as exc:
        validate_record({"amount": 20, "category": "food"}, spent=990.0, budget_limit=1000.0)
    assert exc.value.code == "policy:budget"
    assert exc.value.review is True
