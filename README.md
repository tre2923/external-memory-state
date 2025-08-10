# External Memory & State API

A tiny web service for **persistent memory** and **state tracking** that can be used with GPT-OSS or any LLM agent to carry context across sessions and goals.

- Store & retrieve key/value **state variables** (e.g., `current_phase`, `trade_winrate`)
- Keep timestamped **memory logs** with tags and search
- Track **goals** and progress notes
- Export an **LLM-ready context block** for prompt injection

---

## Features

- **Minimal dependencies:** FastAPI + SQLite
- **Auth:** Single API key
- **Search:** SQLite FTS5 for full-text memory search
- **Deploy anywhere:** Works locally or on Fly.io (LiteFS recommended for HA)
- **LLM-friendly:** `/context/export` returns compact prompt text

---

## Requirements

- Python 3.11+
- [FastAPI](https://fastapi.tiangolo.com/)
- SQLite 3.38+ (for FTS5)
- Docker (for deployment)
- Fly.io account (for hosting)
- An OSS or hosted GPT-compatible LLM endpoint

---

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/<your-user>/external-mem-kit.git
cd external-mem-kit
pip install -r requirements.txt

Run locally:

export API_KEY=change-me
uvicorn app.main:app --reload --port 8080


⸻

Deployment (Fly.io)
	1.	Login to Fly.io

fly auth login


	2.	Launch the app

fly launch --name external-mem-kit --copy-config


	3.	Create persistent volume

fly volumes create data --size 1


	4.	Set API key

fly secrets set API_KEY=<your-strong-key>


	5.	Deploy

fly deploy



⸻

Authentication

All requests require an Authorization header:

Authorization: Bearer <API_KEY>


⸻

API Endpoints

State Management

POST /state/set

Set or update a state variable.

Body:

{
  "key": "current_phase",
  "value": "testing"
}

Response:

{ "ok": true }

GET /state/get?key=<name>

Get a stored state variable by key.

Example:

/state/get?key=current_phase

Response:

{ "value": "testing" }


⸻

Memory Log

POST /memory/add

Add a timestamped memory entry.

Body:

{
  "event": "Deployed v1.2",
  "tags": ["deploy", "v1.2"]
}

Response:

{ "ok": true }

GET /memory/search?q=<query>&limit=<n>

Search memory entries with full-text search.

Example:

/memory/search?q=deploy&limit=5

Response:

[
  { "id": 1, "event": "Deployed v1.2", "tags": "deploy,v1.2" }
]


⸻

Goals

POST /goals/add

Add a new goal.

Body:

{
  "goal": "Launch MVP"
}

Response:

{ "id": 1, "goal": "Launch MVP", "status": "new" }

POST /goals/progress

Update goal status or add a progress note.

Body:

{
  "goal_id": 1,
  "status": "in_progress",
  "note": "Wired authentication"
}

Response:

{ "ok": true }


⸻

Context Export

GET /context/export?max_tokens=<n>

Export a compact, LLM-ready context block containing:
	•	Current state variables
	•	Active goals
	•	Recent memory entries

Example:

/context/export?max_tokens=1500

Response:

{
  "prompt_block": "# State:\n- current_phase: testing\n\n# Goals:\n- [in_progress] (1) Launch MVP\n\n# Recent Memory:\n- Deployed v1.2 (deploy,v1.2)"
}


⸻

Example Usage

Set state:

curl -s -H "Authorization: Bearer <KEY>" \
  -H "Content-Type: application/json" \
  -d '{"key":"current_phase","value":"testing"}' \
  https://<APP>.fly.dev/state/set

Get state:

curl -s -H "Authorization: Bearer <KEY>" \
  "https://<APP>.fly.dev/state/get?key=current_phase"

Add memory:

curl -s -H "Authorization: Bearer <KEY>" \
  -H "Content-Type: application/json" \
  -d '{"event":"Deployed v1.2","tags":["deploy","v1.2"]}' \
  https://<APP>.fly.dev/memory/add

Search memory:

curl -s -H "Authorization: Bearer <KEY>" \
  "https://<APP>.fly.dev/memory/search?q=deploy&limit=5"

Export context:

curl -s -H "Authorization: Bearer <KEY>" \
  "https://<APP>.fly.dev/context/export?max_tokens=1500"


⸻

Hooking up to a GPT-Compatible LLM
	1.	Fetch /context/export before each LLM request.
	2.	Prepend prompt_block to your system message.
	3.	Send combined messages to your GPT-compatible endpoint.

Example (JavaScript):

const ctx = await fetch(`${BASE}/context/export?max_tokens=1500`, { headers });
const { prompt_block } = await ctx.json();

const messages = [
  { role: "system", content: "You are a helpful assistant." },
  { role: "system", content: prompt_block },
  { role: "user", content: "What's our next step?" }
];

const resp = await fetch(LLM_ENDPOINT+"/chat/completions", {
  method: "POST",
  headers: { "Authorization": "Bearer "+LLM_KEY, "Content-Type":"application/json" },
  body: JSON.stringify({ model: "your-oss-model", messages })
});
const data = await resp.json();


⸻

License

MIT