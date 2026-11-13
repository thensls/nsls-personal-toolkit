// First-run tips (coach marks) for Plan your day and the Command Center.
//
// Markup contract:
//   #nsls-callouts[data-screen][data-dismissed]  rendered inside <main> by
//       _components/callouts.html: which tip set this screen uses ("plan" |
//       "command") and the ids already dismissed (JSON array, read from the
//       companion's saved state)
//   [data-callout="<id>"]  a tip's target where it has no natural selector
//   window.__toolkitCalloutStore  optional: {dismiss(ids)}; returning false
//       (or a promise of false) means it wasn't saved
//   "toolkit:did" events on document, detail {action: "drag" | "progress" |
//       "add"}: the builder just did that, so its tip retires. drag.js sends
//       "drag"; progress and add are read from HTMX responses here; the demo
//       sends all three itself.
//
// Tips are short: "Tip 1 of 3", a heading, and Got it. They run as a tour, one
// at a time: the next appears when the builder clicks Got it or does what the
// tip teaches (doneWhen: a state is reached; doneOn: an action happened). Each
// sits beside its control (right, left or below, falling back to below when
// the side has no room), never on top of it. A tip that waits for the builder
// to act (noOk) has no Got it. Dismissals go to POST /callouts/dismiss unless
// the page installs its own store first (the setup.nsls.org demo).
(function () {
  "use strict";

  const plan = (sel) => document.querySelectorAll("#plan-your-day " + sel);
  const placed = (lane) => plan(".nsls-lane--" + lane + " [data-drag-item]").length;
  const twoPlaced = () => placed("top3") >= 2 || placed("bonus") >= 2;
  // The task to drag: the first in a section with two to reorder, else the
  // first placed task, else the first suggestion (it can be dragged in).
  const firstTask = (sel) => plan(sel + " [data-drag-item]:not(.is-set-aside)")[0] || null;
  const taskToDrag = () => {
    for (const lane of ["top3", "bonus"]) {
      if (placed(lane) >= 2) return firstTask(".nsls-lane--" + lane);
    }
    return firstTask(".nsls-lane--top3") || firstTask(".nsls-lane--bonus") || firstTask(".nsls-lane--pool");
  };

  const TIPS = {
    plan: [
      { id: "plan-assign", target: () => firstTask(".nsls-lane--pool"), side: "right",
        doneWhen: twoPlaced,
        title: "Assign task priorities" },
      { id: "plan-drag", target: taskToDrag, side: "left", doneOn: "drag",
        title: "Drag to change a priority" },
      { id: "plan-lockin", target: '[data-callout="plan-lockin"]',
        title: "When everything looks good, click Done" },
    ],
    command: [
      // Anchored to the whole task row, so the card clears the row's ✕ too.
      { id: "cc-progress", target: "#task-table [data-drag-item]", side: "right",
        doneOn: "progress",
        title: "Mark your progress here" },
      // The whole form, not just its text box: on a narrow screen the picker and
      // the Add item button wrap below the box, and the card must clear them.
      { id: "cc-add", target: ".nsls-add-item", side: "below", doneOn: "add",
        title: "Add a task here",
        body: "Type it, pick Today · Top 3 or Today · Bonus, then click Add item." },
      { id: "cc-close", target: '[data-callout="cc-close"]', noOk: true, doneOn: "close",
        title: "Close your day",
        body: "At the end of your day, click “I'm done — close my day”." },
    ],
  };

  const GAP = 14;          // control edge to card edge, room for the arrow
  const EDGE = 12;         // card never closer than this to the viewport side

  const serverStore = {
    dismiss(ids) {
      const body = new URLSearchParams();
      ids.forEach((id) => body.append("id", id));
      return fetch("/callouts/dismiss", { method: "POST", body: body })
        .then((r) => r.ok, () => false);
    },
  };
  const store = () => window.__toolkitCalloutStore || serverStore;

  let screen = "";
  let dismissed = new Set();
  // This tab's own dismissals: a <main> re-render that raced the POST must not
  // bring a closed tip back.
  const closedHere = new Set();
  let openId = null;
  let shownId = null;      // the open tip we last scrolled into view
  // Set when the builder moves the tour on, so the next tip is scrolled into
  // view; a screen that has just opened is left where it is (at the top).
  let advanced = false;
  let layer = null;
  let frame = 0;
  const dots = new Map();  // tip id -> dot button
  let card = null;         // {id, el}

  function readConfig() {
    const cfg = document.getElementById("nsls-callouts");
    let saved = [];
    if (cfg) {
      try { saved = JSON.parse(cfg.dataset.dismissed || "[]"); } catch (_) { saved = []; }
    }
    screen = cfg ? cfg.dataset.screen || "" : "";
    dismissed = new Set(saved.concat(Array.from(closedHere)));
  }

  function findTarget(tip) {
    if (typeof tip.target === "function") {
      const el = tip.target();
      return el && el.getClientRects().length ? el : null;
    }
    for (const el of document.querySelectorAll(tip.target)) {
      if (el.getClientRects().length) return el;
    }
    return null;
  }

  // The next tip on this tour whose control is on the page: one at a time.
  function pending() {
    return (TIPS[screen] || [])
      .filter((tip) => !dismissed.has(tip.id))
      .map((tip) => ({ tip: tip, el: findTarget(tip) }))
      .filter((p) => p.el)
      .slice(0, 1);
  }

  function ensureLayer() {
    if (layer && layer.isConnected) return;
    dots.clear();
    card = null;
    layer = document.createElement("div");
    layer.className = "nsls-coach-layer";
    document.body.appendChild(layer);
  }

  function dismiss(ids) {
    ids = ids.filter((id) => !dismissed.has(id));
    if (!ids.length) return;
    ids.forEach((id) => { closedHere.add(id); dismissed.add(id); });
    openId = null;
    advanced = true;
    // If it didn't save, bring the tip back rather than let it return on the
    // next reload, so Got it can simply be clicked again.
    Promise.resolve(store().dismiss(ids)).then((saved) => {
      if (saved !== false) return;
      ids.forEach((id) => closedHere.delete(id));
      schedule();
    });
    schedule();
  }

  // The builder did what a tip teaches: by reaching its state (doneWhen) or by
  // the action itself (doneOn). Either way it has served its purpose.
  function retireOutgrown() {
    const done = (TIPS[screen] || [])
      .filter((tip) => !dismissed.has(tip.id) && tip.doneWhen && tip.doneWhen())
      .map((tip) => tip.id);
    if (done.length) dismiss(done);
  }
  function did(action) {
    readConfig();
    dismiss((TIPS[screen] || []).filter((tip) => tip.doneOn === action).map((tip) => tip.id));
  }

  function stepLabel(tip) {
    const tour = TIPS[screen] || [];
    return tour.length > 1 ? "Tip " + (tour.indexOf(tip) + 1) + " of " + tour.length : "Tip";
  }

  function buildCard(tip) {
    const el = document.createElement("div");
    el.className = "nsls-coach-card";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-label", tip.title);
    const row = document.createElement("div");
    row.className = "nsls-coach-row";
    const head = document.createElement("div");
    const step = document.createElement("div");
    step.className = "nsls-coach-step";
    step.textContent = stepLabel(tip);
    const title = document.createElement("p");
    title.className = "nsls-coach-title";
    title.textContent = tip.title;
    head.append(step, title);
    row.append(head);
    if (!tip.noOk) {
      const ok = document.createElement("button");
      ok.type = "button";
      ok.className = "nsls-coach-ok";
      ok.textContent = "Got it";
      ok.addEventListener("click", () => dismiss([tip.id]));
      row.append(ok);
    }
    el.append(row);
    if (tip.body) {
      const body = document.createElement("p");
      body.className = "nsls-coach-body";
      body.textContent = tip.body;
      el.append(body);
    }
    return el;
  }

  // Where the arrow points: a short control's middle, or near the top of a
  // tall one (a whole section), level with its heading.
  const anchorY = (r) => r.top + Math.min(r.height / 2, 22);

  function placeDot(dot, tip, r, vw) {
    let x, y;
    if (tip.side === "right") { x = r.right + 2; y = anchorY(r); }
    else if (tip.side === "left") { x = r.left - 2; y = anchorY(r); }
    else {
      // Top-right corner; top-left if that's off-screen.
      x = r.right + 10 > vw ? r.left - 4 : r.right + 4;
      y = r.top - 4;
    }
    dot.style.left = x + window.scrollX + "px";
    dot.style.top = y + window.scrollY + "px";
  }

  function placeCard(el, tip, r, vw) {
    el.style.maxWidth = Math.min(320, vw - EDGE * 2) + "px";
    const w = el.offsetWidth;
    const h = el.offsetHeight;
    let side = tip.side;
    if (side === "right" && r.right + GAP + w > vw - EDGE) side = null;
    if (side === "left" && r.left - GAP - w < EDGE) side = null;
    let left, top;
    if (side === "right" || side === "left") {
      const y = anchorY(r);
      left = side === "right" ? r.right + GAP : r.left - GAP - w;
      top = Math.max(EDGE, y - 22);
      el.style.setProperty("--arrow-y", y - top + "px");
    } else {
      // Below the control, unless it was free to choose and only above fits.
      // Either way the card starts past the control's edge, so it never covers it.
      const below = tip.side === "below" || r.bottom + GAP + h <= window.innerHeight || r.top - GAP - h < 0;
      side = below ? "below" : "above";
      top = below ? r.bottom + GAP : r.top - GAP - h;
      const cx = r.left + r.width / 2;
      // Centred on the control, or starting at it when the control is tiny.
      const want = r.width < 48 ? cx - 24 : cx - w / 2;
      left = Math.max(EDGE, Math.min(want, vw - EDGE - w));
      el.style.setProperty("--arrow-x", Math.max(18, Math.min(cx - left, w - 18)) + "px");
    }
    el.dataset.side = side;
    el.style.left = left + window.scrollX + "px";
    el.style.top = top + window.scrollY + "px";
  }

  // When a tip opens, bring its control and card fully into view, once.
  function reveal(id, target, el) {
    if (shownId === id) return;
    shownId = id;
    if (!advanced) return;
    advanced = false;
    const a = target.getBoundingClientRect();
    const b = el.getBoundingClientRect();
    const top = Math.min(a.top, b.top) - EDGE;
    const bottom = Math.max(a.bottom, b.bottom) + EDGE;
    let dy = 0;
    if (bottom > window.innerHeight) dy = bottom - window.innerHeight;
    if (top - dy < 0) dy = top;
    // A plain jump: smooth scrolling never runs in a tab that isn't painting
    // (a background or embedded view), and then the tip would stay off-screen.
    if (dy) window.scrollBy(0, dy);
  }

  function draw() {
    frame = 0;
    readConfig();
    retireOutgrown();
    const items = pending();
    if (!items.length) {
      if (layer) layer.replaceChildren();
      dots.clear();
      card = null;
      return;
    }
    ensureLayer();
    if (!items.some((p) => p.tip.id === openId)) openId = items[0].tip.id;
    const vw = document.documentElement.clientWidth;
    const live = new Set(items.map((p) => p.tip.id));
    for (const [id, dot] of dots) {
      if (!live.has(id)) { dot.remove(); dots.delete(id); }
    }
    if (card && card.id !== openId) { card.el.remove(); card = null; }
    items.forEach((item) => {
      let dot = dots.get(item.tip.id);
      if (!dot) {
        dot = document.createElement("button");
        dot.type = "button";
        dot.className = "nsls-coach-dot";
        dot.setAttribute("aria-label", "Show tip: " + item.tip.title);
        dot.addEventListener("click", () => { openId = item.tip.id; draw(); });
        layer.appendChild(dot);
        dots.set(item.tip.id, dot);
      }
      const r = item.el.getBoundingClientRect();
      placeDot(dot, item.tip, r, vw);
      if (item.tip.id === openId) {
        if (!card) {
          card = { id: openId, el: buildCard(item.tip) };
          layer.appendChild(card.el);
        }
        placeCard(card.el, item.tip, r, vw);
        reveal(openId, item.el, card.el);
      }
    });
  }

  function schedule() {
    if (frame) return;
    // The animation frame folds a burst of layout changes into one draw; the
    // timer covers a page that isn't painting frames (a background tab or an
    // embedded view), which would otherwise never draw at all.
    frame = requestAnimationFrame(draw);
    setTimeout(() => {
      if (frame) { cancelAnimationFrame(frame); draw(); }
    }, 120);
  }

  window.addEventListener("resize", schedule);
  window.addEventListener("load", schedule);
  document.addEventListener("htmx:afterSettle", schedule);
  document.addEventListener("toolkit:did", (e) => did(e.detail && e.detail.action));
  // The companion's own controls: marking progress and adding a task.
  document.addEventListener("htmx:afterRequest", (e) => {
    const d = e.detail || {};
    if (!d.successful || !d.requestConfig) return;
    const path = d.requestConfig.path || "";
    if (path === "/set-progress") did("progress");
    else if (path === "/close-ready") did("close");
    else if (path === "/move-item" && d.elt && d.elt.closest && d.elt.closest(".nsls-add-item")) did("add");
  });
  if ("ResizeObserver" in window) new ResizeObserver(schedule).observe(document.body);
  schedule();

  // For pages that switch screens or reset themselves (the demo).
  window.__toolkitCallouts = {
    refresh: schedule,
    did: did,
    reset() {
      closedHere.clear();
      openId = null;
      shownId = null;
      schedule();
    },
  };
})();
