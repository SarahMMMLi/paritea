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


def main() -> int:
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 860})
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

        # Show a detecting region on the first example for a screenshot.
        run_case(page, *CASES[0])
        page.click(".segmented button[data-kind='regions']")
        page.click("#next")
        page.screenshot(path=SHOTS / "4-region.png", full_page=True)

        # Preview mode works without the engine.
        preview = browser.new_page(viewport={"width": 1280, "height": 860})
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
