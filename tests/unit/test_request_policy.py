from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.exceptions import ProxyModelNotAllowed
from app.core.openai.requests import ResponsesRequest
from app.modules.proxy.request_policy import apply_api_key_enforcement, validate_model_access


def test_gpt_55_extra_alias_targets_gpt_55_with_high_reasoning() -> None:
    request = ResponsesRequest.model_validate(
        {
            "model": "gpt-5.5-extra",
            "instructions": "",
            "input": [],
            "reasoning": {"effort": "low"},
        }
    )

    apply_api_key_enforcement(request, None)

    assert request.model == "gpt-5.5"
    assert request.reasoning is not None
    assert request.reasoning.effort == "high"


def test_model_access_accepts_allowed_canonical_model_alias() -> None:
    api_key = SimpleNamespace(allowed_models=frozenset({"gpt-5.5"}))

    validate_model_access(api_key, "gpt-5.5-extra")  # type: ignore[arg-type]


def test_model_access_rejects_alias_when_canonical_model_not_allowed() -> None:
    api_key = SimpleNamespace(allowed_models=frozenset({"gpt-5.2"}))

    with pytest.raises(ProxyModelNotAllowed):
        validate_model_access(api_key, "gpt-5.5-extra")  # type: ignore[arg-type]
