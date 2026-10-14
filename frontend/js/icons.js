/* ==========================================================================
   StudyMate AI — Inline SVG icon system (no remote icon fonts).
   Usage in HTML:  <span data-icon="upload"></span>
   Usage in JS:    StudyUI.icon("upload")
   ========================================================================== */
(function (global) {
  "use strict";

  var ICONS = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.7V21h14V9.7"/><path d="M9.5 21v-6.5h5V21"/>',
    grid: '<rect x="3" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.6"/>',
    book: '<path d="M12 6.8C10.6 5.4 8.6 4.8 4 4.8V18.6c4.6 0 6.6.6 8 2 1.4-1.4 3.4-2 8-2V4.8c-4.6 0-6.6.6-8 2Z"/><path d="M12 6.8v13.8"/>',
    bookOpen: '<path d="M12 6.8C10.6 5.4 8.6 4.8 4 4.8V18.6c4.6 0 6.6.6 8 2 1.4-1.4 3.4-2 8-2V4.8c-4.6 0-6.6.6-8 2Z"/><path d="M12 6.8v13.8"/>',
    chat: '<path d="M21 11.7a8.4 8.4 0 0 1-8.4 8.4H4.6l1.7-3.4a8.4 8.4 0 1 1 14.7-5Z"/>',
    quiz: '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.4a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1.1.9-1.1 1.6v.4"/><path d="M12 17h.01"/>',
    chart: '<path d="M3 17.5 9 11l4 3.5 7.5-8"/><path d="M15.5 6.5H21v5.5"/>',
    target: '<circle cx="12" cy="12" r="8.6"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.6"/>',
    layers: '<path d="m12 3 8.5 4.5L12 12 3.5 7.5 12 3Z"/><path d="m4 12.5 8 4.3 8-4.3"/><path d="m4 17 8 4.3 8-4.3"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4.8 20a7.4 7.4 0 0 1 14.4 0"/>',
    users: '<circle cx="9.5" cy="8" r="3.6"/><path d="M3.2 19.5a6.4 6.4 0 0 1 12.6 0"/><path d="M16.2 5a3.6 3.6 0 0 1 0 6.8"/><path d="M17.6 14.4a6.4 6.4 0 0 1 3.2 5.1"/>',
    settings: '<circle cx="12" cy="12" r="3.2"/><path d="M19.4 14.6a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.03 1.56V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.55 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.56-1.03H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.55-1.1 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34H9a1.7 1.7 0 0 0 1-1.56V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1.03 1.56 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87V9c.24.62.84 1.03 1.5 1.03H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1.03Z"/>',
    upload: '<path d="M12 16V4"/><path d="m7.5 8.5 4.5-4.5 4.5 4.5"/><path d="M4 16.5V19a1.5 1.5 0 0 0 1.5 1.5h13A1.5 1.5 0 0 0 20 19v-2.5"/>',
    download: '<path d="M12 4v12"/><path d="m7.5 11.5 4.5 4.5 4.5-4.5"/><path d="M4 16.5V19a1.5 1.5 0 0 0 1.5 1.5h13A1.5 1.5 0 0 0 20 19v-2.5"/>',
    send: '<path d="M21 3 10.5 13.5"/><path d="M21 3 14.4 21l-3.9-7.5L3 9.6 21 3Z"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    checkCircle: '<circle cx="12" cy="12" r="9"/><path d="m8.4 12.2 2.5 2.5 4.7-5.2"/>',
    xCircle: '<circle cx="12" cy="12" r="9"/><path d="m9.2 9.2 5.6 5.6"/><path d="m14.8 9.2-5.6 5.6"/>',
    alert: '<path d="M12 4 2.9 19.5h18.2L12 4Z"/><path d="M12 10v4"/><path d="M12 17h.01"/>',
    alertCircle: '<circle cx="12" cy="12" r="9"/><path d="M12 8v5"/><path d="M12 16h.01"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/>',
    flame: '<path d="M12 3c1 3-1.6 4-1.6 6.5A2.4 2.4 0 0 0 13 12c1.4-1 1.4-2.4 1.4-2.4 2 1.5 3.1 3.6 3.1 6a5.5 5.5 0 1 1-11 0C6.5 9 12 8 12 3Z"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5.2l3.2 1.9"/>',
    calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 9.6h17"/><path d="M8 3v4"/><path d="M16 3v4"/>',
    trending: '<path d="m3 17 6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    bolt: '<path d="M13 3 5 14h6l-1 7 8-11h-6l1-7Z"/>',
    brain: '<path d="M12 5.5a3 3 0 0 0-5.6-1.5A2.8 2.8 0 0 0 4.4 8a3 3 0 0 0-.6 5.3A3 3 0 0 0 7 18.4a2.8 2.8 0 0 0 5 .6 2.8 2.8 0 0 0 5-.6 3 3 0 0 0 3.2-5.1A3 3 0 0 0 19.6 8a2.8 2.8 0 0 0-2-4A3 3 0 0 0 12 5.5Z"/><path d="M12 5.5v13.5"/>',
    sparkle: '<path d="m12 3 1.9 4.8L18.7 9.7l-4.8 1.9L12 16.4l-1.9-4.8L5.3 9.7l4.8-1.9L12 3Z"/><path d="m18.6 15.4.8 2 .2.8.8.2 2 .8-2 .8-.8.2-.2.8-2-.8-2-.8.2-.8.8-2 .8-2Z"/>',
    shield: '<path d="M12 3.2 19 6v6.2c0 4.4-2.9 7.3-7 8.6-4.1-1.3-7-4.2-7-8.6V6l7-2.8Z"/><path d="m9 12 2.2 2.2L15.2 10"/>',
    lock: '<rect x="5" y="11" width="14" height="9.2" rx="2"/><path d="M8.2 11V8a3.8 3.8 0 0 1 7.6 0v3"/>',
    server: '<rect x="3.5" y="4" width="17" height="6.5" rx="1.6"/><rect x="3.5" y="13.5" width="17" height="6.5" rx="1.6"/><path d="M7.2 7.2h.01"/><path d="M7.2 16.8h.01"/>',
    database: '<ellipse cx="12" cy="6" rx="7.5" ry="3.2"/><path d="M4.5 6v12c0 1.8 3.4 3.2 7.5 3.2s7.5-1.4 7.5-3.2V6"/><path d="M4.5 12c0 1.8 3.4 3.2 7.5 3.2s7.5-1.4 7.5-3.2"/>',
    refresh: '<path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v4.4h-4.4"/>',
    arrowRight: '<path d="M4.5 12h14"/><path d="m13 6 6 6-6 6"/>',
    arrowLeft: '<path d="M19.5 12h-14"/><path d="m11 6-6 6 6 6"/>',
    chevronRight: '<path d="m9.5 6 6 6-6 6"/>',
    chevronLeft: '<path d="m14.5 6-6 6 6 6"/>',
    chevronDown: '<path d="m6 9.5 6 6 6-6"/>',
    plus: '<path d="M12 5v14"/><path d="M5 12h14"/>',
    x: '<path d="m6 6 12 12"/><path d="M18 6 6 18"/>',
    menu: '<path d="M4 7h16"/><path d="M4 12h16"/><path d="M4 17h16"/>',
    more: '<circle cx="5.5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="18.5" cy="12" r="1.4"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/>',
    filter: '<path d="M4 6h16"/><path d="M7 12h10"/><path d="M10 18h4"/>',
    play: '<circle cx="12" cy="12" r="9"/><path d="m10 8.5 6 3.5-6 3.5v-7Z"/>',
    video: '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10.5 5-3v9l-5-3"/>',
    image: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="9" cy="10" r="1.8"/><path d="m4.5 17.5 4.8-4.4 3.4 3 3-2.6 4 4"/>',
    file: '<path d="M14 3.5H7.5A1.5 1.5 0 0 0 6 5v14a1.5 1.5 0 0 0 1.5 1.5h9A1.5 1.5 0 0 0 18 19V7.5L14 3.5Z"/><path d="M13.8 3.6V8h4.2"/>',
    slides: '<rect x="3.5" y="4.5" width="17" height="11.5" rx="1.8"/><path d="M12 16v3.6"/><path d="M8.5 19.6h7"/>',
    pdf: '<path d="M14 3.5H7.5A1.5 1.5 0 0 0 6 5v14a1.5 1.5 0 0 0 1.5 1.5h9A1.5 1.5 0 0 0 18 19V7.5L14 3.5Z"/><path d="M13.8 3.6V8h4.2"/><path d="M9 13.5h1.2a1.1 1.1 0 0 0 0-2.2H9v5"/><path d="M13.2 11.3h1.4a1.6 1.6 0 0 1 0 3.2h-1.4v-3.2Zm0 3.2V11.3"/>',
    mic: '<rect x="9" y="3.4" width="6" height="11" rx="3"/><path d="M5.6 11.6a6.4 6.4 0 0 0 12.8 0"/><path d="M12 18v3"/>',
    attach: '<path d="M19.6 11.2 12 18.8a5 5 0 0 1-7-7l8-8a3.5 3.5 0 0 1 5 5l-8 8a2 2 0 0 1-2.8-2.8l7.3-7.3"/>',
    flag: '<path d="M5 21V4.5"/><path d="M5 5.2h11.5l-1.7 3.6 1.7 3.6H5"/>',
    lightbulb: '<path d="M9.5 18.5h5"/><path d="M10.5 21.5h3"/><path d="M12 3.2a6 6 0 0 0-3.6 10.8c.7.6 1.1 1.3 1.1 2.1h5c0-.8.4-1.5 1.1-2.1A6 6 0 0 0 12 3.2Z"/>',
    eye: '<path d="M2.5 12S6 6.2 12 6.2 21.5 12 21.5 12 18 17.8 12 17.8 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/>',
    external: '<path d="M14 4.5h5.5V10"/><path d="M19.5 4.5 11 13"/><path d="M18.5 14.5V19a1.5 1.5 0 0 1-1.5 1.5H5.5A1.5 1.5 0 0 1 4 19V7.5A1.5 1.5 0 0 1 5.5 6H10"/>',
    gradCap: '<path d="m12 4.5 9.5 4.7-9.5 4.7-9.5-4.7L12 4.5Z"/><path d="M6.8 11.4V16c0 1.7 2.3 3 5.2 3s5.2-1.3 5.2-3v-4.6"/><path d="M21 9.4v5"/>',
    route: '<circle cx="6.5" cy="17.5" r="2.6"/><circle cx="17.5" cy="6.5" r="2.6"/><path d="M9 17.5h4.5a4 4 0 0 0 0-8H10a4 4 0 0 1 0-8h0"/>',
    history: '<path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 4.5V9h4.5"/><path d="M12 8v4.4l3 1.8"/>',
    swap: '<path d="M7 4.5 3.5 8 7 11.5"/><path d="M3.5 8H15a4 4 0 0 1 0 8h-2"/><path d="m17 12.5 3.5 3.5-3.5 3.5"/>',
    pie: '<path d="M12 3.5a8.5 8.5 0 1 0 8.5 8.5H12V3.5Z"/><path d="M14.5 3.9A8.5 8.5 0 0 1 20.1 9.5H14.5V3.9Z"/>',
    camera: '<path d="M4.5 8.5h2.6l1.4-2h6l1.4 2h2.6A1.5 1.5 0 0 1 20 10v8a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18v-8a1.5 1.5 0 0 1 1.5-1.5Z"/><circle cx="12" cy="13.6" r="3.2"/>',
    logout: '<path d="M9.5 4.5H6A1.5 1.5 0 0 0 4.5 6v12A1.5 1.5 0 0 0 6 19.5h3.5"/><path d="M14.5 8 18.5 12l-4 4"/><path d="M18.5 12H9"/>',
    compass: '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5.2-5.2 2 2-5.2 5.2-2Z"/>',
    pause: '<circle cx="12" cy="12" r="9"/><path d="M10 9.5v5"/><path d="M14 9.5v5"/>',
    rotate: '<path d="M4 8.5A8.6 8.6 0 0 1 19 6.6"/><path d="M20 3.5v4.4h-4.4"/><path d="M20 15.5A8.6 8.6 0 0 1 5 17.4"/><path d="M4 20.5v-4.4h4.4"/>',
    inbox: '<path d="M4 13.5 6.6 5.4A1.5 1.5 0 0 1 8 4.3h8a1.5 1.5 0 0 1 1.4 1.1L20 13.5V18a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18v-4.5Z"/><path d="M4 13.5h4l1.2 2.2h5.6L16 13.5h4"/>',
    wifiOff: '<path d="m3 3 18 18"/><path d="M8.6 15.1a5 5 0 0 1 6.1-.7"/><path d="M5.4 11.6a10 10 0 0 1 3.5-2.2"/><path d="M2 8.3a15 15 0 0 1 5-3.2"/><path d="M13.5 5.4a15 15 0 0 1 8.5 2.9"/><path d="M18.6 11.6a10 10 0 0 0-2.4-1.6"/><path d="M12 19h.01"/>',
    trash: '<path d="M4.5 7h15"/><path d="M9.5 7V5.4A1.4 1.4 0 0 1 10.9 4h2.2a1.4 1.4 0 0 1 1.4 1.4V7"/><path d="M6.5 7l.8 12.1A1.5 1.5 0 0 0 8.8 20.5h6.4a1.5 1.5 0 0 0 1.5-1.4L17.5 7"/><path d="M10.5 11v5.5"/><path d="M13.5 11v5.5"/>'
  };

  function svg(name, extraClass) {
    var body = ICONS[name];
    if (!body) return "";
    return (
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"' +
      (extraClass ? ' class="' + extraClass + '"' : "") +
      ">" + body + "</svg>"
    );
  }

  function hydrate(root) {
    var nodes = (root || document).querySelectorAll("[data-icon]");
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (el.getAttribute("data-icon-done") === "1") continue;
      var markup = svg(el.getAttribute("data-icon"));
      if (markup) {
        el.innerHTML = markup;
        el.setAttribute("data-icon-done", "1");
      }
    }
  }

  global.StudyIcons = { svg: svg, hydrate: hydrate, ICONS: ICONS };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { hydrate(document); });
  } else {
    hydrate(document);
  }
})(window);
