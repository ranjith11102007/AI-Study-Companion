/* ==========================================================================
   StudyMate AI — Results page. Loads a graded attempt from the backend and
   renders the score, a client-side per-topic breakdown (graded detail has no
   topic map) and a full per-question review with source citations.
   ========================================================================== */
(function (global) {
  "use strict";

  var App = global.StudyApp;
  var RING_C = 2 * Math.PI * 52;
  var attemptId = "";

  function esc(value) { return global.StudyUI.escapeHtml(value); }

  function pct(n, d) { return d ? Math.round((n / d) * 100) : 0; }

  function grade(p) {
    if (p >= 85) return { label: "Strong mastery", tone: "mastery" };
    if (p >= 70) return { label: "On track", tone: "primary" };
    if (p >= 50) return { label: "Needs revision", tone: "warn" };
    return { label: "Rebuild the basics", tone: "danger" };
  }

  function showState(title, text) {
    var loading = document.getElementById("results-loading");
    if (loading) loading.hidden = true;
    document.getElementById("results-filled").hidden = true;
    var empty = document.getElementById("results-empty");
    empty.hidden = false;
    if (title) document.getElementById("empty-title").textContent = title;
    if (text) document.getElementById("empty-text").textContent = text;
  }

  function answerIsEmpty(value) {
    return value == null || String(value).trim() === "";
  }

  function sourceLinks(ids) {
    if (!ids || !ids.length) return "";
    return '<div class="row row-wrap" style="gap:6px;margin-top:6px">' +
      ids.map(function (id) {
        return '<a class="chip" href="source.html?unit=' + encodeURIComponent(id) + '">' +
          '<span data-icon="file"></span> Source #' + esc(id) + "</a>";
      }).join("") + "</div>";
  }

  function qtypeLabel(qtype) {
    if (qtype === "mcq") return "Multiple choice";
    if (qtype === "numeric") return "Numeric";
    if (qtype === "short") return "Short answer";
    return qtype || "Question";
  }

  function renderReview(questions) {
    var host = document.getElementById("review");
    host.innerHTML = questions.map(function (q, i) {
      var mark, markText;
      if (q.is_correct === true) { mark = "ok"; markText = "Correct"; }
      else if (q.is_correct === false) { mark = "no"; markText = "Incorrect"; }
      else { mark = "pending"; markText = "Needs review"; }

      var answer = q.answer == null ? "" : String(q.answer);
      var yourAnswer = answer.trim() ? esc(answer) : "<em>Not answered</em>";

      var body =
        '<div class="stack stack-xs" style="flex:1;min-width:0">' +
        '<div class="row row-wrap" style="gap:6px">' +
        '<span class="badge badge-neutral">' + qtypeLabel(q.qtype) + "</span>" +
        '<span class="badge badge-neutral">' + esc(q.topic || "General") + "</span>" +
        (q.verified
          ? '<span class="badge badge-mastery">Verified</span>'
          : '<span class="badge badge-warn">Not machine-verified</span>') +
        "</div>" +
        '<span class="r-q">' + (i + 1) + ". " + esc(q.prompt) + "</span>" +
        '<span class="r-a">Your answer: <strong class="' +
        (q.is_correct === true ? "mastery" : q.is_correct === false ? "rose" : "") + '">' +
        yourAnswer + "</strong></span>" +
        '<span class="r-a">Correct answer: <strong class="mastery">' +
        esc(q.correct_answer) + "</strong></span>" +
        (q.rubric ? '<span class="r-a">Rubric: ' + esc(q.rubric) + "</span>" : "") +
        '<div class="explanation"><strong>Why:</strong> ' + esc(q.explanation || "") + "</div>" +
        (q.feedback ? '<span class="r-a">Feedback: ' + esc(q.feedback) + "</span>" : "") +
        (q.verified === false && q.verification_notes
          ? '<span class="r-a">' + esc(q.verification_notes) + "</span>" : "") +
        sourceLinks(q.source_unit_ids) +
        "</div>";

      return (
        '<div class="review-item">' +
        '<span class="review-mark ' + mark + '" title="' + markText + '">' +
        global.StudyUI.icon(q.is_correct === true ? "check" : q.is_correct === false ? "x" : "alert") +
        "</span>" + body + "</div>"
      );
    }).join("");
    global.StudyIcons.hydrate(host);
  }

  function renderReviewSummary(questions) {
    var el = document.getElementById("review-summary");
    if (!el) return;
    var pending = questions.filter(function (q) { return q.is_correct === null; }).length;
    el.textContent = questions.length + " questions" +
      (pending ? " · " + pending + " need manual review" : "");
  }

  function render(attempt) {
    var questions = attempt.questions || [];
    var correct = questions.filter(function (q) { return q.is_correct === true; }).length;
    var incorrect = questions.filter(function (q) { return q.is_correct === false; }).length;
    var pending = questions.filter(function (q) { return q.is_correct === null; }).length;
    var unanswered = questions.filter(function (q) {
      return q.answer == null || String(q.answer).trim() === "";
    }).length;
    var percent = Math.round(attempt.percent || 0);
    var g = grade(percent);

    document.getElementById("results-loading").hidden = true;
    document.getElementById("results-empty").hidden = true;
    document.getElementById("results-filled").hidden = false;

    document.getElementById("score-value").textContent = percent + "%";
    document.getElementById("score-caption").textContent =
      (attempt.score != null && attempt.max_score != null
        ? "Score " + attempt.score + " / " + attempt.max_score
        : correct + " / " + questions.length + " correct");
    var gradeEl = document.getElementById("score-grade");
    gradeEl.textContent = g.label;
    gradeEl.className = "badge badge-" + g.tone;
    document.getElementById("score-meta").textContent =
      questions.length + " questions · attempt #" + attempt.attempt_id;

    var fill = document.getElementById("score-ring-fill");
    fill.setAttribute("stroke-dasharray", RING_C.toFixed(1));
    fill.setAttribute("stroke-dashoffset", RING_C.toFixed(1));
    requestAnimationFrame(function () {
      fill.setAttribute("stroke-dashoffset", (RING_C * (1 - percent / 100)).toFixed(1));
    });

    document.getElementById("stat-correct").textContent = correct;
    document.getElementById("stat-wrong").textContent = incorrect;
    document.getElementById("stat-unanswered").textContent = unanswered;
    document.getElementById("stat-pending").textContent = pending;

    var byTopic = {};
    questions.forEach(function (q) {
      var topic = q.topic || "General";
      if (!byTopic[topic]) byTopic[topic] = { correct: 0, total: 0 };
      byTopic[topic].total += 1;
      if (q.is_correct === true) byTopic[topic].correct += 1;
    });
    var breakdown = document.getElementById("breakdown");
    breakdown.innerHTML = Object.keys(byTopic).map(function (topic) {
      var t = byTopic[topic];
      var tp = pct(t.correct, t.total);
      var tone = tp >= 80 ? "mastery" : tp >= 50 ? "" : "rose";
      return (
        '<div class="breakdown-bar">' +
        '<span class="bb-label">' + esc(topic) + "</span>" +
        '<span class="progress bb-track ' + tone + '"><span style="width:' + tp + '%"></span></span>' +
        '<span class="bb-value">' + tp + "%</span>" +
        "</div>"
      );
    }).join("") ||
      '<p class="t-sm muted">No topics to summarise.</p>';

    renderReview(questions);
    renderReviewSummary(questions);

    document.getElementById("retry-btn").addEventListener("click", function () {
      global.location.href = retakeHref;
    });
  }

  var retakeHref = "assessment.html";

  function init() {
    attemptId = App.queryParam("attempt");
    if (!attemptId) {
      document.getElementById("results-loading").hidden = true;
      document.getElementById("results-empty").hidden = false;
      return;
    }

    global.StudyAPI.getAttempt(attemptId)
      .then(function (attempt) {
        if (!attempt) throw new Error("Attempt not found");
        if (attempt.status !== "graded") {
          global.location.replace("quiz.html?attempt=" + encodeURIComponent(attemptId));
          return;
        }
        render(attempt);

        global.StudyAPI.getAssessment(attempt.assessment_id)
          .then(function (assessment) {
            var courseId = assessment && assessment.course_id;
            var weak = document.querySelector('a[href="recommendations.html"]');
            if (courseId != null) {
              retakeHref = "assessment.html?course=" + encodeURIComponent(courseId);
              if (weak) weak.href = "recommendations.html?course=" + encodeURIComponent(courseId);
            }
          })
          .catch(function () { /* links keep their defaults */ });
      })
      .catch(function (err) {
        if (global.StudyApp.isAuthError(err)) return;
        document.getElementById("results-loading").hidden = true;
        document.getElementById("results-empty").hidden = false;
        document.getElementById("empty-title").textContent = "Could not load this result";
        document.getElementById("empty-text").textContent =
          err && err.message ? err.message : "The attempt could not be found.";
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
