"""Behavioural tests for the Segment 11J PR A Quick Setup card wiring.

PR A flips the Reviewers and Reviewees slots from inert (the 11H
scaffold state) to live. The card's Lock / Unlock, added then, retired
in ``guide/operator_pages_enhancements.md`` Item 1: the card is live on
load while it is available and locked only when it is not.

Slots 3 (Assignments, PR B) and 4 (Settings, Segment 12A) stay inert
and are not exercised here.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import ReviewSession
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)
from ._validated import validate_session


REVIEWER_CSV = b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n"
REVIEWEE_CSV = b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n"
SECOND_REVIEWER_CSV = (
    b"ReviewerName,ReviewerEmail\n"
    b"Beth,beth@example.edu\n"
    b"Carlos,carlos@example.edu\n"
)
BAD_CSV = b"ReviewerName,WrongColumn\nAlice,oops\n"


def _make_session(
    client: TestClient, db: Session, *, code: str = "qs-pra"
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
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    review_session = _make_session(client, db, code=code)
    client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/reviewers",
        files={"file": ("r.csv", REVIEWER_CSV, "text/csv")},
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/reviewees",
        files={"file": ("e.csv", REVIEWEE_CSV, "text/csv")},
        follow_redirects=False,
    )
    return review_session


def _activate(
    client: TestClient, db: Session, review_session: ReviewSession
) -> None:
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)
    validate_session(review_session)
    client.get(f"/operator/sessions/{review_session.id}/assignments")
    client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)


# --------------------------------------------------------------------------- #
# No Lock / Unlock: availability alone locks the card
# --------------------------------------------------------------------------- #


def _tag(body: str, marker: str) -> str:
    at = body.index(marker)
    return body[body.rfind("<", 0, at) : body.index(">", at) + 1]


def test_the_card_is_live_on_load_with_no_lock(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qs-live")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    assert 'class="quick-setup-body"' in body
    assert 'class="quick-setup-body locked"' not in body
    assert "quick-setup-lock-toggle" not in body
    assert "/quick-setup/lock" not in body
    assert "disabled" not in _tag(body, 'name="reviewers_file"')
    assert "disabled" not in _tag(body, 'id="quick-setup-confirm-replace-toggle"')


def test_the_lock_route_is_gone(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, code="qs-no-route")
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/lock",
        data={"action": "unlock"},
        follow_redirects=False,
    )
    assert response.status_code in (404, 405)
    assert "set-cookie" not in response.headers


def test_an_unavailable_card_is_locked_with_nothing_to_unlock(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(client, db, code="qs-unavail")
    _activate(client, db, review_session)
    body = client.get(f"/operator/sessions/{review_session.id}").text

    assert 'class="quick-setup-body locked"' in body
    assert "disabled" in _tag(body, 'name="reviewers_file"')
    assert "disabled" in _tag(body, 'id="quick-setup-confirm-replace-toggle"')
    assert "Unlock" not in body[body.index('class="quick-setup-body locked"') :
                                body.index('id="quick-setup-submit-all"')]
    assert "quick-setup-lock-toggle" not in body


# --------------------------------------------------------------------------- #
# Reviewers / Reviewees golden-path upload
# --------------------------------------------------------------------------- #


def test_reviewers_upload_golden_path_no_banner_on_success(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qs-r-golden")
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/reviewers",
        files={"file": ("r.csv", REVIEWER_CSV, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("#quick-setup-reviewers")

    body = client.get(f"/operator/sessions/{review_session.id}").text
    # Reviewers slot still rendered, no error banner content.
    assert "Reviewers" in body
    # No flash banner — neither error nor confirm renders content.
    assert (
        '<div class="banner banner-error banner-scroll-target"\n'
        '       id="quick-setup-reviewers-error-banner"\n'
        "       hidden"
    ) in body or (
        'id="quick-setup-reviewers-error-banner"' in body
        and "hidden" in body
    )
    # DB confirms the row landed.
    from app.db.models import Reviewer

    assert (
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        )
        .scalars()
        .all()
    )


def test_reviewees_upload_golden_path(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, code="qs-e-golden")
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/reviewees",
        files={"file": ("e.csv", REVIEWEE_CSV, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    body = client.get(f"/operator/sessions/{review_session.id}").text
    assert "Reviewees" in body
    from app.db.models import Reviewee

    assert (
        db.execute(
            select(Reviewee).where(Reviewee.session_id == review_session.id)
        )
        .scalars()
        .all()
    )


# --------------------------------------------------------------------------- #
# Replacement-confirmation — single card-level checkbox
# --------------------------------------------------------------------------- #


def test_card_level_replacement_checkbox_renders_once(
    client: TestClient, db: Session
) -> None:
    """One card-level confirmation checkbox at the top of the body
    wrapper, regardless of how many slots already have data. Inline
    JS mirrors its state into each slot form's hidden
    ``confirm_replace`` input on submit; the route's server-side
    gate stays the source of truth."""

    review_session = _seed_pair(client, db, code="qs-confirm-checkbox")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    # Exactly one card-level toggle.
    assert body.count('id="quick-setup-confirm-replace-toggle"') == 1
    assert (
        "Yes, replace existing reviewers, reviewees"
        in body
    )
    # No per-slot ``banner-warning`` cascade-confirm banners anymore.
    for key in ("reviewers", "reviewees", "settings"):
        assert f"quick-setup-{key}-confirm-banner" not in body
    # No "Confirm replacement" button (that was on the per-slot banner).
    assert "Confirm replacement" not in body
    # The consolidated submit-all form carries a single hidden
    # ``confirm_replace`` input that the inline JS sets from the
    # toggle on submit. (Count the actual ``<input ... name="confirm_replace"``
    # markup; the inline JS also references the name as a CSS
    # selector but that's not a render of the input itself.)
    assert (
        body.count('type="hidden" name="confirm_replace"') == 1
    )


# --------------------------------------------------------------------------- #
# Replacement requires confirm
# --------------------------------------------------------------------------- #


def test_reviewers_replace_without_confirm_redirects_with_error(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(client, db, code="qs-needs-confirm")
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/reviewers",
        files={"file": ("r2.csv", SECOND_REVIEWER_CSV, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "quick_setup_error=reviewers" in location
    assert "quick_setup_reason=needs_confirm" in location
    assert "#quick-setup-reviewers" in location

    body = client.get(location).text
    assert (
        "Tick the replacement-confirmation box just above "
        "Submit, then submit again."
    ) in body
    # Where the banner says it is: after the slot grid, before Submit.
    # It once said "at the top of Quick Setup", which it has not been
    # since the checkbox moved to the footer (post_assessment_1oct E6).
    grid = body.index('class="quick-setup-top-grid"')
    toggle = body.index('id="quick-setup-confirm-replace-toggle"')
    submit = body.index('id="quick-setup-submit-all"')
    assert grid < toggle < submit
    # Cancel button on the error banner points at clean URL with the
    # slot fragment.
    assert (
        f'href="/operator/sessions/{review_session.id}#quick-setup-reviewers"'
        in body
    )


def test_reviewers_replace_with_confirm_applies(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(client, db, code="qs-confirm-applies")
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/reviewers",
        files={"file": ("r2.csv", SECOND_REVIEWER_CSV, "text/csv")},
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    body = client.get(f"/operator/sessions/{review_session.id}").text
    assert "Reviewers" in body
    from app.db.models import Reviewer

    rows = (
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2


# --------------------------------------------------------------------------- #
# Parse / validation error path
# --------------------------------------------------------------------------- #


def test_reviewers_parse_error_routes_to_scoped_error_banner(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qs-parse-error")
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/reviewers",
        files={"file": ("bad.csv", BAD_CSV, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "quick_setup_error=reviewers" in location
    assert "quick_setup_reason=parse" in location

    body = client.get(location).text
    # Error banner scoped to Reviewers slot only.
    assert "Could not import reviewers." in body
    # Reviewees slot's error banner stays hidden.
    assert (
        'id="quick-setup-reviewees-error-banner"\n'
        '       hidden' in body
    ) or (
        'id="quick-setup-reviewees-error-banner"' in body
        and "Could not import reviewees" not in body
    )


# --------------------------------------------------------------------------- #
# Lifecycle rejection on `ready`
# --------------------------------------------------------------------------- #


def test_reviewers_submit_on_ready_routes_to_lifecycle_banner(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """On ``ready`` the operator may visually unlock the card via
    the toggle, but the importer rejects the submit at the service
    layer. The route 303s with a lifecycle error and the banner
    inside the slot names the next move (Pause)."""

    operator = make_client(alice)
    review_session = _seed_pair(operator, db, code="qs-lifecycle")
    _activate(operator, db, review_session)

    response = operator.post(
        f"/operator/sessions/{review_session.id}/quick-setup/reviewers",
        files={"file": ("r2.csv", SECOND_REVIEWER_CSV, "text/csv")},
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "quick_setup_error=reviewers" in location
    assert "quick_setup_reason=lifecycle" in location

    body = operator.get(location).text
    # Both sentences. 19O Item 7 entry 13 renamed the second and left
    # the first saying "paused" — two vocabularies in one banner, which
    # survived because only the second half was ever asserted.
    assert (
        "Setup edits are locked while the session is Activated. "
        "Revert the session to draft before applying setup changes." in body
    )
    assert "paused" not in body


def test_reviewers_submit_on_validated_applies_and_demotes(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Findings B1 (ruled 2026-10-07): the card is live on a validated
    session, so a submit there imports and demotes the session to
    ``draft`` like any roster import, rather than bouncing."""
    from app.db.models import AuditEvent

    operator = make_client(alice)
    review_session = _seed_pair(operator, db, code="qs-validated-submit")
    validate_session(review_session)
    db.flush()
    assert review_session.status == "validated"

    # The card's one Submit.
    response = operator.post(
        f"/operator/sessions/{review_session.id}/quick-setup/submit-all",
        files={
            "reviewers_file": ("r2.csv", SECOND_REVIEWER_CSV, "text/csv")
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "quick_setup_error" not in response.headers["location"]
    db.expire_all()
    assert review_session.status == "draft"
    from app.db.models import Reviewer

    names = sorted(
        db.execute(
            select(Reviewer.name).where(
                Reviewer.session_id == review_session.id
            )
        ).scalars()
    )
    assert names == ["Beth", "Carlos"]
    invalidated = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == review_session.id,
            AuditEvent.event_type == "session.invalidated",
        )
    ).scalars().all()
    assert invalidated


# --------------------------------------------------------------------------- #
# Assignments slot — Segment 11J PR B
# --------------------------------------------------------------------------- #


MANUAL_CSV = (
    b"ReviewerEmail,RevieweeEmail\n"
    b"alice@example.edu,carol@example.edu\n"
)
BAD_MANUAL_CSV = b"WrongHeader,Whatever\nfoo,bar\n"


# ---------------------------------------------------------------------------
# Consolidated submit-all (PR C)
# ---------------------------------------------------------------------------


def test_card_renders_single_bottom_submit_button(
    client: TestClient, db: Session
) -> None:
    """One Submit button at the bottom of the card, associated with
    the outer submit-all form via the HTML ``form="..."`` attribute,
    and starting ``disabled`` because no file is attached on first
    paint."""

    review_session = _make_session(client, db, code="qs-submit-bottom")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    assert 'id="quick-setup-submit-all"' in body
    # Disabled by default — no file selected on first paint.
    submit_start = body.index('id="quick-setup-submit-all"')
    submit_block = body[submit_start - 200 : submit_start + 200]
    assert "disabled" in submit_block
    # Form is the consolidated submit-all endpoint.
    assert (
        'action="/operator/sessions/'
        f'{review_session.id}/quick-setup/submit-all"' in body
    )
    # Per-slot Submit buttons are gone.
    assert "Submit</button>" in body  # the bottom Submit
    submit_count = body.count("Submit</button>")
    assert submit_count == 1, (
        "Only the bottom Submit should remain; per-slot Submits "
        "were retired in PR C."
    )


def test_submit_all_runs_reviewers_slot_when_file_attached(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qs-sa-rev")
    csv = REVIEWER_CSV
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/submit-all",
        files={"reviewers_file": ("reviewers.csv", csv, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    client.get(f"/operator/sessions/{review_session.id}")
    from app.db.models import Reviewer

    rows = (
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        )
        .scalars()
        .all()
    )
    assert rows


def test_submit_all_with_no_input_is_a_clean_redirect(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qs-sa-empty")
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/submit-all",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith(
        f"/operator/sessions/{review_session.id}"
    )


def test_submit_all_runs_reviewers_and_reviewees_in_one_post(
    client: TestClient, db: Session
) -> None:
    """A single submit-all POST with files in two slots runs both —
    no per-slot button required."""

    review_session = _make_session(client, db, code="qs-sa-both")
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/submit-all",
        files={
            "reviewers_file": (
                "reviewers.csv",
                REVIEWER_CSV,
                "text/csv",
            ),
            "reviewees_file": (
                "reviewees.csv",
                REVIEWEE_CSV,
                "text/csv",
            ),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    body = client.get(f"/operator/sessions/{review_session.id}").text
    assert "Reviewers" in body and "Reviewees" in body


# ---------------------------------------------------------------------------
# Leaving Home no longer relocks anything (the navigation middleware went
# with the last unlock cookie, operator pages Item 1)
# ---------------------------------------------------------------------------


def test_leaving_home_and_returning_finds_the_card_still_live(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qs-nav-live")
    home_url = f"/operator/sessions/{review_session.id}"
    for away_url in (
        f"{home_url}/reviewers",
        "/operator/sessions",
        "/operator/settings",
        "/about",
    ):
        assert client.get(away_url).status_code == 200
        assert 'class="quick-setup-body"' in client.get(home_url).text
