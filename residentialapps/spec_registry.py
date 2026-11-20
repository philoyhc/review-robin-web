"""Which spec governs which of Residential's routing modules (RRW 23H).

The package's half of RRW's ``app/web/spec_registry.py`` rule: every
routing module has a live spec that governs it.
``tests/unit/test_package_spec_coverage.py`` walks the Cordware host's
route table and fails on a module missing here, or a mapping that names
no live file. Adding a routing module? Add it here too.
"""

from __future__ import annotations

_OPS = ("residentialapps/spec/residentialops_ui.md",)
_LOGS = ("residentialapps/spec/supportlogs_ui.md",)

SPEC_COVERAGE: dict[str, tuple[str, ...]] = {
    "residentialapps.residentialops.routes_access": _OPS,
    "residentialapps.residentialops.routes_home": _OPS,
    "residentialapps.residentialops.routes_leave_admin": _OPS,
    "residentialapps.residentialops.routes_leave_ra": _OPS,
    "residentialapps.residentialops.routes_leave_staff": _OPS,
    "residentialapps.residentialops.routes_rosters": _OPS,
    "residentialapps.supportlogs.routes_consultation": _LOGS,
    "residentialapps.supportlogs.routes_frontline": _LOGS,
    "residentialapps.supportlogs.routes_home": _LOGS,
    "residentialapps.supportlogs.routes_overview": _LOGS,
    "residentialapps.supportlogs.routes_plans": _LOGS,
    "residentialapps.supportlogs.routes_records": _LOGS,
    "residentialapps.supportlogs.routes_safety": _LOGS,
    "residentialapps.supportlogs.routes_sys_admin": _LOGS,
}

# Liveness: no user-facing contract to describe.
INFRASTRUCTURE_MODULES: frozenset[str] = frozenset(
    {
        "residentialapps.residentialops.routes_health",
        "residentialapps.supportlogs.routes_health",
    }
)
