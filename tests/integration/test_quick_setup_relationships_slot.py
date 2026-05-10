"""Integration coverage for Segment 15D PR 7c — Quick Setup
Relationships slot.

PR 7c re-introduces a slot at position 3 carrying Relationships
(file-upload mode) after PR 7a retired the legacy
Assignments-with-rule slot. Generation is no longer driven from
Quick Setup — it's an explicit operator action on the Operations
Assignments page (PR 6a).
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Relationship, ReviewSession
from app.web import views


REVIEWER_CSV = b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n"
REVIEWEE_CSV = b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n"
RELATIONSHIP_CSV = (
    b"ReviewerEmail,RevieweeEmail,PairContextTag1\n"
    b"alice@example.edu,carol@example.edu,Mentor\n"
)


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "QSRel", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_rosters(client: TestClient, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/quick-setup/reviewers",
        files={"file": ("r.csv", REVIEWER_CSV, "text/csv")},
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/quick-setup/reviewees",
        files={"file": ("e.csv", REVIEWEE_CSV, "text/csv")},
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# View-shape tests
# ---------------------------------------------------------------------------


def test_quick_setup_relationships_slot_is_wired_live(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qsrel-live")
    context = views.build_quick_setup_context(db, review_session)
    by_key = {slot.key: slot for slot in context.slots}

    assert by_key["relationships"].is_wired is True
    assert by_key["relationships"].mode == "file_upload"
    assert by_key["relationships"].wire_url == (
        f"/operator/sessions/{review_session.id}/quick-setup/relationships"
    )
    assert by_key["relationships"].coming_in is None


def test_quick_setup_relationships_slot_count_reflects_population(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qsrel-count")
    _seed_rosters(client, review_session.id)
    context_empty = views.build_quick_setup_context(db, review_session)
    by_key = {slot.key: slot for slot in context_empty.slots}
    assert by_key["relationships"].count == 0

    client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/relationships",
        files={"file": ("rel.csv", RELATIONSHIP_CSV, "text/csv")},
        follow_redirects=False,
    )
    context_after = views.build_quick_setup_context(db, review_session)
    by_key_after = {slot.key: slot for slot in context_after.slots}
    assert by_key_after["relationships"].count == 1


# ---------------------------------------------------------------------------
# Per-slot route
# ---------------------------------------------------------------------------


def test_quick_setup_relationships_route_imports_rows(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qsrel-route")
    _seed_rosters(client, review_session.id)

    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/relationships",
        files={"file": ("rel.csv", RELATIONSHIP_CSV, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("#quick-setup-relationships")

    rows = db.execute(
        select(Relationship).where(
            Relationship.session_id == review_session.id
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].tag_1 == "Mentor"


def test_quick_setup_relationships_route_replace_requires_confirm(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qsrel-confirm")
    _seed_rosters(client, review_session.id)

    # First upload populates.
    client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/relationships",
        files={"file": ("rel.csv", RELATIONSHIP_CSV, "text/csv")},
        follow_redirects=False,
    )
    # Second upload without confirm should redirect with needs_confirm.
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/relationships",
        files={"file": ("rel.csv", RELATIONSHIP_CSV, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "quick_setup_error=relationships" in location
    assert "quick_setup_reason=needs_confirm" in location


def test_quick_setup_relationships_route_unknown_email_is_parse_error(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qsrel-parse")
    _seed_rosters(client, review_session.id)

    bad_csv = (
        b"ReviewerEmail,RevieweeEmail\n"
        b"ghost@example.edu,carol@example.edu\n"
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/relationships",
        files={"file": ("rel.csv", bad_csv, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "quick_setup_error=relationships" in location
    assert "quick_setup_reason=parse" in location


def test_quick_setup_relationships_lifecycle_gate_on_ready(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """An Activated session rejects relationships uploads with the
    ``lifecycle`` reason token."""

    from app.db.models import ReviewSession as RS
    from app.services import session_lifecycle as lifecycle

    operator = make_client(alice)
    operator.post(
        "/operator/sessions",
        data={"name": "Locked", "code": "qsrel-lifecycle"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(RS).where(RS.code == "qsrel-lifecycle")
    ).scalar_one()
    review_session.status = lifecycle.SessionStatus.ready.value
    db.commit()

    response = operator.post(
        f"/operator/sessions/{review_session.id}/quick-setup/relationships",
        files={"file": ("rel.csv", RELATIONSHIP_CSV, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "quick_setup_reason=lifecycle" in response.headers["location"]


# ---------------------------------------------------------------------------
# Submit-all chain
# ---------------------------------------------------------------------------


def test_submit_all_runs_relationships_after_rosters(
    client: TestClient, db: Session
) -> None:
    """Chain order: reviewers → reviewees → relationships. A
    submit-all POST with all three files runs them in sequence."""

    review_session = _make_session(client, db, code="qsrel-chain")

    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/submit-all",
        files={
            "reviewers_file": ("r.csv", REVIEWER_CSV, "text/csv"),
            "reviewees_file": ("e.csv", REVIEWEE_CSV, "text/csv"),
            "relationships_file": (
                "rel.csv",
                RELATIONSHIP_CSV,
                "text/csv",
            ),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    # Last fragment is the relationships slot since it's the final
    # step in the chain.
    assert response.headers["location"].endswith(
        "#quick-setup-relationships"
    )

    rows = db.execute(
        select(Relationship).where(
            Relationship.session_id == review_session.id
        )
    ).scalars().all()
    assert len(rows) == 1


def test_create_session_with_relationships_file_processes_upload(
    client: TestClient, db: Session
) -> None:
    """POST /operator/sessions with reviewers + reviewees +
    relationships files dispatches all three through the same
    pipeline."""

    response = client.post(
        "/operator/sessions",
        data={
            "name": "NewQSRel",
            "code": "qsrel-newsess",
            "description": "d",
        },
        files={
            "reviewers_file": ("r.csv", REVIEWER_CSV, "text/csv"),
            "reviewees_file": ("e.csv", REVIEWEE_CSV, "text/csv"),
            "relationships_file": (
                "rel.csv",
                RELATIONSHIP_CSV,
                "text/csv",
            ),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "qsrel-newsess")
    ).scalar_one()
    rows = db.execute(
        select(Relationship).where(
            Relationship.session_id == review_session.id
        )
    ).scalars().all()
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Card markup
# ---------------------------------------------------------------------------


def test_quick_setup_card_renders_relationships_slot_section(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qsrel-render")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    assert 'id="quick-setup-relationships"' in body
    # Active label on the slot heading.
    assert ">Relationships" in body
    # File-upload control points at the per-slot route.
    assert 'name="relationships_file"' in body


def test_quick_setup_relationships_slot_renders_disabled_on_new_session_inert(
    client: TestClient,
) -> None:
    """The ``/operator/sessions/new`` Quick Setup variant renders
    every slot wired (when called with db + user). The slot order
    includes Relationships at position 3."""

    body = client.get("/operator/sessions/new").text
    # Slot fragment present + Relationships heading rendered.
    assert 'id="quick-setup-relationships"' in body
    rel_pos = body.find('id="quick-setup-relationships"')
    reviewees_pos = body.find('id="quick-setup-reviewees"')
    settings_pos = body.find('id="quick-setup-settings"')
    assert reviewees_pos < rel_pos < settings_pos
