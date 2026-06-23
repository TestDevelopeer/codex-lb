# Context: add-freemodel-cloudflare-proxy

## Purpose

Allow operators to route the `freemodel` provider's upstream traffic
through an operator-owned Cloudflare Worker acting as a reverse proxy
in front of `https://api.freemodel.dev`. The Worker provides a single
configurable egress layer and, because it executes on Cloudflare's
globally distributed edge network, naturally produces per-request
egress-IP diversity across Cloudflare colos.

## Rationale

- **No routing code change required.** codex-lb already selects the
  FreeModel upstream base URL purely from `CODEX_LB_FREEMODEL_BASE_URL`
  (`app/core/config/settings.py`, `freemodel_base_url`, default
  `https://api.freemodel.dev`). Pointing the load balancer at the Worker
  is therefore an environment override, not an application change.
- **Egress diversity is an emergent property of the Cloudflare edge.**
  Each `fetch(origin)` issued by a Worker is served by Cloudflare's
  network; different inbound requests are handled by different colos and
  therefore different egress IPs. This is useful for realistic-load
  testing of request recognition / attribution on the FreeModel service
  itself, where a test harness must exercise many requests whose
  apparent source varies rather than always coming from a single static
  LB egress address.
- **Shared-secret gating prevents open-proxy abuse.** Without an
  authorization check the Worker would proxy any caller to the FreeModel
  origin. The `X-Worker-Token` / `WORKER_PROXY_TOKEN` pair ensures only
  the operator's own codex-lb can use it.
- **Backward compatible by default.** Deployments that do not set
  `CODEX_LB_FREEMODEL_BASE_URL` to a Worker URL keep connecting directly
  to `api.freemodel.dev`, and the `X-Worker-Token` header is only
  attached when `CODEX_LB_FREEMODEL_WORKER_TOKEN` is configured.

## Decisions

- **Worker lives in-repo at `cloudflare/freemodel-proxy/`.** It is a
  deployment artifact, not a runtime dependency of codex-lb. Removing
  it (and resetting the env) returns codex-lb to direct-origin
  behaviour.
- **No custom DNS is required for the basic case** — the default
  `*.workers.dev` subdomain is sufficient. A custom domain
  (e.g. `fm.example.com`) is optional and configured separately in the
  Cloudflare dashboard or via the operator's DNS.
- **Streaming is preserved by returning the upstream `Response`
  directly** rather than buffering. This keeps `/v1/responses?stream=true`
  SSE working correctly.
- **Hop-by-hop headers are stripped on both legs** per RFC 7230 to keep
  the proxy well-behaved and avoid leaking the Worker's own connection
  control headers to the origin or back to codex-lb.

## Constraints

- Cloudflare Workers have a CPU-time budget (default subrequest CPU
  ~30s on the bundled plan; CPU time, not wall-clock). Streaming
  response bodies are not charged against this CPU budget the same way,
  but very long-running single requests may still hit platform limits.
  codex-lb's own stream timeouts (`stream_idle_timeout_seconds`,
  `proxy_request_budget_seconds`) remain the authoritative timeouts.
- The Worker must not be used to circumvent a provider's acceptable-use
  protections. This change exists to give operators an egress layer and
  realistic test diversity for their own FreeModel-side attribution
  testing; it is not a mechanism for hiding traffic source from a
  provider that the operator does not own or is not authorized to test.

## Failure modes

- **Wrong / missing `WORKER_PROXY_TOKEN`.** codex-lb will receive `401`
  from the Worker and surface it as an upstream error. Mitigation:
  verify `CODEX_LB_FREEMODEL_WORKER_TOKEN` on the LB matches the
  Worker secret; the Worker logs the mismatch reason.
- **Worker origin misconfiguration.** If `FREEMODEL_ORIGIN` is wrong,
  the Worker returns `502` with a JSON error body. codex-lb treats this
  as a retryable upstream failure per its existing retry policy.
- **Cloudflare outage / Worker not deployed.** codex-lb receives DNS or
  connection errors against the Worker URL. Operators can roll back
  instantly by unsetting `CODEX_LB_FREEMODEL_BASE_URL` (and the token
  env) to return to the direct origin.
- **Stale secret.** Rotating `WORKER_PROXY_TOKEN` requires updating
  both the Worker secret (`wrangler secret put`) and the LB env; a
  mismatch causes `401`s.

## Example

Operator wants to route FreeModel through a Worker deployed at
`https://freemodel-proxy.example.workers.dev`:

```dotenv
# .env on the codex-lb host
CODEX_LB_FREEMODEL_BASE_URL=https://freemodel-proxy.example.workers.dev
CODEX_LB_FREEMODEL_WORKER_TOKEN=<long-random-secret>
```

Worker side (`wrangler secret put WORKER_PROXY_TOKEN` set to the same
secret):

```
Codex Desktop -> Codex LB -> Cloudflare Worker -> api.freemodel.dev -> OpenAI
                       ^ X-Worker-Token gate
```

Each LB request reaches the Worker at the Cloudflare colo nearest the
LB host and is forwarded to `api.freemodel.dev`, with the apparent
source IP varying across the Cloudflare edge — suitable for
attribution testing on the FreeModel service.

## Per-request egress diversity — how it actually works

Cloudflare Workers run at the edge colo closest to the caller (here,
the codex-lb host). The Worker's `fetch(origin)` call is performed by
that colo's network. Because the edge network is anycast and the
caller-to-colo mapping is stable for a single host, the simplest
deployment yields the same colo per request. To obtain genuine
per-request egress-IP diversity across Cloudflare colos, raise
**multiple Workers** (e.g. one per region: `freemodel-proxy-eu`,
`freemodel-proxy-us`, `freemodel-proxy-ap`) and round-robin between
their URLs in the test harness, or front them with a single Worker that
explicitly rewrites the outbound request's `cf` metadata. The basic
single-Worker deployment already benefits from Cloudflare's internal
egress IP pool rotation at the colo level; the multi-Worker variant is
for operators who need cross-colo diversity.
