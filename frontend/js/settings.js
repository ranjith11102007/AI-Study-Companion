/* ==========================================================================
   StudyMate AI — Settings: profile and preferences are stored on the account.
   Live backend facts still come from health.js via [data-health-field].
   ========================================================================== */
(function (global) {
  "use strict";

  var LS_KEY = "studymate:prefs";

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

  function savePrefLocal(key, value) {
    var prefs = {};
    try { prefs = JSON.parse(localStorage.getItem(LS_KEY) || "{}") || {}; } catch (e) { prefs = {}; }
    prefs[key] = value;
    try { localStorage.setItem(LS_KEY, JSON.stringify(prefs)); } catch (e) { /* ignore */ }
  }

  function init() {
    // Apply the cached motion preference immediately, so the page does not
    // animate before the (async) profile fetch resolves.
    try {
      var cached = JSON.parse(localStorage.getItem(LS_KEY) || "{}") || {};
      if (cached.reduceMotion != null) applyPref("reduceMotion", cached.reduceMotion);
    } catch (e) { /* ignore */ }

    // ---- Profile from the server (single source of truth) -----------------
    global.StudyAPI.getProfile().then(function (profile) {
      if (!profile) return;

      var name = document.getElementById("display-name");
      if (name) name.value = profile.display_name || "";

      applyDisplayName(profile.display_name || profile.name);

      var emailEl = document.getElementById("account-email");
      if (emailEl) {
        var verified = profile.email_verified ? " · verified" : " · unverified";
        emailEl.textContent = profile.email + verified;
      }
      var created = document.getElementById("account-created");
      if (created && profile.created_at) created.textContent = "Account created " + App.timeLabel(profile.created_at);

      var verifyRow = document.getElementById("verify-row");
      var verifyBtn = document.getElementById("verify-request-btn");
      var verifyStatus = document.getElementById("verify-status");
      if (verifyRow) {
        if (profile.email_verified) {
          verifyRow.hidden = true;
          if (verifyStatus) { verifyStatus.hidden = false; verifyStatus.textContent = "Email verified."; }
        } else {
          verifyRow.hidden = false;
          if (verifyBtn) verifyBtn.addEventListener("click", function () {
            global.StudyAPI.verifyEmailRequest().then(function () {
              global.StudyUI.toast("Verification link sent (if email delivery is configured).", "success");
            }).catch(function (err) { App.handleError(err, "Could not request verification."); });
          });
        }
      }

      var prefs = profile.preferences || {};
      var reduceMotion = document.querySelector('[data-pref="reduceMotion"]');
      if (reduceMotion) reduceMotion.checked = !!prefs.reduceMotion;
      applyPref("reduceMotion", !!prefs.reduceMotion);
      savePrefLocal("reduceMotion", !!prefs.reduceMotion);

      // Other prefs (compact, reminders) are not wired to the backend yet —
      // keep their localStorage behaviour for those two.
      var prefsLocal = loadLocal();
      document.querySelectorAll("[data-pref]").forEach(function (el) {
        var key = el.getAttribute("data-pref");
        if (key === "reduceMotion") return;
        if (prefsLocal[key] != null) el.checked = !!prefsLocal[key];
        applyPref(key, el.checked);
      });
    }).catch(function (err) {
      if (App.isAuthError(err)) return;
      App.handleError(err, "Could not load your profile.");
    });

    // ---- Display name -> server ------------------------------------------
    var name = document.getElementById("display-name");
    if (name) {
      name.addEventListener("change", function () {
        var value = name.value.trim();
        global.StudyAPI.updateProfile({ display_name: value })
          .then(function () {
            applyDisplayName(value);
            global.StudyUI.toast("Profile saved.", "success");
          })
          .catch(function (err) { App.handleError(err, "Could not save the profile."); });
      });
    }

    // ---- Reduce motion -> server + local cache ----------------------------
    var rm = document.querySelector('[data-pref="reduceMotion"]');
    if (rm) {
      rm.addEventListener("change", function () {
        var on = !!rm.checked;
        global.StudyAPI.updateProfile({ preferences: { reduceMotion: on } })
          .then(function () {
            savePrefLocal("reduceMotion", on);
            applyPref("reduceMotion", on);
            global.StudyUI.toast("Preference saved.", "success");
          })
          .catch(function (err) { App.handleError(err, "Could not save the preference."); });
      });
    }

    // ---- Other (localStorage-only) prefs ---------------------------------
    document.querySelectorAll("[data-pref]").forEach(function (el) {
      var key = el.getAttribute("data-pref");
      if (key === "reduceMotion") return;
      if (key === "compact" || key === "reminders") return;
      var prefsLocal = loadLocal();
      if (prefsLocal[key] != null) el.checked = !!prefsLocal[key];
      applyPref(key, el.checked);
      el.addEventListener("change", function () {
        prefsLocal[key] = el.checked;
        applyPref(key, el.checked);
        saveLocal(prefsLocal);
        global.StudyUI.toast("Preference saved in this browser.", "success");
      });
    });

    // ---- Reset local preferences -----------------------------------------
    var resetBtn = document.getElementById("reset-prefs");
    if (resetBtn) {
      resetBtn.addEventListener("click", function () {
        try { localStorage.removeItem(LS_KEY); } catch (e) { /* ignore */ }
        document.querySelectorAll("[data-pref]").forEach(function (el) {
          el.checked = false;
          applyPref(el.getAttribute("data-pref"), false);
        });
        if (name) name.value = "";
        applyDisplayName(null);
        global.StudyAPI.updateProfile({ preferences: {} }).catch(function () { /* best effort */ });
        global.StudyUI.toast("Local preferences cleared.", "success");
      });
    }

    // data-todo switches.
    document.querySelectorAll("[data-todo]").forEach(function (el) {
      el.addEventListener("change", function () {
        el.checked = el.defaultChecked;
        global.StudyUI.toast(el.getAttribute("data-todo"), "warn");
      });
    });
  }

  function loadLocal() {
    try { return JSON.parse(localStorage.getItem(LS_KEY) || "{}") || {}; } catch (e) { return {}; }
  }
  function saveLocal(prefs) {
    try { localStorage.setItem(LS_KEY, JSON.stringify(prefs)); } catch (e) { /* ignore */ }
  }

  var App = global.StudyApp;

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})(window);
