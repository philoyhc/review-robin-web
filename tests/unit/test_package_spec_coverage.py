"""Every application package's routing module has a live spec (RRW 23H).

``tests/unit/test_spec_coverage.py`` holds RRW's ``app/`` to this rule
through ``app/web/spec_registry.py``. The packages beside it
(``APP_DIRS``) route through the Cordware host and had nothing: 26
routing modules, none mapped, on 2026-11-20. Each package now keeps its
own ``spec_registry.py``, so the rule stays with the package and no
package depends on ``app/``, and this test reads the host's route table
against all of them, both directions, as the RRW gate does.
"""

from __future__ import annotations

import importlib
from collections import defaultdict
from types import ModuleType
from typing import Any, cast

import pytest

from app.web.spec_registry import _iter_endpoint_routes
from cordware.main import create_app

from ._packages import REPO, app_dirs

APP_DIRS = app_dirs()


def _package_routing_modules() -> dict[str, set[str]]:
    by_package: dict[str, set[str]] = defaultdict(set)
    for route in _iter_endpoint_routes(create_app().routes):
        module = cast(Any, route).endpoint.__module__
        package = module.split(".", 1)[0]
        if package in APP_DIRS:
            by_package[package].add(module)
    return by_package


ROUTING = _package_routing_modules()


def _registry(package: str) -> ModuleType:
    return importlib.import_module(f"{package}.spec_registry")


@pytest.mark.parametrize("package", APP_DIRS)
def test_every_package_routing_module_is_registered(package: str) -> None:
    registry = _registry(package)
    registered = set(registry.SPEC_COVERAGE) | set(registry.INFRASTRUCTURE_MODULES)
    routing = ROUTING.get(package, set())
    unregistered = sorted(routing - registered)
    stale = sorted(registered - routing)
    assert not unregistered and not stale, (
        f"{package}/spec_registry.py is out of step with the route table.\n"
        f"  routing modules with no entry: {unregistered or 'none'}\n"
        f"  entries that no longer route: {stale or 'none'}"
    )


@pytest.mark.parametrize("package", APP_DIRS)
def test_every_package_mapping_names_a_live_spec_of_its_own(package: str) -> None:
    problems = []
    for module, paths in sorted(_registry(package).SPEC_COVERAGE.items()):
        if not paths:
            problems.append(f"{module}: no spec")
        for path in paths:
            if not path.startswith((f"{package}/spec/", f"{package}/docs/")):
                problems.append(f"{module} -> {path}: not under {package}/spec/ or docs/")
            elif "archive/" in path or not (REPO / path).is_file():
                problems.append(f"{module} -> {path}: not a live file")
    assert not problems, "\n  ".join(["unusable mappings:", *problems])


def test_the_walk_sees_every_package() -> None:
    """Guards the guard: a host that stopped mounting a package, or a walk
    that stopped descending into mounts, would pass the tests above by
    seeing nothing."""
    assert APP_DIRS and all(ROUTING.get(package) for package in APP_DIRS)
