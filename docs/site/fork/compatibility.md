---
title: Compatibility
description: Upstream tracking policy and behavior notes for the ForgeGuard ComfyUI fork.
order: 20
status: beta
---

# Compatibility

- **Upstream base:** recorded in [`FORK_UPSTREAM_BASE`](https://github.com/forgeguard-ai/ComfyUI/blob/master/FORK_UPSTREAM_BASE) at the
  repository root. The fork tracks upstream **tagged releases**; syncs are merges (no history
  rewrites) followed by the patch-audit checklist in
  [forgeguard-changes](./forgeguard-changes.md).
- **Workflows, custom nodes, models:** unchanged — anything that runs on the matching upstream
  version runs here, except custom nodes that depended on the removed `comfy_api_nodes`
  partner-node classes.
- **API clients:** all upstream HTTP/WebSocket endpoints are unchanged in shape; when auth is
  enforced they additionally require an API key header (`Authorization: Bearer` or
  `X-API-Key`) or session cookie. `/ws` accepts `?token=`.
- **Local development:** with the default `--auth-mode auto`, binding only loopback keeps the
  upstream zero-auth experience. Upstream's own test workflows (`test-execution`,
  `test-unit`) run unmodified because they bind `127.0.0.1`; `test-launch` only
  checks out this fork instead of upstream's `Comfy-Org/ComfyUI`.
- **Offline flags:** upstream's `--offline`, its deprecated alias `--disable-api-nodes`, and
  `--disable-partner-nodes` are accepted for compatibility; they change nothing here because the
  CSP is always on and the partner nodes do not exist.
- **Frontend:** pinned via `requirements.txt` (`comfyui-frontend-package`); the ComfyUI-Foundry
  image additionally neutralizes the frontend bundle's telemetry endpoints at build time.
