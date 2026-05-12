"""UI render tests for the Rule Builder's Add-from-library mini-
card (PR 3 of the post-15C parity polish).

The Add-from-library service + route shipped in 15C Slice 4a but
never grew a UI on the Rule Builder page. This PR adds the
mini-card on the right column above the Available rulesets card,
mirroring the RTD's same-named card on the Instruments page.

Pinned:

1. Empty library pool → card is hidden.
2. Library entry not in session → card surfaces it in the picker.
3. Library entry already in session (auto-copy / earlier Save-As)
   → card hides that entry (or hides itself entirely if no entries
   remain).
4. POST routes through to ``/add-from-library`` and copies the
   library row into ``session_rule_sets``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    ReviewSession,
    RuleSet,
    RuleSetRevision,
    SessionRuleSet,
    User,
)


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "RBAFL", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _builder_url(session_id: int) -> str:
    return (
        f"/operator/sessions/{session_id}"
        "/assignments/rule-based-editor"
    )


def _make_library_rule_set(
    db: Session, *, owner: User, name: str
) -> RuleSet:
    rs = RuleSet(
        name=name,
        description=f"library {name}",
        scope="personal",
        owner_user_id=owner.id,
        is_seed=False,
    )
    db.add(rs)
    db.flush()
    revision = RuleSetRevision(
        rule_set_id=rs.id,
        revision_no=1,
        combinator="ALL_OF",
        exclude_self_reviews=True,
        seed=None,
        rules_json=[],
        created_at=datetime.now(timezone.utc),
        created_by_user_id=owner.id,
    )
    db.add(revision)
    db.flush()
    rs.current_revision_id = revision.id
    db.flush()
    return rs


def _current_user(client: TestClient, db: Session) -> User:
    client.get("/operator/settings")
    return db.execute(
        select(User).order_by(User.id.desc()).limit(1)
    ).scalar_one()


# --- card visibility --------------------------------------------------------


def test_empty_library_hides_add_from_library_card(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="afl-empty")
    body = client.get(_builder_url(review_session.id)).text
    assert 'id="add-rule-set-from-library-card"' not in body
    # Available rulesets card still renders — it lists session rows
    # regardless of library state.
    assert 'id="available-rulesets-card"' in body


def test_library_entry_surfaces_in_picker(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="afl-vis")
    user = review_session.created_by_user
    _make_library_rule_set(db, owner=user, name="MyLibRule")
    db.commit()

    body = client.get(_builder_url(review_session.id)).text
    assert 'id="add-rule-set-from-library-card"' in body
    assert "MyLibRule" in body
    # The Add button posts to the Slice 4a route.
    assert "/assignments/rule-based-editor/add-from-library" in body


def test_already_in_session_filters_out(
    client: TestClient, db: Session
) -> None:
    """When the operator's library entry has been added to the
    session already, the picker drops that row. If no library
    entries remain to pull in, the card hides entirely."""
    review_session = _make_session(client, db, code="afl-filter")
    user = review_session.created_by_user
    library_row = _make_library_rule_set(
        db, owner=user, name="AlreadyHere"
    )
    db.add(
        SessionRuleSet(
            session_id=review_session.id,
            name="AlreadyHere",
            description="local copy",
            combinator="ALL_OF",
            exclude_self_reviews=True,
            seed=None,
            rules_json=[],
            library_origin_id=library_row.id,
        )
    )
    db.commit()

    body = client.get(_builder_url(review_session.id)).text
    # The library pool minus the in-session row is empty, so the
    # card hides entirely.
    assert 'id="add-rule-set-from-library-card"' not in body


def test_partial_library_pool_renders_remaining(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="afl-partial")
    user = review_session.created_by_user
    in_session_row = _make_library_rule_set(
        db, owner=user, name="HasSessionCopy"
    )
    _make_library_rule_set(db, owner=user, name="StillFree")
    db.add(
        SessionRuleSet(
            session_id=review_session.id,
            name="HasSessionCopy",
            description="local",
            combinator="ALL_OF",
            exclude_self_reviews=True,
            seed=None,
            rules_json=[],
            library_origin_id=in_session_row.id,
        )
    )
    db.commit()

    body = client.get(_builder_url(review_session.id)).text
    assert 'id="add-rule-set-from-library-card"' in body
    assert "StillFree" in body
    # The in-session library entry is filtered out of the picker
    # — its name shouldn't surface inside the picker's <select>.
    picker_start = body.index('id="library-rule-set-picker"')
    picker_end = body.index("</select>", picker_start)
    picker_block = body[picker_start:picker_end]
    assert "HasSessionCopy" not in picker_block


def test_add_from_library_post_succeeds(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="afl-post")
    user = review_session.created_by_user
    library_row = _make_library_rule_set(db, owner=user, name="ToPull")
    db.commit()

    response = client.post(
        f"{_builder_url(review_session.id)}/add-from-library",
        data={"library_rule_set_id": library_row.id},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    surviving = db.execute(
        select(SessionRuleSet)
        .where(SessionRuleSet.session_id == review_session.id)
        .where(SessionRuleSet.name == "ToPull")
    ).scalar_one()
    assert surviving.library_origin_id == library_row.id
    assert surviving.is_seeded is False
