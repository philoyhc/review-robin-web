"""Tests for the Segment 11H PR B Extract Data card scaffold.

The scaffold replaces the ``placeholder_card(id="extract-data")``
stub with the full five-row + zip-bundle layout per
``guide/segment_12A.md`` PR 6. Every Download button is inert
(``aria-disabled="true"``) until 12A wires the routes.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import ReviewSession
from app.web import views


def _make_session(
    client: TestClient, db: Session, *, code: str = "ed-scaffold"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "ExtractScaffold", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_pair(
    client: TestClient, db: Session, *, code: str, reviewer_email: str
) -> ReviewSession:
    review_session = _make_session(client, db, code=code)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nR,{reviewer_email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )
    return review_session


def _activate(
    client: TestClient, db: Session, review_session: ReviewSession
) -> None:
    client.get(f"/operator/sessions/{review_session.id}?validated=1")
    client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)


def test_build_extract_data_context_returns_five_rows_plus_bundle(
    client: TestClient, db: Session
) -> None:
    """The view-shape adapter returns the five per-entity rows in
    the canonical 2-col grid order (Reviewers / Reviewees /
    Assignments / Responses / Session settings — left-right, up-down)
    plus the zip-bundle row separately."""

    review_session = _make_session(client, db, code="ed-shape")
    context = views.build_extract_data_context(db, review_session)

    assert [row.key for row in context.rows] == [
        "reviewers",
        "reviewees",
        "assignments",
        "responses",
        "settings",
    ]
    assert context.bundle.key == "bundle"
    assert context.bundle.label == "Zip all"
    # All inert at scaffold-time.
    assert all(row.is_wired is False for row in context.rows)
    assert context.bundle.is_wired is False


def test_extract_data_filenames_carry_session_code(
    client: TestClient, db: Session
) -> None:
    """The download filename surfaces the operator-typed session
    code so the file is identifiable downstream."""

    review_session = _make_session(client, db, code="abc123")
    context = views.build_extract_data_context(db, review_session)
    by_key = {row.key: row for row in context.rows}

    assert by_key["reviewers"].filename == "session-abc123-reviewers.csv"
    assert by_key["responses"].filename == "session-abc123-responses.csv"
    assert context.bundle.filename == "session-abc123-export.zip"


def test_extract_data_count_summaries_pluralise_correctly(
    client: TestClient, db: Session
) -> None:
    """Empty / singular / plural copy variants render correctly so
    the count line reads naturally on screen."""

    empty = _make_session(client, db, code="ed-empty")
    empty_ctx = views.build_extract_data_context(db, empty)
    empty_by_key = {row.key: row for row in empty_ctx.rows}
    assert empty_by_key["reviewers"].count_summary == "0 reviewers"

    populated = _seed_pair(
        client, db, code="ed-populated", reviewer_email="r@example.edu"
    )
    populated_ctx = views.build_extract_data_context(db, populated)
    populated_by_key = {row.key: row for row in populated_ctx.rows}
    assert populated_by_key["reviewers"].count == 1
    assert populated_by_key["reviewers"].count_summary == "1 reviewer"


def test_extract_data_bundle_count_sums_per_entity_counts(
    client: TestClient, db: Session
) -> None:
    """The bundle row's count summary aggregates the five entity
    counts; useful to give the operator a single "total rows in
    the zip" number."""

    review_session = _seed_pair(
        client, db, code="ed-sum", reviewer_email="r@example.edu"
    )
    context = views.build_extract_data_context(db, review_session)

    assert context.bundle.count == sum(row.count for row in context.rows)


def test_extract_data_dom_carries_wire_target_attributes(
    client: TestClient, db: Session
) -> None:
    """Each row's wrapping ``<section>`` carries
    ``data-wire-target="extract-data-{key}"`` for 12A's wiring
    seam."""

    review_session = _make_session(client, db, code="ed-wire")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    for key in (
        "settings",
        "reviewers",
        "reviewees",
        "assignments",
        "responses",
        "bundle",
    ):
        assert f'data-wire-target="extract-data-{key}"' in body


def test_extract_data_buttons_are_aria_disabled_anchors(
    client: TestClient, db: Session
) -> None:
    """While inert, every Download button renders as an anchor
    without an ``href`` and with ``aria-disabled="true"`` (anchors
    don't honour native ``disabled``). 12A's wiring flips this
    to a real ``href``."""

    review_session = _make_session(client, db, code="ed-anchors")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    # Every "Download" anchor is aria-disabled.
    download_count = body.count(
        '<a class="btn secondary"\n'
        '       role="button"\n'
        '       aria-disabled="true"'
    )
    # Five per-entity rows + one bundle = six download anchors total.
    assert download_count == 6


def test_extract_data_card_renders_when_session_is_activated(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Per ``guide/segment_12A.md`` "No lifecycle gate", the
    Extract Data card stays visible and laid out in every state.
    Today every row is inert; once 12A wires the routes, the card
    will be interactive even on Activated sessions."""

    operator = make_client(alice)
    review_session = _seed_pair(
        operator, db, code="ed-activated", reviewer_email="r@example.edu"
    )
    _activate(operator, db, review_session)

    body = operator.get(f"/operator/sessions/{review_session.id}").text

    # Card rendered without a ``.disabled`` modifier.
    assert 'class="card" id="extract-data"' in body
    # Five rows still present with their counts surfaced.
    for key in (
        "settings",
        "reviewers",
        "reviewees",
        "assignments",
        "responses",
    ):
        assert f'id="extract-data-{key}"' in body
