"""Findings 2026-10-22 P1: a whitespace-only email claim is no email.

Easy Auth's rich principal header reaches `get_or_create_user` unmocked
here. A blank claim used to count, so the user row stored `""` and the
next sign-in answered 500 on the unique email; it now yields to the next
claim in the fallback order, and with none the request is 401
(`spec/permissions.md` §2).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db

from .conftest import app

_EMAILADDRESS = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"


def _principal(*claims: tuple[str, str]) -> dict[str, str]:
    payload = {
        "auth_typ": "aad",
        "claims": [{"typ": typ, "val": val} for typ, val in claims],
    }
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return {"X-MS-CLIENT-PRINCIPAL": encoded, "X-MS-CLIENT-PRINCIPAL-ID": "blank-oid"}


@pytest.fixture
def header_client(db: Session) -> Iterator[TestClient]:
    """A client whose identity comes from the request's headers."""

    def override_get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_a_blank_email_claim_yields_to_the_fallback_claim(
    header_client: TestClient, db: Session
) -> None:
    headers = _principal(
        (_EMAILADDRESS, "   "), ("preferred_username", "pat@example.edu")
    )

    for _ in range(2):  # the second sign-in was the 500
        assert header_client.get("/me", headers=headers).status_code == 200

    assert db.execute(select(User.email)).scalars().all() == ["pat@example.edu"]


def test_only_blank_email_claims_answer_401(
    header_client: TestClient, db: Session
) -> None:
    headers = _principal(
        (_EMAILADDRESS, " "), ("preferred_username", "\t"), ("email", "  ")
    )

    for _ in range(2):
        assert header_client.get("/me", headers=headers).status_code == 401

    assert db.execute(select(User.id)).scalars().all() == []
