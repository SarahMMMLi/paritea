"""Compute a few Pauli-webs results natively, so the page can still show them if the browser engine cannot start.

They also serve as the reference that the in-browser results are checked against.
Run from app/: ``uv run python build/precompute.py``.
"""

import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

from paritea_ui.api import generators, pauli_webs  # noqa: E402

EXAMPLES = [
    ("Rotated surface code memory experiment", {"distance": 3, "rounds": 1}),
    ("Rotated surface code memory experiment", {"distance": 3, "rounds": 2}),
    ("Rotated surface code memory experiment", {"distance": 5, "rounds": 2}),
    ("Steane code, Shor syndrome extraction", {"rounds": 1}),
    ("Steane code, Shor syndrome extraction", {"rounds": 2}),
    ("Z-web grid", {"qubits": 2, "depth": 2}),
    ("Z-web grid", {"qubits": 3, "depth": 3}),
]


def key(generator: str, params: dict[str, int]) -> str:
    return generator + "|" + ",".join(f"{k}={params[k]}" for k in sorted(params))


if __name__ == "__main__":
    out = APP / "web" / "data"
    out.mkdir(parents=True, exist_ok=True)
    index = {}
    for i, (generator, params) in enumerate(EXAMPLES):
        result = pauli_webs(generator, params)
        name = f"webs-{i}.json"
        (out / name).write_text(json.dumps(result))
        index[key(generator, params)] = name
        print(f"{key(generator, params)}: {len(result['stabilisers'])} webs, {len(result['regions'])} regions")
    (out / "index.json").write_text(json.dumps({"generators": generators(), "results": index}, indent=2) + "\n")
