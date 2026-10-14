/* ==========================================================================
   StudyMate AI — Progress page. Renders real per-topic mastery for the
   selected course from GET /api/courses/{id}/mastery (bars + weak / strong /
   untested). No fake values: when there is no evidence the page says so and
   offers the path to create some.
   ========================================================================== */
(function (global) {
  "use strict";

  var App = global.StudyApp;
  var els = {};
  var courseId = null;

  function esc(value) { return global.StudyUI.escapeHtml(value); }

  function percent(value) { return App.percent(value); }

  function tone(value) {
    var p = percent(value);
    return p >= 75 ? "mastery" : p >= 50 ? "amber" : "rose";
  }

  function badgeTone(value) {
    var t = tone(value);
    return t === "mastery" ? "mastery" : t === "amber" ? "warn" : "danger";
  }

  function correctLabel(t) {
    return t.correct_count + " of " + t.evidence_count + " graded correct" +
      (t.last_practiced_at ? " · last practised " + esc(App.timeLabel(t.last_practiced_at)) : "");
  }

  function practiseHref(topic) {
    return "tutor.html?q=" + encodeURIComponent("Explain " + topic + " in detail.") +
      "&course=" + encodeURIComponent(courseId);
  }

  /* ---------------------------------------------------------------------- */
  /* Renderers                                                              */
  /* ---------------------------------------------------------------------- */
  function renderMasteryList(topics) {
    var host = els.masteryList;
    if (!topics || !topics.length) {
      host.innerHTML =
        '<p class="t-sm muted" style="padding:15px 18px">No mastery data yet — take an assessment to start tracking.</p>';
      return;
    }
    host.innerHTML = topics.map(function (t) {
      var p = percent(t.mastery);
      var tn = tone(t.mastery);
      return (
        '<div class="mastery-row">' +
        '<div class="mr-top">' +
        '<span class="mr-name"><span data-icon="target"></span> ' + esc(t.topic) + "</span>" +
        '<span class="mr-actions"><strong class="tnum ' + tn + '">' + p + "%</strong>" +
        '<a class="link" href="' + esc(practiseHref(t.topic)) + '">Practise</a></span>' +
        "</div>" +
        '<div class="progress ' + tn + '"><span style="width:' + p + '%"></span></div>' +
        '<span class="mr-meta">' + correctLabel(t) + "</span></div>"
      );
    }).join("");
    global.StudyIcons.hydrate(host);
  }

  function statusList(host, title, items, emptyText, builder) {
    var head =
      '<div class="row row-between" style="padding:12px 18px 4px;align-items:center">' +
      '<span class="t-eyebrow">' + esc(title) + "</span>" +
      '<span class="badge badge-neutral">' + items.length + "</span></div>";
    if (!items || !items.length) {
      host.innerHTML = head + '<p class="t-sm muted" style="padding:2px 18px 12px">' + esc(emptyText) + "</p>";
      return;
    }
    host.innerHTML = head + '<div class="list">' + items.map(builder).join("") + "</div>";
    global.StudyIcons.hydrate(host);
  }

  function weakItem(t) {
    return (
      '<div class="list-item">' +
      '<span class="item-icon rose" data-icon="target"></span>' +
      '<span class="item-main">' +
      '<span class="item-title">' + esc(t.topic) + "</span>" +
      '<span class="item-sub">' + percent(t.mastery) + "% mastery · " + correctLabel(t) + "</span></span>" +
      '<span class="item-end"><span class="badge badge-' + badgeTone(t.mastery) + '">Weak</span>' +
      '<a class="btn btn-ghost btn-sm" href="' + esc(practiseHref(t.topic)) + '">Revise</a></span></div>'
    );
  }

  function strongItem(t) {
    return (
      '<div class="list-item">' +
      '<span class="item-icon mastery" data-icon="checkCircle"></span>' +
      '<span class="item-main">' +
      '<span class="item-title">' + esc(t.topic) + "</span>" +
      '<span class="item-sub">' + percent(t.mastery) + "% mastery · " + correctLabel(t) + "</span></span>" +
      '<span class="item-end"><span class="badge badge-mastery">Strong</span></span></div>'
    );
  }

  function untestedItem(topic) {
    return (
      '<div class="list-item">' +
      '<span class="item-icon" data-icon="layers"></span>' +
      '<span class="item-main">' +
      '<span class="item-title">' + esc(topic) + "</span>" +
      '<span class="item-sub">Assessed, but no graded answers yet.</span></span>' +
      '<span class="item-end"><a class="btn btn-ghost btn-sm" href="' +
      esc(practiseHref(topic)) + '">Practise</a></span></div>'
    );
  }

  function setStats(mastery) {
    var topics = mastery.topics || [];
    var avg = topics.length
      ? percent(topics.reduce(function (sum, t) { return sum + t.mastery; }, 0) / topics.length)
      : null;
    if (avg == null) {
      document.getElementById("stat-mastery-avg").textContent = "–";
      document.getElementById("stat-topics-tracked").textContent = "No topics tracked";
    } else {
      document.getElementById("stat-mastery-avg").textContent = avg + "%";
      document.getElementById("stat-topics-tracked").textContent =
        topics.length + " topic" + (topics.length === 1 ? "" : "s") + " tracked";
    }
    document.getElementById("stat-weak").textContent = (mastery.weak_topics || []).length;
    document.getElementById("stat-strong").textContent = (mastery.strong_topics || []).length;
    document.getElementById("stat-untested").textContent = (mastery.untested_topics || []).length;
  }

  function render(mastery) {
    var topics = mastery.topics || [];
    var weak = mastery.weak_topics || [];
    var strong = mastery.strong_topics || [];
    var untested = mastery.untested_topics || [];
    var nothing = !topics.length && !weak.length && !strong.length && !untested.length;

    els.error.hidden = true;
    if (nothing) {
      els.empty.hidden = false;
      els.body.hidden = true;
      return;
    }
    els.empty.hidden = true;
    els.body.hidden = false;

    setStats(mastery);
    renderMasteryList(topics);
    statusList(els.statusWeak, "Weak topics", weak, "No weak topics yet.",
      weakItem);
    statusList(els.statusStrong, "Strong topics", strong, "No strong topics yet.",
      strongItem);
    statusList(els.statusUntested, "Untested topics", untested, "No untested topics.",
      untestedItem);
  }

  /* ---------------------------------------------------------------------- */
  /* Loading                                                                */
  /* ---------------------------------------------------------------------- */
  function showError(err) {
    var msg = App.errMessage ? App.errMessage(err, "Could not load mastery for this course.")
      : ((err && err.message) || "Could not load mastery for this course.");
    els.error.hidden = false;
    document.getElementById("progress-error-text").textContent = msg;
    els.empty.hidden = true;
    els.body.hidden = true;
  }

  function loadData(id) {
    courseId = id;
    if (!id) {
      els.error.hidden = true;
      els.body.hidden = true;
      els.empty.hidden = false;
      document.getElementById("progress-empty-text").textContent = "Select a course to see its mastery.";
      document.getElementById("empty-assess-link").href = "courses.html";
      document.getElementById("empty-assess-link").textContent = "Choose a course";
      return;
    }

    var assess = document.getElementById("empty-assess-link");
    assess.href = "assessment.html?course=" + encodeURIComponent(id);

    global.StudyAPI.getMastery(id)
      .then(function (mastery) {
        render(mastery || {
          course_id: id, topics: [], weak_topics: [], strong_topics: [], untested_topics: []
        });
      })
      .catch(function (err) {
        if (App.isAuthError(err)) return;
        showError(err);
      });
  }

  /* ---------------------------------------------------------------------- */
  /* Init                                                                   */
  /* ---------------------------------------------------------------------- */
  function init() {
    els.select = document.getElementById("course-select");
    els.empty = document.getElementById("progress-empty");
    els.body = document.getElementById("progress-body");
    els.error = document.getElementById("progress-error");
    els.masteryList = document.getElementById("mastery-list");
    els.statusWeak = document.getElementById("status-weak");
    els.statusStrong = document.getElementById("status-strong");
    els.statusUntested = document.getElementById("status-untested");

    App.mountCourseSelect(els.select, {
      onChange: function (id) { loadData(id); },
      onLoaded: function (id) { loadData(id); },
      onEmpty: function () {
        els.error.hidden = true;
        els.body.hidden = true;
        els.empty.hidden = false;
        document.getElementById("progress-empty-text").textContent =
          "Create a course and take your first assessment to see mastery tracking.";
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