"""Plain-Python helpers around paritea used by the UI.

Nothing in this module imports Streamlit, so everything here can be unit tested and cached.
"""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from paritea import PauliString
from paritea.diagram import Diagram, NodeType
from paritea.generate import shor_extraction, steane_code_stabilisers, surface_code_memory_experiment, zweb
from paritea.glue.pyzx import from_pyzx
from paritea.web import compute_pauli_webs


@dataclass(frozen=True)
class IntParam:
    """An integer parameter of a diagram generator, rendered as a number input."""

    label: str
    default: int
    min_value: int
    max_value: int
    help: str = ""


@dataclass(frozen=True)
class DiagramGenerator:
    """A named way of building a diagram from integer parameters."""

    description: str
    params: dict[str, IntParam]
    build: Callable[..., Diagram]


def _rotated_surface_code(*, distance: int, rounds: int) -> Diagram:
    return surface_code_memory_experiment(distance=distance, rounds=rounds)


def _steane_shor_extraction(*, rounds: int) -> Diagram:
    return shor_extraction(steane_code_stabilisers(), qubits=7, repeat=rounds)


def _zweb(*, qubits: int, depth: int) -> Diagram:
    return from_pyzx(zweb(qubits, depth), positions=True)


# To offer a new kind of diagram in the UI, add an entry here. Every generator must return a diagram with real IO set
# and node positions, which is what the web computation and the drawing code expect.
GENERATORS: dict[str, DiagramGenerator] = {
    "Rotated surface code memory experiment": DiagramGenerator(
        description="Rotated planar surface code memory experiment, derived from Stim's circuit generator.",
        params={
            "distance": IntParam("Distance", default=3, min_value=2, max_value=9),
            "rounds": IntParam("Rounds", default=1, min_value=1, max_value=10, help="Syndrome extraction rounds"),
        },
        build=_rotated_surface_code,
    ),
    "Steane code, Shor syndrome extraction": DiagramGenerator(
        description="Shor-style syndrome extraction for the [[7,1,3]] Steane code, post-selected on trivial syndromes.",
        params={
            "rounds": IntParam("Rounds", default=1, min_value=1, max_value=5, help="Syndrome extraction rounds"),
        },
        build=_steane_shor_extraction,
    ),
    "Z-web grid": DiagramGenerator(
        description="A grid of Z spiders in which every sub-rectangle is an X-error detecting region.",
        params={
            "qubits": IntParam("Qubits", default=2, min_value=1, max_value=10),
            "depth": IntParam("Depth", default=2, min_value=1, max_value=10),
        },
        build=_zweb,
    ),
}


def build_diagram(generator: str, **params: int) -> Diagram:
    """Build a diagram with one of the GENERATORS.

    Not deterministic for every generator: shor_extraction numbers its nodes and edges differently on each call.
    """
    return GENERATORS[generator].build(**params)


@dataclass(frozen=True)
class PauliWebs:
    """A diagram together with its Pauli webs.

    Webs are keyed by edge indices of exactly this diagram, and rebuilding a diagram can renumber its edges, so keep
    (and cache) the two together rather than pairing webs with a separately built diagram.
    """

    diagram: Diagram
    stabilisers: list[PauliString]
    regions: list[PauliString]


def pauli_webs(d: Diagram) -> PauliWebs:
    """Stabilising webs and detecting regions of a diagram."""
    stabilisers, regions = compute_pauli_webs(d)
    return PauliWebs(d, stabilisers, regions)


def diagram_summary(d: Diagram) -> dict[str, int]:
    """Headline numbers describing a diagram."""
    inputs, outputs = d.io()
    types = Counter(d.type(n) for n in d.node_indices())
    return {
        "Nodes": d.num_nodes(),
        "Edges": d.num_edges(),
        "Inputs": len(inputs),
        "Outputs": len(outputs),
        "Z spiders": types[NodeType.Z],
        "X spiders": types[NodeType.X],
    }


def is_rust_panic(exc: BaseException) -> bool:
    """Whether an exception is a panic from paritea's Rust extension.

    pyo3 raises panics as ``pyo3_runtime.PanicException``, which derives from BaseException rather than Exception, so
    ``except Exception`` does not catch it.
    """
    return type(exc).__name__ == "PanicException"
