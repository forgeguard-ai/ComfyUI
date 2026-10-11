---
title: ForgeGuard changes
description: Every behavioral delta this fork carries against upstream ComfyUI.
---

# ForgeGuard changes

The fork's contract: **zero unsolicited network egress** and **secure-by-default exposure**.
Each sync against upstream re-validates this list; the egress canary test
(`tests-unit/forgeguard_egress_test.py`) enforces the removals mechanically.

## Removed

| Surface | Upstream location | Why |
|---|---|---|
| Partner/API nodes (all paid cloud nodes; every request proxied through `api.comfy.org` with client metadata headers; failure-path connectivity probe to google.com/baidu.com) | `comfy_api_nodes/` (~42 modules) | Cloud service integration |
| Staging-environment URL rewrites surfaced via `/features` | `comfy/comfy_api_env.py` | comfy.org infrastructure plumbing |
| `--comfy-api-base` flag | `comfy/cli_args.py` | Only consumer was the above |
| `argv` field (full process command line) in `GET /system_stats` | `server.py` | Information disclosure to unauthenticated callers in upstream |
| Dead `download_file` helper | `comfy/k_diffusion/utils.py` | Unused network code |

## Changed

| Behavior | Upstream | This fork |
|---|---|---|
| No-external-connect CSP + hardening headers (`connect-src 'self'`, nosniff, frame-deny, referrer) | Only with `--disable-api-nodes` | **Always on** |
| Downloading alternative frontends from GitHub (`--front-end-version`) | Allowed | Refused unless `ALLOW_FRONTEND_DOWNLOAD=1`; falls back to the installed `comfyui-frontend-package` |

## Added

| Feature | Details |
|---|---|
| Built-in authentication | `middleware/auth_middleware.py` + `app/auth_manager.py`. Login page + `SameSite=Strict` session cookie for the UI; `Authorization: Bearer` / `X-API-Key` for the API; `?token=` accepted on `/ws` only. Guards every route including `/api/*` duplicates, `/internal/*`, static mounts, and manager routes. Per-IP login rate limiting; scrypt password hashing; constant-time comparisons. |
| Auth flags | `--auth-mode {auto,on,off}` (auto = enforce when `--listen` is non-loopback), `--auth-state-dir`, `--api-key-file`, `--password-file`, `--session-ttl-hours`; env `API_KEY`, `WEB_PASSWORD`, `WEB_USER`. |
| Credential bootstrap | Env-or-generate: missing credentials are generated, persisted under the auth state dir (0600), and printed once. |
| `GET /healthz` | Unauthenticated `{"status":"ok"}` liveness probe (also at `/api/healthz`). `GET /system_stats` now requires auth. |
| Egress canary | `tests-unit/forgeguard_egress_test.py` fails the build if removed cloud references reappear. |
| Unit-suite setup | `tests-unit/conftest.py` puts CPU-only runs in CPU mode (upstream relied on the removed API-node tests for this). `tests-unit/app_test/conftest.py` opts upstream's frontend-download tests into `ALLOW_FRONTEND_DOWNLOAD=1`; `tests-unit/forgeguard_frontend_test.py` checks the default refusal. |

## Explicitly unchanged

Graph execution, nodes, samplers, model loading/paths, the frontend package, workflow
templates, custom-node loading, `--multi-user` (still unauthenticated header trust upstream —
unsupported in this distribution), and every performance flag.
