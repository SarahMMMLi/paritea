// Small helpers shared by the tool pages: HTML escaping, result blocks, the diagram viewer and downloads.

import { DiagramView } from "./diagram-view.js";

export const escapeHtml = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

export const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export function formatSeconds(seconds) {
  return seconds < 1 ? `${Math.max(1, Math.round(seconds * 1000))} ms` : `${seconds.toFixed(2)} s`;
}

export function statsHtml(summary) {
  return `<div class="stats">${Object.entries(summary)
    .map(([k, v]) => `<div class="stat"><div class="stat-label">${escapeHtml(k)}</div><div class="stat-value">${v}</div></div>`)
    .join("")}</div>`;
}

export function errorHtml(action, err) {
  const details = err.traceback
    ? `<details><summary>Technical details</summary><pre>${escapeHtml(err.traceback)}</pre></details>`
    : "";
  return `<div class="alert alert-error" role="alert"><strong>${escapeHtml(action)}</strong> ${escapeHtml(err.message)}${details}</div>`;
}

export function noticeHtml(text) {
  return `<div class="alert alert-preview">${escapeHtml(text)}</div>`;
}

export function codeCardHtml(code, title = "Python code that reproduces this") {
  return `<section class="card code-card">
      <div class="card-head"><h3>${escapeHtml(title)}</h3>
        <button type="button" class="btn btn-ghost btn-small" data-copy>Copy</button></div>
      <pre class="code"><code>${escapeHtml(code)}</code></pre>
    </section>`;
}

export function wireCopyButtons(root, code) {
  root.querySelectorAll("[data-copy]").forEach((button) =>
    button.addEventListener("click", async () => {
      await navigator.clipboard.writeText(code);
      button.textContent = "Copied";
      setTimeout(() => (button.textContent = "Copy"), 1500);
    }),
  );
}

export function download(filename, text, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const LEGEND_WEBS = `
  <span class="legend-item"><span class="swatch X"></span>X on edge</span>
  <span class="legend-item"><span class="swatch Y"></span>Y on edge</span>
  <span class="legend-item"><span class="swatch Z"></span>Z on edge</span>`;

/** Markup for the diagram viewer. `bar` goes on the left of the toolbar (e.g. web stepping controls). */
export function viewerHtml({ bar = "", webs = false } = {}) {
  return `<div class="viewer">
      <div class="viewer-bar">${bar}
        <div class="viewer-tools">
          <button type="button" class="icon-btn" data-zoom="out" aria-label="Zoom out">−</button>
          <button type="button" class="icon-btn" data-zoom="in" aria-label="Zoom in">+</button>
          <button type="button" class="btn btn-ghost btn-small" data-zoom="fit">Fit</button>
        </div>
      </div>
      <div class="canvas-wrap">
        <svg class="diagram" role="group" aria-roledescription="diagram" aria-label="The ZX diagram"></svg>
        <div class="tooltip" role="presentation"></div>
        <span class="canvas-hint">Drag to move · pinch or Ctrl + scroll to zoom${webs ? " · ← → to step" : ""}</span>
      </div>
      <div class="legend">${webs ? LEGEND_WEBS : ""}
        <span class="legend-item"><span class="dot-node Z"></span>Z spider</span>
        <span class="legend-item"><span class="dot-node X"></span>X spider</span>
        <span class="legend-item"><span class="dot-node H"></span>H box</span>
        <span class="legend-item"><span class="dot-node B"></span>Boundary</span>
      </div>
    </div>`;
}

/** Draws `diagram` in the viewer inside `root` and wires up its zoom buttons. */
export function mountViewer(root, diagram) {
  const view = new DiagramView(root.querySelector(".canvas-wrap"));
  view.setDiagram(diagram);
  root.querySelector('[data-zoom="in"]').addEventListener("click", () => view.zoom(0.8));
  root.querySelector('[data-zoom="out"]').addEventListener("click", () => view.zoom(1.25));
  root.querySelector('[data-zoom="fit"]').addEventListener("click", () => view.fit());
  return view;
}

/** Number inputs for a generator's parameters. */
export function paramsHtml(generator, values = {}) {
  return generator.params
    .map(
      (p) => `
      <div class="param">
        <label for="p-${p.key}">${escapeHtml(p.label)} <span class="range">(${p.step > 1 ? rangeWithStep(p) : `${p.min}–${p.max}`})</span></label>
        <input id="p-${p.key}" name="${p.key}" type="number" min="${p.min}" max="${p.max}" step="${p.step}" required
          value="${values[p.key] ?? p.default}">
        ${p.help ? `<span class="param-help">${escapeHtml(p.help)}</span>` : ""}
      </div>`,
    )
    .join("");
}

function rangeWithStep(p) {
  const values = [];
  for (let v = p.min; v <= p.max; v += p.step) values.push(v);
  return values.join(", ");
}

/** Reads and checks the parameter inputs; throws an Error with a plain message if one is out of range. */
export function readParams(generator) {
  const params = {};
  for (const p of generator.params) {
    const input = document.getElementById(`p-${p.key}`);
    const value = Number(input.value);
    if (!Number.isInteger(value) || value < p.min || value > p.max || (value - p.min) % p.step) {
      input.focus();
      throw new Error(`${p.label} must be ${p.step > 1 ? `one of ${rangeWithStep(p)}` : `a whole number from ${p.min} to ${p.max}`}.`);
    }
    params[p.key] = value;
  }
  return params;
}

/** Puts a button into its busy state while `task` runs. */
export async function withBusyButton(button, busyLabel, task) {
  const label = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `<span class="spinner" aria-hidden="true"></span> ${escapeHtml(busyLabel)}`;
  try {
    return await task();
  } finally {
    button.disabled = false;
    button.innerHTML = label;
  }
}
