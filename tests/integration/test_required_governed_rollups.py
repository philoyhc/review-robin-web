"""19T Item 11 rung 3 — the monitoring rollups count a required governed
field only while its branch is open, by sending its instrument down a
Python path ("route (a)"), and a reviewer whose only empty required field
sits behind a closed branch is complete and is not reminded.

As in rung 2, each test sets ``required`` directly rather than through
the card. The shared parity fixture keeps its governed fields optional so
its "sql" cases still reach the aggregates; this file pins required
governed fields on both halves together."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    EmailOutbox,
    Instrument,
    InstrumentResponseField,
    Invitation,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import monitoring

from .test_monitoring_rollup_parity import (
    REVIEWEE_IMPLEMENTATIONS,
    REVIEWER_IMPLEMENTATIONS,
    _by_email,
    _by_identifier,
    _utc_naive,
)
from .test_reminders import _ready_session

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _mixed_session(db: Session):
    """Rae reviews Carol and Dan on `branched` (Rating required, and
    Comments required while Rating ≥ 4), and Carol on `plain` (one
    required field, no branch), so Carol's row adds the SQL half and the
    Python half.

    - Carol on `branched`: Rating 2, submitted → branch closed, complete.
    - Dan on `branched`: Rating 5, submitted, no Comments → open, missing.
    - Carol on `plain`: answered, submitted, later than the rest."""
    user = User(email="op-rg-rollups@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(name="S", code="rg-rollups", created_by_user_id=user.id)
    db.add(review_session)
    db.flush()
    sid = review_session.id
    rae = Reviewer(session_id=sid, name="Rae", email="rae@example.edu")
    carol = Reviewee(session_id=sid, name="Carol", email_or_identifier="carol@example.edu")
    dan = Reviewee(session_id=sid, name="Dan", email_or_identifier="dan@example.edu")
    branched = Instrument(session_id=sid, name="Branched", order=0, session_seq=1)
    plain = Instrument(session_id=sid, name="Plain", order=1, session_seq=2)
    db.add_all([rae, carol, dan, branched, plain])
    db.flush()
    rating = InstrumentResponseField(
        instrument_id=branched.id, field_key="rating", label="Rating",
        required=True, order=0, _inline_data_type="Integer",
        branch_op="ge", branch_value="4",
    )
    comments = InstrumentResponseField(
        instrument_id=branched.id, field_key="comments", label="Comments",
        required=True, order=1,
    )
    score = InstrumentResponseField(
        instrument_id=plain.id, field_key="score", label="Score", required=True, order=0,
    )
    db.add_all([rating, comments, score])
    db.flush()
    comments.branch_parent_id = rating.id
    rows = {}
    for key, reviewee, instrument in (
        ("carol", carol, branched), ("dan", dan, branched), ("plain", carol, plain),
    ):
        rows[key] = Assignment(
            session_id=sid, reviewer_id=rae.id, reviewee_id=reviewee.id,
            instrument_id=instrument.id,
        )
    db.add_all(rows.values())
    db.flush()
    db.add_all([
        Response(assignment_id=rows["carol"].id, response_field_id=rating.id,
                 value="2", saved_at=T0, submitted_at=T0),
        Response(assignment_id=rows["dan"].id, response_field_id=rating.id,
                 value="5", saved_at=T0, submitted_at=T0),
        Response(assignment_id=rows["plain"].id, response_field_id=score.id,
                 value="7", saved_at=T0, submitted_at=T0 + timedelta(hours=2)),
    ])
    db.flush()
    return review_session, rows


def test_the_reviewer_rollups_count_only_open_branches(db: Session) -> None:
    review_session, _ = _mixed_session(db)
    for name, rollup in REVIEWER_IMPLEMENTATIONS:
        rae = _by_email(rollup(db, review_session))["rae@example.edu"]
        assert rae.assignment_count == 3, name
        # Carol 1 (closed) + Dan 2 (open) + plain 1, not 2 + 2 + 1.
        assert rae.required_total == 4, name
        assert rae.missing_required_count == 1, name
        assert rae.completed_count == 2, name
        assert rae.pill_state == "in progress", name


def test_the_reviewee_rollups_count_only_open_branches(db: Session) -> None:
    review_session, _ = _mixed_session(db)
    for name, rollup in REVIEWEE_IMPLEMENTATIONS:
        rows = _by_identifier(rollup(db, review_session))
        assert list(rows) == ["carol@example.edu", "dan@example.edu"], name
        carol, dan = rows["carol@example.edu"], rows["dan@example.edu"]
        # Carol's two rows add the SQL half (plain) and the Python half.
        assert (carol.reviewer_count, carol.completed_count) == (2, 2), name
        assert carol.pill_state == "complete", name
        assert _utc_naive(carol.last_response_at) == _utc_naive(
            T0 + timedelta(hours=2)
        ), name
        assert (dan.reviewer_count, dan.completed_count) == (1, 0), name
        assert dan.pill_state == "no responses", name
        assert _utc_naive(dan.last_response_at) == _utc_naive(T0), name


def test_the_python_halves_read_only_their_own_work(db: Session) -> None:
    """Route (a) sends only the instruments with a required governed field
    (and group-scoped ones) through Python; the plain instrument's rows
    stay in SQL, never loaded as ORM rows (19R Item 3's Codex P1)."""
    review_session, rows = _mixed_session(db)
    loaded: list[Response] = []

    def on_load(_session, instance):
        if isinstance(instance, Response):
            loaded.append(instance)

    db.expunge_all()
    review_session = db.get(ReviewSession, review_session.id)
    event.listen(db, "loaded_as_persistent", on_load)
    try:
        monitoring.per_reviewer_progress(db, review_session)
        monitoring.per_reviewee_coverage(db, review_session)
    finally:
        event.remove(db, "loaded_as_persistent", on_load)
    assert loaded, "the Python halves loaded nothing; the check is vacuous"
    assert {r.assignment_id for r in loaded} <= {rows["carol"].id, rows["dan"].id}


@pytest.mark.parametrize("mode", [None, "require"])
def test_a_closed_branch_isnt_reminded(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
    mode: str | None,
) -> None:
    """Rae's only empty required field sits behind a closed branch, so she
    is complete and not reminded; Sam opened his and left it empty. Under
    a require-mode parent (19T Item 13) the same: Rae's Rating 2 leaves
    Comments optional, Sam's Rating 5 owes it."""
    operator = make_client(alice)
    session = _ready_session(
        operator, db, f"rg-remind-{mode or 'show'}",
        reviewers=["rae@example.edu", "sam@example.edu"],
    )
    fields = {
        f.field_key: f
        for f in db.execute(
            select(InstrumentResponseField)
            .join(Instrument, Instrument.id == InstrumentResponseField.instrument_id)
            .where(Instrument.session_id == session.id)
        ).scalars()
    }
    fields["rating"].branch_op, fields["rating"].branch_value = "ge", "4"
    fields["comments"].branch_parent_id = fields["rating"].id
    fields["comments"].required = True
    fields["rating"].branch_mode = mode
    db.commit()

    invitations, assignments = {}, {}
    for email in ("rae@example.edu", "sam@example.edu"):
        invitations[email], assignments[email] = db.execute(
            select(Invitation, Assignment)
            .join(Reviewer, Reviewer.id == Invitation.reviewer_id)
            .join(Assignment, Assignment.reviewer_id == Reviewer.id)
            .where(Reviewer.email == email)
        ).one()
    # Every invitation goes out before anyone submits, as in
    # ``test_remind_incomplete_targets_only_incomplete``.
    for invitation in invitations.values():
        operator.post(f"/operator/sessions/{session.id}/invitations/{invitation.id}/send")
    for email, rating in (("rae@example.edu", "2"), ("sam@example.edu", "5")):
        make_client(
            AuthenticatedUser(principal_id=email, email=email, name=email, provider="aad")
        ).post(
            f"/me/sessions/{session.id}/submit",
            data={f"response[{assignments[email].id}][rating]": rating},
            follow_redirects=False,
        )

    rows = _by_email(monitoring.per_reviewer_progress(db, session))
    assert rows["rae@example.edu"].is_incomplete is False
    assert rows["sam@example.edu"].is_incomplete is True

    response = make_client(alice).post(
        f"/operator/sessions/{session.id}/invitations/remind-incomplete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    reminded = {
        email: db.execute(
            select(EmailOutbox).where(
                EmailOutbox.invitation_id == invitation.id,
                EmailOutbox.kind == "reminder",
            )
        ).scalars().all()
        for email, invitation in invitations.items()
    }
    assert len(reminded["rae@example.edu"]) == 0
    assert len(reminded["sam@example.edu"]) == 1
