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
    assert "<h2>Session Details</h2>" in body
    # The Workflow card retired from Session Home on the super-button
    # refresh — it now only lives on the Operations-row pages.
    assert 'id="next-action"' not in body
    assert "<h2>Workflow</h2>" not in body
    assert "<h2>Run Session</h2>" not in body
    assert "Danger Zone" in body
    assert 'id="danger-zone"' in body
    # The standalone "Session Setup" card was retired — its five Manage
    # links live in the chrome top-nav now (see chrome partial), so the
    # body no longer needs an in-page card duplicating them.
    assert "<h2>Session Setup</h2>" not in body
    # Legacy ad-hoc layout markers are gone:
    assert "Run setup validation" not in body
    assert "Validate &amp; activate" not in body
    assert "Validate & activate" not in body


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
    # Populated draft session, no ``?validated=1`` — Session Home no
    # longer carries the Workflow card or any validation summary; both
    # live on the Operations-row pages now.
    assert "<h2>Workflow</h2>" not in body
    assert "<h2>Validation summary</h2>" not in body
    assert (
        f'action="/operator/sessions/{review_session.id}/activate"'
        not in body
    )


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
            f"/reviewer/sessions/{review_session.id}/1/save",
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

    # Edit button shown
    assert (
        f'href="/operator/sessions/{review_session.id}/edit">Edit</a>'
        in body
    )
    # Revert to draft form NOT present
    assert (
        f'action="/operator/sessions/{review_session.id}/revert"' not in body
    )
    # Delete Data form present
    assert (
        f'action="/operator/sessions/{review_session.id}/delete-data"' in body
    )
    # Delete Session form present (not locked)
    assert (
        f'action="/operator/sessions/{review_session.id}/delete"' in body
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
    # Slot 4 (Settings) remains inert pending Segment 12A PR 6;
    # the wired slots have shed their wiring tooltips.
    assert "Wired in Segment 11J PR A" not in body
    assert "Wired in Segment 11J PR B" not in body
    assert "Wired in Segment 12A PR 6" in body
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

    body = operator.get(f"/operator/sessions/{review_session.id}").text

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


def test_extract_data_card_renders_scaffold_in_draft(
    client: TestClient, db: Session
) -> None:
    """The Extract Data card on Session Home renders five per-entity
    rows + a "Zip all" cell in a 2-col grid:

        Reviewers       |  Session settings
        Reviewees       |  Responses
        Relationships   |  Zip all  (greyed out)

    Post-12A-3 PR 2: every row except the zip bundle is wired
    live."""

    review_session = _make_session(client, db, code="extract-draft")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    assert 'id="extract-data"' in body
    assert "<h2>Extract Data</h2>" in body
    # Card subtitle stays.
    assert "Download per-entity CSVs of the session's data." in body
    # Two-column grid wraps the cells.
    assert 'class="extract-data-grid"' in body
    # Five rows + bundle cell with stable fragment anchors.
    for key in (
        "settings",
        "reviewers",
        "reviewees",
        "relationships",
        "responses",
        "bundle",
    ):
        assert f'id="extract-data-{key}"' in body
    # Assignments tile retired in 12A-3 PR 2.
    assert 'id="extract-data-assignments"' not in body
    # Cell labels — bundle is "Zip all".
    assert "Zip all" in body
    # Wiring tooltips: 12A-1 + 12A-3 PR 1 lit every per-entity
    # row live; only the zip bundle row's tooltip remains.
    assert "Wired in Segment 12A PR 1" not in body  # settings — live
    assert "Wired in Segment 12A PR 3" not in body  # reviewers/reviewees — live
    assert "Wired in Segment 12A PR 5" not in body  # responses — live
    assert "Wired in Segment 12A PR 6" in body  # bundle


def test_extract_data_card_stays_interactive_in_ready(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Segment 11H PR B — the Extract Data card has no lifecycle
    gate. Per ``guide/segment_12A.md`` the card stays interactive
    in every lifecycle state; in 11H every row is inert across the
    board, so this only confirms that ready doesn't add a
    ``.disabled`` class."""

    operator = make_client(alice)
    review_session = _seed_pair(
        operator, db, code="extract-ready", reviewer_email="r@example.edu"
    )
    _activate(operator, db, review_session)

    body = operator.get(f"/operator/sessions/{review_session.id}").text

    # No ``disabled`` modifier on the Extract Data card.
    assert 'id="extract-data"' in body
    assert 'class="card disabled" id="extract-data"' not in body
    # Rows still render with their counts.
    assert 'id="extract-data-responses"' in body


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

    # Edit button still shown (lock is enforced server-side on the POST)
    assert (
        f'href="/operator/sessions/{review_session.id}/edit">Edit</a>'
        in body
    )
    # The /revert POST form no longer renders on Session Home — it
    # lives in the Workflow card on the Operations-row pages now.
    assert (
        f'action="/operator/sessions/{review_session.id}/revert"'
        not in body
    )
    # Delete Data form still present (allowed in ready)
    assert (
        f'action="/operator/sessions/{review_session.id}/delete-data"' in body
    )
    # Per PR D, the Delete Session affordance now stays VISIBLE
    # (form + button + confirmation checkbox) but the button and
    # checkbox are disabled while ready, with an explanatory note
    # below. The server-side lock in the route is the source of
    # truth (_require_editable rejects the POST); this is the
    # visual "always show the affordance" change from
    # spec/session_home.md.
    assert (
        f'action="/operator/sessions/{review_session.id}/delete"' in body
    )
    assert "Delete session" in body
    # Button and checkbox carry disabled attribute.
    assert "disabled aria-disabled=\"true\"" in body
    assert "Session deletion is locked while status is Activated" in body
