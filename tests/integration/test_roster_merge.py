"""Merging into a roster (segment 19Z, upsert amendment, rung 9): a row
already on the roster is updated, any other added, and rows absent from
the file are kept. Blank cells and absent columns keep their values;
Status changes only when the file has the column; a row whose address
resolved to an account bound on the roster updates that row and keeps
its address.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Observer, Relationship, Reviewee, Reviewer
from app.schemas.imports import (
    ObserverImportRow,
    RelationshipImportRow,
    RevieweeImportRow,
    ReviewerImportRow,
)
from app.services import csv_imports, relationships
from app.services.csv_imports import AppendConflict, DirectoryCheck

from .test_roster_append import JANE, JANE_OID, _seeded, _session


def _merge_reviewers(db, review_session, owner, rows, **kwargs):
    return csv_imports.save_reviewers(
        db, session=review_session, user=owner, rows=rows, filename="m.csv",
        correlation_id="c", merge=True, **kwargs,
    )


def _reviewer(db: Session, session_id: int, email: str) -> Reviewer:
    db.expire_all()
    return db.execute(
        select(Reviewer).where(Reviewer.session_id == session_id, Reviewer.email == email)
    ).scalar_one()


def test_a_merge_updates_matched_rows_adds_the_rest_and_keeps_the_absent(db: Session) -> None:
    review_session, owner, ana, _ = _seeded(db, "mrg-basic")
    db.add(Reviewer(session_id=review_session.id, name="Kim", email="kim@example.edu", tag_1="A"))
    ana.tag_1 = "Old"
    ana.tag_2 = "Keep"
    db.commit()

    replaced, new = _merge_reviewers(
        db, review_session, owner,
        [
            ReviewerImportRow(name="Ana Lee", email="ANA@example.edu", tag_1="New"),
            ReviewerImportRow(name="Cy", email="cy@example.edu"),
        ],
        columns=frozenset({"ReviewerName", "ReviewerEmail", "ReviewerTag1"}),
    )
    assert (replaced, new) == (0, 1)
    ana = _reviewer(db, review_session.id, "ana@example.edu")
    # Updated from non-blank cells; tag_2 (blank / absent) kept; address kept.
    assert (ana.name, ana.tag_1, ana.tag_2) == ("Ana Lee", "New", "Keep")
    assert _reviewer(db, review_session.id, "kim@example.edu").tag_1 == "A"
    assert _reviewer(db, review_session.id, "cy@example.edu").name == "Cy"

    imported = db.execute(select(AuditEvent).where(AuditEvent.event_type == "reviewers.imported")).scalar_one()
    assert imported.detail["counts"] == {"new": 1, "updated": 1, "unchanged": 0}
    assert imported.detail["context"]["mode"] == "upsert"
    updated = db.execute(select(AuditEvent).where(AuditEvent.event_type == "reviewer.updated")).scalar_one()
    assert updated.detail["changes"]["tag_1"] == ["Old", "New"]
    assert updated.detail["refs"]["reviewer_id"] == ana.id


def test_status_changes_only_when_the_file_has_the_column(db: Session) -> None:
    review_session, owner, ana, _ = _seeded(db, "mrg-status")
    row = ReviewerImportRow(name="Ana", email="ana@example.edu", status="inactive")
    _merge_reviewers(db, review_session, owner, [ReviewerImportRow(name="Ana", email="ana@example.edu")],
                     columns=frozenset({"ReviewerName", "ReviewerEmail"}))
    assert _reviewer(db, review_session.id, "ana@example.edu").status == "active"
    _merge_reviewers(db, review_session, owner, [row],
                     columns=frozenset({"ReviewerName", "ReviewerEmail", "Status"}))
    assert _reviewer(db, review_session.id, "ana@example.edu").status == "inactive"


def test_an_unchanged_row_writes_no_event(db: Session) -> None:
    review_session, owner, _, _ = _seeded(db, "mrg-same")
    _merge_reviewers(db, review_session, owner, [ReviewerImportRow(name="Ana", email="ana@example.edu")])
    assert db.execute(select(AuditEvent).where(AuditEvent.event_type == "reviewer.updated")).first() is None
    imported = db.execute(select(AuditEvent).where(AuditEvent.event_type == "reviewers.imported")).scalar_one()
    assert imported.detail["counts"] == {"new": 0, "updated": 0, "unchanged": 1}


def test_a_row_on_a_bound_account_updates_that_row_and_keeps_its_address(db: Session) -> None:
    review_session, owner = _session(db, "mrg-acct")
    db.add(Reviewer(session_id=review_session.id, name="Jane", email="jane.tan@example.edu", directory_object_id=JANE_OID))
    db.commit()
    directory = DirectoryCheck(accounts={"e0123456@example.edu": JANE}, counts={})
    _merge_reviewers(db, review_session, owner,
                     [ReviewerImportRow(name="Jane", email="e0123456@example.edu", tag_1="T")], directory=directory)
    db.expire_all()
    rows = db.execute(select(Reviewer).where(Reviewer.session_id == review_session.id)).scalars().all()
    assert [(r.email, r.tag_1) for r in rows] == [("jane.tan@example.edu", "T")]


def test_a_matched_unbound_row_is_bound_when_its_address_resolves(db: Session) -> None:
    review_session, owner = _session(db, "mrg-bind")
    db.add(Reviewer(session_id=review_session.id, name="Jane", email="e0123456@example.edu"))
    db.commit()
    directory = DirectoryCheck(accounts={"e0123456@example.edu": JANE}, counts={})
    _merge_reviewers(db, review_session, owner,
                     [ReviewerImportRow(name="Jane", email="e0123456@example.edu")], directory=directory)
    assert _reviewer(db, review_session.id, "e0123456@example.edu").directory_object_id == JANE_OID


def test_two_file_rows_on_one_account_refuse_the_merge(db: Session) -> None:
    review_session, owner = _session(db, "mrg-twice")
    db.commit()
    directory = DirectoryCheck(
        accounts={"e0123456@example.edu": JANE, "jane.tan@example.edu": JANE}, counts={}
    )
    with pytest.raises(AppendConflict) as refused:
        _merge_reviewers(db, review_session, owner, [
            ReviewerImportRow(name="Jane", email="jane.tan@example.edu"),
            ReviewerImportRow(name="Jane", email="e0123456@example.edu"),
        ], directory=directory)
    assert [i.row_number for i in refused.value.issues] == [2]


def test_reviewees_and_observers_merge_the_same_way(db: Session) -> None:
    review_session, owner, _, bo = _seeded(db, "mrg-other")
    db.add(Observer(session_id=review_session.id, email="obs@example.edu", display_name="Old"))
    db.commit()
    csv_imports.save_reviewees(
        db, session=review_session, user=owner, filename="", correlation_id="c", merge=True,
        rows=[RevieweeImportRow(name="Bo", email_or_identifier="bo@example.edu", tag_1="X")],
    )
    csv_imports.save_observers(
        db, session=review_session, user=owner, filename="", correlation_id="c", merge=True,
        rows=[ObserverImportRow(email="obs@example.edu", display_name="New")],
    )
    db.expire_all()
    assert db.get(Reviewee, bo.id).tag_1 == "X"
    assert db.execute(select(Observer.display_name).where(Observer.session_id == review_session.id)).scalar_one() == "New"


def test_relationships_merge_updates_a_held_pairs_tags(db: Session) -> None:
    review_session, owner, ana, bo = _seeded(db, "mrg-rel")
    cy = Reviewer(session_id=review_session.id, name="Cy", email="cy@example.edu")
    db.add(cy)
    db.commit()
    assert relationships.save_relationships(
        db, session=review_session, user=owner, filename="", correlation_id="c", merge=True,
        rows=[RelationshipImportRow(reviewer_id=ana.id, reviewee_id=bo.id, tag_1="G"),
              RelationshipImportRow(reviewer_id=cy.id, reviewee_id=bo.id)],
    ) == (0, 1)
    db.expire_all()
    pairs = {r.reviewer_id: r.tag_1 for r in db.execute(select(Relationship).where(Relationship.session_id == review_session.id)).scalars()}
    assert pairs == {ana.id: "G", cy.id: None}
    assert db.execute(select(AuditEvent).where(AuditEvent.event_type == "relationship.updated")).scalar_one()


def test_a_reviewee_merge_that_redraws_an_answered_group_asks_first(db: Session, client) -> None:
    """Ann moves from red into blue by a merged tag: blue gains her and
    would clear 3 answers, so the save refuses with the count and writes
    nothing; with the count acknowledged it goes through."""
    from app.db.models import User
    from app.services import responses as responses_service

    from .test_group_clear_asks_first import _responses, _reviewee, _seed

    session, _ = _seed(db, client, "mrg-groups")
    owner = db.execute(select(User)).scalars().first()
    row = [RevieweeImportRow(name="Ann", email_or_identifier="ann@example.edu", tag_1="blue")]

    def merge(**kwargs):
        return csv_imports.save_reviewees(
            db, session=session, user=owner, filename="", correlation_id="c", merge=True, rows=row, **kwargs
        )

    # A route passes 0 for an unticked "Yes, clear them" (``None``, the
    # service default, deletes without asking).
    with pytest.raises(responses_service.GroupAnswersWouldClear) as refused:
        merge(acknowledged_loss=0)
    assert refused.value.count == 3
    db.rollback()
    assert _reviewee(db, session.id, "Ann").tag_1 == "red"
    assert _responses(db) == 4

    merge(acknowledged_loss=3)
    assert _reviewee(db, session.id, "Ann").tag_1 == "blue"
    assert _responses(db) == 1


def test_a_rename_through_an_account_match_is_checked_at_the_kept_address(db: Session) -> None:
    """Jane is a reviewer and a reviewee at `jane.tan@`. A merge naming the
    reviewer "Different" through her UPN matches her bound row by account
    and keeps `jane.tan@`, so the name is checked there and the reviewee's
    disagrees (Codex, #3440)."""
    review_session, owner = _session(db, "mrg-rename")
    db.add(Reviewer(session_id=review_session.id, name="Jane", email="jane.tan@example.edu", directory_object_id=JANE_OID))
    db.add(Reviewee(session_id=review_session.id, name="Jane", email_or_identifier="jane.tan@example.edu"))
    db.commit()
    directory = DirectoryCheck(accounts={"e0123456@example.edu": JANE}, counts={})
    with pytest.raises(AppendConflict) as refused:
        _merge_reviewers(db, review_session, owner,
                         [ReviewerImportRow(name="Different", email="e0123456@example.edu")], directory=directory)
    assert refused.value.issues[0].row_number == 1
    db.rollback()
    assert _reviewer(db, review_session.id, "jane.tan@example.edu").name == "Jane"


def test_a_merge_that_binds_a_reviewer_recomputes_self_review(db: Session) -> None:
    """The reviewer row at Jane's UPN is unbound and her reviewee row (by
    mail) is bound: their assignment is not a self-review until a merge
    binds the reviewer, which must recompute it (Codex, #3440)."""
    from app.db.models import Assignment
    from app.services.instruments import ensure_default_instrument

    review_session, owner = _session(db, "mrg-selfrev")
    jane_r = Reviewer(session_id=review_session.id, name="Jane", email="e0123456@example.edu")
    jane_e = Reviewee(session_id=review_session.id, name="Jane", email_or_identifier="jane.tan@example.edu", directory_object_id=JANE_OID)
    db.add_all([jane_r, jane_e])
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    row = Assignment(session_id=review_session.id, reviewer_id=jane_r.id, reviewee_id=jane_e.id, instrument_id=instrument.id, is_self_review=False)
    db.add(row)
    db.commit()
    directory = DirectoryCheck(accounts={"e0123456@example.edu": JANE}, counts={})
    _merge_reviewers(db, review_session, owner,
                     [ReviewerImportRow(name="Jane", email="e0123456@example.edu")], directory=directory)
    db.expire_all()
    assert db.get(Assignment, row.id).is_self_review is True
