// Fault propagation (paritea's push-out): where every fault of a noise model ends up.

import { shelf } from "../shelf.js";
import {
  codeCardHtml,
  download,
  errorHtml,
  escapeHtml,
  formatSeconds,
  noticeHtml,
  plural,
  scrollToResult,
  statsHtml,
  wireCopyButtons,
  withBusyButton,
  withCancel,
} from "../ui.js";

const KIND_LABELS = { detected: "Detected", boundary: "Undetected", none: "No effect" };
const MAX_ROWS = 300;
const remembered = { noise: null };

export async function renderPropagation(ctx, query) {
  const live = ctx.engine.mode !== "precomputed";
  ctx.app.innerHTML = `
    <nav class="crumbs"><a href="#/">Tools</a> / Fault propagation</nav>
    <header class="tool-head">
      <h1>Fault propagation</h1>
      <p class="lead">Push every fault of a noise model out to the boundary of its diagram, and see which faults are
        detected, which reach the boundary undetected, and which have no effect. paritea calls this push-out.</p>
    </header>
    <div class="io-cards">
      <section class="io-card"><h2>You provide</h2>
        <ol><li><strong>A noise model</strong> from your shelf (made in <a href="#/noise">Noise model</a>);
          its diagram comes with it</li></ol></section>
      <section class="io-card"><h2>You get</h2>
        <ul><li>Every distinct effect: the Paulis it leaves on the inputs and outputs, and the detecting regions it flips</li>
          <li>How many faults have each effect, and the lowest weight among them</li>
          <li>The flip operators paritea used, and Python code that reproduces the result</li></ul></section>
    </div>
    ${live ? "" : noticeHtml("Fault propagation needs the in-browser engine, which isn't running here (preview mode).")}
    <form class="panel" id="prop-form" novalidate>
      <div class="step"><span class="step-n">1</span><div class="step-body">
        <label class="field-label" for="prop-noise">Noise model</label>
        <div id="noise-pick"></div>
      </div></div>
      <div class="actions">
        <button class="btn btn-primary" id="run" type="submit">Propagate faults</button>
        <button class="btn btn-ghost" id="cancel" type="button" hidden>Cancel</button>
        <span class="hint" id="elapsed"></span>
        <span class="hint">Usually a second or less; tens of thousands of faults take up to a minute</span>
      </div>
    </form>
    <section class="results" id="results" aria-live="polite">
      <div class="empty">Results appear here: every distinct effect of the faults, grouped into detected, undetected
        and no effect.</div>
    </section>`;

  if (query.noise) remembered.noise = query.noise;
  renderNoisePick(ctx, live);
  const form = document.getElementById("prop-form");
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    propagate(ctx);
  });
  if (query.run === "1" && document.getElementById("prop-noise")) form.requestSubmit();
}

function renderNoisePick(ctx, live) {
  const box = document.getElementById("noise-pick");
  const models = [...shelf.noise.values()];
  const example = `<button type="button" class="btn btn-ghost btn-small" id="use-demo">
    Use the Steane preparation circuit with unit noise</button>`;
  if (!live) {
    box.innerHTML = `<p class="help">The shelf needs the in-browser engine.</p>`;
    return;
  }
  box.innerHTML = models.length
    ? `<select id="prop-noise">${models
        .map((n) => `<option value="${n.id}">${n.id} · ${escapeHtml(n.name)} (${plural(n.summary.Faults, "fault")})</option>`)
        .join("")}</select>
       <p class="help">Make more in <a href="#/noise">Noise model</a>, or ${example}</p>`
    : `<p class="help">You have no noise models yet. <a href="#/noise">Build one</a>, or ${example}</p>`;
  const select = document.getElementById("prop-noise");
  if (select && remembered.noise && shelf.noise.has(remembered.noise)) select.value = remembered.noise;
  select?.addEventListener("change", () => (remembered.noise = select.value));
  document.getElementById("use-demo").addEventListener("click", async (e) => {
    const results = document.getElementById("results");
    await withBusyButton(e.currentTarget, "Preparing…", async () => {
      try {
        const entry = await ctx.engine.run("diagram_example", { example: "steane-circuit" });
        shelf.add(entry);
        const noise = await ctx.engine.run("noise_model", {
          diagram: entry.id,
          weights: { x: 1, y: 1, z: 1 },
          noise_free: [],
        });
        shelf.addNoise(noise);
        remembered.noise = noise.id;
        if (!results.isConnected) return; // the visitor went to another page meanwhile
        renderNoisePick(ctx, live);
        document.getElementById("prop-form").requestSubmit();
      } catch (err) {
        if (results.isConnected) results.innerHTML = errorHtml("Couldn't prepare the example.", err);
      }
    });
  });
}

async function propagate(ctx) {
  const results = document.getElementById("results");
  const select = document.getElementById("prop-noise");
  if (!select) {
    results.innerHTML = errorHtml("No noise model chosen.", new Error("Build a noise model first, or use the example."));
    return;
  }
  remembered.noise = select.value;
  const controls = { cancel: document.getElementById("cancel"), elapsed: document.getElementById("elapsed") };
  await withBusyButton(document.getElementById("run"), "Propagating…", async () => {
    ctx.setBusy(true);
    try {
      const result = await withCancel(ctx, controls, () => ctx.engine.run("propagation", { noise: select.value }));
      if (results.isConnected) showResult(result); // unless the visitor went to another page meanwhile
    } catch (err) {
      if (err.type === "Cancelled") window.lastPropagation = { cancelled: true };
      if (!results.isConnected) return;
      results.innerHTML = err.type === "Cancelled"
        ? noticeHtml(
            "Cancelled. The engine is restarting (a few seconds), so your shelf is empty again: build the noise " +
              "model again, or use the example.",
          )
        : errorHtml(err.type === "UserError" ? "Please check this:" : "Fault propagation failed.", err);
      if (err.type === "Cancelled") renderNoisePick(ctx, true);
    } finally {
      ctx.setBusy(false);
    }
  });
}

function boundaryText(boundary, labels) {
  if (!boundary.length) return `<span class="muted">nothing</span>`;
  return boundary
    .map(([edge, p]) => `<span class="nowrap">${escapeHtml(labels[edge] ?? `edge ${edge}`)} <span class="pauli-chip ${p}">${p}</span></span>`)
    .join(" ");
}

function showResult(result) {
  window.lastPropagation = result; // for the browser check in app/build/check_site.py
  const results = document.getElementById("results");
  const s = result.summary;
  const headline =
    `${plural(s.Faults, "fault")} have ${plural(s["Distinct effects"], "distinct effect")}: ` +
    `${s.Detected} detected, ${s.Undetected} undetected, ${s["No effect"]} with no effect`;
  const rows = result.effects.slice(0, MAX_ROWS);
  results.innerHTML = `
    <div class="result-head">
      <h2 class="headline">${headline}</h2>
      <p class="meta">${escapeHtml(result.noise.id)} · ${escapeHtml(result.noise.name)} · diagram ${escapeHtml(result.diagram.id)}
        · computed in ${formatSeconds(result.seconds)} <span class="where">in your browser</span></p>
    </div>
    ${statsHtml(s)}
    <section class="card">
      <div class="card-head"><h3>Effects (${result.effects.length})</h3>
        <button type="button" class="btn btn-ghost btn-small" id="prop-json">Download JSON</button></div>
      <p class="card-note"><strong>Detected</strong>: flips at least one detecting region, so a check notices it.
        <strong>Undetected</strong>: changes the outputs (or inputs) but no check notices it.
        <strong>No effect</strong>: equivalent to doing nothing. Regions are numbered as on the Pauli webs page.</p>
      <div class="table-wrap tall" tabindex="0"><table>
        <thead><tr><th>Kind</th><th>Left on the boundary</th><th>Regions flipped</th><th>Faults</th><th>Lowest weight</th></tr></thead>
        <tbody>${rows
          .map(
            (e) => `<tr>
              <td><span class="kind ${e.kind}">${KIND_LABELS[e.kind]}</span></td>
              <td>${boundaryText(e.boundary, result.labels)}</td>
              <td>${e.regions.length ? e.regions.map((r) => `region ${r + 1}`).join(", ") : `<span class="muted">none</span>`}</td>
              <td>${e.faults}</td><td>${e.min_weight}</td></tr>`,
          )
          .join("")}</tbody></table>
        ${result.effects.length > MAX_ROWS ? `<p class="truncated">Showing the first ${MAX_ROWS} of ${result.effects.length} effects; the JSON file has them all.</p>` : ""}
      </div>
    </section>
    <div class="below">
      <section class="card">
        <div class="card-head"><h3>Flip operators (${result.flip_operators.length})</h3></div>
        <p class="card-note">One per stabiliser: a single Pauli on one boundary edge that flips that stabiliser and no
          other. paritea writes each fault's effect on the boundary in terms of these.
          ${plural(result.regions, "detecting region")} in this diagram.</p>
        <div class="table-wrap" tabindex="0"><table><thead><tr><th>Stabiliser</th><th>Flip operator</th></tr></thead>
          <tbody>${result.flip_operators
            .map((op, i) => `<tr><td>${i + 1}</td><td>${boundaryText(op, result.labels)}</td></tr>`)
            .join("") || `<tr><td colspan="2" class="muted-cell">This diagram has no stabilisers.</td></tr>`}</tbody></table></div>
      </section>
      ${codeCardHtml(result.code)}
    </div>`;
  wireCopyButtons(results, result.code);
  document.getElementById("prop-json").addEventListener("click", () => {
    const file = {
      noise_model: result.noise,
      diagram: result.diagram,
      summary: result.summary,
      effects: result.effects.map((e) => ({ ...e, boundary: Object.fromEntries(e.boundary) })),
      boundary_edges: result.labels,
    };
    download(`${result.noise.id.toLowerCase()}-propagation.json`, JSON.stringify(file, null, 2), "application/json");
  });
  scrollToResult(results.querySelector(".headline"));
}
