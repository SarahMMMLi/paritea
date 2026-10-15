# CLAUDE.md — paritea UI

A static web page that runs paritea in the browser (`web/`), and the Python it runs (`paritea_ui/`). Read
`../CLAUDE.md` first: UI work stays inside `app/`, and upstream-owned files outside it are not edited.

The page runs paritea client-side: Pyodide 314.0.7 (Python on WebAssembly) in a module web worker, with paritea's Rust
extension compiled to WebAssembly. `.github/workflows/app-pages.yml` builds, checks and publishes it to
https://sarahmmmli.github.io/paritea/ on every push to `main`.

## Commands (run from `app/`)

```shell
uv sync                                        # create app/.venv; builds paritea (Rust) from .. in editable mode
uv run pytest                                  # the Python the page runs, tested natively (a few seconds)
uv run ruff check --fix . && uv run ruff format .

./build/build_wheels.sh                        # browser wheels -> web/wheels/ (toolchains cached in ~/.cache/paritea-web)
uv run python build/precompute.py              # native reference results -> web/data/ (preview mode, browser check)
uv run python build/build_site.py              # web/py/paritea_ui.zip + web/engine.json; rerun after editing paritea_ui
python3 -m http.server 8000 --directory web    # http://localhost:8000
uv run --with playwright python -m playwright install chromium            # once, for the browser check
uv run --with playwright python build/check_site.py http://localhost:8000/ build/screenshots
```

In VS Code, **Run → paritea web page** repackages `paritea_ui` and serves the page (`../.vscode/launch.json`).

A `VIRTUAL_ENV ... does not match` warning from uv just means another venv is active in the shell; uv still uses
`app/.venv`. Before finishing a change, run pytest and ruff and make sure both pass; after changing the page or
anything it calls, also run the browser check.

## Structure

| Path | Role |
|---|---|
| `web/index.html`, `web/css/app.css` | Page shell and styles (design tokens first, light and dark) |
| `web/js/worker.js` | The engine: loads Pyodide, installs `web/wheels` with `deps=False`, calls `paritea_ui.api.dispatch` |
| `web/js/engine.js` | Worker client; falls back to `web/data` (preview mode) if the engine cannot start, or with `?engine=precomputed` |
| `web/js/main.js` | Boot, engine status pill and hash routing (`#/`, `#/diagrams`, `#/webs?generator=z-web-grid&qubits=3`) |
| `web/js/tools/*.js` | One module per page: `home.js` (tool catalogue), `console.js`, `dem.js`, `diagrams.js`, `fault.js`, `noise.js`, `propagation.js`, `semantic.js`, `webs.js` |
| `web/js/ui.js`, `web/js/shelf.js`, `web/js/diagram-view.js` | Shared result blocks, the page's copy of the shelf, SVG drawing |
| `paritea_ui/api.py` | JSON-in/JSON-out operations the page calls; register new ones in `OPS` |
| `paritea_ui/session.py` | The shelf: every diagram (`D1`, ...) and noise model (`N1`, ...) made in the session; tools work on these objects |
| `paritea_ui/core.py` | The `GENERATORS` registry of diagram generators |
| `paritea_ui/layout.py` | Node positions for drawing (`node_positions`), filling gaps left by imports and generators |
| `paritea_ui/validate.py` | Plain-word checks run before anything reaches Rust (panics become `UserError` messages) |
| `paritea_ui/examples.py`, `codegen.py` | Ready-made diagrams with their known answers; the Python shown under every result |
| `paritea_ui/console.py` | The Python console's namespace and runner |
| `paritea_ui/compat/` | Stand-ins for galois (`GF2`), recordclass, an `mpl_toolkits` import, stim/sinter imports and `scipy.stats`; used only when the real package is absent |
| `build/` | `build_wheels.sh` (+ `patches/`), `precompute.py`, `build_site.py`, `check_site.py` (headless-browser check that in-browser results match the native ones) |
| `tests/` | `test_api.py` (every operation, with known answers), `test_core.py` (generators, layout), `test_compat.py` (stand-ins vs the real galois) |

## Conventions

- **Logic in `paritea_ui`, presentation in `web/js`.** Anything that calls paritea is an operation in `api.py` with a
  test in `tests/test_api.py`; the tool pages gather input, call `ctx.engine.run(op, args)` and show the result.
- **New tool page** → a module in `web/js/tools/`, a route in `web/js/main.js`, `live: true` in the catalogue
  (`tools/home.js`), its operations in `paritea_ui/api.py` with tests in `tests/test_api.py`, and a flow in
  `build/check_site.py`.
- **Check before Rust.** Run `validate.require_valid` (or a check of your own that raises `UserError`) before calling
  paritea, so mistakes come back as plain-word messages instead of panics.
- **Keep a diagram together with everything computed from it.** Webs, noise models and faults refer to edge indices,
  and rebuilding a diagram can renumber its edges (`shor_extraction` does so on every call). Results refer to shelf
  entries by id, never to a rebuilt diagram.
- **New diagram source** → an entry in `GENERATORS` in `core.py` and the Python that builds it in
  `codegen._GENERATOR_CODE`; the Diagrams page and the tests pick it up automatically. The builder must return a
  diagram with real IO and node positions.
- **Examples need a known answer**, asserted by `tests/test_api.py` and shown on the page.
- **Links recreate results.** A link can name a generator and its parameters
  (`#/webs?generator=z-web-grid&qubits=3&depth=3`, slugs from `ui.slug`), an example (`?example=steane-state`) or the
  stim preset (`#/dem?distance=3&rounds=2&p=0.001`); the page runs it on arrival. After a run, `ui.setLink` puts the
  link that recreates the shown result in the address bar, with **Copy link** beside the result. Shelf ids
  (`?diagram=D3`) only mean something inside the tab that made them. Anything read from a link is untrusted: convert or
  escape it before it reaches HTML.
- **Symbols never touch.** Every drawing on the page takes node positions from `layout.node_positions`, which spreads
  nodes at least `MIN_SPACING` apart without bending wires. New views, generators and labels must keep a visible gap
  between symbols too; a test checks every generator.
- Every result shows the Python that reproduces it (`codegen.py`).
- Style: ruff with the library's rules (`../ruff.toml`, line length 120). Keyword-only boolean parameters (`FBT`).
  JavaScript: plain ES modules, no bundler or framework.

## Building for the browser

- `build_wheels.sh` builds paritea from a scratch copy of the repository and applies `build/patches/*.patch` to it, so
  no upstream file is modified. When upstream merges a patch, the script reports it as already applied: delete it.
- Never build the browser wheel with the `release-py` profile: `panic = "abort"` turns any Rust panic into a dead engine.
- stim is compiled for the browser too (`build/patches/stim/`); CI caches the wheel, keyed by the patches and the script.
- Generated files (`web/wheels`, `web/py`, `web/data`, `web/engine.json`) are gitignored and rebuilt by CI.

## paritea API cheat sheet

Imports: `from paritea import Pauli, PauliString, build_flip_operators, push_out`, `from paritea.diagram import
Diagram, NodeType`, `from paritea.noise import Fault, NoiseModel`, `from paritea.web import compute_pauli_webs`,
`from paritea.equivalence import is_fault_equivalence, is_semantic_equivalence`, `from paritea.glue.pyzx import
from_pyzx, to_pyzx`, `from paritea.glue.stim import from_stim, push_out_for_measurement_detectors, export_to_stim_dem,
wrap_dem_as_sinter_task`, `from paritea import generate`.

- **Diagram**: `add_node(NodeType.Z|X|H|B, phase=Fraction, x=, y=) -> int`, `add_edge(a, b) -> int`, `add_edges(...)`,
  `set_io(inputs, outputs, virtual=False)`, `infer_io_from_boundaries()`, `io()`, `node_indices()`, `edge_list()`,
  `get_edge_endpoints_by_index(e)`, `type(n)`, `phase(n)`, `x(n)`/`y(n)` (-1 when unset), `num_nodes()`, `num_edges()`.
- **PauliString**: immutable `{edge index: Pauli}`; webs and fault flips use this type. `Pauli` is `I`, `X`, `Y`, `Z`.
- **Webs**: `compute_pauli_webs(d) -> (stabilising webs, detecting regions)`, keyed by `d`'s edge indices. Fast
  (well under a second for a distance-7, 5-round surface code). `paritea.web.partitions.pauli_webs_through_partitions(d,
  partitions=...)` is the accelerated path for big diagrams.
- **Generators** (`paritea.generate`): `surface_code_memory_experiment(distance=, rounds=)`,
  `shor_extraction(stabilisers, qubits=, repeat=)` with `steane_code_stabilisers()` or
  `rotated_planar_surface_code_stabilisers(L)`, `zweb(qubits, depth)` and `clifford(qubits, spiders)` (both return pyzx
  graphs: wrap in `from_pyzx(g, positions=True)`; `clifford` uses the global `random`), `CircuitBuilder` for circuits
  with a noise model.
- **Noise**: `NoiseModel.weighted_edge_flip_noise(d, w_x=, w_y=, w_z=, idealised_edges=[...]) -> NoiseModel[int]`.
- **Fault equivalence**: `is_fault_equivalence(nm1, nm2, until=None, quiet=True) -> bool`. Accepts noise models,
  diagrams or pyzx graphs (the latter two get unit weights). Checks fault weights `1 .. until-1`.
  **Expensive** (enumerates fault combinations; cost grows quickly with `until` and diagram size).
- **Semantic equivalence**: `is_semantic_equivalence(d1, d2) -> bool` (pass `Diagram`s).
- **stim**: `from_stim(circuit.flattened()) -> (diagram, noise model with probabilities, measurement nodes,
  observables, detectors)`; supports H, CX, R/RZ, M/MZ/MR/MRZ, X/Y/Z_ERROR, DEPOLARIZE1/2, DETECTOR,
  OBSERVABLE_INCLUDE. Then `push_out_for_measurement_detectors(...)`, `nm.compress(...)`, `export_to_stim_dem(...)`.
  See `../demo/stim_replication.ipynb` for the full pipeline.

Worked examples: `../demo/*.ipynb`, `../tests/**`, `../benchmarks/`.

## Gotchas

- **Rust panics** surface as `pyo3_runtime.PanicException`, a `BaseException`, so `except Exception` does not catch
  them (`core.is_rust_panic` recognises them). Causes: IO unset or virtual (a fresh `Diagram()` has virtual IO, so call
  `set_io(..., virtual=False)` or `infer_io_from_boundaries()`), parallel edges, H nodes without exactly two neighbours,
  non-Clifford or negative phases, and `is_fault_equivalence(..., until=0)`.
- **Long Rust calls cannot be interrupted.** They block the engine's worker (not the page) until they finish; Cancel
  restarts the worker (`engine.restart()`), which empties the shelf. Bound inputs (number limits, the fault weight) and
  offer Cancel on tools that can be slow.
- **Keep `quiet=True`** for `is_fault_equivalence`: its progress bar needs a thread, which the browser engine lacks.
- **`paritea.draw` only works in Jupyter.** The page draws diagrams itself (`web/js/diagram-view.js`).
- **Mutating functions**: `Diagram.io_sorted()` (called inside both equivalence checks) may set IO, `NoiseModel.compress`
  works in place, and `push_out` requires the *same* diagram object that `build_flip_operators` saw.
- `weighted_edge_flip_noise` turns a weight of 0 into 1; exclude edges with `idealised_edges` instead.
  `NoiseModelBuilder` cost tuples are ordered **(X, Z, Y)**.
- `from_pyzx` defaults: Hadamard edges raise (`convert_had_edges=True` converts them) and positions are dropped
  (`positions=True` keeps them). `to_diagram`/`to_noise_model` use those defaults and discard stim's noise.
- `export_to_stim_dem` numbers detectors after the logicals, so its detector ids differ from stim's.
- Natively, the Rust extension is built unoptimised (`profile = "dev-py"` upstream), so heavy computations run slower
  in the tests than on the page, whose wheel uses the optimised `release` profile.
