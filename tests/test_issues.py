from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.factories import make_class, make_equipment, make_grant, make_issue, make_reservation

from dibs.enums import ScopeKind, Severity, Tier


async def _file(client, eq_id, title="Broken", severity="fatal", description="desc"):
    return await client.post(
        f"/api/equipment/{eq_id}/issues",
        json={"title": title, "severity": severity, "description": description},
    )


async def test_file_changes_status_color(client, db_session, login):
    eq = await make_equipment(db_session)
    await db_session.commit()
    await login(subject="anyone")  # any user (none tier) can file
    r = await _file(client, eq.id, severity="warning")
    assert r.status_code == 201
    row = (await client.get(f"/api/equipment/{eq.id}")).json()
    assert row["status"] == {"color": "yellow", "open_fatal": 0, "open_warning": 1}
    await _file(client, eq.id, severity="fatal")
    row = (await client.get(f"/api/equipment/{eq.id}")).json()
    assert row["status"]["color"] == "red" and row["status"]["open_fatal"] == 1


async def test_close_admin_only_and_restores_green(client, db_session, login):
    eq = await make_equipment(db_session)
    await db_session.commit()
    await login(subject="u-1")
    issue = (await _file(client, eq.id, severity="fatal")).json()
    # non-admin cannot close
    assert (await client.post(f"/api/issues/{issue['id']}/close")).status_code == 403
    await login(subject="admin", groups=("admin-dibs",))
    r = await client.post(f"/api/issues/{issue['id']}/close")
    assert r.status_code == 200 and r.json()["status"] == "closed"
    row = (await client.get(f"/api/equipment/{eq.id}")).json()
    assert row["status"]["color"] == "green"


async def test_update_trail_and_closed_updates(client, db_session, login):
    eq = await make_equipment(db_session)
    await db_session.commit()
    await login(subject="u-1", display_name="User One")
    issue = (await _file(client, eq.id)).json()
    await login(subject="u-2", display_name="User Two")
    assert (
        await client.post(f"/api/issues/{issue['id']}/updates", json={"body": "seen it"})
    ).status_code == 201
    # close then still allow updates
    await login(subject="admin", groups=("admin-dibs",))
    await client.post(f"/api/issues/{issue['id']}/close")
    await login(subject="u-2", display_name="User Two")
    assert (
        await client.post(f"/api/issues/{issue['id']}/updates", json={"body": "after close"})
    ).status_code == 201
    detail = (await client.get(f"/api/issues/{issue['id']}")).json()
    assert detail["description"] == "desc"
    assert [u["body"] for u in detail["updates"]] == ["seen it", "after close"]
    assert detail["updates"][0]["author_name"] == "User Two"


async def test_photo_upload(client, db_session, login):
    eq = await make_equipment(db_session)
    await db_session.commit()
    await login(subject="u-1")
    issue = (await _file(client, eq.id)).json()
    r = await client.post(
        f"/api/issues/{issue['id']}/photos",
        files={"file": ("x.png", b"\x89PNG data", "image/png")},
    )
    assert r.status_code == 201 and r.json()["path"].endswith(".png")


async def test_red_green_notifies_upcoming_holders(client, db_session, login):
    eq = await make_equipment(db_session)
    future = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(
        days=1, hours=2
    )
    await make_reservation(db_session, eq.id, "holder", future, future + timedelta(hours=1))
    await db_session.commit()
    await login(subject="reporter")
    issue = (await _file(client, eq.id, severity="fatal")).json()
    await login(subject="holder")
    notes = (await client.get("/api/me/notifications")).json()
    assert any("out of service" in n["body"] for n in notes)
    # close -> back to green -> notified again
    await login(subject="admin", groups=("admin-dibs",))
    await client.post(f"/api/issues/{issue['id']}/close")
    await login(subject="holder")
    notes = (await client.get("/api/me/notifications")).json()
    assert any("back in service" in n["body"] for n in notes)


async def test_list_filters_and_reachability(client, db_session, login):
    open_cls = await make_class(db_session, name="Open")
    gated_cls = await make_class(db_session, name="Gated", department_groups=["group-eng"])
    eq_open = await make_equipment(db_session, klass=open_cls)
    eq_gated = await make_equipment(db_session, klass=gated_cls)
    await db_session.commit()
    await login(subject="admin", groups=("admin-dibs",))
    await _file(client, eq_open.id, severity="warning")
    await _file(client, eq_gated.id, severity="fatal")
    # admin sees both
    assert len((await client.get("/api/issues")).json()) == 2
    assert len((await client.get("/api/issues?severity=fatal")).json()) == 1
    # outsider only sees the open (reachable) one
    await login(subject="outsider", groups=("group-hr",))
    got = (await client.get("/api/issues")).json()
    assert len(got) == 1 and got[0]["equipment_id"] == str(eq_open.id)


async def test_issue_reads_and_writes_respect_department_gate(client, db_session, login):
    gated = await make_class(db_session, name="Gated-issues", department_groups=["group-eng"])
    eq = await make_equipment(db_session, klass=gated)
    issue = await make_issue(db_session, eq.id, severity=Severity.WARNING)
    await db_session.commit()
    await login(subject="outsider", groups=("group-hr",))
    assert (await client.get(f"/api/issues/{issue.id}")).status_code == 404
    assert (await client.get(f"/api/equipment/{eq.id}/issues")).status_code == 404
    assert (await _file(client, eq.id, severity="warning")).status_code == 404
    assert (
        await client.post(f"/api/issues/{issue.id}/updates", json={"body": "hi"})
    ).status_code == 404
    # a department member can reach it
    await login(subject="member", groups=("group-eng",))
    assert (await client.get(f"/api/issues/{issue.id}")).status_code == 200
    assert (await client.get(f"/api/equipment/{eq.id}/issues")).status_code == 200


async def test_filing_does_not_end_session(client, db_session, login):
    eq = await make_equipment(db_session)
    await make_grant(db_session, "u-1", ScopeKind.ITEM, eq.id, Tier.USER)
    await db_session.commit()
    await login(subject="u-1")
    await client.post(f"/api/equipment/{eq.id}/enable")
    await _file(client, eq.id, severity="fatal")  # red while in use
    row = (await client.get(f"/api/equipment/{eq.id}")).json()
    assert row["current_holder"]["subject"] == "u-1"  # session still live
