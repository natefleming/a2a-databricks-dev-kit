"""Shared pytest fixtures and env-gating helpers.

Mirrors the dao-ai pattern: integration tests are skipped when the workspace env vars
are absent, so unit tests stay green on a laptop.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest

from a2a_databricks.card import AgentCard, AgentSkill
from a2a_databricks.config import AppConfig, AuthMode, Environment


def has_databricks_env() -> bool:
    return bool(os.environ.get("DATABRICKS_HOST")) and bool(
        os.environ.get("DATABRICKS_TOKEN")
        or (
            os.environ.get("DATABRICKS_CLIENT_ID")
            and os.environ.get("DATABRICKS_CLIENT_SECRET")
        )
    )


@pytest.fixture
def app_config_dev(monkeypatch: pytest.MonkeyPatch) -> AppConfig:
    """An AppConfig wired for dev with bearer auth."""
    monkeypatch.setenv("A2A_AGENT_NAME", "test-agent")
    monkeypatch.setenv("A2A_ENV", "dev")
    monkeypatch.setenv("A2A_AUTH_MODE", "bearer")
    monkeypatch.setenv("A2A_LLM_ENDPOINT", "test-endpoint")
    monkeypatch.delenv("A2A_BEARER_SECRET_SCOPE", raising=False)
    monkeypatch.delenv("A2A_BEARER_SECRET_KEY", raising=False)
    return AppConfig()


@pytest.fixture
def agent_card(app_config_dev: AppConfig) -> AgentCard:
    return AgentCard.for_config(
        app_config_dev,
        endpoint_url="http://localhost:8080",
        skills=[
            AgentSkill(
                id="chat",
                name="Chat",
                description="Test chat skill.",
            )
        ],
    )


class EchoHandler:
    """Handler that echoes the text back. Used in transport tests."""

    async def handle(self, task: dict) -> dict:
        text = (task.get("message", task).get("parts") or [{}])[0].get("text", "")
        return {
            "status": {"state": "completed"},
            "artifacts": [
                {
                    "name": "echo",
                    "parts": [{"kind": "text", "text": f"echo: {text}"}],
                }
            ],
        }

    async def stream(self, task: dict) -> AsyncIterator[dict]:
        text = (task.get("message", task).get("parts") or [{}])[0].get("text", "")
        for word in (text or "").split():
            yield {"delta": {"text": word + " "}}
        yield {"status": "completed"}


@pytest.fixture
def echo_handler() -> EchoHandler:
    return EchoHandler()


@pytest.fixture
def integration_env() -> Iterator[None]:
    if not has_databricks_env():
        pytest.skip("Databricks workspace env vars not set; skipping integration.")
    yield


@pytest.fixture
def env_dev() -> Environment:
    return Environment.DEV


@pytest.fixture
def env_prod() -> Environment:
    return Environment.PROD


@pytest.fixture
def auth_bearer() -> AuthMode:
    return AuthMode.BEARER
