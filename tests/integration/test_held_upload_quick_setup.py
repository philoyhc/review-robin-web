"""Segment 19W rung 4 — Quick Setup on Session Home holds a refused
submit's files when the refusal asks a question, so the tick and Submit
are the whole answer; a save, any other refusal and Dismiss end the
hold."""
from __future__ import annotations

import pathlib
import re

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import HeldUpload, Instrument, Reviewee, Reviewer, ReviewSession

CHECKLIST = (
    pathlib.Path(__file__).resolve().parents[2] / "guide/browser_check_files/checklist"
)
REVIEWERS = b"ReviewerName,ReviewerEmail\nAnn,ann@example.edu\n"
REVIEWERS_2 = b"ReviewerName,ReviewerEmail\nBea,bea@example.edu\n"
REVIEWEES = b"RevieweeName,RevieweeEmail\nCy,cy@example.edu\n"


def _session(client: TestClient, db: Session, code: str) -> ReviewSession:
    r = client.post(
        "/operator/sessions", data={"name": "S", "code": code},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _submit(client: TestClient, s: ReviewSession, files: dict[str, tuple], **data):
    return client.post(
        f"/operator/sessions/{s.public_id}/quick-setup/submit-all",
        files={
            f"{slot}_file": (name, content, "text/csv")
            for slot, (name, content) in files.items()
        } or None,
        data=data,
        follow_redirects=False,
    )


def _token(body: str) -> str:
    match = re.search(r'name="held_token" value="([^"]+)"', body)
    assert match is not None, "no held token in the card"
    return match.group(1)


def _held(db: Session) -> int:
    db.expire_all()
    return db.execute(select(func.count()).select_from(HeldUpload)).scalar_one()


def _checklist(name: str) -> tuple[str, bytes]:
    return name, (CHECKLIST / name).read_bytes()


def test_the_deletion_ask_holds_the_settings_file(
    client: TestClient, db: Session
) -> None:
    s = _session(client, db, "qs-held-s4")
    applied = _submit(
        client, s, {"settings": _checklist("05_settings.csv")},
        confirm_replace="true",
    )
    assert applied.status_code == 303, applied.text[:300]

    asked = _submit(
        client, s, {"settings": _checklist("09_settings_one_instrument.csv")},
        confirm_replace="true",
    )
    assert asked.status_code == 422
    assert 'data-quick-setup-reason="deletes_instruments"' in asked.text
    assert "Holding <strong>09_settings_one_instrument.csv</strong>" in asked.text
    assert "Choose the file" not in asked.text
    assert re.search(
        r'id="quick-setup-confirm-replace-toggle"[^>]*\bchecked\b', asked.text
    )
    assert _held(db) == 1

    answered = _submit(
        client, s, {}, held_token=_token(asked.text),
        confirm_replace="true", acknowledge_instrument_deletion="1",
    )
    assert answered.status_code == 303, answered.text[:300]
    db.expire_all()
    names = [
        i.name
        for i in db.execute(
            select(Instrument).where(Instrument.session_id == s.id)
        ).scalars()
    ]
    assert names == ["Team review"]
    assert _held(db) == 0


def test_a_missing_tick_holds_every_file_of_the_submit(
    client: TestClient, db: Session
) -> None:
    s = _session(client, db, "qs-held-two")
    _submit(client, s, {"reviewers": ("r.csv", REVIEWERS)}, confirm_replace="true")

    asked = _submit(
        client, s,
        {"reviewers": ("r2.csv", REVIEWERS_2), "reviewees": ("e.csv", REVIEWEES)},
    )
    assert asked.status_code == 422
    assert 'data-quick-setup-reason="needs_confirm"' in asked.text
    assert "Holding <strong>r2.csv</strong>" in asked.text
    assert "Holding <strong>e.csv</strong>" in asked.text
    # A missing-tick ask leaves the replace tick to the operator.
    assert re.search(
        r'id="quick-setup-confirm-replace-toggle"[^>]*\bchecked\b', asked.text
    ) is None
    assert _held(db) == 2

    answered = _submit(
        client, s, {}, held_token=_token(asked.text), confirm_replace="true"
    )
    assert answered.status_code == 303, answered.text[:300]
    db.expire_all()
    assert [r.name for r in db.execute(
        select(Reviewer).where(Reviewer.session_id == s.id)
    ).scalars()] == ["Bea"]
    assert [r.name for r in db.execute(
        select(Reviewee).where(Reviewee.session_id == s.id)
    ).scalars()] == ["Cy"]
    assert _held(db) == 0


def test_another_refusal_ends_the_hold(client: TestClient, db: Session) -> None:
    s = _session(client, db, "qs-held-bad")
    _submit(client, s, {"reviewers": ("r.csv", REVIEWERS)}, confirm_replace="true")
    asked = _submit(client, s, {"reviewers": ("r2.csv", REVIEWERS_2)})

    refused = _submit(
        client, s, {"reviewers": ("bad.csv", b"Nothing,Useful\n1,2\n")},
        held_token=_token(asked.text), confirm_replace="true",
    )
    assert refused.status_code == 422
    assert 'name="held_token"' not in refused.text
    assert _held(db) == 0


def test_dismiss_ends_the_hold(client: TestClient, db: Session) -> None:
    s = _session(client, db, "qs-held-dismiss")
    _submit(client, s, {"reviewers": ("r.csv", REVIEWERS)}, confirm_replace="true")
    asked = _submit(client, s, {"reviewers": ("r2.csv", REVIEWERS_2)})
    url = f"/operator/sessions/{s.public_id}/quick-setup/dismiss"
    assert f'formaction="{url}"' in asked.text

    dismissed = client.post(
        url, data={"held_token": _token(asked.text)}, follow_redirects=False
    )
    assert dismissed.status_code == 303
    assert dismissed.headers["location"] == (
        f"/operator/sessions/{s.public_id}#quick-setup"
    )
    assert _held(db) == 0


def test_a_lapsed_hold_saves_nothing_and_says_so(
    client: TestClient, db: Session
) -> None:
    s = _session(client, db, "qs-held-lapsed")
    _submit(client, s, {"reviewers": ("r.csv", REVIEWERS)}, confirm_replace="true")
    asked = _submit(client, s, {"reviewers": ("r2.csv", REVIEWERS_2)})
    token = _token(asked.text)
    db.execute(HeldUpload.__table__.delete())
    db.commit()

    tried = _submit(
        client, s, {"reviewees": ("e.csv", REVIEWEES)},
        held_token=token, confirm_replace="true",
    )
    assert tried.status_code == 422
    assert "data-quick-setup-held-lost" in tried.text
    db.expire_all()
    assert [r.name for r in db.execute(
        select(Reviewer).where(Reviewer.session_id == s.id)
    ).scalars()] == ["Ann"]
    assert db.execute(
        select(func.count()).select_from(Reviewee).where(Reviewee.session_id == s.id)
    ).scalar_one() == 0


def test_a_new_file_replaces_only_its_slot_of_the_hold(
    client: TestClient, db: Session
) -> None:
    s = _session(client, db, "qs-held-swap")
    _submit(client, s, {"reviewers": ("r.csv", REVIEWERS)}, confirm_replace="true")
    asked = _submit(
        client, s,
        {"reviewers": ("r2.csv", REVIEWERS_2), "reviewees": ("e.csv", REVIEWEES)},
    )
    newer = b"ReviewerName,ReviewerEmail\nDot,dot@example.edu\n"
    answered = _submit(
        client, s, {"reviewers": ("r3.csv", newer)},
        held_token=_token(asked.text), confirm_replace="true",
    )
    assert answered.status_code == 303, answered.text[:300]
    db.expire_all()
    assert [r.name for r in db.execute(
        select(Reviewer).where(Reviewer.session_id == s.id)
    ).scalars()] == ["Dot"]
    assert [r.name for r in db.execute(
        select(Reviewee).where(Reviewee.session_id == s.id)
    ).scalars()] == ["Cy"]
    assert _held(db) == 0
