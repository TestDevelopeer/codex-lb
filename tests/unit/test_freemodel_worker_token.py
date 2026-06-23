"""Tests for the X-Worker-Token header injection on FreeModel upstream requests.

See openspec/changes/add-freemodel-cloudflare-proxy/. The header is attached
to every FreeModel upstream request when ``settings.freemodel_worker_token``
is configured, and omitted entirely otherwise (default direct-origin path).
"""

from __future__ import annotations

import pytest

from app.core.clients.proxy import (
    _build_upstream_headers,
    _build_upstream_transcribe_headers,
    _build_upstream_websocket_headers,
)


def _settings_with_token(token: str | None):
    from types import SimpleNamespace

    return SimpleNamespace(freemodel_worker_token=token)


def test_build_upstream_headers_attaches_worker_token_for_freemodel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.core.clients.proxy.get_settings",
        lambda: _settings_with_token("secret-token"),
    )
    headers = _build_upstream_headers(
        {"user-agent": "test"},
        "fm-key",
        None,
        needs_account_id_header=False,
        is_freemodel=True,
    )
    assert headers["X-Worker-Token"] == "secret-token"
    # Authorization still present.
    assert headers["Authorization"] == "Bearer fm-key"
    # chatgpt-account-id must NOT be present for freemodel.
    assert all(k.lower() != "chatgpt-account-id" for k in headers)


def test_build_upstream_headers_omits_worker_token_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.core.clients.proxy.get_settings",
        lambda: _settings_with_token(None),
    )
    headers = _build_upstream_headers(
        {"user-agent": "test"},
        "fm-key",
        None,
        needs_account_id_header=False,
        is_freemodel=True,
    )
    assert all(k.lower() != "x-worker-token" for k in headers)


def test_build_upstream_headers_omits_worker_token_for_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Even when the token is configured, OpenAI-bridge requests must NOT
    # carry the FreeModel Worker token.
    monkeypatch.setattr(
        "app.core.clients.proxy.get_settings",
        lambda: _settings_with_token("secret-token"),
    )
    headers = _build_upstream_headers(
        {"user-agent": "test"},
        "oa-key",
        "acct-1",
        needs_account_id_header=True,
        is_freemodel=False,
    )
    assert all(k.lower() != "x-worker-token" for k in headers)
    assert headers["chatgpt-account-id"] == "acct-1"


def test_build_upstream_transcribe_headers_attaches_worker_token_for_freemodel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.core.clients.proxy.get_settings",
        lambda: _settings_with_token("secret-token"),
    )
    headers = _build_upstream_transcribe_headers(
        {"user-agent": "test", "x-openai-custom": "v"},
        "fm-key",
        None,
        needs_account_id_header=False,
        is_freemodel=True,
    )
    assert headers["X-Worker-Token"] == "secret-token"


def test_build_upstream_websocket_headers_attaches_worker_token_for_freemodel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.core.clients.proxy.get_settings",
        lambda: _settings_with_token("secret-token"),
    )
    headers = _build_upstream_websocket_headers(
        {"user-agent": "test"},
        "fm-key",
        None,
        needs_account_id_header=False,
        is_freemodel=True,
    )
    assert headers["X-Worker-Token"] == "secret-token"


def test_worker_token_helper_noop_without_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.clients.proxy import _maybe_apply_freemodel_worker_token

    monkeypatch.setattr(
        "app.core.clients.proxy.get_settings",
        lambda: _settings_with_token(None),
    )
    headers: dict[str, str] = {"Authorization": "Bearer x"}
    _maybe_apply_freemodel_worker_token(headers)
    assert headers == {"Authorization": "Bearer x"}


def test_worker_token_helper_adds_header_with_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.clients.proxy import _maybe_apply_freemodel_worker_token

    monkeypatch.setattr(
        "app.core.clients.proxy.get_settings",
        lambda: _settings_with_token("tok"),
    )
    headers: dict[str, str] = {}
    _maybe_apply_freemodel_worker_token(headers)
    assert headers == {"X-Worker-Token": "tok"}
