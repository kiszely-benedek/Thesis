/* Calls to the FastAPI server (server.py). Errors carry the server's error code. */

/** A failed call: `code` is the server's error code (or "http_<status>"), `message` its detail. */
export class ApiError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

/** The server sends `{"detail": {"code", "message"}}`; a 422 sends a list instead. */
function errorOf(path, status, body) {
  const detail = body.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail) && detail.code) {
    return new ApiError(detail.code, detail.message ?? detail.code);
  }
  const text = detail ? JSON.stringify(detail) : `${path}: HTTP ${status}`;
  return new ApiError(`http_${status}`, text);
}

/** Fetch JSON from the server; throws `ApiError` on a non-2xx reply. */
export async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw errorOf(path, response.status, body);
  }
  return response.json();
}

/** POST a JSON body. */
export function postJson(path, body) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const enc = encodeURIComponent;

export const getStatus = () => api("/api/status");
export const getResults = () => api("/api/results");
export const getPlant = () => api("/api/plant");
export const switchPlant = (corpusId) => postJson("/api/plant", { corpus_id: corpusId });
export const getIndex = (corpusId) => api(`/api/corpora/${enc(corpusId)}/index`);
export const getQuestions = (corpusId) => api(`/api/corpora/${enc(corpusId)}/questions`);
export const startAsk = (body) => postJson("/api/ask", body);
export const getJob = (jobId) => api(`/api/jobs/${enc(jobId)}`);
