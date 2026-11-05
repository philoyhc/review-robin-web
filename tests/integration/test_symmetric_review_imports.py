"""Segment 20B rung 4: the Reviewees roster read-only, and the imports.

Under symmetric review every Reviewees write route answers 409; Quick
Setup refuses a Reviewees file (also when its Settings file turns the mode
on) and, when that file turns it on beside empty rosters, turns it on
before the rosters save so the reviewers mirror; the setup bundle and the
Extract Data setup card carry the Reviewers roster alone; and Rehydrate
rebuilds the reviewees from the reviewers rather than reading the
extract's reviewees.csv.
"""

from __future__ import annotations

import csv
import io
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, User
from app.services import reviewers, session_rehydrate
from app.services.extracts import zip_bundle
from app.services.extracts.responses_extract import serialize_responses
from app.services.extracts.reviewees_extract import serialize_reviewees
from app.services.extracts.reviewers_extract import serialize_reviewers
from app.services.session_config_io import serialize_session_config
from app.web import views
from cordware.graph import FakeDirectory

REVIEWERS_CSV = b"ReviewerName,ReviewerEmail\nAnn,ann@example.edu\nBob,bob@example.edu\n"
REVIEWEES_CSV = b"RevieweeName,RevieweeEmail\nAnn,ann@example.edu\n"


def _session(client: TestClient, db: Session, code: str, *, on: bool = True) -> ReviewSession:
    data = {"name": "Sym", "code": code, "description": ""}
    if on:
        data["symmetric_review"] = "true"
    response = client.post("/operator/sessions", data=data, follow_redirects=False)
    assert response.status_code == 303
    return db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()


def _user(db: Session) -> User:
    user = db.execute(select(User).order_by(User.id)).scalars().first()
    assert user is not None
    return user


def _reviewees(db: Session, review_session: ReviewSession) -> list[Reviewee]:
    db.expire_all()
    return list(
        db.execute(select(Reviewee).where(Reviewee.session_id == review_session.id)).scalars()
    )


def _csv(rows) -> bytes:
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue().encode()


def test_every_reviewee_write_answers_409(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "sym-i-409")
    base = f"/operator/sessions/{review_session.public_id}/reviewees"
    for path, kwargs in (
        ("/create", {"data": {"name": "X", "email_or_identifier": "x@example.edu"}}),
        ("/import", {"files": {"file": ("r.csv", REVIEWEES_CSV, "text/csv")}}),
        ("/delete-all", {"data": {"confirm": "true"}}),
        ("/field-labels", {"data": {"tag_1": "Team"}}),
        ("/self-fields", {"data": {"fields": "name"}}),
        ("/bulk-inactivate", {"data": {"ids": "1"}}),
        ("/bulk-reactivate", {"data": {"ids": "1"}}),
        ("/bulk-delete", {"data": {"ids": "1", "confirm": "true"}}),
        ("/1/update", {"data": {"name": "X", "email_or_identifier": "x@example.edu"}}),
        ("/import/dismiss", {"data": {}}),
    ):
        response = client.post(base + path, follow_redirects=False, **kwargs)
        assert response.status_code == 409, (path, response.status_code)


def test_reviewee_writes_still_work_with_the_mode_off(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "sym-i-off", on=False)
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/reviewees/create",
        data={"name": "X", "email_or_identifier": "x@example.edu"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_quick_setup_refuses_a_reviewees_file(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "sym-i-qs")
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/quick-setup/submit-all",
        files={
            "reviewers_file": ("r.csv", REVIEWERS_CSV, "text/csv"),
            "reviewees_file": ("e.csv", REVIEWEES_CSV, "text/csv"),
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "Reviewees slot empty" in response.text
    assert (
        db.execute(select(Reviewer).where(Reviewer.session_id == review_session.id)).first() is None
    )


def test_quick_setup_reviewers_mirror(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "sym-i-qs-ok")
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/quick-setup/submit-all",
        files={"reviewers_file": ("r.csv", REVIEWERS_CSV, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert sorted(e.email_or_identifier for e in _reviewees(db, review_session)) == [
        "ann@example.edu",
        "bob@example.edu",
    ]


def test_a_settings_file_turning_it_on_mirrors_this_submits_reviewers(
    client: TestClient, db: Session
) -> None:
    source = _session(client, db, "sym-i-src")
    settings = _csv(
        [("field", "value", "data_type")]
        + [(r.field, r.value, r.data_type) for r in serialize_session_config(db, source)]
    )
    target = _session(client, db, "sym-i-target", on=False)
    response = client.post(
        f"/operator/sessions/{target.public_id}/quick-setup/submit-all",
        files={
            "reviewers_file": ("r.csv", REVIEWERS_CSV, "text/csv"),
            "settings_file": ("s.csv", settings, "text/csv"),
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(target)
    assert target.symmetric_review is True
    assert len(_reviewees(db, target)) == 2


def test_the_setup_bundle_and_card_carry_the_reviewers_alone(
    client: TestClient, db: Session
) -> None:
    review_session = _session(client, db, "sym-i-zip")
    reviewers.create_reviewer(
        db, review_session=review_session, name="Ann", email="ann@example.edu", user=_user(db)
    )
    data, counts = zip_bundle.build_setup_bundle(db, review_session)
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert any(n.endswith("_reviewers.csv") for n in names)
    assert not any(n.endswith("_reviewees.csv") for n in names)
    assert "reviewees" not in counts
    keys = [row.key for row in views.build_extract_data_context(db, review_session).rows]
    assert "reviewers" in keys and "reviewees" not in keys


def test_rehydrate_rebuilds_the_reviewees_from_the_reviewers(
    client: TestClient, db: Session
) -> None:
    review_session = _session(client, db, "sym-i-rehyd")
    user = _user(db)
    reviewers.create_reviewer(
        db, review_session=review_session, name="Ann", email="ann@example.edu", user=user
    )
    # The extract's reviewees.csv names someone the reviewers do not; it is
    # left unread, so they do not appear.
    files = {
        "settings.csv": _csv(
            [("field", "value", "data_type")]
            + [
                (r.field, r.value, r.data_type)
                for r in serialize_session_config(db, review_session)
            ]
        ),
        "reviewers.csv": _csv(serialize_reviewers(db, review_session)),
        "reviewees.csv": _csv(
            list(serialize_reviewees(db, review_session))
            + [
                ("Zed", "zed@example.edu", "", "", "", "", "active"),
            ]
        ),
        "responses.csv": _csv(serialize_responses(db, review_session)),
    }
    outcome = session_rehydrate.rehydrate_session(
        db, files=files, user=user, directory=FakeDirectory()
    )
    rehyd = outcome.session
    assert rehyd.symmetric_review is True
    assert [e.email_or_identifier for e in _reviewees(db, rehyd)] == ["ann@example.edu"]


def test_the_row_editor_never_renders_under_the_mode(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "sym-i-editor")
    reviewers.create_reviewer(
        db, review_session=review_session, name="Ann", email="ann@example.edu", user=_user(db)
    )
    [reviewee] = _reviewees(db, review_session)
    base = f"/operator/sessions/{review_session.public_id}/reviewees"
    for query in (f"?edit_id={reviewee.id}", "?add=1"):
        assert 'id="reviewee-edit-form"' not in client.get(base + query).text, query


def test_a_reviewees_file_is_accepted_when_the_settings_turn_the_mode_off(
    client: TestClient, db: Session
) -> None:
    review_session = _session(client, db, "sym-i-off-settings")
    off = _session(client, db, "sym-i-off-src", on=False)
    settings = _csv(
        [("field", "value", "data_type")]
        + [(r.field, r.value, r.data_type) for r in serialize_session_config(db, off)]
    )
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/quick-setup/submit-all",
        files={
            "reviewees_file": ("e.csv", REVIEWEES_CSV, "text/csv"),
            "settings_file": ("s.csv", settings, "text/csv"),
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(review_session)
    assert review_session.symmetric_review is False


def test_a_symmetric_setup_bundle_round_trips_in_one_submit(
    client: TestClient, db: Session
) -> None:
    """The bundle carries no reviewees, so its relationships are checked
    against the reviewers that will mirror (Codex on #3490)."""
    from app.db.models import Relationship

    source = _session(client, db, "sym-i-bundle-src")
    user = _user(db)
    ann = reviewers.create_reviewer(
        db, review_session=source, name="Ann", email="ann@example.edu", user=user
    )
    reviewers.create_reviewer(
        db, review_session=source, name="Bob", email="bob@example.edu", user=user
    )
    bob_reviewee = next(
        e for e in _reviewees(db, source) if e.email_or_identifier == "bob@example.edu"
    )
    source.relationships_enabled = True
    db.add(Relationship(session_id=source.id, reviewer_id=ann.id, reviewee_id=bob_reviewee.id))
    db.commit()
    data, _counts = zip_bundle.build_setup_bundle(db, source)
    bundle = zipfile.ZipFile(io.BytesIO(data))

    def member(suffix: str) -> bytes:
        [name] = [n for n in bundle.namelist() if n.endswith(suffix)]
        return bundle.read(name)

    target = _session(client, db, "sym-i-bundle-target", on=False)
    response = client.post(
        f"/operator/sessions/{target.public_id}/quick-setup/submit-all",
        files={
            "reviewers_file": ("r.csv", member("_reviewers.csv"), "text/csv"),
            "relationships_file": ("rel.csv", member("_relationships.csv"), "text/csv"),
            "settings_file": ("s.csv", member("_settings.csv"), "text/csv"),
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.expire_all()
    db.refresh(target)
    assert target.symmetric_review is True
    assert len(_reviewees(db, target)) == 2
    assert (
        db.execute(select(Relationship).where(Relationship.session_id == target.id)).scalars().all()
    )


def test_rehydrate_takes_a_symmetric_set_without_reviewees_csv(
    client: TestClient, db: Session
) -> None:
    """The setup bundle carries no reviewees.csv under the mode, so the
    pre-flight neither requires it nor checks the responses' reviewees
    against it (Codex on #3490)."""
    review_session = _session(client, db, "sym-i-rehyd-nofile")
    user = _user(db)
    reviewers.create_reviewer(
        db, review_session=review_session, name="Ann", email="ann@example.edu", user=user
    )
    files = {
        "settings.csv": _csv(
            [("field", "value", "data_type")]
            + [
                (r.field, r.value, r.data_type)
                for r in serialize_session_config(db, review_session)
            ]
        ),
        "reviewers.csv": _csv(serialize_reviewers(db, review_session)),
        "responses.csv": _csv(serialize_responses(db, review_session)),
    }
    report = session_rehydrate.analyze_rehydrate_set(db, files=files, user=user)
    assert report.ok, report.errors
    assert report.preview["reviewees"] == 1
    outcome = session_rehydrate.rehydrate_session(
        db, files=files, user=user, directory=FakeDirectory()
    )
    assert [e.email_or_identifier for e in _reviewees(db, outcome.session)] == ["ann@example.edu"]


def test_rehydrate_still_requires_reviewees_csv_with_the_mode_off(
    client: TestClient, db: Session
) -> None:
    review_session = _session(client, db, "sym-i-rehyd-off", on=False)
    user = _user(db)
    files = {
        "settings.csv": _csv(
            [("field", "value", "data_type")]
            + [
                (r.field, r.value, r.data_type)
                for r in serialize_session_config(db, review_session)
            ]
        ),
        "reviewers.csv": _csv(serialize_reviewers(db, review_session)),
        "responses.csv": _csv(serialize_responses(db, review_session)),
    }
    report = session_rehydrate.analyze_rehydrate_set(db, files=files, user=user)
    assert not report.ok
    assert any("reviewees.csv" in e for e in report.errors)


def test_a_turn_on_committed_after_the_route_gate_still_refuses(
    client: TestClient, db: Session
) -> None:
    """The route reads the flag before the lock; the service re-reads it
    under the lock, so a turn-on committed in between refuses the
    reviewee (Codex on #3490)."""
    import pytest
    from sqlalchemy import update

    from app.services import reviewees as reviewees_service
    from app.services.csv_imports import parse_reviewee_csv, save_reviewees
    from app.services.session_guard import SessionStateConflict

    review_session = _session(client, db, "sym-i-race", on=False)
    user = _user(db)
    # Another request turns the mode on; this one still holds the stale row.
    db.execute(
        update(ReviewSession)
        .where(ReviewSession.id == review_session.id)
        .values(symmetric_review=True)
    )
    db.commit()
    db.expire_all()
    vars(review_session)["symmetric_review"] = False  # the route's stale read
    with pytest.raises(SessionStateConflict):
        reviewees_service.create_reviewee(
            db,
            review_session=review_session,
            name="X",
            email_or_identifier="x@example.edu",
            user=user,
        )
    db.rollback()
    with pytest.raises(SessionStateConflict):
        save_reviewees(
            db,
            session=review_session,
            user=user,
            rows=parse_reviewee_csv(REVIEWEES_CSV).rows,
            filename="e.csv",
            correlation_id="",
        )
    db.rollback()
    assert _reviewees(db, review_session) == []


def test_a_relationships_upload_is_checked_against_the_mirroring_reviewers(
    client: TestClient, db: Session
) -> None:
    from app.services import relationships as relationships_service
    from app.services.csv_imports import parse_reviewer_csv

    review_session = _session(client, db, "sym-i-rel-svc", on=False)
    incoming = parse_reviewer_csv(REVIEWERS_CSV).rows
    content = (
        b"ReviewerEmail,RevieweeEmail\nann@example.edu,bob@example.edu\n"
        b"ann@example.edu,zed@example.edu\n"
    )
    result = relationships_service.parse_relationship_upload(
        db, review_session.id, content, incoming_reviewers=incoming, symmetric=True
    )
    problems = [i.problem for i in result.issues if i.severity == "error"]
    # Bob is a reviewer, so he is a reviewee; Zed is neither.
    assert problems == ["RevieweeEmail is not in the uploaded Reviewers file (symmetric review)"]
    off = relationships_service.parse_relationship_upload(
        db, review_session.id, content, incoming_reviewers=incoming, symmetric=False
    )
    assert len([i for i in off.issues if i.severity == "error"]) == 2


def test_the_reviewees_download_misses_under_the_mode(client: TestClient, db: Session) -> None:
    """Only the Reviewers roster is exported under symmetric review
    (author, 2026-11-02); with the mode off the download still works."""
    on = _session(client, db, "sym-i-dl-on")
    off = _session(client, db, "sym-i-dl-off", on=False)
    assert client.get(f"/operator/sessions/{on.public_id}/export/reviewees.csv").status_code == 404
    assert client.get(f"/operator/sessions/{off.public_id}/export/reviewees.csv").status_code == 200


def _bundle_files(db: Session, source: ReviewSession) -> dict[str, tuple[str, bytes, str]]:
    data, _counts = zip_bundle.build_setup_bundle(db, source)
    bundle = zipfile.ZipFile(io.BytesIO(data))

    def member(suffix: str) -> bytes:
        [name] = [n for n in bundle.namelist() if n.endswith(suffix)]
        return bundle.read(name)

    return {
        "reviewers_file": ("r.csv", member("_reviewers.csv"), "text/csv"),
        "settings_file": ("s.csv", member("_settings.csv"), "text/csv"),
    }


def test_a_symmetric_bundle_into_a_session_with_rows_says_its_reviewees_stay(
    client: TestClient, db: Session
) -> None:
    """Findings register L3 (author, 2026-11-03: a notice). The bundle
    carries no reviewees, and symmetric review stays off beside the
    target's roster rows, so its reviewees are left as they were: the
    page says so."""
    source = _session(client, db, "sym-i-l3-src")
    user = _user(db)
    reviewers.create_reviewer(
        db, review_session=source, name="Ann", email="ann@example.edu", user=user
    )
    db.commit()

    target = _session(client, db, "sym-i-l3-target", on=False)
    reviewers.create_reviewer(
        db, review_session=target, name="Kim", email="kim@example.edu", user=user
    )
    db.add(Reviewee(session_id=target.id, name="Lee", email_or_identifier="lee@example.edu"))
    db.commit()

    response = client.post(
        f"/operator/sessions/{target.public_id}/quick-setup/submit-all",
        files=_bundle_files(db, source),
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert "quick_setup_notice=kept_reviewees" in response.headers["location"]
    db.expire_all()
    db.refresh(target)
    assert target.symmetric_review is False
    assert [r.email_or_identifier for r in _reviewees(db, target)] == ["lee@example.edu"]
    page = client.get(response.headers["location"].split("#")[0]).text
    assert "data-quick-setup-kept-reviewees" in page
    assert "reviewees were left as they were" in page
    # It scrolls into view and Dismiss drops the code (spec/ui_elements.md §5a).
    assert "banner-scroll-target" in page.split('id="quick-setup-kept-reviewees-banner"')[0][-200:]
    assert f'href="/operator/sessions/{target.public_id}#quick-setup"' in page


def test_a_symmetric_bundle_into_an_empty_session_says_nothing(
    client: TestClient, db: Session
) -> None:
    source = _session(client, db, "sym-i-l3e-src")
    reviewers.create_reviewer(
        db, review_session=source, name="Ann", email="ann@example.edu", user=_user(db)
    )
    db.commit()
    target = _session(client, db, "sym-i-l3e-target", on=False)
    response = client.post(
        f"/operator/sessions/{target.public_id}/quick-setup/submit-all",
        files=_bundle_files(db, source),
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert "quick_setup_notice" not in response.headers["location"]
    page = client.get(f"/operator/sessions/{target.public_id}").text
    assert "data-quick-setup-kept-reviewees" not in page


def test_a_symmetric_bundle_with_a_reviewees_file_says_nothing(
    client: TestClient, db: Session
) -> None:
    """A Reviewees file in the same submit saves, so nothing was left."""
    source = _session(client, db, "sym-i-l3r-src")
    user = _user(db)
    reviewers.create_reviewer(
        db, review_session=source, name="Ann", email="ann@example.edu", user=user
    )
    db.commit()
    target = _session(client, db, "sym-i-l3r-target", on=False)
    reviewers.create_reviewer(
        db, review_session=target, name="Kim", email="kim@example.edu", user=user
    )
    db.commit()
    files = _bundle_files(db, source)
    files["reviewees_file"] = (
        "e.csv",
        b"RevieweeName,RevieweeEmail\nLee,lee@example.edu\n",
        "text/csv",
    )
    response = client.post(
        f"/operator/sessions/{target.public_id}/quick-setup/submit-all",
        files=files,
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert "quick_setup_notice" not in response.headers["location"]


def test_a_symmetric_bundle_into_a_symmetric_session_says_nothing(
    client: TestClient, db: Session
) -> None:
    """The mode is already on, so the bundle's reviewers mirror."""
    source = _session(client, db, "sym-i-l3s-src")
    user = _user(db)
    reviewers.create_reviewer(
        db, review_session=source, name="Ann", email="ann@example.edu", user=user
    )
    db.commit()
    target = _session(client, db, "sym-i-l3s-target")
    reviewers.create_reviewer(
        db, review_session=target, name="Kim", email="kim@example.edu", user=user
    )
    db.commit()
    response = client.post(
        f"/operator/sessions/{target.public_id}/quick-setup/submit-all",
        files=_bundle_files(db, source),
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert "quick_setup_notice" not in response.headers["location"]


def test_an_unknown_notice_code_shows_nothing(client: TestClient, db: Session) -> None:
    target = _session(client, db, "sym-i-l3u", on=False)
    page = client.get(f"/operator/sessions/{target.public_id}?quick_setup_notice=anything").text
    assert "data-quick-setup-kept-reviewees" not in page
