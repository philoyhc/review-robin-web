"""Importing `app.main` builds no application (segment 21A, A2).

RRW is built once, by whoever serves it: the Cordware host
(`cordware.main:app`) or a test through `tests/_rrw_app.py`. A
module-level `app = create_app()` would build a second one on import.
"""

from __future__ import annotations

from starlette.applications import Starlette

import app.main


def test_app_main_holds_no_application_instance() -> None:
    built = [name for name, value in vars(app.main).items() if isinstance(value, Starlette)]
    assert built == []
    assert callable(app.main.create_app)
