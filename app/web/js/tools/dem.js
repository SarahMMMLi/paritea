// stim → detector error model: paritea's DEM for a stim circuit, checked against stim's own.

import { shelf } from "../shelf.js";
import {
  codeCardHtml,
  copyLinkHtml,
  download,
  errorHtml,
  escapeHtml,
  formatSeconds,
  noticeHtml,
  plural,
  scrollToResult,
  setLink,
  statsHtml,
  wireCopyButtons,
  wireCopyLink,
  withBusyButton,
} from "../ui.js";

const MAX_DEM_LINES = 400;
const remembered = { source: "preset", distance: 3, rounds: 2, p: 0.001, text: "", filename: "" };

export async function renderDem(ctx, query) {
  const live = ctx.engine.mode !== "precomputed";
  // A link gives the surface-code circuit's distance, rounds and error rate; it runs straight away.
  const fromLink = ["distance", "rounds", "p"].some((key) => key in query);
  if (fromLink) {
    remembered.source = "preset";
    for (const key of ["distance", "rounds", "p"]) if (key in query) remembered[key] = Number(query[key]);
  }
  ctx.app.innerHTML = `
    <nav class="crumbs"><a href="#/">Tools</a> / stim → detector error model</nav>
    <header class="tool-head">
      <h1>stim → detector error model</h1>
      <p class="lead">Turn a noisy stim circuit into paritea's detector error model (DEM): paritea imports the circuit
        as a ZX diagram with a noise model, pushes every fault out to the circuit's detectors and observables, and
        writes the result in stim's DEM format.</p>
    </header>
    <div class="io-cards">
      <section class="io-card"><h2>You provide</h2>
        <ol><li><strong>A stim circuit</strong>: stim's rotated surface-code memory experiment (distance, rounds, error
          rate), or your own circuit as text or a <code>.stim</code> file</li></ol></section>
      <section class="io-card"><h2>You get</h2>
        <ul><li>paritea's DEM as a <code>.dem</code> file, with its detectors, observables and error mechanisms</li>
          <li>A check against stim's own DEM for the same circuit</li>
          <li>The circuit's ZX diagram on your shelf, Python code, and a script that compares logical error rates
            by sampling (to run on your computer)</li></ul></section>
    </div>
    ${live ? "" : noticeHtml("The stim tool needs the in-browser engine, which isn't running here (preview mode).")}
    <form class="panel" id="dem-form" novalidate>
      <div class="step"><span class="step-n">1</span><div class="step-body">
        <span class="field-label" id="circuit-label">Circuit</span>
        <div class="segmented" role="tablist" aria-labelledby="circuit-label">
          <button type="button" role="tab" data-source="preset">Surface-code memory experiment</button>
          <button type="button" role="tab" data-source="text">My own circuit</button>
        </div>
        <div id="dem-source" class="source-body"></div>
      </div></div>
      <div class="actions">
        <button class="btn btn-primary" id="run" type="submit">Build detector error model</button>
        <span class="hint">Usually a second or less</span>
      </div>
    </form>
    <section class="results" id="results" aria-live="polite">
      <div class="empty">paritea's detector error model appears here, with the check against stim's.</div>
    </section>`;

  const show = (source) => {
    remembered.source = source;
    ctx.app.querySelectorAll("[data-source]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.source === source)));
    const box = document.getElementById("dem-source");
    if (source === "preset") {
      box.innerHTML = `
        <p class="help">stim's <code>surface_code:rotated_memory_z</code> circuit, with error rate p after every
          Clifford gate, reset and round, and before every measurement.</p>
        <div class="params">
          <div class="param"><label for="dem-d">Distance <span class="range">(2–9)</span></label>
            <input id="dem-d" type="number" min="2" max="9" step="1" value="${remembered.distance}"></div>
          <div class="param"><label for="dem-r">Rounds <span class="range">(1–20)</span></label>
            <input id="dem-r" type="number" min="1" max="20" step="1" value="${remembered.rounds}"></div>
          <div class="param"><label for="dem-p">Error rate p <span class="range">(0–0.1)</span></label>
            <input id="dem-p" type="number" min="0" max="0.1" step="0.001" value="${remembered.p}"></div>
        </div>`;
    } else {
      box.innerHTML = `
        <div class="file-row"><input type="file" id="dem-file" accept=".stim,.txt"></div>
        <textarea id="dem-text" rows="9" spellcheck="false" placeholder="…or paste a stim circuit here">${escapeHtml(remembered.text)}</textarea>
        <p class="help">paritea's import supports H, CX, R, M, MR, X/Y/Z_ERROR, DEPOLARIZE1/2, DETECTOR and
          OBSERVABLE_INCLUDE; TICK and coordinates are ignored and REPEAT blocks are unrolled. Every qubit must start
          in |0⟩ and end with a measurement.</p>`;
      document.getElementById("dem-file").addEventListener("change", async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        remembered.filename = file.name;
        document.getElementById("dem-text").value = await file.text();
      });
    }
  };
  ctx.app.querySelectorAll("[data-source]").forEach((b) => b.addEventListener("click", () => show(b.dataset.source)));
  show(remembered.source);

  document.getElementById("dem-form").addEventListener("submit", (e) => {
    e.preventDefault();
    build(ctx);
  });
  if (fromLink) document.getElementById("dem-form").requestSubmit();
}

async function build(ctx) {
  const results = document.getElementById("results");
  let args;
  if (remembered.source === "preset") {
    const d = Number(document.getElementById("dem-d").value);
    const r = Number(document.getElementById("dem-r").value);
    const p = Number(document.getElementById("dem-p").value);
    const problem =
      !Number.isInteger(d) || d < 2 || d > 9 ? "The distance must be a whole number from 2 to 9."
      : !Number.isInteger(r) || r < 1 || r > 20 ? "The number of rounds must be a whole number from 1 to 20."
      : !(p >= 0 && p <= 0.1) ? "The error rate p must be between 0 and 0.1." : null;
    if (problem) {
      results.innerHTML = errorHtml("Check the inputs.", new Error(problem));
      return;
    }
    Object.assign(remembered, { distance: d, rounds: r, p });
    args = { preset: { distance: d, rounds: r, p } };
  } else {
    const text = document.getElementById("dem-text").value;
    remembered.text = text;
    args = { text, filename: remembered.filename };
  }
  await withBusyButton(document.getElementById("run"), "Building…", async () => {
    ctx.setBusy(true);
    try {
      const result = await ctx.engine.run("stim_dem", args);
      shelf.add(result.entry);
      showResult(result);
    } catch (err) {
      results.innerHTML = errorHtml(err.type === "UserError" ? "Please check this:" : "Building the DEM failed.", err);
    } finally {
      ctx.setBusy(false);
    }
  });
}

function comparisonHtml(c) {
  if (!c.available) return noticeHtml(c.message ?? "stim's own DEM is not available for this circuit.");
  const matches = c.only_paritea === 0 && c.only_stim === 0 && c.worst_relative < 1e-9;
  return `<div class="verdict ${matches ? "yes" : "no"}">
      <span class="verdict-mark" aria-hidden="true">${matches ? "✓" : "✗"}</span>
      <div><h3 class="verdict-title">${matches ? "Matches stim's own DEM" : "Differs from stim's own DEM"}</h3>
        <p class="meta">paritea: ${plural(c.paritea, "error mechanism")}; stim: ${c.stim}.
          ${c.only_paritea || c.only_stim ? `${c.only_paritea} only in paritea's, ${c.only_stim} only in stim's.` : "The same ones in both."}
          Largest relative difference in probability: ${c.worst_relative.toExponential(1)}.</p></div>
    </div>`;
}

function showResult(result) {
  window.lastDem = result; // for the browser check in app/build/check_site.py
  const preset = result.entry.source.preset;
  setLink("dem", preset);
  const results = document.getElementById("results");
  const lines = result.dem.split("\n");
  const shown = lines.slice(0, MAX_DEM_LINES).join("\n");
  const s = result.summary;
  results.innerHTML = `
    <div class="result-head">
      <h2 class="headline">${plural(s.Detectors, "detector")}, ${plural(s.Observables, "observable")} and
        ${plural(s["Error mechanisms"], "error mechanism")}</h2>
      <p class="meta">${escapeHtml(result.name)} · computed in ${formatSeconds(result.seconds)}
        <span class="where">in your browser</span>${preset ? ` · ${copyLinkHtml()}` : ""}</p>
    </div>
    ${comparisonHtml(result.comparison)}
    ${noticeHtml(`paritea numbers the observables first, so its detectors start at D${s.Observables}: its D${s.Observables} is stim's D0, and so on. The check above takes this into account.`)}
    ${statsHtml(s)}
    <div class="next-steps">
      <a class="btn btn-ghost" href="#/diagrams?diagram=${result.diagram.id}">See the circuit's ZX diagram (${escapeHtml(result.diagram.id)})</a>
      <a class="btn btn-ghost" href="#/webs?diagram=${result.diagram.id}&run=1">Its detecting regions</a>
      <span class="download-label">Download</span>
      <button type="button" class="btn btn-ghost btn-small" id="dem-download">.dem file</button>
    </div>
    <section class="card">
      <div class="card-head"><h3>Detector error model (${plural(s["Error mechanisms"], "line")})</h3></div>
      <pre class="code dem-text"><code>${escapeHtml(shown)}</code></pre>
      ${lines.length > MAX_DEM_LINES ? `<p class="truncated">Showing the first ${MAX_DEM_LINES} lines; the .dem file has them all.</p>` : ""}
    </section>
    <div class="below">
      ${codeCardHtml(result.code, "Python code that builds this DEM")}
      ${codeCardHtml(result.sinter_code, "Compare logical error rates by sampling (run on your computer)")}
    </div>`;
  const [codeCard, sinterCard] = results.querySelectorAll(".code-card");
  wireCopyButtons(codeCard, result.code);
  wireCopyButtons(sinterCard, result.sinter_code);
  wireCopyLink(results);
  document.getElementById("dem-download").addEventListener("click", () =>
    download(`${result.diagram.id.toLowerCase()}-paritea.dem`, result.dem),
  );
  scrollToResult(results.querySelector(".headline"));
}
