"""The browser suite navigates RRW under its mount, never at `/`.

Segment 21D (`guide/segment_21D_prefix_flip.md`) moves RRW to
`/reviewrobin`, and the live server the browser tests drive serves it
there. A page's URL is written ``app_url("/operator/…")``
(`tests/browser/conftest.py`), so a test that slips back to a root path
would navigate to the host's 404 rather than RRW, and a negative URL
assertion on one would pass whatever the app did. These rules find one:

- **B1.** The URL a test navigates to, requests or asserts (``goto``,
  ``to_have_url`` and ``not_to_have_url``, and ``page.request``'s
  verbs, positionally or by Playwright's keyword for it) is ``app_url(...)``, or is built
  from a page's own ``.url`` (already under the mount): the ``.url``
  itself, a method or index on it, or a string that starts with it. A
  name counts as its assignment does. A ``re.compile(...)`` pattern
  passed to a URL assertion is a search, not a path, and is left alone.
  ``wait_for_url`` and ``expect_navigation(url=...)`` take globs, so
  only a root-path literal there is refused.
- **B2.** No ``href`` asserted through ``to_have_attribute`` or
  ``not_to_have_attribute`` is a root-path literal.
- **B3.** No script string sends ``location`` (with or without
  ``window.``, by assignment or by ``assign`` / ``replace``) to a
  root-path literal, or to an f-string value not built by
  ``app_url(...)``; and ``location.pathname`` is compared only with
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
_SEND = r"(?:location(?:\.href)?\s*=|location\.(?:assign|replace)\()\s*"
_LOCATION_TO_ROOT = re.compile(_SEND + r"['\"`]/(?!\.auth/)")
_LOCATION_TO_VALUE = re.compile(_SEND + r"['\"`]?$")
_NAVIGATIONS = {"goto", "to_have_url", "not_to_have_url"}
_URL_ASSERTIONS = {"to_have_url", "not_to_have_url"}
_HREF_ASSERTIONS = {"to_have_attribute", "not_to_have_attribute"}
_REQUEST_VERBS = {"get", "post", "put", "patch", "delete", "head", "fetch"}
_GLOB_WAITS = {"wait_for_url", "expect_navigation"}
# Playwright's own names for the URL argument, which a caller may pass by
# keyword: `goto(url=)`, `to_have_url(url_or_reg_exp=)`, `fetch(url_or_request=)`.
_URL_KEYWORDS = ("url", "url_or_reg_exp", "url_or_request")


def _is_app_url(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "app_url"
    )


def _is_compiled_pattern(node: ast.AST) -> bool:
    """``re.compile(...)``, the one call a URL assertion may take unchecked."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "compile"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "re"
    )


def _built_from_page_url(node: ast.AST) -> bool:
    """``page.url``, a method or index on it, or a string starting with it:
    a value whose path is the page's own, so already under the mount."""
    if isinstance(node, ast.Attribute):
        return node.attr == "url"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return _built_from_page_url(node.func.value)
    if isinstance(node, ast.Subscript):
        return _built_from_page_url(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _built_from_page_url(node.left)
    if isinstance(node, ast.JoinedStr) and node.values:
        first = node.values[0]
        return isinstance(first, ast.FormattedValue) and _built_from_page_url(first.value)
    return False


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
    if _is_app_url(arg) or _built_from_page_url(arg):
        return True
    if isinstance(arg, ast.Name) and arg.id in bound:
        return all(_navigable(value, {}) for value in bound[arg.id])
    return False


def _argument(call: ast.Call, position: int, names: tuple[str, ...]) -> ast.AST | None:
    """The argument at ``position``, or passed by one of ``names``."""
    if len(call.args) > position:
        return call.args[position]
    return next((k.value for k in call.keywords if k.arg in names), None)


def _url_argument(call: ast.Call) -> ast.AST | None:
    return _argument(call, 0, _URL_KEYWORDS)


def _is_request_verb(func: ast.Attribute) -> bool:
    return (
        func.attr in _REQUEST_VERBS
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "request"
    )


def _pathname_read(node: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and "location.pathname" in n.value
        for n in ast.walk(node)
    )


def _call_offences(node: ast.Call, bound: dict[str, list[ast.AST]]) -> list[str]:
    assert isinstance(node.func, ast.Attribute)
    method, line = node.func.attr, f"line {node.lineno}"
    if method in _HREF_ASSERTIONS:
        name, value = _argument(node, 0, ("name",)), _argument(node, 1, ("value",))
        if (
            isinstance(name, ast.Constant)
            and name.value == "href"
            and value is not None
            and _root_literal(value)
        ):
            return [f"B2 {line}: {ast.unparse(value)}"]
        return []
    arg = _url_argument(node)
    if arg is None:
        return []
    if method in _NAVIGATIONS or _is_request_verb(node.func):
        if method in _URL_ASSERTIONS and _is_compiled_pattern(arg):
            return []
        if not _navigable(arg, bound):
            return [f"B1 {line}: {ast.unparse(arg)}"]
    if method in _GLOB_WAITS and _root_literal(arg):
        return [f"B1 {line}: {ast.unparse(arg)}"]
    return []


def offences(source: str) -> list[str]:
    tree = ast.parse(source)
    bound = _assignments(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            found += _call_offences(node, bound)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _LOCATION_TO_ROOT.search(node.value):
                found.append(f"B3 line {node.lineno}: {node.value!r}")
        if isinstance(node, ast.JoinedStr):
            # f"location.href = {x!r}", or with the quote in the literal:
            # the value sent is x.
            for part, value in zip(node.values, node.values[1:]):
                if (
                    isinstance(part, ast.Constant)
                    and _LOCATION_TO_VALUE.search(str(part.value))
                    and isinstance(value, ast.FormattedValue)
                    and not _is_app_url(value.value)
                ):
                    found.append(f"B3 line {node.lineno}: {ast.unparse(value.value)}")
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            for left, right in zip(operands, operands[1:]):
                for read, other in ((left, right), (right, left)):
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
        ('page.goto(url="/operator/sessions")', "B1"),
        ('PAGE = "/about"\npage.goto(PAGE)', "B1"),
        ('page.goto("/x?next=" + page.url)', "B1"),
        ("page.goto(f\"/operator/sessions/{resp.url.rsplit('/', 1)[1]}\")", "B1"),
        ('expect(page).to_have_url("/operator/sessions")', "B1"),
        ('expect(page).not_to_have_url("/operator/sessions")', "B1"),
        ('expect(page).to_have_url(str("/operator/sessions"))', "B1"),
        ("expect(page).to_have_url(build_url(sid))", "B1"),
        ('page.request.post("/operator/sessions")', "B1"),
        ('expect(page).to_have_url(url_or_reg_exp="/operator/sessions")', "B1"),
        ('page.request.fetch(url_or_request="/operator/sessions")', "B1"),
        ('page.wait_for_url("/operator/sessions")', "B1"),
        ('page.expect_navigation(url="/operator/sessions")', "B1"),
        ('expect(link).to_have_attribute("href", "/operator/sessions")', "B2"),
        ('expect(link).not_to_have_attribute("href", "/operator/sessions")', "B2"),
        ('expect(link).to_have_attribute(name="href", value="/operator/sessions")', "B2"),
        ('expect(link).to_have_attribute("href", value="/operator/sessions")', "B2"),
        ('page.evaluate("window.location.href = \'/about\'")', "B3"),
        ('page.evaluate("location.href = \'/about\'")', "B3"),
        ('page.evaluate("window.location.assign(\'/about\')")', "B3"),
        ('page.evaluate("window.location.replace(\'/about\')")', "B3"),
        ('page.evaluate(f"window.location.href = {MISSING!r}")', "B3"),
        ('page.evaluate(f"window.location.href = \'{path}\'")', "B3"),
        ('assert page.evaluate("window.location.pathname") == "/me"', "B3"),
        ('assert page.evaluate("location.pathname") == "/me"', "B3"),
        ('assert app_url("/me") == page.evaluate("location.pathname") == "/me"', "B3"),
    ],
)
def test_the_rules_catch_a_root_path(source: str, rule: str) -> None:
    [offence] = offences(source)
    assert offence.startswith(rule)


@pytest.mark.parametrize(
    "source",
    [
        'page.goto(app_url("/operator/sessions"))',
        'page.goto(url=app_url("/operator/sessions"))',
        'url = app_url("/me")\npage.goto(url)',
        "filtered = page.url\npage.goto(filtered)",
        'page.goto(page.url.split("?")[0] + "?editing=1")',
        'page.goto(f"{page.url}#owners")',
        'page.request.get(app_url("/operator/sessions"))',
        'page.wait_for_url("**/operator/sessions")',
        'expect(page).to_have_url(re.compile(r"/operator/sessions/\\w+"))',
        'expect(zip_all).to_have_attribute("href", "#")',
        'page.evaluate("window.location.href = \'/.auth/logout\'")',
        'page.evaluate(f"window.location.href = {app_url(MISSING)!r}")',
        'assert page.evaluate("window.location.pathname") == app_url("/me")',
    ],
)
def test_the_rules_pass_a_mounted_path(source: str) -> None:
    assert offences(source) == []
