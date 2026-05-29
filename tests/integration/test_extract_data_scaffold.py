"""Tests for the Session Home card scaffold (renamed to
"Extract Setup" on 2026-05-29 per ``guide/extract_data.md``).

The scaffold replaces the ``placeholder_card(id="extract-data")``
stub with a per-entity row + zip-bundle layout. Originally five
rows (12A vintage); on 2026-05-29 the Responses row moved off
to the new Extract data Operations-strip tab, leaving four rows
(Reviewers / Reviewees / Relationships / Session settings) +
the Zip-all bundle. DOM ids kept the ``extract-data*`` prefix
to avoid a wider sweep.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import ReviewSession
from app.web import views
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


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
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)
    return review_session


def _activate(
    client: TestClient, db: Session, review_session: ReviewSession
) -> None:
    client.get(f"/operator/sessions/{review_session.id}/assignments?validated=1")
    client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)


def test_build_extract_data_context_returns_four_rows_plus_bundle(
    client: TestClient, db: Session
) -> None:
    """The view-shape adapter returns the four per-entity rows
    (Reviewers / Reviewees / Relationships / Session settings)
    in DOM order. The ``extract-data-grid`` CSS wraps row-major
    in a 2-column grid, so this list lays out as:

        Reviewers       |  Session settings
        Reviewees       |  Zip all
        Relationships   |

    On a freshly-created draft (no rosters yet), the per-entity
    rows are inert — there's nothing to download. Settings stays
    always-live (session metadata always exists).

    Responses moved to the new Extract data Operations-strip tab
    on 2026-05-29 (per ``guide/extract_data.md``); the row no
    longer surfaces on this card.

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
    # Roster rows are inert on an empty session (count=0).
    for key in ("reviewers", "reviewees", "relationships"):
        assert by_key[key].is_wired is False, key
        assert by_key[key].download_url is None, key
        assert by_key[key].coming_in is not None, key
    # Bundle row is wired (Segment 18D PR E1) — the session
    # always has at least the Settings CSV to bundle.
    assert context.bundle.is_wired is True
    assert context.bundle.download_url == (
        f"/operator/sessions/{review_session.id}/export/bundle.zip"
    )
    # Retired / relocated / never-surfaced keys absent.
    assert "assignments" not in by_key
    assert "responses" not in by_key
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
    # Responses row no longer on this card (moved to Extract
    # data Operations-strip tab on 2026-05-29).
    assert "responses" not in by_key


def test_extract_data_filenames_carry_session_code(
    client: TestClient, db: Session
) -> None:
    """The download filename surfaces the operator-typed session
    code so the file is identifiable downstream."""

    review_session = _make_session(client, db, code="abc123")
    context = views.build_extract_data_context(db, review_session)
    by_key = {row.key: row for row in context.rows}

    # Every row uses the {code}_{kind} convention; the zip bundle
    # is {code}_bundle.zip (Segment 18D PR E1).
    assert by_key["reviewers"].filename == "abc123_reviewers.csv"
    assert by_key["reviewees"].filename == "abc123_reviewees.csv"
    assert by_key["relationships"].filename == "abc123_relationships.csv"
    assert context.bundle.filename == "abc123_bundle.zip"


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
    """The bundle row's count summary aggregates the per-entity
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
        "bundle",
    ):
        assert f'data-wire-target="extract-data-{key}"' in body
    # Assignments tile retired in 12A-3 PR 2.
    assert 'data-wire-target="extract-data-assignments"' not in body
    # Responses tile relocated to the Extract data Operations
    # tab on 2026-05-29.
    assert 'data-wire-target="extract-data-responses"' not in body
    # Audit log lives at its own route but is not surfaced on
    # Extract Setup — it'll move to the Sys Admin page (Segment 16).
    assert 'data-wire-target="extract-data-audit_log"' not in body


def test_extract_data_card_renders_counts_for_entity_rows_only(
    client: TestClient, db: Session
) -> None:
    """The per-entity rows (Reviewers / Reviewees / Relationships)
    surface their raw count inline next to the title (e.g.
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
    # Responses row no longer on this card.
    assert "Responses <span" not in body
    # Settings + Zip all keep title-only treatment.
    assert "Session settings <span" not in body
    assert "Zip all <span" not in body

    # ExtractDataRow.show_count flag follows the same shape.
    context = views.build_extract_data_context(db, review_session)
    by_key = {r.key: r for r in context.rows}
    assert by_key["reviewers"].show_count is True
    assert by_key["reviewees"].show_count is True
    assert by_key["relationships"].show_count is True
    assert by_key["settings"].show_count is False
    assert context.bundle.show_count is False


def test_extract_data_buttons_are_aria_disabled_anchors(
    client: TestClient, db: Session
) -> None:
    """While inert, every Download button renders as an anchor
    without an ``href`` and with ``aria-disabled="true"`` (anchors
    don't honour native ``disabled``). On a freshly-created draft
    the three empty per-entity rows (Reviewers / Reviewees /
    Relationships) are inert (nothing to download yet); Settings
    and the Zip-all bundle stay live. So 3 inert anchors total
    on a fresh draft."""

    review_session = _make_session(client, db, code="ed-anchors")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    # Inert rows render as aria-disabled anchors.
    download_count = body.count(
        '<a class="btn secondary"\n'
        '       role="button"\n'
        '       aria-disabled="true"'
    )
    assert download_count == 3


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
    assert 'id="extract-data"' in body
    assert 'class="card disabled' not in body
    # Four rows still present (Responses relocated 2026-05-29).
    for key in (
        "settings",
        "reviewers",
        "reviewees",
        "relationships",
    ):
        assert f'id="extract-data-{key}"' in body
    assert 'id="extract-data-responses"' not in body
