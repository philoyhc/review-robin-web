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

**This rung changes no copy on the roster pages**, which is narrower
than the claim it first carried. The confirmations that will name the
loss land at rung 2, and `test_rung_one_changes_no_copy` pins that.

It is *not* inert everywhere, and a cold read caught the overstatement:
`app/web/views/_audit_log.py` renders a `counts` envelope by iterating
every key and using the raw key as the label, so the Sys-admin audit log
gains a `cascaded_relationships` row on the six events below from this
rung onward. That is intended — the field is the point — but it is a new
user-visible string, so it is named here and pinned by
`test_the_audit_log_page_shows_the_new_count` rather than left to a
claim of inertness that reading the diff would disprove.
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
    User,
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
    # Real ids for both, so a mutation adding either model to the map
    # would be caught. Ids that match no row would make this pass by
    # accident rather than by rule.
    observer = Observer(
        session_id=rs.id, email="o@example.org", display_name="O"
    )
    db.add(observer)
    db.commit()
    db.refresh(observer)
    every_relationship = [
        r.id
        for r in db.execute(
            select(Relationship).where(Relationship.session_id == rs.id)
        ).scalars()
    ]
    assert roster_bulk.relationship_cascade_count(
        db, model=Observer, ids=[observer.id]
    ) == 0
    assert roster_bulk.relationship_cascade_count(
        db, model=Relationship, ids=every_relationship
    ) == 0, "a relationship delete reaches no other relationship"
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


@pytest.mark.parametrize(
    "page,header,event_type",
    [
        ("reviewers", b"ReviewerName,ReviewerEmail", "reviewers.imported"),
        ("reviewees", b"RevieweeName,RevieweeEmail", "reviewees.imported"),
    ],
)
def test_a_csv_replace_logs_the_relationships_it_destroyed(
    client: TestClient, db: Session, page: str, header: bytes, event_type: str
) -> None:
    """The path an operator actually takes, and the one rung 1 first
    left out. A replace deletes every existing row and re-adds, so it
    takes the relationships through the same FK cascade as `delete-all`.

    Rung 2 will quote a number on this confirmation; without this the
    log would have had no counterpart for it, which is the exact
    disagreement the item's Decision argues against.
    """
    rs = _mk(client, db, f"relcc-imp-{page[:4]}")
    _seed(db, rs.id)

    response = client.post(
        f"/operator/sessions/{rs.id}/{page}/import",
        files={"file": ("r.csv", header + b"\nNew,new@example.org\n",
                        "text/csv")},
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.expire_all()

    assert _relationships(db, rs.id) == 0, "seed is vacuous"
    assert _counts(db, rs.id, event_type)["cascaded_relationships"] == 3


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


@pytest.mark.parametrize(
    "page,field,event_type",
    [
        ("observers", "observer_ids", "observer.bulk_deleted"),
        ("relationships", "relationship_ids", "relationship.bulk_deleted"),
    ],
)
def test_bulk_delete_omits_the_key_for_the_models_that_reach_nothing(
    client: TestClient, db: Session, page: str, field: str, event_type: str
) -> None:
    """The `bulk_delete` half of the omitted-not-zero rule, which the
    first version of this file left untested: only `delete-all` had it,
    so a regression emitting `cascaded_relationships: 0` on these two
    would have passed the whole suite.
    """
    rs = _mk(client, db, f"relcc-om-{page[:4]}")
    _seed(db, rs.id)
    if page == "observers":
        row = Observer(
            session_id=rs.id, email="o@example.org", display_name="O"
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        row_id = row.id
    else:
        row_id = db.execute(
            select(Relationship).where(Relationship.session_id == rs.id)
        ).scalars().first().id

    response = client.post(
        f"/operator/sessions/{rs.id}/{page}/bulk-delete",
        data={field: [str(row_id)], "confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.expire_all()

    counts = _counts(db, rs.id, event_type)
    assert "cascaded_relationships" not in counts, counts


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
def test_every_render_path_already_reaches_the_count(
    client: TestClient, db: Session, page: str
) -> None:
    """Rung 2 needs the number in the template, and **it is already
    there** — `views.session_status_pills` carries `relationship_count`
    from the same `relationships_service.existing_count` call, and every
    path these pages render through already puts `status_pills` in its
    context, including the failed-import 400 that builds its own.

    The first version of this rung added a second top-level key holding
    the same number from a second query on all three paths. A cold read
    caught it: `spec/architecture.md`'s fourth seam puts this shape in
    `app/web/views/`, the view adapter already owns it, and a value
    computed twice is a value that can disagree with itself — which is
    the argument this very item makes about the audit log. The keys are
    gone; rung 2 reads `status_pills.relationship_count`.

    Pinned here because "already there" is what rung 2 depends on, and
    the 400 path is where it would be missing if anywhere.
    """
    rs = _mk(client, db, f"relcc-ctx-{page[:4]}")
    _seed(db, rs.id)

    # One object, not three: `_setup_reviewers` and `_setup_reviewees`
    # both import `_templates` FROM `_shared`, so patching per module
    # would wrap the same object twice and restore it to a wrapper.
    from app.web.routes_operator import _shared

    assert _shared._templates is __import__(
        "app.web.routes_operator._setup_" + page, fromlist=["_templates"]
    )._templates, "the page module no longer shares _shared's templates"

    captured: list[dict] = []
    original = _shared._templates.TemplateResponse

    def _capture(request, name, context, *args, **kwargs):
        captured.append(context)
        return original(request, name, context, *args, **kwargs)

    _shared._templates.TemplateResponse = _capture  # type: ignore[assignment]
    try:
        client.get(f"/operator/sessions/{rs.id}/{page}")
        response = client.post(
            f"/operator/sessions/{rs.id}/{page}/import",
            files={"file": ("r.csv", b"NotAColumn\nx\n", "text/csv")},
        )
        assert response.status_code == 400, response.status_code
    finally:
        # `del` rather than reassignment: `original` is the bound method
        # off the class, so assigning it back would leave a permanent
        # instance attribute shadowing it on a shared object.
        del _shared._templates.TemplateResponse

    assert "TemplateResponse" not in _shared._templates.__dict__, (
        "the patch leaked onto an object every later test renders through"
    )
    assert len(captured) >= 2, "expected the GET and the 400 to render"
    for context in captured:
        assert context["status_pills"].relationship_count == 3, sorted(context)


def test_the_audit_log_page_shows_the_new_count(
    client: TestClient, db: Session
) -> None:
    """The one surface this rung DOES change for a reader.

    `format_audit_detail` renders a `counts` envelope by iterating every
    key with the raw key as its label, so the new field appears on the
    Sys-admin audit log the moment it is written — no template change,
    no opt-in. Intended, and pinned here so "rung 1 touches no visible
    surface" is not claimed anywhere it would be false.
    """
    rs = _mk(client, db, "relcc-log")
    _seed(db, rs.id)
    client.post(
        f"/operator/sessions/{rs.id}/reviewers/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    # The page is behind `require_sys_admin`, which reads the column on
    # the user row rather than the settings list.
    signed_in = db.execute(select(User).order_by(User.id)).scalars().first()
    signed_in.is_sys_admin = True
    db.commit()

    response = client.get(f"/operator/sys-admin/sessions/{rs.id}/audit-log")
    assert response.status_code == 200, response.status_code

    # The rendered `<dt>` inside the Counts section, NOT the raw-JSON
    # expander below it — that carries the whole detail verbatim, so a
    # bare substring search passes with the Counts section deleted.
    # Mutation-checked: removing the section leaves the string in place.
    body = response.text
    section = body[body.index("Counts") : body.index("Counts") + 2000]
    assert "<dt>cascaded_relationships</dt>" in section, section[:400]


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

    # Keyed on `data-delete-confirm`, not on label markup: the
    # JS-built confirmation is a string inside a <script>, so a
    # label-shaped regex matches it twice — once as markup and once as
    # the literal it builds — and a naive count reads 4 for 3 gates.
    keys = set(re.findall(r'data-delete-confirm="([^"]+)"', body))
    assert keys == {"delete-all", "replace-roster", f"{page}-bulk-delete"}, keys

    # The text each gate carries, wherever it is written.
    phrases = [
        " ".join(re.sub(r"<[^>]+>", " ", m).split())
        for m in re.findall(
            r'(?:Yes, delete the existing|Yes, replace the existing|'
            r'Yes, delete these)[^<"]*', body
        )
    ]
    assert len(phrases) >= 3, phrases
    for phrase in phrases:
        assert "relationship" not in phrase.lower(), (
            "rung 1 is meant to be inert on these pages; this clause "
            "belongs to rung 2"
        )