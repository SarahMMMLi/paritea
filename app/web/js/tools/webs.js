// Pauli webs: stabilising webs and detecting regions of any diagram, stepped through on the drawing.

import { shelf } from "../shelf.js";
import {
  codeCardHtml,
  errorHtml,
  escapeHtml,
  formatSeconds,
  mountViewer,
  noticeHtml,
  paramsHtml,
  plural,
  readParams,
  statsHtml,
  viewerHtml,
  wireCopyButtons,
  withBusyButton,
} from "../ui.js";

// The first diagram offered: two rounds, so that it has detecting regions as well as stabilising webs.
const FIRST_EXAMPLE = { generator: "Rotated surface code memory experiment", params: { distance: 3, rounds: 2 } };
const remembered = { source: null, diagram: null, generator: null, params: null };

export async function renderWebs(ctx, query) {
  ctx.app.innerHTML = `
    <nav class="crumbs"><a href="#/">Tools</a> / Pauli webs</nav>
    <header class="tool-head">
      <h1>Pauli webs</h1>
      <p class="lead">Find the stabilising webs and detecting regions of a ZX diagram, and see each one drawn on the diagram.</p>
    </header>
    <div class="io-cards">
      <section class="io-card"><h2>You provide</h2>
        <ol><li><strong>A ZX diagram</strong>: one from your shelf (made in <a href="#/diagrams">Diagrams</a>, including
          your own files), or a new one from a generator.</li></ol></section>
      <section class="io-card"><h2>You get</h2>
        <ul><li>How many <strong>stabilising webs</strong> and <strong>detecting regions</strong> the diagram has</li>
          <li>Each web drawn on the diagram, with the Pauli (X, Y or Z) it puts on every edge</li>
          <li>An edge-by-edge table, and Python code that reproduces the result</li></ul></section>
    </div>
    <form class="panel" id="webs-form" novalidate>
      <div class="step"><span class="step-n">1</span><div class="step-body">
        <span class="field-label" id="diagram-label">Diagram</span>
        <div class="segmented" role="tablist" aria-labelledby="diagram-label">
          <button type="button" role="tab" data-source="shelf">From your shelf<span class="count" id="shelf-count"></span></button>
          <button type="button" role="tab" data-source="generate">Generate a new one</button>
        </div>
        <div id="source-body" class="source-body"></div>
      </div></div>
      <div class="actions">
        <button class="btn btn-primary" id="run" type="submit">Compute webs</button>
        <span class="hint">Usually well under a second · <kbd>Ctrl</kbd> + <kbd>Enter</kbd></span>
      </div>
    </form>
    <section class="results" id="results" aria-live="polite">
      <div class="empty">Results appear here: the number of webs, each web on the diagram, an edge table and Python code.</div>
    </section>`;

  const { generators } = await ctx.engine.catalogue;
  const live = ctx.engine.mode !== "precomputed";
  let source = query.diagram ? "shelf" : (remembered.source ?? (shelf.size && live ? "shelf" : "generate"));
  if (query.diagram) remembered.diagram = query.diagram;

  const showSource = (next) => {
    source = next;
    remembered.source = next;
    ctx.app.querySelectorAll("[data-source]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.source === next)));
    document.getElementById("shelf-count").textContent = String(shelf.size);
    const body = document.getElementById("source-body");
    if (next === "shelf") {
      body.innerHTML = shelf.size && live
        ? `<select id="shelf-pick" aria-label="Diagram from your shelf">${shelf
            .list()
            .map((e) => `<option value="${e.id}">${e.id} · ${escapeHtml(e.name)} (${plural(e.summary.Nodes, "node")})</option>`)
            .join("")}</select>
           <p class="help">Make more in <a href="#/diagrams">Diagrams</a>: generators, examples or your own files.</p>`
        : `<p class="help">${live ? "Your shelf is empty." : "The shelf needs the in-browser engine."}
             <a href="#/diagrams">Build, open or import a diagram</a>, or generate one here.</p>`;
      const pick = document.getElementById("shelf-pick");
      if (pick && remembered.diagram && shelf.entries.has(remembered.diagram)) pick.value = remembered.diagram;
      pick?.addEventListener("change", () => (remembered.diagram = pick.value));
    } else {
      body.innerHTML = `
        <select id="generator" aria-label="Generator"></select>
        <p class="help" id="generator-help"></p>
        <div class="params" id="params"></div>`;
      const select = document.getElementById("generator");
      select.innerHTML = generators.map((g) => `<option>${escapeHtml(g.name)}</option>`).join("");
      const showParams = (values = {}) => {
        const g = generators.find((x) => x.name === select.value);
        document.getElementById("generator-help").textContent = g.description;
        document.getElementById("params").innerHTML = paramsHtml(g, values);
      };
      const initial = remembered.generator ? remembered : FIRST_EXAMPLE;
      select.value = initial.generator;
      showParams(initial.params);
      select.addEventListener("change", () => showParams());
    }
  };
  ctx.app.querySelectorAll("[data-source]").forEach((b) => b.addEventListener("click", () => showSource(b.dataset.source)));
  showSource(source);

  const form = document.getElementById("webs-form");
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    compute(ctx, source, generators);
  });
  form.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) form.requestSubmit();
  });
  if (query.run === "1" && source === "shelf" && document.getElementById("shelf-pick")) form.requestSubmit();
}

async function compute(ctx, source, generators) {
  const results = document.getElementById("results");
  let op;
  let args;
  if (source === "shelf") {
    const pick = document.getElementById("shelf-pick");
    if (!pick) {
      results.innerHTML = errorHtml("No diagram chosen.", new Error("Pick a diagram from your shelf or generate one."));
      return;
    }
    remembered.diagram = pick.value;
    [op, args] = ["webs", { diagram: pick.value }];
  } else {
    const generator = generators.find((x) => x.name === document.getElementById("generator").value);
    try {
      args = { generator: generator.name, params: readParams(generator) };
    } catch (err) {
      results.innerHTML = errorHtml("Check the inputs.", err);
      return;
    }
    Object.assign(remembered, args);
    op = "pauli_webs";
  }
  const button = document.getElementById("run");
  await withBusyButton(button, ctx.engine.mode === "starting" ? "Waiting for the engine…" : "Computing…", async () => {
    ctx.setBusy(true);
    try {
      const result = await ctx.engine.run(op, args);
      if (!result.precomputed) shelf.add(result);
      showResult(ctx, result);
    } catch (err) {
      showError(ctx, err, args);
    } finally {
      ctx.setBusy(false);
    }
  });
}

async function showError(ctx, err, args) {
  const results = document.getElementById("results");
  if (err.type === "PreviewOnly") {
    const { results: available } = await ctx.engine.catalogue;
    const options = Object.keys(available)
      .filter((k) => k.startsWith(`${args.generator}|`))
      .map((k) => k.split("|")[1].replaceAll(",", ", "));
    results.innerHTML = noticeHtml(
      `Not available in preview mode. ${err.message} For this diagram, try: ${options.join(" · ") || "another diagram"}.`,
    );
    return;
  }
  results.innerHTML = errorHtml(err.type === "UserError" ? "Please check this:" : "Computing the Pauli webs failed.", err);
}

function showResult(ctx, result) {
  window.lastResult = result; // for the browser check in app/build/check_site.py
  const results = document.getElementById("results");
  const nStab = result.stabilisers.length;
  const nReg = result.regions.length;
  const headline = `${plural(nStab, "stabilising web")} and ${nReg ? plural(nReg, "detecting region") : "no detecting regions"}`;
  const total = result.seconds.webs + (result.seconds.build ?? 0);
  const where = result.precomputed
    ? `<span class="where preview">precomputed natively (preview mode)</span>`
    : `computed in ${formatSeconds(total)} <span class="where">in your browser</span>`;

  results.innerHTML = `
    ${result.precomputed ? noticeHtml(ctx.engineMessage()) : ""}
    <div class="result-head">
      <h2 class="headline">${headline}</h2>
      <p class="meta">${escapeHtml(result.name)} · ${where}</p>
    </div>
    ${statsHtml(result.summary)}
    ${viewerHtml({
      webs: true,
      bar: `
        <div class="segmented" role="tablist" aria-label="Which webs to show">
          <button type="button" role="tab" data-kind="stabilisers">Stabilising webs<span class="count">${nStab}</span></button>
          <button type="button" role="tab" data-kind="regions">Detecting regions<span class="count">${nReg}</span></button>
          <button type="button" role="tab" data-kind="none">Diagram only</button>
        </div>
        <div class="stepper">
          <button type="button" class="icon-btn" id="prev" aria-label="Previous web">‹</button>
          <span id="which"></span>
          <button type="button" class="icon-btn" id="next" aria-label="Next web">›</button>
        </div>`,
    })}
    <div class="below">
      <section class="card">
        <div class="card-head"><h3 id="table-title">Edges in this web</h3></div>
        <div class="table-wrap" id="edge-table"></div>
      </section>
      ${codeCardHtml(result.code)}
    </div>`;

  const view = mountViewer(results, result.diagram);
  wireCopyButtons(results, result.code);
  const endpoints = new Map(result.diagram.edges.map(([e, s, t]) => [e, `${s} – ${t}`]));
  const state = { kind: nStab ? "stabilisers" : nReg ? "regions" : "none", index: 0 };

  const draw = () => {
    const webs = state.kind === "none" ? [] : result[state.kind];
    const web = webs[state.index];
    results.querySelectorAll("[data-kind]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.kind === state.kind)));
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
  results.querySelectorAll("[data-kind]").forEach((b) =>
    b.addEventListener("click", () => {
      state.kind = b.dataset.kind;
      state.index = 0;
      draw();
    }),
  );
  document.getElementById("prev").addEventListener("click", () => step(-1));
  document.getElementById("next").addEventListener("click", () => step(1));
  ctx.setStepKeys(step);
  draw();
}
