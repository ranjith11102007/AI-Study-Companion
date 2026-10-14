/* ==========================================================================
   StudyMate AI — Weak topics / recommendations page. Loads real revision
   targets from GET /api/courses/{id}/recommendations and can rebuild them
   with refresh=true. No fake entries: an empty result renders an honest
   empty state with the action that creates recommendations.
   ========================================================================== */
(function (global) {
  "use strict";

  var App = global.StudyApp;
  var els = {};
  var courseId = null;

  function esc(value) { return global.StudyUI.escapeHtml(value); }

  function kindIcon(kind) {
    if (kind === "diagnostic") return "quiz";
    if (kind === "revision") return "history";
    return "target"; /* weak_topic and anything else */
  }

  function kindTone(kind) {
    if (kind === "weak_topic") return "rose";
    if (kind === "revision") return "amber";
    return "primary"; /* diagnostic */
  }

  function kindLabel(kind) {
    if (kind === "weak_topic") return "Weak topic";
    if (kind === "revision") return "Revision";
    if (kind === "diagnostic") return "Diagnostic";
    return kind || "Recommendation";
  }

  function prioBadge(priority) {
    var p = Number(priority) || 0;
    var tone = p >= 0.7 ? "danger" : p >= 0.4 ? "warn" : "neutral";
    var label = tone === "danger" ? "High" : tone === "warn" ? "Medium" : "Low";
    return '<span class="badge badge-' + tone + '">' + label + " priority</span>";
  }

  function recHref(topic) {
    return "tutor.html?q=" + encodeURIComponent("Explain " + topic + " in detail.") +
      "&course=" + encodeURIComponent(courseId);
  }

  function recItem(rec) {
    var topic = rec.topic || "Revision target";
    var createdAt = rec.created_at ? " · " + esc(App.timeLabel(rec.created_at)) : "";
    return (
      '<div class="list-item">' +
      '<span class="item-icon ' + kindTone(rec.kind) + '" data-icon="' + kindIcon(rec.kind) + '"></span>' +
      '<span class="item-main">' +
      '<span class="item-title">' + esc(topic) + "</span>" +
      '<span class="item-sub">' + esc(kindLabel(rec.kind)) + " · " +
      esc(rec.reason || "") + createdAt + "</span></span>" +
      '<span class="item-end">' + prioBadge(rec.priority) +
      '<a class="btn btn-ghost btn-sm" href="' + esc(recHref(topic)) +
      '"><span data-icon="chat"></span> Review in tutor</a></span></div>'
    );
  }

  /* ---------------------------------------------------------------------- */
  /* Rendering                                                              */
  /* ---------------------------------------------------------------------- */
  function render(list) {
    els.error.hidden = true;
    if (!list || !list.length) {
      els.card.hidden = true;
      els.list.innerHTML = "";
      els.empty.hidden = false;
      return;
    }
    els.empty.hidden = true;
    els.card.hidden = false;
    els.list.innerHTML = list.map(recItem).join("");
    global.StudyIcons.hydrate(els.list);
  }

  function showError(err) {
    var msg = App.errMessage
      ? App.errMessage(err, "Could not load recommendations for this course.")
      : ((err && err.message) || "Could not load recommendations for this course.");
    els.error.hidden = false;
    document.getElementById("rec-error-text").textContent = msg;
    els.empty.hidden = true;
    els.card.hidden = true;
  }

  /* ---------------------------------------------------------------------- */
  /* Data                                                                   */
  /* ---------------------------------------------------------------------- */
  function setRefreshing(state) {
    els.refreshBtn.disabled = state;
    var emptyBtn = document.getElementById("empty-refresh-btn");
    if (emptyBtn) emptyBtn.disabled = state;
    if (state) {
      els.refreshBtn.innerHTML = App.icon("refresh") + " Regenerating…";
    } else {
      els.refreshBtn.innerHTML = App.icon("refresh") + " Regenerate";
    }
    global.StudyIcons.hydrate(els.refreshBtn);
  }

  function regenerate() {
    if (!courseId) { global.StudyUI.toast("Select a course first.", "warn"); return; }
    setRefreshing(true);
    global.StudyAPI.getRecommendations(courseId, true)
      .then(function (list) {
        render(list || []);
        global.StudyUI.toast("Recommendations regenerated.", "success");
      })
      .catch(function (err) {
        if (App.isAuthError(err)) return;
        showError(err);
      })
      .then(function () {
        setRefreshing(false);
      });
  }

  function loadData(id) {
    courseId = id;
    if (!id) {
      els.error.hidden = true;
      els.card.hidden = true;
      els.list.innerHTML = "";
      els.empty.hidden = false;
      document.getElementById("rec-empty-text").textContent =
        "Select a course to see its recommendations.";
      document.getElementById("empty-assess-link").href = "courses.html";
      document.getElementById("empty-assess-link").textContent = "Choose a course";
      return;
    }

    document.getElementById("empty-assess-link").href =
      "assessment.html?course=" + encodeURIComponent(id);

    global.StudyAPI.getRecommendations(id)
      .then(function (list) { render(list || []); })
      .catch(function (err) {
        if (App.isAuthError(err)) return;
        els.empty.hidden = true;
        showError(err);
      });
  }

  /* ---------------------------------------------------------------------- */
  /* Init                                                                   */
  /* ---------------------------------------------------------------------- */
  function init() {
    els.select = document.getElementById("course-select");
    els.empty = document.getElementById("rec-empty");
    els.card = document.getElementById("rec-card");
    els.list = document.getElementById("rec-list");
    els.error = document.getElementById("rec-error");
    els.refreshBtn = document.getElementById("refresh-rec-btn");

    if (els.refreshBtn) {
      els.refreshBtn.addEventListener("click", function (e) {
        e.preventDefault();
        regenerate();
      });
    }
    var emptyBtn = document.getElementById("empty-refresh-btn");
    if (emptyBtn) {
      emptyBtn.addEventListener("click", function (e) {
        e.preventDefault();
        regenerate();
      });
    }

    App.mountCourseSelect(els.select, {
      onChange: function (id) { loadData(id); },
      onLoaded: function (id) { loadData(id); },
      onEmpty: function () {
        els.error.hidden = true;
        els.card.hidden = true;
        els.list.innerHTML = "";
        els.empty.hidden = false;
        document.getElementById("rec-empty-text").textContent =
          "Create a course and take an assessment — recommendations will appear here.";
        document.getElementById("empty-assess-link").href = "courses.html";
        document.getElementById("empty-assess-link").textContent = "Create a course";
      }
    }).catch(function (err) {
      showError(err);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);