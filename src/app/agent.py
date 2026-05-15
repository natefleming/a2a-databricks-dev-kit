"""The agent the user customizes.

This is the file you'll spend most of your time in. The dev kit handles transport,
auth, and the A2A protocol envelope; you write what the agent actually does.

Two contracts:
    handle(task) -> dict                — synchronous task processing for /tasks/send
    stream(task) -> AsyncIterator[dict] — incremental updates for /tasks/sendSubscribe

The default implementation calls a Databricks-hosted LLM and returns a single text
artifact. Replace the body with your own tool calls, RAG lookups, LangGraph runs,
or anything else.
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
        input_modes=["text"],
        output_modes=["text"],
    ),
]


class DatabricksLLMAgent:
    """Reference agent: one-shot call to a Databricks LLM.

    The LLM client is constructed lazily on first task. This means the Agent Card
    and /healthz are reachable even without Databricks creds, so deploys don't
    pre-fail on auth issues during cold start.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._llm = None  # built lazily; see _get_llm()

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
    """Pull a text prompt out of an A2A task envelope.

    A2A tasks carry a `message.parts` list; each part has a `kind` (text/file/data).
    For the default chat skill we just concatenate text parts.
    """
    message = task.get("message", task)
    parts = message.get("parts") or []
    texts = [p.get("text", "") for p in parts if p.get("kind", "text") == "text"]
    if texts:
        return "\n".join(texts)
    return message.get("text") or task.get("text") or ""


def _envelope(*, text: str) -> dict:
    """Wrap a text response in an A2A task result envelope."""
    return {
        "status": {"state": "completed"},
        "artifacts": [
            {
                "name": "response",
                "parts": [{"kind": "text", "text": text}],
            }
        ],
    }
