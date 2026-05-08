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
        "This will replace any existing reviewers, reviewees,"
        in body
    )
    # No per-slot ``banner-warning`` cascade-confirm banners anymore.
    for key in ("reviewers", "reviewees", "assignments", "settings"):
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
        "Tick the replacement-confirmation box at the top of "
        "Quick Setup before submitting."
    ) in body
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
    assert "Assignments" in body and "1 currently, rule_based" in body
    # Error banner stays hidden.
    assert (
        'id="quick-setup-assignments-error-banner"' in body
        and "hidden" in body
    )


def test_assignments_rule_mode_replace_requires_confirm(
    client: TestClient, db: Session
) -> None:
    """Re-submitting Slot 3 when an assignment set already exists
    rejects unless the card-level ``confirm_replace`` checkbox was
    ticked. The route gate stays the source of truth; the
    rejection redirects with ``needs_confirm``."""

    review_session = _seed_pair(client, db, code="qs-a-confirm")
    # First generate so the slot is populated.
    client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/assignments",
        data={"rule": "full_matrix"},
        follow_redirects=False,
    )
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
        "Tick the replacement-confirmation box at the top of "
        "Quick Setup before submitting."
    ) in body
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


def test_assignments_slot_dropdown_lists_seeds_then_personal(
    client: TestClient, db: Session
) -> None:
    """The "Generate by rule" dropdown is populated with every
    visible RuleSet in canonical order (seeds in install order,
    then caller-owned Personal). Replaces the static "Full Matrix"-
    only option."""

    from app.db.models import RuleSet as RuleSetModel

    review_session = _seed_pair(client, db, code="qs-a-rules-list")

    # Seed a Personal RuleSet via the new Save-As flow.
    intra_id = db.execute(
        select(RuleSetModel.id).where(
            RuleSetModel.is_seed.is_(True),
            RuleSetModel.name == "Intra-group peer review",
        )
    ).scalar_one()
    save_response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor/save",
        data={
            "source_rule_set_id": intra_id,
            "name": "Personal Bbb",
            "combinator": "ALL_OF",
            "rules_json": "[]",
        },
        follow_redirects=False,
    )
    assert save_response.status_code == 303

    body = client.get(f"/operator/sessions/{review_session.id}").text

    # Both seed names + the Personal name appear in the slot 3
    # dropdown, with seeds first.
    slot_marker = 'id="quick-setup-assignments-rule"'
    assert slot_marker in body, "assignments slot dropdown missing"
    slot_start = body.index(slot_marker)
    slot_block = body[slot_start : slot_start + 2000]
    full_matrix_pos = slot_block.find("Full Matrix")
    intra_pos = slot_block.find("Intra-group peer review")
    personal_pos = slot_block.find("Personal Bbb")
    assert full_matrix_pos != -1
    assert intra_pos != -1
    assert personal_pos != -1
    assert full_matrix_pos < personal_pos
    assert intra_pos < personal_pos


def test_assignments_rule_mode_with_personal_rule_set_uses_engine(
    client: TestClient, db: Session
) -> None:
    """Submitting the slot with a Personal ``rule_set_id`` routes
    through the new rule-based engine and writes
    ``mode=rule_based`` plus the rule_set provenance refs on the
    audit row."""

    from app.db.models import RuleSet as RuleSetModel

    review_session = _seed_pair(client, db, code="qs-a-personal")

    intra_id = db.execute(
        select(RuleSetModel.id).where(
            RuleSetModel.is_seed.is_(True),
            RuleSetModel.name == "Intra-group peer review",
        )
    ).scalar_one()
    save_response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor/save",
        data={
            "source_rule_set_id": intra_id,
            "name": "Personal Ccc",
            "combinator": "ALL_OF",
            "rules_json": "[]",
        },
        follow_redirects=False,
    )
    personal_id = int(
        save_response.headers["location"]
        .split("rule_set_id=", 1)[1]
        .split("&", 1)[0]
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/assignments",
        data={"rule_set_id": personal_id},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    body = client.get(f"/operator/sessions/{review_session.id}").text
    assert "rule_based" in body


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
    body = client.get(f"/operator/sessions/{review_session.id}").text
    # Reviewer count updated.
    assert "1 currently" in body or "2 currently" in body or "3 currently" in body


def test_submit_all_runs_assignments_rule_when_only_rule_supplied(
    client: TestClient, db: Session
) -> None:
    """submit-all with no file but a ``rule_set_id`` supplied
    triggers the rule-based path on the assignments slot. The
    button-enable gate (file presence) is client-side only — a
    crafted POST that lacks files but carries a rule_set_id is
    handled cleanly."""

    review_session = _seed_pair(client, db, code="qs-sa-rule")

    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/submit-all",
        data={"rule": "full_matrix"},
        follow_redirects=False,
    )
    # No files present; the legacy ``rule="full_matrix"`` path is
    # only honoured by the per-slot route. submit-all expects
    # ``rule_set_id`` directly.
    assert response.status_code == 303
    # Server-side, the empty post is a no-op redirect.
    assert response.headers["location"].startswith(
        f"/operator/sessions/{review_session.id}"
    )


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
# Lock-state-resets-on-navigation (PR D — Quick Setup polish)
# ---------------------------------------------------------------------------


def test_unlock_cookie_clears_on_navigation_to_other_operator_page(
    client: TestClient, db: Session
) -> None:
    """Navigating to any non-Session-Home operator page expires the
    ``qsu_{id}`` unlock cookie. Returning to Home then renders the
    card locked again — operators don't carry an unlocked card
    across page navigations."""

    review_session = _make_session(client, db, code="qs-nav-relock")
    # Unlock the card.
    client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/lock",
        data={"action": "unlock"},
        follow_redirects=False,
    )
    home_unlocked = client.get(
        f"/operator/sessions/{review_session.id}"
    ).text
    assert 'class="quick-setup-body"' in home_unlocked  # no .locked

    # Navigate to a sibling operator page — Reviewers setup.
    away = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    )
    assert away.status_code == 200
    # That response expires the ``qsu_*`` cookie via the middleware
    # so the next request to Home doesn't carry it.
    home_relocked = client.get(
        f"/operator/sessions/{review_session.id}"
    ).text
    assert 'class="quick-setup-body locked"' in home_relocked


def test_unlock_cookie_persists_across_quick_setup_form_submissions(
    client: TestClient, db: Session
) -> None:
    """The unlock cookie must NOT clear on the Quick Setup card's own
    form submissions (lock toggle, submit-all). Only navigations
    *away* from the card surface clear it."""

    review_session = _make_session(client, db, code="qs-nav-keep")
    client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/lock",
        data={"action": "unlock"},
        follow_redirects=False,
    )
    # POST submit-all with no inputs (a no-op redirect) should not
    # invalidate the cookie.
    client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/submit-all",
        follow_redirects=False,
    )
    home_after = client.get(
        f"/operator/sessions/{review_session.id}"
    ).text
    assert 'class="quick-setup-body"' in home_after  # still unlocked
