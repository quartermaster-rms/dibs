from __future__ import annotations

import pytest

from dibs.enums import ScopeKind, Tier
from dibs.errors import DibsError
from dibs.permissions.delegation import (
    ActorGrant,
    GrantFlags,
    actor_flags_for_target,
    authorize_transition,
)
from dibs.permissions.tiers import (
    can_operate,
    combine_grant_tier,
    department_gate_ok,
    effective_tier,
    is_enable_gated,
    is_open_access,
)

ITEM = ScopeKind.ITEM
CLASS = ScopeKind.CLASS


# --- tiers.py ---


@pytest.mark.parametrize(
    "item,cls,expected",
    [(True, False, True), (False, True, True), (False, False, False)],
)
def test_open_access(item, cls, expected):
    assert is_open_access(item, cls) is expected


@pytest.mark.parametrize(
    "item,cls,expected",
    [(True, True, True), (True, False, False), (False, True, False)],
)
def test_enable_gated(item, cls, expected):
    assert is_enable_gated(item, cls) is expected


def test_department_gate():
    assert department_gate_ok(True, set(), {"group-eng"}) is True  # admin bypass
    assert department_gate_ok(False, set(), set()) is True  # no requirement
    assert department_gate_ok(False, {"group-eng"}, {"group-eng"}) is True
    assert department_gate_ok(False, {"group-hr"}, {"group-eng"}) is False


def test_combine_and_effective_tier():
    assert combine_grant_tier(None, None) is Tier.NONE
    assert combine_grant_tier(Tier.USER, None) is Tier.USER
    assert combine_grant_tier(None, Tier.SUPERUSER) is Tier.SUPERUSER
    assert combine_grant_tier(Tier.USER, Tier.SUPERUSER) is Tier.SUPERUSER
    # open access raises none -> user, but never lowers a real grant
    assert effective_tier(None, None, True) is Tier.USER
    assert effective_tier(None, None, False) is Tier.NONE
    assert effective_tier(Tier.SUPERUSER, None, True) is Tier.SUPERUSER


def test_can_operate():
    assert can_operate(True, Tier.NONE) is True
    assert can_operate(False, Tier.USER) is True
    assert can_operate(False, Tier.NONE) is False


# --- delegation flags ---


def test_grant_flags_subset_and_union():
    full = GrantFlags(True, True, True)
    promote = GrantFlags(can_promote=True)
    assert promote.subset_of(full) is True
    assert full.subset_of(promote) is False
    assert promote.union(GrantFlags(can_demote=True)) == GrantFlags(
        can_promote=True, can_demote=True
    )


def test_actor_flags_for_target():
    item_grant = ActorGrant(ITEM, "item-1", Tier.SUPERUSER, GrantFlags(can_promote=True))
    class_grant = ActorGrant(CLASS, "class-1", Tier.SUPERUSER, GrantFlags(can_demote=True))
    plain = ActorGrant(ITEM, "item-1", Tier.USER, GrantFlags())
    grants = [item_grant, class_grant, plain]
    # item covered by item + class grants -> union
    flags = actor_flags_for_target(grants, ITEM, "item-1", "class-1")
    assert flags == GrantFlags(can_promote=True, can_demote=True)
    # item in a different class -> only its own item grant covers
    assert actor_flags_for_target(grants, ITEM, "item-1", "class-9") == GrantFlags(can_promote=True)
    # unrelated item -> uncovered
    assert actor_flags_for_target(grants, ITEM, "item-2", "class-9") is None
    # class target covered only by class grant (not the item grant)
    assert actor_flags_for_target(grants, CLASS, "class-1", None) == GrantFlags(can_demote=True)
    assert actor_flags_for_target(grants, CLASS, "class-2", None) is None


# --- authorize_transition ---


def _auth(**kw):
    base = {
        "actor_is_admin": False,
        "actor_flags": GrantFlags(True, True, True),
        "actor_is_target": False,
        "target_is_admin": False,
        "current_tier": Tier.NONE,
        "new_tier": Tier.USER,
        "requested_flags": GrantFlags(),
        "allow_peer_demote": False,
        "allow_self_demote": False,
    }
    base.update(kw)
    return authorize_transition(**base)


def _forbidden(**kw):
    with pytest.raises(DibsError) as ei:
        _auth(**kw)
    assert ei.value.code == "grant_forbidden"


def test_transition_admin_and_target_admin():
    _forbidden(target_is_admin=True)  # never affect an admin, even as admin actor
    # admin actor may do anything to a non-admin
    _auth(
        actor_is_admin=True,
        actor_flags=None,
        new_tier=Tier.SUPERUSER,
        requested_flags=GrantFlags(True, True, True),
    )


def test_transition_requires_delegate():
    _forbidden(actor_flags=None)


def test_transition_promote():
    _auth(new_tier=Tier.USER, actor_flags=GrantFlags(can_promote=True))
    _forbidden(new_tier=Tier.USER, actor_flags=GrantFlags(can_demote=True))


def test_transition_grant_superuser_and_escalation():
    _auth(
        new_tier=Tier.SUPERUSER,
        actor_flags=GrantFlags(can_grant_superuser=True),
        requested_flags=GrantFlags(),
    )
    # cannot confer an ability the actor lacks
    _forbidden(
        new_tier=Tier.SUPERUSER,
        actor_flags=GrantFlags(can_grant_superuser=True),
        requested_flags=GrantFlags(can_promote=True),
    )
    # needs the grant-superuser ability
    _forbidden(new_tier=Tier.SUPERUSER, actor_flags=GrantFlags(can_promote=True))


def test_transition_demote_peer_and_self():
    demote = GrantFlags(can_demote=True)
    # demote a user -> none: only can_demote needed
    _auth(current_tier=Tier.USER, new_tier=Tier.NONE, actor_flags=demote)
    _forbidden(current_tier=Tier.USER, new_tier=Tier.NONE, actor_flags=GrantFlags(can_promote=True))
    # demote a peer superuser: needs allow_peer_demote
    _forbidden(current_tier=Tier.SUPERUSER, new_tier=Tier.USER, actor_flags=demote)
    _auth(
        current_tier=Tier.SUPERUSER, new_tier=Tier.USER, actor_flags=demote, allow_peer_demote=True
    )
    # self-demote: governed by allow_self_demote (regardless of peer setting)
    _forbidden(
        current_tier=Tier.SUPERUSER,
        new_tier=Tier.NONE,
        actor_flags=demote,
        actor_is_target=True,
        allow_peer_demote=True,
    )
    _auth(
        current_tier=Tier.SUPERUSER,
        new_tier=Tier.NONE,
        actor_flags=demote,
        actor_is_target=True,
        allow_self_demote=True,
    )


def test_transition_noop():
    # user -> user no-op is permitted for a delegate
    _auth(current_tier=Tier.USER, new_tier=Tier.USER, actor_flags=GrantFlags())
