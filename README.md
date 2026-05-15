# a2a-databricks-dev-kit

🔨 Zero-to-deployed A2A agent on Databricks — discoverable in Google Gemini Enterprise.

This dev kit takes you from an empty workspace to a Google **A2A-protocol-compliant**
agent **running on Databricks Apps** and **registered in the Gemini Enterprise
Agent Platform** — without rebuilding the FastAPI scaffolding, Agent Card, auth,
bundle plumbing, or registration glue every time.

## What you get

- A FastAPI-based **Databricks App** that speaks the [A2A protocol](https://a2a-protocol.org/latest/specification/)
  (Agent Card at `/.well-known/agent-card.json`, JSON-RPC at `/tasks/send`, SSE streaming at `/tasks/sendSubscribe`).
- A small Python library (`a2a_databricks`) that handles transport, auth (bearer / OAuth M2M / anonymous),
  Databricks LLM routing (Model Serving and AI Gateway), and MLflow tracing — so your `agent.py`
  only contains agent logic.
- A `databricks bundle init` template path for IaC teams that want declarative deploys.
- A notebook that registers your deployed agent in Gemini Enterprise.

## Two ways to install

### Path 1 — Databricks Apps "Custom from Git" (recommended for first-time users)

1. In your Databricks workspace, click **Apps → Create app → Custom app**.
2. Name it (e.g., `my-a2a-agent`) and click **Create**.
3. Click **Deploy → Configure Git source** and paste this repo's URL.
4. Pick branch `main` (or a tagged release) and click **Deploy**.
5. After the app boots, open **Settings → Environment variables** and set at minimum:
   - `A2A_LLM_ENDPOINT=databricks-claude-sonnet-4-6`
   - `A2A_BEARER_SECRET_SCOPE=<your-scope>` and `A2A_BEARER_SECRET_KEY=<your-key>` (prod)
6. Save and restart. Hit `https://<workspace>/apps/<app-name>/.well-known/agent-card.json` — `200 OK`.

Full walkthrough with screenshots: [docs/INSTALL_UI.md](docs/INSTALL_UI.md).

### Path 2 — `databricks bundle init` (IaC teams)

```bash
databricks bundle init https://github.com/<org>/a2a-databricks-dev-kit
# answers a few prompts: agent name, catalog, schema, LLM endpoint, auth mode
cd <agent-name>
databricks bundle deploy
databricks bundle run <agent-name>_app
```

Full walkthrough: [docs/INSTALL_BUNDLE.md](docs/INSTALL_BUNDLE.md).

## Documentation

| Doc | When to read |
|---|---|
| [QUICKSTART.md](docs/QUICKSTART.md) | First 10 minutes — get an agent running end-to-end |
| [INSTALL_UI.md](docs/INSTALL_UI.md) | UI-driven Apps-from-Git install path |
| [INSTALL_BUNDLE.md](docs/INSTALL_BUNDLE.md) | CLI-driven `databricks bundle init` path |
| **[DEVELOPMENT.md](docs/DEVELOPMENT.md)** ★ | Step-by-step dev workflow: clone → customize → test → deploy → iterate |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Request flow, file purposes, A2A protocol mapping |
| [LOCAL_DEV.md](docs/LOCAL_DEV.md) | Running on your laptop before deploy |
| [CONFIGURATION.md](docs/CONFIGURATION.md) | Every env var, what it does, defaults |
| [TESTING.md](docs/TESTING.md) | Unit vs integration markers, fixtures |
| [GEMINI_REGISTRATION.md](docs/GEMINI_REGISTRATION.md) | Registering with Gemini Enterprise |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common failure modes + fixes |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md) | Extending the kit itself |

## Repo map

```
.
├── app.yaml                  ★ Apps runtime config
├── requirements.txt          ★ Apps auto-installs from here
├── pyproject.toml            Source of truth for deps
├── Makefile                  install / test / check / format / run
├── databricks.yml            ◆ Bundle config (secondary path)
├── databricks_template_schema.json  ◆ Bundle init prompts
├── src/
│   ├── app/                  Your agent — main.py + agent.py
│   └── a2a_databricks/       Helper library
├── notebooks/
│   └── register_in_gemini.py Register with Gemini Enterprise
├── tests/                    pytest unit + integration
└── docs/                     ☚ Start here
```

`★` = Apps-from-Git path. `◆` = `bundle init` path.

## License

Apache-2.0.
