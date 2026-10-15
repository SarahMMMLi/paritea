"""The Python console: run code in the engine with paritea ready to use, like a notebook cell.

Shelf objects are handed out as copies, so console code cannot silently change what the tools work on.
"""

import ast
import contextlib
import io
import time
import traceback
from copy import deepcopy
from typing import Any

from paritea.diagram import Diagram
from paritea.noise import NoiseModel

from paritea_ui.core import is_rust_panic
from paritea_ui.session import SHELF
from paritea_ui.validate import UserError

MAX_OUTPUT_CHARS = 200_000
PRELUDE = """\
from fractions import Fraction

import numpy as np
import pyzx as zx
import paritea
from paritea import Pauli, PauliString, build_flip_operators, generate, push_out
from paritea.diagram import Diagram, NodeType
from paritea.equivalence import is_fault_equivalence, is_semantic_equivalence
from paritea.glue.pyzx import from_pyzx, to_pyzx
from paritea.noise import Fault, NoiseModel
from paritea.web import compute_pauli_webs
"""


def diagram(entry_id: str) -> Diagram:
    """A copy of a diagram on the shelf, e.g. diagram("D1")."""
    return deepcopy(SHELF.get(entry_id).diagram)


def noise_model(noise_id: str) -> NoiseModel:
    """A copy of a noise model on the shelf (with its own copy of the diagram), e.g. noise_model("N1")."""
    noise = SHELF.get_noise(noise_id)
    d = deepcopy(noise.model.diagram)
    return NoiseModel(d, {fault: list(values) for fault, values in noise.model.atomic_faults_with_values()})


def put(d: Diagram, name: str = "Made in the console") -> str:
    """Put a copy of a diagram on the shelf so the tools can use it; returns its id."""
    if not isinstance(d, Diagram):
        raise TypeError("put() takes a paritea Diagram.")
    try:
        d.io()
    except ValueError:
        d.infer_io_from_boundaries()
    entry = SHELF.add(
        deepcopy(d),
        name=name,
        source={"kind": "console"},
        code="# This diagram was made in the page's Python console.\n",
    )
    return entry.id


_namespace: dict[str, Any] | None = None


def _fresh_namespace() -> dict[str, Any]:
    namespace: dict[str, Any] = {"__name__": "__console__", "diagram": diagram, "noise_model": noise_model, "put": put}
    exec(PRELUDE, namespace)  # noqa: S102
    return namespace


def reset() -> None:
    """Forget every variable defined in the console."""
    global _namespace
    _namespace = None


def run(code: str) -> dict[str, Any]:
    """Run code; returns its printed output, the value of its last line (if an expression) and any error."""
    global _namespace
    if _namespace is None:
        _namespace = _fresh_namespace()
    try:
        tree = ast.parse(code, "<console>", "exec")
    except SyntaxError:
        return {"stdout": "", "result": None, "error": traceback.format_exc(limit=0), "seconds": 0}
    last = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
    out = io.StringIO()
    result, error = None, None
    start = time.perf_counter()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            exec(compile(tree, "<console>", "exec"), _namespace)  # noqa: S102
            if last is not None:
                value = eval(compile(ast.Expression(last.value), "<console>", "eval"), _namespace)  # noqa: S307
                result = None if value is None else repr(value)
    except BaseException as exc:  # Rust panics derive from BaseException; so do exit() and KeyboardInterrupt
        if isinstance(exc, KeyboardInterrupt):
            raise
        name = "paritea's Rust core panicked" if is_rust_panic(exc) else None
        user_frames = exc.__traceback__.tb_next if exc.__traceback__ else None  # skip this function's own frame
        error = (name + ":\n" if name else "") + "".join(traceback.format_exception(type(exc), exc, user_frames))
    stdout = out.getvalue()
    if len(stdout) > MAX_OUTPUT_CHARS:
        stdout = stdout[:MAX_OUTPUT_CHARS] + f"\n… (output cut at {MAX_OUTPUT_CHARS} characters)"
    return {"stdout": stdout, "result": result, "error": error, "seconds": time.perf_counter() - start}


__all__ = ["UserError", "diagram", "noise_model", "put", "reset", "run"]
