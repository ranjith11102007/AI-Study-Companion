/* ==========================================================================
   StudyMate AI — Document viewer (split-screen study workspace).

   Renders the *original uploaded file* next to the tutor using the vendored
   PDF.js build. The file is fetched with the bearer token (an <a href> cannot
   send one) and rendered locally; the server never exposes a filesystem path.
   Citations from the tutor can jump straight to the cited page.

   Exposed as window.StudyDocViewer. Emits "docviewer:ready" once mounted.
   ========================================================================== */
import * as pdfjsLib from "../vendor/pdfjs/pdf.min.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  "../vendor/pdfjs/pdf.worker.min.mjs",
  import.meta.url
).href;

var els = {};
var state = {
  courseId: null,
  materials: [],
  loadingToken: 0,
  pdf: null,
  page: 1,
  pages: 0,
  zoom: 1,
  material: null,
  renderTask: null,
  objectUrl: null
};

function updateControls() {
  var hasPages = state.pages > 0;
  if (els.pageLabel) {
    els.pageLabel.textContent = hasPages
      ? "Page " + state.page + " of " + state.pages
      : "—";
  }
  if (els.prev) els.prev.disabled = !hasPages || state.page <= 1;
  if (els.next) els.next.disabled = !hasPages || state.page >= state.pages;
  if (els.zoomLabel) els.zoomLabel.textContent = Math.round(state.zoom * 100) + "%";
}

function buildPageSelect() {
  if (!els.pageSelect) return;
  var options = ['<option value="">Page</option>'];
  for (var i = 1; i <= state.pages; i += 1) {
    options.push('<option value="' + i + '">' + i + "</option>");
  }
  els.pageSelect.innerHTML = options.join("");
  els.pageSelect.value = String(state.page);
}

function populateMaterials(list) {
  if (!els.materialSelect) return;
  var options = ['<option value="">Select a document…</option>'];
  (list || []).forEach(function (m) {
    var label = m.original_filename || m.filename || ("Material #" + m.id);
    if (m.processing_status && m.processing_status !== "ready") {
      label += " (" + m.processing_status + ")";
    }
    options.push('<option value="' + m.id + '">' + escapeHtml(label) + "</option>");
  });
  els.materialSelect.innerHTML = options.join("");
}

function escapeHtml(value) {
  if (window.StudyApp && window.StudyApp.escapeHtml) return window.StudyApp.escapeHtml(value);
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setError(message) {
  if (!els.error) return;
  if (!message) { els.error.hidden = true; els.error.textContent = ""; return; }
  els.error.hidden = false;
  els.error.textContent = message;
}

function showState(which) {
  if (els.state) els.state.hidden = which !== "empty";
  if (els.canvas) els.canvas.hidden = which !== "canvas";
  if (els.text) els.text.hidden = which !== "text";
  if (els.image) els.image.hidden = which !== "image";
}

function setState(title, text) {
  if (els.stateTitle) els.stateTitle.textContent = title;
  if (els.stateText) els.stateText.textContent = text;
}

/* ---------------------------------------------------------------------- */
/* Rendering                                                              */
/* ---------------------------------------------------------------------- */
async function renderPdfPage() {
  if (!state.pdf || !els.canvas) return;
  const page = await state.pdf.getPage(state.page);
  const viewport = page.getViewport({ scale: state.zoom * 1.25 });
  const canvas = els.canvas;
  const ctx = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;

  canvas.width = Math.floor(viewport.width * ratio);
  canvas.height = Math.floor(viewport.height * ratio);
  canvas.style.width = Math.floor(viewport.width) + "px";
  canvas.style.height = Math.floor(viewport.height) + "px";

  if (state.renderTask) {
    try { state.renderTask.cancel(); } catch (e) { /* already finished */ }
    state.renderTask = null;
  }
  const transform = ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : null;
  const task = page.render({ canvasContext: ctx, viewport: viewport, transform: transform });
  state.renderTask = task;
  try {
    await task.promise;
  } catch (err) {
    if (err && err.name === "RenderingCancelledException") return;
    throw err;
  }
  updatePageLabel();
}

function updatePageLabel() {
  if (els.pageLabel) {
    els.pageLabel.textContent = state.pages
      ? "Page " + state.page + " of " + state.pages
      : "—";
  }
  if (els.prev) els.prev.disabled = state.page <= 1;
  if (els.next) els.next.disabled = state.page >= state.pages;
  if (els.pageSelect && state.pages) els.pageSelect.value = String(state.page);
  if (els.zoomLabel) els.zoomLabel.textContent = Math.round(state.zoom * 100) + "%";
}

/* ---------------------------------------------------------------------- */
/* Opening documents                                                      */
/* ---------------------------------------------------------------------- */
function materialById(id) {
  return state.materials.filter(function (m) { return String(m.id) === String(id); })[0] || null;
}

async function open(material, page) {
  const ticket = ++state.loadingToken;
  setError(null);
  state.material = material;
  state.page = page && page > 0 ? page : 1;
  state.zoom = 1;
  state.pdf = null;
  state.pages = 0;
  if (els.pageSelect) els.pageSelect.innerHTML = '<option value="">Page</option>';

  const type = (material.material_type || "").toLowerCase();
  const name = material.original_filename || material.filename || "";
  const extension = name.split(".").pop().toLowerCase();
  if (els.sub) els.sub.textContent = name + " · " + (material.processing_status || "ready");

  let response;
  try {
    response = await window.StudyAPI.fetchMaterialFile(material.id);
  } catch (err) {
    if (ticket !== state.loadingToken) return;
    setError(err && err.message ? err.message : "Could not load the document.");
    showState("empty");
    setState("Could not load", "The stored file could not be retrieved from the server.");
    updateControls();
    return;
  }
  if (ticket !== state.loadingToken) return;

  try {
    if (type === "pdf" || extension === "pdf") {
      const data = await response.arrayBuffer();
      if (ticket !== state.loadingToken) return;
      const pdf = await pdfjsLib.getDocument({ data: data }).promise;
      if (ticket !== state.loadingToken) return;
      state.pdf = pdf;
      state.pages = pdf.numPages;
      state.page = Math.min(Math.max(1, state.page), state.pages);
      buildPageSelect();
      showState("canvas");
      await renderPdfPage();
    } else if (type === "image" || ["png", "jpg", "jpeg", "webp"].includes(extension)) {
      const blob = await response.blob();
      if (ticket !== state.loadingToken) return;
      if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);
      state.objectUrl = URL.createObjectURL(blob);
      if (els.image) { els.image.src = state.objectUrl; els.image.alt = name; }
      showState("image");
    } else if (type === "text" || ["txt", "md"].includes(extension)) {
      const text = await response.text();
      if (ticket !== state.loadingToken) return;
      if (els.text) els.text.textContent = text;
      showState("text");
    } else {
      showState("empty");
      setState(
        "Preview not supported",
        "This file type can't be previewed here. It is still indexed, so the tutor can cite it."
      );
    }
  } catch (err) {
    if (ticket !== state.loadingToken) return;
    setError("This document could not be displayed (" + (err && err.message ? err.message : "unknown error") + ").");
    showState("empty");
    setState("Could not display", "The file downloaded but could not be rendered.");
  }
  updateControls();
}

async function openMaterialId(id, page) {
  let material = materialById(id);
  if (!material) {
    material = {
      id: Number(id),
      original_filename: "Document #" + id,
      material_type: "",
      processing_status: "ready"
    };
  }
  if (els.materialSelect) els.materialSelect.value = String(id);
  await open(material, page);
}

async function openCitation(citation) {
  if (!citation || citation.material_id == null) return;
  await openMaterialId(citation.material_id, citation.page_number);
}

/* ---------------------------------------------------------------------- */
/* Course + controls                                                      */
/* ---------------------------------------------------------------------- */
async function setCourse(courseId) {
  state.courseId = courseId || null;
  state.pdf = null;
  state.pages = 0;
  state.materials = [];
  state.loadingToken += 1;
  showState("empty");
  setState("No document open", "Pick a document above, or click a citation in the tutor to jump straight to its page.");
  setError(null);
  if (els.sub) els.sub.textContent = "Select a material to read it here.";
  updateControls();
  if (!courseId) { populateMaterials([]); return; }
  try {
    const list = await window.StudyAPI.getMaterials(courseId);
    state.materials = (list || []).filter(function (m) {
      return m.processing_status === "ready";
    });
    populateMaterials(state.materials);
    if (state.materials.length) {
      const first = state.materials[0];
      if (els.materialSelect) els.materialSelect.value = String(first.id);
      await open(first, 1);
    }
  } catch (err) {
    state.materials = [];
    populateMaterials([]);
    if (window.StudyApp && window.StudyApp.isAuthError && window.StudyApp.isAuthError(err)) return;
  }
}

function gotoPage(page) {
  if (!state.pdf) return;
  const next = Math.min(Math.max(1, page), state.pages);
  if (next === state.page) return;
  state.page = next;
  renderPdfPage().catch(function () { /* surfaced per-render */ });
}

function zoomBy(delta) {
  state.zoom = Math.min(3, Math.max(0.5, state.zoom + delta));
  if (state.pdf) renderPdfPage().catch(function () {});
  else if (els.zoomLabel) els.zoomLabel.textContent = Math.round(state.zoom * 100) + "%";
}

/* ---------------------------------------------------------------------- */
/* Init                                                                   */
/* ---------------------------------------------------------------------- */
function init() {
  els.materialSelect = document.getElementById("doc-material-select");
  els.pageSelect = document.getElementById("doc-page-select");
  els.viewer = document.getElementById("doc-viewer");
  els.state = document.getElementById("doc-state");
  els.stateTitle = document.getElementById("doc-state-title");
  els.stateText = document.getElementById("doc-state-text");
  els.canvas = document.getElementById("doc-canvas");
  els.text = document.getElementById("doc-text");
  els.image = document.getElementById("doc-image");
  els.error = document.getElementById("doc-error");
  els.sub = document.getElementById("doc-sub");
  els.pageLabel = document.getElementById("doc-page-label");
  els.zoomLabel = document.getElementById("doc-zoom-label");
  els.prev = document.getElementById("doc-prev");
  els.next = document.getElementById("doc-next");

  if (!els.viewer) return; // not on this page

  if (els.materialSelect) {
    els.materialSelect.addEventListener("change", function () {
      if (els.materialSelect.value) openMaterialId(els.materialSelect.value, 1);
    });
  }
  if (els.pageSelect) {
    els.pageSelect.addEventListener("change", function () {
      if (els.pageSelect.value) gotoPage(Number(els.pageSelect.value));
    });
  }
  if (els.prev) els.prev.addEventListener("click", function () { gotoPage(state.page - 1); });
  if (els.next) els.next.addEventListener("click", function () { gotoPage(state.page + 1); });
  var zoomIn = document.getElementById("doc-zoom-in");
  var zoomOut = document.getElementById("doc-zoom-out");
  if (zoomIn) zoomIn.addEventListener("click", function () { zoomBy(0.25); });
  if (zoomOut) zoomOut.addEventListener("click", function () { zoomBy(-0.25); });

  updateControls();

  window.StudyDocViewer = {
    setCourse: setCourse,
    openMaterial: openMaterialId,
    openCitation: openCitation,
    gotoPage: gotoPage,
    zoomIn: function () { zoomBy(0.25); },
    zoomOut: function () { zoomBy(-0.25); },
    isReady: function () { return true; }
  };
  window.dispatchEvent(new CustomEvent("docviewer:ready"));
}

// Module scripts run after the document is parsed, so the DOM is ready.
init();
