## Why

Operators running codex-lb against the FreeModel provider want to route
`freemodel` upstream traffic through a Cloudflare Worker acting as a
reverse proxy in front of `https://api.freemodel.dev`. The Worker gives
operators a single configurable egress layer in front of FreeModel and,
because Cloudflare Workers run on Cloudflare's globally distributed edge
network, naturally produces per-request egress-IP diversity across
Cloudflare colos. This is needed for realistic-load testing of request
recognition/attribution on the FreeModel service itself: a test harness
pointed at codex-lb can exercise many requests and observe how the
downstream service attributes traffic that arrives from the Cloudflare
edge rather than from a single static LB egress address.

codex-lb already selects the FreeModel upstream base URL purely from the
`CODEX_LB_FREEMODEL_BASE_URL` setting (see
`app/core/config/settings.py`, `freemodel_base_url`), so pointing the
load balancer at the Worker requires **no application code change** —
only an environment override plus the Worker deployment artifacts.

## What Changes

- Add a Cloudflare Worker reverse proxy artifact under
  `cloudflare/freemodel-proxy/` (`worker.js`, `wrangler.toml`,
  `package.json`, `README.md`) that forwards inbound requests to
  `https://api.freemodel.dev`:
  - Preserves HTTP method, path, query string, request headers, and
    request body (including streaming request bodies).
  - Strips hop-by-hop headers (`connection`, `keep-alive`,
    `proxy-authenticate`, `proxy-authorization`, `te`, `trailer`,
    `transfer-encoding`, `upgrade`, `host`) on both legs so the proxy is
    RFC 7230 compliant.
  - Streams the upstream response body back to the caller without
    buffering, preserving Server-Sent Events / chunked streaming for
    `/v1/responses?stream=true`.
  - Gate access with a shared secret: the caller (codex-lb) sends
    `X-Worker-Token`; the Worker compares it against the
    `WORKER_PROXY_TOKEN` secret and returns `401` on mismatch. This
    prevents the Worker from operating as an open proxy.
  - Optional upstream origin override via the `FREEMODEL_ORIGIN` Worker
    var (defaults to `https://api.freemodel.dev`).
- Document the new env contract for codex-lb:
  - `CODEX_LB_FREEMODEL_BASE_URL` MAY be set to the deployed Worker URL
    (e.g. `https://freemodel-proxy.<acct>.workers.dev` or a custom
    domain) to route FreeModel traffic through the Worker. The default
    value `https://api.freemodel.dev` is unchanged, so existing
    deployments that do not opt in behave exactly as before.
  - When the Worker is used, codex-lb MUST send the `X-Worker-Token`
    header on every FreeModel request. This header injection is the only
    application code change and is gated on the Worker base URL being
    configured.
- Add an OpenSpec delta under `deployment-networking` describing the
  optional Worker proxy hop, its header contract, and the streaming /
  secret requirements.

## Impact

- Operators gain an optional egress-diversity proxy layer for the
  FreeModel provider without changing any other provider behaviour.
- Deployments that do not set `CODEX_LB_FREEMODEL_BASE_URL` to a Worker
  URL keep identical behaviour (direct connection to
  `api.freemodel.dev`, no extra header).
- No changes to the proxy request/response contract, account routing,
  dashboard, OAuth flow, or any other operator-visible surface beyond
  the optional Worker header when the Worker base URL is configured.
- The Worker is a deployment artifact, not a runtime dependency of
  codex-lb: codex-lb continues to work if the Worker is removed, as long
  as `CODEX_LB_FREEMODEL_BASE_URL` is reset to the direct origin.
