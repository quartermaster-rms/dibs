from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from tests.factories import make_equipment, make_node, make_session

from dibs.device import keys, rate_limit
from dibs.device.keys import hash_key
from dibs.errors import RateLimited


def test_key_hash_verify():
    k = keys.generate_key()
    h = keys.hash_key(k)
    assert keys.verify_key(k, h) is True
    assert keys.verify_key("wrong", h) is False


async def test_rate_limit(clean_db):
    nid = uuid.uuid4()
    await rate_limit.enforce(nid, 2)
    await rate_limit.enforce(nid, 2)
    with pytest.raises(RateLimited):
        await rate_limit.enforce(nid, 2)


async def test_desired_state_no_session(device_client, db_session):
    eq = await make_equipment(db_session)
    node = await make_node(db_session, eq.id, key="k1", poll_interval_s=5)
    await db_session.commit()
    r = await device_client.get(
        f"/device/nodes/{node.id}/desired-state", headers={"Authorization": "Bearer k1"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False and body["context"] is None and body["ttl_seconds"] == 15


async def test_desired_state_live_session(device_client, db_session):
    eq = await make_equipment(db_session)
    node = await make_node(db_session, eq.id, key="k1")
    await make_session(db_session, eq.id, "u-1", datetime.now(UTC))
    await db_session.commit()
    r = await device_client.get(
        f"/device/nodes/{node.id}/desired-state", headers={"X-Node-Key": "k1"}
    )
    body = r.json()
    assert body["enabled"] is True and body["context"]["user_id"] == "u-1"


async def test_bad_and_missing_key(device_client, db_session):
    eq = await make_equipment(db_session)
    node = await make_node(db_session, eq.id, key="k1")
    await db_session.commit()
    assert (
        await device_client.get(
            f"/device/nodes/{node.id}/desired-state", headers={"Authorization": "Bearer wrong"}
        )
    ).status_code == 401
    assert (await device_client.get(f"/device/nodes/{node.id}/desired-state")).status_code == 401
    assert (
        await device_client.get(
            f"/device/nodes/{uuid.uuid4()}/desired-state", headers={"X-Node-Key": "k1"}
        )
    ).status_code == 401


async def test_key_rotation_grace(device_client, db_session):
    eq = await make_equipment(db_session)
    node = await make_node(db_session, eq.id, key="newkey")
    node.prev_key_hash = hash_key("oldkey")
    node.key_expiry = datetime.now(UTC) + timedelta(hours=1)
    await db_session.commit()
    for key in ("newkey", "oldkey"):
        r = await device_client.get(
            f"/device/nodes/{node.id}/desired-state", headers={"X-Node-Key": key}
        )
        assert r.status_code == 200


async def test_key_rotation_expired(device_client, db_session):
    eq = await make_equipment(db_session)
    node = await make_node(db_session, eq.id, key="newkey")
    node.prev_key_hash = hash_key("oldkey")
    node.key_expiry = datetime.now(UTC) - timedelta(hours=1)
    await db_session.commit()
    assert (
        await device_client.get(
            f"/device/nodes/{node.id}/desired-state", headers={"X-Node-Key": "oldkey"}
        )
    ).status_code == 401
    assert (
        await device_client.get(
            f"/device/nodes/{node.id}/desired-state", headers={"X-Node-Key": "newkey"}
        )
    ).status_code == 200


async def test_heartbeat_and_liveness(device_client, db_session):
    eq = await make_equipment(db_session)
    node = await make_node(db_session, eq.id, key="k1")
    node.offline = True
    await db_session.commit()
    r = await device_client.post(
        f"/device/nodes/{node.id}/heartbeat",
        json={"firmware": "v1.2"},
        headers={"X-Node-Key": "k1"},
    )
    assert r.status_code == 200 and r.json()["ok"] is True
    await db_session.refresh(node)
    assert node.last_firmware == "v1.2" and node.offline is False and node.last_heartbeat_at
    # heartbeat with no firmware still works
    r = await device_client.post(
        f"/device/nodes/{node.id}/heartbeat", json={}, headers={"X-Node-Key": "k1"}
    )
    assert r.status_code == 200


async def test_device_healthz(device_client):
    assert (await device_client.get("/healthz")).json()["status"] == "ok"
