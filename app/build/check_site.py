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


def check_fault(page) -> list[str]:
    """Pairs from paritea's demo and tests, then a heavy run that is cancelled."""
    failures = []
    for index, label, expected, first in [(0, "Steane demo", True, None), (3, "star vs ring of 6", False, 2)]:
        page.goto(URL + "#/fault")
        page.evaluate("window.lastFault = null")
        page.click(f"[data-pair='{index}']")
        page.wait_for_function("window.lastFault !== null", timeout=180_000)
        result = page.evaluate("window.lastFault")
        page.screenshot(path=SHOTS / f"11-fault-{index}.png", full_page=True)
        got = (result.get("equivalent"), result.get("first_difference"))
        ok = got == (expected, first)
        print(f"{'OK  ' if ok else 'FAIL'} Fault: {label} -> {got} (expected {(expected, first)})")
        if not ok:
            failures.append(f"fault {label}: {got}")

    # Cancel: a distance-5 surface code compared with itself, with no limit, is far too slow to finish.
    page.goto(URL + "#/diagrams")
    page.click("[data-tab='generate']")
    page.select_option("#generator", "Rotated surface code memory experiment")
    page.fill("#p-distance", "5")
    page.fill("#p-rounds", "2")
    entry = build(page, "#build")
    page.goto(URL + "#/fault")
    page.select_option("#fault-a", entry["id"])
    page.select_option("#fault-b", entry["id"])
    page.check('input[name="limit"][value="none"]')
    page.evaluate("window.lastFault = null")
    page.click("#run")
    page.wait_for_timeout(1500)
    page.click("#cancel")
    page.wait_for_function("window.lastFault !== null", timeout=30_000)
    cancelled = page.evaluate("window.lastFault.cancelled === true")
    page.wait_for_function(READY, timeout=120_000)
    ready = page.inner_text("#engine-status").strip()
    ok = cancelled and ready.startswith("Ready")
    print(f"{'OK  ' if ok else 'FAIL'} Fault: cancel restarts the engine -> cancelled={cancelled}, then '{ready}'")
    if not ok:
        failures.append("cancel")
    return failures


def check_dem(page) -> list[str]:
    """stim's surface-code circuit, a pasted circuit and an unsupported one."""
    failures = []
    page.goto(URL + "#/dem")
    page.click("[data-source='preset']")
    page.fill("#dem-d", "3")
    page.fill("#dem-r", "2")
    page.fill("#dem-p", "0.001")
    page.evaluate("window.lastDem = null")
    page.click("#run")
    page.wait_for_function("window.lastDem !== null", timeout=180_000)
    result = page.evaluate("window.lastDem")
    page.screenshot(path=SHOTS / "12-dem.png", full_page=True)
    s, c = result["summary"], result["comparison"]
    got = (s["Detectors"], s["Observables"], s["Error mechanisms"], c.get("only_paritea"), c.get("only_stim"))
    ok = got == (16, 1, 107, 0, 0) and c["worst_relative"] < 1e-9
    print(f"{'OK  ' if ok else 'FAIL'} DEM: surface code d=3 r=2 -> {got}, worst {c.get('worst_relative')}")
    if not ok:
        failures.append(f"dem preset {got}")

    page.click("[data-source='text']")
    page.fill("#dem-text", "R 0 1\nCX 0 1\nX_ERROR(0.1) 1\nM 0 1\nDETECTOR rec[-1] rec[-2]\n")
    page.evaluate("window.lastDem = null")
    page.click("#run")
    page.wait_for_function("window.lastDem !== null", timeout=60_000)
    small = page.evaluate("window.lastDem")
    counts = (small["summary"]["Detectors"], small["summary"]["Error mechanisms"])
    ok = counts == (1, 1) and small["comparison"]["only_stim"] == 0
    print(f"{'OK  ' if ok else 'FAIL'} DEM: pasted circuit -> {small['summary']}")
    if not ok:
        failures.append("dem pasted")

    page.fill("#dem-text", "S 0\nM 0\n")
    page.click("#run")
    page.wait_for_selector("#results .alert-error", timeout=60_000)
    message = page.inner_text("#results .alert-error")
    ok = "can't import this circuit" in message
    print(f"{'OK  ' if ok else 'FAIL'} DEM: unsupported instruction explained")
    if not ok:
        failures.append(f"dem unsupported: {message}")
    return failures


def check_console(page) -> list[str]:
    """An example cell, a Rust panic reported as an error, and code handed over from a tool's code panel."""
    failures = []
    page.goto(URL + "#/console")
    page.select_option("#console-example", "0")
    page.evaluate("window.lastConsole = null")
    page.click("#console-run")
    page.wait_for_function("window.lastConsole !== null", timeout=120_000)
    first = page.evaluate("window.lastConsole")
    page.fill("#console-code", "compute_pauli_webs(Diagram())  # virtual IO: paritea's Rust core panics")
    page.evaluate("window.lastConsole = null")
    page.click("#console-run")
    page.wait_for_function("window.lastConsole !== null", timeout=60_000)
    panic = page.evaluate("window.lastConsole")
    page.screenshot(path=SHOTS / "13-console.png", full_page=True)
    checks = [
        ("example cell", first["result"] == "(18, 8)", first["result"]),
        ("Rust panic reported", "Rust core panicked" in (panic["error"] or ""), (panic["error"] or "")[:60]),
    ]
    page.goto(URL + "#/webs")
    page.click("[data-source='generate']")
    page.select_option("#generator", "Z-web grid")
    page.fill("#p-qubits", "2")
    page.fill("#p-depth", "2")
    page.evaluate("window.lastResult = null")
    page.click("#run")
    page.wait_for_function("window.lastResult !== null", timeout=60_000)
    page.click("[data-open-console]")
    page.wait_for_selector("#console-code")
    page.evaluate("window.lastConsole = null")
    page.click("#console-run")
    page.wait_for_function("window.lastConsole !== null", timeout=60_000)
    handed = page.evaluate("window.lastConsole")
    checks.append(("code panel opened in console", handed["stdout"].strip() == "4 1", handed["stdout"].strip()))
    for label, ok, got in checks:
        print(f"{'OK  ' if ok else 'FAIL'} Console: {label} -> {got}")
        if not ok:
            failures.append(f"console {label}: {got}")
    return failures


def check_leaving(page) -> list[str]:
    """A result that arrives after the visitor went to another page stays off that page, and still reaches the shelf."""
    pill = "document.getElementById('engine-status').dataset.state"
    page.goto(URL + "#/diagrams")
    page.wait_for_selector("#shelf .section-head")
    before = page.evaluate("document.querySelectorAll('#shelf .shelf-list li').length")
    page.evaluate("window.lastResult = null")
    page.goto(URL + "#/webs?generator=rotated-surface-code-memory-experiment&distance=7&rounds=5")
    page.wait_for_function(f"{pill} === 'busy'")
    page.goto(URL + "#/semantic")
    still_running = page.evaluate(f"{pill} === 'busy'")
    page.wait_for_function(f"{pill} === 'ready'", timeout=300_000)
    page.wait_for_timeout(300)
    leaked = page.evaluate("document.getElementById('results').textContent.includes('stabilising web')")
    leaked = leaked or page.evaluate("window.lastResult !== null")
    page.goto(URL + "#/diagrams")
    page.wait_for_selector("#shelf .section-head")
    grew = page.evaluate("document.querySelectorAll('#shelf .shelf-list li').length") - before
    ok = still_running and not leaked and grew == 1
    print(
        f"{'OK  ' if ok else 'FAIL'} Leaving mid-run: left while running {still_running}, result kept off the next "
        f"page {not leaked}, shelf grew by {grew}"
    )
    return [] if ok else ["a result arriving after leaving its page was shown elsewhere, or missed the shelf"]


AXE = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"
# Each page with a result on it, reached through links where possible (D1 and N1 come from the first two steps).
PAGES_WITH_RESULTS = [
    ("diagrams", "#/diagrams?example=steane-state", "window.lastEntry"),
    ("noise", "#/noise?diagram=D1", "#run"),
    ("propagation", "#/propagation?noise=N1&run=1", "#results .headline"),
    ("webs", "#/webs?generator=z-web-grid&qubits=3&depth=3", "window.lastResult"),
    ("semantic", "#/semantic", "[data-pair='2']"),
    ("fault", "#/fault", "[data-pair='1']"),
    ("dem", "#/dem?distance=3&rounds=2&p=0.001", "window.lastDem"),
    ("console", "#/console", "#console-run"),
    ("home", "#/", ".tool-card"),
]
# What to click on pages that need a click to show a result, and what then appears.
CLICKS = {
    "noise": ("#run", "#results .headline"),
    "semantic": ("[data-pair='2']", "#results .verdict"),
    "fault": ("[data-pair='1']", "#results .verdict"),
    "console": ("#console-run", "#console-output .cell"),
}


PHONE_WIDTH = 360  # a small phone; fonts on Linux (CI) run wider than on macOS, so this leaves some margin
# How far the page scrolls sideways, and which elements stick out (content that scrolls inside its own box is fine).
STICKING_OUT = """() => {
  const width = document.documentElement.clientWidth;
  const out = [...document.querySelectorAll('body *')]
    .filter((el) => el.getBoundingClientRect().right > width + 0.5 && !el.closest('.canvas-wrap, .table-wrap, pre'))
    .slice(0, 5)
    .map((el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')
      + [...el.classList].map((c) => '.' + c).join(''));
  return [document.documentElement.scrollWidth - width, out];
}"""


def check_accessibility(browser) -> list[str]:
    """axe-core finds no violations on any page, with a result showing, in light and dark mode; no page scrolls sideways
    on a phone."""
    failures = []
    for scheme in ["light", "dark"]:
        page = browser.new_page(viewport={"width": 1280, "height": 860}, reduced_motion="reduce", color_scheme=scheme)
        page.goto(URL)
        page.wait_for_function(READY, timeout=300_000)
        for name, link, ready in PAGES_WITH_RESULTS:
            page.evaluate("window.lastEntry = window.lastResult = window.lastDem = null")
            page.goto(URL + link)
            if ready.startswith("window."):
                page.wait_for_function(ready, timeout=120_000)
            else:
                page.wait_for_selector(ready, timeout=120_000)
            if name in CLICKS:
                page.click(CLICKS[name][0])
                page.wait_for_selector(CLICKS[name][1], timeout=120_000)
            page.mouse.move(0, 0)  # no hover states
            if page.evaluate("typeof axe") == "undefined":
                page.add_script_tag(url=AXE)
            violations = page.evaluate(
                """async () => (await axe.run(document, { resultTypes: ['violations'] })).violations
                  .map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(', ')}`)"""
            )
            page.set_viewport_size({"width": PHONE_WIDTH, "height": 800})
            sideways, sticking_out = page.evaluate(STICKING_OUT)
            page.set_viewport_size({"width": 1280, "height": 860})
            ok = not violations and sideways <= 0
            print(
                f"{'OK  ' if ok else 'FAIL'} Accessibility ({scheme}): {name}: {violations or 'no axe violations'}"
                + ("" if sideways <= 0 else f", scrolls sideways on a phone by {sideways} px: {sticking_out}")
            )
            if not ok:
                failures.append(f"accessibility of {name} ({scheme}): {violations}, sideways {sideways}")
        page.close()
    return failures


def check_links(browser) -> tuple[list[str], list[str]]:
    """Open shared links in a fresh tab: each must recreate its result and keep its address; bad links are explained."""
    failures = []
    origin = "/".join(URL.split("/")[:3])
    context = browser.new_context(viewport={"width": 1280, "height": 860}, reduced_motion="reduce")
    context.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
    page = context.new_page()
    logs: list[str] = []
    page.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
    page.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))

    def open_link(link: str, result: str) -> dict:
        if page.url.startswith(URL):
            page.evaluate(f"window.{result} = null")
        page.goto(URL + link)
        page.wait_for_function(f"window.{result}", timeout=300_000)  # the first link also waits for the engine
        return page.evaluate(f"window.{result}")

    def report(name: str, got: object, expected: object, link: str) -> None:
        address = "#" + page.url.split("#", 1)[1]
        ok = got == expected and address == link
        print(f"{'OK  ' if ok else 'FAIL'} Link: {name} -> {got}, address kept: {address == link}")
        if not ok:
            failures.append(f"link {name}: {got} != {expected}, or address {address} != {link}")

    link = "#/webs?generator=z-web-grid&qubits=3&depth=3"
    result = open_link(link, "lastResult")
    report("webs of a Z-web grid 3x3 (cold start)", (len(result["stabilisers"]), len(result["regions"])), (6, 4), link)
    page.click("[data-copy-link]")
    copied = page.evaluate("navigator.clipboard.readText()")
    ok = copied == URL + link
    print(f"{'OK  ' if ok else 'FAIL'} Link: Copy link copies {copied}")
    if not ok:
        failures.append(f"Copy link copied {copied}")

    result = open_link("#/webs?generator=z-web-grid", "lastResult")
    counts = (len(result["stabilisers"]), len(result["regions"]))
    report("missing parameters take their defaults", counts, (4, 1), "#/webs?generator=z-web-grid&qubits=2&depth=2")

    link = "#/webs?example=steane-state"
    result = open_link(link, "lastResult")
    report("webs of an example", (len(result["stabilisers"]), len(result["regions"])), (7, 0), link)

    link = "#/diagrams?generator=random-clifford-diagram&qubits=3&spiders=10&seed=1"
    entry = open_link(link, "lastEntry")
    report("random Clifford diagram, seed 1", entry["summary"]["Nodes"], 29, link)

    link = "#/diagrams?example=ring-5"
    entry = open_link(link, "lastEntry")
    report("example diagram", entry["source"], {"kind": "example", "example": "ring-5"}, link)

    link = "#/dem?distance=3&rounds=2&p=0.001"
    dem = open_link(link, "lastDem")
    s = dem["summary"]
    report("DEM of the surface code", (s["Detectors"], s["Observables"], s["Error mechanisms"]), (16, 1, 107), link)

    def explained(name: str, link: str, selector: str, text: str) -> None:
        page.goto(URL + link)
        page.wait_for_selector(f"{selector}:has-text('{text}')", timeout=60_000)
        injected = page.evaluate("window.pwned === 1")
        ok = not injected
        print(f"{'OK  ' if ok else 'FAIL'} Link: {name} explained" + (" (and injected HTML!)" if injected else ""))
        if not ok:
            failures.append(f"link {name}: injected HTML ran")

    explained("unknown generator", "#/webs?generator=nope", ".alert-error", 'There is no generator called "nope"')
    explained("unknown example", "#/diagrams?example=nope", ".alert-error", 'There is no example called "nope"')
    explained(
        "crafted parameter",
        "#/webs?generator=z-web-grid&qubits=%22%3E%3Cimg%20src%3Dx%20onerror%3Dwindow.pwned%3D1%3E",
        ".alert-error",
        "Qubits must be a whole number from 1 to 10.",
    )
    explained("another tab's shelf", "#/webs?diagram=D99", ".alert-preview", "no D99 on your shelf")
    page.screenshot(path=SHOTS / "14-links.png", full_page=True)
    context.close()
    return failures, logs


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
        failures += check_dem(page)
        failures += check_console(page)
        failures += check_fault(page)
        failures += check_leaving(page)
        link_failures, link_logs = check_links(browser)
        failures += link_failures
        logs += link_logs
        failures += check_accessibility(browser)

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
