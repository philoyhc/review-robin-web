"""Coverage for the ``/me`` dashboard's role-aware session-name
link + per-role pill links.

Contract:

- Each role pill becomes an ``<a>`` to its role-specific surface
  when the surface is reachable, else a plain ``<span>``.
- The session-name link picks the highest-priority reachable
  role (Reviewer → Reviewee → Observer). Single-role users land
  on their role's surface either way; multi-role users land on
  the reviewer surface (the only role with active work) and use
  the pills to reach the read-only views.
- ``session_status == "not opened"`` (draft / validated session)
  disables the reviewer link; the session-name link falls through to
  the next role. An archived session has no row at all.
- The status pill reads Not open yet / Open / Available / Closed,
  one rule for every role (participant audit M6).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    InstrumentViewPolicy,
    Observer,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import visibility_policies


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


# ── Per-pill link rendering ──────────────────────────────────────────


def test_reviewee_pill_renders_as_anchor_to_results(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    review_session = _make_session(client, db, code="link-re")
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier="alice@example.edu",
        )
    )
    db.commit()
    # 19F PR 2 — a reviewee row exists only while a grant resolves.
    grant_reviewee_visibility(review_session)
    body = client.get("/me").text
    expected = (
        f'<a class="pill pill-role-reviewee" '
        f'href="/me/sessions/{review_session.id}/results">Reviewee</a>'
    )
    assert expected in body


def test_observer_pill_renders_as_anchor_to_collation(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="link-ob")
    db.add(
        Observer(
            session_id=review_session.id,
            email="alice@example.edu",
            display_name="Alice",
        )
    )
    db.commit()
    body = client.get("/me").text
    expected = (
        f'<a class="pill pill-role-observer" '
        f'href="/me/sessions/{review_session.id}/collation">Observer</a>'
    )
    assert expected in body


def test_reviewer_pill_renders_as_span_when_session_not_opened(
    client: TestClient, db: Session
) -> None:
    """A draft session reads as ``not opened`` for the reviewer —
    the reviewer surface isn't reachable, so the pill stays as
    a plain ``<span>``."""
    review_session = _make_session(client, db, code="link-rv-draft")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Alice",
            email="alice@example.edu",
        )
    )
    db.commit()
    body = client.get("/me").text
    # No anchor on the reviewer pill — wrapped in a span instead.
    assert '<a class="pill pill-role-reviewer"' not in body
    assert '<span class="pill pill-role-reviewer">Reviewer</span>' in body


# ── Session-name prioritised target ──────────────────────────────────


def test_session_name_links_to_reviewer_when_reviewer_reachable(
    client: TestClient,
    db: Session,
) -> None:
    """A reviewer + reviewee + observer triple-role row, where
    the reviewer surface is reachable, lands the session-name
    link on the reviewer page."""
    review_session = _make_session(client, db, code="link-name-rv")
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Alice",
                email="alice@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Alice",
                email_or_identifier="alice@example.edu",
            ),
            Observer(
                session_id=review_session.id,
                email="alice@example.edu",
                display_name="Alice",
            ),
        ]
    )
    # Mark the session ``ready`` so session_status_for_reviewer
    # doesn't read "not opened" — but there are no instruments /
    # assignments, so it returns "closed", which still enables
    # the link per the existing dashboard contract.
    review_session.status = "ready"
    db.commit()
    body = client.get("/me").text
    assert f'href="/me/sessions/{review_session.id}/1"' in body
    # Reviewee + Observer links should not be the session-name
    # target — only the reviewer target should appear in a name
    # link. (They still appear inside the pill anchors.)
    # A name link is the one wrapping ``{{ session.name }}``;
    # we check by counting occurrences of the reviewer target
    # — once for the pill anchor, once for the name link.
    assert body.count(f'href="/me/sessions/{review_session.id}/1"') == 2


def test_reviewer_wins_over_reviewee_because_the_fall_through_is_unreachable(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    """**Rewritten at 19F PR 2a**, because the case it tested can no
    longer happen.

    It used to assert that on a ``draft`` session a reviewer+reviewee
    user's session-name link falls through past the disabled reviewer
    link to ``/results``. Gating the release window on ``expired``
    killed that scenario outright:

    * a reviewee link exists only when the session is ``expired``
      (their ``while_ongoing`` cell is off by construction, so their
      grant needs the after-release window); and
    * on ``expired``, ``session_status_for_reviewer`` returns
      ``"closed"``, which *enables* the reviewer link.

    So every state with a reviewee link also has a live reviewer link,
    and reviewer is first in priority order. **The Reviewer → Reviewee
    fall-through is now dead code** — recorded in the plan rather than
    quietly deleted. Reviewee → Observer is still reachable and is
    covered by the test below.
    """
    review_session = _make_session(client, db, code="link-fall-re")
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Alice",
                email="alice@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Alice",
                email_or_identifier="alice@example.edu",
            ),
        ]
    )
    db.commit()
    grant_reviewee_visibility(review_session)
    body = client.get("/me").text
    # Reviewer wins: the name points at the reviewer surface, not
    # /results, even though a live reviewee link also exists.
    assert f'href="/me/sessions/{review_session.id}/1"' in body
    # And the reviewee link is present as its own pill — the escape
    # hatch the priority order leaves open.
    assert (
        f'<a class="pill pill-role-reviewee" '
        f'href="/me/sessions/{review_session.id}/results">Reviewee</a>'
    ) in body


def test_session_name_falls_through_to_observer_when_only_observer_reachable(
    client: TestClient, db: Session
) -> None:
    """Observer-only row: the session-name link goes to
    ``/collation``."""
    review_session = _make_session(client, db, code="link-fall-ob")
    db.add(
        Observer(
            session_id=review_session.id,
            email="alice@example.edu",
            display_name="Alice",
        )
    )
    db.commit()
    body = client.get("/me").text
    assert f'href="/me/sessions/{review_session.id}/collation"' in body


def test_session_name_is_plain_text_when_no_role_reachable(
    client: TestClient, db: Session
) -> None:
    """Reviewer-only row on a draft session: the reviewer
    surface is not opened, and the user holds no other role —
    the session-name renders without a link."""
    review_session = _make_session(client, db, code="link-none")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Alice",
            email="alice@example.edu",
        )
    )
    db.commit()
    body = client.get("/me").text
    # No href anywhere in the row for this session — neither
    # session-name link nor pill anchor.
    assert f'href="/me/sessions/{review_session.id}' not in body


# ── Session status pill (participant audit M6) ──────────────────────


def _pill(css: str, label: str) -> str:
    return f'<span class="pill {css}">{label}</span>'


NOT_OPEN_YET = _pill("pill-info", "Not open yet")
OPEN = _pill("pill-success", "Open")
AVAILABLE = _pill("pill-success", "Available")
CLOSED = _pill("pill-error", "Closed")


def _observer_on(
    client: TestClient, db: Session, *, code: str, status: str
) -> ReviewSession:
    review_session = _make_session(client, db, code=code)
    review_session.status = status
    db.add(
        Observer(
            session_id=review_session.id,
            email="alice@example.edu",
            display_name="Alice",
        )
    )
    db.commit()
    return review_session


def test_one_status_rule_reads_the_lifecycle(
    client: TestClient, db: Session
) -> None:
    """Not open yet / Open / Closed from the lifecycle, one
    rule for every role (author's ruling 2026-10-15). Observer-only rows,
    with no observer grant, so "Closed" is not lifted to "Available"."""
    for code, status, pill in (
        ("st-draft", "draft", NOT_OPEN_YET),
        ("st-validated", "validated", NOT_OPEN_YET),
        ("st-ready", "ready", OPEN),
        ("st-expired", "expired", CLOSED),
    ):
        _observer_on(client, db, code=code, status=status)
        body = client.get("/me").text
        assert pill in body, status
        db.execute(
            Observer.__table__.delete().where(
                Observer.email == "alice@example.edu"
            )
        )
        db.commit()


def test_an_observer_with_a_grant_after_the_close_reads_available(
    client: TestClient, db: Session
) -> None:
    """Closed to responses, but the observer's collation still shows
    something: "Available", not "Closed"."""
    review_session = _observer_on(client, db, code="st-avail", status="expired")
    instrument = Instrument(session_id=review_session.id, name="F", order=1)
    db.add(instrument)
    db.flush()
    granularity, identification = visibility_policies.MODE_LABELS["raw"]
    db.add(
        InstrumentViewPolicy(
            instrument_id=instrument.id,
            audience="observer",
            after_release_granularity=granularity,
            after_release_identification=identification,
        )
    )
    review_session.responses_release_at = datetime.now(timezone.utc) - timedelta(
        hours=1
    )
    db.commit()
    body = client.get("/me").text
    assert AVAILABLE in body
    assert CLOSED not in body


def test_a_reviewer_past_the_deadline_with_answers_reads_available(
    client: TestClient, db: Session
) -> None:
    """Past the deadline a ``ready`` session no longer accepts, but the
    reviewer can still read back what they saved; with nothing saved
    there is nothing to see, so the row reads "Closed"."""
    review_session = _make_session(client, db, code="st-rev-past")
    review_session.status = "ready"
    review_session.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    reviewer = Reviewer(
        session_id=review_session.id, name="Alice", email="alice@example.edu"
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Bob",
        email_or_identifier="bob@example.edu",
    )
    instrument = Instrument(session_id=review_session.id, name="F", order=1)
    db.add_all([reviewer, reviewee, instrument])
    db.flush()
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="comments",
        label="Comments",
        order=1,
    )
    assignment = Assignment(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
    )
    db.add_all([field, assignment])
    db.commit()
    assert CLOSED in client.get("/me").text

    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=field.id,
            value="kept",
        )
    )
    db.commit()
    body = client.get("/me").text
    assert AVAILABLE in body


def test_a_reviewer_with_nothing_assigned_is_told_so(
    client: TestClient, db: Session
) -> None:
    """Not a "0/0" progress pill."""
    review_session = _make_session(client, db, code="st-rev-none")
    review_session.status = "ready"
    db.add(
        Reviewer(
            session_id=review_session.id, name="Alice", email="alice@example.edu"
        )
    )
    db.commit()
    body = client.get("/me").text
    assert "Nothing assigned to you" in body
    assert ">0/0<" not in body


def test_no_view_responses_or_until_columns(
    client: TestClient, db: Session
) -> None:
    """Both were always "—" (participant audit M7)."""
    _observer_on(client, db, code="st-cols", status="ready")
    body = client.get("/me").text
    assert "<th>View responses</th>" not in body
    assert "<th>Until</th>" not in body


def test_a_draft_does_not_show_a_start_from_before_its_revert(
    client: TestClient, db: Session
) -> None:
    review_session = _observer_on(client, db, code="st-start", status="expired")
    review_session.activated_at = datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc)
    db.commit()
    assert "2026-01-02 09:00" in client.get("/me").text
    review_session.status = "draft"
    db.commit()
    assert "2026-01-02 09:00" not in client.get("/me").text


# ── 19F PR 5 — the archived observer row is present but unlinked ──────


def test_observer_row_is_linked_in_every_state_but_archived(
    client: TestClient, db: Session
) -> None:
    """Decision 4 and decision 7 together.

    Observers are deliberately not grant-gated — being appointed an
    observer is not a disclosure *about* the observer — so the link is
    live even before their window opens, on `draft` as much as on
    `expired`. An archived session is not listed at all (see below).
    """
    for state in ("draft", "validated", "ready", "expired"):
        review_session = _make_session(client, db, code=f"obs-link-{state}")
        review_session.status = state
        db.add(
            Observer(
                session_id=review_session.id,
                email="alice@example.edu",
                display_name="Alice",
            )
        )
        db.commit()
        body = client.get("/me").text
        assert (
            f'href="/me/sessions/{review_session.id}/collation"' in body
        ), state


def test_an_archived_session_leaves_me_for_every_role(
    client: TestClient, db: Session
) -> None:
    """Once archived a session is off limits to participants (author's
    ruling 2026-10-16): no row for any role, not a "Finished" one."""
    review_session = _make_session(client, db, code="arch-gone")
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Alice",
                email="alice@example.edu",
            ),
            Observer(
                session_id=review_session.id,
                email="alice@example.edu",
                display_name="Alice",
            ),
        ]
    )
    db.commit()
    assert f"/me/sessions/{review_session.id}/" in client.get("/me").text

    review_session.status = "archived"
    db.commit()
    body = client.get("/me").text
    assert f"/me/sessions/{review_session.id}/" not in body
    assert ">Finished<" not in body
    assert 'class="pill pill-role-observer"' not in body
    assert "nothing here for you right now" in body


# ── Status: the other routes to "Available", and the grant check ────


def _policy(
    db: Session,
    review_session: ReviewSession,
    *,
    audience: str,
    while_ongoing: str | None = None,
    after_release: str | None = None,
) -> Instrument:
    instrument = Instrument(session_id=review_session.id, name="F", order=1)
    db.add(instrument)
    db.flush()
    row = InstrumentViewPolicy(instrument_id=instrument.id, audience=audience)
    if while_ongoing:
        (
            row.while_ongoing_granularity,
            row.while_ongoing_identification,
        ) = visibility_policies.MODE_LABELS[while_ongoing]
    if after_release:
        (
            row.after_release_granularity,
            row.after_release_identification,
        ) = visibility_policies.MODE_LABELS[after_release]
    db.add(row)
    db.commit()
    return instrument


def _reviewer_answer(
    db: Session,
    review_session: ReviewSession,
    instrument: Instrument,
    *,
    visible: bool = True,
) -> None:
    reviewer = Reviewer(
        session_id=review_session.id, name="Alice", email="alice@example.edu"
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Bob",
        email_or_identifier="bob@example.edu",
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="comments",
        label="Comments",
        order=1,
        visible=visible,
    )
    assignment = Assignment(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
    )
    db.add_all([field, assignment])
    db.flush()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=field.id,
            value="kept",
        )
    )
    db.commit()


def test_a_reviewee_with_a_grant_reads_available(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    review_session = _make_session(client, db, code="st-reviewee")
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier="alice@example.edu",
        )
    )
    db.commit()
    grant_reviewee_visibility(review_session)
    assert AVAILABLE in client.get("/me").text


def test_an_observer_past_the_deadline_with_a_summarized_grant_reads_available(
    client: TestClient, db: Session
) -> None:
    """The while-ongoing window is the status column, not the deadline:
    a ``ready`` session past its deadline still shows Summarized
    collation."""
    review_session = _observer_on(client, db, code="st-obs-past", status="ready")
    review_session.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    _policy(db, review_session, audience="observer", while_ongoing="summarized")
    assert AVAILABLE in client.get("/me").text


def test_a_reviewer_reads_available_after_release_only_with_raw(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="st-rev-exp")
    review_session.status = "expired"
    review_session.responses_release_at = datetime.now(timezone.utc) - timedelta(
        hours=1
    )
    instrument = _policy(
        db,
        review_session,
        audience="peer_reviewer",
        while_ongoing="raw",  # that cell is raw by rule
        after_release="raw",
    )
    _reviewer_answer(db, review_session, instrument)
    assert AVAILABLE in client.get("/me").text

    # Window still open, but the after-release cell off: nothing to read.
    policy = db.execute(
        select(InstrumentViewPolicy).where(
            InstrumentViewPolicy.instrument_id == instrument.id
        )
    ).scalar_one()
    policy.after_release_granularity = None
    policy.after_release_identification = None
    db.commit()
    assert CLOSED in client.get("/me").text

    # Raw again, but the window closed.
    policy.after_release_granularity, policy.after_release_identification = (
        visibility_policies.MODE_LABELS["raw"]
    )
    review_session.responses_release_at = None
    db.commit()
    assert CLOSED in client.get("/me").text


def test_an_answer_on_a_hidden_field_does_not_make_it_available(
    client: TestClient, db: Session
) -> None:
    """The surface doesn't show it, so there is nothing to read back."""
    review_session = _make_session(client, db, code="st-rev-hidden")
    review_session.status = "ready"
    review_session.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    instrument = Instrument(session_id=review_session.id, name="F", order=1)
    db.add(instrument)
    db.flush()
    _reviewer_answer(db, review_session, instrument, visible=False)
    assert CLOSED in client.get("/me").text


def test_a_prepared_session_shows_its_scheduled_start(
    client: TestClient, db: Session
) -> None:
    review_session = _observer_on(client, db, code="st-sched", status="validated")
    review_session.scheduled_activate_at = datetime(
        2031, 3, 4, 9, 30, tzinfo=timezone.utc
    )
    db.commit()
    assert "2031-03-04 09:30" in client.get("/me").text


def test_observer_has_current_grant_follows_the_windows_and_archive(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="st-obs-grant")
    _policy(db, review_session, audience="observer", while_ongoing="summarized")
    has = visibility_policies.observer_has_current_grant

    assert not has(db, review_session)  # draft: no window open
    review_session.status = "ready"
    assert has(db, review_session)  # the while-ongoing window
    review_session.status = "expired"
    assert not has(db, review_session)  # no after-release mode, no window
    review_session.status = "archived"
    assert not has(db, review_session)  # archive closes it


# ── Notices after a redirect (participant audit M11) ────────────────


def test_me_shows_the_notice_it_was_sent_with(client: TestClient) -> None:
    body = client.get("/me?notice=summary").text
    assert "data-me-notice" in body
    assert "Your summary is available once every review is submitted." in body


def test_me_ignores_an_unknown_notice(client: TestClient) -> None:
    body = client.get("/me?notice=%3Cb%3Ehi%3C%2Fb%3E").text
    assert "data-me-notice" not in body
    assert "<b>hi</b>" not in body


def test_a_participant_sent_from_an_operator_page_is_told_why(make_client) -> None:
    from app.auth.identity import AuthenticatedUser

    pat = AuthenticatedUser(
        principal_id="pat-oid", email="pat@example.edu", name="Pat", provider="aad"
    )
    resp = make_client(pat).get("/operator/sessions")
    assert resp.status_code == 200  # followed to /me
    assert "That page is for the people who run reviews." in resp.text


# ── Participant audit L6 ─────────────────────────────────────────────


def test_rows_keep_their_order_when_a_session_is_edited(
    client: TestClient, db: Session
) -> None:
    """Rows sorted by ``updated_at``, so editing a session moved it to
    the top. They now sort newest-created first. The timestamps are set
    by hand (``func.now()`` ties within a second on SQLite and within a
    transaction on Postgres), with the older session edited last; and
    the newer one gets the lower id. So neither the old ``updated_at``
    key nor the ``id`` tiebreak alone can pass this."""
    newer = _observer_on(client, db, code="ord-newer", status="ready")
    older = _observer_on(client, db, code="ord-older", status="ready")
    assert newer.id < older.id
    older.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer.created_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    newer.updated_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    older.updated_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    db.commit()
    assert older.updated_at > newer.updated_at

    body = client.get("/me").text
    assert body.index(f"/me/sessions/{newer.id}/") < body.index(
        f"/me/sessions/{older.id}/"
    )


def test_a_utc_session_hovers_utc_once(client: TestClient, db: Session) -> None:
    """The Timezone hover read "UTC UTC" (offset label plus IANA id)."""
    _observer_on(client, db, code="tz-utc", status="ready")
    body = client.get("/me").text
    assert 'title="UTC"' in body
    assert 'title="UTC UTC"' not in body
