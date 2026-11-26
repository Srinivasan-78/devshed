/* DevShed shared color-scheme & iframe sync controller */
(function () {
  "use strict";

  const STORAGE_KEY = "devshed-color-scheme";

  function getMeta() {
    return document.querySelector('meta[name="color-scheme"]');
  }

  function systemPrefersDark() {
    return Boolean(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  }

  function isRenderedDark() {
    const meta = getMeta();
    const content = meta ? meta.content : "light dark";
    if (content === "dark") return true;
    if (content === "light") return false;
    return systemPrefersDark();
  }

  function applyContent(content) {
    const meta = getMeta();
    if (meta) meta.content = content;
    const isDark = content === "dark" || (content === "light dark" && systemPrefersDark());
    document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
    const frame = document.getElementById("tool-frame");
    if (frame && frame.contentWindow) {
      frame.contentWindow.postMessage({ type: "devshed-color-scheme", content }, "*");
    }
  }

  function readStored() {
    try {
      return localStorage.getItem(STORAGE_KEY) || "light dark";
    } catch (e) {
      return "light dark";
    }
  }

  function toggleTheme() {
    const next = isRenderedDark() ? "light" : "dark";
    const sys = systemPrefersDark() ? "dark" : "light";
    try {
      if (next === sys) {
        localStorage.removeItem(STORAGE_KEY);
      } else {
        localStorage.setItem(STORAGE_KEY, next);
      }
    } catch (e) {}
    applyContent(next === sys ? "light dark" : next);
  }

  if (window.self !== window.top) {
    document.documentElement.classList.add("in-shell");
  }

  applyContent(readStored());

  window.addEventListener("storage", (e) => {
    if (e.key === STORAGE_KEY) applyContent(e.newValue || "light dark");
  });

  window.addEventListener("message", (e) => {
    if (e.data && e.data.type === "devshed-color-scheme") {
      applyContent(e.data.content || "light dark");
    }
  });

  if (window.matchMedia) {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", () => applyContent(readStored()));
  }

  window.DevShedTheme = { applyContent, toggleTheme, readStored, isRenderedDark };
})();
