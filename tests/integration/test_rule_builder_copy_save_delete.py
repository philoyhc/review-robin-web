"""Integration tests for Segment 13A-1 PR 2 — Copy / Save / Cancel /
Delete on the new single-card Rule Builder page.

PR 2 makes the Rule Builder usable end-to-end for any seeded or
Personal RuleSet that already exists:

- Personal RuleSets render the PR 5b/5c indented inline-composite
  editable form (lifted unchanged into the new card).
- ``POST /assignments/rule-based-editor/copy`` 303s to
  ``?draft_from=<source_id>`` — the draft renders editable from
  source rules but isn't persisted until Save (locked decision #3).
- ``POST .../save`` saves in place when ``rule_set_id`` is set;
  Save-As semantics when it isn't (Copy-then-Save flow).
- ``POST .../delete`` soft-deletes and 303s to the bare URL so the
  GET handler falls through to the first-seed default.

The "+ New blank RuleSet" sentinel ships in PR 3 — not exercised
here.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RuleSet, RuleSetRevision, ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "RBPR2", "code": code, "description": "d"},
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


# ---------------------------------------------------------------------------
# POST /copy — draft-from-source (no persistence)
# ---------------------------------------------------------------------------


def test_copy_from_seed_303s_to_draft_with_source_id(
    client: TestClient, db: Session
) -> None:
    """POST /copy returns 303 to ``?draft_from=<source>`` and does not
    persist a Personal RuleSet (locked decision: draft not persisted
    until Save)."""

    review_session = _make_session(client, db, code="rb-copy-1")
    intra_id = _seed_id(db, "Intra-group peer review")

    pre_count = db.execute(
        select(RuleSet).where(RuleSet.is_seed.is_(False))
    ).scalars().all()

    response = client.post(
        _builder_url(review_session.id, "copy"),
        data={"from_rule_set_id": intra_id},
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert (
        f"draft_from={intra_id}"
        in (response.headers.get("location") or "")
    )

    post_count = db.execute(
        select(RuleSet).where(RuleSet.is_seed.is_(False))
    ).scalars().all()
    assert len(post_count) == len(pre_count), (
        "Copy must not persist a Personal RuleSet — Save creates it."
    )


def test_draft_from_renders_editable_form_with_auto_name(
    client: TestClient, db: Session
) -> None:
    """``GET ?draft_from=<seed_id>`` renders the editable form
    pre-populated with the source's rules + auto-generated name."""

    review_session = _make_session(client, db, code="rb-copy-2")
    intra_id = _seed_id(db, "Intra-group peer review")

    body = client.get(
        _builder_url(review_session.id) + f"?draft_from={intra_id}"
    ).text

    # Editable form is rendered.
    assert 'id="rule-based-editor-form"' in body
    assert 'id="rule-based-editor-rules-json"' in body
    # Draft banner — distinct from seeded banner.
    assert 'id="rule-builder-draft-banner"' in body
    assert 'id="rule-builder-seed-banner"' not in body
    # Auto-generated name "Copy of <source>" pre-populates the
    # editable name input.
    assert 'name="name"' in body
    assert 'value="Copy of Intra-group peer review"' in body
    # Save + Cancel are exposed; Delete is not (nothing to delete).
    assert 'id="rule-builder-save-button"' in body
    assert 'id="rule-builder-cancel-button"' in body
    assert 'id="rule-builder-delete-button"' not in body


# ---------------------------------------------------------------------------
# POST /save — Save-As (draft) and in-place
# ---------------------------------------------------------------------------


def test_save_from_draft_creates_personal_rule_set(
    client: TestClient, db: Session
) -> None:
    """Save with no ``rule_set_id`` + a ``source_rule_set_id`` creates
    a new Personal RuleSet (Save-As semantics)."""

    review_session = _make_session(client, db, code="rb-save-1")
    intra_id = _seed_id(db, "Intra-group peer review")

    response = client.post(
        _builder_url(review_session.id, "save"),
        data={
            "source_rule_set_id": intra_id,
            "name": "Copy of Intra-group peer review",
            "combinator": "ALL_OF",
            "rules_json": json.dumps([]),
            "auto_name": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    location = response.headers.get("location") or ""
    assert "rule_set_id=" in location and "saved=1" in location

    saved = db.execute(
        select(RuleSet).where(
            RuleSet.name == "Copy of Intra-group peer review",
            RuleSet.is_seed.is_(False),
        )
    ).scalar_one()
    assert saved.deleted_at is None


def test_save_in_place_appends_revision(
    client: TestClient, db: Session
) -> None:
    """Save with a ``rule_set_id`` mutates the existing Personal
    RuleSet by appending a new revision (PR 6 semantics).

    Uses the legacy /rule-based/copy route to seed a saved Personal
    so the assertion exercises only the new /save handler."""

    review_session = _make_session(client, db, code="rb-save-2")
    intra_id = _seed_id(db, "Intra-group peer review")
    client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/copy",
        data={"rule_set_id": intra_id, "new_name": "Saveable"},
        follow_redirects=False,
    )
    personal = db.execute(
        select(RuleSet).where(RuleSet.name == "Saveable")
    ).scalar_one()
    initial_revision_no = personal.current_revision.revision_no

    response = client.post(
        _builder_url(review_session.id, "save"),
        data={
            "rule_set_id": personal.id,
            "name": "Saveable",
            "combinator": "ALL_OF",
            "rules_json": json.dumps([]),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    db.refresh(personal)
    assert personal.current_revision.revision_no == initial_revision_no + 1
    revisions = db.execute(
        select(RuleSetRevision).where(
            RuleSetRevision.rule_set_id == personal.id
        )
    ).scalars().all()
    assert len(revisions) >= 2


def test_save_in_place_inline_rename(
    client: TestClient, db: Session
) -> None:
    """Editing the name field on a saved Personal RuleSet and
    submitting Save commits the rename alongside the revision."""

    review_session = _make_session(client, db, code="rb-rename")
    intra_id = _seed_id(db, "Intra-group peer review")
    client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/copy",
        data={"rule_set_id": intra_id, "new_name": "Old name"},
        follow_redirects=False,
    )
    personal = db.execute(
        select(RuleSet).where(RuleSet.name == "Old name")
    ).scalar_one()

    client.post(
        _builder_url(review_session.id, "save"),
        data={
            "rule_set_id": personal.id,
            "name": "New name",
            "combinator": "ALL_OF",
            "rules_json": json.dumps([]),
        },
        follow_redirects=False,
    )

    db.refresh(personal)
    assert personal.name == "New name"


def test_save_with_empty_name_redirects_with_error(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-noname")
    intra_id = _seed_id(db, "Intra-group peer review")

    response = client.post(
        _builder_url(review_session.id, "save"),
        data={
            "source_rule_set_id": intra_id,
            "name": "   ",
            "combinator": "ALL_OF",
            "rules_json": json.dumps([]),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=empty_name" in (response.headers.get("location") or "")


# ---------------------------------------------------------------------------
# Auto-suffix on Copy collision
# ---------------------------------------------------------------------------


def test_copy_collision_auto_suffixes_when_default_name(
    client: TestClient, db: Session
) -> None:
    """First Copy + Save creates ``Copy of <source>``; a second Copy
    + Save with the literal default name auto-suffixes to ``(2)``
    (locked decision #5)."""

    review_session = _make_session(client, db, code="rb-suffix")
    intra_id = _seed_id(db, "Intra-group peer review")

    # First Save: ``Copy of Intra-group peer review`` succeeds.
    client.post(
        _builder_url(review_session.id, "save"),
        data={
            "source_rule_set_id": intra_id,
            "name": "Copy of Intra-group peer review",
            "combinator": "ALL_OF",
            "rules_json": json.dumps([]),
            "auto_name": "true",
        },
        follow_redirects=False,
    )

    # Second Save with the same default name + ``auto_name=true``
    # should auto-suffix.
    response = client.post(
        _builder_url(review_session.id, "save"),
        data={
            "source_rule_set_id": intra_id,
            "name": "Copy of Intra-group peer review",
            "combinator": "ALL_OF",
            "rules_json": json.dumps([]),
            "auto_name": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "saved=1" in (response.headers.get("location") or "")

    suffixed = db.execute(
        select(RuleSet).where(
            RuleSet.name == "Copy of Intra-group peer review (2)",
            RuleSet.is_seed.is_(False),
        )
    ).scalar_one_or_none()
    assert suffixed is not None


def test_save_collision_on_edited_name_returns_error(
    client: TestClient, db: Session
) -> None:
    """Operator-edited names that collide get an explicit error
    instead of a silent auto-suffix."""

    review_session = _make_session(client, db, code="rb-collide")
    intra_id = _seed_id(db, "Intra-group peer review")
    client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/copy",
        data={"rule_set_id": intra_id, "new_name": "Already taken"},
        follow_redirects=False,
    )

    response = client.post(
        _builder_url(review_session.id, "save"),
        data={
            "source_rule_set_id": intra_id,
            "name": "Already taken",
            "combinator": "ALL_OF",
            "rules_json": json.dumps([]),
            # auto_name=false → no suffix on collision
            "auto_name": "false",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=name_collision" in (
        response.headers.get("location") or ""
    )


# ---------------------------------------------------------------------------
# POST /delete
# ---------------------------------------------------------------------------


def test_delete_soft_deletes_and_redirects_to_first_seed(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-delete")
    intra_id = _seed_id(db, "Intra-group peer review")
    client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/copy",
        data={"rule_set_id": intra_id, "new_name": "ToDelete"},
        follow_redirects=False,
    )
    personal = db.execute(
        select(RuleSet).where(RuleSet.name == "ToDelete")
    ).scalar_one()

    response = client.post(
        _builder_url(review_session.id, "delete"),
        data={"rule_set_id": personal.id, "confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    # 303 lands on the bare page URL — no rule_set_id query —
    # so the GET handler falls through to the first-seed default.
    assert response.headers.get("location") == _builder_url(
        review_session.id
    )

    db.refresh(personal)
    assert personal.deleted_at is not None


def test_delete_without_confirm_redirects_with_error(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-del-noconf")
    intra_id = _seed_id(db, "Intra-group peer review")
    client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/copy",
        data={"rule_set_id": intra_id, "new_name": "PR2 keep"},
        follow_redirects=False,
    )
    personal = db.execute(
        select(RuleSet).where(RuleSet.name == "PR2 keep")
    ).scalar_one()

    response = client.post(
        _builder_url(review_session.id, "delete"),
        data={"rule_set_id": personal.id},  # no confirm flag
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=needs_delete_confirm" in (
        response.headers.get("location") or ""
    )

    db.refresh(personal)
    assert personal.deleted_at is None


def test_delete_seed_returns_400(client: TestClient, db: Session) -> None:
    """Seeded RuleSets can't be deleted — they're workspace-wide
    read-only."""

    review_session = _make_session(client, db, code="rb-del-seed")
    full_matrix_id = _seed_id(db, "Full Matrix")

    response = client.post(
        _builder_url(review_session.id, "delete"),
        data={"rule_set_id": full_matrix_id, "confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Cancel — purely client-side; assert GET-after-cancel renders saved state
# ---------------------------------------------------------------------------


def test_get_after_cancel_renders_saved_state(
    client: TestClient, db: Session
) -> None:
    """Cancel is a `<a>` back to the same selection — there's no
    server handler. Assert that GETting the saved-Personal URL
    after a hypothetical Cancel renders the saved state with the
    name unchanged from its persisted value."""

    review_session = _make_session(client, db, code="rb-cancel")
    intra_id = _seed_id(db, "Intra-group peer review")
    client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/copy",
        data={"rule_set_id": intra_id, "new_name": "Cancel me"},
        follow_redirects=False,
    )
    personal = db.execute(
        select(RuleSet).where(RuleSet.name == "Cancel me")
    ).scalar_one()

    body = client.get(
        _builder_url(review_session.id) + f"?rule_set_id={personal.id}"
    ).text

    # Saved name reappears in the editable form.
    assert 'value="Cancel me"' in body


# ---------------------------------------------------------------------------
# Visibility / auth gates on the new POST routes
# ---------------------------------------------------------------------------


def test_copy_other_users_personal_returns_403(
    db: Session,
    alice,  # noqa: ANN001 — fixture
    bob,  # noqa: ANN001 — fixture
    make_client,  # noqa: ANN001 — fixture
) -> None:
    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="rb-priv-copy")
    intra_id = _seed_id(db, "Intra-group peer review")

    alice_client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/copy",
        data={"rule_set_id": intra_id, "new_name": "Alice private 2"},
        follow_redirects=False,
    )
    alice_rs = db.execute(
        select(RuleSet).where(RuleSet.name == "Alice private 2")
    ).scalar_one()

    bob_client = make_client(bob)
    response = bob_client.post(
        _builder_url(review_session.id, "copy"),
        data={"from_rule_set_id": alice_rs.id},
        follow_redirects=False,
    )
    # Bob isn't an operator on Alice's session — the session-permission
    # gate fires before the ownership check.
    assert response.status_code == 403
