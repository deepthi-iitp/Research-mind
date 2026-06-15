/**
 * ResearchMind — API client
 * All calls go through /api (proxied to FastAPI on port 8000)
 */
import axios from "axios";
import { useStore } from "@/stores/useStore";

const http = axios.create({ baseURL: "/api" });

// Attach user's OpenAI key to every request if set
http.interceptors.request.use(config => {
  const key = useStore.getState().apiKey;
  if (key) config.headers["X-OpenAI-Key"] = key;
  return config;
});

// Helper: append ?api_key=... to SSE URLs (EventSource doesn't support headers)
function sseUrl(path) {
  const key = useStore.getState().apiKey;
  return key ? `${path}${path.includes("?") ? "&" : "?"}api_key=${encodeURIComponent(key)}` : path;
}

// ── Sessions ──────────────────────────────────────────────────────────────────
export const createSession = (mode, query) =>
  http.post("/sessions", { mode, query }).then(r => r.data);

export const getSession = (id) =>
  http.get(`/sessions/${id}`).then(r => r.data);

// ── Diagnostic ────────────────────────────────────────────────────────────────
export const submitDiagnostic = (sessionId, answers, topic) =>
  http.post(`/sessions/${sessionId}/diagnostic`, { session_id: sessionId, answers, topic }).then(r => r.data);

// ── Pipeline SSE stream ───────────────────────────────────────────────────────
export function openPipelineStream(sessionId, onMessage, onDone, onError) {
  const es  = new EventSource(sseUrl(`/api/sessions/${sessionId}/pipeline/stream`));
  es.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.event === "done") { onDone(data); es.close(); }
      else onMessage(data);
    } catch {}
  };
  es.onerror = (e) => { onError(e); es.close(); };
  return es; // caller can call es.close() to abort
}

// ── PDF upload ────────────────────────────────────────────────────────────────
export const uploadPDF = (sessionId, file) => {
  const fd = new FormData();
  fd.append("file", file);
  return http.post(`/sessions/${sessionId}/upload`, fd, {
    headers: { "Content-Type": "multipart/form-data" },
  }).then(r => r.data);
};

// ── Explain section ───────────────────────────────────────────────────────────
export const explainSection = (sessionId, paperId, section, levelOverride = "") =>
  http.post(`/sessions/${sessionId}/explain`, {
    session_id: sessionId, paper_id: paperId, section, level_override: levelOverride,
  }).then(r => r.data);

/**
 * Opens an SSE stream for section explanation.
 * Uses EventSource (same as pipeline stream) — proven to work through Vite proxy.
 * Returns the EventSource so callers can close it.
 */
export function openExplainStream(sessionId, paperId, section, level, { onChunk, onDone, onError }) {
  const params = new URLSearchParams({
    paper_id: paperId || "",
    section,
    level_override: level,
  });
  const es = new EventSource(sseUrl(`/api/sessions/${sessionId}/explain/stream?${params}`));

  es.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.error) { onError(data.error); es.close(); return; }
      if (data.chunk) { onChunk(data.chunk); }
      if (data.done)  { onDone(data);        es.close(); }
    } catch {}
  };

  es.onerror = () => { onError("Connection to server lost"); es.close(); };
  return es;
}

// ── Quick explain (Mode 1) ────────────────────────────────────────────────────
export const quickExplain = (sessionId) =>
  http.post(`/sessions/${sessionId}/quick-explain`).then(r => r.data);

/**
 * Opens an SSE stream for the Mode 1 full-paper explanation.
 * Fires onStatus("discovering"|"explaining") before chunks begin.
 */
export function openQuickExplainStream(sessionId, level, { onStatus, onChunk, onDone, onError }) {
  const params = new URLSearchParams({ level_override: level });
  const es = new EventSource(sseUrl(`/api/sessions/${sessionId}/quick-explain/stream?${params}`));

  es.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.error)  { onError(data.error);   es.close(); return; }
      if (data.status) { onStatus?.(data.status); }
      if (data.chunk)  { onChunk(data.chunk); }
      if (data.done)   { onDone(data);          es.close(); }
    } catch {}
  };

  es.onerror = () => { onError("Connection to server lost"); es.close(); };
  return es;
}

// ── Chat ──────────────────────────────────────────────────────────────────────
export const sendChat = (sessionId, message, chatMode = "standard", context = "") =>
  http.post(`/sessions/${sessionId}/chat`, {
    session_id: sessionId, message, chat_mode: chatMode, context,
  }).then(r => r.data);

// ── Quiz ──────────────────────────────────────────────────────────────────────
export const getQuiz = (sessionId) =>
  http.get(`/sessions/${sessionId}/quiz`).then(r => r.data);

export const submitQuiz = (sessionId, answers) =>
  http.post(`/sessions/${sessionId}/quiz/submit`, {
    session_id: sessionId, answers,
  }).then(r => r.data);

// ── Export ────────────────────────────────────────────────────────────────────
export const downloadExport = (sessionId) => {
  window.open(`/api/sessions/${sessionId}/export`, "_blank");
};

// ── History (JSON cache) ──────────────────────────────────────────────────────
export const getHistory      = ()         => http.get("/history").then(r => r.data);
export const deleteHistory   = (entryId)  => http.delete(`/history/${entryId}`).then(r => r.data);
export const clearHistory    = ()         => http.delete("/history").then(r => r.data);
export const restoreSession  = (sessionId, entryId) =>
  http.post(`/sessions/${sessionId}/restore`, { entry_id: entryId }).then(r => r.data);

// ── Paper database (SQLite) ───────────────────────────────────────────────────
export const getPapers       = (mode) =>
  http.get("/papers", { params: mode ? { mode } : {} }).then(r => r.data.papers);
export const getPaper        = (id) => http.get(`/papers/${id}`).then(r => r.data);
export const deletePaper     = (id) => http.delete(`/papers/${id}`).then(r => r.data);
export const downloadPaperPdf = (id) =>
  window.open(`/api/papers/${id}/export`, "_blank");
