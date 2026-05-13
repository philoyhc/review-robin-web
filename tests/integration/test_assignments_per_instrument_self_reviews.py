"""Coverage for the per-instrument self-review surface on the
Assignments page status table (post-15B refinement sweep).

Three layers:

- ``assignments.self_review_breakdown_per_instrument`` — service
  helper that returns ``{instrument_id: (active, deactivated)}``
  for self-review rows.
- ``assignments.set_instrument_self_reviews_active`` — bulk flip
  scoped to one instrument; emits
  ``assignments.instrument_self_reviews_active_set`` audit event.
- ``InstrumentStatusBlock.self_review_checkbox_state`` — the
  view-shape's tri-state signal driving the checkbox render
  (``"checked"`` / ``"unchecked"`` / ``"indeterminate"``).
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import assignments as assignments_service
from app.services.instruments import ensure_default_instrument
from app.web.views import build_assignments_page_context


def _seed_multi_instrument(
    db: Session, *, code: str = "sr-multi"
) -> tuple[
    User, ReviewSession, Instrument, Instrument, Reviewer, Reviewee
]:
    """Two instruments + an Alice reviewer / Alice reviewee pair
    (the self-review). Caller wires per-instrument Assignment
    rows + their include flags."""
    user = User(email="op@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="SR", code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    inst_a = ensure_default_instrument(db, review_session)
    inst_b = Instrument(
        session_id=review_session.id, name="Peer survey", order=2
    )
    db.add(inst_b)
    db.flush()
    alice_r = Reviewer(
        session_id=review_session.id,
        name="Alice",
        email="alice@example.edu",
    )
    alice_e = Reviewee(
        session_id=review_session.id,
        name="Alice",
        email_or_identifier="alice@example.edu",
    )
    db.add_all([alice_r, alice_e])
    db.flush()
    db.commit()
    return user, review_session, inst_a, inst_b, alice_r, alice_e


def _self_review(
    db: Session,
    *,
    review_session: ReviewSession,
    instrument: Instrument,
    reviewer: Reviewer,
    reviewee: Reviewee,
    include: bool,
) -> Assignment:
    a = Assignment(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=include,
    )
    db.add(a)
    db.flush()
    db.commit()
    return a


def test_breakdown_returns_per_instrument_counts(db: Session) -> None:
    """``self_review_breakdown_per_instrument`` returns
    ``(active, deactivated)`` tuples keyed by instrument_id —
    instruments with no self-review rows are absent from the dict."""

    user, review_session, inst_a, inst_b, alice_r, alice_e = (
        _seed_multi_instrument(db, code="sr-counts")
    )
    _self_review(
        db,
        review_session=review_session,
        instrument=inst_a,
        reviewer=alice_r,
        reviewee=alice_e,
        include=True,
    )
    _self_review(
        db,
        review_session=review_session,
        instrument=inst_b,
        reviewer=alice_r,
        reviewee=alice_e,
        include=False,
    )

    out = assignments_service.self_review_breakdown_per_instrument(
        db, review_session.id
    )

    assert out == {
        inst_a.id: (1, 0),
        inst_b.id: (0, 1),
    }


def test_set_instrument_self_reviews_active_scopes_to_one_instrument(
    db: Session,
) -> None:
    """``set_instrument_self_reviews_active`` flips only the named
    instrument's self-review rows; other instruments' rows survive
    untouched."""

    user, review_session, inst_a, inst_b, alice_r, alice_e = (
        _seed_multi_instrument(db, code="sr-scoped")
    )
    sr_a = _self_review(
        db,
        review_session=review_session,
        instrument=inst_a,
        reviewer=alice_r,
        reviewee=alice_e,
        include=True,
    )
    sr_b = _self_review(
        db,
        review_session=review_session,
        instrument=inst_b,
        reviewer=alice_r,
        reviewee=alice_e,
        include=True,
    )

    flipped = assignments_service.set_instrument_self_reviews_active(
        db,
        review_session=review_session,
        instrument_id=inst_a.id,
        user=user,
        active=False,
        correlation_id="sr-scoped-c1",
    )

    assert flipped == 1
    db.refresh(sr_a)
    db.refresh(sr_b)
    assert sr_a.include is False
    assert sr_b.include is True  # inst_b untouched


def test_set_instrument_self_reviews_active_emits_audit_event(
    db: Session,
) -> None:
    """The bulk-flip emits an
    ``assignments.instrument_self_reviews_active_set`` event with
    ``refs.instrument_id`` + ``counts.flipped`` +
    ``context.active``."""

    user, review_session, inst_a, inst_b, alice_r, alice_e = (
        _seed_multi_instrument(db, code="sr-audit")
    )
    _self_review(
        db,
        review_session=review_session,
        instrument=inst_a,
        reviewer=alice_r,
        reviewee=alice_e,
        include=True,
    )

    assignments_service.set_instrument_self_reviews_active(
        db,
        review_session=review_session,
        instrument_id=inst_a.id,
        user=user,
        active=False,
        correlation_id="sr-audit-c1",
    )

    from sqlalchemy import select

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type
            == "assignments.instrument_self_reviews_active_set",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = event.detail or {}
    assert detail["refs"]["instrument_id"] == inst_a.id
    assert detail["counts"]["flipped"] == 1
    assert detail["context"]["active"] is False


def test_status_block_indeterminate_state_when_mixed(db: Session) -> None:
    """``InstrumentStatusBlock.self_review_checkbox_state`` is
    ``"indeterminate"`` when an instrument has a mix of
    include=true and include=false self-review rows. The inline JS
    on the Assignments page reads ``data-self-review-state`` to
    set the HTML5 ``indeterminate`` property on the checkbox."""

    user, review_session, inst_a, inst_b, alice_r, alice_e = (
        _seed_multi_instrument(db, code="sr-mixed")
    )
    # Add a second reviewer so the self-review-rows-per-instrument
    # count is > 1 and we can have a mixed state on inst_a.
    bob_r = Reviewer(
        session_id=review_session.id,
        name="Bob",
        email="bob@example.edu",
    )
    bob_e = Reviewee(
        session_id=review_session.id,
        name="Bob",
        email_or_identifier="bob@example.edu",
    )
    db.add_all([bob_r, bob_e])
    db.flush()
    _self_review(
        db,
        review_session=review_session,
        instrument=inst_a,
        reviewer=alice_r,
        reviewee=alice_e,
        include=True,
    )
    _self_review(
        db,
        review_session=review_session,
        instrument=inst_a,
        reviewer=bob_r,
        reviewee=bob_e,
        include=False,
    )

    ctx = build_assignments_page_context(db, review_session)
    by_id = {b.instrument_id: b for b in ctx.status_blocks}

    inst_a_block = by_id[inst_a.id]
    assert inst_a_block.self_review_total == 2
    assert inst_a_block.self_review_active_count == 1
    assert inst_a_block.self_review_checkbox_state == "indeterminate"

    # inst_b has zero self-review rows → checkbox state defaults to
    # ``"checked"`` (no rows to toggle; the column omits the
    # checkbox entirely in the template).
    inst_b_block = by_id[inst_b.id]
    assert inst_b_block.self_review_total == 0


def test_status_block_unchecked_state_when_all_deactivated(
    db: Session,
) -> None:
    """All self-review rows on an instrument set to
    ``include=False`` → ``self_review_checkbox_state == "unchecked"``."""

    user, review_session, inst_a, inst_b, alice_r, alice_e = (
        _seed_multi_instrument(db, code="sr-all-off")
    )
    _self_review(
        db,
        review_session=review_session,
        instrument=inst_a,
        reviewer=alice_r,
        reviewee=alice_e,
        include=False,
    )

    ctx = build_assignments_page_context(db, review_session)
    block = next(b for b in ctx.status_blocks if b.instrument_id == inst_a.id)
    assert block.self_review_checkbox_state == "unchecked"


def test_status_block_uses_short_label_when_available(
    db: Session,
) -> None:
    """The Instrument column on the status table renders
    ``instrument.short_label`` when set, ``instrument.name``
    otherwise (mirrors the reviewer surface page-button label
    convention from Segment 11D)."""

    user, review_session, inst_a, inst_b, _, _ = _seed_multi_instrument(
        db, code="sr-label"
    )
    inst_b.short_label = "peer"
    db.flush()
    db.commit()

    ctx = build_assignments_page_context(db, review_session)
    by_id = {b.instrument_id: b for b in ctx.status_blocks}

    # inst_a has no short_label → falls back to ``instrument.name``.
    assert by_id[inst_a.id].instrument_label == inst_a.name
    # inst_b's short_label wins.
    assert by_id[inst_b.id].instrument_label == "peer"


def test_status_block_reports_included_count_per_instrument(
    db: Session,
) -> None:
    """The **Included** column on the status table reports the
    count of rows on that instrument with ``include=True`` (the
    counterpart of the **Generated** total). Drives the new
    ``data-included-count`` pill."""

    user, review_session, inst_a, inst_b, alice_r, alice_e = (
        _seed_multi_instrument(db, code="sr-included")
    )
    bob_r = Reviewer(
        session_id=review_session.id,
        name="Bob",
        email="bob@example.edu",
    )
    bob_e = Reviewee(
        session_id=review_session.id,
        name="Bob",
        email_or_identifier="bob@example.edu",
    )
    db.add_all([bob_r, bob_e])
    db.flush()
    # inst_a: 1 included, 1 excluded → included_count=1
    _self_review(
        db,
        review_session=review_session,
        instrument=inst_a,
        reviewer=alice_r,
        reviewee=alice_e,
        include=True,
    )
    _self_review(
        db,
        review_session=review_session,
        instrument=inst_a,
        reviewer=bob_r,
        reviewee=bob_e,
        include=False,
    )
    # inst_b: 1 included → included_count=1
    _self_review(
        db,
        review_session=review_session,
        instrument=inst_b,
        reviewer=alice_r,
        reviewee=alice_e,
        include=True,
    )

    ctx = build_assignments_page_context(db, review_session)
    by_id = {b.instrument_id: b for b in ctx.status_blocks}

    assert by_id[inst_a.id].generated_count == 2
    assert by_id[inst_a.id].included_count == 1
    assert by_id[inst_b.id].generated_count == 1
    assert by_id[inst_b.id].included_count == 1


def test_self_review_pill_class_tracks_checkbox_state(
    client: TestClient, db: Session
) -> None:
    """Self review count pill: ``pill-info`` (blue) when self-
    reviews are included for that instrument (checkbox ticked);
    ``pill-warning`` (yellow) when not (unchecked or
    indeterminate)."""

    # Use the existing integration fixture to seed a session with
    # an Alice→Alice self-review pair, then exercise the per-
    # instrument toggle to flip include states and re-fetch the
    # rendered page.
    from tests.integration.test_assignments_operations_page import (
        _generate_with_self_reviews,
        _make_session,
        _seed_population_with_self_review,
        _self_review_instrument_id,
    )

    review_session = _make_session(client, db, code="sr-pill")
    _seed_population_with_self_review(client, review_session.id)
    _generate_with_self_reviews(client, db, review_session.id)
    instrument_id = _self_review_instrument_id(db, review_session.id)

    # Default ``self_reviews_active=True`` → self-review row lands
    # include=True → state "checked" → blue pill.
    checked_body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    checked_pill = checked_body.split(
        f'data-self-review-count="{instrument_id}"', 1
    )[0][-80:]
    assert "pill-info" in checked_pill
    assert "pill-warning" not in checked_pill

    # Flip to unticked → state "unchecked" → yellow pill.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/{instrument_id}/self-reviews/active",
        data={"active": "false"},
        follow_redirects=False,
    )
    unticked_body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    unticked_pill = unticked_body.split(
        f'data-self-review-count="{instrument_id}"', 1
    )[0][-80:]
    assert "pill-warning" in unticked_pill
    assert "pill-info" not in unticked_pill
