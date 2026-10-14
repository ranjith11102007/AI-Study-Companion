/* ==========================================================================
   StudyMate AI — Quiz runner. Loads the in-progress attempt from the backend,
   renders one question at a time (mcq / numeric / short), tracks answers and
   a query-string timer, then submits to the backend for grading.
   ========================================================================== */
(function (global) {
  "use strict";

  var App = global.StudyApp;
  var els = {};
  var attemptId = App.queryParam("attempt");
  var minutes = parseInt(App.queryParam("minutes"), 10);
  if (isNaN(minutes) || minutes <= 0) minutes = 0;

  var questions = [];
  var state = { index: 0, answers: {}, flags: {}, remaining: null, ids: [] };
  var timerId = null;
  var submitting = false;

  function stateKey() { return "studymate:attempt:" + attemptId; }

  function saveState() {
    try { sessionStorage.setItem(STATE_KEY, JSON.stringify(state)); } catch (e) { /* ignore */ }
  }
  function loadState() {
    try { return JSON.parse(sessionStorage.getItem(STATE_KEY)); } catch (e) { return null; }
  }

  function isAnswered(q) {
    var value = state.answers[q.id];
    return value != null && String(value).trim() !== "";
  }

  function answeredCount() {
    return questions.filter(isAnswered).length;
  }

  function showError(title, text) {
    els.loading.hidden = true;
    els.body.hidden = true;
    els.error.hidden = false;
    if (title) els.errorTitle.textContent = title;
    if (text) els.errorText.textContent = text;
  }

  /* ---------------------------------------------------------------------- */
  /* Rendering                                                              */
  /* ---------------------------------------------------------------------- */
  function renderPalette() {
    els.palette.innerHTML = questions.map(function (q, i) {
      var cls = "p-cell";
      if (i === state.index) cls += " current";
      else if (isAnswered(q)) cls += " answered";
      if (state.flags[q.id]) cls += " flagged";
      return '<button class="' + cls + '" data-go="' + i + '" type="button" aria-label="Question ' +
        (i + 1) + '">' + (i + 1) + "</button>";
    }).join("");
  }

  function renderAnswerArea(q) {
    var host = els.answerArea;
    var value = state.answers[q.id];

    if (q.qtype === "mcq" && q.options && q.options.length) {
      host.innerHTML =
        '<div class="option-stack">' + q.options.map(function (opt, i) {
          var selected = value === opt;
          return '<button type="button" class="option-row' + (selected ? " selected" : "") +
            '" data-opt="' + i + '">' +
            '<span class="option-key">' + "ABCDEFGH"[i] + "</span>" +
            "<span>" + global.StudyUI.escapeHtml(opt) + "</span></button>";
        }).join("") + "</div>";
      return;
    }

    if (q.qtype === "numeric") {
      host.innerHTML =
        '<div class="field">' +
        '<label class="field-label" for="answer-input">Your answer (number)</label>' +
        '<input class="input" id="answer-input" type="text" inputmode="decimal" ' +
        'autocomplete="off" placeholder="e.g. 42" value="' +
        global.StudyUI.escapeHtml(value == null ? "" : value) + '" />' +
        "</div>";
      return;
    }

    host.innerHTML =
      '<div class="field">' +
      '<label class="field-label" for="answer-input">Your answer</label>' +
      '<textarea class="input" id="answer-input" rows="4" ' +
      'placeholder="Write a short answer…">' +
      global.StudyUI.escapeHtml(value == null ? "" : value) + "</textarea>" +
      '<span class="field-help">Short answers are auto-graded by rubric keyword overlap ' +
      "and flagged for manual review.</span>" +
      "</div>";
  }

  function renderQuestion() {
    var q = questions[state.index];
    els.counter.textContent = "Question " + (state.index + 1) + " of " + questions.length;
    els.topic.textContent = q.topic || "General";
    els.difficulty.textContent = q.difficulty || "medium";
    els.text.textContent = q.prompt;
    els.flag.classList.toggle("active", !!state.flags[q.id]);
    els.flag.setAttribute("aria-pressed", state.flags[q.id] ? "true" : "false");

    renderAnswerArea(q);

    els.prev.disabled = state.index === 0;
    els.next.disabled = state.index === questions.length - 1;
    els.answered.textContent = answeredCount() + " / " + questions.length;
    els.progress.firstElementChild.style.width =
      (((state.index + 1) / questions.length) * 100) + "%";
    renderPalette();
  }

  function setAnswer(value) {
    var q = questions[state.index];
    state.answers[q.id] = value;
    saveState();
    els.answered.textContent = answeredCount() + " / " + questions.length;
    renderPalette();
  }

  function go(i) {
    if (i < 0 || i >= questions.length) return;
    state.index = i;
    saveState();
    renderQuestion();
  }

  /* ---------------------------------------------------------------------- */
  /* Timer                                                                  */
  /* ---------------------------------------------------------------------- */
  function formatTime(sec) {
    var m = Math.floor(sec / 60);
    var s = sec % 60;
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }

  function startTimer() {
    if (!minutes) {
      els.timer.textContent = "No limit";
      return;
    }
    if (state.remaining == null) state.remaining = minutes * 60;
    function tick() {
      els.timer.textContent = formatTime(Math.max(0, state.remaining));
      if (state.remaining <= 0) {
        clearInterval(timerId);
        submit(true);
        return;
      }
      state.remaining -= 1;
      saveState();
    }
    tick();
    timerId = setInterval(tick, 1000);
  }

  /* ---------------------------------------------------------------------- */
  /* Submit                                                                 */
  /* ---------------------------------------------------------------------- */
  function submit(auto) {
    if (els.submitBtn.disabled) return;
    if (timerId) clearInterval(timerId);
    els.submit.disabled = true;

    var answers = questions.map(function (q) {
      var value = state.answers[q.id];
      return {
        question_id: q.id,
        answer: value == null ? "" : String(value)
      };
    });

    if (auto) global.StudyUI.toast("Time expired — submitting your answers.", "warn");

    global.StudyAPI.submitAttempt(attemptId, answers)
      .then(function () {
        try { sessionStorage.removeItem(STATE_KEY); } catch (e) { /* ignore */ }
        global.location.href = "results.html?attempt=" + encodeURIComponent(attemptId);
      })
      .catch(function (err) {
        if (err && err.status === 409) {
          global.location.href = "results.html?attempt=" + encodeURIComponent(attemptId);
          return;
        }
        els.submit.disabled = false;
        if (global.StudyApp.isAuthError(err)) return;
        global.StudyUI.toast(
          err && err.message ? err.message : "Could not submit the attempt.",
          "warn"
        );
      });
  }

  /* ---------------------------------------------------------------------- */
  /* Bind / init                                                            */
  /* ---------------------------------------------------------------------- */
  function bind() {
    els.answerArea.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-opt]");
      if (!btn) return;
      var q = questions[state.index];
      if (q.qtype !== "mcq") return;
      var opt = q.options[Number(btn.getAttribute("data-opt"))];
      els.answerArea.querySelectorAll(".option-row").forEach(function (row) {
        row.classList.toggle("selected", row === btn);
      });
      setAnswer(opt);
    });

    els.answerArea.addEventListener("input", function (e) {
      if (e.target && e.target.id === "answer-input") setAnswer(e.target.value);
    });

    els.palette.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-go]");
      if (btn) go(Number(btn.getAttribute("data-go")));
    });

    els.prev.addEventListener("click", function () { go(state.index - 1); });
    els.next.addEventListener("click", function () { go(state.index + 1); });

    els.flag.addEventListener("click", function () {
      var q = questions[state.index];
      state.flags[q.id] = !state.flags[q.id];
      saveState();
      renderQuestion();
    });

    els.submit.addEventListener("click", function () {
      var unanswered = questions.length - answeredCount();
      var message = unanswered
        ? "You have " + unanswered + " unanswered question(s). Submit anyway?"
        : "Submit this attempt for grading?";
      if (global.confirm(message)) submit(false);
    });
  }

  var STATE_KEY = "";

  function init() {
    els.loading = document.getElementById("quiz-loading");
    els.error = document.getElementById("quiz-error");
    els.errorTitle = document.getElementById("quiz-error-title");
    els.errorText = document.getElementById("quiz-error-text");
    els.body = document.getElementById("quiz-body");
    els.title = document.getElementById("quiz-title");
    els.badges = document.getElementById("quiz-badges");
    els.counter = document.getElementById("q-counter");
    els.topic = document.getElementById("q-topic");
    els.difficulty = document.getElementById("q-difficulty");
    els.text = document.getElementById("q-text");
    els.answerArea = document.getElementById("answer-area");
    els.progress = document.getElementById("q-progress");
    els.prev = document.getElementById("prev-btn");
    els.next = document.getElementById("next-btn");
    els.flag = document.getElementById("flag-btn");
    els.palette = document.getElementById("palette");
    els.submit = document.getElementById("submit-btn");
    els.answered = document.getElementById("answered-count");
    els.timer = document.getElementById("q-timer");

    if (!attemptId) {
      showError("No attempt selected", "Open an assessment and start a quiz from there.");
      return;
    }

    STATE_KEY = "studymate:attempt:" + attemptId;

    global.StudyAPI.getAttempt(attemptId)
      .then(function (attempt) {
        if (!attempt || attempt.status !== "in_progress") {
          global.location.replace("results.html?attempt=" + encodeURIComponent(attemptId));
          return;
        }
        questions = attempt.questions || [];
        if (!questions.length) {
          showError("This attempt has no questions", "The assessment may have been deleted.");
          return;
        }

        var saved = loadState();
        var ids = questions.map(function (q) { return q.id; });
        if (saved && saved.ids && saved.ids.length === ids.length &&
            saved.ids.every(function (id, i) { return id === ids[i]; })) {
          state = saved;
        } else {
          state = { index: 0, answers: {}, flags: {}, remaining: null, ids: ids };
        }

        els.loading.hidden = true;
        els.body.hidden = false;
        els.title.textContent = "Assessment #" + (attempt.assessment_id || "");
        if (minutes > 0) {
          els.badges.innerHTML = '<span class="badge badge-primary">' + questions.length +
            " questions</span>" + '<span class="badge badge-neutral">' + minutes + " min limit</span>";
        } else {
          els.badges.innerHTML = '<span class="badge badge-primary">' + questions.length +
            " questions</span>" + '<span class="badge badge-neutral">No time limit</span>';
        }

        if (minutes > 0 && state.remaining == null) state.remaining = minutes * 60;

        bind();
        renderQuestion();
        startTimer();

        global.StudyAPI.getAssessment(attempt.assessment_id)
          .then(function (assessment) {
            if (assessment && assessment.title) els.title.textContent = assessment.title;
          })
          .catch(function () { /* title is optional */ });
      })
      .catch(function (err) {
        if (global.StudyApp.isAuthError(err)) return;
        showError(
          "Could not load this quiz",
          err && err.message ? err.message : "The attempt could not be found."
        );
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
