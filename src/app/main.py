"""FastAPI entrypoint for a Databricks-hosted A2A agent.

You shouldn't need to edit this file often — it just wires three things together:
    1. AppConfig.from_env()    — runtime configuration
    2. agent module             — your actual agent logic
    3. a2a_databricks.build_app — the A2A transport layer

Run locally:
    uv run uvicorn app.main:app --reload --port 8080

On Databricks Apps, `app.yaml` runs the same command bound to $DATABRICKS_APP_PORT.
"""

from __future__ import annotations

import os

from a2a_databricks import AppConfig, build_app
from a2a_databricks.auth import verifier_for
from a2a_databricks.card import AgentCard
from a2a_databricks.config import AuthMode
from app.agent import SKILLS, DatabricksLLMAgent


def _resolve_bearer_token(config: AppConfig) -> str | None:
    """Resolve the bearer token from Databricks secrets, or fall back to env.

    Precedence:
        1. A2A_BEARER_TOKEN env var (local dev convenience)
        2. Databricks secret at (A2A_BEARER_SECRET_SCOPE, A2A_BEARER_SECRET_KEY)
    """
    if config.auth_mode != AuthMode.BEARER:
        return None

    inline = os.environ.get("A2A_BEARER_TOKEN")
    if inline:
        return inline

    if config.bearer_secret_scope and config.bearer_secret_key:
        from databricks.sdk import WorkspaceClient

        ws = WorkspaceClient()
        secret = ws.secrets.get_secret(
            scope=config.bearer_secret_scope,
            key=config.bearer_secret_key,
        )
        if secret.value:
            import base64

            return base64.b64decode(secret.value).decode("utf-8")

    return None


def _public_url() -> str:
    """Best-effort guess at the public URL the agent is reachable on.

    On Databricks Apps the proxy exposes `DATABRICKS_APP_URL`. Locally we fall back
    to the uvicorn bind address.
    """
    return (
        os.environ.get("DATABRICKS_APP_URL")
        or os.environ.get("A2A_PUBLIC_URL")
        or "http://localhost:8080"
    )


def create_app():
    config = AppConfig()
    bearer = _resolve_bearer_token(config)
    auth = verifier_for(config, bearer_token=bearer)
    card = AgentCard.for_config(
        config,
        endpoint_url=_public_url(),
        skills=SKILLS,
    )
    agent = DatabricksLLMAgent(config)
    return build_app(card, agent, auth=auth)


app = create_app()
