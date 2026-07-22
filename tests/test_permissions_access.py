from __future__ import annotations

import uuid

import pytest
from tests.factories import make_class, make_equipment, make_grant

from dibs.auth.identity import Identity
from dibs.enums import ScopeKind, Tier
from dibs.errors import DibsError, NotFound
from dibs.models import Equipment, EquipmentClass
from dibs.permissions.access import compute_access, load_access, reachable_equipment_ids
from dibs.permissions.deps import require_dibs_access, require_dibs_access_csrf
from dibs.services.settings import set_setting


def _eq_and_class(open_item=False, open_cls=False, req_item=True, req_cls=True, dept=None):
    cid = uuid.uuid4()
    klass = EquipmentClass(
        id=cid,
        name="c",
        description="",
        open_use=open_cls,
        requires_enable=req_cls,
        department_groups=dept or [],
    )
    eq = Equipment(
        id=uuid.uuid4(),
        name="e",
        class_id=cid,
        location_id=uuid.uuid4(),
        open_use=open_item,
        requires_enable=req_item,
        qr_token="t",
    )
    return eq, klass


def test_compute_access_basic():
    eq, klass = _eq_and_class()
    user = Identity("u", "", "", ())
    acc = compute_access(
        identity=user,
        equipment=eq,
        klass=klass,
        dibs_gate=set(),
        item_tier=Tier.USER,
        class_tier=None,
    )
    assert acc.reachable and acc.tier is Tier.USER and acc.can_operate
    assert acc.enable_gated and not acc.open_access


def test_compute_access_open_and_gate():
    eq, klass = _eq_and_class(open_cls=True, req_item=False, dept=["group-eng"])
    outsider = Identity("o", "", "", ("group-hr",))
    acc = compute_access(
        identity=outsider,
        equipment=eq,
        klass=klass,
        dibs_gate=set(),
        item_tier=None,
        class_tier=None,
    )
    assert not acc.reachable and acc.tier is Tier.NONE and not acc.can_operate
    member = Identity("m", "", "", ("group-eng",))
    acc2 = compute_access(
        identity=member,
        equipment=eq,
        klass=klass,
        dibs_gate=set(),
        item_tier=None,
        class_tier=None,
    )
    # open-access confers user; item is no-enable (class still requires but item doesn't)
    assert acc2.reachable and acc2.tier is Tier.USER and not acc2.enable_gated


def test_compute_access_admin_bypasses_gate():
    eq, klass = _eq_and_class(dept=["group-eng"])
    admin = Identity("a", "", "", ("admin-dibs",))
    acc = compute_access(
        identity=admin,
        equipment=eq,
        klass=klass,
        dibs_gate={"group-x"},
        item_tier=None,
        class_tier=None,
    )
    assert acc.reachable and acc.is_admin and acc.can_operate


async def test_load_access_db(db_session):
    klass = await make_class(db_session, department_groups=["group-eng"])
    eq = await make_equipment(db_session, klass=klass)
    await make_grant(db_session, "u-1", ScopeKind.CLASS, klass.id, Tier.SUPERUSER)
    member = Identity("u-1", "", "", ("group-eng",))
    acc = await load_access(db_session, member, eq.id)
    assert acc.tier is Tier.SUPERUSER and acc.reachable
    # item grant overrides upward
    await make_grant(db_session, "u-1", ScopeKind.ITEM, eq.id, Tier.USER)
    acc2 = await load_access(db_session, member, eq.id)
    assert acc2.tier is Tier.SUPERUSER  # class superuser still wins (higher)


async def test_load_access_not_found(db_session):
    with pytest.raises(NotFound):
        await load_access(db_session, Identity("u", "", "", ()), uuid.uuid4())


async def test_require_dibs_access_gate(db_session):
    member = Identity("m", "", "", ("group-eng",))
    outsider = Identity("o", "", "", ("group-hr",))
    admin = Identity("a", "", "", ("sysadmin",))
    # no gate configured -> everyone passes
    assert await require_dibs_access(member, db_session) is member
    await set_setting(db_session, "dibs_department_groups", ["group-eng"])
    assert await require_dibs_access(member, db_session) is member
    assert await require_dibs_access(admin, db_session) is admin
    with pytest.raises(DibsError) as ei:
        await require_dibs_access(outsider, db_session)
    assert ei.value.code == "department_gate"
    # csrf variant enforces the same gate
    assert await require_dibs_access_csrf(member, db_session) is member
    with pytest.raises(DibsError):
        await require_dibs_access_csrf(outsider, db_session)


async def test_reachable_equipment_ids(db_session):
    open_cls = await make_class(db_session, name="Open2")
    gated_cls = await make_class(db_session, name="Gated2", department_groups=["group-eng"])
    eq_open = await make_equipment(db_session, klass=open_cls)
    eq_gated = await make_equipment(db_session, klass=gated_cls)
    admin = Identity("a", "", "", ("admin-dibs",))
    member = Identity("m", "", "", ("group-eng",))
    outsider = Identity("o", "", "", ("group-hr",))
    assert await reachable_equipment_ids(db_session, admin) is None  # all
    assert await reachable_equipment_ids(db_session, member) == {eq_open.id, eq_gated.id}
    assert await reachable_equipment_ids(db_session, outsider) == {eq_open.id}
    # dibs-wide gate excludes everyone not in it
    await set_setting(db_session, "dibs_department_groups", ["group-eng"])
    assert await reachable_equipment_ids(db_session, outsider) == set()
