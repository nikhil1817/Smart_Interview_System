# Backend Setup Notes

## OpenAI-powered Interview Inference

The model inference routes in `backend/routes/model_inference.py` now use OpenAI by default with optional fallback to existing local evaluators.

### Recommended local setup (`.env`)

1. Copy `backend/.env.example` to `backend/.env`.
2. Put your real key in `OPENAI_API_KEY`.
3. Start the backend normally; `backend/main.py` loads both `/.env` and `backend/.env`, with `backend/.env` intended as the main local backend config.

### Required environment variable

- `OPENAI_API_KEY`: your OpenAI API key

### Optional environment variables

- `OPENAI_QUESTION_MODEL`: defaults to `o4-mini`
- `OPENAI_EVAL_MODEL`: defaults to `o4-mini`
- `OPENAI_FEEDBACK_MODEL`: defaults to `o4-mini`
- `OPENAI_TIMEOUT_SECONDS`: defaults to `25`
- `OPENAI_MAX_RETRIES`: defaults to `1`
- `OPENAI_RETRY_BACKOFF_SECONDS`: defaults to `0.8`
- `ALLOW_RULE_BASED_FALLBACK`: defaults to `false` (strict LLM-driven behavior)

### Behavior

- If `OPENAI_API_KEY` is set, routes use OpenAI for:
  - `POST /api/v1/model/generate-question`
  - `POST /api/v1/model/evaluate-answer`
  - `POST /api/v1/model/generate-feedback`
- With `ALLOW_RULE_BASED_FALLBACK=false` (default), backend returns `503` if the model call fails.
- If you explicitly set `ALLOW_RULE_BASED_FALLBACK=true`, backend can fall back to local hybrid/rule logic.

### Health check endpoint

- `GET /api/v1/model/health`

Example response:

```json
{
  "ok": true,
  "openai": {
    "enabled": true,
    "question_model": "o4-mini",
    "evaluation_model": "o4-mini",
    "feedback_model": "o4-mini"
  },
  "env_sources": ["/.env", "/backend/.env"]
}
```

### How to verify OpenAI is actually being used

- `GET /api/v1/model/health` should show `"openai": {"enabled": true, ...}`.
- In strict mode (`ALLOW_RULE_BASED_FALLBACK=false`), model routes should either:
  - return `provider: "openai"`, or
  - return `503` with a provider reason when OpenAI is unavailable/rate-limited.
- In fallback mode (`ALLOW_RULE_BASED_FALLBACK=true`), provider may return `"fallback"`.
