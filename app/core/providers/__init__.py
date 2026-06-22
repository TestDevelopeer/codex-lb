"""Абстракция upstream-провайдера аккаунта.

Инкапсулирует различия между ChatGPT/OpenAI OAuth-аккаунтами и статичными
API-ключами OpenAI-совместимого провайдера FreeModel: пути эндпоинтов,
transport, заголовки, необходимость OAuth-refresh и usage-fetch.
"""

from app.core.providers.registry import (
    get_endpoint_for_provider,
    is_freemodel,
    is_openai,
)
from app.core.providers.types import AccountProvider, UpstreamEndpoint

__all__ = [
    "AccountProvider",
    "UpstreamEndpoint",
    "get_endpoint_for_provider",
    "is_freemodel",
    "is_openai",
]
