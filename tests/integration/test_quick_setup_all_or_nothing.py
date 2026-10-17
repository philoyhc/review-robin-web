"""Quick Setup checks every attached file, then saves them all or none.

``guide/quick_setup_update.md`` Item 1, rung 3 (author's rule,
2026-10-12): roster files uploaded together are checked against each
other and against the rosters they do not replace, and a refusal
anywhere leaves the session as it was. Before this, each slot committed
before the next slot's file was read, so a rename across rosters could
not be uploaded at all and a late refusal left a half-applied setup.
"""

from __future__ import annotations

import csv
import io
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionTag,
)
from app.services import csv_imports
from app.services import session_lifecycle as lifecycle

from ._quick_setup_refusal import refusal


BOB = "bob@example.edu"


def _session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _reviewers(*rows: tuple[str, str]) -> bytes:
    return ("ReviewerName,ReviewerEmail\n" + "".join(
        f"{name},{email}\n" for name, email in rows
    )).encode()


def _reviewees(*rows: tuple[str, str]) -> bytes:
    return ("RevieweeName,RevieweeEmail\n" + "".join(
        f"{name},{email}\n" for name, email in rows
    )).encode()


def _relationships(*pairs: tuple[str, str]) -> bytes:
    return ("ReviewerEmail,RevieweeEmail\n" + "".join(
        f"{reviewer},{reviewee}\n" for reviewer, reviewee in pairs
    )).encode()


def _bad_settings() -> bytes:
    """Parses, then fails ``apply_session_config``: an instrument with
    no name is a cross-row error only the apply finds."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(("field", "value", "data_type"))
    writer.writerow(("instruments[1].short_label", "X", "string"))
    return buf.getvalue().encode()


def _submit_all(client: TestClient, rs: ReviewSession, **files: bytes):
    return client.post(
        f"/operator/sessions/{rs.id}/quick-setup/submit-all",
        data={"confirm_replace": "true"},
        files={
            f"{kind}_file": (f"{kind}.csv", payload, "text/csv")
            for kind, payload in files.items()
        },
        follow_redirects=False,
    )


def _query(response) -> dict[str, list[str]]:
    """The refusal as the old redirect query spelled it. An existing
    session's refusal renders Home at 422 and is read off the banner
    (findings O7); Create's, and every success, still redirect."""
    if response.status_code == 422:
        refused = refusal(response)
        return {
            "quick_setup_error": [refused.kind],
            "quick_setup_reason": [refused.reason],
            "quick_setup_detail": refused.details,
        }
    assert response.status_code == 303, response.status_code
    return parse_qs(urlsplit(response.headers["location"]).query)


def _names(db: Session, model, rs: ReviewSession) -> list[str]:
    db.expire_all()
    return sorted(
        row.name
        for row in db.execute(
            select(model).where(model.session_id == rs.id)
        ).scalars()
    )


def _seed_bob(db: Session, rs: ReviewSession, name: str = "Bob Smith") -> None:
    db.add_all(
        [
            Reviewer(session_id=rs.id, name=name, email=BOB),
            Reviewee(session_id=rs.id, name=name, email_or_identifier=BOB),
        ]
    )
    db.commit()  # a savepoint the app's rollback cannot undo


def test_a_rename_across_both_rosters_lands_when_uploaded_together(
    client: TestClient, db: Session
) -> None:
    """The case the item exists for."""
    rs = _session(client, db, "aon-rename")
    _seed_bob(db, rs)

    response = _submit_all(
        client,
        rs,
        reviewers=_reviewers(("Robert Smith", BOB)),
        reviewees=_reviewees(("Robert Smith", BOB)),
    )

    assert response.status_code == 303
    assert "quick_setup_error" not in _query(response)
    assert _names(db, Reviewer, rs) == ["Robert Smith"]
    assert _names(db, Reviewee, rs) == ["Robert Smith"]


def test_the_same_rename_on_one_roster_alone_is_still_refused(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "aon-alone")
    _seed_bob(db, rs)

    response = client.post(
        f"/operator/sessions/{rs.id}/quick-setup/reviewers",
        data={"confirm_replace": "true"},
        files={"file": ("r.csv", _reviewers(("Robert Smith", BOB)), "text/csv")},
        follow_redirects=False,
    )

    assert _query(response)["quick_setup_error"] == ["reviewers"]
    assert _names(db, Reviewer, rs) == ["Bob Smith"]


def test_two_uploads_that_disagree_are_refused_naming_the_other_file(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "aon-clash")

    response = _submit_all(
        client,
        rs,
        reviewers=_reviewers(("Robert Smith", BOB)),
        reviewees=_reviewees(("Bob Smith", BOB)),
    )

    query = _query(response)
    assert query["quick_setup_error"] == ["reviewers"]
    assert query["quick_setup_detail"] == [
        "ReviewerEmail is used under a different name in the uploaded "
        "Reviewees file (1 row)"
    ]
    assert _names(db, Reviewer, rs) == []
    assert _names(db, Reviewee, rs) == []


def test_a_later_refusal_leaves_the_earlier_slots_unsaved(
    client: TestClient, db: Session
) -> None:
    """Reviewers passes and Reviewees does not: the reviewers already on
    the roster stay, and the new file is not half-applied."""
    rs = _session(client, db, "aon-later")
    db.add(Reviewer(session_id=rs.id, name="Old", email="old@example.edu"))
    db.commit()  # a savepoint the app's rollback cannot undo

    response = _submit_all(
        client,
        rs,
        reviewers=_reviewers(("New", "new@example.edu")),
        reviewees=b"RevieweeName,RevieweeEmail\nCy,\n",
    )

    assert _query(response)["quick_setup_error"] == ["reviewees"]
    assert _names(db, Reviewer, rs) == ["Old"]


def test_a_settings_apply_failure_rolls_the_rosters_back(
    client: TestClient, db: Session
) -> None:
    """Settings applies last, inside the unit; an error only the apply
    finds undoes the rosters saved before it."""
    rs = _session(client, db, "aon-settings")
    db.add(Reviewer(session_id=rs.id, name="Old", email="old@example.edu"))
    db.commit()  # a savepoint the app's rollback cannot undo

    response = _submit_all(
        client,
        rs,
        reviewers=_reviewers(("New", "new@example.edu")),
        settings=_bad_settings(),
    )

    query = _query(response)
    assert query["quick_setup_error"] == ["settings"]
    assert query["quick_setup_reason"] == ["parse"]
    assert _names(db, Reviewer, rs) == ["Old"]


def test_a_lifecycle_race_rolls_every_slot_back(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A session that went ``ready`` between the checks and the saves:
    the Reviewees save refuses under its lock, and the Reviewers save
    before it is rolled back with it."""
    rs = _session(client, db, "aon-race")

    def refused(*args, **kwargs):
        raise lifecycle.SessionStateConflict("Session is ready")

    monkeypatch.setattr(csv_imports, "save_reviewees", refused)

    response = _submit_all(
        client,
        rs,
        reviewers=_reviewers(("Al", "al@example.edu")),
        reviewees=_reviewees(("Cy", "cy@example.edu")),
    )

    query = _query(response)
    assert query["quick_setup_error"] == ["reviewees"]
    assert query["quick_setup_reason"] == ["lifecycle"]
    assert _names(db, Reviewer, rs) == []


def test_relationships_uploaded_with_reviewers_resolve_to_the_new_rows(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "aon-rel")

    response = _submit_all(
        client,
        rs,
        reviewers=_reviewers(("Al", "al@example.edu")),
        reviewees=_reviewees(("Cy", "cy@example.edu")),
        relationships=_relationships(("al@example.edu", "cy@example.edu")),
    )

    assert "quick_setup_error" not in _query(response)
    db.expire_all()
    (relationship,) = db.execute(
        select(Relationship).where(Relationship.session_id == rs.id)
    ).scalars()
    assert db.get(Reviewer, relationship.reviewer_id).email == "al@example.edu"
    assert db.get(Reviewee, relationship.reviewee_id).name == "Cy"


def test_relationships_naming_a_reviewer_missing_from_the_upload_refuse(
    client: TestClient, db: Session
) -> None:
    """The reviewer is on the roster being replaced, not in the new file."""
    rs = _session(client, db, "aon-rel-missing")
    db.add_all(
        [
            Reviewer(session_id=rs.id, name="Old", email="old@example.edu"),
            Reviewee(session_id=rs.id, name="Cy", email_or_identifier="cy@example.edu"),
        ]
    )
    db.commit()  # a savepoint the app's rollback cannot undo

    response = _submit_all(
        client,
        rs,
        reviewers=_reviewers(("New", "new@example.edu")),
        relationships=_relationships(("old@example.edu", "cy@example.edu")),
    )

    query = _query(response)
    assert query["quick_setup_error"] == ["relationships"]
    assert query["quick_setup_detail"] == [
        "ReviewerEmail is not in the uploaded Reviewers file (1 row)"
    ]
    assert _names(db, Reviewer, rs) == ["Old"]


def test_create_keeps_its_session_tags_and_saves_no_upload_on_a_refusal(
    client: TestClient, db: Session
) -> None:
    """Create's staged files are all or nothing too; the session row and
    the typed tags survive the refusal, as before."""
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": "aon-create", "tags": "typed"},
        files={
            "reviewers_file": ("r.csv", _reviewers(("Al", "al@example.edu")), "text/csv"),
            "reviewees_file": ("e.csv", b"RevieweeName,RevieweeEmail\nCy,\n", "text/csv"),
        },
        follow_redirects=False,
    )

    assert _query(response)["quick_setup_error"] == ["reviewees"]
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == "aon-create")
    ).scalar_one()
    assert _names(db, Reviewer, rs) == []
    tags = db.execute(
        select(SessionTag).where(SessionTag.session_id == rs.id)
    ).scalars()
    assert [tag.tag for tag in tags] == ["typed"]


def test_a_blocked_file_is_the_refusal_reported_not_its_old_roster(
    client: TestClient, db: Session
) -> None:
    """The Reviewees file is blocked (no ``RevieweeName`` column) but its
    roster is still being replaced: its old "Bob Smith" must not refuse
    the correct Reviewers file ahead of it (cold read on rung 3)."""
    rs = _session(client, db, "aon-blocked")
    _seed_bob(db, rs)

    response = _submit_all(
        client,
        rs,
        reviewers=_reviewers(("Robert Smith", BOB)),
        reviewees=f"RevieweeEmail\n{BOB}\n".encode(),
    )

    query = _query(response)
    assert query["quick_setup_error"] == ["reviewees"]
    assert query["quick_setup_detail"] == [
        "Missing required column: RevieweeName"
    ]
    assert _names(db, Reviewer, rs) == ["Bob Smith"]


def test_create_survives_a_refusal_found_inside_the_save(
    client: TestClient, db: Session
) -> None:
    """A Settings error only the apply finds rolls the unit back before
    Create writes its tags, which must still land."""
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": "aon-create-apply", "tags": "typed"},
        files={
            "reviewers_file": ("r.csv", _reviewers(("Al", "al@example.edu")), "text/csv"),
            "settings_file": ("s.csv", _bad_settings(), "text/csv"),
        },
        follow_redirects=False,
    )

    assert _query(response)["quick_setup_error"] == ["settings"]
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == "aon-create-apply")
    ).scalar_one()
    assert _names(db, Reviewer, rs) == []
    tags = db.execute(
        select(SessionTag).where(SessionTag.session_id == rs.id)
    ).scalars()
    assert [tag.tag for tag in tags] == ["typed"]
