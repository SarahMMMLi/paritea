// Talks to the engine worker. If the engine cannot start (offline, old browser, or ?engine=precomputed in the URL),
// it falls back to results that were computed natively ahead of time, so the page always has something to show.

const START_TIMEOUT_MS = 180_000;

export function resultKey(generator, params) {
  return `${generator}|${Object.keys(params).sort().map((k) => `${k}=${params[k]}`).join(",")}`;
}

export class Engine extends EventTarget {
  constructor() {
    super();
    this.mode = "starting"; // "starting" | "live" | "precomputed"
    this.info = null;
    this.pending = new Map();
    this.nextId = 1;
    this.whenSettled = new Promise((resolve) => (this.settle = resolve));
    this.catalogue = fetch("data/index.json").then((r) => r.json());

    if (new URLSearchParams(location.search).get("engine") === "precomputed") {
      // Deferred so that the page has subscribed to status events before this one fires.
      queueMicrotask(() => this.useFallback("Precomputed mode was requested in the page address."));
      return;
    }
    this.startWorker();
  }

  startWorker() {
    this.worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
    this.worker.onmessage = ({ data }) => this.onMessage(data);
    this.worker.onerror = (event) => this.useFallback(`The in-browser engine failed to start (${event.message || "unknown error"}).`);
    this.timer = setTimeout(() => this.useFallback("The in-browser engine took too long to start."), START_TIMEOUT_MS);
  }

  /**
   * Stops whatever the engine is doing (the only way to interrupt paritea's Rust code) and starts a fresh one.
   * Everything the engine held, such as the shelf, is lost; pending requests fail with type "Cancelled".
   */
  restart(reason = "Cancelled.") {
    if (this.mode === "precomputed") return;
    clearTimeout(this.timer);
    this.worker?.terminate();
    for (const request of this.pending.values()) request.reject(Object.assign(new Error(reason), { type: "Cancelled" }));
    this.pending.clear();
    this.mode = "starting";
    this.info = null;
    this.whenSettled = new Promise((resolve) => (this.settle = resolve));
    this.dispatchEvent(new CustomEvent("restart", { detail: { reason } }));
    this.emit("python", "Restarting the engine…");
    this.startWorker();
  }

  emit(stage, message) {
    this.dispatchEvent(new CustomEvent("status", { detail: { stage, message, mode: this.mode, info: this.info } }));
  }

  onMessage(msg) {
    if (msg.type === "status") {
      this.emit(msg.stage, msg.message);
    } else if (msg.type === "ready") {
      clearTimeout(this.timer);
      this.mode = "live";
      this.info = msg.info;
      this.emit("ready", `Ready · Python ${msg.info.python} in your browser`);
      this.settle();
    } else if (msg.type === "failed") {
      this.useFallback(`The in-browser engine failed to start: ${msg.message}`);
    } else if (msg.type === "result") {
      const request = this.pending.get(msg.id);
      this.pending.delete(msg.id);
      if (!request) return;
      if (msg.ok) request.resolve(msg.result);
      else request.reject(Object.assign(new Error(msg.error.message), msg.error));
    }
  }

  useFallback(reason) {
    if (this.mode === "precomputed") return;
    clearTimeout(this.timer);
    this.worker?.terminate();
    this.mode = "precomputed";
    this.reason = reason;
    for (const request of this.pending.values()) request.reject(new Error(reason));
    this.pending.clear();
    this.emit("preview", "Preview · precomputed results");
    this.settle();
  }

  async run(op, args = {}) {
    await this.whenSettled;
    if (this.mode === "live") {
      const id = this.nextId++;
      return new Promise((resolve, reject) => {
        this.pending.set(id, { resolve, reject });
        this.worker.postMessage({ id, op, args });
      });
    }
    if (op !== "pauli_webs") throw new Error(`"${op}" is not available in preview mode.`);
    const catalogue = await this.catalogue;
    const file = catalogue.results[resultKey(args.generator, args.params)];
    if (!file) {
      const error = new Error("This combination was not computed ahead of time, and the in-browser engine is not running.");
      error.type = "PreviewOnly";
      throw error;
    }
    return { ...(await (await fetch(`data/${file}`)).json()), precomputed: true };
  }
}
