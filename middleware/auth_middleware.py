"""ForgeGuard authentication middleware.

One aiohttp middleware guards every route ComfyUI serves — including the
``/api``-prefixed duplicates, the ``/internal`` subapp, static mounts, custom
node routes, and the ``/ws`` websocket upgrade. It also answers a small set of
endpoints itself so the upstream route table needs no changes:

- ``GET /healthz``            — unauthenticated liveness probe (``{"status":"ok"}``)
- ``GET|POST /auth/login``    — login page / password check (rate-limited)
- ``POST /auth/logout``       — clears the session cookie
- ``GET /auth/status``        — ``{"authenticated": bool, "user": str|None}``

Accepted credentials, in order: ``Authorization: Bearer <key>`` or
``X-API-Key: <key>`` (API clients), a signed session cookie (browsers), or —
for ``/ws`` only, where browsers cannot set headers — a ``?token=<key>`` query
parameter carrying the API key or a session token.
"""

from __future__ import annotations

import logging

from aiohttp import web

from app.auth_manager import AuthManager

SESSION_COOKIE = "fg_session"

_LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ComfyUI — sign in</title>
<style>
  :root {{ color-scheme: dark light; }}
  body {{ margin: 0; min-height: 100vh; display: flex; align-items: center;
         justify-content: center; font-family: system-ui, sans-serif;
         background: #16191d; color: #e6e6e6; }}
  form {{ background: #1e2329; padding: 2.2rem 2.6rem; border-radius: 10px;
          border: 1px solid #2c333b; width: min(20rem, 86vw);
          box-shadow: 0 8px 30px rgba(0,0,0,.35); }}
  h1 {{ font-size: 1.05rem; font-weight: 600; margin: 0 0 1.2rem; }}
  input[type=password] {{ width: 100%; box-sizing: border-box; padding: .6rem .7rem;
          border-radius: 6px; border: 1px solid #3a424c; background: #14171b;
          color: inherit; font-size: 1rem; }}
  button {{ width: 100%; margin-top: 1rem; padding: .6rem; border: 0;
          border-radius: 6px; background: #3f6fd8; color: #fff; font-size: 1rem;
          cursor: pointer; }}
  button:hover {{ background: #4a7ce6; }}
  .err {{ color: #e08585; font-size: .85rem; margin: 0 0 .8rem; }}
  .hint {{ color: #8a939e; font-size: .75rem; margin-top: 1rem; }}
</style>
</head>
<body>
  <form method="post" action="/auth/login">
    <h1>Sign in to ComfyUI</h1>
    {error}
    <input type="password" name="password" placeholder="Password" autofocus
           autocomplete="current-password" required>
    <button type="submit">Sign in</button>
    <p class="hint">This instance requires authentication. API clients use an
    API key via the <code>Authorization: Bearer</code> or
    <code>X-API-Key</code> header.</p>
  </form>
</body>
</html>
"""


def _strip_api_prefix(path: str) -> str:
    return path[4:] if path.startswith("/api/") else path


def _extract_api_key(request: web.Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        return authorization[len("Bearer "):].strip()
    return request.headers.get("X-API-Key") or None


def _wants_html(request: web.Request) -> bool:
    return request.method == "GET" and "text/html" in request.headers.get("Accept", "")


def _set_session_cookie(response: web.StreamResponse, request: web.Request, auth: AuthManager) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        auth.issue_session(),
        max_age=auth.session_ttl_seconds,
        path="/",
        httponly=True,
        samesite="Strict",
        secure=request.secure,
    )


async def _read_password(request: web.Request) -> str | None:
    content_type = request.headers.get("Content-Type", "")
    try:
        if content_type.startswith("application/json"):
            data = await request.json()
            value = data.get("password") if isinstance(data, dict) else None
        else:
            form = await request.post()
            value = form.get("password")
    except Exception:
        return None
    return value if isinstance(value, str) else None


async def _handle_login(request: web.Request, auth: AuthManager) -> web.StreamResponse:
    if request.method == "GET":
        error = ""
        if request.query.get("error"):
            error = '<p class="err">Wrong password, or too many attempts — try again.</p>'
        return web.Response(text=_LOGIN_PAGE.format(error=error), content_type="text/html")
    if request.method != "POST":
        raise web.HTTPMethodNotAllowed(request.method, ["GET", "POST"])

    remote = request.remote or "unknown"
    is_json = request.headers.get("Content-Type", "").startswith("application/json")
    if not auth.rate_limiter.allow(remote):
        logging.warning("[auth] login rate limit hit from %s", remote)
        if is_json:
            return web.json_response({"error": "rate_limited"}, status=429)
        raise web.HTTPSeeOther("/auth/login?error=1")

    password = await _read_password(request)
    if password is not None and auth.verify_password(password):
        if is_json:
            response = web.json_response({"ok": True, "user": auth.username})
            _set_session_cookie(response, request, auth)
            return response
        redirect = web.HTTPSeeOther("/")
        _set_session_cookie(redirect, request, auth)
        raise redirect

    logging.warning("[auth] failed login from %s", remote)
    if is_json:
        return web.json_response({"error": "invalid_credentials"}, status=401)
    raise web.HTTPSeeOther("/auth/login?error=1")


def create_auth_middleware(auth: AuthManager):
    @web.middleware
    async def auth_middleware(request: web.Request, handler):
        path = _strip_api_prefix(request.path)

        if path == "/healthz":
            return web.json_response({"status": "ok"})

        if request.method == "OPTIONS":
            return await handler(request)

        if path == "/auth/login":
            return await _handle_login(request, auth)
        if path == "/auth/logout":
            if request.method != "POST":
                raise web.HTTPMethodNotAllowed(request.method, ["POST"])
            response = web.HTTPSeeOther("/auth/login")
            response.del_cookie(SESSION_COOKIE, path="/")
            raise response

        session_ok = auth.verify_session(request.cookies.get(SESSION_COOKIE))
        if path == "/auth/status":
            user = auth.username if session_ok else None
            return web.json_response({"authenticated": session_ok, "user": user})

        if session_ok:
            return await handler(request)
        if auth.verify_api_key(_extract_api_key(request)):
            return await handler(request)
        if path == "/ws":
            token = request.query.get("token")
            if token and (auth.verify_api_key(token) or auth.verify_session(token)):
                return await handler(request)

        if _wants_html(request):
            raise web.HTTPSeeOther("/auth/login")
        return web.json_response({"error": "unauthorized"}, status=401)

    return auth_middleware


__all__ = ["create_auth_middleware", "SESSION_COOKIE"]
