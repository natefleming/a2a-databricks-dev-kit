# Databricks notebook source
# MAGIC %md
# MAGIC # Register your A2A agent in Gemini Enterprise Agent Platform
# MAGIC
# MAGIC This notebook publishes the running Databricks-hosted A2A agent's Agent Card to
# MAGIC Google's **Gemini Enterprise Agent Platform** (formerly Agentspace / Vertex AI
# MAGIC Agent Builder). After this runs, the agent is discoverable inside the Gemini
# MAGIC Enterprise app and other Google-hosted agents can delegate tasks to it via A2A.
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC 1. The agent is deployed and the URL is reachable (`/.well-known/agent-card.json` returns 200).
# MAGIC 2. `gcloud auth application-default login` has been run on the machine running this notebook.
# MAGIC 3. The Google project has the **Discovery Engine API** enabled.
# MAGIC 4. The user/SP running this has `discoveryengine.agentRegistry.create` (or `roles/discoveryengine.editor`).
# MAGIC
# MAGIC **What this does:**
# MAGIC 1. Fetches the live Agent Card from the deployed Databricks App
# MAGIC 2. Translates A2A fields into the Gemini Enterprise agent-registry payload
# MAGIC 3. Calls the Discovery Engine `agents.create` REST endpoint
# MAGIC 4. Prints the discovery URL the customer can use to find the agent
# MAGIC
# MAGIC See `docs/GEMINI_REGISTRATION.md` for the full story.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Inputs

# COMMAND ----------

import os

AGENT_URL = os.environ.get("AGENT_URL") or dbutils.widgets.get("agent_url")  # type: ignore[name-defined]  # noqa: F821
GEMINI_PROJECT_ID = os.environ.get("GEMINI_PROJECT_ID") or dbutils.widgets.get("gemini_project_id")  # type: ignore[name-defined]  # noqa: F821
GEMINI_LOCATION = os.environ.get("GEMINI_LOCATION", "global")
GEMINI_COLLECTION = os.environ.get("GEMINI_COLLECTION", "default_collection")
BEARER_TOKEN = os.environ.get("A2A_BEARER_TOKEN", "")

print(f"Agent URL:        {AGENT_URL}")
print(f"Gemini project:   {GEMINI_PROJECT_ID}")
print(f"Gemini location:  {GEMINI_LOCATION}")
print(f"Bearer present:   {bool(BEARER_TOKEN)}")

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
print(f"  API URL:    {card['api']['url']}")
print(f"  Skills:     {[s['id'] for s in card.get('skills', [])]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Acquire Google credentials
# MAGIC
# MAGIC Uses Application Default Credentials (ADC). On a laptop this means you ran
# MAGIC `gcloud auth application-default login`. In a job, attach a service account.

# COMMAND ----------

import google.auth
import google.auth.transport.requests

credentials, project = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
auth_req = google.auth.transport.requests.Request()
credentials.refresh(auth_req)
print(f"✔ Acquired ADC token for project: {project or GEMINI_PROJECT_ID}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Build the Gemini Enterprise agent-registry payload
# MAGIC
# MAGIC The Discovery Engine API expects an `Agent` resource that points at our hosted
# MAGIC endpoint. Schema docs (preview, may move):
# MAGIC https://cloud.google.com/discovery-engine/docs/reference/rest/v1alpha/projects.locations.collections.engines.agents

# COMMAND ----------

agent_resource = {
    "displayName": card["name"],
    "description": card["description"],
    "icon": {},
    "a2aAgentDefinition": {
        "agentCard": card,
        "endpoint": card["api"]["url"],
    },
    "starterPrompts": [
        {"text": ex} for s in card.get("skills", []) for ex in s.get("examples", [])
    ][:5],
}
print("✔ Built agent resource payload")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. POST to the agent registry

# COMMAND ----------

base = (
    f"https://discoveryengine.googleapis.com/v1alpha/"
    f"projects/{GEMINI_PROJECT_ID}/locations/{GEMINI_LOCATION}/"
    f"collections/{GEMINI_COLLECTION}/agents"
)
agent_id = card["name"].lower().replace("_", "-").replace(" ", "-")
url = f"{base}?agentId={agent_id}"

post_resp = httpx.post(
    url,
    json=agent_resource,
    headers={"Authorization": f"Bearer {credentials.token}"},
    timeout=30.0,
)
print(f"HTTP {post_resp.status_code}")
print(post_resp.text)

# If it already exists, PATCH it instead.
if post_resp.status_code == 409:
    patch_url = f"{base}/{agent_id}"
    patch_resp = httpx.patch(
        patch_url,
        json=agent_resource,
        headers={"Authorization": f"Bearer {credentials.token}"},
        timeout=30.0,
    )
    print(f"PATCH HTTP {patch_resp.status_code}")
    print(patch_resp.text)
    post_resp = patch_resp

post_resp.raise_for_status()
result = post_resp.json()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Confirm discoverability

# COMMAND ----------

discovery_url = (
    f"https://console.cloud.google.com/gen-app-builder/locations/"
    f"{GEMINI_LOCATION}/engines/{GEMINI_COLLECTION}/agents/{agent_id}?project={GEMINI_PROJECT_ID}"
)
print(f"✔ Registered agent: {agent_id}")
print(f"  Console URL: {discovery_url}")
print(f"  Gemini Enterprise should now discover this agent in {GEMINI_LOCATION}.")
