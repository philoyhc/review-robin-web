from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, AuditEvent, Instrument, Reviewer, ReviewSession


def _operator_creates_session_with_pair(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str,
    reviewee_ident: str,
    activate: bool = True,
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
    if activate:
        _activate(operator_client, db, review_session)
    return review_session


def _activate(
    operator_client: TestClient, db: Session, review_session: ReviewSession
) -> None:
    operator_client.get(f"/operator/sessions/{review_session.id}?validated=1")
    response = operator_client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(review_session)
    assert review_session.status == "ready"


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


def test_dashboard_lists_only_sessions_where_user_is_active_reviewer(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    matched = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-session",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    _operator_creates_session_with_pair(
        operator,
        db,
        code="other-session",
        reviewer_email="someone@example.edu",
        reviewee_ident="dan@example.edu",
    )

    rae_client = make_client(rae)
    response = rae_client.get("/reviewer")

    assert response.status_code == 200
    assert "Rae-Session" in response.text or matched.name in response.text
    assert "Other-Session" not in response.text


def test_dashboard_skips_inactive_reviewer_rows(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-inactive",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalar_one()
    reviewer.status = "inactive"
    db.commit()

    rae_client = make_client(rae)
    response = rae_client.get("/reviewer")

    assert response.status_code == 200
    assert "Rae-Inactive" not in response.text


def test_surface_renders_pair_context_and_default_fields(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-ctx",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        activate=False,
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={
            "file": (
                "m.csv",
                (
                    b"ReviewerEmail,RevieweeEmail,PairContext1,AssignmentContext1\n"
                    b"rae@example.edu,carol@example.edu,morning,panel-1\n"
                ),
                "text/csv",
            )
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    _activate(operator, db, review_session)

    rae_client = make_client(rae)
    response = rae_client.get(f"/reviewer/sessions/{review_session.id}")

    assert response.status_code == 200
    assert "Carol" in response.text
    assert "Pair context 1" in response.text
    assert "morning" in response.text
    assert "P1:" not in response.text  # 10B-1 moved pair context out of identity cell
    assert "panel-1" not in response.text  # assignment_context hidden
    assert "Rating" in response.text
    assert "Comments" in response.text


def test_surface_help_text_renders_as_inline_list(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Help text renders as ``<ul><li><strong>Label</strong> — text</li>``."""
    from app.db.models import InstrumentResponseField

    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-helpfmt",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        activate=False,
    )
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.field_key == "rating"
        )
    ).scalar_one()
    rating.help_text = "1 (poor) to 5 (excellent)."
    rating.help_text_visible = True
    db.commit()
    _activate(operator, db, review_session)

    rae_client = make_client(rae)
    body = make_client(rae).get(f"/reviewer/sessions/{review_session.id}").text
    del rae_client

    # Single help item still renders as a half-width card inside the
    # per-instrument intro grid (the lone-help case used to expand to
    # full width via `rs-help-card-solo`; now it always stays half-
    # width and lands in column 2 next to the heading card).
    assert 'class="card rs-help-card"' in body
    assert "rs-help-card-solo" not in body
    assert "<strong>Rating</strong> — 1 (poor) to 5 (excellent)." in body
    assert "<dl class=\"help-block\">" not in body
    assert '<ul class="help-block">' not in body


def test_surface_help_text_multi_items_render_in_grid(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Two+ help items render as half-width cards inside the per-
    instrument intro grid; no solo-card branch."""
    from app.db.models import InstrumentResponseField

    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-helpgrid",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        activate=False,
    )
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    fields = list(
        db.execute(
            select(InstrumentResponseField)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .order_by(InstrumentResponseField.id)
        ).scalars()
    )
    fields[0].help_text = "Rating help."
    fields[0].help_text_visible = True
    fields[1].help_text = "Comments help."
    fields[1].help_text_visible = True
    db.commit()
    _activate(operator, db, review_session)

    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text

    # Help cards live in their own `.rs-help-grid` row below the
    # heading card's `.rs-intro-grid`; they no longer share a row
    # with the heading.
    assert '<div class="rs-help-grid">' in body
    assert body.count('class="card rs-help-card"') == 2
    assert "Rating help." in body
    assert "Comments help." in body
    # The retired `rs-help-card-solo` modifier no longer renders.
    assert "rs-help-card-solo" not in body


def test_surface_does_not_wrap_groups_in_outer_card(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """No outer .rs-card wrapper around each instrument group.

    Tried briefly during the visual_style_general.md alignment work and dropped:
    the outer card was visually redundant with the help-text grid + table
    inside it. Help text cards (rs-help-card) and the response table stand
    on their own.
    """
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-no-outer-card",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text

    assert '<div class="rs-card">' not in body
    assert ".rs-card {" not in body  # CSS rule also removed


def test_surface_status_column_hidden_pre_submission(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The trailing ✓/⚠ status column is suppressed when no row needs it.

    Pre-submission with show_acknowledge=False, every row has
    submitted_at=None — the column would render empty and just leave a
    thin empty bar at the right of the table. Hide it entirely.
    """
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-status-hidden",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text

    # The trailing status column has no marker text; the easiest pin is the
    # presence of its container styles. Pre-submission, neither the empty
    # <th class="rs-narrow"> trailer nor the centered status <td> should
    # appear.
    assert 'style="width: 1%; white-space: nowrap; text-align: center;"' not in body


def test_surface_applies_column_classes_by_response_type(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Numeric response columns get rs-narrow; long-text columns get rs-textlong."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-cols",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text

    # Default seeded fields: 1-to-5int Rating (numeric → rs-narrow) +
    # Long_text Comments (textarea → rs-textlong).
    assert 'class="rs-narrow">Rating' in body
    assert 'class="rs-textlong">Comments' in body
    # Per-cell <td> classes match.
    assert '<td class="rs-narrow">' in body
    assert '<td class="rs-textlong">' in body


def test_surface_dedupes_reviewee_name_and_email_display_fields(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Display fields for (reviewee, name|email_or_identifier) are not rendered
    as separate columns — the always-rendered Reviewee identity column shows
    them already."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-dedup",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}").text

    # Reviewee column header is present (always rendered).
    assert 'class="rs-reviewee">Reviewee</th>' in body
    # The seeded name + email Display Fields no longer render as <th>.
    assert ">Name</th>" not in body
    assert ">Email</th>" not in body


def test_surface_single_instrument_no_description_renders_no_heading(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Single instrument + empty description → no `<h2>` heading at all.

    Regression: Instrument.name (e.g. "instrument_4" after deletions) used
    to leak through as the heading. The contract is now: single-instrument
    sessions show no per-instrument heading when description is empty.
    """
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-noheading",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        activate=False,
    )
    only_instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    only_instrument.name = "instrument_4"
    only_instrument.description = None
    db.commit()
    _activate(operator, db, review_session)

    rae_client = make_client(rae)
    response = rae_client.get(f"/reviewer/sessions/{review_session.id}")

    assert response.status_code == 200
    assert "instrument_4" not in response.text
    assert "Instrument #1" not in response.text


def test_surface_filters_out_excluded_assignments(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-excl",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        activate=False,
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={
            "file": (
                "m.csv",
                (
                    b"ReviewerEmail,RevieweeEmail,IncludeAssignment\n"
                    b"rae@example.edu,carol@example.edu,false\n"
                ),
                "text/csv",
            )
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    _activate(operator, db, review_session)

    rae_client = make_client(rae)
    response = rae_client.get(f"/reviewer/sessions/{review_session.id}")

    assert response.status_code == 200
    assert "Carol" not in response.text
    assert "No assignments are visible" in response.text


def test_save_draft_persists_and_reload_shows_values(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-save",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()

    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/1/save",
        data={
            f"response[{assignment.id}][rating]": "4",
            f"response[{assignment.id}][comments]": "good work",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/reviewer/sessions/{review_session.id}/1"
    )

    page = rae_client.get(f"/reviewer/sessions/{review_session.id}")
    assert 'value="4"' in page.text
    assert "good work" in page.text


def test_surface_renders_constraint_hints_for_integer_and_string_fields(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The default instrument carries a 1-to-5int rating + a Long_text
    comments field. Numeric inputs surface their constraint via the
    hover ``title`` attribute (kept off ``placeholder`` so the input
    column stays compact); String inputs use ``placeholder`` since
    their column is wide enough."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-placeholder",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    assert 'title="1 to 5, steps of 1"' in body
    assert 'placeholder="0 to 2000 char"' in body


def test_surface_renders_help_contact_line_when_set(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """When the operator sets a per-session help contact, the
    reviewer surface page header surfaces "Questions? Contact <X>"
    as a small ``muted`` line. Hidden when the column is NULL."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-help-contact",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        activate=False,
    )
    # Operator sets the help contact via /edit (only allowed while
    # the session is editable — i.e. before activation).
    response = operator.post(
        f"/operator/sessions/{review_session.id}/edit",
        data={
            "name": review_session.name,
            "code": review_session.code,
            "description": review_session.description or "",
            "help_contact": "Prof X <x@example.edu>",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    # Activate so the reviewer surface is reachable.
    _activate(operator, db, review_session)
    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    assert "Questions? Contact Prof X" in body


def test_surface_renders_constraint_summary_row_above_table(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The default instrument carries a 1-to-5int rating + a Long_text
    comments field. A right-aligned summary line lists each field's
    label (bold) and constraint summary, in column order, above the
    table."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-constraints",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    assert "rs-constraints" in body
    assert "<strong>Rating</strong> (1-5, steps of 1)" in body
    assert "<strong>Comments</strong> (0-2000 char)" in body
    # Row sits above the table-scroll wrapper.
    summary_idx = body.find('class="rs-constraints')
    table_idx = body.find('class="table-scroll"')
    assert 0 < summary_idx < table_idx


def test_numeric_input_carries_step_data_attrs_for_js_validity(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The 1-to-5int rating input carries ``data-rs-step="1"`` and
    ``data-rs-step-anchor="1"`` so the inline ``setCustomValidity`` JS
    can detect off-grid values and pop up the same browser warning
    chrome the range check uses. The HTML5 ``step="any"`` stays in
    place to suppress the native (float-drift-prone) step check."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-step-attrs",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    body = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    assert 'data-rs-step="1"' in body
    assert 'data-rs-step-anchor="1"' in body
    assert 'step="any"' in body
    # JS hook: the recompute helper is wired up.
    assert "recomputeStepValidity" in body
    assert "setCustomValidity" in body


def test_save_rejects_out_of_range_integer_and_keeps_typed_value(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A 1-to-5int rating is bound to ``min=1 max=5 step=1`` via the
    seeded RTD. Saving ``77`` is rejected server-side: the row stays
    unwritten, the surface re-renders with the Invalid-values card,
    and the form input still carries the typed ``77`` so the reviewer
    can correct it in place."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-bad-range",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/1/save",
        data={f"response[{assignment.id}][rating]": "77"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    body = response.text
    assert "data-rs-errors-card" in body
    assert "Must be at most 5" in body
    assert 'value="77"' in body
    # No persisted row.
    page = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    assert 'value="77"' not in page


def test_save_persists_valid_and_rejects_invalid_in_same_batch(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Mixed batch — the valid String input ('comments') saves through;
    the invalid Integer input ('rating') is held back."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-mixed",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/1/save",
        data={
            f"response[{assignment.id}][rating]": "9",
            f"response[{assignment.id}][comments]": "looks good",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    page = rae_client.get(f"/reviewer/sessions/{review_session.id}/1").text
    # Valid one persisted; invalid one did not.
    assert "looks good" in page
    assert 'value="9"' not in page


def test_submit_blocks_on_validation_error(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Submit blocks on out-of-range values just like Save does, and
    the error card takes precedence over the missing-required card so
    invalid values don't masquerade as 'present'."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-submit-bad",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={
            "current_position": "1",
            f"response[{assignment.id}][rating]": "0",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    body = response.text
    assert "data-rs-errors-card" in body
    assert "Must be at least 1" in body
    # Missing-required card does not coexist with the validation card.
    assert "data-rs-missing-card" not in body


def test_submit_with_all_required_filled_succeeds_and_writes_audit(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-submit",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()

    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={f"response[{assignment.id}][rating]": "5"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/reviewer/sessions/{review_session.id}/1"
    )
    audit = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.submitted")
    ).scalar_one()
    assert audit.detail["count"] >= 1


def test_submit_with_missing_required_warns_without_audit(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-warn",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Required fields missing" in response.text
    # Submit is a hard gate — the missing-card lists the gaps but
    # there's no acknowledge-and-submit-anyway escape hatch.
    assert 'name="acknowledge_missing"' not in response.text
    # Per-row amber icon shows on the warn re-render (so reviewer can find
    # which rows are incomplete without scrolling back to the top card).
    assert "⚠" in response.text
    submitted = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.submitted")
    ).first()
    assert submitted is None


def test_submit_with_missing_required_stays_blocked_even_with_legacy_acknowledge(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Sanity check the gate isn't reachable via a stale form payload —
    a POST with the retired ``acknowledge_missing=true`` field still
    blocks when required fields are missing. Drafts written via the
    payload still commit."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-ack-blocked",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={"acknowledge_missing": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Required fields missing" in response.text
    submitted = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.submitted")
    ).first()
    assert submitted is None


def test_clear_all_with_confirm_deletes_responses(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-clear",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/1/save",
        data={f"response[{assignment.id}][rating]": "5"},
        follow_redirects=False,
    )

    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/clear",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    audit = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.cleared")
    ).scalar_one()
    assert audit.detail["deleted_count"] >= 1


def test_clear_all_without_confirm_400s(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-noclear",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    response = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/clear",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_resubmit_after_edit_refreshes_submitted_at(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-resub",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={f"response[{assignment.id}][rating]": "3"},
        follow_redirects=False,
    )
    first_events = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.submitted")
    ).scalars().all()
    assert len(first_events) == 1

    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        data={f"response[{assignment.id}][rating]": "5"},
        follow_redirects=False,
    )
    later_events = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.submitted")
    ).scalars().all()
    assert len(later_events) == 2


def test_cancel_link_renders_last_saved_values(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-cancel",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/1/save",
        data={
            f"response[{assignment.id}][rating]": "4",
            f"response[{assignment.id}][comments]": "saved comment",
        },
        follow_redirects=False,
    )

    page = rae_client.get(f"/reviewer/sessions/{review_session.id}")
    assert "saved comment" in page.text
    assert 'value="4"' in page.text


def test_other_session_url_returns_403(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    op_alice = make_client(alice)
    rae_session = _operator_creates_session_with_pair(
        op_alice,
        db,
        code="rae-only",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    op_bob = make_client(bob)
    other_session = _operator_creates_session_with_pair(
        op_bob,
        db,
        code="bob-only",
        reviewer_email="someone@example.edu",
        reviewee_ident="dan@example.edu",
    )

    rae_client = make_client(rae)
    own = rae_client.get(f"/reviewer/sessions/{rae_session.id}")
    other = rae_client.get(f"/reviewer/sessions/{other_session.id}")
    assert own.status_code == 200
    assert other.status_code == 403


def test_inactive_reviewer_row_403s_on_surface(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-403",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalar_one()
    reviewer.status = "inactive"
    db.commit()

    rae_client = make_client(rae)
    response = rae_client.get(f"/reviewer/sessions/{review_session.id}")
    assert response.status_code == 403
