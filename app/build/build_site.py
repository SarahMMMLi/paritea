"""Prepare app/web/ for serving: package the Python the engine runs and list the wheels it installs.

Run from app/ after build_wheels.sh: ``uv run python build/build_site.py``.
"""

import json
import zipfile
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
WEB = APP / "web"

# The Streamlit-free part of paritea_ui that the browser engine imports.
ENGINE_MODULES = [
    "__init__.py",
    "api.py",
    "codegen.py",
    "console.py",
    "core.py",
    "examples.py",
    "layout.py",
    "session.py",
    "validate.py",
]


def package_python() -> Path:
    target = WEB / "py" / "paritea_ui.zip"
    target.parent.mkdir(exist_ok=True)
    source = APP / "paritea_ui"
    files = [source / name for name in ENGINE_MODULES]
    files += sorted(p for p in (source / "compat").rglob("*.py") if "__pycache__" not in p.parts)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, path.relative_to(APP).as_posix())
    return target


def write_manifest() -> Path:
    wheels = sorted(p.name for p in (WEB / "wheels").glob("*.whl"))
    target = WEB / "engine.json"
    target.write_text(json.dumps({"pyodide": "314.0.7", "wheels": wheels}, indent=2) + "\n")
    return target


if __name__ == "__main__":
    print(package_python().relative_to(APP))
    print(write_manifest().relative_to(APP))
