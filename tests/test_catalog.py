from __future__ import annotations


async def _mk_location(client, building="Building A", room="101"):
    r = await client.post("/api/locations", json={"building": building, "room": room})
    assert r.status_code == 201, r.text
    return r.json()


async def _mk_class(client, name="Lathes", **kw):
    r = await client.post("/api/classes", json={"name": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()


async def _mk_equipment(client, class_id, location_id, name="Lathe 1", **kw):
    r = await client.post(
        "/api/equipment",
        json={"name": name, "class_id": class_id, "location_id": location_id, **kw},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_admin_crud_and_listing(client, login):
    await login(subject="admin", groups=("admin-dibs",))
    loc = await _mk_location(client)
    cls = await _mk_class(client)
    eq = await _mk_equipment(client, cls["id"], loc["id"])
    assert eq["qr_token"]

    # list shows it with green status and admin can operate
    rows = (await client.get("/api/equipment")).json()
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "Lathe 1"
    assert row["status"] == {"color": "green", "open_fatal": 0, "open_warning": 0}
    assert row["is_admin"] and row["can_operate"]
    assert row["current_holder"] is None and row["next_reservation"] is None

    # detail + history + by-qr
    detail = (await client.get(f"/api/equipment/{eq['id']}")).json()
    assert detail["class"]["name"] == "Lathes"
    assert (await client.get(f"/api/equipment/{eq['id']}/history")).json() == []
    by_qr = (await client.get(f"/api/equipment/by-qr/{eq['qr_token']}")).json()
    assert by_qr["id"] == eq["id"]


async def test_non_admin_cannot_write(client, login):
    # first create as admin
    await login(subject="admin", groups=("admin-dibs",))
    await _mk_location(client)
    # a plain user cannot create
    await login(subject="user", groups=())
    r = await client.post("/api/locations", json={"building": "B", "room": "9"})
    assert r.status_code == 403
    # but can read
    assert (await client.get("/api/locations")).status_code == 200


async def test_search_filter(client, login):
    await login(subject="admin", groups=("admin-dibs",))
    loc = await _mk_location(client, room="Shop")
    cls = await _mk_class(client, name="Mills")
    await _mk_equipment(client, cls["id"], loc["id"], name="Bridgeport")
    assert len((await client.get("/api/equipment?q=bridge")).json()) == 1
    assert len((await client.get("/api/equipment?q=mills")).json()) == 1
    assert len((await client.get("/api/equipment?q=nope")).json()) == 0


async def test_department_gate_hides_equipment(client, login):
    await login(subject="admin", groups=("admin-dibs",))
    loc = await _mk_location(client)
    cls = await _mk_class(client, name="Restricted", department_groups=["group-eng"])
    eq = await _mk_equipment(client, cls["id"], loc["id"])
    # outsider cannot see it
    await login(subject="outsider", groups=("group-hr",))
    assert (await client.get("/api/equipment")).json() == []
    assert (await client.get(f"/api/equipment/{eq['id']}")).status_code == 404
    # member sees it, tier none (no grant), cannot operate
    await login(subject="member", groups=("group-eng",))
    rows = (await client.get("/api/equipment")).json()
    assert len(rows) == 1 and rows[0]["effective_tier"] == "none" and not rows[0]["can_operate"]


async def test_open_use_confers_user(client, login):
    await login(subject="admin", groups=("admin-dibs",))
    loc = await _mk_location(client)
    cls = await _mk_class(client, name="Open", open_use=True)
    await _mk_equipment(client, cls["id"], loc["id"])
    await login(subject="anyone", groups=())
    row = (await client.get("/api/equipment?authorized=true")).json()[0]
    assert row["effective_tier"] == "user" and row["can_operate"] and row["open_access"]


async def test_delete_guard(client, login):
    await login(subject="admin", groups=("admin-dibs",))
    loc = await _mk_location(client)
    cls = await _mk_class(client)
    eq = await _mk_equipment(client, cls["id"], loc["id"])
    # cannot delete a class still referenced by equipment
    r = await client.delete(f"/api/classes/{cls['id']}")
    assert r.status_code == 409
    # delete equipment first, then class
    assert (await client.delete(f"/api/equipment/{eq['id']}")).status_code == 204
    assert (await client.delete(f"/api/classes/{cls['id']}")).status_code == 204
