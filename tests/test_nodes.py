from __future__ import annotations

from tests.factories import make_equipment


async def test_provision_rotate_patch_delete(client, db_session, login):
    eq = await make_equipment(db_session)  # enable-gated by default
    await db_session.commit()
    await login(subject="admin", groups=("admin-dibs",))
    r = await client.post(
        "/api/nodes",
        json={"equipment_id": str(eq.id), "name": "door", "fail_state": "fail_enabled"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["key"] and body["fail_state"] == "fail_enabled" and body["has_prev_key"] is False
    node_id = body["id"]
    # listed on the equipment page; key never exposed after creation
    lst = (await client.get(f"/api/equipment/{eq.id}/nodes")).json()
    assert len(lst) == 1 and "key" not in lst[0]
    # rotate produces a new key and a prev key
    r = await client.post(f"/api/nodes/{node_id}/rotate-key")
    assert r.status_code == 200 and r.json()["key"] and r.json()["has_prev_key"] is True
    # patch (admin kill)
    r = await client.patch(f"/api/nodes/{node_id}", json={"enabled": False})
    assert r.json()["enabled"] is False
    assert (await client.delete(f"/api/nodes/{node_id}")).status_code == 204


async def test_node_requires_enable_gated(client, db_session, login):
    eq = await make_equipment(db_session, requires_enable=False)
    await db_session.commit()
    await login(subject="admin", groups=("admin-dibs",))
    r = await client.post(
        "/api/nodes", json={"equipment_id": str(eq.id), "fail_state": "fail_disabled"}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "enable_not_supported"


async def test_node_admin_only(client, db_session, login):
    eq = await make_equipment(db_session)
    await db_session.commit()
    await login(subject="user")
    assert (
        await client.post(
            "/api/nodes", json={"equipment_id": str(eq.id), "fail_state": "fail_enabled"}
        )
    ).status_code == 403
    assert (await client.get(f"/api/equipment/{eq.id}/nodes")).status_code == 403


async def test_multiple_nodes_and_ungate_blocked(client, db_session, login):
    eq = await make_equipment(db_session)
    await db_session.commit()
    await login(subject="admin", groups=("admin-dibs",))
    await client.post("/api/nodes", json={"equipment_id": str(eq.id), "fail_state": "fail_enabled"})
    await client.post(
        "/api/nodes", json={"equipment_id": str(eq.id), "fail_state": "fail_disabled"}
    )
    assert len((await client.get(f"/api/equipment/{eq.id}/nodes")).json()) == 2  # 0..N nodes
    # cannot un-gate equipment while nodes are linked (trigger)
    r = await client.patch(f"/api/equipment/{eq.id}", json={"requires_enable": False})
    assert r.status_code == 422
