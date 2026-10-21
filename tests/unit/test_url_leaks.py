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

**`ALLOWLIST` is exact and may only shrink.** It records, per rule and
file, the leaks the sweep has not reached. A rung that removes leaks
lowers its counts in the same change, so this file always states what is
left; at B7 it is empty and goes.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

from starlette.routing import Mount

from _rrw_app import rrw_app

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "app"
TEMPLATES = APP / "web" / "templates"
URLS_MODULE = "app/web/urls.py"

_HELPERS = re.compile(r"\b(?:url|is_here|here_in|here_under)\(")
_COMMENTS = re.compile(r"\{#.*?#\}|<!--.*?-->", re.DOTALL)
_TEMPLATED_ATTR = re.compile(r"""\b(?:href|action|formaction|src)=(["'])\{[{%]-?\s*+(?!url\()""")
_BARE_ROOT_ATTR = re.compile(r"""\b(?:href|action|formaction|src)=(["'])/\1""")
_URL_PATH = re.compile(r"\burl\.path\b")


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


def template_leaks() -> Counter[tuple[str, str]]:
    found: Counter[tuple[str, str]] = Counter()
    root = _root_literal()
    for path in sorted(TEMPLATES.rglob("*.html")):
        text = _blank_comments(path.read_text())
        spans = _helper_spans(text)
        name = _rel(path)
        for match in root.finditer(text):
            if not any(start <= match.start() < end for start, end in spans):
                found["T1", name] += 1
        found["T1", name] += len(_BARE_ROOT_ATTR.findall(text))
        found["T2", name] += len(_TEMPLATED_ATTR.findall(text))
        found["P3", name] += len(_URL_PATH.findall(text))
    return +found


def _is_cookie_path_call(node: ast.expr) -> bool:
    return isinstance(node, ast.Call) and (
        getattr(node.func, "id", None) == "cookie_path"
        or getattr(node.func, "attr", None) == "cookie_path"
    )


def python_leaks() -> Counter[tuple[str, str]]:
    found: Counter[tuple[str, str]] = Counter()
    for path in sorted(APP.rglob("*.py")):
        name = _rel(path)
        if name == URLS_MODULE:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call):
                func = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if func == "RedirectResponse":
                    found["P1", name] += 1
                if func == "set_cookie":
                    path_kw = next((k.value for k in node.keywords if k.arg == "path"), None)
                    if path_kw is None or not _is_cookie_path_call(path_kw):
                        found["P2", name] += 1
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "path"
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "url"
            ):
                found["P3", name] += 1
    return +found


# Leaks the sweep has not reached yet: (rule, file) -> count. Exact, and
# only ever lowered.
ALLOWLIST: dict[tuple[str, str], int] = {
    ("P1", "app/main.py"): 4,
    ("P1", "app/web/routes_guide.py"): 1,
    ("P1", "app/web/routes_operator/_assignments.py"): 5,
    ("P1", "app/web/routes_operator/_instruments.py"): 15,
    ("P1", "app/web/routes_operator/_lobby.py"): 7,
    ("P1", "app/web/routes_operator/_operations.py"): 12,
    ("P1", "app/web/routes_operator/_preview_surface.py"): 2,
    ("P1", "app/web/routes_operator/_quick_setup.py"): 5,
    ("P1", "app/web/routes_operator/_rehydrate.py"): 1,
    ("P1", "app/web/routes_operator/_session_home.py"): 14,
    ("P1", "app/web/routes_operator/_settings.py"): 3,
    ("P1", "app/web/routes_operator/_setup_invite.py"): 2,
    ("P1", "app/web/routes_operator/_setup_observers.py"): 3,
    ("P1", "app/web/routes_operator/_setup_relationships.py"): 3,
    ("P1", "app/web/routes_operator/_setup_reviewees.py"): 3,
    ("P1", "app/web/routes_operator/_setup_reviewers.py"): 3,
    ("P1", "app/web/routes_operator/_shared.py"): 4,
    ("P1", "app/web/routes_operator/_sys_admin.py"): 4,
    ("P1", "app/web/routes_operator/_workflow.py"): 20,
    ("P1", "app/web/routes_reviewer/_invite.py"): 1,
    ("P1", "app/web/routes_reviewer/_results.py"): 1,
    ("P1", "app/web/routes_reviewer/_summary.py"): 2,
    ("P1", "app/web/routes_reviewer/_surface/_routes.py"): 9,
    ("P2", "app/web/routes_operator/_operations.py"): 1,
    ("P2", "app/web/routes_operator/_sys_admin.py"): 2,
    ("P3", "app/web/error_handlers.py"): 4,
    ("P3", "app/web/templates/base.html"): 8,
    ("P3", "app/web/templates/operator/instruments_index.html"): 1,
    ("P3", "app/web/templates/operator/session_observers.html"): 1,
    ("P3", "app/web/templates/operator/session_relationships.html"): 1,
    ("P3", "app/web/templates/operator/session_reviewees.html"): 1,
    ("P3", "app/web/templates/operator/session_reviewers.html"): 1,
    ("P3", "app/web/templates/operator/session_setupinvite.html"): 2,
    ("P3", "app/web/templates/reviewer/_top_bar.html"): 5,
    ("T1", "app/web/templates/about.html"): 1,
    ("T1", "app/web/templates/base.html"): 15,
    ("T1", "app/web/templates/guide.html"): 41,
    ("T1", "app/web/templates/operator/instruments_index.html"): 16,
    ("T1", "app/web/templates/operator/operator_settings.html"): 3,
    ("T1", "app/web/templates/operator/partials/_email_preview_region.html"): 3,
    ("T1", "app/web/templates/operator/partials/_next_action_issue_list.html"): 1,
    ("T1", "app/web/templates/operator/partials/_quick_setup_card.html"): 3,
    ("T1", "app/web/templates/operator/partials/_roster_lock_card.html"): 2,
    ("T1", "app/web/templates/operator/partials/next_action_card.html"): 18,
    ("T1", "app/web/templates/operator/partials/session_top_nav.html"): 12,
    ("T1", "app/web/templates/operator/partials/sys_admin_top_nav.html"): 2,
    ("T1", "app/web/templates/operator/session_assignments.html"): 5,
    ("T1", "app/web/templates/operator/session_detail.html"): 8,
    ("T1", "app/web/templates/operator/session_extract_data.html"): 15,
    ("T1", "app/web/templates/operator/session_invitations.html"): 6,
    ("T1", "app/web/templates/operator/session_invitations_reviewer_detail.html"): 2,
    ("T1", "app/web/templates/operator/session_new.html"): 2,
    ("T1", "app/web/templates/operator/session_observers.html"): 2,
    ("T1", "app/web/templates/operator/session_rehydrate.html"): 4,
    ("T1", "app/web/templates/operator/session_relationships.html"): 4,
    ("T1", "app/web/templates/operator/session_responses.html"): 3,
    ("T1", "app/web/templates/operator/session_responses_reviewee_detail.html"): 1,
    ("T1", "app/web/templates/operator/session_reviewees.html"): 3,
    ("T1", "app/web/templates/operator/session_reviewers.html"): 2,
    ("T1", "app/web/templates/operator/session_setupinvite.html"): 6,
    ("T1", "app/web/templates/operator/session_validate.html"): 4,
    ("T1", "app/web/templates/operator/sessions_archived.html"): 3,
    ("T1", "app/web/templates/operator/sessions_list.html"): 16,
    ("T1", "app/web/templates/operator/sys_admin_session_audit_log.html"): 1,
    ("T1", "app/web/templates/operator/sys_admin_session_outbox.html"): 1,
    ("T1", "app/web/templates/operator/sys_admin_sessions.html"): 4,
    ("T1", "app/web/templates/operator/sys_admin_users.html"): 1,
    ("T1", "app/web/templates/reviewer/_action_row.html"): 2,
    ("T1", "app/web/templates/reviewer/_top_bar.html"): 8,
    ("T1", "app/web/templates/reviewer/dashboard.html"): 1,
    ("T1", "app/web/templates/reviewer/invite_mismatch.html"): 1,
    ("T1", "app/web/templates/reviewer/pre_open.html"): 1,
    ("T1", "app/web/templates/reviewer/results.html"): 1,
    ("T1", "app/web/templates/reviewer/review_surface.html"): 4,
    ("T1", "app/web/templates/reviewer/summary.html"): 3,
    ("T2", "app/web/templates/_partials/breadcrumb.html"): 1,
    ("T2", "app/web/templates/_partials/profile_value.html"): 1,
    ("T2", "app/web/templates/about.html"): 1,
    ("T2", "app/web/templates/error.html"): 2,
    ("T2", "app/web/templates/guide.html"): 1,
    ("T2", "app/web/templates/me_debug.html"): 1,
    ("T2", "app/web/templates/operator/operator_settings.html"): 2,
    ("T2", "app/web/templates/operator/partials/_extract_data_card.html"): 1,
    ("T2", "app/web/templates/operator/partials/_field_labels_editor.html"): 1,
    ("T2", "app/web/templates/operator/partials/_pager_cluster.html"): 2,
    ("T2", "app/web/templates/operator/partials/_quick_setup_card.html"): 2,
    ("T2", "app/web/templates/operator/partials/_upload_problems.html"): 2,
    ("T2", "app/web/templates/operator/partials/next_action_card.html"): 2,
    ("T2", "app/web/templates/operator/partials/validation_results.html"): 2,
    ("T2", "app/web/templates/operator/session_assignments.html"): 2,
    ("T2", "app/web/templates/operator/session_extract_data.html"): 2,
    ("T2", "app/web/templates/operator/session_observers.html"): 11,
    ("T2", "app/web/templates/operator/session_relationships.html"): 13,
    ("T2", "app/web/templates/operator/session_reviewees.html"): 11,
    ("T2", "app/web/templates/operator/session_reviewers.html"): 11,
    ("T2", "app/web/templates/operator/sys_admin_session_audit_log.html"): 5,
    ("T2", "app/web/templates/operator/sys_admin_sessions.html"): 1,
    ("T2", "app/web/templates/operator/sys_admin_users.html"): 4,
    ("T2", "app/web/templates/reviewer/_action_row.html"): 2,
    ("T2", "app/web/templates/reviewer/_role_chips.html"): 1,
    ("T2", "app/web/templates/reviewer/collation.html"): 1,
    ("T2", "app/web/templates/reviewer/dashboard.html"): 4,
}


def test_no_url_leaks_beyond_the_allowlist() -> None:
    found = template_leaks() + python_leaks()
    allowed = Counter(ALLOWLIST)
    over = {key: (found[key], allowed[key]) for key in found if found[key] > allowed[key]}
    under = {key: (found[key], allowed[key]) for key in allowed if found[key] < allowed[key]}
    assert not over, (
        "URLs emitted without the mount prefix ((rule, file): (found, allowed)); "
        f"use url() / redirect() / cookie_path() / here() (app/web/urls.py): {over}"
    )
    assert not under, (
        f"Fewer leaks than allowed; lower ALLOWLIST to match ((rule, file): (found, allowed)): {under}"
    )


def test_segments_come_from_the_router() -> None:
    assert {"operator", "me", "static"} <= set(_segments())


def test_the_rules_catch_a_planted_leak(tmp_path: Path) -> None:
    root = _root_literal()
    text = _blank_comments(
        """<a href="/operator/x">a</a> <a href="{{ url('/me') }}">b</a>
        {# <a href="/me">c</a> #} <a href="{{ link }}">d</a> <a href="/">e</a>
        {% if is_here("/guide") %}{% endif %}"""
    )
    spans = _helper_spans(text)
    leaks = [m for m in root.finditer(text) if not any(s <= m.start() < e for s, e in spans)]
    assert len(leaks) == 1
    assert len(_TEMPLATED_ATTR.findall(text)) == 1
    assert len(_BARE_ROOT_ATTR.findall(text)) == 1
