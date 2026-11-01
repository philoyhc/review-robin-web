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


# --- Codex on #3489 ---------------------------------------------------------


def test_a_name_correction_is_not_refused_by_the_own_mirror(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "sym-m-rename")
    reviewer = _add(db, review_session, "ann@example.edu")
    reviewers.update_reviewer(db, reviewer=reviewer, name="Ann Tan", user=_user(db))
    [reviewee] = _assert_mirrored(db, review_session)
    assert reviewee.name == "Ann Tan"


def test_an_address_correction_keeps_the_self_review_flag(client: TestClient, db: Session) -> None:
    from app.db.models import Assignment
    from app.services.instruments import ensure_default_instrument

    review_session = _session(client, db, "sym-m-self")
    reviewer = _add(db, review_session, "ann@example.edu")
    [reviewee] = _assert_mirrored(db, review_session)
    instrument = ensure_default_instrument(db, review_session)
    db.add(Assignment(
        session_id=review_session.id, reviewer_id=reviewer.id, reviewee_id=reviewee.id,
        instrument_id=instrument.id, include=False, is_self_review=True,
    ))
    db.commit()
    reviewers.update_reviewer(db, reviewer=reviewer, email="ann.tan@example.edu", user=_user(db))
    db.expire_all()
    row = db.execute(select(Assignment).where(Assignment.reviewer_id == reviewer.id)).scalar_one()
    assert row.is_self_review is True


def test_a_mirrored_tag_change_asks_before_clearing_group_answers(
    client: TestClient, db: Session
) -> None:
    import datetime as dt
    import re

    from sqlalchemy import func

    from app.db.models import Assignment, InstrumentResponseField, Response
    from app.services import instruments as instruments_service
    from app.services.instruments import ensure_default_instrument

    review_session = _session(client, db, "sym-m-groups")
    people = [
        _add(db, review_session, f"{name.lower()}@example.edu", tag_1=team)
        for name, team in (("Ann", "red"), ("Bo", "red"), ("Cy", "blue"), ("Di", "blue"))
    ]
    reviewees = _assert_mirrored(db, review_session)
    instrument = ensure_default_instrument(db, review_session)
    instrument.group_kind = instruments_service.encode_group_kind([("reviewee", "tag_1")])
    field = InstrumentResponseField(
        instrument_id=instrument.id, field_key="sym_rating", label="Rating",
        _inline_data_type="Integer", _inline_response_type="Likert5", order=0,
    )
    db.add(field)
    db.flush()
    rows = [
        Assignment(session_id=review_session.id, reviewer_id=people[0].id,
                   reviewee_id=reviewee.id, instrument_id=instrument.id)
        for reviewee in reviewees
    ]
    db.add_all(rows)
    db.flush()
    db.add_all(
        Response(assignment_id=row.id, response_field_id=field.id, value="3",
                 saved_at=dt.datetime(2026, 11, 1, tzinfo=dt.timezone.utc), version=1)
        for row in rows
    )
    db.commit()

    def responses() -> int:
        db.expire_all()
        return db.execute(select(func.count()).select_from(Response)).scalar_one()

    path = f"/operator/sessions/{review_session.public_id}/reviewers/{people[0].id}/update"
    form = {"name": "Ann", "email": "ann@example.edu", "tag_1": "blue", "status": "active"}
    refused = client.post(path, data=form, follow_redirects=False)
    assert refused.status_code == 400
    assert "Yes, clear them" in refused.text and responses() == 4
    count = re.search(r'name="acknowledge_response_loss"\s+value="(\d+)"', refused.text).group(1)
    accepted = client.post(path, data={**form, "acknowledge_response_loss": count}, follow_redirects=False)
    assert accepted.status_code == 303
    assert responses() == 4 - int(count)
