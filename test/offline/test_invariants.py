"""INV: enforce_amount must reject negative amounts and pass valid ones through."""

import pytest

from src.policy_core import PolicyError, enforce_amount


@pytest.mark.offline
def test_inv001_rejects_negative_amount():
    """INV-001: a negative amount must raise PolicyError."""
    with pytest.raises(PolicyError):
        enforce_amount(-0.01)


@pytest.mark.offline
def test_inv001_accepts_valid_amount():
    """INV-001: a valid amount must be returned unchanged."""
    assert enforce_amount(0.01) == 0.01
