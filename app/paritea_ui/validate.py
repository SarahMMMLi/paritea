"""Checks that explain, in plain words, every diagram that paritea's Rust core would reject with a crash.

paritea's Rust core panics (or silently computes nonsense) on several kinds of input. Running these checks first turns
each case into a message that says what to fix.
"""

from fractions import Fraction

from paritea.diagram import Diagram

MAX_LISTED = 3


class UserError(ValueError):
    """A problem with the user's input. The page shows its message as is, without a traceback."""


def _fmt_phase(p: Fraction) -> str:
    return "0" if p == 0 else f"{p}π"


def diagram_problems(d: Diagram) -> list[str]:
    """Everything about this diagram that paritea's webs, push-out and equivalence code cannot handle."""
    nodes = list(d.node_indices())
    if not nodes:
        return ["The diagram is empty."]
    problems: list[str] = []
    try:
        inputs, outputs = d.io()
    except ValueError:
        inputs, outputs = [], []
        problems.append("No inputs or outputs are set.")
    if d.is_io_virtual():
        problems.append("Its inputs and outputs are virtual; paritea needs them to be boundary nodes.")
    else:
        declared = list(inputs) + list(outputs)
        if sorted(declared) != sorted(d.boundary_nodes()):
            problems.append("Its input and output lists must name every boundary node exactly once.")

    for n in nodes:
        kind = str(d.type(n))
        phase = d.phase(n)
        degree = len(d.incident_edges(n))
        if kind not in {"B", "Z", "X", "H"}:
            problems.append(f"Node {n} has an unknown type ({kind}).")
            continue
        if not isinstance(phase, int | Fraction):
            problems.append(f"Node {n} has phase {phase!r}; phases must be fractions (multiples of π).")
        elif phase < 0:
            problems.append(f"Node {n} has a negative phase ({_fmt_phase(Fraction(phase))}); use one between 0 and 2π.")
        elif kind in {"Z", "X"} and Fraction(phase).denominator > 2:
            problems.append(
                f"Node {n} has phase {_fmt_phase(Fraction(phase))}, which is not Clifford; "
                "paritea supports multiples of π/2."
            )
        elif kind == "H" and Fraction(phase) % 2 not in {0, 1}:
            problems.append(f"H box {n} has phase {_fmt_phase(Fraction(phase))}; only plain Hadamard boxes work.")
        if kind == "H" and degree != 2:
            problems.append(f"H box {n} has {degree} wires; it needs exactly 2.")
        if kind == "B" and degree != 1:
            problems.append(f"Boundary {n} has {degree} wires; every boundary needs exactly one.")

    seen = set()
    for s, t in d.edge_list():
        if s == t:
            problems.append(f"Node {s} has a wire to itself; remove it.")
        pair = (min(s, t), max(s, t))
        if pair in seen:
            problems.append(f"Nodes {s} and {t} are joined by more than one wire; paritea needs at most one.")
        seen.add(pair)
    return problems


def require_valid(d: Diagram) -> None:
    """Raise UserError listing the problems (at most a few) if paritea cannot analyse this diagram."""
    problems = diagram_problems(d)
    if problems:
        more = f" (and {len(problems) - MAX_LISTED} more)" if len(problems) > MAX_LISTED else ""
        raise UserError("paritea can't analyse this diagram: " + " ".join(problems[:MAX_LISTED]) + more)
