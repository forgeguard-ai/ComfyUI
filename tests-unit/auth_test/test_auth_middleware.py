"""Integration tests for middleware/auth_middleware over a minimal aiohttp app."""

import asyncio

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from app.auth_manager import AuthManager
from middleware.auth_middleware import SESSION_COOKIE, create_auth_middleware


def make_app(auth):
    async def protected(request):
        return web.json_response({"ok": True})

    app = web.Application(middlewares=[create_auth_middleware(auth)])
    app.router.add_get("/protected", protected)
    app.router.add_get("/api/protected", protected)
    app.router.add_get("/ws", protected)  # stands in for the websocket route
    return app


def run(test_coro_factory):
    async def go():
        auth = test_coro_factory.auth
        async with TestClient(TestServer(make_app(auth))) as client:
            await test_coro_factory(client, auth)

    asyncio.run(go())


def with_auth(tmp_path, **kw):
    def deco(fn):
        fn.auth = AuthManager(state_dir=str(tmp_path), **kw)
        return fn

    return deco


def test_healthz_is_open(tmp_path):
    @with_auth(tmp_path)
    async def check(client, auth):
        for path in ("/healthz", "/api/healthz"):
            resp = await client.get(path)
            assert resp.status == 200
            assert (await resp.json()) == {"status": "ok"}

    run(check)


def test_protected_requires_credentials(tmp_path):
    @with_auth(tmp_path)
    async def check(client, auth):
        resp = await client.get("/protected")
        assert resp.status == 401
        assert (await resp.json())["error"] == "unauthorized"
        resp = await client.get("/api/protected")
        assert resp.status == 401
        resp = await client.get("/protected", headers={"Authorization": "Bearer wrong"})
        assert resp.status == 401

    run(check)


def test_bearer_and_x_api_key_grant_access(tmp_path):
    @with_auth(tmp_path, api_key="fgc_testkey")
    async def check(client, auth):
        resp = await client.get("/protected", headers={"Authorization": "Bearer fgc_testkey"})
        assert resp.status == 200
        resp = await client.get("/api/protected", headers={"X-API-Key": "fgc_testkey"})
        assert resp.status == 200

    run(check)


def test_html_get_redirects_to_login(tmp_path):
    @with_auth(tmp_path)
    async def check(client, auth):
        resp = await client.get(
            "/protected", headers={"Accept": "text/html"}, allow_redirects=False
        )
        assert resp.status == 303
        assert resp.headers["Location"] == "/auth/login"
        resp = await client.get("/auth/login")
        assert resp.status == 200
        assert "Sign in to ComfyUI" in (await resp.text())

    run(check)


def test_login_logout_cycle(tmp_path):
    @with_auth(tmp_path, password="correct-horse")
    async def check(client, auth):
        resp = await client.post("/auth/login", json={"password": "wrong"})
        assert resp.status == 401
        resp = await client.post("/auth/login", json={"password": "correct-horse"})
        assert resp.status == 200
        assert SESSION_COOKIE in resp.cookies
        # cookie jar now authenticates browser-style requests
        resp = await client.get("/protected")
        assert resp.status == 200
        resp = await client.get("/auth/status")
        assert (await resp.json()) == {"authenticated": True, "user": "comfy"}
        resp = await client.post("/auth/logout", allow_redirects=False)
        assert resp.status == 303
        client.session.cookie_jar.clear()
        resp = await client.get("/protected")
        assert resp.status == 401

    run(check)


def test_form_login_redirects(tmp_path):
    @with_auth(tmp_path, password="pw")
    async def check(client, auth):
        resp = await client.post(
            "/auth/login", data={"password": "nope"}, allow_redirects=False
        )
        assert resp.status == 303
        assert resp.headers["Location"] == "/auth/login?error=1"
        resp = await client.post(
            "/auth/login", data={"password": "pw"}, allow_redirects=False
        )
        assert resp.status == 303
        assert resp.headers["Location"] == "/"
        assert SESSION_COOKIE in resp.cookies

    run(check)


def test_ws_token_query_param(tmp_path):
    @with_auth(tmp_path, api_key="fgc_wskey")
    async def check(client, auth):
        resp = await client.get("/ws")
        assert resp.status == 401
        resp = await client.get("/ws", params={"token": "fgc_wskey"})
        assert resp.status == 200
        resp = await client.get("/ws", params={"token": auth.issue_session()})
        assert resp.status == 200
        # token query param is honored on /ws only
        resp = await client.get("/protected", params={"token": "fgc_wskey"})
        assert resp.status == 401

    run(check)


def test_login_rate_limit(tmp_path):
    @with_auth(tmp_path, password="pw")
    async def check(client, auth):
        auth.rate_limiter.max_attempts = 3
        for _ in range(3):
            resp = await client.post("/auth/login", json={"password": "bad"})
            assert resp.status == 401
        resp = await client.post("/auth/login", json={"password": "pw"})
        assert resp.status == 429

    run(check)


def test_auth_status_unauthenticated(tmp_path):
    @with_auth(tmp_path)
    async def check(client, auth):
        resp = await client.get("/auth/status")
        assert (await resp.json()) == {"authenticated": False, "user": None}

    run(check)
