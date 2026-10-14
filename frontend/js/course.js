/* ==========================================================================
   StudyMate AI — Course page. Everything shown (materials, topics, mastery,
   assessments, recommendations) comes from real endpoints for the course
   identified by ?id= (falling back to the active course).
   ========================================================================== */
(function (global) {
  "use strict";

  var App = global.StudyApp;
  var els = {};
  var courseId = null;
  var masteryByTopic = {};

  function esc(value) { return global.StudyUI.escapeHtml(value); }

  function showError(title, text) {
    els.loading.hidden = true;
    els.tabs.hidden = true;
    els.error.hidden = false;
    if (title) document.getElementById("course-error-title").textContent = title;
    if (text) document.getElementById("course-error-text").textContent = text;
  }

  function masteryTone(value) {
    var p = App.percent(value);
    if (p >= 75) return "mastery";
    if (p >= 50) return "amber";
    return "rose";
  }

  function masteryBadgeTone(value) {
    var tone = masteryTone(value);
    return tone === "mastery" ? "mastery" : tone === "amber" ? "warn" : "danger";
  }

  /* ---------------------------------------------------------------------- */
  /* Overview                                                               */
  /* ---------------------------------------------------------------------- */
  function renderOverview(mastery) {
    var topics = (mastery && mastery.topics) || [];
    document.getElementById("count-mastery").textContent = topics.length
      ? App.percent(topics.reduce(function (sum, t) { return sum + t.mastery; }, 0) / topics.length) + "%"
      : "–";

    var host = document.getElementById("overview-mastery");
    if (!topics.length) {
      host.innerHTML =
        '<div class="card-body"><p class="t-sm muted">No mastery data yet — take an assessment to start tracking.</p></div>';
      return;
    }
    host.innerHTML = topics.map(function (t) {
      var p = App.percent(t.mastery);
      var tone = masteryTone(t.mastery);
      return (
        '<div class="mastery-row">' +
        '<div class="mr-top">' +
        '<span class="mr-name"><span data-icon="target"></span> ' + esc(t.topic) + "</span>" +
        '<span class="mr-actions"><strong class="tnum ' + tone + '">' + p + "%</strong></span>" +
        "</div>" +
        '<div class="progress ' + tone + '"><span style="width:' + p + '%"></span></div>' +
        '<span class="mr-meta">' + t.correct_count + " of " + t.evidence_count + " correct" +
        (t.last_practiced_at ? " · last practised " + esc(global.StudyUI.timeLabel(t.last_practiced_at)) : "") +
        "</span></div>"
      );
    }).join("");
    global.StudyIcons.hydrate(host);
  }

  function renderNextAction(recommendations) {
    var rec = (recommendations || [])[0];
    var title = document.getElementById("next-action-title");
    var text = document.getElementById("next-action-text");
    var link = document.getElementById("next-action-link");
    if (!rec) {
      title.textContent = "No recommendation yet";
      text.textContent = "Complete an assessment and recommendations appear here.";
      link.hidden = true;
      return;
    }
    title.textContent = rec.topic || "Revision target";
    text.textContent = rec.reason || "";
    link.hidden = false;
    link.href = "tutor.html?course=" + encodeURIComponent(courseId) +
      (rec.topic ? "&q=" + encodeURIComponent("Explain " + rec.topic + " in detail.") : "");
    link.innerHTML = App.icon("chat") + " Review with tutor";
    global.StudyIcons.hydrate(link);
  }

  /* ---------------------------------------------------------------------- */
  /* Materials                                                              */
  /* ---------------------------------------------------------------------- */
  function renderMaterials(materials) {
    var host = document.getElementById("materials-list");
    var empty = document.getElementById("materials-empty");
    host.innerHTML = "";
    if (!materials || !materials.length) {
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    host.innerHTML = materials.map(function (m) {
      var status = App.materialStatus(m.processing_status);
      var reason = m.processing_error
        ? '<span class="item-sub" style="color:var(--rose-ink)">' +
          esc(m.processing_error) + "</span>"
        : "";
      var retry = m.processing_status === "failed"
        ? '<button class="btn btn-quiet btn-sm" data-reprocess-material="' + m.id + '">' +
          global.StudyUI.icon("refresh") + " Retry</button>"
        : "";
      return (
        '<div class="list-item">' +
        '<span class="item-icon primary" data-icon="' + App.materialIcon(m.material_type || m.filename) + '"></span>' +
        '<span class="item-main">' +
        '<span class="item-title">' + esc(m.original_filename) + "</span>" +
        '<span class="item-sub">' + esc(m.material_type || "file") + " · " +
        (m.content_unit_count || 0) + " chunks · added " + esc(global.StudyUI.timeLabel(m.created_at)) +
        "</span>" + reason + "</span>" +
        '<span class="item-end"><span class="badge ' + status.tone + '">' + status.label + "</span>" +
        retry +
        '<button class="btn btn-quiet btn-sm" data-delete-material="' + m.id + '" aria-label="Delete material">' +
        global.StudyUI.icon("trash") + "</button></span></div>"
      );
    }).join("");
    global.StudyIcons.hydrate(host);
  }

  /** Re-poll while any material is still pending/processing. */
  function pollMaterialsUntilSettled(attempts) {
    loadMaterials().then(function (list) {
      var busy = (list || []).some(function (m) {
        return m.processing_status === "pending" || m.processing_status === "processing";
      });
      if (busy && attempts > 0) {
        setTimeout(function () { pollMaterialsUntilSettled(attempts - 1); }, 1500);
      }
    });
  }

  /* ---------------------------------------------------------------------- */
  /* Topics                                                                 */
  /* ---------------------------------------------------------------------- */
  function renderTopics(topics) {
    var host = document.getElementById("topics-list");
    var empty = document.getElementById("topics-empty");
    host.innerHTML = "";
    if (!topics || !topics.length) {
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    host.innerHTML = topics.map(function (t) {
      var mastery = masteryByTopic[t.name.toLowerCase()];
      var masteryHtml = "";
      if (mastery) {
        masteryHtml = '<span class="badge badge-' + masteryBadgeTone(mastery) + '">' +
          App.percent(mastery) + "% mastery</span>";
      }
      return (
        '<div class="list-item">' +
        '<span class="item-icon primary" data-icon="target"></span>' +
        '<span class="item-main">' +
        '<span class="item-title">' + esc(t.name) + "</span>" +
        '<span class="item-sub">' +
        (t.description ? esc(t.description) + " · " : "") +
        (t.source_count || 0) + " linked source(s)" +
        (t.parent_name ? " · parent: " + esc(t.parent_name) : "") +
        "</span></span>" +
        '<span class="item-end">' + masteryHtml +
        '<button class="btn btn-quiet btn-sm" data-delete-topic="' + t.id + '" aria-label="Delete topic">' +
        global.StudyUI.icon("trash") + "</button></span></div>"
      );
    }).join("");
    global.StudyIcons.hydrate(host);
  }

  function renderSuggestions(suggestions, topics) {
    var host = document.getElementById("suggestions");
    var existing = {};
    (topics || []).forEach(function (t) { existing[(t.name || "").toLowerCase()] = true; });
    var fresh = (suggestions || []).filter(function (s) {
      return s && s.name && !existing[s.name.toLowerCase()];
    });
    if (!fresh.length) {
      host.innerHTML = '<p class="t-sm muted">No suggestions right now.</p>';
      return;
    }
    host.innerHTML = fresh.map(function (s) {
      return '<button class="chip" type="button" data-suggest="' + esc(s.name) + '">' +
        '<span data-icon="plus"></span> ' + esc(s.name) + "</button>";
    }).join("");
    global.StudyIcons.hydrate(host);
  }

  /* ---------------------------------------------------------------------- */
  /* Assessments                                                            */
  /* ---------------------------------------------------------------------- */
  function renderAssessments(list) {
    var host = document.getElementById("assessments-list");
    var empty = document.getElementById("assessments-empty");
    host.innerHTML = "";
    if (!list || !list.length) {
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    host.innerHTML = list.map(function (a) {
      return (
        '<div class="list-item">' +
        '<span class="item-icon mastery" data-icon="quiz"></span>' +
        '<span class="item-main">' +
        '<span class="item-title">' + esc(a.title) + "</span>" +
        '<span class="item-sub">' + a.question_count + " questions · " + esc(a.difficulty) +
        " · " + esc(timeLimitLabel(a.time_limit_minutes)) + " · " +
        esc(global.StudyUI.timeLabel(a.created_at)) +
        "</span></span>" +
        '<span class="item-end">' +
        '<button class="btn btn-primary btn-sm" data-start-assessment="' + a.id + '">Start</button>' +
        '<button class="btn btn-quiet btn-sm" data-delete-assessment="' + a.id + '" aria-label="Delete assessment">' +
        global.StudyUI.icon("trash") + "</button></span></div>"
      );
    }).join("");
    global.StudyIcons.hydrate(host);
  }

  function timeLimitLabel(minutes) {
    return minutes ? minutes + " min limit" : "No time limit";
  }

  /* ---------------------------------------------------------------------- */
  /* Loading                                                                */
  /* ---------------------------------------------------------------------- */
  function loadTopics() {
    return global.StudyAPI.listTopics(courseId).then(function (topics) {
      currentTopics = topics || [];
      renderTopics(currentTopics);
      return currentTopics;
    });
  }

  function loadSuggestions() {
    global.StudyAPI.suggestTopics(courseId)
      .then(function (suggestions) { renderSuggestions(suggestions, currentTopics); })
      .catch(function (err) {
        if (!App.isAuthError(err)) renderSuggestions([], currentTopics);
      });
  }

  function loadAssessments() {
    return global.StudyAPI.listAssessments(courseId).then(function (list) {
      renderAssessments(list || []);
      return list || [];
    });
  }

  function loadMaterials() {
    return global.StudyAPI.getMaterials(courseId).then(function (list) {
      renderMaterials(list || []);
      return list || [];
    });
  }

  function loadMastery() {
    return global.StudyAPI.getMastery(courseId).then(function (mastery) {
      masteryByTopic = {};
      ((mastery && mastery.topics) || []).forEach(function (t) {
        masteryByTopic[(t.topic || "").toLowerCase()] = t.mastery;
      });
      renderOverview(mastery || {});
      return mastery;
    }).catch(function (err) {
      if (App.isAuthError(err)) throw err;
      renderOverview({});
      return {};
    });
  }

  function loadRecommendations() {
    global.StudyAPI.getRecommendations(courseId)
      .then(function (recs) { renderNextAction(recs || []); })
      .catch(function (err) {
        if (!App.isAuthError(err)) renderNextAction([]);
      });
  }

  var currentTopics = [];

  /* ---------------------------------------------------------------------- */
  /* Init                                                                   */
  /* ---------------------------------------------------------------------- */
  function init() {
    els.loading = document.getElementById("course-loading");
    els.error = document.getElementById("course-error");
    els.tabs = document.getElementById("course-tabs");

    var qsId = App.queryParam("id");
    courseId = qsId ? parseInt(qsId, 10) : App.getCourse();
    if (!courseId || isNaN(courseId)) {
      showError("No course selected", "Pick a course from your course list to view it here.");
      return;
    }

    var upload = "upload.html?course=" + encodeURIComponent(courseId);
    var assess = "assessment.html?course=" + encodeURIComponent(courseId);
    var tutor = "tutor.html?course=" + encodeURIComponent(courseId);
    ["upload-link", "materials-upload-link", "materials-empty-btn"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.href = "upload.html?course=" + encodeURIComponent(courseId);
    });
    ["assess-link", "assess-new-link", "assessments-empty-btn"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.href = "assessment.html?course=" + encodeURIComponent(courseId);
    });
    var tutorLink = document.getElementById("tutor-link");
    if (tutorLink) tutorLink.href = "tutor.html?course=" + encodeURIComponent(courseId);

    global.StudyAPI.getCourse(courseId)
      .then(function (course) {
        if (!course) throw new Error("Course not found");
        App.setCourse(course.id);
        document.getElementById("course-title").textContent = course.title;
        document.getElementById("crumb-current").textContent = course.title;
        document.getElementById("course-sub").textContent =
          course.description || "Materials, topics and assessments for this course.";

        els.loading.hidden = true;
        els.tabs.hidden = false;
        global.StudyShell.bindCommon(document);

        return Promise.all([
          loadMaterials(),
          loadTopics(),
          loadAssessments(),
          loadMastery()
        ]).then(function (results) {
          document.getElementById("count-materials").textContent = results[0].length;
          document.getElementById("count-assessments").textContent = results[2].length;
          document.getElementById("count-topics").textContent = results[1].length;
          loadRecommendations();
          loadSuggestions();
        });
      })
      .catch(function (err) {
        if (App.isAuthError(err)) return;
        showError(
          "Could not load this course",
          err && err.message ? err.message : "The course could not be found."
        );
      });

    bindActions();
  }

  function bindActions() {
    var topicsHost = document.getElementById("topics-list");
    if (topicsHost) {
      topicsHost.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-delete-topic]");
        if (!btn) return;
        global.StudyAPI.deleteTopic(courseId, btn.getAttribute("data-delete-topic"))
          .then(function () { global.StudyUI.toast("Topic deleted.", "success"); loadTopics(); })
          .catch(function (err) { App.handleError(err, "Could not delete the topic."); });
      });
    }

    var suggestions = document.getElementById("suggestions");
    if (suggestions) {
      suggestions.addEventListener("click", function (e) {
        var chip = e.target.closest("[data-suggest]");
        if (!chip) return;
        global.StudyAPI.createTopic(courseId, { name: chip.getAttribute("data-suggest") })
          .then(function () {
            global.StudyUI.toast("Topic added.", "success");
            loadTopics().then(loadSuggestions);
          })
          .catch(function (err) { App.handleError(err, "Could not add the topic."); });
      });
    }

    var form = document.getElementById("topic-form");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var name = document.getElementById("topic-name").value.trim();
        var desc = document.getElementById("topic-desc").value.trim();
        if (!name) { global.StudyUI.toast("Give the topic a name.", "warn"); return; }
        global.StudyAPI.createTopic(courseId, { name: name, description: desc || null })
          .then(function () {
            global.StudyUI.toast("Topic added.", "success");
            form.reset();
            loadTopics().then(loadSuggestions);
          })
          .catch(function (err) { App.handleError(err, "Could not add the topic."); });
      });
    }

    var suggestBtn = document.getElementById("suggest-btn");
    if (suggestBtn) suggestBtn.addEventListener("click", loadSuggestions);

    var materials = document.getElementById("materials-list");
    if (materials) {
      materials.addEventListener("click", function (e) {
        var retry = e.target.closest("[data-reprocess-material]");
        if (retry) {
          retry.disabled = true;
          global.StudyAPI.reprocessMaterial(retry.getAttribute("data-reprocess-material"))
            .then(function () {
              global.StudyUI.toast("Re-indexing started…", "success");
              pollMaterialsUntilSettled(40);
            })
            .catch(function (err) {
              retry.disabled = false;
              App.handleError(err, "Could not re-index the material.");
            });
          return;
        }
        var btn = e.target.closest("[data-delete-material]");
        if (!btn) return;
        if (!global.confirm("Delete this material and its indexed chunks?")) return;
        global.StudyAPI.deleteMaterial(btn.getAttribute("data-delete-material"))
          .then(function () { global.StudyUI.toast("Material deleted.", "success"); loadMaterials(); })
          .catch(function (err) { App.handleError(err, "Could not delete the material."); });
      });
    }

    var assessments = document.getElementById("assessments-list");
    if (assessments) {
      assessments.addEventListener("click", function (e) {
        var start = e.target.closest("[data-start-assessment]");
        if (start) {
          global.StudyAPI.startAttempt(start.getAttribute("data-start-assessment"))
            .then(function (attempt) {
              global.location.href = "quiz.html?attempt=" + encodeURIComponent(attempt.attempt_id) +
                "&course=" + encodeURIComponent(courseId);
            })
            .catch(function (err) { App.handleError(err, "Could not start the assessment."); });
          return;
        }
        var del = e.target.closest("[data-delete-assessment]");
        if (!del) return;
        if (!global.confirm("Delete this assessment and its questions?")) return;
        global.StudyAPI.deleteAssessment(del.getAttribute("data-delete-assessment"))
          .then(function () {
            document.getElementById("count-assessments").textContent =
              Math.max(0, Number(document.getElementById("count-assessments").textContent) - 1);
            global.StudyUI.toast("Assessment deleted.", "success");
            loadAssessments();
          })
          .catch(function (err) { App.handleError(err, "Could not delete the assessment."); });
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
