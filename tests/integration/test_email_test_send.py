"""Send a test to me (segment 14F rung 2b, `app/services/email_test_send.py`).

- The template as edited, saved or not, goes to the signed-in operator
  only, marked "[Test]", with merge tags from the roster's first reviewer
  (a stand-in while the roster is empty) and a placeholder link.
- Nothing is saved, no outbox row is written, and `email.test_sent`
  records the outcome.
- A refused send, or no Microsoft token, comes back as a failure line
  naming why.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, EmailOutbox, Reviewer, ReviewSession
from app.services import email_test_send
from app.web.routes_operator import _setup_invite
from cordware.graph import FakeMailer, GraphError, MailMessage


class Refusing:
    def __init__(self, kind: str) -> None:
        self.kind = kind

    def send_mail(self, message: MailMessage) -> None:
        raise GraphError(self.kind)


def _session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions", data={"name": f"Sess {code}", "code": code}, follow_redirects=False
    )
    assert response.status_code == 303, response.text
    return db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()


@pytest.fixture
def mailer(monkeypatch: pytest.MonkeyPatch) -> FakeMailer:
    fake = FakeMailer()
    monkeypatch.setattr(_setup_invite.graph, "mailer_for", lambda _request: fake)
    return fake


def _send(client: TestClient, rs: ReviewSession, **fields: str):
    return client.post(
        f"/operator/sessions/{rs.public_id}/setup-invite/send-test",
        data={"template": "invitation", **fields},
        follow_redirects=False,
    )


def _events(db: Session, rs: ReviewSession) -> list[AuditEvent]:
    stmt = select(AuditEvent).where(
        AuditEvent.session_id == rs.id, AuditEvent.event_type == "email.test_sent"
    )
    return list(db.execute(stmt).scalars())


def test_the_edited_unsaved_template_goes_to_the_operator(
    client: TestClient, db: Session, mailer: FakeMailer
) -> None:
    rs = _session(client, db, "TEST1")
    db.add(Reviewer(session_id=rs.id, name="Ada First", email="ada@example.edu"))
    db.commit()

    response = _send(
        client, rs, subject="Hi $reviewer_name", body="Open $invite_url, $reviewer_name"
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("template=invitation&test=sent")

    [sent] = mailer.sent
    db.refresh(rs)
    operator_email = rs.created_by_user.email
    assert sent.to == operator_email
    assert sent.subject == "[Test] Hi Ada First"
    assert sent.body.startswith(f"Open {email_test_send.SAMPLE_INVITE_URL}, Ada First")
    assert (sent.cc, sent.bcc) == ((), ())

    db.refresh(rs)
    assert not (rs.email_template_overrides or {}).get("invitation_subject")  # nothing saved
    assert db.execute(select(func.count()).select_from(EmailOutbox)).scalar() == 0
    [event] = _events(db, rs)
    assert event.detail is not None and event.detail["context"]["outcome"] == "sent"

    page = client.get(response.headers["location"]).text
    assert f"Test sent to {operator_email}." in page


def test_an_empty_roster_fills_tags_from_a_stand_in(
    client: TestClient, db: Session, mailer: FakeMailer
) -> None:
    rs = _session(client, db, "TEST2")
    _send(client, rs, subject="For $reviewer_name", body="b")
    assert mailer.sent[0].subject == f"[Test] For {email_test_send.SAMPLE_REVIEWER_NAME}"


def test_a_blank_field_tests_the_default(
    client: TestClient, db: Session, mailer: FakeMailer
) -> None:
    rs = _session(client, db, "TEST3")
    _send(client, rs, subject="", body="")
    [sent] = mailer.sent
    assert sent.subject.startswith("[Test] ") and len(sent.subject) > len("[Test] ")
    assert email_test_send.SAMPLE_INVITE_URL in sent.body


@pytest.mark.parametrize("template", ["reminder", "responses_received"])
def test_the_other_templates_send_too(
    client: TestClient, db: Session, mailer: FakeMailer, template: str
) -> None:
    rs = _session(client, db, f"T-{template[:4]}")
    response = client.post(
        f"/operator/sessions/{rs.public_id}/setup-invite/send-test",
        data={"template": template, "subject": "S $session_name", "body": "B"},
        follow_redirects=False,
    )
    assert response.headers["location"].endswith(f"template={template}&test=sent")
    assert mailer.sent[0].subject == f"[Test] S {rs.name}"


@pytest.mark.parametrize("kind", ["forbidden", "no_token"])
def test_a_failed_test_says_why(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    def build(_request: object) -> Refusing:
        if kind == "no_token":
            raise GraphError("no_token")
        return Refusing(kind)

    monkeypatch.setattr(_setup_invite.graph, "mailer_for", build)
    rs = _session(client, db, f"TF-{kind[:4]}")
    response = _send(client, rs, subject="s", body="b")
    assert response.headers["location"].endswith(f"test=failed&kind={kind}")
    page = client.get(response.headers["location"]).text
    assert "The test was not sent." in page
    [event] = _events(db, rs)
    assert event.detail is not None and event.detail["context"]["outcome"] == "failed"


def test_an_unknown_template_is_refused(
    client: TestClient, db: Session, mailer: FakeMailer
) -> None:
    rs = _session(client, db, "TEST9")
    response = client.post(
        f"/operator/sessions/{rs.public_id}/setup-invite/send-test",
        data={"template": "nope"},
        follow_redirects=False,
    )
    assert response.status_code == 404
    assert mailer.sent == []
