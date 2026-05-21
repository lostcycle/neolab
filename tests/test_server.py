import pytest

from neolab.server import build_app


@pytest.fixture
def app():
    return build_app()


async def test_health(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.get("/api/health")
    assert resp.status == 200
    assert await resp.json() == {"ok": True, "service": "neolab"}


async def test_index(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.get("/")
    assert resp.status == 200
    assert resp.headers["content-type"].startswith("text/html")
    body = await resp.text()
    assert "neolab" in body


async def test_static_css(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.get("/static/style.css")
    assert resp.status == 200
    assert "--bg" in await resp.text()
