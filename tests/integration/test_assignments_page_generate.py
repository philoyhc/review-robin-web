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


def test_status_block_reports_pinned_rule(
    client: TestClient, db: Session
) -> None:
    """Pinning a rule on every instrument lights up the status
    block with the rule name. (The standalone Eligible-pairs column
    was dropped in Segment 13C — the engine pass still feeds the
    block's staleness check, it's just no longer a column.)"""

    review_session = _make_session(client, db, code="page-pin")
    _seed_pair(client, review_session.id)
    pin_full_matrix_on_all_instruments(db, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    status_section = body.split('id="assignments-status-blocks"', 1)[1]
    assert "Full Matrix" in status_section
    # The per-reviewee instrument reports its Type.
    assert "Individual" in status_section


def test_status_block_reports_group_type_and_group_count(
    client: TestClient, db: Session
) -> None:
    """A group-scoped instrument's status block reports Type
    "Group" and, once generated, a Groups count — distinct
    (reviewer, group_key) over its assignments (Segment 13C)."""
    review_session = _make_session(client, db, code="page-group")
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-group",
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
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
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail,RevieweeTag1\n"
                b"Carol,carol@example.edu,Team A\n"
                b"Eve,eve@example.edu,Team A\n"
                b"Dan,dan@example.edu,Team B\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    group = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.group_kind.is_not(None))
    ).scalar_one()
    group.group_kind = "r1"  # group by RevieweeTag1
    db.commit()
    pin_full_matrix_on_all_instruments(db, review_session.id)

    status_url = f"/operator/sessions/{review_session.id}/assignments"
    # Before generation: Type "Group", Groups column shows "—".
    section = client.get(status_url).text.split(
        'id="assignments-status-blocks"', 1
    )[1]
    assert "Group" in section

    generate_via_page_button(client, review_session.id)

    # After generation: 2 boundary groups (Team A, Team B).
    section = client.get(status_url).text.split(
        'id="assignments-status-blocks"', 1
    )[1]
    row = section.split(f'id="status-block-{group.id}"', 1)[1].split(
        "</tr>", 1
    )[0]
    assert ">2</span>" in row  # Groups count


def test_bulk_inactivate_and_activate_assignments(
    client: TestClient, db: Session
) -> None:
    """The operator-actions card's bulk Inactivate / Activate
    buttons flip the ``include`` flag on the selected assignment
    rows (Segment 13C slice 2)."""
    review_session = _make_session(client, db, code="page-bulk")
    _seed_pair(client, review_session.id)
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)

    def _includes() -> list[bool]:
        return [
            a.include
            for a in db.execute(
                select(Assignment).where(
                    Assignment.session_id == review_session.id
                )
            ).scalars()
        ]

    ids = [
        a.id
        for a in db.execute(
            select(Assignment).where(
                Assignment.session_id == review_session.id
            )
        ).scalars()
    ]
    assert ids and all(_includes())  # generated rows start included

    # The page renders the row-select column + bulk buttons.
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert 'id="assignments-select-all"' in body
    assert 'id="assignments-inactivate-btn"' in body

    payload = {"assignment_ids": [str(i) for i in ids]}
    resp = client.post(
        f"/operator/sessions/{review_session.id}/assignments/bulk-inactivate",
        data=payload,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    db.expire_all()
    assert not any(_includes())

    resp = client.post(
        f"/operator/sessions/{review_session.id}/assignments/bulk-activate",
        data=payload,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    db.expire_all()
    assert all(_includes())


def test_assignment_search_filters_the_preview_table(
    client: TestClient, db: Session
) -> None:
    """Card B's free-text search filters the assignments preview by
    reviewer / reviewee name or email; a non-matching term shows
    the no-match message and keeps the term (Segment 13C slice 3)."""
    review_session = _make_session(client, db, code="page-search")
    _seed_pair(client, review_session.id)
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)

    base = f"/operator/sessions/{review_session.id}/assignments"

    # A matching term (the reviewee's email) keeps the row.
    body = client.get(base + "?q=carol").text
    assert "carol@example.edu" in body
    assert "No assignments match" not in body

    # A non-matching term → no-match message + "Showing 0 of 1";
    # the search box retains the term so it can be cleared.
    body = client.get(base + "?q=nosuchterm").text
    assert "No assignments match the search." in body
    assert 'value="nosuchterm"' in body
    assert "Showing 0 of 1" in body


def test_assignment_search_by_scopes_the_match(
    client: TestClient, db: Session
) -> None:
    """The 'Search by' dropdown scopes the search to the reviewer
    or the reviewee side only (Segment 13C)."""
    review_session = _make_session(client, db, code="page-searchby")
    _seed_pair(client, review_session.id)  # reviewer alice@, reviewee carol@
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)
    base = f"/operator/sessions/{review_session.id}/assignments"

    def _matches(query: str) -> bool:
        return "No assignments match" not in client.get(base + query).text

    # search_by=reviewer: the reviewer's name matches, the reviewee's
    # does not.
    assert _matches("?q=alice&search_by=reviewer")
    assert not _matches("?q=carol&search_by=reviewer")
    # search_by=reviewee: the reverse.
    assert not _matches("?q=alice&search_by=reviewee")
    assert _matches("?q=carol&search_by=reviewee")
    # The dropdown reflects the chosen dimension.
    body = client.get(base + "?q=alice&search_by=reviewer").text
    assert '<option value="reviewer" selected>Reviewers</option>' in body


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
