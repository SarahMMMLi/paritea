// Diagrams: generate, open an example or import a diagram; show it; keep it on the shelf for the other tools.

import { shelf } from "../shelf.js";
import {
  codeCardHtml,
  copyLinkHtml,
  download,
  errorHtml,
  escapeHtml,
  generatorFromLink,
  mountViewer,
  noticeHtml,
  paramsHtml,
  plural,
  readParams,
  recipeOf,
  scrollToResult,
  setLink,
  statsHtml,
  viewerHtml,
  wireCopyButtons,
  wireCopyLink,
  withBusyButton,
} from "../ui.js";

const SAMPLE_QASM = `OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
cx q[0],q[1];
s q[1];
`;

// Remembered while the page is open, so coming back shows the same tab and inputs.
const remembered = { tab: "generate", generator: null, params: {}, shown: null };

export async function renderDiagrams(ctx, query) {
  const preview = ctx.engine.mode === "precomputed";
  ctx.app.innerHTML = `
    <nav class="crumbs"><a href="#/">Tools</a> / Diagrams</nav>
    <header class="tool-head">
      <h1>Diagrams</h1>
      <p class="lead">Generate a ZX diagram, open a ready-made one or import your own. Every diagram you make is kept
        on your shelf, ready for the other tools.</p>
    </header>
    <div class="io-cards">
      <section class="io-card"><h2>You provide</h2>
        <ol><li><strong>One of:</strong> a generator and a few numbers, a ready-made example, or a file
          (PyZX / ZXLive JSON, OpenQASM 2).</li></ol></section>
      <section class="io-card"><h2>You get</h2>
        <ul><li>An interactive drawing and a summary: nodes, edges, inputs, outputs</li>
          <li>The diagram on your shelf, ready for Pauli webs and the other tools</li>
          <li>PyZX JSON (opens in ZXLive), TikZ and SVG files, and Python code</li></ul></section>
    </div>
    ${preview ? noticeHtml("Building diagrams needs the in-browser engine, which isn't running here (preview mode).") : ""}
    <div class="panel">
      <div class="tabs" role="tablist" aria-label="Where the diagram comes from">
        <button type="button" role="tab" data-tab="generate">Generate</button>
        <button type="button" role="tab" data-tab="examples">Examples</button>
        <button type="button" role="tab" data-tab="import">Import a file</button>
      </div>
      <div id="tab-body"></div>
    </div>
    <section class="results" id="results" aria-live="polite"></section>
    <section class="shelf-section" id="shelf" aria-label="Your diagrams"></section>`;

  const catalogue = await ctx.engine.catalogue;
  // A link names a generator and its parameters, an example, or (within this tab) a diagram on the shelf.
  const fromLink = query.generator ? generatorFromLink(catalogue.generators, query) : null;
  if (fromLink) Object.assign(remembered, fromLink);

  const tabs = { generate: () => generateTab(ctx, catalogue), examples: () => examplesTab(ctx, catalogue), import: () => importTab(ctx) };
  const show = (tab) => {
    remembered.tab = tab;
    ctx.app.querySelectorAll("[data-tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
    tabs[tab]();
  };
  ctx.app.querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", () => show(b.dataset.tab)));
  show(fromLink ? "generate" : query.example ? "examples" : tabs[query.tab] ? query.tab : remembered.tab);

  renderShelf(ctx);
  const onChange = () => document.getElementById("shelf") && renderShelf(ctx);
  shelf.addEventListener("change", onChange);
  ctx.onLeave(() => shelf.removeEventListener("change", onChange));

  if (query.generator && !fromLink) {
    showError("This link doesn't work.", new Error(`There is no generator called "${query.generator}".`));
  } else if (fromLink) {
    document.getElementById("gen-form").requestSubmit();
  } else if (query.example) {
    const button = [...document.querySelectorAll("[data-example]")].find((b) => b.dataset.example === query.example);
    if (button) button.click();
    else showError("This link doesn't work.", new Error(`There is no example called "${query.example}".`));
  } else if (query.diagram && !preview && !shelf.entries.has(query.diagram)) {
    document.getElementById("results").innerHTML = noticeHtml(
      `There's no ${query.diagram} on your shelf: the shelf belongs to the browser tab that made it. To share a ` +
        "diagram, use Copy link next to it.",
    );
  } else {
    const toShow = query.diagram ?? remembered.shown;
    if (toShow && shelf.entries.has(toShow)) showDiagram(ctx, toShow);
  }
}

// ---------------------------------------------------------------- Tabs

function generateTab(ctx, { generators }) {
  const body = document.getElementById("tab-body");
  body.innerHTML = `
    <form id="gen-form" class="tab-form" novalidate>
      <label class="field-label" for="generator">Generator</label>
      <select id="generator"></select>
      <p class="help" id="generator-help"></p>
      <div class="params" id="params"></div>
      <div class="actions">
        <button class="btn btn-primary" type="submit" id="build">Build diagram</button>
        <span class="hint">Usually well under a second</span>
      </div>
    </form>`;
  const select = document.getElementById("generator");
  select.innerHTML = generators.map((g) => `<option>${escapeHtml(g.name)}</option>`).join("");
  const showParams = (values = {}) => {
    const g = generators.find((x) => x.name === select.value);
    document.getElementById("generator-help").textContent = g.description;
    document.getElementById("params").innerHTML = paramsHtml(g, values);
  };
  select.value = remembered.generator ?? generators[0].name;
  showParams(remembered.params);
  select.addEventListener("change", () => showParams());

  document.getElementById("gen-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const generator = generators.find((x) => x.name === select.value);
    let params;
    try {
      params = readParams(generator);
    } catch (err) {
      return showError("Check the inputs.", err);
    }
    remembered.generator = generator.name;
    remembered.params = params;
    await run(ctx, document.getElementById("build"), "Building…", "diagram_generate", { generator: generator.name, params });
  });
}

function examplesTab(ctx, { examples }) {
  const body = document.getElementById("tab-body");
  const answer = (e) =>
    `paritea finds ${plural(e.stabilising_webs, "stabilising web")} and ` +
    `${e.detecting_regions ? plural(e.detecting_regions, "detecting region") : "no detecting regions"}.`;
  body.innerHTML = `<div class="example-grid">${examples
    .map(
      (e) => `
      <article class="example-card">
        <h3>${escapeHtml(e.title)}</h3>
        <p>${escapeHtml(e.description)}</p>
        <p class="known">${answer(e)}</p>
        <button type="button" class="btn btn-ghost btn-small" data-example="${e.id}">Open</button>
      </article>`,
    )
    .join("")}</div>`;
  body.querySelectorAll("[data-example]").forEach((button) =>
    button.addEventListener("click", () => run(ctx, button, "Opening…", "diagram_example", { example: button.dataset.example })),
  );
}

function importTab(ctx) {
  const body = document.getElementById("tab-body");
  body.innerHTML = `
    <form id="import-form" class="tab-form" novalidate>
      <label class="field-label" for="import-text">File or text</label>
      <div class="file-row">
        <input type="file" id="import-file" accept=".json,.zxg,.qgraph,.qasm">
        <button type="button" class="btn btn-ghost btn-small" id="sample">Use a sample circuit</button>
      </div>
      <textarea id="import-text" rows="7" spellcheck="false"
        placeholder="…or paste PyZX / ZXLive JSON or an OpenQASM 2 circuit here"></textarea>
      <p class="help">PyZX and ZXLive save diagrams as JSON (.json, .zxg). Circuits in OpenQASM 2 must use Clifford gates
        only (phases that are multiples of π/2).</p>
      <div class="option-grid">
        <label class="param">Format
          <select id="import-format">
            <option value="auto">Detect automatically</option>
            <option value="pyzx">PyZX / ZXLive JSON</option>
            <option value="qasm">OpenQASM 2</option>
          </select></label>
        <label class="param">Inputs and outputs
          <select id="import-io">
            <option value="file">From the file</option>
            <option value="detect">Detect from positions</option>
            <option value="outputs">Every boundary is an output</option>
          </select></label>
      </div>
      <label class="check"><input type="checkbox" id="import-had" checked>
        Convert Hadamard edges to H boxes <span class="muted">(paritea has no Hadamard edges)</span></label>
      <label class="check"><input type="checkbox" id="import-pos" checked>
        Keep the file's positions <span class="muted">(off: lay the diagram out automatically)</span></label>
      <div class="actions">
        <button class="btn btn-primary" type="submit" id="import-run">Import diagram</button>
      </div>
    </form>`;
  const text = document.getElementById("import-text");
  let filename = "";
  document.getElementById("import-file").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 5_000_000) return showError("Check the file.", new Error("The file is larger than 5 MB."));
    filename = file.name;
    text.value = await file.text();
  });
  document.getElementById("sample").addEventListener("click", () => {
    filename = "bell-and-s.qasm";
    text.value = SAMPLE_QASM;
  });
  text.addEventListener("input", () => (filename = filename || ""));
  document.getElementById("import-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!text.value.trim()) return showError("Check the input.", new Error("Choose a file or paste its contents first."));
    await run(ctx, document.getElementById("import-run"), "Importing…", "diagram_import", {
      text: text.value,
      filename,
      fmt: document.getElementById("import-format").value,
      convert_hadamard: document.getElementById("import-had").checked,
      keep_positions: document.getElementById("import-pos").checked,
      io: document.getElementById("import-io").value,
    });
  });
}

// ---------------------------------------------------------------- Results

async function run(ctx, button, busyLabel, op, args) {
  const results = document.getElementById("results");
  await withBusyButton(button, busyLabel, async () => {
    try {
      const entry = await ctx.engine.run(op, args);
      shelf.add(entry);
      if (results.isConnected) showEntry(ctx, entry); // unless the visitor went to another page meanwhile
    } catch (err) {
      if (results.isConnected) showError(err.type === "UserError" ? "Please check this:" : "That didn't work.", err);
    }
  });
}

async function showDiagram(ctx, id) {
  const results = document.getElementById("results");
  try {
    const entry = await ctx.engine.run("diagram_get", { diagram: id });
    if (results.isConnected) showEntry(ctx, entry);
  } catch (err) {
    if (results.isConnected) showError("Couldn't show this diagram.", err);
  }
}

function showError(action, err) {
  document.getElementById("results").innerHTML = errorHtml(action, err);
}

function ranges(ids) {
  if (!ids.length) return "none";
  const sorted = [...ids].sort((a, b) => a - b);
  const contiguous = sorted.every((v, i) => i === 0 || v === sorted[i - 1] + 1);
  return contiguous && sorted.length > 2 ? `nodes ${sorted[0]}–${sorted.at(-1)}` : `node${ids.length > 1 ? "s" : ""} ${ids.join(", ")}`;
}

function showEntry(ctx, entry) {
  window.lastEntry = entry; // for the browser check in app/build/check_site.py
  remembered.shown = entry.id;
  const recipe = recipeOf(entry.source);
  setLink("diagrams", recipe);
  const results = document.getElementById("results");
  const s = entry.summary;
  const closed = s.Inputs + s.Outputs === 0 ? " — no boundaries (a closed diagram)" : "";
  const problems = entry.problems.length
    ? `<div class="alert alert-error"><strong>paritea can't analyse this diagram yet.</strong>
        <ul>${entry.problems.slice(0, 5).map((p) => `<li>${escapeHtml(p)}</li>`).join("")}</ul></div>`
    : "";
  results.innerHTML = `
    <div class="result-head">
      <h2 class="headline">Saved as ${entry.id} · ${escapeHtml(entry.name)}</h2>
      <p class="meta">${plural(s.Nodes, "node")}, ${plural(s.Edges, "edge")}, ${plural(s.Inputs, "input")},
        ${plural(s.Outputs, "output")}${closed}${recipe ? ` · ${copyLinkHtml()}` : ""}</p>
    </div>
    ${problems}
    ${entry.notes.map(noticeHtml).join("")}
    ${statsHtml(s)}
    ${viewerHtml()}
    <p class="io-line"><strong>Inputs:</strong> ${ranges(entry.diagram.inputs)} · <strong>Outputs:</strong> ${ranges(entry.diagram.outputs)}</p>
    <div class="next-steps">
      ${entry.problems.length ? "" : `<a class="btn btn-primary" href="#/webs?diagram=${entry.id}&run=1">Compute Pauli webs →</a>
        <a class="btn btn-ghost" href="#/noise?diagram=${entry.id}">Add a noise model</a>`}
      <span class="download-label">Download</span>
      <button type="button" class="btn btn-ghost btn-small" data-export="pyzx">PyZX JSON</button>
      <button type="button" class="btn btn-ghost btn-small" data-export="tikz">TikZ</button>
      <button type="button" class="btn btn-ghost btn-small" data-export="svg">SVG</button>
    </div>
    ${codeCardHtml(entry.code, "Python code that builds this diagram")}`;

  const view = mountViewer(results, entry.diagram);
  wireCopyButtons(results, entry.code);
  wireCopyLink(results);
  results.querySelectorAll("[data-export]").forEach((button) =>
    button.addEventListener("click", async () => {
      const fmt = button.dataset.export;
      if (fmt === "svg") return download(`${entry.id.toLowerCase()}.svg`, view.toSVG(), "image/svg+xml");
      try {
        const file = await ctx.engine.run("diagram_export", { diagram: entry.id, fmt });
        download(file.filename, file.text, fmt === "pyzx" ? "application/json" : "text/plain");
      } catch (err) {
        showError("Couldn't export the diagram.", err);
      }
    }),
  );
  scrollToResult(results.querySelector(".headline"));
}

// ---------------------------------------------------------------- Shelf

function renderShelf(ctx) {
  const box = document.getElementById("shelf");
  const items = shelf.list();
  box.innerHTML = `
    <div class="section-head"><h2>Your diagrams</h2><p>Kept while this tab is open; use them in every tool.</p></div>
    ${items.length ? `<ul class="shelf-list">${items
      .map(
        (e) => `
        <li>
          <div class="shelf-name"><span class="shelf-id">${e.id}</span> ${escapeHtml(e.name)}
            <span class="muted">${plural(e.summary.Nodes, "node")} · ${plural(e.summary.Edges, "edge")}</span></div>
          <div class="row-actions">
            <button type="button" class="btn btn-ghost btn-small" data-show="${e.id}">Show</button>
            <a class="btn btn-ghost btn-small" href="#/webs?diagram=${e.id}&run=1">Pauli webs</a>
            <button type="button" class="btn btn-ghost btn-small" data-remove="${e.id}" aria-label="Remove ${e.id}">Remove</button>
          </div>
        </li>`,
      )
      .join("")}</ul>` : `<p class="empty">Nothing yet. Diagrams you build, open or import appear here.</p>`}`;
  box.querySelectorAll("[data-show]").forEach((b) => b.addEventListener("click", () => showDiagram(ctx, b.dataset.show)));
  box.querySelectorAll("[data-remove]").forEach((b) =>
    b.addEventListener("click", async () => {
      const id = b.dataset.remove;
      try {
        const removed = await ctx.engine.run("diagram_remove", { diagram: id });
        removed.noise.forEach((noiseId) => shelf.removeNoise(noiseId));
      } finally {
        shelf.remove(id);
        if (remembered.shown === id) {
          remembered.shown = null;
          if (box.isConnected) document.getElementById("results").innerHTML = "";
        }
      }
    }),
  );
}
