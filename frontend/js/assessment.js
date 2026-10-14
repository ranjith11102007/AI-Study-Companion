/* ==========================================================================
   StudyMate AI — Assessment setup. Generates a verified assessment from the
   selected course's indexed material, starts an attempt and hands off to
   quiz.html. No sample bank, no fabricated content.
   ========================================================================== */
(function (global) {
  "use strict";

  var els = {};
  var difficulty = "medium";
  var busy = false;

  function showError(message) {
    if (!els.error) return;
    els.error.hidden = !message;
    if (message && els.errorText) els.errorText.textContent = message;
  }

  function timeLabel(minutes) {
    return minutes ? minutes + " min limit" : "No time limit";
  }

  /* ---------------------------------------------------------------------- */
  /* Recent assessments                                                     */
  /* ---------------------------------------------------------------------- */
  function assessmentItem(item) {
    var el = document.createElement("div");
    el.className = "list-item";
    el.innerHTML =
      '<span class="item-icon mastery" data-icon="quiz"></span>' +
      '<span class="item-main">' +
      '<span class="item-title">' + global.StudyUI.escapeHtml(item.title) + "</span>" +
      '<span class="item-sub">' + item.question_count + " questions · " +
      global.StudyUI.escapeHtml(item.difficulty) + " · " +
      global.StudyUI.escapeHtml(timeLabel(item.time_limit_minutes)) + " · " +
      global.StudyUI.escapeHtml(global.StudyUI.timeLabel(item.created_at)) + "</span>" +
      "</span>" +
      '<span class="item-end">' +
      '<button class="btn btn-primary btn-sm" data-start="' + item.id + '">Start</button>' +
      '<button class="btn btn-quiet btn-sm" data-delete="' + item.id + '" aria-label="Delete assessment">' +
      global.StudyUI.icon("trash") + "</button>" +
      "</span>";
    return el;
  }

  function renderAssessments(list) {
    var host = document.getElementById("assessment-list");
    if (!host) return;
    host.innerHTML = "";
    if (!list || !list.length) {
      host.innerHTML =
        '<div class="state compact">' +
        '<span class="state-icon slate"><span data-icon="quiz"></span></span>' +
        '<span class="state-title">No assessments yet</span>' +
        '<span class="state-text">Generate one from your indexed material with the form.</span>' +
        "</div>";
      global.StudyIcons.hydrate(host);
      return;
    }
    list.forEach(function (item) { host.appendChild(assessmentItem(item)); });
    global.StudyIcons.hydrate(host);
  }

  function loadAssessments() {
    var courseId = els.courseSelect ? els.courseSelect.value : "";
    if (!courseId || !global.StudyApp.isAuthed()) { renderAssessments([]); return; }
    global.StudyAPI.listAssessments(courseId)
      .then(function (list) { renderAssessments(list || []); })
      .catch(function (err) {
        if (!global.StudyApp.isAuthError(err)) renderAssessments([]);
      });
  }

  /* ---------------------------------------------------------------------- */
  /* Flows                                                                  */
  /* ---------------------------------------------------------------------- */
  function redirectToQuiz(attempt) {
    var params = new URLSearchParams();
    params.set("attempt", attempt.attempt_id);
    if (attempt.assessment_id) params.set("assessment", attempt.assessment_id);
    if (els.courseSelect && els.courseSelect.value) params.set("course", els.courseSelect.value);
    if (els.timeLimit && els.timeLimit.value) params.set("minutes", els.timeLimit.value);
    global.location.href = "quiz.html?" + params.toString();
  }

  function setStartDisabled(state) {
    busy = state;
    if (els.startBtn) els.startBtn.disabled = state;
  }

  function startExisting(assessmentId) {
    if (busy) return;
    busy = true;
    showError("");
    if (els.startBtn) els.startBtn.disabled = true;
    global.StudyAPI.startAttempt(assessmentId)
      .then(function (attempt) { redirectToQuiz(attempt); })
      .catch(function (err) {
        busy = false;
        if (els.startBtn) els.startBtn.disabled = false;
        if (global.StudyApp.isAuthError(err)) return;
        showError(err && err.message ? err.message : "Could not start that assessment.");
      });
  }

  function generate() {
    if (busy) return;
    var courseId = els.courseSelect ? els.courseSelect.value : "";
    if (!courseId) {
      global.StudyUI.toast("Select a course first.", "warn");
      return;
    }
    var title = els.title && els.title.value.trim();
    var count = Number(els.countRange.value);
    var minutes = els.timeLimit && els.timeLimit.value ? Number(els.timeLimit.value) : null;

    busy = true;
    showError("");
    els.startBtn.disabled = true;

    global.StudyAPI.createAssessment({
      course_id: Number(courseId),
      title: title || "Practice assessment",
      question_count: count,
      difficulty: difficulty,
      time_limit_minutes: minutes
    })
      .then(function (assessment) {
        global.StudyUI.toast("Generated " + assessment.question_count + " questions.", "success");
        return global.StudyAPI.startAttempt(assessment.id).then(function (attempt) {
          redirectToQuiz(attempt);
        });
      })
      .catch(function (err) {
        busy = false;
        els.startBtn.disabled = false;
        if (global.StudyApp.isAuthError(err)) return;

        var message;
        if (err && err.status === 422) {
          message = err.message ||
            "No verifiable questions could be generated. Upload and index more material for this course.";
        } else if (err && err.status === 503) {
          message = "The local AI model (Ollama) is unavailable. Start Ollama and make sure the configured chat model is pulled, then try again.";
        } else if (err && err.status === 0) {
          message = "Could not reach the backend. Make sure it is running.";
        } else {
          message = err && err.message ? err.message : "Could not generate the assessment.";
        }
        showError(message);
        global.StudyUI.toast(message, "warn");
      });
  }

  /* ---------------------------------------------------------------------- */
  /* Init                                                                   */
  /* ---------------------------------------------------------------------- */
  function init() {
    els.courseSelect = document.getElementById("course-select");
    els.title = document.getElementById("assessment-title");
    els.countRange = document.getElementById("count-range");
    els.countLabel = document.getElementById("count-label");
    els.timeLimit = document.getElementById("time-limit");
    els.startBtn = document.getElementById("start-btn");
    els.error = document.getElementById("gen-error");
    els.errorText = document.getElementById("gen-error-text");

    var seg = document.getElementById("difficulty");
    if (seg) {
      seg.addEventListener("click", function (e) {
        var btn = e.target.closest("button[data-diff]");
        if (!btn) return;
        seg.querySelectorAll("button").forEach(function (b) {
          b.classList.toggle("active", b === btn);
        });
        difficulty = btn.getAttribute("data-diff");
      });
    }

    if (els.countRange && els.countLabel) {
      els.countRange.addEventListener("input", function () {
        els.countLabel.textContent = els.countRange.value;
      });
    }

    if (els.startBtn) els.startBtn.addEventListener("click", generate);

    var list = document.getElementById("assessment-list");
    if (list) {
      list.addEventListener("click", function (e) {
        var start = e.target.closest("[data-start]");
        if (start) { startExisting(start.getAttribute("data-start")); return; }
        var del = e.target.closest("[data-delete]");
        if (!del) return;
        if (!global.confirm("Delete this assessment and its questions?")) return;
        global.StudyAPI.deleteAssessment(del.getAttribute("data-delete"))
          .then(function () {
            global.StudyUI.toast("Assessment deleted.", "success");
            loadAssessments();
          })
          .catch(function (err) {
            global.StudyApp.handleError(err, "Could not delete the assessment.");
          });
      });
    }

    var reload = document.getElementById("reload-assessments");
    if (reload) reload.addEventListener("click", loadAssessments);

    global.StudyApp.mountCourseSelect(els.courseSelect, {
      onChange: function () { loadAssessments(); },
      onLoaded: function () { loadAssessments(); }
    }).catch(function () { /* mountCourseSelect surfaces the error */ });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
