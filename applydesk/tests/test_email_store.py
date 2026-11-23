"""Emails in the database (segment AD2L rung 3, `applydesk/email_store.py`):
Process's ticks recorded whole, retired and revived; one card's template
kept, its version guarding a save from an older page; a template Process
no longer owes, or too long, refused; each save audited."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from applydesk import db, email_store, panels_store
from applydesk.email_store import Refused
from applydesk.models import AuditEvent, EmailSend

MODEL = "wa9juxbc2t"
RECEIPT = ("receipt", "Applicants")
O1 = ("o1", "Applicants")


@pytest.fixture
def session() -> Iterator[Session]:
    s = db.new_session()
    yield s
    s.close()


def _save(session: Session, pair: tuple[str, str], subject: str, body: str, opened: int) -> int:
    got = email_store.save_template(
        session, MODEL, pair, subject, body, opened, None, owed=lambda: True
    )
    session.commit()
    return got


def test_no_ticks_are_recorded_until_process_saves_them(session: Session) -> None:
    assert email_store.sends(session, MODEL) is None
    assert email_store.templates(session, MODEL) == {}


def test_ticks_are_recorded_whole_retired_and_revived(session: Session) -> None:
    assert email_store.save_sends(session, MODEL, {RECEIPT, O1}) == 2
    session.commit()
    assert email_store.stored_sends(MODEL) == {RECEIPT, O1}
    email_store.save_sends(session, MODEL, {RECEIPT})
    session.commit()
    assert email_store.sends(session, MODEL) == {RECEIPT}
    retired = session.scalars(select(EmailSend).where(EmailSend.item == "o1")).one()
    assert retired.retired_at is not None
    email_store.save_sends(session, MODEL, {RECEIPT, O1})
    session.commit()
    assert email_store.sends(session, MODEL) == {RECEIPT, O1}
    assert session.scalar(select(func.count()).select_from(EmailSend)) == 2  # revived, not added
    # Nothing ticked is recorded too: an exercise that sends no email.
    email_store.save_sends(session, MODEL, ())
    session.commit()
    assert email_store.sends(session, MODEL) == frozenset()


def test_a_template_is_kept_and_its_version_counts_its_saves(session: Session) -> None:
    assert _save(session, RECEIPT, "Thanks", "Dear $applicant_name,", 0) == 1
    kept = email_store.stored_templates(MODEL)[RECEIPT]
    assert (kept.subject, kept.body, kept.version, kept.written) == (
        "Thanks",
        "Dear $applicant_name,",
        1,
        True,
    )
    assert _save(session, RECEIPT, "", "", 1) == 2  # kept as owed
    assert email_store.stored_templates(MODEL)[RECEIPT].written is False
    event = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.event_type == "exercise.email_saved")
        .order_by(AuditEvent.id)
    ).all()
    assert [e.detail["context"]["version"] for e in event] == [1, 2]
    assert event[0].detail["context"]["item"] == "receipt"


def test_a_card_opened_before_another_save_is_refused_but_not_another_card(
    session: Session,
) -> None:
    _save(session, RECEIPT, "A", "B", 0)
    with pytest.raises(Refused) as why:
        email_store.save_template(session, MODEL, RECEIPT, "C", "D", 0, None, owed=lambda: True)
    assert why.value.key == "stale"
    session.rollback()
    assert _save(session, O1, "E", "F", 0) == 1  # another card's own version


def test_an_email_process_no_longer_owes_is_refused_under_the_lock(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    real = panels_store.lock
    monkeypatch.setattr(panels_store, "lock", lambda s, p: (seen.append("lock"), real(s, p))[1])

    def owed() -> bool:
        seen.append("owed")
        return False

    with pytest.raises(Refused) as why:
        email_store.save_template(session, MODEL, O1, "A", "B", 0, None, owed=owed)
    assert why.value.key == "not_owed" and seen == ["lock", "owed"]


def test_too_long_a_template_is_refused(session: Session) -> None:
    with pytest.raises(Refused, match="at most 300"):
        email_store.save_template(
            session, MODEL, RECEIPT, "x" * 301, "", 0, None, owed=lambda: True
        )
    with pytest.raises(Refused, match="20,000"):
        email_store.save_template(
            session, MODEL, RECEIPT, "", "x" * 20001, 0, None, owed=lambda: True
        )


def test_a_sample_s_card_saves_and_the_page_and_status_follow() -> None:
    """Rung 4: Emails saves for every exercise, a sample's included; its
    other cards keep the sample's, and its ticks Process's once recorded."""
    from fastapi.testclient import TestClient

    from applydesk import workflow
    from applydesk.tests._host import host_with

    client = TestClient(host_with(("applydesk",))[0])
    page = f"/applydesk/operator/exercises/{MODEL}/emails"
    text = client.get(page).text
    assert "data-em-save=" in text and "Placeholder." not in text
    owed = next(e for e in workflow.emails(MODEL) if not e.ok)
    card = {
        "item": owed.item,
        "audience": owed.audience,
        "name": owed.name,
        "revision": workflow.process_revision(MODEL),
        "version": 0,
        "subject": "$exercise_name: news",
        "body": "Dear $applicant_name,",
    }
    reply = client.post(page, json=card)
    assert reply.status_code == 200 and reply.json()["version"] == 1, reply.text
    assert next(e for e in workflow.emails(MODEL) if e.name == owed.name).ok
    assert 'value="$exercise_name: news"' in client.get(page).text
    # A second tab still at version 0 is refused, not overwriting it.
    stale = client.post(page, json={**card, "subject": "Other"})
    assert stale.status_code == 409
    # The sample's other written cards keep their default.
    written = next(e for e in workflow.emails(MODEL) if e.ok and e.name != owed.name)
    assert workflow.template_text(MODEL, written) == workflow.DEFAULT_TEMPLATES[written.kind]


def test_recorded_ticks_replace_the_sample_s(session: Session) -> None:
    from applydesk import workflow

    assert workflow.sends(MODEL, "o2", "Evaluators")  # the sample's
    email_store.save_sends(session, MODEL, {RECEIPT})
    session.commit()
    assert not workflow.sends(MODEL, "o2", "Evaluators")
    assert [e.item for e in workflow.emails(MODEL)] == ["receipt"]
