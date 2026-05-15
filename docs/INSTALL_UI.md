# INSTALL_UI — Apps "Custom from Git" walkthrough

This is the primary install path. No CLI required; everything happens in the
Databricks workspace UI plus the Google Cloud console.

## Prerequisites

- A Databricks workspace where you can create Databricks Apps
- (For prod auth) Permission to read a Databricks secret scope
- (For Gemini registration) A GCP project + `gcloud` on your laptop

## Steps

### 1. Create the App

In the workspace sidebar, click **Apps**. Then **Create app** → **Custom app**.

Fill in:
- **Name**: lowercase, hyphens, e.g. `my-a2a-agent`. This becomes the URL slug.
- **Description**: anything; can edit later.

Click **Create**. You land on the app's status page.

### 2. Configure the Git source

Click **Deploy**. The first deploy prompts you to pick a source:
- **Git source** → paste `https://github.com/natefleming/a2a-databricks-dev-kit`
- **Branch**: `main` for latest, or a tag like `v1.0.0` for a pinned release
- Click **Deploy**

The platform clones the repo, reads `app.yaml`, runs `pip install -r requirements.txt`,
then executes the `command` block. Watch progress on the **Logs** tab.

### 3. (If your workspace has a Git policy) Add the GitHub PAT

If your workspace admin has enabled "Only allow app deployments from Git" or restricts
public Git access, you may need to configure a GitHub access token in **Settings →
Git providers** first.

### 4. Set environment variables

Once the app is running (~2 minutes for first deploy), open **Settings → Environment
variables**.

For a **demo** environment (no auth, fastest path):

| Name | Value |
|---|---|
| `A2A_LLM_ENDPOINT` | `databricks-claude-sonnet-4-6` |
| `A2A_AUTH_MODE` | `none` |
| `A2A_ENV` | `dev` |

For **production** (bearer auth):

| Name | Value |
|---|---|
| `A2A_LLM_ENDPOINT` | your serving endpoint |
| `A2A_AUTH_MODE` | `bearer` |
| `A2A_ENV` | `prod` |
| `A2A_BEARER_SECRET_SCOPE` | your secret scope name |
| `A2A_BEARER_SECRET_KEY` | the key holding the bearer token |

Then **Save & Restart**.

> Create the secret first:
> ```bash
> databricks secrets create-scope my-a2a-agent-scope
> databricks secrets put-secret my-a2a-agent-scope bearer-token \
>   --string-value "$(openssl rand -hex 32)"
> ```
> Then in the App Settings: `A2A_BEARER_SECRET_SCOPE=my-a2a-agent-scope`,
> `A2A_BEARER_SECRET_KEY=bearer-token`.

### 5. Grant UC access (if the agent reads Unity Catalog)

The App runs as a service principal. It is **not** in the `account users` group by
default, so it can't see anything in UC until you grant it. From a SQL editor:

```sql
GRANT USE CATALOG ON CATALOG main TO `<app-sp-client-id>`;
GRANT USE SCHEMA ON SCHEMA main.a2a_agents TO `<app-sp-client-id>`;
GRANT SELECT ON ALL TABLES IN SCHEMA main.a2a_agents TO `<app-sp-client-id>`;
```

(Find the SP client ID in the App's **Settings → Permissions** tab.)

### 6. Verify the Agent Card

Open in a browser:
```
https://<workspace>.cloud.databricks.com/apps/my-a2a-agent/.well-known/agent-card.json
```

You should see JSON starting with `"name": "my-a2a-agent"`. If you get a 502 or 404,
see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

### 7. Send a test task

```bash
curl -X POST https://<workspace>.cloud.databricks.com/apps/my-a2a-agent/tasks/send \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $A2A_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tasks/send",
    "params": {"message": {"parts": [{"kind": "text", "text": "Hello"}]}}
  }'
```

`200 OK` + a result envelope means everything works.

### 8. Register with Gemini Enterprise

See [GEMINI_REGISTRATION.md](GEMINI_REGISTRATION.md).

## What to do when you push code changes

1. Push to the repo's chosen branch.
2. In the App page, click **Redeploy**. Apps re-clones, re-installs deps (cached),
   restarts uvicorn.
3. The Agent Card serves the new version instantly.

## How to roll back

In the App page, click **Deploy history** → pick a previous successful deploy →
**Redeploy**. The Apps proxy switches the active commit; no downtime.
