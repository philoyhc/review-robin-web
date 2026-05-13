"""Slice 3a coverage for the reshaped Assignments page —
page-level Generate + per-instrument status blocks + stale badge.

Pre-15B the page hosted a Rule Based card (pick a rule + Generate).
Slice 3a flips it to:

- A page-level **Generate assignments** button that calls
  ``replace_assignments(instrument_id=None)`` over every instrument
  with a non-NULL ``rule_set_id``. Disabled when zero instruments
  have a rule pinned, with a "Pin rules on the Instruments page
  first" nudge.
- Per-instrument status blocks reporting Rule / Eligible /
  Generated independently. The eligible count refreshes on every
  page load (reflects roster edits before Generate runs); the
  generated count only changes when Generate runs.
- A "Pairs may be stale" badge near the Generate button when the
  eligible and materialised counts diverge for any pinned
  instrument.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    ReviewSession,
)
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "AsgnPage", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_pair(client: TestClient, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )


def test_status_block_reports_pinned_rule_and_eligible_count(
    client: TestClient, db: Session
) -> None:
    """Pinning a rule on every instrument lights up the status
    block: rule name + eligible count from the engine pass. The
    standalone Generate card UI it previously gated retired with
    the Next-Action workflow-stepper refresh, but the engine pass
    still feeds the per-instrument status block."""

    review_session = _make_session(client, db, code="page-pin")
    _seed_pair(client, review_session.id)
    pin_full_matrix_on_all_instruments(db, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    # Status block reports the pinned rule + eligible count from
    # the engine pass.
    assert "Full Matrix" in body
    # 1 reviewer × 1 reviewee = 1 eligible pair.
    status_section = body.split('id="assignments-status-blocks"', 1)[1]
    assert ">1</span>" in status_section


def test_generate_materialises_per_instrument(
    client: TestClient, db: Session
) -> None:
    """Posting the page-level Generate route runs the materialiser
    over every pinned instrument; per-instrument status block
    flips from "Not generated yet" to a count + last-generated
    timestamp."""

    review_session = _make_session(client, db, code="page-mat")
    _seed_pair(client, review_session.id)
    pin_full_matrix_on_all_instruments(db, review_session.id)

    response = generate_via_page_button(client, review_session.id)
    assert response.status_code == 303
    # Post-generate redirect lands plain on the Assignments page —
    # the ``?generated=1`` flash signal retired with the banner.
    assert (
        response.headers["location"]
        == f"/operator/sessions/{review_session.id}/assignments"
    )

    rows = list(
        db.execute(
            select(Assignment).where(
                Assignment.session_id == review_session.id
            )
        ).scalars()
    )
    assert len(rows) == 1

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert 'id="generated-flash"' not in body
    # Status block flips from "Not generated yet" placeholder to a
    # generated-count pill. The "last generated …" timestamp
    # suffix retired in the post-15B refinement sweep — the pill
    # itself is the signal now.
    assert "Not generated yet" not in body
    # Generated-count pill renders with the actual row count (1
    # alice→carol pair in this fixture).
    assert ">1</span>" in body.split('id="assignments-status-blocks"', 1)[1]


def test_status_block_renders_no_rule_pinned_state(
    client: TestClient, db: Session
) -> None:
    """Instrument with NULL ``rule_set_id`` shows the "— No rule
    pinned —" placeholder + an "Edit on Instruments page" deep
    link, no eligible / generated counts."""

    review_session = _make_session(client, db, code="page-norule")
    _seed_pair(client, review_session.id)
    [instrument] = list(
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        ).scalars()
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    section = body.split('id="assignments-status-blocks"', 1)[1].split(
        "</section>", 1
    )[0]
    assert "— No rule pinned —" in section
    assert (
        f'href="/operator/sessions/{review_session.id}'
        f'/instruments#instrument-{instrument.id}"'
    ) in section


def test_generate_with_existing_pairs_requires_confirm(
    client: TestClient, db: Session
) -> None:
    """Re-Generating with existing pairs requires the
    ``confirm_replace`` checkbox; without it the route 303s with
    ``?needs_confirm=1`` and the existing rows survive."""

    review_session = _make_session(client, db, code="page-confirm")
    _seed_pair(client, review_session.id)
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)

    response = generate_via_page_button(client, review_session.id)
    assert response.status_code == 303
    assert "needs_confirm=1" in response.headers["location"]
    assert (
        len(
            list(
                db.execute(
                    select(Assignment).where(
                        Assignment.session_id == review_session.id
                    )
                ).scalars()
            )
        )
        == 1
    )

    confirmed = generate_via_page_button(
        client, review_session.id, confirm_replace=True
    )
    assert confirmed.status_code == 303
    # Redirect lands plain on the Assignments page (flash retired).
    assert (
        confirmed.headers["location"]
        == f"/operator/sessions/{review_session.id}/assignments"
    )
