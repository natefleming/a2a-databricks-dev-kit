"""Tests for the FastAPI server factory + A2A routes."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from a2a_databricks.auth import AnonymousVerifier, BearerVerifier
from a2a_databricks.card import AgentCard
from a2a_databricks.config import Environment
from a2a_databricks.server import build_app


@pytest.fixture
def client(agent_card: AgentCard, echo_handler) -> TestClient:
    app = build_app(agent_card, echo_handler, auth=AnonymousVerifier(Environment.DEV))
    return TestClient(app)


@pytest.mark.unit
def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.unit
def test_agent_card_well_known(client: TestClient) -> None:
    resp = client.get("/.well-known/agent-card.json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "test-agent"
    assert body["api"]["type"] == "a2a"


@pytest.mark.unit
def test_tasks_send_echoes(client: TestClient) -> None:
    payload = {
        "jsonrpc": "2.0",
        "id": "abc",
        "method": "tasks/send",
        "params": {
            "message": {
                "parts": [{"kind": "text", "text": "hello world"}],
            },
        },
    }
    resp = client.post("/tasks/send", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "abc"
    artifact_text = body["result"]["artifacts"][0]["parts"][0]["text"]
    assert artifact_text == "echo: hello world"


@pytest.mark.unit
def test_tasks_send_rejects_wrong_method(client: TestClient) -> None:
    resp = client.post(
        "/tasks/send",
        json={"jsonrpc": "2.0", "id": 1, "method": "garbage", "params": {}},
    )
    assert resp.status_code == 400


@pytest.mark.unit
def test_tasks_send_rejects_non_jsonrpc(client: TestClient) -> None:
    resp = client.post("/tasks/send", json={"hello": "world"})
    assert resp.status_code == 400


@pytest.mark.unit
def test_bearer_blocks_unauthenticated(agent_card: AgentCard, echo_handler) -> None:
    app = build_app(agent_card, echo_handler, auth=BearerVerifier("s3cret"))
    client = TestClient(app)
    resp = client.post(
        "/tasks/send",
        json={"jsonrpc": "2.0", "id": 1, "method": "tasks/send", "params": {}},
    )
    assert resp.status_code == 401


@pytest.mark.unit
def test_bearer_accepts_authenticated(agent_card: AgentCard, echo_handler) -> None:
    app = build_app(agent_card, echo_handler, auth=BearerVerifier("s3cret"))
    client = TestClient(app)
    resp = client.post(
        "/tasks/send",
        headers={"Authorization": "Bearer s3cret"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/send",
            "params": {"message": {"parts": [{"kind": "text", "text": "ping"}]}},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["artifacts"][0]["parts"][0]["text"] == "echo: ping"


@pytest.mark.unit
def test_send_subscribe_streams_events(client: TestClient) -> None:
    payload = {
        "jsonrpc": "2.0",
        "id": "sub",
        "method": "tasks/sendSubscribe",
        "params": {"message": {"parts": [{"kind": "text", "text": "a b c"}]}},
    }
    with client.stream("POST", "/tasks/sendSubscribe", json=payload) as resp:
        assert resp.status_code == 200
        events = []
        for raw_line in resp.iter_lines():
            if raw_line.startswith("data:"):
                events.append(json.loads(raw_line[len("data:") :].strip()))
    assert events, "Expected at least one SSE event"
    assert any(
        e.get("result", {}).get("update", {}).get("delta", {}).get("text") == "a "
        for e in events
    )
