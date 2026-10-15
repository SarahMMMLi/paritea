// Page logic: the tool catalogue (home) and the Pauli webs tool.

import { DiagramView } from "./diagram-view.js";
import { Engine } from "./engine.js";

// Every tool paritea will offer. Only Pauli webs is live in this prototype; the others show what is planned.
const TOOLS = [
  { id: "diagrams", group: "Build", title: "Diagrams", summary: "Build a ZX diagram from a generator, or import your own.",
    provide: "A generator and its size, or a PyZX, QASM or stim file", get: "An interactive drawing with its size and inputs/outputs" },
  { id: "webs", group: "Analyse", title: "Pauli webs", live: true, summary: "Find the stabilising webs and detecting regions of a diagram.",
    provide: "A ZX diagram", get: "Every web drawn on the diagram, an edge table and Python code" },
  { id: "noise", group: "Analyse", title: "Noise model", summary: "Place independent X, Y and Z faults on the edges of a diagram.",
    provide: "A diagram and X/Y/Z fault weights", get: "The list of faults with their weights" },
  { id: "propagation", group: "Analyse", title: "Fault propagation", summary: "See where each fault ends up on the boundary and which detectors it flips.",
    provide: "A noise model", get: "Each fault's boundary Paulis and flipped detecting regions" },
  { id: "semantic", group: "Compare", title: "Semantic equivalence", summary: "Check whether two diagrams have the same stabilisers on their boundary.",
    provide: "Two diagrams", get: "Equivalent or not, with both stabiliser sets" },
  { id: "fault", group: "Compare", title: "Fault equivalence", summary: "Check whether two noisy diagrams behave the same up to a fault weight.",
    provide: "Two diagrams or noise models and a maximum weight", get: "Equivalent up to that weight, or not" },
  { id: "dem", group: "stim", title: "stim → detector error model", summary: "Turn a stim circuit into paritea's detector error model.",
    provide: "A stim circuit, from a preset or your own", get: "A .dem file with its detectors, observables and errors" },
  { id: "console", group: "Advanced", title: "Python console", summary: "Use the whole paritea API from Python, right in the page.",
    provide: "Python code", get: "Its output, with paritea already imported" },
];

// The first diagram shown: two rounds, so that it has detecting regions as well as stabilising webs.
const FIRST_EXAMPLE = { generator: "Rotated surface code memory experiment", params: { distance: 3, rounds: 2 } };

const app = document.getElementById("app");
const pill = document.getElementById("engine-status");
const engine = new Engine();
let engineMessage = "Starting the engine…";

const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

function setPill(state, label) {
  pill.dataset.state = state;
  pill.querySelector(".engine-label").textContent = label;
}

engine.addEventListener("status", ({ detail }) => {
  engineMessage = detail.message;
  if (detail.stage === "ready") {
    engineMessage = `Engine ready in ${detail.info.seconds.toFixed(1)} s — Python ${detail.info.python} running in this page.`;
    setPill("ready", detail.message);
  } else if (detail.stage === "preview") {
    engineMessage = `${engine.reason} Showing results computed ahead of time.`;
    setPill("preview", detail.message);
  } else {
    setPill("loading", detail.message);
  }
  document.querySelectorAll("[data-engine-message]").forEach((n) => (n.textContent = engineMessage));
});

// ---------------------------------------------------------------- Home

function renderHome() {
  const cards = TOOLS.map((t) => `
    <article class="tool-card ${t.live ? "live" : "planned"}">
      <div class="card-top"><span class="group">${t.group}</span>
        <span class="badge ${t.live ? "badge-live" : "badge-planned"}">${t.live ? "Live" : "Planned"}</span></div>
      <h3>${t.title}</h3>
      <p>${t.summary}</p>
      <dl class="io"><dt>You provide</dt><dd>${t.provide}</dd><dt>You get</dt><dd>${t.get}</dd></dl>
      ${t.live ? `<a class="card-link" href="#/${t.id}">Open ${t.title} →</a>` : ""}
    </article>`).join("");

  app.innerHTML = `
    <section class="hero">
      <p class="eyebrow">Fault tolerance with ZX diagrams</p>
      <h1>paritea, in your browser</h1>
      <p class="lead">paritea finds Pauli webs, builds noise models and checks fault equivalence of Clifford ZX diagrams.
        This page runs it for you: Python and paritea's Rust core are compiled to WebAssembly, so there is nothing to
        install and nothing leaves your computer.</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="#/webs">Compute Pauli webs →</a>
        <span class="hint" data-engine-message>${escapeHtml(engineMessage)}</span>
      </div>
    </section>
    <div class="section-head"><h2>Tools</h2><p>Each tool says what it needs and what it gives back.</p></div>
    <div class="grid">${cards}</div>
    <section class="how" aria-label="How it works">
      <div class="how-step"><span class="step-n">1</span><div><strong>Loads once</strong>
        <p>The first visit downloads Python and paritea (about 12 MB); later visits come from the browser cache.</p></div></div>
      <div class="how-step"><span class="step-n">2</span><div><strong>You choose the inputs</strong>
        <p>Every input has a sensible default, a valid range and a short explanation.</p></div></div>
      <div class="how-step"><span class="step-n">3</span><div><strong>paritea computes locally</strong>
        <p>Results are drawn on the diagram and come with the Python code that reproduces them.</p></div></div>
    </section>`;
}

// ---------------------------------------------------------------- Pauli webs tool

let lastInputs = null; // keeps the form's values when navigating away and back

async function renderWebs() {
  app.innerHTML = `
    <nav class="crumbs"><a href="#/">Tools</a> / Pauli webs</nav>
    <header class="tool-head">
      <h1>Pauli webs</h1>
      <p class="lead">Find the stabilising webs and detecting regions of a ZX diagram, and see each one drawn on the diagram.</p>
    </header>
    <div class="io-cards">
      <section class="io-card"><h2>You provide</h2>
        <ol><li><strong>A ZX diagram.</strong> Pick a generator and its size below.</li></ol></section>
      <section class="io-card"><h2>You get</h2>
        <ul><li>How many <strong>stabilising webs</strong> and <strong>detecting regions</strong> the diagram has</li>
          <li>Each web drawn on the diagram, with the Pauli (X, Y or Z) it puts on every edge</li>
          <li>An edge-by-edge table, and Python code that reproduces the result</li></ul></section>
    </div>
    <form class="panel" id="webs-form" novalidate>
      <div class="step"><span class="step-n">1</span><div class="step-body">
        <label class="field-label" for="generator">Diagram</label>
        <select id="generator" name="generator"></select>
        <p class="help" id="generator-help"></p>
        <div class="params" id="params"></div>
      </div></div>
      <div class="actions">
        <button class="btn btn-primary" id="run" type="submit">Compute webs</button>
        <span class="hint" id="run-hint">Usually well under a second · <kbd>Ctrl</kbd> + <kbd>Enter</kbd></span>
      </div>
    </form>
    <section class="results" id="results" aria-live="polite">
      <div class="empty">Results appear here: the number of webs, each web on the diagram, an edge table and Python code.</div>
    </section>`;

  const { generators } = await engine.catalogue;
  const select = document.getElementById("generator");
  const paramsBox = document.getElementById("params");
  const help = document.getElementById("generator-help");
  select.innerHTML = generators.map((g) => `<option>${escapeHtml(g.name)}</option>`).join("");

  const showParams = (values = {}) => {
    const g = generators.find((x) => x.name === select.value);
    help.textContent = g.description;
    paramsBox.innerHTML = g.params.map((p) => `
      <div class="param">
        <label for="p-${p.key}">${escapeHtml(p.label)} <span class="range">(${p.min}–${p.max})</span></label>
        <input id="p-${p.key}" name="${p.key}" type="number" min="${p.min}" max="${p.max}" step="1" required
          value="${values[p.key] ?? p.default}" ${p.help ? `title="${escapeHtml(p.help)}"` : ""}>
      </div>`).join("");
  };
  const initial = lastInputs ?? FIRST_EXAMPLE;
  select.value = initial.generator;
  showParams(initial.params);
  select.addEventListener("change", () => showParams());

  const form = document.getElementById("webs-form");
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    compute(generators.find((x) => x.name === select.value));
  });
  form.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) form.requestSubmit();
  });
}

function readParams(generator) {
  const params = {};
  for (const p of generator.params) {
    const input = document.getElementById(`p-${p.key}`);
    const value = Number(input.value);
    if (!Number.isInteger(value) || value < p.min || value > p.max) {
      input.focus();
      throw new Error(`${p.label} must be a whole number from ${p.min} to ${p.max}.`);
    }
    params[p.key] = value;
  }
  return params;
}

async function compute(generator) {
  const results = document.getElementById("results");
  const button = document.getElementById("run");
  let params;
  try {
    params = readParams(generator);
  } catch (err) {
    results.innerHTML = `<div class="alert alert-error"><strong>Check the inputs.</strong> ${escapeHtml(err.message)}</div>`;
    return;
  }
  lastInputs = { generator: generator.name, params };
  button.disabled = true;
  button.innerHTML = `<span class="spinner" aria-hidden="true"></span> ${engine.mode === "starting" ? "Waiting for the engine…" : "Computing…"}`;
  const before = pill.dataset.state;
  if (engine.mode === "live") setPill("busy", "Computing…");
  try {
    const result = await engine.run("pauli_webs", { generator: generator.name, params });
    showResult(result, generator);
  } catch (err) {
    showError(err, generator);
  } finally {
    button.disabled = false;
    button.textContent = "Compute webs";
    if (engine.mode === "live") setPill("ready", `Ready · Python ${engine.info.python} in your browser`);
    else if (before === "preview") setPill("preview", "Preview · precomputed results");
  }
}

function showError(err, generator) {
  const results = document.getElementById("results");
  if (err.type === "PreviewOnly") {
    engine.catalogue.then(({ results: available }) => {
      const options = Object.keys(available).filter((k) => k.startsWith(`${generator.name}|`)).map((k) => k.split("|")[1].replaceAll(",", ", "));
      results.innerHTML = `<div class="alert alert-preview"><strong>Not available in preview mode.</strong>
        ${escapeHtml(err.message)} For this diagram, try: ${options.map(escapeHtml).join(" · ") || "another diagram"}.</div>`;
    });
    return;
  }
  results.innerHTML = `<div class="alert alert-error"><strong>Computing the Pauli webs failed.</strong> ${escapeHtml(err.message)}
    ${err.traceback ? `<details><summary>Technical details</summary><pre>${escapeHtml(err.traceback)}</pre></details>` : ""}</div>`;
}

function showResult(result, generator) {
  window.lastResult = result; // for the browser check in app/build/check_site.py
  const results = document.getElementById("results");
  const nStab = result.stabilisers.length;
  const nReg = result.regions.length;
  const headline = `${plural(nStab, "stabilising web")} and ${nReg ? plural(nReg, "detecting region") : "no detecting regions"}`;
  const paramText = generator.params.map((p) => `${p.label.toLowerCase()} ${result.params[p.key]}`).join(", ");
  const total = result.seconds.build + result.seconds.webs;
  const where = result.precomputed
    ? `<span class="where preview">precomputed natively (preview mode)</span>`
    : `computed in ${total < 1 ? `${Math.max(1, Math.round(total * 1000))} ms` : `${total.toFixed(2)} s`} <span class="where">in your browser</span>`;
  const stats = Object.entries(result.summary).map(([k, v]) => `
    <div class="stat"><div class="stat-label">${escapeHtml(k)}</div><div class="stat-value">${v}</div></div>`).join("");

  results.innerHTML = `
    ${result.precomputed ? `<div class="alert alert-preview">${escapeHtml(engineMessage)}</div>` : ""}
    <div class="result-head">
      <h2 class="headline">${headline}</h2>
      <p class="meta">${escapeHtml(result.generator)}, ${escapeHtml(paramText)} · ${where}</p>
    </div>
    <div class="stats">${stats}</div>
    <div class="viewer">
      <div class="viewer-bar">
        <div class="segmented" role="tablist" aria-label="Which webs to show">
          <button type="button" role="tab" data-kind="stabilisers">Stabilising webs<span class="count">${nStab}</span></button>
          <button type="button" role="tab" data-kind="regions">Detecting regions<span class="count">${nReg}</span></button>
          <button type="button" role="tab" data-kind="none">Diagram only</button>
        </div>
        <div class="stepper">
          <button type="button" class="icon-btn" id="prev" aria-label="Previous web">‹</button>
          <span id="which"></span>
          <button type="button" class="icon-btn" id="next" aria-label="Next web">›</button>
        </div>
        <div class="viewer-tools">
          <button type="button" class="icon-btn" id="zoom-out" aria-label="Zoom out">−</button>
          <button type="button" class="icon-btn" id="zoom-in" aria-label="Zoom in">+</button>
          <button type="button" class="btn btn-ghost btn-small" id="fit">Fit</button>
        </div>
      </div>
      <div class="canvas-wrap">
        <svg class="diagram" role="img" aria-label="The diagram, with the selected web highlighted"></svg>
        <div class="tooltip" role="presentation"></div>
        <span class="canvas-hint">Drag to move · pinch or Ctrl + scroll to zoom · ← → to step</span>
      </div>
      <div class="legend">
        <span class="legend-item"><span class="swatch X"></span>X on edge</span>
        <span class="legend-item"><span class="swatch Y"></span>Y on edge</span>
        <span class="legend-item"><span class="swatch Z"></span>Z on edge</span>
        <span class="legend-item"><span class="dot-node Z"></span>Z spider</span>
        <span class="legend-item"><span class="dot-node X"></span>X spider</span>
        <span class="legend-item"><span class="dot-node H"></span>H box</span>
        <span class="legend-item"><span class="dot-node B"></span>Boundary</span>
      </div>
    </div>
    <div class="below">
      <section class="card">
        <div class="card-head"><h3 id="table-title">Edges in this web</h3></div>
        <div class="table-wrap" id="edge-table"></div>
      </section>
      <section class="card">
        <div class="card-head"><h3>Python code that reproduces this</h3>
          <button type="button" class="btn btn-ghost btn-small" id="copy">Copy</button></div>
        <pre class="code"><code>${escapeHtml(result.code)}</code></pre>
      </section>
    </div>`;

  const view = new DiagramView(results.querySelector(".canvas-wrap"));
  view.setDiagram(result.diagram);
  const endpoints = new Map(result.diagram.edges.map(([e, s, t]) => [e, `${s} – ${t}`]));
  const state = { kind: nStab ? "stabilisers" : "none", index: 0 };

  const draw = () => {
    const webs = state.kind === "none" ? [] : result[state.kind];
    const web = webs[state.index];
    results.querySelectorAll(".segmented button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.kind === state.kind)));
    const noun = state.kind === "regions" ? "Region" : "Web";
    document.getElementById("which").textContent = webs.length ? `${noun} ${state.index + 1} of ${webs.length}` : "—";
    document.getElementById("prev").disabled = state.index <= 0;
    document.getElementById("next").disabled = state.index >= webs.length - 1;
    view.setWeb(web);

    const table = document.getElementById("edge-table");
    if (!web) {
      document.getElementById("table-title").textContent = "Edges in this web";
      table.innerHTML = `<p class="muted-cell">${state.kind === "none" ? "Choose stabilising webs or detecting regions to list a web's edges."
        : `This diagram has no ${state.kind === "regions" ? "detecting regions" : "stabilising webs"}.`}</p>`;
      return;
    }
    document.getElementById("table-title").textContent = `Edges in ${noun.toLowerCase()} ${state.index + 1} (${web.length})`;
    table.innerHTML = `<table><thead><tr><th>Edge</th><th>Between nodes</th><th>Pauli</th></tr></thead><tbody>${web
      .map(([e, p]) => `<tr><td>${e}</td><td>${endpoints.get(e)}</td><td><span class="pauli-chip ${p}">${p}</span></td></tr>`)
      .join("")}</tbody></table>`;
  };

  const step = (delta) => {
    const webs = state.kind === "none" ? [] : result[state.kind];
    const next = state.index + delta;
    if (next >= 0 && next < webs.length) {
      state.index = next;
      draw();
    }
  };
  results.querySelectorAll(".segmented button").forEach((b) => b.addEventListener("click", () => {
    state.kind = b.dataset.kind;
    state.index = 0;
    draw();
  }));
  document.getElementById("prev").addEventListener("click", () => step(-1));
  document.getElementById("next").addEventListener("click", () => step(1));
  document.getElementById("zoom-in").addEventListener("click", () => view.zoom(0.8));
  document.getElementById("zoom-out").addEventListener("click", () => view.zoom(1.25));
  document.getElementById("fit").addEventListener("click", () => view.fit());
  document.getElementById("copy").addEventListener("click", async (e) => {
    await navigator.clipboard.writeText(result.code);
    e.target.textContent = "Copied";
    setTimeout(() => (e.target.textContent = "Copy"), 1500);
  });
  stepKeys = step;
  draw();
}

let stepKeys = null;
document.addEventListener("keydown", (e) => {
  if (!stepKeys || ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
  if (e.key === "ArrowLeft") stepKeys(-1);
  if (e.key === "ArrowRight") stepKeys(1);
});

// ---------------------------------------------------------------- Routing

function route() {
  stepKeys = null;
  const page = location.hash.replace(/^#\/?/, "");
  if (page === "webs") renderWebs();
  else renderHome();
  window.scrollTo(0, 0);
}
window.addEventListener("hashchange", route);
route();

