"""{{.project_name}} — your agent logic lives here.

Customize `DatabricksLLMAgent.handle` and `.stream`. The dev kit ships a reference
implementation that calls a Databricks-hosted LLM and returns a single text artifact.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from a2a_databricks import AppConfig, chat_model, trace_task
from a2a_databricks.card import AgentSkill

SKILLS: list[AgentSkill] = [
    AgentSkill(
        id="chat",
        name="Chat",
        description="Free-form conversational reply backed by a Databricks LLM.",
        tags=["chat", "default"],
        examples=["What is Databricks Unity Catalog?"],
    ),
]


class DatabricksLLMAgent:
    """LLM client is constructed lazily on first task call, so the Agent Card
    and /healthz remain reachable even without Databricks creds at cold start."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            self._llm = chat_model(
                endpoint=self._config.llm_endpoint,
                ai_gateway=self._config.llm_ai_gateway,
            )
        return self._llm

    @trace_task("a2a.handle")
    async def handle(self, task: dict) -> dict:
        prompt = _extract_text(task)
        response = await self._get_llm().ainvoke(prompt)
        return _envelope(text=response.content)

    async def stream(self, task: dict) -> AsyncIterator[dict]:
        prompt = _extract_text(task)
        async for chunk in self._get_llm().astream(prompt):
            if chunk.content:
                yield {"delta": {"text": chunk.content}}
        yield {"status": "completed"}


def _extract_text(task: dict) -> str:
    message = task.get("message", task)
    parts = message.get("parts") or []
    texts = [p.get("text", "") for p in parts if p.get("kind", "text") == "text"]
    if texts:
        return "\n".join(texts)
    return message.get("text") or task.get("text") or ""


def _envelope(*, text: str) -> dict:
    return {
        "status": {"state": "completed"},
        "artifacts": [
            {
                "name": "response",
                "parts": [{"kind": "text", "text": text}],
            }
        ],
    }
