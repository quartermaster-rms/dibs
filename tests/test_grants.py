from __future__ import annotations

from tests.factories import make_class, make_equipment, make_grant

from dibs.enums import ScopeKind, Tier


async def test_admin_grants_and_roster(client, db_session, login):
    eq = await make_equipment(db_session)
    await db_session.commit()
    await login(subject="target", display_name="Target")  # create principal
    await login(subject="admin", groups=("admin-dibs",))
    r = await client.put(
        "/api/grants",
        json={"subject": "target", "scope_kind": "item", "scope_id": str(eq.id), "tier": "user"},
    )
    assert r.status_code == 200 and r.json()["tier"] == "user"
    roster = (await client.get(f"/api/equipment/{eq.id}/grants")).json()
    assert any(g["subject"] == "target" and g["display_name"] == "Target" for g in roster)
    # admins never appear in a roster
    assert all(not g.get("is_admin") for g in roster)
    # tier=none removes the grant
    await client.put(
        "/api/grants",
        json={"subject": "target", "scope_kind": "item", "scope_id": str(eq.id), "tier": "none"},
    )
    assert (await client.get(f"/api/equipment/{eq.id}/grants")).json() == []


async def test_superuser_promote_and_no_escalation(client, db_session, login):
    eq = await make_equipment(db_session)
    await make_grant(db_session, "su", ScopeKind.ITEM, eq.id, Tier.SUPERUSER, can_promote=True)
    await db_session.commit()
    await login(subject="target")
    await login(subject="su")
    # promote none -> user OK
    r = await client.put(
        "/api/grants",
        json={"subject": "target", "scope_kind": "item", "scope_id": str(eq.id), "tier": "user"},
    )
    assert r.status_code == 200
    # cannot grant superuser without the ability
    r = await client.put(
        "/api/grants",
        json={
            "subject": "target",
            "scope_kind": "item",
            "scope_id": str(eq.id),
            "tier": "superuser",
        },
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "grant_forbidden"


async def test_escalation_blocked(client, db_session, login):
    eq = await make_equipment(db_session)
    await make_grant(
        db_session, "su", ScopeKind.ITEM, eq.id, Tier.SUPERUSER, can_grant_superuser=True
    )
    await db_session.commit()
    await login(subject="target")
    await login(subject="su")
    # cannot confer promote it doesn't hold
    r = await client.put(
        "/api/grants",
        json={
            "subject": "target",
            "scope_kind": "item",
            "scope_id": str(eq.id),
            "tier": "superuser",
            "can_promote": True,
        },
    )
    assert r.status_code == 403
    # granting superuser with only abilities the actor holds is fine (explicit
    # empty flags; the default prefill includes promote, which the actor lacks)
    r = await client.put(
        "/api/grants",
        json={
            "subject": "target",
            "scope_kind": "item",
            "scope_id": str(eq.id),
            "tier": "superuser",
            "can_promote": False,
            "can_grant_superuser": True,
            "can_demote": False,
        },
    )
    assert r.status_code == 200


async def test_class_grant_covers_items(client, db_session, login):
    eq = await make_equipment(db_session)
    await make_grant(
        db_session, "su", ScopeKind.CLASS, eq.class_id, Tier.SUPERUSER, can_promote=True
    )
    await db_session.commit()
    await login(subject="target")
    await login(subject="su")
    # class-scoped superuser may promote an item in the class
    r = await client.put(
        "/api/grants",
        json={"subject": "target", "scope_kind": "item", "scope_id": str(eq.id), "tier": "user"},
    )
    assert r.status_code == 200


async def test_cannot_affect_admin(client, db_session, login):
    eq = await make_equipment(db_session)
    await db_session.commit()
    await login(subject="adminuser", groups=("admin-dibs",))  # principal is_admin
    await login(subject="admin", groups=("admin-dibs",))
    r = await client.put(
        "/api/grants",
        json={"subject": "adminuser", "scope_kind": "item", "scope_id": str(eq.id), "tier": "user"},
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "grant_forbidden"


async def test_my_abilities_in_equipment_detail(client, db_session, login):
    eq = await make_equipment(db_session)
    await make_grant(db_session, "su", ScopeKind.ITEM, eq.id, Tier.SUPERUSER, can_promote=True)
    await db_session.commit()
    # a superuser sees only the abilities its grant carries
    await login(subject="su")
    detail = (await client.get(f"/api/equipment/{eq.id}")).json()
    assert detail["my_abilities"] == {
        "can_promote": True,
        "can_grant_superuser": False,
        "can_demote": False,
    }
    # an admin holds all delegation abilities
    await login(subject="admin", groups=("admin-dibs",))
    detail = (await client.get(f"/api/equipment/{eq.id}")).json()
    assert detail["my_abilities"] == {
        "can_promote": True,
        "can_grant_superuser": True,
        "can_demote": True,
    }


async def test_grants_roster_and_quota_respect_department_gate(client, db_session, login):
    gated = await make_class(db_session, name="Gated-roster", department_groups=["group-eng"])
    eq = await make_equipment(db_session, klass=gated)
    await make_grant(db_session, "su", ScopeKind.ITEM, eq.id, Tier.SUPERUSER)
    await db_session.commit()
    # an outsider passes the dibs-wide gate but not the class department gate
    await login(subject="outsider", groups=("group-hr",))
    assert (await client.get(f"/api/equipment/{eq.id}/grants")).status_code == 404
    assert (await client.get(f"/api/classes/{gated.id}/grants")).status_code == 404
    assert (await client.get(f"/api/me/quota?equipment_id={eq.id}")).status_code == 404
    # a department member reaches all three
    await login(subject="member", groups=("group-eng",))
    assert (await client.get(f"/api/equipment/{eq.id}/grants")).status_code == 200
    assert (await client.get(f"/api/classes/{gated.id}/grants")).status_code == 200
    assert (await client.get(f"/api/me/quota?equipment_id={eq.id}")).status_code == 200


async def test_roster_demotable_reflects_peer_and_self_rules(client, db_session, login):
    eq = await make_equipment(db_session)
    await make_grant(db_session, "actor", ScopeKind.ITEM, eq.id, Tier.SUPERUSER, can_demote=True)
    await make_grant(db_session, "peer", ScopeKind.ITEM, eq.id, Tier.SUPERUSER)
    await make_grant(db_session, "plainuser", ScopeKind.ITEM, eq.id, Tier.USER)
    await db_session.commit()

    async def roster():
        rows = (await client.get(f"/api/equipment/{eq.id}/grants")).json()
        return {g["subject"]: g for g in rows}

    # a can_demote superuser may demote a plain user, but not a peer superuser
    # or itself while the peer/self settings are off (default)
    await login(subject="actor")
    r = await roster()
    assert r["plainuser"]["demotable"] is True
    assert r["peer"]["demotable"] is False
    assert r["actor"]["demotable"] is False
    # an admin may demote everyone in the roster
    await login(subject="admin", groups=("admin-dibs",))
    assert all(g["demotable"] for g in (await roster()).values())
    # enabling peer-demote makes the peer demotable; self stays off
    await client.put("/api/settings", json={"delegation_allow_peer_demote": True})
    await login(subject="actor")
    r = await roster()
    assert r["peer"]["demotable"] is True
    assert r["actor"]["demotable"] is False


async def test_peer_demote_setting(client, db_session, login):
    eq = await make_equipment(db_session)
    await make_grant(db_session, "actor", ScopeKind.ITEM, eq.id, Tier.SUPERUSER, can_demote=True)
    await make_grant(db_session, "peer", ScopeKind.ITEM, eq.id, Tier.SUPERUSER)
    await db_session.commit()
    await login(subject="peer")
    await login(subject="actor")
    body = {"subject": "peer", "scope_kind": "item", "scope_id": str(eq.id), "tier": "user"}
    assert (await client.put("/api/grants", json=body)).status_code == 403
    # admin enables peer-demote
    await login(subject="admin", groups=("admin-dibs",))
    await client.put("/api/settings", json={"delegation_allow_peer_demote": True})
    await login(subject="actor")
    assert (await client.put("/api/grants", json=body)).status_code == 200
