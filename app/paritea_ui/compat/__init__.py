"""Stand-ins for packages that paritea imports but that cannot run in the browser.

galois needs numba (a JIT compiler that does not exist for WebAssembly), recordclass is a C extension with no
WebAssembly build, and ``paritea.generate`` imports ``Fraction`` from matplotlib's ``mpl_toolkits`` by mistake.
``install()`` appends the stand-ins to ``sys.path``, so a real package, when installed, always wins.
"""

import sys
from pathlib import Path

STUBS = Path(__file__).parent / "_stubs"


def install() -> None:
    """Make the stand-ins importable, after every real package."""
    if str(STUBS) not in sys.path:
        sys.path.append(str(STUBS))
