from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from dibs.app import create_app
from dibs.config import Settings


async def test_unknown_api_is_json_404(client):
    r = await client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


async def test_spa_serving(tmp_path):
    static = tmp_path / "dist"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>dibs spa</html>")
    (static / "assets" / "app.js").write_text("console.log(1)")
    settings = Settings(auth_mode="stub", static_dir=str(static), cookie_secure=False)
    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # deep link falls back to index.html
        r = await c.get("/equipment/123")
        assert r.status_code == 200 and "dibs spa" in r.text
        # a real asset file is served
        r = await c.get("/assets/app.js")
        assert r.status_code == 200 and "console" in r.text
        # root serves index
        assert (await c.get("/")).status_code == 200
        # unknown /api/* is still a JSON 404, not the SPA
        r = await c.get("/api/nope")
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
