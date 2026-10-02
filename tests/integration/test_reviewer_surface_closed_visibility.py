"""What a reviewer can read back once their session closes.

The instrument's ``peer_reviewer`` visibility policy decides (author's
ruling, 2026-10-01, on ``guide/findings_2026-10-01_corpus.md`` G10;
``visibility_policies.reviewer_sees_own_responses``):

- ``expired`` and the release window open: the reviewer's own values
  show when the policy's "Responses released" cell is Raw, and not when
  it is Summarized or off;
- ``expired`` outside the window: nothing;
- archived: nothing, on the summary page or its CSV either.

``responses_visible_when_closed`` no longer decides anything; it
round-trips for config only, and setting it changes nothing here.
"""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    Instrument,
    ReviewSession,
    User,
)
from app.main import app
from app.services import session_lifecycle as lifecycle
from app.services import visibility_policies
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
    extra_instruments: int = 0,
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
    for _ in range(extra_instruments):
        operator_client.post(
            f"/operator/sessions/{review_session.id}/instruments/add-new-model"
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


def _close_after_rae_submits(
    client: TestClient,
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client,
    *,
    code: str,
    released_mode: str | None,
    open_release: bool,
    retired_flag: bool = True,
    second_instrument_mode: str | None = "unused",
) -> tuple[ReviewSession, TestClient]:
    """Rae submits 5 / "great review"; the operator authors the
    peer_reviewer "Responses released" cell, closes the session, and
    optionally opens the release window. Returns Rae's client, with her
    identity installed."""
    two = second_instrument_mode != "unused"
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code=code, reviewer_email=rae.email,
        extra_instruments=1 if two else 0,
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit_rating(
        rae_client, review_session, rating_value="5",
        comments_value="great review", db=db,
    )
    _restore_operator_identity(alice)
    instruments = sorted(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars(),
        key=lambda i: (i.order, i.id),
    )
    operator = db.execute(
        select(User).where(User.email == alice.email)
    ).scalar_one()
    modes = [released_mode] + ([second_instrument_mode] if two else [])
    for instrument, mode in zip(instruments, modes):
        visibility_policies.upsert_policy(
            db,
            review_session=review_session,
            instrument=instrument,
            audience="peer_reviewer",
            while_ongoing_mode="raw",
            after_release_mode=mode,
            user=operator,
        )
        # The retired toggle: it must no longer decide anything.
        instrument.responses_visible_when_closed = retired_flag
    db.commit()
    close_resp = client.post(
        f"/operator/sessions/{review_session.id}/workflow/close",
        follow_redirects=False,
    )
    assert close_resp.status_code == 303
    db.refresh(review_session)
    assert lifecycle.is_expired(review_session)
    if open_release:
        review_session.responses_release_at = dt.datetime.now(
            dt.timezone.utc
        ) - dt.timedelta(hours=1)
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: rae
    return review_session, rae_client


def test_released_raw_shows_the_reviewers_own_values(
    client: TestClient, db: Session, alice, rae, make_client
) -> None:
    """The policy alone shows them: the retired toggle is off here."""
    review_session, rae_client = _close_after_rae_submits(
        client, db, alice, rae, make_client,
        code="vis-raw", released_mode="raw", open_release=True,
        retired_flag=False,
    )
    body = rae_client.get(f"/me/sessions/{review_session.id}/1").text
    assert 'value="5"' in body
    assert "great review" in body
    assert "remain visible below" in body
    # Still the closed, read-only form, not pre_open.html.
    assert "Review opens later" not in body
    assert "disabled" in body
    summary = rae_client.get(f"/me/sessions/{review_session.id}/summary")
    assert "great review" in summary.text
    csv_body = rae_client.get(
        f"/me/sessions/{review_session.id}/summary.csv"
    ).text
    assert "great review" in csv_body


@pytest.mark.parametrize(
    ("released_mode", "open_release"),
    [("raw", False), (None, True)],
    ids=["window-not-open", "released-off"],
)
def test_otherwise_a_closed_session_hides_them(
    client: TestClient,
    db: Session,
    alice,
    rae,
    make_client,
    released_mode: str | None,
    open_release: bool,
) -> None:
    """Outside the release window, or with the released cell off, the
    reviewer's values are hidden — even with the retired toggle set."""
    review_session, rae_client = _close_after_rae_submits(
        client, db, alice, rae, make_client,
        code=f"vis-hide-{released_mode}-{open_release}",
        released_mode=released_mode,
        open_release=open_release,
    )
    body = rae_client.get(f"/me/sessions/{review_session.id}/1").text
    assert 'value="5"' not in body
    assert "great review" not in body
    assert "hidden by the operator" in body
    assert "disabled" in body
    summary = rae_client.get(f"/me/sessions/{review_session.id}/summary").text
    assert "great review" not in summary
    assert "Your responses are not shown" in summary
    assert "summary.csv" not in summary
    csv_body = rae_client.get(
        f"/me/sessions/{review_session.id}/summary.csv"
    ).text
    assert "great review" not in csv_body


def test_visibility_is_decided_per_instrument(
    client: TestClient, db: Session, alice, rae, make_client
) -> None:
    """Instrument 1 released Raw, instrument 2 off: the surface says some
    values are hidden, the summary shows one section and says so, and the
    CSV carries instrument 1 only."""
    review_session, rae_client = _close_after_rae_submits(
        client, db, alice, rae, make_client,
        code="vis-mixed", released_mode="raw", open_release=True,
        second_instrument_mode=None,
    )
    body = rae_client.get(f"/me/sessions/{review_session.id}/1").text
    assert "Some of your previously saved values are hidden" in body
    assert "great review" in body
    summary = rae_client.get(f"/me/sessions/{review_session.id}/summary").text
    assert "Some of your responses are not shown" in summary
    assert summary.count('<section class="card"') == 1
    assert "summary.csv" in summary
    csv_body = rae_client.get(
        f"/me/sessions/{review_session.id}/summary.csv"
    ).text
    assert "instrument_1" in csv_body
    assert "instrument_2" not in csv_body


def test_archiving_ends_all_visibility(
    client: TestClient, db: Session, alice, rae, make_client
) -> None:
    """Archived: nothing, whatever the policy says — not on the summary,
    not in its CSV (the surface already shows the not-open page)."""
    review_session, rae_client = _close_after_rae_submits(
        client, db, alice, rae, make_client,
        code="vis-archived", released_mode="raw", open_release=True,
    )
    review_session.status = "archived"
    db.commit()
    summary = rae_client.get(f"/me/sessions/{review_session.id}/summary").text
    assert "great review" not in summary
    csv_body = rae_client.get(
        f"/me/sessions/{review_session.id}/summary.csv"
    ).text
    assert "great review" not in csv_body


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
    can't reach their own submissions even where the visibility
    policy shows them.
    """
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="dash-closed", reviewer_email=rae.email
    )
    _activate(client, review_session)
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
