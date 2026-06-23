## ADDED Requirements

### Requirement: FreeModel upstream base URL is operator-configurable

The proxy MUST resolve the FreeModel upstream origin from the
`CODEX_LB_FREEMODEL_BASE_URL` setting, defaulting to
`https://api.freemodel.dev`. Every scenario elsewhere in this
specification that names `https://api.freemodel.dev` as the upstream
target MUST be read as "the currently configured FreeModel base URL",
so that operators MAY redirect FreeModel traffic to an operator-owned
reverse proxy (for example a Cloudflare Worker) without changing any
other provider behaviour.

#### Scenario: Default FreeModel base URL targets the direct origin

- **WHEN** the operator does not configure `CODEX_LB_FREEMODEL_BASE_URL`
- **THEN** FreeModel upstream requests MUST target `https://api.freemodel.dev`

#### Scenario: Configured FreeModel base URL targets an operator proxy

- **WHEN** the operator sets `CODEX_LB_FREEMODEL_BASE_URL=https://freemodel-proxy.example.com`
- **THEN** FreeModel upstream requests MUST target that origin instead of `https://api.freemodel.dev`
- **AND** request paths, query string, headers, and body MUST be identical to what would have been sent to the direct origin.

### Requirement: FreeModel Worker proxy requests carry a shared-secret header

When the configured FreeModel base URL is an operator-owned Cloudflare
Worker proxy (or any operator-owned reverse proxy that requires
authorization), the proxy MUST attach the configured shared secret as
the `X-Worker-Token` request header on every FreeModel upstream request.
The header value MUST be sourced from the `CODEX_LB_FREEMODEL_WORKER_TOKEN`
setting. When that setting is unset, the header MUST be omitted entirely
so the direct-origin default path is unaffected.

#### Scenario: Worker token header attached when configured

- **GIVEN** `CODEX_LB_FREEMODEL_BASE_URL` points at an operator proxy
- **AND** `CODEX_LB_FREEMODEL_WORKER_TOKEN` is set
- **WHEN** the proxy builds a FreeModel upstream request
- **THEN** the request MUST include `X-Worker-Token: <token>`

#### Scenario: Worker token header omitted when unset

- **WHEN** `CODEX_LB_FREEMODEL_WORKER_TOKEN` is not configured
- **THEN** no `X-Worker-Token` header MUST be added to FreeModel upstream requests
- **AND** requests to the default `https://api.freemodel.dev` origin MUST be byte-identical in headers to the pre-change behaviour.

## MODIFIED Requirements

### Requirement: Upstream paths and headers are selected per provider

The proxy MUST select upstream URL paths (`/codex/responses` vs
`/v1/responses`, `/codex/models` vs `/v1/models`), the upstream base
URL, and whether to emit the `chatgpt-account-id` header based on the
selected account's `provider`, via a provider registry. The FreeModel
upstream base URL MUST be resolved from `CODEX_LB_FREEMODEL_BASE_URL`
(default `https://api.freemodel.dev`); when that setting points at an
operator-owned proxy, the proxy MAY additionally emit the
`X-Worker-Token` header per the shared-secret requirement.

#### Scenario: FreeModel request omits chatgpt-account-id

- **GIVEN** a request is routed to a `freemodel` account
- **WHEN** the upstream request is built
- **THEN** the request MUST target `<CODEX_LB_FREEMODEL_BASE_URL>/v1/responses`
- **AND** it MUST NOT include a `chatgpt-account-id` header.
