/* ==========================================================================
   StudyMate AI — Courses index. Lists the signed-in user's real courses and
   creates new ones via POST /api/courses/.
   ========================================================================== */
(function (global) {
  "use strict";

  var App = global.StudyApp;
  var grid, emptyState, modal, form, createBtn, emptyBtn, closeBtn;

  function setEmpty(show) {
    if (emptyState) emptyState.hidden = !show;
    if (grid) grid.hidden = show;
  }

  function courseCard(course) {
    var card = document.createElement("div");
    card.className = "rev-card";
    card.innerHTML =
      '<div class="rev-top">' +
      '<span class="tile-icon" data-icon="book"></span>' +
      '<span class="badge badge-neutral">ID ' + App.escapeHtml(course.id) + "</span>" +
      "</div>" +
      '<div class="stack stack-xs">' +
      '<strong class="t-h3">' + App.escapeHtml(course.title) + "</strong>" +
      '<p class="t-sm muted">' +
      App.escapeHtml(course.description || "No description yet.") +
      "</p>" +
      "</div>" +
      '<p class="t-sm muted">Created ' + App.escapeHtml(App.timeLabel(course.created_at)) + "</p>" +
      '<a class="btn btn-ghost btn-block" href="course.html?id=' + encodeURIComponent(course.id) + '">' +
      "Open course " + App.icon("arrowRight") + "</a>";

    var link = card.querySelector("a[href^='course.html']");
    if (link) {
      link.addEventListener("click", function () { App.setCourse(course.id); });
    }
    return card;
  }

  function render(courses) {
    if (!grid) return;
    grid.innerHTML = "";
    if (!courses || !courses.length) {
      setEmpty(true);
      return;
    }
    setEmpty(false);
    courses.forEach(function (course) {
      grid.appendChild(courseCard(course));
    });
    global.StudyIcons.hydrate(grid);
  }

  function loadCourses() {
    if (!grid) return;
    if (!App.isAuthed()) return; /* shell guard already redirected */
    return global.StudyAPI.getCourses()
      .then(function (courses) { render(courses || []); })
      .catch(function (err) {
        setEmpty(true);
        if (emptyState) {
          var title = emptyState.querySelector(".state-title");
          var text = emptyState.querySelector(".state-text");
          if (title) title.textContent = App.isAuthError(err)
            ? "Please sign in again" : "Could not load your courses";
          if (text) text.textContent = App.isAuthError(err)
            ? "Your session has expired."
            : (err && err.message ? err.message : "The backend could not be reached.");
        }
        App.handleError(err, "Could not load your courses.");
      });
  }

  function openModal() {
    if (!modal) return;
    if (typeof modal.showModal === "function") modal.showModal();
    else modal.setAttribute("open", "");
  }

  function closeModal() {
    if (!modal) return;
    if (typeof modal.close === "function") modal.close();
    else modal.removeAttribute("open");
  }

  function init() {
    grid = document.getElementById("courses-grid");
    emptyState = document.getElementById("empty-state");
    modal = document.getElementById("new-course-modal");
    form = document.getElementById("new-course-form");
    createBtn = document.getElementById("new-course-btn");
    emptyBtn = document.getElementById("empty-state-btn");
    closeBtn = document.getElementById("close-modal");

    if (createBtn) createBtn.addEventListener("click", openModal);
    if (emptyBtn) emptyBtn.addEventListener("click", openModal);
    if (closeBtn) closeBtn.addEventListener("click", function () { modal.close(); });

    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var titleEl = document.getElementById("course-title");
        var descEl = document.getElementById("course-desc");
        var title = titleEl ? titleEl.value.trim() : "";
        if (!title) {
          global.StudyUI.toast("Give the course a title first.", "warn");
          return;
        }
        var submit = form.querySelector('button[type="submit"]');
        if (submit) submit.disabled = true;

        global.StudyAPI.createCourse({
          title: title,
          description: (document.getElementById("course-desc").value || "").trim() || null
        }).then(function (course) {
          if (modal && modal.close) modal.close();
          form.reset();
          App.setCourse(course.id);
          global.StudyUI.toast("Course created.", "success");
          return loadCourses();
        }).catch(function (err) {
          App.handleError(err, "Could not create the course.");
        }).then(function () {
          if (submit) submit.disabled = false;
        });
      });
    }

    loadCourses();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
