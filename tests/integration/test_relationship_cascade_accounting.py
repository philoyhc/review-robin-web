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
    Assignment,
    AuditEvent,
    Instrument,
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
def test_every_confirmation_names_the_relationship_loss(
    client: TestClient, db: Session, page: str
) -> None:
    """**Rung 2 flips rung 1's inertness test rather than deleting it.**
    The three gates per page are the same three; what changed is which
    way the assertion points, so a clause landing anywhere else fails
    here.

    Keyed on `data-delete-confirm`, not on label markup: the JS-built
    confirmation is a string inside a `<script>`, so a label-shaped
    regex matches it twice — once as markup, once as the literal it
    builds — and a naive count reads 4 for 3 gates.
    """
    rs = _mk(client, db, f"relcc-copy-{page[:4]}")
    _seed(db, rs.id)
    body = client.get(f"/operator/sessions/{rs.id}/{page}?unlocked=1").text
    body = re.sub(r"<style\b.*?</style>", "", body, flags=re.S)

    keys = set(re.findall(r'data-delete-confirm="([^"]+)"', body))
    assert keys == {"delete-all", "replace-roster", f"{page}-bulk-delete"}, keys

    flat = " ".join(re.sub(r"<[^>]+>", " ", body).split())

    # **The two numbered gates use different verbs, and the cold read
    # found out why.** The Danger Zone opens "delete the existing N
    # reviewers", which governs the clause. The Upload card opens
    # "replace the existing N reviewers" — which does NOT: the
    # relationships are destroyed and nothing re-creates them, so
    # inheriting `replace` told the operator a roster would come back.
    #
    # This fixture seeds NO assignments, which is the state that was
    # wrong: `delete` is introduced by the assignment clause when there
    # is one, so with none the replace sentence had no verb of its own.
    # The first version of this test asserted a count of the shared
    # phrase and passed on the defective sentence.
    noun = page[:-1]
    assert (
        f"delete the existing 3 {noun}s and the 3 relationships "
        "involving them." in flat
    ), flat[:400]
    assert (
        f"replace the existing 3 {noun}s and delete the 3 "
        "relationships involving them." in flat
    ), flat[:400]

    # The expander's clause is numberless and selection-summed.
    assert '" and the relationships involving them"' in " ".join(body.split())


@pytest.mark.parametrize("page", ["reviewers", "reviewees"])
def test_a_roster_with_no_relationships_reads_exactly_as_before(
    client: TestClient, db: Session, page: str
) -> None:
    """The zero case, pinned byte-identical.

    `Semantics` makes this a contract, not a nicety: the three-state
    rule exists because a label naming a loss that cannot happen is its
    own defect, so a session with no relationships — including every
    session with `relationships_enabled` off — must read exactly as it
    did before this item.
    """
    rs = _mk(client, db, f"relcc-zero-{page[:4]}")
    # Rosters, but no relationships between them.
    db.add_all(
        [Reviewer(session_id=rs.id, name="R", email="r@example.org"),
         Reviewee(session_id=rs.id, name="E",
                  email_or_identifier="e@example.org")]
    )
    db.commit()

    body = client.get(f"/operator/sessions/{rs.id}/{page}?unlocked=1").text
    flat = " ".join(re.sub(r"<style\b.*?</style>", "", body, flags=re.S).split())

    # The confirmation SENTENCES, not the page: the chrome carries a
    # `Relationships` nav tab and a status pill on every roster page, so
    # an unscoped search reports a mention that was always there.
    phrases = re.findall(
        r"(?:Yes, delete the existing|Yes, replace the existing)[^.]*",
        re.sub(r"<[^>]+>", " ", flat),
    )
    assert len(phrases) == 2, phrases
    for phrase in phrases:
        assert "relationship" not in phrase.lower(), phrase
    # The clause is still COMPILED into the expander's script — it is
    # summed at click time, not rendered away — so its absence from the
    # sentence is the script's decision, not the server's.
    assert '" and the relationships involving them"' in flat
    assert 'data-relationships="0"' in flat


@pytest.mark.parametrize("page,noun", [("reviewers", "reviewer"),
                                       ("reviewees", "reviewee")])
def test_each_row_carries_the_relationships_it_would_take(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """The numbers the expander sums, checked per row.

    Seeded unevenly on purpose: a roster where every row carried the
    same count would pass with the map keyed wrongly, or replaced by a
    constant.
    """
    rs = _mk(client, db, f"relcc-rows-{page[:4]}")
    reviewers, reviewees = _seed(db, rs.id, pairs=2)
    # A third pair hanging off the FIRST row of each roster, so row 0
    # carries 2 and row 1 carries 1.
    db.add(
        Relationship(
            session_id=rs.id,
            reviewer_id=reviewers[0].id,
            reviewee_id=reviewees[1].id,
        )
    )
    db.commit()

    body = client.get(f"/operator/sessions/{rs.id}/{page}").text
    rows = (reviewers if page == "reviewers" else reviewees)
    found = {}
    for row in rows:
        m = re.search(
            rf'id="{noun}-row-{row.id}".*?data-relationships="(\d+)"',
            body, re.S,
        )
        assert m, f"row {row.id} carries no count"
        found[row.id] = int(m.group(1))
    assert sorted(found.values()) == [1, 2], found


@pytest.mark.parametrize("page", ["reviewers", "reviewees"])
def test_the_expander_clause_is_gated_on_the_selection_not_the_roster(
    client: TestClient, db: Session, page: str
) -> None:
    """**A source assertion, and the reason is worth stating.**

    The clause is appended by a script from the ticked rows'
    `data-relationships`, so what a server-side test can see is that the
    expression ships — not that it evaluates. Mutating the condition to
    `true` or `false` passes every other test in this file, which is how
    this gap was found.

    Measured instead in headless Chromium against a local dev server in
    the agent's container — **not** the Azure dev slot, which is still
    the verification of record (`CLAUDE.md`, "Where work runs"). On a
    roster where row A carries two pairs, row B one and row C none:

        C alone   -> "Yes, delete these"
        B alone   -> "Yes, delete these and the relationships between them"
        A + C     -> "Yes, delete these and the relationships between them"

    So a selection touching no pair stays silent, which is the
    behaviour `Semantics` asks for and the reason this clause reads the
    selection where its three neighbours read the session.
    """
    rs = _mk(client, db, f"relcc-src-{page[:4]}")
    _seed(db, rs.id)
    body = client.get(f"/operator/sessions/{rs.id}/{page}").text

    assert "relationshipsIn(sel) > 0" in body, (
        "the clause no longer reads the selection"
    )
    assert "parseInt(row.dataset.relationships, 10) || 0" in body, (
        "the summing helper is gone or no longer defaults a missing "
        "attribute to 0"
    )


@pytest.mark.parametrize("page", ["reviewers", "reviewees"])
def test_the_replace_verb_is_not_repeated_when_assignments_exist(
    client: TestClient, db: Session, page: str
) -> None:
    """The other half of the verb rule.

    With assignments, the sentence already says "and delete the N
    assignments", and that `delete` governs everything after it — so
    this clause must NOT supply a second one. With none, it must (the
    case the cold read caught). One conditional, both states pinned.
    """
    rs = _mk(client, db, f"relcc-verb-{page[:4]}")
    reviewers, reviewees = _seed(db, rs.id)
    instrument = Instrument(session_id=rs.id, name="I", order=0)
    db.add(instrument)
    db.flush()
    db.add(
        Assignment(
            session_id=rs.id,
            reviewer_id=reviewers[0].id,
            reviewee_id=reviewees[0].id,
            instrument_id=instrument.id,
            include=True,
            created_by_mode="rule_based",
        )
    )
    db.commit()

    body = client.get(f"/operator/sessions/{rs.id}/{page}?unlocked=1").text
    flat = " ".join(re.sub(r"<[^>]+>", " ", body).split())

    assert (
        "and delete the 1 assignment and the 3 relationships involving "
        "them." in flat
    ), flat[:500]
    assert "and delete the 3 relationships" not in flat, (
        "the verb is repeated where the assignment clause already "
        "introduced it"
    )


# ── Rung 3: the prose that explains the cost before it is incurred ────


def test_the_guide_tells_operators_what_order_to_work_in(
    client: TestClient, db: Session
) -> None:
    """The confirmations name the cost at the moment it is about to be
    paid; the Guide is where an operator learns to avoid paying it.

    Its `Optional: relationships and observers` section was two
    sentences about turning the features on and said nothing about the
    dependency — so the only way to discover that a roster re-upload
    empties this one was to do it.
    """
    rs = _mk(client, db, "relcc-guide")
    body = client.get(
        f"/guide?return_to=/operator/sessions/{rs.id}/relationships"
    ).text
    section = body[body.index("Optional: relationships and observers"):]
    section = " ".join(re.sub(r"<[^>]+>", " ", section[:2000]).split())

    assert "after the reviewer and reviewee rosters" in section, section[:400]
    # The two paths, scoped differently, and the one that costs nothing.
    assert "replacing a roster deletes every relationship in the session" in section
    assert "deleting rows takes the relationships that involved them" in section
    assert "Marking someone inactive costs nothing" in section
    # And the re-upload advice is scoped to the path that empties this
    # roster. It first read "whenever you replace or delete rows in
    # either", which is advice to destroy data: after a selected delete
    # the relationships that did not involve those rows are still here,
    # and an upload replaces the whole roster.
    assert "upload them again whenever you replace either" in section
    assert "replace or delete" not in section, section[:400]
    assert "the rest survive" in section
    # The honest half: the app warns and does not undo. It no longer
    # points at the audit log — that page is `require_sys_admin`, so an
    # operator following the Guide there gets a 403.
    assert "nothing undoes it" in section
    assert "audit log" not in section.lower(), (
        "the Guide is operator-facing; the audit log is sys-admin-only"
    )


def test_the_three_cards_agree_about_what_an_upload_costs(
    client: TestClient, db: Session
) -> None:
    """One fact, three pages, and each states the half it owns.

    Reviewers and Reviewees say what an upload *there* destroys;
    Relationships says why — every row names a pair, so it cannot
    outlive either side. A reader landing on any one of the three gets
    the whole rule, which is the point of saying it three times rather
    than pointing twice.
    """
    rs = _mk(client, db, "relcc-cards")

    bodies = {}
    for page in ("reviewers", "reviewees", "relationships"):
        body = client.get(f"/operator/sessions/{rs.id}/{page}").text
        start = body.index('<details class="card page-guidance')
        bodies[page] = " ".join(
            re.sub(r"<[^>]+>", " ", body[start : body.index("</details>", start)])
            .split()
        )

    for page in ("reviewers", "reviewees"):
        # The replace destroys ALL of them, not only the removed
        # people's: `_save` deletes every row and re-adds, so an
        # identical re-upload still wipes the roster. The first draft
        # said "every relationship involving the people it removes" and
        # gave a reason — "a relationship names a pair, so it cannot
        # outlive either side" — that an identical re-upload falsifies.
        assert "every relationship in the session" in bodies[page], page
        assert "removes and re-creates every row" in bodies[page], page
        # And the narrower path, named rather than folded in: a
        # selected delete takes only its own rows' relationships.
        assert "Deleting selected rows is narrower" in bodies[page], page

    rel = bodies["relationships"]
    assert "This roster depends on the other two" in rel
    assert "deletes every relationship in the session" in rel
    assert "Deleting selected rows there is narrower" in rel
    assert "marking someone inactive costs nothing" in rel
    assert "nothing here brings them back" in rel
    # Same scoping as the Guide: re-upload after a replace, add rows
    # back after a selected delete.
    assert "upload this one again after you replace either" in rel
    assert "replace or delete" not in rel, rel[:400]
    assert "another upload here would replace the whole roster" in rel


@pytest.mark.parametrize("page", ["reviewers", "reviewees"])
def test_a_session_without_relationships_is_not_told_their_cost(
    client: TestClient, db: Session, page: str
) -> None:
    """The item's own rule, applied to guidance rather than a label.

    `Decision` rejects listing relationships unconditionally — *"a label
    naming a loss that cannot happen is its own defect"* — and
    `update_session` refuses to turn `relationships_enabled` off while
    rows exist, so off means no relationships can exist and the cost
    described is impossible. The page is not even in the nav.

    The first draft of this rung shipped the paragraph unconditionally.
    A cold read caught it: the rule had been reasoned about for rung 2's
    labels and not carried across.
    """
    rs = _mk(client, db, f"relcc-off-{page[:4]}")
    rs.relationships_enabled = False
    db.commit()

    body = client.get(f"/operator/sessions/{rs.id}/{page}").text
    start = body.index('<details class="card page-guidance')
    prose = " ".join(
        re.sub(r"<[^>]+>", " ", body[start : body.index("</details>", start)])
        .split()
    )

    assert "relationship" not in prose.lower(), prose
    # The rest of the card is untouched — this is a suppressed clause,
    # not a suppressed paragraph.
    assert "replaces the whole roster" in prose
    assert "clears any assignments already generated" in prose
