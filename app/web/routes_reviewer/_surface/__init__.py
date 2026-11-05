"""Reviewer response surface — the multi-instrument-aware
review table at ``/me/sessions/{id}/{instrument_position}``,
its per-page Save, and the session-wide Submit / Clear.

Was a single 1,299-line ``_surface.py`` module until the Segment
18O Track D carve split it into four concern-scoped sub-modules.
The public surface is preserved here as an explicit re-export wall
so external callers — ``app.web.routes_operator._preview_surface``
(``_pages_for_session``, ``_surface_context``),
``app.web.views._instruments`` (``GROUP_MEMBER_NAME_LIMIT``),
``tests/unit/test_reviewer_surface_group_collapse.py``
(``_collapse_group_rows``), and the package mount in
``routes_reviewer/__init__.py`` (``router``) — continue to work
byte-identical to the pre-package shape.

Layout:

- ``_status.py`` — ``PageStatus`` / ``GroupCompletion`` +
  per-page + per-session state rollups.
- ``_group_collapse.py`` — ``_collapse_group_rows`` +
  ``GROUP_MEMBER_NAME_LIMIT`` constant.
- ``_context.py`` — ``_surface_context`` + the small loaders +
  the write gate ``_write_refusal`` and what a refused write shows.
- ``_routes.py`` — GET + four POST handlers + the
  ``router`` instance + ``submit_redirect_url``.

Reviewer surface — multi-instrument-aware URL pattern (Segment
11D follow-on, PR α onward):

- GET  /sessions/{id}                         → 303 to /sessions/{id}/1
- GET  /sessions/{id}/{instrument_position}   → renders the surface
- POST /sessions/{id}/{instrument_position}/save
- POST /sessions/{id}/submit                  → session-wide
- POST /sessions/{id}/clear                   → session-wide

Submit and Clear stay session-wide; their redirect targets are the
bare session URL ``/me/sessions/{id}`` which 303s on to
``/1`` — post-Segment-18L the URL slot is the operator-defined
page number, so a "go back to where you were" round-trip is no
longer possible after a session-wide POST.
"""

from __future__ import annotations

# Only the names the docstring lists are re-exported; the sub-modules
# are imported directly for anything else.
from ._context import _pages_for_session, _surface_context
from ._group_collapse import GROUP_MEMBER_NAME_LIMIT, _collapse_group_rows
from ._routes import router
from ._status import PageStatus

__all__ = [
    "GROUP_MEMBER_NAME_LIMIT",
    "PageStatus",
    "_collapse_group_rows",
    "_pages_for_session",
    "_surface_context",
    "router",
]
