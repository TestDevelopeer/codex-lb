## ADDED Requirements

### Requirement: Account provider field distinguishes ChatGPT/OpenAI from FreeModel
Every account MUST carry a `provider` field whose value is one of `openai` (default, ChatGPT OAuth) or `freemodel` (static FreeModel API key). Existing accounts created before this change MUST be backfilled to `openai`.

#### Scenario: Existing accounts backfilled to openai provider
- **GIVEN** the database contains accounts created before the provider field existed
- **WHEN** the provider migration runs
- **THEN** every existing account MUST have `provider = "openai"`
- **AND** no account MUST be left without a provider value.

### Requirement: FreeModel accounts store only the encrypted API key
FreeModel accounts MUST store their static API key in `access_token_encrypted` and MUST leave `refresh_token_encrypted` and `id_token_encrypted` null, because FreeModel keys never need OAuth refresh.

#### Scenario: Importing a FreeModel key
- **WHEN** an admin imports a FreeModel API key via `POST /api/accounts/import-freemodel`
- **THEN** the stored account MUST have `provider = "freemodel"`
- **AND** `access_token_encrypted` MUST contain the encrypted API key
- **AND** `refresh_token_encrypted` and `id_token_encrypted` MUST be null.

### Requirement: Upstream paths and headers are selected per provider
The proxy MUST select upstream URL paths (`/codex/responses` vs `/v1/responses`, `/codex/models` vs `/v1/models`), the upstream base URL, and whether to emit the `chatgpt-account-id` header based on the selected account's `provider`, via a provider registry.

#### Scenario: FreeModel request omits chatgpt-account-id
- **GIVEN** a request is routed to a `freemodel` account
- **WHEN** the upstream request is built
- **THEN** the request MUST target `https://api.freemodel.dev/v1/responses`
- **AND** it MUST NOT include a `chatgpt-account-id` header.

### Requirement: FreeModel compact requests use the standard Responses endpoint
When a request is routed to a `freemodel` account, the proxy MUST satisfy `/backend-api/codex/responses/compact` and `/v1/responses/compact` by sending the sanitized compact payload to FreeModel's standard `/v1/responses` endpoint and adapting the successful Responses payload to a `response.compaction` response. It MUST NOT return local `unsupported_operation` solely because FreeModel lacks a provider-specific compact endpoint.

#### Scenario: FreeModel-only deployment compacts through /v1/responses
- **GIVEN** the only eligible account is a `freemodel` account
- **WHEN** Codex Desktop sends a compact request
- **THEN** the upstream request MUST target `https://api.freemodel.dev/v1/responses`
- **AND** the downstream response MUST have `object = "response.compaction"`.

### Requirement: FreeModel accounts skip OAuth refresh
The AuthManager MUST NOT attempt OAuth token refresh or `chatgpt-account-id` resolution for `freemodel` accounts, because they have no refresh token and no OpenAI id_token.

#### Scenario: FreeModel account never refreshes
- **GIVEN** a `freemodel` account has been stored
- **WHEN** `AuthManager.ensure_fresh` is invoked for that account
- **THEN** the account MUST be returned unchanged
- **AND** no request to `https://auth.openai.com/oauth/token` MUST be made.

### Requirement: FreeModel accounts are not filtered by plan_type
When the model registry has plan-based availability for a model, the load balancer MUST NOT filter `freemodel` accounts by `plan_type`, because FreeModel keys do not carry a ChatGPT plan.

#### Scenario: FreeModel account eligible for any model
- **GIVEN** the model registry reports `available_in_plans = ["plus", "pro"]` for a model
- **AND** a `freemodel` account has `plan_type = "freemodel"`
- **WHEN** the load balancer filters accounts for that model
- **THEN** the `freemodel` account MUST remain a candidate.

### Requirement: Dashboard exposes account provider
The account summary returned by `GET /api/accounts` MUST include the `provider` field so the dashboard can visually distinguish ChatGPT/OpenAI accounts from FreeModel accounts.

#### Scenario: Provider visible in account list
- **WHEN** the dashboard requests the account list
- **THEN** each account object MUST include a `provider` string equal to `openai` or `freemodel`.

### Requirement: FreeModel limit errors must block the account until the advertised reset
When a FreeModel upstream limit response only includes a human-readable message such as `Usage limit reached, will reset on ...`, the proxy MUST normalize that response into a rate-limit error with a concrete reset timestamp and MUST persist the account as unavailable until that reset elapses.

#### Scenario: Text-only FreeModel limit error becomes a persisted rate limit
- **GIVEN** a request is routed to a `freemodel` account
- **AND** the upstream returns HTTP `429` with an error message `Usage limit reached, will reset on Jun 24 at 7:50 PM (UTC+8)`
- **WHEN** codex-lb handles that upstream error
- **THEN** the downstream error MUST use code `usage_limit_reached`
- **AND** it MUST include `resets_at`
- **AND** the account row MUST be persisted with status `rate_limited`
- **AND** the load balancer MUST stop selecting that account until `resets_at` has elapsed.

### Requirement: Dashboard must expose runtime limit reset time even without usage windows
When an account is blocked by a persisted runtime `reset_at` but has no current usage-window snapshots, `GET /api/accounts` MUST still expose that recovery time separately so operators can see when the account becomes available again.

#### Scenario: FreeModel runtime reset is visible without quota rows
- **GIVEN** a `freemodel` account is persisted as `rate_limited`
- **AND** it has `reset_at` in the future
- **AND** it has no primary, secondary, or monthly usage rows
- **WHEN** the dashboard requests `GET /api/accounts`
- **THEN** the account summary MUST include `status_reset_at`
- **AND** the primary, secondary, and monthly reset fields MAY remain null.

### Requirement: FreeModel websocket fallback must avoid OpenAI-only previous-response continuations
When a websocket turn is relayed through FreeModel's HTTP Responses API fallback, the proxy MUST forward the prepared fresh-turn payload whenever the request state already has a retry-safe `fresh_upstream_request_text`. It MUST NOT reintroduce an OpenAI-only `previous_response_id` continuation into that FreeModel HTTP request solely because the original downstream websocket payload carried one.

#### Scenario: FreeModel HTTP relay drops websocket-v2-only previous_response_id
- **GIVEN** a downstream websocket turn was prepared with a retry-safe `fresh_upstream_request_text`
- **AND** the original websocket payload carried `previous_response_id`
- **WHEN** codex-lb relays that turn to FreeModel through the HTTP fallback path
- **THEN** the upstream FreeModel request MUST be built from the prepared fresh-turn payload
- **AND** the forwarded request MUST omit `previous_response_id`.
