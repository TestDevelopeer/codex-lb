from __future__ import annotations

from functools import lru_cache

from app.core.config.settings import get_settings
from app.core.providers.types import AccountProvider, UpstreamEndpoint


def _openai_endpoint() -> UpstreamEndpoint:
    """Конфигурация upstream для ChatGPT/OpenAI OAuth-аккаунтов."""
    settings = get_settings()
    return UpstreamEndpoint(
        base_url=settings.upstream_base_url,
        responses_path="/codex/responses",
        compact_path="/codex/responses/compact",
        models_path="/codex/models",
        models_query_param="client_version",
        transcribe_path="/transcribe",
        usage_path="/wham/usage",
        usage_needs_backend_api_prefix=True,
        transport=settings.upstream_stream_transport,
        needs_account_id_header=True,
        needs_usage_fetch=True,
        needs_oauth_refresh=True,
        parse_models_as_data_list=False,
        compact_uses_responses_path=False,
    )


def _freemodel_endpoint() -> UpstreamEndpoint:
    """Конфигурация upstream для FreeModel (OpenAI-совместимый API)."""
    settings = get_settings()
    return UpstreamEndpoint(
        base_url=settings.freemodel_base_url,
        responses_path="/v1/responses",
        compact_path=None,
        models_path="/v1/models",
        models_query_param=None,
        transcribe_path="/v1/audio/transcriptions",
        usage_path=None,
        usage_needs_backend_api_prefix=False,
        transport="http",
        needs_account_id_header=False,
        needs_usage_fetch=False,
        needs_oauth_refresh=False,
        parse_models_as_data_list=True,
        compact_uses_responses_path=True,
    )


def get_endpoint_for_provider(provider: AccountProvider | str | None) -> UpstreamEndpoint:
    """Возвращает конфигурацию upstream-эндпоинтов для провайдера аккаунта.

    Unknown/None значения трактуется как ``openai`` (обратная совместимость).
    """
    resolved = AccountProvider.from_value(provider.value if isinstance(provider, AccountProvider) else provider)
    if resolved is AccountProvider.FREEMODEL:
        return _freemodel_endpoint()
    return _openai_endpoint()


def is_freemodel(provider: AccountProvider | str | None) -> bool:
    """Удобный предикат: провайдер аккаунта — FreeModel."""
    return AccountProvider.from_value(
        provider.value if isinstance(provider, AccountProvider) else provider
    ) is AccountProvider.FREEMODEL


def is_openai(provider: AccountProvider | str | None) -> bool:
    """Удобный предикат: провайдер аккаунта — ChatGPT/OpenAI (или неизвестный)."""
    return not is_freemodel(provider)
