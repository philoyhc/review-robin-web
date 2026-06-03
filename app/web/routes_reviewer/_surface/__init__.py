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
  ``_require_session_accepting``.
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

# The F401 noqa markers on the private (single-underscore) names
# acknowledge that these imports are deliberate re-exports rather
# than dead code; the operator-side preview surface +
# ``tests/unit/test_reviewer_surface_group_collapse.py`` reach in
# via ``_surface._<name>`` and the byte-stable surface keeps those
# working unchanged.
from ._context import (
    _load_assignments_with_relations,  # noqa: F401
    _instruments_for_session,  # noqa: F401
    _pages_for_session,
    _require_session_accepting,  # noqa: F401
    _reviewer_row_sort_key,  # noqa: F401
    _surface_context,
)
from ._group_collapse import GROUP_MEMBER_NAME_LIMIT, _collapse_group_rows
from ._routes import (
    review_surface,  # noqa: F401
    review_surface_default_position,  # noqa: F401
    reviewer_clear,  # noqa: F401
    reviewer_recall,  # noqa: F401
    reviewer_save,  # noqa: F401
    reviewer_save_consolidated,  # noqa: F401
    reviewer_submit,  # noqa: F401
    router,
    submit_redirect_url,  # noqa: F401
)
from ._status import (
    GroupCompletion,  # noqa: F401
    PageStatus,
    PageStatusState,  # noqa: F401
    SessionStatusState,  # noqa: F401
    _group_completion,  # noqa: F401
    _page_status_for_group,  # noqa: F401
    _session_status,  # noqa: F401
)


__all__ = [
    "GROUP_MEMBER_NAME_LIMIT",
    "PageStatus",
    "_collapse_group_rows",
    "_pages_for_session",
    "_surface_context",
    "router",
]
