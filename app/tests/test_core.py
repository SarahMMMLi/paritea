import math

import pytest
from paritea.diagram import Diagram, NodeType
from paritea.web import compute_pauli_webs

from paritea_ui.core import GENERATORS, build_diagram
from paritea_ui.layout import MIN_SPACING, node_positions


def _defaults(generator: str) -> dict[str, int]:
    return {name: spec.default for name, spec in GENERATORS[generator].params.items()}


@pytest.mark.parametrize("generator", list(GENERATORS))
def test_generators_build_diagrams_ready_for_web_computation(generator: str) -> None:
    d = build_diagram(generator, **_defaults(generator))

    assert not d.is_io_virtual()
    assert all(d.x(n) != -1 and d.y(n) != -1 for n in d.node_indices()), "generators must set node positions"
    stabilisers, _ = compute_pauli_webs(d)
    assert stabilisers


@pytest.mark.parametrize("generator", list(GENERATORS))
def test_generator_defaults_lie_within_their_bounds(generator: str) -> None:
    for spec in GENERATORS[generator].params.values():
        assert spec.min_value <= spec.default <= spec.max_value


@pytest.mark.parametrize("generator", list(GENERATORS))
def test_node_positions_keep_symbols_apart_and_wires_straight(generator: str) -> None:
    d = build_diagram(generator, **_defaults(generator))

    pos = node_positions(d)

    nodes = list(pos)
    assert min(math.dist(pos[a], pos[b]) for i, a in enumerate(nodes) for b in nodes[i + 1 :]) >= MIN_SPACING
    for s, t in d.edge_list():
        assert (d.x(s) == d.x(t)) == (pos[s][0] == pos[t][0])
        assert (d.y(s) == d.y(t)) == (pos[s][1] == pos[t][1])


def test_node_positions_fall_back_to_a_layout_when_positions_are_missing() -> None:
    d = Diagram()
    b1, b2 = d.add_node(NodeType.B), d.add_node(NodeType.B)
    z = d.add_node(NodeType.Z)
    d.add_edges([(b1, z), (z, b2)])

    pos = node_positions(d)

    assert set(pos) == {b1, b2, z}
    assert len(set(pos.values())) == 3
