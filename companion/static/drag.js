// Drag-and-drop for the vertical task lanes (Plan-your-day + Command Center).
//
// Markup contract:
//   [data-drag-view="plan"|"command"]  the swappable container (has an id);
//                                      every request replaces it
//   [data-drop-lane="top_3"|"bonus"]   a lane that accepts drops
//   [data-drag-item]                   a draggable card, with data-text
//                                      (its title), data-lane (sent as
//                                      `from`), data-est
//   [data-plan-pill]                   a Plan-your-day destination button
//
// All listeners are delegated on document, so HTMX swaps never need a
// re-bind. Requests go through htmx.ajax with the card as `source`, so the
// page's inherited hx-vals (the note date) ride along like any hx-post.
(function () {
  "use strict";

  let drag = null;         // {card, view, fromLane, fromIndex}
  let downTarget = null;   // where the pointer went down — gates dragstart
  let marker = null;       // the drop-position line
  let scrollVelocity = 0;
  let scrollFrame = null;

  const cards = (stack) =>
    Array.from(stack.querySelectorAll(":scope > [data-drag-item]"));
  const stackOf = (lane) => lane.querySelector(".nsls-lane-stack");

  function post(source, path, values) {
    const view = source.closest("[data-drag-view]");
    if (!view || !window.htmx) return;
    htmx.ajax("POST", path, {
      source: source,
      target: "#" + view.id,
      swap: "outerHTML",
      values: Object.assign({ view: view.dataset.dragView }, values),
    });
  }

  // ---- auto-scroll while dragging near the top/bottom edge ---------------
  function runScroll() {
    if (!drag || scrollVelocity === 0) { scrollFrame = null; return; }
    window.scrollBy(0, scrollVelocity);
    scrollFrame = window.requestAnimationFrame(runScroll);
  }
  function updateScroll(clientY) {
    const edge = 70;
    scrollVelocity = clientY < edge ? -14 : clientY > window.innerHeight - edge ? 14 : 0;
    if (scrollVelocity !== 0 && scrollFrame === null) {
      scrollFrame = window.requestAnimationFrame(runScroll);
    }
  }
  function stopScroll() {
    if (scrollFrame !== null) window.cancelAnimationFrame(scrollFrame);
    scrollFrame = null;
    scrollVelocity = 0;
  }

  // ---- drop position ------------------------------------------------------
  // Index among the lane's cards with the dragged card left out — the same
  // counting /move-item uses ("position after the task leaves its place").
  function dropIndex(stack, clientY) {
    const others = cards(stack).filter((c) => c !== drag.card);
    for (let i = 0; i < others.length; i++) {
      const r = others[i].getBoundingClientRect();
      if (clientY < r.top + r.height / 2) return { index: i, before: others[i] };
    }
    return { index: others.length, before: null };
  }

  function showMarker(lane, stack, before) {
    if (!marker) {
      marker = document.createElement("div");
      marker.className = "nsls-drop-marker";
    }
    if (before) {
      stack.insertBefore(marker, before);
    } else {
      // After the last card, ahead of any add box / empty-slot rows.
      const all = cards(stack).filter((c) => c !== drag.card);
      const last = all[all.length - 1];
      if (last) last.after(marker);
      else stack.prepend(marker);
    }
    document.querySelectorAll(".nsls-lane.is-drag-over").forEach((l) => {
      if (l !== lane) l.classList.remove("is-drag-over");
    });
    lane.classList.add("is-drag-over");
  }

  function clearDropUi() {
    if (marker) marker.remove();
    document.querySelectorAll(".nsls-lane.is-drag-over")
      .forEach((l) => l.classList.remove("is-drag-over"));
  }

  // ---- drag lifecycle -----------------------------------------------------
  // Remember where the current press started; forget it once the press ends,
  // so a finished click in a text box can never veto a later drag.
  document.addEventListener("pointerdown", (e) => { downTarget = e.target; }, true);
  document.addEventListener("pointerup", () => { downTarget = null; }, true);

  document.addEventListener("dragstart", (e) => {
    const card = e.target.closest && e.target.closest("[data-drag-item]");
    if (!card) return;
    // Starting on a text box or button means select / click, not drag.
    const from = downTarget || e.target;
    if (from && from.closest && from.closest("input, button, textarea, select, a")) {
      e.preventDefault();
      return;
    }
    const view = card.closest("[data-drag-view]");
    const lane = card.closest("[data-drop-lane]");
    drag = {
      card: card,
      view: view,
      fromLane: card.dataset.lane,
      fromIndex: lane ? cards(stackOf(lane)).indexOf(card) : -1,
    };
    card.classList.add("is-dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", card.dataset.text || "");
  });

  document.addEventListener("dragover", (e) => {
    if (!drag) return;
    updateScroll(e.clientY);
    const lane = e.target.closest && e.target.closest("[data-drop-lane]");
    if (!lane || lane.closest("[data-drag-view]") !== drag.view) {
      clearDropUi();
      return;
    }
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    const stack = stackOf(lane);
    showMarker(lane, stack, dropIndex(stack, e.clientY).before);
  });

  document.addEventListener("drop", (e) => {
    if (!drag) return;
    stopScroll();
    const lane = e.target.closest && e.target.closest("[data-drop-lane]");
    if (!lane || lane.closest("[data-drag-view]") !== drag.view) return;
    e.preventDefault();
    const to = lane.dataset.dropLane;
    const { index } = dropIndex(stackOf(lane), e.clientY);
    const card = drag.card;
    const unchanged = to === drag.fromLane && index === drag.fromIndex;
    clearDropUi();
    card.classList.remove("is-dragging");
    drag = null;
    downTarget = null;
    if (unchanged) return;
    post(card, "/move-item", {
      text: card.dataset.text,
      from: card.dataset.lane,
      to: to,
      position: String(index),
      est: card.dataset.est || "",
    });
  });

  document.addEventListener("dragend", () => {
    stopScroll();
    clearDropUi();
    if (drag) drag.card.classList.remove("is-dragging");
    drag = null;
    downTarget = null;
  });

  // ---- Plan-your-day destination buttons ----------------------------------
  document.addEventListener("click", (e) => {
    const btn = e.target.closest && e.target.closest("[data-plan-pill]");
    if (!btn || btn.disabled) return;
    const card = btn.closest("[data-drag-item]");
    if (!card) return;
    const act = btn.dataset.planPill;
    if (act === "pri" || act === "bonus") {
      post(card, "/move-item", {
        text: card.dataset.text,
        from: card.dataset.lane,
        to: act === "pri" ? "top_3" : "bonus",
        est: card.dataset.est || "",
      });
    } else {
      post(card, "/plan-action", { text: card.dataset.text, action: act });
    }
  });

  // A renamed card must drag and click under its new title.
  document.addEventListener("change", (e) => {
    const input = e.target.closest && e.target.closest(".nsls-tcard-title");
    if (!input) return;
    const card = input.closest("[data-drag-item]");
    if (card && input.value.trim()) card.dataset.text = input.value.trim();
  });

  // Empty Top 3 slots and the Bonus add box submit on Enter / change; a
  // blank box sends nothing. (htmx trigger filters can't read the box's
  // value, so the guard lives here.)
  document.addEventListener("htmx:beforeRequest", (e) => {
    const elt = e.detail && e.detail.elt;
    if (elt && elt.matches && elt.matches(".nsls-slot input") && !elt.value.trim()) {
      e.preventDefault();
    }
  });

  // htmx.ajax requests carry no hx-on handler — surface their errors too.
  document.addEventListener("htmx:responseError", (e) => {
    const src = e.detail && e.detail.elt;
    if (src && src.closest && src.closest("[data-drag-item]") &&
        typeof window.__toolkitErrorToast === "function") {
      window.__toolkitErrorToast(e);
    }
  });
})();
