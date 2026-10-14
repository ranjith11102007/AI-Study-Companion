/* ==========================================================================
   StudyMate AI — Real backend health integration (GET /api/health).
   No hard-coded "Connected": every label is rendered from the live payload.

   Updates:
     - [data-health-pill] header/status pills (short label + dot)
     - legacy landing card ids (api-dot, api-label, health-meta, meta-*, …)
     - [data-health-field="…"] values anywhere on the page
   Emits window event "studymate:health" with { payload | error }.
   ========================================================================== */
(function (global) {
  "use strict";

  var POLL_MS = 30000;
  var timer = null;
  var last = { payload: null, error: null, at: null };
  var started = false;

  function apiUp(p) { return p.status === "ok" || p.status === "degraded"; }
  function dbUp(p) { return !!(p.database && p.database.status === "connected"); }

  function dotClass(p, checking) {
    if (checking) return "status-dot lg idle dot dot-unknown";
    if (!p || !apiUp(p)) return "status-dot lg err dot dot-err";
    return dbUp(p) ? "status-dot lg ok dot dot-ok" : "status-dot lg warn dot dot-warn";
  }

  function shortLabel(p) {
    if (!p || !apiUp(p)) return "Backend offline";
    return dbUp(p) ? "API online · DB up" : "API online · DB down";
  }

  function longLabel(p) {
    if (!apiUp(p)) return "Backend degraded";
    return dbUp(p)
      ? "Backend online, database connected"
      : "Backend online, database unreachable";
  }

  function setText(selector, text, root) {
    var el = (root || document).querySelector(selector);
    if (el) el.textContent = text;
  }

  function renderPills(p, checking) {
    document.querySelectorAll("[data-health-pill]").forEach(function (pill) {
      var dot = pill.querySelector("[data-health-dot]");
      var label = pill.querySelector("[data-health-label]");
      if (dot) dot.className = dotClass(p, checking);
      if (label) label.textContent = checking ? "Checking backend…" : shortLabel(p);
      pill.setAttribute(
        "title",
        checking ? "Checking backend…" : "Backend: " + p.status + " · database: " + (p.database && p.database.status)
      );
    });
  }

  /* Landing status card (legacy ids preserved from home.js). */
  function renderCard(p) {
    var dot = document.getElementById("api-dot");
    var label = document.getElementById("api-label");
    var meta = document.getElementById("health-meta");
    if (!dot || !label || !meta) return;

    dot.className = dotClass(p, false);
    label.textContent = longLabel(p);
    meta.hidden = false;

    var err = document.getElementById("health-error");
    if (err) err.hidden = true;

    setText("#meta-service", p.service);
    setText("#meta-version", p.version);
    setText("#meta-environment", p.environment);
    setText("#meta-database", p.database ? p.database.status : "unknown");
    setText(
      "#meta-latency",
      p.database && p.database.latency_ms != null ? p.database.latency_ms + " ms" : "n/a"
    );
    setText("#meta-timestamp", p.timestamp);
  }

  function renderCardError(message) {
    var dot = document.getElementById("api-dot");
    var label = document.getElementById("api-label");
    var meta = document.getElementById("health-meta");
    var err = document.getElementById("health-error");
    if (dot) dot.className = dotClass(null, false);
    if (label) label.textContent = "Backend not reachable";
    if (meta) meta.hidden = true;
    if (err) {
      err.hidden = false;
      err.textContent = message;
    }
  }

  function renderFields(p) {
    if (!p) return;
    var map = {
      status: p.status,
      service: p.service,
      version: p.version,
      environment: p.environment,
      database: p.database ? p.database.status : "unknown",
      latency: p.database && p.database.latency_ms != null ? p.database.latency_ms + " ms" : "n/a",
      timestamp: p.timestamp
    };
    document.querySelectorAll("[data-health-field]").forEach(function (el) {
      var key = el.getAttribute("data-health-field");
      if (map[key] != null) el.textContent = map[key];
    });
  }

  function emit(detail) {
    try {
      window.dispatchEvent(new CustomEvent("studymate:health", { detail: detail }));
    } catch (e) { /* older browsers */ }
  }

  function paint() {
    if (last.error) {
      renderPills(null, false);
      document.querySelectorAll("[data-health-pill] .health-text").forEach(function (el) {
        el.textContent = "Backend offline";
      });
      document.querySelectorAll("[data-health-pill] [data-health-dot]").forEach(function (d) {
        d.className = "status-dot lg err dot dot-err";
      });
      renderCardError(last.error);
      return;
    }
    if (!last.payload) return;
    renderPills(last.payload, false);
    renderCard(last.payload);
    renderFields(last.payload);
  }

  async function refresh() {
    renderPills(null, true);
    var checkingLabel = document.getElementById("api-label");
    var checkingDot = document.getElementById("api-dot");
    if (checkingLabel) checkingLabel.textContent = "Checking backend…";
    if (checkingDot) checkingDot.className = dotClass(null, true);

    try {
      var payload = await global.StudyAPI.fetchHealth();
      last = { payload: payload, error: null, at: Date.now() };
    } catch (error) {
      last = {
        payload: null,
        error: error.message + ". Start the backend and refresh.",
        at: Date.now()
      };
    }
    paint();
    emit(last);
    return last;
  }

  function init() {
    if (started) return;
    started = true;

    var refreshBtn = document.getElementById("refresh-btn");
    if (refreshBtn) refreshBtn.addEventListener("click", refresh);

    document.querySelectorAll("[data-health-refresh]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        btn.classList.add("spin");
        refresh().then(function () { btn.classList.remove("spin"); });
        StudyUI.toast("Re-checking backend…", "info");
      });
    });

    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && (!last.at || Date.now() - last.at > POLL_MS)) refresh();
    });

    refresh();
    timer = setInterval(function () {
      if (!document.hidden) refresh();
    }, POLL_MS);
  }

  global.StudyHealth = {
    init: init,
    refresh: refresh,
    get: function () { return last; }
  };
})(window);
