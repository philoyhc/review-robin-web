"""19S Item 7 — the tag typeahead on the four tag boxes.

The four comma-separated tag boxes each opt into the shared partial
(``operator/partials/_tag_typeahead.html``) with ``data-tag-typeahead``:
the lobby's row and bulk expanders, Create's Tags card, and Session
Home's Tags field. Each page renders one ``<datalist id="tag-vocabulary">``
holding every tag on a session the operator owns, archived included
(author's ruling, 2026-09-23), from ``session_tags.vocabulary_for_user``.

What the options *are* as the operator types is
``test_tag_typeahead_rule.py``'s, run under node. This file pins the
wiring: which boxes opt in, which tags a page offers, and that no box
carries a static ``list=``, since a bare datalist without the script
would offer to replace the whole line.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionOperator, SessionTag, User
from app.services import session_tags


def _create(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": code, "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _owner(db: Session, review_session: ReviewSession) -> User:
    operator = db.execute(
        select(SessionOperator).where(
            SessionOperator.session_id == review_session.id
        )
    ).scalars().first()
    return db.get(User, operator.user_id)


def _tag(db: Session, review_session: ReviewSession, tags: list[str]) -> None:
    session_tags.set_tags(
        db,
        review_session=review_session,
        user=_owner(db, review_session),
        tags=tags,
    )


def _someone_elses_session(db: Session, tags: list[str]) -> None:
    other = User(email="zed@example.edu", is_operator=True)
    db.add(other)
    db.flush()
    review_session = ReviewSession(
        name="Theirs", code="THEIRS", created_by_user_id=other.id
    )
    db.add(review_session)
    db.flush()
    db.add(SessionOperator(session_id=review_session.id, user_id=other.id,
                           role="owner"))
    db.commit()
    session_tags.set_tags(db, review_session=review_session, user=other,
                          tags=tags)


def _vocabulary(body: str) -> list[str]:
    assert body.count('<datalist id="tag-vocabulary">') == 1, (
        "one vocabulary per page"
    )
    block = body.split('<datalist id="tag-vocabulary">', 1)[1].split(
        "</datalist>", 1
    )[0]
    return re.findall(r'<option value="([^"]*)"></option>', block)


def _seed(client: TestClient, db: Session) -> ReviewSession:
    """Two sessions the operator owns — one archived — and one they do
    not, each carrying a tag only it has."""
    mine = _create(client, db, "TA-MINE")
    _tag(db, mine, ["alpha", "shared"])
    archived = _create(client, db, "TA-OLD")
    _tag(db, archived, ["legacy"])
    archived.status = "archived"
    db.commit()
    _someone_elses_session(db, ["theirs", "shared"])
    return mine


EXPECTED = ["alpha", "legacy", "shared"]


def test_the_service_scopes_to_owned_sessions_archived_included(
    client: TestClient, db: Session
) -> None:
    mine = _seed(client, db)

    assert session_tags.vocabulary_for_user(db, _owner(db, mine)) == EXPECTED


def test_a_legacy_capitalized_tag_is_offered_lower_case_once(
    client: TestClient, db: Session
) -> None:
    """Tags the settings-CSV importer stored raw before 19S Item 9 are
    still in deployed data. Offered raw, ``Pilot`` would sit beside
    ``pilot`` and be offered again when already in the box."""
    mine = _create(client, db, "TA-LEGACY")
    _tag(db, mine, ["pilot"])
    other = _create(client, db, "TA-RAW")
    db.add(SessionTag(session_id=other.id, tag="Pilot"))
    db.add(SessionTag(session_id=other.id, tag="Cohort-A"))
    db.commit()

    assert session_tags.vocabulary_for_user(db, _owner(db, mine)) == [
        "cohort-a",
        "pilot",
    ]


def test_create_offers_the_operators_vocabulary(
    client: TestClient, db: Session
) -> None:
    _seed(client, db)
    body = client.get("/operator/sessions/new").text

    assert _vocabulary(body) == EXPECTED
    assert re.search(r'<input type="text" id="tags"[^>]*data-tag-typeahead', body)


def test_session_home_offers_the_operators_vocabulary(
    client: TestClient, db: Session
) -> None:
    mine = _seed(client, db)
    body = client.get(f"/operator/sessions/{mine.id}?editing=1").text

    assert _vocabulary(body) == EXPECTED
    assert re.search(
        r'<input type="text" id="config-tags"[^>]*data-tag-typeahead', body
    )


def test_the_lobby_offers_the_wider_vocabulary_to_its_editors(
    client: TestClient, db: Session
) -> None:
    """The row and bulk expanders get every owned tag, ``legacy`` from
    the archived session included, while the filter strip keeps its own
    list scoped to the rows shown."""
    _seed(client, db)
    body = client.get("/operator/sessions").text

    assert _vocabulary(body) == EXPECTED
    assert re.search(
        r'data-expander-field="tags"\s+data-tag-typeahead', body
    ), "the row expander opts in"
    assert re.search(
        r'data-expander-field="bulk-tags"\s+data-tag-typeahead', body
    ), "the bulk expander opts in"
    filter_list = body.split('<datalist id="lobby-filter-options">', 1)[1]
    filter_list = filter_list.split("</datalist>", 1)[0]
    assert "legacy" not in filter_list, "the filter strip is not widened"


def test_exactly_four_boxes_opt_in_and_none_carries_a_static_list(
    client: TestClient, db: Session
) -> None:
    """Without the script a bare datalist would complete the whole line,
    so ``list=`` is set on focus, never in the markup."""
    mine = _seed(client, db)
    pages = [
        client.get("/operator/sessions").text,
        client.get("/operator/sessions/new").text,
        client.get(f"/operator/sessions/{mine.id}?editing=1").text,
    ]
    boxes = [
        tag
        for body in pages
        for tag in re.findall(r"<input[^>]*data-tag-typeahead[^>]*>", body)
    ]

    assert len(boxes) == 4
    assert not any("list=" in box for box in boxes)


def test_an_operator_with_no_tags_gets_an_empty_list(
    client: TestClient, db: Session
) -> None:
    body = client.get("/operator/sessions/new").text

    assert _vocabulary(body) == []
