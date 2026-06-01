from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.services import monitoring as monitoring_service
from app.services import responses as responses_service
from app.services import visibility_policies
from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


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
    review_session.relationships_enabled = True
    db.commit()
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
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator_client, review_session.id)
    if activate:
        _activate(operator_client, db, review_session)
    return review_session


def _activate(
    operator_client: TestClient, db: Session, review_session: ReviewSession
) -> None:
    operator_client.get(f"/operator/sessions/{review_session.id}/assignments?validated=1")
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
    response = rae_client.get("/me")

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
    response = rae_client.get("/me")

    assert response.status_code == 200
    assert "Rae-Inactive" not in response.text


def test_surface_renders_pair_context_and_default_fields(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """15D PR 6b: pair_context now lives on the relationships table.
    Upload the Relationships CSV separately to populate the per-pair
    tag the reviewer surface renders. Assignment-level context
    retired entirely."""

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
        f"/operator/sessions/{review_session.id}/relationships/import",
        files={
            "file": (
                "rel.csv",
                (
                    b"ReviewerEmail,RevieweeEmail,PairContextTag1\n"
                    b"rae@example.edu,carol@example.edu,morning\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    _activate(operator, db, review_session)

    rae_client = make_client(rae)
    response = rae_client.get(f"/me/sessions/{review_session.id}")

    assert response.status_code == 200
    assert "Carol" in response.text
    assert "Pair context 1" in response.text
    assert "morning" in response.text
    assert "P1:" not in response.text  # 10B-1 moved pair context out of identity cell
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
    body = make_client(rae).get(f"/me/sessions/{review_session.id}").text
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
    body = rae_client.get(f"/me/sessions/{review_session.id}").text

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
    body = rae_client.get(f"/me/sessions/{review_session.id}").text

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
    body = rae_client.get(f"/me/sessions/{review_session.id}").text

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
    body = rae_client.get(f"/me/sessions/{review_session.id}").text

    # Default seeded fields: 1-to-5int Rating (numeric → rs-narrow) +
    # Long_text Comments (textarea → rs-textlong).
    assert '>Rating' in body
    assert '>Comments' in body
    # Per-cell <td> classes match (the 13B PR 3 sort scaffolding
    # appends a ``data-sort-value`` attribute on each td, so the
    # class no longer sits right before the closing ``>``).
    assert '<td class="rs-narrow"' in body
    assert '<td class="rs-textlong"' in body


def test_surface_sizes_textarea_rows_from_max_chars_and_column_width(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Regression for the 2026-05-28 textarea-sizing policy
    (``views/_instruments.py::textarea_rows_for``). The
    long-text Comments field (max_length=2000) renders with the
    derivation's cap of ``rows="8"`` at the default column width,
    NOT the prior static ``rows="2"``. Widening the column via
    ``Instrument.column_widths["rf_<id>"]`` shrinks the row
    count — proving the formula is consuming the operator-set
    width."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-tarows",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    body_default = rae_client.get(
        f"/me/sessions/{review_session.id}"
    ).text

    # Default seeded Comments is max_length=2000 → at default
    # 224px column → typical 1000 chars / 28 chars/row → 36 →
    # clamped to the 8-row cap.
    assert 'rows="8"' in body_default
    # Sanity check: the legacy hard-coded ``rows="2"`` is gone.
    assert 'rows="2"' not in body_default

    # The 2000-char field's typical-response still caps at every
    # realistic width. Switch to a smaller field that WILL shrink:
    # shorten max_length to 300 and re-render.
    from app.db.models import Instrument

    instrument = db.execute(
        select(Instrument).where(
            Instrument.session_id == review_session.id
        )
    ).scalars().first()
    assert instrument is not None
    comments = next(
        rf for rf in instrument.response_fields if rf.label == "Comments"
    )
    # Shrink max_length so the formula has headroom to vary with
    # column width.
    validation = dict(comments.validation or {})
    validation["max_length"] = 300
    comments.validation = validation
    db.flush()
    body_narrow = rae_client.get(
        f"/me/sessions/{review_session.id}"
    ).text
    # 300 max → typical 150 / 28 chars/row (default 224px) =
    # ceil(5.36) = 6.
    assert 'rows="6"' in body_narrow

    # Now widen the column for the Comments field to 800px and
    # re-render — chars/row jumps to 100, typical 150 / 100 =
    # ceil(1.5) = 2 → floor 2 (the MIN_TEXTAREA_ROWS clamp).
    widths = dict(instrument.column_widths or {})
    widths[f"rf_{comments.id}"] = 800
    instrument.column_widths = widths
    db.flush()
    body_wide = rae_client.get(
        f"/me/sessions/{review_session.id}"
    ).text
    assert 'rows="2"' in body_wide


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
    body = rae_client.get(f"/me/sessions/{review_session.id}").text

    # Reviewee column header is present (always rendered). The
    # PR 3 sort scaffolding wraps the label between the tag's
    # opening ``>`` and a trailing ``<span class="rs-sort-badge">``;
    # match by ``data-sort-key="reviewee.name"`` instead so the
    # assertion stays stable across cosmetic markup changes.
    assert 'data-sort-key="reviewee.name"' in body
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
    response = rae_client.get(f"/me/sessions/{review_session.id}")

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
    # _operator_creates_session_with_pair already generated assignments
    # via the rule engine; flip the one (rae, carol) row to include=False
    # directly. The retired manual-CSV path used to do this via an
    # explicit "IncludeAssignment=false" row in the upload; rule-based
    # has no equivalent CSV column today, so the DB-level flip is the
    # most precise replacement for the test's intent.
    rae_carol_assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalar_one()
    rae_carol_assignment.include = False
    db.commit()
    _activate(operator, db, review_session)

    rae_client = make_client(rae)
    response = rae_client.get(f"/me/sessions/{review_session.id}")

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
        f"/me/sessions/{review_session.id}/1/save",
        data={
            f"response[{assignment.id}][rating]": "4",
            f"response[{assignment.id}][comments]": "good work",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/me/sessions/{review_session.id}/1"
    )

    page = rae_client.get(f"/me/sessions/{review_session.id}")
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
    body = rae_client.get(f"/me/sessions/{review_session.id}/1").text
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
    body = rae_client.get(f"/me/sessions/{review_session.id}/1").text
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
    body = rae_client.get(f"/me/sessions/{review_session.id}/1").text
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
    body = rae_client.get(f"/me/sessions/{review_session.id}/1").text
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
        f"/me/sessions/{review_session.id}/1/save",
        data={f"response[{assignment.id}][rating]": "77"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    body = response.text
    assert "data-rs-errors-card" in body
    assert "Must be at most 5" in body
    assert 'value="77"' in body
    # No persisted row.
    page = rae_client.get(f"/me/sessions/{review_session.id}/1").text
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
        f"/me/sessions/{review_session.id}/1/save",
        data={
            f"response[{assignment.id}][rating]": "9",
            f"response[{assignment.id}][comments]": "looks good",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    page = rae_client.get(f"/me/sessions/{review_session.id}/1").text
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
        f"/me/sessions/{review_session.id}/submit",
        data={
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
        f"/me/sessions/{review_session.id}/submit",
        data={f"response[{assignment.id}][rating]": "5"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    # 17B Phase 2 PR B — submit closes out the single-assignment
    # session so the redirect lands on the summary page.
    assert response.headers["location"].endswith(
        f"/me/sessions/{review_session.id}/summary"
    )
    audit = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.submitted")
    ).scalar_one()
    assert audit.detail["counts"]["submitted"] >= 1


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
        f"/me/sessions/{review_session.id}/submit",
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
        f"/me/sessions/{review_session.id}/submit",
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
        f"/me/sessions/{review_session.id}/1/save",
        data={f"response[{assignment.id}][rating]": "5"},
        follow_redirects=False,
    )

    response = rae_client.post(
        f"/me/sessions/{review_session.id}/clear",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    audit = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.cleared")
    ).scalar_one()
    assert audit.detail["counts"]["deleted"] >= 1


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
        f"/me/sessions/{review_session.id}/clear",
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
        f"/me/sessions/{review_session.id}/submit",
        data={f"response[{assignment.id}][rating]": "3"},
        follow_redirects=False,
    )
    first_events = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.submitted")
    ).scalars().all()
    assert len(first_events) == 1

    rae_client.post(
        f"/me/sessions/{review_session.id}/submit",
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
        f"/me/sessions/{review_session.id}/1/save",
        data={
            f"response[{assignment.id}][rating]": "4",
            f"response[{assignment.id}][comments]": "saved comment",
        },
        follow_redirects=False,
    )

    page = rae_client.get(f"/me/sessions/{review_session.id}")
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
    own = rae_client.get(f"/me/sessions/{rae_session.id}")
    other = rae_client.get(f"/me/sessions/{other_session.id}")
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
    response = rae_client.get(f"/me/sessions/{review_session.id}")
    assert response.status_code == 403


def test_save_drops_foreign_assignment_id_from_post(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A reviewer save POST must not trust a client-supplied
    assignment_id: an id belonging to another session's reviewer is
    silently dropped, never written. Guards the §5.6 "POST endpoints
    do not trust client-side identifiers" contract.
    """
    op_alice = make_client(alice)
    rae_session = _operator_creates_session_with_pair(
        op_alice,
        db,
        code="rae-tamper",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )
    op_bob = make_client(bob)
    foreign_session = _operator_creates_session_with_pair(
        op_bob,
        db,
        code="bob-tamper",
        reviewer_email="someone@example.edu",
        reviewee_ident="dan@example.edu",
    )
    foreign_assignment = db.execute(
        select(Assignment).where(
            Assignment.session_id == foreign_session.id
        )
    ).scalar_one()

    rae_client = make_client(rae)
    response = rae_client.post(
        f"/me/sessions/{rae_session.id}/1/save",
        data={
            f"response[{foreign_assignment.id}][rating]": "4",
            f"response[{foreign_assignment.id}][comments]": "tampered",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    written = db.execute(
        select(Response).where(
            Response.assignment_id == foreign_assignment.id
        )
    ).scalars().all()
    assert written == []


def test_reviewer_surface_response_inputs_carry_aria_labels(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Segment 14A PR 5 — every response control in the reviewer
    table names its column and row, so a screen-reader user hears
    "{field} for {reviewee}" rather than an unlabelled box."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-a11y",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    page = rae_client.get(f"/me/sessions/{review_session.id}")

    assert page.status_code == 200
    assert 'aria-label="' in page.text
    assert " for Carol" in page.text


def test_reviewer_surface_table_headers_have_scope(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Segment 14A PR 5 — column headers are marked scope="col" so
    assistive tech associates each header with its column."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-scope",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    page = rae_client.get(f"/me/sessions/{review_session.id}")

    assert page.status_code == 200
    assert '<th scope="col"' in page.text


def test_base_layout_has_skip_link_and_main_landmark(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Segment 14A PR 5 — base.html exposes a skip-to-content link
    and a <main> landmark on every page."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-skip",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
    )

    rae_client = make_client(rae)
    page = rae_client.get(f"/me/sessions/{review_session.id}")

    assert page.status_code == 200
    assert '<a class="skip-link" href="#main-content">' in page.text
    assert '<main id="main-content" tabindex="-1">' in page.text


def test_group_instrument_save_fans_out_to_all_members(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Saving a group-scoped instrument's response fans the single
    answer out to every member assignment (Segment 13C PR 2 write
    fan-out)."""
    operator = make_client(alice)
    operator.post(
        "/operator/sessions",
        data={"name": "Grp Fan", "code": "grp-fan"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "grp-fan")
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/instruments/add-group",
        follow_redirects=False,
    )
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
                b"RevieweeName,RevieweeEmail\n"
                b"Carol,carol@example.edu\nDan,dan@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    _activate(operator, db, review_session)

    group = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.group_kind.is_not(None))
    ).scalar_one()
    group_assignments = list(
        db.execute(
            select(Assignment)
            .where(Assignment.session_id == review_session.id)
            .where(Assignment.instrument_id == group.id)
        ).scalars()
    )
    assert len(group_assignments) == 2  # one reviewer x two reviewees

    rae_client = make_client(rae)
    first = group_assignments[0]
    # Segment 18L: single-page-default session keeps every instrument
    # on page 1, so /1/save accepts inputs for any instrument.
    response = rae_client.post(
        f"/me/sessions/{review_session.id}/1/save",
        data={
            f"response[{first.id}][rating]": "4",
            f"response[{first.id}][comments]": "team did well",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    # The single answer landed on every member assignment.
    for assignment in group_assignments:
        rows = db.execute(
            select(Response).where(Response.assignment_id == assignment.id)
        ).scalars().all()
        by_key = {r.response_field.field_key: r.value for r in rows}
        assert by_key.get("rating") == "4"
        assert by_key.get("comments") == "team did well"


def test_group_instrument_fan_out_stays_within_boundary_group(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A group-scoped instrument with a boundary tag fans a reviewer's
    answer only to the members of the *same* boundary-defined group —
    a different group on the same instrument is untouched (Segment 13C
    PR 2 slice B)."""
    operator = make_client(alice)
    operator.post(
        "/operator/sessions",
        data={"name": "Grp Boundary", "code": "grp-bnd"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "grp-bnd")
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/instruments/add-group",
        follow_redirects=False,
    )
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
                b"RevieweeName,RevieweeEmail,RevieweeTag1\n"
                b"Carol,carol@example.edu,Team A\n"
                b"Eve,eve@example.edu,Team A\n"
                b"Dan,dan@example.edu,Team B\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    # Set the group boundary directly: group by RevieweeTag1, so
    # Team A (Carol, Eve) and Team B (Dan) are two distinct groups.
    group = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.group_kind.is_not(None))
    ).scalar_one()
    group.group_kind = "r1"
    db.commit()

    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    _activate(operator, db, review_session)

    by_reviewee = {
        a.reviewee.name: a
        for a in db.execute(
            select(Assignment)
            .where(Assignment.session_id == review_session.id)
            .where(Assignment.instrument_id == group.id)
            .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        ).scalars()
    }
    assert set(by_reviewee) == {"Carol", "Eve", "Dan"}

    rae_client = make_client(rae)
    # Segment 18L: single-page-default session — every instrument
    # lives on page 1.
    # Answer the Team A group (keyed to Carol's assignment).
    response = rae_client.post(
        f"/me/sessions/{review_session.id}/1/save",
        data={f"response[{by_reviewee['Carol'].id}][rating]": "5"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    def _rating(assignment: Assignment) -> str | None:
        rows = db.execute(
            select(Response).where(Response.assignment_id == assignment.id)
        ).scalars().all()
        return {r.response_field.field_key: r.value for r in rows}.get("rating")

    # Team A members both got the answer; Team B (Dan) is untouched.
    assert _rating(by_reviewee["Carol"]) == "5"
    assert _rating(by_reviewee["Eve"]) == "5"
    assert _rating(by_reviewee["Dan"]) is None

    # Answering the Team B group leaves Team A's answer intact.
    response = rae_client.post(
        f"/me/sessions/{review_session.id}/1/save",
        data={f"response[{by_reviewee['Dan'].id}][rating]": "2"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert _rating(by_reviewee["Dan"]) == "2"
    assert _rating(by_reviewee["Carol"]) == "5"
    assert _rating(by_reviewee["Eve"]) == "5"


def test_group_boundary_tag_change_defuncts_that_reviewees_responses(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Editing a reviewee's group-boundary tag deletes the
    group-scoped Response rows that point at them — the now
    mis-attributed fan-out copies — while the other group members'
    rows survive (Segment 13C PR 5)."""
    from app.db.models import User
    from app.services import reviewees as reviewees_service

    operator = make_client(alice)
    operator.post(
        "/operator/sessions",
        data={"name": "Grp Tag Edit", "code": "grp-tagedit"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "grp-tagedit")
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/instruments/add-group",
        follow_redirects=False,
    )
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
                b"RevieweeName,RevieweeEmail,RevieweeTag1\n"
                b"Carol,carol@example.edu,Team A\n"
                b"Eve,eve@example.edu,Team A\n"
                b"Dan,dan@example.edu,Team B\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    group = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.group_kind.is_not(None))
    ).scalar_one()
    group.group_kind = "r1"  # group by RevieweeTag1
    db.commit()

    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    _activate(operator, db, review_session)

    by_reviewee = {
        a.reviewee.name: a
        for a in db.execute(
            select(Assignment)
            .where(Assignment.session_id == review_session.id)
            .where(Assignment.instrument_id == group.id)
            .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        ).scalars()
    }
    # Segment 18L: single-page-default session — every instrument
    # lives on page 1.
    # Reviewer answers the Team A group → fans to Carol + Eve.
    rae_client = make_client(rae)
    saved = rae_client.post(
        f"/me/sessions/{review_session.id}/1/save",
        data={f"response[{by_reviewee['Carol'].id}][rating]": "5"},
        follow_redirects=False,
    )
    assert saved.status_code == 303, saved.text

    def _rating(assignment: Assignment) -> str | None:
        rows = (
            db.execute(
                select(Response).where(
                    Response.assignment_id == assignment.id
                )
            )
            .scalars()
            .all()
        )
        return {r.response_field.field_key: r.value for r in rows}.get(
            "rating"
        )

    assert _rating(by_reviewee["Carol"]) == "5"
    assert _rating(by_reviewee["Eve"]) == "5"

    # Operator corrects Carol's boundary tag — she moves to Team B.
    carol = db.execute(
        select(Reviewee).where(
            Reviewee.session_id == review_session.id,
            Reviewee.email_or_identifier == "carol@example.edu",
        )
    ).scalar_one()
    operator_user = db.get(User, review_session.created_by_user_id)
    reviewees_service.update_reviewee(
        db, reviewee=carol, tag_1="Team B", user=operator_user
    )

    # Carol's group-scoped Response rows are defuncted; Eve — a
    # retained Team A member — keeps the reviewer's answer.
    assert _rating(by_reviewee["Carol"]) is None
    assert _rating(by_reviewee["Eve"]) == "5"


def test_tag_change_into_answered_group_refans_the_answer(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A reviewee moved by a boundary-tag change into an
    already-answered group is re-fanned that group's answer — so
    the group keeps surfacing it even when the relocated reviewee
    (with no fanned copy) would otherwise be the collapse
    representative (Segment 18H)."""
    from app.db.models import User
    from app.services import reviewees as reviewees_service

    operator = make_client(alice)
    operator.post(
        "/operator/sessions",
        data={"name": "Grp Join", "code": "grp-join"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "grp-join")
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/instruments/add-group",
        follow_redirects=False,
    )
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
                b"RevieweeName,RevieweeEmail,RevieweeTag1\n"
                b"Carol,carol@example.edu,Team A\n"
                b"Eve,eve@example.edu,Team A\n"
                b"Dan,dan@example.edu,Team B\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    group = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.group_kind.is_not(None))
    ).scalar_one()
    group.group_kind = "r1"
    db.commit()
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    _activate(operator, db, review_session)

    by_reviewee = {
        a.reviewee.name: a
        for a in db.execute(
            select(Assignment)
            .where(Assignment.session_id == review_session.id)
            .where(Assignment.instrument_id == group.id)
            .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        ).scalars()
    }
    # Carol (Team A) has the lower assignment id, so after she joins
    # Team B she becomes its collapse representative.
    assert by_reviewee["Carol"].id < by_reviewee["Dan"].id
    # Segment 18L: single-page-default session — every instrument
    # lives on page 1.
    rae_client = make_client(rae)
    # Reviewer answers Team A (via Carol) and Team B (via Dan).
    saved = rae_client.post(
        f"/me/sessions/{review_session.id}/1/save",
        data={
            f"response[{by_reviewee['Carol'].id}][rating]": "5",
            f"response[{by_reviewee['Dan'].id}][rating]": "3",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303, saved.text

    # Operator moves Carol into the already-answered Team B.
    carol = db.execute(
        select(Reviewee).where(
            Reviewee.session_id == review_session.id,
            Reviewee.email_or_identifier == "carol@example.edu",
        )
    ).scalar_one()
    operator_user = db.get(User, review_session.created_by_user_id)
    reviewees_service.update_reviewee(
        db, reviewee=carol, tag_1="Team B", user=operator_user
    )

    # Carol's assignment is re-fanned with Team B's answer ("3"),
    # not left blank by the defunct.
    carol_rows = (
        db.execute(
            select(Response).where(
                Response.assignment_id == by_reviewee["Carol"].id
            )
        )
        .scalars()
        .all()
    )
    assert {
        r.response_field.field_key: r.value for r in carol_rows
    }.get("rating") == "3"

    # The surface still surfaces Team B's answer.
    page = rae_client.get(
        f"/me/sessions/{review_session.id}/1"
    )
    marker = f"rrw-sort-rs-{review_session.id}-{group.id}"
    table = page.text[
        page.text.index(marker) : page.text.index(
            "</table>", page.text.index(marker)
        )
    ]
    assert 'value="3"' in table


def test_relationship_pair_context_tag_change_defuncts_pair_responses(
    db: Session,
) -> None:
    """Editing a relationship's grouping pair-context tag deletes
    the group-scoped Response rows for exactly that (reviewer,
    reviewee) pair (Segment 13C PR 5 — pair-context variant)."""
    import datetime as _dt

    from app.db.models import (
        InstrumentResponseField,
        Relationship,
        User,
    )
    from app.services import relationships as relationships_service

    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Rel Defunct",
        code="rel-defunct",
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    # Group-scoped instrument grouped by pair-context tag 1.
    instrument = Instrument(
        session_id=review_session.id,
        name="Grp",
        order=0,
        group_kind="p1",
    )
    db.add(instrument)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="rating",
        label="Rating",
        _inline_data_type="Integer",
        _inline_response_type="Likert5",
        order=0,
    )
    db.add(field)
    reviewer = Reviewer(
        session_id=review_session.id, name="R", email="r@example.edu"
    )
    carol = Reviewee(
        session_id=review_session.id,
        name="Carol",
        email_or_identifier="carol@example.edu",
    )
    db.add_all([reviewer, carol])
    db.flush()
    relationship = Relationship(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=carol.id,
        tag_1="Cohort A",
        status="active",
    )
    db.add(relationship)
    assignment = Assignment(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=carol.id,
        instrument_id=instrument.id,
        include=True,
        created_by_mode="manual",
    )
    db.add(assignment)
    db.flush()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=field.id,
            value="4",
            saved_at=_dt.datetime(2026, 5, 9, tzinfo=_dt.timezone.utc),
            version=1,
        )
    )
    db.commit()

    def _response_count() -> int:
        return len(
            db.execute(
                select(Response).where(
                    Response.assignment_id == assignment.id
                )
            )
            .scalars()
            .all()
        )

    assert _response_count() == 1

    # Editing the relationship's grouping pair-context tag defuncts
    # the pair's group-scoped responses.
    relationships_service.update_relationship(
        db, relationship=relationship, tag_1="Cohort B", user=user
    )
    assert _response_count() == 0


def test_relationship_repoint_defuncts_both_old_and_new_pair(
    db: Session,
) -> None:
    """Re-pointing a relationship to a different pair — even with no
    tag value change — mis-attributes the group-scoped Response
    rows of *both* the old and the new pair: the relationship's
    pair-context tags move off the old pair and onto the new one.
    Both pairs are defuncted; an unrelated pair on the same group
    instrument is untouched (Segment 18H — re-point handling)."""
    import datetime as _dt

    from app.db.models import (
        InstrumentResponseField,
        Relationship,
        User,
    )
    from app.services import relationships as relationships_service

    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Rel Repoint",
        code="rel-repoint",
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    # Group-scoped instrument grouped by pair-context tag 1.
    instrument = Instrument(
        session_id=review_session.id,
        name="Grp",
        order=0,
        group_kind="p1",
    )
    db.add(instrument)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="rating",
        label="Rating",
        _inline_data_type="Integer",
        _inline_response_type="Likert5",
        order=0,
    )
    db.add(field)
    reviewer = Reviewer(
        session_id=review_session.id, name="R", email="r@example.edu"
    )
    reviewer2 = Reviewer(
        session_id=review_session.id, name="R2", email="r2@example.edu"
    )
    carol = Reviewee(
        session_id=review_session.id,
        name="Carol",
        email_or_identifier="carol@example.edu",
    )
    dave = Reviewee(
        session_id=review_session.id,
        name="Dave",
        email_or_identifier="dave@example.edu",
    )
    eve = Reviewee(
        session_id=review_session.id,
        name="Eve",
        email_or_identifier="eve@example.edu",
    )
    db.add_all([reviewer, reviewer2, carol, dave, eve])
    db.flush()
    # The relationship under edit describes (R, Carol).
    relationship = Relationship(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=carol.id,
        tag_1="Cohort A",
        status="active",
    )
    db.add(relationship)

    def _assignment(reviewer_id: int, reviewee_id: int) -> Assignment:
        a = Assignment(
            session_id=review_session.id,
            reviewer_id=reviewer_id,
            reviewee_id=reviewee_id,
            instrument_id=instrument.id,
            include=True,
            created_by_mode="manual",
        )
        db.add(a)
        db.flush()
        db.add(
            Response(
                assignment_id=a.id,
                response_field_id=field.id,
                value="4",
                saved_at=_dt.datetime(
                    2026, 5, 9, tzinfo=_dt.timezone.utc
                ),
                version=1,
            )
        )
        return a

    a_old = _assignment(reviewer.id, carol.id)  # the old pair
    a_new = _assignment(reviewer.id, dave.id)  # the re-point target
    a_other = _assignment(reviewer2.id, eve.id)  # unrelated control
    db.commit()

    def _has_response(assignment: Assignment) -> bool:
        return (
            db.execute(
                select(Response).where(
                    Response.assignment_id == assignment.id
                )
            ).first()
            is not None
        )

    assert _has_response(a_old)
    assert _has_response(a_new)
    assert _has_response(a_other)

    # Re-point the relationship from (R, Carol) to (R, Dave) — a
    # pure re-point, no tag value change.
    relationships_service.update_relationship(
        db, relationship=relationship, reviewee_id=dave.id, user=user
    )

    # Both the old pair and the new pair are defuncted.
    assert not _has_response(a_old)
    assert not _has_response(a_new)
    # The unrelated pair on the same group instrument survives.
    assert _has_response(a_other)


def test_group_self_review_toggle_rules_out_whole_group(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """On a group-scoped instrument the self-review toggle works on
    groups: deactivating self-reviews rules out every assignment in
    a group the reviewer is a member of — not just the (R, R) pair
    — while a group the reviewer is not in is untouched (13C)."""
    from app.db.models import User
    from app.services import assignments as assignments_service

    operator = make_client(alice)
    operator.post(
        "/operator/sessions",
        data={"name": "Grp SR", "code": "grp-sr"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "grp-sr")
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/instruments/add-group",
        follow_redirects=False,
    )
    # One reviewer, R, who is also a reviewee — so R is a member of
    # the Team X group. Team Y has no R.
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nR,r@example.edu\n",
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
                b"RevieweeName,RevieweeEmail,RevieweeTag1\n"
                b"R,r@example.edu,Team X\n"
                b"A,a@example.edu,Team X\n"
                b"C,c@example.edu,Team Y\n"
                b"D,d@example.edu,Team Y\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    group = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.group_kind.is_not(None))
    ).scalar_one()
    group.group_kind = "r1"  # group by RevieweeTag1
    db.commit()

    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)

    def _include_by_reviewee() -> dict[str, bool]:
        return {
            a.reviewee.name: a.include
            for a in db.execute(
                select(Assignment)
                .where(Assignment.instrument_id == group.id)
                .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
            ).scalars()
        }

    operator_user = db.get(User, review_session.created_by_user_id)

    # Deactivate self-reviews: R's Team X group (R, A) is ruled out
    # wholesale; the Team Y group (C, D) — which R is not in — stays.
    assignments_service.set_instrument_self_reviews_active(
        db,
        review_session=review_session,
        instrument_id=group.id,
        user=operator_user,
        active=False,
        correlation_id="test-sr-off",
    )
    db.expire_all()
    includes = _include_by_reviewee()
    assert includes == {"R": False, "A": False, "C": True, "D": True}

    # The breakdown counts the whole self-review group (R, A).
    breakdown = assignments_service.self_review_breakdown_per_instrument(
        db, review_session.id
    )
    assert breakdown[group.id] == (0, 2)

    # Re-activating brings the whole group back.
    assignments_service.set_instrument_self_reviews_active(
        db,
        review_session=review_session,
        instrument_id=group.id,
        user=operator_user,
        active=True,
        correlation_id="test-sr-on",
    )
    db.expire_all()
    assert _include_by_reviewee() == {
        "R": True,
        "A": True,
        "C": True,
        "D": True,
    }


def test_group_instrument_surface_renders_one_row_per_group(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The reviewer surface collapses a group-scoped instrument's
    per-reviewee rows into one row per boundary-defined group, with a
    composed group-identity cell (Segment 13C PR 2 slice C)."""
    operator = make_client(alice)
    operator.post(
        "/operator/sessions",
        data={"name": "Grp Render", "code": "grp-rnd"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "grp-rnd")
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/instruments/add-group",
        follow_redirects=False,
    )
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
                b"RevieweeName,RevieweeEmail,RevieweeTag1\n"
                b"Carol,carol@example.edu,Team A\n"
                b"Eve,eve@example.edu,Team A\n"
                b"Dan,dan@example.edu,Team B\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    group = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.group_kind.is_not(None))
    ).scalar_one()
    group.group_kind = "r1"
    db.commit()

    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    _activate(operator, db, review_session)

    # Segment 18L: single-page-default session — every instrument
    # lives on page 1.
    rae_client = make_client(rae)
    page = rae_client.get(
        f"/me/sessions/{review_session.id}/1"
    )
    assert page.status_code == 200

    # Isolate the group instrument's table from the rendered surface.
    marker = f"rrw-sort-rs-{review_session.id}-{group.id}"
    start = page.text.index(marker)
    table = page.text[start : page.text.index("</table>", start)]

    # The table is group-scoped: a "Group" header, not "Reviewee".
    assert ">Group</th>" in table
    # One row per boundary group (Team A, Team B) — not one per
    # reviewee — so two rating inputs, not three.
    assert table.count("[rating]") == 2
    assert "Team A" in table and "Team B" in table
    # Team A's member-name list renders (RevieweeName Included).
    assert "Carol" in table and "Eve" in table
    # The numeric Rating column is pinned to a ch-width keyed to its
    # header + RTD digit span, so it doesn't sprawl across the
    # fixed-layout group table.
    assert 'style="width: 12ch"' in table


def test_group_instrument_counts_once_per_group_in_reviewer_state(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A group-scoped instrument counts once per boundary group in a
    reviewer's session state — not once per member assignment
    (Segment 13C PR 2 slice D aggregation)."""
    operator = make_client(alice)
    operator.post(
        "/operator/sessions",
        data={"name": "Grp State", "code": "grp-st"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "grp-st")
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/instruments/add-group",
        follow_redirects=False,
    )
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
                b"RevieweeName,RevieweeEmail,RevieweeTag1\n"
                b"Carol,carol@example.edu,Team A\n"
                b"Eve,eve@example.edu,Team A\n"
                b"Dan,dan@example.edu,Team B\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    group = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.group_kind.is_not(None))
    ).scalar_one()
    group.group_kind = "r1"  # group by RevieweeTag1 → Team A, Team B
    db.commit()

    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    _activate(operator, db, review_session)

    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalar_one()
    raw_assignment_count = db.execute(
        select(Assignment).where(
            Assignment.session_id == review_session.id,
            Assignment.reviewer_id == reviewer.id,
        )
    ).scalars().all()
    # 3 reviewees x 2 instruments (default per-reviewee + group) = 6
    # raw assignments.
    assert len(raw_assignment_count) == 6

    state = responses_service.reviewer_session_state(
        db, reviewer=reviewer, session_id=review_session.id
    )
    # The per-reviewee instrument contributes 3; the group instrument
    # collapses its 3 member assignments to 2 boundary groups → 5.
    assert state.total_assignments == 5

    # per_reviewer_progress threads a session-wide group-key map into
    # each reviewer's rollup (computed once, not once per reviewer);
    # the collapsed count must match the direct call above.
    progress = monitoring_service.per_reviewer_progress(db, review_session)
    assert [p.assignment_count for p in progress] == [5]


def test_surface_hides_response_field_when_visible_false(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Wave 3 PR ii — once the operator deselects a response-field
    pill in Band 2, the underlying ``InstrumentResponseField.visible``
    flips to False and the reviewer surface stops rendering the
    column header + cell."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-hide",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        activate=False,
    )
    _activate(operator, db, review_session)

    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    comments_field = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()
    comments_field.visible = False
    db.commit()

    rae_client = make_client(rae)
    response = rae_client.get(f"/me/sessions/{review_session.id}")

    assert response.status_code == 200
    # Rating (visible) still renders; Comments (hidden) does not.
    assert "Rating" in response.text
    assert "Comments" not in response.text


def test_surface_visibility_policy_card_reflects_persisted_policy(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The reviewer surface renders a read-only "Who can see what
    you wrote (other than admin)" card next to each instrument's
    heading card, reflecting the operator's persisted Band 3
    policy. Observers are intentionally omitted — they're the
    admin-side audience and the suffix "(other than admin)" makes
    that explicit."""
    operator = make_client(alice)
    review_session = _operator_creates_session_with_pair(
        operator,
        db,
        code="rae-vp-card",
        reviewer_email="rae@example.edu",
        reviewee_ident="carol@example.edu",
        activate=False,
    )
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    operator_user = db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()
    # Reviewees: Summarized after release; Observer policy
    # authored too — should NOT appear on the reviewer surface
    # (admin-side audience). peer_reviewer takes the baseline
    # (Raw ongoing, off after release).
    visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="reviewee",
        while_ongoing_mode=None,
        after_release_mode="summarized",
        user=operator_user,
    )
    visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="observer",
        while_ongoing_mode="raw",
        after_release_mode="raw",
        user=operator_user,
    )
    db.commit()
    _activate(operator, db, review_session)

    rae_client = make_client(rae)
    body = rae_client.get(f"/me/sessions/{review_session.id}").text

    assert "data-rs-visibility-policy-card" in body
    assert "Who can see what you wrote (other than admin)" in body
    # Column headings.
    assert "Session ongoing" in body
    assert "Responses released" in body
    # Two audience labels in the table — Observers omitted.
    flat = " ".join(body.split())
    assert "<td style=\"padding: 4px 8px;\">You</td>" in flat
    assert "<td style=\"padding: 4px 8px;\">Reviewees</td>" in flat
    assert "<td style=\"padding: 4px 8px;\">Observers</td>" not in flat
    # The reviewee after-release cell shows the Summarized mode,
    # which the reviewer-facing vocabulary names "Anonymized
    # summaries" (operators see "summarized" as the encoded mode;
    # the reviewer-surface wording is gentler).
    assert "Anonymized summaries" in body
