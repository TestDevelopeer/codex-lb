# Codex-LB Usage Guide

Date: 2026-04-22  
Scope: daily usage with multiple ChatGPT accounts (example: 3 active accounts)

## 1) Daily workflow

1. Start `codex-lb` container (or keep it running with `--restart unless-stopped`).
2. Ensure accounts are `Active` on `http://127.0.0.1:2455/accounts`.
3. Use Codex CLI as usual (`codex`, `codex exec`, IDE integration) - requests go through `codex-lb`.
4. Observe distribution/errors in dashboard:
   - `Dashboard -> Request Logs`
   - `Dashboard -> Accounts` (usage bars, token status, reset timers)

## 2) Required Codex CLI config

`C:\Users\User\.codex\config.toml` must contain:

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

Set user environment variable once:

```powershell
setx CODEX_LB_API_KEY "sk-clb-..."
```

For current shell session immediately:

```powershell
$env:CODEX_LB_API_KEY = "sk-clb-..."
```

Quick check:

```bash
codex exec "Reply with OK only."
```

Expected output:
- `OK`

## 3) Recommended dashboard settings for 3 accounts

In `Settings -> Routing`:

- `sticky_threads_enabled = true`
  - Keeps a thread on the same account when possible (better context consistency).
- `routing_strategy = capacity_weighted` (default)
  - Distributes load by remaining capacity.
- `prefer_earlier_reset_accounts = true` (default)
  - Prefers accounts that reset earlier when it makes sense.
- `upstream_stream_transport = auto` (or `default`)
  - Uses best streaming transport automatically.

## 4) How balancing works (short)

- Paused/deactivated/rate-limited/quota-exceeded accounts are skipped.
- On transient limits/errors, balancer can fail over to next eligible account.
- With 3 active accounts, requests are automatically spread by configured strategy.

## 5) Security mode (active)

- API key auth is enabled.
- Proxy routes (`/v1/*`, `/backend-api/codex/*`, `/backend-api/transcribe`) require Bearer key.
- Deployment does not rely on unauthenticated local CIDR exceptions.

Quick checks:

```bash
# without Authorization -> should be 401
curl -i http://127.0.0.1:2455/v1/models

# with Authorization -> should be 200
curl -i -H "Authorization: Bearer $CODEX_LB_API_KEY" http://127.0.0.1:2455/v1/models
```

## 6) Useful operations

```bash
docker ps --filter "name=codex-lb"
docker logs -f codex-lb
curl http://127.0.0.1:2455/health/ready
```

If you see `401 Proxy authentication must be configured...`, check that:
- API key auth is enabled in dashboard settings.
- `CODEX_LB_API_KEY` is present in your environment.
- client sends `Authorization: Bearer sk-clb-...`.
