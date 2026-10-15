/* ==========================================================================
   StudyMate AI — Global search page (Mode C).

   Talks to POST /api/search/web. Nothing is fabricated: every source shows the
   provider's real title, URL, domain and retrieval time, and each row is
   labelled as a search-result snippet (not a verified page). If the local
   model is unavailable the page still lists the retrieved results.
   ========================================================================== */
(function (global) {
  "use strict";

  var App = global.StudyApp;
  var els = {};
  var busy = false;

  function esc(value) { return App.escapeHtml(value); }

  function setStatus(kind, text) {
    if (!els.status) return;
    els.status.className = "ai-pill " + (kind || "idle");
    var label = els.status.querySelector("[data-status-text]");
    if (label) label.textContent = text;
  }

  function showEmpty(show) {
    if (els.empty) els.empty.hidden = !show;
    if (els.wrap) els.wrap.hidden = show;
  }

  function notice(kind, html) {
    if (!els.notice) return;
    if (!html) { els.notice.hidden = true; els.notice.innerHTML = ""; return; }
    els.notice.hidden = false;
    els.notice.innerHTML =
      '<div class="banner ' + kind + '">' + App.icon("alert") + "<div>" + html + "</div></div>";
    global.StudyIcons.hydrate(els.notice);
  }

  function sourceRow(item) {
    var label = item.source === "page" ? "full page retrieved" : "search-result snippet";
    var badgeClass = item.source === "page" ? "badge badge-mastery" : "badge";
    var retrieved = item.retrieved_at ? App.timeLabel(item.retrieved_at) : "";
    return '<div class="list-item">' +
      '<span class="item-icon primary" data-icon="compass"></span>' +
      '<span class="item-main">' +
        '<a class="item-title" href="' + esc(item.url) + '" target="_blank" rel="noopener noreferrer">' +
          esc(item.title || item.url) + "</a>" +
        '<span class="item-sub">' + esc(item.domain || "") +
          (retrieved ? " · retrieved " + esc(retrieved) : "") + "</span>" +
        (item.snippet ? '<span class="t-sm muted">' + esc(item.snippet) + "</span>" : "") +
        '<span class="' + badgeClass + '" style="margin-top:6px">' + label + "</span>" +
      "</span>" +
      '<span class="item-end">' +
        '<a class="btn btn-quiet btn-sm" href="' + esc(item.url) +
          '" target="_blank" rel="noopener noreferrer">Open ' + App.icon("external") + "</a>" +
      "</span>" +
    "</div>";
  }

  function render(data) {
    showEmpty(false);
    if (els.answer) {
      els.answer.innerHTML = data.answer
        ? App.paragraphs(data.answer)
        : '<p class="muted">No summary was generated.</p>';
    }
    var results = data.results || [];
    if (els.sourceCount) {
      els.sourceCount.textContent = results.length + " result" + (results.length === 1 ? "" : "s");
    }
    if (els.results) {
      els.results.innerHTML = results.length
        ? results.map(sourceRow).join("")
        : '<div class="list-item"><span class="item-main">' +
          '<span class="item-title">No results</span>' +
          '<span class="item-sub">Try rephrasing the query.</span></span></div>';
      global.StudyIcons.hydrate(els.results);
    }

    if (data.evidence_status === "grounded") {
      setStatus("ok", "Grounded · " + results.length + " source(s)");
      notice("banner-info", data.notice ? esc(data.notice) : "");
    } else if (data.evidence_status === "unavailable") {
      setStatus("idle", "Model unavailable");
      notice("banner-warn",
        "<strong>Local model unavailable.</strong> " + esc(data.notice || ""));
    } else {
      setStatus("idle", "No answer");
      notice("banner-warn", "<strong>Not enough evidence.</strong> " +
        esc(data.notice || "The snippets did not support an answer."));
    }
  }

  function run(query) {
    if (busy || !query || !query.trim()) return;
    busy = true;
    if (els.submit) els.submit.disabled = true;
    showEmpty(true);
    if (els.empty) {
      els.empty.querySelector(".state-title").textContent = "Searching…";
      els.empty.querySelector(".state-text").textContent =
        "Retrieving web results and grounding an answer with the local model.";
    }
    setStatus("busy", "Searching…");
    global.StudyAPI.searchWeb({ query: query.trim() })
      .then(function (data) { render(data); })
      .catch(function (err) {
        if (App.isAuthError(err)) return;
        showEmpty(true);
        if (els.empty) {
          els.empty.querySelector(".state-title").textContent = "Search failed";
          els.empty.querySelector(".state-text").textContent =
            (err && err.message) || "The search could not be completed.";
        }
        setStatus("idle", "Error");
        App.handleError(err, "The web search could not be completed.");
      })
      .then(function () {
        busy = false;
        if (els.submit) els.submit.disabled = false;
      });
  }

  function checkStatus() {
    global.StudyAPI.searchStatus().then(function (status) {
      if (!status || !status.configured) {
        if (els.config) els.config.hidden = false;
        if (els.configText) {
          els.configText.innerHTML =
            "<strong>Global web search is not configured.</strong> An operator must set " +
            "<code>SEARCH_PROVIDER=brave</code> and <code>BRAVE_SEARCH_API_KEY</code> on the server.";
        }
        if (els.submit) els.submit.disabled = true;
      } else if (els.config) {
        els.config.hidden = true;
      }
    }).catch(function (err) {
      if (App.isAuthError(err)) return;
    });
  }

  function init() {
    els.form = document.getElementById("search-form");
    els.input = document.querySelector("#search-form input");
    els.submit = document.querySelector("#search-form button[type=submit]");
    els.config = document.getElementById("search-config");
    els.configText = document.getElementById("search-config-text");
    els.empty = document.getElementById("search-empty");
    els.results = document.getElementById("search-results");
    els.answer = document.getElementById("search-answer");
    els.notice = document.getElementById("search-notice");
    els.status = document.getElementById("search-status");
    els.sourceCount = document.getElementById("search-source-count");
    els.wrap = els.results ? els.results.closest(".stack.stack-lg") : null;

    if (els.form) {
      els.form.addEventListener("submit", function (e) {
        e.preventDefault();
        var text = els.input ? els.input.value : "";
        if (text) run(text);
      });
    }

    var q = App.queryParam("q");
    if (q && els.input) { els.input.value = q; run(q); }

    checkStatus();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
