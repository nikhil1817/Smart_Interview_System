export const API_BASE = "http://localhost:8000/api";

function extractErrorMessage(data, status) {
  // FastAPI detail can be a string or a structured object
  const detail = data?.detail;
  if (detail) {
    if (typeof detail === "string") return detail;
    if (typeof detail === "object") {
      return detail.message || detail.code || JSON.stringify(detail);
    }
  }
  if (data?.message) return data.message;
  if (status === 503) return "AI model is temporarily unavailable. Please try again in a moment.";
  if (status === 429) return "Too many requests — please wait a few seconds and try again.";
  return `Request failed (${status})`;
}

async function parseJsonResponse(res) {
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const message = extractErrorMessage(data, res.status);
    const err = new Error(message);
    err.status = res.status;
    err.code = data?.detail?.code || null;
    err.providerReason = data?.detail?.provider_reason || null;
    throw err;
  }

  return data;
}

async function fetchWithTimeout(url, options, timeoutMs = 20000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (err) {
    if (err?.name === "AbortError") {
      const timeoutError = new Error("Request timed out");
      timeoutError.status = 408;
      throw timeoutError;
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function fetchWithRetry(url, options, maxRetries = 2, delayMs = 1200, timeoutMs = 20000) {
  let lastError;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = timeoutMs > 0
        ? await fetchWithTimeout(url, options, timeoutMs)
        : await fetch(url, options);
      if (res.status === 429 && attempt < maxRetries) {
        await new Promise((resolve) => setTimeout(resolve, delayMs * (attempt + 1)));
        continue;
      }
      if (res.status === 503 && attempt < maxRetries) {
        const data = await res.clone().json().catch(() => ({}));
        const reason = data?.detail?.provider_reason || "";
        if (reason === "github_models_rate_limited") {
          await new Promise((resolve) => setTimeout(resolve, delayMs * (attempt + 1)));
          continue;
        }
      }
      return parseJsonResponse(res);
    } catch (err) {
      lastError = err;
      if (err.status === 429 || (err.status === 503 && err.providerReason === "github_models_rate_limited")) {
        if (attempt < maxRetries) {
          await new Promise((resolve) => setTimeout(resolve, delayMs * (attempt + 1)));
          continue;
        }
      }
      throw err;
    }
  }
  throw lastError;
}

export async function startInterview(role, mode, options = {}) {
  const res = await fetch(`${API_BASE}/start-interview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, mode, ...options })
  });
  return parseJsonResponse(res);
}

export async function sendAnswer(sessionId, answer) {
  const res = await fetch(`${API_BASE}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, answer })
  });
  return parseJsonResponse(res);
}

export async function parseResumeFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/parse-resume`, {
    method: "POST",
    body: formData
  });

  const data = await parseJsonResponse(res);
  return data.data;
}

export async function generateModelQuestion(payload) {
  return fetchWithRetry(`${API_BASE}/v1/model/generate-question`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function evaluateModelAnswer(payload) {
  return fetchWithRetry(`${API_BASE}/v1/model/evaluate-answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function generateModelFeedback(payload) {
  return fetchWithRetry(`${API_BASE}/v1/model/generate-feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}
