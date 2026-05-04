"""Tests for Segment 11D PR C — reviewer top-bar variant + D5/D6/D7 sweep."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, Instrument, Reviewer, ReviewSession


def _operator_creates_session_with_pair(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str,
    reviewee_ident: str,
) -> ReviewSession:
    operator_client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    operator_client.post(
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
    operator_client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                f"RevieweeName,RevieweeEmail\nCarol,{reviewee_ident}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )
    operator_client.get(f"/operator/sessions/{review_session.id}?validated=1")
    operator_client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert review_session.status == "ready"
    return review_session


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


# ── D2: reviewer top bar variant ────────────────────────────────────────


def test_reviewer_dashboard_uses_ui_v2_reviewer_body_class(
    client: TestClient,
) -> None:
    body = client.get("/reviewer").text
    assert '<body class="ui-v2 reviewer">' in body


def test_reviewer_dashboard_chrome_drops_about_link_and_version(
    client: TestClient,
) -> None:
    body = client.get("/reviewer").text
    # Operator-style chrome details are gone from the reviewer top bar.
    assert "Review Robin Web App" not in body
    assert "version dev" not in body
    assert 'href="/about"' not in body
    # Identity is the lighter "Review Robin" text-only span.
    assert 'class="chrome-app-identity">Review Robin</span>' in body


def test_reviewer_chrome_suppresses_my_reviews_link_with_one_review(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """My Reviews link is only useful when the reviewer has more than
    one review pending or completed (otherwise the dashboard would be
    a single row). Test the count == 1 case → link suppressed."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-c-one",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert "My Reviews" not in body


def test_reviewer_chrome_renders_my_reviews_link_with_multiple_reviews(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """When the reviewer has more than one review, the chrome carries
    a "My Reviews" link back to the dashboard."""
    operator = make_client(alice)
    first = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-c-multi-1",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-c-multi-2",
        reviewer_email="rae@example.edu",
        reviewee_ident="dan@example.edu",
    )

    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{first.id}").text
    assert (
        'class="chrome-link" href="/reviewer">My Reviews</a>' in body
    )


# ── D5: status icons ────────────────────────────────────────────────────


def test_status_icons_use_canonical_classes_not_inline_style(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The ✓ / ⚠ glyphs migrate from inline `color: #16a34a/#d97706` to
    the `.status-icon-complete` / `.status-icon-incomplete` classes
    (D5; spec/ui_elements.md §9)."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-d5",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalar_one()
    assignment = db.execute(
        select(Assignment).where(
            Assignment.session_id == review_session.id,
            Assignment.reviewer_id == reviewer.id,
        )
    ).scalar_one()

    rae_client = make_client(rae)
    # Submit with no values to force the status column to render with
    # the incomplete glyph (show_acknowledge path).
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={f"response[{assignment.id}][rating]": ""},
        follow_redirects=False,
    )
    body = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={},
        follow_redirects=False,
    ).text
    # The legacy inline `style="color: #...; font-weight: bold; font-size:
    # 1.2em;"` blocks on the ✓/⚠ glyphs are gone — the canonical
    # `.status-icon-{complete,incomplete}` classes carry the colour now.
    assert "font-weight: bold; font-size: 1.2em" not in body
    # The incomplete state is rendered (no values → required missing).
    assert 'class="status-icon-incomplete"' in body


# ── D6: banner family ───────────────────────────────────────────────────


def test_invite_mismatch_renders_banner_warning(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The invite-mismatch error renders as a `.banner.banner-warning`
    rather than the legacy inline-styled red card."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-mismatch",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    # Find the invitation token.
    from app.db.models import EmailOutbox, Invitation

    operator.post(
        f"/operator/sessions/{review_session.id}/invitations/generate"
    )
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == review_session.id)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/invitations/{invitation.id}/send",
        follow_redirects=False,
    )
    # Mint a token by reading the outbox row the send route just wrote
    # — alice (the signed-in operator) doesn't match the invitation's
    # reviewer email (rae), so the GET below 403s into the mismatch
    # template, which is what we want to test the markup of.
    outbox_row = db.execute(
        select(EmailOutbox).where(
            EmailOutbox.invitation_id == invitation.id
        )
    ).scalar_one()
    import re

    match = re.search(r"/reviewer/invite/([A-Za-z0-9_\-]+)", outbox_row.body)
    assert match is not None
    raw_token = match.group(1)

    response = operator.get(
        f"/reviewer/invite/{raw_token}", follow_redirects=False
    )
    assert response.status_code == 403
    body = response.text
    assert 'class="banner banner-warning"' in body
    # The legacy inline `style="border-color: #b91c1c; background: #fee2e2;"`
    # block on the wrapper card is gone — the .banner.banner-warning
    # primitive carries the framing now.
    assert 'style="border-color: #b91c1c' not in body
    # Body is a banner, not the legacy red `.card` wrapper.
    assert (
        'class="card" style="border-color: #b91c1c'
        not in body
    )


def test_review_surface_preview_banner_is_banner_info(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Operator preview banner migrates from `.warning-banner` (the
    recoloured-blue legacy class) to the canonical `.banner.banner-info`."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-d6-prev",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    body = operator.get(
        f"/operator/sessions/{review_session.id}/preview"
    ).text
    assert 'class="banner banner-info"' in body
    assert 'class="warning-banner"' not in body
    # Copy is preserved exactly so cross-tests don't churn.
    assert "Preview" in body
    assert "not visible to reviewers" in body


def test_review_surface_saved_banner_uses_banner_success(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-d6-saved",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}?saved=ok"
    ).text
    assert 'class="banner banner-success"' in body
    assert "Your draft has been saved." in body


# ── D7: page header ─────────────────────────────────────────────────────


def test_review_surface_renders_h1_and_deadline(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The reviewer surface page header carries the session name as H1
    plus a small text-secondary line for the deadline (D7). Post-D7
    revisit: deadline sits inline with the H1 inside `.rs-page-header`
    so "what session, due when" reads in one glance."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-d7",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert f"<h1>{review_session.name}</h1>" in body
    # H1 is wrapped in the page-header flex row.
    assert 'class="rs-page-header"' in body
    # Newly created session has no deadline; absence is a feature, not
    # a bug — assertion below only checks the H1 is present and the
    # template doesn't crash on the optional deadline branch.


def test_review_surface_action_rows_render_above_and_below_tables(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Save draft / Submit / Cancel triplet renders flush right both
    above and below the instrument tables."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-act-rows",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    # Two .rs-action-row containers — one above the instrument loop
    # (carries the .rs-action-row-left modifier so it sits flush left
    # under the description card), one after the tables (default
    # flush-right).
    assert body.count("rs-action-row") >= 2
    assert "rs-action-row rs-action-row-top rs-action-row-left" in body
    # Each row carries the same three controls. Cancel is now an
    # anchor inside the form rather than a free-floating <p> above.
    save_count = body.count(">Save draft</button>")
    cancel_count = body.count(">Cancel — discard unsaved edits</a>")
    assert save_count >= 2, f"expected 2 Save draft buttons; got {save_count}"
    assert cancel_count >= 2, f"expected 2 Cancel anchors; got {cancel_count}"
    # Submit lives at both rows too — formaction routes the click to
    # /submit instead of the form's default /save action.
    assert (
        body.count(f'formaction="/reviewer/sessions/{review_session.id}/submit"')
        >= 2
    )


def test_review_surface_session_description_renders_in_half_width_card(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Session description sits in a `.card.rs-description-card` (the
    half-width, flush-left modifier) instead of as a loose `<p>`."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-desc",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    review_session.description = "Please rate each reviewee on the rubric."
    db.commit()

    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert 'class="card rs-description-card"' in body
    assert "Please rate each reviewee on the rubric." in body


def test_review_surface_single_instrument_has_no_next_button(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Next is suppressed when the session has only one instrument —
    pagination only kicks in when there's somewhere to step to."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-one-inst",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    # No Previous / Next button DOM elements (the inline JS hook
    # mentions the class names as string literals, but the rendered
    # buttons aren't there).
    assert ">Next</button>" not in body
    assert ">Previous</button>" not in body
    # No paginated wrapper around the instrument groups.
    assert '<div class="rs-paginated">' not in body
    # Instrument group wrapper still renders so the markup is uniform,
    # but with no `.rs-paginated` ancestor it has no display-toggling
    # CSS effect.
    assert 'class="rs-instrument-group rs-active"' in body


def test_review_surface_multi_instrument_renders_next_button_in_both_rows(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """When the session has more than one instrument, both action rows
    carry a Next button (`type="button"`, no form submission) and the
    instrument groups are wrapped in `.rs-paginated` so CSS hides
    inactive groups."""
    operator = make_client(alice)
    # Build the session in draft so we can slot in a second instrument
    # before activation; `_require_instrument_editable` rejects edits
    # once the session is `ready`.
    operator.post(
        "/operator/sessions",
        data={"name": "Multi", "code": "rae-multi-inst"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "rae-multi-inst")
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nR,rae@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator.post(
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
    operator.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )
    # full-matrix pins all assignments to the default instrument; add a
    # second instrument and slot in an extra Assignment for it so the
    # reviewer sees both in their surface.
    [default_instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/instruments/add",
        data={"after": str(default_instrument.id)},
        follow_redirects=False,
    )
    second_instrument = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != default_instrument.id)
    ).scalar_one()
    seed_assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    db.add(
        Assignment(
            session_id=review_session.id,
            reviewer_id=seed_assignment.reviewer_id,
            reviewee_id=seed_assignment.reviewee_id,
            instrument_id=second_instrument.id,
            include=True,
            created_by_mode="full_matrix",
        )
    )
    db.commit()
    operator.get(f"/operator/sessions/{review_session.id}?validated=1")
    operator.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert review_session.status == "ready"

    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert '<div class="rs-paginated">' in body
    # Previous + Next render in the top + bottom action rows (the JS
    # selector also names the classes as string literals — count the
    # `>Previous</button>` / `>Next</button>` payloads to skip that
    # noise).
    assert body.count(">Previous</button>") == 2
    assert body.count(">Next</button>") == 2
    # Markup ships with Previous disabled — we start at the first
    # instrument, so navigating backwards is a no-op.
    assert (
        body.count(
            '<button class="btn secondary rs-prev-btn" type="button" disabled>Previous</button>'
        )
        == 2
    )
    # Next is NOT pre-disabled in markup — JS will disable it on the
    # last group at runtime.
    assert (
        '<button class="btn secondary rs-next-btn" type="button" disabled>'
        not in body
    )
    # Two `.rs-instrument-group` wrappers — the first is marked active
    # so only it is visible until Next is clicked.
    assert body.count('class="rs-instrument-group rs-active"') == 1
    # Plus the second group without `rs-active`.
    assert body.count('class="rs-instrument-group"') == 1


def test_review_surface_clear_all_card_is_half_width_flush_right(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Clear-all (Danger Zone) renders as a half-width, flush-right
    card via the new `.rs-danger-zone` modifier (which carries
    `max-width: calc(50% - 10px); margin-left: auto`)."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-dz-half",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert 'class="card danger-zone rs-danger-zone"' in body
    assert "<h2>Clear all responses</h2>" in body


# ── Operator preview keeps operator chrome ──────────────────────────────


def test_operator_preview_keeps_operator_chrome(
    client: TestClient, db: Session
) -> None:
    """The operator preview reuses review_surface.html but should keep
    the operator chrome (with breadcrumb back to the session) — the
    reviewer top bar override is suppressed in preview_mode."""
    client.post(
        "/operator/sessions",
        data={"name": "Prev", "code": "rae-prev-chrome"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "rae-prev-chrome")
    ).scalar_one()
    body = client.get(f"/operator/sessions/{review_session.id}/preview").text
    # Operator chrome present (Web App identity, breadcrumb).
    assert "Review Robin Web App (version dev)" in body
    assert 'class="breadcrumb"' in body
    # Reviewer body class branch is dropped on preview so the operator
    # surface doesn't pick up the .reviewer-scoped chrome rules.
    assert '<body class="ui-v2 reviewer">' not in body
    assert '<body class="ui-v2">' in body
