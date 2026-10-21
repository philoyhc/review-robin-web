"""No URL RRW emits may lose the mount's prefix.

Segment 21B (`guide/segment_21B_url_sweep.md`): app-relative values
travel, and the prefix is added once, at emission (`app/web/urls.py`).
These static rules find every emission that skips it:

- **T1.** In a template, a quoted root path (one starting with an RRW
  top-level segment) appears only inside ``url(``, ``is_here(``,
  ``here_in(`` or ``here_under(``; a bare ``"/"`` link counts too.
- **T2.** A templated ``href`` / ``action`` / ``formaction`` / ``src``
  value starts with ``url(``.
- **P1.** ``RedirectResponse(`` is built only in ``app/web/urls.py``.
- **P2.** Every ``set_cookie`` passes ``path=cookie_path(...)``.
- **P3.** Nothing but ``app/web/urls.py`` reads ``.url.path``; templates
  use ``here()``.

The top-level segments come from RRW's own router, not a list kept here,
so a new top-level route is covered with no edit. ``/.auth/`` is the
host's (v0.8 §3) and is not an RRW path.

**The allowlist is exact and may only shrink.** `url_leaks_allowlist.json`
records each leak the sweep has not reached, by rule, file and the
leaking source itself (whitespace collapsed), so a fixed leak cannot be
traded for a new one in the same file. A rung that removes leaks deletes
their entries in the same change, so the file always states what is
left; at B7 it is empty and goes.
"""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
from pathlib import Path

from starlette.routing import Mount

from _rrw_app import rrw_app

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "app"
TEMPLATES = APP / "web" / "templates"
URLS_MODULE = "app/web/urls.py"
ALLOWLIST_FILE = Path(__file__).with_name("url_leaks_allowlist.json")

_HELPERS = re.compile(r"\b(?:url|is_here|here_in|here_under)\(")
# Jinja and HTML comments, CSS and script block comments, and script
# line comments: none of them is emitted as a URL.
_COMMENTS = re.compile(
    r"\{#.*?#\}|<!--.*?-->|/\*.*?\*/|^[ \t]*//[^\n]*", re.DOTALL | re.MULTILINE
)
_TEMPLATED_ATTR = re.compile(r"""\b(?:href|action|formaction|src)=(["'])\{[{%]-?\s*+(?!url\()""")
_BARE_ROOT_ATTR = re.compile(r"""\b(?:href|action|formaction|src)=(["'])/\1""")
_URL_PATH = re.compile(r"\burl\.path\b")
_HELPER_NAMES = r"(?:url|here|is_here|here_in|here_under)"
_REBINDS = re.compile(
    rf"\{{%-?\s*(?:set\s+{_HELPER_NAMES}\b|for\s+[^%]*\b{_HELPER_NAMES}\b[^%]*\bin\b)"
    rf"|\bmacro\s+\w+\([^)]*\b{_HELPER_NAMES}\b"
)


def _segments() -> list[str]:
    app = rrw_app()
    paths = list(app.openapi()["paths"]) + [r.path for r in app.routes if isinstance(r, Mount)]
    return sorted({p.split("/")[1] for p in paths if p.count("/") >= 1 and p.split("/")[1]})


def _root_literal() -> re.Pattern[str]:
    alternatives = "|".join(re.escape(s) for s in _segments())
    return re.compile(rf"""(["'`])/(?:{alternatives})(?=[/"'`?#{{$\s])""")


def _blank_comments(text: str) -> str:
    return _COMMENTS.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text)


def _helper_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    for match in _HELPERS.finditer(text):
        depth, i = 1, match.end()
        while i < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        spans.append((match.start(), i))
    return spans


def _rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


Leak = tuple[str, str, str]  # (rule, file, the leaking source, whitespace-collapsed)


def _norm(text: str) -> str:
    return " ".join(text.split())


def _line_at(text: str, offset: int) -> str:
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    return _norm(text[start : end if end != -1 else len(text)])


def _template_text_leaks(raw: str, name: str, root: re.Pattern[str]) -> Counter[Leak]:
    found: Counter[Leak] = Counter()
    text = _blank_comments(raw)
    spans = _helper_spans(text)
    for match in root.finditer(text):
        if not any(start <= match.start() < end for start, end in spans):
            found["T1", name, _line_at(text, match.start())] += 1
    for rule, pattern in (("T1", _BARE_ROOT_ATTR), ("T2", _TEMPLATED_ATTR), ("P3", _URL_PATH)):
        for match in pattern.finditer(text):
            found[rule, name, _line_at(text, match.start())] += 1
    return found


def template_leaks() -> Counter[Leak]:
    found: Counter[Leak] = Counter()
    root = _root_literal()
    for path in sorted(TEMPLATES.rglob("*.html")):
        found += _template_text_leaks(path.read_text(), _rel(path), root)
    return found


def _is_cookie_path_call(node: ast.expr) -> bool:
    return isinstance(node, ast.Call) and (
        getattr(node.func, "id", None) == "cookie_path"
        or getattr(node.func, "attr", None) == "cookie_path"
    )


def python_leaks() -> Counter[Leak]:
    """Each leak is keyed by its whole call (P1, P2) or line (P3), so a
    fixed leak cannot be traded for a new one in the same file."""
    found: Counter[Leak] = Counter()
    for path in sorted(APP.rglob("*.py")):
        name = _rel(path)
        if name == URLS_MODULE:
            continue
        source = path.read_text()
        lines = source.splitlines()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call):
                func = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                call = _norm(ast.get_source_segment(source, node) or "")
                if func == "RedirectResponse":
                    found["P1", name, call] += 1
                if func == "set_cookie":
                    path_kw = next((k.value for k in node.keywords if k.arg == "path"), None)
                    if path_kw is None or not _is_cookie_path_call(path_kw):
                        found["P2", name, call] += 1
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "path"
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "url"
            ):
                found["P3", name, _norm(lines[node.lineno - 1])] += 1
    return found


def allowlist() -> Counter[Leak]:
    """Leaks the sweep has not reached yet, one entry per leaking source.
    Exact, and only ever shrunk."""
    entries = json.loads(ALLOWLIST_FILE.read_text())
    return Counter({(rule, file, text): count for rule, file, text, count in entries})


def test_no_url_leaks_beyond_the_allowlist() -> None:
    found = template_leaks() + python_leaks()
    allowed = allowlist()
    new = sorted((found - allowed).elements())
    stale = sorted((allowed - found).elements())
    assert not new, (
        "URLs emitted without the mount prefix; use url() / redirect() / "
        f"cookie_path() / here() (app/web/urls.py): {new}"
    )
    assert not stale, (
        f"Allowlisted leaks no longer found; remove them from {_rel(ALLOWLIST_FILE)}: {stale}"
    )


def test_no_template_rebinds_a_url_helper() -> None:
    """A ``{% set url = … %}`` or a loop variable named ``here`` hides the
    global for the rest of its scope, and every link under it renders
    unprefixed."""
    found = [
        _rel(path)
        for path in sorted(TEMPLATES.rglob("*.html"))
        if _REBINDS.search(_blank_comments(path.read_text()))
    ]
    assert not found, f"templates rebind a URL helper name: {found}"


def test_segments_come_from_the_router() -> None:
    assert {"operator", "me", "static"} <= set(_segments())


def test_the_rules_catch_a_planted_leak() -> None:
    planted = """<a href="/operator/x">a</a> <a href="{{ url('/me') }}">b</a>
    {# <a href="/me">c</a> #} <a href="{{ link }}">d</a> <a href="/">e</a>
    {% if is_here("/guide") %}{% endif %} {{ request.url.path }}"""
    found = _template_text_leaks(planted, "t.html", _root_literal())
    assert sorted(rule for rule, _, _ in found.elements()) == ["P3", "T1", "T1", "T2"]


def test_a_fixed_leak_cannot_be_traded_for_a_new_one() -> None:
    root = _root_literal()
    before = _template_text_leaks('<a href="/me">a</a>\n<a href="{{ url(\'/guide\') }}">b</a>', "t.html", root)
    after = _template_text_leaks('<a href="{{ url(\'/me\') }}">a</a>\n<a href="/guide">b</a>', "t.html", root)
    assert sum(before.values()) == sum(after.values()) == 1
    assert after - before
