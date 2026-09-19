"""The Workflow card's right column points at Validate, not at every issue.

Author's call, 2026-09-19 (19Q Item 4): *"Don't put the complete list
of Assignments related validation items in the workflow card. Rather,
link to Validate page, which has the full list in its table anyway."*

``_next_action_issue_list.html`` used to render every issue across all
three severities, uncapped, each with its own ``fix_url`` deep link, so
a session with several assignment warnings repeated "Assignments" down
the column.

**Coverage, stated rather than implied.** The partial is included at
three sites — State 3, State 4Err, and the ``W`` overlay — with
identical content, so the behaviour is pinned once at the site that has
a deterministic fixture (``W``), and
``test_the_card_includes_the_partial_at_exactly_three_sites`` keeps that
one case standing in for the other two. If a later change gives the
sites different content, that structural test fails and this file needs
per-state fixtures rather than one.
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from .test_workflow_card_w_overlay import _home, _prepared_session

CARD = "app/web/templates/operator/partials/next_action_card.html"

#: The markup the retired per-issue loop emitted. None of it may return.
RETIRED_MARKUP = (
    "next-action-issue-list",
    "next-action-issue-message",
    "next-action-issue-fix",
)


@dataclass(frozen=True)
class _FakeSession:
    """Just the ``session.id`` the partial reads, for the direct renders."""

    id: int


def _status_aside(body: str) -> str:
    """The card's right column, and only it.

    Scoped deliberately: `/validate` links exist elsewhere on Session
    Home (the Operations row, for one), so an unscoped `in body` would
    pass without the card rendering anything at all.
    """
    start = body.find('class="next-action-status"')
    assert start != -1, "right column not found"
    end = body.find("</aside>", start)
    assert end != -1, "right column not closed"
    return body[start:end]


def test_the_overlay_column_carries_one_validate_link(
    client: TestClient, db: Session
) -> None:
    session = _prepared_session(client, db, "ptr-one", warning=True)
    aside = _status_aside(_home(client, session.id))

    links = re.findall(
        rf'href="/operator/sessions/{session.id}/validate"', aside
    )
    assert len(links) == 1, (
        f"expected exactly one Validate link in the right column, got "
        f"{len(links)} — one per block, never one per severity"
    )
    assert aside.count("next-action-issue-pointer") == 1


def test_the_per_issue_enumeration_is_gone(
    client: TestClient, db: Session
) -> None:
    """The other half: the link replaced the list rather than joining it."""
    session = _prepared_session(client, db, "ptr-gone", warning=True)
    aside = _status_aside(_home(client, session.id))
    for marker in RETIRED_MARKUP:
        assert marker not in aside, (
            f"{marker!r} is back in the Workflow card's right column; the "
            f"per-issue list retired at 19Q Item 4"
        )


def test_the_premise_holds_there_really_are_issues_to_point_at(
    client: TestClient, db: Session
) -> None:
    """Anti-vacuity. Both cases above pass trivially on a card with
    nothing to report — and "nothing to report" is exactly what the
    guard below renders. Without this, a fixture that quietly stopped
    raising its W8 warning would keep them green."""
    session = _prepared_session(client, db, "ptr-premise", warning=True)
    aside = _status_aside(_home(client, session.id))
    counts = re.findall(r'<span class="pill[^"]*">(\d+) (?:warning|error)', aside)
    assert any(int(n) > 0 for n in counts), (
        f"fixture reports no warnings or errors, so the pointer cases "
        f"prove nothing; pills found: {counts}"
    )


def _render_partial(**context: object) -> str:
    """The partial alone, with a context handed to it directly.

    Through a page it cannot be reached with an empty issue set: the
    two unconditional include sites (States 3 and 4Err) both require a
    ``validation_summary``, and a draft that validates clean flips to
    ``validated`` rather than rendering State 3 with nothing in it. So
    a page-level "clean session" test exercises the *absence of the
    include*, not the guard inside it — which is how the first draft of
    this file passed while a mutant deleted the guard outright.
    """
    from jinja2 import Environment, FileSystemLoader

    root = pathlib.Path(__file__).resolve().parents[2] / "app/web/templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=True)
    template = env.get_template("operator/partials/_next_action_issue_list.html")
    return template.render(**context)


def test_the_guard_holds_a_link_back_when_there_is_nothing_to_point_at() -> None:
    """A context with every severity empty renders nothing at all —
    no link to an empty report."""
    rendered = _render_partial(
        session=_FakeSession(7),
        validation_issues_by_severity={"errors": [], "warnings": [], "info": []},
    )
    assert rendered.strip() == "", f"expected empty render, got: {rendered!r}"


def test_the_same_partial_does_render_when_there_is_something() -> None:
    """The control's control: an empty render above must mean the guard
    fired, not that the partial renders nothing whatever it is given."""
    rendered = _render_partial(
        session=_FakeSession(7),
        validation_issues_by_severity={
            "errors": [],
            "warnings": [{"message": "one thing"}],
            "info": [],
        },
    )
    assert 'href="/operator/sessions/7/validate"' in rendered
    assert rendered.count("next-action-issue-pointer") == 1


def test_a_state_without_issues_never_reaches_the_partial(
    client: TestClient, db: Session
) -> None:
    """The page-level half, stated for what it is: States 4 / 5 / 6
    without the overlay do not include the partial, so the column
    carries no pointer."""
    session = _prepared_session(client, db, "ptr-clean", warning=False)
    aside = _status_aside(_home(client, session.id))
    assert "next-action-issue-pointer" not in aside
    assert f'href="/operator/sessions/{session.id}/validate"' not in aside


def test_the_card_includes_the_partial_at_exactly_three_sites() -> None:
    """What lets the `W` case above stand in for States 3 and 4Err.

    All three includes render the same partial with the same context,
    so one measured case covers them — but only while there are three
    of them and nothing else renders issues. A fourth site, or a site
    that stops including the partial, means this file's coverage claim
    has changed.
    """
    from pathlib import Path

    card = Path(__file__).resolve().parents[2] / CARD
    source = card.read_text(encoding="utf-8")
    includes = re.findall(
        r'{%\s*include\s+"operator/partials/_next_action_issue_list\.html"\s*%}',
        source,
    )
    assert len(includes) == 3, (
        f"expected 3 includes of the issue partial in {CARD}, found "
        f"{len(includes)} — see this file's docstring on coverage"
    )
    for marker in RETIRED_MARKUP:
        assert marker not in source, (
            f"{marker!r} is back in {CARD}; the per-issue list retired "
            f"at 19Q Item 4"
        )
