/* ==========================================================================
   StudyMate AI — Flashcards: flip / navigate / grade a labeled EXAMPLE
   deck. Progress lives in memory for this session only.
   ========================================================================== */
(function (global) {
  "use strict";

  var deck = [
    {
      front: "What is the function of the mitochondrion?",
      back: "It produces ATP through cellular respiration — glycolysis feeds the citric acid cycle, and the electron transport chain on the inner membrane drives oxidative phosphorylation.",
      topic: "Cell biology"
    },
    {
      front: "Define 'selectively permeable' and name the structure that provides it.",
      back: "Selectively permeable means a barrier that allows some substances through and blocks others. In cells this is the plasma membrane — a phospholipid bilayer with transport proteins.",
      topic: "Membranes"
    },
    {
      front: "What happens in metaphase?",
      back: "Chromosomes line up along the cell equator (metaphase plate), attached to spindle fibres from opposite poles, ready for sister chromatids to separate in anaphase.",
      topic: "Cell division"
    },
    {
      front: "Prokaryote vs. eukaryote — the key structural difference?",
      back: "Prokaryotes have no membrane-bound nucleus or organelles (DNA sits in the nucleoid); eukaryotes package DNA inside a nucleus and compartmentalise organelles.",
      topic: "Cell biology"
    },
    {
      front: "Why is DNA the genetic material rather than protein?",
      back: "DNA is chemically stable, copies faithfully, and is sequenced by base-pairing rules; proteins cannot template themselves. Hershey–Chase and Avery–MacLeod–McCarty showed this experimentally.",
      topic: "Molecular biology"
    }
  ];

  var idx = 0;
  var known = 0;
  var again = 0;

  var cardEl, frontEl, backEl, posEl, knownEl, againEl, barEl, topicEl;

  function render() {
    var c = deck[idx];
    cardEl.classList.remove("flipped");
    /* force reflow so back-to-front on next tick animates correctly */
    void cardEl.offsetWidth;
    frontEl.textContent = c.front;
    backEl.textContent = c.back;
    topicEl.textContent = c.topic;
    posEl.textContent = (idx + 1) + " / " + deck.length;
    knownEl.textContent = known;
    againEl.textContent = again;
    barEl.style.width = ((idx + 1) / deck.length) * 100 + "%";
    document.getElementById("prev-card").disabled = idx === 0;
    document.getElementById("next-card").disabled = idx === deck.length - 1;
  }

  function flip() { cardEl.classList.toggle("flipped"); }

  function go(delta) {
    var next = idx + delta;
    if (next < 0 || next >= deck.length) return;
    idx = next;
    render();
  }

  function grade(kind) {
    if (kind === "known") {
      known += 1;
      global.StudyUI.toast("Marked as known", "success");
    } else {
      again += 1;
      global.StudyUI.toast("Queued for another pass", "warn");
    }
    if (idx < deck.length - 1) { go(1); }
    else {
      render();
      global.StudyUI.toast("Deck finished — " + known + " known, " + again + " to revisit", "success");
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

    cardEl.addEventListener("click", flip);
    cardEl.addEventListener("keydown", function (e) {
      if (e.key === " " || e.key === "Enter") { e.preventDefault(); flip(); }
    });

    document.getElementById("prev-card").addEventListener("click", function () { go(-1); });
    document.getElementById("next-card").addEventListener("click", function () { go(1); });
    document.getElementById("know-btn").addEventListener("click", function () { grade("known"); });
    document.getElementById("again-btn").addEventListener("click", function () { grade("again"); });

    document.addEventListener("keydown", function (e) {
      if (e.target.matches("input, textarea, button")) return;
      if (e.key === "ArrowLeft") go(-1);
      if (e.key === "ArrowRight") go(1);
      if (e.key === " " && !e.target.closest("#flashcard")) { e.preventDefault(); flip(); }
    });

    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
