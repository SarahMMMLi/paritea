// Semantic equivalence: are two diagrams the same linear map (up to a scalar)?

import { shelf } from "../shelf.js";
import { codeCardHtml, errorHtml, escapeHtml, noticeHtml, plural, scrollToResult, wireCopyButtons, withBusyButton } from "../ui.js";

// Ready-made pairs from paritea's tests, with what paritea answers for them.
const PAIRS = [
  {
    label: "Surface code: 1 round vs 2 rounds",
    a: ["diagram_generate", { generator: "Rotated surface code memory experiment", params: { distance: 3, rounds: 1 } }],
    b: ["diagram_generate", { generator: "Rotated surface code memory experiment", params: { distance: 3, rounds: 2 } }],
    answer: true,
  },
  { label: "Two π/2 spiders vs one π spider", a: ["diagram_example", { example: "two-half-pi" }], b: ["diagram_example", { example: "one-pi" }], answer: true },
  { label: "Two π/2 spiders vs one π/2 spider", a: ["diagram_example", { example: "two-half-pi" }], b: ["diagram_example", { example: "one-half-pi" }], answer: false },
  { label: "Star of 6 vs ring of 6", a: ["diagram_example", { example: "star-6" }], b: ["diagram_example", { example: "ring-6" }], answer: true },
];
const remembered = { a: null, b: null };

export async function renderSemantic(ctx, query) {
  const live = ctx.engine.mode !== "precomputed";
  ctx.app.innerHTML = `
    <nav class="crumbs"><a href="#/">Tools</a> / Semantic equivalence</nav>
    <header class="tool-head">
      <h1>Semantic equivalence</h1>
      <p class="lead">Check whether two diagrams are the same linear map, up to a scalar: paritea compares their
        stabilisers on the boundary.</p>
    </header>
    <div class="io-cards">
      <section class="io-card"><h2>You provide</h2>
        <ol><li><strong>Two diagrams</strong> from your shelf, with the same numbers of inputs and outputs. Boundaries are
          matched in order: inputs first, then outputs.</li></ol></section>
      <section class="io-card"><h2>You get</h2>
        <ul><li><strong>Yes or no</strong>, with the reason</li>
          <li>Both diagrams' row-reduced stabilisers on their boundaries, side by side</li>
          <li>Python code that asks paritea the same question</li></ul></section>
    </div>
    ${live ? "" : noticeHtml("Semantic equivalence needs the in-browser engine, which isn't running here (preview mode).")}
    <form class="panel" id="sem-form" novalidate>
      <div class="step"><span class="step-n">1</span><div class="step-body">
        <span class="field-label">Two diagrams</span>
        <div class="pair-row" id="pair-pick"></div>
        <p class="help">Or try a pair from paritea's tests:</p>
        <div class="preset-row">${PAIRS.map(
          (p, i) => `<button type="button" class="btn btn-ghost btn-small" data-pair="${i}">${escapeHtml(p.label)}</button>`,
        ).join("")}</div>
      </div></div>
      <div class="actions">
        <button class="btn btn-primary" id="run" type="submit">Check equivalence</button>
        <span class="hint">Usually well under a second</span>
      </div>
    </form>
    <section class="results" id="results" aria-live="polite">
      <div class="empty">The answer appears here, with both diagrams' stabilisers on their boundaries.</div>
    </section>`;

  if (query.a) remembered.a = query.a;
  if (query.b) remembered.b = query.b;
  renderPick(live);
  ctx.app.querySelectorAll("[data-pair]").forEach((button) =>
    button.addEventListener("click", () => usePair(ctx, PAIRS[Number(button.dataset.pair)], button, live)),
  );
  document.getElementById("sem-form").addEventListener("submit", (e) => {
    e.preventDefault();
    check(ctx);
  });
}

function renderPick(live) {
  const box = document.getElementById("pair-pick");
  const diagrams = shelf.list();
  if (!live || !diagrams.length) {
    box.innerHTML = `<p class="help">${live ? "Your shelf is empty." : "The shelf needs the in-browser engine."}
      <a href="#/diagrams">Build, open or import diagrams</a>, or use a pair below.</p>`;
    return;
  }
  const options = diagrams
    .map((e) => `<option value="${e.id}">${e.id} · ${escapeHtml(e.name)} (${e.summary.Inputs} in, ${e.summary.Outputs} out)</option>`)
    .join("");
  box.innerHTML = ["a", "b"]
    .map((side) => `<label class="param">Diagram ${side.toUpperCase()}<select id="sem-${side}">${options}</select></label>`)
    .join("");
  const a = document.getElementById("sem-a");
  const b = document.getElementById("sem-b");
  if (remembered.a && shelf.entries.has(remembered.a)) a.value = remembered.a;
  b.value = remembered.b && shelf.entries.has(remembered.b) ? remembered.b : diagrams[Math.min(1, diagrams.length - 1)].id;
  a.addEventListener("change", () => (remembered.a = a.value));
  b.addEventListener("change", () => (remembered.b = b.value));
}

async function usePair(ctx, pair, button, live) {
  const results = document.getElementById("results");
  let ready = false;
  await withBusyButton(button, "Preparing…", async () => {
    try {
      const a = await ctx.engine.run(...pair.a);
      const b = await ctx.engine.run(...pair.b);
      shelf.add(a);
      shelf.add(b);
      remembered.a = a.id;
      remembered.b = b.id;
      ready = true;
    } catch (err) {
      if (results.isConnected) results.innerHTML = errorHtml("Couldn't prepare the pair.", err);
    }
  });
  if (!ready || !results.isConnected) return; // it failed, or the visitor went to another page meanwhile
  renderPick(live);
  if (document.getElementById("sem-a")) document.getElementById("sem-form").requestSubmit();
}

async function check(ctx) {
  const results = document.getElementById("results");
  const a = document.getElementById("sem-a");
  const b = document.getElementById("sem-b");
  if (!a || !b) {
    results.innerHTML = errorHtml("No diagrams chosen.", new Error("Put two diagrams on your shelf first, or use a pair."));
    return;
  }
  remembered.a = a.value;
  remembered.b = b.value;
  await withBusyButton(document.getElementById("run"), "Checking…", async () => {
    ctx.setBusy(true);
    try {
      const result = await ctx.engine.run("semantic_equivalence", { a: a.value, b: b.value });
      if (results.isConnected) showResult(result); // unless the visitor went to another page meanwhile
    } catch (err) {
      if (!results.isConnected) return;
      results.innerHTML = errorHtml(err.type === "UserError" ? "Please check this:" : "The check failed.", err);
    } finally {
      ctx.setBusy(false);
    }
  });
}

function tableauHtml(side, other) {
  const shared = new Set(other.rows);
  const row = (text) => {
    const letters = [...text]
      .map((p, i) => `${i === side.inputs && side.inputs ? '<span class="io-split">|</span>' : ""}<span class="p ${p}">${p}</span>`)
      .join("");
    return `<li class="${shared.has(text) ? "" : "differs"}"><code>${letters}</code></li>`;
  };
  return `<section class="card tableau">
      <div class="card-head"><h3>${escapeHtml(side.id)} · ${escapeHtml(side.name)}</h3>
        <span class="muted">${side.inputs} in | ${side.outputs} out</span></div>
      ${side.rows.length ? `<ol>${side.rows.map(row).join("")}</ol>` : `<p class="muted-cell">No stabilisers on the boundary.</p>`}
    </section>`;
}

function showResult(result) {
  window.lastSemantic = result; // for the browser check in app/build/check_site.py
  const results = document.getElementById("results");
  results.innerHTML = `
    <div class="verdict ${result.equivalent ? "yes" : "no"}">
      <span class="verdict-mark" aria-hidden="true">${result.equivalent ? "✓" : "✗"}</span>
      <div><h2 class="headline">${result.equivalent ? "Yes: A and B are semantically equivalent" : "No: A and B are not semantically equivalent"}</h2>
        <p class="meta">${escapeHtml(result.reason)}</p></div>
    </div>
    <p class="card-note plain">Each line is one stabiliser generator, row reduced, written over the boundaries
      (inputs | outputs). ${result.equivalent ? "" : "Lines that do not appear on the other side are marked."}
      ${plural(result.a.rows.length, "stabiliser")} vs ${plural(result.b.rows.length, "stabiliser")}.</p>
    <div class="below tableaus">${tableauHtml(result.a, result.b)}${tableauHtml(result.b, result.a)}</div>
    ${codeCardHtml(result.code, "Python code that asks paritea the same question")}`;
  wireCopyButtons(results, result.code);
  scrollToResult(results.querySelector(".headline"));
}
