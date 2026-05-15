"""Tests for the auth verifiers."""

from __future__ import annotations

import pytest
from fastapi import HTTPException, Request

from a2a_databricks.auth import (
    AnonymousVerifier,
    BearerVerifier,
    verifier_for,
)
from a2a_databricks.config import AppConfig, AuthMode, Environment


def _request_with_header(value: str | None) -> Request:
    headers = []
    if value is not None:
        headers.append((b"authorization", value.encode("utf-8")))
    scope = {
        "type": "http",
        "headers": headers,
        "method": "POST",
        "path": "/tasks/send",
    }
    return Request(scope)


@pytest.mark.unit
async def test_bearer_accepts_correct_token() -> None:
    verifier = BearerVerifier("s3cret")
    await verifier.verify(_request_with_header("Bearer s3cret"))


@pytest.mark.unit
async def test_bearer_rejects_wrong_token() -> None:
    verifier = BearerVerifier("s3cret")
    with pytest.raises(HTTPException) as exc:
        await verifier.verify(_request_with_header("Bearer nope"))
    assert exc.value.status_code == 401


@pytest.mark.unit
async def test_bearer_rejects_missing_header() -> None:
    verifier = BearerVerifier("s3cret")
    with pytest.raises(HTTPException) as exc:
        await verifier.verify(_request_with_header(None))
    assert exc.value.status_code == 401


@pytest.mark.unit
async def test_bearer_rejects_wrong_scheme() -> None:
    verifier = BearerVerifier("s3cret")
    with pytest.raises(HTTPException) as exc:
        await verifier.verify(_request_with_header("Basic s3cret"))
    assert exc.value.status_code == 401


@pytest.mark.unit
def test_bearer_requires_nonempty_token() -> None:
    with pytest.raises(ValueError):
        BearerVerifier("")


@pytest.mark.unit
async def test_anonymous_allows_in_dev() -> None:
    verifier = AnonymousVerifier(Environment.DEV)
    await verifier.verify(_request_with_header(None))


@pytest.mark.unit
def test_anonymous_refuses_in_prod() -> None:
    with pytest.raises(ValueError, match="cannot be used when A2A_ENV=prod"):
        AnonymousVerifier(Environment.PROD)


@pytest.mark.unit
def test_verifier_for_bearer_requires_resolved_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("A2A_AUTH_MODE", "bearer")
    monkeypatch.setenv("A2A_ENV", "dev")
    config = AppConfig()
    assert config.auth_mode == AuthMode.BEARER
    with pytest.raises(ValueError, match="resolved bearer_token"):
        verifier_for(config, bearer_token=None)


@pytest.mark.unit
def test_verifier_for_anonymous(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A2A_AUTH_MODE", "none")
    monkeypatch.setenv("A2A_ENV", "dev")
    config = AppConfig()
    verifier = verifier_for(config)
    assert isinstance(verifier, AnonymousVerifier)
