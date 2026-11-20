"""The application packages the prose gates read (segment 23H).

One list, ``APP_DIRS`` in ``tools/close_check/_manifest.py``, names the
packages beside the root that keep their own ``spec/``, ``docs/`` and
``guide/``. The gates that read package prose take it from there through
this helper, so a new package is added once and every gate follows. An
exported kit without the close check has no packages.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def app_dirs() -> tuple[str, ...]:
    """``APP_DIRS`` from the close check, or ``()`` without one."""
    path = REPO / "tools" / "close_check.py"
    if not path.exists():
        return ()
    spec = importlib.util.spec_from_file_location("close_check_for_unit_gates", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(module.APP_DIRS)
