/* ==========================================================================
   StudyMate AI — Sign-up page. Creates the account, then returns to sign in
   with the requested destination preserved.
   ========================================================================== */
(function (global) {
  "use strict";

  function loginLink() {
    var next = global.StudyApp ? global.StudyApp.safeNext(
      new URLSearchParams(global.location.search).get("next")
    ) : "";
    return "login.html" + (next ? "?next=" + encodeURIComponent(next) : "");
  }

  function init() {
    var form = document.getElementById("signup-form");
    if (!form) return;

    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var nameEl = document.getElementById("signup-name") || document.getElementById("name");
      var emailEl = document.getElementById("signup-email") || document.getElementById("email");
      var passwordEl = document.getElementById("signup-password") || document.getElementById("password");
      var name = nameEl ? nameEl.value.trim() : "";
      var email = emailEl ? emailEl.value.trim() : "";
      var password = passwordEl ? passwordEl.value : "";

      if (!name || !email || !password) {
        global.StudyUI.toast("Please fill in all fields.", "warn");
        return;
      }

      var button = form.querySelector('button[type="submit"]');
      if (button) button.disabled = true;

      try {
        await global.StudyAPI.signup({ name: name, email: email, password: password });
        global.StudyUI.toast("Account created — taking you to sign in…", "success");
        setTimeout(function () { global.location.href = loginLink(); }, 900);
      } catch (err) {
        if (button) button.disabled = false;
        global.StudyUI.toast(err && err.message ? err.message : "Signup failed.", "warn");
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
