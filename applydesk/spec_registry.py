"""Which spec governs which of Apply Desk's routing modules (RRW 23H).

The package's half of RRW's ``app/web/spec_registry.py`` rule: every
routing module has a live spec that governs it.
``tests/unit/test_package_spec_coverage.py`` walks the Cordware host's
route table and fails on a module missing here, or a mapping that names
no live file. Adding a routing module? Add it here too.
"""

from __future__ import annotations

SPEC_COVERAGE: dict[str, tuple[str, ...]] = {
    "applydesk.routes_home": ("applydesk/spec/applications.md",),
    "applydesk.routes_me": ("applydesk/spec/applications.md",),
    "applydesk.routes_operator": ("applydesk/spec/applications.md",),
}

# Liveness: no user-facing contract to describe.
INFRASTRUCTURE_MODULES: frozenset[str] = frozenset({"applydesk.routes_health"})
