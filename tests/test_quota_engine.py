from __future__ import annotations

from decimal import Decimal

from dibs.services.quota_engine import PolicyMatch, binding_limit


def p(prank, trank, limit, hard_cap=False):
    return PolicyMatch(prank, trank, Decimal(limit), hard_cap)


def test_no_policies_unlimited():
    assert binding_limit([]) is None


def test_single_policy():
    assert binding_limit([p(2, 1, 5)]) == Decimal(5)


def test_more_specific_dominates():
    # user+item (2,1)=5 dominates everyone+class (0,0)=10
    assert binding_limit([p(2, 1, 5), p(0, 0, 10)]) == Decimal(5)


def test_incomparable_tie_takes_lowest():
    # user+class (2,0)=8 vs group+item (1,1)=6 -> incomparable -> lowest
    assert binding_limit([p(2, 0, 8), p(1, 1, 6)]) == Decimal(6)


def test_equal_specificity_lowest():
    assert binding_limit([p(2, 1, 5), p(2, 1, 3)]) == Decimal(3)


def test_hard_cap_applies_in_addition():
    # winner user+item=10 but an everyone+class hard_cap=4 also applies
    assert binding_limit([p(2, 1, 10), p(0, 0, 4, hard_cap=True)]) == Decimal(4)


def test_hard_cap_not_binding_when_higher():
    assert binding_limit([p(2, 1, 5), p(0, 0, 40, hard_cap=True)]) == Decimal(5)
