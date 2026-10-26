"""The Cordware host with Residential mounted, for Residential's tests.

After RRW's `tests/_mounted.py`: the host is `cordware.main.create_app`,
and the root logger it configures is put back afterwards, so the rest of
the worker's tests see the logging they had. The handler the host
installed is returned too, for the tests that read its log stamps.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from fastapi import FastAPI


def host_with(apps: Sequence[str] | None) -> tuple[FastAPI, logging.Handler]:
    """The host mounting ``apps`` from the real registry (``None``: every
    registered application, as an unset `CORDWARE_APPS` does).

    ``None`` is passed on as the registry's names, not as ``None``: the
    host would read `CORDWARE_APPS` from the shell or `.env`, and a
    developer running RRW alone sets it (`docs/local_setup.md`). What an
    unset value selects is `parse_apps`'s, tested in `cordware/tests`."""
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    try:
        # Imported here, not at the top: `cordware.main` builds its own
        # `app` (and configures logging) at import, which this restores.
        from cordware.main import REGISTRY, create_app

        host = create_app(apps=tuple(REGISTRY) if apps is None else apps)
        installed = next(h for h in root.handlers if getattr(h, "_cordware_json", False))
        return host, installed
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)
