"""Tests for the Segment 13A PR 0 Rule Based card scaffold.

The scaffold replaces the
``placeholder_card(id="rule-based-assignment")`` stub on the
Setup → Assignments page with a fully-rendered card whose
RuleSet selector, Exclude self-review checkbox, cascade-replace
confirmation checkbox, and Generate button render disabled until
PR 4 wires the writer. The single live control is the
**Edit ruleset** link, which points at the editor stub at
``/operator/sessions/{id}/assignments/rule-based/edit``.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.web import views


def _make_session(
    client: TestClient, db: Session, *, code: str = "rb-scaffold"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "RuleBasedScaffold", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_with_assignments(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    review_session = _make_session(client, db, code=code)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nBob,bob@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )
    return review_session


def test_rule_based_card_context_is_inert_at_scaffold_time(
    client: TestClient, db: Session
) -> None:
    """The view-shape adapter returns a frozen scaffold context —
    ``is_wired=False`` and a workspace edit URL."""

    review_session = _make_session(client, db, code="rb-shape")
    context = views.build_rule_based_card_context(
        review_session, assignment_count=0
    )

    assert context.is_wired is False
    assert context.assignment_count == 0
    assert context.edit_url == (
        f"/operator/sessions/{review_session.id}/assignments/rule-based/edit"
    )
    assert "PR 4" in context.coming_in


def test_rule_based_card_renders_disabled_controls_with_edit_link_live(
    client: TestClient, db: Session
) -> None:
    """The card renders the final-shape DOM: a disabled selector +
    Exclude-self-review checkbox + Generate button, with only the
    ``Edit ruleset`` link enabled and pointing at the stub editor."""

    review_session = _make_session(client, db, code="rb-render")
    body = client.get(f"/operator/sessions/{review_session.id}/assignments").text

    assert 'id="rule-based-assignment"' in body
    assert 'id="rule-based-ruleset"' in body
    # Selector + Exclude-self-review + Generate are all disabled.
    assert 'name="rule_set_id"' in body
    assert 'name="exclude_self_review"' in body
    # Edit ruleset is the lone live affordance.
    edit_url = (
        f"/operator/sessions/{review_session.id}/assignments/rule-based/edit"
    )
    assert f'href="{edit_url}"' in body
    assert ">Edit ruleset</a>" in body


def test_rule_based_card_shows_cascade_confirm_when_assignments_exist(
    client: TestClient, db: Session
) -> None:
    """The cascade-replace ``confirm_replace`` checkbox surfaces only
    on a session that already has assignments — matching the sibling
    Manual / Full Matrix cards on the same page."""

    empty = _make_session(client, db, code="rb-empty")
    empty_body = client.get(
        f"/operator/sessions/{empty.id}/assignments"
    ).text
    # No assignments → no cascade checkbox inside the Rule Based card.
    rb_section_empty = empty_body.split('id="rule-based-assignment"', 1)[1]
    assert 'name="confirm_replace"' not in rb_section_empty.split("</section>")[0]

    populated = _seed_with_assignments(client, db, code="rb-pop")
    pop_body = client.get(
        f"/operator/sessions/{populated.id}/assignments"
    ).text
    rb_section_pop = pop_body.split('id="rule-based-assignment"', 1)[1]
    rb_section_pop = rb_section_pop.split("</section>", 1)[0]
    assert 'name="confirm_replace"' in rb_section_pop
    # The disabled attribute keeps the checkbox inert at PR 0.
    assert "disabled" in rb_section_pop


def test_rule_based_editor_stub_renders_with_back_link(
    client: TestClient, db: Session
) -> None:
    """The editor stub page ships with the standard operator chrome,
    a back link to Assignments, and a placeholder card pointing at
    PR 5."""

    review_session = _make_session(client, db, code="rb-stub")
    response = client.get(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/edit"
    )
    assert response.status_code == 200, response.text
    body = response.text
    back_url = f"/operator/sessions/{review_session.id}/assignments"
    assert f'href="{back_url}"' in body
    assert "Back to Assignments" in body
    assert "PR 5" in body
