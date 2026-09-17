"""What a roster delete costs in relationships, counted and logged.

19O.5 rung 1. `relationships.reviewer_id` / `reviewee_id` are declared
`ondelete="CASCADE"` and `app/db/session.py` sets
`PRAGMA foreign_keys = ON`, so emptying either roster empties the
Relationships roster too — on both dialects, and **without SQLAlchemy
ever seeing it happen**: there is no ORM collection on either parent,
so no `delete-orphan` fires and no service is told.

That is why the count is taken *before* the delete. A count afterwards
reads 0 every time, which is precisely the shape of bug that let the
audit log undercount this loss since the cascade was declared.

**This rung deliberately changes no copy.** The count is wired into the
page context and the audit payload; the confirmations that will name it
land at rung 2. The last test here pins that, so "rung 1 was inert on
the visible surface" is a checked claim rather than an intention.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Observer,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import roster_bulk


def _mk(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "R", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    rs.relationships_enabled = True
    rs.observers_enabled = True
    db.commit()
    db.refresh(rs)
    return rs


def _seed(db: Session, sid: int, *, pairs: int = 3):
    """`pairs` reviewers, `pairs` reviewees, and one relationship each."""
    reviewers = [
        Reviewer(session_id=sid, name=f"R{i}", email=f"r{i}@example.org")
        for i in range(pairs)
    ]
    reviewees = [
        Reviewee(
            session_id=sid,
            name=f"E{i}",
            email_or_identifier=f"e{i}@example.org",
        )
        for i in range(pairs)
    ]
    db.add_all(reviewers + reviewees)
    db.commit()
    for row in reviewers + reviewees:
        db.refresh(row)
    db.add_all(
        [
            Relationship(
                session_id=sid,
                reviewer_id=reviewers[i].id,
                reviewee_id=reviewees[i].id,
            )
            for i in range(pairs)
        ]
    )
    db.commit()
    return reviewers, reviewees


def _counts(db: Session, sid: int, event_type: str) -> dict:
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == sid,
            AuditEvent.event_type == event_type,
        )
    ).scalar_one()
    return event.detail["counts"]


def _relationships(db: Session, sid: int) -> int:
    return len(
        db.execute(
            select(Relationship).where(Relationship.session_id == sid)
        ).scalars().all()
    )


# ── The counter itself ─────────────────────────────────────────────────


def test_the_counter_answers_per_model_and_per_row(
    client: TestClient, db: Session
) -> None:
    """Three models, three answers, and only two of them are non-zero.

    `Observer` and `Relationship` are absent from the FK map — nothing
    references an observer, and a relationship delete reaches no other
    relationship — so both count 0 rather than raising.
    """
    rs = _mk(client, db, "relcc-1")
    reviewers, reviewees = _seed(db, rs.id)

    assert roster_bulk.relationship_cascade_count(
        db, model=Reviewer, ids=[reviewers[0].id]
    ) == 1
    assert roster_bulk.relationship_cascade_count(
        db, model=Reviewer, ids=[r.id for r in reviewers]
    ) == 3
    assert roster_bulk.relationship_cascade_count(
        db, model=Reviewee, ids=[reviewees[0].id]
    ) == 1
    assert roster_bulk.relationship_cascade_count(
        db, model=Observer, ids=[1, 2, 3]
    ) == 0
    # An empty selection. **This one is behaviour-preserving**: the
    # `not ids` short-circuit mirrors `cascade_counts`' and saves a
    # query, but `column.in_([])` already answers 0, so removing the
    # guard passes this assertion. Mutation-checked and recorded rather
    # than dressed up as a behavioural claim — the reason to keep the
    # line is symmetry with its sibling, which is a source fact.
    assert roster_bulk.relationship_cascade_count(
        db, model=Reviewer, ids=[]
    ) == 0


def test_the_count_must_be_taken_before_the_delete(
    client: TestClient, db: Session
) -> None:
    """The reason the counter is a separate call rather than something
    the delete reports: afterwards there is nothing left to count.

    This is the bug's actual shape, pinned so a later refactor that
    moves the call below `db.delete` fails here instead of silently
    logging zeros.
    """
    rs = _mk(client, db, "relcc-2")
    reviewers, _ = _seed(db, rs.id)
    ids = [r.id for r in reviewers]

    before = roster_bulk.relationship_cascade_count(
        db, model=Reviewer, ids=ids
    )
    client.post(
        f"/operator/sessions/{rs.id}/reviewers/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    db.expire_all()
    after = roster_bulk.relationship_cascade_count(db, model=Reviewer, ids=ids)

    assert before == 3
    assert after == 0, "the rows are gone; counting later cannot work"


# ── The audit payload ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "page,event_type",
    [
        ("reviewers", "reviewers.deleted_all"),
        ("reviewees", "reviewees.deleted_all"),
    ],
)
def test_delete_all_logs_the_relationships_it_destroyed(
    client: TestClient, db: Session, page: str, event_type: str
) -> None:
    rs = _mk(client, db, f"relcc-da-{page[:4]}")
    _seed(db, rs.id)

    response = client.post(
        f"/operator/sessions/{rs.id}/{page}/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.expire_all()

    assert _relationships(db, rs.id) == 0, "seed is vacuous"
    assert _counts(db, rs.id, event_type)["cascaded_relationships"] == 3


@pytest.mark.parametrize(
    "page,field,event_type",
    [
        ("reviewers", "reviewer_ids", "reviewer.bulk_deleted"),
        ("reviewees", "reviewee_ids", "reviewee.bulk_deleted"),
    ],
)
def test_bulk_delete_logs_only_the_selection_s_relationships(
    client: TestClient, db: Session, page: str, field: str, event_type: str
) -> None:
    """The selection's, not the session's — the same distinction
    `cascaded_assignments` already draws on this route."""
    rs = _mk(client, db, f"relcc-bd-{page[:4]}")
    reviewers, reviewees = _seed(db, rs.id)
    one = (reviewers if page == "reviewers" else reviewees)[0]

    response = client.post(
        f"/operator/sessions/{rs.id}/{page}/bulk-delete",
        data={field: [str(one.id)], "confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.expire_all()

    assert _relationships(db, rs.id) == 2, "one pair went, not all three"
    assert _counts(db, rs.id, event_type)["cascaded_relationships"] == 1


def test_observers_events_keep_the_payload_they_had(
    client: TestClient, db: Session
) -> None:
    """Omitted, not zero. Nothing references `observers`, so a key
    reading 0 would describe a cascade that cannot exist — the same
    reason their delete confirmation never mentions assignments.
    """
    rs = _mk(client, db, "relcc-obs")
    _seed(db, rs.id)
    db.add(
        Observer(session_id=rs.id, email="o@example.org", display_name="O")
    )
    db.commit()

    client.post(
        f"/operator/sessions/{rs.id}/observers/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    db.expire_all()

    counts = _counts(db, rs.id, "observers.deleted_all")
    assert "cascaded_relationships" not in counts, counts
    assert _relationships(db, rs.id) == 3, "an observer delete reaches none"


def test_the_envelope_admits_the_field_without_a_schema_edit(
    client: TestClient, db: Session
) -> None:
    """`EVENT_SCHEMAS` declares `{"counts"}` for these event types and
    `audit.counts(**values)` takes arbitrary keys, so no registration
    was needed — **verified, not assumed**, because strict mode fails
    the write rather than the read and a passing suite elsewhere would
    not distinguish "admitted" from "never exercised".
    """
    rs = _mk(client, db, "relcc-env")
    _seed(db, rs.id)
    client.post(
        f"/operator/sessions/{rs.id}/reviewers/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    db.expire_all()
    # A rejected envelope writes no row in strict mode.
    assert _counts(db, rs.id, "reviewers.deleted_all") == {
        "deleted": 3,
        "cascaded_assignments": 0,
        "cascaded_relationships": 3,
    }


# ── The page context, and the copy that has NOT moved ──────────────────


@pytest.mark.parametrize("page", ["reviewers", "reviewees"])
def test_the_page_carries_the_count_on_every_render_path(
    client: TestClient, db: Session, page: str
) -> None:
    """Both the plain GET and the failed-import 400, which builds its
    own context. An absent key would raise in rung 2's confirmation
    rather than degrade quietly — the trap 19P.1 and 19P.3 both hit on
    this handler, so it is pinned before there is anything to break.
    """
    rs = _mk(client, db, f"relcc-ctx-{page[:4]}")
    _seed(db, rs.id)

    from app.web.routes_operator import _setup_reviewees, _setup_reviewers
    from app.web.routes_operator import _shared

    page_module = _setup_reviewers if page == "reviewers" else _setup_reviewees
    # The 400 re-render is `_shared._handle_import`'s, and it renders
    # through `_shared`'s own templates object — patching the page
    # module's would capture the GET and silently miss the path this
    # test exists for.
    captured: dict = {}
    patched = []

    def _wrap(module):
        original = module._templates.TemplateResponse

        def _capture(request, name, context, *args, **kwargs):
            captured.update(context)
            return original(request, name, context, *args, **kwargs)

        module._templates.TemplateResponse = _capture  # type: ignore[assignment]
        patched.append((module, original))

    _wrap(page_module)
    if _shared is not page_module:
        _wrap(_shared)
    try:
        client.get(f"/operator/sessions/{rs.id}/{page}")
        assert captured.get("relationship_count") == 3, sorted(captured)

        captured.clear()
        response = client.post(
            f"/operator/sessions/{rs.id}/{page}/import",
            files={"file": ("r.csv", b"NotAColumn\nx\n", "text/csv")},
        )
        assert response.status_code == 400, response.status_code
        assert captured, "the 400 rendered through neither templates object"
        assert captured.get("relationship_count") == 3, sorted(captured)
    finally:
        for module, original in patched:
            module._templates.TemplateResponse = original  # type: ignore[assignment]


@pytest.mark.parametrize("page", ["reviewers", "reviewees"])
def test_rung_one_changes_no_copy(
    client: TestClient, db: Session, page: str
) -> None:
    """**The inertness claim, checked.** Rung 1 lands the number and
    nothing that reads it, so no confirmation on either page may
    mention relationships yet.

    Rung 2 flips this test rather than deleting it: the same three
    confirmations are where the clause belongs, so a failure here after
    rung 2 means the copy landed somewhere else.
    """
    rs = _mk(client, db, f"relcc-copy-{page[:4]}")
    _seed(db, rs.id)
    body = client.get(f"/operator/sessions/{rs.id}/{page}?unlocked=1").text
    body = re.sub(r"<style\b.*?</style>", "", body, flags=re.S)

    labels = re.findall(
        r'<label class="confirm-label[^"]*">(.*?)</label>', body, re.S
    ) + re.findall(r'"(Yes, delete these[^"]*)"', body)
    assert labels, "no confirmations on the page — the seed is vacuous"
    for label in labels:
        assert "relationship" not in label.lower(), (
            "rung 1 is meant to be inert on the visible surface; this "
            "clause belongs to rung 2"
        )
