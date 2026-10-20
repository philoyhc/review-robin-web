"""Segment 19Y Item 1 — an instrument's intro picks its layout.

``Instrument.intro_layout`` is ``layout_1`` (heading and help cards left,
visibility right; the default) or ``layout_2`` (heading and visibility
left, help cards right). The instrument card's chip sets it through both
Saves; Replicate, Duplicate and the Settings CSV carry it; the reviewer
surface and the card's preview render it as ``data-intro-layout``.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession, User
from app.db.models.instrument import INTRO_LAYOUT_DEFAULT, INTRO_LAYOUTS
from app.services import session_clone
from app.services.instruments import (
    IntroLayoutError,
    ensure_default_instrument,
    is_untouched_default,
    replicate_instrument,
    set_intro_layout,
)
from app.services.session_config_io import (
    Row,
    apply_session_config,
    serialize_session_config,
)
from app.web.views._instruments import INTRO_LAYOUT_CHOICES, intro_layout_for


def _make_session(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Layouts", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _instrument(db: Session, review_session: ReviewSession) -> Instrument:
    return db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()


def _layout_events(db: Session, instrument: Instrument) -> list[AuditEvent]:
    return [
        event
        for event in db.execute(
            select(AuditEvent)
            .where(AuditEvent.event_type == "instrument.intro_layout_updated")
            .order_by(AuditEvent.id)
        ).scalars()
        if (event.detail or {}).get("refs", {}).get("instrument_id")
        == instrument.id
    ]


def _seed(db: Session, *, code: str) -> tuple[User, ReviewSession, Instrument]:
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="19Y", code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    db.commit()
    return user, review_session, instrument


def test_the_chip_vocabulary_follows_the_model() -> None:
    assert tuple(c["value"] for c in INTRO_LAYOUT_CHOICES) == INTRO_LAYOUTS
    assert INTRO_LAYOUTS[0] == INTRO_LAYOUT_DEFAULT


def test_a_value_outside_the_cycle_renders_as_layout_1() -> None:
    assert intro_layout_for(Instrument(intro_layout="layout_2")) == "layout_2"
    assert intro_layout_for(Instrument(intro_layout="sideways")) == "layout_1"


def test_a_new_instrument_takes_layout_1(db: Session) -> None:
    _, _, instrument = _seed(db, code="19y-default")
    assert instrument.intro_layout == "layout_1"


def test_the_setter_stores_audits_and_skips_a_no_op(db: Session) -> None:
    user, _, instrument = _seed(db, code="19y-setter")
    set_intro_layout(db, instrument=instrument, layout="layout_2", actor=user)
    set_intro_layout(db, instrument=instrument, layout="layout_2", actor=user)
    db.commit()
    assert instrument.intro_layout == "layout_2"
    events = _layout_events(db, instrument)
    assert len(events) == 1
    assert events[0].detail["changes"] == {
        "intro_layout": ["layout_1", "layout_2"]
    }


def test_the_setter_refuses_an_unknown_layout(db: Session) -> None:
    user, _, instrument = _seed(db, code="19y-unknown")
    with pytest.raises(IntroLayoutError):
        set_intro_layout(db, instrument=instrument, layout="layout_9", actor=user)
    assert instrument.intro_layout == "layout_1"


def test_a_layout_2_instrument_is_not_the_untouched_default(db: Session) -> None:
    _, _, instrument = _seed(db, code="19y-untouched")
    assert is_untouched_default(instrument)
    instrument.intro_layout = "layout_2"
    assert not is_untouched_default(instrument)


def test_the_card_renders_the_chip_input_and_preview_attribute(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="19y-card")
    instrument = _instrument(db, review_session)
    instrument.intro_layout = "layout_2"
    db.commit()
    flat = " ".join(
        client.get(
            f"/operator/sessions/{review_session.public_id}/instruments"
        ).text.split()
    )
    heading = flat.index("Preview review instrument</h3>")
    chip = re.search(r"<span [^>]*data-intro-layout-chip[^>]*>([^<]*)</span>", flat)
    assert chip is not None and chip.start() > heading
    assert chip.group(1) == "Layout 2"
    assert 'role="button"' in chip.group(0)
    # The card renders locked: out of the tab order, read disabled.
    assert 'aria-disabled="true"' in chip.group(0)
    assert "tabindex" not in chip.group(0)
    assert re.search(
        rf'<input type="hidden" form="dfsave-{instrument.id}" name="intro_layout" '
        r'value="layout_2" autocomplete="off" data-intro-layout-input>',
        flat,
    )
    assert re.search(
        r'class="rs-intro-columns" data-new-model-band2-intro-card '
        r'data-intro-layout="layout_2"',
        flat,
    )


@pytest.mark.parametrize("path", ["fields/save", "save"])
def test_both_saves_store_the_layout(
    client: TestClient, db: Session, path: str
) -> None:
    review_session = _make_session(client, db, code=f"19y-{path.replace('/', '-')}")
    instrument = _instrument(db, review_session)
    response = client.post(
        f"/operator/sessions/{review_session.public_id}"
        f"/instruments/{instrument.id}/{path}",
        data={"intro_layout": "layout_2"},
        follow_redirects=False,
    )
    assert response.status_code in (200, 303), response.text
    db.expire_all()
    assert db.get(Instrument, instrument.id).intro_layout == "layout_2"
    assert len(_layout_events(db, instrument)) == 1


@pytest.mark.parametrize("path", ["fields/save", "save"])
def test_a_save_without_the_input_keeps_the_layout(
    client: TestClient, db: Session, path: str
) -> None:
    review_session = _make_session(client, db, code=f"19y-keep-{path.replace('/', '-')}")
    instrument = _instrument(db, review_session)
    instrument.intro_layout = "layout_2"
    db.commit()
    response = client.post(
        f"/operator/sessions/{review_session.public_id}"
        f"/instruments/{instrument.id}/{path}",
        data={},
        follow_redirects=False,
    )
    assert response.status_code in (200, 303), response.text
    db.expire_all()
    assert db.get(Instrument, instrument.id).intro_layout == "layout_2"


@pytest.mark.parametrize(
    ("path", "status_code"), [("fields/save", 400), ("save", 422)]
)
def test_both_saves_refuse_an_unknown_layout(
    client: TestClient, db: Session, path: str, status_code: int
) -> None:
    review_session = _make_session(client, db, code=f"19y-bad-{path.replace('/', '-')}")
    instrument = _instrument(db, review_session)
    response = client.post(
        f"/operator/sessions/{review_session.public_id}"
        f"/instruments/{instrument.id}/{path}",
        data={"intro_layout": "sideways", "short_label": "Changed"},
        follow_redirects=False,
    )
    assert response.status_code == status_code
    db.expire_all()
    stored = db.get(Instrument, instrument.id)
    assert stored.intro_layout == "layout_1"
    assert stored.short_label != "Changed"


def test_replicate_carries_the_layout(db: Session) -> None:
    user, review_session, instrument = _seed(db, code="19y-repl")
    instrument.intro_layout = "layout_2"
    db.commit()
    replica = replicate_instrument(
        db, review_session=review_session, source=instrument, actor=user
    )
    assert replica.intro_layout == "layout_2"


def test_duplicate_carries_each_instruments_layout(db: Session) -> None:
    user, review_session, first = _seed(db, code="19y-dup")
    second = Instrument(session_id=review_session.id, name="Second", order=1)
    db.add(second)
    db.flush()
    first.intro_layout = "layout_2"
    db.commit()
    clone = session_clone.clone_session(
        db, source=review_session, user=user, mode="config"
    )
    layouts = dict(
        db.execute(
            select(Instrument.name, Instrument.intro_layout).where(
                Instrument.session_id == clone.id
            )
        ).all()
    )
    assert layouts == {first.name: "layout_2", "Second": "layout_1"}


def _bare(db: Session, code: str) -> ReviewSession:
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(name=code, code=code, created_by_user_id=user.id)
    db.add(review_session)
    db.flush()
    return review_session


def test_settings_csv_round_trip_carries_each_instruments_layout(
    db: Session,
) -> None:
    _, source, first = _seed(db, code="19y-csv-src")
    second = Instrument(session_id=source.id, name="Second", order=1)
    db.add(second)
    db.flush()
    first.intro_layout = "layout_2"
    db.commit()

    rows = serialize_session_config(db, source)
    by_field = {r.field: r for r in rows}
    assert by_field["instruments[1].intro_layout"] == Row(
        "instruments[1].intro_layout", "layout_2", "enum"
    )
    assert by_field["instruments[2].intro_layout"].value == "layout_1"

    destination = _bare(db, "19y-csv-dst")
    result = apply_session_config(db, destination, rows)
    assert result.ok, result.errors
    layouts = [
        layout
        for (layout,) in db.execute(
            select(Instrument.intro_layout)
            .where(Instrument.session_id == destination.id)
            .order_by(Instrument.order)
        ).all()
    ]
    assert layouts == ["layout_2", "layout_1"]


def test_an_older_settings_csv_takes_the_default(db: Session) -> None:
    destination = _bare(db, "19y-csv-old")
    result = apply_session_config(
        db, destination, [Row("instruments[1].name", "Eval", "string")]
    )
    assert result.ok, result.errors
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == destination.id)
    ).scalar_one()
    assert instrument.intro_layout == "layout_1"


def test_the_settings_csv_refuses_an_unknown_layout(db: Session) -> None:
    destination = _bare(db, "19y-csv-bad")
    result = apply_session_config(
        db,
        destination,
        [
            Row("instruments[1].name", "Eval", "string"),
            Row("instruments[1].intro_layout", "layout_9", "enum"),
        ],
    )
    assert not result.ok
    assert any("intro_layout" in str(error) for error in result.errors)


def test_a_stray_stored_value_reads_exports_and_cycles_as_layout_1(
    client: TestClient, db: Session
) -> None:
    """A value outside ``INTRO_LAYOUTS`` (a later build's layout, say) is
    the default everywhere it is read, so a backup of it still imports."""
    review_session = _make_session(client, db, code="19y-stray")
    instrument = _instrument(db, review_session)
    instrument.intro_layout = "layout_9"
    db.commit()

    flat = " ".join(
        client.get(
            f"/operator/sessions/{review_session.public_id}/instruments"
        ).text.split()
    )
    chip = re.search(r"<span [^>]*data-intro-layout-chip[^>]*>([^<]*)</span>", flat)
    assert chip is not None and chip.group(1) == "Layout 1"
    assert 'name="intro_layout" value="layout_1"' in flat

    rows = serialize_session_config(db, review_session)
    assert {r.field: r.value for r in rows}["instruments[1].intro_layout"] == "layout_1"
