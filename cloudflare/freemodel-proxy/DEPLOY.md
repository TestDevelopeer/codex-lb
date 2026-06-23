# Deploy guide — freemodel-proxy + codex-lb

End-to-end deployment of the Cloudflare Worker reverse proxy in front of
FreeModel, and the codex-lb configuration to route FreeModel traffic
through it.

```
Codex Desktop -> Codex LB (168.222.194.228) -> Cloudflare Worker -> api.freemodel.dev -> OpenAI
                          ^ X-Worker-Token shared secret
```

This guide is for the **operator** to run. No step requires sharing
secrets with anyone, and the LB host is accessed over SSH **key** (not
password).

---

## 0. Prerequisites

- A Cloudflare account (free plan is enough for Workers).
- Node.js 18+ and npm on the machine you deploy the Worker from (can be
  your laptop — not the LB host).
- SSH **key** access to the codex-lb host `168.222.194.228`.

> Security: rotate any password that may have leaked and disable SSH
> password auth for `root` on the LB host before continuing. Use a
> dedicated deploy user + SSH key.

---

## 1. Deploy the Worker (from your laptop)

```bash
cd cloudflare/freemodel-proxy
npm install
npx wrangler login            # one-time browser auth to your Cloudflare account
```

Set the shared secret the Worker will require (generate a long random
value; this never goes into git):

```bash
# Generate a secret, e.g.:
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Then store it in the Worker (prompts interactively):
npx wrangler secret put WORKER_PROXY_TOKEN
```

Deploy:

```bash
npm run deploy                # == wrangler deploy
```

Note the published URL, e.g.
`https://freemodel-proxy.<your-account>.workers.dev`.

### (Optional) Custom domain

If you prefer a custom domain (e.g. `fm.example.com`) instead of the
`*.workers.dev` subdomain, add a DNS record in the Cloudflare dashboard
and attach a Worker route / custom domain to the Worker. The codex-lb
config below uses whatever URL you choose.

### Smoke test

```bash
# Should return 401 (no token):
curl -i https://freemodel-proxy.<your-account>.workers.dev/v1/models

# Should reach the origin (200 from FreeModel, possibly 401 from
# FreeModel itself if the Bearer token is invalid — the point is the
# Worker let the request through):
curl -i -H "X-Worker-Token: <your-secret>" \
     -H "Authorization: Bearer <freemodel-key>" \
     https://freemodel-proxy.<your-account>.workers.dev/v1/models
```

---

## 2. Configure codex-lb to use the Worker (on the LB host)

SSH into the LB host with your key:

```bash
ssh -i ~/.ssh/<your-key> root@168.222.194.228
```

Find the codex-lb env file (depends on your install: systemd
`/etc/codex-lb/env`, docker-compose `.env`, etc.). Add / edit:

```dotenv
CODEX_LB_FREEMODEL_BASE_URL=https://freemodel-proxy.<your-account>.workers.dev
CODEX_LB_FREEMODEL_WORKER_TOKEN=<same value you set as WORKER_PROXY_TOKEN>
```

Restart codex-lb so the new env takes effect:

```bash
# systemd example:
systemctl restart codex-lb

# docker-compose example:
docker compose up -d --force-recreate codex-lb
```

Confirm codex-lb sees the new config (check the startup log or the
dashboard settings page). FreeModel requests should now go through the
Worker.

---

## 3. Verify the end-to-end path

From the LB host:

```bash
# Watch Worker logs in real time from your laptop:
npx wrangler tail freemodel-proxy

# Trigger a FreeModel request through codex-lb (e.g. a warmup or a real
# Codex Desktop turn against a freemodel account). In `wrangler tail`
# you should see the proxied request to /v1/responses or /v1/models
# returning 200 from the origin.
```

The apparent source IP seen by FreeModel will be a Cloudflare edge IP,
varying across requests — suitable for attribution testing on the
FreeModel side.

---

## 4. Roll back

To return to the direct origin instantly, unset both env vars on the LB
host and restart codex-lb:

```dotenv
# remove or comment out:
# CODEX_LB_FREEMODEL_BASE_URL=...
# CODEX_LB_FREEMODEL_WORKER_TOKEN=...
```

codex-lb will connect directly to `https://api.freemodel.dev` again with
no extra header. You can leave the Worker deployed (it is harmless with
the token gate) or remove it:

```bash
npx wrangler delete --name freemodel-proxy
```

---

## 5. Per-request egress-IP diversity

A single Worker gives Cloudflare-edge-level diversity. For genuine
cross-colo diversity in load tests, deploy regional Workers
(`freemodel-proxy-eu`, `-us`, `-ap`) and round-robin the
`CODEX_LB_FREEMODEL_BASE_URL` value between test runs, or front a single
Worker that rewrites the outbound `cf` metadata. See the
`Per-request egress diversity` section in `README.md`.

---

## Troubleshooting

- **`401` from the Worker on every FreeModel request:** the
  `CODEX_LB_FREEMODEL_WORKER_TOKEN` on the LB host does not match the
  Worker's `WORKER_PROXY_TOKEN` secret. Re-set both to the same value
  and restart.
- **`502 {"error":"bad_gateway"}` from the Worker:** the Worker could
  not reach `api.freemodel.dev`. Check `FREEMODEL_ORIGIN` in
  `wrangler.toml` and FreeModel availability.
- **FreeModel requests still hit the direct origin:** the LB did not
  pick up the new env. Confirm the env file the service actually reads
  and that the service was restarted.
- **Streaming responses cut off early:** verify you did not deploy a
  buffered variant; the committed Worker streams the body through. Also
  check codex-lb's `stream_idle_timeout_seconds`.
