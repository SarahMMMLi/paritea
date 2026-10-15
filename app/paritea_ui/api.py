"""JSON-in, JSON-out operations behind the web page.

The browser engine (Pyodide in a web worker) calls ``dispatch(op, args_json)`` and gets a JSON string back. The same
functions run natively, which is how their results are tested and precomputed.
"""

import json
import math
import sys
import time
import traceback
from collections import Counter
from collections.abc import Callable
from typing import Any

import numpy as np
import pyzx as zx
from paritea import PauliString, build_flip_operators, push_out
from paritea.diagram import Diagram
from paritea.glue.pyzx import from_pyzx, to_pyzx
from paritea.noise import NoiseModel
from paritea.web import compute_pauli_webs, compute_stabilisers, row_reduce_webs

from paritea_ui import codegen
from paritea_ui.core import GENERATORS, build_diagram, is_rust_panic
from paritea_ui.examples import EXAMPLES
from paritea_ui.layout import UNSET, node_positions, place_unpositioned
from paritea_ui.session import SHELF, Entry, NoiseEntry
from paritea_ui.validate import UserError, diagram_problems, require_valid

MAX_IMPORT_CHARS = 5_000_000
MAX_WEIGHT = 100


def info() -> dict[str, str]:
    """Where the engine runs, e.g. Python 3.14.2 on emscripten inside a browser."""
    return {"python": sys.version.split()[0], "platform": sys.platform}


def generators() -> list[dict[str, Any]]:
    """The diagram generators and their integer parameters, for building input forms."""
    return [
        {
            "name": name,
            "description": generator.description,
            "params": [
                {
                    "key": key,
                    "label": p.label,
                    "default": p.default,
                    "min": p.min_value,
                    "max": p.max_value,
                    "step": p.step,
                    "help": p.help,
                }
                for key, p in generator.params.items()
            ],
        }
        for name, generator in GENERATORS.items()
    ]


def examples() -> list[dict[str, Any]]:
    """The ready-made diagrams and the numbers of webs paritea finds in them."""
    return [
        {
            "id": key,
            "title": e.title,
            "description": e.description,
            "stabilising_webs": e.stabilising_webs,
            "detecting_regions": e.detecting_regions,
        }
        for key, e in EXAMPLES.items()
    ]


# ---------------------------------------------------------------- Serialisation


def summary(d: Diagram) -> dict[str, int]:
    """Headline numbers describing a diagram."""
    try:
        inputs, outputs = d.io()
    except ValueError:
        inputs, outputs = [], []
    types = Counter(str(d.type(n)) for n in d.node_indices())
    return {
        "Nodes": d.num_nodes(),
        "Edges": d.num_edges(),
        "Inputs": len(inputs),
        "Outputs": len(outputs),
        "Z spiders": types["Z"],
        "X spiders": types["X"],
        "H boxes": types["H"],
    }


def diagram_json(d: Diagram) -> dict[str, Any]:
    """Everything needed to draw a diagram: typed nodes with positions and phases, edges as [index, source, target]."""
    positions = node_positions(d)
    try:
        inputs, outputs = d.io()
    except ValueError:
        inputs, outputs = [], []
    return {
        "nodes": [
            {
                "id": n,
                "type": str(d.type(n)),
                "phase": str(d.phase(n)),
                "x": round(positions[n][0], 3),
                "y": round(positions[n][1], 3),
            }
            for n in d.node_indices()
        ],
        "edges": [[e, *d.get_edge_endpoints_by_index(e)] for e in d.edge_indices()],
        "inputs": list(inputs),
        "outputs": list(outputs),
    }


def web_json(web: PauliString) -> list[tuple[int, str]]:
    """A web as sorted [edge index, Pauli] pairs."""
    return [(edge, str(pauli)) for edge, pauli in sorted(web.items())]


def entry_json(entry: Entry) -> dict[str, Any]:
    """A shelf entry for the page: its drawing, summary, problems and the Python that rebuilds it."""
    return {
        "id": entry.id,
        "name": entry.name,
        "source": entry.source,
        "summary": summary(entry.diagram),
        "problems": diagram_problems(entry.diagram),
        "notes": entry.notes,
        "code": entry.code,
        "diagram": diagram_json(entry.diagram),
    }


# ---------------------------------------------------------------- Diagrams


def _check_params(generator: str, params: dict[str, int]) -> None:
    if generator not in GENERATORS:
        raise UserError(f"Unknown diagram generator: {generator}.")
    for key, p in GENERATORS[generator].params.items():
        value = params.get(key)
        if not isinstance(value, int) or not p.min_value <= value <= p.max_value:
            raise UserError(f"{p.label} must be a whole number from {p.min_value} to {p.max_value}.")
        if (value - p.min_value) % p.step:
            raise UserError(f"{p.label} must be one of {list(range(p.min_value, p.max_value + 1, p.step))}.")


def _short_name(generator: str, params: dict[str, int]) -> str:
    values = ", ".join(f"{GENERATORS[generator].params[k].label.split()[0].lower()} {v}" for k, v in params.items())
    return f"{generator} ({values})"


def diagram_generate(generator: str, params: dict[str, int]) -> dict[str, Any]:
    """Build a diagram with a generator and put it on the shelf (the same recipe twice gives the same entry)."""
    _check_params(generator, params)
    key = "generate|" + generator + "|" + json.dumps(params, sort_keys=True)
    entry = SHELF.find(key)
    if entry is None:
        d = place_unpositioned(build_diagram(generator, **params))
        entry = SHELF.add(
            d,
            name=_short_name(generator, params),
            source={"kind": "generator", "generator": generator, "params": params},
            code=codegen.generator_code(generator, params),
            key=key,
        )
    return entry_json(entry)


def diagram_example(example: str) -> dict[str, Any]:
    """Put one of the ready-made diagrams on the shelf."""
    if example not in EXAMPLES:
        raise UserError(f"Unknown example: {example}.")
    key = "example|" + example
    entry = SHELF.find(key)
    if entry is None:
        e = EXAMPLES[example]
        entry = SHELF.add(
            place_unpositioned(e.build()),
            name=e.title,
            source={"kind": "example", "example": example},
            code=codegen.example_code(example),
            key=key,
        )
    return entry_json(entry)


def _detect_format(text: str, filename: str) -> str:
    name = filename.lower()
    if name.endswith((".json", ".zxg", ".qgraph")):
        return "pyzx"
    if name.endswith(".qasm"):
        return "qasm"
    start = text.lstrip()[:300]
    if start.startswith("{"):
        return "pyzx"
    if "OPENQASM" in start.upper():
        return "qasm"
    raise UserError("Couldn't tell the file's format. Choose PyZX JSON or OpenQASM 2 under Format.")


def _read_graph(text: str, fmt: str) -> zx.graph.base.BaseGraph:
    try:
        if fmt == "pyzx":
            return zx.Graph.from_json(text)
        return zx.Circuit.from_qasm(text).to_graph()
    except Exception as exc:
        kind = "PyZX JSON" if fmt == "pyzx" else "OpenQASM 2"
        raise UserError(f"This doesn't read as {kind}: {exc}") from exc


def _from_pyzx(graph: zx.graph.base.BaseGraph, *, convert_hadamard: bool, keep_positions: bool) -> Diagram:
    try:
        return from_pyzx(graph, convert_had_edges=convert_hadamard, positions=keep_positions)
    except ValueError as exc:
        message = str(exc)
        if "phase" in message:
            message += ". paritea supports Clifford diagrams only: phases must be multiples of π/2."
        elif "HADAMARD" in message:
            message = "the file has Hadamard edges; tick 'Convert Hadamard edges to H boxes'."
        else:
            message += ". Try setting 'Inputs and outputs' to 'Every boundary is an output'."
        raise UserError(f"paritea can't read this diagram: {message}") from exc


def diagram_import(
    text: str,
    filename: str = "",
    fmt: str = "auto",
    *,
    convert_hadamard: bool = True,
    keep_positions: bool = True,
    io: str = "file",
) -> dict[str, Any]:
    """Read a PyZX/ZXLive JSON file or an OpenQASM 2 circuit and put the diagram on the shelf.

    ``io`` says where inputs and outputs come from: ``file`` (the file's lists; all boundaries become outputs if it has
    none), ``detect`` (from positions: a boundary left of its neighbour is an input) or ``outputs`` (every boundary).
    """
    if not text.strip():
        raise UserError("The file is empty.")
    if len(text) > MAX_IMPORT_CHARS:
        raise UserError("The file is larger than 5 MB.")
    fmt = _detect_format(text, filename) if fmt == "auto" else fmt
    graph = _read_graph(text, fmt)
    notes = []
    if io == "detect":
        try:
            graph.auto_detect_io()
        except TypeError as exc:
            raise UserError(f"Couldn't tell inputs from outputs by position: {exc}") from exc
    elif io == "outputs" or not (graph.inputs() or graph.outputs()):
        graph.set_inputs(())
        graph.set_outputs(())
        notes.append("Every boundary is treated as an output, in the order of their vertex numbers.")
    d = _from_pyzx(graph, convert_hadamard=convert_hadamard, keep_positions=keep_positions)
    for n in d.node_indices():  # unusable coordinates (e.g. NaN) mean "no position"
        if not (math.isfinite(d.x(n)) and math.isfinite(d.y(n))):
            d.set_x(n, UNSET).set_y(n, UNSET)
    place_unpositioned(d)
    inputs, outputs = d.io()
    filename = filename or ("pasted.json" if fmt == "pyzx" else "pasted.qasm")
    entry = SHELF.add(
        d,
        name=filename,
        source={"kind": "import", "format": fmt, "filename": filename},
        code=codegen.import_code(
            filename=filename,
            fmt=fmt,
            convert_hadamard=convert_hadamard,
            keep_positions=keep_positions,
            io=io,
            inputs=list(inputs),
            outputs=list(outputs),
        ),
        notes=notes,
    )
    return entry_json(entry)


def diagram_get(diagram: str) -> dict[str, Any]:
    return entry_json(SHELF.get(diagram))


def diagram_remove(diagram: str) -> dict[str, Any]:
    """Remove a diagram from the shelf, together with its noise models."""
    return {"removed": diagram, "noise": SHELF.remove(diagram)}


def diagram_export(diagram: str, fmt: str) -> dict[str, str]:
    """The diagram as a PyZX JSON file (opens in ZXLive) or as TikZ."""
    entry = SHELF.get(diagram)
    d = entry.diagram
    g, mapping = to_pyzx(d, with_mapping=True)
    inputs, outputs = d.io()
    g.set_inputs(tuple(mapping[n] for n in inputs))
    g.set_outputs(tuple(mapping[n] for n in outputs))
    stem = codegen.file_stem(entry.name, entry.id.lower())
    if fmt == "tikz":
        return {"filename": f"{stem}.tikz", "text": g.to_tikz()}
    return {"filename": f"{stem}.json", "text": g.to_json()}


# ---------------------------------------------------------------- Noise models


def noise_json(noise: NoiseEntry) -> dict[str, Any]:
    """A noise model for the page: its faults, settings and notes, plus the drawing of its diagram."""
    entry = SHELF.get(noise.diagram_id)
    weights = noise.settings["weights"]
    faults = [
        [[(edge, str(pauli)) for edge, pauli in sorted(fault.edge_flips.items())], value]
        for fault, value in noise.model.atomic_faults_with_values_unpacked()
    ]
    faults.sort(key=lambda row: [(e, "IXYZ".index(p)) for e, p in row[0]])
    noisy_edges = {e for edges, _ in faults for e, _ in edges}
    notes = []
    if len(set(weights.values())) > 1:
        notes.append(
            "The X, Y and Z weights differ. paritea's fault-equivalence check assumes equal weights, so with these it "
            "may give a wrong answer."
        )
    if not faults:
        notes.append("Every edge is noise-free, so this noise model has no faults.")
    return {
        "id": noise.id,
        "name": noise.name,
        "diagram": {"id": entry.id, "name": entry.name},
        "settings": noise.settings,
        "summary": {
            "Faults": noise.model.num_faults(),
            "Noisy edges": len(noisy_edges),
            "Noise-free edges": len(noise.settings["noise_free"]),
            "Weights X, Y, Z": f"{weights['x']}, {weights['y']}, {weights['z']}",
        },
        "faults": faults,
        "notes": notes,
        "code": noise.code,
        "drawing": diagram_json(entry.diagram),
    }


def noise_model(diagram: str, weights: dict[str, int], noise_free: list[int]) -> dict[str, Any]:
    """Independent X, Y and Z flips with the given weights on every edge except the noise-free ones."""
    entry = SHELF.get(diagram)
    d = entry.diagram
    for key in "xyz":
        w = weights.get(key)
        if not isinstance(w, int) or not 1 <= w <= MAX_WEIGHT:
            raise UserError(f"The {key.upper()} weight must be a whole number from 1 to {MAX_WEIGHT}.")
    edges = set(d.edge_indices())
    unknown = sorted(set(noise_free) - edges)
    if unknown:
        raise UserError(f"Diagram {diagram} has no edge {unknown[0]}.")
    chosen = sorted(set(noise_free))
    weights = {k: weights[k] for k in "xyz"}
    model = NoiseModel.weighted_edge_flip_noise(
        d, w_x=weights["x"], w_y=weights["y"], w_z=weights["z"], idealised_edges=chosen
    )
    code = codegen.noise_code(
        codegen.exact_diagram_code(entry),
        weights=weights,
        noise_free=[tuple(d.get_edge_endpoints_by_index(e)) for e in chosen],
    )
    free = f", {len(chosen)} noise-free" if chosen else ""
    noise = SHELF.add_noise(
        model,
        name=f"Edge-flip noise on {entry.id} (X {weights['x']}, Y {weights['y']}, Z {weights['z']}{free})",
        diagram_id=entry.id,
        settings={"weights": weights, "noise_free": chosen},
        code=code,
    )
    return noise_json(noise)


def noise_get(noise: str) -> dict[str, Any]:
    return noise_json(SHELF.get_noise(noise))


def noise_remove(noise: str) -> dict[str, str]:
    SHELF.remove_noise(noise)
    return {"removed": noise}


# ---------------------------------------------------------------- Fault propagation

KINDS = ["detected", "boundary", "none"]


def _boundary_labels(d: Diagram) -> dict[int, str]:
    """Names for boundary edges: 'in 0', 'out 3', ... (the edge next to that input or output)."""
    labels = {}
    inputs, outputs = d.io()
    for prefix, nodes in (("in", inputs), ("out", outputs)):
        for i, node in enumerate(nodes):
            for edge in d.incident_edges(node):
                labels[edge] = f"{prefix} {i}"
    return labels


def propagation(noise: str) -> dict[str, Any]:
    """Where every fault of a noise model ends up: Paulis on the boundary and the detecting regions it flips."""
    entry_noise = SHELF.get_noise(noise)
    entry = SHELF.get(entry_noise.diagram_id)
    d = entry.diagram
    require_valid(d)
    start = time.perf_counter()
    try:
        flip_ops = build_flip_operators(d)
    except AssertionError as exc:
        raise UserError(
            "paritea can't push faults out of this diagram: one of its stabilisers has no support on the boundary."
        ) from exc
    pushed = push_out(entry_noise.model, flip_ops)
    seconds = time.perf_counter() - start

    effects = []
    for fault, values in pushed.atomic_faults_with_values():
        boundary = [(edge, str(pauli)) for edge, pauli in sorted(fault.edge_flips.items())]
        detectors = sorted(fault.detector_flips)
        kind = "detected" if detectors else ("boundary" if boundary else "none")
        effects.append(
            {"kind": kind, "boundary": boundary, "regions": detectors, "faults": len(values), "min_weight": min(values)}
        )
    effects.sort(key=lambda e: (KINDS.index(e["kind"]), e["min_weight"], -e["faults"], e["regions"], e["boundary"]))
    counts = {kind: sum(e["faults"] for e in effects if e["kind"] == kind) for kind in KINDS}
    labels = _boundary_labels(d)
    return {
        "noise": {"id": entry_noise.id, "name": entry_noise.name},
        "diagram": {"id": entry.id, "name": entry.name},
        "summary": {
            "Faults": entry_noise.model.num_faults(),
            "Distinct effects": len(effects),
            "Detected": counts["detected"],
            "Undetected": counts["boundary"],
            "No effect": counts["none"],
        },
        "effects": effects,
        "labels": {str(edge): label for edge, label in labels.items()},
        "flip_operators": [[(edge, str(pauli)) for edge, pauli in sorted(op.items())] for op in flip_ops.stab_flip_ops],
        "regions": len(flip_ops.region_gen_set),
        "seconds": seconds,
        "code": codegen.propagation_code(entry_noise.code),
    }


# ---------------------------------------------------------------- Semantic equivalence


def _boundary_tableau(d: Diagram) -> np.ndarray:
    """The diagram's stabilisers on its boundary, row reduced, exactly as paritea's is_semantic_equivalence does.

    Columns are the boundaries in order (inputs, then outputs): first the Z parts, then the X parts.
    """
    idx_map = {d.incident_edges(b)[0]: i for i, b in enumerate(d.io_sorted())}
    return np.asarray(row_reduce_webs(compute_stabilisers(d), idx_map), dtype=np.uint8)


def _tableau_rows(tableau: np.ndarray) -> list[str]:
    """Rows as Pauli strings over the boundaries (I, X, Y, Z), without the all-zero rows."""
    n = tableau.shape[1] // 2
    return ["".join("IXZY"[int(row[i + n]) + 2 * int(row[i])] for i in range(n)) for row in tableau if row.any()]


def semantic_equivalence(a: str, b: str) -> dict[str, Any]:
    """Whether two diagrams are the same linear map up to a scalar: the same stabilisers on their boundaries.

    This is paritea's is_semantic_equivalence, computed from its parts so that stim is not needed.
    """
    sides = {}
    tableaus = []
    for key, entry_id in (("a", a), ("b", b)):
        entry = SHELF.get(entry_id)
        require_valid(entry.diagram)
        inputs, outputs = entry.diagram.io()
        tableau = _boundary_tableau(entry.diagram)
        tableaus.append(tableau)
        sides[key] = {
            "id": entry.id,
            "name": entry.name,
            "inputs": len(inputs),
            "outputs": len(outputs),
            "rows": _tableau_rows(tableau),
        }
    equivalent = bool(np.array_equal(*tableaus))
    if (sides["a"]["inputs"], sides["a"]["outputs"]) != (sides["b"]["inputs"], sides["b"]["outputs"]):
        reason = "They have different numbers of inputs or outputs, so they cannot be the same map."
    elif equivalent:
        reason = "They have the same stabilisers on their boundaries, so they are the same map up to a scalar."
    else:
        reason = "Their stabilisers on the boundaries differ, so they are different maps."
    return {
        "equivalent": equivalent,
        "reason": reason,
        **sides,
        "code": codegen.semantic_code(SHELF.get(a).code, SHELF.get(b).code),
    }


# ---------------------------------------------------------------- Pauli webs


def webs(diagram: str) -> dict[str, Any]:
    """Stabilising webs and detecting regions of a diagram on the shelf."""
    entry = SHELF.get(diagram)
    require_valid(entry.diagram)
    start = time.perf_counter()
    stabilisers, regions = compute_pauli_webs(entry.diagram)
    seconds = time.perf_counter() - start
    return {
        **entry_json(entry),
        "stabilisers": [web_json(w) for w in stabilisers],
        "regions": [web_json(w) for w in regions],
        "seconds": {"webs": seconds},
        "code": codegen.webs_code(entry.code),
    }


def pauli_webs(generator: str, params: dict[str, int]) -> dict[str, Any]:
    """Build a diagram with a generator (it goes on the shelf) and compute its Pauli webs."""
    start = time.perf_counter()
    built = diagram_generate(generator, params)
    result = webs(built["id"])
    result["seconds"]["build"] = time.perf_counter() - start - result["seconds"]["webs"]
    return {**result, "generator": generator, "params": params}


OPS: dict[str, Callable[..., Any]] = {
    "info": info,
    "generators": generators,
    "examples": examples,
    "diagram_generate": diagram_generate,
    "diagram_example": diagram_example,
    "diagram_import": diagram_import,
    "diagram_get": diagram_get,
    "diagram_remove": diagram_remove,
    "diagram_export": diagram_export,
    "noise_model": noise_model,
    "noise_get": noise_get,
    "noise_remove": noise_remove,
    "propagation": propagation,
    "semantic_equivalence": semantic_equivalence,
    "webs": webs,
    "pauli_webs": pauli_webs,
}


def _run(op: str, args_json: str) -> Any:
    if op not in OPS:
        raise UserError(f"Unknown operation: {op}.")
    return OPS[op](**json.loads(args_json))


def dispatch(op: str, args_json: str) -> str:
    """Run one operation and return ``{"ok": true, "result": ...}`` or ``{"ok": false, "error": ...}`` as JSON."""
    try:
        return json.dumps({"ok": True, "result": _run(op, args_json)}, allow_nan=False)
    except BaseException as exc:  # Rust panics derive from BaseException
        if not isinstance(exc, Exception) and not is_rust_panic(exc):
            raise
        error = {"type": type(exc).__name__, "message": str(exc) or type(exc).__name__}
        if is_rust_panic(exc):
            error["message"] = f"paritea's Rust core stopped with an internal error: {exc}"
        if not isinstance(exc, UserError):
            error["traceback"] = traceback.format_exc()
        return json.dumps({"ok": False, "error": error})
