/* ==========================================================================
   StudyMate AI — Flashcards: real decks from /api/flashcards, spaced review.
   No hardcoded example data.
   ========================================================================== */
(function (global) {
  "use strict";

  var deck = [];
  var idx = 0;
  var courseId = null;
  var courseTitle = null;

  var cardEl, frontEl, backEl, posEl, knownEl, againEl, barEl, topicEl;
  var courseSelect, generateBtn, generateStatus;

  function esc(s) { return global.StudyApp.escapeHtml(s || ""); }

  function render() {
    if (!deck.length) {
      frontEl.textContent = "No cards yet — generate a deck from a course.";
      backEl.textContent = "";
      topicEl.textContent = "";
      posEl.textContent = "0 / 0";
      knownEl.textContent = "0";
      againEl.textContent = "0";
      barEl.style.width = "0%";
      if (cardEl) cardEl.classList.remove("flipped");
      if (cardEl) cardEl.disabled = true;
      return;
    }
    var c = deck[idx];
    if (cardEl) cardEl.classList.remove("flipped");
    void cardEl.offsetWidth;
    frontEl.textContent = c.front;
    backEl.textContent = c.back;
    topicEl.textContent = c.topic || "—";
    posEl.textContent = (idx + 1) + " / " + deck.length;
    knownEl.textContent = String(c.correct_count || 0);
    againEl.textContent = String(c.wrong_count || 0);
    var pct = deck.length ? ((idx + 1) / deck.length) * 100 : 0;
    barEl.style.width = pct + "%";
    if (document.getElementById("prev-card")) {
      document.getElementById("prev-card").disabled = idx === 0;
      document.getElementById("next-card").disabled = idx === deck.length - 1;
    }
    if (cardEl) cardEl.disabled = false;
  }

  function flip() { if (cardEl) cardEl.classList.toggle("flipped"); }

  function go(delta) {
    var next = idx + delta;
    if (next < 0 || next >= deck.length) return;
    idx = next;
    render();
  }

  async function grade(kind) {
    if (!deck.length) return;
    var card = deck[idx];
    try {
      var r = await global.StudyAPI.flashcards.review(card.id, kind === "known");
      if (!r.ok) { global.StudyUI.toast("Review failed: " + (r.detail || "error"), "danger"); return; }
      var updated = await r.json();
      // Update local copy
      deck[idx] = updated;
      if (kind === "known") {
        global.StudyUI.toast("Marked as known", "success");
      } else {
        global.StudyUI.toast("Queued for another pass", "warn");
      }
      if (idx < deck.length - 1) { go(1); }
      else { render(); global.StudyUI.toast("Deck finished.", "success"); }
    } catch (e) {
      global.StudyUI.toast("Could not save review.", "danger");
    }
  }

  async function loadCourseList() {
    try {
      var courses = await global.StudyAPI.getCourses();
      if (!courseSelect) return;
      courseSelect.innerHTML = '<option value="">Select a course…</option>' +
        courses.map(function (c) {
          return '<option value="' + c.id + '">' + esc(c.title) + '</option>';
        }).join("");
    } catch (e) {
      global.StudyUI.toast("Could not load courses.", "danger");
    }
  }

  async function loadDeck() {
    if (!courseId) { deck = []; render(); return; }
    try {
      var data = await global.StudyAPI.flashcards.list(courseId);
      deck = data || [];
      idx = 0;
      render();
    } catch (e) {
      global.StudyUI.toast("Could not load flashcards.", "danger");
      deck = [];
      render();
    }
  }

  async function generateDeck() {
    if (!courseId) return;
    if (generateBtn) { generateBtn.disabled = true; generateBtn.textContent = "Generating…"; }
    if (generateStatus) { generateStatus.textContent = ""; generateStatus.hidden = true; }
    try {
      var r = await global.StudyAPI.flashcards.generate(courseId);
      if (!r.ok) {
        var err = await r.json().catch(function () { return {}; });
        throw new Error(err.detail || "Generation failed");
      }
      var cards = await r.json();
      if (cards.length === 0) {
        if (generateStatus) { generateStatus.textContent = "No cards produced — the course may need more indexed content."; generateStatus.hidden = false; }
        return;
      }
      deck = cards;
      idx = 0;
      render();
      if (generateStatus) { generateStatus.textContent = "Generated " + cards.length + " cards."; generateStatus.hidden = false; }
    } catch (e) {
      if (generateStatus) { generateStatus.textContent = e.message; generateStatus.hidden = false; }
      global.StudyUI.toast("Could not generate deck: " + e.message, "danger");
    } finally {
      if (generateBtn) { generateBtn.disabled = false; generateBtn.textContent = "Generate deck"; }
    }
  }

  function init() {
    cardEl = document.getElementById("flashcard");
    frontEl = document.getElementById("flash-front");
    backEl = document.getElementById("flash-back");
    posEl = document.getElementById("flash-pos");
    knownEl = document.getElementById("flash-known");
    againEl = document.getElementById("flash-again");
    barEl = document.getElementById("flash-bar");
    topicEl = document.getElementById("flash-topic");
    courseSelect = document.getElementById("course-select");
    generateBtn = document.getElementById("generate-btn");
    generateStatus = document.getElementById("generate-status");

    if (cardEl) {
      cardEl.addEventListener("click", flip);
      cardEl.addEventListener("keydown", function (e) {
        if (e.key === " " || e.key === "Enter") { e.preventDefault(); flip(); }
      });
    }
    if (document.getElementById("prev-card")) {
      document.getElementById("prev-card").addEventListener("click", function () { go(-1); });
      document.getElementById("next-card").addEventListener("click", function () { go(1); });
      document.getElementById("know-btn").addEventListener("click", function () { grade("known"); });
      document.getElementById("again-btn").addEventListener("click", function () { grade("again"); });
    }

    if (courseSelect) {
      courseSelect.addEventListener("change", function () {
        courseId = courseSelect.value ? parseInt(courseSelect.value, 10) : null;
        loadDeck();
      });
      loadCourseList();
    }

    if (generateBtn) generateBtn.addEventListener("click", generateDeck);

    document.addEventListener("keydown", function (e) {
      if (e.target.matches("input, textarea, button, select")) return;
      if (e.key === "ArrowLeft") go(-1);
      if (e.key === "ArrowRight") go(1);
      if (e.key === " " && !e.target.closest("#flashcard")) { e.preventDefault(); flip(); }
    });

    loadDeck();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

})(window);