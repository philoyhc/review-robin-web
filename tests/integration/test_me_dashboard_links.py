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
- ``session_status == "not opened"`` (draft / validated / archived
  session) disables the reviewer link; the session-name link falls
  through to the next role.
- The status pill reads Not open yet / Open / Available / Closed /
  Finished, one rule for every role (participant audit M6).
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
FINISHED = _pill("pill-lifecycle-archived", "Finished")


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
    """Not open yet / Open / Closed / Finished from the lifecycle, one
    rule for every role (author's ruling 2026-10-15). Observer-only rows,
    with no observer grant, so "Closed" is not lifted to "Available"."""
    for code, status, pill in (
        ("st-draft", "draft", NOT_OPEN_YET),
        ("st-validated", "validated", NOT_OPEN_YET),
        ("st-ready", "ready", OPEN),
        ("st-expired", "expired", CLOSED),
        ("st-archived", "archived", FINISHED),
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
    `expired`. Archive is the exception: it closes every non-operator
    grant, so `/collation` there is empty by construction and a live
    link to it is a dead end.
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


def test_an_archived_session_keeps_the_observer_row_but_drops_its_link(
    client: TestClient, db: Session
) -> None:
    """The row stays — the author declined to filter archived sessions
    off `/me` for reviewers and observers, so they read "Finished" until
    the session is deleted. Only the link goes."""
    review_session = _make_session(client, db, code="obs-link-arch")
    db.add(
        Observer(
            session_id=review_session.id,
            email="alice@example.edu",
            display_name="Alice",
        )
    )
    db.commit()
    assert (
        f'href="/me/sessions/{review_session.id}/collation"'
        in client.get("/me").text
    )

    review_session.status = "archived"
    db.commit()
    body = client.get("/me").text
    # Row survives...
    assert 'class="pill pill-role-observer"' in body
    assert FINISHED in body
    # ...without its link.
    assert f'href="/me/sessions/{review_session.id}/collation"' not in body


def test_only_an_archived_session_reads_finished(
    client: TestClient, db: Session
) -> None:
    """"Finished" replaced 19G.9's "not opened" plus an "archived"
    companion pill: a draft is not open *yet*, an archived session is
    done, and the one label now says which."""
    for state in ("draft", "validated", "ready", "expired"):
        _observer_on(client, db, code=f"fin-none-{state}", status=state)
        assert FINISHED not in client.get("/me").text, state
        db.execute(
            Observer.__table__.delete().where(
                Observer.email == "alice@example.edu"
            )
        )
        db.commit()


def test_an_archived_row_is_not_linked_for_any_role(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="arch-nolink")
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
    review_session.status = "archived"
    db.commit()
    body = client.get("/me").text
    assert FINISHED in body
    assert f'href="/me/sessions/{review_session.id}' not in body
