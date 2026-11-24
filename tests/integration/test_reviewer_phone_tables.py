"""Segment 20Q rung 5 — the lobby, summary, results and collation tables
render as cards on a phone: each is an ``rs-table`` (base.html's card
layout under 640 px) whose value cells carry the ``data-label`` a card
shows over (or, in the lobby, beside) each value. The layout itself is
held at 390 px by the browser guard (rung 6); this pins the markup the
layout reads, on real pages."""

from __future__ import annotations

from collections.abc import Callable
from html.parser import HTMLParser

import pytest
from _mounted import MOUNT
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Instrument, InstrumentViewPolicy
from app.services.visibility_policies import MODE_LABELS

from .test_url_crawl import _go_live, _release, _seed_draft, _submit, _user


class _Tables(HTMLParser):
    """Each ``rs-table``'s body value cells' ``data-label``s: every
    ``<td>`` but a row's first (the identity: reviewee, group, reviewer,
    cohort or session) and a cell spanning columns (collation's download)."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[str | None]] = []
        self._first = False
        self._depth = 0
        self._in_body = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "table":
            if self._depth or "rs-table" in (a.get("class") or "").split():
                self._depth += 1
                if self._depth == 1:
                    self.tables.append([])
        elif self._depth == 1 and tag == "tbody":
            self._in_body = True
        elif self._depth == 1 and self._in_body and tag == "tr":
            self._first = True
        elif self._depth == 1 and self._in_body and tag == "td":
            if self._first or a.get("colspan"):
                self._first = False
                return
            self.tables[-1].append(a.get("data-label"))

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._depth:
            self._depth -= 1
            self._in_body = False


def _cells(body: str) -> list[list[str | None]]:
    parser = _Tables()
    parser.feed(body)
    return parser.tables


@pytest.fixture
def pages(
    db: Session,
    mounted_client: TestClient,
    make_mounted_client: Callable[[AuthenticatedUser], TestClient],
    grant_reviewee_visibility: Callable[..., Instrument],
) -> dict[str, str]:
    """The four pages of one released session whose responses rae and
    carol may read."""
    review_session, params = _seed_draft(mounted_client, db)
    _go_live(make_mounted_client(_user("alice")), db, review_session, params)
    _submit(make_mounted_client(_user("rae")), db, review_session)
    _release(db, review_session, grant_reviewee_visibility)
    granularity, identification = MODE_LABELS["raw"]
    with db.no_autoflush:
        instruments = db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
        for instrument in instruments.all():
            policy = db.execute(
                select(InstrumentViewPolicy).where(
                    InstrumentViewPolicy.instrument_id == instrument.id,
                    InstrumentViewPolicy.audience == "peer_reviewer",
                )
            ).scalar_one_or_none()
            if policy is None:
                policy = InstrumentViewPolicy(instrument_id=instrument.id, audience="peer_reviewer")
                db.add(policy)
            policy.while_ongoing_granularity = granularity
            policy.while_ongoing_identification = identification
            policy.after_release_granularity = granularity
            policy.after_release_identification = identification
            reviewee = db.execute(
                select(InstrumentViewPolicy).where(
                    InstrumentViewPolicy.instrument_id == instrument.id,
                    InstrumentViewPolicy.audience == "reviewee",
                )
            ).scalar_one_or_none()
            if reviewee is None:
                reviewee = InstrumentViewPolicy(instrument_id=instrument.id, audience="reviewee")
                db.add(reviewee)
            reviewee.after_release_granularity = granularity
            reviewee.after_release_identification = identification
    db.commit()
    sid = params["session_id"]
    visits = {
        "lobby": ("rae", "/me"),
        "summary": ("rae", f"/me/sessions/{sid}/summary"),
        "results": ("carol", f"/me/sessions/{sid}/results"),
        "collation": ("olive", f"/me/sessions/{sid}/collation"),
    }
    bodies: dict[str, str] = {}
    for name, (who, path) in visits.items():
        response = make_mounted_client(_user(who)).get(MOUNT + path)
        assert response.status_code == 200, (name, response.status_code)
        bodies[name] = response.text
    return bodies


@pytest.mark.parametrize("page", ["lobby", "summary", "results", "collation"])
def test_each_page_table_is_a_card_table_with_labelled_values(
    pages: dict[str, str], page: str
) -> None:
    tables = _cells(pages[page])
    assert tables, f"{page}: no rs-table"
    for labels in tables:
        assert labels, f"{page}: an rs-table with no value cells"
        assert all(labels), (page, labels)


def test_the_lobby_reads_its_labels_beside_their_values(pages: dict[str, str]) -> None:
    assert 'class="rs-table rs-table-inline"' in pages["lobby"]
    tables = _cells(pages["lobby"])
    assert tables[0][:5] == ["Start", "End", "Timezone", "Session status", "Reviewer status"]
