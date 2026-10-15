/* ==========================================================================
   StudyMate AI — Study History page.

   Reads GET /api/history (real rows only). Every row deep-links to the actual
   object; nothing is synthesised or inflated.
   ========================================================================== */
(function (global) {
  "use strict";

  var App = global.StudyApp;
  var els = {};
  var page = 0;
  var limit = 20;
  var total = 0;
  var currentKind = "";

  var KIND_LABEL = {
    tutor: "Tutor",
    assessment: "Quiz",
    upload: "Upload",
    mastery: "Mastery"
  };
  var KIND_ICON = {
    tutor: "chat",
    assessment: "quiz",
    upload: "book",
    mastery: "chart"
  };

  function esc(value) { return App.escapeHtml(value); }

  function setEmpty(show, loading) {
    if (els.empty) els.empty.hidden = !show;
    if (els.list) els.list.hidden = show;
    if (show && loading && els.list) {
      els.list.hidden = false;
      els.empty.hidden = true;
      els.list.innerHTML =
        '<div class="state tinted"><span class="state-title">Loading…</span>' +
        '<span class="state-text">Gathering your real activity.</span></div>';
    }
  }

  function Row(e) {
    var d = e.at ? App.timeLabel(e.at) : "—";
    var icon = KIND_ICON[e.kind] || "chat";
    var badgeClass = e.kind === "mastery" ? "badge badge-primary"
      : e.kind === "assessment" ? "badge badge-amber"
      : e.kind === "upload" ? "badge badge-outline"
      : "badge badge-neutral";
    var detail = e.detail || "";
    var link = e.href ? "href=\"" + esc(e.href) + "\"" : "href=\"#\"";
    return '<div class="list-item">' +
      '<span class="item-icon primary" data-icon="' + icon + '"></span>' +
      '<span class="item-main">' +
        '<a class="item-title" ' + link + '>' + esc(e.title || "Untitled") + "</a>" +
        (detail ? '<span class="item-sub">' + esc(detail) + "</span>" : "") +
        '<span class="item-sub">' + esc(e.course_title || "") +
          (e.course_title && d ? " · " : "") + esc(d) + "</span>" +
      "</span>" +
      '<span class="item-end">' +
        '<span class="' + badgeClass + '">' + esc(KIND_LABEL[e.kind] || e.kind) + "</span>" +
        (e.score != null && e.max_score != null && e.kind !== "mastery"
          ? ' <span class="t-sm muted">' + Math.round((e.score / (e.max_score || 1)) * 100) + "%</span>"
          : "") +
      "</span>" +
      "</div>";
  }

  function render(data) {
    total = data.total || 0;
    els.list.innerHTML = (data.events && data.events.length)
      ? data.events.map(Row).join("")
      : '<div class="state tinted"><span class="state-title">No activity yet</span>' +
        '<span class="state-text">Use the app and this list fills itself.</span></div>';
    global.StudyIcons.hydrate(els.list);
    els.count.textContent = total + " event" + (total === 1 ? "" : "s");
    els.pageEl.textContent = total === 0 ? "—" : "Page " + (page + 1) + " of " + Math.max(1, Math.ceil(total / limit));
    els.prev.disabled = (page === 0);
    els.next.disabled = ((page + 1) * limit >= total);
    els.empty.hidden = (total !== 0);
    if (total === 0) els.list.innerHTML = '';
    els.list.hidden = (total === 0);
  }

  function load() {
    setEmpty(true, true);
    global.StudyAPI.getHistory({ limit: limit, offset: page * limit, kind: currentKind || undefined })
      .then(function (data) { render(data || { events: [], total: 0 }); })
      .catch(function (err) {
        if (App.isAuthError(err)) return;
        global.StudyUI.toast("Could not load your history.", "danger");
        els.list.innerHTML = '<div class="state tinted"><span class="state-title">Could not load</span>' +
          '<span class="state-text">' + App.escapeHtml((err && err.message) || "Unknown error") + "</span></div>";
      });
  }

  function init() {
    els.list = document.getElementById("history-list");
    els.count = document.getElementById("history-count");
    els.empty = document.getElementById("history-empty");
    els.prev = document.getElementById("history-prev");
    els.next = document.getElementById("history-next");
    els.pageEl = document.getElementById("history-page");
    els.kind = document.getElementById("history-kind");
    els.summary = document.getElementById("history-summary");

    if (els.kind) {
      els.kind.addEventListener("change", function () {
        currentKind = els.kind.value;
        page = 0;
        load();
      });
    }
    if (els.prev) els.prev.addEventListener("click", function () { if (page > 0) { page--; load(); } });
    if (els.next) els.next.addEventListener("click", function () { if ((page + 1) * limit < total) { page++; load(); } });

    load();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

})(window);
