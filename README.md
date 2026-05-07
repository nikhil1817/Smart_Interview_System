# Interviewpreppy

AI interview simulator with a `FastAPI` backend and `React` frontend.

## Project Structure

- `backend/`: API, model inference routes, interview logic
- `frontend/`: React UI

## Prerequisites

- Python `3.10+` (your workspace currently uses a local venv at `.venv`)
- Node.js `18+` and npm

## 1) Backend Setup and Run

From project root:

```bash
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Configure env file:

```bash
cp backend/.env.example backend/.env
```

Set your key in `backend/.env`:

```dotenv
OPENAI_API_KEY=sk-...
```

Run backend:

```bash
.venv/bin/uvicorn --app-dir backend main:app --host 127.0.0.1 --port 8000
```

Backend checks:

```bash
curl -s http://127.0.0.1:8000/
curl -s http://127.0.0.1:8000/api/v1/model/health
```

## 2) Frontend Setup and Run

In a new terminal:

```bash
npm install
npm start
```

Open:

- `http://localhost:3000`

## 3) Run Both Together (2 terminals)

Terminal A (backend):

```bash
source .venv/bin/activate
.venv/bin/uvicorn --app-dir backend main:app --host 127.0.0.1 --port 8000
```

Terminal B (frontend):

```bash
npm start
```

## Notes

- Backend is strict LLM-first by default (`ALLOW_RULE_BASED_FALLBACK=false` in `backend/.env`).
- If OpenAI is rate-limited, endpoints may return `503` with a provider reason.
- Detailed backend model settings are documented in `backend/README.md`.
