"""Every Relationships change that would clear group answers asks first.

Author's ruling 2026-10-17 (``guide/warnings_updates.md`` Item 1, rung
4): refuse, then re-offer, on add, edit, CSV import, Delete all,
Inactivate, Reactivate and bulk Delete. A refused change persists
nothing and the page offers a ``Yes, clear them`` tick carrying the
count; the same change with that count goes through. A tick for another
count is refused again, and a change that clears nothing never asks.

The world: Rae reviews Ann and Bo (pair tag ``x``), Cy and Di (``y``)
on a ``p1`` group instrument, all four answered; Ed has no relationship,
so he sits alone and unanswered in the empty-tag group.
"""

from __future__ import annotations

import datetime as dt
import re

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentResponseField,
    Relationship,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from ._feature_toggles import enable_relationships

_SAVED = dt.datetime(2026, 10, 17, tzinfo=dt.timezone.utc)
_TICK = 'name="acknowledge_response_loss"'


def _line(count: int) -> str:
    noun = "response" if count == 1 else "responses"
    return f"This change clears {count} saved {noun} on groups whose members it changes."


def _reselected(page: str, relationship_id: int) -> bool:
    """Whether the refused selection's own row box comes back checked."""
    return re.search(
        rf'class="relationship-select"\s+name="relationship_ids" value="{relationship_id}"'
        r"[^>]*\bchecked\b",
        page,
    ) is not None


def _seed(
    db: Session,
    client: TestClient,
    code: str,
    *,
    inactive: frozenset[str] = frozenset(),
) -> ReviewSession:
    assert (
        client.post(
            "/operator/sessions", data={"name": "S", "code": code}, follow_redirects=False
        ).status_code
        == 303
    )
    session = db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()
    enable_relationships(db, session)
    instrument = Instrument(session_id=session.id, name="Grp", order=9, group_kind="p1")
    db.add(instrument)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="rating",
        label="Rating",
        _inline_data_type="Integer",
        _inline_response_type="Likert5",
        order=0,
    )
    reviewer = Reviewer(session_id=session.id, name="Rae", email="rae@example.edu")
    tags = {"Ann": "x", "Bo": "x", "Cy": "y", "Di": "y", "Ed": None}
    reviewees = {
        name: Reviewee(
            session_id=session.id, name=name, email_or_identifier=f"{name.lower()}@example.edu"
        )
        for name in tags
    }
    db.add_all([field, reviewer, *reviewees.values()])
    db.flush()
    for name, tag in tags.items():
        if tag is not None:
            db.add(
                Relationship(
                    session_id=session.id,
                    reviewer_id=reviewer.id,
                    reviewee_id=reviewees[name].id,
                    tag_1=tag,
                    status="inactive" if name in inactive else "active",
                )
            )
        row = Assignment(
            session_id=session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewees[name].id,
            instrument_id=instrument.id,
        )
        db.add(row)
        db.flush()
        if tag is not None:
            db.add(
                Response(
                    assignment_id=row.id,
                    response_field_id=field.id,
                    value="3",
                    saved_at=_SAVED,
                    version=1,
                )
            )
    db.commit()
    return session


def _responses(db: Session) -> int:
    db.expire_all()
    return db.execute(select(func.count()).select_from(Response)).scalar_one()


def _relationship(db: Session, session_id: int, name: str) -> Relationship:
    db.expire_all()
    return db.execute(
        select(Relationship)
        .join(Reviewee, Reviewee.id == Relationship.reviewee_id)
        .where(Relationship.session_id == session_id, Reviewee.name == name)
    ).scalar_one()


def _edit(name: str, tag: str, *, acknowledged: int | None = None) -> dict[str, str]:
    data = {
        "reviewer_pick": "Rae (rae@example.edu)",
        "reviewee_pick": f"{name} ({name.lower()}@example.edu)",
        "tag_1": tag,
        "status": "active",
    }
    if acknowledged is not None:
        data["acknowledge_response_loss"] = str(acknowledged)
    return data


def _base(session: ReviewSession) -> str:
    return f"/operator/sessions/{session.public_id}/relationships"


def _tick_inside_banner(html: str, count: int) -> bool:
    """The tick the refusal throws up sits inside its red banner, under
    the message (browser run 2026-10-19), not below it."""
    banner = re.search(
        r"<div[^>]*data-group-clear-banner[^>]*>(.*?)</div>", html, re.S
    )
    return (
        banner is not None
        and 'name="acknowledge_response_loss"' in banner.group(1)
        and f'value="{count}"' in banner.group(1)
    )


# --- edit ---------------------------------------------------------------


def test_an_edit_into_an_answered_group_is_refused_then_goes_through(
    db: Session, client: TestClient
) -> None:
    # Ann moves from x into y: y gains her and clears with her row (3).
    session = _seed(db, client, "rgc-edit")
    ann = _relationship(db, session.id, "Ann")
    url = f"{_base(session)}/{ann.id}/update"

    refused = client.post(url, data=_edit("Ann", "y"), follow_redirects=False)
    assert refused.status_code == 400
    assert _line(3) in refused.text
    assert _TICK in refused.text and 'value="3"' in refused.text
    assert _relationship(db, session.id, "Ann").tag_1 == "x"
    assert _responses(db) == 4

    stale = client.post(url, data=_edit("Ann", "y", acknowledged=2), follow_redirects=False)
    assert stale.status_code == 400
    assert _responses(db) == 4

    accepted = client.post(url, data=_edit("Ann", "y", acknowledged=3), follow_redirects=False)
    assert accepted.status_code == 303
    assert _relationship(db, session.id, "Ann").tag_1 == "y"
    assert _responses(db) == 1


def test_a_refused_edit_keeps_the_view(db: Session, client: TestClient) -> None:
    session = _seed(db, client, "rgc-edit-view")
    ann = _relationship(db, session.id, "Ann")

    refused = client.post(
        f"{_base(session)}/{ann.id}/update",
        data=_edit("Ann", "y") | {"filter_q": "Ann", "filter_status": "active"},
        follow_redirects=False,
    )

    assert refused.status_code == 400
    assert 'name="filter_q" value="Ann"' in refused.text
    assert 'name="filter_status" value="active"' in refused.text


def test_an_edit_that_clears_nothing_never_asks(db: Session, client: TestClient) -> None:
    # Ann alone in a new tag is a subset of x: it keeps her answer.
    session = _seed(db, client, "rgc-edit-noop")
    ann = _relationship(db, session.id, "Ann")

    resp = client.post(
        f"{_base(session)}/{ann.id}/update", data=_edit("Ann", "z"), follow_redirects=False
    )

    assert resp.status_code == 303
    assert _responses(db) == 4


# --- add ----------------------------------------------------------------


def test_an_add_into_an_answered_group_is_refused_then_goes_through(
    db: Session, client: TestClient
) -> None:
    # Ed joins y: Cy's and Di's answers clear (2); Ed had none.
    session = _seed(db, client, "rgc-add")
    url = f"{_base(session)}/create"

    refused = client.post(url, data=_edit("Ed", "y"), follow_redirects=False)
    assert refused.status_code == 400
    assert _line(2) in refused.text
    assert _TICK in refused.text and 'value="2"' in refused.text
    assert db.execute(select(func.count()).select_from(Relationship)).scalar_one() == 4

    accepted = client.post(url, data=_edit("Ed", "y", acknowledged=2), follow_redirects=False)
    assert accepted.status_code == 303
    assert _responses(db) == 2


def test_an_add_that_clears_nothing_never_asks(db: Session, client: TestClient) -> None:
    # Ed alone in a new tag is the group he came from: nothing clears.
    session = _seed(db, client, "rgc-add-noop")

    resp = client.post(f"{_base(session)}/create", data=_edit("Ed", "z"), follow_redirects=False)

    assert resp.status_code == 303
    assert _responses(db) == 4


def test_a_refusal_leaves_a_validated_session_validated(
    db: Session, client: TestClient
) -> None:
    # Every service demotes a validated session before the clear: the
    # refusal's rollback must take the demotion, and any audit row, with it.
    session = _seed(db, client, "rgc-validated")
    session.status = "validated"
    db.commit()
    events_before = db.execute(select(func.count()).select_from(AuditEvent)).scalar_one()
    ann = _relationship(db, session.id, "Ann")

    refused = client.post(
        f"{_base(session)}/{ann.id}/update", data=_edit("Ann", "y"), follow_redirects=False
    )

    assert refused.status_code == 400
    db.expire_all()
    assert db.get(ReviewSession, session.id).status == "validated"
    assert db.execute(select(func.count()).select_from(AuditEvent)).scalar_one() == events_before


# --- bulk Inactivate / Reactivate / Delete --------------------------------


def _bulk(session: ReviewSession, db: Session, name: str, acknowledged: int | None = None):
    data: dict[str, object] = {"relationship_ids": [_relationship(db, session.id, name).id]}
    if acknowledged is not None:
        data["acknowledge_response_loss"] = str(acknowledged)
    return data


def test_an_inactivate_into_an_answered_group_is_refused_then_goes_through(
    db: Session, client: TestClient
) -> None:
    # Inactive, Ann reads as empty tags and joins Ed: that group gained
    # her, so her own answer clears (1).
    session = _seed(db, client, "rgc-inactivate")
    url = f"{_base(session)}/bulk-inactivate"

    refused = client.post(url, data=_bulk(session, db, "Ann"), follow_redirects=False)
    assert refused.status_code == 400
    # The panel rebuilds over the refused selection, with the tick.
    assert '"count": 1' in refused.text
    assert _line(1) in refused.text
    ann_id = _relationship(db, session.id, "Ann").id
    assert _reselected(refused.text, ann_id)
    assert not _reselected(refused.text, _relationship(db, session.id, "Bo").id)
    assert _relationship(db, session.id, "Ann").status == "active"
    assert _responses(db) == 4

    accepted = client.post(url, data=_bulk(session, db, "Ann", 1), follow_redirects=False)
    assert accepted.status_code == 303
    assert _relationship(db, session.id, "Ann").status == "inactive"
    assert _responses(db) == 3


def test_a_reactivate_into_an_answered_group_is_refused_then_goes_through(
    db: Session, client: TestClient
) -> None:
    # Ann starts inactive (with Ed in the empty-tag group); reactivated,
    # she rejoins x, which gained her: Bo's and her answers clear (2).
    session = _seed(db, client, "rgc-reactivate", inactive=frozenset({"Ann"}))
    url = f"{_base(session)}/bulk-reactivate"

    refused = client.post(url, data=_bulk(session, db, "Ann"), follow_redirects=False)
    assert refused.status_code == 400
    assert '"count": 2' in refused.text
    assert _reselected(refused.text, _relationship(db, session.id, "Ann").id)
    assert _relationship(db, session.id, "Ann").status == "inactive"

    stale = client.post(url, data=_bulk(session, db, "Ann", 1), follow_redirects=False)
    assert stale.status_code == 400
    assert _responses(db) == 4
    assert _responses(db) == 4

    accepted = client.post(url, data=_bulk(session, db, "Ann", 2), follow_redirects=False)
    assert accepted.status_code == 303
    assert _responses(db) == 2


def test_a_bulk_delete_into_an_answered_group_is_refused_then_goes_through(
    db: Session, client: TestClient
) -> None:
    session = _seed(db, client, "rgc-bulk-delete")
    url = f"{_base(session)}/bulk-delete"

    refused = client.post(
        url, data={**_bulk(session, db, "Ann"), "confirm": "true"}, follow_redirects=False
    )
    assert refused.status_code == 400
    assert '"count": 1' in refused.text
    assert _reselected(refused.text, _relationship(db, session.id, "Ann").id)
    assert db.execute(select(func.count()).select_from(Relationship)).scalar_one() == 4

    accepted = client.post(
        url, data={**_bulk(session, db, "Ann", 1), "confirm": "true"}, follow_redirects=False
    )
    assert accepted.status_code == 303
    assert db.execute(select(func.count()).select_from(Relationship)).scalar_one() == 3
    assert _responses(db) == 3


# --- Delete all and import ------------------------------------------------


def test_delete_all_is_refused_with_the_count_then_goes_through(
    db: Session, client: TestClient
) -> None:
    # Every pair lands in Ed's empty-tag group: all four answers clear.
    session = _seed(db, client, "rgc-delete-all")
    url = f"{_base(session)}/delete-all"

    refused = client.post(url, data={"confirm": "true"}, follow_redirects=False)
    assert refused.status_code == 400
    assert _line(4) in refused.text
    assert _TICK in refused.text and 'value="4"' in refused.text
    assert _tick_inside_banner(refused.text, 4)
    assert db.execute(select(func.count()).select_from(Relationship)).scalar_one() == 4

    accepted = client.post(
        url,
        data={"confirm": "true", "acknowledge_response_loss": "4"},
        follow_redirects=False,
    )
    assert accepted.status_code == 303
    assert _responses(db) == 0


def test_an_import_is_refused_with_the_count_then_goes_through(
    db: Session, client: TestClient
) -> None:
    # The replace moves Ann from x into y (3 clear) and keeps the rest.
    session = _seed(db, client, "rgc-import")
    csv = (
        b"ReviewerEmail,RevieweeEmail,PairContextTag1\n"
        b"rae@example.edu,ann@example.edu,y\n"
        b"rae@example.edu,bo@example.edu,x\n"
        b"rae@example.edu,cy@example.edu,y\n"
        b"rae@example.edu,di@example.edu,y\n"
    )

    def upload(extra: dict[str, str]):
        return client.post(
            f"{_base(session)}/import",
            files={"file": ("relationships.csv", csv, "text/csv")},
            data={"confirm_replace": "true", **extra},
            follow_redirects=False,
        )

    refused = upload({})
    assert refused.status_code == 400
    assert _line(3) in refused.text
    assert _TICK in refused.text and 'value="3"' in refused.text
    assert _tick_inside_banner(refused.text, 3)
    assert _relationship(db, session.id, "Ann").tag_1 == "x"
    assert _responses(db) == 4

    accepted = upload({"acknowledge_response_loss": "3"})
    assert accepted.status_code == 303
    assert _relationship(db, session.id, "Ann").tag_1 == "y"
    assert _responses(db) == 1
