from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from tests.factories import (
    make_class,
    make_equipment,
    make_grant,
    make_quota_policy,
    make_reservation,
)

from dibs.enums import QuotaType, QuotaWindow, ScopeKind, Tier


def slot(days=1, hour=17, minute=0, dur=60):
    s = (datetime.now(UTC) + timedelta(days=days)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )
    return s, s + timedelta(minutes=dur)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


async def _setup(db_session, subject="u-1", tier=Tier.USER):
    eq = await make_equipment(db_session)
    if tier is not None:
        await make_grant(db_session, subject, ScopeKind.ITEM, eq.id, tier)
    await db_session.commit()
    return eq


async def _book(client, eq_id, days=1, hour=17, dur=60, key=None):
    s, e = slot(days=days, hour=hour, dur=dur)
    headers = {"Idempotency-Key": key} if key else {}
    return await client.post(
        f"/api/equipment/{eq_id}/reservations",
        json={"starts_at": iso(s), "ends_at": iso(e)},
        headers=headers,
    )


async def test_book_and_list(client, db_session, login):
    eq = await _setup(db_session)
    await login(subject="u-1")
    r = await _book(client, eq["id"] if isinstance(eq, dict) else eq.id)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "booked"
    mine = (await client.get("/api/me/reservations")).json()
    assert len(mine) == 1
    eq_res = (await client.get(f"/api/equipment/{eq.id}/reservations")).json()
    assert len(eq_res) == 1 and eq_res[0]["display_name"] == "User One"


async def test_book_requires_tier(client, db_session, login):
    eq = await make_equipment(db_session)
    await db_session.commit()
    await login(subject="nobody")
    r = await _book(client, eq.id)
    assert r.status_code == 403


async def test_overlap_conflict_and_back_to_back(client, db_session, login):
    eq = await _setup(db_session)
    await login(subject="u-1")
    assert (await _book(client, eq.id, hour=17, dur=60)).status_code == 201
    # overlapping
    assert (await _book(client, eq.id, hour=17, dur=60)).status_code == 409
    # back-to-back (18:00-19:00) is allowed
    assert (await _book(client, eq.id, hour=18, dur=60)).status_code == 201


async def test_validation(client, db_session, login):
    eq = await _setup(db_session)
    await login(subject="u-1")
    s, _ = slot(hour=17)
    bad = s.replace(minute=7)
    r = await client.post(
        f"/api/equipment/{eq.id}/reservations",
        json={"starts_at": iso(bad), "ends_at": iso(bad + timedelta(hours=1))},
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "slot_misaligned"
    # ends before starts
    r = await client.post(
        f"/api/equipment/{eq.id}/reservations",
        json={"starts_at": iso(s + timedelta(hours=1)), "ends_at": iso(s)},
    )
    assert r.status_code == 400
    # past
    ps, pe = slot(days=-1)
    r = await client.post(
        f"/api/equipment/{eq.id}/reservations",
        json={"starts_at": iso(ps), "ends_at": iso(pe)},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "starts_in_past"
    # too far ahead
    assert (await _book(client, eq.id, days=60)).json()["error"]["code"] == "advance_limit_exceeded"


async def test_modify(client, db_session, login):
    eq = await _setup(db_session)
    await login(subject="u-1")
    res = (await _book(client, eq.id, hour=17)).json()
    ns, ne = slot(hour=20)
    r = await client.patch(
        f"/api/reservations/{res['id']}", json={"starts_at": iso(ns), "ends_at": iso(ne)}
    )
    assert r.status_code == 200 and r.json()["starts_at"] == iso(ns)
    # old 17:00 slot is now free to book
    assert (await _book(client, eq.id, hour=17)).status_code == 201


async def test_modify_only_owner(client, db_session, login):
    eq = await _setup(db_session, subject="u-1")
    await make_grant(db_session, "u-2", ScopeKind.ITEM, eq.id, Tier.USER)
    await db_session.commit()
    await login(subject="u-1")
    res = (await _book(client, eq.id, hour=17)).json()
    await login(subject="u-2")
    ns, ne = slot(hour=20)
    r = await client.patch(
        f"/api/reservations/{res['id']}", json={"starts_at": iso(ns), "ends_at": iso(ne)}
    )
    assert r.status_code == 403


async def test_cancel_own_then_rebook(client, db_session, login):
    eq = await _setup(db_session)
    await login(subject="u-1")
    res = (await _book(client, eq.id, hour=17)).json()
    r = await client.delete(f"/api/reservations/{res['id']}")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert (await _book(client, eq.id, hour=17)).status_code == 201


async def test_admin_cancels_other_user_not(client, db_session, login):
    eq = await _setup(db_session, subject="u-1")
    await login(subject="u-1")
    res = (await _book(client, eq.id, hour=17)).json()
    # another user cannot cancel
    await login(subject="u-2")
    assert (await client.delete(f"/api/reservations/{res['id']}")).status_code == 403
    # admin can
    await login(subject="admin", groups=("admin-dibs",))
    assert (await client.delete(f"/api/reservations/{res['id']}")).status_code == 200


async def test_cancel_after_start_immutable(client, db_session, login):
    eq = await make_equipment(db_session)
    past = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
    res = await make_reservation(db_session, eq.id, "u-1", past, past + timedelta(hours=1))
    await db_session.commit()
    await login(subject="u-1")
    r = await client.delete(f"/api/reservations/{res.id}")
    assert r.status_code == 422 and r.json()["error"]["code"] == "reservation_immutable"


async def test_reserve_quota(client, db_session, login):
    eq = await make_equipment(db_session)
    await make_grant(db_session, "u-1", ScopeKind.ITEM, eq.id, Tier.USER)
    await make_quota_policy(
        db_session, QuotaType.RESERVE, "user:u-1", ScopeKind.ITEM, eq.id, QuotaWindow.DAY, 2
    )
    await db_session.commit()
    await login(subject="u-1")
    assert (await _book(client, eq.id, hour=17, dur=90)).status_code == 201  # 1.5h
    r = await _book(client, eq.id, hour=19, dur=60)  # +1h -> 2.5h > 2
    assert r.status_code == 422 and r.json()["error"]["code"] == "quota_exceeded"


async def test_reservation_list_respects_department_gate(client, db_session, login):
    gated = await make_class(db_session, name="Gated-res", department_groups=["group-eng"])
    eq = await make_equipment(db_session, klass=gated)
    await db_session.commit()
    await login(subject="outsider", groups=("group-hr",))
    assert (await client.get(f"/api/equipment/{eq.id}/reservations")).status_code == 404


async def test_idempotent_booking(client, db_session, login):
    eq = await _setup(db_session)
    await login(subject="u-1")
    key = str(uuid.uuid4())
    first = await _book(client, eq.id, hour=17, key=key)
    second = await _book(client, eq.id, hour=17, key=key)
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len((await client.get("/api/me/reservations")).json()) == 1
