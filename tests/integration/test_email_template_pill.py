"""Session Home's Email Template pill reads *Default* until a template
carries an override, *Customized* after, and is neutral either way, since a
session always has usable email from the defaults (findings 2026-11-20, E1).
The Validate page's coverage row reads the same predicate,
``email_templates.is_customized``."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def _session(client: TestClient, db: Session) -> ReviewSession:
    client.post("/operator/sessions", data={"name": "Pill", "code": "pill-e1"})
    return db.scalars(select(ReviewSession).where(ReviewSession.code == "pill-e1")).one()


def _pill(client: TestClient, rs: ReviewSession) -> str:
    body = client.get(f"/operator/sessions/{rs.public_id}").text
    return body.split("Email Template:", 1)[1].split("&middot;", 1)[0]


def _validate_row(client: TestClient, rs: ReviewSession) -> str:
    body = client.get(f"/operator/sessions/{rs.public_id}/validate").text
    if "Default (no overrides)" in body:
        return "default"
    assert "Custom overrides" in body
    return "customized"


def _assert_neutral(pill: str, state: str) -> None:
    label = {"default": "Default", "customized": "Customized"}[state]
    assert f'<span class="pill pill-info" data-email-template-pill="{state}">{label}</span>' in pill
    for amber in ("pill-empty", "pill-warning", "pill-error"):
        assert amber not in pill


@pytest.mark.parametrize(
    ("overrides", "state"),
    [
        (None, "default"),
        ({}, "default"),
        ({"invitation_subject": "   "}, "default"),
        ({"responses_received_enabled": False}, "default"),
        ({"invitation_subject": "Your review"}, "customized"),
        ({"responses_received_bcc": "a@example.edu"}, "customized"),
    ],
)
def test_the_pill_and_validate_agree(
    client: TestClient, db: Session, overrides: dict[str, Any] | None, state: str
) -> None:
    rs = _session(client, db)
    rs.email_template_overrides = overrides
    db.commit()
    _assert_neutral(_pill(client, rs), state)
    assert _validate_row(client, rs) == state
