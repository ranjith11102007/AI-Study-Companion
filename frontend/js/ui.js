/* ==========================================================================
   StudyMate AI — UI primitives: toasts, formatting, state helpers.
   No API calls here (see js/api.js).
   ========================================================================== */
(function (global) {
  "use strict";

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function icon(name) {
    return global.StudyIcons ? global.StudyIcons.svg(name) : "";
  }

  function region() {
    var el = document.querySelector(".toast-region");
    if (!el) {
      el = document.createElement("div");
      el.className = "toast-region";
      el.setAttribute("role", "status");
      el.setAttribute("aria-live", "polite");
      document.body.appendChild(el);
    }
    return el;
  }

  /**
   * Toast notification. tone: "info" | "success" | "warn"
   */
  function toast(message, tone) {
    var host = region();
    var node = document.createElement("div");
    node.className = "toast" + (tone ? " " + tone : "");
    var glyph = tone === "success" ? "checkCircle" : tone === "warn" ? "alert" : "info";
    node.innerHTML =
      icon(glyph) +
      "<span>" + escapeHtml(message) + "</span>" +
      '<button class="toast-close" aria-label="Dismiss">&times;</button>';
    var close = function () {
      if (node.parentNode) node.parentNode.removeChild(node);
    };
    node.querySelector(".toast-close").addEventListener("click", close);
    host.appendChild(node);
    setTimeout(close, 5200);
    return node;
  }

  /** ISO timestamp → compact local time label. */
  function timeLabel(iso) {
    if (!iso) return "—";
    try {
      var d = new Date(iso);
      return d.toLocaleString(undefined, {
        month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
      });
    } catch (e) {
      return iso;
    }
  }

  global.StudyUI = {
    escapeHtml: escapeHtml,
    icon: icon,
    toast: toast,
    timeLabel: timeLabel
  };
})(window);
