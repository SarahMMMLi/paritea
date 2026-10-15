// Python console: run any paritea code in the page's engine, like a notebook cell.

import { shelf } from "../shelf.js";
import { escapeHtml, formatSeconds, noticeHtml, pending, withBusyButton, withCancel } from "../ui.js";

const EXAMPLES = [
  {
    title: "Pauli webs of a surface code",
    code: `d = generate.surface_code_memory_experiment(distance=3, rounds=2)
stabilising, detecting = compute_pauli_webs(d)
len(stabilising), len(detecting)`,
  },
  {
    title: "Build a diagram by hand",
    code: `d = Diagram()
b0, b1 = d.add_node(NodeType.B, x=0, y=0), d.add_node(NodeType.B, x=3, y=0)
z1 = d.add_node(NodeType.Z, phase=Fraction(1, 2), x=1, y=0)
z2 = d.add_node(NodeType.Z, phase=Fraction(1, 2), x=2, y=0)
d.add_edges([(b0, z1), (z1, z2), (z2, b1)])
d.set_io(inputs=[b0], outputs=[b1], virtual=False)
put(d, "Two π/2 spiders from the console")  # now on your shelf for every tool`,
  },
  {
    title: "Fault equivalence of spider fusion",
    code: `def spiders(*phases):
    d = Diagram()
    nodes = [d.add_node(NodeType.B)] + [d.add_node(NodeType.Z, phase=p) for p in phases] + [d.add_node(NodeType.B)]
    d.add_edges(list(zip(nodes, nodes[1:])))
    d.set_io(inputs=[nodes[0]], outputs=[nodes[-1]], virtual=False)
    return d

two, one = spiders(Fraction(1, 2), Fraction(1, 2)), spiders(1)
is_fault_equivalence(NoiseModel.weighted_edge_flip_noise(two), NoiseModel.weighted_edge_flip_noise(one))`,
  },
  {
    title: "Push faults out of a noise model",
    code: `d = from_pyzx(generate.zweb(2, 2), positions=True)
noise = NoiseModel.weighted_edge_flip_noise(d)
pushed = push_out(noise, build_flip_operators(d))
detected = sum(len(v) for f, v in pushed.atomic_faults_with_values() if f.detector_flips)
print(noise.num_faults(), "faults, of which", detected, "are detected")`,
  },
  {
    title: "stim circuit → detector error model",
    code: `import stim
from paritea.glue.stim import export_to_stim_dem, from_stim, push_out_for_measurement_detectors

circuit = stim.Circuit.generated("surface_code:rotated_memory_z", distance=3, rounds=2,
                                 after_clifford_depolarization=0.001).flattened()
d, noise, measurements, observables, detectors = from_stim(circuit)
pushed, logicals, dets = push_out_for_measurement_detectors(
    noise, measurement_nodes=measurements, logicals=[observables[k] for k in sorted(observables)], detectors=detectors)
pushed.compress(lambda x, y: x * (1 - y) + (1 - x) * y)
dem = export_to_stim_dem(pushed, logical_regions=logicals, detector_regions=dets)
print(dem.num_detectors, "detector ids,", dem.num_errors, "error mechanisms")`,
  },
  {
    title: "Use a diagram from your shelf",
    code: `d = diagram("D1")  # a copy of D1, so changes here do not affect the tools
d.num_nodes(), d.num_edges(), d.io()`,
  },
];
const history = [];
const remembered = { code: EXAMPLES[0].code };

export async function renderConsole(ctx) {
  const live = ctx.engine.mode !== "precomputed";
  if (pending.code) {
    remembered.code = pending.code;
    pending.code = null;
  }
  ctx.app.innerHTML = `
    <nav class="crumbs"><a href="#/">Tools</a> / Python console</nav>
    <header class="tool-head">
      <h1>Python console</h1>
      <p class="lead">Run any paritea code in this page, like a notebook cell. paritea, pyzx, numpy and stim are
        ready to use, and so are the diagrams and noise models on your shelf.</p>
    </header>
    <div class="io-cards">
      <section class="io-card"><h2>You provide</h2>
        <ol><li><strong>Python code.</strong> Already imported: <code>Diagram</code>, <code>NodeType</code>,
          <code>Pauli</code>, <code>PauliString</code>, <code>NoiseModel</code>, <code>generate</code>,
          <code>compute_pauli_webs</code>, <code>build_flip_operators</code>, <code>push_out</code>,
          <code>is_semantic_equivalence</code>, <code>is_fault_equivalence</code>, <code>from_pyzx</code>,
          <code>Fraction</code>, <code>np</code>, <code>zx</code>.</li></ol></section>
      <section class="io-card"><h2>You get</h2>
        <ul><li>What the code prints, and the value of its last line</li>
          <li>Your shelf: <code>diagram("D1")</code> and <code>noise_model("N1")</code> give copies;
            <code>put(d, "name")</code> adds a diagram for the tools</li>
          <li>Variables that persist between runs, until you reset</li></ul></section>
    </div>
    ${live ? "" : noticeHtml("The console needs the in-browser engine, which isn't running here (preview mode).")}
    <div class="panel console-panel">
      <div class="console-bar">
        <label class="param inline">Example
          <select id="console-example"><option value="">Choose an example…</option>${EXAMPLES.map(
            (e, i) => `<option value="${i}">${escapeHtml(e.title)}</option>`,
          ).join("")}</select></label>
        <span class="hint">Shelf: ${shelf.size ? [...shelf.entries.keys(), ...shelf.noise.keys()].join(", ") : "empty"}</span>
      </div>
      <textarea id="console-code" rows="12" spellcheck="false" aria-label="Python code">${escapeHtml(remembered.code)}</textarea>
      <div class="actions">
        <button class="btn btn-primary" id="console-run" type="button">Run</button>
        <button class="btn btn-ghost" id="console-cancel" type="button" hidden>Cancel</button>
        <button class="btn btn-ghost" id="console-reset" type="button">Reset variables</button>
        <span class="hint"><kbd>Ctrl</kbd> + <kbd>Enter</kbd> runs · <kbd>Tab</kbd> indents</span>
      </div>
    </div>
    <section class="results console-output" id="console-output" aria-live="polite"></section>`;

  const editor = document.getElementById("console-code");
  editor.addEventListener("input", () => (remembered.code = editor.value));
  editor.addEventListener("keydown", (e) => {
    if (e.key === "Tab" && !e.shiftKey) {
      e.preventDefault();
      editor.setRangeText("    ", editor.selectionStart, editor.selectionEnd, "end");
      remembered.code = editor.value;
    } else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      run(ctx);
    }
  });
  document.getElementById("console-example").addEventListener("change", (e) => {
    if (e.target.value === "") return;
    editor.value = remembered.code = EXAMPLES[Number(e.target.value)].code;
    e.target.value = "";
    editor.focus();
  });
  document.getElementById("console-run").addEventListener("click", () => run(ctx));
  document.getElementById("console-reset").addEventListener("click", async () => {
    await ctx.engine.run("console_reset");
    history.unshift({ code: "# Variables reset", stdout: "", result: null, error: null, seconds: 0 });
    renderHistory();
  });
  renderHistory();
}

async function run(ctx) {
  const code = document.getElementById("console-code").value;
  if (!code.trim()) return;
  const controls = { cancel: document.getElementById("console-cancel") };
  await withBusyButton(document.getElementById("console-run"), "Running…", async () => {
    ctx.setBusy(true);
    try {
      const result = await withCancel(ctx, controls, () => ctx.engine.run("console_run", { code }));
      result.shelf.forEach((entry) => shelf.add(entry));
      history.unshift({ code, ...result });
    } catch (err) {
      const message = err.type === "Cancelled"
        ? "Cancelled. The engine restarted: variables and the shelf are empty again."
        : err.message;
      history.unshift({ code, stdout: "", result: null, error: message, seconds: 0 });
    } finally {
      ctx.setBusy(false);
    }
  });
  window.lastConsole = history[0]; // for the browser check in app/build/check_site.py
  renderHistory();
}

function renderHistory() {
  const box = document.getElementById("console-output");
  if (!box) return;
  box.innerHTML = history.length
    ? history
        .map(
          (h) => `<article class="cell">
            <pre class="cell-code"><code>${escapeHtml(h.code)}</code></pre>
            ${h.stdout ? `<pre class="cell-out">${escapeHtml(h.stdout)}</pre>` : ""}
            ${h.result !== null && h.result !== undefined ? `<pre class="cell-result">${escapeHtml(h.result)}</pre>` : ""}
            ${h.error ? `<pre class="cell-error">${escapeHtml(h.error)}</pre>` : ""}
            ${h.seconds ? `<p class="cell-time">${formatSeconds(h.seconds)}</p>` : ""}
          </article>`,
        )
        .join("")
    : `<div class="empty">Output appears here. Pick an example above, or write your own code and press Run.</div>`;
}
