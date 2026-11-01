// Light / dark theme. Dark is the default; the button in the top bar switches
// and the choice is remembered in this browser. Loaded in <head> without
// defer so <html data-theme> is set before the page paints (no light flash).
(function () {
  "use strict";
  var KEY = "nsls-companion:theme";
  var root = document.documentElement;

  function saved() {
    try { return window.localStorage.getItem(KEY); } catch (_) { return null; }
  }

  function apply(theme, persist) {
    theme = theme === "light" ? "light" : "dark";
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
    if (persist) {
      // A private window may refuse storage; the page still switches.
      try { window.localStorage.setItem(KEY, theme); } catch (_) {}
    }
    var toggle = document.querySelector("[data-theme-toggle]");
    if (toggle) {
      toggle.setAttribute("aria-label", theme === "dark" ? "Switch to the light theme" : "Switch to the dark theme");
    }
  }

  apply(saved());
  document.addEventListener("DOMContentLoaded", function () { apply(root.dataset.theme); });
  document.addEventListener("click", function (e) {
    if (!e.target.closest || !e.target.closest("[data-theme-toggle]")) return;
    apply(root.dataset.theme === "dark" ? "light" : "dark", true);
  });
})();
