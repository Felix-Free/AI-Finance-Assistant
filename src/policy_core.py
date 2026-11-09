"""Deterministic policy core: the ONLY place that decides an outcome from model output.

The model proposes; this module disposes. It performs no IO: no files, no
database, no .env, no model calls. Every guard raises PolicyError on failure and
returns the validated value on success, so the caller can build the record.

Rules implemented per task sheet v2 §3.3 (INV-001, INV-002, INV-003).
"""
from __future__ import annotations

import math
from decimal import Decimal

CATEGORY_WHITELIST = frozenset({
    "food", "transport", "shopping", "entertainment",
    "housing", "utilities", "health", "other",
})


class PolicyError(ValueError):
    """The single rejection type.

    Attributes:
        code: log error code, one of "policy:amount" | "policy:category" | "policy:budget"
        review: True when the rejection must also be flagged for human inspection
    """

    def __init__(self, message: str, code: str, review: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.review = review


def enforce_amount(amount):
    """INV-001: amount must be a finite positive number with at most two decimals.

    Returns the original value unchanged (int stays int, float stays float,
    str stays str). Never returns a Decimal.
    """
    if isinstance(amount, bool):
        raise PolicyError("amount must be a number, not bool",
                          code="policy:amount", review=False)
    if not isinstance(amount, (int, float)):
        raise PolicyError("amount must be a number, got %r"
                          % (type(amount).__name__,),
                          code="policy:amount", review=False)
    if not math.isfinite(amount):
        raise PolicyError("amount must be finite", code="policy:amount",
                          review=False)
    if amount <= 0:
        raise PolicyError("amount must be > 0", code="policy:amount",
                          review=False)
    try:
        decimals = Decimal(str(amount)).as_tuple().exponent
    except Exception as exc:  # pragma: no cover - defensive
        raise PolicyError("amount is not representable: %s" % exc,
                          code="policy:amount", review=False) from exc
    if decimals < -2:
        raise PolicyError("amount must have at most two decimals",
                          code="policy:amount", review=False)
    return amount


def enforce_category(category):
    """INV-002: category must match the closed vocabulary exactly (case-sensitive)."""
    if not isinstance(category, str) or category not in CATEGORY_WHITELIST:
        raise PolicyError("category %r not in whitelist" % (category,),
                          code="policy:category", review=True)
    return category


def enforce_budget(spent, amount, limit):
    """INV-003: cumulative spend must never exceed the budget (equality is allowed).

    Rejects only when spent + amount > limit (strictly greater than). Returns
    the new running total as the same numeric kind it was computed from.
    """
    try:
        total = Decimal(str(spent)) + Decimal(str(amount))
        cap = Decimal(str(limit))
    except Exception as exc:  # pragma: no cover - defensive
        raise PolicyError("budget values not comparable: %s" % exc,
                          code="policy:budget", review=True) from exc
    if total > cap:
        raise PolicyError("spent %s + amount %s exceeds budget %s"
                          % (spent, amount, limit),
                          code="policy:budget", review=True)
    return float(total)


def validate_record(raw: dict, spent: float, budget_limit: float) -> dict:
    """Validate in order INV-001 -> INV-002 -> INV-003.

    Return the normalised record only if all three pass. Stops at the first
    failure by letting PolicyError propagate.
    """
    amount = enforce_amount(raw.get("amount"))
    category = enforce_category(raw.get("category"))
    enforce_budget(spent, amount, budget_limit)
    return {"amount": amount, "category": category}
