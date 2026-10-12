"""ForgeGuard: the strict CSP is sent on every response, offline or not."""

from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from comfy.cli_args import args
import server


async def pong(request):
    return web.Response(text="pong")


@pytest.mark.asyncio
@pytest.mark.parametrize("offline", [False, True])
async def test_csp_header_always_present(monkeypatch, offline):
    monkeypatch.setattr(args, "offline", offline)
    prompt_server = server.PromptServer(None, MagicMock(enabled=False))
    prompt_server.app.router.add_get("/ping", pong)
    async with TestClient(TestServer(prompt_server.app)) as client:
        resp = await client.get("/ping")
        assert resp.status == 200
        csp = resp.headers.get("Content-Security-Policy")
    assert csp is not None
    assert "connect-src 'self' data:" in csp
