"""Modules a caller may import first, in a fresh interpreter (segment
20E rung 3's cold read).

``app/web/roster_import.py`` sits outside the operator routes package, and
the package's slices import it. If it imported the package at its top, it
would load only when ``app.main`` happened to import the package first:
imported first, it fails on a cycle through the package's ``__init__``.
Each module here is imported alone, in its own process, so import order
inside the suite cannot hide such a cycle.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

FIRST_IMPORTS = [
    "app.web.roster_import",
    "app.services.csv_imports",
    "app.services.responses",
]


@pytest.mark.parametrize("module", FIRST_IMPORTS)
def test_the_module_imports_on_its_own(module: str) -> None:
    done = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr[-2000:]
