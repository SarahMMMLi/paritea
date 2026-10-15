"""The browser's stand-in for galois.GF2 must behave like the real one wherever paritea uses it."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest
from galois import GF2 as RealGF2

_spec = importlib.util.spec_from_file_location(
    "gf2_standin", Path(__file__).parent.parent / "paritea_ui" / "compat" / "_stubs" / "galois" / "__init__.py"
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
StandIn = _module.GF2


def _random(seed: int, shape: tuple[int, int] | None = None) -> np.ndarray:
    rng = np.random.default_rng(seed)
    rows, cols = shape or (int(rng.integers(1, 14)), int(rng.integers(1, 18)))
    return rng.integers(0, 2, size=(rows, cols))


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("eye", ["left", "right"])
def test_row_reduce_matches_galois(seed: int, eye: str) -> None:
    a = _random(seed)

    np.testing.assert_array_equal(
        np.asarray(StandIn(a).row_reduce(eye=eye)), np.asarray(RealGF2(a).row_reduce(eye=eye))
    )


@pytest.mark.parametrize("seed", range(20))
def test_arithmetic_matches_galois(seed: int) -> None:
    a, b = _random(seed, (6, 9)), _random(seed + 1000, (6, 9))
    m = _random(seed + 2000, (9, 5))
    columns = [3, 0, 7]
    pivots = _random(seed + 3000, (len(columns), 9))  # shaped like paritea's rref

    for ours, theirs in [
        (StandIn(a) + StandIn(b), RealGF2(a) + RealGF2(b)),
        (StandIn(a) - StandIn(b), RealGF2(a) - RealGF2(b)),
        (StandIn(a) @ StandIn(m), RealGF2(a) @ RealGF2(m)),
        (StandIn(a)[:, columns], RealGF2(a)[:, columns]),
        # fault_equivalence.py: compiled_faults + compiled_faults[:, idx] @ rref
        (
            StandIn(a) + StandIn(a)[:, columns] @ StandIn(pivots),
            RealGF2(a) + RealGF2(a)[:, columns] @ RealGF2(pivots),
        ),
    ]:
        np.testing.assert_array_equal(np.asarray(ours), np.asarray(theirs))
    assert StandIn(a).row_reduce().argmax(axis=1).tolist() == RealGF2(a).row_reduce().argmax(axis=1).tolist()
    assert StandIn(a)[0].tolist() == RealGF2(a)[0].tolist()


def test_construction_like_paritea() -> None:
    zeros = StandIn.Zeros(6)
    zeros[2] = 1
    rows = StandIn([zeros, StandIn.Zeros(6)])
    stacked = StandIn(np.vstack([rows, [zeros]]))

    assert zeros.tolist() == [0, 0, 1, 0, 0, 0]
    assert stacked.shape == (3, 6)
    assert stacked.dtype == np.uint8
    assert StandIn.Zeros((2, 3)).shape == (2, 3)
    with pytest.raises(ValueError, match="0 and 1"):
        StandIn([0, 2])
