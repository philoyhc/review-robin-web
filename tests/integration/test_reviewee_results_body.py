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


def test_results_body_summarized_mode_is_unrendered(
    db: Session,
    alice: AuthenticatedUser,
    carol: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """``summarized`` (operator's "Anonymized summaries" chip) is
    per-data-type aggregation — a different render shape from
    the per-row table. Until the aggregation render ships, an
    instrument whose only authored mode is ``summarized`` reads
    as unrendered (no section, empty page). This pins the
    contract so a future aggregation slice doesn't accidentally
    inherit the dashed-row treatment from PR #1741's slip."""
    operator = make_client(alice)
    review_session = _seed_and_activate(operator, db, code="vp-sum-unrend")
    _seed_submitted_responses(
        db, review_session, comments_value="Solid work."
    )
    _enable_reviewee_after_release_summarized(
        db, review_session, operator=_operator_user(db), open_window=True
    )

    body = make_client(carol).get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    assert "No responses to view yet." in body
    assert "Solid work." not in body
    assert "Reviewer</th>" not in body


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
