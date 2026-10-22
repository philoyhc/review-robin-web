"""The browser suite navigates RRW under its mount, never at `/`.

Segment 21D (`guide/segment_21D_prefix_flip.md`) moves RRW to
`/reviewrobin`, and the live server the browser tests drive serves it
there. A page's URL is written ``app_url("/operator/…")``
(`tests/browser/conftest.py`), so a test that slips back to a root path
would navigate to the host's 404 rather than RRW. These rules find one:

- **B1.** A ``goto`` or ``to_have_url`` argument is ``app_url(...)``, or
  is built from a page's own ``.url`` (already under the mount). A name
  passed there counts as its assignment does. A ``re.compile(...)``
  pattern passed to ``to_have_url`` is a search, not a path, and is left
  alone; any other call is checked like a path.
- **B2.** No ``href`` asserted through ``to_have_attribute`` is a
  root-path literal.
- **B3.** No script string assigns ``window.location`` a root-path
  literal or an f-string value not built by ``app_url(...)``, and ``window.location.pathname`` is compared only with
  ``app_url(...)``.

Easy Auth's ``/.auth/`` paths are the host's, outside the mount, and are
not RRW paths.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

BROWSER = Path(__file__).resolve().parents[1] / "browser"
_LOCATION_ASSIGN = re.compile(r"window\.location(?:\.href)?\s*=\s*['\"`]/(?!\.auth/)")
_LOCATION_ASSIGN_END = re.compile(r"window\.location(?:\.href)?\s*=\s*$")


def _is_app_url(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "app_url"
    )


def _is_compiled_pattern(node: ast.AST) -> bool:
    """``re.compile(...)``, the one call ``to_have_url`` may take unchecked."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "compile"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "re"
    )


def _reads_a_page_url(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Attribute) and n.attr == "url" for n in ast.walk(node))


def _root_literal(node: ast.AST) -> bool:
    """A string, or an f-string, that starts with `/` (not `/.auth/`)."""
    if isinstance(node, ast.JoinedStr) and node.values:
        node = node.values[0]
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith("/")
        and not node.value.startswith("/.auth/")
    )


def _assignments(tree: ast.AST) -> dict[str, list[ast.AST]]:
    bound: dict[str, list[ast.AST]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bound.setdefault(target.id, []).append(node.value)
    return bound


def _navigable(arg: ast.AST, bound: dict[str, list[ast.AST]]) -> bool:
    if _is_app_url(arg) or _reads_a_page_url(arg):
        return True
    if isinstance(arg, ast.Name) and arg.id in bound:
        return all(_navigable(value, {}) for value in bound[arg.id])
    return False


def _pathname_read(node: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and "window.location.pathname" in n.value
        for n in ast.walk(node)
    )


def offences(source: str) -> list[str]:
    tree = ast.parse(source)
    bound = _assignments(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.args:
            method, arg = node.func.attr, node.args[0]
            if method == "goto" or (method == "to_have_url" and not _is_compiled_pattern(arg)):
                if not _navigable(arg, bound):
                    found.append(f"B1 line {node.lineno}: {ast.unparse(arg)}")
            if (
                method == "to_have_attribute"
                and len(node.args) == 2
                and isinstance(arg, ast.Constant)
                and arg.value == "href"
                and _root_literal(node.args[1])
            ):
                found.append(f"B2 line {node.lineno}: {ast.unparse(node.args[1])}")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _LOCATION_ASSIGN.search(node.value):
                found.append(f"B3 line {node.lineno}: {node.value!r}")
        if isinstance(node, ast.JoinedStr):
            # f"window.location.href = {x!r}": the value assigned is x.
            for part, value in zip(node.values, node.values[1:]):
                if (
                    isinstance(part, ast.Constant)
                    and _LOCATION_ASSIGN_END.search(str(part.value))
                    and isinstance(value, ast.FormattedValue)
                    and not _is_app_url(value.value)
                ):
                    found.append(f"B3 line {node.lineno}: {ast.unparse(value.value)}")
        if isinstance(node, ast.Compare) and len(node.comparators) == 1:
            sides = (node.left, node.comparators[0])
            for read, other in (sides, sides[::-1]):
                if _pathname_read(read) and not _is_app_url(other):
                    found.append(f"B3 line {node.lineno}: {ast.unparse(other)}")
    return found


@pytest.mark.parametrize(
    "path", sorted(BROWSER.glob("*.py")), ids=lambda path: path.name
)
def test_browser_tests_navigate_under_the_mount(path: Path) -> None:
    assert offences(path.read_text()) == []


@pytest.mark.parametrize(
    ("source", "rule"),
    [
        ('page.goto("/operator/sessions")', "B1"),
        ('page.goto(f"/operator/sessions/{sid}")', "B1"),
        ('PAGE = "/about"\npage.goto(PAGE)', "B1"),
        ('expect(page).to_have_url("/operator/sessions")', "B1"),
        ('expect(page).to_have_url(str("/operator/sessions"))', "B1"),
        ("expect(page).to_have_url(build_url(sid))", "B1"),
        ('expect(link).to_have_attribute("href", "/operator/sessions")', "B2"),
        ('page.evaluate("window.location.href = \'/about\'")', "B3"),
        ('page.evaluate(f"window.location.href = {MISSING!r}")', "B3"),
        ('assert page.evaluate("window.location.pathname") == "/me"', "B3"),
    ],
)
def test_the_rules_catch_a_root_path(source: str, rule: str) -> None:
    [offence] = offences(source)
    assert offence.startswith(rule)


@pytest.mark.parametrize(
    "source",
    [
        'page.goto(app_url("/operator/sessions"))',
        'url = app_url("/me")\npage.goto(url)',
        "filtered = page.url\npage.goto(filtered)",
        'page.goto(page.url.split("?")[0] + "?editing=1")',
        'expect(page).to_have_url(re.compile(r"/operator/sessions/\\w+"))',
        'expect(zip_all).to_have_attribute("href", "#")',
        'page.evaluate("window.location.href = \'/.auth/logout\'")',
        'page.evaluate(f"window.location.href = {app_url(MISSING)!r}")',
        'assert page.evaluate("window.location.pathname") == app_url("/me")',
    ],
)
def test_the_rules_pass_a_mounted_path(source: str) -> None:
    assert offences(source) == []
