"""Tests for AppConfig env loading and validation."""

from __future__ import annotations

import pytest

from a2a_databricks.config import AppConfig, AuthMode, Environment


@pytest.mark.unit
def test_defaults_load_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "A2A_AGENT_NAME",
        "A2A_AUTH_MODE",
        "A2A_ENV",
        "A2A_LLM_ENDPOINT",
        "A2A_BEARER_SECRET_SCOPE",
        "A2A_BEARER_SECRET_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    config = AppConfig()
    assert config.agent_name == "my-a2a-agent"
    assert config.auth_mode == AuthMode.BEARER
    assert config.env == Environment.DEV


@pytest.mark.unit
def test_anonymous_rejected_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A2A_AUTH_MODE", "none")
    monkeypatch.setenv("A2A_ENV", "prod")
    with pytest.raises(ValueError, match="not allowed when A2A_ENV=prod"):
        AppConfig()


@pytest.mark.unit
def test_bearer_in_prod_requires_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A2A_AUTH_MODE", "bearer")
    monkeypatch.setenv("A2A_ENV", "prod")
    monkeypatch.delenv("A2A_BEARER_SECRET_SCOPE", raising=False)
    monkeypatch.delenv("A2A_BEARER_SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="requires A2A_BEARER_SECRET_SCOPE"):
        AppConfig()


@pytest.mark.unit
def test_bearer_in_prod_with_secret_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A2A_AUTH_MODE", "bearer")
    monkeypatch.setenv("A2A_ENV", "prod")
    monkeypatch.setenv("A2A_BEARER_SECRET_SCOPE", "my-scope")
    monkeypatch.setenv("A2A_BEARER_SECRET_KEY", "my-key")
    config = AppConfig()
    assert config.bearer_secret_scope == "my-scope"


@pytest.mark.unit
def test_oauth_requires_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A2A_AUTH_MODE", "oauth_m2m")
    monkeypatch.setenv("A2A_ENV", "dev")
    monkeypatch.delenv("A2A_OAUTH_AUDIENCE", raising=False)
    with pytest.raises(ValueError, match="requires A2A_OAUTH_AUDIENCE"):
        AppConfig()
