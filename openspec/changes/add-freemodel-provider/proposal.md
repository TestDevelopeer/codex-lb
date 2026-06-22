# Change: add FreeModel provider

## Why
codex-lb currently only supports ChatGPT/OpenAI OAuth accounts. Operators need to load-balance requests across multiple static API keys of the OpenAI-compatible provider FreeModel (`https://api.freemodel.dev`) the same way they already load-balance ChatGPT accounts. FreeModel uses simple Bearer API keys (no OAuth refresh, no `chatgpt-account-id`, no `/wham/usage`, no `plan_type`) and the standard OpenAI Responses API surface (`/v1/responses`, `/v1/models`).

## What changes
- Introduce an `Account.provider` field (`openai` | `freemodel`, default `openai`) on the existing `accounts` table.
- Make ChatGPT-only columns (`refresh_token_encrypted`, `id_token_encrypted`) nullable to allow FreeModel rows.
- Add a provider abstraction (`app/core/providers/`) that maps each provider to its upstream endpoint paths, transport, and header rules.
- Parameterize hard-coded upstream paths (`/codex/responses`, `/codex/models`, `/wham/usage`, `/transcribe`) to be selected per account provider.
- Skip OAuth refresh, `chatgpt-account-id` header, and `plan_type`-based model filtering for `freemodel` accounts.
- Add a dashboard endpoint `POST /api/accounts/import-freemodel` and UI dialog to import a FreeModel API key.
- Add `provider` to the account summary schema (backend + frontend) so the UI can distinguish account types.

## Non-goals
- No removal or degradation of existing ChatGPT/OpenAI OAuth support.
- No generic multi-provider plugin system; only `openai` and `freemodel` are first-class providers.
- No FreeModel OAuth flow or token refresh — FreeModel keys are static.
- No usage/quota endpoint polling for FreeModel unless FreeModel exposes a compatible `/v1/usage` endpoint (verified during implementation).
- No changes to the local Codex CLI configuration contract — clients keep pointing at `codex-lb` exactly as before.
