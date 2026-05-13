"""Assignments page route coverage (post-15B Slice 3a).

Slice 3a flipped the page from "pick a rule + Generate" to
"preview + page-level Generate". The materialise flow is now:

1. The operator pins a ``session_rule_sets`` row on each
   instrument via the per-card picker (Slice 2a) — or via the
   :func:`pin_full_matrix_on_all_instruments` test helper here.
2. POST ``/assignments/generate`` invokes
   ``replace_assignments(instrument_id=None)`` per Slice 1.

These tests exercise the new end-to-end wire: pin → Generate →
audit envelope → preview render. The legacy
``/assignments/rule-based/generate`` route + the Rule Based card
template + the ``test_rule_based_*`` files retired with this slice.
"""
from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, AuditEvent, Instrument, ReviewSession
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _make_session(
    client: TestClient, db: Session, code: str = "spring-2026"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_roster(
    client: TestClient,
    session_id: int,
    *,
    reviewer_emails: list[str],
    reviewee_idents: list[str],
) -> None:
    reviewer_csv = "ReviewerName,ReviewerEmail\n" + "".join(
        f"R{i},{email}\n" for i, email in enumerate(reviewer_emails)
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={"file": ("r.csv", reviewer_csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    reviewee_csv = "RevieweeName,RevieweeEmail\n" + "".join(
        f"E{i},{ident}\n" for i, ident in enumerate(reviewee_idents)
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={"file": ("e.csv", reviewee_csv.encode(), "text/csv")},
        follow_redirects=False,
    )


def test_full_matrix_save_persists_assignments_and_sets_mode(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu", "dan-2026"],
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)

    response = generate_via_page_button(client, review_session.id)
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}/assignments"
    )
    rows = list(
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    assert len(rows) == 2
    assert all(r.created_by_mode == "rule_based" for r in rows)

    db.refresh(review_session)
    assert review_session.assignment_mode == "rule_based"

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "assignments.generated")
    ).scalar_one()
    assert event.detail["session_code"] == "spring-2026"
    assert event.detail["counts"]["new"] == 2
    assert event.detail["counts"]["pairs"] == 2
    assert event.detail["counts"]["instruments"] == 1
    assert event.detail["context"]["mode"] == "rule_based"


def test_full_matrix_fans_pairs_out_per_instrument(
    client: TestClient, db: Session
) -> None:
    """Each (reviewer, reviewee) pair gets one Assignment row per
    instrument. Multi-instrument sessions need the fanout for the
    reviewer surface's per-instrument paginated view to find rows."""
    from app.db.models import Instrument

    review_session = _make_session(client, db, code="multi-fan")
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu", "dan-2026"],
    )
    [default_instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add",
        data={"after": str(default_instrument.id)},
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)

    response = generate_via_page_button(client, review_session.id)
    assert response.status_code == 303

    rows = list(
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    # 2 pairs × 2 instruments = 4 Assignment rows.
    assert len(rows) == 4
    instrument_ids = {r.instrument_id for r in rows}
    assert len(instrument_ids) == 2
    pair_counts: dict[tuple[int, int], int] = {}
    for r in rows:
        key = (r.reviewer_id, r.reviewee_id)
        pair_counts[key] = pair_counts.get(key, 0) + 1
    assert all(count == 2 for count in pair_counts.values())

    # Slice 1: one ``assignments.generated`` event per processed
    # instrument, scoped via ``refs.instrument_id``.
    events = list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.event_type == "assignments.generated")
            .order_by(AuditEvent.id)
        ).scalars()
    )
    assert len(events) == 2
    total_new = sum(e.detail["counts"]["new"] for e in events)
    assert total_new == 4
    for event in events:
        assert event.detail["counts"]["instruments"] == 1
        assert isinstance(event.detail["refs"]["instrument_id"], int)
    assert {
        event.detail["refs"]["instrument_id"] for event in events
    } == set(instrument_ids)


def test_re_save_without_confirm_blocks(
    client: TestClient, db: Session
) -> None:
    """Re-Generate on a session with existing pairs requires the
    confirm checkbox; the route 303s back with ``?needs_confirm=1``
    and the existing rows survive."""

    review_session = _make_session(client, db)
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)

    response = generate_via_page_button(client, review_session.id)
    assert response.status_code == 303
    assert "needs_confirm=1" in response.headers["location"]
    rows = list(
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    assert len(rows) == 1


def test_re_save_with_confirm_replaces(
    client: TestClient, db: Session
) -> None:
    """``confirm_replace=true`` lets the page-level Generate cascade
    over existing rows. The new event's ``replaced`` count reflects
    the per-instrument tear-down (1 row replaced on the only
    instrument)."""

    review_session = _make_session(client, db)
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)

    response = generate_via_page_button(
        client, review_session.id, confirm_replace=True
    )
    assert response.status_code == 303

    events = list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.event_type == "assignments.generated")
            .order_by(AuditEvent.id.desc())
        ).scalars()
    )
    assert events[0].detail["counts"]["replaced"] == 1


def test_assignments_hub_renders_count_and_mode(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)

    empty = client.get(f"/operator/sessions/{review_session.id}/assignments")
    assert empty.status_code == 200
    # Page-level Generate button is now the materialise affordance.
    assert "Generate assignments" in empty.text
    # Per-instrument status block surfaces the pinned rule.
    assert "Full Matrix" in empty.text

    generate_via_page_button(client, review_session.id)
    populated = client.get(f"/operator/sessions/{review_session.id}/assignments")
    assert "Assignments preview" in populated.text
    # The per-instrument status table renders a Self review pill
    # (even when the instrument has zero self-review rows). Reads
    # the count via the ``data-self-review-count`` attribute so the
    # assertion is robust to formatting tweaks.
    assert 'data-self-review-count=' in populated.text
    # Show column: header renamed from "Filter" → "Show"; the
    # filter checkbox renders ``checked`` by default for any
    # instrument with generated rows so the post-Generate view
    # surfaces every materialised pair (the user's "all ticked"
    # rule). The row-count pill that used to sit before the
    # checkbox retired — that count moved to the new Included
    # column.
    assert "<th>Show</th>" in populated.text
    assert "<th>Included</th>" in populated.text
    assert "<th>Filter</th>" not in populated.text
    assert "data-show-pill=" not in populated.text
    assert "data-included-count=" in populated.text
    instrument_id = db.execute(
        select(Instrument.id).where(Instrument.session_id == review_session.id)
    ).scalars().first()
    show_cell = populated.text.split(
        f'data-filter-instrument="{instrument_id}"', 1
    )[1][:200]
    assert "checked" in show_cell


def test_assignments_hub_no_flash_banner_after_generate(
    client: TestClient, db: Session
) -> None:
    """Post-15B refinement: the blue "Assignments generated" flash
    banner retired. The redirect after Generate lands plain on the
    Assignments page; the status table is the only post-generate
    signal."""

    review_session = _make_session(client, db, code="no-flash")
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    response = generate_via_page_button(client, review_session.id)
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}/assignments"
    )
    body = client.get(response.headers["location"]).text
    assert 'id="generated-flash"' not in body
    assert "Assignments generated" not in body


def test_ready_session_preview_rows_render_alongside_show_script(
    client: TestClient, db: Session
) -> None:
    """On ready sessions the per-instrument status card still
    renders (matching the Instruments-page pattern: status info
    card stays first under chrome, yellow banner sits beneath).
    Self-review checkboxes are disabled — review is ongoing and
    flipping include flags from this surface would silently
    change live invitation eligibility. Show + Filter checkboxes
    remain interactive (they're pure client-side affordances).

    Pin: on a ready session, the status table renders, the self-
    review checkbox carries ``disabled``, the Show checkbox does
    not, and the early-return guard remains in place for the
    no-instruments edge case.
    """

    review_session = _make_session(client, db, code="ready-show")
    # Use literal Alice→Alice naming so the engine's email-vs-
    # ident self-review detection picks it up (mirrors
    # ``_seed_population_with_self_review`` in
    # ``test_assignments_operations_page.py``).
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
                b"RevieweeName,RevieweeEmail\nAlice,alice@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)
    # Flip to ready by direct write — the lifecycle transition
    # surface lives elsewhere and isn't this test's concern.
    review_session.status = "ready"
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    # Status table renders in ready state too.
    assert 'id="assignments-status-blocks"' in body
    assert "data-filter-instrument=" in body
    # The Show + Filter checkboxes are interactive (no disabled
    # attribute on the Show row).
    show_cell = body.split("data-filter-instrument=", 1)[1][:200]
    assert "disabled" not in show_cell
    # Self-review checkbox carries the disabled attribute.
    assert "data-self-review-instrument=" in body
    sr_cell = body.split("data-self-review-instrument=", 1)[1][:300]
    assert "disabled" in sr_cell
    # Preview pairs table renders for review.
    assert "data-row-instrument=" in body
    # Early-return guard still present (the no-checkboxes edge
    # case is still possible — e.g. a session with no
    # instruments — even if uncommon).
    assert "if (boxes.length === 0) return;" in body
    # The yellow ``card lock`` revert notice was retired with the
    # Next Action card State 6 workflow-stepper refresh — the
    # stepper's Revert to draft Primary now carries that affordance.
    assert 'class="card lock"' not in body


def test_non_operator_gets_403_on_assignments_hub_and_post(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="alice-only")

    bob_client = make_client(bob)
    hub = bob_client.get(f"/operator/sessions/{review_session.id}/assignments")
    assert hub.status_code == 403

    post = generate_via_page_button(bob_client, review_session.id)
    assert post.status_code == 403


def test_assignments_hub_truncates_large_pair_list(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=[f"r{i}@example.edu" for i in range(7)],
        reviewee_idents=[f"e{i}@example.edu" for i in range(31)],
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert "Showing first 200 of 217" in body
    assert "and 17 more" in body


def test_hub_renders_current_pairs_card_when_assignments_exist(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="hub-pairs")
    _seed_roster(
        client,
        review_session.id,
        reviewer_emails=["alice@example.edu"],
        reviewee_idents=["carol@example.edu"],
    )

    empty = client.get(f"/operator/sessions/{review_session.id}/assignments")
    assert "Assignments preview" not in empty.text

    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert "Assignments preview" in body
    assert "alice@example.edu" in body
    assert "carol@example.edu" in body


def test_hub_renders_per_slot_columns_with_visibility_toggles(
    client: TestClient, db: Session
) -> None:
    """15D PR 6b: pair_context columns read from the relationships
    table. Reviewer / reviewee tag toggles + Pair toggles drive
    column visibility on the preview table."""

    review_session = _make_session(client, db, code="hub-cols")
    reviewer_csv = (
        "ReviewerName,ReviewerEmail,ReviewerTag1\n"
        "Alice,alice@example.edu,senior\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={"file": ("r.csv", reviewer_csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    reviewee_csv = (
        "RevieweeName,RevieweeEmail,RevieweeTag2\n"
        "Carol,carol@example.edu,cohort-a\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={"file": ("e.csv", reviewee_csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    rel_csv = (
        "ReviewerEmail,RevieweeEmail,PairContextTag1\n"
        "alice@example.edu,carol@example.edu,bench-a\n"
    )
    client.post(
        f"/operator/sessions/{review_session.id}/relationships/import",
        files={"file": ("rel.csv", rel_csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text

    # Header carries every per-slot column even when the data is sparse.
    assert 'class="assignment-col col-rt1 rrw-sortable"' in body
    assert "Tag 1" in body
    assert 'class="assignment-col col-et2 rrw-sortable"' in body
    assert "Tag 2" in body
    assert 'class="assignment-col col-p1 rrw-sortable"' in body
    assert "Pair context 1" in body
    assert "col-a3" not in body
    assert 'data-sort-key="reviewer"' in body
    assert 'data-sort-key="reviewee"' in body
    assert 'data-sort-key="include"' in body
    assert 'data-sort-key="instrument"' in body

    # Per-slot cells render values from rosters + relationships.
    assert ">senior</td>" in body
    assert ">cohort-a</td>" in body
    assert ">bench-a</td>" in body

    # Toggle initial state — only the slots that have data are ticked.
    assert 'data-col-toggle="rt1"\n                       checked' in body
    assert 'data-col-toggle="et2"\n                       checked' in body
    assert 'data-col-toggle="p1"\n                       checked' in body
    assert 'data-col-toggle="rt2"\n                       checked' not in body
    assert 'data-col-toggle="p3"\n                       checked' not in body
