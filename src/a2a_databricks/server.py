"""FastAPI factory that wires the A2A endpoints around a user-supplied TaskHandler.

Endpoints mounted:
- GET  /.well-known/agent-card.json  → the Agent Card
- POST /tasks/send                    → JSON-RPC 2.0 task submission
- POST /tasks/sendSubscribe           → SSE-streamed task updates
- GET  /healthz                       → liveness for the Databricks Apps proxy

The user owns task execution by passing a `TaskHandler` to `build_app()`. The kit
handles transport, auth, validation, tracing, and SSE plumbing.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Protocol

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from a2a_databricks.auth import AuthVerifier
from a2a_databricks.card import AgentCard


class TaskHandler(Protocol):
    """User-supplied agent logic.

    Two methods:
    - handle(task) -> dict          for synchronous tasks/send
    - stream(task) -> AsyncIterator for tasks/sendSubscribe (SSE)
    """

    async def handle(self, task: dict) -> dict: ...

    def stream(self, task: dict) -> AsyncIterator[dict]: ...


def build_app(
    card: AgentCard,
    handler: TaskHandler,
    *,
    auth: AuthVerifier,
) -> FastAPI:
    """Wire up the FastAPI app for one A2A agent."""

    app = FastAPI(
        title=card.name,
        description=card.description,
        version=card.version,
    )

    async def _check_auth(request: Request) -> None:
        await auth.verify(request)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/.well-known/agent-card.json", tags=["a2a"])
    async def agent_card() -> JSONResponse:
        return JSONResponse(content=json.loads(card.model_dump_json()))

    @app.post(
        "/tasks/send",
        tags=["a2a"],
        dependencies=[Depends(_check_auth)],
    )
    async def tasks_send(request: Request) -> JSONResponse:
        body = await request.json()
        rpc_id, method, params = _parse_jsonrpc(body)
        if method not in {"tasks/send", "message/send"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported method: {method}",
            )
        try:
            result = await handler.handle(params)
        except Exception as exc:
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32000, "message": str(exc)},
                },
            )
        return JSONResponse(
            status_code=200,
            content={"jsonrpc": "2.0", "id": rpc_id, "result": result},
        )

    @app.post(
        "/tasks/sendSubscribe",
        tags=["a2a"],
        dependencies=[Depends(_check_auth)],
    )
    async def tasks_send_subscribe(request: Request) -> EventSourceResponse:
        body = await request.json()
        rpc_id, method, params = _parse_jsonrpc(body)
        if method not in {"tasks/sendSubscribe", "message/sendStream"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported method: {method}",
            )

        async def event_stream() -> AsyncIterator[dict]:
            task_id = params.get("id") or str(uuid.uuid4())
            try:
                async for chunk in handler.stream(params):
                    yield {
                        "event": "task.update",
                        "data": json.dumps(
                            {
                                "jsonrpc": "2.0",
                                "id": rpc_id,
                                "result": {"taskId": task_id, "update": chunk},
                            }
                        ),
                    }
            except Exception as exc:
                yield {
                    "event": "task.error",
                    "data": json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": rpc_id,
                            "error": {"code": -32000, "message": str(exc)},
                        }
                    ),
                }

        return EventSourceResponse(event_stream())

    return app


def _parse_jsonrpc(body: dict) -> tuple[str | int | None, str, dict]:
    """Pull (id, method, params) from a JSON-RPC 2.0 body."""
    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must be a JSON-RPC 2.0 object.",
        )
    method = body.get("method")
    if not method or not isinstance(method, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'method' in JSON-RPC body.",
        )
    params = body.get("params") or {}
    if not isinstance(params, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'params' must be an object.",
        )
    return body.get("id"), method, params
