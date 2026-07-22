"""Pure effective-tier / flag / department-gate math (no I/O)."""

from __future__ import annotations

from ..enums import Tier

TIER_RANK: dict[Tier, int] = {Tier.NONE: 0, Tier.USER: 1, Tier.SUPERUSER: 2}


def rank(tier: Tier) -> int:
    return TIER_RANK[tier]


def is_open_access(item_open_use: bool, class_open_use: bool) -> bool:
    """An item is open-access if it OR its class is marked open_use."""
    return item_open_use or class_open_use


def is_enable_gated(item_requires_enable: bool, class_requires_enable: bool) -> bool:
    """An item is enable-gated only while BOTH it and its class require enable."""
    return item_requires_enable and class_requires_enable


def department_gate_ok(is_admin: bool, groups: set[str], required: set[str]) -> bool:
    """sysadmin/admin-dibs bypass; otherwise the caller must share at least one
    required group. An empty requirement gates nothing."""
    if is_admin:
        return True
    if not required:
        return True
    return bool(required & groups)


def combine_grant_tier(item_tier: Tier | None, class_tier: Tier | None) -> Tier:
    """Higher of the item grant and the class grant; none when neither present."""
    present = [t for t in (item_tier, class_tier) if t is not None]
    if not present:
        return Tier.NONE
    return max(present, key=rank)


def effective_tier(item_tier: Tier | None, class_tier: Tier | None, open_access: bool) -> Tier:
    """The caller's effective fine tier on an item: the higher of its item and
    class grant, raised to `user` when the item is open-access."""
    base = combine_grant_tier(item_tier, class_tier)
    if open_access and rank(base) < rank(Tier.USER):
        return Tier.USER
    return base


def can_operate(is_admin: bool, tier: Tier) -> bool:
    """May reserve / Enable / operate: admin, or effective user tier or above."""
    return is_admin or rank(tier) >= rank(Tier.USER)
