# CLAUDE.md — paritea UI

A Streamlit app on top of the paritea library in `../src/paritea`. Read `../CLAUDE.md` first: UI work stays inside
`app/`, and upstream-owned files outside it are not edited.

## Commands (run from `app/`)

```shell
uv sync                                   # create app/.venv; builds paritea (Rust) from .. in editable mode
uv run streamlit run streamlit_app.py     # http://localhost:8501, reloads on save
uv run pytest                             # unit tests + headless app tests (~15 s)
uv run ruff check --fix . && uv run ruff format .
```

A `VIRTUAL_ENV ... does not match` warning from uv just means another venv is active in the shell; uv still uses
`app/.venv`. Before finishing a change, run pytest and ruff and make sure both pass.

## Structure

| Path | Role |
|---|---|
| `streamlit_app.py` | Entry point: page config and `st.navigation`. **Register every new page here.** |
| `paritea_ui/core.py` | paritea logic with **no Streamlit import**: the `GENERATORS` registry, `PauliWebs`, summaries. Unit tested. |
| `paritea_ui/drawing.py` | `draw_diagram(d, *, web=None, show_phases=False) -> matplotlib Figure` |
| `paritea_ui/components.py` | Shared Streamlit pieces: `report_errors`, `diagram_picker`, cached computations |
| `paritea_ui/pages/*.py` | One script per page, run top to bottom by Streamlit |
| `tests/test_core.py` | Tests for `core.py` and `drawing.py` |
| `tests/test_app.py` | `streamlit.testing.v1.AppTest` smoke tests that run real pages |

## Conventions

- **Logic in `core.py`, layout in pages.** Anything that calls paritea and does not need Streamlit goes in `core.py`
  (or a new Streamlit-free module) with a unit test. Pages only gather input, call helpers and display results.
- **Wrap every paritea call in a page with `with report_errors("<what was attempted>"):`.** It shows the error and
  stops the run, and it also catches Rust panics, which `except Exception` does not.
- **Cache with `st.cache_data`, keyed by a hashable spec** (e.g. `DiagramSpec`), never by a `Diagram` object.
  `cache_data` gives each caller a pickled copy, so mutating a result is safe.
- **Cache a diagram together with everything computed from it** (see `PauliWebs`). Webs, noise models and faults
  refer to edge indices, and rebuilding a diagram can renumber edges (`shor_extraction` does so on every call).
- **New diagram source** → add an entry to `GENERATORS` in `core.py`; the picker and tests pick it up automatically.
  The builder must return a diagram with real IO and node positions.
- **New page** → add `paritea_ui/pages/<name>.py`, register it in `streamlit_app.py`, link it from `home.py`, and add an
  `AppTest` in `tests/test_app.py` (switch to the page, interact, assert `not at.exception` and `not at.error`).
- Draw with `matplotlib.figure.Figure()` (as `drawing.py` does), not `pyplot`, and show it with `st.pyplot(fig)`.
- Style: ruff with the library's rules (`../ruff.toml`, line length 120). Keyword-only boolean parameters (`FBT`).

## Web page (`web/`): paritea in the browser

`web/` is a static page that runs paritea client-side: Pyodide 314.0.7 (Python on WebAssembly) in a module web worker,
with paritea's Rust extension compiled to WebAssembly. `.github/workflows/app-pages.yml` builds, checks and publishes it
to https://sarahmmmli.github.io/paritea/ on every push to `main`.

```shell
./build/build_wheels.sh                        # browser wheels -> web/wheels/ (toolchains cached in ~/.cache/paritea-web)
uv run python build/precompute.py              # native reference results -> web/data/ (preview mode, browser check)
uv run python build/build_site.py              # web/py/paritea_ui.zip + web/engine.json; rerun after editing paritea_ui
python3 -m http.server 8000 --directory web    # http://localhost:8000
```

| Path | Role |
|---|---|
| `web/js/worker.js` | The engine: loads Pyodide, installs `web/wheels` with `deps=False`, calls `paritea_ui.api.dispatch` |
| `web/js/engine.js` | Worker client; falls back to `web/data` (preview mode) if the engine cannot start, or with `?engine=precomputed` |
| `web/js/main.js`, `web/js/diagram-view.js`, `web/css/app.css` | Tool catalogue, Pauli webs tool, SVG diagram view, design tokens |
| `paritea_ui/api.py` | JSON-in/JSON-out operations the page calls; register new ones in `OPS` |
| `paritea_ui/compat/` | Stand-ins for galois (`GF2`), recordclass and an `mpl_toolkits` import; used only when the real package is absent |
| `build/check_site.py` | Headless-browser check that in-browser results match the native ones (needs Playwright) |

- `build_wheels.sh` builds paritea from a scratch copy of the repository, so no upstream file is modified.
- Never build the browser wheel with the `release-py` profile: `panic = "abort"` turns any Rust panic into a dead engine.
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

- **Rust panics** surface as `pyo3_runtime.PanicException`, a `BaseException`. Causes: IO unset or virtual (a fresh
  `Diagram()` has virtual IO, so call `set_io(..., virtual=False)` or `infer_io_from_boundaries()`), parallel edges,
  H nodes without exactly two neighbours, non-Clifford or negative phases, and `is_fault_equivalence(..., until=0)`.
- **Long Rust calls hold the GIL**: they freeze the whole server for every user and cannot be cancelled. Bound inputs
  (`max_value` on widgets, `until` for fault equivalence) and put slow work behind a button. If that is not enough, run
  it in a subprocess (`concurrent.futures.ProcessPoolExecutor`; diagrams pickle).
- **Keep `quiet=True`** for `is_fault_equivalence`: otherwise Rust prints progress bars to the server's stdout.
- **`paritea.draw` only works in Jupyter.** Use `paritea_ui.drawing.draw_diagram`.
- **Mutating functions**: `Diagram.io_sorted()` (called inside both equivalence checks) may set IO, `NoiseModel.compress`
  works in place, and `push_out` requires the *same* diagram object that `build_flip_operators` saw.
- `weighted_edge_flip_noise` turns a weight of 0 into 1; exclude edges with `idealised_edges` instead.
  `NoiseModelBuilder` cost tuples are ordered **(X, Z, Y)**.
- `from_pyzx` defaults: Hadamard edges raise (`convert_had_edges=True` converts them) and positions are dropped
  (`positions=True` keeps them). `to_diagram`/`to_noise_model` use those defaults and discard stim's noise.
- `export_to_stim_dem` numbers detectors after the logicals, so its detector ids differ from stim's.
- The Rust extension is built unoptimised (`profile = "dev-py"` upstream). Fine for now; a release build would make
  heavy computations faster.
