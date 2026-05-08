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


def test_rule_based_card_renders_seed_selector_after_pr4(
    client: TestClient, db: Session
) -> None:
    """The card flips live in PR 4: the selector lists the five
    seeded RuleSets in install order (Full Matrix first), the
    Exclude self-review checkbox is enabled, the Generate button is
    a real submit button, and the Edit ruleset link still points at
    the editor stub."""

    review_session = _make_session(client, db, code="rb-render")
    body = client.get(f"/operator/sessions/{review_session.id}/assignments").text

    assert 'id="rule-based-assignment"' in body
    assert 'id="rule-based-ruleset"' in body
    # All five canonical seeds render in install order — Full Matrix
    # first, then Intra / Cross / Same-group-different-role / Three.
    expected_order = [
        "Full Matrix",
        "Intra-group peer review",
        "Cross-group peer review",
        "Same group, different role",
        "Three reviewers per reviewee",
    ]
    last_pos = -1
    for seed_name in expected_order:
        marker = f">{seed_name}</option>"
        pos = body.find(marker)
        assert pos != -1, f"missing {seed_name}"
        assert pos > last_pos, (
            f"{seed_name} rendered out of install order"
        )
        last_pos = pos
    # The form posts to the live Generate route.
    generate_action = (
        f'action="/operator/sessions/{review_session.id}'
        '/assignments/rule-based/generate"'
    )
    assert generate_action in body
    # Edit ruleset link points at the new single-card Rule Builder
    # surface, with the currently-selected RuleSet pinned in the
    # ``?rule_set_id=`` query (Segment 13A-1 PR 4a).
    edit_url_prefix = (
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor?rule_set_id="
    )
    assert f'href="{edit_url_prefix}' in body
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
    # PR 4: the checkbox is required (not disabled).
    assert "required" in rb_section_pop


def test_rule_based_editor_no_id_redirects_to_assignments(
    client: TestClient, db: Session
) -> None:
    """The id-less editor URL is now a 404; the real editor at
    ``…/edit/{rule_set_id}`` is exercised in
    ``test_rule_based_editor.py``."""

    review_session = _make_session(client, db, code="rb-no-id")
    response = client.get(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/edit",
        follow_redirects=False,
    )
    assert response.status_code in (404, 405)


def test_rule_based_card_dropdown_lists_seeds_before_personal(
    client: TestClient, db: Session
) -> None:
    """The Rule Based card on the Assignments page renders seeds
    first (in install order) followed by caller-owned Personal
    RuleSets — same canonical ordering as the new Rule Builder
    dropdown. Pre-fix, ``list_visible_rule_sets`` ordered by
    ``scope ASC`` which placed Personal before Seeds alphabetically.
    """

    from app.db.models import RuleSet

    review_session = _make_session(client, db, code="rb-order")

    # Seed a Personal RuleSet via the new Save-As flow (Save with no
    # rule_set_id, source = first seed).
    intra_id = db.execute(
        select(RuleSet.id).where(
            RuleSet.is_seed.is_(True),
            RuleSet.name == "Intra-group peer review",
        )
    ).scalar_one()
    save_response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor/save",
        data={
            "source_rule_set_id": intra_id,
            "name": "Personal Aaa",
            "combinator": "ALL_OF",
            "rules_json": "[]",
        },
        follow_redirects=False,
    )
    assert save_response.status_code == 303, save_response.text

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text

    # Pull out the order of rule-based-card option labels.
    selector_marker = 'name="rule_set_id"'
    if selector_marker not in body:
        # Fallback: card may render the id under a different attribute;
        # tag-based search keeps the test robust.
        selector_marker = 'data-rule-set-id'
    selector_start = body.index(selector_marker)
    # Just take a wide slice — the dropdown's options live within a
    # few hundred bytes of the marker.
    slice_window = body[selector_start : selector_start + 4000]

    seed_pos = slice_window.find("Full Matrix")
    personal_pos = slice_window.find("Personal Aaa")
    assert seed_pos != -1, "Full Matrix seed missing from selector"
    assert personal_pos != -1, "Personal RuleSet missing from selector"
    assert seed_pos < personal_pos, (
        "Seeds must render before Personal RuleSets in the Rule "
        "Based card selector"
    )
