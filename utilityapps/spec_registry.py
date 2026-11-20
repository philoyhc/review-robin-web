"""Which spec governs which of Utilities' routing modules (RRW 23H).

The package's half of RRW's ``app/web/spec_registry.py`` rule: every
routing module has a live spec that governs it.
``tests/unit/test_package_spec_coverage.py`` walks the Cordware host's
route table and fails on a module missing here, or a mapping that names
no live file. Adding a routing module? Add it here too.
"""

from __future__ import annotations

_UTILITIES = ("utilityapps/spec/utilities.md",)

SPEC_COVERAGE: dict[str, tuple[str, ...]] = {
    "utilityapps.routes_home": _UTILITIES,
    "utilityapps.email_check.routes": ("utilityapps/spec/email_check.md",),
    "utilityapps.diagnostics.routes": _UTILITIES,
    "utilityapps.interop_poc.routes": _UTILITIES,
    "utilityapps.photo_poc.routes": _UTILITIES,
}

# Liveness: no user-facing contract to describe.
INFRASTRUCTURE_MODULES: frozenset[str] = frozenset({"utilityapps.routes_health"})
