"""Render tests for the unified pill convention across the
Rule Builder's Available rulesets card and the Instruments
page's RTD card.

Pill conventions (consistent across both surfaces):

- **Seeded** rows: no pill (workspace-shipped; identity is the
  name + description).
- **In library** (``library_origin_id`` non-NULL, non-seeded):
  green ``pill-success`` "in library".
- **Personal** (operator-authored, session-only;
  ``library_origin_id`` NULL, non-seeded): blue ``pill-info``
  "personal".
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    OperatorResponseTypeDefinition,
    ResponseTypeDefinition,
    ReviewSession,
    RuleSet,
    RuleSetRevision,
    SessionRuleSet,
)
from app.services.instruments import add_response_type_definition


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "PILLS", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _rule_builder_url(session_id: int) -> str:
    return (
        f"/operator/sessions/{session_id}"
        "/assignments/rule-based-editor"
    )


def _instruments_url(session_id: int) -> str:
    return f"/operator/sessions/{session_id}/instruments"


def _available_block(body: str) -> str:
    """Slice out the Available rulesets card body so pill counts
    are local to it (not the editor card on the left). The card
    is one self-contained <div> — a generous fixed slice is plenty
    given the test fixtures are small."""
    start = body.index('id="available-rulesets-card"')
    return body[start : start + 6000]


def _rtd_table_block(body: str) -> str:
    """Slice from the RTD table tbody so pill assertions only see
    the RTD rows (not, e.g., the Add cards below or pills inside
    instrument cards above)."""
    start = body.index("data-rtd-tbody")
    end = body.index("</tbody>", start)
    return body[start:end]


# --- RuleSet: Available rulesets card --------------------------------------


def test_available_rulesets_seeded_renders_no_pill(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pills-seed")
    body = client.get(_rule_builder_url(review_session.id)).text
    avail = _available_block(body)
    # Full Matrix is a seeded row on the freshly-created session.
    assert "Full Matrix" in avail
    # Neither pill renders on a seeded row.
    assert "in library" not in avail
    assert ">personal<" not in avail


def test_available_rulesets_personal_renders_blue_pill(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pills-personal")
    # Save-As a brand new SessionRuleSet (library_origin_id NULL).
    intra_id = db.execute(
        select(SessionRuleSet.id).where(
            SessionRuleSet.session_id == review_session.id,
            SessionRuleSet.name == "Intra-group peer review",
        )
    ).scalar_one()
    client.post(
        f"{_rule_builder_url(review_session.id)}/save",
        data={
            "source_rule_set_id": intra_id,
            "name": "MyAuthored",
            "combinator": "ALL_OF",
            "rules_json": "[]",
        },
        follow_redirects=False,
    )

    body = client.get(_rule_builder_url(review_session.id)).text
    avail = _available_block(body)
    assert "MyAuthored" in avail
    # Personal pill present, in-library pill absent for this row.
    # The substring "personal" appears as the pill label; we check
    # the class for stronger localisation.
    assert "pill-info" in avail
    assert ">personal<" in avail


def test_available_rulesets_in_library_renders_green_pill(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pills-inlib")
    user = review_session.created_by_user
    # Plant a session row that points at a library entry.
    library_row = RuleSet(
        name="LinkedRule",
        description="",
        scope="personal",
        owner_user_id=user.id,
        is_seed=False,
    )
    db.add(library_row)
    db.flush()
    rev = RuleSetRevision(
        rule_set_id=library_row.id,
        revision_no=1,
        combinator="ALL_OF",
        exclude_self_reviews=True,
        seed=None,
        rules_json=[],
        created_at=datetime.now(timezone.utc),
        created_by_user_id=user.id,
    )
    db.add(rev)
    db.flush()
    library_row.current_revision_id = rev.id
    db.add(
        SessionRuleSet(
            session_id=review_session.id,
            name="LinkedRule",
            description="",
            combinator="ALL_OF",
            exclude_self_reviews=True,
            seed=None,
            rules_json=[],
            library_origin_id=library_row.id,
        )
    )
    db.commit()

    body = client.get(_rule_builder_url(review_session.id)).text
    avail = _available_block(body)
    assert "LinkedRule" in avail
    assert "pill-success" in avail
    assert "in library" in avail


# --- RTD: Instruments page RTD card ----------------------------------------


def test_rtd_seeded_renders_no_pill(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pills-rtd-seed")
    body = client.get(_instruments_url(review_session.id)).text
    rtd_block = _rtd_table_block(body)
    # Long_text is one of the ten seeded RTDs.
    assert "Long_text" in rtd_block
    # Pills are scoped per-row inside the RTD body; seeded rows
    # don't emit either pill class.
    # (The page-level body may contain pill-success / pill-info for
    # other surfaces; that's why we slice the table.)
    assert ">in library<" not in rtd_block
    assert ">personal<" not in rtd_block


def test_rtd_personal_renders_blue_pill(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pills-rtd-pers")
    user = review_session.created_by_user
    add_response_type_definition(
        db,
        review_session=review_session,
        response_type="MyAuthoredType",
        data_type="Integer",
        min=0,
        max=10,
        step=1,
        list_csv=None,
        actor=user,
    )
    db.commit()

    body = client.get(_instruments_url(review_session.id)).text
    rtd_block = _rtd_table_block(body)
    assert "MyAuthoredType" in rtd_block
    # personal pill present; in-library absent.
    assert ">personal<" in rtd_block
    assert ">in library<" not in rtd_block


def test_rtd_in_library_renders_green_pill(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pills-rtd-lib")
    user = review_session.created_by_user
    library_rtd = OperatorResponseTypeDefinition(
        owner_user_id=user.id,
        response_type="LinkedType",
        data_type="Integer",
        min=0,
        max=10,
        step=1,
        list_csv=None,
    )
    db.add(library_rtd)
    db.flush()
    db.add(
        ResponseTypeDefinition(
            session_id=review_session.id,
            response_type="LinkedType",
            data_type="Integer",
            min=0,
            max=10,
            step=1,
            list_csv=None,
            is_seeded=False,
            seed_order=0,
            library_origin_id=library_rtd.id,
        )
    )
    db.commit()

    body = client.get(_instruments_url(review_session.id)).text
    rtd_block = _rtd_table_block(body)
    assert "LinkedType" in rtd_block
    assert ">in library<" in rtd_block
    # Personal pill absent for an in-library row.
    # (Other RTD rows in the same block — operator-authored types
    # if any — could trigger the substring; this test plants only
    # a library-linked row, so >personal< should not appear.)
    assert ">personal<" not in rtd_block


# --- Rule Builder card no longer carries the in-library pill ----------------


def test_rule_builder_card_does_not_render_in_library_pill(
    client: TestClient, db: Session
) -> None:
    """The in-library pill moved to the Available rulesets card.
    The Rule Builder card (left column) should not render it
    next to the Name input."""
    review_session = _make_session(client, db, code="pills-editor")
    user = review_session.created_by_user
    library_row = RuleSet(
        name="EditorPillTest",
        description="",
        scope="personal",
        owner_user_id=user.id,
        is_seed=False,
    )
    db.add(library_row)
    db.flush()
    rev = RuleSetRevision(
        rule_set_id=library_row.id,
        revision_no=1,
        combinator="ALL_OF",
        exclude_self_reviews=True,
        seed=None,
        rules_json=[],
        created_at=datetime.now(timezone.utc),
        created_by_user_id=user.id,
    )
    db.add(rev)
    db.flush()
    library_row.current_revision_id = rev.id
    db.flush()
    new_session_row = SessionRuleSet(
        session_id=review_session.id,
        name="EditorPillTest",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=True,
        seed=None,
        rules_json=[],
        library_origin_id=library_row.id,
    )
    db.add(new_session_row)
    db.commit()

    body = client.get(
        f"{_rule_builder_url(review_session.id)}?rule_set_id={new_session_row.id}"
    ).text
    # The pill renders in the Available rulesets block (right
    # column), not within the Rule Builder editor block (left).
    # The editor block doesn't have a unique container id, so
    # check the Name input's wrapping <label> doesn't include the
    # pill.
    name_idx = body.index('id="rule-builder-name-input"')
    name_window = body[max(0, name_idx - 300) : name_idx + 200]
    assert "in library" not in name_window
