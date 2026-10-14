/* ==========================================================================
   StudyMate AI — Dashboard. Pulls real courses, mastery, recommendations,
   materials and assessments for the active course. No example telemetry.
   ========================================================================== */
(function (global) {
  "use strict";

  var App = global.StudyApp;
  var els = {};
  var courseId = null;

  function esc(value) { return global.StudyUI.escapeHtml(value); }

  function empty(host, icon, title, text) {
    host.innerHTML =
      '<div class="state compact">' +
      '<span class="state-icon slate"><span data-icon="' + icon + '"></span></span>' +
      '<span class="state-title">' + esc(title) + "</span>" +
      '<span class="state-text">' + esc(text) + "</span></div>";
    global.StudyIcons.hydrate(host);
  }

  /* ---------------------------------------------------------------------- */
  /* Renderers                                                              */
  /* ---------------------------------------------------------------------- */
  function renderCourses(courses) {
    var host = document.getElementById("course-list");
    if (!courses || !courses.length) {
      host.innerHTML =
        '<div class="state compact">' +
        '<span class="state-icon slate"><span data-icon="book"></span></span>' +
        '<span class="state-title">No courses yet</span>' +
        '<span class="state-text">Create a course and upload material to get started.</span>' +
        '<span class="state-actions"><a class="btn btn-primary btn-sm" href="courses.html">Create a course</a></span>' +
        "</div>";
      global.StudyIcons.hydrate(host);
      return;
    }
    host.innerHTML = courses.map(function (c) {
      var active = String(c.id) === String(courseId);
      return (
        '<a class="list-item" href="course.html?id=' + encodeURIComponent(c.id) + '">' +
        '<span class="item-icon' + (active ? " primary" : "") + '" data-icon="book"></span>' +
        '<span class="item-main">' +
        '<span class="item-title">' + esc(c.title) + "</span>" +
        '<span class="item-sub">' + esc(c.description || "No description yet.") + "</span>" +
        "</span>" +
        '<span class="item-end">' +
        (String(c.id) === String(courseId) ? '<span class="badge badge-primary">Active</span>' : "") +
        '<span class="muted" data-icon="chevronRight"></span></span></div>'
      );
    }).join("");
    global.StudyIcons.hydrate(host);
  }

  function renderWeak(recommendations) {
    var host = document.getElementById("weak-list");
    var list = (recommendations || []).slice(0, 4);
    if (!list.length) {
      empty(host, "target", "No weak topics yet", "Complete an assessment and revision targets appear here.");
      return;
    }
    host.innerHTML = list.map(function (rec) {
      var tone = rec.priority >= 0.7 ? "danger" : rec.priority >= 0.4 ? "warn" : "neutral";
      var label = tone === "danger" ? "High" : tone === "warn" ? "Medium" : "Low";
      var q = encodeURIComponent("Explain " + (rec.topic || "this topic") + " in detail.");
      return (
        '<a class="list-item" href="tutor.html?course=' + encodeURIComponent(courseId) + "&q=" + q + '">' +
        '<span class="item-icon rose" data-icon="target"></span>' +
        '<span class="item-main">' +
        '<span class="item-title">' + esc(rec.topic || "Revision target") + "</span>" +
        '<span class="item-sub">' + esc(rec.reason || "") + "</span></span>" +
        '<span class="item-end"><span class="badge badge-' + tone + '">' + label + "</span>" +
        '<span class="muted" data-icon="chevronRight"></span></span></a>'
      );
    }).join("");
    global.StudyIcons.hydrate(host);
  }

  function renderAssessments(list) {
    var host = document.getElementById("assessment-list");
    if (!list || !list.length) {
      host.innerHTML =
        '<div class="state compact">' +
        '<span class="state-icon amber"><span data-icon="quiz"></span></span>' +
        '<span class="state-title">No assessments yet</span>' +
        '<span class="state-text">Generate one from this course\'s indexed material.</span>' +
        '<span class="state-actions"><a class="btn btn-primary btn-sm" href="' +
        esc("assessment.html?course=" + courseId) + '">Start an assessment</a></span></div>';
      global.StudyIcons.hydrate(host);
      return;
    }
    host.innerHTML = list.slice(0, 4).map(function (a) {
      return (
        '<div class="list-item">' +
        '<span class="item-icon mastery" data-icon="quiz"></span>' +
        '<span class="item-main">' +
        '<span class="item-title">' + esc(a.title) + "</span>" +
        '<span class="item-sub">' + a.question_count + " questions · " +
        esc(a.difficulty) + " · " + esc(global.StudyUI.timeLabel(a.created_at)) + "</span></span>" +
        '<span class="item-end"><button class="btn btn-primary btn-sm" data-start-assessment="' +
        a.id + '">Start</button></span></div>'
      );
    }).join("");
    global.StudyIcons.hydrate(host);
  }

  function renderMaterials(list) {
    var host = document.getElementById("materials-list");
    if (!list || !list.length) {
      empty(host, "upload", "No material indexed", "Upload a document to enable tutoring and testing.");
      return;
    }
    host.innerHTML = list.slice(0, 4).map(function (m) {
      var status = App.materialStatus(m.processing_status);
      return (
        '<div class="list-item">' +
        '<span class="item-icon primary" data-icon="' + App.materialIcon(m.material_type || m.filename) + '"></span>' +
        '<span class="item-main">' +
        '<span class="item-title">' + esc(m.original_filename) + "</span>" +
        '<span class="item-sub">' + esc(m.material_type || "file") + " · " +
        (m.content_unit_count || 0) + " chunks</span></span>" +
        '<span class="item-end"><span class="badge ' + status.tone + '">' + status.label + "</span></span></div>"
      );
    }).join("");
    global.StudyIcons.hydrate(host);
  }

  function setStats(mastery, materials, weakCount) {
    var topics = (mastery && mastery.topics) || [];
    document.getElementById("stat-materials").textContent = (materials || []).length;
    document.getElementById("stat-topics").textContent = topics.length;
    document.getElementById("stat-mastery").textContent = topics.length
      ? App.percent(topics.reduce(function (s, t) { return s + t.mastery; }, 0) / topics.length) + "%"
      : "–";
    document.getElementById("stat-weak").textContent = weakCount;
  }

  function resetStats() {
    document.getElementById("stat-materials").textContent = "–";
    document.getElementById("stat-topics").textContent = "–";
    document.getElementById("stat-mastery").textContent = "–";
    document.getElementById("stat-weak").textContent = "–";
  }

  function loadCourseData(id) {
    courseId = id;
    if (!id) {
      resetStats();
      renderAssessments([]);
      renderMaterials([]);
      renderWeak([]);
      return;
    }

    var courseHref = "course.html?id=" + encodeURIComponent(id);
    document.getElementById("course-link").href = courseHref;
    document.getElementById("weak-link").href = "recommendations.html?course=" + encodeURIComponent(id);
    document.getElementById("assess-link").href = "assessment.html?course=" + encodeURIComponent(id);

    App.setCourse(id);
    Promise.all([
      global.StudyAPI.getMastery(id).catch(function () { return {}; }),
      global.StudyAPI.getRecommendations(id).catch(function () { return []; }),
      global.StudyAPI.getMaterials(id).catch(function () { return []; }),
      global.StudyAPI.listAssessments(id).catch(function () { return []; })
    ]).then(function (results) {
      var mastery = results[0] || {};
      var recommendations = results[1] || [];
      var materials = results[2] || [];
      var assessments = results[3] || [];
      setStats(mastery, materials, (mastery.weak_topics || []).length);
      renderWeak(recommendations);
      renderMaterials(materials);
      renderAssessments(assessments);
    });
  }

  /* ---------------------------------------------------------------------- */
  /* Init                                                                   */
  /* ---------------------------------------------------------------------- */
  function init() {
    els.select = document.getElementById("course-select");

    var name = App.displayName();
    if (name) document.getElementById("welcome-title").textContent = "Welcome back, " + name + ".";

    var list = document.getElementById("assessment-list");
    if (list) {
      list.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-start-assessment]");
        if (!btn) return;
        global.StudyAPI.startAttempt(btn.getAttribute("data-start-assessment"))
          .then(function (attempt) {
            global.location.href = "quiz.html?attempt=" + encodeURIComponent(attempt.attempt_id) +
              "&course=" + encodeURIComponent(courseId);
          })
          .catch(function (err) { App.handleError(err, "Could not start the assessment."); });
      });
    }

    App.mountCourseSelect(els.select, {
      onChange: function (id) { loadCourseData(id); },
      onLoaded: function (id, courses) {
        renderCourses(courses);
        loadCourseData(id);
      }
    }).catch(function () { /* mountCourseSelect surfaces the error */ });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
