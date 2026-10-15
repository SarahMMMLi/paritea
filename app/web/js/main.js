// Boot: starts the engine, shows its status in the header, and routes between the tool pages.

import { Engine } from "./engine.js";
import { renderConsole } from "./tools/console.js";
import { shelf } from "./shelf.js";
import { renderDem } from "./tools/dem.js";
import { renderDiagrams } from "./tools/diagrams.js";
import { renderFault } from "./tools/fault.js";
import { TOOLS, renderHome } from "./tools/home.js";
import { renderNoise } from "./tools/noise.js";
import { renderPropagation } from "./tools/propagation.js";
import { renderSemantic } from "./tools/semantic.js";
import { renderWebs } from "./tools/webs.js";

const app = document.getElementById("app");
const pill = document.getElementById("engine-status");
const engine = new Engine();
let engineMessage = "Starting the engine…";
let readyLabel = "Ready";
let stepKeys = null;
let leaveHandlers = [];

function setPill(state, label) {
  pill.dataset.state = state;
  pill.querySelector(".engine-label").textContent = label;
}

engine.addEventListener("status", ({ detail }) => {
  engineMessage = detail.message;
  if (detail.stage === "ready") {
    engineMessage = `Engine ready in ${detail.info.seconds.toFixed(1)} s — Python ${detail.info.python} running in this page.`;
    readyLabel = detail.message;
    setPill("ready", detail.message);
  } else if (detail.stage === "preview") {
    engineMessage = `${engine.reason} Showing results computed ahead of time.`;
    setPill("preview", detail.message);
  } else {
    setPill("loading", detail.message);
  }
  document.querySelectorAll("[data-engine-message]").forEach((n) => (n.textContent = engineMessage));
});

// The header's tools menu: every live tool, grouped as in the catalogue on the home page.
const menu = document.getElementById("tools-menu");
const groups = [...new Set(TOOLS.filter((t) => t.live).map((t) => t.group))];
document.getElementById("tools-menu-panel").innerHTML = `${groups
  .map(
    (group) => `<div class="menu-group"><span class="menu-group-name">${group}</span>${TOOLS.filter((t) => t.live && t.group === group)
      .map((t) => `<a href="#/${t.id}" data-tool="${t.id}">${t.title}</a>`)
      .join("")}</div>`,
  )
  .join("")}<a class="menu-all" href="#/">All tools, with what each needs and gives</a>`;
document.addEventListener("click", (e) => {
  if (menu.open && (!menu.contains(e.target) || e.target.closest(".menu-panel a"))) menu.open = false;
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && menu.open) {
    menu.open = false;
    menu.querySelector("summary").focus();
  }
});

// The header's theme switch: flips between light and dark, overriding (and remembering) the system setting.
const themeButton = document.getElementById("theme-toggle");
const systemDark = window.matchMedia("(prefers-color-scheme: dark)");
const isDark = () => (document.documentElement.dataset.theme ?? (systemDark.matches ? "dark" : "light")) === "dark";
function labelThemeButton() {
  const label = isDark() ? "Switch to the light theme" : "Switch to the dark theme";
  themeButton.setAttribute("aria-label", label);
  themeButton.title = label;
}
themeButton.addEventListener("click", () => {
  const theme = isDark() ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem("paritea-theme", theme);
  } catch {
    // Storage can be unavailable (private windows); the switch still works for this visit.
  }
  labelThemeButton();
});
systemDark.addEventListener("change", labelThemeButton);
labelThemeButton();

// A restarted engine has an empty shelf, so the page's copy is emptied too.
engine.addEventListener("restart", () => shelf.clear());

// What every page gets: where to render, the engine, and a few shared hooks.
const ctx = {
  app,
  engine,
  engineMessage: () => engineMessage,
  setBusy(busy) {
    if (engine.mode === "live") setPill(busy ? "busy" : "ready", busy ? "Computing…" : readyLabel);
  },
  setStepKeys(fn) {
    stepKeys = fn;
  },
  onLeave(fn) {
    leaveHandlers.push(fn);
  },
};

const ROUTES = {
  "": [renderHome, "paritea in your browser"],
  console: [renderConsole, "Python console · paritea"],
  dem: [renderDem, "stim → detector error model · paritea"],
  diagrams: [renderDiagrams, "Diagrams · paritea"],
  fault: [renderFault, "Fault equivalence · paritea"],
  noise: [renderNoise, "Noise model · paritea"],
  propagation: [renderPropagation, "Fault propagation · paritea"],
  semantic: [renderSemantic, "Semantic equivalence · paritea"],
  webs: [renderWebs, "Pauli webs · paritea"],
};

function route() {
  leaveHandlers.forEach((fn) => fn());
  leaveHandlers = [];
  stepKeys = null;
  const [path, search = ""] = location.hash.replace(/^#\/?/, "").split("?");
  const [render, title] = ROUTES[path] ?? ROUTES[""];
  document.title = title;
  menu.open = false;
  menu.querySelectorAll("[data-tool]").forEach((a) =>
    a.dataset.tool === path ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"),
  );
  render(ctx, Object.fromEntries(new URLSearchParams(search)));
  window.scrollTo(0, 0);
}

document.addEventListener("keydown", (e) => {
  if (!stepKeys || ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
  if (e.key === "ArrowLeft") stepKeys(-1);
  if (e.key === "ArrowRight") stepKeys(1);
});

window.addEventListener("hashchange", route);
route();
