"""Integration tests for Segment 12C-1 PR 2 — visible
``exclude_self_reviews`` checkbox in the Rule Builder card.

The flag has always lived on ``RuleSetRevision.exclude_self_reviews``
and travelled through the save flow as a form value; PR 2 promotes
it to a first-class control between the rule-list editor and the
Save / Cancel action row.

Coverage:

- Checkbox renders in the editor form when a Personal RuleSet is
  loaded; ``checked`` mirrors the saved revision's value.
- POST /save with ``exclude_self_reviews=true`` persists the flag
  on the new revision; without the form field it persists as
  ``False`` (HTML form semantics — unchecked checkboxes don't
  submit a value).
- Round-trip: save with the flag, GET the page back, the checkbox
  renders pre-checked.
- Regression guard: the previous "intentionally not exposed"
  comment is gone from the template (search-for-string sentinel).
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, RuleSet, RuleSetRevision

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = (
    REPO_ROOT
    / "app/web/templates/operator/partials/_rule_builder_card.html"
)


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "RBESR", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_id(db: Session, name: str) -> int:
    return db.execute(
        select(RuleSet.id).where(
            RuleSet.is_seed.is_(True), RuleSet.name == name
        )
    ).scalar_one()


def _builder_url(session_id: int, *parts: str) -> str:
    base = (
        f"/operator/sessions/{session_id}"
        "/assignments/rule-based-editor"
    )
    return base if not parts else base + "/" + "/".join(parts)


def _make_personal(
    client: TestClient,
    session_id: int,
    *,
    source_id: int,
    name: str,
    exclude_self_reviews: bool = True,
) -> RuleSet:
    """Save-As a Personal RuleSet with the given exclude flag."""

    data: dict[str, str] = {
        "source_rule_set_id": str(source_id),
        "name": name,
        "combinator": "ALL_OF",
        "rules_json": "[]",
    }
    if exclude_self_reviews:
        data["exclude_self_reviews"] = "true"
    response = client.post(
        _builder_url(session_id, "save"),
        data=data,
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return None  # caller looks the row up by name


def test_checkbox_renders_in_editor_form(
    client: TestClient, db: Session
) -> None:
    """Loading a Personal RuleSet renders the visible checkbox."""

    review_session = _make_session(client, db, code="rb-esr-render")
    intra_id = _seed_id(db, "Intra-group peer review")
    _make_personal(
        client,
        review_session.id,
        source_id=intra_id,
        name="Render-test",
        exclude_self_reviews=True,
    )
    saved = db.execute(
        select(RuleSet).where(RuleSet.name == "Render-test")
    ).scalar_one()

    response = client.get(
        _builder_url(review_session.id) + f"?rule_set_id={saved.id}"
    )
    assert response.status_code == 200
    html = response.text
    assert 'id="rule-based-editor-exclude-self"' in html
    assert 'name="exclude_self_reviews"' in html
    assert "Exclude self-review pairs" in html


def test_checkbox_checked_when_saved_value_true(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-esr-checked")
    intra_id = _seed_id(db, "Intra-group peer review")
    _make_personal(
        client,
        review_session.id,
        source_id=intra_id,
        name="Checked-true",
        exclude_self_reviews=True,
    )
    saved = db.execute(
        select(RuleSet).where(RuleSet.name == "Checked-true")
    ).scalar_one()

    response = client.get(
        _builder_url(review_session.id) + f"?rule_set_id={saved.id}"
    )
    html = response.text
    # The checkbox input lines up across multiple lines in the
    # template; test the rendered attribute presence rather than
    # the exact substring.
    assert 'id="rule-based-editor-exclude-self"' in html
    # ``checked`` follows the input id within ~200 chars in the rendered
    # HTML. The template emits ``checked`` (no value) when the flag is
    # ``True``.
    after_id = html.split('id="rule-based-editor-exclude-self"', 1)[1][:300]
    assert "checked" in after_id


def test_checkbox_unchecked_when_saved_value_false(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-esr-unchecked")
    intra_id = _seed_id(db, "Intra-group peer review")
    _make_personal(
        client,
        review_session.id,
        source_id=intra_id,
        name="Checked-false",
        exclude_self_reviews=False,
    )
    saved = db.execute(
        select(RuleSet).where(RuleSet.name == "Checked-false")
    ).scalar_one()

    response = client.get(
        _builder_url(review_session.id) + f"?rule_set_id={saved.id}"
    )
    html = response.text
    assert 'id="rule-based-editor-exclude-self"' in html
    after_id = html.split('id="rule-based-editor-exclude-self"', 1)[1][:300]
    assert "checked" not in after_id


def test_save_with_checkbox_checked_persists_true(
    client: TestClient, db: Session
) -> None:
    """POST /save with ``exclude_self_reviews=true`` writes the flag
    on the new revision."""

    review_session = _make_session(client, db, code="rb-esr-save-true")
    intra_id = _seed_id(db, "Intra-group peer review")

    response = client.post(
        _builder_url(review_session.id, "save"),
        data={
            "source_rule_set_id": str(intra_id),
            "name": "Save-true",
            "combinator": "ALL_OF",
            "rules_json": json.dumps([]),
            "exclude_self_reviews": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    saved = db.execute(
        select(RuleSet).where(RuleSet.name == "Save-true")
    ).scalar_one()
    revision = saved.current_revision
    assert revision.exclude_self_reviews is True


def test_save_without_checkbox_persists_false(
    client: TestClient, db: Session
) -> None:
    """Omitting the form field (unchecked checkbox) saves ``False``."""

    review_session = _make_session(client, db, code="rb-esr-save-false")
    intra_id = _seed_id(db, "Intra-group peer review")

    response = client.post(
        _builder_url(review_session.id, "save"),
        data={
            "source_rule_set_id": str(intra_id),
            "name": "Save-false",
            "combinator": "ALL_OF",
            "rules_json": json.dumps([]),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    saved = db.execute(
        select(RuleSet).where(RuleSet.name == "Save-false")
    ).scalar_one()
    revision = saved.current_revision
    assert revision.exclude_self_reviews is False


def test_round_trip_save_then_get(
    client: TestClient, db: Session
) -> None:
    """Save with the flag, reload the page, the checkbox is pre-checked."""

    review_session = _make_session(client, db, code="rb-esr-roundtrip")
    intra_id = _seed_id(db, "Intra-group peer review")

    client.post(
        _builder_url(review_session.id, "save"),
        data={
            "source_rule_set_id": str(intra_id),
            "name": "Roundtrip",
            "combinator": "ALL_OF",
            "rules_json": json.dumps([]),
            "exclude_self_reviews": "true",
        },
        follow_redirects=False,
    )
    saved = db.execute(
        select(RuleSet).where(RuleSet.name == "Roundtrip")
    ).scalar_one()

    response = client.get(
        _builder_url(review_session.id) + f"?rule_set_id={saved.id}"
    )
    html = response.text
    after_id = html.split('id="rule-based-editor-exclude-self"', 1)[1][:300]
    assert "checked" in after_id

    # And the underlying revision actually carries the flag.
    db.refresh(saved)
    revision = db.execute(
        select(RuleSetRevision).where(
            RuleSetRevision.id == saved.current_revision_id
        )
    ).scalar_one()
    assert revision.exclude_self_reviews is True


def test_intentionally_not_exposed_comment_removed() -> None:
    """Regression guard — the comment that gated this UI is gone."""

    text = TEMPLATE.read_text()
    assert "intentionally not exposed" not in text
