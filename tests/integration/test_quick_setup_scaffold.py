"""Tests for the Segment 11H PR A Quick Setup card scaffold.

The scaffold replaces the ``placeholder_card(id="quick-setup")``
stub with the full four-slot layout from
``spec/quick_setup_card_spec.md``. Every interactive control is
inert until Segment 11J wires the slots; these tests pin the
visual + DOM contract so 11J's wiring patches don't have to
worry about a colliding markup tweak.
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
    client: TestClient, db: Session, *, code: str = "qs-scaffold"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Scaffold", "code": code, "description": "d"},
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


def test_build_quick_setup_context_returns_three_slots(
    client: TestClient, db: Session
) -> None:
    """15D PR 7a retired the legacy Assignments slot from Quick Setup
    — generation no longer runs from this card. The slot list
    shrinks to Reviewers, Reviewees, Session settings. PR 7c
    re-introduces a Relationships slot at position 3."""

    review_session = _make_session(client, db, code="qs-shape")
    context = views.build_quick_setup_context(db, review_session)

    assert [slot.key for slot in context.slots] == [
        "reviewers",
        "reviewees",
        "settings",
    ]
    by_key = {slot.key: slot for slot in context.slots}
    assert by_key["reviewers"].is_wired is True
    assert by_key["reviewers"].wire_url == (
        f"/operator/sessions/{review_session.id}/quick-setup/reviewers"
    )
    assert by_key["reviewers"].coming_in is None
    assert by_key["reviewees"].is_wired is True
    assert by_key["reviewees"].wire_url == (
        f"/operator/sessions/{review_session.id}/quick-setup/reviewees"
    )
    # Settings remains inert pending Segment 12A PR 6.
    assert by_key["settings"].is_wired is False
    assert by_key["settings"].coming_in == "Wired in Segment 12A PR 6"
    # Default state is not disabled in draft.
    assert context.is_disabled is False


def test_quick_setup_count_reflects_population(
    client: TestClient, db: Session
) -> None:
    """The slot ``count`` field surfaces the live population so other
    code paths can branch on whether the slot is empty."""

    empty = _make_session(client, db, code="qs-empty")
    empty_ctx = views.build_quick_setup_context(db, empty)
    by_key = {slot.key: slot for slot in empty_ctx.slots}
    assert by_key["reviewers"].count == 0
    assert by_key["reviewees"].count == 0

    populated = _seed_pair(
        client, db, code="qs-populated", reviewer_email="r@example.edu"
    )
    populated_ctx = views.build_quick_setup_context(db, populated)
    populated_by_key = {slot.key: slot for slot in populated_ctx.slots}
    assert populated_by_key["reviewers"].count == 1


def test_quick_setup_disables_when_session_is_activated(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """An Activated session marks Quick Setup unavailable
    (``is_disabled=True``). Description copy is the single static
    line covering both gates (draft-only + no-responses)."""

    operator = make_client(alice)
    review_session = _seed_pair(
        operator, db, code="qs-activated", reviewer_email="r@example.edu"
    )
    _activate(operator, db, review_session)

    context = views.build_quick_setup_context(db, review_session)

    assert context.is_disabled is True
    assert (
        "Available only when session is in draft mode and does not "
        "have any responses." in context.description
    )


def test_quick_setup_unavailable_when_responses_exist_even_on_draft(
    client: TestClient, db: Session, monkeypatch
) -> None:
    """A draft session that carries persisted responses (e.g. from a
    prior activation cycle that bumped back to draft) is treated as
    unavailable for Quick Setup. The route layer's
    ``_require_response_loss_ack`` already rejects submits in this
    case; the card-level signal makes the constraint visible by
    locking the body and hiding the Lock / Unlock toggle."""

    from app.services import responses as responses_service

    review_session = _make_session(client, db, code="qs-has-responses")
    # The session is freshly created (draft, no responses). Stub the
    # response-count helper so the context-builder treats it as if
    # responses were persisted.
    monkeypatch.setattr(
        responses_service,
        "session_response_count",
        lambda db, session_id: 1,
    )
    context = views.build_quick_setup_context(db, review_session)
    assert context.is_disabled is True
    assert context.is_locked is True
    assert context.show_lock_toggle is False


def test_quick_setup_slot_modes_all_file_upload(
    client: TestClient, db: Session
) -> None:
    """Post-15D PR 7a every slot is plain ``file_upload`` — the
    legacy ``rule_or_csv`` mode retired with the Assignments slot.
    PR 7c re-introduces a Relationships slot in the same
    file-upload mode."""

    review_session = _make_session(client, db, code="qs-modes")
    context = views.build_quick_setup_context(db, review_session)
    by_key = {slot.key: slot for slot in context.slots}

    assert by_key["reviewers"].mode == "file_upload"
    assert by_key["reviewees"].mode == "file_upload"
    assert by_key["settings"].mode == "file_upload"


def test_quick_setup_dom_carries_wire_target_attributes(
    client: TestClient, db: Session
) -> None:
    """Each slot's wrapping ``<section>`` carries
    ``data-wire-target="quick-setup-{key}"`` so Segment 11J's
    wiring patches can locate the slot without a CSS-selector
    contract."""

    review_session = _make_session(client, db, code="qs-wire-targets")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    for key in ("reviewers", "reviewees", "settings"):
        assert f'data-wire-target="quick-setup-{key}"' in body
    # Assignments slot retired in 15D PR 7a.
    assert 'data-wire-target="quick-setup-assignments"' not in body


def test_quick_setup_card_level_replacement_checkbox_renders(
    client: TestClient, db: Session
) -> None:
    """Replacement-confirmation moved from per-slot inline banners
    to a single card-level checkbox above the slot grid. The
    checkbox state mirrors into each form's hidden ``confirm_replace``
    input via inline JS on submit."""

    review_session = _make_session(client, db, code="qs-confirm-checkbox")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    assert 'id="quick-setup-confirm-replace-toggle"' in body
    assert (
        "Yes, replace existing reviewers, reviewees"
        in body
    )
    # Error-banner containers per slot stay (parse / lifecycle / etc.).
    for key in ("reviewers", "reviewees", "settings"):
        assert f'id="quick-setup-{key}-error-banner"' in body
    # Retired slot's banner container is gone.
    assert 'id="quick-setup-assignments-error-banner"' not in body


def test_quick_setup_locks_by_default_in_draft(
    client: TestClient, db: Session
) -> None:
    """Per the Lock / Unlock requirement, the card defaults to
    ``locked`` whenever the session is editable so the operator
    must explicitly Unlock before changing setup. The locked
    state greys the body via ``.quick-setup-body.locked``; the
    Lock / Unlock button sits outside the locked wrapper so it
    stays vivid."""

    review_session = _make_session(client, db, code="qs-locked")
    context = views.build_quick_setup_context(db, review_session)
    body = client.get(f"/operator/sessions/{review_session.id}").text

    assert context.is_disabled is False
    assert context.is_locked is True
    assert 'class="quick-setup-body locked"' in body
    # Footer button renders with the Unlock label (since locked).
    assert 'id="quick-setup-lock-toggle"' in body
    assert ">Unlock</button>" in body


def test_quick_setup_lock_toggle_hidden_when_session_activated(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Quick Setup is available only on ``draft`` AND when no
    persisted responses exist. On any other state — here ``ready`` —
    the card is permanently locked and the Lock / Unlock toggle is
    hidden entirely, so the operator can't even cosmetically unlock
    something the route layer would reject."""

    operator = make_client(alice)
    review_session = _seed_pair(
        operator, db, code="qs-activated-toggle", reviewer_email="r@example.edu"
    )
    _activate(operator, db, review_session)

    context = views.build_quick_setup_context(db, review_session)
    body = operator.get(f"/operator/sessions/{review_session.id}").text

    # Permanent-locked, no-toggle state.
    assert context.is_disabled is True
    assert context.is_locked is True
    assert context.show_lock_toggle is False
    assert 'id="quick-setup-lock-toggle"' not in body
    # ``.card.disabled`` is retired in favour of the body-greying.
    assert 'class="card disabled"' not in body
    assert 'class="quick-setup-body locked"' in body


def test_quick_setup_card_lives_in_right_column_under_session_details(
    client: TestClient, db: Session
) -> None:
    """Per ``spec/session_home.md`` the page-level card order is:

    1. Next Action (left column, top)
    2. Extract Data (left column, middle)
    3. Danger Zone (left column, bottom)
    4. Session Details (right column, top)
    5. Quick Setup (right column, bottom)

    Pin the DOM order so a template tweak can't silently regress
    the column placement. Mobile DOM collapse follows source
    order: Next Action → Extract Data → Danger Zone → Session
    Details → Quick Setup.
    """

    review_session = _make_session(client, db, code="qs-card-order")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    next_action_pos = body.find('id="next-action"')
    extract_data_pos = body.find('id="extract-data"')
    danger_zone_pos = body.find('id="danger-zone"')
    session_details_pos = body.find("<h2>Session Details</h2>")
    quick_setup_pos = body.find('id="quick-setup"')

    # All anchors found.
    assert -1 not in (
        next_action_pos,
        extract_data_pos,
        danger_zone_pos,
        session_details_pos,
        quick_setup_pos,
    )

    # Source order = mobile DOM collapse order = page reading order.
    assert (
        next_action_pos
        < extract_data_pos
        < danger_zone_pos
        < session_details_pos
        < quick_setup_pos
    )


def test_quick_setup_top_grid_layout(
    client: TestClient, db: Session
) -> None:
    """Post-15D PR 7a the card collapses to a single column —
    Reviewers, Reviewees, Session settings stacked. The legacy
    Assignments slot (which lived in the second column) retired."""

    review_session = _make_session(client, db, code="qs-grid")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    grid_start = body.find('class="quick-setup-top-grid"')
    config_pos = body.find('id="quick-setup-settings"')
    reviewers_pos = body.find('id="quick-setup-reviewers"')
    reviewees_pos = body.find('id="quick-setup-reviewees"')

    assert -1 not in (grid_start, config_pos, reviewers_pos, reviewees_pos)
    assert '<hr class="quick-setup-divider">' not in body

    # Order: Reviewers → Reviewees → Settings.
    assert grid_start < reviewers_pos < reviewees_pos < config_pos
    # Assignments slot is gone.
    assert 'id="quick-setup-assignments"' not in body
    # Single column wrapper.
    assert body.count('class="quick-setup-top-grid-col"') == 1
