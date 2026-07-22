"""The delegation model: which grant transitions a caller may apply.

A superuser exercises only the abilities its grant enables, only within scope,
never conferring an ability it lacks (no escalation), and never affecting an
admin. Peer- and self-demote are admin-configurable (default off). Admins may
apply any transition on a non-admin target.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..enums import ScopeKind, Tier
from ..errors import named_error
from .tiers import rank


@dataclass(frozen=True)
class GrantFlags:
    can_promote: bool = False
    can_grant_superuser: bool = False
    can_demote: bool = False

    def subset_of(self, other: GrantFlags) -> bool:
        return (
            (other.can_promote or not self.can_promote)
            and (other.can_grant_superuser or not self.can_grant_superuser)
            and (other.can_demote or not self.can_demote)
        )

    def union(self, other: GrantFlags) -> GrantFlags:
        return GrantFlags(
            self.can_promote or other.can_promote,
            self.can_grant_superuser or other.can_grant_superuser,
            self.can_demote or other.can_demote,
        )


@dataclass(frozen=True)
class ActorGrant:
    scope_kind: ScopeKind
    scope_id: str
    tier: Tier
    flags: GrantFlags


def actor_flags_for_target(
    actor_grants: list[ActorGrant],
    target_kind: ScopeKind,
    target_id: str,
    item_class_id: str | None,
) -> GrantFlags | None:
    """The union of delegation flags from the caller's superuser grants that
    cover the target scope (an item is covered by its own grant or its class
    grant; a class is covered only by its class grant). None if uncovered."""
    covering: GrantFlags | None = None
    for g in actor_grants:
        if g.tier != Tier.SUPERUSER:
            continue
        if target_kind == ScopeKind.ITEM:
            covers = (g.scope_kind == ScopeKind.ITEM and g.scope_id == target_id) or (
                g.scope_kind == ScopeKind.CLASS and g.scope_id == item_class_id
            )
        else:
            covers = g.scope_kind == ScopeKind.CLASS and g.scope_id == target_id
        if covers:
            covering = g.flags if covering is None else covering.union(g.flags)
    return covering


def authorize_transition(
    *,
    actor_is_admin: bool,
    actor_flags: GrantFlags | None,
    actor_is_target: bool,
    target_is_admin: bool,
    current_tier: Tier,
    new_tier: Tier,
    requested_flags: GrantFlags,
    allow_peer_demote: bool,
    allow_self_demote: bool,
) -> None:
    """Raise ``grant_forbidden`` unless the transition is permitted."""
    if target_is_admin:
        raise named_error("grant_forbidden", "cannot change an administrator's grant")

    if actor_is_admin:
        return

    if actor_flags is None:
        raise named_error("grant_forbidden", "no delegation authority in this scope")

    if new_tier == Tier.SUPERUSER:
        if not actor_flags.can_grant_superuser:
            raise named_error("grant_forbidden", "grant-superuser ability required")
        if not requested_flags.subset_of(actor_flags):
            raise named_error("grant_forbidden", "cannot confer an ability you lack")
        return

    if rank(new_tier) > rank(current_tier):  # raise to user (from none)
        if not actor_flags.can_promote:
            raise named_error("grant_forbidden", "promote ability required")
        return

    if rank(new_tier) < rank(current_tier):  # demote
        if not actor_flags.can_demote:
            raise named_error("grant_forbidden", "demote ability required")
        if actor_is_target and not allow_self_demote:
            raise named_error("grant_forbidden", "self-demote not permitted")
        if not actor_is_target and current_tier == Tier.SUPERUSER and not allow_peer_demote:
            raise named_error("grant_forbidden", "peer-demote not permitted")
        return

    # new_tier == current_tier and not superuser: a no-op is permitted.
