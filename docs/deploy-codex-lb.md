# Codex-LB Deployment Report

Date: 2026-04-22  
Host path: `D:\domains\codex-lb`  
Deployment mode: Docker container from `ghcr.io/soju06/codex-lb:latest`

## What was done

1. Created persistent Docker volume:
   - `docker volume create codex-lb-data`
2. Deployed service container with restart policy:
   - `docker run -d --name codex-lb --restart unless-stopped -p 2455:2455 -p 1455:1455 -v codex-lb-data:/var/lib/codex-lb ghcr.io/soju06/codex-lb:latest`
3. Enabled protected proxy mode with API key authentication:
   - `api_key_auth_enabled = true` (persisted in dashboard settings)
4. Created dedicated API key for local Codex client:
   - key name: `codex-cli-local`
   - key format: `sk-clb-...`
5. Switched runtime to strict mode without local bridge exceptions:
   - running container has no `CODEX_LB_PROXY_UNAUTHENTICATED_CLIENT_CIDRS`
6. Verified readiness endpoint:
   - `http://127.0.0.1:2455/health/ready`
7. Verified dashboard endpoint:
   - `http://127.0.0.1:2455/`
## Codex CLI integration

Updated `C:\Users\User\.codex\config.toml`:

```toml
model_provider = "codex-lb"

[model_providers.codex-lb]
name = "OpenAI"
base_url = "http://127.0.0.1:2455/backend-api/codex"
wire_api = "responses"
env_key = "CODEX_LB_API_KEY"
supports_websockets = true
requires_openai_auth = true
```

Backup created before edits:
- `C:\Users\User\.codex\config.toml.bak-20260422-142003`

Proxy validation command:

```bash
codex exec "Reply with OK only."
```

Result:
- Request succeeded through `codex-lb`.
- Response: `OK`
- Container logs show accepted WebSocket on `/backend-api/codex/responses`.
- Secure-mode verification:
  - request without `Authorization` to `/v1/models` returns `401`
  - request with `Authorization: Bearer sk-clb-...` to `/v1/models` returns `200`

## Current runtime status

- Container: `codex-lb`
- Image: `ghcr.io/soju06/codex-lb:latest`
- Ports:
  - `2455` (dashboard + API)
  - `1455` (OAuth callback helper)
- Health check response: `{"status":"ok","checks":{"database":"ok"},...}`

## First login / bootstrap token

For remote first-run setup, get the bootstrap token from container logs:

```bash
docker logs codex-lb
```

Then open dashboard and complete initial password setup.

## Operational commands

```bash
docker ps --filter "name=codex-lb"
docker logs -f codex-lb
docker restart codex-lb
docker stop codex-lb
docker start codex-lb
```

## Notes

- Data persists in Docker volume `codex-lb-data`.
- `--restart unless-stopped` is configured for automatic recovery after Docker daemon or host restart.
- API key secret is intentionally not stored in repository documentation.
- Client secret is stored in user environment variable `CODEX_LB_API_KEY`.
- Daily usage instructions are documented in `docs/usage-guide.md`.

## 2026-04-22 VPS Migration Status

- A full data migration from local Docker volume to VPS Docker volume was executed.
- VPS container `codex-lb` is up and reachable on `http://168.222.194.228:2455`.
- Added upstream proxy chain through secondary VPS:
  - SOCKS5 endpoint on `89.23.105.29:49964`
  - local HTTP-to-SOCKS bridge (`gost`) on primary VPS: `127.0.0.1:18080`
- `codex-lb` upstream proxy env is now enabled on VPS:
  - `HTTP_PROXY=http://127.0.0.1:18080`
  - `HTTPS_PROXY=http://127.0.0.1:18080`
  - `ALL_PROXY=http://127.0.0.1:18080`
  - `CODEX_LB_UPSTREAM_WEBSOCKET_TRUST_ENV=true`
- Local Codex client is now configured to use VPS endpoint:
  - `base_url = "http://168.222.194.228:2455/backend-api/codex"`
- Validation:
  - `codex exec "Reply with OK only."` returns `OK` through VPS path.
- Local fallback container on this PC was stopped and removed after VPS validation.
- Detailed migration log: `docs/vps-migration-2026-04-22.md`.

## 2026-06-05 Server Update

- Local repository `main` was synced with `origin/main`; current upstream head:
  - `581322e4 chore(deps): bump the python-minor-patch group across 1 directory with 15 updates (#927)`
- On VPS `168.222.194.228`, the old container was running image digest `ghcr.io/soju06/codex-lb@sha256:932eacd59ffd640dfdbdc969aa5f28d05926fdfb2ff3241d1dd14cc1a48a6f97`.
- Pulled the new `latest` image and recreated the container with the same runtime settings:
  - `--restart unless-stopped`
  - `--network host`
  - volume `codex-lb-data:/var/lib/codex-lb`
  - env: `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`, `CODEX_LB_UPSTREAM_WEBSOCKET_TRUST_ENV`
- Current deployed image:
  - `ghcr.io/soju06/codex-lb@sha256:732cbb2d29b3f02ddacaf5aad6458e60fb926e58a5376cab1a288b9c866ea219`
  - image created: `2026-05-25T13:26:27Z`
- Post-update validation:
  - `/health/ready` returns `200` with `{"status":"ok","checks":{"database":"ok"},...}`
  - `/backend-api/codex/models` without auth returns `401` as expected
  - container accepted a live WebSocket connection immediately after restart
