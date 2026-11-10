// First-run tips (coach marks) for Plan your day and the Command Center.
//
// Markup contract:
//   #nsls-callouts[data-screen][data-dismissed]  rendered inside <main> by
//       _components/callouts.html: which tip set this screen uses ("plan" |
//       "command") and the ids already dismissed (JSON array, read from the
//       companion's saved state)
//   [data-callout="<id>"]  a tip's target where it has no natural selector
//
// A tip's dot sits just outside its control's top-right corner, or on its
// left edge (dot: "left") for a control too small to share a corner with,
// like a drag handle.
//
// One tip is open at a time: a small card beside its control, with an arrow,
// never on top of it. Every other tip still waiting on this screen shows as a
// pulsing dot on its control; click a dot to open that tip. "Got it" closes a
// tip for good and opens the next; "Hide these tips" closes the screen's set.
// A tip whose control isn't on the page (no tasks yet, Top 3 full) waits until
// it is. Dismissals go to POST /callouts/dismiss unless the page installs its
// own store first (window.__toolkitCalloutStore — the setup.nsls.org demo).
(function () {
  "use strict";

  const TIPS = {
    plan: [
      { id: "plan-energy", target: '[data-callout="plan-energy"] .nsls-energy-row > div',
        title: "Start with your energy",
        body: "Pick Low, Medium or High. It's saved with today's note." },
      { id: "plan-add", target: "#plan-your-day .nsls-slot input",
        title: "Add a task here",
        body: "Type a priority and press Enter, or drag a suggestion into a slot." },
      { id: "plan-drag", target: "#plan-your-day [data-drag-item] .nsls-grip", dot: "left",
        title: "Click and drag to reorder",
        body: "Grab any task by its handle to reorder it, or move it between Top 3, Bonus and suggestions." },
      { id: "plan-lockin", target: '[data-callout="plan-lockin"]',
        title: "Lock in your day",
        body: "When your Top 3 looks right, click Done. Your Command Center opens." },
    ],
    command: [
      { id: "cc-drag", target: "#task-table [data-drag-item] .nsls-grip", dot: "left",
        title: "Click and drag to reorder",
        body: "Move tasks up and down, or between Top 3 and Bonus." },
      { id: "cc-progress", target: "#task-table [data-drag-item] .nsls-seg",
        title: "Mark your progress here",
        body: "Click 25, 50, 75 or 100 as you go. Anything under 100 carries over to tomorrow." },
      { id: "cc-add", target: '[data-callout="cc-add"]',
        title: "Add a task here",
        body: "Type it, pick Top 3 or Bonus, then click Add item." },
      { id: "cc-close", target: '[data-callout="cc-close"]',
        title: "Close your day",
        body: "When you're finished, click I'm done to close your day." },
    ],
  };

  const GAP = 14;          // target edge to card edge, room for the arrow
  const EDGE = 12;         // card never closer than this to the viewport side
  const reducedMotion = () =>
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const serverStore = {
    dismiss(ids) {
      const body = new URLSearchParams();
      ids.forEach((id) => body.append("id", id));
      return fetch("/callouts/dismiss", { method: "POST", body: body }).catch(() => {});
    },
  };
  const store = () => window.__toolkitCalloutStore || serverStore;

  let screen = "";
  let dismissed = new Set();
  // This tab's own dismissals: a <main> re-render that raced the POST must not
  // bring a closed tip back.
  const closedHere = new Set();
  let openId = null;
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
    for (const el of document.querySelectorAll(tip.target)) {
      if (el.getClientRects().length) return el;
    }
    return null;
  }

  // Tips waiting on this screen whose control is on the page, in tour order.
  function pending() {
    return (TIPS[screen] || [])
      .filter((tip) => !dismissed.has(tip.id))
      .map((tip) => ({ tip: tip, el: findTarget(tip) }))
      .filter((p) => p.el);
  }

  function ensureLayer() {
    if (layer && layer.isConnected) return;
    dots.clear();
    card = null;
    layer = document.createElement("div");
    layer.className = "nsls-coach-layer";
    document.body.appendChild(layer);
  }

  function dismiss(ids, advance) {
    ids.forEach((id) => { closedHere.add(id); dismissed.add(id); });
    store().dismiss(ids);
    openId = null;
    draw();
    // Walk the builder to the next tip only when they asked for it.
    if (advance && card) {
      const next = pending().find((p) => p.tip.id === card.id);
      const r = next && next.el.getBoundingClientRect();
      if (r && (r.top < 0 || r.bottom > window.innerHeight)) {
        next.el.scrollIntoView({ block: "center", behavior: reducedMotion() ? "auto" : "smooth" });
      }
    }
  }

  // "Tip 2 of 4": the tip's place in this screen's tour, which stays put as
  // earlier tips are closed.
  function stepLabel(tip) {
    const tour = TIPS[screen] || [];
    return tour.length > 1 ? "Tip " + (tour.indexOf(tip) + 1) + " of " + tour.length : "Tip";
  }

  function buildCard(item) {
    const el = document.createElement("div");
    el.className = "nsls-coach-card";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-label", item.tip.title);
    const step = document.createElement("div");
    step.className = "nsls-coach-step";
    step.textContent = stepLabel(item.tip);
    const title = document.createElement("p");
    title.className = "nsls-coach-title";
    title.textContent = item.tip.title;
    const body = document.createElement("p");
    body.className = "nsls-coach-body";
    body.textContent = item.tip.body;
    const foot = document.createElement("div");
    foot.className = "nsls-coach-foot";
    const skip = document.createElement("button");
    skip.type = "button";
    skip.className = "nsls-coach-skip";
    skip.textContent = "Hide these tips";
    skip.addEventListener("click", () => dismiss((TIPS[screen] || []).map((t) => t.id), false));
    const ok = document.createElement("button");
    ok.type = "button";
    ok.className = "nsls-coach-ok";
    ok.textContent = "Got it";
    ok.addEventListener("click", () => dismiss([item.tip.id], true));
    foot.append(skip, ok);
    el.append(step, title, body, foot);
    return el;
  }

  function placeDot(dot, tip, r, vw) {
    let x, y;
    if (tip.dot === "left") {
      x = r.left - 9;
      y = r.top + r.height / 2;
    } else {
      // Top-right corner; top-left if that's off-screen.
      x = r.right + 10 > vw ? r.left - 4 : r.right + 4;
      y = r.top - 4;
    }
    dot.style.left = x + window.scrollX + "px";
    dot.style.top = y + window.scrollY + "px";
  }

  function placeCard(el, r, vw) {
    const w = Math.min(300, vw - EDGE * 2);
    el.style.width = w + "px";
    const h = el.offsetHeight;
    // Below the control unless that runs off the bottom and above fits. Either
    // way the card starts past the control's edge, so it never covers it.
    const below = r.bottom + GAP + h <= window.innerHeight || r.top - GAP - h < 0;
    const top = below ? r.bottom + GAP : r.top - GAP - h;
    const cx = r.left + r.width / 2;
    // Centred on the control, or starting at it when the control is tiny (a
    // drag handle at a card's edge), so the card stays over the page content.
    const want = r.width < 48 ? cx - 24 : cx - w / 2;
    const left = Math.max(EDGE, Math.min(want, vw - EDGE - w));
    el.dataset.side = below ? "below" : "above";
    el.style.setProperty("--arrow-x", Math.max(18, Math.min(cx - left, w - 18)) + "px");
    el.style.left = left + window.scrollX + "px";
    el.style.top = top + window.scrollY + "px";
  }

  function draw() {
    frame = 0;
    readConfig();
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
          card = { id: openId, el: buildCard(item) };
          layer.appendChild(card.el);
        }
        placeCard(card.el, r, vw);
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
  if ("ResizeObserver" in window) new ResizeObserver(schedule).observe(document.body);
  schedule();

  // For pages that switch screens or reset themselves (the demo).
  window.__toolkitCallouts = {
    refresh: schedule,
    reset() {
      closedHere.clear();
      openId = null;
      schedule();
    },
  };
})();
