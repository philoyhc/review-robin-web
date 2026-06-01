"""Integration coverage for the reviewee ``/me/sessions/{id}/results``
body — the Raw visibility-mode slice of W16.

Setup pattern: operator creates a session (alice), seeds one
reviewer + one reviewee, generates Full Matrix assignments,
activates. The reviewer signs in (rae), submits one full set of
responses on the instrument. The reviewee (carol) signs in and
GETs ``/me/sessions/{id}/results``. The expected outcome
depends on the operator's ``reviewee`` visibility-policy
authoring:

- Policy off (or no row) → empty body ("No responses to view
  yet.").
- Policy Raw after_release + release window open → one section
  with the Reviewer column showing rae's name + email.
- Policy Raw after_release + window not opened → empty body.

See ``spec/visibility_policy.md`` + the W16 slice plan.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
import pytest

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Response,
    ReviewSession,
    User,
)
from app.services import visibility_policies
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


@pytest.fixture
def carol() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="carol-oid",
        email="carol@example.edu",
        name="Carol Reviewee",
        provider="aad",
    )


def _seed_and_activate(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str = "rae@example.edu",
    reviewee_email: str = "carol@example.edu",
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
                f"RevieweeName,RevieweeEmail\nCarol,{reviewee_email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator_client, review_session.id)
    operator_client.get(
        f"/operator/sessions/{review_session.id}/assignments?validated=1"
    )
    response = operator_client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(review_session)
    return review_session


def _seed_submitted_responses(
    db: Session,
    review_session: ReviewSession,
    *,
    instrument: Instrument | None = None,
    rating_value: str = "4",
    comments_value: str = "Solid work.",
    submitted: bool = True,
) -> None:
    """Insert ``Response`` rows directly for every assignment on
    the (instrument | first instrument) of the session. Skips the
    HTTP submit pipeline so the test setup stays simple; the
    surface-rendering invariants we're checking don't depend on
    going through the form."""
    if instrument is None:
        instrument = db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars().first()
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()
    submitted_at = datetime.now(timezone.utc) if submitted else None
    assignments = db.execute(
        select(Assignment).where(
            Assignment.session_id == review_session.id,
            Assignment.instrument_id == instrument.id,
            Assignment.include.is_(True),
        )
    ).scalars().all()
    for assignment in assignments:
        db.add(
            Response(
                assignment_id=assignment.id,
                response_field_id=rating.id,
                value=rating_value,
                submitted_at=submitted_at,
            )
        )
        db.add(
            Response(
                assignment_id=assignment.id,
                response_field_id=comments.id,
                value=comments_value,
                submitted_at=submitted_at,
            )
        )
    db.commit()


def _enable_reviewee_after_release_raw(
    db: Session,
    review_session: ReviewSession,
    *,
    operator: User,
    open_window: bool,
) -> None:
    """Author the ``reviewee`` policy as Raw on the after_release
    cell + (optionally) move the release-from anchor into the
    past so the window is currently open."""
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="reviewee",
        while_ongoing_mode=None,
        after_release_mode="raw",
        user=operator,
    )
    if open_window:
        review_session.responses_release_at = datetime.now(
            timezone.utc
        ) - timedelta(hours=1)
    db.commit()


# ── Body coverage ─────────────────────────────────────────────────────


def _operator_user(db: Session) -> User:
    return db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()


def test_results_body_renders_raw_responses_for_reviewee(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Happy path: operator opens Raw after_release for the
    reviewee audience + the release window is open → reviewee
    sees one section with the reviewer's name + email + the
    submitted values."""
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="vp-raw-ok")
    _seed_submitted_responses(db, review_session)
    _enable_reviewee_after_release_raw(
        db, review_session, operator=_operator_user(db), open_window=True
    )

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text

    # No empty-state copy.
    assert "No responses to view yet." not in body
    # The Reviewer column header is the differentiator from the
    # operator-side / reviewer summary surfaces (which lead with
    # Reviewee / Group).
    assert '<th scope="col" class="rs-reviewee">Reviewer</th>' in body
    # Rae's identity in the row.
    assert "Rae" in body
    assert "rae@example.edu" in body
    # The submitted values surface.
    assert "Solid work." in body


def test_results_body_empty_when_no_visibility_policy(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Reviewer submitted, but no operator-authored visibility
    policy for the ``reviewee`` audience → empty body."""
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="vp-raw-nopol")
    _seed_submitted_responses(db, review_session)

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    assert "No responses to view yet." in body
    assert "Reviewer</th>" not in body


def test_results_body_window_closed_shows_scaffolding_without_values(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Operator authored Raw on after_release but ``responses_release_at``
    is NULL (or in the future) — the section still renders so the
    reviewee can see the would-be reviewers, but the submitted
    response values stay hidden until the window opens. Empty
    cells render as muted em-dashes."""
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="vp-raw-future")
    _seed_submitted_responses(
        db, review_session, comments_value="Solid work."
    )
    _enable_reviewee_after_release_raw(
        db, review_session, operator=_operator_user(db), open_window=False
    )

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    # Section renders — the reviewer-row scaffolding is visible.
    assert "No responses to view yet." not in body
    assert '<th scope="col" class="rs-reviewee">Reviewer</th>' in body
    assert "Rae" in body
    # But the submitted values stay hidden until the window opens.
    assert "Solid work." not in body
    # And the empty cells render as the muted em-dash placeholder.
    assert body.count('<span class="muted">—</span>') >= 2


def test_results_body_drafts_render_empty_value_cells(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A reviewer with only draft rows still surfaces in the
    table — their identity (Rae + email) renders so the
    reviewee can see who the would-be reviewers are — but the
    response cells stay empty until the reviewer hits Submit.
    Draft text never leaks back to the reviewee."""
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="vp-raw-draft")
    _seed_submitted_responses(
        db,
        review_session,
        comments_value="draft text",
        submitted=False,
    )
    _enable_reviewee_after_release_raw(
        db, review_session, operator=_operator_user(db), open_window=True
    )

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    # Draft content never leaks.
    assert "draft text" not in body
    # The section still renders — the reviewer's row is there.
    assert "No responses to view yet." not in body
    assert '<th scope="col" class="rs-reviewee">Reviewer</th>' in body
    assert "Rae" in body
    assert "rae@example.edu" in body
    # The empty-cell placeholder appears at least twice (the
    # rating + comments fields both render as ``—`` since no
    # submitted value exists). The em-dash is wrapped in
    # ``<span class="muted">—</span>``.
    assert body.count('<span class="muted">—</span>') >= 2


def test_results_body_lists_unsubmitted_reviewers_with_empty_cells(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """When the operator opens Raw + the window is open but no
    reviewer has filed anything yet, every assigned reviewer
    surfaces with empty value cells — the reviewee can see the
    would-be reviewers' identities before any have submitted."""
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="vp-raw-no-resp")
    # No ``_seed_submitted_responses`` call — there are zero
    # responses on the session.
    _enable_reviewee_after_release_raw(
        db, review_session, operator=_operator_user(db), open_window=True
    )

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    assert "No responses to view yet." not in body
    assert '<th scope="col" class="rs-reviewee">Reviewer</th>' in body
    assert "Rae" in body
    assert "rae@example.edu" in body
    # Empty cells render as muted em-dash placeholders.
    assert body.count('<span class="muted">—</span>') >= 2


def test_results_body_omits_instrument_with_policy_off(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Multi-instrument case: open Raw on one instrument and
    leave the other off. Only the policy-on instrument renders a
    section."""
    operator = make_client(alice)
    # Build the session manually so a second instrument can be
    # added pre-activation (post-activation the editable-window
    # check rejects new instruments).
    operator.post(
        "/operator/sessions",
        data={"name": "vp-raw-multi", "code": "vp-raw-multi"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "vp-raw-multi")
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\n",
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
    # Label the seeded first instrument + add a second before
    # generating assignments.
    first_instrument = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .order_by(Instrument.order, Instrument.id)
    ).scalars().first()
    first_instrument.short_label = "First Form"
    db.commit()
    operator.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        follow_redirects=False,
    )
    instruments = (
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        )
        .scalars()
        .all()
    )
    assert len(instruments) == 2
    second_instrument = instruments[1]
    second_instrument.short_label = "Second Form"
    db.commit()
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    operator.get(
        f"/operator/sessions/{review_session.id}/assignments?validated=1"
    )
    response = operator.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(review_session)

    # Submit responses for both instruments.
    _seed_submitted_responses(
        db, review_session, instrument=first_instrument
    )
    _seed_submitted_responses(
        db, review_session, instrument=second_instrument
    )

    # Open Raw on the first instrument; leave second off.
    visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=first_instrument,
        audience="reviewee",
        while_ongoing_mode=None,
        after_release_mode="raw",
        user=_operator_user(db),
    )
    review_session.responses_release_at = datetime.now(
        timezone.utc
    ) - timedelta(hours=1)
    db.commit()

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    assert "First Form" in body
    assert "Second Form" not in body


def test_results_body_hides_section_when_release_window_explicitly_closed(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Once the operator has explicitly shut the after-release
    window (``responses_release_until`` set and reached — Stop
    release, or the scheduled close datetime), the reviewee
    surface drops back to empty. The pre-release scaffolding
    exception only applies before the window has fired; after
    the explicit close, the grant is retired and reviewer
    identities + display fields stop surfacing alongside the
    values they used to pair with."""
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="vp-raw-closed")
    _seed_submitted_responses(
        db, review_session, comments_value="Solid work."
    )
    # Author Raw on after_release; stamp anchor + until both in
    # the past so the window has explicitly closed.
    _enable_reviewee_after_release_raw(
        db, review_session, operator=_operator_user(db), open_window=True
    )
    review_session.responses_release_until = datetime.now(
        timezone.utc
    ) - timedelta(minutes=30)
    db.commit()

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    assert "No responses to view yet." in body
    assert "Rae" not in body
    assert "rae@example.edu" not in body
    assert "Solid work." not in body


def _enable_reviewee_after_release_anonymized(
    db: Session,
    review_session: ReviewSession,
    *,
    operator: User,
    open_window: bool,
) -> None:
    """Author the ``reviewee`` policy as Anonymized (the operator-
    facing "Anonymized responses" chip) on after_release."""
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="reviewee",
        while_ongoing_mode=None,
        after_release_mode="anonymized",
        user=operator,
    )
    if open_window:
        review_session.responses_release_at = datetime.now(
            timezone.utc
        ) - timedelta(hours=1)
    db.commit()


def _enable_reviewee_after_release_summarized(
    db: Session,
    review_session: ReviewSession,
    *,
    operator: User,
    open_window: bool,
) -> None:
    """Author the ``reviewee`` policy as Summarized (the operator-
    facing "Anonymized summaries" chip) on after_release.

    ``summarized`` is per-data-type aggregation, a different
    render shape from the per-row ``anonymized`` view, and is
    not surfaced in this slice — these tests assert it's
    treated as unrendered (the section drops)."""
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="reviewee",
        while_ongoing_mode=None,
        after_release_mode="summarized",
        user=operator,
    )
    if open_window:
        review_session.responses_release_at = datetime.now(
            timezone.utc
        ) - timedelta(hours=1)
    db.commit()


def test_results_body_anonymized_dashes_identification_keeps_values(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """``anonymized`` mode (operator's "Anonymized responses"
    chip): the same per-reviewer table renders as Raw, but the
    Reviewer column's name + email — and every display-field
    cell — collapses to the muted em-dash placeholder. The
    response values themselves still surface."""
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="vp-anon-ok")
    _seed_submitted_responses(
        db, review_session, comments_value="Solid work."
    )
    _enable_reviewee_after_release_anonymized(
        db, review_session, operator=_operator_user(db), open_window=True
    )

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    # Section renders + Reviewer column header still labeled.
    assert "No responses to view yet." not in body
    assert '<th scope="col" class="rs-reviewee">Reviewer</th>' in body
    # Identification dashed — Rae's name + email never surface.
    assert "Rae" not in body
    assert "rae@example.edu" not in body
    # Response values still surface.
    assert "Solid work." in body
    # At least one em-dash placeholder rendered inside an
    # ``rs-reviewee`` cell — the Reviewer column cell.
    assert '<span class="muted">—</span>' in body


def test_results_body_anonymized_window_closed_explicitly_hides_section(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Same gating as Raw — once the operator explicitly closes
    the after-release window (``responses_release_until`` set +
    reached), the Anonymized section also hides. The grant has
    been retired and even the dashed scaffolding stops showing."""
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="vp-anon-closed")
    _seed_submitted_responses(
        db, review_session, comments_value="Solid work."
    )
    _enable_reviewee_after_release_anonymized(
        db, review_session, operator=_operator_user(db), open_window=True
    )
    review_session.responses_release_until = datetime.now(
        timezone.utc
    ) - timedelta(minutes=30)
    db.commit()

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    assert "No responses to view yet." in body
    assert "Solid work." not in body


def test_results_body_summarized_aggregates_numerical_and_strings(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """``summarized`` (operator's "Anonymized summaries" chip)
    collapses identification columns into a single counts cell
    and rows into one. Numerical response fields render mean,
    median, min, max + the count basis; String fields render
    total + average character length. The raw String value
    itself never surfaces (the whole point of the summary
    mode)."""
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="vp-sum-num")
    _seed_submitted_responses(
        db,
        review_session,
        rating_value="4",
        comments_value="Solid work.",
    )
    _enable_reviewee_after_release_summarized(
        db, review_session, operator=_operator_user(db), open_window=True
    )

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    # Section renders; the per-row table chrome is gone.
    assert "No responses to view yet." not in body
    assert "Reviewer</th>" not in body
    assert ">Summary</th>" in body
    # Counts cell: one reviewer assigned, one with responses.
    assert "Number of reviewers assigned: 1" in body
    assert "Number of reviewers with some responses: 1" in body
    # Integer aggregate for the seeded rating=4 (single response):
    # mean / median / min / max all 4.0, count 1.
    assert "Average: 4.0" in body
    assert "Median: 4.0" in body
    assert "Min: 4.0" in body
    assert "Max: 4.0" in body
    assert "(based on 1 responses)" in body
    # String aggregate: "Solid work." = 11 chars.
    assert "Total length: 11 characters" in body
    assert "Average length: 11.0 characters" in body
    # But the raw String content itself never surfaces.
    assert "Solid work." not in body


def test_results_body_summarized_aggregates_list_choice_frequencies(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A List response field renders one ``choice: count`` line
    per declared option, including options that received zero
    responses. The operator's "Anonymized summaries" chip is
    the right surface to see a quick distribution snapshot
    without exposing per-reviewer authorship."""
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="vp-sum-list")
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    # Add a List response field with three options.
    list_field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="grade",
        label="Grade",
        required=False,
        order=3,
        _inline_data_type="List",
        _inline_response_type="Letter_grade",
        _inline_list_csv="A,B,C",
    )
    db.add(list_field)
    db.commit()

    # One reviewer + one reviewee → only one Response row for the
    # list field. Seed it as "B".
    assignment = db.execute(
        select(Assignment).where(
            Assignment.session_id == review_session.id,
            Assignment.instrument_id == instrument.id,
            Assignment.include.is_(True),
        )
    ).scalar_one()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=list_field.id,
            value="B",
            submitted_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    _enable_reviewee_after_release_summarized(
        db, review_session, operator=_operator_user(db), open_window=True
    )

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    # Every declared option surfaces — including the two with zero
    # responses — so the operator/reviewee can see the distribution.
    # Percentages are computed over the total response count.
    assert "A: 0 (0.0%)" in body
    assert "B: 1 (100.0%)" in body
    assert "C: 0 (0.0%)" in body


def test_results_body_summarized_zero_responses_shows_label_scaffolding(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """When the reviewer has assignments but hasn't submitted
    yet, the summarized section still renders with full label
    scaffolding so the reviewee can see what each cell will
    eventually show. Numerical cells render "Average: —",
    "Median: —", etc. with the count line below; String cells
    render the length labels likewise. Mirrors the Raw mode's
    "scaffolding without values" preview behavior."""
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="vp-sum-empty")
    # No _seed_submitted_responses() — no Response rows exist.
    _enable_reviewee_after_release_summarized(
        db, review_session, operator=_operator_user(db), open_window=True
    )

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    assert ">Summary</th>" in body
    assert "Number of reviewers assigned: 1" in body
    assert "Number of reviewers with some responses: 0" in body
    # Numerical labels show even with zero responses — operator + reviewee
    # see the future shape of the cell.
    assert "Average:" in body
    assert "Median:" in body
    assert "Min:" in body
    assert "Max:" in body
    # String labels show likewise.
    assert "Total length:" in body
    assert "Average length:" in body
    assert "(based on 0 responses)" in body


# ── Column-shape mirroring (Raw + Anonymized contract) ───────────────


def test_results_columns_mirror_reviewer_surface_widths(
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Contract: when the operator drag-resizes a column on the
    Band 2 editor, the resulting per-column pixel width must
    apply uniformly across the reviewer surface (where the
    operator authored it) AND the reviewee results page (where
    the reviewee reads the same instrument). Same applies for
    Raw + Anonymized modes — both keep the operator's column
    layout intact.

    Pin: ``Instrument.column_widths`` (``"identity"`` /
    ``"df_<id>"`` / ``"rf_<id>"``) drives both surfaces. When
    any custom width is set, the rendered HTML carries
    ``style="table-layout: fixed;"`` + a ``<colgroup>`` with
    the same explicit ``<col style="width: Npx">`` pixel
    values on both pages.
    """
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="vp-cols")
    instrument = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .order_by(Instrument.order, Instrument.id)
    ).scalars().first()
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    # Operator drag-resizes the identity column + the rating
    # response field. This is the same per-column-widths shape
    # the Band 2 editor persists; cosmetic divergence between
    # the reviewer form and the reviewee results page is the
    # exact regression this test guards against.
    instrument.column_widths = {
        "identity": 220,
        f"rf_{rating.id}": 90,
    }
    db.commit()

    _seed_submitted_responses(
        db, review_session, comments_value="Solid work."
    )
    _enable_reviewee_after_release_raw(
        db, review_session, operator=_operator_user(db), open_window=True
    )

    # Both surfaces should render the same widths.
    reviewer_body = make_client(rae).get(
        f"/me/sessions/{review_session.id}/1"
    ).text
    reviewee_body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    for body in (reviewer_body, reviewee_body):
        assert 'style="table-layout: fixed;"' in body
        assert 'style="width: 220px"' in body
        assert 'style="width: 90px"' in body


def test_results_columns_drop_deselected_response_fields(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Contract: a response field deselected on the Band 2
    editor (``InstrumentResponseField.visible = False``) must
    not surface as a column on the reviewee results page —
    same filter the reviewer surface applies."""
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="vp-cols-drop")
    instrument = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .order_by(Instrument.order, Instrument.id)
    ).scalars().first()
    # Hide the comments field so the operator's "Anonymized
    # responses" view should only show the rating column. The
    # column header literal "Comments" must not surface.
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()
    comments.visible = False
    db.commit()

    _seed_submitted_responses(
        db, review_session, comments_value="Solid work."
    )
    _enable_reviewee_after_release_raw(
        db, review_session, operator=_operator_user(db), open_window=True
    )

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    assert "Rating" in body
    assert "Comments" not in body
    # The hidden comments value also doesn't leak.
    assert "Solid work." not in body


def test_results_columns_drop_reviewee_identity_display_fields(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Contract: reviewee-identity display fields (Name / Email
    / Profile) are excluded from the per-row display cells on
    both surfaces — they'd just repeat the signed-in reviewee
    on every row. The exclusion is keyed by
    ``InstrumentDisplayField.source_type == "reviewee"`` +
    ``source_field in {"name", "email_or_identifier",
    "profile_link"}``."""
    operator = make_client(alice)
    review_session = _seed_and_activate(
        operator, db, code="vp-cols-identity"
    )
    instrument = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .order_by(Instrument.order, Instrument.id)
    ).scalars().first()
    # Add a reviewee Name display field (would-be identity
    # column) + a reviewee.tag_1 column (would-be tag column).
    db.add(
        InstrumentDisplayField(
            instrument_id=instrument.id,
            source_type="reviewee",
            source_field="name",
            label="Reviewee Name",
            order=1,
            visible=True,
        )
    )
    db.add(
        InstrumentDisplayField(
            instrument_id=instrument.id,
            source_type="reviewee",
            source_field="tag_1",
            label="Reviewee Tag 1",
            order=2,
            visible=True,
        )
    )
    db.commit()

    _seed_submitted_responses(db, review_session)
    _enable_reviewee_after_release_raw(
        db, review_session, operator=_operator_user(db), open_window=True
    )

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    # tag_1 column survives (visible non-identity). Its label
    # ("Tag 1" by default) appears as a column header.
    assert "tag_1" in body.lower() or "Tag" in body
    # The signed-in reviewee's own name "Carol" must not surface
    # as a display-field value cell on every row (it'd repeat
    # the user's identity unnecessarily). The session header /
    # role chips might mention Carol, but the per-row display
    # cells shouldn't.
    body_lower = body.lower()
    # Carol is a Reviewee in this session; she's the signed-in
    # user. Her name should not appear in any per-row display
    # cell. The reviewer surface's identity column on a
    # reviewer-facing form would show her in the Reviewee cell,
    # but on the reviewee surface the identity column is the
    # Reviewer instead. Counting Carol mentions in the table
    # body: should be 0 (no display cell repeats her).
    table_open = body_lower.find("<table")
    table_close = body_lower.find("</table>")
    assert table_open != -1
    assert table_close != -1
    table_section = body_lower[table_open:table_close]
    assert "carol" not in table_section


# ── Group-scoped instrument rendering ────────────────────────────────


def test_results_body_group_scoped_drops_display_field_columns(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """For a group-scoped instrument, the reviewee surface drops
    every display-field column entirely — mirroring the reviewer
    surface + reviewer summary's group rendering. The per-row
    identity for a group-scoped instrument is conceptually the
    *group*, not individual members; fanning reviewee-tag
    columns out alongside a group row would split the table's
    identity axis into 4-5 distinct columns and lose its
    row-per-reviewer shape.

    Pin: a group-scoped instrument with a visible
    ``reviewee.tag_1`` display field renders with only the
    Reviewer identity column + the response field columns. The
    tag column header doesn't appear; no tag value cell leaks
    onto the page either.
    """
    operator = make_client(alice)
    # Manual setup so we can add a group-scoped instrument
    # before activation. Mirrors the pattern in
    # ``test_reviewer_response_flow.test_group_instrument_save_fans_out_to_all_members``.
    operator.post(
        "/operator/sessions",
        data={"name": "Grp Results", "code": "grp-res"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "grp-res")
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
                b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\n",
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
                b"Carol,carol@example.edu,Squad-A\n"
                b"Dan,dan@example.edu,Squad-A\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    # Pull the group-scoped instrument out so we can configure
    # display fields + the visibility policy. Drop the seeded
    # per-reviewee instrument so this test only exercises the
    # group case.
    group_instrument = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.group_kind.is_not(None))
    ).scalar_one()
    other_instruments = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.group_kind.is_(None))
    ).scalars().all()
    for other in other_instruments:
        db.delete(other)
    db.commit()
    # Add a visible reviewee.tag_1 display field on the group
    # instrument — its column must NOT surface on the reviewee
    # results page.
    db.add(
        InstrumentDisplayField(
            instrument_id=group_instrument.id,
            source_type="reviewee",
            source_field="tag_1",
            label="Squad",
            order=1,
            visible=True,
        )
    )
    db.commit()
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    operator.get(
        f"/operator/sessions/{review_session.id}/assignments?validated=1"
    )
    activate_response = operator.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert activate_response.status_code == 303
    db.refresh(review_session)

    _seed_submitted_responses(
        db,
        review_session,
        instrument=group_instrument,
        comments_value="Team did well.",
    )
    visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=group_instrument,
        audience="reviewee",
        while_ongoing_mode=None,
        after_release_mode="raw",
        user=_operator_user(db),
    )
    review_session.responses_release_at = datetime.now(
        timezone.utc
    ) - timedelta(hours=1)
    db.commit()

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text

    # Section + Reviewer column render.
    assert "No responses to view yet." not in body
    assert '<th scope="col" class="rs-reviewee">Reviewer</th>' in body
    # The seeded response surfaces.
    assert "Team did well." in body
    # Critically: the reviewee.tag_1 display column ("Squad")
    # does NOT surface — group-scoped instruments drop display
    # field columns to keep the table's row-per-reviewer shape.
    table_open = body.find("<table")
    table_close = body.find("</table>")
    assert table_open != -1
    table_section = body[table_open:table_close]
    assert "Squad" not in table_section
    assert "Squad-A" not in table_section
    # Carol's name should not leak into the table body — for a
    # group-scoped instrument on the reviewee surface the
    # per-row identity is the Reviewer (Rae), not the
    # signed-in reviewee.
    assert "Carol" not in table_section
    assert "Dan" not in table_section
    # Exactly one row in the rendered table (Rae's row) — no
    # per-member fan-out.
    assert table_section.count("<tr>") == 1 + 1  # thead + 1 body row


# ── Scope-leak guard: only own / own-group responses surface ─────────


def test_results_body_excludes_responses_about_other_reviewees(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A per-reviewee instrument where Rae reviews TWO reviewees
    (Carol + Dan). Rae submits distinct comments about each.
    When Carol queries /results, she must see ONLY Rae's
    response about her — never the response about Dan."""
    operator = make_client(alice)
    operator.post(
        "/operator/sessions",
        data={"name": "Multi Reviewee", "code": "multi-ree"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "multi-ree")
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\n",
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
                b"Carol,carol@example.edu\n"
                b"Dan,dan@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    operator.get(
        f"/operator/sessions/{review_session.id}/assignments?validated=1"
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)

    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()
    # Distinct comments per assignment so we can detect a leak
    # by string match: Carol's row should NOT carry Dan's text.
    assignments = db.execute(
        select(Assignment).where(
            Assignment.session_id == review_session.id,
            Assignment.instrument_id == instrument.id,
            Assignment.include.is_(True),
        )
    ).scalars().all()
    submitted_at = datetime.now(timezone.utc)
    for assignment in assignments:
        reviewee_row = assignment.reviewee
        if reviewee_row.email_or_identifier == "carol@example.edu":
            comment_text = "About-Carol comment."
        else:
            comment_text = "About-Dan comment."
        db.add(
            Response(
                assignment_id=assignment.id,
                response_field_id=rating.id,
                value="4",
                submitted_at=submitted_at,
            )
        )
        db.add(
            Response(
                assignment_id=assignment.id,
                response_field_id=comments.id,
                value=comment_text,
                submitted_at=submitted_at,
            )
        )
    db.commit()

    visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="reviewee",
        while_ongoing_mode=None,
        after_release_mode="raw",
        user=_operator_user(db),
    )
    review_session.responses_release_at = datetime.now(
        timezone.utc
    ) - timedelta(hours=1)
    db.commit()

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    # Carol's own comment surfaces.
    assert "About-Carol comment." in body
    # Dan's comment must NOT leak — it's not about Carol.
    assert "About-Dan comment." not in body
    # Dan's identity (name / email) must not leak as an identity
    # either — Carol shouldn't learn what Rae said about Dan.
    assert "dan@example.edu" not in body


def test_results_body_excludes_responses_about_other_groups(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A group-scoped instrument with TWO groups (Squad-A:
    Carol + Dan, Squad-B: Erin + Frank). Rae reviews both
    groups and submits distinct comments per group. When Carol
    queries /results, she must see ONLY Rae's response about
    her group (Squad-A) — never the Squad-B response."""
    operator = make_client(alice)
    operator.post(
        "/operator/sessions",
        data={"name": "Multi Group", "code": "multi-grp"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "multi-grp")
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
                b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\n",
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
                b"Carol,carol@example.edu,Squad-A\n"
                b"Dan,dan@example.edu,Squad-A\n"
                b"Erin,erin@example.edu,Squad-B\n"
                b"Frank,frank@example.edu,Squad-B\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    # Drop the seeded per-reviewee instrument so we only test
    # the group-scoped one.
    other_instruments = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.group_kind.is_(None))
    ).scalars().all()
    for other in other_instruments:
        db.delete(other)
    db.commit()
    group_instrument = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.group_kind.is_not(None))
    ).scalar_one()
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    operator.get(
        f"/operator/sessions/{review_session.id}/assignments?validated=1"
    )
    operator.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(review_session)

    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == group_instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == group_instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()
    # Look up which assignments belong to which group via the
    # reviewee's tag_1 — Squad-A vs Squad-B.
    assignments = db.execute(
        select(Assignment).where(
            Assignment.session_id == review_session.id,
            Assignment.instrument_id == group_instrument.id,
            Assignment.include.is_(True),
        )
    ).scalars().all()
    submitted_at = datetime.now(timezone.utc)
    for assignment in assignments:
        reviewee_row = assignment.reviewee
        if reviewee_row.tag_1 == "Squad-A":
            comment_text = "Squad-A: team did well."
        else:
            comment_text = "Squad-B: team did poorly."
        db.add(
            Response(
                assignment_id=assignment.id,
                response_field_id=rating.id,
                value="4",
                submitted_at=submitted_at,
            )
        )
        db.add(
            Response(
                assignment_id=assignment.id,
                response_field_id=comments.id,
                value=comment_text,
                submitted_at=submitted_at,
            )
        )
    db.commit()

    visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=group_instrument,
        audience="reviewee",
        while_ongoing_mode=None,
        after_release_mode="raw",
        user=_operator_user(db),
    )
    review_session.responses_release_at = datetime.now(
        timezone.utc
    ) - timedelta(hours=1)
    db.commit()

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    # Carol's own group's response surfaces.
    assert "Squad-A: team did well." in body
    # Squad-B's response must not leak.
    assert "Squad-B: team did poorly." not in body
    # Erin / Frank's names + emails must not leak as identities
    # — Carol shouldn't learn anything about Squad-B's
    # composition or responses.
    assert "Erin" not in body
    assert "Frank" not in body
    assert "erin@example.edu" not in body
    assert "frank@example.edu" not in body


def test_results_body_team_unit_of_review_scopes_to_own_team(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Mirrors the user-reported setup: an instrument grouped by
    ``reviewee.tag_3`` (= "team"), with one Group of 4 teams
    (Team 1..4) each holding one reviewee. The reviewer (R21 on
    Team 2) reviews Teams 1, 3, 4 (pool = same group + different
    team). Each (reviewer, team) submission has a distinct
    value.

    Carol = A11 (Team 1). Her ``/results`` surface must show
    only R21's response about TEAM 1 — never R21's responses
    about Teams 3 or 4.
    """
    from app.db.models import Reviewer, Reviewee

    operator = make_client(alice)
    operator.post(
        "/operator/sessions",
        data={"name": "Pool TUR", "code": "pool-tur"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "pool-tur")
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{review_session.id}/instruments/add-group",
        follow_redirects=False,
    )
    # Drop the seeded per-reviewee instrument so this test is
    # scoped to the group-by-team instrument.
    pri = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.group_kind.is_(None))
    ).scalars().all()
    for inst in pri:
        db.delete(inst)
    db.commit()
    group_instrument = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.group_kind.is_not(None))
    ).scalar_one()
    # Configure the group boundary as ``reviewee.tag_3`` (the
    # "team" tag). The seeded ``group_kind`` from add-group may
    # be different; override directly so the fan-out keys by
    # team.
    group_instrument.group_kind = "r3"
    db.commit()

    # Roster: 4 individuals, each on a distinct team in the
    # same Group ("Alpha"). Each is BOTH a reviewer and a
    # reviewee in the session — mirrors the 360-style setup.
    rosters: list[tuple[str, str, str]] = [
        ("A11", "a11@example.edu", "Team-1"),
        ("A21", "a21@example.edu", "Team-2"),
        ("A31", "a31@example.edu", "Team-3"),
        ("A41", "a41@example.edu", "Team-4"),
    ]
    operator.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail,ReviewerTag2,ReviewerTag3\n"
                + b"".join(
                    f"{n},{e},Alpha,{t}\n".encode() for n, e, t in rosters
                ),
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
                b"RevieweeName,RevieweeEmail,RevieweeTag2,RevieweeTag3\n"
                + b"".join(
                    b"Carol,carol@example.edu,Alpha,Team-1\n"
                    if e == "a11@example.edu"
                    else f"{n},{e},Alpha,{t}\n".encode()
                    for n, e, t in rosters
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    db.commit()
    # Manually build the "Same Group + Different team" pool by
    # creating one Assignment row per (reviewer, reviewee) pair
    # where the team tag differs. This bypasses the rule
    # engine but produces the exact assignment matrix the user
    # describes.
    reviewers_by_email = {
        r.email: r
        for r in db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        ).scalars()
    }
    reviewees_by_email = {
        e.email_or_identifier: e
        for e in db.execute(
            select(Reviewee).where(Reviewee.session_id == review_session.id)
        ).scalars()
    }
    for reviewer_email, r in reviewers_by_email.items():
        for reviewee_email, e in reviewees_by_email.items():
            # Same Group + Different team — and skip self-review
            # by mismatched email.
            if r.tag_3 == e.tag_3:
                continue
            if r.tag_2 != e.tag_2:
                continue
            db.add(
                Assignment(
                    session_id=review_session.id,
                    instrument_id=group_instrument.id,
                    reviewer_id=r.id,
                    reviewee_id=e.id,
                    include=True,
                    created_by_mode="manual",
                )
            )
    db.commit()
    # Activate.
    review_session.status = "ready"
    db.commit()

    # Each (reviewer, target-team) team-review has one set of
    # values. We mimic that by inserting Responses whose value
    # encodes (reviewer_email, target_team) — so a leak would
    # surface a value tied to a team other than Carol's.
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == group_instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == group_instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()
    submitted_at = datetime.now(timezone.utc)
    assignments = db.execute(
        select(Assignment).where(
            Assignment.session_id == review_session.id,
            Assignment.instrument_id == group_instrument.id,
        )
    ).scalars().all()
    for a in assignments:
        # The "team being reviewed" is the reviewee's team.
        target_team = a.reviewee.tag_3
        reviewer_label = a.reviewer.name
        db.add(
            Response(
                assignment_id=a.id,
                response_field_id=rating.id,
                value=f"{reviewer_label}->{target_team}",
                submitted_at=submitted_at,
            )
        )
        db.add(
            Response(
                assignment_id=a.id,
                response_field_id=comments.id,
                value=f"{reviewer_label}-comment-about-{target_team}",
                submitted_at=submitted_at,
            )
        )
    db.commit()

    visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=group_instrument,
        audience="reviewee",
        while_ongoing_mode=None,
        after_release_mode="raw",
        user=_operator_user(db),
    )
    review_session.responses_release_at = datetime.now(
        timezone.utc
    ) - timedelta(hours=1)
    db.commit()

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text

    # Carol (A11, Team-1) should see responses ABOUT Team-1
    # from reviewers on Teams 2/3/4. Each surfaces as
    # ``<reviewer>-comment-about-Team-1``.
    assert "A21-comment-about-Team-1" in body
    assert "A31-comment-about-Team-1" in body
    assert "A41-comment-about-Team-1" in body
    # No response about another team should leak.
    for other_team in ("Team-2", "Team-3", "Team-4"):
        assert f"about-{other_team}" not in body, (
            f"leak: response about {other_team} should not appear "
            "on Carol's /results — she's on Team-1"
        )
