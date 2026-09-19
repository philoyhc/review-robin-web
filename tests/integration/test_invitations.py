from __future__ import annotations

import re
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    AuditEvent,
    EmailOutbox,
    Invitation,
    Reviewer,
    ReviewSession,
)
from app.db.models.email_outbox import EMAIL_OUTBOX_STATUSES
from app.services import email_send
from app.services import invitations as inv_service
from app.web import views
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)
from ._invitation_states import _create_session, _populate


# --------------------------------------------------------------------------- #
# Fixture helpers
# --------------------------------------------------------------------------- #


def _activate(client: TestClient, session_id: int) -> None:
    # Prepare, not the `?validated=1` promotion: since 19Q.2 rung 2
    # Prepare is what creates the invitations, and every test below
    # that used to call `POST /invitations/generate` now relies on it.
    response = client.post(
        f"/operator/sessions/{session_id}/workflow/prepare",
        follow_redirects=False,
    )
    # 303 alone says nothing: `workflow_prepare` also 303s on a failed
    # validation, on the response-loss detour and on the `is_editable`
    # precondition. 19Q.2 rung 1 wrote that guard for
    # `_strand_an_invitation` and rung 3 re-fixtured 46 tests without
    # it — named by the item's cumulative cold read.
    assert response.status_code == 303, response.text
    assert "super_status=failed" not in response.headers["location"], (
        f"Prepare did not succeed: {response.headers['location']}"
    )
    response = client.post(
        f"/operator/sessions/{session_id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def _ready_session(
    client: TestClient,
    db: Session,
    code: str = "inv-1",
    reviewer_email: str = "rae@example.edu",
) -> ReviewSession:
    session = _create_session(client, db, code)
    _populate(client, db, session.id, reviewer_email=reviewer_email)
    _activate(client, session.id)
    db.refresh(session)
    return session


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_invitations_page_renders_workflow_card(
    client: TestClient, db: Session
) -> None:
    """Per spec/workflow_card.md — the Invitations page hosts
    the Workflow card with ``next_action_return_to=invitations``."""
    session = _ready_session(client, db, code="inv-card")
    body = client.get(f"/operator/sessions/{session.id}/invitations").text
    assert 'id="next-action"' in body
    assert "<h2>Workflow</h2>" in body
    # In a ready session, the card's invitation forms render with
    # the page-specific return_to slug.
    assert 'value="invitations"' in body


def test_the_generate_route_is_gone(client: TestClient, db: Session) -> None:
    """`POST /invitations/generate` retired at 19Q Item 2 rung 3.

    Three tests used to live here — one per assigned reviewer and
    idempotent, 409 from `draft`, live from `validated`. Every one of
    those properties is now Prepare's and is asserted against Prepare
    in `test_workflow_super_button.py`
    (`test_prepare_creates_one_invitation_per_eligible_reviewer`,
    `test_a_failed_validation_creates_no_invitations`,
    `test_re_prepare_is_additive_and_preserves_existing_tokens`), so
    they are deleted rather than re-aimed: re-aiming them at Prepare
    would have duplicated those three under names that describe a
    button nobody can press.

    What is left is the one thing those tests cannot say — that the
    route itself is gone. A POST is not a bookmark (Item 2, open
    question 2), so it 404s rather than redirecting.
    """
    session = _ready_session(client, db, code="gen-gone")
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/generate",
        follow_redirects=False,
    )
    assert response.status_code == 404, (
        "the Create invites route answered; Prepare is the only "
        "creator since rung 2 and the button retired at rung 3"
    )


def _ready_session_without_invitations(
    client: TestClient,
    db: Session,
    code: str,
    reviewer_email: str = "rae@example.edu",
) -> ReviewSession:
    """A `ready` session with assignments and **no** invitations.

    Since 19Q.2 rung 2, Prepare creates one invitation per eligible
    reviewer, so `_ready_session` — which goes through Prepare — can no
    longer produce this state. It is still reachable, by the
    `?validated=1` promotion that `build_workflow_card_context`
    performs inline: that path runs validation and flips
    `draft -> validated` without running Prepare, so nothing creates
    invitations. The author's ruling (2026-09-18) was to keep that
    backend rather than migrate ~200 tests off it, so the state this
    fixture builds is one an operator can still reach.

    The tests below are the ones that guard what the page does when a
    listed reviewer has no invitation row. Pointing them at
    `_ready_session` after rung 3 would have made every one of them
    vacuous — a table where every row always has an invitation cannot
    exercise the row that does not.
    """
    session = _create_session(client, db, code)
    _populate(client, db, session.id, reviewer_email=reviewer_email)
    client.get(f"/operator/sessions/{session.id}/assignments?validated=1")
    response = client.post(
        f"/operator/sessions/{session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(session)
    assert (
        db.execute(
            select(Invitation).where(Invitation.session_id == session.id)
        ).first()
        is None
    ), "this fixture exists to have no invitations; something created one"
    return session


def _validated_session(
    client: TestClient,
    db: Session,
    code: str,
    reviewer_email: str = "rae@example.edu",
) -> ReviewSession:
    """Bring a session to ``validated`` without activating, so 18F
    Part 2's "invitations from Prepared" path can be exercised."""
    session = _create_session(client, db, code)
    _populate(client, db, session.id, reviewer_email=reviewer_email)
    response = client.post(
        f"/operator/sessions/{session.id}/workflow/prepare",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(session)
    return session


def test_send_all_works_from_validated_session(
    client: TestClient, db: Session
) -> None:
    """18F Part 2 — Send invites is live from Validated too, so an
    operator can notify reviewers ahead of activation."""
    session = _validated_session(client, db, "val-send")
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/send-all",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def test_reviewer_pre_open_page_renders_for_validated_session(
    client: TestClient,
    db: Session,
    make_client,
) -> None:
    """18F Part 2 — a reviewer with a roster row who lands on the
    response surface URL of a not-yet-activated session sees the
    "this review hasn't opened yet" page instead of the form or
    a 403."""
    session = _validated_session(client, db, "val-preopen")
    rae = AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae",
        provider="aad",
    )
    rae_client = make_client(rae)
    page = rae_client.get(f"/me/sessions/{session.id}/1")
    assert page.status_code == 200
    body = page.text
    assert "<title>Review opens later" in body
    assert "hasn't opened yet" in body


def test_send_writes_outbox_and_flips_to_sent(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="send-1")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send",
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(invitation)
    assert invitation.status == "sent"
    assert invitation.sent_at is not None

    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    assert outbox.kind == "invitation"
    assert outbox.status == "sent"
    assert outbox.sent_at is not None
    assert outbox.to_email == "rae@example.edu"
    assert "/me/invite/" in outbox.body  # raw token URL embedded


def test_send_all_writes_one_outbox_per_pending(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="sendall-1")

    response = client.post(
        f"/operator/sessions/{session.id}/invitations/send-all",
        follow_redirects=False,
    )
    assert response.status_code == 303
    outbox_count = len(
        db.execute(
            select(EmailOutbox).where(EmailOutbox.session_id == session.id)
        ).scalars().all()
    )
    pending_count = len(
        db.execute(
            select(Invitation).where(
                Invitation.session_id == session.id,
                Invitation.status == "pending",
            )
        ).scalars().all()
    )
    assert outbox_count == 1
    assert pending_count == 0  # all flipped to sent


def test_regenerate_rotates_token_and_resets_status(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="regen-1")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send",
        follow_redirects=False,
    )
    db.refresh(invitation)
    old_hash = invitation.token_hash
    assert invitation.status == "sent"

    response = client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/regenerate",
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(invitation)
    assert invitation.token_hash != old_hash
    assert invitation.status == "pending"
    assert invitation.sent_at is None
    assert invitation.opened_at is None


def _extract_invite_token(outbox_body: str) -> str:
    match = re.search(r"/me/invite/([A-Za-z0-9_\-]+)", outbox_body)
    assert match is not None, f"could not find invite URL in: {outbox_body!r}"
    return match.group(1)


def test_token_url_with_matching_email_stamps_opened_and_redirects(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _ready_session(operator, db, code="open-1")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    raw_token = _extract_invite_token(outbox.body)

    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    rae_client = make_client(rae)

    response = rae_client.get(f"/me/invite/{raw_token}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/me/sessions/{session.id}"

    db.refresh(invitation)
    assert invitation.status == "opened"
    assert invitation.opened_at is not None


def test_token_url_repeat_visit_does_not_restamp(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _ready_session(operator, db, code="repeat-1")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    raw_token = _extract_invite_token(outbox.body)

    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    rae_client = make_client(rae)
    rae_client.get(f"/me/invite/{raw_token}", follow_redirects=False)
    db.refresh(invitation)
    first_opened_at = invitation.opened_at
    rae_client.get(f"/me/invite/{raw_token}", follow_redirects=False)
    rae_client.get(f"/me/invite/{raw_token}", follow_redirects=False)
    db.refresh(invitation)
    assert invitation.opened_at == first_opened_at


def test_token_url_with_mismatched_email_returns_403(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _ready_session(operator, db, code="mismatch-1")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    raw_token = _extract_invite_token(outbox.body)

    eve = AuthenticatedUser(
        principal_id="eve-oid", email="eve@example.edu", name="Eve", provider="aad"
    )
    eve_client = make_client(eve)
    response = eve_client.get(f"/me/invite/{raw_token}", follow_redirects=False)
    assert response.status_code == 403
    assert "belongs to someone else" in response.text

    db.refresh(invitation)
    assert invitation.opened_at is None  # mismatch did not stamp


def test_token_url_with_unknown_token_returns_404(client: TestClient) -> None:
    response = client.get("/me/invite/not-a-real-token", follow_redirects=False)
    assert response.status_code == 404


def test_revert_then_reactivate_keeps_existing_invitations_idempotent(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="reactivate-1")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    initial_hash = invitation.token_hash

    # Revert + reactivate without touching the roster.
    client.post(
        f"/operator/sessions/{session.id}/revert",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    _activate(client, session.id)

    # The re-Prepare inside `_activate` is a no-op for invitations:
    # same row, same token. It used to be a `POST /invitations/generate`
    # here; since 19Q.2 rung 3 that route is gone and Prepare is the
    # only creator, so this asserts the same idempotence one layer up.
    rows = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].token_hash == initial_hash


def test_manage_invitations_no_longer_links_to_outbox(
    client: TestClient, db: Session
) -> None:
    """The "View outbox" button on Manage Invitations retired in
    16A PR 3 and the per-session ``/operator/sessions/{id}/outbox``
    route retired in the inline-outbox reshape. Both verifications
    landed here so future refactors don't accidentally bring either
    back. Outbox content rendering itself is exercised by
    ``test_sys_admin_outbox_inline.py``.
    """
    session = _ready_session(client, db, code="outbox-retired")
    invitations_body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    assert (
        f'href="/operator/sessions/{session.id}/outbox">View outbox</a>'
        not in invitations_body
    )
    # The per-session route is gone — direct access 404s.
    response = client.get(f"/operator/sessions/{session.id}/outbox")
    assert response.status_code == 404


def test_audit_events_written_for_lifecycle(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="audit-inv")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/regenerate"
    )

    events = {
        e.event_type
        for e in db.execute(
            select(AuditEvent).where(AuditEvent.session_id == session.id)
        ).scalars()
    }
    assert {"invitations.generated", "invitation.sent", "invitation.regenerated"}.issubset(
        events
    )

    generated = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "invitations.generated")
    ).scalar_one()
    assert generated.detail is not None
    assert len(generated.detail["set_changes"]["added"]) == 1


def test_record_open_audit_event_written(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _ready_session(operator, db, code="open-audit")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    raw_token = _extract_invite_token(outbox.body)

    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    make_client(rae).get(f"/me/invite/{raw_token}", follow_redirects=False)

    opened = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "invitation.opened")
    ).scalar_one()
    assert opened.detail is not None
    assert opened.detail["refs"]["invitation_id"] == invitation.id


# --------------------------------------------------------------------------- #
# Segment 11C Part 1 — consolidated Manage Invitations page
# --------------------------------------------------------------------------- #


def test_invitations_page_renders_consolidated_column_headers(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="cols-1")

    body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    # The full new column spec from segment_11C plan, in order.
    #
    # Matched by sort key rather than by `<th>Label</th>`: Segment 19I
    # Item 11 made every one of these sortable, so the header now
    # carries a class, a key and a button. Pinning the label to its
    # key keeps both facts — the column exists, and it is the column
    # the sort cascade names.
    start = body.index("<thead>")
    head = body[start : body.index("</thead>", start)]
    # Three labels were narrowed in Segment 19I Item 11 after the tag
    # columns pushed the table past its container at every viewport
    # width: `Review Progress` -> `Progress`, `Last reminder` ->
    # `Reminder`, and `Required Fields` kept both words stacked onto
    # two lines rather than shortened.
    for key, label in (
        ("name", "Reviewer"),
        ("email_status", "Email Status"),
        ("email_sent_at", "Sent"),
        ("review_progress", "Progress"),
        ("required_fields", "Required<br>Fields"),
        ("last_reminder_at", "Reminder"),
    ):
        assert (
            f'data-sort-key="{key}">{label}' in head
        ), f"missing column header: {label!r} under key {key!r}"
    # The dropped "Opened" column from the pre-rewrite shape stays out.
    assert "Opened" not in head


def test_invitations_page_renders_review_progress_and_required_fields_format(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="prog-fmt")

    body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    # Review Progress: "{state} ({done}/{total})". Single reviewer with
    # one assignment (Rae ⨯ Carol), no responses yet → "not started (0/1)".
    assert "not started" in body
    assert "(0/1)" in body  # review progress + required fields both 0/0 or 0/1


def test_invitations_data_cells_render_in_pills(
    client: TestClient, db: Session
) -> None:
    """Email Status / Email Sent / Review Progress / Required Fields /
    Last reminder all render their cell content inside a
    ``<span class="pill ...">`` so the table reads as a sparkline of
    state at a glance."""
    session = _ready_session(client, db, code="pill-cells")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()

    # Pre-send state: not-sent pill, em-dash pills for empty cells.
    body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    assert '<span class="pill pill-empty">not sent</span>' in body
    # Review Progress pill (not started state) carries the formatted count.
    # audit V2 — "not started" is now the canonical blue pill-info
    # (blue = nothing yet), via the shared progress_pill helper.
    assert '<span class="pill pill-info">not started (0/1)</span>' in body
    # Required Fields pill — "(0/{total})" or "—" depending on
    # whether the seeded instrument has required fields. Either way
    # the cell content is wrapped in a pill.
    assert (
        '<span class="pill pill-empty">(0/' in body
        or '<span class="pill pill-empty">—</span>' in body
    )
    # Last reminder pre-send is em-dash in pill-empty.
    assert '<span class="pill pill-empty">—</span>' in body

    # After send: Email Sent timestamp wraps in a pill-count.
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    # The Email Sent cell now carries a pill-count with a timestamp
    # (look for the year prefix as a reasonable shape proxy).
    assert '<span class="pill pill-count">202' in body or \
        '<span class="pill pill-count">203' in body


def test_invitations_page_email_status_reflects_outbox_row(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="email-status")
    body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    # Before send: no outbox row exists → "not sent" pill.
    assert "not sent" in body

    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    # After send: outbox row exists at status="sent" (today the queue
    # path stamps sent immediately; Part 2 widens the value set).
    assert ">sent</span>" in body


def test_invitations_page_reviewer_name_links_to_drill_in(
    client: TestClient, db: Session
) -> None:
    """**The link does not wait for an invitation** (19P.6 rung 1).

    It used to render on `{% if row.invitation %}`, so the table was a
    list of names that went nowhere until Create invites — which is the
    moment an operator most wants to open one. The page is keyed on the
    reviewer now, so the link exists for every row.

    Asserted in that order — before generate, then after — because the
    before case is the whole point and an after-only assertion passes on
    the old markup too.
    """
    session = _ready_session_without_invitations(client, db, "drill-link")
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == session.id)
    ).scalar_one()
    href = (
        f'href="/operator/sessions/{session.id}'
        f'/invitations/reviewers/{reviewer.id}"'
    )

    no_invitations = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalars().all()
    assert no_invitations == []
    assert href in client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text

    assert href in client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text


def test_old_invitation_keyed_detail_url_308s_to_the_reviewer_url(
    client: TestClient, db: Session
) -> None:
    """The pre-19P.6 URL is permanent-redirected, so a bookmark or a
    pasted link survives the re-key. 308 rather than 303: the move is
    permanent and the method is preserved."""
    # A throwaway session first, so this session's reviewer ids start
    # above 1 while its invitation ids start at 1. Without it both are
    # 1 and the Location assertion below holds whichever id the route
    # interpolates — which is how the first version of this test
    # survived a mutation swapping them.
    #
    # **The pad has to create reviewers without creating invitations**,
    # or the two sequences advance in lockstep and the ids coincide
    # again. They did, briefly, at 19Q.2 rung 3: the pad was a
    # `_ready_session`, which since rung 2 mints one invitation per
    # reviewer, so padding by one advanced both by one. The assertion
    # below caught it, which is the whole reason it is written down
    # rather than left to the fixture.
    _ready_session_without_invitations(client, db, "drill-308-pad")
    session = _ready_session(client, db, code="drill-308")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    assert invitation.id != invitation.reviewer_id, (
        "vacuity: the ids coincide, so this test cannot tell them apart"
    )

    response = client.get(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/detail",
        follow_redirects=False,
    )
    assert response.status_code == 308
    assert response.headers["location"] == (
        f"/operator/sessions/{session.id}"
        f"/invitations/reviewers/{invitation.reviewer_id}"
    )


# 19P.6 rung 2a — the Invitation card's two fact lines, sliced out of
# the page before anything is asserted about them.
#
# Scoped deliberately. `base.html` inlines the whole app's CSS and JS
# into every page, so a substring assertion over `response.text` can
# match prose *about* the thing rather than the thing, and a negative
# assertion (`assert "created" not in body`) can fail on a CSS comment.
# Both directions of that trap have cost this segment a rung already.
#
# The pill markup is asserted whole rather than by its text. Asserting
# the text would be ambiguous — "not created" contains "created" — and
# matching the whole span also pins the pill role, which carries the
# meaning: `pill-count` is informational, `pill-empty` is the warning
# amber (`spec/ui_elements.md` §9).
_CREATED = '<span class="pill pill-count">created</span>'
_NOT_CREATED = '<span class="pill pill-empty">not created</span>'
_NO_DATE = '<span class="pill pill-empty">\u2014</span>'


def _DELIVERY(status: str) -> str:
    """The delivery-state pill's exact markup for one status."""
    return f'<span class="pill pill-empty">{status}</span>'


def _invitation_facts(body: str) -> str:
    """The `#invitation-facts` block: the Invite line and the dates line."""
    start = body.index('<div id="invitation-facts">')
    return body[start:body.index("</div>", start)]


def _invitation_card(body: str) -> str:
    """The whole Invitation card — heading through to the next card.

    Wider than `_invitation_facts` on purpose. A negative assertion
    scoped to the facts block is vacuous for anything the block cannot
    contain by construction; the card is the region that could
    plausibly regrow a field, so it is the region to deny.
    """
    start = body.index('<h2 style="margin-top: 0;">Invitation</h2>')
    nxt = body.find('<div class="card">', start)
    return body[start:nxt if nxt != -1 else len(body)]


@pytest.mark.parametrize("how", ["inactive", "unassigned"])
def test_detail_page_renders_for_a_reviewer_the_table_does_not_list(
    client: TestClient, db: Session, how: str
) -> None:
    """The page must render when `row` is None, not 500.

    The table lists `_assigned_active_reviewers` — active reviewers
    with an included assignment — so there are **two** ways off it, and
    both are covered here: the reviewer goes inactive, or their
    assignments do.

    **This state is not new at 19P.6**, though the first version of
    this docstring said it was. Deactivating a reviewer leaves their
    invitation alone, so the old invitation-keyed URL already reached
    this page from a bookmark — measured on the pre-re-key commit:
    200, no Review Progress card. What the re-key changes is *who* can
    reach it: every reviewer in the session, including one that never
    had an invitation, where before only an invitation could name one.
    """
    # No invitations at all, then make the reviewer ineligible — the
    # test needs *both* facts and since 19Q.2 rung 2 a Prepared
    # session has an invitation for everyone who was eligible at
    # Prepare time, including this reviewer before the edit below.
    session = _ready_session_without_invitations(
        client, db, f"drill-norow-{how[:4]}"
    )
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == session.id)
    ).scalar_one()
    if how == "inactive":
        reviewer.status = "inactive"
    else:
        for assignment in db.execute(
            select(Assignment).where(Assignment.session_id == session.id)
        ).scalars():
            assignment.include = False
    db.commit()

    # Precondition: the reviewer really is off the table. Without this
    # the assertions below pass for a reviewer who simply has no
    # responses yet.
    assert reviewer.id not in {
        r.reviewer.id for r in views.build_invitations_rows(db, session)
    }

    response = client.get(
        f"/operator/sessions/{session.id}/invitations/reviewers/{reviewer.id}"
    )
    assert response.status_code == 200, response.text
    body = response.text
    assert reviewer.email in body
    # No invitation exists here, so the top line says so and the dates
    # line is two em-dashes — "no date", not "no invitation" (19P.6
    # rung 2a; the two are separate facts and the card reports both).
    facts = _invitation_facts(body)
    assert _NOT_CREATED in facts
    assert _CREATED not in facts
    assert facts.count(_NO_DATE) == 2
    # 19P.6 rung 2a, after Codex: this reviewer is off the table, which
    # is the same predicate `generate_invitations` selects on, so
    # **Create invites** cannot reach them. The card must not tell the
    # operator to press it.
    card = _invitation_card(body)
    assert "will skip this one" in card
    assert "Prepare session</strong> on the" not in card
    # The per-row cards need a row; this reviewer has none. The string
    # appears once in the whole template tree and not in `base.html`.
    assert "Review Progress" not in body


def test_detail_page_keeps_the_invite_url_for_a_reviewer_off_the_table(
    client: TestClient, db: Session
) -> None:
    """A sent invitation outlives its reviewer's place on the table.

    `reviewers.bulk_inactivate` flips `status` only, so an invitation
    that was already sent is still the live link in that reviewer's
    inbox — and the page that shows it must keep showing it. Deriving
    the invitation from `build_invitations_rows` loses it, because that
    row set is `_assigned_active_reviewers`; the lookup is by reviewer
    and session instead, which is what the old invitation-keyed route
    effectively did.
    """
    session = _ready_session(client, db, code="drill-url-off")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.id == invitation.reviewer_id)
    ).scalar_one()
    reviewer.status = "inactive"
    db.commit()

    assert reviewer.id not in {
        r.reviewer.id for r in views.build_invitations_rows(db, session)
    }
    body = client.get(
        f"/operator/sessions/{session.id}/invitations/reviewers/{reviewer.id}"
    ).text
    assert "/me/invite/" in body
    assert "No invitation URL has been issued yet." not in body
    # 19P.6 rung 2a — and the card's own two lines survive the same
    # way, for the same reason. They read `invitation`, whose `sent_at`
    # and `last_reminder_at` are columns on the row itself; the first
    # draft read `row`, which is `_assigned_active_reviewers` and so is
    # None here — reporting "created" with no send date for a reviewer
    # whose invitation had demonstrably been sent.
    facts = _invitation_facts(body)
    assert _CREATED in facts
    assert facts.count(_NO_DATE) == 1, (
        "Email sent carries the send timestamp even off the table; "
        "only Last reminder is empty"
    )


def test_detail_page_does_not_claim_an_invitation_that_was_never_created(
    client: TestClient, db: Session
) -> None:
    """Reported from the dev slot, 2026-09-17: assignments generated,
    **Create invites not clicked**, and the Invitation card read
    "Email Status: not sent &middot; Email Sent: — &middot; Last
    reminder: —" — a card describing an invitation that does not
    exist, on a page whose own chrome pill said `Invitations: NOT
    CREATED` two inches above.

    `email_status` comes from the **outbox**, so it falls back to
    "not sent" when there is no invitation to have an outbox row. The
    card used to be gated on `row`, and rows exist for every assigned
    active reviewer. Rung 1 made that state reachable from the table;
    before it, the page needed an invitation in the path, so "not
    sent" always meant one existed.
    """
    session = _ready_session_without_invitations(client, db, "drill-noinv")
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == session.id)
    ).scalar_one()
    # Assignments exist; invitations deliberately do not.
    assert db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalars().all() == []
    row = next(
        r for r in views.build_invitations_rows(db, session)
        if r.reviewer.id == reviewer.id
    )
    assert row.email_status == "not sent", (
        "premise: the row still reports an email status with no invitation"
    )

    body = client.get(
        f"/operator/sessions/{session.id}/invitations/reviewers/{reviewer.id}"
    ).text
    facts = _invitation_facts(body)
    # The top line reports the state the page previously got wrong.
    assert _NOT_CREATED in facts
    assert _CREATED not in facts
    # The dates line still renders, both slots empty: the author's
    # correction, 2026-09-17 — the em-dashes are right, they mean "no
    # date attached", and hiding the line was the over-correction.
    assert "Invite:" in facts
    assert "Email sent:" in facts
    assert "Last reminder:" in facts
    assert facts.count(_NO_DATE) == 2
    # And the card no longer reports an outbox-derived email status
    # anywhere, which is what made it claim "not sent" with nothing to
    # send. Asserted over the whole Invitation card, not over
    # `#invitation-facts`: that block cannot contain the string by
    # construction, so scoping this one would make it vacuous.
    assert "Email Status" not in _invitation_card(body)
    # Review Progress is unaffected — the assignments are real.
    assert "Review Progress" in body


def test_detail_page_links_to_the_reviewer_surface_in_a_new_tab(
    client: TestClient, db: Session
) -> None:
    """The Review Progress card's `Open reviewer surface` link.

    Placement, destination and target are all decided in Item 6's
    § *Where the link goes* rather than iterated on the dev slot, so
    they are asserted rather than left to a look:

    - a `.card-action-row` at the **foot of the card**;
    - straight at `/preview-surface`, **never through `/previews`**,
      which is what keeps Item 7's retirement of that hub cheap;
    - a new tab, so the drill-in stays put behind it.
    """
    session = _ready_session(client, db, code="drill-surface")
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == session.id)
    ).scalar_one()
    body = client.get(
        f"/operator/sessions/{session.id}/invitations/reviewers/{reviewer.id}"
    ).text

    card = body[body.index("Review Progress") :]
    row = card[card.index('<div class="card-action-row">') :]
    row = row[: row.index("</div>")]
    assert ">\n          Open reviewer surface\n        </a>" in row
    assert 'class="btn secondary"' in row
    assert 'target="_blank"' in row and 'rel="noopener"' in row
    assert (
        f'href="/operator/sessions/{session.id}/preview-surface/1'
        f'?reviewer_email=rae%40example.edu"' in row
    )
    assert "/previews" not in row

    # **Last child of the card**, which is the placement decision and
    # not an accident of where it happened to be written: after the
    # action row closes, the only markup left before the card closes is
    # whitespace and that closing tag.
    after_row = card[card.index("</div>", card.index("card-action-row")) + 6:]
    assert after_row.lstrip().startswith("</div>"), after_row[:120]

    # The promise the link makes good on is gone from the note.
    assert "will land in a future" not in card


def test_detail_page_404s_for_a_reviewer_in_another_session(
    client: TestClient, db: Session
) -> None:
    """The scoped lookup the hoisted `_require_reviewer_in_session`
    exists for — a reviewer id is not a capability."""
    mine = _ready_session(client, db, code="drill-scope-a")
    theirs = _ready_session(client, db, code="drill-scope-b")
    other_reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == theirs.id)
    ).scalar_one()
    response = client.get(
        f"/operator/sessions/{mine.id}"
        f"/invitations/reviewers/{other_reviewer.id}"
    )
    assert response.status_code == 404


def test_invitation_reviewer_detail_renders(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="drill-detail")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    response = client.get(
        f"/operator/sessions/{session.id}"
        f"/invitations/reviewers/{invitation.reviewer_id}"
    )
    assert response.status_code == 200
    body = response.text
    assert "rae@example.edu" in body
    # Created but never sent: top line created, both dates empty.
    facts = _invitation_facts(body)
    assert _CREATED in facts
    assert _NOT_CREATED not in facts
    assert facts.count(_NO_DATE) == 2
    # Pre-send there is no URL to show, and "issued" is why: the raw
    # token is discarded at generate and only recovered from the body
    # of the email that carried it.
    assert "No invitation URL has been issued yet." in body

    # After send: the Email sent slot takes a timestamp, Last reminder
    # stays empty, and the URL surfaces.
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    body = client.get(
        f"/operator/sessions/{session.id}"
        f"/invitations/reviewers/{invitation.reviewer_id}"
    ).text
    facts = _invitation_facts(body)
    assert _CREATED in facts
    assert facts.count(_NO_DATE) == 1, (
        "Email sent should carry a timestamp; only Last reminder is empty"
    )
    assert "/me/invite/" in body


@pytest.mark.parametrize(
    ("email_tab", "active_label", "expected_body"),
    (
        ("invitation", "Invitation", "Invitation to review:"),
        ("reminder", "Reminder", "Reminder: review for"),
        (
            "responses_received",
            "Responses received",
            "Responses received:",
        ),
    ),
)
def test_invitation_reviewer_detail_renders_email_preview_tab(
    client: TestClient,
    db: Session,
    email_tab: str,
    active_label: str,
    expected_body: str,
) -> None:
    session = _ready_session(client, db, code=f"drill-email-{email_tab}")
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == session.id)
    ).scalar_one()

    response = client.get(
        f"/operator/sessions/{session.id}"
        f"/invitations/reviewers/{reviewer.id}",
        params={"email": email_tab},
    )

    assert response.status_code == 200
    body = response.text
    assert (
        f'<span class="nav-tab active" aria-current="page">'
        f"{active_label}</span>"
    ) in body
    assert expected_body in body
    assert f"<strong>To:</strong> {reviewer.email}" in body
    assert 'id="email-previews"' in body
    assert (
        f"/operator/sessions/{session.id}/invitations/reviewers/{reviewer.id}"
        in body
    )


def test_detail_page_dates_line_reports_a_sent_reminder(
    client: TestClient, db: Session
) -> None:
    """The Last reminder slot takes a timestamp once a reminder goes.

    Added because mutation testing found the whole second half of the
    dates line unpinned: no test sent a reminder, so `{% if false %}`
    in that slot, and reading `row.last_reminder_at` instead of
    `invitation.last_reminder_at`, both survived the suite. Every
    assertion below fails on at least one of those.

    The reviewer is taken off the table on purpose, which is what
    separates the two sources: `row` is `_assigned_active_reviewers`
    and is None here, so the row-reading version renders an em-dash
    for a reminder that demonstrably went out.
    """
    session = _ready_session(client, db, code="drill-remind")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/remind"
    )
    db.refresh(invitation)
    assert invitation.last_reminder_at is not None, (
        "premise: the reminder actually stamped the invitation"
    )
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.id == invitation.reviewer_id)
    ).scalar_one()
    reviewer.status = "inactive"
    db.commit()
    assert reviewer.id not in {
        r.reviewer.id for r in views.build_invitations_rows(db, session)
    }

    facts = _invitation_facts(
        client.get(
            f"/operator/sessions/{session.id}"
            f"/invitations/reviewers/{reviewer.id}"
        ).text
    )
    assert _CREATED in facts
    # Both slots filled: neither em-dash survives a sent invitation
    # followed by a sent reminder.
    assert _NO_DATE not in facts
    assert "Email sent:" in facts
    assert "Last reminder:" in facts


def test_detail_page_url_region_distinguishes_its_states(
    client: TestClient, db: Session
) -> None:
    """`no URL` and `no invitation` are different, and say different things.

    Added after a cold read showed the three-way branch entirely
    unpinned: deleting the third branch left the suite at 48 passed.
    The rung's own mutation run had scored this CAUGHT, but that mutant
    rewrote `{% elif %}` to a second `{% else %}` and so was a Jinja
    syntax error — every render failed, which proves nothing about the
    assertions. A mutant that breaks the template is not a mutant.

    The distinction is real: `generate_invitations` discards the raw
    token (`invitations.py:170`), so the URL is recoverable only from
    the body of the email that carried it. An invitation can exist with
    no URL ever issued; an absent invitation is a different state, and
    the third branch names the action that fixes it.
    """
    # The three states have to be walked in order, and since 19Q.2
    # rung 3 the middle one is reached by Prepare rather than by a
    # `POST /invitations/generate`. Start with the fixture that has no
    # invitations at all, then revert and Prepare to create one.
    session = _ready_session_without_invitations(client, db, "drill-3way")
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == session.id)
    ).scalar_one()
    url = f"/operator/sessions/{session.id}/invitations/reviewers/{reviewer.id}"

    # No invitation: the card names the action, not the missing URL.
    card = _invitation_card(client.get(url).text)
    assert "creates one invitation per eligible reviewer" in card
    assert "No invitation URL has been issued yet." not in card

    client.post(
        f"/operator/sessions/{session.id}/revert",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    response = client.post(
        f"/operator/sessions/{session.id}/workflow/prepare",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    # Invitation created, never sent: now it IS the missing URL.
    card = _invitation_card(client.get(url).text)
    assert "No invitation URL has been issued yet." in card
    assert "creates one invitation per eligible reviewer" not in card

    # Sent: the URL itself, and neither fallback.
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    card = _invitation_card(client.get(url).text)
    assert "/me/invite/" in card
    assert "No invitation URL has been issued yet." not in card
    assert "creates one invitation per eligible reviewer" not in card


def test_detail_page_after_regenerate_reports_the_current_token(
    client: TestClient, db: Session
) -> None:
    """Regenerate resets the invitation; the card follows the invitation.

    `regenerate_token` clears `sent_at` but leaves `last_reminder_at`
    and every outbox row alone (`invitations.py:221-224`), so the three
    slots disagree by design: no send date for the current token, the
    old reminder date, and the previous URL still recoverable from the
    outbox.

    Pinned rather than smoothed over. The divergence is older than this
    card — the chrome strip already reads `NOT SENT` here while the
    table's Sent column shows a date — and reconciling it is a decision
    about `regenerate_token`, not about this template. This test exists
    so the state is known and cannot drift unnoticed while that is open
    (Item 6 open question 4).
    """
    session = _ready_session(client, db, code="drill-regen")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/remind"
    )
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/regenerate"
    )
    db.refresh(invitation)
    assert invitation.sent_at is None, "premise: regenerate cleared the send"
    assert invitation.last_reminder_at is not None, (
        "premise: regenerate left the reminder stamp alone"
    )

    body = client.get(
        f"/operator/sessions/{session.id}"
        f"/invitations/reviewers/{invitation.reviewer_id}"
    ).text
    facts = _invitation_facts(body)
    assert _CREATED in facts
    # Exactly one em-dash: Email sent is empty for the new token, Last
    # reminder still carries the old stamp.
    assert facts.count(_NO_DATE) == 1
    # No delivery pill — but note this test cannot prove the gate: its
    # outbox row is `sent`, which renders nothing under any gate.
    # `test_regenerate_clears_a_stale_delivery_pill` is the one that
    # discriminates.
    assert _DELIVERY("sent") not in facts


def test_detail_page_reports_a_failed_delivery(
    client: TestClient, db: Session
) -> None:
    """The Invitation card carries delivery state, `failed` included.

    Item 6 open question 5. `invitation.sent_at` says a send was
    attempted on the current token; the outbox row says what became of
    it. Rung 2a moved the card off the outbox for the *dates*, which
    was right — these are different facts — so the card now carries
    both rather than picking one.

    Nothing writes `failed` yet: `send_invitation` flips the row to
    `sent` in the same call, and Segment 14B Part A lights up the real
    transport that will. The status is set directly here because the
    column already accepts the model's full `EMAIL_OUTBOX_STATUSES`
    and the card must not wait for the producer to exist.
    """
    session = _ready_session(client, db, code="drill-failed")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    assert "failed" in EMAIL_OUTBOX_STATUSES, "premise: the model allows it"
    outbox.status = "failed"
    db.commit()

    facts = _invitation_facts(
        client.get(
            f"/operator/sessions/{session.id}"
            f"/invitations/reviewers/{invitation.reviewer_id}"
        ).text
    )
    # The send time stays — the attempt happened — and the state joins it.
    assert _CREATED in facts
    assert _DELIVERY("failed") in facts
    # One em-dash only, and it is Last reminder's: the send attempt
    # happened, so Email sent keeps its timestamp and gains the state
    # beside it rather than being replaced by it.
    assert facts.count(_NO_DATE) == 1


def test_detail_page_shows_no_delivery_pill_on_an_ordinary_send(
    client: TestClient, db: Session
) -> None:
    """`sent` is the ordinary case and earns no pill of its own.

    The counterpart to the test above: without this, rendering the
    status unconditionally would pass there and clutter every card.
    """
    session = _ready_session(client, db, code="drill-sent-ok")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    facts = _invitation_facts(
        client.get(
            f"/operator/sessions/{session.id}"
            f"/invitations/reviewers/{invitation.reviewer_id}"
        ).text
    )
    # Asserted as whole pill markup, not as the word: "sent" is a
    # substring of the label "Email sent:", so a bare `not in` here
    # would fail on the label and prove nothing about the pill.
    assert _DELIVERY("sent") not in facts, (
        "an ordinary send shows its timestamp, not a redundant pill"
    )
    assert "Email sent:" in facts, "premise: the label is there to be confused with"


def test_table_and_card_agree_on_a_failed_delivery(
    client: TestClient, db: Session
) -> None:
    """One fact, one reading, on both surfaces.

    19P.6 rung 3, after a cold read. Rung 2b gave the drill-in card a
    delivery-state pill and claimed the value was "rendered, never
    enumerated" — true of that template, false of this page: the table
    branched on `sent` / `queued` and sent everything else to an
    `{% else %}` printing the literal `not sent`. So a failed row read
    `not sent` in the table and `failed` one click away, which is the
    genre of contradiction this item exists to close.
    """
    session = _ready_session(client, db, code="tbl-card-agree")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    outbox.status = "failed"
    db.commit()

    table = client.get(f"/operator/sessions/{session.id}/invitations").text
    assert _DELIVERY("failed") in table
    assert _DELIVERY("not sent") not in table, (
        "the table must not relabel a failed delivery as never sent"
    )
    facts = _invitation_facts(
        client.get(
            f"/operator/sessions/{session.id}"
            f"/invitations/reviewers/{invitation.reviewer_id}"
        ).text
    )
    assert _DELIVERY("failed") in facts


def test_delivery_pill_does_not_need_a_send_timestamp(
    client: TestClient, db: Session
) -> None:
    """A failed send shows its state even with no delivery date.

    Codex, on 19P.6 rung 3's PR: the pill was gated on
    `invitation.sent_at`, so a `queued` / `sending` / `failed` row whose
    timestamp is still NULL rendered an em-dash and nothing else —
    hiding exactly what the pill exists to show. Unreachable today,
    because `send_invitation` writes `sent_at` and `status="sent"` in
    one breath, but the shape a 14B async dispatch would produce.

    Simulated by clearing `sent_at` while leaving `status` alone, which
    is precisely the divergence at issue. The counterpart —
    `test_detail_page_after_regenerate_reports_the_current_token` —
    pins the case that stops this from being a plain ungating: there
    `status` is back to `pending`, and no pill renders.
    """
    session = _ready_session(client, db, code="drill-nodate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    outbox.status = "failed"
    invitation.sent_at = None
    db.commit()
    assert invitation.status != "pending", (
        "premise: the current token has been sent, only the date is absent"
    )

    facts = _invitation_facts(
        client.get(
            f"/operator/sessions/{session.id}"
            f"/invitations/reviewers/{invitation.reviewer_id}"
        ).text
    )
    assert _DELIVERY("failed") in facts, (
        "the state must not depend on the timestamp being populated"
    )
    # The date slot is honestly empty — two facts, not one standing in
    # for the other.
    assert facts.count(_NO_DATE) == 2


def test_regenerate_clears_a_stale_delivery_pill(
    client: TestClient, db: Session
) -> None:
    """A rotated token reports nothing about the old token's delivery.

    This is the test that stops the pill from simply being ungated.
    Measured: after a send whose outbox row reads `failed`, a
    **Regenerate** leaves `invitation.sent_at` NULL and `status` back at
    `pending`, while `most_recent_invitation_status` still returns
    `failed` — the previous token's fate, for a token that has been
    rotated and never sent.

    Written after a mutation run showed the sibling regenerate test
    could not catch this: its outbox row is `sent`, which renders no
    pill under any gate, so removing the gate entirely still passed.
    """
    session = _ready_session(client, db, code="drill-stale-pill")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    outbox.status = "failed"
    db.commit()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/regenerate"
    )
    db.refresh(invitation)
    assert invitation.status == "pending", "premise: the token was rotated"
    assert (
        inv_service.most_recent_invitation_status(
            db, invitation_id=invitation.id
        )
        == "failed"
    ), "premise: the stale status is still what the outbox reports"

    facts = _invitation_facts(
        client.get(
            f"/operator/sessions/{session.id}"
            f"/invitations/reviewers/{invitation.reviewer_id}"
        ).text
    )
    assert _DELIVERY("failed") not in facts, (
        "the previous token's delivery must not be reported for this one"
    )


def test_per_row_remind_redirects_to_invitations_page(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="remind-redir")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/remind",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/operator/sessions/{session.id}/invitations"
    )


def test_invitations_remind_incomplete_bulk_endpoint(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="bulk-remind")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/remind-incomplete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/operator/sessions/{session.id}/invitations"
    )
    # A reminder outbox row was written.
    reminder_count = len(
        db.execute(
            select(EmailOutbox).where(
                EmailOutbox.session_id == session.id,
                EmailOutbox.kind == "reminder",
            )
        ).scalars().all()
    )
    assert reminder_count == 1


def test_invitations_remind_incomplete_409_while_session_draft(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, "bulk-draft")
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/remind-incomplete",
        follow_redirects=False,
    )
    assert response.status_code == 409


def test_send_invitation_populates_cc_bcc_from_override_json(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="cc-bcc")
    # Operator sets CC + BCC on the session's email_template_overrides
    # (the editor surface from Segment 11E PR 2 writes this same shape).
    session.email_template_overrides = {
        "invitation_cc": "ops@example.edu",
        "invitation_bcc": "audit@example.edu, archive@example.edu",
    }
    db.commit()

    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )

    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    assert outbox.cc_emails == "ops@example.edu"
    assert outbox.bcc_emails == "audit@example.edu, archive@example.edu"


def test_send_reminder_populates_cc_bcc_from_override_json(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="rem-cc-bcc")
    session.email_template_overrides = {
        "reminder_cc": "ops@example.edu",
        "reminder_bcc": "archive@example.edu",
    }
    db.commit()

    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/remind"
    )

    reminder = db.execute(
        select(EmailOutbox).where(
            EmailOutbox.invitation_id == invitation.id,
            EmailOutbox.kind == "reminder",
        )
    ).scalar_one()
    assert reminder.cc_emails == "ops@example.edu"
    assert reminder.bcc_emails == "archive@example.edu"


def test_send_omits_cc_bcc_when_overrides_blank(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="cc-bcc-blank")
    # No overrides set at all.
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    assert outbox.cc_emails is None
    assert outbox.bcc_emails is None


# --------------------------------------------------------------------------- #
# Filter strip — status + search (Segment 11C Part 1 follow-up)
# --------------------------------------------------------------------------- #


def _ready_session_with_two_reviewers(
    client: TestClient, db: Session, code: str
) -> ReviewSession:
    """Helper: ready session with two reviewers (rae + ren) so we can
    exercise filters that narrow to one row."""
    session = _create_session(client, db, code)
    client.post(
        f"/operator/sessions/{session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\n"
                b"Ren,ren@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, session.id)
    generate_via_page_button(client, session.id)
    _activate(client, session.id)
    db.refresh(session)
    return session


def test_invitations_filter_strip_renders(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="filt-strip")
    body = client.get(f"/operator/sessions/{session.id}/invitations").text
    # Status dropdown lands with the four mapped options + All.
    assert '<option value="all"' in body
    assert '<option value="not_sent"' in body
    assert '<option value="not_started"' in body
    assert '<option value="in_progress"' in body
    assert '<option value="submitted"' in body
    # Search input renders, no Clear link when no filter active.
    assert 'name="q"' in body
    assert ">Clear</a>" not in body


def _strip_datalist(body: str) -> str:
    """Return the response body with `<datalist>` blocks removed.

    The Manage Invitations / Responses typeahead datalist legitimately
    contains every option regardless of the active filter, so
    "excluded reviewer not in body" assertions need to look at
    everything *outside* the datalist."""
    return re.sub(r"<datalist[^>]*>.*?</datalist>", "", body, flags=re.DOTALL)


def test_the_count_line_sits_with_the_table_not_the_filter_row(
    client: TestClient, db: Session
) -> None:
    """Segment 19I Item 10 — the count moved out of `.filter-actions`
    to the top-left of the table card, in the rosters' class, so all
    seven preview pages report the same way in the same place.

    `Clear` and the submit stay in the actions row: they are actions,
    and the count is a report about the rows below.

    **19P.5 rung 3 moved the filter into the table card's toolbar**, so
    "with the table, not the filter row" is now a claim about the two
    panes rather than about two cards. The submit is `Search` there,
    not `Apply` — the label the other five pages use.
    """
    session = _ready_session_with_two_reviewers(client, db, "inv-count-line")

    body = client.get(
        f"/operator/sessions/{session.id}/invitations?q=rae"
    ).text

    # Left pane: what the table is showing.
    left = body[body.index('<div class="toolbar-pane toolbar-left">') :]
    left = left[: left.index('<div class="toolbar-pane toolbar-right">')]
    assert '<p class="muted table-showing-hint">' in left
    assert "Showing 1 reviewer." in left

    # Right pane's actions row: the controls, and no report.
    start = body.index('<div class="filter-actions">')
    actions = body[start : body.index("</div>", start)]
    assert "Showing" not in actions
    assert ">Clear</a>" in actions
    assert ">Search</button>" in actions
    assert ">Apply</button>" not in actions


def test_the_count_line_is_absent_when_no_filter_narrows(
    client: TestClient, db: Session
) -> None:
    """`Showing 2 of 2` is noise — the rule Item 4 set for the
    rosters, now shared. Note this page is **uncapped** by decision
    (19I Item 10), so the cap branch can never fire here: absent or
    the plain filter count are its only two states."""
    session = _ready_session_with_two_reviewers(client, db, "inv-count-quiet")

    body = client.get(f"/operator/sessions/{session.id}/invitations").text

    assert '<p class="muted table-showing-hint">' not in body
    assert "more not shown" not in body


def test_invitations_filter_status_narrows_rows(
    client: TestClient, db: Session
) -> None:
    session = _ready_session_with_two_reviewers(client, db, "filt-status")
    # Send invitation for Rae only — Ren stays "not sent".
    invitation_rae = db.execute(
        select(Invitation)
        .join(Invitation.reviewer)
        .where(Invitation.session_id == session.id)
        .order_by(Invitation.id)
    ).scalars().first()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation_rae.id}/send"
    )
    # Filter to "Not yet sent" → only Ren.
    body = _strip_datalist(client.get(
        f"/operator/sessions/{session.id}/invitations?status=not_sent"
    ).text)
    assert "ren@example.edu" in body
    assert "rae@example.edu" not in body
    # Clear link surfaces when filter is active.
    assert ">Clear</a>" in body
    # The count line renders — with the noun this page is organised
    # around. Invitations is one row per *reviewer*, so it says
    # "reviewers" even though the rows are invitations (19I Item 10).
    assert "Showing 1 reviewer." in body


def test_invitations_filter_search_narrows_rows(
    client: TestClient, db: Session
) -> None:
    session = _ready_session_with_two_reviewers(client, db, "filt-search")
    # Search by partial email.
    body = _strip_datalist(client.get(
        f"/operator/sessions/{session.id}/invitations?q=rae"
    ).text)
    assert "rae@example.edu" in body
    assert "ren@example.edu" not in body
    # Search is case-insensitive.
    body = _strip_datalist(client.get(
        f"/operator/sessions/{session.id}/invitations?q=REN"
    ).text)
    assert "ren@example.edu" in body


def test_invitations_filter_no_match_shows_empty_message(
    client: TestClient, db: Session
) -> None:
    session = _ready_session_with_two_reviewers(client, db, "filt-empty")
    body = client.get(
        f"/operator/sessions/{session.id}/invitations?q=nobody"
    ).text
    assert "No reviewers match the current filter." in body


# --------------------------------------------------------------------------- #
# Bulk regenerate-all (Segment 11C Part 1 follow-up)
# --------------------------------------------------------------------------- #


def test_regenerate_all_rotates_every_token_and_resets_status(
    client: TestClient, db: Session
) -> None:
    session = _ready_session_with_two_reviewers(client, db, "regen-all-rot")
    # Send Rae's invitation so its status is "sent" and we can confirm
    # regenerate-all flips it back to "pending".
    rae_invitation = db.execute(
        select(Invitation)
        .join(Invitation.reviewer)
        .where(Invitation.session_id == session.id)
        .order_by(Invitation.id)
    ).scalars().first()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{rae_invitation.id}/send"
    )
    db.refresh(rae_invitation)
    rae_old_hash = rae_invitation.token_hash
    assert rae_invitation.status == "sent"

    response = client.post(
        f"/operator/sessions/{session.id}/invitations/regenerate-all",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/operator/sessions/{session.id}/invitations"
    )

    rows = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalars().all()
    assert len(rows) == 2
    for inv in rows:
        assert inv.status == "pending"
        assert inv.sent_at is None
        assert inv.opened_at is None
    db.refresh(rae_invitation)
    assert rae_invitation.token_hash != rae_old_hash


def test_regenerate_all_writes_single_batch_audit_event(
    client: TestClient, db: Session
) -> None:
    session = _ready_session_with_two_reviewers(client, db, "regen-all-audit")
    client.post(
        f"/operator/sessions/{session.id}/invitations/regenerate-all"
    )

    audit_rows = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == session.id,
            AuditEvent.event_type == "invitations.regenerated",
        )
    ).scalars().all()
    assert len(audit_rows) == 1
    detail = audit_rows[0].detail
    assert detail is not None
    updated = detail["set_changes"]["updated"]
    assert len(updated) == 2
    assert all("invitation_id" in entry and "reviewer_id" in entry for entry in updated)


def test_regenerate_all_409_while_session_draft(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, "regen-all-draft")
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/regenerate-all",
        follow_redirects=False,
    )
    assert response.status_code == 409


def test_regenerate_all_with_zero_invitations_writes_no_audit(
    client: TestClient, db: Session
) -> None:
    session = _ready_session_without_invitations(client, db, "regen-all-empty")
    # Don't generate invitations.
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/regenerate-all",
        follow_redirects=False,
    )
    assert response.status_code == 303
    audit_rows = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == session.id,
            AuditEvent.event_type == "invitations.regenerated",
        )
    ).scalars().all()
    assert audit_rows == []


def test_invitations_info_card_omits_bulk_action_buttons(
    client: TestClient, db: Session
) -> None:
    """The info card on the Invitations page retired its bulk-
    action buttons (Generate invitations / Send all pending /
    Regenerate all / Send reminders) with the
    Workflow-card-as-Operations-chrome rollout. The card now
    reports an eight-counter lifecycle inventory only; the
    affordances those buttons covered live on the Workflow card's
    Create / Send invites / Send reminders super-buttons. The
    /invitations/regenerate-all route stays alive for the per-
    invitation regenerate flow (still surfaced in the per-row
    actions column)."""
    session = _ready_session(client, db, code="regen-all-btn")
    body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    # The card itself renders with its new info-list shape.
    assert 'id="invitations-info-card"' in body
    # Bulk-action buttons retire.
    assert "Regenerate all" not in body
    assert "Send all pending" not in body
    # The eight counters are present.
    for label in (
        "Eligible reviewers",
        "Invitations created",
        "Invitations sent",
        "Pending invitations",
        "Reminders sent",
        "Pending reminders",
        "Completed reviews",
        "Incomplete reviews",
    ):
        assert f">{label}\n" in body or label in body, label


# --------------------------------------------------------------------------- #
# 19Q Item 2 rung 1 — Send all respects eligibility
# --------------------------------------------------------------------------- #


def _two_reviewer_validated_session(
    client: TestClient, db: Session, code: str
) -> ReviewSession:
    """A prepared session with two assigned, active reviewers."""
    session = _create_session(client, db, code)
    client.post(
        f"/operator/sessions/{session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\n"
                b"Rae,rae@example.edu\nSam,sam@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, session.id)
    generate_via_page_button(client, session.id)
    response = client.post(
        f"/operator/sessions/{session.id}/workflow/prepare",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(session)
    return session


def _strand_an_invitation(
    client: TestClient, db: Session, session: ReviewSession, email: str
) -> Reviewer:
    """Invite both reviewers, then make one ineligible and re-Prepare.

    This is the live sequence, not a contrived one. `bulk_inactivate`
    flips `Reviewer.status` and leaves the invitation alone — stated at
    `app/web/routes_operator/_operations.py:561` — and lifecycle never
    deletes invitation rows (`scheduled_events/_invites.py:167-171`
    states the invariant; the only `delete(Invitation)` in the tree is
    `app/services/session_purge.py`), so the row survives
    the round trip to `draft` and back. The reviewer is then off the
    Manage Invitations table, which lists
    `monitoring.per_reviewer_progress` (assigned **and** active), while
    their `pending` row is still in the send set.
    """
    assert _pending_count(db, session.id) == 2

    stranded = db.execute(
        select(Reviewer).where(
            Reviewer.session_id == session.id, Reviewer.email == email
        )
    ).scalar_one()
    response = client.post(
        f"/operator/sessions/{session.id}/reviewers/bulk-inactivate",
        data={"reviewer_ids": [stranded.id]},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    # The edit invalidated the session; Prepare again so Send all is live.
    response = client.post(
        f"/operator/sessions/{session.id}/workflow/prepare",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    db.refresh(stranded)
    db.refresh(session)
    assert stranded.status != "active"
    # `workflow_prepare` answers 303 on a *failed* validation too, so
    # the status code above says nothing about the state we are in.
    # Without this the send-all tests could be exercising a 409 rather
    # than a filtered send.
    assert session.status in {"validated", "ready"}, (
        f"session is {session.status}; the re-Prepare did not validate, "
        "so Send all would 409 and these tests would prove nothing"
    )
    assert _pending_count(db, session.id) == 2, (
        "the stranded invitation must survive — if lifecycle started "
        "deleting these rows this test would pass for the wrong reason"
    )
    return stranded


def _pending_count(db: Session, session_id: int) -> int:
    return len(
        db.execute(
            select(Invitation).where(
                Invitation.session_id == session_id,
                Invitation.status == "pending",
            )
        ).scalars().all()
    )


def test_send_all_skips_a_reviewer_who_is_no_longer_eligible(
    client: TestClient, db: Session
) -> None:
    """19Q Item 2 rung 1 — the operator Send all button.

    The Manage Invitations table lists only assigned, active reviewers,
    so before this fix the operator saw one row and the button emailed
    two people. **The page and the button disagreed about who is in
    the session**, and the one the operator could not see is the one
    who got the mail.
    """
    session = _two_reviewer_validated_session(db=db, client=client, code="sa-elig")
    stranded = _strand_an_invitation(client, db, session, "sam@example.edu")

    response = client.post(
        f"/operator/sessions/{session.id}/invitations/send-all",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    recipients = {
        row.to_email
        for row in db.execute(
            select(EmailOutbox).where(EmailOutbox.session_id == session.id)
        ).scalars()
    }
    assert recipients == {"rae@example.edu"}, (
        f"Send all emailed {sorted(recipients)}; `{stranded.email}` is "
        "inactive and off the Manage Invitations table"
    )


def test_send_all_leaves_the_ineligible_invitation_pending(
    client: TestClient, db: Session
) -> None:
    """Skipped, not consumed.

    Rung 1 filters the send set; it does not prune rows — that is
    explicitly out of scope, because deleting one risks removing a
    *sent* invitation still live in a reviewer's inbox. So the row must
    still be `pending` afterwards, ready to send if the reviewer is
    reactivated.
    """
    session = _two_reviewer_validated_session(db=db, client=client, code="sa-keep")
    stranded = _strand_an_invitation(client, db, session, "sam@example.edu")

    response = client.post(
        f"/operator/sessions/{session.id}/invitations/send-all",
        follow_redirects=False,
    )
    # Both assertions below are satisfied by a send that never
    # happened — a 409 from `_require_validated_or_ready`, a 500, or a
    # Send all that became a total no-op would all leave the row
    # `pending` with a null `sent_at`. So prove a send *did* happen
    # first, and that the eligible reviewer got theirs.
    assert response.status_code == 303, response.text
    mailed = {
        row.to_email
        for row in db.execute(
            select(EmailOutbox).where(EmailOutbox.session_id == session.id)
        ).scalars()
    }
    assert mailed == {"rae@example.edu"}

    row = db.execute(
        select(Invitation).where(
            Invitation.session_id == session.id,
            Invitation.reviewer_id == stranded.id,
        )
    ).scalar_one()
    assert row.status == "pending"
    assert row.sent_at is None


def test_send_all_skips_an_active_reviewer_with_no_included_assignment(
    client: TestClient, db: Session
) -> None:
    """The other half of ineligibility, which had no test.

    `bulk_inactivate` was the only path exercised, and it moves
    `Reviewer.status`. Eligibility has a second limb — at least one
    `include=True` assignment — and a filter checking only the status
    would pass every other test in this file.

    **The exclusion is set directly, and the first draft of this test
    proved why.** It used `POST /assignments/bulk-inactivate` and then
    re-Prepared, and failed: Sam was mailed anyway. `workflow_prepare`
    runs `assignments.replace_assignments`
    (`app/web/routes_operator/_workflow.py:145`), which re-materialises
    every row from the instrument's pinned rule set
    (`app/services/assignments/_generate.py:826`), so a per-row
    exclusion is gone by the time Send all is reachable — the session
    has to pass through Prepare to be sendable at all. In the field
    this state comes from a **rule** that excludes the reviewer's
    pairs, which regeneration reproduces rather than undoes. Writing
    the column is the honest short-cut to that state; going through
    the rule engine would test the rule engine.
    """
    session = _two_reviewer_validated_session(db=db, client=client, code="sa-unassigned")
    assert _pending_count(db, session.id) == 2

    stranded = db.execute(
        select(Reviewer).where(
            Reviewer.session_id == session.id,
            Reviewer.email == "sam@example.edu",
        )
    ).scalar_one()
    rows = list(
        db.execute(
            select(Assignment).where(
                Assignment.session_id == session.id,
                Assignment.reviewer_id == stranded.id,
            )
        ).scalars()
    )
    assert rows, "fixture produced no assignments to exclude"
    for assignment in rows:
        assignment.include = False
    db.flush()
    db.commit()

    db.refresh(stranded)
    db.refresh(session)
    assert stranded.status == "active", (
        "this test is about the assignment limb; if the reviewer went "
        "inactive it collapses into the sibling test"
    )
    assert session.status in {"validated", "ready"}

    response = client.post(
        f"/operator/sessions/{session.id}/invitations/send-all",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    mailed = {
        row.to_email
        for row in db.execute(
            select(EmailOutbox).where(EmailOutbox.session_id == session.id)
        ).scalars()
    }
    assert mailed == {"rae@example.edu"}


def test_pending_counter_counts_what_send_all_can_actually_send(
    client: TestClient, db: Session
) -> None:
    """The info-card pill and the button must agree.

    "Pending invitations" is a nonzero-is-attention pill
    (`spec/operations_pages.md`), so a count the operator cannot clear
    is worse than no count. Filtering the send set without filtering
    this counter would have left an ineligible reviewer's row showing
    amber permanently, with no control on the page able to act on it —
    the rung moving its own defect from the button to the counter
    rather than removing it.
    """
    session = _two_reviewer_validated_session(db=db, client=client, code="sa-pill")
    _strand_an_invitation(client, db, session, "sam@example.edu")

    client.post(
        f"/operator/sessions/{session.id}/invitations/send-all",
        follow_redirects=False,
    )

    rows = invitations_view_rows = inv_service.list_sendable_invitations(
        db, session.id
    )
    assert rows == [], "the eligible invitation was sent, so nothing is sendable"
    assert invitations_view_rows == []

    body = client.get(f"/operator/sessions/{session.id}/invitations").text
    assert "Pending invitations" in body
    # The stranded row is still `pending` in the table, and must not be
    # counted here — the counter is about what can still be sent.
    assert _pending_count(db, session.id) == 1
    marker = body.split("Pending invitations", 1)[1][:200]
    assert 'pill-count">0<' in marker, (
        "the Pending invitations pill still counts the unsendable row; "
        f"saw: {marker!r}"
    )


def test_send_one_refuses_a_reviewer_the_bulk_paths_would_skip(
    client: TestClient, db: Session
) -> None:
    """All three send paths agree, not two of three.

    The per-row Send button renders only for rows the table lists, so
    this is reachable by a direct POST or a stale tab. Before rung 1
    the route's own comment said it matched "the bulk send-path's
    active-only gate" — true when the bulk path had no gate at all,
    and a half-truth in the other direction once the bulk paths
    filtered on assigned-and-active.
    """
    session = _two_reviewer_validated_session(db=db, client=client, code="sa-one")
    stranded = _strand_an_invitation(client, db, session, "sam@example.edu")

    invitation = db.execute(
        select(Invitation).where(
            Invitation.session_id == session.id,
            Invitation.reviewer_id == stranded.id,
        )
    ).scalar_one()
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send",
        follow_redirects=False,
    )
    assert response.status_code == 409, response.text

    assert db.execute(
        select(EmailOutbox).where(EmailOutbox.to_email == stranded.email)
    ).first() is None


def test_an_open_session_with_no_invitations_is_told_a_remedy_it_can_reach(
    client: TestClient, db: Session
) -> None:
    """The copy must name an action the state actually offers.

    19Q Item 2 rung 3's first attempt told a `ready` operator to
    "include an assignment for an active reviewer and run Prepare
    session again". Measured in that state: the Prepare button is not
    rendered (`prepare_visible` is `(is_draft and not is_setup_empty)
    or is_validated`), `POST /workflow/prepare` 303s to
    `super_step=precondition`, and every roster mutator 409s on
    `_require_editable`. **Both named remedies were unreachable in the
    only state where the copy renders** — found by the item's
    cumulative cold read, not by any test, which is why this exists.

    Revert is the way back, and it is not free: it closes every
    accepting instrument (`session_lifecycle.py`), so the copy says
    that rather than letting the operator discover it.
    """
    session = _ready_session_without_invitations(client, db, "open-noinv")

    # The premise, asserted rather than assumed — if Prepare ever
    # becomes reachable from `ready`, this test should fail and the
    # copy should go back to naming it.
    assert (
        client.post(
            f"/operator/sessions/{session.id}/workflow/prepare",
            follow_redirects=False,
        ).headers["location"].find("super_step=precondition")
        != -1
    ), "Prepare is reachable from `ready` now; the copy below is stale"

    body = client.get(f"/operator/sessions/{session.id}").text
    assert "no invitations exist" in body
    assert "Revert to draft" in body
    assert "stops responses" in body
    assert "next-action-prepare-form" not in body, (
        "the Prepare button renders here after all"
    )


def _next_action_body(page: str) -> str:
    """The Workflow card's prose block, without its button row.

    Sliced rather than searched, because two of the three strings below
    occur elsewhere on the page. Measured on a rendered State 2 page:
    `"validate"` appears 9 more times, almost all of them
    `--lifecycle-validated-*` custom properties in `base.html`'s inline
    stylesheet, and `"invitation"` once more in the Operations nav
    tab's href. Only `"assignment pairs"` is unique to the copy, so a
    whole-page `in` would pass vacuously on the other two.
    """
    start = page.index('<div class="next-action-body">')
    return page[start : page.index("</div>", start)]


def test_the_copy_that_prompts_prepare_names_what_prepare_does(
    client: TestClient, db: Session
) -> None:
    """State 2 is the only Workflow-card copy an operator reads
    *before* pressing Prepare, and until 19Q Item 3 it named two of
    Prepare's three effects — the assignment pairs and the validation,
    but not the invitations 19Q Item 2 rung 2 moved into
    ``workflow_prepare``. States 4 and 7 both name invitation creation,
    so the card explained it only to an operator who had already run
    the thing, or who had reached a state where running it was the
    remedy.

    Nothing asserted this string, which is how it stayed stale through
    the rung that made it wrong: ``ready for prime time`` appeared in
    ``spec/workflow_card.md`` and in no test at all.

    Pinned by **effect**, not by sentence. The three claims must be
    named, and the third must also be true — a copy test that only
    greps for the word would still pass on the day Prepare stopped
    creating invitations, which is the failure worth catching.
    """
    session = _create_session(client, db, "state2-copy")
    _populate(client, db, session.id, reviewer_email="rae@example.edu")

    card = _next_action_body(client.get(f"/operator/sessions/{session.id}").text)

    # The premise: this is State 2 — Prepare is offered, and it has not
    # run, so no invitations exist yet.
    assert "next-action-prepare-form" in card
    assert not inv_service.has_invitations(db, session.id)

    for claim in ("assignment pairs", "invitation", "validate"):
        assert claim in card, f"State 2 copy does not name {claim!r}: {card}"

    # And the claim the copy gained is true from exactly this state.
    response = client.post(
        f"/operator/sessions/{session.id}/workflow/prepare",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert "super_status=failed" not in response.headers["location"]
    assert inv_service.has_invitations(db, session.id)


def test_state_6_copy_does_not_claim_reviewers_were_told(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """State 6 — invitations sent — used to read "Reviewers have been
    notified that the review will open."

    Nothing notifies. `generate_invitations`' send path writes an
    `EmailOutbox` row and flips it `queued` → `sent` in one transaction;
    `app/services/email_send.py` says "Nothing in the app calls this
    yet." The claim reached the Guide by being copied out of this card
    (19Q Item 3 rung 2's cold read), so the card is where it had to be
    fixed.

    **Pinned by the fact that makes the copy true, not by the copy.**
    The transport is asserted unreachable during a real send, so the
    day someone wires it this test fails and the sentence gets revisited
    rather than quietly becoming wrong in the other direction.
    """
    called: list[object] = []
    monkeypatch.setattr(
        email_send,
        "transport_for",
        lambda *a, **k: called.append(a) or (_ for _ in ()).throw(
            AssertionError("transport_for was called")
        ),
    )
    session = _validated_session(client, db, "state6-copy")
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/send-all",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    assert not called, "a transport was constructed; the copy below is now wrong"
    assert inv_service.has_sent_invitations(db, session.id)

    card = _next_action_body(client.get(f"/operator/sessions/{session.id}").text)
    assert "no mail leaves the app" in card
    assert "have been notified" not in card
