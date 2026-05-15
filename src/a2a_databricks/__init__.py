"""a2a_databricks — helpers for building A2A-protocol agents on Databricks.

Public API:
    AgentCard         — Pydantic model matching the A2A v1.0 Agent Card schema
    AppConfig         — env-driven runtime config
    build_app         — FastAPI factory that mounts the A2A routes
    chat_model        — AI Gateway-aware chat factory (port of dao-ai)
    trace_task        — MLflow tracing decorator for task handlers
    BearerVerifier, OAuthM2MVerifier, AnonymousVerifier — auth verifiers
"""

from a2a_databricks.auth import (
    AnonymousVerifier,
    AuthVerifier,
    BearerVerifier,
    OAuthM2MVerifier,
)
from a2a_databricks.card import AgentCard, AgentSkill
from a2a_databricks.config import AppConfig, AuthMode, Environment
from a2a_databricks.llm import chat_model
from a2a_databricks.server import TaskHandler, build_app
from a2a_databricks.tracing import trace_task

__version__ = "0.1.0"

__all__ = [
    "AgentCard",
    "AgentSkill",
    "AnonymousVerifier",
    "AppConfig",
    "AuthMode",
    "AuthVerifier",
    "BearerVerifier",
    "Environment",
    "OAuthM2MVerifier",
    "TaskHandler",
    "build_app",
    "chat_model",
    "trace_task",
]
