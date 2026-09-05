"""Every routing module has a live spec that governs it.

Derived from ``app/web/spec_registry.py`` in the same idiom as
``tests/unit/test_doc_conventions.py`` and the ``EVENT_SCHEMAS``
strict-mode gate: the rule is a constant in the code, so the check
cannot go stale independently of the thing it checks
(``constitution.md`` Article II).

The failure this catches is a routing surface shipping with **no spec at
all** — the undeclared half of the phase rule's exit. The declared half
(a plan that commits to a spec edit and does not make it) is
``tools/close_check.py``'s. Planned in
``guide/segment_19A_spec_documentation.md`` Item 3.
"""

from __future__ import annotations

from app.main import create_app
from app.web.spec_registry import (
    EXPECTED_PENDING,
    INFRASTRUCTURE_MODULES,
    REPO_ROOT,
    SPEC_COVERAGE,
    pending_modules,
    routing_modules,
)


def test_every_routing_module_is_registered() -> None:
    """Set equality, not containment, in both directions.

    A new routing module with no registry entry is the failure this
    exists for. A registry entry whose module no longer routes is drift
    too — it means the map describes a surface that is gone.
    """
    enumerated = routing_modules(create_app())
    registered = set(SPEC_COVERAGE) | set(INFRASTRUCTURE_MODULES)

    unregistered = sorted(enumerated - registered)
    stale = sorted(registered - enumerated)
    assert not unregistered and not stale, (
        "app/web/spec_registry.py is out of step with the route table.\n"
        f"  routing modules with no registry entry: {unregistered or 'none'}\n"
        "    -> add each to SPEC_COVERAGE with the spec that governs it "
        "(or to INFRASTRUCTURE_MODULES if it carries no user-facing "
        "contract; or to SPEC_PENDING + EXPECTED_PENDING to declare the "
        "debt).\n"
        f"  registered modules that no longer route: {stale or 'none'}\n"
        "    -> remove the entry."
    )


def test_every_mapped_spec_path_is_a_live_file() -> None:
    """A mapping is only worth having if it points at a live contract."""
    problems: list[str] = []
    for module, paths in sorted(SPEC_COVERAGE.items()):
        for path in paths:
            if not (path.startswith("spec/") or path.startswith("docs/")):
                problems.append(f"{module} -> {path}: not under spec/ or docs/")
                continue
            if "archive/" in path:
                problems.append(
                    f"{module} -> {path}: archived docs are history, "
                    "not a governing contract"
                )
                continue
            if not (REPO_ROOT / path).is_file():
                problems.append(f"{module} -> {path}: file does not exist")
    assert not problems, "spec_registry.py maps to unusable paths:\n  " + "\n  ".join(
        problems
    )


def test_pending_modules_match_the_expected_baseline() -> None:
    """``EXPECTED_PENDING`` is the declared spec debt, and nothing else.

    Two distinct failures share this assertion, so the message names
    which one happened: debt added without declaring it, and debt paid
    off without clearing the declaration.
    """
    pending = pending_modules()
    expected = set(EXPECTED_PENDING)

    undeclared = sorted(pending - expected)
    unrecorded = sorted(expected - pending)
    assert not undeclared and not unrecorded, (
        "spec debt in app/web/spec_registry.py does not match "
        "EXPECTED_PENDING.\n"
        f"  new debt, not declared: {undeclared or 'none'}\n"
        "    -> write the spec, or add the module to EXPECTED_PENDING "
        "with the reason in the PR body.\n"
        f"  debt closed but still declared: {unrecorded or 'none'}\n"
        "    -> remove it from EXPECTED_PENDING."
    )
