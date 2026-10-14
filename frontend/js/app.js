/* ==========================================================================
   StudyMate AI — Shared application layer.
   Session/token helpers, route guard, course selection, consistent error
   handling and small formatting helpers. Loaded after ui.js on every page
   that talks to the backend. Contains no API definitions (see api.js).
   ========================================================================== */
(function (global) {
  "use strict";

  var TOKEN_KEY = "studymate:token";
  var COURSE_KEY = "studymate:course";

  function ui() { return global.StudyUI; }

  /* ---------------------------------------------------------------------- */
  /* Session / token                                                        */
  /* ---------------------------------------------------------------------- */
  function getToken() {
    try { return sessionStorage.getItem(TOKEN_KEY); } catch (e) { return null; }
  }

  function setToken(token) {
    try {
      if (token) sessionStorage.setItem(TOKEN_KEY, token);
      else sessionStorage.removeItem(TOKEN_KEY);
    } catch (e) { /* storage unavailable */ }
  }

  function clearToken() {
    try { sessionStorage.removeItem(TOKEN_KEY); } catch (e) { /* ignore */ }
  }

  function isAuthed() { return !!getToken(); }

  /** A missing/expired token surfaces as 401 (or 403) from the backend. */
  function isAuthError(err) {
    return !!err && (err.status === 401 || err.status === 403);
  }

  /* ---------------------------------------------------------------------- */
  /* Navigation / guard                                                     */
  /* ---------------------------------------------------------------------- */
  function safeNext(next) {
    var value = String(next == null ? "" : next).trim();
    if (!value) return "";
    if (/^[a-z][a-z0-9+.-]*:/i.test(value)) return "";   /* has a scheme */
    if (value.indexOf("//") === 0) return "";              /* protocol-relative */
    if (value.charAt(0) === "\\") return "";               /* windows path */
    return value;
  }

  function currentRelative() {
    var path = global.location.pathname || "";
    var idx = path.lastIndexOf("/");
    var file = idx >= 0 ? path.slice(idx + 1) : path;
    return (file || "dashboard.html") + (global.location.search || "");
  }

  function loginUrl(next) {
    var target = safeNext(next) || safeNext(currentRelative()) || "dashboard.html";
    return "login.html?next=" + encodeURIComponent(target);
  }

  function gotoLogin(next) {
    global.location.href = loginUrl(next);
  }

  /** Returns true when a token exists; otherwise redirects to login. */
  function requireAuth() {
    if (isAuthed()) return true;
    gotoLogin();
    return false;
  }

  function signOut() {
    clearToken();
    global.location.href = "login.html";
  }

  /* ---------------------------------------------------------------------- */
  /* Error handling                                                         */
  /* ---------------------------------------------------------------------- */
  function errMessage(err, fallback) {
    if (isAuthError(err)) return "Your session has expired — please sign in again.";
    if (err && err.message) return err.message;
    return fallback || "Something went wrong.";
  }

  /**
   * Show a toast for an error and, when it is an auth error, clear the token
   * and return to the login page. Returns the message so callers can also
   * render it inline.
   */
  function handleError(err, fallback, opts) {
    opts = opts || {};
    var message = errMessage(err, fallback);
    if (ui() && ui().toast) ui().toast(message, "warn");
    if (isAuthError(err) && !opts.noRedirect) {
      clearToken();
      setTimeout(function () { gotoLogin(); }, 1200);
    }
    return message;
  }

  /* ---------------------------------------------------------------------- */
  /* Course selection (persisted in sessionStorage)                         */
  /* ---------------------------------------------------------------------- */
  function getCourse() {
    var raw;
    try { raw = sessionStorage.getItem(COURSE_KEY); } catch (e) { raw = null; }
    var n = raw == null ? NaN : parseInt(raw, 10);
    return isNaN(n) ? null : n;
  }

  function setCourse(id) {
    if (id == null || id === "") {
      try { sessionStorage.removeItem(COURSE_KEY); } catch (e) { /* ignore */ }
      return null;
    }
    var n = parseInt(id, 10);
    if (isNaN(n)) {
      try { sessionStorage.removeItem(COURSE_KEY); } catch (e) { /* ignore */ }
      return null;
    }
    try { sessionStorage.setItem(COURSE_KEY, String(n)); } catch (e) { /* ignore */ }
    return n;
  }

  function preferredCourseId(opts) {
    opts = opts || {};
    if (opts.preferId != null) return opts.preferId;
    var qs = new URLSearchParams(global.location.search).get("course");
    if (qs) return qs;
    return getCourse();
  }

  function fillCourseSelect(select, courses, opts) {
    opts = opts || {};
    select.innerHTML = "";
    if (!courses || !courses.length) {
      var none = document.createElement("option");
      none.value = "";
      none.textContent = opts.emptyLabel || "No courses yet";
      select.appendChild(none);
      select.disabled = true;
      if (opts.onEmpty) opts.onEmpty();
      return courses || [];
    }

    courses.forEach(function (course) {
      var option = document.createElement("option");
      option.value = String(course.id);
      option.textContent = course.title;
      select.appendChild(option);
    });
    select.disabled = false;

    var want = preferredCourseId(opts);
    var match = null;
    for (var i = 0; i < courses.length; i++) {
      if (String(courses[i].id) === String(want)) { match = courses[i]; break; }
    }
    select.value = String(match ? match.id : courses[0].id);
    setCourse(select.value);
    if (opts.onReady) opts.onReady(getCourse(), courses);
    return courses;
  }

  /**
   * Load the user's courses into <select>, restore the saved/query course and
   * persist changes. Bind a single change handler.
   */
  function mountCourseSelect(select, opts) {
    opts = opts || {};
    if (!select) return Promise.reject(new Error("No course selector"));

    if (select.getAttribute("data-course-bound") !== "1") {
      select.setAttribute("data-course-bound", "1");
      select.addEventListener("change", function () {
        setCourse(select.value);
        if (opts.onChange) opts.onChange(getCourse(), select);
      });
    }

    if (!global.StudyAPI || !global.StudyAPI.getCourses) {
      return Promise.reject(new Error("API layer not loaded"));
    }

    return global.StudyAPI.getCourses().then(function (courses) {
      fillCourseSelect(select, courses, opts);
      if (opts.onLoaded) opts.onLoaded(getCourse(), courses);
      return courses;
    }).catch(function (err) {
      select.innerHTML = "";
      var option = document.createElement("option");
      option.value = "";
      option.textContent = isAuthError(err)
        ? "Sign in to load courses"
        : "Could not load courses";
      select.appendChild(option);
      select.disabled = true;
      if (opts.onError) opts.onError(err);
      else handleError(err, "Could not load your courses.");
      throw err;
    });
  }

  /* ---------------------------------------------------------------------- */
  /* Formatting helpers                                                     */
  /* ---------------------------------------------------------------------- */
  function escapeHtml(value) {
    return ui() ? ui().escapeHtml(value) : String(value == null ? "" : value);
  }

  /** Plain-text answer → escaped paragraph HTML (blank line = paragraph). */
  function paragraphs(text) {
    return String(text == null ? "" : text)
      .split(/\n{2,}/)
      .map(function (block) {
        return "<p>" + escapeHtml(block).replace(/\n/g, "<br>") + "</p>";
      })
      .join("");
  }

  /** Location label for a citation/source record. */
  function citationLocation(item) {
    if (!item) return "excerpt";
    if (item.page_number != null) return "page " + item.page_number;
    if (item.slide_number != null) return "slide " + item.slide_number;
    if (item.start_timestamp != null) {
      var total = Math.round(item.start_timestamp);
      var m = Math.floor(total / 60);
      var s = total % 60;
      return "at " + m + ":" + (s < 10 ? "0" : "") + s;
    }
    return "excerpt";
  }

  function icon(name) {
    return ui() ? ui().icon(name) : "";
  }

  function timeLabel(iso) {
    return ui() ? ui().timeLabel(iso) : (iso || "—");
  }

  function percent(value) {
    var n = Number(value);
    return isNaN(n) ? 0 : Math.round(n * 100);
  }

  /** Read a single query-string parameter ("" when absent). */
  function queryParam(name) {
    try {
      return new URLSearchParams(global.location.search).get(name) || "";
    } catch (e) {
      return "";
    }
  }

  /** Build a link that carries the active course id when one is set. */
  function withCourse(page, courseId) {
    var id = courseId == null ? getCourse() : courseId;
    return id == null || id === "" ? page : page + (page.indexOf("?") >= 0 ? "&" : "?") + "course=" + encodeURIComponent(id);
  }

  /** Material processing status → badge tone + human label. */
  var MATERIAL_STATUS = {
    pending: { label: "Pending", tone: "badge-warn" },
    processing: { label: "Indexing…", tone: "badge-warn" },
    ready: { label: "Indexed", tone: "badge-mastery" },
    failed: { label: "Failed", tone: "badge-danger" }
  };

  function materialStatus(status) {
    return MATERIAL_STATUS[status] || { label: status || "Unknown", tone: "badge-neutral" };
  }

  /** Material type / filename → icon name available in icons.js. */
  function materialIcon(value) {
    var v = String(value == null ? "" : value).toLowerCase();
    if (v.indexOf("pdf") >= 0) return "pdf";
    if (v.indexOf("ppt") >= 0 || v.indexOf("slide") >= 0) return "slides";
    if (v.indexOf("video") >= 0 || v.indexOf("mp4") >= 0) return "video";
    if (v.indexOf("image") >= 0 || /\.(png|jpe?g|webp|gif)$/.test(v)) return "image";
    if (v.indexOf("txt") >= 0 || v.indexOf("md") >= 0 || v.indexOf("text") >= 0) return "file";
    return "file";
  }

  function providerTone(status) {
    if (status === "ok") return "mastery";
    if (status === "degraded") return "amber";
    return "rose";
  }

  function initialFrom(name) {
    var value = String(name == null ? "" : name).trim();
    return value ? value.charAt(0).toUpperCase() : "";
  }

  /** Read the locally-stored display name (settings.js writes it). */
  function displayName() {
    try {
      var prefs = JSON.parse(localStorage.getItem("studymate:prefs")) || {};
      return (prefs.displayName || "").trim();
    } catch (e) {
      return "";
    }
  }

  global.StudyApp = {
    TOKEN_KEY: TOKEN_KEY,
    COURSE_KEY: COURSE_KEY,
    getToken: getToken,
    setToken: setToken,
    clearToken: clearToken,
    isAuthed: isAuthed,
    isAuthError: isAuthError,
    safeNext: safeNext,
    currentRelative: currentRelative,
    loginUrl: loginUrl,
    gotoLogin: gotoLogin,
    requireAuth: requireAuth,
    signOut: signOut,
    errMessage: errMessage,
    handleError: handleError,
    getCourse: getCourse,
    setCourse: setCourse,
    fillCourseSelect: fillCourseSelect,
    mountCourseSelect: mountCourseSelect,
    escapeHtml: escapeHtml,
    paragraphs: paragraphs,
    citationLocation: citationLocation,
    icon: icon,
    timeLabel: timeLabel,
    percent: percent,
    queryParam: queryParam,
    withCourse: withCourse,
    materialStatus: materialStatus,
    materialIcon: materialIcon,
    displayName: displayName
  };
})(window);
