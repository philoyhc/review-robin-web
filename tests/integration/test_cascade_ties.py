r"""Same-specificity ties among canonical classes in ``base.html`` (19K.6).

`base.html` owns the app's whole stylesheet inline — deliberately, per
`CLAUDE.md` and `spec/architecture.md`. The cost is that two rules can
tie on specificity and the later one wins silently. During 19J.9,
``body.ui-v2 .table-pager-step`` was **dead from rung 1 until the fifth
of that item's seven merges**: it and ``body.ui-v2 .btn-icon`` are both
(0,2,1), ``.btn-icon`` sits later, and nobody could see it because the
loser's declarations happened to match what the winner already set. It
surfaced only when someone asked for a bigger glyph and the glyph did
not change. `spec/ui_elements.md` §6 records the hazard in prose; this
is the check.

**What this resolves, and what it cannot.** It reads the rendered markup
for elements carrying two or more classes, parses the ``<style>``
element, computes specificity, and reports a tie where two rules that
both match one element declare the same property — the earlier one is
dead. It is deliberately narrow:

* **simple class selectors only** — an optional ``body.ui-v2`` prefix
  then a compound of classes. Combinator rules (``.page-grid .card``)
  need ancestor matching over a parsed tree and are a separate rung;
  `.page-grid` and `card` never share an element, so a same-element
  check is structurally blind to them.
* **top-level rules only** — rules inside ``@media`` apply at some
  viewports and not others, so comparing them against unconditional
  rules would report ties that cannot both be live.
* **no inline ``style=``**, which always beats a class selector and is
  not in the stylesheet at all.
* **exact property names**, so a shorthand overriding a longhand
  (``background`` against ``background-color``) is not seen.

Each exclusion can make the check *silent*; none can make it report a
tie that is not there. That asymmetry is the point: a false negative
costs what we already have, a false positive would cost trust.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

BASE = pathlib.Path(__file__).resolve().parents[2] / "app/web/templates/base.html"

# Classes `spec/ui_elements.md` names canonical: the §6 button roles and
# the §10 primitives that appear as simple class selectors. A tie
# involving one of these is a defect by definition — the repo has
# committed to keeping them stable. A tie between two ad-hoc classes may
# be intentional and is not reported.
CANONICAL = frozenset({
    # §6 buttons
    "btn", "secondary", "alert", "alert-solid", "destructive",
    "danger-solid", "danger", "btn-cta", "btn-icon",
    # §10 primitives that live on an element rather than in a combinator
    "table-pager-step", "table-pager-cluster", "table-pager-menu",
    "btn-row", "btn-pair", "chip-group",
})

_SIMPLE = re.compile(r"^(?:body\.ui-v2\s+)?(?:\.[A-Za-z0-9_-]+)+$")
_CLASS = re.compile(r"\.([A-Za-z0-9_-]+)")
_ELEMENT = re.compile(r"(?:^|\s|>|\+|~)([a-z][a-z0-9]*)")


def _specificity(selector: str) -> tuple[int, int, int]:
    """(ids, classes, elements) — CSS 2.1 specificity for a simple selector.

    Checked against the two values `spec/ui_elements.md` §6 states in
    prose: ``body.ui-v2 .btn-icon`` is (0,2,1) and the specialising
    ``body.ui-v2 .btn-icon.table-pager-step`` is (0,3,1).
    """
    return (
        selector.count("#"),
        len(_CLASS.findall(selector)) + selector.count("["),
        len(_ELEMENT.findall(selector)),
    )


def _style_element(html: str) -> str:
    """The CSS inside the real ``<style>`` element.

    Located by walking lines rather than by regex: `base.html:9` carries
    a Jinja comment whose *text* contains the literal string
    ``<style>``, and a non-greedy regex over the raw template matches
    that instead, swallowing the no-FOUC script as if it were CSS. That
    cost a wrong figure in this item's own plan (19K.9).
    """
    lines = html.splitlines()
    start = next(
        i for i, line in enumerate(lines)
        if line.strip().startswith("<style") and "{#" not in line
    )
    end = next(i for i, line in enumerate(lines) if "</style>" in line)
    return "\n".join(lines[start + 1:end])


def _top_level_rules(css: str) -> list[tuple[str, dict[str, str], int]]:
    """(selector, declarations, source order) for every top-level rule.

    Brace-walked rather than regex-matched so that rules nested inside
    ``@media`` are skipped rather than silently flattened into the
    unconditional set.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rules: list[tuple[str, dict[str, str], int]] = []
    depth, buf, order = 0, "", 0
    i = 0
    while i < len(css):
        ch = css[i]
        if ch == "{":
            depth += 1
            if depth == 1:
                selector_text, body_start = buf.strip(), i + 1
                if selector_text.startswith("@"):
                    # Skip the whole at-rule block.
                    inner = 1
                    j = i + 1
                    while j < len(css) and inner:
                        inner += (css[j] == "{") - (css[j] == "}")
                        j += 1
                    depth, i, buf = 0, j, ""
                    continue
                j = css.index("}", body_start)
                declarations: dict[str, str] = {}
                for decl in css[body_start:j].split(";"):
                    if ":" in decl:
                        key, value = decl.split(":", 1)
                        declarations[key.strip()] = value.strip()
                for selector in (s.strip() for s in selector_text.split(",")):
                    order += 1
                    if _SIMPLE.match(selector):
                        rules.append((selector, declarations, order))
                depth, i, buf = 0, j + 1, ""
                continue
        elif ch == "}":
            depth = max(0, depth - 1)
            buf = ""
        else:
            buf += ch
        i += 1
    return rules


def _class_sets(html: str) -> set[frozenset[str]]:
    """Every multi-class element class set in a rendered page."""
    return {
        frozenset(m.split())
        for m in re.findall(r'class="([^"]+)"', html)
        if len(m.split()) > 1
    }


def _is_variant_of(later: set[str], earlier: set[str]) -> bool:
    """Does `later` name a variant of something `earlier` names?

    `.table-pager-cluster-bottom` extends `.table-pager-cluster` — the
    repo's convention for a variant, and a variant is *meant* to
    override its base. Matching on the `-` boundary rather than a bare
    prefix so `.btn` does not read as the base of `.btn-icon`'s
    unrelated neighbours.
    """
    return any(
        name != base and name.startswith(base + "-")
        for name in later
        for base in earlier
    )


def find_ties(
    css: str, class_sets: set[frozenset[str]]
) -> list[tuple[str, str, str]]:
    """(dead selector, winning selector, property) for each live tie.

    A tie where the **variant comes later and wins** is the CSS idiom
    working, not a defect: `.table-pager-cluster-bottom` deliberately
    overrides `.table-pager-cluster`'s `display`, and `base.html` says
    so in a comment beside it. Found by running this check against the
    real stylesheet, which is the only way that distinction was going to
    surface.

    A tie where the **variant comes earlier and loses** is 19J.9 — the
    author wrote a specialisation and the base silently ate it. That is
    what this reports.
    """
    rules = _top_level_rules(css)
    found: list[tuple[str, str, str]] = []
    for classes in class_sets:
        matching = [
            (sel, decls, order, _specificity(sel))
            for sel, decls, order in rules
            if set(_CLASS.findall(sel)) - {"ui-v2"} <= classes
        ]
        for i, (sel_a, decls_a, order_a, spec_a) in enumerate(matching):
            for sel_b, decls_b, order_b, spec_b in matching[i + 1:]:
                if spec_a != spec_b or sel_a == sel_b:
                    continue
                names = set(_CLASS.findall(sel_a)) | set(_CLASS.findall(sel_b))
                if not (names & CANONICAL):
                    continue
                dead, winner = (
                    (sel_a, sel_b) if order_a < order_b else (sel_b, sel_a)
                )
                dead_decls = decls_a if order_a < order_b else decls_b
                live_decls = decls_b if order_a < order_b else decls_a
                dead_names = set(_CLASS.findall(dead)) - {"ui-v2"}
                live_names = set(_CLASS.findall(winner)) - {"ui-v2"}
                if _is_variant_of(live_names, dead_names):
                    continue  # the variant wins, which is the intent
                for prop in sorted(set(dead_decls) & set(live_decls)):
                    entry = (dead, winner, prop)
                    if entry not in found:
                        found.append(entry)
    return found


# The pager renders only above the page size, and its steps are the
# `.btn-icon` role — the exact element 19J.9's collision sat on. A
# fixture smaller than this renders no pager at all, and the end-to-end
# check below then passes against the very mutation it exists to catch.
# Measured while writing this file: with an empty session, **zero** of
# the 46 collected class sets contained `btn-icon` or
# `table-pager-step`.
_ROSTER_ROWS = 220


def _rendered_pages(client: TestClient, db: Session) -> list[str]:
    client.post(
        "/operator/sessions",
        data={"name": "Cascade", "code": "CASCADE", "description": "d"},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "CASCADE")
    ).scalar_one()
    csv = b"ReviewerName,ReviewerEmail\n" + b"".join(
        f"R{i},r{i}@example.edu\n".encode() for i in range(_ROSTER_ROWS)
    )
    client.post(
        f"/operator/sessions/{session.id}/reviewers/import",
        files={"file": ("r.csv", csv, "text/csv")},
        follow_redirects=False,
    )
    urls = [
        "/operator/sessions",
        f"/operator/sessions/{session.id}",
        f"/operator/sessions/{session.id}/assignments",
        f"/operator/sessions/{session.id}/reviewers",
        f"/operator/sessions/{session.id}/instruments",
        "/guide",
    ]
    pages = []
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, (url, response.status_code)
        pages.append(response.text)
    return pages


# --------------------------------------------------------------------
# the resolver's own arithmetic


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        # The two values `spec/ui_elements.md` §6 states in prose.
        ("body.ui-v2 .btn-icon", (0, 2, 1)),
        ("body.ui-v2 .btn-icon.table-pager-step", (0, 3, 1)),
        (".btn", (0, 1, 0)),
        (".btn.secondary", (0, 2, 0)),
    ],
)
def test_specificity_matches_the_spec(selector, expected) -> None:
    assert _specificity(selector) == expected


def test_media_rules_are_not_treated_as_unconditional() -> None:
    """A rule inside ``@media`` applies at some viewports only, so
    comparing it against an unconditional rule would report a tie that
    cannot be live. `base.html` has 14 such blocks.

    The block carries **two** rules deliberately. With one, the brace
    walk mangles the nested rule and drops it either way, so a
    single-rule fixture passes whether the at-rule is skipped or not —
    it pins nothing. The second rule is the one that leaks.
    """
    css = (
        "@media (max-width: 700px) { .a.b { color: blue; } "
        ".e.f { color: red; } }\n.c.d { color: green; }\n"
    )
    assert [sel for sel, _, _ in _top_level_rules(css)] == [".c.d"]


def test_combinator_rules_are_not_parsed_as_simple() -> None:
    """`.page-grid .card` needs ancestor matching this resolver does not
    do, and its two names never share an element. Silently treating it
    as a compound would match the wrong things."""
    css = ".page-grid .card { margin-bottom: 0; } .btn.secondary { color: red; }"
    assert [sel for sel, _, _ in _top_level_rules(css)] == [".btn.secondary"]


def test_the_style_element_is_located_without_the_jinja_comment() -> None:
    """`base.html:9`'s Jinja comment contains the literal text
    ``<style>``; a regex matches it and swallows the no-FOUC script."""
    css = _style_element(BASE.read_text())
    assert "DOMContentLoaded" not in css.split("\n")[0]
    assert css.lstrip().startswith((":root", "/*", "html", "body", "*"))


# --------------------------------------------------------------------
# the check itself


def test_a_canonical_tie_is_reported() -> None:
    """19J.9's collision, reconstructed: two (0,2,1) rules both matching
    a `btn-icon table-pager-step` element and both setting `font-size`;
    the later wins and the earlier is dead."""
    css = (
        "body.ui-v2 .table-pager-step { font-size: 1.5em; }\n"
        "body.ui-v2 .btn-icon { font-size: 1em; }\n"
    )
    ties = find_ties(css, {frozenset({"btn-icon", "table-pager-step"})})
    assert ties == [
        ("body.ui-v2 .table-pager-step", "body.ui-v2 .btn-icon", "font-size")
    ]


def test_the_real_fix_is_not_reported() -> None:
    """The shipped selector carries `.btn-icon`, making it (0,3,1) — it
    wins on specificity, not on order, so there is no tie."""
    css = (
        "body.ui-v2 .btn-icon.table-pager-step { font-size: 1.5em; }\n"
        "body.ui-v2 .btn-icon { font-size: 1em; }\n"
    )
    assert find_ties(css, {frozenset({"btn-icon", "table-pager-step"})}) == []


def test_two_ad_hoc_classes_tying_is_not_reported() -> None:
    """Scope. A tie between classes the repo has not committed to may be
    deliberate; reporting it would make the check noise in a week."""
    css = ".alpha { color: red; }\n.beta { color: blue; }\n"
    assert find_ties(css, {frozenset({"alpha", "beta"})}) == []


def test_classes_that_never_share_an_element_do_not_tie() -> None:
    """Co-occurrence is the whole reason this needs rendered markup:
    two rules tying matters only if some element carries both."""
    css = "body.ui-v2 .btn { color: red; }\nbody.ui-v2 .other { color: blue; }\n"
    assert find_ties(css, {frozenset({"btn", "unrelated"})}) == []


def test_different_properties_do_not_tie() -> None:
    """Two rules can tie on specificity and not collide at all."""
    css = "body.ui-v2 .btn { color: red; }\nbody.ui-v2 .thing { padding: 0; }\n"
    assert find_ties(css, {frozenset({"btn", "thing"})}) == []


def test_base_html_has_no_live_canonical_tie(
    client: TestClient, db: Session
) -> None:
    """The check, against the real stylesheet and real pages.

    If this fails, a canonical rule is dead in the shipped app: read the
    named pair, decide which should win, and specialise the loser's
    selector as 19J.9 did — do not delete the rule.
    """
    css = _style_element(BASE.read_text())
    class_sets: set[frozenset[str]] = set()
    for page in _rendered_pages(client, db):
        class_sets |= _class_sets(page)

    ties = find_ties(css, class_sets)
    assert not ties, "\n".join(
        f"`{dead}` is dead: `{winner}` ties it and sets `{prop}` later"
        for dead, winner, prop in ties
    )


def test_a_variant_winning_later_is_not_reported() -> None:
    """`.table-pager-cluster-bottom` overrides `.table-pager-cluster`'s
    `display` on purpose, and `base.html` says so in a comment. A
    variant that comes later and wins is the idiom working. This case is
    live in the shipped stylesheet and was found by running the check
    against it."""
    css = (
        "body.ui-v2 .table-pager-cluster { display: inline-flex; }\n"
        "body.ui-v2 .table-pager-cluster-bottom { display: flex; }\n"
    )
    classes = {frozenset({"table-pager-cluster", "table-pager-cluster-bottom"})}
    assert find_ties(css, classes) == []


def test_a_variant_losing_earlier_is_reported() -> None:
    """The half that must not regress. Order-reversed, the same pair is
    19J.9's shape: the specialisation is written first and the base
    silently eats it. Suppressing variants outright would hide exactly
    the defect this check exists for."""
    css = (
        "body.ui-v2 .table-pager-cluster-bottom { display: flex; }\n"
        "body.ui-v2 .table-pager-cluster { display: inline-flex; }\n"
    )
    classes = {frozenset({"table-pager-cluster", "table-pager-cluster-bottom"})}
    assert find_ties(css, classes) == [
        (
            "body.ui-v2 .table-pager-cluster-bottom",
            "body.ui-v2 .table-pager-cluster",
            "display",
        )
    ]


def test_the_fixture_renders_the_classes_the_check_needs(
    client: TestClient, db: Session
) -> None:
    """Non-vacuity, as its own test rather than an assertion inside the
    check — deleting a guard that lives beside the thing it guards is
    invisible, and a mutation proved it: removing the inline version
    left every test green.

    Asserted on the classes that matter, not on a count. With an
    empty-session fixture this file collected **46** class sets and not
    one carried `btn-icon` or `table-pager-step`: the pager renders only
    above the page size, so the end-to-end check would have passed
    against 19J.9's own collision. "The pages rendered something" is not
    evidence that the check looked at anything.
    """
    class_sets: set[frozenset[str]] = set()
    for page in _rendered_pages(client, db):
        class_sets |= _class_sets(page)
    covered = {name for classes in class_sets for name in classes} & CANONICAL
    for required in ("btn", "btn-icon", "table-pager-step"):
        assert required in covered, (
            f"no rendered element carries `{required}`, so the cascade check "
            f"cannot see a tie involving it. Covered: {sorted(covered)}"
        )
