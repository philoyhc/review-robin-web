"""``results.csv`` tells *not asked* from *missing* (segment 23G rung 5,
`guide/segment_23G_linked_custom_instrument.md`): a field a branch closed
on a submitted assignment has a ``not_asked`` row with no value; a field
asked and left blank has none. A custom linked instrument reports its
held fields only."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import handoffs
from utilityapps.interop_poc import mock

from .test_handoff_update import _created
from .test_handoffs import REVIEWEES, REVIEWERS


def _session(client: TestClient, db: Session, mode: str) -> tuple[ReviewSession, str]:
    settings = mock.settings_csv() + f"instruments[1].linked_mode,{mode},enum\r\n"
    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": settings}
    return _created(client, db, files=files)


def _familiarity_governs_score(db: Session) -> dict[str, InstrumentResponseField]:
    """Familiarity (Review Robin's own) first, governing Score when at
    least 1; Comments after, outside any branch."""
    instrument = db.scalars(select(Instrument)).one()
    fields = {f.field_key: f for f in instrument.response_fields}
    for field in fields.values():
        field.order += 1
    familiarity = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="familiarity",
        label="Familiarity",
        order=0,
        required=True,
        visible=True,
        _inline_data_type="Integer",
        _inline_response_type="1-to-5int",
        _inline_min=0,
        _inline_max=5,
        _inline_step=1,
        branch_op="ge",
        branch_value="1",
    )
    db.add(familiarity)
    db.flush()
    fields["score"].branch_parent_id = familiarity.id
    db.commit()
    return {**fields, "familiarity": familiarity}


def _answer(db: Session, values: list[dict[str, str]]) -> None:
    """The first reviewer's assignments, one per reviewee, each submitted
    with ``values`` (field key → value) in turn."""
    review_session = db.scalars(select(ReviewSession)).one()
    instrument = db.scalars(select(Instrument)).one()
    by_key = {f.field_key: f for f in instrument.response_fields}
    reviewer = db.scalars(
        select(Reviewer).where(Reviewer.session_id == review_session.id).order_by(Reviewer.id)
    ).first()
    assert reviewer is not None
    reviewees = db.scalars(
        select(Reviewee).where(Reviewee.session_id == review_session.id).order_by(Reviewee.id)
    ).all()
    for reviewee, answers in zip(reviewees, values, strict=False):
        assignment = Assignment(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
        )
        db.add(assignment)
        db.flush()
        for key, value in answers.items():
            db.add(
                Response(
                    assignment_id=assignment.id,
                    response_field_id=by_key[key].id,
                    value=value,
                    submitted_at=datetime.now(UTC),
                )
            )
    db.commit()


def _results(client: TestClient, transfer: str) -> list[dict[str, Any]]:
    reply = client.get(f"/operator/handoffs/{transfer}/results.csv")
    assert reply.status_code == 200, reply.text
    return list(csv.DictReader(io.StringIO(reply.content.decode("utf-8"))))


def _by_reviewee(rows: list[dict[str, Any]]) -> dict[str, list[tuple[str, str, str]]]:
    out: dict[str, list[tuple[str, str, str]]] = {}
    for row in rows:
        out.setdefault(row["RevieweeEmail"], []).append(
            (row["FieldKey"], row["Value"], row["Answer"])
        )
    return out


def test_the_header_ends_with_answer() -> None:
    assert handoffs.RESULTS_HEADER[-1] == "Answer"


def test_a_closed_branch_is_not_asked_and_own_fields_stay_home(
    client: TestClient, db: Session
) -> None:
    _, transfer = _session(client, db, "custom")
    _familiarity_governs_score(db)
    _answer(
        db,
        [
            {"familiarity": "0", "comment": "Barely know them"},
            {"familiarity": "3", "score": "4", "comment": "Strong"},
        ],
    )
    rows = _results(client, transfer)
    assert all(row["SubmittedAt"] for row in rows)
    first, second = _by_reviewee(rows).values()
    # Score sits behind Familiarity's closed branch: not asked, no value.
    # Familiarity is Review Robin's own, so it is not reported.
    assert first == [("score", "", "not_asked"), ("comment", "Barely know them", "answered")]
    assert second == [("score", "4", "answered"), ("comment", "Strong", "answered")]


def test_a_field_asked_and_left_blank_has_no_row(client: TestClient, db: Session) -> None:
    _, transfer = _session(client, db, "custom")
    _familiarity_governs_score(db)
    _answer(db, [{"familiarity": "3", "score": "2"}])  # Comments left blank
    (only,) = _by_reviewee(_results(client, transfer)).values()
    assert only == [("score", "2", "answered")]


def test_any_branched_instrument_says_not_asked(client: TestClient, db: Session) -> None:
    """Not custom-only (author, 2026-11-25): a locked instrument with a
    branch set reports every field, a closed one as not asked."""
    _, transfer = _session(client, db, "locked")
    _familiarity_governs_score(db)
    _answer(db, [{"familiarity": "0", "comment": "Barely"}])
    (only,) = _by_reviewee(_results(client, transfer)).values()
    assert only == [
        ("familiarity", "0", "answered"),
        ("score", "", "not_asked"),
        ("comment", "Barely", "answered"),
    ]


def test_an_unsubmitted_assignment_says_nothing_of_its_branches(
    client: TestClient, db: Session
) -> None:
    _, transfer = _session(client, db, "custom")
    _familiarity_governs_score(db)
    _answer(db, [{"familiarity": "0"}])
    for response in db.scalars(select(Response)):
        response.submitted_at = None
    db.commit()
    assert _results(client, transfer) == []
