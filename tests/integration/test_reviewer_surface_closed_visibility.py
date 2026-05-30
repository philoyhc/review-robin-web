"""Reviewer surface visibility when the session is closed via the
Workflow card's Close session button.

The per-instrument ``responses_visible_when_closed`` toggle is
supposed to keep the reviewer's saved values visible on the
surface after the instrument closes. PR #1480 wired Close
session (``ready → expired``) and relaxed the surface's master
gate to render in ``expired`` too. This file pins the end-to-end
visibility contract: a reviewer who submits responses, then has
the session closed under them, should still read their own
submissions on the surface — but only on instruments whose
``responses_visible_when_closed`` flag is True.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    Instrument,
    ReviewSession,
)
from app.main import app
from app.services import session_lifecycle as lifecycle
from app.web.deps import get_current_user

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _restore_operator_identity(operator: AuthenticatedUser) -> None:
    """Re-install the operator's ``get_current_user`` override so a
    subsequent operator-route POST resolves to her, not whichever
    reviewer was last installed by ``make_client``. The conftest's
    ``app.dependency_overrides`` is global across the test, so
    swapping between operator + reviewer clients requires putting
    the override back before each side's calls."""
    app.dependency_overrides[get_current_user] = lambda: operator


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


def _seed_session_with_rae_and_one_reviewee(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str,
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
                f"ReviewerName,ReviewerEmail\nRae,{reviewer_email}\n".encode(),
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
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator_client, review_session.id)
    return review_session


def _activate(
    operator_client: TestClient, review_session: ReviewSession
) -> None:
    operator_client.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        follow_redirects=False,
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )


def _submit_rating(
    rae_client: TestClient,
    review_session: ReviewSession,
    rating_value: str,
    comments_value: str,
    db: Session,
) -> None:
    """Type rating + comments on every assignment row, save, submit."""
    assignment_ids = [
        a.id
        for a in db.execute(
            select(Assignment).where(
                Assignment.session_id == review_session.id
            )
        ).scalars()
    ]
    data: dict[str, str] = {}
    for aid in assignment_ids:
        data[f"response[{aid}][rating]"] = rating_value
        data[f"response[{aid}][comments]"] = comments_value
    save_resp = rae_client.post(
        f"/me/sessions/{review_session.id}/1/save",
        data=data,
        follow_redirects=False,
    )
    assert save_resp.status_code in (200, 303), save_resp.text[:500]
    submit_resp = rae_client.post(
        f"/me/sessions/{review_session.id}/submit",
        follow_redirects=False,
    )
    assert submit_resp.status_code == 303, submit_resp.text[:500]


def test_close_session_with_show_when_closed_preserves_reviewer_visibility(
    client: TestClient,
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """With ``responses_visible_when_closed=True`` set BEFORE the
    operator clicks Close session, the reviewer's submitted values
    must still be visible on the surface after the session goes
    ``expired``.

    This is the user-reported regression scenario: 'Show when
    closed' on the Instruments page wasn't keeping responses
    visible to the reviewer after a closed session.
    """
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="vis-closed", reviewer_email=rae.email
    )
    _activate(client, review_session)
    db.refresh(review_session)
    assert lifecycle.is_ready(review_session)

    # Flip Show-when-closed ON for the (single) instrument before
    # the reviewer submits — mirrors the operator's pre-close
    # workflow.
    instrument = db.execute(
        select(Instrument).where(
            Instrument.session_id == review_session.id
        )
    ).scalar_one()
    flip_resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{instrument.id}/visibility",
        data={"visible_when_closed": "true"},
        follow_redirects=False,
    )
    assert flip_resp.status_code == 303
    db.refresh(instrument)
    assert instrument.responses_visible_when_closed is True

    # Reviewer types + submits.
    rae_client = make_client(rae)
    _submit_rating(
        rae_client, review_session, rating_value="5",
        comments_value="great review", db=db,
    )

    # Operator closes the session. Re-install Alice's override
    # so the workflow route resolves to the operator, not Rae.
    _restore_operator_identity(alice)
    close_resp = client.post(
        f"/operator/sessions/{review_session.id}/workflow/close",
        follow_redirects=False,
    )
    assert close_resp.status_code == 303
    db.refresh(review_session)
    assert lifecycle.is_expired(review_session)
    db.refresh(instrument)
    assert instrument.accepting_responses is False
    # ``responses_visible_when_closed`` survives the close flip.
    assert instrument.responses_visible_when_closed is True

    # Reviewer reloads the surface. The values must appear in the
    # disabled inputs — this is the user-facing contract that the
    # bug report says is broken. Reinstall Rae's override first
    # since the workflow_close just swapped back to Alice.
    app.dependency_overrides[get_current_user] = lambda: rae
    body = rae_client.get(
        f"/me/sessions/{review_session.id}/1"
    ).text
    # The numeric input renders ``value="5"`` and the comments
    # textarea inlines the text as its text content.
    assert 'value="5"' in body, (
        "rating value missing — responses_visible_when_closed=True "
        "should have preserved it on the closed-session surface"
    )
    assert "great review" in body, (
        "comments value missing — responses_visible_when_closed=True "
        "should have preserved it on the closed-session surface"
    )
    # Sanity: the surface IS rendering the closed form (disabled
    # inputs), not redirecting / showing pre_open.html.
    assert "Review opens later" not in body
    assert "disabled" in body


def test_show_when_closed_flipped_after_close_takes_effect(
    client: TestClient,
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """The operator's likely real-world flow: forgot to set Show-
    when-closed before closing, flips it on after. The toggle
    must still take effect — the visibility route is
    deliberately not gated by ``_require_instrument_editable``,
    so it accepts the flip on an ``expired`` session.

    This test pins that contract end-to-end: post-close toggle
    flips, reviewer reloads the surface, sees their values.
    """
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="vis-after", reviewer_email=rae.email
    )
    _activate(client, review_session)
    instrument = db.execute(
        select(Instrument).where(
            Instrument.session_id == review_session.id
        )
    ).scalar_one()

    # Reviewer types + submits while the session is open.
    rae_client = make_client(rae)
    _submit_rating(
        rae_client, review_session, rating_value="5",
        comments_value="great review", db=db,
    )

    # Operator closes the session without flipping Show-when-closed.
    _restore_operator_identity(alice)
    client.post(
        f"/operator/sessions/{review_session.id}/workflow/close",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert lifecycle.is_expired(review_session)
    db.refresh(instrument)
    assert instrument.responses_visible_when_closed is False

    # Reviewer reloads — values should NOT appear yet.
    app.dependency_overrides[get_current_user] = lambda: rae
    body_before = rae_client.get(
        f"/me/sessions/{review_session.id}/1"
    ).text
    assert 'value="5"' not in body_before

    # Operator flips Show-when-closed AFTER the session is
    # already ``expired``. The route deliberately has no
    # ``_require_instrument_editable`` gate.
    _restore_operator_identity(alice)
    flip_resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{instrument.id}/visibility",
        data={"visible_when_closed": "true"},
        follow_redirects=False,
    )
    assert flip_resp.status_code == 303
    db.refresh(instrument)
    assert instrument.responses_visible_when_closed is True

    # Reviewer reloads again — values must NOW appear.
    app.dependency_overrides[get_current_user] = lambda: rae
    body_after = rae_client.get(
        f"/me/sessions/{review_session.id}/1"
    ).text
    assert 'value="5"' in body_after, (
        "post-close flip of responses_visible_when_closed should "
        "make the reviewer's saved values visible on the next "
        "surface fetch"
    )
    assert "great review" in body_after


def test_dashboard_shows_closed_status_and_keeps_link_after_close(
    client: TestClient,
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """After the operator closes a session, the reviewer dashboard
    must report it as ``closed`` (not ``not opened``) and keep
    the session-name link enabled — otherwise the reviewer
    can't reach their own submissions even when
    ``responses_visible_when_closed=True``. This was the user-
    visible symptom of the original bug report: the toggle was
    fine, but the dashboard hid the route in.
    """
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="dash-closed", reviewer_email=rae.email
    )
    _activate(client, review_session)
    instrument = db.execute(
        select(Instrument).where(
            Instrument.session_id == review_session.id
        )
    ).scalar_one()
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{instrument.id}/visibility",
        data={"visible_when_closed": "true"},
        follow_redirects=False,
    )
    rae_client = make_client(rae)
    _submit_rating(
        rae_client, review_session, rating_value="5",
        comments_value="great review", db=db,
    )
    _restore_operator_identity(alice)
    client.post(
        f"/operator/sessions/{review_session.id}/workflow/close",
        follow_redirects=False,
    )

    # Reviewer-side: ``session_status_for_reviewer`` must distinguish
    # ``expired`` (the post-Close-session state) from ``draft`` /
    # ``validated`` (pre-activation). The dashboard hides the link
    # on ``not opened`` sessions; an ``expired`` session should
    # read as ``closed`` so the link stays enabled.
    reviewer_row = db.execute(
        select(__import__(
            "app.db.models", fromlist=["Reviewer"]
        ).Reviewer).where(
            __import__("app.db.models", fromlist=["Reviewer"])
            .Reviewer.session_id
            == review_session.id
        )
    ).scalar_one()
    status_value = lifecycle.session_status_for_reviewer(
        db, reviewer=reviewer_row, review_session=review_session
    )
    assert status_value == "closed", (
        f"expected 'closed' for an expired session, got {status_value!r}; "
        "dashboard would hide the link and the reviewer couldn't reach "
        "/summary or the per-instrument surface to read submissions"
    )

    # And the dashboard page should render a clickable link for
    # this session. ``link_enabled = session_status != 'not opened'``
    # in _dashboard.py:172 — a "closed" status keeps the link live.
    app.dependency_overrides[get_current_user] = lambda: rae
    body = rae_client.get("/me").text
    # The reviewer's session row carries either /summary (fully
    # submitted) or /1 as the link target. After full submission
    # of one instrument's only assignment, the pill should be
    # ``submitted`` and the link target ``/summary``.
    assert (
        f'href="/me/sessions/{review_session.id}/summary"' in body
        or f'href="/me/sessions/{review_session.id}/1"' in body
    ), "dashboard must keep an active link into the closed session"


def test_close_session_without_show_when_closed_hides_reviewer_values(
    client: TestClient,
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """The flag-False default is the opposite contract: reviewer
    sees disabled inputs with **blank** values on the closed-
    session surface."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="vis-closed-off", reviewer_email=rae.email
    )
    _activate(client, review_session)
    instrument = db.execute(
        select(Instrument).where(
            Instrument.session_id == review_session.id
        )
    ).scalar_one()
    # responses_visible_when_closed defaults to False — don't flip it.
    assert instrument.responses_visible_when_closed is False

    rae_client = make_client(rae)
    _submit_rating(
        rae_client, review_session, rating_value="5",
        comments_value="great review", db=db,
    )

    _restore_operator_identity(alice)
    client.post(
        f"/operator/sessions/{review_session.id}/workflow/close",
        follow_redirects=False,
    )

    app.dependency_overrides[get_current_user] = lambda: rae
    body = rae_client.get(
        f"/me/sessions/{review_session.id}/1"
    ).text
    # Values must NOT appear — show_values=False on the cell builds
    # ``value=""`` and the comments textarea body is empty.
    assert 'value="5"' not in body
    assert "great review" not in body
    # Still the closed-form variant, not pre_open.html.
    assert "Review opens later" not in body
    assert "disabled" in body
