# freemodel-proxy

Cloudflare Worker that reverse-proxies the FreeModel provider
(`https://api.freemodel.dev`) for codex-lb. It preserves HTTP method,
path, query, headers and body, streams the response back unbuffered
(so SSE `/v1/responses?stream=true` keeps working), and gates access
behind a shared secret so it cannot be used as an open proxy.

```
Codex Desktop -> Codex LB -> [this Worker] -> api.freemodel.dev -> OpenAI
                       ^ X-Worker-Token gate
```

## Why

codex-lb already selects the FreeModel upstream base URL from the
`CODEX_LB_FREEMODEL_BASE_URL` setting. Pointing it at this Worker is an
environment override — no codex-lb code change is required to route
through it. Because the Worker runs on Cloudflare's globally distributed
edge network, requests naturally exit through different Cloudflare
colos, giving per-request egress-IP diversity. That is useful for
realistic-load testing of request recognition / attribution on the
FreeModel service, where the apparent source of the traffic must vary
rather than always coming from a single static LB egress address.

## Files

- `worker.js` — the Worker.
- `wrangler.toml` — Wrangler config; `FREEMODEL_ORIGIN` var defaults to
  `https://api.freemodel.dev`.
- `package.json` — `wrangler` dev dependency + `dev`/`deploy`/`tail`/`test`
  scripts.
- `test/worker.test.js` — Node-test-runner contract tests (no external
  deps).

## Local development

```bash
cd cloudflare/freemodel-proxy
npm install
npm run dev      # wrangler dev — serves the Worker locally
```

For local dev you can leave `WORKER_PROXY_TOKEN` unset (the token gate
is disabled when the secret is absent).

## Configure the shared secret

Set the secret via Wrangler (never commit it):

```bash
npx wrangler secret put WORKER_PROXY_TOKEN
# paste a long random string
```

When `WORKER_PROXY_TOKEN` is set, every inbound request MUST carry a
matching `X-Worker-Token` header or the Worker returns `401`. codex-lb
sends that header automatically when you set
`CODEX_LB_FREEMODEL_WORKER_TOKEN` to the same value on the LB host.

## Deploy

```bash
npm run deploy   # wrangler deploy
```

The Worker is reachable at `https://freemodel-proxy.<account>.workers.dev`
(or a custom domain you configure in the Cloudflare dashboard).

## Point codex-lb at the Worker

On the codex-lb host, set:

```dotenv
CODEX_LB_FREEMODEL_BASE_URL=https://freemodel-proxy.<account>.workers.dev
CODEX_LB_FREEMODEL_WORKER_TOKEN=<same value as WORKER_PROXY_TOKEN>
```

and restart codex-lb. To roll back, unset both and restart — codex-lb
returns to connecting directly to `api.freemodel.dev`.

## Run the contract tests

```bash
npm test         # node --test test/
```

## Per-request egress diversity — how it actually works

A Worker runs at the Cloudflare colo nearest the caller (here, the
codex-lb host). The simplest single-Worker deployment benefits from
Cloudflare's internal egress-IP pool rotation at the colo level. For
genuine cross-colo per-request diversity, deploy **multiple Workers**
(e.g. `freemodel-proxy-eu`, `freemodel-proxy-us`,
`freemodel-proxy-ap`) and round-robin between their URLs in your test
harness, or front them with a single Worker that rewrites the outbound
request's `cf` metadata.

## Platform limits

- Cloudflare Workers have a CPU-time budget (CPU time, not wall-clock);
  streaming response bodies are not charged against it the same way as
  request processing. codex-lb's own stream timeouts
  (`stream_idle_timeout_seconds`, `proxy_request_budget_seconds`)
  remain authoritative.
- If the origin fetch fails, the Worker returns a JSON `502`
  `{ "error": "bad_gateway", ... }`, which codex-lb treats as a
  retryable upstream failure per its existing retry policy.
