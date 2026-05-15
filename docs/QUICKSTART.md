# QUICKSTART — 10 minutes to a live A2A agent

This is the shortest path from a fresh Databricks workspace to a running, A2A-compliant
agent that's discoverable in Gemini Enterprise. For deeper customization, head to
[DEVELOPMENT.md](DEVELOPMENT.md) right after.

## Prereqs

- A Databricks workspace where you can create Apps
- Workspace permission to grant `USE_SCHEMA` on a Unity Catalog schema
- `gcloud` installed locally (for step 6 only)

## Steps

### 1. Create the App
- In your Databricks workspace, click **Apps → Create app → Custom app**
- Name: `my-a2a-agent`
- Click **Create**

### 2. Point at this repo
- On the new app's page, click **Deploy → Configure Git source**
- Paste: `https://github.com/natefleming/a2a-databricks-dev-kit`
- Branch: `main` (or pick a tagged release like `v1.0.0`)
- Click **Deploy**

### 3. Wait for build
The Apps runtime installs `requirements.txt` and runs `uvicorn app.main:app`. First-time
builds take ~2 minutes. Watch the **Logs** tab.

### 4. Set required env vars
Open **Settings → Environment variables** and set:

| Variable | Value |
|---|---|
| `A2A_LLM_ENDPOINT` | `databricks-claude-sonnet-4-6` (or any Model Serving endpoint you can reach) |
| `A2A_AUTH_MODE` | `none` (for the demo; switch to `bearer` for anything real) |
| `A2A_ENV` | `dev` |

Click **Save** → **Restart**.

### 5. Verify the Agent Card
Open `https://<workspace>.cloud.databricks.com/apps/my-a2a-agent/.well-known/agent-card.json`
in your browser. You should see a JSON document starting with:

```json
{
  "name": "my-a2a-agent",
  "description": "An A2A-protocol agent running on Databricks",
  ...
}
```

### 6. Register in Gemini Enterprise (optional but recommended)
```bash
gcloud auth application-default login
git clone https://github.com/natefleming/a2a-databricks-dev-kit
cd a2a-databricks-dev-kit
uv sync --extra gemini
AGENT_URL=https://<workspace>.cloud.databricks.com/apps/my-a2a-agent \
GEMINI_PROJECT_ID=<your-project> \
uv run python notebooks/register_in_gemini.py
```

You should see `✔ Registered agent` plus a console URL.

### 7. Send a test task
```bash
curl -X POST https://<workspace>.cloud.databricks.com/apps/my-a2a-agent/tasks/send \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tasks/send",
    "params": {"message": {"parts": [{"kind": "text", "text": "Hello"}]}}
  }'
```

You'll get back a JSON-RPC response with an `artifacts` array containing the LLM's reply.

## What next

- **[DEVELOPMENT.md](DEVELOPMENT.md)** — customize `agent.py` to add tools, RAG, LangGraph, etc.
- **[CONFIGURATION.md](CONFIGURATION.md)** — every env var, including production-grade auth
- **[GEMINI_REGISTRATION.md](GEMINI_REGISTRATION.md)** — production registration with IAM
