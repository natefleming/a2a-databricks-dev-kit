"""FastAPI entrypoint for {{.project_name}}.

Wires the user-supplied agent into the a2a_databricks transport layer.
Edit `agent.py` for behavior changes; this file rarely needs edits.
"""

from __future__ import annotations

import os

from a2a_databricks import AppConfig, build_app
from a2a_databricks.auth import verifier_for
from a2a_databricks.card import AgentCard
from a2a_databricks.config import AuthMode
from app.agent import SKILLS, DatabricksLLMAgent


def _resolve_bearer_token(config: AppConfig) -> str | None:
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
    return (
        os.environ.get("DATABRICKS_APP_URL")
        or os.environ.get("A2A_PUBLIC_URL")
        or "http://localhost:8080"
    )


def create_app():
    config = AppConfig()
    bearer = _resolve_bearer_token(config)
    auth = verifier_for(config, bearer_token=bearer)
    card = AgentCard.for_config(config, endpoint_url=_public_url(), skills=SKILLS)
    agent = DatabricksLLMAgent(config)
    return build_app(card, agent, auth=auth)


app = create_app()
