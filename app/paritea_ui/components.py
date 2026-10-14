"""Streamlit building blocks shared by the pages: caching, error reporting and input widgets."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import NoReturn

import streamlit as st

from paritea_ui.core import GENERATORS, PauliWebs, build_diagram, is_rust_panic, pauli_webs

# A hashable description of a diagram: (generator name, ((param, value), ...)). Cached functions take this instead of
# a Diagram, so the cache key is cheap and stable.
type DiagramSpec = tuple[str, tuple[tuple[str, int], ...]]


@contextmanager
def report_errors(action: str) -> Iterator[None]:
    """Show any error raised inside the block (including Rust panics) on the page, then stop this script run."""
    try:
        yield
    except Exception as exc:
        _show_failure(action, exc)
    except BaseException as exc:
        if not is_rust_panic(exc):
            raise  # Streamlit's own control flow (st.rerun, st.stop) and KeyboardInterrupt must pass through
        _show_failure(action, exc)


def _show_failure(action: str, exc: BaseException) -> NoReturn:
    st.error(f"**{action} failed.** `{type(exc).__name__}`: {exc}")
    st.stop()


def diagram_picker(key: str) -> DiagramSpec:
    """Inputs for choosing a generator and its parameters. ``key`` keeps several pickers on one page apart."""
    name = st.selectbox("Diagram", list(GENERATORS), key=f"{key}-generator")
    generator = GENERATORS[name]
    st.caption(generator.description)
    params = tuple(
        (
            param,
            st.number_input(
                spec.label,
                min_value=spec.min_value,
                max_value=spec.max_value,
                value=spec.default,
                help=spec.help or None,
                key=f"{key}-{name}-{param}",
            ),
        )
        for param, spec in generator.params.items()
    )
    return name, params


# st.cache_data hands every caller its own unpickled copy, so a paritea function that mutates a diagram (several do,
# e.g. Diagram.io_sorted or NoiseModel.compress) cannot corrupt the cache or another user's session.
# Cache a diagram together with everything computed from it: rebuilding the diagram can renumber its edges.
@st.cache_data(max_entries=32, show_spinner="Building diagram and computing Pauli webs…")
def cached_pauli_webs(spec: DiagramSpec) -> PauliWebs:
    name, params = spec
    return pauli_webs(build_diagram(name, **dict(params)))
