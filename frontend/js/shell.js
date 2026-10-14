/* ==========================================================================
   StudyMate AI — Shared app shell.
   Renders sidebar / topbar / bottom nav / bare header from body[data-*]:
     <body data-shell="app" data-page="dashboard">
     <body data-shell="bare" data-page="landing">
   Also binds: [data-todo] toasts, [data-tabs], mobile drawer.
   ========================================================================== */
(function (global) {
  "use strict";

  var NAV = [
    {
      title: "Study",
      items: [
        { id: "dashboard", label: "Dashboard", href: "dashboard.html", icon: "home" },
        { id: "courses", label: "Courses", href: "courses.html", icon: "book" }
      ]
    },
    {
      title: "Learn",
      items: [
        { id: "tutor", label: "AI Tutor", href: "tutor.html", icon: "chat" },
        { id: "assessment", label: "Assessments", href: "assessment.html", icon: "quiz" },
        { id: "flashcards", label: "Flashcards", href: "flashcards.html", icon: "layers", badge: "Soon" }
      ]
    },
    {
      title: "Insights",
      items: [
        { id: "progress", label: "Progress", href: "progress.html", icon: "chart" },
        { id: "recommendations", label: "Weak topics", href: "recommendations.html", icon: "target" }
      ]
    },
    {
      title: "Account",
      items: [
        { id: "settings", label: "Settings", href: "settings.html", icon: "settings" }
      ]
    }
  ];

  /* Which nav entry lights up for sub-pages. */
  var PAGE_GROUP = {
    dashboard: "dashboard",
    courses: "courses",
    course: "courses",
    upload: "courses",
    source: "courses",
    tutor: "tutor",
    assessment: "assessment",
    quiz: "assessment",
    results: "assessment",
    progress: "progress",
    recommendations: "progress",
    flashcards: "flashcards",
    settings: "settings"
  };

  var TITLES = {
    dashboard: ["Dashboard", "Your study command center"],
    courses: ["Courses", "Materials, topics and assessments"],
    course: ["Course overview", "Structure and readiness"],
    upload: ["Upload materials", "PDF · PPT/PPTX · video · images"],
    tutor: ["AI tutor", "Source-grounded answers with citations"],
    assessment: ["Assessments", "Configure an adaptive quiz"],
    quiz: ["Quiz", "Answer session"],
    results: ["Results", "Score breakdown and review"],
    progress: ["Progress", "Mastery tracking"],
    recommendations: ["Weak topics", "Revision recommendations"],
    source: ["Source viewer", "Page · slide · timestamp references"],
    flashcards: ["Flashcards", "Spaced revision"],
    settings: ["Settings", "Account and preferences"]
  };

  var BOTTOM = [
    { id: "dashboard", label: "Home", href: "dashboard.html", icon: "home" },
    { id: "courses", label: "Courses", href: "courses.html", icon: "book" },
    { id: "tutor", label: "Tutor", href: "tutor.html", icon: "chat", fab: true },
    { id: "assessment", label: "Quiz", href: "assessment.html", icon: "quiz" },
    { id: "progress", label: "Progress", href: "progress.html", icon: "chart" }
  ];

  /* Auth pages (login / sign up) share one two-column layout: the same header,
     promotional panel and form-card styling. Only the copy and the form differ.
     The panel is rendered here so the markup is never duplicated per page. */
  var AUTH_ASIDE = {
    login: {
      heading: "Pick up where you left off.",
      sub: "One workspace for your sources, tutor conversations, assessments and " +
        "mastery map — all stored locally."
    },
    signup: {
      heading: "Start your learning journey.",
      sub: "Create your personal study workspace and turn your learning materials " +
        "into lasting knowledge."
    }
  };

  var AUTH_POINTS = [
    {
      icon: "lock",
      title: "Local-first by design",
      text: "Your materials and study data live on your machine — not on a paid cloud."
    },
    {
      icon: "chat",
      title: "Cited answers only",
      text: "Every tutor response points back to a page, slide or timestamp in your sources."
    },
    {
      icon: "chart",
      title: "Progress you can prove",
      text: "Mastery is computed from your actual answers, question by question."
    }
  ];

  function ico(name) { return global.StudyIcons ? global.StudyIcons.svg(name) : ""; }

  function isActive(item, page) {
    return (PAGE_GROUP[page] || page) === item.id;
  }

  function sidebarHtml(page) {
    var groups = NAV.map(function (group) {
      var items = group.items.map(function (item) {
        return (
          '<a class="nav-item' + (isActive(item, page) ? " active" : "") + '" href="' + item.href + '">' +
          ico(item.icon) +
          "<span>" + item.label + "</span>" +
          (item.badge ? '<span class="nav-badge">' + item.badge + "</span>" : "") +
          "</a>"
        );
      }).join("");
      return (
        '<div class="nav-group">' +
        '<div class="nav-title">' + group.title + "</div>" +
        items +
        "</div>"
      );
    }).join("");

    return (
      '<div class="brand">' +
      '<span class="brand-mark">' + ico("gradCap") + "</span>" +
      '<span class="stack">' +
      '<span class="brand-name">StudyMate <span class="brand-tag">AI</span></span>' +
      '<span class="brand-sub">Adaptive learning</span>' +
      "</span>" +
      "</div>" +
      '<nav aria-label="Primary">' + groups + "</nav>" +
      '<div class="sidebar-foot">' +
      '<a class="nav-item" href="index.html">' + ico("compass") + "<span>Landing page</span></a>" +
      '<button type="button" class="nav-item" data-signout>' + ico("logout") + "<span>Sign out</span></button>" +
      "</div>"
    );
  }

  function topbarHtml(page) {
    var t = TITLES[page] || ["StudyMate AI", ""];
    var name = global.StudyApp ? global.StudyApp.displayName() : "";
    var initial = (name && name.trim() ? name.trim().charAt(0) : "S").toUpperCase();
    var html =
      '<button class="btn btn-icon menu-toggle" id="menu-toggle" aria-label="Open navigation">' +
      ico("menu") + "</button>" +
      '<div class="stack" style="gap:0">' +
      '<span class="topbar-title">' + t[0] + "</span>" +
      '<span class="topbar-sub">' + t[1] + "</span>" +
      "</div>" +
      '<div class="spacer"></div>' +
      (page === "settings" ? ('<span class="health-pill" data-health-pill title="Backend status">' +
      '<span class="status-dot" data-health-dot></span>' +
      '<span class="health-text" data-health-label>Checking backend…</span>' +
      "</span>") : '') +
      '<a class="avatar" href="settings.html" aria-label="Settings">' + initial + "</a>";
    return html;
  }

  function bottomNavHtml(page) {
    var items = BOTTOM.map(function (item) {
      var active = isActive(item, page) ? " active" : "";
      if (item.fab) {
        return (
          '<a class="' + active.trim() + '" href="' + item.href + '">' +
          '<span class="bn-fab">' + ico(item.icon) + "</span>" +
          "<span>" + item.label + "</span></a>"
        );
      }
      return (
        '<a class="' + active.trim() + '" href="' + item.href + '">' +
        ico(item.icon) + "<span>" + item.label + "</span></a>"
      );
    }).join("");
    return '<div class="bottomnav-inner">' + items + "</div>";
  }

  function footerHtml(page) {
    return (
      '<div class="footer-inner">' +
      "<span>StudyMate AI · Personalized Tutoring &amp; Adaptive Learning</span>" +
      '<span class="footer-links">' +
      '<a href="index.html">Home</a>' +
      (page === "settings" ? '<a href="/docs" target="_blank" rel="noopener">API docs</a>' : '') +
      '<a href="settings.html">Settings</a>' +
      "<span>Free &amp; open-source · local-first · no paid APIs</span>" +
      "</span></div>"
    );
  }

  function bareHeaderHtml(page) {
    var cta =
      page === "login"
        ? '<a class="btn btn-primary btn-sm" href="signup.html">Create account</a>'
        : '<a class="btn btn-primary btn-sm" href="login.html">Sign in</a>';
    return (
      '<div class="bare-header-inner container">' +
      '<a class="brand" href="index.html">' +
      '<span class="brand-mark">' + ico("gradCap") + "</span>" +
      '<span class="stack" style="gap:0">' +
      '<span class="brand-name">StudyMate <span class="brand-tag">AI</span></span>' +
      '<span class="brand-sub">Adaptive learning</span>' +
      "</span></a>" +
      '<nav class="bare-nav">' + cta + "</nav></div>"
    );
  }

  function authAsideHtml(page) {
    var cfg = AUTH_ASIDE[page];
    if (!cfg) return "";
    var points = AUTH_POINTS.map(function (p) {
      return (
        '<div class="auth-point">' +
        '<span class="ap-icon">' + ico(p.icon) + "</span>" +
        "<div>" +
        "<h4>" + p.title + "</h4>" +
        "<p>" + p.text + "</p>" +
        "</div></div>"
      );
    }).join("");
    return (
      '<aside class="auth-aside">' +
      "<div>" +
      '<span class="ai-pill"><span class="dot6"></span> StudyMate AI</span>' +
      '<h2 class="t-h1 mt-md">' + cfg.heading + "</h2>" +
      '<p class="aside-sub mt-sm">' + cfg.sub + "</p>" +
      "</div>" +
      '<div class="auth-points">' + points + "</div>" +
      '<div class="aside-foot">' +
      ico("shield") +
      "<span>Free &amp; open-source · no paid APIs · runs on your own infrastructure</span>" +
      "</div>" +
      "</aside>"
    );
  }

  function mount() {
    var body = document.body;
    var shell = body.getAttribute("data-shell") || "bare";
    var page = body.getAttribute("data-page") || "";

    if (shell === "app") {
      if (global.StudyApp && !global.StudyApp.requireAuth()) return;

      var app = document.createElement("div");
      app.className = "app";

      var sidebar = document.createElement("aside");
      sidebar.className = "sidebar";
      sidebar.id = "sidebar";
      sidebar.innerHTML = sidebarHtml(page);

      var col = document.createElement("div");
      col.className = "main-col";

      var topbar = document.createElement("header");
      topbar.className = "topbar";
      topbar.innerHTML = topbarHtml(page);

      var content = document.getElementById("page-content");
      if (!content) {
        content = document.createElement("main");
        content.className = "content with-bottomnav";
        content.id = "page-content";
        while (body.firstChild) content.appendChild(body.firstChild);
      }
      content.classList.add("content");
      content.classList.add("with-bottomnav");

      var footer = document.createElement("footer");
      footer.className = "footer";
      footer.innerHTML = footerHtml(page);

      col.appendChild(topbar);
      col.appendChild(content);
      col.appendChild(footer);
      app.appendChild(sidebar);
      app.appendChild(col);
      body.appendChild(app);

      var scrim = document.createElement("div");
      scrim.className = "scrim";
      scrim.id = "scrim";
      body.appendChild(scrim);

      var bottom = document.createElement("nav");
      bottom.className = "bottomnav";
      bottom.setAttribute("aria-label", "Mobile");
      bottom.innerHTML = bottomNavHtml(page);
      body.appendChild(bottom);

      var toggle = document.getElementById("menu-toggle");
      var closeDrawer = function () {
        sidebar.classList.remove("open");
        scrim.classList.remove("open");
      };
      if (toggle) {
        toggle.addEventListener("click", function () {
          sidebar.classList.toggle("open");
          scrim.classList.toggle("open");
        });
      }
      scrim.addEventListener("click", closeDrawer);
      sidebar.addEventListener("click", function (e) {
        var a = e.target.closest ? e.target.closest("a") : null;
        if (a) closeDrawer();
      });

      document.title = (TITLES[page] ? TITLES[page][0] + " · " : "") + "StudyMate AI";
    } else {
      var header = document.createElement("header");
      header.className = "bare-header";
      header.innerHTML = bareHeaderHtml(page);
      body.insertBefore(header, body.firstChild);

      /* Auth pages get the shared promotional panel and fill the viewport;
         the landing page keeps the marketing footer. */
      if (AUTH_ASIDE[page]) {
        var authRoot = body.querySelector(".auth");
        if (authRoot) authRoot.insertAdjacentHTML("afterbegin", authAsideHtml(page));
      } else {
        var footerBare = document.createElement("footer");
        footerBare.className = "footer";
        footerBare.innerHTML = footerHtml();
        body.appendChild(footerBare);
      }
    }

    bindCommon(body);
    if (global.StudyIcons) global.StudyIcons.hydrate(body);
    if (global.StudyHealth && page === "settings") global.StudyHealth.init();
  }

  function bindCommon(root) {
    /* Sign out from the sidebar foot */
    root.querySelectorAll("[data-signout]").forEach(function (el) {
      if (el.getAttribute("data-signout-bound") === "1") return;
      el.setAttribute("data-signout-bound", "1");
      el.addEventListener("click", function (e) {
        e.preventDefault();
        if (global.StudyApp) global.StudyApp.signOut();
      });
    });

    /* Placeholder actions that surface a short "coming soon" note */
    root.querySelectorAll("[data-todo]").forEach(function (el) {
      if (el.getAttribute("data-todo-bound") === "1") return;
      el.setAttribute("data-todo-bound", "1");
      el.addEventListener("click", function (e) {
        e.preventDefault();
        global.StudyUI.toast(el.getAttribute("data-todo"), "warn");
      });
    });

    /* Tab groups: [data-tabs] > .tab[data-tab] + .tabpanel[data-panel] */
    root.querySelectorAll("[data-tabs]").forEach(function (group) {
      if (group.getAttribute("data-tabs-bound") === "1") return;
      group.setAttribute("data-tabs-bound", "1");
      var tabs = group.querySelectorAll(".tab[data-tab]");
      tabs.forEach(function (tab) {
        tab.addEventListener("click", function () {
          var name = tab.getAttribute("data-tab");
          tabs.forEach(function (t) { t.classList.toggle("active", t === tab); });
          group.querySelectorAll(".tabpanel[data-panel]").forEach(function (p) {
            p.hidden = p.getAttribute("data-panel") !== name;
          });
        });
      });
    });
  }

  global.StudyShell = { mount: mount, bindCommon: bindCommon, NAV: NAV };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})(window);
