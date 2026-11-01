"""Segment 20B rung 3: the reconcile.

Under symmetric review every service that writes reviewers leaves the
Reviewees roster with the same people, fields and status, each reviewee
linked to its reviewer by ``mirrors_reviewer_id``. One test per writer,
plus the address change that keeps the reviewee's id, the labels and the
"what they see of their own entry" list. With the mode off nothing is
mirrored.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, SessionFieldLabel, User
from app.services import csv_imports, participant_info, reviewers, session_clone, symmetric_review


def _session(client: TestClient, db: Session, code: str, *, on: bool = True) -> ReviewSession:
    data = {"name": "Sym", "code": code, "description": ""}
    if on:
        data["symmetric_review"] = "true"
    response = client.post("/operator/sessions", data=data, follow_redirects=False)
    assert response.status_code == 303
    return db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()


def _user(db: Session) -> User:
    return db.execute(select(User).order_by(User.id)).scalars().first()


def _assert_mirrored(db: Session, review_session: ReviewSession) -> list[Reviewee]:
    db.expire_all()
    revs = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id).order_by(Reviewer.id)
    ).scalars().all()
    ees = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalars().all()
    by_link = {e.mirrors_reviewer_id: e for e in ees}
    assert len(ees) == len(revs) and set(by_link) == {r.id for r in revs}
    for r in revs:
        e = by_link[r.id]
        for ee_field, r_field in symmetric_review.MIRRORED_FIELDS:
            assert getattr(e, ee_field) == getattr(r, r_field), (ee_field, r.email)
    return [by_link[r.id] for r in revs]


def _add(db: Session, review_session: ReviewSession, email: str, **kw: str) -> Reviewer:
    return reviewers.create_reviewer(
        db, review_session=review_session, name=email.split("@")[0], email=email,
        user=_user(db), **kw,
    )


def _import(db: Session, review_session: ReviewSession, body: str, **kw: bool) -> None:
    parsed = csv_imports.parse_reviewer_csv(body.encode())
    assert not parsed.issues, parsed.issues
    csv_imports.save_reviewers(
        db, session=review_session, user=_user(db), rows=parsed.rows,
        filename="r.csv", correlation_id="c", **kw,
    )
    db.commit()


def test_create_mirrors(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "sym-m-create")
    _add(db, review_session, "ann@example.edu", tag_1="A", profile_link="https://x.example/ann")
    _assert_mirrored(db, review_session)


def test_an_address_correction_keeps_the_reviewee(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "sym-m-edit")
    reviewer = _add(db, review_session, "ann@example.edu")
    [before] = _assert_mirrored(db, review_session)
    reviewers.update_reviewer(db, reviewer=reviewer, email="ann.tan@example.edu", name="Ann Tan", user=_user(db))
    [after] = _assert_mirrored(db, review_session)
    assert after.id == before.id and after.email_or_identifier == "ann.tan@example.edu"


def test_status_mirrors(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "sym-m-status")
    reviewer = _add(db, review_session, "ann@example.edu")
    reviewers.bulk_inactivate(db, review_session=review_session, reviewer_ids=[reviewer.id], user=_user(db))
    [reviewee] = _assert_mirrored(db, review_session)
    assert reviewee.status == "inactive"
    reviewers.bulk_reactivate(db, review_session=review_session, reviewer_ids=[reviewer.id], user=_user(db))
    [reviewee] = _assert_mirrored(db, review_session)
    assert reviewee.status == "active"


def test_delete_selected_takes_the_reviewee(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "sym-m-delete")
    ann = _add(db, review_session, "ann@example.edu")
    _add(db, review_session, "bob@example.edu")
    reviewers.delete_selected(db, review_session=review_session, reviewer_ids=[ann.id], user=_user(db))
    [bob] = _assert_mirrored(db, review_session)
    assert bob.email_or_identifier == "bob@example.edu"


def test_imports_mirror_replace_append_and_merge(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "sym-m-import")
    _import(db, review_session, "ReviewerName,ReviewerEmail\nAnn,ann@example.edu\nBob,bob@example.edu\n")
    assert len(_assert_mirrored(db, review_session)) == 2
    _import(db, review_session, "ReviewerName,ReviewerEmail\nCai,cai@example.edu\n", append=True)
    assert len(_assert_mirrored(db, review_session)) == 3
    _import(db, review_session, "ReviewerName,ReviewerEmail\nAnn Tan,ann@example.edu\n", merge=True)
    names = sorted(e.name for e in _assert_mirrored(db, review_session))
    assert names == ["Ann Tan", "Bob", "Cai"]
    _import(db, review_session, "ReviewerName,ReviewerEmail\nDee,dee@example.edu\n")
    [dee] = _assert_mirrored(db, review_session)
    assert dee.email_or_identifier == "dee@example.edu"


def test_delete_all_takes_every_reviewee(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "sym-m-delall")
    _add(db, review_session, "ann@example.edu")
    csv_imports.delete_all_reviewers(db, review_session=review_session, user=_user(db), correlation_id="c")
    assert _assert_mirrored(db, review_session) == []


def test_a_clone_links_its_copied_reviewees(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "sym-m-clone")
    _add(db, review_session, "ann@example.edu")
    clone = session_clone.clone_session(db, source=review_session, user=_user(db), mode="all")
    assert clone.symmetric_review is True
    [reviewee] = _assert_mirrored(db, clone)
    assert reviewee.email_or_identifier == "ann@example.edu"


def test_labels_and_self_fields_follow(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "sym-m-labels")
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/reviewers/field-labels",
        data={"tag_1": "Team"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303), response.text
    db.expire_all()
    label = db.execute(
        select(SessionFieldLabel).where(
            SessionFieldLabel.session_id == review_session.id,
            SessionFieldLabel.source_type == "reviewee",
            SessionFieldLabel.source_field == "tag_1",
        )
    ).scalar_one()
    assert label.label == "Team"
    participant_info.set_self_fields(
        db, review_session=review_session, user=_user(db), participant="reviewer",
        keys=["name", "email", "tag_1"],
    )
    db.refresh(review_session)
    assert review_session.reviewee_self_fields == ["name", "email_or_identifier", "tag_1"]


def test_off_mirrors_nothing(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "sym-m-off", on=False)
    _add(db, review_session, "ann@example.edu")
    assert db.execute(select(Reviewee).where(Reviewee.session_id == review_session.id)).first() is None
