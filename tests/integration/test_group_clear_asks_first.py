"""The Instrument card's Save asks before it clears group answers.

Author's ruling 2026-10-17 (``guide/warnings_updates.md`` Item 1):
refuse, then re-offer. A Save whose regroup would clear an answer does
nothing and answers with the count; the same Save with
``acknowledge_response_loss=true`` goes through. A Save that clears
nothing never asks.
"""

from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import instruments as instruments_service
from app.services.instruments import ensure_default_instrument

_SAVED = dt.datetime(2026, 10, 17, tzinfo=dt.timezone.utc)
_BY_TEAM = instruments_service.encode_group_kind([("reviewee", "tag_1")])


def _seed(db: Session, client: TestClient, code: str) -> tuple[ReviewSession, Instrument]:
    """One reviewer and four reviewees in two teams, grouped by team,
    every row answered."""
    assert (
        client.post(
            "/operator/sessions", data={"name": "S", "code": code}, follow_redirects=False
        ).status_code
        == 303
    )
    session = db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()
    instrument = ensure_default_instrument(db, session)
    instrument.group_kind = _BY_TEAM
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="gc_rating",
        label="Rating",
        _inline_data_type="Integer",
        _inline_response_type="Likert5",
        order=0,
    )
    reviewer = Reviewer(session_id=session.id, name="Rae", email="rae@example.edu")
    reviewees = [
        Reviewee(
            session_id=session.id,
            name=name,
            email_or_identifier=f"{name.lower()}@example.edu",
            tag_1=team,
        )
        for name, team in (("Ann", "red"), ("Bo", "red"), ("Cy", "blue"), ("Di", "blue"))
    ]
    db.add_all([field, reviewer, *reviewees])
    db.flush()
    rows = [
        Assignment(
            session_id=session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
        )
        for reviewee in reviewees
    ]
    db.add_all(rows)
    db.flush()
    db.add_all(
        Response(
            assignment_id=row.id,
            response_field_id=field.id,
            value="3",
            saved_at=_SAVED,
            version=1,
        )
        for row in rows
    )
    db.commit()
    return session, instrument


def _form(*boundary: str, acknowledged: int | None = None) -> dict[str, object]:
    data: dict[str, object] = {
        "link3_mode": "grouped",
        "link3_touched": "true",
        "link3_boundary": list(boundary),
    }
    for link in ("link1", "link2"):
        data[f"{link}_touched"] = "true"
        data[f"{link}_combinator"] = "AND"
        data[f"{link}_mode"] = "all"
    if acknowledged is not None:
        data["acknowledge_response_loss"] = str(acknowledged)
    return data


def _responses(db: Session) -> int:
    db.expire_all()
    return db.execute(select(func.count()).select_from(Response)).scalar_one()


def _group_kind(db: Session, instrument_id: int) -> str | None:
    db.expire_all()
    return db.get(Instrument, instrument_id).group_kind


def test_a_merge_is_refused_with_the_count(db: Session, client: TestClient) -> None:
    session, instrument = _seed(db, client, "gc-merge")

    resp = client.post(
        f"/operator/sessions/{session.id}/instruments/{instrument.id}/save", data=_form()
    )

    assert resp.status_code == 422
    body = resp.json()
    assert body["ok"] is False
    assert body["confirm_group_clear"] == 4
    assert body["errors"] == [
        "This change clears 4 saved responses on groups whose members it changes."
    ]
    assert _responses(db) == 4
    assert _group_kind(db, instrument.id) == _BY_TEAM


def test_an_acknowledged_merge_clears(db: Session, client: TestClient) -> None:
    session, instrument = _seed(db, client, "gc-merge-ack")

    resp = client.post(
        f"/operator/sessions/{session.id}/instruments/{instrument.id}/save",
        data=_form(acknowledged=4),
    )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert _responses(db) == 0
    assert _group_kind(db, instrument.id) == instruments_service.encode_group_kind([])


def test_a_tick_for_another_count_is_refused_again(
    db: Session, client: TestClient
) -> None:
    """A tick left on after further edits carries the count it was shown,
    so it cannot approve a clear of a different size."""
    session, instrument = _seed(db, client, "gc-stale")

    resp = client.post(
        f"/operator/sessions/{session.id}/instruments/{instrument.id}/save",
        data=_form(acknowledged=2),
    )

    assert resp.status_code == 422
    assert resp.json()["confirm_group_clear"] == 4
    assert _responses(db) == 4


def test_the_no_js_fallback_refuses_then_goes_through(
    db: Session, client: TestClient
) -> None:
    session, instrument = _seed(db, client, "gc-fallback")
    url = f"/operator/sessions/{session.id}/instruments/{instrument.id}/fields/save"

    refused = client.post(url, data=_form(), follow_redirects=False)
    assert refused.status_code == 422
    assert "clears 4 saved responses" in refused.text
    assert _responses(db) == 4
    assert _group_kind(db, instrument.id) == _BY_TEAM

    accepted = client.post(url, data=_form(acknowledged=4), follow_redirects=False)
    assert accepted.status_code == 303
    assert _responses(db) == 0


def test_a_save_that_clears_nothing_never_asks(db: Session, client: TestClient) -> None:
    session, instrument = _seed(db, client, "gc-noop")
    url = f"/operator/sessions/{session.id}/instruments/{instrument.id}/save"

    unchanged = client.post(url, data=_form("reviewee.tag1"))
    assert unchanged.status_code == 200
    assert "confirm_group_clear" not in unchanged.json()
    # Individual splits every group into one-member parts, each a
    # subset of the group it came from: nothing clears, nothing asks.
    split = client.post(url, data={**_form(), "link3_mode": "individual"})
    assert split.status_code == 200
    assert _responses(db) == 4
    assert _group_kind(db, instrument.id) is None


def test_the_card_renders_the_tick_on_its_dfsave_form(
    db: Session, client: TestClient
) -> None:
    session, instrument = _seed(db, client, "gc-tick")

    page = client.get(
        f"/operator/sessions/{session.id}/instruments?editing={instrument.id}"
    ).text

    assert "confirm_group_clear" in page
    assert "acknowledge_response_loss" in page
    assert "Yes, clear them" in page
