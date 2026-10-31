"""Appending to a roster (segment 19Z, rung 3): the services' ``append``
mode adds a file's rows and keeps every row, assignment and relationship
already there; a row already on the roster, or on a directory account
already there, refuses the whole file before anything is written.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Observer,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.schemas.imports import (
    ObserverImportRow,
    RelationshipImportRow,
    RevieweeImportRow,
    ReviewerImportRow,
)
from app.services import csv_imports, field_labels, relationships
from app.services.csv_imports import AppendConflict, DirectoryCheck
from app.services.directory_accounts import Account
from app.services.instruments import ensure_default_instrument

JANE_OID = "11111111-1111-4111-8111-111111111111"
JANE = Account(object_id=JANE_OID, mail="jane.tan@example.edu", upn="e0123456@example.edu")


def _session(db: Session, code: str) -> tuple[ReviewSession, User]:
    owner = User(email=f"op-{code}@example.edu")
    db.add(owner)
    db.flush()
    review_session = ReviewSession(name=code.title(), code=code, created_by_user_id=owner.id)
    review_session.status = "draft"
    db.add(review_session)
    db.flush()
    return review_session, owner


def _seeded(db: Session, code: str) -> tuple[ReviewSession, User, Reviewer, Reviewee]:
    review_session, owner = _session(db, code)
    ana = Reviewer(session_id=review_session.id, name="Ana", email="ana@example.edu")
    bo = Reviewee(session_id=review_session.id, name="Bo", email_or_identifier="bo@example.edu")
    db.add_all([ana, bo])
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    db.add(Assignment(session_id=review_session.id, reviewer_id=ana.id, reviewee_id=bo.id, instrument_id=instrument.id))
    db.add(Relationship(session_id=review_session.id, reviewer_id=ana.id, reviewee_id=bo.id))
    db.commit()
    return review_session, owner, ana, bo


def _save_reviewers(db, review_session, owner, rows, **kwargs):
    return csv_imports.save_reviewers(
        db, session=review_session, user=owner, rows=rows,
        filename="late.csv", correlation_id="c", **kwargs,
    )


def _names(db: Session, model, session_id: int) -> list[str]:
    column = model.name if model is not Observer else model.email
    return sorted(db.execute(select(column).where(model.session_id == session_id)).scalars())


def test_an_append_adds_the_rows_and_keeps_everything_already_there(db: Session) -> None:
    review_session, owner, ana, bo = _seeded(db, "app-keep")
    replaced, new = _save_reviewers(
        db, review_session, owner, [ReviewerImportRow(name="Cy", email="cy@example.edu")], append=True
    )
    assert (replaced, new) == (0, 1)
    assert _names(db, Reviewer, review_session.id) == ["Ana", "Cy"]
    # The assignment and the relationship on Ana survive, as a replace's
    # cascade would not let them.
    assert db.execute(select(Assignment).where(Assignment.reviewer_id == ana.id)).scalar_one()
    assert db.execute(select(Relationship).where(Relationship.reviewer_id == ana.id)).scalar_one()

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "reviewers.imported")
    ).scalar_one()
    assert event.detail["counts"] == {"new": 1, "kept": 1}
    assert event.detail["context"] == {"filename": "late.csv", "mode": "append"}


def test_a_replace_is_unchanged(db: Session) -> None:
    review_session, owner, ana, _ = _seeded(db, "app-replace")
    replaced, new = _save_reviewers(db, review_session, owner, [ReviewerImportRow(name="Cy", email="cy@example.edu")])
    assert (replaced, new) == (1, 1)
    assert _names(db, Reviewer, review_session.id) == ["Cy"]
    event = db.execute(select(AuditEvent).where(AuditEvent.event_type == "reviewers.imported")).scalar_one()
    assert event.detail["counts"]["replaced"] == 1 and "kept" not in event.detail["counts"]
    assert "mode" not in (event.detail.get("context") or {})


def test_a_row_already_on_the_roster_refuses_the_whole_append(db: Session) -> None:
    review_session, owner, _, _ = _seeded(db, "app-dup")
    review_session.status = "validated"
    db.commit()
    rows = [
        ReviewerImportRow(name="Cy", email="cy@example.edu"),
        ReviewerImportRow(name="Ana", email=" ANA@example.edu "),
    ]
    assert [i.row_number for i in csv_imports.append_conflicts(
        db, session_id=review_session.id, kind="reviewers", rows=rows
    )] == [2]
    with pytest.raises(AppendConflict) as refused:
        _save_reviewers(db, review_session, owner, rows, append=True)
    issue = refused.value.issues[0]
    assert issue.row_number == 2 and issue.problem == "ReviewerEmail is already on the roster"
    db.rollback()
    # Nothing written: no Cy, and the session is not knocked back to draft.
    assert _names(db, Reviewer, review_session.id) == ["Ana"]
    db.refresh(review_session)
    assert review_session.status == "validated"


def test_a_row_on_an_account_already_on_the_roster_refuses_the_append(db: Session) -> None:
    review_session, owner = _session(db, "app-acct")
    db.add(Reviewer(session_id=review_session.id, name="Jane", email="jane.tan@example.edu", directory_object_id=JANE_OID))
    db.commit()
    by_upn = [ReviewerImportRow(name="Jane", email="e0123456@example.edu")]
    directory = DirectoryCheck(accounts={"e0123456@example.edu": JANE}, counts={})
    with pytest.raises(AppendConflict) as refused:
        _save_reviewers(db, review_session, owner, by_upn, directory=directory, append=True)
    assert refused.value.issues[0].problem == "ReviewerEmail is a directory account already on the roster"
    db.rollback()
    # Unchecked, the address alone decides, and it is new.
    _save_reviewers(db, review_session, owner, by_upn, append=True)
    assert _names(db, Reviewer, review_session.id) == ["Jane", "Jane"]


def test_reviewee_identifiers_and_observers_are_checked_the_same_way(db: Session) -> None:
    review_session, owner = _session(db, "app-other")
    db.add(Reviewee(session_id=review_session.id, name="Anon", email_or_identifier="STU-0001"))
    db.add(Observer(session_id=review_session.id, email="obs@example.edu"))
    db.commit()
    with pytest.raises(AppendConflict):
        csv_imports.save_reviewees(
            db, session=review_session, user=owner, filename="", correlation_id="c", append=True,
            rows=[RevieweeImportRow(name="Anon", email_or_identifier="stu-0001")],
        )
    db.rollback()
    with pytest.raises(AppendConflict):
        csv_imports.save_observers(
            db, session=review_session, user=owner, filename="", correlation_id="c", append=True,
            rows=[ObserverImportRow(email="OBS@example.edu")],
        )
    db.rollback()
    csv_imports.save_observers(
        db, session=review_session, user=owner, filename="", correlation_id="c", append=True,
        rows=[ObserverImportRow(email="new@example.edu")],
    )
    assert _names(db, Observer, review_session.id) == ["new@example.edu", "obs@example.edu"]


def test_an_append_upserts_header_labels_and_clears_none(db: Session) -> None:
    review_session, owner, _, _ = _seeded(db, "app-labels")
    field_labels.upsert(db, review_session, source_type="reviewer", source_field="tag_1", label="Tutor", user=owner)
    db.commit()
    _save_reviewers(
        db, review_session, owner, [ReviewerImportRow(name="Cy", email="cy@example.edu")],
        field_labels_captured={("reviewer", "tag_2"): "House"}, append=True,
    )
    db.refresh(review_session)
    labels = field_labels.all_labels(review_session)
    assert labels.get(("reviewer", "tag_1")) == "Tutor"
    assert labels.get(("reviewer", "tag_2")) == "House"


def test_relationships_append_keeps_the_pairs_and_refuses_a_held_one(db: Session) -> None:
    review_session, owner, ana, bo = _seeded(db, "app-rel")
    cy = Reviewer(session_id=review_session.id, name="Cy", email="cy@example.edu")
    db.add(cy)
    db.commit()

    def save(rows):
        return relationships.save_relationships(
            db, session=review_session, user=owner, rows=rows,
            filename="", correlation_id="c", append=True,
        )

    with pytest.raises(AppendConflict) as refused:
        save([RelationshipImportRow(reviewer_id=cy.id, reviewee_id=bo.id),
              RelationshipImportRow(reviewer_id=ana.id, reviewee_id=bo.id)])
    assert [i.row_number for i in refused.value.issues] == [2]
    db.rollback()
    assert save([RelationshipImportRow(reviewer_id=cy.id, reviewee_id=bo.id)]) == (0, 1)
    pairs = set(db.execute(select(Relationship.reviewer_id).where(Relationship.session_id == review_session.id)).scalars())
    assert pairs == {ana.id, cy.id}
    event = db.execute(select(AuditEvent).where(AuditEvent.event_type == "relationships.imported")).scalar_one()
    assert event.detail["counts"] == {"new": 1, "kept": 1}
    assert event.detail["context"]["mode"] == "append"
