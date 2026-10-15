/* ==========================================================================
   StudyMate AI — Courses index. Lists the signed-in user's real courses and
   creates / edits / deletes them via the Course API. Nothing is fabricated.
   ========================================================================== */
(function (global) {
  "use strict";

  var App = global.StudyApp;
  var grid, emptyState, modal, form, createBtn, emptyBtn, closeBtn;
  var modalTitle;
  var editingId = null;

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
      '<span class="row" style="gap:6px;margin-left:auto">' +
        '<button class="btn btn-quiet btn-sm" data-edit="' + course.id + '" aria-label="Edit course">' + App.icon("pencil") + '</button>' +
        '<button class="btn btn-quiet btn-sm" data-delete="' + course.id + '" aria-label="Delete course">' + App.icon("trash") + '</button>' +
      "</span>" +
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

    card.querySelector("a[href^='course.html']").addEventListener("click", function () { App.setCourse(course.id); });

    var editBtn = card.querySelector('[data-edit]');
    if (editBtn) editBtn.addEventListener("click", function () { openEditModal(course); });
    var delBtn = card.querySelector('[data-delete]');
    if (delBtn) delBtn.addEventListener("click", function () { deleteCourse(course); });

    return card;
  }

  function render(courses) {
    if (!grid) return;
    grid.innerHTML = "";
    if (!courses || !courses.length) { setEmpty(true); return; }
    setEmpty(false);
    courses.forEach(function (course) { grid.appendChild(courseCard(course)); });
    global.StudyIcons.hydrate(grid);
  }

  function loadCourses() {
    if (!grid) return;
    if (!App.isAuthed()) return;
    return global.StudyAPI.getCourses()
      .then(function (courses) { render(courses || []); })
      .catch(function (err) {
        setEmpty(true);
        if (emptyState) {
          var title = emptyState.querySelector(".state-title");
          var text = emptyState.querySelector(".state-text");
          if (title) title.textContent = App.isAuthError(err) ? "Please sign in again" : "Could not load your courses";
          if (text) text.textContent = App.isAuthError(err) ? "Your session has expired." :
            (err && err.message ? err.message : "The backend could not be reached.");
        }
        App.handleError(err, "Could not load your courses.");
      });
  }

  function openModal() {
    editingId = null;
    if (modalTitle) modalTitle.textContent = "Create New Course";
    var submit = form ? form.querySelector('button[type="submit"]') : null;
    if (submit) submit.textContent = "Create";
    if (form) form.reset();
    if (!modal) return;
    if (typeof modal.showModal === "function") modal.showModal();
    else modal.setAttribute("open", "");
  }

  function openEditModal(course) {
    editingId = course.id;
    if (modalTitle) modalTitle.textContent = "Edit Course";
    var submit = form ? form.querySelector('button[type="submit"]') : null;
    if (submit) submit.textContent = "Save";
    if (form) {
      var titleEl = document.getElementById("course-title");
      var descEl = document.getElementById("course-desc");
      if (titleEl) titleEl.value = course.title || "";
      if (descEl) descEl.value = course.description || "";
    }
    if (!modal) return;
    if (typeof modal.showModal === "function") modal.showModal();
    else modal.setAttribute("open", "");
  }

  function closeModal() {
    if (!modal) return;
    if (typeof modal.close === "function") modal.close();
    else modal.removeAttribute("open");
    editingId = null;
  }

  function deleteCourse(course) {
    if (!window.confirm("Delete \"" + course.title + "\" and all of its materials, topics and questions? This cannot be undone.")) return;
    global.StudyAPI.deleteCourse(course.id)
      .then(function () {
        global.StudyUI.toast("Course deleted.", "success");
        loadCourses();
      })
      .catch(function (err) { App.handleError(err, "Could not delete the course."); });
  }

  function init() {
    grid = document.getElementById("courses-grid");
    emptyState = document.getElementById("empty-state");
    modal = document.getElementById("new-course-modal");
    form = document.getElementById("new-course-form");
    createBtn = document.getElementById("new-course-btn");
    emptyBtn = document.getElementById("empty-state-btn");
    closeBtn = document.getElementById("close-modal");
    modalTitle = document.getElementById("modal-title");

    if (createBtn) createBtn.addEventListener("click", openModal);
    if (emptyBtn) emptyBtn.addEventListener("click", openModal);
    if (closeBtn) closeBtn.addEventListener("click", function () { modal.close(); closeModal(); });

    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var title = (document.getElementById("course-title").value || "").trim();
        if (!title) {
          global.StudyUI.toast("Give the course a title first.", "warn");
          return;
        }
        var submit = form.querySelector('button[type="submit"]');
        if (submit) submit.disabled = true;
        var payload = {
          title: title,
          description: (document.getElementById("course-desc").value || "").trim() || null
        };

        var op = editingId
          ? global.StudyAPI.updateCourse(editingId, payload)
          : global.StudyAPI.createCourse(payload);

        op.then(function (course) {
          if (modal && modal.close) modal.close();
          form.reset();
          editingId = null;
          App.setCourse(course.id);
          global.StudyUI.toast(editingId ? "Course updated." : "Course created.", "success");
          return loadCourses();
        }).catch(function (err) {
          App.handleError(err, editingId ? "Could not update the course." : "Could not create the course.");
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
