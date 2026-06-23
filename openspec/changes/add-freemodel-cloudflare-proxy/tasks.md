## 1. Cloudflare Worker artifact

- [x] 1.1 Create `cloudflare/freemodel-proxy/worker.js` implementing a
  reverse proxy to the FreeModel origin:
  - Read origin from `env.FREEMODEL_ORIGIN` (default `https://api.freemodel.dev`).
  - Read shared secret from `env.WORKER_PROXY_TOKEN`.
  - If `env.WORKER_PROXY_TOKEN` is set and the incoming request's
    `X-Worker-Token` header does not match, return `401` with a JSON
    error body.
  - Forward HTTP method, path, query string, request body, and request
    headers to the origin.
  - Strip hop-by-hop headers (`connection`, `keep-alive`,
    `proxy-authenticate`, `proxy-authorization`, `te`, `trailer`,
    `transfer-encoding`, `upgrade`, `host`) on both request and response
    legs.
  - Never forward the inbound `X-Worker-Token` to the origin (strip it
    before the origin fetch).
  - Return the upstream `Response` directly so the body streams through
    unbuffered (SSE / chunked).
  - Return a JSON `502` on origin fetch failure with the failure reason.
- [x] 1.2 Create `cloudflare/freemodel-proxy/wrangler.toml` with
  `name = "freemodel-proxy"`, `main = "worker.js"`, a current
  `compatibility_date`, and a `[vars]` block documenting
  `FREEMODEL_ORIGIN`. Document `WORKER_PROXY_TOKEN` as a secret set via
  `wrangler secret put` (never committed).
- [x] 1.3 Create `cloudflare/freemodel-proxy/package.json` with
  `wrangler` in `devDependencies` and `deploy` / `tail` npm scripts.
- [x] 1.4 Create `cloudflare/freemodel-proxy/README.md` covering local
  dev (`wrangler dev`), secret configuration (`wrangler secret put
  WORKER_PROXY_TOKEN`), deploy (`npm run deploy`), and the per-request
  egress-diversity property of the Cloudflare edge.

## 2. Load balancer integration (header injection, no routing change)

- [x] 2.1 In `app/core/config/settings.py`, add
  `freemodel_worker_token: str | None = None` (env
  `CODEX_LB_FREEMODEL_WORKER_TOKEN`).
- [x] 2.2 Where FreeModel upstream headers are assembled (the code path
  that builds FreeModel requests and currently omits
  `chatgpt-account-id`), inject `X-Worker-Token` from
  `settings.freemodel_worker_token` when that setting is set, for ALL
  FreeModel upstream call sites:
  - responses (`/v1/responses`),
  - models (`/v1/models`),
  - compact (`/v1/responses`),
  - transcribe (`/v1/audio/transcriptions`),
  - any warmup / model-refresh path.
- [x] 2.3 Ensure no header is added when `freemodel_worker_token` is
  `None` (default path identical to pre-change).

## 3. Documentation of the env contract

- [x] 3.1 Append `CODEX_LB_FREEMODEL_BASE_URL` and
  `CODEX_LB_FREEMODEL_WORKER_TOKEN` to `.env.example` with explanatory
  comments noting both default to direct-origin behaviour.

## 4. Tests

- [x] 4.1 `tests/unit/test_freemodel_worker_token.py`:
  - FreeModel request includes `X-Worker-Token` when the setting is set.
  - FreeModel request omits `X-Worker-Token` when the setting is `None`.
  - OpenAI-bridge path is unaffected (no `X-Worker-Token`).
- [x] 4.2 Worker contract test (`cloudflare/freemodel-proxy/test/worker.test.js`,
  Node test runner, no external deps):
  - Missing/mismatched `X-Worker-Token` returns `401`.
  - Matching token forwards method/path/query/body/headers (minus
    hop-by-hop and minus the inbound token) to the origin.
  - SSE response body streams through unbuffered.

## 5. Spec delta and validation

- [x] 5.1 Add the `freemodel-provider` delta spec at
  `openspec/changes/add-freemodel-cloudflare-proxy/specs/freemodel-provider/spec.md`.
- [ ] 5.2 `openspec validate --strict --specs` and
  `openspec validate --strict --changes` both pass. *(Could not run
  locally — OpenSpec CLI is not installed in this environment. To be
  executed in CI / by the operator.)*
- [x] 5.3 `uv run pytest tests/unit/test_freemodel_worker_token.py -q`
  passes (7 tests, run via the project's Python 3.13 interpreter).
- [x] 5.4 `uv run ruff check app/core/config/settings.py` (and any
  touched source files) introduces no new lint errors (pre-existing
  I001/E501 in `proxy_websocket.py` are unrelated to this change).
