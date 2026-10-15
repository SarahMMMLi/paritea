"""Check the browser's stand-ins for galois and recordclass against paritea's own test suite.

The browser cannot install galois (it needs numba) or recordclass (a C extension), so the page's engine uses the
stand-ins in paritea_ui/compat. This runs the library's tests (../tests) twice in this environment, once with the real
packages and once with the stand-ins in their place, and fails if any test's outcome differs. Tests that fail either
way (for instance because this environment has a newer pyzx than the library pins) are listed but don't count against
the stand-ins. Run from app/: ``uv run python build/test_with_stand_ins.py``.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree

APP = Path(__file__).resolve().parent.parent
REPO = APP.parent
STUBS = APP / "paritea_ui" / "compat" / "_stubs"
REPLACED = ["galois", "recordclass"]


def outcomes(report: Path) -> dict[str, str]:
    """Test id -> passed, failed or skipped, from a JUnit XML report."""
    result = {}
    for case in ElementTree.parse(report).getroot().iter("testcase"):  # noqa: S314 (pytest wrote this file)
        kinds = {child.tag for child in case}
        outcome = "failed" if kinds & {"failure", "error"} else "skipped" if "skipped" in kinds else "passed"
        result[f"{case.get('classname')}::{case.get('name')}"] = outcome
    return result


def run_tests(report: Path, env: dict[str, str], traceback: str) -> dict[str, str]:
    command = [sys.executable, "-m", "pytest", str(REPO / "tests"), f"--rootdir={REPO}", "-p", "no:cacheprovider"]
    subprocess.run([*command, "-q", f"--tb={traceback}", f"--junitxml={report}"], env=env, cwd=REPO, check=False)  # noqa: S603
    return outcomes(report)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        stand_ins = Path(tmp) / "stand-ins"
        for name in REPLACED:
            shutil.copytree(STUBS / name, stand_ins / name)
        # PYTHONPATH comes before site-packages, so the stand-ins win over the installed packages.
        env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join(filter(None, [str(stand_ins), os.environ.get("PYTHONPATH")])),
        }
        check = f"import {', '.join(REPLACED)}; print({', '.join(f'{name}.__file__' for name in REPLACED)})"
        files = subprocess.run([sys.executable, "-c", check], env=env, capture_output=True, text=True, check=True)  # noqa: S603
        if any(not Path(f).resolve().is_relative_to(stand_ins.resolve()) for f in files.stdout.split()):
            print(f"The stand-ins were not the modules imported: {files.stdout.strip()}")
            return 1

        print("== paritea's tests with the real galois and recordclass", flush=True)
        real = run_tests(Path(tmp) / "real.xml", dict(os.environ), "no")
        print(f"== paritea's tests with the browser's stand-ins for {' and '.join(REPLACED)}", flush=True)
        stood_in = run_tests(Path(tmp) / "stand-ins.xml", env, "short")

    differ = sorted(t for t in real.keys() | stood_in.keys() if real.get(t) != stood_in.get(t))
    either_way = sorted(t for t in real if real[t] == "failed" and stood_in.get(t) == "failed")
    print(f"\n{len(real)} tests; {len(differ)} with a different outcome under the stand-ins.")
    for test in either_way:
        print(f"  fails either way (not the stand-ins): {test}")
    for test in differ:
        was, now = real.get(test, "missing"), stood_in.get(test, "missing")
        print(f"  DIFFERENT: {test}: {was} with the real packages, {now} with the stand-ins")
    return 1 if differ or not real else 0


if __name__ == "__main__":
    sys.exit(main())
