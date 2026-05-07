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


def test_build_quick_setup_context_returns_four_slots(
    client: TestClient, db: Session
) -> None:
    """The view-shape adapter returns the four slots in the
    canonical order — Reviewers, Reviewees, Assignments, Session
    settings. After Segment 11J PR A, Reviewers and Reviewees are
    wired live; Assignments and Settings remain inert pending
    Segment 11J PR B / Segment 12A PR 6."""

    review_session = _make_session(client, db, code="qs-shape")
    context = views.build_quick_setup_context(db, review_session)

    assert [slot.key for slot in context.slots] == [
        "reviewers",
        "reviewees",
        "assignments",
        "settings",
    ]
    by_key = {slot.key: slot for slot in context.slots}
    # PR A + PR B — Reviewers, Reviewees, and Assignments are live.
    assert by_key["reviewers"].is_wired is True
    assert by_key["reviewers"].wire_url == (
        f"/operator/sessions/{review_session.id}/quick-setup/reviewers"
    )
    assert by_key["reviewers"].coming_in is None
    assert by_key["reviewees"].is_wired is True
    assert by_key["reviewees"].wire_url == (
        f"/operator/sessions/{review_session.id}/quick-setup/reviewees"
    )
    assert by_key["assignments"].is_wired is True
    assert by_key["assignments"].wire_url == (
        f"/operator/sessions/{review_session.id}/quick-setup/assignments"
    )
    assert by_key["assignments"].coming_in is None
    # Settings remains inert pending Segment 12A PR 6.
    assert by_key["settings"].is_wired is False
    assert by_key["settings"].coming_in == "Wired in Segment 12A PR 6"
    # Default state is not disabled in draft.
    assert context.is_disabled is False


def test_quick_setup_count_summary_reflects_population(
    client: TestClient, db: Session
) -> None:
    """The slot count summary line surfaces the live population
    so the operator can see at a glance what's on file."""

    empty = _make_session(client, db, code="qs-empty")
    empty_ctx = views.build_quick_setup_context(db, empty)
    by_key = {slot.key: slot for slot in empty_ctx.slots}
    assert by_key["reviewers"].count == 0
    assert by_key["reviewers"].count_summary == "none yet"
    assert by_key["assignments"].count_summary == "none yet"

    populated = _seed_pair(
        client, db, code="qs-populated", reviewer_email="r@example.edu"
    )
    populated_ctx = views.build_quick_setup_context(db, populated)
    populated_by_key = {slot.key: slot for slot in populated_ctx.slots}
    assert populated_by_key["reviewers"].count == 1
    assert populated_by_key["reviewers"].count_summary == "1 currently"
    # Assignments slot includes the stored rule label (lowercase enum
    # value as Text — ``full_matrix``).
    assert populated_by_key["assignments"].count >= 1
    assert "full_matrix" in populated_by_key["assignments"].count_summary


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


def test_quick_setup_slot_assignments_uses_rule_or_csv_mode(
    client: TestClient, db: Session
) -> None:
    """Slot 3 carries ``mode == "rule_or_csv"`` so the partial
    renders the rule selector + CSV upload toggle. Slots 1, 2,
    and 4 use the simpler ``"file_upload"`` shape."""

    review_session = _make_session(client, db, code="qs-modes")
    context = views.build_quick_setup_context(db, review_session)
    by_key = {slot.key: slot for slot in context.slots}

    assert by_key["reviewers"].mode == "file_upload"
    assert by_key["reviewees"].mode == "file_upload"
    assert by_key["assignments"].mode == "rule_or_csv"
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

    for key in ("reviewers", "reviewees", "assignments", "settings"):
        assert f'data-wire-target="quick-setup-{key}"' in body


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
        "This will replace any existing reviewers, reviewees,"
        in body
    )
    # No per-slot ``banner-warning`` confirm-banners anymore — the
    # global checkbox is the single confirmation surface.
    for key in ("reviewers", "reviewees", "assignments", "settings"):
        assert f"quick-setup-{key}-confirm-banner" not in body
    # Error-banner containers per slot stay (parse / lifecycle / etc.).
    for key in ("reviewers", "reviewees", "assignments", "settings"):
        assert f'id="quick-setup-{key}-error-banner"' in body


def test_quick_setup_assignments_slot_has_exclude_self_review_checkbox(
    client: TestClient, db: Session
) -> None:
    """The Assignments slot now carries an inert
    ``exclude_self_review`` checkbox alongside the rule selector
    and CSV upload. The checkbox is ``disabled`` until 11J PR B
    wires the slot."""

    review_session = _make_session(client, db, code="qs-exclude")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    assert 'name="exclude_self_review"' in body
    assert "Exclude self-review" in body


def test_quick_setup_assignments_slot_drops_segment_13_caption(
    client: TestClient, db: Session
) -> None:
    """The "More rules ship with Segment 13" caption is removed
    from the Assignments slot — the rule menu's expansion is
    Segment 13's concern, but the caption was a forward-looking
    note that got noisy on Home."""

    review_session = _make_session(client, db, code="qs-no-caption")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    assert "Segment 13" not in body
    assert "More rules ship" not in body


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
    """The Quick Setup card body splits into three regions:

    1. A ``.quick-setup-top-grid`` 2-column grid: Reviewers +
       Reviewees stacked in the left column, Assignments alone
       in the right column.
    2. A ``.quick-setup-divider`` horizontal rule.
    3. The Session settings slot full-width below the
       divider, outside the grid.

    Pin the structural contract so 11J / 12A wiring patches can
    rely on it.
    """

    review_session = _make_session(client, db, code="qs-grid")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    grid_start = body.find('class="quick-setup-top-grid"')
    divider_pos = body.find('class="quick-setup-divider"')
    config_pos = body.find('id="quick-setup-settings"')
    reviewers_pos = body.find('id="quick-setup-reviewers"')
    reviewees_pos = body.find('id="quick-setup-reviewees"')
    assignments_pos = body.find('id="quick-setup-assignments"')

    # All anchors found.
    assert -1 not in (
        grid_start,
        divider_pos,
        config_pos,
        reviewers_pos,
        reviewees_pos,
        assignments_pos,
    )

    # Reviewers + Reviewees + Assignments live inside the grid;
    # Session settings sits after the divider.
    assert grid_start < reviewers_pos < reviewees_pos
    assert reviewees_pos < assignments_pos
    assert assignments_pos < divider_pos
    assert divider_pos < config_pos

    # Two ``.quick-setup-top-grid-col`` wrappers — left column
    # holds the two reviewer-side slots, right column holds
    # Assignments.
    assert body.count('class="quick-setup-top-grid-col"') == 2
