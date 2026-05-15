# GEMINI_REGISTRATION

How to publish your Databricks-hosted A2A agent into Google's **Gemini Enterprise
Agent Platform** so it's discoverable inside the Gemini Enterprise app and other
agents can delegate to it.

## How this works

- Your agent is **hosted on Databricks**. Google never sees the runtime — only the
  Agent Card URL.
- Gemini Enterprise's **Agent Registry** stores the Agent Card + endpoint URL.
- When a Gemini user (or another Gemini-hosted agent) delegates to your agent,
  Gemini's outbound gateway calls your `/tasks/send` with an OAuth-bridged bearer.
- The registration step is a one-time POST per (agent, project) pair. Re-run to
  update the Agent Card.

## Prerequisites

1. Your agent is deployed and reachable. Confirm:
   ```bash
   curl https://<workspace>/apps/<agent>/.well-known/agent-card.json   # → 200
   ```
2. You have a Google Cloud project with the **Discovery Engine API** enabled:
   ```bash
   gcloud services enable discoveryengine.googleapis.com --project=<your-project>
   ```
3. You have one of these IAM roles on the project:
   - `roles/discoveryengine.editor` (broad)
   - `roles/discoveryengine.agentRegistryEditor` (narrow, recommended)
4. You've authenticated locally:
   ```bash
   gcloud auth application-default login
   gcloud config set project <your-project>
   ```
5. You've installed the kit's Gemini extras:
   ```bash
   uv sync --extra gemini
   ```

## Step-by-step

### 1. Confirm the Agent Card is good
The card you register is the card Gemini will show users. Make sure:
- `name`, `description`, `version` are user-facing-ready
- `skills[]` lists every capability your agent offers, with examples
- `security_schemes` matches your `A2A_AUTH_MODE`

Edit `src/app/agent.py:SKILLS` and `app.yaml`'s `A2A_AGENT_*` vars to tune.

### 2. Run the registration notebook

```bash
AGENT_URL=https://<workspace>/apps/<agent> \
GEMINI_PROJECT_ID=<your-project> \
uv run python notebooks/register_in_gemini.py
```

(Or run it as a notebook in your workspace, setting widgets accordingly.)

Output:
```
Agent URL:        https://<workspace>/apps/my-a2a-agent
Gemini project:   my-gcp-project
Gemini location:  global
Bearer present:   true
✔ Fetched Agent Card for: my-a2a-agent  (version 0.1.0)
✔ Acquired ADC token for project: my-gcp-project
✔ Built agent resource payload
HTTP 200
✔ Registered agent: my-a2a-agent
  Console URL: https://console.cloud.google.com/...
```

### 3. Verify in the Gemini Enterprise console

Open the console URL printed by the notebook. You should see your agent in the Agent
Registry, with the Agent Card preview and a "Test" button.

Click **Test**, type a prompt, and confirm a response comes back. Latency includes
the cross-cloud hop (Gemini → Databricks → LLM → back), so expect ~2-5s.

### 4. Re-register after Agent Card changes

If you edit `SKILLS` or auth mode, re-run the notebook. It uses `PATCH` if the agent
already exists (409 on `POST`), so updates are idempotent.

### 5. Deregister

```bash
gcloud alpha discovery-engine agents delete <agent-id> \
  --project=<your-project> \
  --location=global \
  --collection=default_collection
```

Or use the registry UI's delete button.

## Outbound auth: how Gemini calls your endpoint

Gemini Enterprise's outbound gateway uses the **`securitySchemes`** advertised in
your Agent Card to figure out what credentials to send.

| Your `A2A_AUTH_MODE` | What Gemini sends | What you need to configure on Gemini's side |
|---|---|---|
| `bearer` | `Authorization: Bearer <your-token>` | Store the same token in Gemini's Agent Registry "credentials" field. Gemini will retrieve it from Secret Manager and inject on each call. |
| `oauth_m2m` | `Authorization: Bearer <OIDC token>` minted via client-credentials flow | Configure the client_id/client_secret in Gemini's Agent Registry credentials. |
| `none` | No auth header (will be rejected by your agent unless `A2A_ENV != prod`) | Only useful for demos. |

The Gemini Enterprise Agent Registry UI walks you through credential setup the first
time you create an agent.

## Troubleshooting

- **`403: ApiNotEnabled`** — enable Discovery Engine API on the project.
- **`403: PermissionDenied`** — check IAM; you need `discoveryengine.editor` or finer.
- **`404` on POST** — `GEMINI_LOCATION` likely wrong; try `global`.
- **`409: AlreadyExists`** — the notebook auto-converts to PATCH; if it still fails,
  delete the agent and re-run.
- **Agent registered but Gemini can't invoke it** — check your agent's Apps logs for
  `401` lines; you probably need to load the bearer token into Gemini's credentials.
- **"Agent Card URL not reachable"** — your App is behind workspace auth; you need to
  make it accessible to the Gemini Enterprise outbound gateway. See the App's
  Sharing settings.
