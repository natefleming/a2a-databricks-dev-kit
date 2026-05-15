"""AI Gateway-aware chat factory.

Port of the dao-ai `InferenceEndpointModel.chat_model_for_workspace_client` pattern
(`src/dao_ai/config.py:874,1009`). Returns a LangChain-compatible chat model that
either:
- talks to a Databricks Model Serving endpoint via langchain-databricks, or
- routes via AI Gateway at /ai-gateway/mlflow/v1/chat/completions via langchain-openai,
  stripping the `name` field from messages (per dao-ai vault note on the AI Gateway
  400 on `messages.N.name`).
"""

from __future__ import annotations

from typing import Any

from databricks.sdk import WorkspaceClient
from langchain_core.language_models.chat_models import BaseChatModel


class _AIGatewayChatOpenAI:
    """Lazy wrapper that builds a ChatOpenAI pointed at AI Gateway with name-field strip.

    Implemented as a builder so we don't import langchain_openai at module load
    when AI Gateway isn't in use.
    """

    @staticmethod
    def build(endpoint: str, workspace_client: WorkspaceClient) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        host = workspace_client.config.host.rstrip("/")
        base_url = f"{host}/ai-gateway/mlflow/v1/chat/completions"
        token = workspace_client.config.token or _oauth_token(workspace_client)

        class NameStrippingChatOpenAI(ChatOpenAI):
            """AI Gateway 400s on messages.N.name — strip it before send.

            See vault memory `reference_dao_ai_ai_gateway_name_strip`.
            """

            def _get_request_payload(
                self,
                input_: Any,
                *,
                stop: list[str] | None = None,
                **kwargs: Any,
            ) -> dict[str, Any]:
                payload = super()._get_request_payload(input_, stop=stop, **kwargs)
                for msg in payload.get("messages", []):
                    if msg.get("role") in {"user", "assistant", "system"}:
                        msg.pop("name", None)
                return payload

        return NameStrippingChatOpenAI(
            model=endpoint,
            base_url=base_url,
            api_key=token,
        )


def _oauth_token(client: WorkspaceClient) -> str:
    """Resolve an OAuth token from the SDK's auth provider."""
    auth = client.config.authenticate()
    return auth.get("Authorization", "").removeprefix("Bearer ").strip()


def chat_model(
    endpoint: str,
    *,
    ai_gateway: bool = False,
    workspace_client: WorkspaceClient | None = None,
    on_behalf_of_token: str | None = None,
    disable_streaming: bool = False,
) -> BaseChatModel:
    """Build a chat model pointed at a Databricks-hosted LLM.

    Args:
        endpoint: Serving endpoint name (e.g. "databricks-claude-sonnet-4-6").
        ai_gateway: If True, route via /ai-gateway/mlflow/v1/chat/completions.
        workspace_client: Reuse an existing WorkspaceClient; only built lazily when needed.
        on_behalf_of_token: When set, builds a client bound to this user's token (OBO).
        disable_streaming: Force non-streaming (required when output guardrails are on).

    The default Databricks Model Serving path doesn't need a WorkspaceClient at all —
    `ChatDatabricks` handles its own auth via the databricks-sdk's auth chain at call
    time. We only construct a WorkspaceClient when the AI Gateway or OBO paths
    actually require one.
    """
    if ai_gateway or on_behalf_of_token:
        if workspace_client is None:
            workspace_client = (
                WorkspaceClient(token=on_behalf_of_token)
                if on_behalf_of_token
                else WorkspaceClient()
            )

    if ai_gateway:
        assert workspace_client is not None
        return _AIGatewayChatOpenAI.build(endpoint, workspace_client)

    from databricks_langchain import ChatDatabricks

    kwargs: dict[str, Any] = {"endpoint": endpoint}
    if disable_streaming:
        kwargs["disable_streaming"] = True
    return ChatDatabricks(**kwargs)
