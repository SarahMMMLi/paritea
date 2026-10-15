"""Open the page in headless Chromium, compute Pauli webs in the browser and compare with the native results.

Usage (with Playwright installed): python build/check_site.py [URL] [SCREENSHOT_DIR]
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = Path(__file__).resolve().parent.parent
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
SHOTS = Path(sys.argv[2]) if len(sys.argv) > 2 else APP / "build" / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)

CASES = [
    ("Rotated surface code memory experiment", {"distance": 3, "rounds": 2}),
    ("Z-web grid", {"qubits": 2, "depth": 2}),
    ("Steane code, Shor syndrome extraction", {"rounds": 1}),
    ("Rotated surface code memory experiment", {"distance": 5, "rounds": 2}),
]
READY = "['ready', 'preview'].includes(document.getElementById('engine-status').dataset.state)"


def reference(generator: str, params: dict[str, int]) -> dict:
    index = json.loads((APP / "web/data/index.json").read_text())["results"]
    key = generator + "|" + ",".join(f"{k}={params[k]}" for k in sorted(params))
    return json.loads((APP / "web/data" / index[key]).read_text())


def run_case(page, generator: str, params: dict[str, int]) -> dict:
    page.select_option("#generator", generator)
    for k, v in params.items():
        page.fill(f"#p-{k}", str(v))
    page.evaluate("window.lastResult = null")
    page.click("#run")
    page.wait_for_function("window.lastResult !== null", timeout=180_000)
    return page.evaluate("window.lastResult")


def build(page, click: str) -> dict:
    page.evaluate("window.lastEntry = null")
    page.click(click)
    page.wait_for_function("window.lastEntry !== null", timeout=120_000)
    return page.evaluate("window.lastEntry")


def webs_of_shown_diagram(page) -> tuple[int, int]:
    page.evaluate("window.lastResult = null")
    page.click("text=Compute Pauli webs →")
    page.wait_for_function("window.lastResult !== null", timeout=120_000)
    result = page.evaluate("window.lastResult")
    return len(result["stabilisers"]), len(result["regions"])


def check_diagrams(page) -> list[str]:
    """Generate, open an example and import a file on the Diagrams page, then compute their webs."""
    failures = []
    cases = [
        ("Z-web grid 3x3", ("generate", "Z-web grid", {"qubits": 3, "depth": 3}), (6, 4)),
        ("Steane preparation circuit", ("example", "steane-circuit"), (7, 1)),
        (
            "Random Clifford, seed 1",
            ("generate", "Random Clifford diagram", {"qubits": 3, "spiders": 10, "seed": 1}),
            (6, 0),
        ),
        ("Sample QASM circuit", ("import",), (4, 0)),
    ]
    for i, (label, how, expected) in enumerate(cases):
        page.goto(URL + "#/diagrams")
        if how[0] == "generate":
            page.click("[data-tab='generate']")
            page.select_option("#generator", how[1])
            for k, v in how[2].items():
                page.fill(f"#p-{k}", str(v))
            entry = build(page, "#build")
        elif how[0] == "example":
            page.click("[data-tab='examples']")
            entry = build(page, f"[data-example='{how[1]}']")
        else:
            page.click("[data-tab='import']")
            page.click("#sample")
            entry = build(page, "#import-run")
        page.screenshot(path=SHOTS / f"6-diagram-{i}.png", full_page=True)
        got = webs_of_shown_diagram(page)
        ok = got == expected and not entry["problems"]
        size = f"{entry['id']}, {entry['summary']['Nodes']} nodes"
        print(f"{'OK  ' if ok else 'FAIL'} Diagrams: {label} -> {size}; webs {got}")
        if not ok:
            failures.append(f"{label}: webs {got} != {expected} or problems {entry['problems']}")

    # A non-Clifford circuit is explained, not crashed on.
    page.goto(URL + "#/diagrams")
    page.click("[data-tab='import']")
    page.fill("#import-text", 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\nt q[0];\n')
    page.click("#import-run")
    page.wait_for_selector("#results .alert-error", timeout=60_000)
    message = page.inner_text("#results .alert-error")
    ok = "Clifford" in message
    print(f"{'OK  ' if ok else 'FAIL'} Diagrams: non-Clifford QASM explained: {message.splitlines()[0][:90]}")
    if not ok:
        failures.append(f"non-Clifford import message: {message}")

    # Downloads: PyZX JSON and SVG of the shown diagram.
    page.click("[data-tab='examples']")
    build(page, "[data-example='steane-state']")
    with page.expect_download() as download:
        page.click("[data-export='pyzx']")
    pyzx = json.loads(Path(download.value.path()).read_text())
    with page.expect_download() as download:
        page.click("[data-export='svg']")
    svg = Path(download.value.path()).read_text()
    ok = pyzx.get("version") == 2 and len(pyzx["inputs"]) + len(pyzx["outputs"]) == 7 and svg.startswith("<svg")
    print(f"{'OK  ' if ok else 'FAIL'} Diagrams: downloads (PyZX JSON with {len(pyzx['outputs'])} outputs, SVG)")
    if not ok:
        failures.append("downloads")
    shelf = page.locator(".shelf-list li").count()
    print(f"{'OK  ' if shelf >= 5 else 'FAIL'} Diagrams: shelf lists {shelf} diagrams")
    if shelf < 5:
        failures.append(f"shelf lists {shelf}")
    page.screenshot(path=SHOTS / "7-shelf.png", full_page=True)
    return failures


def settle(page) -> None:
    """Wait until the page has stopped scrolling (results scroll smoothly into view)."""
    page.evaluate(
        """() => new Promise((resolve) => {
          let last = -1, still = 0;
          const tick = () => {
            still = window.scrollY === last ? still + 1 : 0;
            last = window.scrollY;
            if (still > 5) resolve(); else requestAnimationFrame(tick);
          };
          tick();
        })"""
    )


def build_noise(page) -> dict:
    page.evaluate("window.lastNoise = null")
    page.click("#run")
    page.wait_for_function("window.lastNoise !== null", timeout=60_000)
    return page.evaluate("window.lastNoise")


def check_noise(page) -> list[str]:
    """The Steane demo's noise model, an edge picked on the drawing, and a preset."""
    failures = []
    page.goto(URL + "#/noise")
    page.click("#use-steane")
    count = "(document.getElementById('picked-count')?.textContent ?? '')"
    page.wait_for_function(f"{count}.startsWith('13 noise-free')", timeout=60_000)
    steps = [("demo: X-spider wires noise-free", None, 21)]
    noise = build_noise(page)
    got = [(steps[0][0], noise["summary"]["Faults"])]
    settle(page)
    page.locator("#pick-canvas .hit").first.click()  # switch one wire
    page.wait_for_function(f"!{count}.startsWith('13 noise-free')", timeout=10_000)
    picked = page.evaluate(count)
    toggled = build_noise(page)["summary"]["Faults"]
    steps.append(("one wire clicked", picked, 24 if picked.startswith("12") else 18))
    got.append((steps[1][0], toggled))
    page.click("[data-preset='none']")
    steps.append(("preset: none", None, 60))
    got.append((steps[2][0], build_noise(page)["summary"]["Faults"]))
    page.screenshot(path=SHOTS / "8-noise.png", full_page=True)
    for (label, _, expected), (_, faults) in zip(steps, got, strict=True):
        ok = faults == expected
        print(f"{'OK  ' if ok else 'FAIL'} Noise: {label} -> {faults} faults (expected {expected})")
        if not ok:
            failures.append(f"noise {label}: {faults} != {expected}")
    listed = page.locator("#noise-shelf .shelf-list li").count()
    print(f"{'OK  ' if listed == 3 else 'FAIL'} Noise: shelf lists {listed} noise models")
    if listed != 3:
        failures.append(f"noise shelf lists {listed}")
    return failures


def check_propagation(page) -> list[str]:
    """The Steane preparation circuit with unit noise on every edge, pushed out."""
    page.goto(URL + "#/propagation")
    page.evaluate("window.lastPropagation = null")
    page.click("#use-demo")
    page.wait_for_function("window.lastPropagation !== null", timeout=120_000)
    s = page.evaluate("window.lastPropagation.summary")
    got = (s["Faults"], s["Distinct effects"], s["Detected"], s["Undetected"], s["No effect"])
    expected = (123, 44, 54, 60, 9)  # paritea natively, see tests/test_api.py
    page.screenshot(path=SHOTS / "9-propagation.png", full_page=True)
    ok = got == expected
    print(f"{'OK  ' if ok else 'FAIL'} Propagation: Steane circuit {got} (expected {expected})")
    return [] if ok else [f"propagation {got} != {expected}"]


def check_semantic(page) -> list[str]:
    """Pairs from paritea's tests: the surface code with 1 and 2 rounds, and two pi/2 spiders vs one."""
    failures = []
    for index, label, expected in [(0, "surface code 1 vs 2 rounds", True), (2, "two pi/2 vs one pi/2", False)]:
        page.goto(URL + "#/semantic")
        page.evaluate("window.lastSemantic = null")
        page.click(f"[data-pair='{index}']")
        page.wait_for_function("window.lastSemantic !== null", timeout=120_000)
        got = page.evaluate("window.lastSemantic.equivalent")
        page.screenshot(path=SHOTS / f"10-semantic-{index}.png", full_page=True)
        ok = got is expected
        print(f"{'OK  ' if ok else 'FAIL'} Semantic: {label} -> {got} (expected {expected})")
        if not ok:
            failures.append(f"semantic {label}: {got}")
    return failures


def main() -> int:
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 860}, reduced_motion="reduce")
        logs: list[str] = []
        page.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
        page.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))

        start = time.time()
        page.goto(URL)
        page.screenshot(path=SHOTS / "1-home-loading.png")
        page.wait_for_function(READY, timeout=300_000)
        print(f"Engine: {page.inner_text('#engine-status').strip()} after {time.time() - start:.1f} s")
        page.screenshot(path=SHOTS / "2-home-ready.png", full_page=True)

        page.goto(URL + "#/webs")
        page.wait_for_selector("#generator option", state="attached")
        for i, (generator, params) in enumerate(CASES):
            got = run_case(page, generator, params)
            want = reference(generator, params)
            counts = (len(got["stabilisers"]), len(got["regions"]), got["summary"])
            expected = (len(want["stabilisers"]), len(want["regions"]), want["summary"])
            same_webs = got["stabilisers"] == want["stabilisers"] and got["regions"] == want["regions"]
            ok = counts == expected
            seconds = got["seconds"]["build"] + got["seconds"]["webs"]
            print(
                f"{'OK  ' if ok else 'FAIL'} {generator} {params}: {counts[0]} webs / {counts[1]} regions "
                f"in {seconds:.3f} s (browser); "
                f"identical webs to native: {same_webs}"
            )
            if not ok:
                failures.append(f"{generator} {params}: browser {counts} != native {expected}")
            page.screenshot(path=SHOTS / f"3-webs-{i}.png", full_page=True)

        failures += check_diagrams(page)
        failures += check_noise(page)
        failures += check_propagation(page)
        failures += check_semantic(page)

        # Show a detecting region on the first example for a screenshot.
        page.goto(URL + "#/webs")
        page.click("[data-source='generate']")
        run_case(page, *CASES[0])
        page.click(".segmented button[data-kind='regions']")
        page.click("#next")
        page.screenshot(path=SHOTS / "4-region.png", full_page=True)

        # Preview mode works without the engine.
        preview = browser.new_page(viewport={"width": 1280, "height": 860}, reduced_motion="reduce")
        preview.goto(URL + "?engine=precomputed#/webs")
        preview.wait_for_function(READY, timeout=60_000)
        preview.wait_for_selector("#generator option", state="attached")
        got = run_case(preview, *CASES[0])
        webs, regions = len(got["stabilisers"]), len(got["regions"])
        print(f"Preview mode: {webs} webs / {regions} regions, precomputed={got.get('precomputed')}")
        preview.screenshot(path=SHOTS / "5-preview.png", full_page=True)
        browser.close()

    problems = [line for line in logs if line.startswith(("error", "pageerror"))]
    print("Console errors:", problems or "none")
    for f in failures:
        print("FAILED:", f)
    return 1 if failures or problems else 0


if __name__ == "__main__":
    sys.exit(main())
