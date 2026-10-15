"""Python that reproduces what the page did, using paritea's public API only."""

import inspect
from typing import Any

from paritea_ui.examples import EXAMPLES

# How to build each generator's diagram: imports, then the line(s) that build ``diagram``.
_GENERATOR_CODE: dict[str, tuple[str, str]] = {
    "Rotated surface code memory experiment": (
        "from paritea.generate import surface_code_memory_experiment",
        "diagram = surface_code_memory_experiment(distance={distance}, rounds={rounds})",
    ),
    "Steane code, Shor syndrome extraction": (
        "from paritea.generate import shor_extraction, steane_code_stabilisers",
        "diagram = shor_extraction(steane_code_stabilisers(), qubits=7, repeat={rounds})",
    ),
    "Rotated surface code, Shor syndrome extraction": (
        "from paritea.generate import rotated_planar_surface_code_stabilisers, shor_extraction",
        "stabilisers = rotated_planar_surface_code_stabilisers({size})\n"
        "diagram = shor_extraction(stabilisers, qubits={size} * {size}, repeat={rounds})",
    ),
    "Z-web grid": (
        "from paritea.generate import zweb\nfrom paritea.glue.pyzx import from_pyzx",
        "diagram = from_pyzx(zweb({qubits}, {depth}), positions=True)",
    ),
    "Random Clifford diagram": (
        "import random\n\nfrom paritea.generate import clifford\nfrom paritea.glue.pyzx import from_pyzx",
        "random.seed({seed})  # the generator uses Python's global random numbers\n"
        "graph = clifford({qubits}, {spiders})\n"
        "graph.auto_detect_io()\n"
        "diagram = from_pyzx(graph, positions=True)",
    ),
}


def generator_code(generator: str, params: dict[str, int]) -> str:
    imports, build = _GENERATOR_CODE[generator]
    return f"{imports}\n\n{build.format(**params)}\n"


def example_code(example: str) -> str:
    builder = EXAMPLES[example].build
    source = inspect.getsource(builder)
    imports = [
        line
        for line, needed in [
            ("import math", "math." in source),
            ("from fractions import Fraction", "Fraction(" in source),
            ("", True),
            ("from paritea.diagram import Diagram, NodeType", True),
            (
                "from paritea.generate import surface_code_memory_experiment",
                "surface_code_memory_experiment(" in source,
            ),
        ]
        if needed
    ]
    return "\n".join(imports).lstrip("\n") + f"\n\n\n{source}\n\ndiagram = {builder.__name__}()\n"


def import_code(
    *, filename: str, fmt: str, convert_hadamard: bool, keep_positions: bool, io: str, inputs: list, outputs: list
) -> str:
    read = "zx.Graph.from_json(f.read())" if fmt == "pyzx" else "zx.Circuit.from_qasm(f.read()).to_graph()"
    lines = [
        "import pyzx as zx",
        "from paritea.glue.pyzx import from_pyzx",
        "",
        f"with open({filename!r}) as f:  # the file you imported",
        f"    graph = {read}",
    ]
    if io == "detect":
        lines.append("graph.auto_detect_io()")
    elif io == "outputs":
        lines += ["graph.set_inputs(())", "graph.set_outputs(())"]
    lines += [
        f"diagram = from_pyzx(graph, convert_had_edges={convert_hadamard}, positions={keep_positions})",
        "# The inputs and outputs used on the page (older pyzx versions do not read them from files):",
        f"diagram.set_io(inputs={inputs}, outputs={outputs}, virtual=False)",
    ]
    return "\n".join(lines) + "\n"


# Generators whose edge numbers differ between runs or computers: shor_extraction renumbers on every call, and the
# surface code iterates sets of tuples, whose order differs between 32-bit browsers and 64-bit Python.
UNSTABLE_NUMBERING = {
    "Rotated surface code memory experiment",
    "Steane code, Shor syndrome extraction",
    "Rotated surface code, Shor syndrome extraction",
}


def file_stem(name: str, fallback: str) -> str:
    """A file name (without extension) for downloads of a shelf object."""
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")[:60] or fallback


def _with_import(code: str, statement: str) -> str:
    """Add an import statement after the import block at the top of ``code``."""
    lines = code.rstrip("\n").split("\n")
    last = -1
    for i, line in enumerate(lines):
        if line.startswith(("import ", "from ")):
            last = i
        elif line.strip():
            break
    lines.insert(last + 1, statement)
    return "\n".join(lines) + "\n"


def exact_diagram_code(entry: Any) -> str:
    """Python that rebuilds exactly this shelf diagram, with the same node and edge numbers.

    Needed whenever the code goes on to name particular edges.
    """
    source = entry.source
    if source["kind"] != "generator" or source["generator"] not in UNSTABLE_NUMBERING:
        return entry.code
    filename = file_stem(entry.name, entry.id.lower()) + ".json"
    inputs, outputs = entry.diagram.io()
    return (
        "import pyzx as zx\nfrom paritea.glue.pyzx import from_pyzx\n\n"
        "# Building this diagram again would number its edges differently, so load the exact copy:\n"
        f"# download {filename} (PyZX JSON) from the Diagrams page first.\n"
        f"with open({filename!r}) as f:\n"
        "    diagram = from_pyzx(zx.Graph.from_json(f.read()), positions=True)\n"
        f"diagram.set_io(inputs={list(inputs)}, outputs={list(outputs)}, virtual=False)\n"
    )


def _pairs(pairs: list[tuple[int, int]], indent: str = "    ") -> str:
    """A list of (s, t) pairs as Python, eight per line."""
    rows = [", ".join(f"({s}, {t})" for s, t in pairs[i : i + 8]) for i in range(0, len(pairs), 8)]
    if len(rows) <= 1:
        return f"[{rows[0] if rows else ''}]"
    return "[\n" + "".join(f"{indent}{row},\n" for row in rows) + "]"


def webs_code(diagram_code: str) -> str:
    return (
        _with_import(diagram_code, "from paritea.web import compute_pauli_webs")
        + "stabilising_webs, detecting_regions = compute_pauli_webs(diagram)\n"
        + "print(len(stabilising_webs), len(detecting_regions))\n"
    )


def _as_function(code: str, name: str) -> str:
    """Wrap diagram-building code in a function returning ``diagram``, so two diagrams can share one script."""
    body = "".join(f"    {line}\n" if line.strip() else "\n" for line in code.rstrip("\n").split("\n"))
    return f"def {name}():\n{body}    return diagram\n"


def semantic_code(code_a: str, code_b: str) -> str:
    return (
        "from paritea.equivalence import is_semantic_equivalence\n\n\n"
        f"{_as_function(code_a, 'diagram_a')}\n\n{_as_function(code_b, 'diagram_b')}\n\n"
        "print(is_semantic_equivalence(diagram_a(), diagram_b()))\n"
    )


def propagation_code(noise_code: str) -> str:
    code = _with_import(noise_code, "from paritea import build_flip_operators, push_out")
    return code + (
        "\nflip_operators = build_flip_operators(diagram)\n"
        "pushed_out = push_out(noise_model, flip_operators)\n"
        "for fault, weights in pushed_out.atomic_faults_with_values():\n"
        "    boundary = {edge: str(pauli) for edge, pauli in fault.edge_flips.items()}\n"
        "    print(boundary, sorted(fault.detector_flips), weights)\n"
    )


def noise_code(diagram_code: str, *, weights: dict[str, int], noise_free: list[tuple[int, int]]) -> str:
    code = _with_import(diagram_code, "from paritea.noise import NoiseModel")
    if noise_free:
        code += (
            "\n# Noise-free edges, named by the nodes they join\n"
            f"noise_free_wires = {_pairs(noise_free)}\n"
            "noise_free = [diagram.edge_indices_from_endpoints(s, t)[0] for s, t in noise_free_wires]\n"
        )
    else:
        code += "\nnoise_free = []\n"
    return code + (
        "noise_model = NoiseModel.weighted_edge_flip_noise(\n"
        f"    diagram, w_x={weights['x']}, w_y={weights['y']}, w_z={weights['z']}, idealised_edges=noise_free\n"
        ")\n"
        "print(noise_model.num_faults(), 'faults')\n"
    )
