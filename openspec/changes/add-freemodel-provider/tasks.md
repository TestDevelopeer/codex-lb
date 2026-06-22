# Tasks

## 1. Provider foundation
- [ ] Add `Account.provider` column with Alembic migration (`down_revision = "20260611_000000_merge_dashboard_guest_and_weekly_useragent_heads"`), backfill existing rows to `openai`, make `refresh_token_encrypted` and `id_token_encrypted` nullable.
- [ ] Update `app/db/models.py` `Account` model: add `provider` field, mark nullable columns.
- [ ] Add `app/core/providers/types.py` with `AccountProvider` enum (`openai`, `freemodel`) and `UpstreamEndpoint` dataclass.
- [ ] Add `app/core/providers/registry.py` mapping each provider to base_url + paths + transport + header flags + usage fetch flag.
- [ ] Add `freemodel_base_url` and `freemodel_models_path` settings to `app/core/config/settings.py`.

## 2. Upstream client parameterization
- [ ] Parameterize `stream_responses` URL path in `app/core/clients/proxy.py` via provider endpoint config.
- [ ] Parameterize `compact_responses` URL path and add base_url override.
- [ ] Adapt FreeModel compact requests through `/v1/responses` and return a `response.compaction` payload.
- [ ] Parameterize `transcribe_audio` URL path.
- [ ] Skip `chatgpt-account-id` header in `_build_upstream_headers` when provider endpoint reports `needs_account_id_header=False`.
- [ ] Force HTTP transport for `freemodel` (no websocket upstream).

## 3. OAuth refresh and account lifecycle
- [ ] Guard `AuthManager.ensure_fresh` in `app/modules/accounts/auth_manager.py` to skip refresh + `_ensure_chatgpt_account_id` for `freemodel` accounts.
- [ ] Adapt `_filter_accounts_for_model` in `app/modules/proxy/load_balancer.py` to skip `plan_type` filtering for `freemodel` accounts.
- [ ] Adapt `model_refresh_scheduler` to group `freemodel` accounts by provider (not plan_type) and fetch `/v1/models`.

## 4. Import API and service
- [ ] Add `AccountsService.import_freemodel_key` in `app/modules/accounts/service.py` that encrypts the API key and creates an `Account(provider=freemodel)`.
- [ ] Add `POST /api/accounts/import-freemodel` endpoint in `app/modules/accounts/api.py` accepting JSON `{api_key, label?}`.
- [ ] Add Pydantic schemas for freemodel import request/response in `app/modules/accounts/schemas.py`.
- [ ] Adapt account mappers to omit refresh/id_token decryption for `freemodel` and expose `provider` in `AccountSummary`.

## 5. Frontend
- [ ] Add `provider` field to `AccountSummarySchema` in `frontend/src/features/accounts/schemas.ts`.
- [ ] Add `importFreemodelKey` API call and mutation hook.
- [ ] Add `freemodel-import-dialog.tsx` component (text input for API key + optional label).
- [ ] Add provider badge in `account-list-item.tsx` and an "Add FreeModel Key" button in `account-list.tsx`.

## 6. Proxy service wiring
- [ ] Resolve provider endpoint config from the selected account in `proxy/service.py` and pass `base_url`/paths to upstream client calls.
- [ ] Normalize text-only FreeModel limit errors into persisted `usage_limit_reached` / `resets_at` account blocks.
- [ ] Expose runtime `status_reset_at` in account summaries when no usage-window reset is available.
- [ ] Ensure FreeModel warmup and websocket HTTP fallback preserve provider-aware compact routing and do not replay OpenAI-only `previous_response_id` continuations.

## 7. Validation
- [ ] `openspec validate --specs` passes.
- [ ] Unit tests: provider registry, freemodel import, AuthManager guard, URL/header building.
- [ ] Smoke test: import a freemodel key, send a request through `/backend-api/codex/responses`, receive response from FreeModel.
- [ ] Regression: existing ChatGPT path unchanged.

## 8. Deploy
- [ ] Build Docker image and deploy to VPS 168.222.194.228.
- [ ] Import freemodel keys via dashboard and verify load balancing.
