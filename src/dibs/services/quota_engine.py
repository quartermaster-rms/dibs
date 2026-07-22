"""Pure quota precedence. A policy dominates only when at least as specific on
BOTH dimensions (principal user>group>everyone AND target item>class); otherwise
matching policies tie and the lowest limit binds. Every hard_cap policy applies
additionally (guide/SPEC 'ties take the lowest limit; every hard_cap also
applies')."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

PRINCIPAL_RANK = {"user": 2, "group": 1, "everyone": 0}
TARGET_RANK = {"item": 1, "class": 0}


@dataclass(frozen=True)
class PolicyMatch:
    principal_rank: int
    target_rank: int
    limit_hours: Decimal
    hard_cap: bool


def _dominates(q: PolicyMatch, p: PolicyMatch) -> bool:
    return (
        q.principal_rank >= p.principal_rank
        and q.target_rank >= p.target_rank
        and (q.principal_rank > p.principal_rank or q.target_rank > p.target_rank)
    )


def binding_limit(policies: list[PolicyMatch]) -> Decimal | None:
    """The effective hours ceiling for one (quota_type, window), or None when no
    policy applies (unlimited)."""
    if not policies:
        return None
    maximal = [p for p in policies if not any(_dominates(q, p) for q in policies if q is not p)]
    winner = min(p.limit_hours for p in maximal)
    caps = [p.limit_hours for p in policies if p.hard_cap]
    return min([winner, *caps])
