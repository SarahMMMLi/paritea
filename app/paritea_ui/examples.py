"""Ready-made diagrams from paritea's demo notebook and tests, with the answers paritea gives for them.

Each builder is plain paritea code that does not depend on this package: the page shows its source as the Python that
reproduces the diagram.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from paritea.diagram import Diagram, NodeType
from paritea.generate import surface_code_memory_experiment


def steane_state() -> Diagram:
    """The [[7,1,3]] Steane code's logical |0> state (demo/steane-state-prep-ft-check.ipynb)."""
    d = Diagram()
    xs = [d.add_node(NodeType.X, x=0, y=1.5 + i) for i in range(4)]
    zs = [d.add_node(NodeType.Z, x=2, y=i) for i in range(7)]
    bs = [d.add_node(NodeType.B, x=3, y=i) for i in range(7)]
    d.add_edges([(xs[0], zs[0]), (xs[0], zs[1]), (xs[0], zs[2])])
    d.add_edges([(xs[1], zs[0]), (xs[1], zs[2]), (xs[1], zs[3]), (xs[1], zs[5])])
    d.add_edges([(xs[2], zs[2]), (xs[2], zs[4]), (xs[2], zs[5])])
    d.add_edges([(xs[3], zs[0]), (xs[3], zs[5]), (xs[3], zs[6])])
    d.add_edges(list(zip(zs, bs, strict=True)))
    d.set_io(inputs=[], outputs=bs, virtual=False)
    return d


def steane_circuit() -> Diagram:
    """A circuit preparing the Steane |0>, checked by one extra qubit (demo/steane-state-prep-ft-check.ipynb)."""
    d = Diagram()
    # First layer: |0> (X spider) or |+> (Z spider) on each qubit; qubit 7 is the extra verification qubit.
    kinds = [NodeType.X, NodeType.Z, NodeType.Z, NodeType.Z, NodeType.X, NodeType.X, NodeType.X, NodeType.X]
    qubits = [d.add_node(kind, x=0, y=q) for q, kind in enumerate(kinds)]

    def add_cnot(*, ct: int, tgt: int, x: int) -> None:
        ct_node, tgt_node = d.add_node(NodeType.Z, x=x, y=ct), d.add_node(NodeType.X, x=x, y=tgt)
        d.add_edges([(ct_node, tgt_node), (ct_node, qubits[ct]), (tgt_node, qubits[tgt])])
        qubits[ct], qubits[tgt] = ct_node, tgt_node

    for ct, tgt, x in [(1, 0, 1), (3, 5, 1), (2, 6, 2), (1, 4, 3), (2, 0, 4), (3, 6, 4), (1, 5, 5), (6, 4, 6)]:
        add_cnot(ct=ct, tgt=tgt, x=x)  # encoding
    for ct, tgt, x in [(0, 7, 7), (5, 7, 8), (6, 7, 9)]:
        add_cnot(ct=ct, tgt=tgt, x=x)  # verification onto qubit 7

    bs = [d.add_node(NodeType.B, x=11, y=q) for q in range(7)]
    d.add_edges(list(zip(qubits, bs, strict=False)))
    d.add_edge(qubits[7], d.add_node(NodeType.X, x=10, y=7))  # post-select qubit 7 on |0>
    d.set_io(inputs=[], outputs=bs, virtual=False)
    return d


def closed_surface_code() -> Diagram:
    """The distance-3, one-round surface code with every input and output capped by an X spider (paritea's tests)."""
    d = surface_code_memory_experiment(distance=3, rounds=1)
    d.virtualize_io()  # removes the boundaries; the spiders next to them become the inputs and outputs
    inputs, outputs = d.io()
    for b in inputs + outputs:
        cap = d.add_node(NodeType.X, x=d.x(b) - 1 if b in inputs else d.x(b) + 1, y=d.y(b))
        d.add_edge(cap, b)
    d.set_io([], [], virtual=False)
    return d


def two_half_pi_spiders() -> Diagram:
    """Two π/2 Z spiders on a wire; fusing them gives a single π spider (paritea's tests)."""
    d = Diagram()
    b1 = d.add_node(NodeType.B, x=0, y=0)
    z1 = d.add_node(NodeType.Z, phase=Fraction(1, 2), x=1, y=0)
    z2 = d.add_node(NodeType.Z, phase=Fraction(1, 2), x=2, y=0)
    b2 = d.add_node(NodeType.B, x=3, y=0)
    d.add_edges([(b1, z1), (z1, z2), (z2, b2)])
    d.set_io(inputs=[b1], outputs=[b2], virtual=False)
    return d


def one_pi_spider() -> Diagram:
    """A single π Z spider on a wire (paritea's tests)."""
    d = Diagram()
    b1 = d.add_node(NodeType.B, x=0, y=0)
    z = d.add_node(NodeType.Z, phase=1, x=1.5, y=0)
    b2 = d.add_node(NodeType.B, x=3, y=0)
    d.add_edges([(b1, z), (z, b2)])
    d.set_io(inputs=[b1], outputs=[b2], virtual=False)
    return d


def one_half_pi_spider() -> Diagram:
    """A single π/2 Z spider on a wire: not the same map as two π/2 spiders (paritea's tests)."""
    d = Diagram()
    b1 = d.add_node(NodeType.B, x=0, y=0)
    z = d.add_node(NodeType.Z, phase=Fraction(1, 2), x=1.5, y=0)
    b2 = d.add_node(NodeType.B, x=3, y=0)
    d.add_edges([(b1, z), (z, b2)])
    d.set_io(inputs=[b1], outputs=[b2], virtual=False)
    return d


def spider_star(legs: int = 6) -> Diagram:
    """One Z spider with a boundary on each of its legs (paritea's tests)."""
    d = Diagram()
    z = d.add_node(NodeType.Z, x=0, y=0)
    for i in range(legs):
        angle = 2 * math.pi * i / legs
        d.add_edge(z, d.add_node(NodeType.B, x=round(2 * math.cos(angle), 3), y=round(2 * math.sin(angle), 3)))
    d.infer_io_from_boundaries()
    return d


def spider_ring(size: int = 6) -> Diagram:
    """A ring of Z spiders, each with one boundary; paritea's tests compare it with the star of the same size."""
    d = Diagram()
    zs, bs = [], []
    for i in range(size):
        angle = 2 * math.pi * i / size
        zs.append(d.add_node(NodeType.Z, x=round(1.5 * math.cos(angle), 3), y=round(1.5 * math.sin(angle), 3)))
        bs.append(d.add_node(NodeType.B, x=round(2.7 * math.cos(angle), 3), y=round(2.7 * math.sin(angle), 3)))
    for i in range(size):
        d.add_edges([(zs[i - 1], zs[i]), (zs[i], bs[i])])
    d.infer_io_from_boundaries()
    return d


@dataclass(frozen=True)
class Example:
    """A ready-made diagram and what paritea finds in it."""

    title: str
    description: str
    build: Callable[[], Diagram]
    stabilising_webs: int
    detecting_regions: int


EXAMPLES: dict[str, Example] = {
    "steane-state": Example(
        "Steane code: logical |0⟩",
        "The [[7,1,3]] Steane code's logical zero state, from paritea's demo notebook.",
        steane_state,
        stabilising_webs=7,
        detecting_regions=0,
    ),
    "steane-circuit": Example(
        "Steane code: |0⟩ preparation circuit",
        "A circuit that prepares the same state, checked by an extra qubit. paritea shows it is fault equivalent "
        "to the logical |0⟩.",
        steane_circuit,
        stabilising_webs=7,
        detecting_regions=1,
    ),
    "closed-surface-code": Example(
        "Closed surface code (distance 3)",
        "Every input and output capped by an X spider, so only detecting regions remain.",
        closed_surface_code,
        stabilising_webs=0,
        detecting_regions=9,
    ),
    "two-half-pi": Example(
        "Two π/2 spiders",
        "Fusing them gives a single π spider; paritea's tests check that the two are fault equivalent.",
        two_half_pi_spiders,
        stabilising_webs=2,
        detecting_regions=0,
    ),
    "one-pi": Example(
        "One π spider",
        "The fused form of the two π/2 spiders.",
        one_pi_spider,
        stabilising_webs=2,
        detecting_regions=0,
    ),
    "one-half-pi": Example(
        "One π/2 spider",
        "Half the phase of the fused pair, so a different map: semantic equivalence says no.",
        one_half_pi_spider,
        stabilising_webs=2,
        detecting_regions=0,
    ),
    "star-6": Example(
        "Star of 6",
        "One spider with six legs. Collapsing a ring into a star is fault equivalent only up to five legs.",
        spider_star,
        stabilising_webs=6,
        detecting_regions=0,
    ),
    "ring-6": Example(
        "Ring of 6",
        "Six spiders in a ring, each with one leg. The ring itself is a detecting region.",
        spider_ring,
        stabilising_webs=6,
        detecting_regions=1,
    ),
}
