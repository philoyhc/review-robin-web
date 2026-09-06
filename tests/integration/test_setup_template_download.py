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
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.identity import (
    AuthenticatedUser,
    get_current_user,
    resolve_current_user,
)
from app.config import Settings
from app.db.models import (
    Assignment,
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.main import app
from app.services import csv_imports, relationships
from app.services.setup_templates import (
    build_zip,
    set_by_key,
    templates_in,
)

DOWNLOAD_URL = "/templates/starter.zip"
DEMO_URL = "/templates/demo.zip"


def _files(set_key: str = "starter") -> dict[str, bytes]:
    archive = zipfile.ZipFile(io.BytesIO(build_zip(set_by_key(set_key))))
    return {name: archive.read(name) for name in archive.namelist()}


def test_the_route_serves_the_zip(client: TestClient) -> None:
    response = client.get(DOWNLOAD_URL)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    starter = set_by_key("starter")
    assert starter.zip_name in response.headers["content-disposition"]
    assert sorted(zipfile.ZipFile(io.BytesIO(response.content)).namelist()) == (
        sorted(t.filename for t in templates_in(starter))
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


def test_the_roster_templates_capture_their_worked_label_overrides() -> None:
    """The templates demonstrate the `<Column>.<label>` grammar, so the
    importer must actually read those labels back — otherwise the header
    is decoration. This is also the live consequence: uploading a
    template unedited renames that session's tag columns to Tutor /
    Group, which the Guide card tells the operator."""
    files = _files()

    assert csv_imports.parse_reviewer_csv(files["reviewers.csv"]).field_labels == {
        ("reviewer", "tag_1"): "Tutor",
        ("reviewer", "tag_2"): "Group",
    }
    assert csv_imports.parse_reviewee_csv(files["reviewees.csv"]).field_labels == {
        ("reviewee", "tag_1"): "Tutor",
        ("reviewee", "tag_2"): "Group",
    }


def test_the_observer_template_captures_no_label_overrides() -> None:
    """Observer tags are outside the labelable set, so nothing there can
    become an override however the header is written."""
    files = _files()

    assert csv_imports.parse_observer_csv(files["observers.csv"]).field_labels == {}


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
    assert "Tutor" in body  # the worked-label caveat names the example labels


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


# --------------------------------------------------------------------------- #
# The demo set — Segment 19E rung 5
# --------------------------------------------------------------------------- #


def test_the_demo_route_serves_its_own_zip(client: TestClient) -> None:
    response = client.get(DEMO_URL)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert set_by_key("demo").zip_name in response.headers["content-disposition"]


def test_the_demo_roster_files_parse_with_no_issues() -> None:
    files = _files("demo")

    for filename, parse in (
        ("reviewers.csv", csv_imports.parse_reviewer_csv),
        ("reviewees.csv", csv_imports.parse_reviewee_csv),
        ("observers.csv", csv_imports.parse_observer_csv),
    ):
        result = parse(files[filename])

        assert not result.is_blocked, (filename, result.issues)
        assert result.issues == [], filename


def test_the_demo_set_builds_a_validated_session(
    client: TestClient, db: Session
) -> None:
    """The rung's acceptance test: download -> Quick Setup -> Prepare ->
    `validated`, through the real import path rather than a fixture.

    Nothing is configured along the way. A new session is seeded with a
    default instrument whose rule defaults to Full Matrix, so the four
    roster files are sufficient on their own — which is why neither
    template set carries a `settings.csv`.
    """
    files = _files("demo")
    client.post(
        "/operator/sessions",
        data={"name": "Sample session", "code": "demo-round-trip"},
        follow_redirects=False,
    )
    session_id = db.execute(
        select(ReviewSession.id).where(
            ReviewSession.code == "demo-round-trip"
        )
    ).scalar_one()

    submitted = client.post(
        f"/operator/sessions/{session_id}/quick-setup/submit-all",
        files={
            "reviewers_file": ("reviewers.csv", files["reviewers.csv"], "text/csv"),
            "reviewees_file": ("reviewees.csv", files["reviewees.csv"], "text/csv"),
            "relationships_file": (
                "relationships.csv",
                files["relationships.csv"],
                "text/csv",
            ),
            "observers_file": ("observers.csv", files["observers.csv"], "text/csv"),
        },
        follow_redirects=False,
    )
    # A slot that fails redirects with ?quick_setup_error=...; a clean
    # submit carries no flag. Asserted because a silently-skipped slot
    # would still let the session validate on the remaining rosters.
    assert submitted.status_code == 303
    assert "quick_setup_error" not in submitted.headers["location"]

    prepared = client.post(
        f"/operator/sessions/{session_id}/workflow/prepare",
        follow_redirects=False,
    )
    assert prepared.status_code == 303

    db.expire_all()
    assert db.get(ReviewSession, session_id).status == "validated"


def test_the_demo_set_populates_the_surfaces_it_is_meant_to_show(
    client: TestClient, db: Session
) -> None:
    """`validated` alone would be satisfied by a one-pair session. The
    demo set exists so the Assignments page, the Responses grid and
    observer collation have something in them — so assert the rosters and
    the generated assignments actually landed."""
    files = _files("demo")
    client.post(
        "/operator/sessions",
        data={"name": "Sample session", "code": "demo-populated"},
        follow_redirects=False,
    )
    session_id = db.execute(
        select(ReviewSession.id).where(ReviewSession.code == "demo-populated")
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session_id}/quick-setup/submit-all",
        files={
            "reviewers_file": ("reviewers.csv", files["reviewers.csv"], "text/csv"),
            "reviewees_file": ("reviewees.csv", files["reviewees.csv"], "text/csv"),
            "relationships_file": (
                "relationships.csv",
                files["relationships.csv"],
                "text/csv",
            ),
            "observers_file": ("observers.csv", files["observers.csv"], "text/csv"),
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/workflow/prepare",
        follow_redirects=False,
    )

    demo = set_by_key("demo")
    assert db.scalar(
        select(func.count()).select_from(Reviewer).where(
            Reviewer.session_id == session_id
        )
    ) == len(demo.rows["reviewers"])
    assert db.scalar(
        select(func.count()).select_from(Reviewee).where(
            Reviewee.session_id == session_id
        )
    ) == len(demo.rows["reviewees"])
    assert db.scalar(
        select(func.count()).select_from(Observer).where(
            Observer.session_id == session_id
        )
    ) == len(demo.rows["observers"])

    assignments = db.scalar(
        select(func.count()).select_from(Assignment).where(
            Assignment.session_id == session_id
        )
    )
    assert assignments > len(demo.rows["reviewers"]), assignments


def test_the_guide_offers_the_sample_session(client: TestClient) -> None:
    body = client.get("/guide").text

    assert "<h2>Sample session</h2>" in body
    assert DEMO_URL in body


def test_the_lobby_first_run_card_does_not_offer_the_demo_set(
    client: TestClient,
) -> None:
    """The first-run card is for someone about to set up for real. The
    sample session is a detour, and it lives on the Guide where there is
    room to explain what to do with it."""
    body = client.get("/operator/sessions").text

    assert 'id="lobby-first-run"' in body
    assert DEMO_URL not in body
