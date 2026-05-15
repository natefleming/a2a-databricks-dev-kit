"""Tests for AgentCard serialization."""

from __future__ import annotations

import json

import pytest

from a2a_databricks.card import AgentCard, AgentSkill
from a2a_databricks.config import AppConfig, AuthMode


@pytest.mark.unit
def test_card_bearer_advertises_http_bearer(app_config_dev: AppConfig) -> None:
    card = AgentCard.for_config(
        app_config_dev,
        endpoint_url="https://example.com/apps/my-agent",
        skills=[AgentSkill(id="chat", name="Chat", description="x")],
    )
    payload = json.loads(card.model_dump_json())
    assert payload["name"] == "test-agent"
    assert payload["security_schemes"]["bearer"]["type"] == "http"
    assert payload["security_schemes"]["bearer"]["scheme"] == "bearer"
    assert {"bearer": []} in payload["security"]
    assert payload["api"]["type"] == "a2a"
    assert payload["api"]["url"].startswith("https://example.com/apps/my-agent")


@pytest.mark.unit
def test_card_anonymous_advertises_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A2A_AUTH_MODE", "none")
    monkeypatch.setenv("A2A_ENV", "dev")
    config = AppConfig()
    assert config.auth_mode == AuthMode.NONE
    card = AgentCard.for_config(config, endpoint_url="http://localhost:8080")
    payload = json.loads(card.model_dump_json())
    assert payload["security_schemes"]["none"]["type"] == "none"


@pytest.mark.unit
def test_card_skills_round_trip(app_config_dev: AppConfig) -> None:
    skills = [
        AgentSkill(
            id="search",
            name="Search",
            description="Vector search over UC",
            tags=["retrieval"],
        ),
        AgentSkill(
            id="summarize",
            name="Summarize",
            description="Summarize a passage",
        ),
    ]
    card = AgentCard.for_config(
        app_config_dev,
        endpoint_url="http://localhost:8080",
        skills=skills,
    )
    payload = json.loads(card.model_dump_json())
    assert [s["id"] for s in payload["skills"]] == ["search", "summarize"]
    assert payload["skills"][0]["tags"] == ["retrieval"]
