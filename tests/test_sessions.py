from __future__ import annotations

from datetime import UTC, datetime, timedelta

from freezegun import freeze_time
from tests.factories import (
    make_equipment,
    make_grant,
    make_issue,
    make_node,
    make_quota_policy,
    make_session,
)

from dibs.enums import QuotaType, QuotaWindow, ScopeKind, Severity, Tier


async def _enable_gated_eq(db_session, subject="u-1", tier=Tier.USER):
    eq = await make_equipment(db_session)  # requires_enable defaults true on item+class
    if tier is not None:
        await make_grant(db_session, subject, ScopeKind.ITEM, eq.id, tier)
    await db_session.commit()
    return eq


async def test_enable_disable_cycle(client, db_session, login):
    eq = await _enable_gated_eq(db_session)
    await login(subject="u-1")
    r = await client.post(f"/api/equipment/{eq.id}/enable")
    assert r.status_code == 201, r.text
    # row shows holder
    row = (await client.get(f"/api/equipment/{eq.id}")).json()
    assert row["current_holder"]["subject"] == "u-1"
    # idempotent re-enable
    r2 = await client.post(f"/api/equipment/{eq.id}/enable")
    assert r2.status_code == 200 and r2.json()["id"] == r.json()["id"]
    # disable
    d = await client.post(f"/api/equipment/{eq.id}/disable")
    assert d.status_code == 200 and d.json()["end_cause"] == "user"
    # appears in history
    hist = (await client.get(f"/api/equipment/{eq.id}/history")).json()
    assert len(hist) == 1 and hist[0]["end_cause"] == "user"


async def test_enable_requires_tier(client, db_session, login):
    eq = await make_equipment(db_session)
    await db_session.commit()
    await login(subject="nobody")
    assert (await client.post(f"/api/equipment/{eq.id}/enable")).status_code == 403


async def test_enable_not_supported_on_no_enable(client, db_session, login):
    eq = await make_equipment(db_session, requires_enable=False)
    await make_grant(db_session, "u-1", ScopeKind.ITEM, eq.id, Tier.USER)
    await db_session.commit()
    await login(subject="u-1")
    r = await client.post(f"/api/equipment/{eq.id}/enable")
    assert r.status_code == 422 and r.json()["error"]["code"] == "enable_not_supported"


async def test_in_use_by_other(client, db_session, login):
    eq = await _enable_gated_eq(db_session, subject="u-1")
    await make_grant(db_session, "u-2", ScopeKind.ITEM, eq.id, Tier.USER)
    await db_session.commit()
    await login(subject="u-1")
    assert (await client.post(f"/api/equipment/{eq.id}/enable")).status_code == 201
    await login(subject="u-2")
    r = await client.post(f"/api/equipment/{eq.id}/enable")
    assert r.status_code == 409 and r.json()["error"]["code"] == "equipment_in_use"


async def test_fatal_blocks_user_admits_admin(client, db_session, login):
    eq = await _enable_gated_eq(db_session, subject="u-1")
    await make_issue(db_session, eq.id, severity=Severity.FATAL)
    await db_session.commit()
    await login(subject="u-1")
    r = await client.post(f"/api/equipment/{eq.id}/enable")
    assert r.status_code == 422 and r.json()["error"]["code"] == "fatal_fault_open"
    # admin admitted for diagnosis
    await login(subject="admin", groups=("admin-dibs",))
    assert (await client.post(f"/api/equipment/{eq.id}/enable")).status_code == 201


# Frozen mid-afternoon UTC (= mid-morning in the default PLATFORM_TZ) so the prior
# session sits wholly inside the current day window regardless of when CI runs.
# The usage-quota day window is boundary-aligned in PLATFORM_TZ, so a session
# placed relative to a real "now" near the local midnight would otherwise be
# clipped and under-count.
@freeze_time("2026-07-23 20:00:00")
async def test_usage_quota_blocks_enable(client, db_session, login):
    eq = await make_equipment(db_session)
    await make_grant(db_session, "u-1", ScopeKind.ITEM, eq.id, Tier.USER)
    await make_quota_policy(
        db_session, QuotaType.USAGE, "user:u-1", ScopeKind.ITEM, eq.id, QuotaWindow.DAY, 2
    )
    now = datetime.now(UTC)
    await make_session(db_session, eq.id, "u-1", now - timedelta(hours=3), now - timedelta(hours=1))
    await db_session.commit()
    await login(subject="u-1")
    r = await client.post(f"/api/equipment/{eq.id}/enable")
    assert r.status_code == 422 and r.json()["error"]["code"] == "quota_exceeded"


async def test_node_disabled_blocks_new_enable_not_reenable(client, db_session, login):
    eq = await _enable_gated_eq(db_session, subject="u-1")
    await db_session.commit()
    await login(subject="u-1")
    # enable while node enabled
    assert (await client.post(f"/api/equipment/{eq.id}/enable")).status_code == 201
    # admin disables the node mid-session: session persists, re-enable is idempotent
    await make_node(db_session, eq.id, enabled=False)
    await db_session.commit()
    r = await client.post(f"/api/equipment/{eq.id}/enable")
    assert r.status_code == 200  # same holder idempotent, not blocked
    # a different user cannot start a new session (in use)
    await make_grant(db_session, "u-2", ScopeKind.ITEM, eq.id, Tier.USER)
    await db_session.commit()
    await login(subject="u-2")
    assert (await client.post(f"/api/equipment/{eq.id}/enable")).json()["error"][
        "code"
    ] == "equipment_in_use"


async def test_node_disabled_blocks_fresh_enable(client, db_session, login):
    eq = await _enable_gated_eq(db_session, subject="u-1")
    await make_node(db_session, eq.id, enabled=False)
    await db_session.commit()
    await login(subject="u-1")
    r = await client.post(f"/api/equipment/{eq.id}/enable")
    assert r.status_code == 409 and r.json()["error"]["code"] == "node_disabled"


async def test_admin_force_close(client, db_session, login):
    eq = await _enable_gated_eq(db_session, subject="u-1")
    await db_session.commit()
    await login(subject="u-1")
    await client.post(f"/api/equipment/{eq.id}/enable")
    # non-holder non-admin cannot disable
    await login(subject="u-2")
    assert (await client.post(f"/api/equipment/{eq.id}/disable")).status_code == 403
    # admin force-closes another user's session
    await login(subject="admin", groups=("admin-dibs",))
    d = await client.post(f"/api/equipment/{eq.id}/disable")
    assert d.status_code == 200 and d.json()["end_cause"] == "admin"


async def test_disable_no_active_session(client, db_session, login):
    eq = await _enable_gated_eq(db_session, subject="u-1")
    await db_session.commit()
    await login(subject="u-1")
    r = await client.post(f"/api/equipment/{eq.id}/disable")
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_active_session"
