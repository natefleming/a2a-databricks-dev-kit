"""A2A Agent Card model.

Matches the A2A v1.0 Agent Card schema. Served at `/.well-known/agent-card.json` so
Gemini Enterprise and other A2A clients can discover the agent's capabilities and
auth requirements.

Spec reference: https://a2a-protocol.org/latest/specification/
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from a2a_databricks.config import AppConfig, AuthMode


class AgentSkill(BaseModel):
    """One capability the agent advertises."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    input_modes: list[str] = Field(default=["text"])
    output_modes: list[str] = Field(default=["text"])


class AgentApi(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["a2a"] = "a2a"
    url: HttpUrl


class SecurityScheme(BaseModel):
    """OpenAPI-3.1-style security scheme advertised in the Agent Card."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["http", "oauth2", "apiKey", "none"]
    scheme: str | None = None  # for type=http: "bearer", "basic", etc.
    bearer_format: str | None = None
    flows: dict | None = None  # oauth2 flows; left untyped for caller flexibility


class AgentCard(BaseModel):
    """A2A Agent Card served at /.well-known/agent-card.json."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    version: str
    api: AgentApi
    skills: list[AgentSkill] = Field(default_factory=list)
    security_schemes: dict[str, SecurityScheme] = Field(default_factory=dict)
    security: list[dict[str, list[str]]] = Field(default_factory=list)
    documentation_url: HttpUrl | None = None
    provider: dict[str, str] | None = None

    @classmethod
    def for_config(
        cls,
        config: AppConfig,
        *,
        endpoint_url: str,
        skills: list[AgentSkill] | None = None,
    ) -> "AgentCard":
        """Build an Agent Card from an AppConfig + the resolved endpoint URL.

        endpoint_url is the public URL where the A2A endpoints are mounted (e.g.
        https://<workspace>/apps/<app-name>).
        """
        security_schemes: dict[str, SecurityScheme] = {}
        security: list[dict[str, list[str]]] = []

        if config.auth_mode == AuthMode.BEARER:
            security_schemes["bearer"] = SecurityScheme(
                type="http", scheme="bearer", bearer_format="JWT"
            )
            security.append({"bearer": []})
        elif config.auth_mode == AuthMode.OAUTH_M2M:
            security_schemes["oauth_m2m"] = SecurityScheme(
                type="oauth2",
                flows={
                    "clientCredentials": {
                        "tokenUrl": config.oauth_issuer,
                        "scopes": {},
                    }
                },
            )
            security.append({"oauth_m2m": []})
        else:
            security_schemes["none"] = SecurityScheme(type="none")

        return cls(
            name=config.agent_name,
            description=config.agent_description,
            version=config.agent_version,
            api=AgentApi(url=endpoint_url),
            skills=skills or [],
            security_schemes=security_schemes,
            security=security,
            provider={"name": "Databricks", "url": "https://www.databricks.com"},
        )
