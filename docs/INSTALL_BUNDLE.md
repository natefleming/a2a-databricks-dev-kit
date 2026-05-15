# INSTALL_BUNDLE — `databricks bundle init` walkthrough

This is the alternative install path for IaC teams who prefer to manage Databricks
resources declaratively. The end-user experience is one `bundle init` command, one
`bundle deploy`, and the agent is live.

## Prerequisites

- Databricks CLI ≥ 0.279.0 (`databricks --version`)
- `uv` ≥ 0.4
- A configured Databricks profile (`databricks auth login --profile <name>`)

## Steps

### 1. Init the project

```bash
databricks bundle init https://github.com/natefleming/a2a-databricks-dev-kit
```

You'll be prompted for:
- **Project name** — slug, e.g. `customer_support_agent`
- **Agent description** — one-liner for the Agent Card
- **Catalog** — UC catalog for agent artifacts
- **Schema** — UC schema for agent artifacts
- **LLM endpoint** — serving endpoint backing the agent
- **Auth mode** — `bearer`, `oauth_m2m`, or `none` (none rejected in `prod`)

The CLI clones the repo, processes `template/{{.project_name}}/...` through Go
templates, and writes the rendered project to `./customer_support_agent/`.

### 2. Inspect what was generated

```bash
cd customer_support_agent
tree -L 2
# customer_support_agent/
# ├── README.md
# ├── databricks.yml
# ├── app.yaml
# ├── pyproject.toml
# ├── requirements.txt
# ├── Makefile
# ├── .env.example
# ├── .gitignore
# ├── resources/
# │   └── app.yml
# └── src/
#     └── app/
```

### 3. Sync deps + run tests

```bash
make install
make unit
```

### 4. Validate the bundle

```bash
databricks bundle validate -t dev --profile <your-profile>
```

Fixes any YAML errors before the deploy. Expected output: `Bundle is valid`.

### 5. Deploy

```bash
databricks bundle deploy -t dev --profile <your-profile>
```

What this does:
- Builds the wheel via `uv build` (declared in `databricks.yml: artifacts.default`)
- Uploads source files matching `sync.include` to the workspace
- Creates/updates the App resource defined in `resources/app.yml`
- Applies UC schema grants to the App's service principal
- Creates the MLflow experiment

### 6. Run / start the app

```bash
databricks bundle run a2a_agent_app -t dev --profile <your-profile>
```

The App boots, runs `pip install -r requirements.txt` (which includes a pip-from-git
install of the helper library), and starts uvicorn.

### 7. Verify

```bash
APP_URL=$(databricks apps get a2a_agent_app-dev --profile <your-profile> | jq -r .url)
curl $APP_URL/.well-known/agent-card.json
```

### 8. Promote to staging / prod

```bash
databricks bundle deploy -t staging --profile <prod-profile>
databricks bundle run a2a_agent_app -t staging --profile <prod-profile>
```

The `staging` and `prod` targets in `databricks.yml` override `auth_mode` to `bearer`
and toggle the bundle into production mode.

## Iteration loop

```bash
# Edit src/app/agent.py
make unit                                # verify locally
databricks bundle deploy -t dev          # push to dev
databricks bundle run a2a_agent_app -t dev  # restart with new code
```

Apps caches the dependency install, so re-deploys after the first are <30s.

## Tear down

```bash
databricks bundle destroy -t dev --profile <your-profile>
```

Removes the App, the experiment, and the schema grants.

## When to pick this path over Apps-from-Git

- You want **multi-target** deploys (dev / staging / prod) without using three
  separate workspace UIs.
- You want **resource changes** (UC grants, experiment locations) to be part of the
  same commit as code changes.
- You're already running Asset Bundles for other workloads and want consistency.

Apps-from-Git is simpler for one-off demos; bundle init is better for repeatable,
auditable deployments.
