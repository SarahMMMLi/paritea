// Boot: starts the engine, shows its status in the header, and routes between the tool pages.

import { Engine } from "./engine.js";
import { renderDiagrams } from "./tools/diagrams.js";
import { renderHome } from "./tools/home.js";
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
  diagrams: [renderDiagrams, "Diagrams · paritea"],
  webs: [renderWebs, "Pauli webs · paritea"],
};

function route() {
  leaveHandlers.forEach((fn) => fn());
  leaveHandlers = [];
  stepKeys = null;
  const [path, search = ""] = location.hash.replace(/^#\/?/, "").split("?");
  const [render, title] = ROUTES[path] ?? ROUTES[""];
  document.title = title;
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
