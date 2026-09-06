"""The setup-template download — Segment 19E rung 4.

Two things are worth testing here and neither is the zip mechanics: that
the generated templates survive the real importers, and that the two
pre-session surfaces actually offer them.
"""

from __future__ import annotations

import io
import zipfile

from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.identity import (
    AuthenticatedUser,
    get_current_user,
    resolve_current_user,
)
from app.config import Settings
from app.db.models import Reviewee, Reviewer, ReviewSession, User
from app.main import app
from app.services import csv_imports, relationships
from app.services.setup_templates import (
    STARTER_TEMPLATES,
    STARTER_ZIP_NAME,
    build_starter_zip,
)

DOWNLOAD_URL = "/templates/starter.zip"


def _files() -> dict[str, bytes]:
    archive = zipfile.ZipFile(io.BytesIO(build_starter_zip()))
    return {name: archive.read(name) for name in archive.namelist()}


def test_the_route_serves_the_zip(client: TestClient) -> None:
    response = client.get(DOWNLOAD_URL)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert STARTER_ZIP_NAME in response.headers["content-disposition"]
    assert sorted(zipfile.ZipFile(io.BytesIO(response.content)).namelist()) == (
        sorted(t.filename for t in STARTER_TEMPLATES)
    )


def test_the_route_requires_authentication() -> None:
    """Not because the payload is sensitive — it is four constant
    headers — but because every surface in this app is behind sign-in and
    an unauthenticated route here would be the app's first exception. The
    open question of whether `/guide` should be public is deferred to
    Segment 20; until it is answered, this route stays gated too."""
    real_settings = Settings(allow_fake_auth=False)

    def override(request: Request) -> AuthenticatedUser:
        return resolve_current_user(request, real_settings)

    app.dependency_overrides[get_current_user] = override
    try:
        response = TestClient(app).get(DOWNLOAD_URL)
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 401


def test_the_roster_templates_parse_with_no_issues() -> None:
    """The point of deriving headers from the extracts: what the operator
    downloads is what the importer accepts. A parser change that breaks
    the templates fails here rather than in the operator's hands."""
    files = _files()

    for filename, parse in (
        ("reviewers.csv", csv_imports.parse_reviewer_csv),
        ("reviewees.csv", csv_imports.parse_reviewee_csv),
        ("observers.csv", csv_imports.parse_observer_csv),
    ):
        result = parse(files[filename])

        assert not result.is_blocked, (filename, result.issues)
        assert result.issues == [], filename
        assert len(result.rows) == 1, filename


def test_the_roster_templates_capture_no_label_overrides() -> None:
    """Bare headers must read as "no override captured". If a template
    header ever grew a `<Column>.<label>` suffix it would silently rename
    the operator's tag column on upload."""
    files = _files()

    assert csv_imports.parse_reviewer_csv(files["reviewers.csv"]).field_labels == {}
    assert csv_imports.parse_reviewee_csv(files["reviewees.csv"]).field_labels == {}


def test_the_relationships_template_parses_against_its_own_rosters(
    db: Session,
) -> None:
    """The four files are one coherent set — the relationship row names
    the people the roster files define, so the whole set imports as a
    working one-pair session."""
    files = _files()
    reviewer_rows = csv_imports.parse_reviewer_csv(files["reviewers.csv"]).rows
    reviewee_rows = csv_imports.parse_reviewee_csv(files["reviewees.csv"]).rows

    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Templates", code="tpl-parse", created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    reviewers = [
        Reviewer(session_id=review_session.id, name=r.name, email=r.email)
        for r in reviewer_rows
    ]
    reviewees = [
        Reviewee(
            session_id=review_session.id,
            name=r.name,
            email_or_identifier=r.email_or_identifier,
        )
        for r in reviewee_rows
    ]
    db.add_all([*reviewers, *reviewees])
    db.flush()

    result = relationships.parse_relationship_csv(
        files["relationships.csv"], reviewers=reviewers, reviewees=reviewees
    )

    assert result.issues == []
    assert len(result.rows) == 1


def test_the_guide_offers_the_download(client: TestClient) -> None:
    body = client.get("/guide").text

    assert DOWNLOAD_URL in body
    assert "download that session's roster" in body  # the bare-header caveat


def test_the_lobby_first_run_card_offers_the_download(client: TestClient) -> None:
    body = client.get("/operator/sessions").text

    assert 'id="lobby-first-run"' in body
    assert DOWNLOAD_URL in body


def test_a_lobby_with_sessions_does_not_offer_the_download(
    client: TestClient,
) -> None:
    """The download rides on the first-run card, so it leaves with it.
    An operator with a session gets templates from the Guide."""
    client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )

    body = client.get("/operator/sessions").text

    assert DOWNLOAD_URL not in body
