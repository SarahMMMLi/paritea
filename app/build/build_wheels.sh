#!/usr/bin/env bash
# Build the browser (Pyodide) wheels the web UI needs and collect them in app/web/wheels/.
#
# paritea is built from a scratch copy of the repository, so no upstream-owned file is ever modified. Toolchains
# (pyodide-build, the cross-build environment and Emscripten) are cached in ~/.cache/paritea-web.
set -euo pipefail

PYODIDE_VERSION=314.0.7
PYODIDE_BUILD_VERSION=0.39.1
# Pure-Python or Pyodide wheels from PyPI, pinned to the versions in app/uv.lock: name==version.
PYPI_WHEELS=(rustworkx==0.18.1 pyzx==0.10.7 frozendict==2.4.7 lark==1.3.1 pyperclip==1.11.0)

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_DIR="$(cd "$APP_DIR/.." && pwd)"
CACHE="${PARITEA_WEB_CACHE:-$HOME/.cache/paritea-web}"
OUT="$APP_DIR/web/wheels"
export PATH="$HOME/.cargo/bin:$PATH"
export PYODIDE_XBUILDENV_PATH="$CACHE/xbuildenv"
mkdir -p "$CACHE" "$OUT"

if [ ! -x "$CACHE/pyodide-env/bin/pyodide" ]; then
  uv venv --python 3.14 "$CACHE/pyodide-env"
  uv pip install --python "$CACHE/pyodide-env/bin/python" "pyodide-build==$PYODIDE_BUILD_VERSION"
fi
PYODIDE="$CACHE/pyodide-env/bin/pyodide"

echo "== Cross-build environment for Pyodide $PYODIDE_VERSION"
"$PYODIDE" xbuildenv install "$PYODIDE_VERSION"
"$PYODIDE" xbuildenv install-emscripten
rustup target add wasm32-unknown-emscripten

echo "== Pinned wheels from PyPI"
"$CACHE/pyodide-env/bin/python" - "$OUT" "${PYPI_WHEELS[@]}" <<'PY'
import json
import pathlib
import sys
import urllib.request

out = pathlib.Path(sys.argv[1])
for pin in sys.argv[2:]:
    name, version = pin.split("==")
    meta = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json"))
    wheels = [f for f in meta["urls"] if f["filename"].endswith(("-none-any.whl", "-pyemscripten_2026_0_wasm32.whl"))]
    if not wheels:
        sys.exit(f"No browser-compatible wheel for {pin}")
    wheel = wheels[0]
    target = out / wheel["filename"]
    if not target.exists():
        urllib.request.urlretrieve(wheel["url"], target)
    print(target.name)
PY

echo "== paritea (from a scratch copy, optimised build that keeps Rust panics catchable)"
SRC="$(mktemp -d)/paritea"
mkdir -p "$SRC"
cp -R "$REPO_DIR"/{src,rust,Cargo.toml,Cargo.lock,pyproject.toml,README.md,LICENSE.md,NOTICE.md} "$SRC"/
find "$SRC" \( -name '__pycache__' -o -name '*.so' \) -prune -exec rm -rf {} +
# Library fixes the browser needs that are not upstream yet (each one also goes upstream as a pull request).
for fix in "$APP_DIR"/build/patches/*.patch; do
  if patch -p1 --forward --dry-run -s -d "$SRC" < "$fix" > /dev/null 2>&1; then
    patch -p1 --forward -s -d "$SRC" < "$fix"
    echo "Applied $(basename "$fix")"
  elif patch -p1 --reverse --dry-run -s -d "$SRC" < "$fix" > /dev/null 2>&1; then
    echo "$(basename "$fix") is already in the library: delete it from app/build/patches/"
  else
    echo "$(basename "$fix") no longer applies: update or delete it" >&2
    exit 1
  fi
done
rm -f "$OUT"/paritea-*.whl
# Overflow checks stay on so that, e.g., a bad fault-equivalence bound panics (a catchable error) instead of hanging.
(cd "$SRC" && CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS=true MATURIN_PEP517_ARGS="--profile release" \
  "$PYODIDE" build . -o "$OUT")

echo "== Done"
ls -la "$OUT"
