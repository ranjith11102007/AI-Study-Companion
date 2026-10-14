/* ==========================================================================
   StudyMate AI — Tutor page. Streams answers from POST /api/tutor/ask/stream
   (live retrieval → sources → tokens → citations) and falls back to the
   classic POST /api/tutor/ask while the streaming endpoint is not deployed.
   Talks to the conversation endpoints too. Nothing is fabricated: an answer
   that cannot be grounded in indexed material is shown with its real
   "insufficient" status.
   ========================================================================== */
(function (global) {
  "use strict";

  var App = global.StudyApp;
  var els = {};
  var conversationId = null;
  var busy = false;

  function esc(value) { return App.escapeHtml(value); }

  function setStatus(kind, text) {
    if (!els.status) return;
    els.status.className = "ai-pill " + (kind || "idle");
    var label = els.status.querySelector("[data-status-text]");
    if (label) label.textContent = text;
  }

  function scrollDown() {
    if (els.thread && !els.thread.hidden) {
      global.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
    }
  }

  function showEmpty(show) {
    if (els.empty) els.empty.hidden = !show;
    if (els.thread) els.thread.hidden = show;
  }

  function timeLabel() {
    return new Date().toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }

  function citationChip(c) {
    var loc = App.citationLocation(c);
    var excerpt = c.excerpt ? String(c.excerpt).slice(0, 100) : "";
    return '<a class="citation" href="source.html?unit=' +
      encodeURIComponent(c.content_unit_id) + '">' +
      '<span class="cite-icon" data-icon="' + App.materialIcon(c.material_type) + '"></span>' +
      '<span class="cite-main">' +
      '<span class="cite-name">' + esc(c.material_title || "Source") + "</span>" +
      '<span class="cite-ref">' + esc(loc) +
      (excerpt ? " · “" + esc(excerpt) + "…”" : "") + "</span>" +
      "</span>" +
      '<span class="cite-go">Open ' + App.icon("external") + "</span>" +
      "</a>";
  }

  function assistantBody(message) {
    var html = App.paragraphs(message.content || "");
    if (message.evidence_status === "insufficient") {
      html +=
        '<div class="banner banner-warn" style="margin-top:10px">' + App.icon("alert") +
        "<div><strong>Not in your sources.</strong> The tutor could not ground this " +
        "answer in the indexed material for this course.</div></div>";
    }
    var citations = message.citations || [];
    if (citations.length) {
      html += '<div class="citation-list">' + citations.map(citationChip).join("") + "</div>";
    }
    return html;
  }

  function appendUser(text) {
    var el = document.createElement("div");
    el.className = "msg msg-user";
    el.innerHTML =
      '<div class="msg-meta"><span>You</span><span>' + timeLabel() + "</span></div>" +
      '<div class="msg-bubble">' + esc(text) + "</div>";
    els.thread.appendChild(el);
  }

  function appendAssistant(message) {
    var el = document.createElement("div");
    el.className = "msg msg-ai";
    el.innerHTML =
      '<div class="msg-meta"><span class="ai-avatar">' + App.icon("sparkle") +
      "</span><span>StudyMate AI</span><span>" +
      (message.created_at ? esc(App.timeLabel(message.created_at)) : timeLabel()) +
      "</span></div>" +
      '<div class="msg-bubble">' + assistantBody(message) + "</div>";
    els.thread.appendChild(el);
    global.StudyIcons.hydrate(el);
    return el;
  }

  function appendPending() {
    var el = document.createElement("div");
    el.className = "msg msg-ai";
    el.innerHTML =
      '<div class="msg-meta"><span class="ai-avatar">' + App.icon("sparkle") +
      "</span><span>StudyMate AI</span>" +
      '<span class="msg-elapsed" data-elapsed></span></div>' +
      '<div class="msg-bubble"><span class="ai-pill warn" data-stream-pill>' +
      '<span class="dot6"></span><span data-stream-status>Searching your sources…</span></span></div>';
    els.thread.appendChild(el);
    global.StudyIcons.hydrate(el);
    return el;
  }

  function renderMessages(messages) {
    els.thread.innerHTML = "";
    (messages || []).forEach(function (message) {
      if (message.role === "user") {
        var el = document.createElement("div");
        el.className = "msg msg-user";
        el.innerHTML =
          '<div class="msg-meta"><span>You</span><span>' +
          esc(App.timeLabel(message.created_at)) + "</span></div>" +
          '<div class="msg-bubble">' + esc(message.content) + "</div>";
        els.thread.appendChild(el);
      } else {
        appendAssistant(message);
      }
    });
    showEmpty(!(message2Length = (els.thread.children || []).length));
  }

  var message2Length = 0;

  function newChat() {
    conversationId = null;
    els.thread.innerHTML = "";
    showEmpty(true);
    setStatus("idle", "Ready");
    if (els.threadTitle) els.threadTitle.textContent = "Tutor conversation";
    if (els.threadSub) els.threadSub.textContent = "Ask a question about the selected course.";
    highlightConversation(null);
    if (els.input) els.input.focus();
  }

  /* ---------------------------------------------------------------------- */
  /* Conversations rail                                                     */
  /* ---------------------------------------------------------------------- */
  function highlightConversation(id) {
    if (!els.conversationList) return;
    els.conversationList.querySelectorAll("[data-conversation]").forEach(function (row) {
      row.classList.toggle("active", String(row.getAttribute("data-conversation")) === String(id));
    });
  }

  function renderConversations(list) {
    if (!els.conversationList) return;
    if (!list || !list.length) {
      els.conversationList.innerHTML =
        '<div class="list-item"><span class="item-main">' +
        '<span class="item-title">No conversations yet</span>' +
        '<span class="item-sub">Ask a question to start one.</span></span></div>';
      return;
    }
    els.conversationList.innerHTML = list.map(function (c) {
      return '<div class="list-item" data-conversation="' + esc(c.id) + '">' +
        '<span class="item-icon primary" data-icon="chat"></span>' +
        '<span class="item-main">' +
        '<span class="item-title">' + esc(c.title || "Conversation") + "</span>" +
        '<span class="item-sub">' + esc(App.timeLabel(c.updated_at || c.created_at)) + "</span>" +
        "</span>" +
        '<span class="item-end">' +
        '<button class="btn btn-quiet btn-sm" data-open="' + esc(c.id) + '">Open</button>' +
        '<button class="btn btn-quiet btn-sm" data-delete="' + esc(c.id) + '" aria-label="Delete conversation">' +
        App.icon("trash") + "</button>" +
        "</span></div>";
    }).join("");
    global.StudyIcons.hydrate(els.conversationList);
  }

  function loadConversations() {
    var courseId = App.getCourse();
    if (!courseId) { renderConversations([]); return; }
    global.StudyAPI.listConversations(courseId)
      .then(function (list) { renderConversations(list || []); })
      .catch(function (err) {
        if (App.isAuthError(err)) return;
        renderConversations([]);
      });
  }

  function openConversation(id) {
    global.StudyAPI.getConversation(id).then(function (detail) {
      conversationId = detail.id;
      els.thread.innerHTML = "";
      if (detail.messages && detail.messages.length) {
        detail.messages.forEach(function (m) {
          if (m.role === "user") {
            var el = document.createElement("div");
            el.className = "msg msg-user";
            el.innerHTML = '<div class="msg-meta"><span>You</span><span>' +
              esc(App.timeLabel(m.created_at)) + "</span></div>" +
              '<div class="msg-bubble">' + esc(m.content) + "</div>";
            els.thread.appendChild(el);
          } else {
            appendAssistant(m);
          }
        });
        showEmpty(false);
      } else {
        showEmpty(true);
      }
      if (els.threadTitle) els.threadTitle.textContent = detail.title || "Conversation";
      if (els.threadSub) els.threadSub.textContent = "Course #" + detail.course_id;
      highlightConversation(id);
      scrollDown();
    }).catch(function (err) {
      App.handleError(err, "Could not open that conversation.");
    });
  }

  function deleteConversation(id) {
    if (!global.confirm("Delete this conversation?")) return;
    global.StudyAPI.deleteConversation(id).then(function () {
      if (String(id) === String(conversationId)) newChat();
      loadConversations();
      global.StudyUI.toast("Conversation deleted.", "success");
    }).catch(function (err) {
      App.handleError(err, "Could not delete the conversation.");
    });
  }

  /* ---------------------------------------------------------------------- */
  /* Asking                                                                 */
  /* ---------------------------------------------------------------------- */
  function ask(text) {
    var courseId = App.getCourse();
    if (!courseId) { global.StudyUI.toast("Select a course first.", "warn"); return; }
    if (!text.trim() || busy) return;

    busy = true;
    if (els.askBtn) els.askBtn.disabled = true;
    showEmpty(false);
    appendUser(text.trim());
    var bubble = appendPending();
    var t0 = Date.now();
    var timer = setInterval(updateElapsed, 1000);

    var ctx = {
      question: text.trim(),
      fullText: "",
      sourceCount: 0,
      previewCitations: [],
      finalCitations: [],
      evidenceStatus: null,
      sourcesConsidered: 0,
      conversationId: null,
      sawEvent: false,
      finished: false,
      bubble: bubble,
      t0: t0,
      timer: timer
    };

    function updateElapsed() {
      setElapsed(ctx, "");
    }

    // "Searching your sources…" -> "N sources found" -> "Writing answer…"
    function progress(text) {
      var label = ctx.bubble.querySelector("[data-stream-status]");
      if (label) label.textContent = text;
      setStatus("busy", text);
    }

    function finalizeStream(ev) {
      conversationId = ev.conversation_id;
      ctx.bubble.removeAttribute("data-streaming");
      var html = App.paragraphs(ctx.fullText);
      if (ev.evidence_status === "insufficient") {
        html +=
          '<div class="banner banner-warn" style="margin-top:10px">' + App.icon("alert") +
          "<div><strong>Not in your sources.</strong> The tutor could not ground this " +
          "answer in the indexed material for this course.</div></div>";
      }
      var citations = ev.citations && ev.citations.length ? ev.citations : ctx.previewCitations;
      if (citations.length) {
        html += '<div class="citation-list">' + citations.map(citationChip).join("") + "</div>";
      }
      var body = ctx.bubble.querySelector(".msg-bubble");
      if (body) body.innerHTML = html;
      global.StudyIcons.hydrate(ctx.bubble);

      if (els.threadTitle) els.threadTitle.textContent = ctx.question.slice(0, 60);
      if (els.threadSub) {
        els.threadSub.textContent = "Sources considered: " + (ev.sources_considered || 0);
      }
      setStatus(
        ev.evidence_status === "grounded" ? "ok" : "idle",
        ev.evidence_status === "grounded"
          ? "Grounded · " + citations.length + " citation(s)"
          : "Not in sources"
      );
      showEmpty(false);
      loadConversations();
      highlightConversation(conversationId);
      scrollDown();
    }

    function enterStreaming() {
      if (ctx.bubble.getAttribute("data-streaming") === "1") return;
      ctx.bubble.setAttribute("data-streaming", "1");
      var pill = ctx.bubble.querySelector("[data-stream-pill]");
      var host = document.createElement("div");
      host.className = "stream-caret";
      host.innerHTML = '<span data-stream-text></span><span class="caret"></span>';
      if (pill && pill.parentNode) pill.parentNode.replaceChild(host, pill);
      setStatus("busy", "Writing answer…");
    }

    // End the streamed bubble the normal way (onDone fired).
    function done(ev) {
      finalizeStream(ev);
      ctx.finished = true;
      clearInterval(ctx.timer);
      setElapsed(ctx, "done");
    }

    // Render an in-stream {"type":"error"} event.
    function streamError(ev) {
      ctx.finished = true;
      clearInterval(ctx.timer);
      setElapsed(ctx, "none");
      var body = ctx.bubble.querySelector(".msg-bubble");
      var detail = String(ev.status) === "503"
        ? "The local AI model (Ollama) is unavailable. Start Ollama and pull the configured model, then try again."
        : (ev.message || "The tutor could not answer right now.");
      if (body) {
        body.innerHTML = '<div class="banner banner-warn">' + App.icon("alert") +
          "<div>" + esc(detail) + "</div></div>";
      }
      global.StudyIcons.hydrate(ctx.bubble);
      setStatus("idle", "Error");
      App.handleError({ status: ev.status, message: ev.message }, detail);
    }

    // The stream resolved but never sent a `done` event.
    function earlyEnd() {
      ctx.finished = true;
      clearInterval(ctx.timer);
      setElapsed(ctx, "none");
      var body = ctx.bubble.querySelector(".msg-bubble");
      var html = ctx.fullText ? App.paragraphs(ctx.fullText) : "";
      html +=
        '<div class="banner banner-warn" style="margin-top:10px">' + App.icon("alert") +
        "<div><strong>Response ended early.</strong> The stream closed before the tutor " +
        "finished — this answer may be incomplete. Try again.</div></div>";
      if (body) body.innerHTML = html;
      global.StudyIcons.hydrate(ctx.bubble);
      setStatus("idle", "Ended early");
      if (els.threadSub) els.threadSub.textContent = "Stream ended before completion.";
    }

    // Keep the loaded answer but note that the stream dropped mid-way.
    function interrupted(err) {
      ctx.finished = true;
      clearInterval(ctx.timer);
      setElapsed(ctx, "none");
      var body = ctx.bubble.querySelector(".msg-bubble");
      var html = ctx.fullText ? App.paragraphs(ctx.fullText) : "";
      html +=
        '<div class="banner banner-warn" style="margin-top:10px">' + App.icon("alert") +
        "<div><strong>Connection lost.</strong> The answer stream was interrupted before it " +
        "finished. Please try again.</div></div>";
      if (body) body.innerHTML = html;
      global.StudyIcons.hydrate(ctx.bubble);
      setStatus("idle", "Interrupted");
      App.handleError(err, "The answer stream was interrupted.");
    }

    // Fallback when /api/tutor/ask/stream is not available yet: POST /api/tutor/ask.
    function fallback(payload) {
      return global.StudyAPI.askTutor(payload).then(function (result) {
        conversationId = result.conversation_id;
        var pending = ctx.bubble;
        if (pending && pending.parentNode) pending.parentNode.removeChild(pending);
        appendAssistant({
          content: result.answer,
          evidence_status: result.evidence_status,
          citations: result.citations,
          created_at: null
        });
        setStatus(
          result.evidence_status === "grounded" ? "ok" : "idle",
          result.evidence_status === "grounded"
            ? "Grounded · " + (result.citations || []).length + " citation(s)"
            : "Not in sources"
        );
        if (els.threadTitle) els.threadTitle.textContent = ctx.question.slice(0, 60);
        if (els.threadSub) {
          els.threadSub.textContent =
            "Sources considered: " + (result.sources_considered || 0) + " · answered in " +
            Math.round((Date.now() - ctx.t0) / 1000) + "s";
        }
        showEmpty(false);
        loadConversations();
        highlightConversation(conversationId);
        scrollDown();
        ctx.finished = true;
        clearInterval(ctx.timer);
      }).catch(function (err) {
        if (ctx.finished) return;
        renderReqError(err);
      });
    }

    function renderReqError(err) {
      ctx.finished = true;
      clearInterval(ctx.timer);
      setElapsed(ctx, "none");
      var pendingEl = els.thread.querySelector(".msg-ai:last-child");
      var detail = App.isAuthError(err)
        ? "Your session expired — please sign in again."
        : (err && err.status === 503)
          ? "The local AI model (Ollama) is unavailable. Start Ollama and pull the configured model, then try again."
          : (err && err.status === 0)
            ? "Could not reach the backend."
            : (err && err.message) || "The tutor could not answer right now.";
      if (pendingEl) {
        pendingEl.innerHTML =
          '<div class="msg-meta"><span class="ai-avatar">' + App.icon("alertCircle") +
          "</span><span>StudyMate AI</span></div>" +
          '<div class="msg-bubble"><div class="banner banner-warn">' + App.icon("alert") +
          "<div>" + esc(detail) + "</div></div></div>";
        global.StudyIcons.hydrate(pendingEl);
      }
      setStatus("idle", "Error");
      App.handleError(err, detail);
    }

    function setElapsed(ctx, mode) {
      var el = ctx.bubble.querySelector("[data-elapsed]");
      if (!el) return;
      if (mode === "done") {
        el.textContent = "· answered in " + Math.round((Date.now() - ctx.t0) / 1000) + "s";
      } else if (mode === "none") {
        el.textContent = "";
      } else {
        el.textContent = "· " + Math.round((Date.now() - ctx.t0) / 1000) + "s";
      }
    }

    var payload = {
      course_id: Number(courseId),
      question: ctx.question,
      conversation_id: conversationId
    };

    global.StudyAPI.streamTutor(payload, {
      onStatus: function (ev) {
        ctx.sawEvent = true;
        progress(ev.stage === "retrieving" ? "Searching your sources…" : "Working…");
      },
      onSources: function (ev) {
        ctx.sawEvent = true;
        ctx.sourceCount = ev.count || 0;
        ctx.previewCitations = ev.citations || [];
        progress(ctx.sourceCount > 0
          ? ctx.sourceCount + " source" + (ctx.sourceCount === 1 ? "" : "s") + " found"
          : "No sources found");
      },
      onToken: function (ev) {
        ctx.sawEvent = true;
        enterStreaming();
        ctx.fullText += ev.text;
        var node = ctx.bubble.querySelector("[data-stream-text]");
        if (node) node.textContent = ctx.fullText;
        scrollDown();
      },
      onDone: function (ev) {
        ctx.sawEvent = true;
        done(ev);
      },
      onError: function (ev) {
        streamError(ev);
      }
    }).then(function () {
      if (!ctx.finished) earlyEnd();
    }, function (err) {
      if (ctx.finished) return;
      if (!ctx.sawEvent && (!err || err.status === 0 || err.status === 404 || err.status === 405)) {
        return fallback(payload);
      }
      if (!ctx.sawEvent) {
        renderReqError(err);
        return;
      }
      interrupted(err);
    }).then(function () {
      busy = false;
      if (els.askBtn) els.askBtn.disabled = false;
    });
  }

  /* ---------------------------------------------------------------------- */
  /* Init                                                                   */
  /* ---------------------------------------------------------------------- */
  function init() {
    els.select = document.getElementById("course-select");
    els.thread = document.getElementById("chat-thread");
    els.empty = document.getElementById("thread-empty");
    els.status = document.getElementById("tutor-status");
    els.input = document.getElementById("composer-input");
    els.form = document.getElementById("composer-form");
    els.conversationList = document.getElementById("conversation-list");
    els.threadTitle = document.getElementById("thread-title");
    els.threadSub = document.getElementById("thread-sub");

    if (els.form) {
      els.form.addEventListener("submit", function (e) {
        e.preventDefault();
        var text = els.input.value;
        els.input.value = "";
        ask(text);
      });
    }

    var newBtn = document.getElementById("new-chat");
    if (newBtn) newBtn.addEventListener("click", newChat);

    var refreshBtn = document.getElementById("refresh-conversations");
    if (refreshBtn) refreshBtn.addEventListener("click", loadConversations);

    if (els.conversationList) {
      els.conversationList.addEventListener("click", function (e) {
        var open = e.target.closest("[data-open]");
        var del = e.target.closest("[data-delete]");
        if (open) openConversation(open.getAttribute("data-open"));
        else if (del) deleteConversation(del.getAttribute("data-delete"));
      });
    }

    newChat();
    App.mountCourseSelect(els.select, {
      onChange: function () {
        newChat();
        loadConversations();
      },
      onLoaded: function () {
        newChat();
        loadConversations();
      }
    });

    var q = App.queryParam("q");
    if (q && els.input) { els.input.value = q; }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
