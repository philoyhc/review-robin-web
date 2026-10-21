"""The import boundary (v0.8 §3, "The independence requirement").

Applications may import Cordware, but not its entry point `cordware.main`;
Cordware imports an application only
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

_DYNAMIC = {"import_module", "__import__"}


def imported_packages(source: str) -> set[str]:
    """The top-level packages a module's source imports, at any depth,
    including a literal ``importlib.import_module("x...")`` or
    ``__import__("x...")``."""
    packages: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            packages.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            packages.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and node.args:
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            first = node.args[0]
            if (
                name in _DYNAMIC
                and isinstance(first, ast.Constant)
                and isinstance(first.value, str)
            ):
                packages.add(first.value.split(".")[0])
    return packages


def violations(package: str, root: Path = ROOT) -> list[str]:
    found = []
    tests = root / package / "tests"
    for path in sorted((root / package).rglob("*.py")):
        if package == "cordware" and path.is_relative_to(tests):
            continue  # the host's tests drive real applications on purpose
        bad = imported_packages(path.read_text()) & FORBIDDEN[package]
        found += [f"{path.relative_to(root)} imports {name}" for name in sorted(bad)]
    return found


# `residentialapps/` joins once stage 3 imports it.
@pytest.mark.parametrize("package", [p for p in sorted(FORBIDDEN) if (ROOT / p).is_dir()])
def test_no_package_crosses_the_boundary(package: str) -> None:
    assert violations(package) == []


def test_imports_are_read_at_any_depth_and_dynamically() -> None:
    assert imported_packages("import residentialapps.core\n") == {"residentialapps"}
    assert imported_packages("def f():\n    from app.main import create_app\n") == {"app"}
    assert imported_packages("import importlib\nimportlib.import_module('app.x')\n") >= {"app"}
    assert imported_packages("__import__('residentialapps')\n") == {"residentialapps"}
    assert imported_packages("from . import sibling\n") == set()


def test_a_planted_import_under_app_is_caught(tmp_path: Path) -> None:
    (tmp_path / "app" / "services").mkdir(parents=True)
    (tmp_path / "app" / "services" / "leak.py").write_text("import residentialapps.core\n")
    (tmp_path / "cordware" / "tests").mkdir(parents=True)
    (tmp_path / "cordware" / "main.py").write_text("from app.main import create_app\n")
    (tmp_path / "cordware" / "tests" / "test_x.py").write_text("import app.main\n")
    assert violations("app", tmp_path) == ["app/services/leak.py imports residentialapps"]
    assert violations("cordware", tmp_path) == ["cordware/main.py imports app"]


def imported_modules(source: str) -> set[str]:
    """Every dotted module a source imports by name, `from x import y`
    also counting as importing `x.y` (it may be a submodule)."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def test_no_application_imports_the_host_entry_point() -> None:
    """`cordware.main` builds the host when imported (segment 21C):
    applications import `cordware.identity`, never the entry point."""
    found = [
        str(path.relative_to(ROOT))
        for package in ("app", "residentialapps")
        if (ROOT / package).is_dir()
        for path in sorted((ROOT / package).rglob("*.py"))
        if "cordware.main" in imported_modules(path.read_text())
    ]
    assert found == []


def test_the_entry_point_check_reads_both_import_forms() -> None:
    assert "cordware.main" in imported_modules("import cordware.main\n")
    assert "cordware.main" in imported_modules("from cordware import main\n")
    assert "cordware.main" in imported_modules("def f():\n    from cordware.main import app\n")
    assert "cordware.main" not in imported_modules("from cordware.identity import fake_auth\n")
