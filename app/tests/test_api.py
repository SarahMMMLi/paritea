"""Tests for the operations behind the web page (paritea_ui.api), run natively with the real dependencies."""

import json

import pytest
import pyzx as zx

from paritea_ui import api
from paritea_ui.examples import EXAMPLES


def call(op: str, **args):
    reply = json.loads(api.dispatch(op, json.dumps(args)))
    assert reply["ok"], reply.get("error")
    return reply["result"]


def error(op: str, **args) -> dict:
    reply = json.loads(api.dispatch(op, json.dumps(args)))
    assert not reply["ok"]
    return reply["error"]


@pytest.mark.parametrize("generator", [g["name"] for g in api.generators()])
def test_every_generator_builds_a_drawable_diagram_with_webs(generator: str) -> None:
    params = {p["key"]: p["default"] for p in next(g for g in api.generators() if g["name"] == generator)["params"]}

    result = call("pauli_webs", generator=generator, params=params)

    assert result["problems"] == []
    assert len(result["stabilisers"]) > 0
    assert {n["type"] for n in result["diagram"]["nodes"]} <= {"B", "Z", "X", "H"}
    assert len(result["diagram"]["edges"]) == result["summary"]["Edges"]


@pytest.mark.parametrize(
    ("generator", "params", "expected"),
    [
        ("Rotated surface code memory experiment", {"distance": 3, "rounds": 2}, (18, 8)),
        ("Rotated surface code memory experiment", {"distance": 5, "rounds": 2}, (50, 24)),
        ("Z-web grid", {"qubits": 2, "depth": 2}, (4, 1)),
    ],
)
def test_known_web_counts(generator: str, params: dict, expected: tuple[int, int]) -> None:
    result = call("pauli_webs", generator=generator, params=params)

    assert (len(result["stabilisers"]), len(result["regions"])) == expected


@pytest.mark.parametrize("example", list(EXAMPLES))
def test_examples_give_their_stated_answers(example: str) -> None:
    entry = call("diagram_example", example=example)

    result = call("webs", diagram=entry["id"])

    expected = (EXAMPLES[example].stabilising_webs, EXAMPLES[example].detecting_regions)
    assert (len(result["stabilisers"]), len(result["regions"])) == expected


def test_the_same_recipe_reuses_the_shelf_entry() -> None:
    params = {"qubits": 2, "depth": 3}
    first = call("diagram_generate", generator="Z-web grid", params=params)

    second = call("diagram_generate", generator="Z-web grid", params=params)

    assert first["id"] == second["id"]


def test_pyzx_export_imports_back_to_the_same_diagram() -> None:
    original = call("diagram_generate", generator="Z-web grid", params={"qubits": 3, "depth": 3})
    exported = call("diagram_export", diagram=original["id"], fmt="pyzx")

    imported = call("diagram_import", text=exported["text"], filename=exported["filename"])

    assert imported["summary"] == original["summary"]
    assert imported["notes"] == []  # the export declares inputs and outputs
    assert call("webs", diagram=imported["id"])["regions"] == call("webs", diagram=original["id"])["regions"]


def test_qasm_import_of_a_clifford_circuit() -> None:
    qasm = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\ns q[1];\n'

    imported = call("diagram_import", text=qasm, filename="bell.qasm")

    assert imported["summary"]["Inputs"] == imported["summary"]["Outputs"] == 2
    result = call("webs", diagram=imported["id"])
    assert (len(result["stabilisers"]), len(result["regions"])) == (4, 0)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\nt q[0];\n', "Clifford diagrams only"),
        ("{not json", "doesn't read as PyZX JSON"),
        ("hello", "Couldn't tell the file's format"),
        ("", "The file is empty"),
    ],
)
def test_bad_imports_are_explained(text: str, message: str) -> None:
    problem = error("diagram_import", text=text)

    assert problem["type"] == "UserError"
    assert message in problem["message"]


def test_a_diagram_paritea_cannot_analyse_is_explained_instead_of_crashing() -> None:
    g = zx.Graph()
    b0 = g.add_vertex(zx.VertexType.BOUNDARY, qubit=0, row=0)
    h = g.add_vertex(zx.VertexType.H_BOX, qubit=0, row=1)
    z1, z2 = g.add_vertex(zx.VertexType.Z, qubit=0, row=2), g.add_vertex(zx.VertexType.Z, qubit=1, row=2)
    b1 = g.add_vertex(zx.VertexType.BOUNDARY, qubit=0, row=3)
    g.add_edges([(b0, h), (h, z1), (h, z2), (z1, b1)])

    imported = call("diagram_import", text=g.to_json(), filename="h-box.json")

    assert imported["problems"] == ["H box 1 has 3 wires; it needs exactly 2."]
    assert "H box 1 has 3 wires" in error("webs", diagram=imported["id"])["message"]


def test_invalid_generator_parameters_are_explained() -> None:
    problem = error(
        "diagram_generate", generator="Rotated surface code, Shor syndrome extraction", params={"size": 4, "rounds": 1}
    )

    assert problem["message"] == "Size L must be one of [3, 5]."


def test_generated_python_reproduces_the_web_counts() -> None:
    result = call("pauli_webs", generator="Rotated surface code memory experiment", params={"distance": 3, "rounds": 2})
    namespace: dict = {}

    exec(result["code"].replace("print(", "counts = ("), namespace)  # noqa: S102

    assert namespace["counts"] == (len(result["stabilisers"]), len(result["regions"]))


@pytest.mark.parametrize("example", ["steane-state", "ring-6"])
def test_example_python_reproduces_the_diagram(example: str) -> None:
    entry = call("diagram_example", example=example)
    namespace: dict = {}

    exec(entry["code"], namespace)  # noqa: S102

    d = namespace["diagram"]
    assert (d.num_nodes(), d.num_edges()) == (entry["summary"]["Nodes"], entry["summary"]["Edges"])
