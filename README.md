<div align="center">

# ComfyUI — ForgeGuard Fork

<!-- banner: docs/site/assets/repository/banner-dark.png (asset pending) -->

**A hardened, telemetry-free fork of [ComfyUI](https://github.com/comfyanonymous/ComfyUI) with built-in authentication and HTTPS — the engine inside [ComfyUI-Foundry](https://github.com/forgeguard-ai/comfyui-foundry) container images.**

<a href="https://github.com/comfyanonymous/ComfyUI"><img alt="Upstream" src="https://img.shields.io/badge/Upstream-comfyanonymous%2FComfyUI-FFD700?style=for-the-badge"></a>
<a href="https://github.com/forgeguard-ai/comfyui-foundry"><img alt="Images" src="https://img.shields.io/badge/Images-ComfyUI--Foundry-111820?style=for-the-badge&logo=github"></a>
<a href="./LICENSE"><img alt="License" src="https://img.shields.io/github/license/forgeguard-ai/ComfyUI?style=for-the-badge"></a>

</div>

> [!IMPORTANT]
> **ForgeGuard maintained fork of [`comfyanonymous/ComfyUI`](https://github.com/comfyanonymous/ComfyUI).**
> This fork changes behavior on purpose: it **removes every cloud-service integration and
> telemetry surface** and **adds built-in single-user authentication, API-key access, and
> first-class HTTPS**, so a ComfyUI instance can be exposed on a network without a reverse
> proxy. Core graph execution, nodes, and model behavior are unchanged and track upstream.
>
> [What changed](./docs/site/fork/forgeguard-changes.md) ·
> [Compatibility](./docs/site/fork/compatibility.md) ·
> [Upstream docs](https://docs.comfy.org/) ·
> Not affiliated with or endorsed by Comfy Org.

## What this fork changes

| Area | Delta vs upstream |
|---|---|
| Cloud/API nodes | `comfy_api_nodes/` (paid partner nodes proxied via api.comfy.org) **removed**, along with the staging-environment plumbing and the `--comfy-api-base` flag. |
| Telemetry | None existed in upstream core; this fork additionally strips the info-disclosing `argv` field from `/system_stats` and applies the no-external-connect CSP headers **unconditionally** (upstream only arms them with `--disable-api-nodes`). |
| Authentication | New: login page + session cookie for the UI, `Authorization: Bearer` / `X-API-Key` for the API, `?token=` for `/ws`. `--auth-mode auto` enforces auth whenever `--listen` binds a non-loopback address; loopback-only development is unchanged. |
| Health | New unauthenticated `GET /healthz` liveness endpoint. |
| Frontend | Served strictly from the pinned `comfyui-frontend-package`; downloading alternative frontends from GitHub requires an explicit `ALLOW_FRONTEND_DOWNLOAD=1` opt-in. |

Everything is delivered as a small, auditable patch set on top of upstream — see the
[change log for this fork](./docs/site/fork/forgeguard-changes.md).

## Quick start

Most users want the prebuilt, fully hardened container image instead of this source tree:
**[ComfyUI-Foundry](https://github.com/forgeguard-ai/comfyui-foundry)** packages this fork
together with the [ForgeGuard ComfyUI-Manager fork](https://github.com/forgeguard-ai/ComfyUI-Manager),
HTTPS, and generated credentials in a single `docker run`.

Running this fork bare-metal works exactly like upstream:

```bash
git clone https://github.com/forgeguard-ai/ComfyUI
cd ComfyUI
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
pip install -r requirements.txt
python main.py                       # local dev: auth stays off on 127.0.0.1
python main.py --listen 0.0.0.0      # network: auth enforces automatically
```

On first network start the generated **web password** and **API key** are printed once and
persisted under `auth/` (override with the `WEB_PASSWORD` / `API_KEY` environment variables or
`--password-file` / `--api-key-file`). Add `--tls-keyfile`/`--tls-certfile` for HTTPS.

```bash
curl -H "Authorization: Bearer $API_KEY" http://host:8188/api/system_stats
```

## Upstream tracking

- Upstream base: see [`FORK_UPSTREAM_BASE`](./FORK_UPSTREAM_BASE); the fork syncs to upstream
  tagged releases and re-validates the patch set each sync.
- Upstream product documentation lives at [docs.comfy.org](https://docs.comfy.org/) and applies
  to this fork except where [forgeguard-changes](./docs/site/fork/forgeguard-changes.md) says
  otherwise.

## License

GPL-3.0, same as upstream. ForgeGuard modifications are documented in the fork docs and the
commit history.
