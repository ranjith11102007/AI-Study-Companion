/* ==========================================================================
   StudyMate AI — API layer (no UI concerns).
   Thin, honest wrapper over the FastAPI backend. Every helper maps to a real
   endpoint; there is no mock or fallback data here.

   Conventions:
     - fetchJson attaches `error.status` (HTTP code, 0 for a network failure)
       so callers can detect auth errors and route to sign-in.
   - 204 / empty bodies resolve to null instead of throwing on JSON parse.
   ========================================================================== */

const DEFAULT_BACKEND_ORIGIN = "http://127.0.0.1:8000";

/**
 * When pages are served by FastAPI (/ui/) we call the same origin.
 * When a page is opened directly from disk (file://) we fall back to the
 * local backend origin.
 */
function resolveApiBase() {
  if (window.location.protocol === "file:") {
    return DEFAULT_BACKEND_ORIGIN;
  }
  return "";
}

function token() {
  try { return sessionStorage.getItem("studymate:token"); } catch (e) { return null; }
}

/** Turn a FastAPI error payload into a readable message. */
function errorMessage(payload, path, status) {
  if (payload && typeof payload.detail === "string") return payload.detail;
  if (payload && Array.isArray(payload.detail)) {
    var parts = payload.detail.map(function (item) {
      if (item && item.msg) {
        var loc = Array.isArray(item.loc) ? item.loc.filter(function (p) {
          return p !== "body";
        }).join(".") : "";
        return (loc ? loc + ": " : "") + item.msg;
      }
      return JSON.stringify(item);
    });
    if (parts.length) return parts.join("; ");
  }
  if (payload && payload.detail) return JSON.stringify(payload.detail);
  return "Request to " + path + " failed (HTTP " + status + ").";
}

async function fetchJson(path, options = {}) {
  const token = sessionStorage.getItem("studymate:token");
  const headers = Object.assign({ Accept: "application/json" }, options.headers || {});
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const config = Object.assign({
    headers: headers,
    cache: "no-store",
    method: "GET"
  }, options);
  config.headers = headers;

  let response;
  try {
    response = await fetch(`${resolveApiBase()}${path}`, config);
  } catch (networkError) {
    const err = new Error("Could not reach the backend. Make sure it is running.");
    err.status = 0;
    err.cause = networkError;
    throw err;
  }

  if (!response.ok) {
    let payload = null;
    try { payload = await response.json(); } catch (e) { payload = null; }
    const err = new Error(errorMessage(payload, path, response.status));
    err.status = response.status;
    err.detail = payload ? payload.detail : null;
    throw err;
  }

  if (response.status === 204) return null;
  const text = await response.text();
  if (!text) return null;
  try { return JSON.parse(text); } catch (e) { return null; }
}

/* -------------------------------------------------------------------------- */
/* Health                                                                     */
/* -------------------------------------------------------------------------- */
async function fetchHealth() {
  return fetchJson("/api/health");
}

/* -------------------------------------------------------------------------- */
/* Auth                                                                       */
/* -------------------------------------------------------------------------- */
function verifyEmailRequest() {
  return fetchJson("/api/auth/verify-email/request", { method: "POST" });
}

async function getAuthProviders() {
  return fetchJson("/api/auth/providers");
}

async function signin(data) {
  return fetchJson("/api/auth/signin", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
}

/* -------------------------------------------------------------------------- */
/* Courses                                                                    */
/* -------------------------------------------------------------------------- */
async function getCourses() {
  return fetchJson("/api/courses/");
}

async function createCourse(data) {
  return fetchJson("/api/courses/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
}

async function getCourse(courseId) {
  return fetchJson(`/api/courses/${encodeURIComponent(courseId)}`);
}

async function updateCourse(courseId, data) {
  return fetchJson(`/api/courses/${encodeURIComponent(courseId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
}

async function deleteCourse(courseId) {
  return fetchJson(`/api/courses/${encodeURIComponent(courseId)}`, { method: "DELETE" });
}

/* -------------------------------------------------------------------------- */
/* Materials                                                                  */
/* -------------------------------------------------------------------------- */
async function uploadMaterial(courseId, file) {
  const token = sessionStorage.getItem("studymate:token");
  const form = new FormData();
  form.append("file", file);
  let response;
  const controller =
    typeof AbortController !== "undefined" ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), 120000) : null;
  try {
    response = await fetch(`${resolveApiBase()}/api/courses/${encodeURIComponent(courseId)}/materials`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
      signal: controller ? controller.signal : undefined
    });
  } catch (networkError) {
    const aborted = networkError && networkError.name === "AbortError";
    const err = new Error(
      aborted
        ? "The upload timed out. Check the backend and try again."
        : "Could not reach the backend. Make sure it is running."
    );
    err.status = 0;
    err.cause = networkError;
    throw err;
  } finally {
    if (timer) clearTimeout(timer);
  }
  if (!response.ok) {
    let payload = null;
    try { payload = await response.json(); } catch (e) { payload = null; }
    const err = new Error(errorMessage(payload, "/materials", response.status));
    err.status = response.status;
    throw err;
  }
  return response.json();
}

async function getMaterials(courseId) {
  return fetchJson(`/api/courses/${encodeURIComponent(courseId)}/materials`);
}

async function getMaterial(materialId) {
  return fetchJson(`/api/materials/${encodeURIComponent(materialId)}`);
}

async function deleteMaterial(materialId) {
  return fetchJson(`/api/materials/${encodeURIComponent(materialId)}`, { method: "DELETE" });
}

async function reprocessMaterial(materialId) {
  return fetchJson(`/api/materials/${encodeURIComponent(materialId)}/reprocess`, {
    method: "POST"
  });
}

/**
 * Fetch a material's original file as a Response, carrying the bearer token.
 * Used by the document viewer (an <a href> cannot send an Authorization
 * header, so the viewer fetches the bytes and renders them locally).
 */
async function fetchMaterialFile(materialId) {
  const token = sessionStorage.getItem("studymate:token");
  const response = await fetch(
    `${resolveApiBase()}/api/materials/${encodeURIComponent(materialId)}/file`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {}, cache: "no-store" }
  );
  if (!response.ok) {
    const err = new Error(
      response.status === 404
        ? "That file is no longer available on the server."
        : "Could not load the document (" + response.status + ")."
    );
    err.status = response.status;
    throw err;
  }
  return response;
}

/* -------------------------------------------------------------------------- */
/* Global web search (Mode C, optional)                                       */
/* -------------------------------------------------------------------------- */
async function searchWeb(payload) {
  return fetchJson("/api/search/web", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

async function searchStatus() {
  return fetchJson("/api/search/status");
}

/* -------------------------------------------------------------------------- */
/* Profile + study history                                                    */
/* -------------------------------------------------------------------------- */
async function getProfile() {
  return fetchJson("/api/users/me");
}

async function updateProfile(data) {
  return fetchJson("/api/users/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
}

async function getHistory(params) {
  const opts = params || {};
  const query = [];
  Object.keys(opts).forEach(function (key) {
    const value = opts[key];
    if (value === undefined || value === null || value === "") return;
    query.push(encodeURIComponent(key) + "=" + encodeURIComponent(value));
  });
  return fetchJson("/api/history" + (query.length ? "?" + query.join("&") : ""));
}

/* -------------------------------------------------------------------------- */
/* Flashcards                                                                 */
/* -------------------------------------------------------------------------- */
async function generateFlashcards(courseId) {
  return fetchJson("/api/flashcards/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ course_id: courseId })
  });
}

async function listFlashcards(courseId) {
  return fetchJson("/api/flashcards?course_id=" + encodeURIComponent(courseId));
}

async function reviewFlashcard(cardId, correct) {
  return fetchJson("/api/flashcards/" + encodeURIComponent(cardId), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ correct: correct })
  });
}

async function getCourseSummary(courseId, force) {
  return fetchJson("/api/summaries/" + encodeURIComponent(courseId) + (force ? "?force=true" : ""));
}

/* -------------------------------------------------------------------------- */
/* Tutor                                                                      */
/* -------------------------------------------------------------------------- */
async function askTutor(payload) {
  return fetchJson("/api/tutor/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

/**
 * Stream a tutor answer from POST /api/tutor/ask/stream.
 *
 * The backend emits one SSE line per event, each `data:` carrying JSON:
 *   {"type":"status","stage":"retrieving"}
 *   {"type":"sources","count":N,"citations":[...]}
 *   {"type":"token","text":"..."}                      (repeated)
 *   {"type":"done","conversation_id":..,"message_id":..,
 *    "evidence_status":"grounded|insufficient","citations":[...],
 *    "sources_considered":N}
 *   {"type":"error","status":503,"message":"..."}
 *
 * handlers (all optional):
 *   onStatus(ev), onSources(ev), onToken(ev), onDone(ev), onError(ev)
 *
 * Resolves with the `done` event when the stream completes normally, or with
 * null when it ends via an in-stream `error` event (handlers.onError already
 * ran) or closes early without `done`. Rejects when the HTTP request itself
 * fails before any SSE event (network failure → err.status = 0; HTTP error →
 * err.status = response status). Callers use that to fall back to askTutor.
 * A rejection that happens after events already streamed carries
 * `err.streamStarted = true` so callers do not double-ask.
 */
async function streamTutor(payload, handlers) {
  handlers = handlers || {};
  const token = sessionStorage.getItem("studymate:token");
  const headers = { Accept: "text/event-stream", "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${resolveApiBase()}/api/tutor/ask/stream`, {
      method: "POST",
      headers: headers,
      cache: "no-store",
      body: JSON.stringify(payload)
    });
  } catch (networkError) {
    const err = new Error("Could not reach the backend. Make sure it is running.");
    err.status = 0;
    err.cause = networkError;
    throw err;
  }

  if (!response.ok) {
    let body = null;
    try { body = await response.json(); } catch (e) { body = null; }
    const err = new Error(errorMessage(body, "/api/tutor/ask/stream", response.status));
    err.status = response.status;
    err.detail = body ? body.detail : null;
    throw err;
  }

  if (!response.body || typeof response.body.getReader !== "function") {
    const err = new Error("This browser does not support streaming responses.");
    err.status = 0;
    throw err;
  }

  return new Promise(function (resolve, reject) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let dispatchedAny = false;
    let finished = false;
    let doneEvent = null;

    function call(name, ev) {
      if (typeof handlers[name] === "function") handlers[name](ev);
    }

    /* Dispatch a single SSE `data:` payload. Malformed lines are skipped. */
    function dispatch(data) {
      let ev;
      try { ev = JSON.parse(data); } catch (e) { return; }
      if (!ev || !ev.type) return;
      if (ev.type === "status") call("onStatus", ev);
      else if (ev.type === "sources") call("onSources", ev);
      else if (ev.type === "token") { if (ev.text != null) call("onToken", ev); }
      else if (ev.type === "done") {
        doneEvent = ev;
        finished = true;
        call("onDone", ev);
        resolve(doneEvent);
      } else if (ev.type === "error") {
        finished = true;
        call("onError", ev);
        resolve(null);
      }
    }

    /* Consume complete lines; tolerate both \n and \r\n, ignore comments. */
    function drain(b) {
      let idx;
      while ((idx = b.indexOf("\n")) >= 0) {
        let line = b.slice(0, idx);
        b = b.slice(idx + 1);
        if (line.charAt(line.length - 1) === "\r") line = line.slice(0, -1);
        if (!line.trim() || line.charAt(0) === ":") continue;
        const colon = line.indexOf(":");
        if (colon < 0) continue;
        if (line.slice(0, colon).trim() !== "data") continue;
        let value = line.slice(colon + 1);
        if (value.charAt(0) === " ") value = value.slice(1);
        if (!value.trim()) continue;
        dispatchedAny = true;
        dispatch(value);
        if (finished) return "";
      }
      return b;
    }

    function fail(err) {
      if (dispatchedAny) err.streamStarted = true;
      reject(err);
    }

    function stopStream() {
      if (typeof reader.cancel === "function") {
        try { reader.cancel(); } catch (e) { /* ignore */ }
      }
    }

    function pump() {
      reader.read().then(function (chunk) {
        if (finished) { stopStream(); return; }
        if (chunk.done) {
          buffer = drain(buffer + decoder.decode());
          if (finished) { stopStream(); return; }
          resolve(doneEvent);
          return;
        }
        buffer = drain(buffer + decoder.decode(chunk.value, { stream: true }));
        if (finished) { stopStream(); return; }
        pump();
      }).catch(fail);
    }

    pump();
  });
}

async function listConversations(courseId) {
  return fetchJson(`/api/tutor/conversations?course_id=${encodeURIComponent(courseId)}`);
}

async function getConversation(conversationId) {
  return fetchJson(`/api/tutor/conversations/${encodeURIComponent(conversationId)}`);
}

async function deleteConversation(conversationId) {
  return fetchJson(`/api/tutor/conversations/${encodeURIComponent(conversationId)}`, {
    method: "DELETE"
  });
}

/* -------------------------------------------------------------------------- */
/* Citations                                                                  */
/* -------------------------------------------------------------------------- */
async function resolveCitation(contentUnitId) {
  return fetchJson(`/api/citations/${encodeURIComponent(contentUnitId)}`);
}

/* -------------------------------------------------------------------------- */
/* Assessments & attempts                                                     */
/* -------------------------------------------------------------------------- */
async function createAssessment(data) {
  return fetchJson("/api/assessments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
}

async function listAssessments(courseId) {
  return fetchJson(`/api/assessments?course_id=${encodeURIComponent(courseId)}`);
}

async function getAssessment(assessmentId) {
  return fetchJson(`/api/assessments/${encodeURIComponent(assessmentId)}`);
}

async function deleteAssessment(assessmentId) {
  return fetchJson(`/api/assessments/${encodeURIComponent(assessmentId)}`, { method: "DELETE" });
}

async function startAttempt(assessmentId) {
  return fetchJson(`/api/assessments/${encodeURIComponent(assessmentId)}/attempts`, {
    method: "POST"
  });
}

async function submitAttempt(attemptId, answers) {
  return fetchJson(`/api/attempts/${encodeURIComponent(attemptId)}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers: answers })
  });
}

async function getAttempt(attemptId) {
  return fetchJson(`/api/attempts/${encodeURIComponent(attemptId)}`);
}

/* -------------------------------------------------------------------------- */
/* Learner: mastery & recommendations                                         */
/* -------------------------------------------------------------------------- */
async function getMastery(courseId) {
  return fetchJson(`/api/courses/${encodeURIComponent(courseId)}/mastery`);
}

async function getRecommendations(courseId, refresh) {
  const suffix = refresh ? "?refresh=true" : "";
  return fetchJson(`/api/courses/${encodeURIComponent(courseId)}/recommendations${suffix}`);
}

/* -------------------------------------------------------------------------- */
/* Topics                                                                     */
/* -------------------------------------------------------------------------- */
async function listTopics(courseId) {
  return fetchJson(`/api/courses/${encodeURIComponent(courseId)}/topics`);
}

async function suggestTopics(courseId) {
  return fetchJson(`/api/courses/${encodeURIComponent(courseId)}/topics/suggestions`);
}

async function createTopic(courseId, data) {
  return fetchJson(`/api/courses/${encodeURIComponent(courseId)}/topics`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
}

async function deleteTopic(courseId, topicId) {
  return fetchJson(
    `/api/courses/${encodeURIComponent(courseId)}/topics/${encodeURIComponent(topicId)}`,
    { method: "DELETE" }
  );
}

async function setPrerequisite(courseId, topicId, prerequisiteId) {
  return fetchJson(
    `/api/courses/${encodeURIComponent(courseId)}/topics/${encodeURIComponent(topicId)}/prerequisite`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prerequisite_id: prerequisiteId })
    }
  );
}

async function attachTopicSource(courseId, topicId, contentUnitId) {
  return fetchJson(
    `/api/courses/${encodeURIComponent(courseId)}/topics/${encodeURIComponent(topicId)}/sources`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content_unit_id: contentUnitId })
    }
  );
}

/* -------------------------------------------------------------------------- */
/* Providers                                                                  */
/* -------------------------------------------------------------------------- */
async function getProviders() {
  return fetchJson("/api/providers/status");
}

window.StudyAPI = {
  base: resolveApiBase,
  fetchJson: fetchJson,
  fetchHealth: fetchHealth,
  signup: signup,
  signin: signin,
  getCourses: getCourses,
  createCourse: createCourse,
  getCourse: getCourse,
  updateCourse: updateCourse,
  deleteCourse: deleteCourse,
  uploadMaterial: uploadMaterial,
  getMaterials: getMaterials,
  getMaterial: getMaterial,
  deleteMaterial: deleteMaterial,
  reprocessMaterial: reprocessMaterial,
  fetchMaterialFile: fetchMaterialFile,
  searchWeb: searchWeb,
  searchStatus: searchStatus,
  getProfile: getProfile,
  updateProfile: updateProfile,
  getHistory: getHistory,
  verifyEmailRequest: verifyEmailRequest,
  getAuthProviders: getAuthProviders,
  generateFlashcards: generateFlashcards,
  listFlashcards: listFlashcards,
  reviewFlashcard: reviewFlashcard,
  getCourseSummary: getCourseSummary,
  askTutor: askTutor,
  streamTutor: streamTutor,
  listConversations: listConversations,
  getConversation: getConversation,
  deleteConversation: deleteConversation,
  resolveCitation: resolveCitation,
  createAssessment: createAssessment,
  listAssessments: listAssessments,
  getAssessment: getAssessment,
  deleteAssessment: deleteAssessment,
  startAttempt: startAttempt,
  submitAttempt: submitAttempt,
  getAttempt: getAttempt,
  getMastery: getMastery,
  getRecommendations: getRecommendations,
  listTopics: listTopics,
  suggestTopics: suggestTopics,
  createTopic: createTopic,
  deleteTopic: deleteTopic,
  setPrerequisite: setPrerequisite,
  attachTopicSource: attachTopicSource,
  getProviders: getProviders
};
