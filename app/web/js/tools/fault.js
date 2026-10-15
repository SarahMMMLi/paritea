// Fault equivalence: do two noisy diagrams behave the same, fault for fault, up to some fault weight?

import { shelf } from "../shelf.js";
import { codeCardHtml, errorHtml, escapeHtml, formatSeconds, noticeHtml, plural, scrollToResult, wireCopyButtons, withBusyButton } from "../ui.js";

// Pairs from paritea's demo and tests, with paritea's answers.
const PAIRS = [
  {
    label: "Steane |0⟩ vs its preparation circuit (demo)",
    make: async (ctx) => {
      const state = await ctx.engine.run("diagram_example", { example: "steane-state" });
      const circuit = await ctx.engine.run("diagram_example", { example: "steane-circuit" });
      const types = new Map(state.diagram.nodes.map((n) => [n.id, n.type]));
      const xWires = state.diagram.edges.filter(([, s, t]) => types.get(s) === "X" || types.get(t) === "X").map(([e]) => e);
      const weights = { x: 1, y: 2, z: 1 }; // as in paritea's demo notebook
      const a = await ctx.engine.run("noise_model", { diagram: state.id, weights, noise_free: xWires });
      const b = await ctx.engine.run("noise_model", { diagram: circuit.id, weights, noise_free: [] });
      [state, circuit].forEach((d) => shelf.add(d));
      [a, b].forEach((n) => shelf.addNoise(n));
      return [a.id, b.id];
    },
  },
  { label: "Two π/2 spiders vs one π spider", diagrams: ["two-half-pi", "one-pi"] },
  { label: "Star vs ring of 5", diagrams: ["star-5", "ring-5"] },
  { label: "Star vs ring of 6", diagrams: ["star-6", "ring-6"] },
];
const remembered = { a: null, b: null, limit: "4", smallest: true };

export async function renderFault(ctx, query) {
  const live = ctx.engine.mode !== "precomputed";
  ctx.app.innerHTML = `
    <nav class="crumbs"><a href="#/">Tools</a> / Fault equivalence</nav>
    <header class="tool-head">
      <h1>Fault equivalence</h1>
      <p class="lead">Check whether two noisy diagrams are interchangeable: every fault on one side must have a fault on
        the other side with the same effect and no larger weight, up to a weight you choose.</p>
    </header>
    <div class="io-cards">
      <section class="io-card"><h2>You provide</h2>
        <ol><li><strong>Two noise models</strong> from your shelf, or two diagrams (then every edge gets an X, a Y and a Z
            fault of weight 1). They must be the same map, with boundaries in the same order.</li>
          <li><strong>How far to check</strong>: fault weights up to some number, or no limit</li></ol></section>
      <section class="io-card"><h2>You get</h2>
        <ul><li><strong>Yes or no</strong>, with the reason and how long it took</li>
          <li>Optionally, the smallest fault weight at which the two differ</li>
          <li>Python code that asks paritea the same question</li></ul></section>
    </div>
    ${live ? "" : noticeHtml("Fault equivalence needs the in-browser engine, which isn't running here (preview mode).")}
    <form class="panel" id="fault-form" novalidate>
      <div class="step"><span class="step-n">1</span><div class="step-body">
        <span class="field-label">Two noisy diagrams</span>
        <div class="pair-row" id="pair-pick"></div>
        <p class="help">Or try a pair from paritea's demo and tests:</p>
        <div class="preset-row">${PAIRS.map(
          (p, i) => `<button type="button" class="btn btn-ghost btn-small" data-pair="${i}">${escapeHtml(p.label)}</button>`,
        ).join("")}</div>
      </div></div>
      <div class="step"><span class="step-n">2</span><div class="step-body">
        <span class="field-label">How far to check</span>
        <div class="limit-row">
          <label class="check"><input type="radio" name="limit" value="weight" ${remembered.limit !== "none" ? "checked" : ""}>
            Fault weights up to <input type="number" id="max-weight" min="1" max="12" step="1" value="${remembered.limit === "none" ? 4 : remembered.limit}"></label>
          <label class="check"><input type="radio" name="limit" value="none" ${remembered.limit === "none" ? "checked" : ""}> No limit</label>
        </div>
        <label class="check"><input type="checkbox" id="smallest" ${remembered.smallest ? "checked" : ""}>
          If the answer is no, also find the smallest fault weight where they differ</label>
        <p class="help">The check grows quickly with the weight and the size of the diagrams. Small examples take
          milliseconds; for big diagrams, start low. You can cancel a run at any time.</p>
      </div></div>
      <div class="actions">
        <button class="btn btn-primary" id="run" type="submit">Check fault equivalence</button>
        <button class="btn btn-ghost" id="cancel" type="button" hidden>Cancel</button>
        <span class="hint" id="elapsed"></span>
      </div>
    </form>
    <section class="results" id="results" aria-live="polite">
      <div class="empty">The answer appears here, with the reason and the Python that reproduces it.</div>
    </section>`;

  renderPick(live);
  ctx.app.querySelectorAll("[data-pair]").forEach((button) =>
    button.addEventListener("click", () => usePair(ctx, PAIRS[Number(button.dataset.pair)], button, live)),
  );
  document.getElementById("fault-form").addEventListener("submit", (e) => {
    e.preventDefault();
    check(ctx);
  });
}

function renderPick(live) {
  const box = document.getElementById("pair-pick");
  const models = [...shelf.noise.values()];
  const diagrams = shelf.list();
  if (!live || (!models.length && !diagrams.length)) {
    box.innerHTML = `<p class="help">${live ? "Your shelf is empty." : "The shelf needs the in-browser engine."}
      <a href="#/noise">Build noise models</a> or <a href="#/diagrams">diagrams</a>, or use a pair below.</p>`;
    return;
  }
  const options = `
    ${models.length ? `<optgroup label="Noise models">${models
      .map((n) => `<option value="${n.id}">${n.id} · ${escapeHtml(n.name)}</option>`)
      .join("")}</optgroup>` : ""}
    ${diagrams.length ? `<optgroup label="Diagrams (weight-1 faults on every edge)">${diagrams
      .map((d) => `<option value="${d.id}">${d.id} · ${escapeHtml(d.name)}</option>`)
      .join("")}</optgroup>` : ""}`;
  box.innerHTML = ["a", "b"]
    .map((side) => `<label class="param">Side ${side.toUpperCase()}<select id="fault-${side}">${options}</select></label>`)
    .join("");
  const ids = [...models.map((n) => n.id), ...diagrams.map((d) => d.id)];
  const a = document.getElementById("fault-a");
  const b = document.getElementById("fault-b");
  if (remembered.a && ids.includes(remembered.a)) a.value = remembered.a;
  b.value = remembered.b && ids.includes(remembered.b) ? remembered.b : ids[Math.min(1, ids.length - 1)];
  a.addEventListener("change", () => (remembered.a = a.value));
  b.addEventListener("change", () => (remembered.b = b.value));
}

async function usePair(ctx, pair, button, live) {
  let ids;
  await withBusyButton(button, "Preparing…", async () => {
    try {
      if (pair.make) {
        ids = await pair.make(ctx);
      } else {
        const made = [];
        for (const example of pair.diagrams) made.push(await ctx.engine.run("diagram_example", { example }));
        made.forEach((d) => shelf.add(d));
        ids = made.map((d) => d.id);
      }
    } catch (err) {
      document.getElementById("results").innerHTML = errorHtml("Couldn't prepare the pair.", err);
    }
  });
  if (!ids) return;
  [remembered.a, remembered.b] = ids;
  remembered.limit = "none";
  remembered.smallest = true;
  document.querySelector('input[name="limit"][value="none"]').checked = true;
  document.getElementById("smallest").checked = true;
  renderPick(live);
  document.getElementById("fault-form").requestSubmit();
}

async function check(ctx) {
  const results = document.getElementById("results");
  const a = document.getElementById("fault-a");
  const b = document.getElementById("fault-b");
  if (!a || !b) {
    results.innerHTML = errorHtml("Nothing to compare.", new Error("Put noise models or diagrams on your shelf, or use a pair."));
    return;
  }
  const noLimit = document.querySelector('input[name="limit"]:checked').value === "none";
  const maxWeight = Number(document.getElementById("max-weight").value);
  if (!noLimit && (!Number.isInteger(maxWeight) || maxWeight < 1 || maxWeight > 12)) {
    results.innerHTML = errorHtml("Check the inputs.", new Error("The maximum fault weight must be a whole number from 1 to 12."));
    return;
  }
  const smallest = document.getElementById("smallest").checked;
  Object.assign(remembered, { a: a.value, b: b.value, limit: noLimit ? "none" : String(maxWeight), smallest });

  const cancel = document.getElementById("cancel");
  const elapsed = document.getElementById("elapsed");
  const started = performance.now();
  const timer = setInterval(() => (elapsed.textContent = `Running for ${Math.round((performance.now() - started) / 1000)} s`), 1000);
  cancel.hidden = false;
  cancel.onclick = () => ctx.engine.restart("Cancelled.");
  await withBusyButton(document.getElementById("run"), "Checking…", async () => {
    ctx.setBusy(true);
    try {
      const result = await ctx.engine.run("fault_equivalence", {
        a: a.value,
        b: b.value,
        max_weight: noLimit ? null : maxWeight,
        smallest,
      });
      showResult(result);
    } catch (err) {
      if (err.type === "Cancelled") {
        window.lastFault = { cancelled: true };
        results.innerHTML = noticeHtml(
          "Cancelled. The engine is restarting (a few seconds), so your shelf is empty again: build the diagrams and " +
            "noise models again, or use a pair.",
        );
        renderPick(true);
      } else {
        results.innerHTML = errorHtml(err.type === "UserError" ? "Please check this:" : "The check failed.", err);
      }
    } finally {
      clearInterval(timer);
      cancel.hidden = true;
      elapsed.textContent = "";
      ctx.setBusy(false);
    }
  });
}

function showResult(result) {
  window.lastFault = result; // for the browser check in app/build/check_site.py
  const results = document.getElementById("results");
  const scope = result.max_weight === null ? "for faults of any weight" : `for fault weights up to ${result.max_weight}`;
  const headline = result.equivalent
    ? `Yes: A and B are fault equivalent ${scope}`
    : result.semantic ? `No: A and B are not fault equivalent ${scope}` : "No: A and B are not even the same map";
  const difference = result.first_difference
    ? `<p class="first-difference">They agree for every fault of weight ${result.first_difference - 1} or less and first
        differ at weight <strong>${result.first_difference}</strong>.</p>`
    : "";
  results.innerHTML = `
    <div class="verdict ${result.equivalent ? "yes" : "no"}">
      <span class="verdict-mark" aria-hidden="true">${result.equivalent ? "✓" : "✗"}</span>
      <div><h2 class="headline">${headline}</h2>
        <p class="meta">${escapeHtml(result.reason)} Checked in ${formatSeconds(result.seconds)}
          <span class="where">in your browser</span></p>
        ${difference}</div>
    </div>
    ${result.notes.map(noticeHtml).join("")}
    <div class="below">
      ${["a", "b"]
        .map(
          (side) => `<section class="card"><div class="card-head"><h3>${side.toUpperCase()} · ${escapeHtml(result[side].id)}</h3>
            <span class="muted">${plural(result[side].faults, "fault")}</span></div>
            <p class="card-note plain-pad">${escapeHtml(result[side].name)}</p></section>`,
        )
        .join("")}
    </div>
    ${codeCardHtml(result.code, "Python code that asks paritea the same question")}`;
  wireCopyButtons(results, result.code);
  scrollToResult(results.querySelector(".headline"));
}
