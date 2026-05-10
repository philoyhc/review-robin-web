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
from ._full_matrix import full_matrix_seed_id


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
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": ""},
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
    the post-12A-3-PR-2 DOM order. The ``extract-data-grid`` CSS
    wraps row-major in a 2-column grid, so this list lays out as:

        Reviewers       |  Session settings
        Reviewees       |  Responses
        Relationships   |  Zip all  (inert)

    On a freshly-created draft (no rosters yet), the per-entity
    rows are inert — there's nothing to download. Settings stays
    always-live (session metadata always exists).

    Audit log download is deliberately *not* surfaced here —
    it lives at the audit-log route but relocates to the Sys
    Admin page (Segment 16) per industry best practice for
    audit-data surfaces."""

    review_session = _make_session(client, db, code="ed-shape")
    context = views.build_extract_data_context(db, review_session)

    assert [row.key for row in context.rows] == [
        "reviewers",
        "settings",
        "reviewees",
        "responses",
        "relationships",
    ]
    assert context.bundle.key == "bundle"
    assert context.bundle.label == "Zip all"
    by_key = {r.key: r for r in context.rows}
    # Settings always live — session metadata always exists.
    assert by_key["settings"].is_wired is True
    assert by_key["settings"].download_url == (
        f"/operator/sessions/{review_session.id}/export/settings.csv"
    )
    # Roster + responses rows are inert on an empty session (count=0).
    for key in ("reviewers", "reviewees", "relationships", "responses"):
        assert by_key[key].is_wired is False, key
        assert by_key[key].download_url is None, key
        assert by_key[key].coming_in is not None, key
    # Bundle row stays inert until its own PR.
    assert context.bundle.is_wired is False
    # Retired / never-surfaced keys absent.
    assert "assignments" not in by_key
    assert "audit_log" not in by_key


def test_per_entity_rows_go_live_when_populated(
    client: TestClient, db: Session
) -> None:
    """Once the operator uploads any rosters / generates any
    rule-based assignments / etc., the corresponding per-entity
    row's button flips from grey to live."""

    review_session = _seed_pair(
        client, db, code="ed-live", reviewer_email="r@example.edu"
    )
    context = views.build_extract_data_context(db, review_session)
    by_key = {r.key: r for r in context.rows}

    # Reviewers + reviewees seeded by ``_seed_pair`` → both live.
    assert by_key["reviewers"].is_wired is True
    assert by_key["reviewers"].download_url == (
        f"/operator/sessions/{review_session.id}/export/reviewers.csv"
    )
    assert by_key["reviewees"].is_wired is True
    # Relationships not seeded → still inert.
    assert by_key["relationships"].is_wired is False
    # No responses on a not-yet-activated session → still inert.
    assert by_key["responses"].is_wired is False


def test_extract_data_filenames_carry_session_code(
    client: TestClient, db: Session
) -> None:
    """The download filename surfaces the operator-typed session
    code so the file is identifiable downstream."""

    review_session = _make_session(client, db, code="abc123")
    context = views.build_extract_data_context(db, review_session)
    by_key = {row.key: row for row in context.rows}

    # Live rows use the {code}_{kind}.csv convention; only the
    # zip bundle keeps its pre-12A-1 placeholder filename until
    # its own PR graduates it.
    assert by_key["reviewers"].filename == "abc123_reviewers.csv"
    assert by_key["reviewees"].filename == "abc123_reviewees.csv"
    assert by_key["relationships"].filename == "abc123_relationships.csv"
    assert by_key["responses"].filename == "abc123_responses.csv"
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
        "relationships",
        "responses",
        "bundle",
    ):
        assert f'data-wire-target="extract-data-{key}"' in body
    # Assignments tile retired in 12A-3 PR 2.
    assert 'data-wire-target="extract-data-assignments"' not in body
    # Audit log lives at its own route but is not surfaced on
    # Extract Data — it'll move to the Sys Admin page (Segment 16).
    assert 'data-wire-target="extract-data-audit_log"' not in body


def test_extract_data_card_renders_counts_for_entity_rows_only(
    client: TestClient, db: Session
) -> None:
    """Per the post-Part-1 polish, the per-entity rows
    (Reviewers / Reviewees / Relationships / Responses) surface
    their raw count inline next to the title (e.g.
    ``Reviewers (1)``). Session settings and the zip-bundle row
    keep the title-only treatment — counts there are either
    redundant (instrument count isn't a useful "Session settings"
    signal) or already implied (zip aggregates everything
    above)."""

    review_session = _seed_pair(
        client, db, code="ed-counts", reviewer_email="r@example.edu"
    )
    body = client.get(f"/operator/sessions/{review_session.id}").text

    # Entity rows render their count after the title.
    assert "Reviewers <span" in body
    assert "Reviewees <span" in body
    assert "Relationships <span" in body
    assert "Responses <span" in body
    # Settings + Zip all keep title-only treatment.
    assert "Session settings <span" not in body
    assert "Zip all <span" not in body

    # ExtractDataRow.show_count flag follows the same shape.
    context = views.build_extract_data_context(db, review_session)
    by_key = {r.key: r for r in context.rows}
    assert by_key["reviewers"].show_count is True
    assert by_key["reviewees"].show_count is True
    assert by_key["relationships"].show_count is True
    assert by_key["responses"].show_count is True
    assert by_key["settings"].show_count is False
    assert context.bundle.show_count is False


def test_extract_data_buttons_are_aria_disabled_anchors(
    client: TestClient, db: Session
) -> None:
    """While inert, every Download button renders as an anchor
    without an ``href`` and with ``aria-disabled="true"`` (anchors
    don't honour native ``disabled``). On a freshly-created draft
    every per-entity row is inert (nothing to download yet); only
    Settings stays live. So 5 inert anchors total — the four
    empty per-entity rows + the zip bundle."""

    review_session = _make_session(client, db, code="ed-anchors")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    # Inert rows render as aria-disabled anchors.
    download_count = body.count(
        '<a class="btn secondary"\n'
        '       role="button"\n'
        '       aria-disabled="true"'
    )
    assert download_count == 5


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
        "relationships",
        "responses",
    ):
        assert f'id="extract-data-{key}"' in body
