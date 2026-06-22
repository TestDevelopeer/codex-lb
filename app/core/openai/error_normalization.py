from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from app.core.errors import OpenAIErrorDetail
from app.core.openai.models import OpenAIError

_USAGE_LIMIT_MESSAGE_PATTERN = re.compile(r"usage limit reached", re.IGNORECASE)
_RATE_LIMIT_MESSAGE_PATTERN = re.compile(r"rate limit", re.IGNORECASE)
_QUOTA_LIMIT_MESSAGE_PATTERN = re.compile(r"quota exceeded|insufficient quota", re.IGNORECASE)
_GENERIC_ERROR_CODES = frozenset({"upstream_error", "server_error", "error"})
_RESET_ON_PATTERN = re.compile(
    r"will reset on\s+"
    r"(?P<month>[A-Za-z]{3})\s+"
    r"(?P<day>\d{1,2})\s+at\s+"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*"
    r"(?P<ampm>AM|PM)\s*"
    r"\(UTC(?P<offset>[+-]\d{1,2})(?::(?P<offset_min>\d{2}))?\)",
    re.IGNORECASE,
)
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def normalize_openai_error(error: OpenAIError | None) -> OpenAIError | None:
    if error is None:
        return None
    if error.code and (error.resets_at is not None or error.resets_in_seconds is not None):
        return error

    message = (error.message or "").strip()
    if not message:
        return error

    updates: dict[str, object] = {}
    normalized_code = _infer_error_code(message)
    if normalized_code is not None and (not error.code or error.code in _GENERIC_ERROR_CODES):
        updates["code"] = normalized_code
    if normalized_code is not None and (error.type is None or error.type in _GENERIC_ERROR_CODES):
        updates["type"] = normalized_code
    if error.resets_at is None and error.resets_in_seconds is None:
        reset_at = _extract_reset_at_from_message(message)
        if reset_at is not None:
            updates["resets_at"] = reset_at
    if not updates:
        return error
    return error.model_copy(update=updates)


def apply_error_detail_normalization(detail: OpenAIErrorDetail) -> OpenAIErrorDetail:
    error = normalize_openai_error(OpenAIError.model_validate(detail))
    if error is None:
        return detail
    return error.model_dump(exclude_none=True)


def _infer_error_code(message: str) -> str | None:
    if _USAGE_LIMIT_MESSAGE_PATTERN.search(message):
        return "usage_limit_reached"
    if _QUOTA_LIMIT_MESSAGE_PATTERN.search(message):
        return "quota_exceeded"
    if _RATE_LIMIT_MESSAGE_PATTERN.search(message):
        return "rate_limit_exceeded"
    return None


def _extract_reset_at_from_message(message: str) -> int | None:
    match = _RESET_ON_PATTERN.search(message)
    if match is None:
        return None
    month = _MONTHS.get(match.group("month").lower())
    if month is None:
        return None

    day = int(match.group("day"))
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    ampm = match.group("ampm").upper()
    if hour == 12:
        hour = 0
    if ampm == "PM":
        hour += 12

    offset_hours = int(match.group("offset"))
    offset_minutes = int(match.group("offset_min") or "0")
    offset_sign = 1 if offset_hours >= 0 else -1
    total_offset_minutes = offset_hours * 60 + offset_sign * offset_minutes
    tzinfo = timezone.utc if total_offset_minutes == 0 else timezone(timedelta(minutes=total_offset_minutes))

    now = datetime.now(tzinfo)
    candidate = datetime(now.year, month, day, hour, minute, tzinfo=tzinfo)
    if candidate < now:
        candidate = datetime(now.year + 1, month, day, hour, minute, tzinfo=tzinfo)
    return int(candidate.astimezone(timezone.utc).timestamp())
