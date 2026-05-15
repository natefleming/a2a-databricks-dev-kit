# Databricks notebook source
# MAGIC %md
# MAGIC # Register your A2A agent in Gemini Enterprise Agent Platform
# MAGIC
# MAGIC Publishes the running Databricks-hosted A2A agent's Agent Card to Google's
# MAGIC **Gemini Enterprise Agent Platform** (the April-2026 unification of Agentspace +
# MAGIC Vertex AI Agent Builder). After this runs, the agent is discoverable inside the
# MAGIC Gemini Enterprise app, and other Google-hosted agents can delegate tasks to it
# MAGIC via the A2A protocol.
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC 1. The agent is deployed and `/.well-known/agent-card.json` returns 200.
# MAGIC 2. A **Gemini Enterprise app** has already been created in your project (the
# MAGIC    "engine" that hosts conversations + agents). You need its `GEMINI_APP_ID`
# MAGIC    (a.k.a. `engineId`). Create one in the Cloud console under
# MAGIC    *Gemini Enterprise → Apps → Create app*, or via the Discovery Engine API.
# MAGIC 3. `gcloud auth application-default login` has been run, OR the notebook runs
# MAGIC    as a Databricks job with a SP that has `roles/discoveryengine.editor` on the
# MAGIC    GCP project.
# MAGIC 4. The Discovery Engine API is enabled on the GCP project.
# MAGIC
# MAGIC **What this does:**
# MAGIC 1. Fetches the live Agent Card from the deployed Databricks App
# MAGIC 2. Translates A2A fields into the Discovery Engine Agent payload
# MAGIC 3. Calls `agents.create` on the engine's `assistants/default_assistant` resource
# MAGIC 4. On 409 (already exists), falls back to PATCH so re-runs are idempotent
# MAGIC 5. Prints the console URL where the agent is now discoverable
# MAGIC
# MAGIC See `docs/GEMINI_REGISTRATION.md` for the full story, including IAM and OAuth
# MAGIC credential configuration on Google's side.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Inputs

# COMMAND ----------

import os


def _from_env_or_widget(name: str, default: str = "") -> str:
    val = os.environ.get(name)
    if val:
        return val
    try:
        return dbutils.widgets.get(name.lower())  # type: ignore[name-defined]  # noqa: F821
    except Exception:
        return default


AGENT_URL = _from_env_or_widget("AGENT_URL")
GEMINI_PROJECT_ID = _from_env_or_widget("GEMINI_PROJECT_ID")
GEMINI_LOCATION = _from_env_or_widget("GEMINI_LOCATION", "global")
GEMINI_APP_ID = _from_env_or_widget("GEMINI_APP_ID")
GEMINI_ASSISTANT_ID = _from_env_or_widget("GEMINI_ASSISTANT_ID", "default_assistant")
GEMINI_COLLECTION = _from_env_or_widget("GEMINI_COLLECTION", "default_collection")
BEARER_TOKEN = os.environ.get("A2A_BEARER_TOKEN", "")

assert AGENT_URL, "AGENT_URL must be set (the public URL of your Databricks app)"
assert GEMINI_PROJECT_ID, "GEMINI_PROJECT_ID must be set"
assert GEMINI_APP_ID, (
    "GEMINI_APP_ID must be set. This is the engineId of an existing Gemini "
    "Enterprise app. Create one in the Cloud console first."
)

print(f"Agent URL:           {AGENT_URL}")
print(f"Gemini project:      {GEMINI_PROJECT_ID}")
print(f"Gemini location:     {GEMINI_LOCATION}")
print(f"Gemini app (engine): {GEMINI_APP_ID}")
print(f"Gemini assistant:    {GEMINI_ASSISTANT_ID}")
print(f"Gemini collection:   {GEMINI_COLLECTION}")
print(f"Bearer present:      {bool(BEARER_TOKEN)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Fetch the live Agent Card

# COMMAND ----------

import httpx

card_url = AGENT_URL.rstrip("/") + "/.well-known/agent-card.json"
headers = {"Authorization": f"Bearer {BEARER_TOKEN}"} if BEARER_TOKEN else {}

resp = httpx.get(card_url, headers=headers, timeout=15.0)
resp.raise_for_status()
card = resp.json()
print(f"✔ Fetched Agent Card for: {card['name']}  (version {card['version']})")
print(f"  protocolVersion: {card.get('protocol_version', card.get('protocolVersion'))}")
print(f"  API URL:         {card['api']['url']}")
print(f"  Auth type:       {card['api'].get('authentication', {}).get('type', 'unknown')}")
print(f"  Capabilities:    {card.get('capabilities', {})}")
print(f"  Skills:          {[s['id'] for s in card.get('skills', [])]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Acquire Google credentials
# MAGIC
# MAGIC Uses Application Default Credentials. On a laptop this means you ran
# MAGIC `gcloud auth application-default login`. In a Databricks job, attach a GCP
# MAGIC service account via Workload Identity Federation.

# COMMAND ----------

import google.auth
import google.auth.transport.requests

credentials, project = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
auth_req = google.auth.transport.requests.Request()
credentials.refresh(auth_req)
print(f"✔ Acquired ADC token (project hint: {project or GEMINI_PROJECT_ID})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Build the Discovery Engine agent-registry payload
# MAGIC
# MAGIC The `agents.create` resource sits under a specific assistant inside a specific
# MAGIC engine (Gemini Enterprise app). Full path:
# MAGIC
# MAGIC ```
# MAGIC projects/{P}/locations/{L}/collections/{C}/engines/{APP_ID}/assistants/{A}/agents
# MAGIC ```

# COMMAND ----------

agent_resource = {
    "displayName": card["name"],
    "description": card["description"],
    "icon": {},
    "a2aAgentDefinition": {
        "agentCard": card,
        "endpoint": str(card["api"]["url"]),
    },
    "starterPrompts": [
        {"text": ex}
        for s in card.get("skills", [])
        for ex in s.get("examples", [])
    ][:5],
}
print("✔ Built agent resource payload")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. POST to the agent registry
# MAGIC
# MAGIC On a regional location, the host is `{region}-discoveryengine.googleapis.com`.
# MAGIC On `global`, it's just `discoveryengine.googleapis.com`.

# COMMAND ----------

host = (
    "discoveryengine.googleapis.com"
    if GEMINI_LOCATION == "global"
    else f"{GEMINI_LOCATION}-discoveryengine.googleapis.com"
)
base = (
    f"https://{host}/v1alpha/"
    f"projects/{GEMINI_PROJECT_ID}/locations/{GEMINI_LOCATION}/"
    f"collections/{GEMINI_COLLECTION}/engines/{GEMINI_APP_ID}/"
    f"assistants/{GEMINI_ASSISTANT_ID}/agents"
)
agent_id = card["name"].lower().replace("_", "-").replace(" ", "-")
url = f"{base}?agentId={agent_id}"

print(f"POST {url}")
post_resp = httpx.post(
    url,
    json=agent_resource,
    headers={"Authorization": f"Bearer {credentials.token}"},
    timeout=30.0,
)
print(f"  HTTP {post_resp.status_code}")
print(post_resp.text[:1500])

# Already exists? Update it instead. PATCH semantics keep this notebook idempotent.
if post_resp.status_code == 409:
    patch_url = f"{base}/{agent_id}"
    print(f"\nAgent exists. PATCHing instead: {patch_url}")
    patch_resp = httpx.patch(
        patch_url,
        json=agent_resource,
        headers={"Authorization": f"Bearer {credentials.token}"},
        timeout=30.0,
    )
    print(f"  HTTP {patch_resp.status_code}")
    print(patch_resp.text[:1500])
    post_resp = patch_resp

post_resp.raise_for_status()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Confirm discoverability

# COMMAND ----------

console_url = (
    f"https://console.cloud.google.com/gen-app-builder/locations/"
    f"{GEMINI_LOCATION}/engines/{GEMINI_APP_ID}/agents/{agent_id}"
    f"?project={GEMINI_PROJECT_ID}"
)
print(f"✔ Registered agent: {agent_id}")
print(f"  Console URL: {console_url}")
print()
print("Next:")
print(f"  - Open the console URL above to verify the agent appears in {GEMINI_APP_ID}.")
print("  - If A2A_AUTH_MODE=bearer or oauth_m2m, configure the matching credentials")
print("    in the Gemini Enterprise console for this agent (Settings → Credentials).")
print("  - Test by delegating a task from another Gemini Enterprise agent or the")
print("    Gemini Enterprise chat surface.")
