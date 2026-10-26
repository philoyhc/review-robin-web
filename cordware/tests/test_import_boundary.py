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
    also counting as importing `x.y` (it may be a submodule), including
    a literal ``importlib.import_module("x.y")`` or ``__import__("x.y")``."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Call) and node.args:
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            first = node.args[0]
            if (
                name in _DYNAMIC
                and isinstance(first, ast.Constant)
                and isinstance(first.value, str)
            ):
                modules.add(first.value)
    return modules


def test_no_application_imports_the_host_entry_point() -> None:
    """`cordware.main` builds the host when imported (segment 21C):
    applications import `cordware.identity`, never the entry point.
    Residential's tests build the host on purpose, as RRW's root `tests/`
    do (`residentialapps/spec/architecture.md`)."""
    tests = ROOT / "residentialapps" / "tests"
    found = [
        str(path.relative_to(ROOT))
        for package in ("app", "residentialapps")
        if (ROOT / package).is_dir()
        for path in sorted((ROOT / package).rglob("*.py"))
        if not path.is_relative_to(tests)
        and "cordware.main" in imported_modules(path.read_text())
    ]
    assert found == []


# Residential application package -> the Residential modules it must never
# import (`residentialapps/spec/architecture.md` "Import boundaries"; the
# rest join with their packages).
RESIDENTIAL_FORBIDDEN = {
    "residentialapps.ops": ("residentialapps.supportlogs",),
    "residentialapps.supportlogs": ("residentialapps.ops",),
    "residentialapps.web": (
        "residentialapps.ops",
        "residentialapps.supportlogs",
        "residentialapps.leave",
        "residentialapps.events",
    ),
}


def residential_modules(path: Path, root: Path = ROOT) -> set[str]:
    """Every module a Residential source imports, its relative imports
    resolved against the package the file sits in."""
    package = list(path.relative_to(root).parent.parts)
    modules = imported_modules(path.read_text())
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.level:
            base = package[: len(package) - node.level + 1]
            stem = ".".join(base + ([node.module] if node.module else []))
            modules.add(stem)
            modules.update(f"{stem}.{alias.name}" for alias in node.names)
    return modules


def residential_violations(root: Path = ROOT) -> list[str]:
    found = []
    for package, forbidden in RESIDENTIAL_FORBIDDEN.items():
        directory = root / package.replace(".", "/")
        for path in sorted(directory.rglob("*.py")) if directory.is_dir() else []:
            bad = {
                module
                for module in residential_modules(path, root)
                if any(module == f or module.startswith(f + ".") for f in forbidden)
            }
            found += [f"{path.relative_to(root)} imports {name}" for name in sorted(bad)]
    return found


def test_neither_residential_application_imports_the_other() -> None:
    assert (ROOT / "residentialapps" / "ops").is_dir()
    assert residential_violations() == []


def test_a_planted_cross_application_import_is_caught(tmp_path: Path) -> None:
    ops = tmp_path / "residentialapps" / "ops"
    logs = tmp_path / "residentialapps" / "supportlogs"
    ops.mkdir(parents=True)
    logs.mkdir()
    (ops / "leak.py").write_text("from residentialapps.supportlogs import main\n")
    (logs / "leak.py").write_text("from ..ops import main\n")
    (logs / "fine.py").write_text("from . import main\nimport residentialapps.core\n")
    assert residential_violations(tmp_path) == [
        "residentialapps/ops/leak.py imports residentialapps.supportlogs",
        "residentialapps/ops/leak.py imports residentialapps.supportlogs.main",
        "residentialapps/supportlogs/leak.py imports residentialapps.ops",
        "residentialapps/supportlogs/leak.py imports residentialapps.ops.main",
    ]


def test_a_planted_import_from_shared_web_code_is_caught(tmp_path: Path) -> None:
    web = tmp_path / "residentialapps" / "web"
    web.mkdir(parents=True)
    (web / "leak.py").write_text("from residentialapps.ops import pages\n")
    (web / "fine.py").write_text("from residentialapps.web import urls\n")
    assert residential_violations(tmp_path) == [
        "residentialapps/web/leak.py imports residentialapps.ops",
        "residentialapps/web/leak.py imports residentialapps.ops.pages",
    ]


def test_the_entry_point_check_reads_both_import_forms() -> None:
    assert "cordware.main" in imported_modules("import cordware.main\n")
    assert "cordware.main" in imported_modules("from cordware import main\n")
    assert "cordware.main" in imported_modules("def f():\n    from cordware.main import app\n")
    assert "cordware.main" in imported_modules("import importlib\nimportlib.import_module('cordware.main')\n")
    assert "cordware.main" in imported_modules("__import__('cordware.main')\n")
    assert "cordware.main" not in imported_modules("from cordware.identity import fake_auth\n")
