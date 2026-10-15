"""JSON-in, JSON-out operations behind the web page.

The browser engine (Pyodide in a web worker) calls ``dispatch(op, args_json)`` and gets a JSON string back. The same
functions run natively, which is how their results are tested and precomputed.
"""

import json
import sys
import time
import traceback
from collections.abc import Callable
from typing import Any

from paritea import PauliString
from paritea.diagram import Diagram
from paritea.web import compute_pauli_webs

from paritea_ui.core import GENERATORS, build_diagram, diagram_summary, is_rust_panic
from paritea_ui.layout import node_positions

# Python that builds each generator's diagram, shown on the page so a result can be reproduced outside the browser.
_BUILD_CODE: dict[str, tuple[str, str]] = {
    "Rotated surface code memory experiment": (
        "from paritea.generate import surface_code_memory_experiment",
        "diagram = surface_code_memory_experiment(distance={distance}, rounds={rounds})",
    ),
    "Steane code, Shor syndrome extraction": (
        "from paritea.generate import shor_extraction, steane_code_stabilisers",
        "diagram = shor_extraction(steane_code_stabilisers(), qubits=7, repeat={rounds})",
    ),
    "Z-web grid": (
        "from paritea.generate import zweb\nfrom paritea.glue.pyzx import from_pyzx",
        "diagram = from_pyzx(zweb({qubits}, {depth}), positions=True)",
    ),
}


def info() -> dict[str, str]:
    """Where the engine runs, e.g. Python 3.14.2 on emscripten inside a browser."""
    return {"python": sys.version.split()[0], "platform": sys.platform}


def generators() -> list[dict[str, Any]]:
    """The diagram generators and their integer parameters, for building the input form."""
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
                    "help": p.help,
                }
                for key, p in generator.params.items()
            ],
        }
        for name, generator in GENERATORS.items()
    ]


def diagram_json(d: Diagram) -> dict[str, Any]:
    """Everything needed to draw a diagram: typed nodes with positions and phases, edges as [index, source, target]."""
    positions = node_positions(d)
    inputs, outputs = d.io()
    return {
        "nodes": [
            {"id": n, "type": str(d.type(n)), "phase": str(d.phase(n)), "x": positions[n][0], "y": positions[n][1]}
            for n in d.node_indices()
        ],
        "edges": [[e, *d.get_edge_endpoints_by_index(e)] for e in d.edge_indices()],
        "inputs": list(inputs),
        "outputs": list(outputs),
    }


def web_json(web: PauliString) -> list[tuple[int, str]]:
    """A web as sorted [edge index, Pauli] pairs."""
    return [(edge, str(pauli)) for edge, pauli in sorted(web.items())]


def python_code(generator: str, params: dict[str, int]) -> str:
    """Stand-alone Python that reproduces a Pauli-webs result."""
    imports, build = _BUILD_CODE[generator]
    return (
        f"{imports}\nfrom paritea.web import compute_pauli_webs\n\n"
        f"{build.format(**params)}\n"
        "stabilising_webs, detecting_regions = compute_pauli_webs(diagram)\n"
        "print(len(stabilising_webs), len(detecting_regions))\n"
    )


def pauli_webs(generator: str, params: dict[str, int]) -> dict[str, Any]:
    """Build a diagram with a generator and compute its stabilising webs and detecting regions."""
    spec = GENERATORS[generator]
    for key, p in spec.params.items():
        value = params.get(key)
        if not isinstance(value, int) or not p.min_value <= value <= p.max_value:
            raise ValueError(f"{p.label} must be a whole number from {p.min_value} to {p.max_value}.")

    start = time.perf_counter()
    d = build_diagram(generator, **params)
    built = time.perf_counter()
    stabilisers, regions = compute_pauli_webs(d)
    done = time.perf_counter()
    return {
        "generator": generator,
        "params": params,
        "diagram": diagram_json(d),
        "summary": diagram_summary(d),
        "stabilisers": [web_json(w) for w in stabilisers],
        "regions": [web_json(w) for w in regions],
        "seconds": {"build": built - start, "webs": done - built},
        "code": python_code(generator, params),
    }


OPS: dict[str, Callable[..., Any]] = {"info": info, "generators": generators, "pauli_webs": pauli_webs}


def dispatch(op: str, args_json: str) -> str:
    """Run one operation and return ``{"ok": true, "result": ...}`` or ``{"ok": false, "error": ...}`` as JSON."""
    try:
        result = OPS[op](**json.loads(args_json))
    except BaseException as exc:  # Rust panics derive from BaseException
        if not isinstance(exc, Exception) and not is_rust_panic(exc):
            raise
        error = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        return json.dumps({"ok": False, "error": error})
    return json.dumps({"ok": True, "result": result})
