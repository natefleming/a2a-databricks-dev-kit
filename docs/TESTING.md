# TESTING

The kit uses pytest with three markers:

| Marker | What it means | Where to put tests |
|---|---|---|
| `@pytest.mark.unit` | Fast (<1s each), no external deps | `tests/test_*.py` |
| `@pytest.mark.integration` | Talks to a real Databricks workspace; gated by env vars | `tests/test_*_integration.py` |
| `@pytest.mark.slow` | Anything that legitimately takes >5s | rare; mark explicitly |

## Running

```bash
make unit            # CI-safe; no creds needed
make integration    # requires DATABRICKS_HOST + auth set
make test           # everything
```

CI runs `make unit` only.

## Fixtures available (from `tests/conftest.py`)

| Fixture | Yields | Use for |
|---|---|---|
| `app_config_dev` | `AppConfig` with bearer auth in dev | Building cards/agents in tests |
| `agent_card` | `AgentCard` matching `app_config_dev` | Tests of routes that need a card |
| `echo_handler` | `EchoHandler` (TaskHandler) | Server tests that don't care about LLM output |
| `integration_env` | skips if no workspace creds | Use as a fixture parameter on integration tests |

## Writing a unit test (worked example)

```python
# tests/test_agent.py
import pytest
from app.agent import _extract_text, _envelope

@pytest.mark.unit
def test_extract_text_from_parts():
    task = {"message": {"parts": [{"kind": "text", "text": "hi"}]}}
    assert _extract_text(task) == "hi"

@pytest.mark.unit
def test_envelope_shape():
    env = _envelope(text="ok")
    assert env["status"]["state"] == "completed"
    assert env["artifacts"][0]["parts"][0]["text"] == "ok"
```

## Writing an integration test (worked example)

```python
# tests/test_serving_integration.py
import os
import pytest
from a2a_databricks import chat_model

@pytest.mark.integration
def test_chat_endpoint_responds(integration_env):
    llm = chat_model(endpoint=os.environ["A2A_LLM_ENDPOINT"])
    resp = llm.invoke("Say 'pong'")
    assert "pong" in resp.content.lower()
```

## Asserting against the FastAPI app

```python
from fastapi.testclient import TestClient
from a2a_databricks.server import build_app

def test_agent_card(agent_card, echo_handler):
    app = build_app(agent_card, echo_handler, auth=AnonymousVerifier(Environment.DEV))
    client = TestClient(app)
    resp = client.get("/.well-known/agent-card.json")
    assert resp.status_code == 200
```

## Test layout

```
tests/
├── conftest.py              # shared fixtures + has_databricks_env()
├── fixtures/
│   └── sample_task.json     # JSON-RPC fixture for curl/manual tests
├── test_auth.py             # unit
├── test_card.py             # unit
├── test_config.py           # unit
├── test_server.py           # unit
└── (your tests)
```

## Timeouts

`pyproject.toml` sets `timeout = 120, timeout_method = "thread"` so a hung gRPC call
can't wedge the suite. Adjust per-test with `@pytest.mark.timeout(30)`.

## Why this layout

Mirrors the dao-ai pattern: integration tests gated by env vars, unit tests always
green on a laptop. Keeps CI green and lets you iterate offline.
