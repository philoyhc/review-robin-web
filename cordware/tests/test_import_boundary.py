"""The import boundary (v0.8 §3, "The independence requirement").

Applications may import Cordware; Cordware imports an application only
through its registry entry's factory path, a string; applications never
import each other. Read from the source, so a forbidden import fails
here even if no test exercises the module.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Package directory -> top-level packages it must never import.
FORBIDDEN = {
    "app": {"residentialapps"},
    "residentialapps": {"app"},
    "cordware": {"app", "residentialapps"},
}


def imported_packages(source: str) -> set[str]:
    """The top-level packages a module's source imports, at any depth."""
    packages: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            packages.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            packages.add(node.module.split(".")[0])
    return packages


def violations(package: str) -> list[str]:
    found = []
    for path in sorted((ROOT / package).rglob("*.py")):
        if package == "cordware" and "tests" in path.relative_to(ROOT / package).parts:
            continue  # the host's tests drive real applications on purpose
        bad = imported_packages(path.read_text()) & FORBIDDEN[package]
        found += [f"{path.relative_to(ROOT)} imports {name}" for name in sorted(bad)]
    return found


# `residentialapps/` joins once stage 3 imports it.
@pytest.mark.parametrize("package", [p for p in sorted(FORBIDDEN) if (ROOT / p).is_dir()])
def test_no_package_crosses_the_boundary(package: str) -> None:
    assert violations(package) == []


def test_a_planted_import_is_caught() -> None:
    assert imported_packages("import residentialapps.core\n") == {"residentialapps"}
    assert imported_packages("def f():\n    from app.main import create_app\n") == {"app"}
    assert imported_packages("from . import sibling\n") == set()
