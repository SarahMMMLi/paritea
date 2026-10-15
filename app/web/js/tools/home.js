// Home: what paritea is, the catalogue of tools (what each needs and gives) and how the page works.

import { shelf } from "../shelf.js";
import { escapeHtml, plural } from "../ui.js";

// Every tool paritea will offer; `live` ones work today, the others show what is planned.
export const TOOLS = [
  { id: "diagrams", group: "Build", title: "Diagrams", live: true,
    summary: "Generate a ZX diagram, open a ready-made one or import your own.",
    provide: "A generator and its size, an example, or a PyZX / QASM file",
    get: "An interactive drawing, a summary, files to download and Python code" },
  { id: "webs", group: "Analyse", title: "Pauli webs", live: true,
    summary: "Find the stabilising webs and detecting regions of a diagram.",
    provide: "Any diagram on your shelf, or a generator",
    get: "Every web drawn on the diagram, an edge table and Python code" },
  { id: "noise", group: "Analyse", title: "Noise model", live: true,
    summary: "Place independent X, Y and Z faults on the edges of a diagram.",
    provide: "A diagram, X/Y/Z fault weights and the noise-free edges",
    get: "Every fault with its weight, a JSON file and Python code" },
  { id: "propagation", group: "Analyse", title: "Fault propagation", live: true,
    summary: "See where each fault ends up on the boundary and which detectors it flips.",
    provide: "A noise model from your shelf",
    get: "Every effect: detected, undetected or none, with its boundary Paulis and regions" },
  { id: "semantic", group: "Compare", title: "Semantic equivalence", live: true,
    summary: "Check whether two diagrams have the same stabilisers on their boundary.",
    provide: "Two diagrams from your shelf",
    get: "Yes or no, with both diagrams' stabilisers on their boundaries" },
  { id: "fault", group: "Compare", title: "Fault equivalence",
    summary: "Check whether two noisy diagrams behave the same up to a fault weight.",
    provide: "Two diagrams or noise models and a maximum weight", get: "Equivalent up to that weight, or not" },
  { id: "dem", group: "stim", title: "stim → detector error model",
    summary: "Turn a stim circuit into paritea's detector error model.",
    provide: "A stim circuit, from a preset or your own", get: "A .dem file with its detectors, observables and errors" },
  { id: "console", group: "Advanced", title: "Python console",
    summary: "Use the whole paritea API from Python, right in the page.",
    provide: "Python code", get: "Its output, with paritea already imported" },
];

export function renderHome(ctx) {
  const cards = TOOLS.map((t) => `
    <article class="tool-card ${t.live ? "live" : "planned"}">
      <div class="card-top"><span class="group">${t.group}</span>
        <span class="badge ${t.live ? "badge-live" : "badge-planned"}">${t.live ? "Live" : "Planned"}</span></div>
      <h3>${t.title}</h3>
      <p>${t.summary}</p>
      <dl class="io"><dt>You provide</dt><dd>${t.provide}</dd><dt>You get</dt><dd>${t.get}</dd></dl>
      ${t.live ? `<a class="card-link" href="#/${t.id}">Open ${t.title} →</a>` : ""}
    </article>`).join("");
  const kept = shelf.size
    ? `<p class="hint">Your shelf has ${plural(shelf.size, "diagram")}: <a href="#/diagrams">see them in Diagrams</a>.</p>`
    : "";

  ctx.app.innerHTML = `
    <section class="hero">
      <p class="eyebrow">Fault tolerance with ZX diagrams</p>
      <h1>paritea, in your browser</h1>
      <p class="lead">paritea finds Pauli webs, builds noise models and checks fault equivalence of Clifford ZX diagrams.
        This page runs it for you: Python and paritea's Rust core are compiled to WebAssembly, so there is nothing to
        install and your inputs and results never leave your computer.</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="#/diagrams">Build or import a diagram →</a>
        <a class="btn btn-ghost" href="#/webs">Compute Pauli webs</a>
        <span class="hint" data-engine-message>${escapeHtml(ctx.engineMessage())}</span>
      </div>
      ${kept}
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
