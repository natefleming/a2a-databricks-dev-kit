# CONFIGURATION

Every runtime knob the agent reads. All vars use the `A2A_` prefix (except the
Gemini and Databricks SDK ones, which use their library conventions).

Precedence, highest wins:
1. Databricks Apps **Settings → Environment variables** panel
2. `app.yaml` `env:` defaults
3. `.env.local` (local dev only — never deployed)
4. Library defaults in `a2a_databricks.config.AppConfig`

## Agent identity

| Variable | Default | Required | Description |
|---|---|---|---|
| `A2A_AGENT_NAME` | `my-a2a-agent` | yes | Public name in the Agent Card. Lowercase + hyphens. |
| `A2A_AGENT_DESCRIPTION` | "An A2A-protocol agent..." | recommended | One-line description for the Agent Card. |
| `A2A_AGENT_VERSION` | `0.1.0` | recommended | SemVer; bump when you make breaking changes to skills. |

## LLM backing the agent

| Variable | Default | Required | Description |
|---|---|---|---|
| `A2A_LLM_ENDPOINT` | `databricks-claude-sonnet-4-6` | yes | Databricks Model Serving endpoint name (or AI Gateway route). |
| `A2A_LLM_AI_GATEWAY` | `false` | no | `true` routes via `/ai-gateway/mlflow/v1/chat/completions` via langchain-openai. |

## Inbound auth

| Variable | Default | Required when | Description |
|---|---|---|---|
| `A2A_AUTH_MODE` | `bearer` | always | One of `bearer`, `oauth_m2m`, `none`. `none` rejected if `A2A_ENV=prod`. |
| `A2A_ENV` | `dev` | always | `dev`, `staging`, or `prod`. Gates anonymous auth. |
| `A2A_BEARER_SECRET_SCOPE` | `""` | bearer + prod | Databricks secret scope holding the token. |
| `A2A_BEARER_SECRET_KEY` | `""` | bearer + prod | Secret key for the token. |
| `A2A_BEARER_TOKEN` | unset | bearer + local dev | Inline bearer token; only honored in `dev`. |
| `A2A_OAUTH_AUDIENCE` | `""` | oauth_m2m | Audience claim the agent will accept. |
| `A2A_OAUTH_ISSUER` | `""` | oauth_m2m | OIDC issuer URL; introspection endpoint is `{issuer}/oauth2/introspect`. |

## Unity Catalog target

| Variable | Default | Required | Description |
|---|---|---|---|
| `A2A_CATALOG` | `main` | when reading UC | UC catalog the agent reads/writes. |
| `A2A_SCHEMA` | `a2a_agents` | when reading UC | UC schema for agent artifacts. |

## A2A capabilities (advertised in the Agent Card)

| Variable | Default | Description |
|---|---|---|
| `A2A_CAPABILITY_STREAMING` | `true` | Whether `/tasks/sendSubscribe` (SSE) is supported. Set to `false` only if you remove the streaming handler. |
| `A2A_CAPABILITY_PUSH_NOTIFICATIONS` | `false` | Whether the agent supports push-notification callbacks for long-running tasks. Default `false`; the kit doesn't ship a push-notification handler. |

## Databricks workspace auth

These are read by `databricks-sdk` directly and only needed for local dev:

| Variable | Used for |
|---|---|
| `DATABRICKS_HOST` | Workspace URL |
| `DATABRICKS_TOKEN` | PAT auth |
| `DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET` | OAuth M2M auth |

On Databricks Apps these are injected automatically — leave them empty in `app.yaml`.

## Gemini Enterprise registration (notebook only)

| Variable | Default | Description |
|---|---|---|
| `GEMINI_PROJECT_ID` | `""` | GCP project running Gemini Enterprise. |
| `GEMINI_LOCATION` | `global` | Discovery Engine location (`global`, `us`, or `eu`). |
| `GEMINI_APP_ID` | `""` | engineId of an existing Gemini Enterprise app. Create one in the Cloud console before running the notebook. |
| `GEMINI_ASSISTANT_ID` | `default_assistant` | Assistant scope inside the app. Almost always the default. |
| `GEMINI_COLLECTION` | `default_collection` | Discovery Engine collection ID. |
| `AGENT_URL` | — | Public Databricks Apps URL of the agent. |

## Special variables

| Variable | Used for |
|---|---|
| `DATABRICKS_APP_PORT` | Set by the Apps runtime. `app.yaml` binds uvicorn to it. |
| `DATABRICKS_APP_URL` | Set by the Apps runtime. Read by `main.py:_public_url` to build the Agent Card. |
| `A2A_PUBLIC_URL` | Override for `_public_url` when you're behind a custom domain. |
