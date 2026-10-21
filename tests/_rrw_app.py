"""RRW's application for the test suite, built once per process.

`app.main` builds nothing at import (segment 21A, A2), so a test or test
helper that needs RRW's own app, to override a dependency or to drive it
with a `TestClient`, asks for it here. It is RRW's `create_app()` alone,
unmounted, so test request paths stay app-relative.

Imported as a top-level module, like `_sqlite_schema`: pytest puts
`tests/` on `sys.path` for the root conftest.
"""

from __future__ import annotations

from functools import cache

from fastapi import FastAPI

from app.main import create_app


@cache
def rrw_app() -> FastAPI:
    return create_app()
