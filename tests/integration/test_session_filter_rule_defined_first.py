"""The Lobby / Archive filter rule is defined before either page calls it.

``rrwSessionFilterMatches`` lives once in ``base.html``
(``test_session_filter_rule.py`` executes it). Both pages' own filter
scripts call it while the page is still parsing, in their load-time
``apply()``. When the rule sat with the shared scripts at the foot of
``<body>``, it did not exist yet at that point: every load threw
``rrwSessionFilterMatches is not defined``, and the Archive then ignored
a saved tag filter on reload (found 2026-09-23, driving the lobby in
Chromium for 19S Item 7). It now sits in ``<head>``.

A script's position is the whole of the contract, so that is what this
pins: in each rendered page the definition precedes the first call.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

DEFINITION = "function rrwSessionFilterMatches("
CALL = "return rrwSessionFilterMatches("


def _session(client: TestClient, db: Session, code: str, archived: bool) -> None:
    response = client.post(
        "/operator/sessions",
        data={"name": code, "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    if archived:
        review_session = db.execute(
            select(ReviewSession).where(ReviewSession.code == code)
        ).scalar_one()
        review_session.status = "archived"
        db.commit()


@pytest.mark.parametrize(
    "path,archived",
    [("/operator/sessions", False), ("/operator/sessions/archived", True)],
)
def test_the_rule_is_defined_before_the_page_calls_it(
    client: TestClient, db: Session, path: str, archived: bool
) -> None:
    _session(client, db, "FILTER-ORDER", archived)
    body = client.get(path).text

    assert body.count(DEFINITION) == 1
    assert CALL in body, "the page still calls the shared rule"
    assert body.index(DEFINITION) < body.index(CALL)
    assert body.index(DEFINITION) < body.index("</head>"), "defined in <head>"
