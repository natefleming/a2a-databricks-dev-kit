# GEMINI_REGISTRATION

How to publish your Databricks-hosted A2A agent into Google's **Gemini Enterprise
Agent Platform** so it's discoverable inside the Gemini Enterprise app and other
agents can delegate to it.

## How this works

- Your agent is **hosted on Databricks**. Google never sees the runtime — only the
  Agent Card URL.
- Google's **Agent Registry** (a sub-resource of the Discovery Engine API) stores the
  Agent Card + endpoint URL, scoped to a specific Gemini Enterprise **app** (engine).
- When a Gemini user delegates a task to your agent, Gemini's outbound gateway calls
  your `/tasks/send` with the credentials you configure on Google's side.
- Registration is a one-time POST per (agent, app) pair. Re-run the notebook to update.

## Required Google-side concepts

| Concept | What it is | Where you set it |
|---|---|---|
| **Project** | Your GCP project | `GEMINI_PROJECT_ID` |
| **Location** | `global`, `us`, or `eu` | `GEMINI_LOCATION` |
| **Collection** | Discovery Engine collection (usually `default_collection`) | `GEMINI_COLLECTION` |
| **Engine / App** | A Gemini Enterprise "app" — the conversational surface users interact with. Created in Cloud console before registration. | `GEMINI_APP_ID` |
| **Assistant** | A scope inside an app (usually `default_assistant`) | `GEMINI_ASSISTANT_ID` |
| **Agent** | Your registered A2A agent under an assistant | derived from your Agent Card `name` |

Full API path:
```
projects/{P}/locations/{L}/collections/{C}/engines/{APP_ID}/assistants/{A}/agents
```

## Prerequisites

1. **Agent is deployed and reachable:**
   ```bash
   curl https://<workspace>/apps/<agent>/.well-known/agent-card.json   # → 200
   ```

2. **A Gemini Enterprise app exists in your project.** In the Cloud console:
   *Gemini Enterprise → Apps → Create app*. Copy the `engineId` — that's
   `GEMINI_APP_ID`. (You can also create one via the Discovery Engine API
   `engines.create` endpoint, but UI is faster for first-time setup.)

3. **APIs enabled:**
   ```bash
   gcloud services enable discoveryengine.googleapis.com --project=<your-project>
   ```

4. **IAM:** the principal running the registration needs one of:
   - `roles/discoveryengine.editor`
   - `roles/discoveryengine.agentspaceAdmin` (Gemini Enterprise admin)
   - A custom role with `discoveryengine.agents.create`, `discoveryengine.agents.get`,
     and `discoveryengine.agents.patch`

5. **Auth locally:**
   ```bash
   gcloud auth application-default login
   gcloud config set project <your-project>
   ```

6. **Install Gemini extras:**
   ```bash
   uv sync --extra gemini
   ```

## Step-by-step

### 1. Confirm the Agent Card

The card you register is the card Gemini will display. Make sure:
- `name`, `description`, `version` are user-facing-ready
- `skills[]` lists every capability with examples
- `capabilities` matches what your agent actually supports
  (set `A2A_CAPABILITY_STREAMING` / `A2A_CAPABILITY_PUSH_NOTIFICATIONS` in `app.yaml`)
- `api.authentication.type` matches `A2A_AUTH_MODE` (auto-emitted)

Pull the live card to verify:
```bash
curl https://<workspace>/apps/<agent>/.well-known/agent-card.json | jq
```

### 2. Run the registration notebook

```bash
AGENT_URL=https://<workspace>/apps/<agent> \
GEMINI_PROJECT_ID=<your-project> \
GEMINI_APP_ID=<engineId-from-step-2> \
GEMINI_LOCATION=global \
uv run python notebooks/register_in_gemini.py
```

Or run it as a notebook in your workspace, setting widgets to the same values.

Expected output:
```
✔ Fetched Agent Card for: my-a2a-agent  (version 0.1.0)
  protocolVersion: v1.0
  API URL:         https://<workspace>/apps/my-a2a-agent/
  Auth type:       bearer
  Capabilities:    {'streaming': True, 'push_notifications': False, ...}
✔ Acquired ADC token (project hint: my-gcp-project)
✔ Built agent resource payload
POST https://discoveryengine.googleapis.com/v1alpha/projects/.../agents?agentId=my-a2a-agent
  HTTP 200
✔ Registered agent: my-a2a-agent
  Console URL: https://console.cloud.google.com/gen-app-builder/...
```

### 3. Configure credentials on Google's side

This step is **necessary** unless your agent runs with `A2A_AUTH_MODE=none` in a
demo environment. Without it, Gemini's outbound gateway can't authenticate to your
agent and calls will fail with 401.

In the Cloud console:
1. Navigate to **Gemini Enterprise → Apps → `<your-app>` → Agents → `<your-agent>`**
2. Open **Settings → Credentials**
3. Pick the type matching your `A2A_AUTH_MODE`:
   - **Bearer** → paste the same token you stored in your Databricks secret
   - **OAuth M2M** → paste the `client_id` / `client_secret` and the token URL
4. Save

Gemini caches these credentials in Secret Manager and injects them on every outbound
call to your agent.

### 4. Verify in the Gemini Enterprise console

Open the console URL from step 2. You should see:
- Your agent in the Agent Registry
- The Agent Card preview (skills, description, version)
- A **Test** button

Click **Test**, type a prompt, confirm a response. Cross-cloud latency is ~2-5s.

### 5. Re-register after Agent Card changes

If you edit `SKILLS`, capabilities, or auth, re-run the notebook. The notebook
auto-detects existing agents (409 conflict) and converts to PATCH for idempotent
updates.

### 6. Deregister

```bash
gcloud alpha discovery-engine agents delete <agent-id> \
  --project=<your-project> \
  --location=<your-location> \
  --collection=default_collection \
  --engine=<your-app-id> \
  --assistant=default_assistant
```

Or use the registry UI's delete button.

## Outbound auth: how Gemini calls your endpoint

Gemini reads `api.authentication.type` in your Agent Card and uses the credentials
you stored in step 3.

| `A2A_AUTH_MODE` | What Gemini sends | What you configure on Google's side |
|---|---|---|
| `bearer` | `Authorization: Bearer <stored-token>` | Paste the token in Gemini's Agent Credentials UI |
| `oauth_m2m` | `Authorization: Bearer <minted-OIDC-token>` | Paste `client_id` / `client_secret` / token URL |
| `none` | No auth header | Demo only — your agent rejects unless `A2A_ENV != prod` |

There's no Google-signed identity JWT — Gemini does not assert its own identity to
your agent. It uses credentials you give it.

## Troubleshooting

- **`403: API not enabled`** — `gcloud services enable discoveryengine.googleapis.com`
- **`403: PermissionDenied`** — your principal needs `discoveryengine.editor` or finer
- **`404` on the registration POST** — usually `GEMINI_APP_ID` is wrong. Confirm the
  app exists: `gcloud alpha discovery-engine engines list --project=<p> --location=global`
- **`400: Invalid agent definition`** — Agent Card is missing a required field. Common
  causes: missing `protocolVersion`, missing `capabilities`, malformed `api.authentication`.
  Pull the live card with curl and check.
- **`409: AlreadyExists`** — notebook auto-converts to PATCH. If you see this in logs,
  the update path was used; check the next status line.
- **Agent registered but Gemini's test call returns `401`** — credentials not configured
  on Google's side. Go back to step 3.
- **`504: Gateway Timeout`** — Gemini's outbound gateway timed out waiting for your
  agent. Either your agent is too slow for sync responses (>30s) or it's not reachable.
  Switch to streaming via `A2A_CAPABILITY_STREAMING=true` and `/tasks/sendSubscribe`.

## What the registration does NOT do

- It does **not** make your agent reachable from the public internet — that's the
  Databricks Apps proxy's job.
- It does **not** verify your domain or check TLS certs at registration time (only at
  invocation time).
- It does **not** push the Agent Card; it pulls. If your card changes, re-run the
  notebook to refresh Gemini's cached copy.
