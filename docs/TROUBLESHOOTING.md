# TROUBLESHOOTING

Symptom → likely cause → fix.

## Deploy / startup failures

### "App Not Available" 502 from the Apps proxy
**Cause:** uvicorn is binding to a port other than `$DATABRICKS_APP_PORT` (defaults to 8000).

**Fix:** Make sure `app.yaml` has `--port ${DATABRICKS_APP_PORT:-8000}` in the command.
This kit ships with that. If you've edited `app.yaml`, double-check the port arg.

### Build fails: "No command to run"
**Cause:** `app.yaml` not in the repo root, or wasn't synced.

**Fix:** Confirm `app.yaml` is at the repo root (not inside `src/` or `template/`).
For the bundle path, confirm `sync.include` lists `app.yaml`.

### `ImportError: cannot import name 'ChatDatabricks' from 'langchain_databricks'`
**Cause:** Old `langchain-databricks` is pinned somewhere.

**Fix:** This kit uses the newer `databricks-langchain`. If you've edited deps,
make sure your `requirements.txt` lists `databricks-langchain>=0.4,<1` (not the
deprecated `langchain-databricks`).

### `ValidationError: A2A_AUTH_MODE=oauth_m2m requires A2A_OAUTH_AUDIENCE`
**Cause:** You set oauth_m2m but didn't configure the audience.

**Fix:** Either set `A2A_OAUTH_AUDIENCE` (and `A2A_OAUTH_ISSUER`), or switch to a
different auth mode.

## Runtime errors

### `PERMISSION_DENIED` when the agent queries Unity Catalog
**Cause:** The App's service principal isn't in `account users` by default and has
no UC grants.

**Fix:** Grant explicitly:
```sql
GRANT USE CATALOG ON CATALOG main TO `<app-sp-client-id>`;
GRANT USE SCHEMA ON SCHEMA main.a2a_agents TO `<app-sp-client-id>`;
GRANT SELECT ON ALL TABLES IN SCHEMA main.a2a_agents TO `<app-sp-client-id>`;
```
(For the bundle path, this is in `resources/app.yml`; for Apps-from-Git, do it once
in a SQL editor after first deploy.)

### AI Gateway returns `400 Bad Request — Unexpected field 'name' in messages`
**Cause:** AI Gateway 400s on `messages[n].name`. The kit strips that field, but only
if you go through `chat_model(..., ai_gateway=True)`.

**Fix:** Use the helper (`from a2a_databricks import chat_model`); don't construct
`ChatOpenAI` yourself. If you do, mirror the `_AIGatewayChatOpenAI._get_request_payload`
pattern in `src/a2a_databricks/llm.py`.

### `PERMISSION_DENIED` from the LLM when calling `/tasks/send`
**Cause:** The App service principal isn't granted `CAN_QUERY` on the serving
endpoint. Setting `A2A_LLM_ENDPOINT=<name>` tells your code which endpoint to call —
it does NOT grant the App SP permission to call it.

**Fix (UI / Apps-from-Git):**
Apps → your app → **Resources → + Add resource → Serving endpoint**, set
permission `CAN_QUERY`, restart the app.

**Fix (bundle):**
The inner `resources:` list under `apps.a2a_agent_app` in `resources/app.yml`
should already declare this. If it's missing or `var.llm_endpoint` doesn't match
`A2A_LLM_ENDPOINT`, fix and `databricks bundle deploy` again.

### `PERMISSION_DENIED` reading the bearer-token secret at startup
**Cause:** Same shape as above, but for secrets. The App SP needs explicit `READ`
on the secret scope/key.

**Fix (UI):** Apps → your app → **Resources → + Add resource → Secret**, permission `READ`.

**Fix (bundle):** Uncomment the `bearer-token` block in `resources/app.yml` and set
`var.bearer_secret_scope` + `var.bearer_secret_key` in `databricks.yml`. (If you
ran `bundle init` with `auth_mode=bearer`, the secret block is already uncommented;
just fill the vars.)

### `401 Unauthorized` on `/tasks/send`
**Cause:** Either the bearer token is wrong, or the App is using `A2A_AUTH_MODE=bearer`
but no token has been provisioned.

**Fix:**
- Check `A2A_BEARER_SECRET_SCOPE` + `A2A_BEARER_SECRET_KEY` point at a real secret.
- For local dev, set `A2A_BEARER_TOKEN=<any-string>` and use the same in `curl`.
- To bypass auth in dev, set `A2A_AUTH_MODE=none` + `A2A_ENV=dev`.

### `OAuth token introspection failed` in production
**Cause:** Either the issuer URL is wrong or the IdP doesn't expose `/oauth2/introspect`.

**Fix:** Check `A2A_OAUTH_ISSUER` is the base URL (no trailing slash) and that the
IdP supports OAuth 2.0 token introspection (RFC 7662). If not, replace
`OAuthM2MVerifier` with a JWKS-based verifier.

## Bundle-specific

### `databricks bundle deploy` fails: `Terraform engine deprecated`
**Cause:** Old CLI; the kit uses `bundle.engine: direct` which requires CLI ≥ 0.279.0.

**Fix:** `databricks --version` → upgrade if needed: `brew upgrade databricks/tap/databricks`.

### Deploy errors with `App name must contain only lowercase letters, numbers, and dashes`
**Cause:** The `project_name` you gave to `bundle init` contains an underscore. The
Databricks Apps API rejects underscores in app names.

**Fix:** Re-init with a hyphen-only name (e.g. `my-a2a-agent`, not `my_a2a_agent`). The
template schema enforces this on fresh inits; older renders may still have an
underscore in `databricks.yml` — edit the `agent_name` default to use hyphens.

### Deploy errors with `Parent directory does not exist: /Shared/...`
**Cause:** Older versions of the kit declared the MLflow experiment at
`/Shared/a2a-agents/...`, which requires that parent directory to pre-exist with
CREATE permission for your user.

**Fix:** Newer renders use `/Users/${workspace.current_user.userName}/a2a-agents-...`.
Either re-init from a current template, or edit `resources/app.yml` to put the
experiment under your user path.

### `uv sync` errors with `Could not find a version that satisfies the requirement ...`
**Cause:** Your local Python is outside the kit's pinned range (`>=3.11,<3.12`).
The kit pins to Python 3.11 specifically because that's what Databricks Apps runs;
resolving against 3.12+ can pull in wheels that don't exist for 3.11 at deploy.

**Fix:** Install Python 3.11 via `uv` and let the `.python-version` file at the
repo root pick it up: `uv python install 3.11 && uv sync`.

### App crashes at startup with `ModuleNotFoundError: No module named 'app'`
**Cause:** You're on the Apps-from-Git path. Apps clones your repo and runs
`pip install -r requirements.txt`, which installs the listed dependencies but
**does not install the project's own source as a package**. The `app` package
sitting at `src/app/` isn't on Python's import path.

(The bundle path doesn't hit this because `uv build` creates a wheel that
Apps installs, exposing the `app` package.)

**Fix:** The kit's `app.yaml` runs uvicorn under `sh -c "PYTHONPATH=src uvicorn ..."`.
If you've customized the command, make sure `PYTHONPATH=src` is preserved, or
move your agent to `app/` at the repo root.

### App crashes at startup: `Error: Invalid value for '--port': '${DATABRICKS_APP_PORT:-8000}' is not a valid integer.`
**Cause:** Databricks Apps' list-form `command:` is exec'd directly without a shell,
so `${VAR}` isn't expanded — it's passed to uvicorn as a literal string.

**Fix:** Use shell-form to force expansion (this is the kit's default since the
deploy verification on FEVM):
```yaml
command:
  - "sh"
  - "-c"
  - "uvicorn app.main:app --host 0.0.0.0 --port ${DATABRICKS_APP_PORT:-8000}"
```

### Deploy errors with `User does not have CREATE SCHEMA on Catalog ...`
**Cause:** The deploying user doesn't have `CREATE SCHEMA` on the chosen catalog.
Most FEVM and field workspaces don't grant this by default.

**Fix:** The kit ships the schema declaration commented out for this reason. The
reference agent doesn't use UC anyway. If you want a schema:
- Use a catalog where you have `CREATE SCHEMA` (often `workspace.default`), or
- Pre-create the schema in a SQL editor, then uncomment **only the grants** in
  `resources/app.yml`, replacing the schema-creation block.

### Deploy errors with `Workspace ... has reached the maximum limit of 300 apps`
**Cause:** Environmental, not a kit bug. The target workspace has hit Databricks' per-
workspace app cap.

**Fix:** Delete an unused app (`databricks apps list --profile <p>` → pick one →
`databricks apps delete <name>`), or pick a different workspace.

### `requirements.txt` and `pyproject.toml` drift
**Cause:** You added a dep to `pyproject.toml` but forgot to regen `requirements.txt`.

**Fix:** `make export-reqs` regenerates `requirements.txt` from `uv.lock`. Apps reads
`requirements.txt`, not `pyproject.toml` — this is the canonical pattern.

## Gemini Enterprise registration

### `403: API not enabled`
**Fix:** `gcloud services enable discoveryengine.googleapis.com --project=<project>`

### `404` on the registration POST
**Fix:** `GEMINI_LOCATION` is wrong. Try `global`. Some features are region-locked.

### Agent registered but Gemini calls fail at runtime
**Fix:** Check the App's logs. Most likely the bearer token Gemini is sending doesn't
match the one your agent expects. Make sure the same value is in both the Databricks
secret (read by the agent) and the Gemini Agent Registry credentials field (sent by
Gemini's outbound gateway).

## Local dev

### `make run` fails with `Address already in use`
**Fix:** `lsof -ti:8080 | xargs kill` then retry, or pass `LOCAL_PORT=8090 make run`.

### uvicorn doesn't pick up code changes
**Fix:** Make sure you used `make run` (passes `--reload`) and not a raw uvicorn invocation.

### Tests pass locally but fail in CI
**Fix:** CI runs only `-m unit`. If your test depends on a workspace, mark it
`@pytest.mark.integration` so CI skips it.
