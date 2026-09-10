#!/usr/bin/env python3
"""Entry point for the segment close check — see ``tools/close_check/``.

**This file exists to keep one string true.** ``python3
tools/close_check.py <id>`` appears in the Definition of done of every
segment plan in ``guide/`` and ``guide/archive/``, and in
``CLAUDE.md``; Segment 19J Item 3 carved the 1,000-line implementation
into a package and froze that invocation rather than reprint it across
the corpus.

``tools/close_check.py`` and ``tools/close_check/`` coexist on disk
deliberately. A directory with ``__init__.py`` wins over a same-named
module on the same ``sys.path`` entry, so the import below resolves to
the package — verified for both ``python3 tools/close_check.py`` and
``importlib.util.spec_from_file_location``, which is how
``tests/unit/test_close_check.py`` loads this file.

The real reading order: ``__init__.py`` (the reasoning + ``main``),
``_manifest.py`` (C1–C7, 680 lines), ``_sweep.py``, ``_archive.py``,
``_shared.py``.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from close_check import *  # noqa: F401,F403  — re-export for by-path loaders
from close_check import _shared  # noqa: F401  — the single REPO patch point
from close_check import main

if __name__ == "__main__":
    sys.exit(main())
