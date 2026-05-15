# LOCAL_DEV

How to develop the agent on your laptop before ever deploying to Databricks.

## The basic loop

```bash
cp .env.example .env.local
# Edit .env.local — at minimum:
#   A2A_AUTH_MODE=none
#   A2A_ENV=dev
#   A2A_LLM_ENDPOINT=<a Databricks endpoint you can reach>

make run     # uvicorn --reload on :8080

# In another terminal:
curl http://localhost:8080/.well-known/agent-card.json
curl -X POST http://localhost:8080/tasks/send \
  -d @tests/fixtures/sample_task.json -H "Content-Type: application/json"
```

Edit `src/app/agent.py` and uvicorn reloads instantly.

## Calling Databricks LLMs from your laptop

`databricks_langchain.ChatDatabricks` uses the `databricks-sdk` auth chain. So:

```bash
export DATABRICKS_HOST=https://<workspace>.cloud.databricks.com
export DATABRICKS_TOKEN=<personal-access-token>
# Or, with OAuth M2M:
export DATABRICKS_CLIENT_ID=...
export DATABRICKS_CLIENT_SECRET=...
```

Then `make run` and the LLM call works against your workspace. If you only want
to test transport/auth and don't care about real LLM output, see "Mocking the LLM"
below.

## Mocking the LLM for offline dev

Drop this into `src/app/agent.py` temporarily:

```python
class FakeLLM:
    async def ainvoke(self, prompt):
        from types import SimpleNamespace
        return SimpleNamespace(content=f"[fake reply to: {prompt[:40]}...]")

    async def astream(self, prompt):
        for word in str(prompt).split():
            from types import SimpleNamespace
            yield SimpleNamespace(content=word + " ")

class DatabricksLLMAgent:
    def __init__(self, config):
        self._llm = FakeLLM()  # ← swap in
        ...
```

Now `make run` works without any Databricks credentials. Don't commit this; it's a
local-only fast path.

## Driving the local server with the `a2a-sdk` client

```python
import asyncio
from a2a import A2AClient  # from the a2a-sdk PyPI package

async def main():
    client = A2AClient.from_url("http://localhost:8080")
    card = await client.get_agent_card()
    print(card.name)
    result = await client.send_task({"parts": [{"kind": "text", "text": "hello"}]})
    print(result)

asyncio.run(main())
```

This is a real round-trip and is the same code path Gemini Enterprise will execute.

## Reading SSE streams with curl

```bash
curl -N -X POST http://localhost:8080/tasks/sendSubscribe \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tasks/sendSubscribe",
    "params": {"message": {"parts": [{"kind": "text", "text": "stream me a poem"}]}}
  }'
```

You'll see `event: task.update` and `data: {...}` lines stream in.

## Enabling MLflow tracing locally

```bash
export MLFLOW_TRACKING_URI=databricks
export MLFLOW_EXPERIMENT_NAME=/Users/<you>/local-a2a-dev
```

Every `@trace_task`-decorated handler will emit a trace to the experiment.

## Common local-dev gotchas

- **`ImportError: cannot import name 'ChatDatabricks'`** — the old `langchain-databricks`
  is installed instead of the new `databricks-langchain`. `uv sync` again.
- **`401` on `/tasks/send`** — you have `A2A_AUTH_MODE=bearer` but no token. Either
  switch to `A2A_AUTH_MODE=none` for local dev or set `A2A_BEARER_TOKEN=<anything>`.
- **`ValidationError: oauth_m2m requires audience`** — you set `A2A_AUTH_MODE=oauth_m2m`
  but no audience. Either set `A2A_OAUTH_AUDIENCE` or pick a different mode.
- **uvicorn doesn't reload** — make sure you're using `make run` (passes `--reload`),
  not `uvicorn app.main:app` directly.
