/* ==========================================================================
   StudyMate AI — Upload page: real upload + background indexing status.
   Files are sent to the local backend, extracted, embedded and indexed into
   the selected course. Status is polled until ready/failed.
   ========================================================================== */
(function (global) {
  "use strict";

  var queue = []; /* { file, status, message, materialId } */
  var uploading = false;
  var dz, input, listHost, emptyHost, queueCard, countLabel, courseSelect, courseHint, indexBtn;

  var STATUS_LABEL = {
    queued: "Queued",
    uploading: "Uploading…",
    pending: "Pending",
    processing: "Indexing…",
    ready: "Indexed",
    failed: "Failed"
  };
  var STATUS_CLASS = {
    queued: "badge-neutral",
    uploading: "badge-warn",
    pending: "badge-warn",
    processing: "badge-warn",
    ready: "badge-mastery",
    failed: "badge-danger"
  };

  var ALLOWED_EXT = { pdf: 1, pptx: 1, png: 1, jpg: 1, jpeg: 1, webp: 1, txt: 1, md: 1 };

  function extOf(name) {
    return (name.split(".").pop() || "").toLowerCase();
  }

  function fmtSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function iconFor(name) {
    var ext = (name.split(".").pop() || "").toLowerCase();
    if (ext === "pdf") return "pdf";
    if (["ppt", "pptx", "key"].indexOf(ext) >= 0) return "slides";
    if (["png", "jpg", "jpeg", "gif", "webp"].indexOf(ext) >= 0) return "image";
    if (["mp4", "mov", "webm", "mkv"].indexOf(ext) >= 0) return "video";
    return "file";
  }

  function busyStatus(status) {
    return status === "uploading" || status === "pending" || status === "processing";
  }

  function render() {
    var has = queue.length > 0;
    emptyHost.hidden = has;
    queueCard.hidden = !has;
    countLabel.textContent =
      queue.length + " file" + (queue.length > 1 ? "s" : "") + " in queue";

    listHost.innerHTML = queue.map(function (item, i) {
      var label = STATUS_LABEL[item.status] || item.status;
      var cls = STATUS_CLASS[item.status] || "badge-neutral";
      var detail = item.message
        ? '<span class="q-size">' + global.StudyUI.escapeHtml(item.message) + "</span>"
        : "";
      var actions = "";
      if (item.status === "failed") {
        actions += '<button class="btn btn-quiet btn-sm" data-retry="' + i + '">Retry</button>';
      }
      if (!busyStatus(item.status)) {
        actions += '<button class="btn btn-quiet btn-sm" data-remove="' + i + '">Remove</button>';
      }
      return (
        '<div class="queue-item">' +
        '<span class="item-icon primary" data-icon="' + iconFor(item.file.name) + '"></span>' +
        '<span class="stack" style="flex:1;min-width:0;gap:0">' +
        '<span class="q-name truncate">' + global.StudyUI.escapeHtml(item.file.name) + "</span>" +
        '<span class="q-size">' + fmtSize(item.file.size) + "</span>" +
        detail +
        "</span>" +
        '<span class="badge ' + cls + '">' + label + "</span>" +
        actions +
        "</div>"
      );
    }).join("");
    global.StudyIcons.hydrate(listHost);
  }

  function addFiles(fileList) {
    var added = 0;
    var rejected = [];
    Array.prototype.forEach.call(fileList, function (f) {
      var ext = extOf(f.name);
      if (!ALLOWED_EXT[ext]) {
        rejected.push(f.name);
        return;
      }
      var dup = queue.some(function (q) {
        return q.file.name === f.name && q.file.size === f.size;
      });
      if (!dup) {
        queue.push({ file: f, status: "queued", message: "", materialId: null });
        added += 1;
      }
    });
    render();
    if (rejected.length) {
      global.StudyUI.toast(
        rejected.length + " file(s) skipped — only .pdf, .pptx, .png, .jpg, .jpeg, .webp, .txt and .md are supported.",
        "warn"
      );
    } else if (added) {
      global.StudyUI.toast("Added to upload queue", "info");
    }
  }

  function setBusy(state) {
    if (indexBtn) indexBtn.disabled = state;
    if (courseSelect) courseSelect.disabled = state;
  }

  function upload() {
    if (uploading) return;
    var courseId = courseSelect.value;
    if (!courseId) {
      global.StudyUI.toast("Select a course before uploading.", "warn");
      return;
    }
    if (!sessionStorage.getItem("studymate:token")) {
      global.StudyUI.toast("Please sign in to upload materials.", "warn");
      setTimeout(function () { global.location.href = "login.html"; }, 1200);
      return;
    }
    var pending = queue.filter(function (q) {
      return q.status === "queued" || q.status === "failed";
    });
    if (!pending.length) {
      global.StudyUI.toast("Nothing queued to upload.", "info");
      return;
    }

    uploading = true;
    setBusy(true);

    var chain = Promise.resolve();
    pending.forEach(function (item) {
      chain = chain.then(function () {
        item.status = "uploading";
        item.message = "";
        render();
        return global.StudyAPI.uploadMaterial(courseId, item.file)
          .then(function (material) {
            item.materialId = material.id;
            item.status = material.processing_status || "pending";
            render();
            pollMaterial(item);
          })
          .catch(function (err) {
            item.status = "failed";
            item.message = err.message || "Upload failed";
            render();
          });
      });
    });

    function finish(message, tone) {
      if (!uploading) return;
      uploading = false;
      setBusy(false);
      global.StudyUI.toast(message, tone);
    }

    /* Re-enable the button on BOTH settle paths, so a failed or thrown
       upload can never leave it stuck disabled. */
    chain.then(
      function () {
        finish("Upload complete — indexing runs in the background.", "success");
      },
      function (err) {
        finish((err && err.message) || "Upload failed — please try again.", "warn");
      }
    );

    /* Safety net: if a request hangs and never settles, free the button. */
    setTimeout(function () {
      if (uploading) finish("Upload is taking too long — you can try again.", "warn");
    }, 180000);
  }

  function pollMaterial(item) {
    var attempts = 0;
    var maxAttempts = 80; /* ~2 minutes at 1.5s */

    function tick() {
      if (!item.materialId) return;
      global.StudyAPI.getMaterial(item.materialId)
        .then(function (material) {
          item.status = material.processing_status;
          if (material.processing_status === "ready") {
            item.message = material.content_unit_count + " chunks indexed";
          } else if (material.processing_status === "failed") {
            item.message =
              material.processing_error || "Processing failed — check the server log.";
          }
          render();
          if (material.processing_status === "pending" ||
              material.processing_status === "processing") {
            attempts += 1;
            if (attempts < maxAttempts) setTimeout(tick, 1500);
          }
        })
        .catch(function () {
          attempts += 1;
          if (attempts < maxAttempts) setTimeout(tick, 2000);
        });
    }
    setTimeout(tick, 1200);
  }

  /** Re-run indexing for a failed queue item (no re-upload needed). */
  function retryItem(index) {
    var item = queue[index];
    if (!item || !item.materialId || busyStatus(item.status)) return;
    item.status = "uploading";
    item.message = "Re-indexing…";
    render();
    global.StudyAPI.reprocessMaterial(item.materialId)
      .then(function () {
        item.message = "";
        pollMaterial(item);
      })
      .catch(function (err) {
        item.status = "failed";
        item.message = err.message || "Could not re-index this file.";
        render();
      });
  }

  function loadCourses() {
    global.StudyAPI.getCourses()
      .then(function (courses) {
        courseSelect.innerHTML = "";
        if (!courses.length) {
          var none = document.createElement("option");
          none.value = "";
          none.textContent = "No courses yet — create one first";
          courseSelect.appendChild(none);
          if (courseHint) {
            courseHint.innerHTML =
              'No courses yet — <a href="courses.html">create a course</a> first, then come back to upload.';
          }
          if (indexBtn) indexBtn.disabled = true;
          return;
        }
        var placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Select a course…";
        courseSelect.appendChild(placeholder);

        courses.forEach(function (course) {
          var option = document.createElement("option");
          option.value = course.id;
          option.textContent = course.title;
          courseSelect.appendChild(option);
        });

        var params = new URLSearchParams(global.location.search);
        var preselect = params.get("course") || params.get("course_id");
        if (preselect && courses.some(function (c) { return String(c.id) === String(preselect); })) {
          courseSelect.value = String(preselect);
        }
        if (courseHint) {
          courseHint.textContent =
            "Materials are extracted, embedded and indexed into the selected course.";
        }
        if (indexBtn) indexBtn.disabled = false;
      })
      .catch(function (err) {
        courseSelect.innerHTML = "";
        var option = document.createElement("option");
        option.value = "";
        option.textContent = /401/.test(err.message)
          ? "Sign in to select a course"
          : "Could not load courses";
        courseSelect.appendChild(option);
        if (indexBtn) indexBtn.disabled = true;
        global.StudyUI.toast(
          /401/.test(err.message)
            ? "Please sign in to load your courses."
            : "Could not load your courses — is the backend running?",
          "warn"
        );
      });
  }

  function init() {
    dz = document.getElementById("dropzone");
    input = document.getElementById("file-input");
    listHost = document.getElementById("queue-list");
    emptyHost = document.getElementById("queue-empty");
    queueCard = document.getElementById("queue-card");
    countLabel = document.getElementById("queue-count");
    courseSelect = document.getElementById("course-select");
    courseHint = document.getElementById("course-hint");
    indexBtn = document.getElementById("index-btn");

    dz.addEventListener("click", function () { input.click(); });
    input.addEventListener("change", function () { addFiles(input.files); input.value = ""; });

    ["dragenter", "dragover"].forEach(function (ev) {
      dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add("dragover"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove("dragover"); });
    });
    dz.addEventListener("drop", function (e) {
      if (e.dataTransfer && e.dataTransfer.files) addFiles(e.dataTransfer.files);
    });

    listHost.addEventListener("click", function (e) {
      var retry = e.target.closest("[data-retry]");
      if (retry) {
        if (uploading) { global.StudyUI.toast("Upload in progress…", "warn"); return; }
        retryItem(Number(retry.getAttribute("data-retry")));
        return;
      }
      var btn = e.target.closest("[data-remove]");
      if (!btn) return;
      var index = Number(btn.getAttribute("data-remove"));
      if (queue[index] && !busyStatus(queue[index].status)) {
        queue.splice(index, 1);
        render();
      }
    });

    var clear = document.getElementById("clear-queue");
    if (clear) {
      clear.addEventListener("click", function () {
        if (uploading) { global.StudyUI.toast("Upload in progress…", "warn"); return; }
        queue = [];
        render();
      });
    }

    if (indexBtn) indexBtn.addEventListener("click", upload);

    /* Choosing a course always makes the button usable again. */
    if (courseSelect) {
      courseSelect.addEventListener("change", function () {
        if (courseSelect.value && indexBtn) indexBtn.disabled = false;
      });
    }

    render();
    loadCourses();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
