"""Where to draw each node of a diagram (no plotting library needed)."""

import rustworkx as rx
from paritea.diagram import Diagram


def node_positions(d: Diagram) -> dict[int, tuple[float, float]]:
    """Node positions from the diagram, or a spring layout if some node has no position."""
    nodes = list(d.node_indices())
    if all(d.x(n) != -1 and d.y(n) != -1 for n in nodes):
        return {n: (float(d.x(n)), float(d.y(n))) for n in nodes}

    g = rx.PyGraph()
    idx = {n: g.add_node(n) for n in nodes}
    g.add_edges_from_no_data([(idx[s], idx[t]) for s, t in d.edge_list()])
    layout = rx.spring_layout(g, seed=0)
    return {n: (float(layout[idx[n]][0]), float(layout[idx[n]][1])) for n in nodes}
