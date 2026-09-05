"""Which spec governs which routing module.

The rule this module encodes: **every routing module in ``app/`` has a
live spec that governs it**. That rule used to be prose, so nothing
noticed a surface that shipped without one. Here it is a constant, and
``tests/unit/test_spec_coverage.py`` derives its checks from it — the
same idiom as ``EVENT_SCHEMAS`` in ``app/services/audit.py`` and
``DISPLAY_LABELS`` in ``app/services/lifecycle_display.py``: the rule
lives in code, so it cannot go stale independently of the code
(``constitution.md`` Article II).

What this gate does and does not claim. It catches a routing module
with **no spec at all**. It does not catch a surface whose governing
section is thin, out of date, or lodged in a neighbouring spec rather
than a dedicated one — the two Tier-1 gaps closed in #2101
(``spec/permissions.md``, ``spec/email_template_editor.md``) both had
sections in ``spec/operator_ui_concept.md`` and would have passed here.
Declared spec drift is ``tools/close_check.py``'s job; this is the
undeclared-surface half. See ``guide/segment_19A_spec_documentation.md``
Item 3.

Adding a routing module? Add it here too, or the coverage test fails.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Iterator

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import FastAPI
    from starlette.routing import BaseRoute

REPO_ROOT = Path(__file__).resolve().parents[2]

# Modules under this prefix are ours; everything else reaching the route
# table belongs to the framework (``fastapi.applications`` serves
# ``/openapi.json``, ``/docs``, ``/redoc``) and is not ours to spec.
FIRST_PARTY_PREFIX = "app."

# A routing module that carries no user-facing contract of its own.
# Excluded from the coverage requirement rather than mapped to a spec,
# because there is no surface to describe: liveness, identity
# diagnostics, and the two role-aware redirects out of ``/`` and
# ``/operator``. Registering a *new* module here is a deliberate act —
# the coverage test reads this set, so an unlisted module still fails.
INFRASTRUCTURE_MODULES: frozenset[str] = frozenset(
    {
        "app.web.routes_health",  # GET /health — liveness + build metadata
        "app.web.routes_auth",  # GET /auth/me, /auth/me/debug — identity diagnostics
        "app.main",  # GET /, /operator, /operator/ — role-aware redirects only
    }
)

# Sentinel for a routing module that ships without a governing spec.
# Map a module to this rather than to a plausible-looking spec that does
# not actually describe it, then add the module to ``EXPECTED_PENDING``
# so the debt is declared instead of hidden.
SPEC_PENDING: tuple[str, ...] = ()

# Every routing module, mapped to the live spec(s) that govern it.
# Paths are repo-relative and must point at a live file under ``spec/``
# or ``docs/`` — never under an ``archive/``, which is history, not a
# contract.
#
# Seeding rule: map the spec that documents the module's **routes, or
# the surface those routes serve** — not every document that touches the
# subject. ``spec/reconciling_regeneration.md`` is the design record
# behind ``POST .../assignments/generate`` and describes no route, so
# ``_assignments`` maps to ``spec/assignments.md`` alone. A second entry
# earns its place only where it carries route-level contract the first
# does not (``_session_home`` → ``spec/permissions.md`` for the two
# owner routes; ``_operations`` → the Validate and Preview page specs).
SPEC_COVERAGE: dict[str, tuple[str, ...]] = {
    # --- operator: session-scoped setup -------------------------------
    "app.web.routes_operator._lobby": ("spec/sessions_overview.md",),
    "app.web.routes_operator._session_home": (
        "spec/session_home.md",
        "spec/permissions.md",  # owners/add, owners/{id}/remove
    ),
    "app.web.routes_operator._quick_setup": ("spec/quick_setup_card_spec.md",),
    "app.web.routes_operator._setup_reviewers": ("spec/setup_pages.md",),
    "app.web.routes_operator._setup_reviewees": ("spec/setup_pages.md",),
    "app.web.routes_operator._setup_relationships": ("spec/setup_pages.md",),
    "app.web.routes_operator._setup_observers": ("spec/setup_pages.md",),
    "app.web.routes_operator._setup_invite": ("spec/email_template_editor.md",),
    "app.web.routes_operator._settings": (
        "spec/settings_inventory.md",
        "spec/timezone_display.md",  # the Date & time card at /operator/settings
    ),
    # --- operator: instruments + assignments ---------------------------
    # incl. POST .../{id}/visibility, documented at instruments.md:331 —
    # spec/visibility_policy.md describes the policy model, not the route.
    "app.web.routes_operator._instruments": ("spec/instruments.md",),
    "app.web.routes_operator._instruments_band2": ("spec/instruments.md",),
    "app.web.routes_operator._instruments_pagination": ("spec/instruments.md",),
    "app.web.routes_operator._assignments": ("spec/assignments.md",),
    # --- operator: lifecycle + operations ------------------------------
    "app.web.routes_operator._workflow": (
        "spec/workflow_card.md",
        "spec/lifecycle.md",
    ),
    "app.web.routes_operator._operations": (
        "spec/operations_pages.md",
        "spec/validate_page.md",  # GET .../validate
        "spec/preview_hub.md",  # GET .../preview, .../previews
    ),
    "app.web.routes_operator._preview_surface": ("spec/preview_hub.md",),
    "app.web.routes_operator._extracts": ("spec/csv_contracts.md",),
    "app.web.routes_operator._extract_data": ("spec/extract_data.md",),
    "app.web.routes_operator._rehydrate": ("spec/rehydrate.md",),
    "app.web.routes_operator._sys_admin": ("spec/permissions.md",),
    # --- participant surfaces ------------------------------------------
    # /me itself carries no role-chip strip (it is what the chips let a
    # multi-role user skip), so spec/role_navigator.md does not govern it.
    "app.web.routes_reviewer._dashboard": ("spec/reviewer-surface.md",),
    "app.web.routes_reviewer._invite": ("spec/reviewer-surface.md",),
    "app.web.routes_reviewer._surface._routes": (
        "spec/reviewer-surface.md",
        "spec/sort_by_reviewee.md",  # the surface's sort UX
    ),
    "app.web.routes_reviewer._summary": ("spec/reviewer-surface.md",),
    "app.web.routes_reviewer._results": (
        "spec/participant_model.md",
        "spec/reviewer-surface.md",
    ),
    "app.web.routes_reviewer._collation": (
        "spec/participant_model.md",
        "spec/reviewer-surface.md",
    ),
    # --- standalone pages -----------------------------------------------
    # /about is a real page with its own contract section
    # (operator_ui_concept.md "### `/about` — About"), not infrastructure.
    "app.web.routes_about": ("spec/operator_ui_concept.md",),
}

# Modules currently mapped to ``SPEC_PENDING``. Empty is the correct
# baseline: as of 2026-09-05 every routing module has a governing spec.
# Adding an entry here is declaring debt, and the test message says so.
EXPECTED_PENDING: tuple[str, ...] = ()

# A broken route walk (see ``_iter_endpoint_routes``) would under-report
# rather than fail, turning a framework change into a confusing set diff.
# The app has had well over a hundred routes since Segment 18; this floor
# turns that failure into a named one.
_MINIMUM_ROUTES = 100


def _iter_endpoint_routes(routes: Iterable[BaseRoute]) -> Iterator[BaseRoute]:
    """Yield every route that has an endpoint, descending into routers.

    FastAPI 0.140+ does not flatten ``include_router`` results into
    ``app.routes``; it leaves a lazy wrapper holding the original router.
    So a plain iteration over ``app.routes`` sees three endpoints, not
    185, and the naive ``{r.endpoint.__module__ for r in app.routes}``
    silently reports almost nothing.
    """
    for route in routes:
        if getattr(route, "endpoint", None) is not None:
            yield route
            continue
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from _iter_endpoint_routes(included.routes)
            continue
        nested = getattr(route, "routes", None)
        if nested:
            yield from _iter_endpoint_routes(nested)


def routing_modules(app: FastAPI) -> set[str]:
    """Every first-party module that owns at least one live route."""
    routes = list(_iter_endpoint_routes(app.routes))
    if len(routes) < _MINIMUM_ROUTES:
        raise RuntimeError(
            f"route walk found only {len(routes)} routes (expected at "
            f"least {_MINIMUM_ROUTES}) — the FastAPI route-table shape "
            "has probably changed; fix _iter_endpoint_routes rather than "
            "the registry"
        )
    return {
        route.endpoint.__module__
        for route in routes
        if route.endpoint.__module__.startswith(FIRST_PARTY_PREFIX)
    }


def pending_modules() -> set[str]:
    """Registered modules that have declared they have no spec yet."""
    return {
        module for module, paths in SPEC_COVERAGE.items() if paths == SPEC_PENDING
    }
