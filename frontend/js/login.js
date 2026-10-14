/* ==========================================================================
   StudyMate AI — Sign-in page. Verifies credentials against the backend,
   stores the issued session token and continues to the requested page.
   ========================================================================== */
(function (global) {
  "use strict";

  function target() {
    var next = global.StudyApp ? global.StudyApp.safeNext(
      new URLSearchParams(global.location.search).get("next")
    ) : "";
    return next || "dashboard.html";
  }

  function init() {
    var form = document.getElementById("signin-form");
    if (!form) return;

    /* Already signed in? Skip the form. */
    if (global.StudyApp && global.StudyApp.isAuthed()) {
      global.location.replace(target());
      return;
    }

    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var email = document.getElementById("signin-email") || document.getElementById("email");
      var password = document.getElementById("signin-password") || document.getElementById("password");

      if (!email || !password || !email.value.trim() || !password.value) {
        global.StudyUI.toast("Enter an email and password to continue.", "warn");
        var focusEl = (!email || !email.value.trim()) ? email : password;
        if (focusEl && focusEl.focus) focusEl.focus();
        return;
      }

      var button = form.querySelector('button[type="submit"]');
      if (button) button.disabled = true;

      try {
        var result = await global.StudyAPI.signin({
          email: email.value.trim(),
          password: password.value
        });
        global.StudyApp.setToken(result.access_token);
        global.StudyUI.toast("Signed in successfully!", "success");
        global.location.href = target();
      } catch (err) {
        if (button) button.disabled = false;
        var message = err && err.message ? err.message : "Sign in failed.";
        global.StudyUI.toast(message, "warn");
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
