"""Findings R1 (author's ruling 2026-10-17): a Save that **changes** a
submitted answer clears that answer's ``submitted_at``, so the edit is
not released as submitted until the reviewer submits again. A Save that
re-posts the same value leaves the stamp alone. On a group-scoped
instrument the change clears the stamp on every member's copy.

Blanking a submitted answer is a change too: its row (and stamp) is
deleted, so the assignment's remaining rows lose theirs instead, on
every member's copy for a group (Codex on the rulings PR).
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser

from app.db.models import (
    Assignment,
    AuditEvent,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionOperator,
    User,
)
from app.schemas.responses import ResponseUpsert
from app.services import monitoring
from app.services import responses as responses_service
from app.services import instruments as instruments_service
from app.services.instruments import ensure_default_instrument


def _seed(
    db: Session, *, group: bool = False
) -> tuple[User, Reviewer, ReviewSession, list[Assignment]]:
    op = User(email="op@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(
        name="Spring", code="spring-r1", created_by_user_id=op.id
    )
    db.add(review_session)
    db.flush()
    db.add(
        SessionOperator(session_id=review_session.id, user_id=op.id, role="owner")
    )
    if group:
        instrument = instruments_service.create_instrument(
            db,
            review_session=review_session,
            actor=op,
            group_kind=instruments_service.GROUP_KIND_SENTINEL,
        )
    else:
        instrument = ensure_default_instrument(db, review_session)
    reviewer = Reviewer(
        session_id=review_session.id, name="Rae", email="rae@example.edu"
    )
    db.add(reviewer)
    reviewees = [
        Reviewee(
            session_id=review_session.id,
            name=name,
            email_or_identifier=f"{name.lower()}@example.edu",
        )
        for name in (["Carol", "Dan"] if group else ["Carol"])
    ]
    db.add_all(reviewees)
    db.flush()
    assignments = [
        Assignment(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
        )
        for reviewee in reviewees
    ]
    db.add_all(assignments)
    # ``ready``: the reviewer write services re-check it under the
    # session lock (findings L3).
    review_session.status = "ready"
    db.flush()
    return op, reviewer, review_session, assignments


def _save(db, op, reviewer, review_session, assignment, **values) -> None:
    responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[
            ResponseUpsert(assignment_id=assignment.id, field_key=k, value=v)
            for k, v in values.items()
        ],
        correlation_id="save",
    )


def _submit(db, op, reviewer, review_session, assignment, **values) -> None:
    result = responses_service.submit(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[
            ResponseUpsert(assignment_id=assignment.id, field_key=k, value=v)
            for k, v in values.items()
        ],
        correlation_id="submit",
    )
    assert result.submitted


def _stamps(db: Session, assignment: Assignment) -> dict[str, bool]:
    rows = db.execute(
        select(Response).where(Response.assignment_id == assignment.id)
    ).scalars()
    return {r.response_field.field_key: r.submitted_at is not None for r in rows}


def _pill(db: Session, reviewer: Reviewer, review_session: ReviewSession) -> str:
    return responses_service.session_pill_for_reviewer(
        db, reviewer=reviewer, session_id=review_session.id
    ).state


def test_changed_value_after_submit_clears_its_stamp(db: Session) -> None:
    op, reviewer, review_session, [a] = _seed(db)
    _submit(db, op, reviewer, review_session, a, rating="3", comments="ok")
    assert _stamps(db, a) == {"rating": True, "comments": True}
    assert _pill(db, reviewer, review_session) == "submitted"

    _save(db, op, reviewer, review_session, a, rating="5", comments="ok")

    # Only the changed answer loses its stamp; the reviewer must submit
    # again, and the dashboard says so.
    assert _stamps(db, a) == {"rating": False, "comments": True}
    assert _pill(db, reviewer, review_session) == "in progress"
    [progress] = monitoring.per_reviewer_progress(db, review_session)
    assert progress.pill_state == "in progress"
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "responses.saved")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event.detail["counts"]["submissions_cleared"] == 1

    _submit(db, op, reviewer, review_session, a)
    assert _stamps(db, a) == {"rating": True, "comments": True}
    assert _pill(db, reviewer, review_session) == "submitted"


def test_unchanged_value_after_submit_keeps_its_stamp(db: Session) -> None:
    op, reviewer, review_session, [a] = _seed(db)
    _submit(db, op, reviewer, review_session, a, rating="3", comments="ok")

    # The surface posts every input on Save, so an untouched answer comes
    # back with its stored value.
    _save(db, op, reviewer, review_session, a, rating="3", comments="ok")

    assert _stamps(db, a) == {"rating": True, "comments": True}
    assert _pill(db, reviewer, review_session) == "submitted"
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "responses.saved")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert "submissions_cleared" not in event.detail["counts"]


def test_number_in_another_form_is_unchanged(db: Session) -> None:
    """A number is stored canonically (findings R4), so ``3.0`` against a
    stored ``3`` is the same answer and keeps its stamp."""
    op, reviewer, review_session, [a] = _seed(db)
    _submit(db, op, reviewer, review_session, a, rating="3")

    _save(db, op, reviewer, review_session, a, rating="3.0")

    assert _stamps(db, a) == {"rating": True}


def test_blocked_submit_that_changes_a_value_clears_its_stamp(
    db: Session,
) -> None:
    """A Submit refused for a missing required field still writes its
    drafts, so a change it carries is unsubmitted, as a Save's is."""
    op, reviewer, review_session, [a] = _seed(db)
    _submit(db, op, reviewer, review_session, a, rating="3", comments="ok")

    result = responses_service.submit(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[
            ResponseUpsert(assignment_id=a.id, field_key="rating", value=""),
            ResponseUpsert(assignment_id=a.id, field_key="comments", value="new"),
        ],
        correlation_id="blocked",
    )

    assert not result.submitted
    assert _stamps(db, a) == {"comments": False}
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "responses.saved")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event.detail["counts"]["submissions_cleared"] == 1


def test_group_change_after_submit_clears_every_copy(db: Session) -> None:
    op, reviewer, review_session, [first, second] = _seed(db, group=True)
    _submit(db, op, reviewer, review_session, first, rating="3", comments="ok")
    assert _stamps(db, first) == {"rating": True, "comments": True}
    assert _stamps(db, second) == {"rating": True, "comments": True}

    _save(db, op, reviewer, review_session, first, rating="4", comments="ok")

    assert _stamps(db, first) == {"rating": False, "comments": True}
    assert _stamps(db, second) == {"rating": False, "comments": True}
    assert _pill(db, reviewer, review_session) == "in progress"


def test_group_copy_already_holding_the_new_value_is_cleared_too(
    db: Session,
) -> None:
    """Copies that disagree (one already holds the new value) still end
    up agreeing about the stamp: a change to any copy clears them all."""
    op, reviewer, review_session, [first, second] = _seed(db, group=True)
    _submit(db, op, reviewer, review_session, first, rating="3")
    rating_field_id = db.execute(
        select(Response.response_field_id).where(
            Response.assignment_id == second.id
        )
    ).scalar_one()
    copy = db.execute(
        select(Response).where(
            Response.assignment_id == second.id,
            Response.response_field_id == rating_field_id,
        )
    ).scalar_one()
    copy.value = "4"
    db.commit()

    _save(db, op, reviewer, review_session, first, rating="4")

    assert _stamps(db, first) == {"rating": False}
    assert _stamps(db, second) == {"rating": False}


def test_blanking_a_submitted_answer_unsubmits_the_rest(db: Session) -> None:
    op, reviewer, review_session, [a] = _seed(db)
    _submit(db, op, reviewer, review_session, a, rating="3", comments="ok")

    _save(db, op, reviewer, review_session, a, rating="3", comments="")

    # The optional answer is gone, and what remains is no longer
    # released as submitted without it.
    assert _stamps(db, a) == {"rating": False}
    assert _pill(db, reviewer, review_session) == "in progress"
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "responses.saved")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event.detail["counts"]["submissions_cleared"] == 1

    _submit(db, op, reviewer, review_session, a)
    assert _stamps(db, a) == {"rating": True}
    assert _pill(db, reviewer, review_session) == "submitted"


def test_blanking_any_answer_after_submit_unsubmits_the_rest(
    db: Session,
) -> None:
    """A blanked answer the Submit never saw cannot be told from one
    changed and saved before it was blanked, so either withholds the
    rest until the next Submit (the read of the R1 PR)."""
    op, reviewer, review_session, [a] = _seed(db)
    _submit(db, op, reviewer, review_session, a, rating="3")
    _save(db, op, reviewer, review_session, a, rating="3", comments="draft")
    assert _stamps(db, a) == {"rating": True, "comments": False}

    _save(db, op, reviewer, review_session, a, rating="3", comments="")

    assert _stamps(db, a) == {"rating": False}
    assert _pill(db, reviewer, review_session) == "in progress"


def test_change_then_blank_still_needs_a_resubmit(db: Session) -> None:
    """Changing a submitted answer and blanking it in a second Save
    leaves no submission standing (the read of the R1 PR)."""
    op, reviewer, review_session, [a] = _seed(db)
    _submit(db, op, reviewer, review_session, a, rating="3", comments="ok")
    _save(db, op, reviewer, review_session, a, rating="3", comments="okay")
    assert _stamps(db, a) == {"rating": True, "comments": False}

    _save(db, op, reviewer, review_session, a, rating="3", comments="")

    assert _stamps(db, a) == {"rating": False}
    assert _pill(db, reviewer, review_session) == "in progress"


def test_group_blanking_a_submitted_answer_unsubmits_every_copy(
    db: Session,
) -> None:
    op, reviewer, review_session, [first, second] = _seed(db, group=True)
    _submit(db, op, reviewer, review_session, first, rating="3", comments="ok")

    _save(db, op, reviewer, review_session, first, rating="3", comments="")

    assert _stamps(db, first) == {"rating": False}
    assert _stamps(db, second) == {"rating": False}
    assert _pill(db, reviewer, review_session) == "in progress"


def _restamp_stored(db: Session, assignment: Assignment, **stored: str) -> None:
    """Overwrite submitted rows' stored values in place, as an older build
    or the responses import left them."""
    for row in db.execute(
        select(Response).where(Response.assignment_id == assignment.id)
    ).scalars():
        key = row.response_field.field_key
        if key in stored:
            row.value = stored[key]
    db.flush()


def test_re_saving_an_answer_stored_in_an_older_form_keeps_its_stamp(
    db: Session,
) -> None:
    """Findings R2 (2026-10-22): a post arrives CRLF-as-LF and with numbers
    canonical, so an answer stored as CRLF, with outer spaces, or as
    ``04`` read as changed on every Save and lost its stamp. The change
    test now compares the stored value in the form a post of it takes."""
    op, reviewer, review_session, [a] = _seed(db)
    _submit(db, op, reviewer, review_session, a, rating="4", comments="one\ntwo")
    _restamp_stored(db, a, rating="04", comments="  one\r\ntwo ")
    assert _stamps(db, a) == {"rating": True, "comments": True}

    _save(db, op, reviewer, review_session, a, rating="4", comments="one\ntwo")

    assert _stamps(db, a) == {"rating": True, "comments": True}
    assert _pill(db, reviewer, review_session) == "submitted"


def test_a_real_change_to_an_older_form_still_clears_its_stamp(db: Session) -> None:
    op, reviewer, review_session, [a] = _seed(db)
    _submit(db, op, reviewer, review_session, a, rating="4", comments="one\ntwo")
    _restamp_stored(db, a, rating="04", comments="one\r\ntwo")

    _save(db, op, reviewer, review_session, a, rating="5", comments="one\nthree")

    assert _stamps(db, a) == {"rating": False, "comments": False}


def test_blanking_an_answer_already_blank_as_posted_unstamps_nothing(
    db: Session,
) -> None:
    """Findings R2, the read of the fix: the import stores a whitespace
    cell as given, a browser posts it stripped to blank, and the blank
    rule then cleared every answer on the row. Blanking what is already
    blank is no change."""
    op, reviewer, review_session, [a] = _seed(db)
    _submit(db, op, reviewer, review_session, a, rating="4", comments="ok")
    _restamp_stored(db, a, comments="   ")

    _save(db, op, reviewer, review_session, a, rating="4", comments="")

    assert _stamps(db, a) == {"rating": True, "comments": True}
    assert _pill(db, reviewer, review_session) == "submitted"


def test_group_copies_stored_in_different_forms_keep_their_stamps(
    db: Session,
) -> None:
    op, reviewer, review_session, [first, second] = _seed(db, group=True)
    _submit(db, op, reviewer, review_session, first, rating="4", comments="ok")
    _restamp_stored(db, first, rating="04")
    _restamp_stored(db, second, rating="+4")

    _save(db, op, reviewer, review_session, first, rating="4", comments="ok")

    assert _stamps(db, first) == {"rating": True, "comments": True}
    assert _stamps(db, second) == {"rating": True, "comments": True}


@pytest.mark.parametrize(
    ("data_type", "stored", "posted"),
    [
        ("Integer", "04", "4"),
        ("Integer", " +4 ", "4"),
        ("Decimal", "1.50", "1.5"),
        ("Decimal", "x", "x"),
        ("List", " A ", "A"),
        ("String", "  one\r\ntwo ", "one\ntwo"),
        ("String", "one\rtwo", "one\ntwo"),
        ("String", None, ""),
    ],
)
def test_stored_as_posted(data_type: str, stored: str | None, posted: str) -> None:
    field = SimpleNamespace(data_type=data_type)  # all the helper reads
    assert responses_service.stored_as_posted(stored, field) == posted


def test_the_page_renders_a_stored_number_as_a_save_posts_it(
    db: Session,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A browser posts a number box holding ``+4`` as blank, so the page
    renders the stored value in the form a Save posts."""
    op, reviewer, review_session, [a] = _seed(db)
    _submit(db, op, reviewer, review_session, a, rating="4", comments="ok")
    _restamp_stored(db, a, rating="+4")
    db.commit()

    client = make_client(
        AuthenticatedUser(
            principal_id="rae-oid",
            email="rae@example.edu",
            name="Rae",
            provider="aad",
        )
    )
    body = client.get(f"/me/sessions/{review_session.public_id}/1").text

    assert 'data-rs-saved-value="4"' in body
    assert '"+4"' not in body


def test_blanking_an_assignments_only_answer_leaves_it_submitted(
    db: Session,
) -> None:
    """Findings R3, ruled 2026-10-22 (narrow the spec): with nothing
    left on its row there is nothing to release and nothing else to
    unstamp; a lone assignment's review then has no answer at all."""
    op, reviewer, review_session, [a] = _seed(db)
    _submit(db, op, reviewer, review_session, a, rating="4", comments="")
    assert _stamps(db, a) == {"rating": True}

    _save(db, op, reviewer, review_session, a, rating="", comments="")

    assert _stamps(db, a) == {}
    assert _pill(db, reviewer, review_session) == "not started"
