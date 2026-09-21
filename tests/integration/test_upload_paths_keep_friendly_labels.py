"""Every roster upload entry point keeps the header's friendly labels.

Segment 19R Item 4. A roster CSV header may carry a friendly label as a
suffix — ``ReviewerTag1.Tutor`` means *call `tag_1` "Tutor"* — and the
save functions reconcile it into ``session_field_labels`` when handed
``field_labels_captured``. The three roster cards always passed it. The
**five Quick Setup upload routes did not**, so an operator who set up a
session through the card lost every label they had written into the
header, silently.

The loss is not recoverable anywhere else: 19C Item 1 retired
``field_labels.*`` from the settings bundle precisely *because* roster
headers carry them, so a dropped label means retyping it by hand and
the extract → edit → re-upload round trip stops closing.

So this file is a matrix rather than a case: every route that accepts
a roster CSV, asserted the same way. A new upload path that forgets the
argument shows up here as a failure, not as a report six months later.
"""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.services import field_labels

REVIEWER_CSV = (
    b"ReviewerName,ReviewerEmail,ReviewerTag1.Tutor\n"
    b"Alice,alice@example.edu,senior\n"
)
REVIEWEE_CSV = (
    b"RevieweeName,RevieweeEmail,RevieweeTag1.House\n"
    b"Carol,carol@example.edu,Gryffindor\n"
)
RELATIONSHIP_CSV = (
    b"ReviewerEmail,RevieweeEmail,PairContextTag1.Mentor\n"
    b"alice@example.edu,carol@example.edu,primary\n"
)
#: The same three files with bare tag headers — no ``.Label`` suffix.
#: `spec/csv_contracts.md`'s "upsert present, clear absent" rule makes
#: these *clear* an existing override rather than leave it alone.
BARE_REVIEWER_CSV = (
    b"ReviewerName,ReviewerEmail,ReviewerTag1\n"
    b"Alice,alice@example.edu,senior\n"
)


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "FL", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    review_session.relationships_enabled = True
    db.commit()
    return review_session


def _seed_pair(client: TestClient, review_session: ReviewSession) -> None:
    """A reviewer and a reviewee, so a relationships upload resolves.

    Uploaded through the *card* routes, which were never broken — the
    relationship cases below must fail for their own reason, not
    because the roster they point at is missing.
    """
    for kind, payload in (
        ("reviewers", REVIEWER_CSV),
        ("reviewees", REVIEWEE_CSV),
    ):
        response = client.post(
            f"/operator/sessions/{review_session.id}/{kind}/import",
            files={"file": (f"{kind}.csv", payload, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code in (200, 303), response.text


# --------------------------------------------------------------------------- #
# The matrix: one case per upload entry point.
# --------------------------------------------------------------------------- #
#: ``(id, needs_roster, post)`` — ``post`` uploads the file whose header
#: carries the label, and the assertion after it is always the same.
def _card_reviewers(client, db, s):
    return client.post(
        f"/operator/sessions/{s.id}/reviewers/import",
        files={"file": ("r.csv", REVIEWER_CSV, "text/csv")},
        follow_redirects=False,
    )


def _card_reviewees(client, db, s):
    return client.post(
        f"/operator/sessions/{s.id}/reviewees/import",
        files={"file": ("e.csv", REVIEWEE_CSV, "text/csv")},
        follow_redirects=False,
    )


def _card_relationships(client, db, s):
    return client.post(
        f"/operator/sessions/{s.id}/relationships/import",
        files={"file": ("rel.csv", RELATIONSHIP_CSV, "text/csv")},
        follow_redirects=False,
    )


def _quick_setup_reviewers(client, db, s):
    return client.post(
        f"/operator/sessions/{s.id}/quick-setup/reviewers",
        files={"file": ("r.csv", REVIEWER_CSV, "text/csv")},
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )


def _quick_setup_reviewees(client, db, s):
    return client.post(
        f"/operator/sessions/{s.id}/quick-setup/reviewees",
        files={"file": ("e.csv", REVIEWEE_CSV, "text/csv")},
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )


def _quick_setup_relationships(client, db, s):
    return client.post(
        f"/operator/sessions/{s.id}/quick-setup/relationships",
        files={"file": ("rel.csv", RELATIONSHIP_CSV, "text/csv")},
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )


def _submit_all(client, db, s):
    return client.post(
        f"/operator/sessions/{s.id}/quick-setup/submit-all",
        files={
            "reviewers_file": ("r.csv", REVIEWER_CSV, "text/csv"),
            "reviewees_file": ("e.csv", REVIEWEE_CSV, "text/csv"),
            "relationships_file": ("rel.csv", RELATIONSHIP_CSV, "text/csv"),
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )


#: ``(name, endpoint, needs_roster, post, expected)`` — ``endpoint`` is
#: what the gate at the end of this file matches against the router, and
#: ``expected`` is the set of
#: ``(source_type, field_key, label)`` that upload must leave resolvable.
#: Note the pair-context slots are keyed ``"1"``, not ``"tag_1"`` —
#: ``field_labels._VALID_SOURCE_FIELDS`` spells the three families
#: differently, and resolving the wrong one returns the
#: ``"pair_context:tag_1"`` fallback, which reads exactly like a
#: dropped label.
UPLOAD_PATHS = [
    (
        "card:reviewers",
        "_setup_reviewers.reviewers_import_submit",
        False,
        _card_reviewers,
        [("reviewer", "tag_1", "Tutor")],
    ),
    (
        "card:reviewees",
        "_setup_reviewees.reviewees_import_submit",
        False,
        _card_reviewees,
        [("reviewee", "tag_1", "House")],
    ),
    (
        "card:relationships",
        "_setup_relationships.relationships_import_submit",
        True,
        _card_relationships,
        [("pair_context", "1", "Mentor")],
    ),
    (
        "quick-setup:reviewers",
        "_quick_setup.quick_setup_reviewers_submit",
        False,
        _quick_setup_reviewers,
        [("reviewer", "tag_1", "Tutor")],
    ),
    (
        "quick-setup:reviewees",
        "_quick_setup.quick_setup_reviewees_submit",
        False,
        _quick_setup_reviewees,
        [("reviewee", "tag_1", "House")],
    ),
    (
        "quick-setup:relationships",
        "_quick_setup.quick_setup_relationships_submit",
        True,
        _quick_setup_relationships,
        [("pair_context", "1", "Mentor")],
    ),
    (
        "quick-setup:submit-all",
        "_quick_setup.quick_setup_submit_all",
        False,
        _submit_all,
        [
            ("reviewer", "tag_1", "Tutor"),
            ("reviewee", "tag_1", "House"),
            ("pair_context", "1", "Mentor"),
        ],
    ),
]


@pytest.mark.parametrize(
    ("needs_roster", "post", "expected"),
    [(n, p, e) for _, _, n, p, e in UPLOAD_PATHS],
    ids=[name for name, _, _, _, _ in UPLOAD_PATHS],
)
def test_the_upload_keeps_the_headers_friendly_label(
    client: TestClient,
    db: Session,
    needs_roster: bool,
    post,
    expected: list[tuple[str, str, str]],
) -> None:
    """Measured against the pre-fix tree: the three `card:` cases
    passed and all four `quick-setup:` cases failed — as did the two
    tests below, for six failures in this file and no others anywhere
    in the suite. That silence is the point: nothing else noticed."""

    code = f"fl{abs(hash(post.__name__)) % 100000}"
    review_session = _make_session(client, db, code=code)
    if needs_roster:
        _seed_pair(client, review_session)

    response = post(client, db, review_session)
    assert response.status_code in (200, 303), response.text
    db.expire_all()
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()

    for source_type, field_key, label in expected:
        assert (
            field_labels.resolve(review_session, source_type, field_key)
            == label
        ), (
            f"{source_type}.{field_key} lost its header label: the upload "
            "saved without reconciling field_labels_captured"
        )


def test_the_create_session_form_keeps_the_label(
    client: TestClient, db: Session
) -> None:
    """The eighth entry point, which the matrix above cannot reach: the
    labels ride in on the POST that *creates* the session, so there is
    no session to hand a `post` callable."""

    response = client.post(
        "/operator/sessions",
        data={"name": "FL", "code": "fl-create", "description": "d"},
        files={
            "reviewers_file": ("r.csv", REVIEWER_CSV, "text/csv"),
            "reviewees_file": ("e.csv", REVIEWEE_CSV, "text/csv"),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.expire_all()
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "fl-create")
    ).scalar_one()

    assert field_labels.resolve(review_session, "reviewer", "tag_1") == "Tutor"
    assert field_labels.resolve(review_session, "reviewee", "tag_1") == "House"


def test_a_bare_header_on_quick_setup_clears_the_override(
    client: TestClient, db: Session
) -> None:
    """The half of this item worth review.

    `spec/csv_contracts.md` reconciles a header's labels "upsert
    present, clear absent", and the card has always done that. Making
    Quick Setup pass the captured map gives it the clearing behavior
    too — so a second upload with a bare `ReviewerTag1` header now
    *removes* a label the first one set, where before it would have
    left it standing because nothing was reconciled at all.
    """

    review_session = _make_session(client, db, code="fl-bare")
    client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/reviewers",
        files={"file": ("r.csv", REVIEWER_CSV, "text/csv")},
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    db.expire_all()
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert field_labels.resolve(review_session, "reviewer", "tag_1") == "Tutor"

    client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/reviewers",
        files={"file": ("r.csv", BARE_REVIEWER_CSV, "text/csv")},
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    db.expire_all()
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert (
        field_labels.resolve(review_session, "reviewer", "tag_1") != "Tutor"
    ), (
        "a bare tag header left the override standing; Quick Setup is "
        "supposed to reconcile on the same terms as the card"
    )


# --------------------------------------------------------------------------- #
# The gate (19R Item 4 rung 2) — completeness, not behavior.
# --------------------------------------------------------------------------- #
#: Upload endpoints that legitimately reconcile nothing, each with the
#: reason. An entry here is a claim someone has to defend in review; an
#: endpoint that is in neither this map nor ``UPLOAD_PATHS`` fails the
#: gate, which is the whole point of it.
EXEMPT_ENDPOINTS: dict[str, str] = {
    "_setup_observers.observers_import_submit": (
        "Observers carry no friendly labels by design — "
        "`parse_observer_csv` discards the captured map and "
        "`save_observers` has no parameter for it (19C Item 1)."
    ),
    "_quick_setup.quick_setup_observers_submit": (
        "Same as the Observers card: nothing to reconcile."
    ),
    "_quick_setup.import_session_config": (
        "A Settings CSV, not a roster. 19C Item 1 deliberately retired "
        "`field_labels.*` from the settings bundle, and it stays retired."
    ),
    "_rehydrate.rehydrate_validate": (
        "Validates and stashes; saves no roster. The rehydrate path that "
        "*does* save is `app/services/session_rehydrate.py`, which passes "
        "`field_labels_captured` for all three rosters."
    ),
}

#: Driven by `test_the_create_session_form_keeps_the_label` rather than
#: by the matrix, because its labels arrive on the POST that creates the
#: session and the matrix needs a session to exist first.
CREATE_SESSION_ENDPOINT = "_quick_setup.create_session"


def _upload_endpoints() -> dict[str, list[str]]:
    """Every endpoint the app exposes that accepts an upload, read off
    the router rather than off a list someone maintains.

    That is the difference between this and the matrix above. The matrix
    enumerates the paths *known* to exist when it was written, so it
    catches a regression on one of them; it cannot catch a route added
    later that nobody thought to write a case for — which is exactly how
    the labels came to be dropped on five routes at once.

    The walk has to descend through FastAPI's lazy ``_IncludedRouter``
    wrappers: ``app.routes`` holds seven of them and three real routes,
    so a walk that only looks at the top level finds **no** upload
    endpoints and passes vacuously. The assertion below exists for that.
    """
    from app.main import app

    def walk(routes):
        for route in routes:
            inner = getattr(route, "original_router", None)
            if inner is not None:
                yield from walk(inner.routes)
                continue
            nested = getattr(route, "routes", None)
            if nested and not hasattr(route, "endpoint"):
                yield from walk(nested)
                continue
            if hasattr(route, "endpoint"):
                yield route

    found: dict[str, list[str]] = {}
    for route in walk(app.routes):
        if "POST" not in (getattr(route, "methods", set()) or set()):
            continue
        try:
            signature = inspect.signature(route.endpoint)
        except (ValueError, TypeError):  # pragma: no cover - defensive
            continue
        uploads = [
            name
            for name, param in signature.parameters.items()
            if "UploadFile" in str(param.annotation)
        ]
        if not uploads:
            continue
        key = (
            f"{route.endpoint.__module__.rsplit('.', 1)[-1]}."
            f"{route.endpoint.__name__}"
        )
        found[key] = uploads
    return found


def test_every_upload_endpoint_either_reconciles_labels_or_says_why() -> None:
    """The gate. 19R Item 4's defect was not a wrong line — it was five
    routes nobody had asked the question of.

    So the question gets asked of the *router*: every POST endpoint
    taking an ``UploadFile`` must either be exercised by the matrix
    above (it keeps the header's labels) or appear in
    ``EXEMPT_ENDPOINTS`` with a reason. A new upload route fails here
    until someone classifies it, and classifying it wrongly is at least
    a sentence in a diff that a reviewer can disagree with.

    It deliberately asserts no *count*. A figure self-stales, and the
    next legitimate upload route would fail a test pinned to twelve
    while the contract it guards still held.
    """
    discovered = set(_upload_endpoints())
    assert discovered, (
        "no upload endpoints discovered at all — the router walk is "
        "broken, and a broken walk makes this gate silently vacuous"
    )

    covered = {endpoint for _, endpoint, _, _, _ in UPLOAD_PATHS}
    covered.add(CREATE_SESSION_ENDPOINT)
    accounted = covered | set(EXEMPT_ENDPOINTS)

    unclassified = discovered - accounted
    assert not unclassified, (
        "these upload endpoints are neither exercised by UPLOAD_PATHS nor "
        f"listed in EXEMPT_ENDPOINTS: {sorted(unclassified)}. If the route "
        "saves a roster it must pass field_labels_captured and gain a "
        "matrix case; if it does not, add it to EXEMPT_ENDPOINTS with the "
        "reason."
    )

    stale = accounted - discovered
    assert not stale, (
        "these endpoints are classified but are no longer on the router: "
        f"{sorted(stale)}. A renamed or deleted route leaves this file "
        "asserting something about code that is gone."
    )
