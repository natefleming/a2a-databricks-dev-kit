# DEVELOPMENT — the dev loop for your A2A agent

This is the doc you read once you've gotten past [QUICKSTART](QUICKSTART.md) and want
to actually build something. Every step below has prerequisites, exact commands,
expected output, and a "what just happened" paragraph.

---

## 1. Set up your local environment

### Prerequisites
- macOS or Linux (Windows users: use WSL2)
- Python ≥3.11
- [`uv`](https://github.com/astral-sh/uv) ≥0.4 — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [`databricks` CLI](https://docs.databricks.com/aws/en/dev-tools/cli/install) ≥0.279.0
- (Step 9 only) [`gcloud` CLI](https://cloud.google.com/sdk/docs/install)

### Commands
```bash
git clone https://github.com/<org>/a2a-databricks-dev-kit
cd a2a-databricks-dev-kit
uv sync                                 # installs all deps into .venv/
databricks auth login --host https://<workspace>.cloud.databricks.com \
                      --profile aws-field-eng
```

### Expected output
- `.venv/` directory created
- A `Successfully logged in` message from `databricks auth login`
- `make unit` runs in <1s and prints `25 passed`

### What just happened
`uv sync` reads `pyproject.toml`, resolves the dep graph, and installs into a hidden
`.venv/`. The `databricks` CLI stores OAuth tokens in `~/.databrickscfg` keyed by
profile name. Both are local; nothing has touched the workspace yet.

---

## 2. Run the agent on your laptop

### Prerequisites
- Step 1 completed
- (Optional) a real Databricks Model Serving endpoint reachable from your laptop, if
  you want the LLM call to actually work. Otherwise the test fixture echo works fine.

### Commands
```bash
cp .env.example .env.local
# Edit .env.local. For purely local testing set:
#   A2A_AUTH_MODE=none
#   A2A_ENV=dev
#   A2A_LLM_ENDPOINT=databricks-claude-sonnet-4-6
make run                                # starts uvicorn on :8080

# In a second terminal:
curl http://localhost:8080/.well-known/agent-card.json
curl -X POST http://localhost:8080/tasks/send \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_task.json
```

### Expected output
- First curl: a JSON Agent Card with `"name": "my-a2a-agent"`.
- Second curl: a JSON-RPC response with `result.artifacts[0].parts[0].text` containing
  the LLM's reply.

### What just happened
`make run` calls `uv run uvicorn app.main:app --reload --port 8080`. The `--reload`
flag restarts the server when you save a file, so this is your tight loop. The
Agent Card is built from `AppConfig().model_dump()` at startup; the task endpoint
dispatches into `app.agent.DatabricksLLMAgent.handle()`.

---

## 3. Modify the agent's logic

The file you'll edit most is **`src/app/agent.py`**.

### Where things live

| Edit | File | Hot-reload? |
|---|---|---|
| System prompt, tool list, behavior | `src/app/agent.py` | yes (uvicorn --reload) |
| Advertised skills in the Agent Card | `src/app/agent.py` (`SKILLS` list) | yes |
| FastAPI wiring (auth, public URL) | `src/app/main.py` | yes |
| Env-var schema | `src/a2a_databricks/config.py` | yes |
| Transport routes | `src/a2a_databricks/server.py` | rarely needed |

### Worked example — swap the prompt for a customer-support persona
```python
# src/app/agent.py
SYSTEM_PROMPT = (
    "You are Tier-1 product support for ACME. Be terse, cite SKUs when relevant, "
    "and escalate to a human if the user asks for a refund."
)

class DatabricksLLMAgent:
    ...
    @trace_task("a2a.handle")
    async def handle(self, task: dict) -> dict:
        prompt = _extract_text(task)
        response = await self._llm.ainvoke(
            [("system", SYSTEM_PROMPT), ("user", prompt)]
        )
        return _envelope(text=response.content)
```

### Verify
`make unit` must still pass. Hit the local server with curl and confirm the response
reflects the new prompt.

---

## 4. Add a new tool / capability

Worked example: add a `lookup_sku` capability backed by a Unity Catalog table.

### Prerequisites
- Step 1 + 2 complete
- A UC table you can read (e.g. `main.a2a_agents.products`)

### Commands / code
```python
# src/app/agent.py
from databricks.sdk import WorkspaceClient

SKILLS = [
    AgentSkill(id="chat", name="Chat", description="..."),
    AgentSkill(
        id="lookup_sku",
        name="Look up SKU",
        description="Find a product by its SKU code.",
        tags=["retrieval", "product"],
        examples=["What is SKU AB-1234?"],
    ),
]

class DatabricksLLMAgent:
    def __init__(self, config):
        self._config = config
        self._llm = chat_model(endpoint=config.llm_endpoint)
        self._ws = WorkspaceClient()

    @trace_task("a2a.handle")
    async def handle(self, task: dict) -> dict:
        text = _extract_text(task)
        if text.upper().startswith("SKU "):
            sku = text.split(" ", 1)[1].strip()
            rows = self._ws.statement_execution.execute_statement(
                statement=f"SELECT name, price FROM main.a2a_agents.products WHERE sku = :sku",
                warehouse_id=os.environ["A2A_WAREHOUSE_ID"],
                parameters=[{"name": "sku", "value": sku}],
            )
            return _envelope(text=str(rows.result.data_array))
        return _envelope(text=(await self._llm.ainvoke(text)).content)
```

### Verify
- Add a test:
  ```python
  # tests/test_agent.py
  @pytest.mark.unit
  async def test_lookup_sku_branches_on_text(...): ...
  ```
- `make unit` passes
- Local curl: send a task with text `"SKU AB-1234"` and confirm the UC branch fires

---

## 5. Add or change configuration

Three places must stay in sync whenever you add a new env var:

1. **`src/a2a_databricks/config.py`** — add a `Field` on `AppConfig`
2. **`app.yaml`** — add to the `env:` list (with a safe default)
3. **`.env.example`** — add to the documentation
4. **`docs/CONFIGURATION.md`** — add a row to the table

Worked example: add `A2A_WAREHOUSE_ID`.

```python
# src/a2a_databricks/config.py
class AppConfig(BaseSettings):
    ...
    warehouse_id: str = Field(default="", description="SQL warehouse for UC queries")
```

```yaml
# app.yaml
env:
  ...
  - name: A2A_WAREHOUSE_ID
    value: ""
```

```
# .env.example
A2A_WAREHOUSE_ID=
```

`config.warehouse_id` is now available wherever you `AppConfig()`.

---

## 6. Run tests

```bash
make unit              # fast, no external deps
make integration      # requires a workspace; gated by env vars
make check            # ruff lint with autofix
make format           # ruff lint + format
```

### Pre-push gate
`make unit` must be green before any push. Failing unit tests block deploy.

### Adding a unit test
```python
# tests/test_agent.py
import pytest
from app.agent import _extract_text

@pytest.mark.unit
def test_extract_text_from_parts():
    task = {"message": {"parts": [{"kind": "text", "text": "hi"}]}}
    assert _extract_text(task) == "hi"
```

---

## 7. Deploy to a sandbox workspace

There are two deploy paths — pick whichever fits your team.

### 7a. Apps-from-Git path (UI)
```bash
git add -A && git commit -m "feat: SKU lookup" && git push
```
Then in the workspace: **Apps → my-a2a-agent → Deploy → pick latest commit**.

### 7b. Bundle path (CLI)
```bash
databricks bundle deploy -t dev --profile aws-field-eng
databricks bundle run a2a_agent_app -t dev --profile aws-field-eng
```

### Verify
```bash
curl https://<workspace>/apps/my-a2a-agent/.well-known/agent-card.json   # → 200
curl -X POST https://<workspace>/apps/my-a2a-agent/tasks/send \
  -H "Authorization: Bearer $A2A_TOKEN" \
  -d @tests/fixtures/sample_task.json
```

### What just happened
The Apps proxy synced your repo, ran `pip install -r requirements.txt`, and started
the uvicorn process. The bundle path additionally re-applied `databricks.yml`
resources (App, experiment, UC schema grants).

---

## 8. Iterate fast

### Local re-test loop (sub-second)
```bash
make run     # uvicorn --reload watches src/
# Edit src/app/agent.py
# Curl again — change is live
```

### Sandbox loop (~30s)
```bash
git commit -am "tweak prompt" && git push
# In workspace: Apps → my-a2a-agent → Redeploy
# Or use the CLI:
databricks bundle deploy -t dev && databricks bundle run a2a_agent_app -t dev
```

Apps caches the dep install across deploys, so iterations after the first are fast.

### Promotion
- Tag a release: `git tag v1.1.0 && git push --tags`
- In the prod workspace: redeploy from the new tag

---

## 9. Register with Gemini Enterprise

### Prerequisites
- Step 7 complete; agent reachable on the public URL
- `gcloud auth application-default login` has been run
- The Google project has the **Discovery Engine API** enabled
- IAM role: `roles/discoveryengine.editor` (or fine-grained `discoveryengine.agentRegistry.create`)

### Commands
```bash
uv sync --extra gemini
AGENT_URL=https://<workspace>/apps/my-a2a-agent \
GEMINI_PROJECT_ID=<your-project> \
uv run python notebooks/register_in_gemini.py
```

### Verify
- The script prints `✔ Registered agent` and a console URL.
- Open the URL — the agent appears in the Gemini Enterprise Agent Registry.
- From another Gemini-hosted agent or the Gemini Enterprise chat, delegate a task to
  your agent by name; it should respond.

---

## 10. Tear down

### Apps path
- Apps → your app → Delete

### Bundle path
```bash
databricks bundle destroy -t dev
```

### Gemini Enterprise
```bash
gcloud alpha discovery-engine agents delete <agent-id> \
  --project=$GEMINI_PROJECT_ID --location=global \
  --collection=default_collection
```

---

## Where to go next

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — mental model + request flow diagram
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** — symptoms → fixes
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — extending the kit itself
