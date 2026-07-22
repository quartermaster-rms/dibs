from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.factories import make_equipment, make_grant, make_session

from dibs.enums import ScopeKind, Tier


async def test_settings_read_update_guarded(client, db_session, login):
    await login(subject="admin", groups=("admin-dibs",))
    s = (await client.get("/api/settings")).json()
    assert s["reservation_slot_granularity_minutes"] == 15
    r = await client.put("/api/settings", json={"max_reservation_days_advance": 60})
    assert r.status_code == 200 and r.json()["max_reservation_days_advance"] == 60
    assert (await client.put("/api/settings", json={"nope": 1})).status_code == 400
    await login(subject="user")
    assert (await client.get("/api/settings")).status_code == 403
    assert (
        await client.put("/api/settings", json={"max_reservation_days_advance": 5})
    ).status_code == 403


async def test_quota_policy_crud(client, db_session, login):
    eq = await make_equipment(db_session)
    await db_session.commit()
    await login(subject="admin", groups=("admin-dibs",))
    p = (
        await client.post(
            "/api/quota-policies",
            json={
                "quota_type": "reserve",
                "principal": "everyone",
                "target_kind": "item",
                "target_id": str(eq.id),
                "window": "day",
                "limit_hours": 4,
            },
        )
    ).json()
    assert len((await client.get("/api/quota-policies")).json()) == 1
    r = await client.patch(
        f"/api/quota-policies/{p['id']}", json={"limit_hours": 8, "active": False}
    )
    assert float(r.json()["limit_hours"]) == 8.0 and r.json()["active"] is False
    assert (await client.delete(f"/api/quota-policies/{p['id']}")).status_code == 204
    assert (await client.get("/api/quota-policies")).json() == []


async def test_analytics(client, db_session, login):
    eq = await make_equipment(db_session)
    now = datetime.now(UTC)
    await make_session(db_session, eq.id, "u-1", now - timedelta(hours=2), now - timedelta(hours=1))
    await db_session.commit()
    await login(subject="admin", groups=("admin-dibs",))
    data = (await client.get("/api/analytics/utilization")).json()
    entry = next(e for e in data["equipment"] if e["equipment_id"] == str(eq.id))
    assert entry["used_hours"] == 1.0 and entry["session_count"] == 1
    await login(subject="user")
    assert (await client.get("/api/analytics/utilization")).status_code == 403


async def test_audit_log(client, db_session, login):
    await login(subject="admin", groups=("admin-dibs",))
    await client.post("/api/locations", json={"building": "B", "room": "1"})
    log = (await client.get("/api/audit")).json()
    assert any(i["action"] == "location.create" and i["actor"] == "admin" for i in log["items"])
    filtered = (await client.get("/api/audit?action=location.create")).json()
    assert filtered["items"] and all(i["action"] == "location.create" for i in filtered["items"])
    await login(subject="user")
    assert (await client.get("/api/audit")).status_code == 403


async def test_audit_pagination(client, db_session, login):
    await login(subject="admin", groups=("admin-dibs",))
    for i in range(5):
        await client.post("/api/locations", json={"building": "B", "room": f"{i}"})
    page1 = (await client.get("/api/audit?limit=2")).json()
    assert len(page1["items"]) == 2 and page1["next_cursor"]
    page2 = (await client.get(f"/api/audit?limit=2&cursor={page1['next_cursor']}")).json()
    ids1 = {i["id"] for i in page1["items"]}
    ids2 = {i["id"] for i in page2["items"]}
    assert not (ids1 & ids2)


async def test_people_directory(client, db_session, login):
    eq = await make_equipment(db_session)
    await make_grant(db_session, "u-1", ScopeKind.CLASS, eq.class_id, Tier.SUPERUSER)
    await db_session.commit()
    await login(subject="u-1", display_name="User One", email="u1@x")
    await login(subject="admin", display_name="Admin", email="a@x", groups=("admin-dibs",))
    people = {p["subject"]: p for p in (await client.get("/api/people")).json()}
    assert people["admin"]["standing"] == "admin" and people["admin"]["grants"] == []
    assert people["u-1"]["standing"] == "user"
    assert any(g["tier"] == "superuser" for g in people["u-1"]["grants"])
