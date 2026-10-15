// Noise models: independent X, Y and Z flips on the edges of a diagram, except the edges chosen as noise-free.

import { shelf } from "../shelf.js";
import {
  codeCardHtml,
  download,
  errorHtml,
  escapeHtml,
  mountViewer,
  noticeHtml,
  plural,
  scrollToResult,
  statsHtml,
  viewerHtml,
  wireCopyButtons,
  withBusyButton,
} from "../ui.js";

const PRESETS = [
  ["none", "None"],
  ["X", "Wires of X spiders"],
  ["Z", "Wires of Z spiders"],
  ["B", "Boundary wires"],
];
const MAX_ROWS = 400;
// Remembered while the page is open: the chosen diagram, the weights and the picked edges of each diagram.
const remembered = { diagram: null, weights: { x: 1, y: 1, z: 1 }, picks: new Map(), shown: null };

export async function renderNoise(ctx, query) {
  const live = ctx.engine.mode !== "precomputed";
  ctx.app.innerHTML = `
    <nav class="crumbs"><a href="#/">Tools</a> / Noise model</nav>
    <header class="tool-head">
      <h1>Noise model</h1>
      <p class="lead">Put independent X, Y and Z faults on the edges of a diagram, each with a weight, and choose
        which edges are noise-free.</p>
    </header>
    <div class="io-cards">
      <section class="io-card"><h2>You provide</h2>
        <ol><li><strong>A diagram</strong> from your shelf</li>
          <li><strong>A weight</strong> for X, Y and Z faults: what one fault of that kind costs</li>
          <li><strong>Noise-free edges</strong> (paritea: <code>idealised_edges</code>): a preset, or picks on the drawing</li></ol></section>
      <section class="io-card"><h2>You get</h2>
        <ul><li>A noise model on your shelf: an X, a Y and a Z fault on every other edge</li>
          <li>Every fault with its weight, as a table and a JSON file</li>
          <li>Python code that builds the same noise model</li></ul></section>
    </div>
    ${live ? "" : noticeHtml("Noise models need the in-browser engine, which isn't running here (preview mode).")}
    <form class="panel" id="noise-form" novalidate>
      <div class="step"><span class="step-n">1</span><div class="step-body">
        <label class="field-label" for="noise-diagram">Diagram</label>
        <div id="diagram-pick"></div>
      </div></div>
      <div class="step"><span class="step-n">2</span><div class="step-body">
        <span class="field-label">Fault weights</span>
        <div class="weights">${["x", "y", "z"]
          .map(
            (k) => `<div class="param"><label for="w-${k}">${k.toUpperCase()} flip</label>
              <input id="w-${k}" type="number" min="1" max="100" step="1" value="${remembered.weights[k]}"></div>`,
          )
          .join("")}</div>
        <p class="help">Whole numbers from 1 to 100. Keep them equal if you will check fault equivalence: paritea
          assumes equal weights there.</p>
      </div></div>
      <div class="step"><span class="step-n">3</span><div class="step-body">
        <span class="field-label">Noise-free edges</span>
        <div class="preset-row">
          <div class="segmented" role="group" aria-label="Noise-free preset">${PRESETS.map(
            ([key, label]) => `<button type="button" data-preset="${key}">${label}</button>`,
          ).join("")}</div>
          <span class="picked-count" id="picked-count"></span>
        </div>
        <p class="help">Or click edges on the drawing to switch them between noisy (solid) and noise-free (dashed).</p>
        <div id="pick-canvas" class="canvas-small"></div>
      </div></div>
      <div class="actions">
        <button class="btn btn-primary" id="run" type="submit">Build noise model</button>
        <span class="hint">Instant</span>
      </div>
    </form>
    <section class="results" id="results" aria-live="polite"></section>
    <section class="shelf-section" id="noise-shelf" aria-label="Your noise models"></section>`;

  if (query.diagram) remembered.diagram = query.diagram;
  const state = { drawing: null, view: null };
  renderDiagramPick(ctx, state, live);
  renderNoiseShelf(ctx);
  const onChange = () => document.getElementById("noise-shelf") && renderNoiseShelf(ctx);
  shelf.addEventListener("change", onChange);
  ctx.onLeave(() => shelf.removeEventListener("change", onChange));

  ctx.app.querySelectorAll("[data-preset]").forEach((b) =>
    b.addEventListener("click", () => state.drawing && applyPreset(state, b.dataset.preset)),
  );
  document.getElementById("noise-form").addEventListener("submit", (e) => {
    e.preventDefault();
    build(ctx, state);
  });
  if (remembered.shown && shelf.noise.has(remembered.shown)) showNoise(ctx, remembered.shown);
}

function renderDiagramPick(ctx, state, live) {
  const box = document.getElementById("diagram-pick");
  const diagrams = shelf.list();
  const example = `<button type="button" class="btn btn-ghost btn-small" id="use-steane">
    Use the Steane |0⟩ example (from paritea's demo)</button>`;
  if (!live) {
    box.innerHTML = `<p class="help">The shelf needs the in-browser engine.</p>`;
    return;
  }
  box.innerHTML = diagrams.length
    ? `<select id="noise-diagram">${diagrams
        .map((e) => `<option value="${e.id}">${e.id} · ${escapeHtml(e.name)} (${plural(e.summary.Edges, "edge")})</option>`)
        .join("")}</select>
       <p class="help">Make more in <a href="#/diagrams">Diagrams</a>, or ${example}</p>`
    : `<p class="help">Your shelf is empty. <a href="#/diagrams">Build, open or import a diagram</a>, or ${example}</p>`;
  const select = document.getElementById("noise-diagram");
  if (select) {
    if (remembered.diagram && shelf.entries.has(remembered.diagram)) select.value = remembered.diagram;
    select.addEventListener("change", () => loadDiagram(ctx, state, select.value));
    loadDiagram(ctx, state, select.value);
  }
  document.getElementById("use-steane").addEventListener("click", async (e) => {
    await withBusyButton(e.currentTarget, "Opening…", async () => {
      try {
        const entry = await ctx.engine.run("diagram_example", { example: "steane-state" });
        shelf.add(entry);
        remembered.diagram = entry.id;
        if (!remembered.picks.has(entry.id)) remembered.picks.set(entry.id, edgesTouching(entry.diagram, "X"));
        renderDiagramPick(ctx, state, live);
      } catch (err) {
        document.getElementById("results").innerHTML = errorHtml("Couldn't open the example.", err);
      }
    });
  });
}

async function loadDiagram(ctx, state, id) {
  remembered.diagram = id;
  const request = (state.request = (state.request ?? 0) + 1);
  const canvas = document.getElementById("pick-canvas");
  canvas.innerHTML = `<p class="help">Loading the drawing…</p>`;
  try {
    const entry = await ctx.engine.run("diagram_get", { diagram: id });
    if (request !== state.request || !canvas.isConnected) return; // a newer request (or page) took over
    state.drawing = entry.diagram;
    canvas.innerHTML = viewerHtml().replace(
      '<div class="legend">',
      `<div class="legend"><span class="legend-item"><span class="swatch noisy"></span>Noisy edge</span>
       <span class="legend-item"><span class="swatch noise-free"></span>Noise-free edge</span>`,
    );
    state.view = mountViewer(canvas, entry.diagram);
    if (!remembered.picks.has(id)) remembered.picks.set(id, new Set());
    state.view.onEdgeClick((edge) => {
      const picks = remembered.picks.get(id);
      if (picks.has(edge)) picks.delete(edge);
      else picks.add(edge);
      showPicks(state);
    }, "click to switch noisy / noise-free");
    showPicks(state);
  } catch (err) {
    canvas.innerHTML = errorHtml("Couldn't load the drawing.", err);
  }
}

function edgesTouching(drawing, type) {
  const types = new Map(drawing.nodes.map((n) => [n.id, n.type]));
  return new Set(drawing.edges.filter(([, s, t]) => types.get(s) === type || types.get(t) === type).map(([e]) => e));
}

function applyPreset(state, preset) {
  const picks = preset === "none" ? new Set() : edgesTouching(state.drawing, preset);
  remembered.picks.set(remembered.diagram, picks);
  showPicks(state, preset);
}

function showPicks(state, preset = null) {
  const picks = remembered.picks.get(remembered.diagram) ?? new Set();
  document.querySelectorAll("[data-preset]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.preset === preset)));
  state.view.setNoiseFree(picks);
  const total = state.drawing.edges.length;
  document.getElementById("picked-count").textContent =
    `${plural(picks.size, "noise-free edge")} · ${plural(total - picks.size, "noisy edge")}`;
}

async function build(ctx, state) {
  const results = document.getElementById("results");
  if (!state.drawing) {
    results.innerHTML = errorHtml("No diagram chosen.", new Error("Pick a diagram from your shelf first."));
    return;
  }
  const weights = {};
  for (const k of ["x", "y", "z"]) {
    const value = Number(document.getElementById(`w-${k}`).value);
    if (!Number.isInteger(value) || value < 1 || value > 100) {
      results.innerHTML = errorHtml("Check the inputs.", new Error(`The ${k.toUpperCase()} weight must be a whole number from 1 to 100.`));
      return;
    }
    weights[k] = value;
  }
  remembered.weights = weights;
  const noiseFree = [...(remembered.picks.get(remembered.diagram) ?? [])];
  await withBusyButton(document.getElementById("run"), "Building…", async () => {
    try {
      const noise = await ctx.engine.run("noise_model", { diagram: remembered.diagram, weights, noise_free: noiseFree });
      shelf.addNoise(noise);
      showResult(noise);
    } catch (err) {
      results.innerHTML = errorHtml(err.type === "UserError" ? "Please check this:" : "Building the noise model failed.", err);
    }
  });
}

async function showNoise(ctx, id) {
  try {
    showResult(await ctx.engine.run("noise_get", { noise: id }));
  } catch (err) {
    document.getElementById("results").innerHTML = errorHtml("Couldn't show this noise model.", err);
  }
}

function showResult(noise) {
  window.lastNoise = noise; // for the browser check in app/build/check_site.py
  remembered.shown = noise.id;
  const results = document.getElementById("results");
  const s = noise.summary;
  const endpoints = new Map(noise.drawing.edges.map(([e, a, b]) => [e, `${a} – ${b}`]));
  const rows = noise.faults.slice(0, MAX_ROWS);
  results.innerHTML = `
    <div class="result-head">
      <h2 class="headline">Saved as ${noise.id} · ${plural(s.Faults, "fault")} on ${plural(s["Noisy edges"], "noisy edge")}</h2>
      <p class="meta">${escapeHtml(noise.name)} · diagram ${noise.diagram.id} · ${escapeHtml(noise.diagram.name)}</p>
    </div>
    ${noise.notes.map(noticeHtml).join("")}
    ${statsHtml(s)}
    <div class="below">
      <section class="card">
        <div class="card-head"><h3>Faults (${s.Faults})</h3>
          <button type="button" class="btn btn-ghost btn-small" id="noise-json">Download JSON</button></div>
        <div class="table-wrap">${rows.length ? `<table><thead><tr><th>#</th><th>Edge</th><th>Between nodes</th><th>Pauli</th><th>Weight</th></tr></thead>
          <tbody>${rows
            .map(([edges, weight], i) => edges
              .map(([e, p]) => `<tr><td>${i + 1}</td><td>${e}</td><td>${endpoints.get(e)}</td><td><span class="pauli-chip ${p}">${p}</span></td><td>${weight}</td></tr>`)
              .join(""))
            .join("")}</tbody></table>` : `<p class="muted-cell">No faults: every edge is noise-free.</p>`}
          ${noise.faults.length > MAX_ROWS ? `<p class="truncated">Showing the first ${MAX_ROWS} of ${noise.faults.length} faults; the JSON file has them all.</p>` : ""}
        </div>
      </section>
      ${codeCardHtml(noise.code, "Python code that builds this noise model")}
    </div>`;
  wireCopyButtons(results, noise.code);
  document.getElementById("noise-json").addEventListener("click", () => {
    const file = {
      noise_model: noise.id,
      diagram: noise.diagram,
      weights: noise.settings.weights,
      noise_free_edges: noise.settings.noise_free,
      faults: noise.faults.map(([edges, weight]) => ({ edge_flips: Object.fromEntries(edges), weight })),
    };
    download(`${noise.id.toLowerCase()}-noise-model.json`, JSON.stringify(file, null, 2), "application/json");
  });
  scrollToResult(results.querySelector(".headline"));
}

function renderNoiseShelf(ctx) {
  const box = document.getElementById("noise-shelf");
  const items = [...shelf.noise.values()];
  box.innerHTML = `
    <div class="section-head"><h2>Your noise models</h2><p>Kept while this tab is open, each with its diagram.</p></div>
    ${items.length ? `<ul class="shelf-list">${items
      .map(
        (n) => `
        <li>
          <div class="shelf-name"><span class="shelf-id">${n.id}</span> ${escapeHtml(n.name)}
            <span class="muted">${plural(n.summary.Faults, "fault")}</span></div>
          <div class="row-actions">
            <button type="button" class="btn btn-ghost btn-small" data-show-noise="${n.id}">Show</button>
            <button type="button" class="btn btn-ghost btn-small" data-remove-noise="${n.id}" aria-label="Remove ${n.id}">Remove</button>
          </div>
        </li>`,
      )
      .join("")}</ul>` : `<p class="empty">Nothing yet. Noise models you build appear here.</p>`}`;
  box.querySelectorAll("[data-show-noise]").forEach((b) => b.addEventListener("click", () => showNoise(ctx, b.dataset.showNoise)));
  box.querySelectorAll("[data-remove-noise]").forEach((b) =>
    b.addEventListener("click", async () => {
      const id = b.dataset.removeNoise;
      try {
        await ctx.engine.run("noise_remove", { noise: id });
      } finally {
        shelf.removeNoise(id);
        if (remembered.shown === id) {
          remembered.shown = null;
          document.getElementById("results").innerHTML = "";
        }
      }
    }),
  );
}
