"""Integration coverage for Segment 15D PR 6a — Operations
Assignments page surface.

PR 6a moves the Assignments tab from the Setup row to the
Operations row, drops the operator-facing manual upload card,
adds the bulk Include toggle for self-reviews, and drops the
ad-hoc ``exclude_self_review`` checkbox from the Rule Based card.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "OpsAsgn", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_population_with_self_review(
    client: TestClient, session_id: int
) -> None:
    """Alice appears as both reviewer and reviewee — that pair is
    the self-review."""

    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                (
                    b"ReviewerName,ReviewerEmail\n"
                    b"Alice,alice@example.edu\n"
                    b"Bob,bob@example.edu\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                (
                    b"RevieweeName,RevieweeEmail\n"
                    b"Alice,alice@example.edu\n"
                    b"Carol,carol@example.edu\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )


# Wave 5 PR 5.2 — ``_full_matrix_seed_id`` retired with the
# ``RuleSet`` operator-library model. Unused locally; was a
# legacy helper from the pre-15B test surface.


def _generate_with_self_reviews(
    client: TestClient, db: Session, session_id: int
) -> None:
    """Generate via the seeded Full Matrix RuleSet, overriding
    exclude_self_review=false so self-review pairs reach the
    assignments table."""

    pin_full_matrix_on_all_instruments(db, session_id)
    response = generate_via_page_button(client, session_id)
    assert response.status_code == 303, response.text


# ---------------------------------------------------------------------------
# Chrome restructure
# ---------------------------------------------------------------------------


def test_chrome_assignments_tab_now_on_operations_row(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ops-chrome")
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text

    # The Setup tab strip no longer carries Assignments.
    setup_strip = body.split('class="tab-strip tab-strip-setup', 1)[1].split(
        "</div>", 1
    )[0]
    assert ">Assignments</a>" not in setup_strip

    # The Operations tab strip now does.
    ops_strip = body.split('class="tab-strip tab-strip-ops"', 1)[1].split(
        "</div>", 1
    )[0]
    assert ">Assignments</a>" in ops_strip

    # Order on Ops row (Slice 3b swap): Assignments · Validate ·
    # Previews · Invitations · Responses. Assignments leads because
    # it's now where the operator confirms materialised pairs are
    # sensible *before* running Validate; pre-Slice-3a it was where
    # the operator did the Generate work.
    indices = {
        label: ops_strip.find(f">{label}</a>")
        for label in (
            "Assignments",
            "Validate",
            "Previews",
            "Invitations",
            "Responses",
        )
    }
    assert all(idx > 0 for idx in indices.values())
    assert (
        indices["Assignments"]
        < indices["Validate"]
        < indices["Previews"]
        < indices["Invitations"]
        < indices["Responses"]
    )


def test_assignments_page_marks_active_tab_on_operations_row(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ops-active")
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    target = (
        f'href="/operator/sessions/{review_session.id}/assignments"'
    )
    cut = body.find(target)
    assert cut > 0
    preceding = body[max(0, cut - 200):cut]
    assert "nav-tab active" in preceding


def test_setup_card_no_longer_includes_assignments_row(
    client: TestClient, db: Session
) -> None:
    """``build_setup_rows`` drops the Assignments row; the canonical
    test in ``test_session_detail_restructure.py`` already pins
    the new shape. This is the explicit PR 6a regression guard."""

    from app.web import views

    review_session = _make_session(client, db, code="ops-card")
    rows = views.build_setup_rows(db, review_session)
    labels = [r.label for r in rows]
    assert "Assignments" not in labels


# ---------------------------------------------------------------------------
# Operations page surface
# ---------------------------------------------------------------------------


def test_operations_page_drops_manual_upload_card(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ops-noupload")
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert 'id="upload-csv"' not in body
    assert "Upload Manual Assignment" not in body
    assert "manual/import" not in body


def test_operations_page_does_not_render_generate_card(
    client: TestClient, db: Session
) -> None:
    """Slice 3a retired the Rule Based card; the Next-Action
    workflow-stepper refresh subsequently retired the standalone
    Generate assignments card too — the Next Action card's Generate
    Primary now carries that affordance."""

    review_session = _make_session(client, db, code="ops-rule")
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert 'id="rule-based-assignment"' not in body
    assert 'id="assignments-generate-card"' not in body


def _self_review_instrument_id(db: Session, session_id: int) -> int:
    from app.db.models import Instrument
    return db.execute(
        select(Instrument.id).where(Instrument.session_id == session_id)
    ).scalars().first()


def test_operations_page_renders_self_reviews_toggle_section(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ops-toggle")
    _seed_population_with_self_review(client, review_session.id)
    _generate_with_self_reviews(client, db, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    instrument_id = _self_review_instrument_id(db, review_session.id)
    # Standalone self-reviews card retired in the post-15B
    # refinement sweep — per-instrument Self review column on the
    # status block table owns the surface now.
    assert 'id="self-reviews-toggle"' not in body
    # The per-instrument checkbox is in the Self review column.
    assert (
        f'data-self-review-instrument="{instrument_id}"' in body
    )
    # Default state on a fresh session is ``self_reviews_active=True``;
    # the single self-review row in this fixture lands include=True,
    # so the checkbox renders as ``checked``.
    assert (
        'data-self-review-state="checked"' in body
    )


def test_self_reviews_column_omits_checkbox_when_count_zero(
    client: TestClient, db: Session
) -> None:
    """Empty self-review state: the Self review column shows a 0
    pill but does NOT render the checkbox — nothing to toggle."""

    review_session = _make_session(client, db, code="ops-toggle-zero")
    # Generate against a population with no email overlap.
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
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
    _generate_with_self_reviews(client, db, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    instrument_id = _self_review_instrument_id(db, review_session.id)
    # 0 self-review rows → pill still renders (with value 0) but no
    # toggle checkbox.
    assert (
        f'data-self-review-count="{instrument_id}">0</span>' in body
    )
    assert (
        f'data-self-review-instrument="{instrument_id}"' not in body
    )


# ---------------------------------------------------------------------------
# Bulk-toggle route
# ---------------------------------------------------------------------------


def _self_review_includes(
    db: Session, session_id: int
) -> set[bool]:
    rows = db.execute(
        select(Assignment, Reviewer, Reviewee)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .where(Assignment.session_id == session_id)
    ).all()
    return {
        a.include
        for a, r, e in rows
        if r.email.casefold() == e.email_or_identifier.casefold()
    }


def test_per_instrument_toggle_off_flips_self_review_rows_to_inactive(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ops-flip-off")
    _seed_population_with_self_review(client, review_session.id)
    _generate_with_self_reviews(client, db, review_session.id)
    instrument_id = _self_review_instrument_id(db, review_session.id)

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/{instrument_id}/self-reviews/active",
        data={"active": "false"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    assert _self_review_includes(db, review_session.id) == {False}


def test_per_instrument_toggle_on_flips_self_review_rows_to_active(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ops-flip-on")
    review_session.self_reviews_active = False
    db.commit()
    _seed_population_with_self_review(client, review_session.id)
    _generate_with_self_reviews(client, db, review_session.id)
    # After generation against the OFF session flag, self-review
    # rows landed inactive (12C-1 PR 1 wired this).
    assert _self_review_includes(db, review_session.id) == {False}
    instrument_id = _self_review_instrument_id(db, review_session.id)

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/{instrument_id}/self-reviews/active",
        data={"active": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    assert _self_review_includes(db, review_session.id) == {True}


def test_per_instrument_toggle_emits_audit_event(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ops-audit")
    _seed_population_with_self_review(client, review_session.id)
    _generate_with_self_reviews(client, db, review_session.id)
    instrument_id = _self_review_instrument_id(db, review_session.id)

    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/{instrument_id}/self-reviews/active",
        data={"active": "false"},
        follow_redirects=False,
    )

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type
            == "assignments.instrument_self_reviews_active_set",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = event.detail
    assert detail["counts"]["flipped"] == 1
    assert detail["context"]["active"] is False
    assert detail["refs"]["instrument_id"] == instrument_id


def test_per_instrument_toggle_idempotent_when_state_unchanged(
    client: TestClient, db: Session
) -> None:
    """Posting active=true on an already-active instrument should
    succeed and audit zero flipped rows (no work to do)."""

    review_session = _make_session(client, db, code="ops-idem")
    _seed_population_with_self_review(client, review_session.id)
    _generate_with_self_reviews(client, db, review_session.id)
    instrument_id = _self_review_instrument_id(db, review_session.id)
    # Default is_active=True; toggling to true again does nothing.
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/{instrument_id}/self-reviews/active",
        data={"active": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type
            == "assignments.instrument_self_reviews_active_set",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    assert event.detail["counts"]["flipped"] == 0
