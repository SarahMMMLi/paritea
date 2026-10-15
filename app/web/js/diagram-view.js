// Draws a ZX diagram as SVG in pyzx's style and highlights one Pauli web on it. Drag to pan; pinch or Ctrl+scroll
// (and the +/− buttons) to zoom.

const SVG_NS = "http://www.w3.org/2000/svg";
const UNIT = 40; // pixels per diagram coordinate unit at zoom 1
const MAX_PHASE_LABELS = 800;
const NODE_NAMES = { Z: "Z spider", X: "X spider", H: "H box", B: "Boundary" };
// Concrete colours for exported SVG files, which cannot use the page's CSS variables.
const EXPORT_CSS = `
  .edge { stroke: #334155; stroke-width: 1.4; }
  .has-web .edge { opacity: 0.35; }
  .web-edge { stroke-width: 7; stroke-linecap: round; opacity: 0.85; }
  .web-edge.X { stroke: #d62728; } .web-edge.Y { stroke: #1f77b4; } .web-edge.Z { stroke: #2ca02c; }
  .node { stroke: #1e293b; stroke-width: 1.1; }
  .node.Z { fill: #ccffcc; } .node.X { fill: #ff8888; } .node.H { fill: #ffff66; } .node.B { fill: #0f172a; stroke: none; }
  .phase { font: 11px ui-monospace, Menlo, monospace; fill: #475569; text-anchor: middle; }`;

function el(name, attrs = {}, parent = null) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.append(node);
  return node;
}

export function phaseLabel(phase) {
  if (phase === "0") return "";
  const [num, den] = phase.split("/");
  const n = num === "1" ? "" : num === "-1" ? "-" : num;
  return den ? `${n}π/${den}` : `${n}π`;
}

export class DiagramView {
  constructor(wrap) {
    this.wrap = wrap;
    this.svg = wrap.querySelector("svg");
    this.tip = wrap.querySelector(".tooltip");
    this.web = el("g", {}, this.svg);
    this.edges = el("g", {}, this.svg);
    this.nodes = el("g", {}, this.svg);
    this.labels = el("g", {}, this.svg);
    this.box = { x: 0, y: 0, w: 100, h: 100 };
    this.bindPointer();
  }

  setDiagram(diagram) {
    this.diagram = diagram;
    this.points = new Map(diagram.nodes.map((n) => [n.id, n]));
    this.endpoints = new Map(diagram.edges.map(([e, s, t]) => [e, [s, t]]));
    for (const layer of [this.web, this.edges, this.nodes, this.labels]) layer.replaceChildren();

    const role = new Map();
    diagram.inputs.forEach((n, i) => role.set(n, `input ${i}`));
    diagram.outputs.forEach((n, i) => role.set(n, `output ${i}`));

    for (const [e, s, t] of diagram.edges) {
      const a = this.points.get(s);
      const b = this.points.get(t);
      el("line", { class: "edge", x1: a.x * UNIT, y1: a.y * UNIT, x2: b.x * UNIT, y2: b.y * UNIT }, this.edges);
      el("line", { class: "hit", x1: a.x * UNIT, y1: a.y * UNIT, x2: b.x * UNIT, y2: b.y * UNIT, "data-tip": `Edge ${e} (nodes ${s}–${t})` }, this.edges);
    }

    const showPhases = diagram.nodes.length <= MAX_PHASE_LABELS;
    for (const n of diagram.nodes) {
      const x = n.x * UNIT;
      const y = n.y * UNIT;
      // An H box is always a Hadamard to paritea; pyzx gives them phase 1, paritea 0, so neither is shown.
      const phase = n.type === "H" && (n.phase === "0" || n.phase === "1") ? "" : phaseLabel(n.phase);
      const tip = [`${NODE_NAMES[n.type] ?? n.type} ${n.id}`, phase && `phase ${phase}`, role.get(n.id)].filter(Boolean).join(" · ");
      if (n.type === "H") el("rect", { class: "node H", x: x - 9, y: y - 9, width: 18, height: 18, "data-tip": tip }, this.nodes);
      else el("circle", { class: `node ${n.type}`, cx: x, cy: y, r: n.type === "B" ? 4.5 : 11.5, "data-tip": tip }, this.nodes);
      if (showPhases && phase) el("text", { class: "phase", x, y: y - 16 }, this.labels).textContent = phase;
    }

    const xs = diagram.nodes.map((n) => n.x * UNIT);
    const ys = diagram.nodes.map((n) => n.y * UNIT);
    const pad = UNIT;
    this.bounds = {
      x: Math.min(...xs) - pad,
      y: Math.min(...ys) - pad,
      w: Math.max(...xs) - Math.min(...xs) + 2 * pad,
      h: Math.max(...ys) - Math.min(...ys) + 2 * pad,
    };
    this.fit();
  }

  setWeb(web) {
    this.web.replaceChildren();
    this.svg.classList.toggle("has-web", Boolean(web && web.length));
    for (const [e, pauli] of web ?? []) {
      const [s, t] = this.endpoints.get(e);
      const a = this.points.get(s);
      const b = this.points.get(t);
      el("line", {
        class: `web-edge ${pauli}`, x1: a.x * UNIT, y1: a.y * UNIT, x2: b.x * UNIT, y2: b.y * UNIT,
        "data-tip": `Edge ${e} carries ${pauli}`,
      }, this.web);
    }
  }

  /** The whole drawing as a standalone SVG file. */
  toSVG() {
    const copy = this.svg.cloneNode(true);
    copy.querySelectorAll(".hit").forEach((n) => n.remove());
    copy.querySelectorAll("[data-tip]").forEach((n) => n.removeAttribute("data-tip"));
    const { x, y, w, h } = this.bounds;
    copy.setAttribute("xmlns", SVG_NS);
    copy.setAttribute("viewBox", `${x} ${y} ${w} ${h}`);
    copy.setAttribute("width", String(Math.round(w)));
    copy.setAttribute("height", String(Math.round(h)));
    const style = document.createElementNS(SVG_NS, "style");
    style.textContent = EXPORT_CSS;
    copy.prepend(style);
    return new XMLSerializer().serializeToString(copy);
  }

  fit() {
    this.box = { ...this.bounds };
    this.apply();
  }

  zoom(factor, cx = this.box.x + this.box.w / 2, cy = this.box.y + this.box.h / 2) {
    const w = Math.min(Math.max(this.box.w * factor, this.bounds.w / 40), this.bounds.w * 6);
    const k = w / this.box.w;
    this.box = { x: cx - (cx - this.box.x) * k, y: cy - (cy - this.box.y) * k, w, h: this.box.h * k };
    this.apply();
  }

  apply() {
    const { x, y, w, h } = this.box;
    this.svg.setAttribute("viewBox", `${x} ${y} ${w} ${h}`);
  }

  toDiagram(clientX, clientY) {
    return new DOMPoint(clientX, clientY).matrixTransform(this.svg.getScreenCTM().inverse());
  }

  bindPointer() {
    let drag = null;
    this.svg.addEventListener("pointerdown", (e) => {
      drag = { x: e.clientX, y: e.clientY, box: { ...this.box }, scale: 1 / this.svg.getScreenCTM().a };
      this.svg.setPointerCapture(e.pointerId);
      this.svg.classList.add("dragging");
    });
    this.svg.addEventListener("pointermove", (e) => {
      if (drag) {
        this.box = { ...drag.box, x: drag.box.x - (e.clientX - drag.x) * drag.scale, y: drag.box.y - (e.clientY - drag.y) * drag.scale };
        this.apply();
        return;
      }
      const tip = e.target.getAttribute?.("data-tip");
      if (!tip) return this.tip.classList.remove("show");
      const rect = this.wrap.getBoundingClientRect();
      this.tip.textContent = tip;
      this.tip.style.left = `${e.clientX - rect.left}px`;
      this.tip.style.top = `${e.clientY - rect.top}px`;
      this.tip.classList.add("show");
    });
    const end = () => {
      drag = null;
      this.svg.classList.remove("dragging");
    };
    this.svg.addEventListener("pointerup", end);
    this.svg.addEventListener("pointercancel", end);
    this.svg.addEventListener("pointerleave", () => this.tip.classList.remove("show"));
    this.svg.addEventListener("wheel", (e) => {
      if (!e.ctrlKey && !e.metaKey) return; // plain scrolling scrolls the page; pinch and Ctrl+scroll zoom
      e.preventDefault();
      const p = this.toDiagram(e.clientX, e.clientY);
      this.zoom(Math.exp(Math.max(-0.5, Math.min(0.5, e.deltaY * 0.01))), p.x, p.y);
    }, { passive: false });
  }
}
