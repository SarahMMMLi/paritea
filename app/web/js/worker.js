// The engine: a module web worker that runs Python (Pyodide) with paritea installed.
// It keeps heavy computation off the page's main thread. Messages in: {id, op, args}. Messages out:
// {type: "status" | "ready" | "failed"} while starting, then {type: "result", id, ok, result | error}.

import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

const site = new URL("../", import.meta.url);
let api = null;

function status(stage, message) {
  postMessage({ type: "status", stage, message });
}

async function start() {
  const started = performance.now();
  status("python", "Loading Python…");
  const pyodide = await loadPyodide({ packages: ["micropip", "numpy", "tqdm", "typing-extensions"] });

  status("install", "Installing paritea…");
  const manifest = await (await fetch(new URL("engine.json", site))).json();
  pyodide.globals.set("wheel_urls", manifest.wheels.map((name) => new URL(`wheels/${name}`, site).href));
  // deps=False: the wheels listed in engine.json are exactly what paritea needs here (no Jupyter, no numba).
  await pyodide.runPythonAsync("import micropip\nawait micropip.install(wheel_urls.to_py(), deps=False)");

  const bundle = await (await fetch(new URL("py/paritea_ui.zip", site))).arrayBuffer();
  pyodide.unpackArchive(bundle, "zip", { extractDir: "/home/pyodide/ui" });

  status("import", "Starting paritea…");
  await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, "/home/pyodide/ui")
from paritea_ui import compat
compat.install()
from paritea_ui import api
`);
  api = pyodide.globals.get("api");
  const info = JSON.parse(api.dispatch("info", "{}")).result;
  postMessage({ type: "ready", info: { ...info, seconds: (performance.now() - started) / 1000 } });
}

const ready = start().catch((err) => {
  postMessage({ type: "failed", message: String(err?.message ?? err) });
  throw err;
});

onmessage = async ({ data }) => {
  const { id, op, args } = data;
  try {
    await ready;
    const reply = JSON.parse(api.dispatch(op, JSON.stringify(args ?? {})));
    postMessage({ type: "result", id, ...reply });
  } catch (err) {
    postMessage({ type: "result", id, ok: false, error: { type: "EngineError", message: String(err?.message ?? err) } });
  }
};
