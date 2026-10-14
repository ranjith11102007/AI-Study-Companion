/* ==========================================================================
   StudyMate AI — Settings: preferences persist to localStorage. Live backend
   facts come from health.js via [data-health-field].
   ========================================================================== */
(function (global) {
  "use strict";

  var LS_KEY = "studymate:prefs";

  function load() {
    try { return JSON.parse(localStorage.getItem(LS_KEY)) || {}; } catch (e) { return {}; }
  }

  function save(prefs) {
    try { localStorage.setItem(LS_KEY, JSON.stringify(prefs)); } catch (e) { /* ignore */ }
  }

  function init() {
    var prefs = load();

    var name = document.getElementById("display-name");
    if (name) {
      name.value = prefs.displayName || "";
      applyDisplayName(prefs.displayName);
      name.addEventListener("change", function () {
        prefs.displayName = name.value.trim();
        save(prefs);
        applyDisplayName(prefs.displayName);
        global.StudyUI.toast("Display name saved in this browser", "success");
      });
    }

    document.querySelectorAll("[data-pref]").forEach(function (el) {
      var key = el.getAttribute("data-pref");
      if (prefs[key] != null) el.checked = !!prefs[key];
      applyPref(key, el.checked);
      el.addEventListener("change", function () {
        prefs[key] = el.checked;
        applyPref(key, el.checked);
        save(prefs);
        global.StudyUI.toast("Preference saved in this browser", "success");
      });
    });

    document.getElementById("reset-prefs").addEventListener("click", function () {
      try { localStorage.removeItem(LS_KEY); } catch (e) { /* ignore */ }
      document.querySelectorAll("[data-pref]").forEach(function (el) {
        el.checked = false;
        applyPref(el.getAttribute("data-pref"), false);
      });
      if (name) name.value = "";
      applyDisplayName(null);
      global.StudyUI.toast("Local preferences cleared", "success");
    });
  }

  function applyPref(key, on) {
    if (key === "reduceMotion") {
      document.body.classList.toggle("reduce-motion", !!on);
    }
  }

  function applyDisplayName(displayName) {
    var label = document.getElementById("profile-label");
    if (label) label.textContent = displayName || "Local learner";
    if (displayName && displayName.trim()) {
      var initial = displayName.trim().charAt(0).toUpperCase();
      document.querySelectorAll(".avatar").forEach(function (av) { av.textContent = initial; });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
