from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AccountProvider(str, Enum):
    """Тип upstream-провайдера для аккаунта.

    ``openai`` — нативные ChatGPT/OpenAI OAuth-аккаунты (refresh-цикл,
    ``chatgpt-account-id``, пути ``/codex/*``, ``/wham/usage``).
    ``freemodel`` — статичные API-ключи OpenAI-совместимого провайдера
    FreeModel (``https://api.freemodel.dev``), без OAuth и без account-id.
    """

    OPENAI = "openai"
    FREEMODEL = "freemodel"

    @classmethod
    def from_value(cls, value: str | None) -> AccountProvider:
        """Нормализует значение провайдера из БД/настроек в enum.

        Неизвестные значения трактуем как ``openai`` (обратная совместимость
        со старыми строками до миграции поля ``provider``).
        """
        if not value:
            return cls.OPENAI
        try:
            return cls(value)
        except ValueError:
            return cls.OPENAI


@dataclass(frozen=True)
class UpstreamEndpoint:
    """Конфигурация upstream-эндпоинтов для конкретного провайдера.

    Инкапсулирует различия между ChatGPT (пути ``/codex/*``, нужен
    ``chatgpt-account-id``, usage через ``/wham/usage``) и FreeModel
    (пути ``/v1/*``, без account-id, без usage-fetch).
    """

    base_url: str
    responses_path: str
    compact_path: str | None
    models_path: str
    models_query_param: str | None
    transcribe_path: str
    usage_path: str | None
    usage_needs_backend_api_prefix: bool
    transport: str
    needs_account_id_header: bool
    needs_usage_fetch: bool
    needs_oauth_refresh: bool
    parse_models_as_data_list: bool
    compact_uses_responses_path: bool = False
