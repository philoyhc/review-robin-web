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
  disables the reviewer link; the session-name link falls
  through to the next role.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession


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
    client: TestClient, db: Session
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


def test_session_name_falls_through_to_reviewee_when_reviewer_not_opened(
    client: TestClient, db: Session
) -> None:
    """Reviewer + reviewee on a ``draft`` session: the reviewer
    surface is ``not opened``, so the session-name link falls
    through to ``/results``."""
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
    body = client.get("/me").text
    # Session-name link target is the reviewee surface.
    assert f'href="/me/sessions/{review_session.id}/results"' in body
    # The reviewer pill is a plain span (not opened), so no
    # reviewer anchor at all on this row.
    assert '<a class="pill pill-role-reviewer"' not in body


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


# ── Session status pill styling ──────────────────────────────────────


def test_session_status_pills_are_visibly_styled(
    client: TestClient, db: Session
) -> None:
    """Each of the three Session-status states renders as a clearly
    pill-styled span — ``open`` green, ``not opened`` light-blue,
    ``closed`` red (matching the past-deadline pill in the End
    column). Earlier renders used the muted
    ``pill-lifecycle-archived`` grey for ``closed``, which read
    as plain text on a glance.

    Uses reviewee-only rows so the non-reviewer status path
    fires (``_non_reviewer_session_status`` — pure
    ``is_ready`` / ``is_expired`` peek; no assignment fan-out
    needed)."""
    # "not opened" — fresh session, no activation (draft).
    s_draft = _make_session(client, db, code="status-draft")
    db.add(
        Reviewee(
            session_id=s_draft.id,
            name="Alice",
            email_or_identifier="alice@example.edu",
        )
    )
    # "open" — second session, lifecycle flipped to ``ready``.
    s_open = _make_session(client, db, code="status-open")
    s_open.status = "ready"
    db.add(
        Reviewee(
            session_id=s_open.id,
            name="Alice",
            email_or_identifier="alice@example.edu",
        )
    )
    # "closed" — third session, lifecycle ``expired``.
    s_closed = _make_session(client, db, code="status-closed")
    s_closed.status = "expired"
    db.add(
        Reviewee(
            session_id=s_closed.id,
            name="Alice",
            email_or_identifier="alice@example.edu",
        )
    )
    db.commit()

    body = client.get("/me").text
    assert '<span class="pill pill-info">not opened</span>' in body
    assert '<span class="pill pill-success">open</span>' in body
    assert '<span class="pill pill-error">closed</span>' in body
    # The earlier muted-grey treatment retired — the regression
    # guard pins the new prominent treatment. The CSS rule for
    # ``.pill-lifecycle-archived`` still ships in base.html for
    # other surfaces (e.g. the operator archive lobby), so the
    # check looks for the class on a rendered element rather
    # than its mere presence in the stylesheet.
    assert 'class="pill pill-lifecycle-archived"' not in body
