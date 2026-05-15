"""MLflow tracing decorators for A2A task handlers.

Wraps a task handler with MLflow's tracing decorator so every inbound call shows
up as a trace in the configured experiment. Falls back to a no-op when MLflow
isn't available (e.g., local dev without `mlflow[databricks]`).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def trace_task(name: str | None = None) -> Callable[[F], F]:
    """Decorator wrapping a task handler in an MLflow span."""

    def decorator(fn: F) -> F:
        try:
            import mlflow
        except ImportError:
            return fn

        span_name = name or fn.__name__

        @wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with mlflow.start_span(name=span_name, span_type="AGENT") as span:
                if args and isinstance(args[0], dict):
                    span.set_inputs(args[0])
                elif "task" in kwargs:
                    span.set_inputs(kwargs["task"])
                result = await fn(*args, **kwargs)
                span.set_outputs(
                    result if isinstance(result, dict) else {"result": result}
                )
                return result

        return async_wrapper  # type: ignore[return-value]

    return decorator
