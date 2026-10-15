"""Where to draw each node of a diagram (no plotting library needed).

paritea stores a position per node, with -1 meaning "no position". Generators set positions; imported files and some
generators leave gaps, which ``place_unpositioned`` fills while keeping every existing position.
"""

import math
import statistics
from copy import deepcopy

import rustworkx as rx
from paritea.diagram import Diagram

UNSET = -1
# Drawings look right when a typical wire is about this long (in the page's units of 40 px).
TYPICAL_EDGE = 1.2
# No two symbols are drawn closer than this, so they never touch (a Z or X spider is 0.575 units across).
MIN_SPACING = 0.75


def _placed(d: Diagram, n: int) -> bool:
    return d.x(n) != UNSET and d.y(n) != UNSET


def place_unpositioned(d: Diagram) -> Diagram:
    """Give every node without a position one, keeping the positions that exist. Returns the same diagram."""
    nodes = list(d.node_indices())
    placed = {n: (float(d.x(n)), float(d.y(n))) for n in nodes if _placed(d, n)}
    missing = [n for n in nodes if n not in placed]
    if not missing:
        return d

    # A node between positioned neighbours, such as an H box on a wire, goes to their midpoint.
    for _ in range(3):
        filled = False
        for n in missing:
            around = [placed[m] for m in d.neighbors(n) if m in placed]
            if n not in placed and len(around) >= 2:
                placed[n] = (statistics.fmean(p[0] for p in around), statistics.fmean(p[1] for p in around))
                filled = True
        if not filled:
            break

    rest = [n for n in missing if n not in placed]
    if rest:
        g = rx.PyGraph()
        idx = {n: g.add_node(n) for n in nodes}
        g.add_edges_from_no_data([(idx[s], idx[t]) for s, t in d.edge_list()])
        if placed:
            layout = rx.spring_layout(
                g,
                pos={idx[n]: list(p) for n, p in placed.items()},
                fixed={idx[n] for n in placed},
                k=TYPICAL_EDGE,
                seed=0,
                num_iter=300,
            )
        else:
            layout = rx.spring_layout(g, seed=0, num_iter=300)
        for n in rest:
            placed[n] = (float(layout[idx[n]][0]), float(layout[idx[n]][1]))

    for n in missing:
        x, y = placed[n]
        d.set_x(n, round(x, 3)).set_y(n, round(y, 3))
    return d


def _spread(values: dict[int, float]) -> dict[int, float]:
    """Move coordinates apart along one axis: distinct values end up at least MIN_SPACING apart.

    Order and equality are kept, so a wire that was horizontal or vertical stays that way.
    """
    moved: dict[float, float] = {}
    previous = None
    for value in sorted(set(values.values())):
        if previous is None:
            moved[value] = value
        else:  # the tiny margin keeps the gap at least MIN_SPACING after floating-point rounding
            moved[value] = moved[previous] + max(value - previous, MIN_SPACING + 1e-9)
        previous = value
    return {n: moved[v] for n, v in values.items()}


def node_positions(d: Diagram) -> dict[int, tuple[float, float]]:
    """Positions for drawing: the stored ones (missing ones filled in), scaled so a typical wire has a sensible length
    and spread so that no two symbols are closer than MIN_SPACING.

    The diagram itself is not changed.
    """
    if not all(_placed(d, n) for n in d.node_indices()):
        d = place_unpositioned(deepcopy(d))
    pos = {n: (float(d.x(n)), float(d.y(n))) for n in d.node_indices()}
    lengths = [math.dist(pos[s], pos[t]) for s, t in d.edge_list() if pos[s] != pos[t]]
    if lengths:
        typical = statistics.median(lengths)
        if not 0.5 <= typical <= 3:
            scale = TYPICAL_EDGE / typical
            pos = {n: (x * scale, y * scale) for n, (x, y) in pos.items()}
    xs = _spread({n: x for n, (x, _) in pos.items()})
    ys = _spread({n: y for n, (_, y) in pos.items()})
    return {n: (xs[n], ys[n]) for n in pos}
