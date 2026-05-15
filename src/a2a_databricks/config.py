"""Runtime configuration for an A2A agent.

Reads `A2A_*` environment variables; rejects invalid combinations at startup. Used
by both the FastAPI app and the example agent. Mirrors dao-ai's config-driven pattern
but trimmed to what an A2A agent actually needs.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthMode(str, Enum):
    BEARER = "bearer"
    OAUTH_M2M = "oauth_m2m"
    NONE = "none"


class Environment(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class AppConfig(BaseSettings):
    """Env-driven config for the agent runtime.

    Read once at app startup via `AppConfig()` (pydantic-settings auto-loads from env).
    """

    model_config = SettingsConfigDict(
        env_prefix="A2A_",
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    agent_name: str = Field(default="my-a2a-agent")
    agent_description: str = Field(
        default="An A2A-protocol agent running on Databricks"
    )
    agent_version: str = Field(default="0.1.0")

    llm_endpoint: str = Field(default="databricks-claude-sonnet-4-6")
    llm_ai_gateway: bool = Field(default=False)

    auth_mode: AuthMode = Field(default=AuthMode.BEARER)
    env: Environment = Field(default=Environment.DEV)

    bearer_secret_scope: str = Field(default="")
    bearer_secret_key: str = Field(default="")

    oauth_audience: str = Field(default="")
    oauth_issuer: str = Field(default="")

    catalog: str = Field(default="main")
    schema_name: str = Field(default="a2a_agents", alias="A2A_SCHEMA")

    @model_validator(mode="after")
    def _reject_anonymous_in_prod(self) -> "AppConfig":
        if self.auth_mode == AuthMode.NONE and self.env == Environment.PROD:
            raise ValueError(
                "A2A_AUTH_MODE=none is not allowed when A2A_ENV=prod. "
                "Use 'bearer' or 'oauth_m2m'."
            )
        return self

    @model_validator(mode="after")
    def _bearer_requires_secret(self) -> "AppConfig":
        if self.auth_mode == AuthMode.BEARER and self.env == Environment.PROD:
            if not (self.bearer_secret_scope and self.bearer_secret_key):
                raise ValueError(
                    "A2A_AUTH_MODE=bearer in prod requires A2A_BEARER_SECRET_SCOPE "
                    "and A2A_BEARER_SECRET_KEY pointing at a Databricks secret."
                )
        return self

    @model_validator(mode="after")
    def _oauth_requires_audience(self) -> "AppConfig":
        if self.auth_mode == AuthMode.OAUTH_M2M:
            if not self.oauth_audience:
                raise ValueError("A2A_AUTH_MODE=oauth_m2m requires A2A_OAUTH_AUDIENCE.")
        return self
