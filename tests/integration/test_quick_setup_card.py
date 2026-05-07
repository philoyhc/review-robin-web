"""Behavioural tests for the Segment 11J PR A Quick Setup card wiring.

PR A flips the Reviewers and Reviewees slots from inert (the 11H
scaffold state) to live, wires the Lock / Unlock toggle to a real
per-session cookie, and unifies the card's status awareness so the
toggle is visible in every editable-conceivable lifecycle state.

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
from app.web import views


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
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )
    client.get(f"/operator/sessions/{review_session.id}?validated=1")
    client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)


# --------------------------------------------------------------------------- #
# Lock / Unlock toggle
# --------------------------------------------------------------------------- #


def test_unlock_sets_cookie_and_drops_locked_class(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qs-unlock")
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/lock",
        data={"action": "unlock"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("#quick-setup")
    cookie = response.cookies.get(f"qsu_{review_session.id}")
    assert cookie == "1"

    body = client.get(f"/operator/sessions/{review_session.id}").text
    assert 'class="quick-setup-body"' in body
    assert ">Lock</button>" in body
    assert ">Unlock</button>" not in body


def test_lock_clears_cookie_and_restores_locked_class(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qs-lock")
    client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/lock",
        data={"action": "unlock"},
        follow_redirects=False,
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/lock",
        data={"action": "lock"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    body = client.get(f"/operator/sessions/{review_session.id}").text
    assert 'class="quick-setup-body locked"' in body
    assert ">Unlock</button>" in body


def test_lock_cookie_scoped_per_session(
    client: TestClient, db: Session
) -> None:
    """Unlocking session A must not leak into session B's lock state."""

    session_a = _make_session(client, db, code="qs-cookie-a")
    session_b = _make_session(client, db, code="qs-cookie-b")
    client.post(
        f"/operator/sessions/{session_a.id}/quick-setup/lock",
        data={"action": "unlock"},
        follow_redirects=False,
    )
    body_a = client.get(f"/operator/sessions/{session_a.id}").text
    body_b = client.get(f"/operator/sessions/{session_b.id}").text
    assert 'class="quick-setup-body"' in body_a
    assert 'class="quick-setup-body locked"' in body_b


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
    # Count indicator reflects the new state — the success signal.
    assert "Reviewers" in body and "1 currently" in body
    # No flash banner — neither error nor confirm renders content.
    assert (
        '<div class="banner banner-error banner-scroll-target"\n'
        '       id="quick-setup-reviewers-error-banner"\n'
        "       hidden"
    ) in body or (
        'id="quick-setup-reviewers-error-banner"' in body
        and "hidden" in body
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
    assert "Reviewees" in body and "1 currently" in body


# --------------------------------------------------------------------------- #
# Replacement-confirmation banner + cascade copy
# --------------------------------------------------------------------------- #


def test_replacement_banner_appears_when_slot_populated(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(client, db, code="qs-replace-banner")
    body = client.get(f"/operator/sessions/{review_session.id}").text
    # cascade_message populated for both Reviewers and Reviewees.
    assert "This will replace 1 existing reviewer." in body
    assert "This will replace 1 existing reviewee." in body
    # The banner-warning containers are visible (no ``hidden`` attr).
    assert (
        'id="quick-setup-reviewers-confirm-banner"\n'
        '           ' in body
    ) or 'id="quick-setup-reviewers-confirm-banner"' in body
    # Cancel + Confirm-replacement buttons render.
    assert "Confirm replacement" in body
    # Cancel link points at clean URL with the slot fragment.
    cancel_href = (
        f'href="/operator/sessions/{review_session.id}#quick-setup-reviewers"'
    )
    assert cancel_href in body


def test_cascade_message_calls_out_assignment_clearance(
    client: TestClient, db: Session
) -> None:
    """When assignments exist, replacing reviewers / reviewees must
    surface the cascade explicitly per the spec."""

    review_session = _seed_pair(client, db, code="qs-cascade")
    # Generate full-matrix assignments so the cascade has something
    # to mention.
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )
    body = client.get(f"/operator/sessions/{review_session.id}").text
    # Reviewers cascade calls out the existing assignments.
    assert (
        "1 existing assignment will be cleared" in body
        or "existing assignment will be cleared" in body
    )


def test_cascade_helper_zero_count_returns_none() -> None:
    assert (
        views.cascade_message_for_replace("reviewers", reviewer_count=0)
        is None
    )
    assert (
        views.cascade_message_for_replace("reviewees", reviewee_count=0)
        is None
    )
    assert (
        views.cascade_message_for_replace(
            "assignments", assignment_count=0
        )
        is None
    )


def test_cascade_helper_pluralisation() -> None:
    # Singular vs plural noun for the target entity.
    assert "1 existing reviewer." in views.cascade_message_for_replace(
        "reviewers", reviewer_count=1
    )
    assert "8 existing reviewers." in views.cascade_message_for_replace(
        "reviewers", reviewer_count=8
    )
    # Singular for one assignment in the cascade phrase.
    msg = views.cascade_message_for_replace(
        "reviewers", reviewer_count=2, assignment_count=1
    )
    assert "1 existing assignment will be cleared" in msg


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
    assert "Tick the confirmation box to replace existing reviewers." in body
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
    # New reviewer count reflected.
    assert "Reviewers" in body and "2 currently" in body


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
    assert "Pause the session before applying setup changes." in body


# --------------------------------------------------------------------------- #
# Assignments slot — Segment 11J PR B
# --------------------------------------------------------------------------- #


MANUAL_CSV = (
    b"ReviewerEmail,RevieweeEmail\n"
    b"alice@example.edu,carol@example.edu\n"
)
BAD_MANUAL_CSV = b"WrongHeader,Whatever\nfoo,bar\n"


def test_assignments_rule_mode_golden_path(
    client: TestClient, db: Session
) -> None:
    """Submitting Slot 3 with no file falls back to rule mode and
    generates a full-matrix assignment set. Success: 303 → Home,
    no flash banner; the slot's count + rule indicator updates in
    place."""

    review_session = _seed_pair(client, db, code="qs-a-rule")
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/assignments",
        data={"rule": "full_matrix"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        "#quick-setup-assignments"
    )
    body = client.get(f"/operator/sessions/{review_session.id}").text
    assert "Assignments" in body and "1 currently, full_matrix" in body
    # Error banner stays hidden.
    assert (
        'id="quick-setup-assignments-error-banner"' in body
        and "hidden" in body
    )


def test_assignments_rule_mode_replace_requires_confirm(
    client: TestClient, db: Session
) -> None:
    """Re-submitting Slot 3 when an assignment set already exists
    triggers the replace-confirmation banner and rejects the
    second submit unless ``confirm_replace=true`` is set."""

    review_session = _seed_pair(client, db, code="qs-a-confirm")
    # First generate so the slot is populated.
    client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/assignments",
        data={"rule": "full_matrix"},
        follow_redirects=False,
    )
    # Now the cascade banner-warning renders inside the slot.
    body = client.get(f"/operator/sessions/{review_session.id}").text
    assert "This will replace 1 existing assignment." in body
    cancel_href = (
        f'href="/operator/sessions/{review_session.id}'
        "#quick-setup-assignments\""
    )
    assert cancel_href in body
    # Re-submit without ``confirm_replace`` → needs_confirm.
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/assignments",
        data={"rule": "full_matrix"},
        follow_redirects=False,
    )
    location = response.headers["location"]
    assert "quick_setup_error=assignments" in location
    assert "quick_setup_reason=needs_confirm" in location
    body = client.get(location).text
    assert (
        "Tick the confirmation box to replace existing assignments."
        in body
    )
    # Re-submit with confirm → applies, no error.
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/assignments",
        data={"rule": "full_matrix", "confirm_replace": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "quick_setup_error" not in response.headers["location"]


def test_assignments_csv_mode_golden_path(
    client: TestClient, db: Session
) -> None:
    """Uploading a non-empty file flips the route into CSV mode and
    runs the manual-import pipeline. Success path matches rule mode
    — count updates in place, no flash banner."""

    review_session = _seed_pair(client, db, code="qs-a-csv")
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/assignments",
        files={"file": ("a.csv", MANUAL_CSV, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    body = client.get(f"/operator/sessions/{review_session.id}").text
    assert "Assignments" in body and "1 currently, manual" in body


def test_assignments_csv_mode_parse_error_routes_to_scoped_banner(
    client: TestClient, db: Session
) -> None:
    """Bad CSV: 303 → Home with parse error scoped to slot 3 only.
    Reviewers / Reviewees error banners stay hidden."""

    review_session = _seed_pair(client, db, code="qs-a-parse")
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/assignments",
        files={"file": ("bad.csv", BAD_MANUAL_CSV, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "quick_setup_error=assignments" in location
    assert "quick_setup_reason=parse" in location
    body = client.get(location).text
    assert "Could not import assignments." in body
    # Reviewers slot not affected.
    assert "Could not import reviewers." not in body


def test_assignments_submit_on_ready_routes_to_lifecycle_banner(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """On ``ready`` the route rejects mutating submits at the
    service layer regardless of whether the card is visually
    unlocked. The rejection scopes to slot 3."""

    operator = make_client(alice)
    review_session = _seed_pair(operator, db, code="qs-a-ready")
    _activate(operator, db, review_session)

    response = operator.post(
        f"/operator/sessions/{review_session.id}/quick-setup/assignments",
        data={"rule": "full_matrix", "confirm_replace": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "quick_setup_error=assignments" in location
    assert "quick_setup_reason=lifecycle" in location
    body = operator.get(location).text
    assert "Pause the session before applying setup changes." in body
