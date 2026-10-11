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
| Partner/API nodes (all paid cloud nodes, including the Comfy Cloud nodes added in v0.39; every request proxied through `api.comfy.org` with client metadata headers; failure-path connectivity probe to google.com/baidu.com) | `comfy_api_nodes/` and `tests-unit/comfy_api_nodes_test/` — the whole directories, including files upstream adds later | Cloud service integration |
| Staging-environment URL rewrites surfaced via `/features` | `comfy/comfy_api_env.py` | comfy.org infrastructure plumbing |
| `--comfy-api-base` flag | `comfy/cli_args.py` | Only consumer was the above |
| Dead `download_file` helper | `comfy/k_diffusion/utils.py` | Unused network code |
| 21 upstream-only GitHub workflows (CLA bot, AI co-author check, PR-template injection, version auto-commits, stale bot, Cursor review, cloud/desktop dispatches, release webhooks, upstream release and Windows packaging builds, CI-container build, `api.comfy.org` stub refresh, `ci.comfy.org` GPU CI) | `.github/workflows/` | Need upstream secrets, call comfy.org services, or run upstream's own release/process automation |

## Changed

| Behavior | Upstream | This fork |
|---|---|---|
| No-external-connect CSP + hardening headers (`connect-src 'self'`, nosniff, frame-deny, referrer) | Only with `--offline` (or its deprecated alias `--disable-api-nodes`) | **Always on** — `--offline`, `--disable-api-nodes` and `--disable-partner-nodes` are accepted but change nothing here |
| `argv` in `GET /system_stats` | Full `sys.argv` verbatim — paths, URLs and secrets passed as flag values, to unauthenticated callers | Flag names only, every value dropped (`app/forgeguard_compat.py`); always includes `--disable-api-nodes`, the frontend's offline signal that suppresses its release-notes check; the endpoint requires auth |
| Downloading alternative frontends from GitHub (`--front-end-version`) | Allowed | Refused unless `ALLOW_FRONTEND_DOWNLOAD=1`; falls back to the installed `comfyui-frontend-package` |

## Added

| Feature | Details |
|---|---|
| Built-in authentication | `middleware/auth_middleware.py` + `app/auth_manager.py`. Login page + `SameSite=Strict` session cookie for the UI; `Authorization: Bearer` / `X-API-Key` for the API; `?token=` accepted on `/ws` only. Guards every route including `/api/*` duplicates, `/internal/*`, static mounts, and manager routes. Per-IP login rate limiting; scrypt password hashing; constant-time comparisons. |
| Auth flags | `--auth-mode {auto,on,off}` (auto = enforce when `--listen` is non-loopback), `--auth-state-dir`, `--api-key-file`, `--password-file`, `--session-ttl-hours`; env `API_KEY`, `WEB_PASSWORD`, `WEB_USER`. |
| Credential bootstrap | Env-or-generate: missing credentials are generated, persisted under the auth state dir (0600), and printed once. |
| `GET /healthz` | Unauthenticated `{"status":"ok"}` liveness probe (also at `/api/healthz`). `GET /system_stats` now requires auth. |
| Egress canary | `tests-unit/forgeguard_egress_test.py` fails the build if removed cloud references or directories reappear, and pins the workflow set: kept are `forgeguard-ci`, `ruff`, `check-line-endings`, `openapi-lint`, `test-build`, `test-execution`, `test-launch`, `test-unit` (code checks on GitHub-hosted runners, no secrets). |
| Unit-suite setup | `tests-unit/conftest.py` puts CPU-only runs in CPU mode (upstream relied on the removed API-node tests for this). `tests-unit/app_test/conftest.py` opts upstream's frontend-download tests into `ALLOW_FRONTEND_DOWNLOAD=1`; `tests-unit/forgeguard_frontend_test.py` checks the default refusal. `tests-unit/server_test/conftest.py` marks upstream's no-CSP case of `test_csp_header` as a strict expected failure, because CSP is always on; `server_test/forgeguard_csp_test.py` checks the header with and without `--offline`. |

## Explicitly unchanged

Graph execution, nodes, samplers, model loading/paths, the frontend package, workflow
templates, custom-node loading, `--multi-user` (still unauthenticated header trust upstream —
unsupported in this distribution), and every performance flag.

## Sync log

| Upstream | Notes |
|---|---|
| v0.33.0 | Initial fork point. |
| v0.39.2 | Merged (295 upstream commits). Conflicts: `server.py` (middleware block — upstream moved the CSP behind its new `--offline` flag; this fork keeps it unconditional with auth wired after it), `.github/workflows/ruff.yml`, `README.md`. Upstream added 11 files under the removed partner-node directories (incl. Comfy Cloud nodes); deleted again. 21 upstream-only workflows removed; workflow allowlist added to the canary. |
