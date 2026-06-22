from __future__ import annotations

from datetime import datetime, timezone

from app.core.openai.error_normalization import apply_error_detail_normalization, normalize_openai_error
from app.core.openai.models import OpenAIError


def test_normalize_openai_error_infers_usage_limit_code_and_reset_at() -> None:
    error = OpenAIError(
        message="Usage limit reached, will reset on Jun 24 at 7:50 PM (UTC+8)",
        type="server_error",
        code=None,
    )

    normalized = normalize_openai_error(error)

    assert normalized is not None
    assert normalized.code == "usage_limit_reached"
    assert normalized.type == "server_error"
    assert normalized.resets_at == int(datetime(2026, 6, 24, 11, 50, tzinfo=timezone.utc).timestamp())


def test_apply_error_detail_normalization_preserves_existing_fields() -> None:
    detail = apply_error_detail_normalization(
        {
            "message": "Usage limit reached, will reset on Jun 24 at 7:50 PM (UTC+8)",
            "type": "usage_limit_reached",
            "plan_type": "freemodel",
        }
    )

    assert detail["type"] == "usage_limit_reached"
    assert detail["code"] == "usage_limit_reached"
    assert detail["plan_type"] == "freemodel"
    assert detail["resets_at"] == int(datetime(2026, 6, 24, 11, 50, tzinfo=timezone.utc).timestamp())
