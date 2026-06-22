# VPS Migration Report (2026-04-22)

## Scope

Move the existing local `codex-lb` runtime to VPS (`168.222.194.228`), preserve current data, route upstream traffic through an additional proxy server, and switch local Codex client to VPS endpoint.

## Migration Timeline

1. Local backup and state capture
   - Source Docker volume: `codex-lb-data`
   - Backup archive: `C:\Users\User\AppData\Local\Temp\codex-lb-migration-20260422-145629\codex-lb-data.tgz`
   - Archive contained `store.db*` and `encryption.key`.

2. Initial VPS restore
   - Uploaded archive to `/root/codex-lb-data.tgz`.
   - Restored into VPS volume `codex-lb-data`.
   - Started `codex-lb` on VPS and confirmed `http://168.222.194.228:2455/` returns `200`.

3. First issue discovered
   - Direct upstream from VPS to `chatgpt.com/backend-api` returned Cloudflare challenge `403`.
   - Initial attempt to pass SOCKS5 directly via `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY=socks5h://...` was not compatible in this image path:
     - websocket path required missing `python-socks`
     - some HTTP flows treated SOCKS URL as invalid HTTP proxy.

4. Final working proxy topology
   - Secondary server (`89.23.105.29`) exposes SOCKS5 (`49964`).
   - Deployed local bridge on primary VPS:
     - container: `socks-http-bridge`
     - image: `ginuerzh/gost`
     - listener: `http://127.0.0.1:18080`
     - forward chain: `SOCKS5 -> 89.23.105.29:49964`
   - Reconfigured `codex-lb` on primary VPS to use HTTP proxy env:
     - `HTTP_PROXY=http://127.0.0.1:18080`
     - `HTTPS_PROXY=http://127.0.0.1:18080`
     - `ALL_PROXY=http://127.0.0.1:18080`
     - `CODEX_LB_UPSTREAM_WEBSOCKET_TRUST_ENV=true`
   - Re-ran end-to-end test with local `codex` against VPS:
     - `codex exec "Reply with OK only."` -> `OK`

## Current Runtime State

- Primary VPS (`168.222.194.228`)
  - `codex-lb`: running
  - `socks-http-bridge`: running
  - service URL: `http://168.222.194.228:2455`
- Secondary VPS (`89.23.105.29`)
  - `amnezia-socks5proxy`: running on port `49964`

## Local Client Configuration

Updated `C:\Users\User\.codex\config.toml`:

- `base_url = "http://168.222.194.228:2455/backend-api/codex"`

Backup created before the final switch:

- `C:\Users\User\.codex\config.toml.bak-vps-proxy-enabled-20260422-154412`

## Local Container Decommissioning

After VPS validation, local `codex-lb` container on this PC was decommissioned.

Executed:

```bash
docker stop codex-lb
docker rm codex-lb
```

Optional volume cleanup (only if rollback is not needed):

```bash
docker volume rm codex-lb-data
```
