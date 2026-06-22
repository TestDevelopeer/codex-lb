from __future__ import annotations

import pytest

from app.core.providers import AccountProvider, get_endpoint_for_provider, is_freemodel
from app.core.providers.registry import _freemodel_endpoint, _openai_endpoint
from app.db.models import Account, AccountStatus
from app.modules.accounts.auth_manager import AuthManager
from app.modules.accounts.service import AccountsService, InvalidAuthJsonError


def test_freemodel_endpoint_uses_v1_paths() -> None:
    endpoint = _freemodel_endpoint()
    assert endpoint.responses_path == "/v1/responses"
    assert endpoint.models_path == "/v1/models"
    assert endpoint.compact_path is None
    assert endpoint.compact_uses_responses_path is True
    assert endpoint.needs_account_id_header is False
    assert endpoint.needs_oauth_refresh is False
    assert endpoint.transport == "http"


def test_openai_endpoint_uses_codex_paths() -> None:
    endpoint = _openai_endpoint()
    assert endpoint.responses_path == "/codex/responses"
    assert endpoint.compact_path == "/codex/responses/compact"
    assert endpoint.compact_uses_responses_path is False
    assert endpoint.needs_account_id_header is True
    assert endpoint.needs_oauth_refresh is True


def test_freemodel_compact_can_parse_responses_payload() -> None:
    from app.core.clients.proxy import _compact_payload_from_responses_payload

    parsed = _compact_payload_from_responses_payload(
        {
            "id": "resp_fm_compact",
            "object": "response",
            "status": "completed",
            "output": [
                {
                    "id": "msg_fm_compact",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "compact summary"}],
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 3, "total_tokens": 13},
        }
    )

    assert parsed is not None
    assert parsed.object == "response.compaction"
    dumped = parsed.model_dump(mode="json", exclude_none=True)
    assert dumped["id"] == "resp_fm_compact"
    assert dumped["status"] == "completed"
    assert dumped["output"][0]["id"] == "msg_fm_compact"


def test_get_endpoint_for_provider_defaults_to_openai() -> None:
    endpoint = get_endpoint_for_provider(None)
    assert endpoint.responses_path == "/codex/responses"


def test_is_freemodel_predicate() -> None:
    assert is_freemodel(AccountProvider.FREEMODEL)
    assert is_freemodel("freemodel")
    assert not is_freemodel("openai")


@pytest.mark.asyncio
async def test_auth_manager_skips_refresh_for_freemodel_account() -> None:
    account = Account(
        id="fm_test",
        chatgpt_account_id=None,
        email="freemodel@test.local",
        plan_type="freemodel",
        provider="freemodel",
        access_token_encrypted=b"encrypted",
        refresh_token_encrypted=None,
        id_token_encrypted=None,
        last_refresh=__import__("app.core.utils.time", fromlist=["utcnow"]).utcnow(),
        status=AccountStatus.ACTIVE,
    )

    class _Repo:
        async def get_by_id(self, account_id: str) -> Account | None:
            return account

        async def update_tokens(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("update_tokens should not be called for freemodel")

    manager = AuthManager(_Repo())  # type: ignore[arg-type]
    refreshed = await manager.ensure_fresh(account, force=True)
    assert refreshed is account


@pytest.mark.asyncio
async def test_import_freemodel_key_rejects_empty_key() -> None:
    from app.modules.accounts.schemas import FreemodelImportRequest

    service = AccountsService(repo=None)  # type: ignore[arg-type]
    with pytest.raises(InvalidAuthJsonError):
        await service.import_freemodel_key(FreemodelImportRequest(api_key="   "))


@pytest.mark.asyncio
async def test_event_block_is_terminal_uses_raw_payload_type() -> None:
    from app.core.clients.proxy import _event_block_is_terminal
    from app.core.utils.sse import format_sse_event

    block = format_sse_event({"type": "response.completed", "response": {"id": "resp_test", "status": "completed"}})
    assert _event_block_is_terminal(block)


@pytest.mark.asyncio
async def test_connect_responses_websocket_uses_http_sse_for_freemodel(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.clients import proxy_websocket

    async def fail_websocket_connect(*args: object, **kwargs: object) -> object:
        raise AssertionError("websocket_connect must not be called for freemodel")

    monkeypatch.setattr(proxy_websocket, "websocket_connect", fail_websocket_connect)

    upstream = await proxy_websocket.connect_responses_websocket(
        {"user-agent": "test"},
        "fm-key",
        None,
        allow_direct_egress=True,
        provider="freemodel",
    )

    assert isinstance(upstream._wrapped, proxy_websocket.HttpSseResponsesUpstream)


def test_filter_accounts_for_model_excludes_freemodel_when_model_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.modules.proxy.load_balancer import _filter_accounts_for_model

    freemodel_account = SimpleNamespace(provider="freemodel", plan_type="freemodel")
    openai_account = SimpleNamespace(provider="openai", plan_type="plus")

    class _FakeRegistry:
        def plan_types_for_model(self, slug: str) -> frozenset[str]:
            if slug == "gpt-5.3-codex":
                return frozenset({"freemodel", "plus"})
            if slug == "gpt-5.4-mini":
                return frozenset({"plus", "pro"})
            return frozenset()

    monkeypatch.setattr(
        "app.modules.proxy.load_balancer.get_model_registry",
        lambda: _FakeRegistry(),
    )

    accounts = [freemodel_account, openai_account]
    codex_accounts = _filter_accounts_for_model(accounts, "gpt-5.3-codex")
    assert freemodel_account in codex_accounts
    assert openai_account in codex_accounts

    mini_accounts = _filter_accounts_for_model(accounts, "gpt-5.4-mini")
    assert freemodel_account not in mini_accounts
    assert mini_accounts == [openai_account]

    assert _filter_accounts_for_model([freemodel_account], "gpt-5.4-mini") == []
