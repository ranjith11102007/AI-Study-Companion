/* ==========================================================================
   StudyMate AI — Source viewer. Resolves ?unit=<content_unit_id> through
   GET /api/citations/{id} and renders the exact cited passage. Nothing is
   fabricated: an unresolvable citation shows an honest error state.
   ========================================================================== */
(function (global) {
  "use strict";

  function render(unit) {
    document.getElementById("source-loading").hidden = true;
    document.getElementById("source-error").hidden = true;
    document.getElementById("viewer").hidden = false;
    document.getElementById("source-actions").hidden = false;

    var title = unit.title || unit.location || "Cited passage";
    document.getElementById("viewer-title").textContent = unit.material_title || "Source viewer";
    document.getElementById("page-sub").textContent = title;
    document.getElementById("side-title").textContent = unit.material_title || "Source";
    document.getElementById("side-meta").textContent = unit.location || "excerpt";
    document.getElementById("side-location").textContent = unit.location || "excerpt";
    document.getElementById("side-type").textContent =
      (unit.material_type || "source") + " · " + (unit.content_type || "content");
    document.getElementById("toolbar-title").textContent = unit.material_title || "Source";
    document.getElementById("toolbar-type").textContent = unit.material_type || "source";
    document.getElementById("page-heading").textContent = unit.title || "Cited passage";
    document.getElementById("page-body").innerHTML =
      global.StudyApp.paragraphs(unit.content || "");

    if (unit.course_id != null) {
      var cid = encodeURIComponent(unit.course_id);
      document.getElementById("course-link").href = "course.html?id=" + cid;
      document.getElementById("crumb-course").href = "course.html?id=" + cid;
      document.getElementById("ask-link").href = "tutor.html?course=" + cid;
    }
    global.StudyIcons.hydrate(document);
  }

  function init() {
    var unitId = global.StudyApp.queryParam("unit");
    if (!unitId) {
      document.getElementById("source-loading").hidden = true;
      document.getElementById("source-error").hidden = false;
      document.getElementById("error-title").textContent = "No source selected";
      document.getElementById("error-text").textContent =
        "Open a citation from the tutor or a result to view its source passage here.";
      return;
    }

    global.StudyAPI.resolveCitation(unitId)
      .then(function (unit) {
        if (!unit) throw new Error("Source not found");
        render(unit);
      })
      .catch(function (err) {
        if (global.StudyApp.isAuthError(err)) return;
        document.getElementById("source-loading").hidden = true;
        document.getElementById("source-error").hidden = false;
        document.getElementById("error-title").textContent = "Source not found";
        document.getElementById("error-text").textContent =
          err && err.message ? err.message : "The cited passage could not be resolved.";
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
