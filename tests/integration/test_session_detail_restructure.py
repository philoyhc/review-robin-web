"""Tests for the Segment 9.4B session-detail restructure.

Covers:
- Setup-row view helper output.
- Four-card layout on ``GET /operator/sessions/{id}``.
- Inline validate-summary card via ``?validated=1``.
- ``/validate`` page activate-form removed.
- ``POST /delete-data`` wipes responses, preserves setup, audits, and is
  allowed in ``ready``.
- Edit-lock visibility on the Session card and Danger Zone.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    AuditEvent,
    Reviewee,
    Reviewer,
    Response,
    ReviewSession,
)
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)
from app.web import views


def _make_session(
    client: TestClient, db: Session, *, code: str = "restruct-test"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code, "description": "d"},
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


def _activate(client: TestClient, db: Session, review_session: ReviewSession) -> None:
    client.get(f"/operator/sessions/{review_session.id}/assignments?validated=1")
    response = client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(review_session)


# ---------------------------------------------------------------------------
# Slice 1 — view helper + four-card render
# ---------------------------------------------------------------------------


def test_build_setup_rows_returns_expected_shape(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(
        client, db, code="rows", reviewer_email="r@example.edu"
    )

    rows = views.build_setup_rows(db, review_session)
    by_label = {r.label: r for r in rows}

    assert list(by_label.keys()) == [
        "Reviewers",
        "Reviewees",
        "Relationships",
        "Instruments",
        "Email Invites",
    ]
    assert by_label["Reviewers"].value == "Number of reviewers: 1"
    assert by_label["Reviewers"].manage_url.endswith("/reviewers")
    assert by_label["Reviewers"].manage_disabled is False
    assert by_label["Instruments"].manage_disabled is False
    assert by_label["Instruments"].manage_url.endswith("/instruments")
    assert by_label["Email Invites"].manage_disabled is False
    assert by_label["Email Invites"].manage_url.endswith("/setupinvite")


def test_session_detail_renders_session_layout(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(
        client, db, code="layout-cards", reviewer_email="r@example.edu"
    )

    response = client.get(f"/operator/sessions/{review_session.id}")
    body = response.text

    assert response.status_code == 200
    # 18R Item 4 Slice 5b — the old read-only Session Details metadata card
    # is retired; its markers (session-detail-code, the name-in-h2) are gone.
    # Session identity now lives on the #session-config card.
    assert 'class="session-detail-code' not in body
    assert 'id="session-config"' in body
    assert "<h2>Session details</h2>" in body
    # Per spec/workflow_card.md, the Workflow card
    # back to Session Home (full-width, just below the chrome).
    assert 'id="next-action"' in body
    assert "<h2>Workflow</h2>" in body
    assert "<h2>Run Session</h2>" not in body
    # 18R Item 4 Slice 5 — Danger Zone is wired on Session Home (bottom
    # right), relocated from the retired Edit page.
    assert 'id="danger-zone"' in body
    # The standalone "Session Setup" card was retired — its five Manage
    # links live in the chrome top-nav now (see chrome partial), so the
    # body no longer needs an in-page card duplicating them.
    assert "<h2>Session Setup</h2>" not in body
    # Legacy ad-hoc layout markers are gone:
    assert "Run setup validation" not in body
    assert "Validate &amp; activate" not in body
    assert "Validate & activate" not in body


def test_session_detail_description_preserves_line_breaks(
    client: TestClient, db: Session
) -> None:
    """A multi-paragraph session description renders in the #session-config
    display value with the ``config-value-multiline`` styling hook
    (``white-space: pre-wrap``) so the operator's line breaks survive
    instead of collapsing to whitespace. (18R Item 4 Slice 5b — the old
    ``session-detail-description`` card was retired.)"""
    description = "First paragraph.\n\nSecond paragraph."
    response = client.post(
        "/operator/sessions",
        data={
            "name": "Multi-para",
            "code": "multi-desc",
            "description": description,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "multi-desc")
    ).scalar_one()

    body = client.get(f"/operator/sessions/{review_session.id}").text
    assert 'class="config-value config-value-multiline"' in body
    # The newline-bearing text reaches the page verbatim; the CSS
    # ``white-space: pre-wrap`` renders the breaks.
    assert description in body


def test_setup_table_renders_manage_links(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="disabled-manage")

    body = client.get(f"/operator/sessions/{review_session.id}").text

    # All five Manage buttons are real anchors after 9.4C
    assert (
        f'href="/operator/sessions/{review_session.id}/reviewers"' in body
    )
    assert (
        f'href="/operator/sessions/{review_session.id}/reviewees"' in body
    )
    assert (
        f'href="/operator/sessions/{review_session.id}/assignments"' in body
    )
    assert (
        f'href="/operator/sessions/{review_session.id}/instruments"' in body
    )
    assert (
        f'href="/operator/sessions/{review_session.id}/setupinvite"' in body
    )


# ---------------------------------------------------------------------------
# Slice 2 — inline validate-summary via ?validated=1
# ---------------------------------------------------------------------------


def test_session_detail_no_validate_summary_by_default(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(
        client, db, code="no-summary", reviewer_email="r@example.edu"
    )
    body = client.get(f"/operator/sessions/{review_session.id}").text
    # Populated draft session — the Workflow card surfaces State 2
    # (Validate-not-yet-run), so no validation-summary pill row
    # renders and no direct /activate form is emitted (the
    # super-button POSTs to /workflow/activate instead).
    assert "<h2>Workflow</h2>" in body
    assert "<h2>Validation summary</h2>" not in body
    # The only path to /activate is the warnings-detour banner on
    # the Validate page; Session Home's Workflow card never emits
    # a direct /activate form.
    assert 'id="next-action-activate-form"' not in body


def test_validate_page_activate_form_removed(
    client: TestClient, db: Session
) -> None:
    """The Validate page itself does not host an Activate form —
    activation lives on Session Home (or via the warnings detour
    when present, which posts from /validate?activate=1)."""
    review_session = _seed_pair(
        client, db, code="no-activate-form", reviewer_email="r@example.edu"
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    assert (
        f'action="/operator/sessions/{review_session.id}/activate"'
        not in body
    )
    # Setup-coverage card surfaces the inventory.
    assert "Setup coverage" in body


# ---------------------------------------------------------------------------
# Slice 3 — Delete Data
# ---------------------------------------------------------------------------


def _seed_responses(client: TestClient, db: Session) -> tuple[ReviewSession, int]:
    """Activate the seeded session and have the reviewer save a draft.

    Returns ``(review_session, response_count)``.
    """
    review_session = _seed_pair(
        client, db, code="del-data", reviewer_email="rae@example.edu"
    )
    _activate(client, db, review_session)

    rae = AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae",
        provider="aad",
    )

    from app.auth.identity import get_current_user
    from app.db.session import get_db
    from app.main import app

    def override_user() -> AuthenticatedUser:
        return rae

    def override_db():
        yield db

    # Swap in the reviewer's identity for the save call only.
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        rae_client = TestClient(app)
        assignment = db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalar_one()
        response = rae_client.post(
            f"/me/sessions/{review_session.id}/1/save",
            data={
                f"response[{assignment.id}][rating]": "4",
                f"response[{assignment.id}][comments]": "ok",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
    finally:
        # Restore the operator override so the rest of the test sees alice.
        app.dependency_overrides.clear()

    response_count = db.execute(
        select(Response)
        .join(Assignment, Response.assignment_id == Assignment.id)
        .where(Assignment.session_id == review_session.id)
    ).all()
    return review_session, len(response_count)


def test_delete_data_wipes_responses_and_preserves_setup(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session, count_before = _seed_responses(operator, db)
    assert count_before > 0

    # Re-arm the operator client after _seed_responses cleared overrides.
    operator = make_client(alice)
    response = operator.post(
        f"/operator/sessions/{review_session.id}/delete-data",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    # Responses gone for this session
    remaining = db.execute(
        select(Response)
        .join(Assignment, Response.assignment_id == Assignment.id)
        .where(Assignment.session_id == review_session.id)
    ).all()
    assert remaining == []

    # Setup intact
    assert (
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        ).first()
        is not None
    )
    assert (
        db.execute(
            select(Reviewee).where(Reviewee.session_id == review_session.id)
        ).first()
        is not None
    )
    assert (
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).first()
        is not None
    )

    audit = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.deleted_all")
    ).scalar_one()
    assert audit.detail["counts"]["deleted"] == count_before
    assert audit.session_id == review_session.id


def test_edit_session_details_succeeds_with_responses_present(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Editing session metadata is non-destructive — ``update_session``
    never deletes responses — so the edit form must not be gated
    behind a response-loss acknowledgement, even on a session that
    holds responses."""
    operator = make_client(alice)
    review_session, count_before = _seed_responses(operator, db)
    assert count_before > 0

    operator = make_client(alice)
    # Revert ready → draft so the lifecycle-gated edit form is reachable.
    revert = operator.post(
        f"/operator/sessions/{review_session.id}/revert",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert revert.status_code == 303

    response = operator.post(
        f"/operator/sessions/{review_session.id}/edit",
        data={"name": "Renamed Session", "code": "renamed-code"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    db.refresh(review_session)
    assert review_session.name == "Renamed Session"
    assert review_session.code == "renamed-code"

    # The edit left every response untouched.
    remaining = db.execute(
        select(Response)
        .join(Assignment, Response.assignment_id == Assignment.id)
        .where(Assignment.session_id == review_session.id)
    ).all()
    assert len(remaining) == count_before


def test_delete_data_requires_confirm(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(
        client, db, code="confirm-req", reviewer_email="r@example.edu"
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/delete-data",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 400

    # No audit event written
    rows = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "responses.deleted_all"
        )
    ).all()
    assert rows == []


def test_delete_data_allowed_in_ready_status(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session, count_before = _seed_responses(operator, db)
    db.refresh(review_session)
    assert review_session.status == "ready"

    operator = make_client(alice)
    response = operator.post(
        f"/operator/sessions/{review_session.id}/delete-data",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    audit = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.deleted_all")
    ).scalar_one()
    assert audit.detail["counts"]["deleted"] == count_before


# ---------------------------------------------------------------------------
# Edit-lock visibility on Session card / Danger Zone
# ---------------------------------------------------------------------------


def test_session_card_buttons_when_draft(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="draft-buttons")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    # 18R Item 4 Slice 5 — the standalone Edit page is retired from the UI:
    # no /edit link on Home. Editing happens in place on #session-config.
    assert (
        f'href="/operator/sessions/{review_session.id}/edit"' not in body
    )
    # Revert to draft form NOT present
    assert (
        f'action="/operator/sessions/{review_session.id}/revert"' not in body
    )
    # Danger Zone now lives on Home — Delete Data / Delete session forms
    # are wired here (draft session → not locked).
    assert (
        f'action="/operator/sessions/{review_session.id}/delete-data"'
        in body
    )
    assert (
        f'action="/operator/sessions/{review_session.id}/delete"'
        in body
    )


# ---------------------------------------------------------------------------
# Slice 11B — Quick Setup disabled-greyed when ready
# ---------------------------------------------------------------------------


def test_quick_setup_card_renders_scaffold_in_draft(
    client: TestClient, db: Session
) -> None:
    """Post-15D PR 7c the Quick Setup card on Session Home renders
    a 4-slot layout in draft (Reviewers, Reviewees, Relationships,
    Settings). Settings remains inert pending Segment 12A PR 6.
    The legacy Assignments slot retired in PR 7a."""

    review_session = _make_session(client, db, code="qs-draft")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    # Outer card with stable id; no .placeholder modifier.
    assert 'id="quick-setup"' in body
    assert "<h2>Quick Setup</h2>" in body
    # Action-oriented body copy in draft / validated.
    assert (
        "Bulk-populate reviewers, reviewees, relationships, and "
        "session settings"
    ) in body
    # Four slots render with stable fragment anchors.
    for key in ("reviewers", "reviewees", "relationships", "settings"):
        assert f'id="quick-setup-{key}"' in body
    # Legacy Assignments slot retired in PR 7a.
    assert 'id="quick-setup-assignments"' not in body
    # The wired slots have shed their wiring tooltips.
    assert "Wired in Segment 11J PR A" not in body
    assert "Wired in Segment 11J PR B" not in body
    # The consolidated submit-all form posts at the card level —
    # the per-slot Submit buttons + per-slot form actions were
    # retired in PR C of the rule-builder follow-on stream.
    assert (
        f'action="/operator/sessions/{review_session.id}/quick-setup/submit-all"'
        in body
    )
    # Replacement confirmation lives at the card level (single
    # checkbox above the slot grid), not per-slot inline banners.
    # Per-slot error banners stay (parse / lifecycle).
    assert 'id="quick-setup-confirm-replace-toggle"' in body
    assert "quick-setup-reviewers-confirm-banner" not in body
    assert 'id="quick-setup-reviewers-error-banner"' in body


def test_quick_setup_card_greys_in_ready(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """On a session outside ``draft`` (here ``ready``), Quick Setup
    is permanently locked and the Lock / Unlock toggle disappears
    entirely — the operator can't even cosmetically unlock something
    the route layer would reject. Body-greying via the
    ``.quick-setup-body.locked`` wrapper is the visual signal; the
    description's single static copy names the availability rule."""

    operator = make_client(alice)
    review_session = _seed_pair(
        operator, db, code="qs-ready", reviewer_email="r@example.edu"
    )
    _activate(operator, db, review_session)

    body = operator.get(f"/operator/sessions/{review_session.id}").text

    # Body-greying via .locked, no separate .card.disabled treatment.
    assert 'class="card disabled"' not in body
    assert 'class="quick-setup-body locked"' in body
    # Description copy is the single static line naming the
    # availability rule.
    assert (
        "Available only when session is in draft mode and does not "
        "have any responses." in body
    )
    # Slot anchors still rendered (the body's still in the DOM, just
    # greyed) but the Lock / Unlock toggle is suppressed entirely.
    assert 'id="quick-setup-reviewers"' in body
    assert 'id="quick-setup-reviewees"' in body
    assert 'id="quick-setup-lock-toggle"' not in body


# ---------------------------------------------------------------------------
# Slice 11B — Danger Zone Delete Session visible-disabled when ready
# ---------------------------------------------------------------------------


def test_delete_session_visible_but_disabled_when_ready(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Per spec/session_home.md, the Delete Session affordance stays
    visible-but-disabled when the session is Activated rather than
    being hidden — the operator should always see the action and the
    path forward."""

    operator = make_client(alice)
    review_session = _seed_pair(
        operator, db, code="del-visible", reviewer_email="r@example.edu"
    )
    _activate(operator, db, review_session)

    # Danger Zone moved to the Edit Session page — assert the
    # visible-but-disabled state there. The Edit page is reachable
    # in `ready` (sys-admin / session-operator gate), but the form
    # is gated by ``is_ready`` to render the disabled state.
    body = operator.get(
        f"/operator/sessions/{review_session.id}/edit"
    ).text

    # Form, button, and confirmation checkbox all rendered.
    assert (
        f'action="/operator/sessions/{review_session.id}/delete"' in body
    )
    assert "Delete session" in body
    assert (
        'name="confirm" value="true" required'
        in body
    )
    # Disabled attribute carried on both controls.
    assert 'disabled aria-disabled="true"' in body
    # Explanatory note present.
    assert "Session deletion is locked while status is Activated" in body
    assert "Pause the session" in body


def test_delete_session_post_still_rejected_when_ready(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The visible-but-disabled UI change is cosmetic. Server-side,
    the lifecycle gate (_require_editable in the /delete route)
    still rejects the POST — bypassing the disabled attribute via a
    direct POST should still 4xx."""

    operator = make_client(alice)
    review_session = _seed_pair(
        operator, db, code="del-block", reviewer_email="r@example.edu"
    )
    _activate(operator, db, review_session)

    response = operator.post(
        f"/operator/sessions/{review_session.id}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code in (400, 403, 409)


# ---------------------------------------------------------------------------
# Slice 11B — Extract Data card (placeholder until Segment 12)
# ---------------------------------------------------------------------------


def test_extract_setup_card_relocated_off_session_home(
    client: TestClient, db: Session
) -> None:
    """18R Item 4 Slice 1 — the Extract Setup card moved off Session
    Home to the Extract data page. Home no longer renders it; the
    Extract data page does (its scaffold is covered by
    ``test_extract_data_scaffold.py``)."""

    review_session = _make_session(client, db, code="extract-moved")

    home = client.get(f"/operator/sessions/{review_session.id}").text
    assert 'id="extract-data"' not in home
    assert "<h2>Extract Setup</h2>" not in home

    tab = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text
    assert 'id="extract-data"' in tab
    assert "<h2>Extract Setup</h2>" in tab
    # And the placeholder Archive session card sits beside it.
    assert 'id="extract-data-archive-session"' in tab
    assert ">Archive session</h2>" in tab


# ---------------------------------------------------------------------------
# Slice 11B — Lifecycle display label rendered everywhere
# ---------------------------------------------------------------------------


def test_chrome_status_pill_renders_activated_for_ready_session(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """When the session is in the ``ready`` enum state, the chrome
    status pill (and other operator-readable surfaces) must render
    "Activated", not "ready" / "READY". The CSS class still uses the
    enum (``pill-lifecycle-ready``)."""

    operator = make_client(alice)
    review_session = _seed_pair(
        operator, db, code="chrome-activated", reviewer_email="r@example.edu"
    )
    _activate(operator, db, review_session)

    body = operator.get(f"/operator/sessions/{review_session.id}").text

    # Pill class still keyed by enum; pill text uses the display label.
    assert 'class="pill pill-lifecycle-ready"' in body
    assert ">Activated</span>" in body


# ---------------------------------------------------------------------------
# Slice 11B — Workflow card on Session Home retired (it only renders on the
# Operations-row pages now); equivalent stepper behaviour is covered in
# test_assignments_next_action_return_to.py against the Assignments URL.
# ---------------------------------------------------------------------------


def test_revert_route_handles_validated_to_draft(
    client: TestClient, db: Session
) -> None:
    """The "Revert to draft" supporting button in the validated-state
    action card POSTs to /revert; the route now dispatches to
    ``invalidate_session`` for ``validated → draft`` transitions
    (previously only handled ``ready → draft``)."""

    review_session = _seed_pair(
        client, db, code="validated-revert", reviewer_email="r@example.edu"
    )
    # Mark validated via the ?validated=1 entry path.
    client.get(f"/operator/sessions/{review_session.id}/assignments?validated=1")
    db.refresh(review_session)
    assert review_session.status == "validated"

    response = client.post(
        f"/operator/sessions/{review_session.id}/revert",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(review_session)
    assert review_session.status == "draft"

    # An audit row was written for the operator-initiated invalidation.
    audit = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.invalidated"
        )
    ).scalar_one()
    assert audit.detail["reason"] == "operator_revert"


def test_session_card_buttons_when_ready(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(
        client, db, code="ready-buttons", reviewer_email="r@example.edu"
    )
    _activate(client, db, review_session)

    body = client.get(f"/operator/sessions/{review_session.id}").text

    # 18R Item 4 Slice 5 — no /edit link (Edit page retired). Editing is
    # lifecycle-gated: on an activated session the config card's Unlock
    # control is rendered inert (aria-disabled), not a live edit affordance.
    assert (
        f'href="/operator/sessions/{review_session.id}/edit"' not in body
    )
    assert 'data-config-lock-toggle aria-disabled="true"' in body
    # Workflow card is back on Session Home (PR 6 of
    # spec/workflow_card.md) — its ready-state pause form
    # posts to /revert.
    assert (
        f'action="/operator/sessions/{review_session.id}/revert"'
        in body
    )
    # Danger Zone lives on Home now. Delete Data has no lifecycle gate;
    # Delete session is present but locked (disabled) while Activated.
    assert (
        f'action="/operator/sessions/{review_session.id}/delete-data"'
        in body
    )
    assert (
        f'action="/operator/sessions/{review_session.id}/delete"'
        in body
    )
    assert "Session deletion is locked while status is Activated" in body


def test_session_config_card_display_edit_swap(
    client: TestClient, db: Session
) -> None:
    """18R Item 4 Slice 2 — the "Session details" config card sits below
    Workflow and renders each field as a display value + an edit input in
    one slot, toggled by the card's data-config-mode and the Edit button
    (both ways). Defaults to display mode."""
    review_session = _make_session(client, db, code="cfg-swap")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    workflow_pos = body.find('id="next-action"')
    config_pos = body.find('id="session-config"')
    assert -1 not in (workflow_pos, config_pos)
    assert workflow_pos < config_pos  # below Workflow
    assert "<h2>Session details</h2>" in body

    end = body.find('window.sessionConfig', config_pos)
    card = body[config_pos:end]

    # Card defaults to display mode; both view + edit slots exist.
    assert 'data-config-mode="display"' in card
    assert "data-display-only" in card  # read values
    assert "data-edit-only" in card  # inputs
    # Display value is filled (Name shows the session name).
    assert f">{review_session.name}</div>" in card

    # All fields present (each has both slots keyed on the same id).
    for fid in (
        "mock-name",
        "mock-code",
        "mock-description",
        "mock-help-contact",
        "mock-timezone",
        "mock-start",
        "mock-end",
        "mock-release-from",
        "mock-invite-offsets",
        "mock-reminder-offsets",
        "mock-release-until",
    ):
        assert f'id="{fid}"' in card

    # Mode-control cluster (Slice 3 wired): Save is a real submit for the
    # config form; Cancel + Unlock are anchors carrying ?editing hrefs.
    assert "data-config-save" in card
    assert ">Save</button>" in card
    assert 'type="submit"' in card
    assert f'form="config-save-{review_session.id}"' in card
    assert "data-config-cancel" in card
    assert ">Cancel</a>" in card
    assert "data-config-lock-toggle" in card
    assert ">Unlock</a>" in card
    # Display mode → the Unlock link points at ?editing=1.
    assert "?editing=1" in card
    assert "window.sessionConfig" in body

    # The edit inputs post as one form to the config route.
    assert (
        f'action="/operator/sessions/{review_session.id}/config"' in card
    )
    assert 'name="name"' in card
    assert 'name="display_timezone"' in card
    assert 'name="relationships_enabled"' in card


def test_config_card_editing_param_renders_edit_mode(
    client: TestClient, db: Session
) -> None:
    """18R Item 4 Slice 3 — ``?editing=1`` is the canonical edit-mode state:
    the GET renders the card in edit mode and the Lock link drops the param."""
    review_session = _make_session(client, db, code="cfg-editing")
    body = client.get(
        f"/operator/sessions/{review_session.id}?editing=1"
    ).text

    config_pos = body.find('id="session-config"')
    card = body[config_pos:body.find("window.sessionConfig", config_pos)]
    assert 'data-config-mode="edit"' in card
    # Edit mode → the toggle reads Lock and its href has no ?editing param.
    assert ">Lock</a>" in card


def test_config_card_editing_param_ignored_when_not_editable(
    client: TestClient, db: Session
) -> None:
    """An activated session isn't editable — ``?editing=1`` degrades to
    display mode (the route gates the flag on lifecycle)."""
    review_session = _seed_pair(
        client, db, code="cfg-noedit", reviewer_email="rev@example.edu"
    )
    _activate(client, db, review_session)
    body = client.get(
        f"/operator/sessions/{review_session.id}?editing=1"
    ).text

    config_pos = body.find('id="session-config"')
    card = body[config_pos:body.find("window.sessionConfig", config_pos)]
    assert 'data-config-mode="display"' in card


def test_config_card_save_persists_and_redirects_home(
    client: TestClient, db: Session
) -> None:
    """Saving the config card POSTs to /config, persists the change, and
    redirects back to Session Home in display mode (#session-config)."""
    review_session = _make_session(client, db, code="cfg-save")
    response = client.post(
        f"/operator/sessions/{review_session.id}/config",
        data={
            "name": "Renamed Session",
            "code": review_session.code,
            "description": "New description",
            "display_timezone": "",
            "relationships_enabled": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}#session-config"
    )
    db.refresh(review_session)
    assert review_session.name == "Renamed Session"
    assert review_session.description == "New description"
    assert review_session.relationships_enabled is True


def test_config_card_save_rejects_bad_schedule_ordering(
    client: TestClient, db: Session
) -> None:
    """The config route reuses the Edit route's validation — an End before
    Start is a 422, and nothing is persisted."""
    review_session = _make_session(client, db, code="cfg-badorder")
    original_name = review_session.name
    response = client.post(
        f"/operator/sessions/{review_session.id}/config",
        data={
            "name": "Should Not Save",
            "code": review_session.code,
            "scheduled_activate_at": "2099-06-01T10:00",
            "deadline": "2099-05-01T10:00",  # End before Start
        },
        follow_redirects=False,
    )
    assert response.status_code == 422, response.text
    db.refresh(review_session)
    assert review_session.name == original_name


def test_config_card_invite_offset_shows_offset_plus_resolved_datetime(
    client: TestClient, db: Session
) -> None:
    """18R Item 4 — in display mode the Send-invites offset renders as two
    pills: the ISO offset, then its resolved send datetime (Start + offset)."""
    from datetime import datetime, timezone

    review_session = _make_session(client, db, code="cfg-offset")
    review_session.scheduled_activate_at = datetime(
        2026, 8, 30, 0, 0, tzinfo=timezone.utc
    )
    review_session.invite_offsets = ["-P1D"]
    db.commit()

    body = client.get(f"/operator/sessions/{review_session.id}").text
    config_pos = body.find('id="session-config"')
    end = body.find('window.sessionConfig', config_pos)
    card = body[config_pos:end]

    # The offset pill.
    assert ">-P1D</span>" in card
    # A resolved-datetime pill (Start − 1 day) — lighter chip variant.
    assert "config-value-resolved" in card
    # Both live inside an offset row.
    assert "config-offset-row" in card


def test_session_config_card_has_owners_subcard(
    client: TestClient, db: Session
) -> None:
    """18R Item 4 — the Session details card carries an Owners sub-card
    (half-width, inside the card) showing the current owners; edit mode has
    the wired add/remove UI (Slice 4). The Schedule timeline card is gone."""
    review_session = _make_session(client, db, code="cfg-owners")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    config_pos = body.find('id="session-config"')
    end = body.find('window.sessionConfig', config_pos)
    card = body[config_pos:end]

    assert ">Owners</h3>" in card
    # Mirrors the Edit Owners card columns.
    for col in ("<th>Email</th>", "<th>Name</th>", "<th>Role</th>", "<th>Added</th>"):
        assert col in card
    assert 'class="col-shrink">Action</th>' in card  # edit-mode Action column
    # The creator is an owner — their email shows in the table, with a wired
    # Remove form (Slice 4). (Add-owner form coverage — which needs a second
    # workspace operator to have candidates — lives in test_session_owners.)
    assert "alice@example.edu" in card
    assert 'type="submit">Remove</button>' in card
    assert "/remove\"" in card

    # User interface settings card sits to the right of Owners.
    assert 'id="config-ui-settings-card"' in card
    assert ">User interface settings</h3>" in card
    assert "Relationships tab and page" in card
    assert "Observers tab and page" in card

    # Schedule timeline card retired from Session Home.
    assert "<h2>Schedule timeline</h2>" not in body


def test_config_owners_error_surfaces_on_home(
    client: TestClient, db: Session
) -> None:
    """18R Item 4 Slice 4 — owner add/remove redirect back to Home with an
    ``owners_error`` param; the config Owners sub-card renders the banner."""
    review_session = _make_session(client, db, code="cfg-ownerr")
    body = client.get(
        f"/operator/sessions/{review_session.id}"
        "?editing=1&owners_error=not_in_workspace"
    ).text
    config_pos = body.find('id="session-config"')
    card = body[config_pos:body.find("window.sessionConfig", config_pos)]
    assert 'role="alert"' in card
    assert "workspace operator allowlist" in card


def test_session_home_danger_zone_wired(
    client: TestClient, db: Session
) -> None:
    """18R Item 4 Slice 5 — the Danger Zone card in the bottom-right column
    is wired (relocated from the retired Edit page): real Delete Data /
    Delete session forms posting to the delete routes, each gated by a
    ``required`` confirm checkbox."""
    review_session = _make_session(client, db, code="cfg-danger")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    danger_pos = body.find('id="danger-zone"')
    assert danger_pos != -1
    # It lives after (below/right of) the working session-details card and
    # the Quick Setup card in the bottom grid.
    assert danger_pos > body.find('id="quick-setup"')

    card = body[danger_pos:]
    assert ">Danger Zone</h2>" in card
    # Both destructive actions post to their real routes.
    assert (
        f'action="/operator/sessions/{review_session.id}/delete-data"' in card
    )
    assert f'action="/operator/sessions/{review_session.id}/delete"' in card
    assert ">Delete Data</button>" in card
    assert ">Delete session</button>" in card
    # Confirm checkboxes are required (no-JS-safe destructive gate).
    assert 'name="confirm" value="true" required' in card
    # No lingering mock markers.
    assert "Mock — not wired yet" not in card
