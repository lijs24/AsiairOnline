"""Shared fixtures for asiairbridge unit tests.

All tests run without a real device.  The web server and camera cache are
stubbed so no network or filesystem access is needed.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the package is importable from the repo root without installing it.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# ---------------------------------------------------------------------------
# Stub heavy optional dependencies that may not be installed in CI.
# ---------------------------------------------------------------------------
for _mod in ("moderngl", "astropy", "astropy.coordinates", "astropy.units",
             "astropy.time"):
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)
