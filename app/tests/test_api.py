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


def _wires_touching(entry: dict, kind: str) -> list[int]:
    types = {n["id"]: n["type"] for n in entry["diagram"]["nodes"]}
    return [e for e, s, t in entry["diagram"]["edges"] if kind in (types[s], types[t])]


def test_noise_model_of_the_steane_demo() -> None:
    """The demo's state noise model: X, Y, Z flips on every edge except the wires of the four X spiders."""
    state = call("diagram_example", example="steane-state")

    noise = call(
        "noise_model", diagram=state["id"], weights={"x": 1, "y": 1, "z": 1}, noise_free=_wires_touching(state, "X")
    )

    assert noise["summary"]["Faults"] == 21  # 7 noisy wires, 3 faults each
    assert noise["summary"]["Noisy edges"] == 7
    assert noise["summary"]["Noise-free edges"] == 13
    assert noise["notes"] == []
    assert {pauli for edges, _ in noise["faults"] for _, pauli in edges} == {"X", "Y", "Z"}


def test_noise_model_without_noise_free_edges() -> None:
    circuit = call("diagram_example", example="steane-circuit")

    noise = call("noise_model", diagram=circuit["id"], weights={"x": 1, "y": 2, "z": 1}, noise_free=[])

    assert noise["summary"]["Faults"] == 3 * circuit["summary"]["Edges"]
    assert sorted({w for _, w in noise["faults"]}) == [1, 2]
    assert "weights differ" in noise["notes"][0]


@pytest.mark.parametrize(
    ("weights", "noise_free", "message"),
    [
        ({"x": 0, "y": 1, "z": 1}, [], "The X weight must be a whole number from 1 to 100."),
        ({"x": 1, "y": 1, "z": 101}, [], "The Z weight must be a whole number from 1 to 100."),
        ({"x": 1, "y": 1, "z": 1}, [9999], "has no edge 9999"),
    ],
)
def test_bad_noise_settings_are_explained(weights: dict, noise_free: list[int], message: str) -> None:
    state = call("diagram_example", example="steane-state")

    assert message in error("noise_model", diagram=state["id"], weights=weights, noise_free=noise_free)["message"]


def test_removing_a_diagram_removes_its_noise_models() -> None:
    d = call("diagram_generate", generator="Z-web grid", params={"qubits": 1, "depth": 1})
    noise = call("noise_model", diagram=d["id"], weights={"x": 1, "y": 1, "z": 1}, noise_free=[])

    removed = call("diagram_remove", diagram=d["id"])

    assert removed["noise"] == [noise["id"]]
    assert "not on the shelf" in error("noise_get", noise=noise["id"])["message"]


@pytest.mark.parametrize(
    ("make", "args"),
    [
        ("diagram_example", {"example": "steane-state"}),
        ("diagram_generate", {"generator": "Z-web grid", "params": {"qubits": 3, "depth": 2}}),
        (
            "diagram_generate",
            {"generator": "Rotated surface code memory experiment", "params": {"distance": 3, "rounds": 2}},
        ),
        ("diagram_generate", {"generator": "Steane code, Shor syndrome extraction", "params": {"rounds": 1}}),
    ],
)
def test_noise_python_reproduces_the_noise_model(make: str, args: dict, tmp_path, monkeypatch) -> None:
    entry = call(make, **args)
    free = _wires_touching(entry, "X")[:5]
    noise = call("noise_model", diagram=entry["id"], weights={"x": 1, "y": 1, "z": 1}, noise_free=free)
    exported = call("diagram_export", diagram=entry["id"], fmt="pyzx")  # some codes load the exact diagram from it
    (tmp_path / exported["filename"]).write_text(exported["text"])
    monkeypatch.chdir(tmp_path)
    namespace: dict = {}

    exec(noise["code"].replace("print(", "result = ("), namespace)  # noqa: S102

    model = namespace["noise_model"]
    assert model.num_faults() == noise["summary"]["Faults"]
    d = namespace["diagram"]
    endpoints = {e: (s, t) for e, s, t in entry["diagram"]["edges"]}
    assert sorted(d.get_edge_endpoints_by_index(e) for e in namespace["noise_free"]) == sorted(
        endpoints[e] for e in free
    )


@pytest.mark.parametrize(
    ("example", "free", "expected"),
    [
        # (faults, distinct effects, detected, undetected, no effect), worked out natively with paritea
        ("steane-state", "X", (21, 21, 0, 21, 0)),
        ("steane-circuit", None, (123, 44, 54, 60, 9)),
        ("ring-6", None, (36, 25, 12, 24, 0)),
    ],
)
def test_fault_propagation_known_answers(example: str, free: str | None, expected: tuple) -> None:
    entry = call("diagram_example", example=example)
    noise_free = _wires_touching(entry, free) if free else []
    noise = call("noise_model", diagram=entry["id"], weights={"x": 1, "y": 1, "z": 1}, noise_free=noise_free)

    result = call("propagation", noise=noise["id"])

    s = result["summary"]
    assert (s["Faults"], s["Distinct effects"], s["Detected"], s["Undetected"], s["No effect"]) == expected
    assert sum(e["faults"] for e in result["effects"]) == s["Faults"]
    labelled = {int(edge) for edge in result["labels"]}
    assert all(edge in labelled for e in result["effects"] for edge, _ in e["boundary"])


def test_fault_propagation_python_reproduces_the_effects() -> None:
    entry = call("diagram_example", example="steane-circuit")
    noise = call("noise_model", diagram=entry["id"], weights={"x": 1, "y": 1, "z": 1}, noise_free=[])
    result = call("propagation", noise=noise["id"])
    namespace: dict = {}

    exec(result["code"].replace("print(", "(lambda *a: None)("), namespace)  # noqa: S102

    assert len(list(namespace["pushed_out"].atomic_faults())) == result["summary"]["Distinct effects"]


SEMANTIC_PAIRS = [
    # (make A, make B, paritea's answer)
    (
        (
            "diagram_generate",
            {"generator": "Rotated surface code memory experiment", "params": {"distance": 3, "rounds": 1}},
        ),
        (
            "diagram_generate",
            {"generator": "Rotated surface code memory experiment", "params": {"distance": 3, "rounds": 2}},
        ),
        True,
    ),
    (("diagram_example", {"example": "two-half-pi"}), ("diagram_example", {"example": "one-pi"}), True),
    (("diagram_example", {"example": "two-half-pi"}), ("diagram_example", {"example": "one-half-pi"}), False),
    (("diagram_example", {"example": "steane-state"}), ("diagram_example", {"example": "steane-circuit"}), True),
    (("diagram_example", {"example": "star-6"}), ("diagram_example", {"example": "ring-6"}), True),
    (("diagram_example", {"example": "steane-state"}), ("diagram_example", {"example": "one-pi"}), False),
]


@pytest.mark.parametrize(("make_a", "make_b", "expected"), SEMANTIC_PAIRS)
def test_semantic_equivalence_agrees_with_paritea(make_a, make_b, expected) -> None:
    from paritea.equivalence import is_semantic_equivalence

    a, b = call(make_a[0], **make_a[1]), call(make_b[0], **make_b[1])

    result = call("semantic_equivalence", a=a["id"], b=b["id"])

    assert result["equivalent"] is expected
    da, db = api.SHELF.get(a["id"]).diagram, api.SHELF.get(b["id"]).diagram
    assert is_semantic_equivalence(da, db) is expected
    assert all(len(row) == result["a"]["inputs"] + result["a"]["outputs"] for row in result["a"]["rows"])


def test_semantic_python_reproduces_the_answer() -> None:
    a = call("diagram_example", example="two-half-pi")
    b = call("diagram_example", example="one-half-pi")
    result = call("semantic_equivalence", a=a["id"], b=b["id"])
    namespace: dict = {}

    exec(result["code"].replace("print(", "answer = ("), namespace)  # noqa: S102

    assert namespace["answer"] is result["equivalent"] is False


def _noise(example: str, free: str | None = None, weights: tuple[int, int, int] = (1, 1, 1)) -> str:
    entry = call("diagram_example", example=example)
    noise_free = _wires_touching(entry, free) if free else []
    w = dict(zip("xyz", weights, strict=True))
    return call("noise_model", diagram=entry["id"], weights=w, noise_free=noise_free)["id"]


@pytest.mark.parametrize(
    ("a", "b", "max_weight", "expected"),
    [
        # paritea's Steane demo: X 1, Y 2, Z 1 weights, the state's X-spider wires noise-free
        (lambda: _noise("steane-state", "X", (1, 2, 1)), lambda: _noise("steane-circuit", None, (1, 2, 1)), None, True),
        (lambda: _noise("steane-state", "X"), lambda: _noise("steane-circuit"), None, False),
        # bare diagrams get weight-1 faults on every edge, as in paritea's tests
        (
            lambda: call("diagram_example", example="two-half-pi")["id"],
            lambda: call("diagram_example", example="one-pi")["id"],
            None,
            True,
        ),
        (
            lambda: call("diagram_example", example="star-5")["id"],
            lambda: call("diagram_example", example="ring-5")["id"],
            None,
            True,
        ),
        (
            lambda: call("diagram_example", example="star-6")["id"],
            lambda: call("diagram_example", example="ring-6")["id"],
            None,
            False,
        ),
        (
            lambda: call("diagram_example", example="star-6")["id"],
            lambda: call("diagram_example", example="ring-6")["id"],
            1,
            True,
        ),
    ],
)
def test_fault_equivalence_known_answers(a, b, max_weight, expected) -> None:
    result = call("fault_equivalence", a=a(), b=b(), max_weight=max_weight)

    assert result["equivalent"] is expected


def test_fault_equivalence_reports_the_first_difference() -> None:
    star, ring = call("diagram_example", example="star-6"), call("diagram_example", example="ring-6")

    result = call("fault_equivalence", a=star["id"], b=ring["id"], max_weight=None, smallest=True)

    assert (result["equivalent"], result["first_difference"]) == (False, 2)


def test_fault_equivalence_explains_different_semantics_and_closed_diagrams() -> None:
    two, one = call("diagram_example", example="two-half-pi"), call("diagram_example", example="one-half-pi")
    closed = call("diagram_example", example="closed-surface-code")

    different = call("fault_equivalence", a=two["id"], b=one["id"])

    assert (different["equivalent"], different["semantic"]) == (False, False)
    assert "closed diagram" in error("fault_equivalence", a=closed["id"], b=closed["id"])["message"]
    assert "maximum fault weight" in error("fault_equivalence", a=two["id"], b=two["id"], max_weight=0)["message"]


def test_fault_equivalence_python_reproduces_the_answer() -> None:
    a, b = _noise("steane-state", "X", (1, 2, 1)), _noise("steane-circuit", None, (1, 2, 1))
    result = call("fault_equivalence", a=a, b=b)
    namespace: dict = {}

    exec(result["code"].replace("print(", "answer = ("), namespace)  # noqa: S102

    assert namespace["answer"] is result["equivalent"] is True


@pytest.mark.parametrize(
    ("preset", "expected"),
    [
        ({"distance": 3, "rounds": 2, "p": 0.001}, (16, 1, 107)),
        ({"distance": 3, "rounds": 3, "p": 0.01}, (24, 1, 219)),
    ],
)
def test_stim_dem_matches_stims_own_model(preset: dict, expected: tuple[int, int, int]) -> None:
    result = call("stim_dem", preset=preset)

    s = result["summary"]
    assert (s["Detectors"], s["Observables"], s["Error mechanisms"]) == expected
    c = result["comparison"]
    assert c["available"]
    assert (c["paritea"], c["stim"], c["only_paritea"], c["only_stim"]) == (expected[2], expected[2], 0, 0)
    assert c["worst_relative"] < 1e-9
    assert result["dem"].count("error(") == expected[2]


def test_stim_dem_of_pasted_text_and_its_python(tmp_path, monkeypatch) -> None:
    import stim

    text = str(
        stim.Circuit.generated(
            "surface_code:rotated_memory_z", distance=3, rounds=2, after_clifford_depolarization=0.01
        )
    )

    result = call("stim_dem", text=text, filename="memory.stim")

    assert result["comparison"]["only_paritea"] == result["comparison"]["only_stim"] == 0
    (tmp_path / "memory.stim").write_text(text)
    monkeypatch.chdir(tmp_path)
    namespace: dict = {}
    exec(result["code"].replace("print(dem)", "pass"), namespace)  # noqa: S102
    assert str(namespace["dem"]) == result["dem"]
    # The circuit's ZX diagram went on the shelf and can be analysed.
    assert call("webs", diagram=result["diagram"]["id"])["regions"]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("S 0\nM 0\n", "can't import this circuit"),
        ("H 0\nM 0\nNOT_AN_INSTRUCTION 0\n", "stim couldn't read this circuit"),
        ("", "Paste a stim circuit"),
    ],
)
def test_stim_dem_explains_bad_circuits(text: str, message: str) -> None:
    assert message in error("stim_dem", text=text)["message"]


def test_console_runs_paritea_code_like_a_notebook_cell() -> None:
    call("console_reset")

    first = call(
        "console_run", code="d = generate.surface_code_memory_experiment(distance=3, rounds=2)\nprint('built')"
    )
    second = call("console_run", code="stabs, regions = compute_pauli_webs(d)\nlen(stabs), len(regions)")

    assert first["stdout"] == "built\n"
    assert first["result"] is None
    assert second["result"] == "(18, 8)"  # the variable `d` survived between runs
    assert second["error"] is None


def test_console_reports_errors_and_panics_without_failing() -> None:
    syntax = call("console_run", code="def broken(:")
    runtime = call("console_run", code="1 / 0")
    panic = call("console_run", code="compute_pauli_webs(Diagram())")  # virtual IO makes paritea's Rust panic

    assert "SyntaxError" in syntax["error"]
    assert "ZeroDivisionError" in runtime["error"]
    assert "Rust core panicked" in panic["error"]


def test_console_works_on_copies_of_shelf_objects_and_can_add_diagrams() -> None:
    entry = call("diagram_example", example="steane-state")
    call("console_reset")

    result = call(
        "console_run", code=f'd = diagram("{entry["id"]}")\nd.add_node(NodeType.Z)\nput(d, "Steane plus a spider")'
    )

    new_id = result["result"].strip("'")
    assert api.SHELF.get(entry["id"]).diagram.num_nodes() == entry["summary"]["Nodes"]  # the shelf copy is untouched
    assert api.SHELF.get(new_id).diagram.num_nodes() == entry["summary"]["Nodes"] + 1
    assert any(e["id"] == new_id for e in result["shelf"])
