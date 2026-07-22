from __future__ import annotations


async def test_healthz_ok(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"db": "ok", "cache": "ok"}


async def test_metrics_exposed(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "dibs_http_requests_total" in resp.text


async def test_request_id_echoed(client):
    resp = await client.get("/healthz", headers={"X-Request-Id": "not-a-uuid"})
    # invalid id is replaced with a generated UUID
    rid = resp.headers["X-Request-Id"]
    assert len(rid) == 36


async def test_request_id_preserved(client):
    valid = "123e4567-e89b-12d3-a456-426614174000"
    resp = await client.get("/healthz", headers={"X-Request-Id": valid})
    assert resp.headers["X-Request-Id"] == valid
