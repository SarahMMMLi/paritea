"""Matplotlib rendering of paritea diagrams, optionally highlighting a Pauli web.

``paritea.draw`` only works inside Jupyter, so the UI draws diagrams itself from node positions. Figures are created
with ``Figure()`` rather than pyplot, which keeps them out of pyplot's global state and needs no GUI backend.
"""

from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from paritea import Pauli, PauliString
from paritea.diagram import Diagram, NodeType

from paritea_ui.layout import node_positions

# Colours follow pyzx's defaults so diagrams look the same as in the notebooks.
NODE_STYLES: dict[NodeType, dict] = {
    NodeType.Z: {"c": "#ccffcc", "marker": "o", "s": 120},
    NodeType.X: {"c": "#ff8888", "marker": "o", "s": 120},
    NodeType.H: {"c": "#ffff66", "marker": "s", "s": 80},
    NodeType.B: {"c": "#000000", "marker": "o", "s": 15},
}
PAULI_COLORS: dict[Pauli, str] = {Pauli.X: "#d62728", Pauli.Z: "#2ca02c", Pauli.Y: "#1f77b4"}


def draw_diagram(d: Diagram, *, web: PauliString | None = None, show_phases: bool = False) -> Figure:
    """Draw a diagram, colouring the edges of ``web`` (if given) by their Pauli."""
    pos = node_positions(d)
    xs = [x for x, _ in pos.values()]
    ys = [y for _, y in pos.values()]
    width = min(max((max(xs) - min(xs)) * 0.4, 6), 30)
    height = min(max((max(ys) - min(ys)) * 0.4, 3), 20)

    fig = Figure(figsize=(width, height), layout="tight")
    ax = fig.subplots()
    ax.set_axis_off()
    ax.invert_yaxis()  # Qubit 0 at the top, as in pyzx

    edges = [(pos[s], pos[t]) for s, t in d.edge_list()]
    ax.add_collection(LineCollection(edges, colors="#000000", linewidths=0.8, zorder=1))

    if web is not None:
        web_edges = [(e, p) for e, p in web.items() if p != Pauli.I]
        segments = []
        for e, _ in web_edges:
            s, t = d.get_edge_endpoints_by_index(e)
            segments.append((pos[s], pos[t]))
        colors = [PAULI_COLORS[p] for _, p in web_edges]
        ax.add_collection(LineCollection(segments, colors=colors, linewidths=4, alpha=0.8, zorder=2))
        legend = [Line2D([0], [0], color=c, linewidth=4, label=p) for p, c in PAULI_COLORS.items()]
        ax.legend(handles=legend, loc="upper left", bbox_to_anchor=(1, 1), frameon=False)

    for node_type, style in NODE_STYLES.items():
        nodes = [n for n in pos if d.type(n) == node_type]
        if nodes:
            ax.scatter(
                [pos[n][0] for n in nodes],
                [pos[n][1] for n in nodes],
                edgecolors="#000000",
                linewidths=0.8,
                zorder=3,
                **style,
            )

    if show_phases:
        for n, (x, y) in pos.items():
            if d.phase(n) != 0:
                ax.annotate(f"{d.phase(n)}π", (x, y), xytext=(0, 8), textcoords="offset points", ha="center", size=7)

    ax.autoscale_view()
    return fig
