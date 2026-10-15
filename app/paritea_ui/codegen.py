"""Python that reproduces what the page did, using paritea's public API only."""

import inspect

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


def webs_code(diagram_code: str) -> str:
    return (
        diagram_code.replace("\n\n", "\nfrom paritea.web import compute_pauli_webs\n\n", 1)
        + "stabilising_webs, detecting_regions = compute_pauli_webs(diagram)\n"
        + "print(len(stabilising_webs), len(detecting_regions))\n"
    )
