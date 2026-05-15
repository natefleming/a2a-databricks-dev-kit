"""Inbound auth verifiers for the A2A endpoint.

Three modes:
- BearerVerifier: a static bearer token, loaded from Databricks secrets at startup.
- OAuthM2MVerifier: validates an OAuth2 access token against the configured issuer/audience.
- AnonymousVerifier: pass-through. Refuses to instantiate in prod environments.
"""

from __future__ import annotations

import hmac
from abc import ABC, abstractmethod

import httpx
from fastapi import HTTPException, Request, status

from a2a_databricks.config import AppConfig, AuthMode, Environment


class AuthVerifier(ABC):
    """Pluggable auth verifier protocol."""

    @abstractmethod
    async def verify(self, request: Request) -> None:
        """Raise HTTPException on auth failure; return None on success."""


class BearerVerifier(AuthVerifier):
    def __init__(self, expected_token: str) -> None:
        if not expected_token:
            raise ValueError("BearerVerifier requires a non-empty token.")
        self._expected = expected_token.encode("utf-8")

    async def verify(self, request: Request) -> None:
        header = request.headers.get("authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or malformed Authorization header.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not hmac.compare_digest(token.encode("utf-8"), self._expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer token.",
            )


class OAuthM2MVerifier(AuthVerifier):
    """Validates OAuth 2.0 M2M tokens against an OIDC issuer's JWKS.

    Minimal verifier: introspects the token via the issuer's userinfo or
    introspection endpoint. Customize for your IdP if it differs.
    """

    def __init__(self, audience: str, issuer: str) -> None:
        if not audience or not issuer:
            raise ValueError("OAuthM2MVerifier requires audience and issuer.")
        self._audience = audience
        self._issuer = issuer.rstrip("/")

    async def verify(self, request: Request) -> None:
        header = request.headers.get("authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing OAuth bearer token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        introspect_url = f"{self._issuer}/oauth2/introspect"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(introspect_url, data={"token": token})
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OAuth token introspection failed.",
            )
        claims = resp.json()
        if not claims.get("active"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OAuth token is not active.",
            )
        aud = claims.get("aud", "")
        if isinstance(aud, list):
            if self._audience not in aud:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="OAuth audience mismatch.",
                )
        elif aud != self._audience:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OAuth audience mismatch.",
            )


class AnonymousVerifier(AuthVerifier):
    """Pass-through verifier. Refuses to construct in prod."""

    def __init__(self, env: Environment) -> None:
        if env == Environment.PROD:
            raise ValueError(
                "AnonymousVerifier cannot be used when A2A_ENV=prod. "
                "Switch A2A_AUTH_MODE to 'bearer' or 'oauth_m2m'."
            )

    async def verify(self, request: Request) -> None:
        return None


def verifier_for(config: AppConfig, *, bearer_token: str | None = None) -> AuthVerifier:
    """Build the right verifier from config.

    bearer_token is read from Databricks secrets (or .env) by the caller and passed in,
    so this module stays decoupled from secret resolution.
    """
    if config.auth_mode == AuthMode.BEARER:
        if bearer_token is None:
            raise ValueError(
                "Bearer auth mode requires a resolved bearer_token. "
                "Resolve A2A_BEARER_SECRET_SCOPE/KEY before calling verifier_for()."
            )
        return BearerVerifier(bearer_token)
    if config.auth_mode == AuthMode.OAUTH_M2M:
        return OAuthM2MVerifier(config.oauth_audience, config.oauth_issuer)
    return AnonymousVerifier(config.env)
