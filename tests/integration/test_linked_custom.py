"""What a custom linked instrument allows (segment 23G rung 3,
`guide/segment_23G_linked_custom_instrument.md`): the fields the
application sent are held, known by key (``Instrument.held_field_keys``);
the card's Save may reorder them, set whether they are required, branch
them and add Review Robin's own fields, and refuses removing or redefining
a held one. A locked instrument keeps its fields as before."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession
from utilityapps.interop_poc import mock

from .test_handoff_update import _created, _resend, _update_bundle, _with
from .test_handoffs import REVIEWEES, REVIEWERS
from .test_instrument_builder_routes import _band2_rfs


def _custom(client: TestClient, db: Session, mode: str = "custom") -> ReviewSession:
    settings = mock.settings_csv() + f"instruments[1].linked_mode,{mode},enum\r\n"
    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": settings}
    review_session, _ = _created(client, db, files=files)
    return review_session


def _instrument(db: Session) -> Instrument:
    db.expire_all()
    return db.scalars(select(Instrument)).one()


def _save(client: TestClient, review_session: ReviewSession, rfs: list[dict[str, Any]]):
    instrument_id = review_session.id and _instrument_id(client, review_session)
    return client.post(
        f"/operator/sessions/{review_session.public_id}/instruments/{instrument_id}/save",
        data={"band2_state_snapshot": json.dumps({"response_fields": rfs})},
        follow_redirects=False,
    )


def _instrument_id(client: TestClient, review_session: ReviewSession) -> int:
    del client
    return next(i.id for i in review_session.instruments)


def _keys(db: Session) -> list[str]:
    return [f.field_key for f in sorted(_instrument(db).response_fields, key=lambda f: f.order)]


def test_the_create_records_the_fields_it_sent(client: TestClient, db: Session) -> None:
    _custom(client, db)
    assert _instrument(db).held_field_keys == ["score", "comment"]


def test_a_resend_records_the_fields_it_sent(client: TestClient, db: Session) -> None:
    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": mock.settings_csv()}
    _, created = _created(client, db, files=files)
    fields = (
        "field,value,data_type\r\n"
        "instruments[1].name,Gate 2,string\r\n"
        "instruments[1].response_fields[1].field_key,comment,string\r\n"
        "instruments[1].response_fields[1].label,Comments,string\r\n"
        "instruments[1].response_fields[1].response_type,text,string\r\n"
        "instruments[1].response_fields[1].data_type,String,string\r\n"
    )
    reply = _resend(client, created, _update_bundle(files=_with(fields)))
    assert reply.status_code == 200, reply.text
    assert _instrument(db).held_field_keys == ["comment"]


def test_custom_saves_order_required_and_an_own_field(client: TestClient, db: Session) -> None:
    review_session = _custom(client, db)
    rfs = _band2_rfs(_instrument(db))
    score, comment = rfs
    own = {
        "name": "Familiarity",
        "data_type": "integer",
        "min": "0",
        "max": "5",
        "step": "1",
        "selected": True,
        "required": True,
        "help_text": "",
        "help_text_visible": False,
    }
    reply = _save(
        client, review_session, [own, {**comment, "required": True}, {**score, "required": False}]
    )
    assert reply.status_code == 200, reply.text
    assert _keys(db) == ["familiarity", "comment", "score"]
    by_key = {f.field_key: f for f in _instrument(db).response_fields}
    assert by_key["comment"].required and not by_key["score"].required
    # The own field is Review Robin's: never held.
    assert _instrument(db).held_field_keys == ["score", "comment"]


def test_custom_refuses_removing_a_held_field(client: TestClient, db: Session) -> None:
    review_session = _custom(client, db)
    score, _comment = _band2_rfs(_instrument(db))
    reply = _save(client, review_session, [score])
    assert reply.status_code == 422
    assert "can't be removed" in reply.json()["errors"][0]
    assert _keys(db) == ["score", "comment"]


def test_custom_refuses_redefining_a_held_field(client: TestClient, db: Session) -> None:
    review_session = _custom(client, db)
    score, comment = _band2_rfs(_instrument(db))
    for change in ({"name": "Rating"}, {"max": "7"}, {"help_text": "Mine"}, {"selected": False}):
        reply = _save(client, review_session, [{**score, **change}, comment])
        assert reply.status_code == 422, change
        assert "only whether it is required" in reply.json()["errors"][0]
    instrument = _instrument(db)
    score_row = next(f for f in instrument.response_fields if f.field_key == "score")
    assert (score_row.label, score_row._inline_max, score_row.visible) == ("Score", 5, True)


def test_a_locked_instrument_keeps_its_fields_whatever_the_save_says(
    client: TestClient, db: Session
) -> None:
    review_session = _custom(client, db, mode="locked")
    score, _comment = _band2_rfs(_instrument(db))
    reply = _save(client, review_session, [{**score, "name": "Rating"}])
    assert reply.status_code == 200, reply.text
    assert _keys(db) == ["score", "comment"]


def test_the_page_fixes_held_rows_and_opens_band_3(client: TestClient, db: Session) -> None:
    review_session = _custom(client, db)
    page = client.get(f"/operator/sessions/{review_session.public_id}/instruments").text
    assert page.count('data-new-model-rf-held="true"') == 2
    assert "The fields marked with a lock come from" in page
    # Band 3 is the operator's lock region, not the linked-fixed one.
    start = page.index('<table class="rf-table" data-new-model-rf-rows')
    rows = page[start : page.index("<tbody", start)]
    assert "data-linked-fixed" not in rows and "data-lock-region" in rows
    assert "data-linked-structure\n" not in page and "data-linked-structure " not in page


def test_a_locked_page_stays_fixed(client: TestClient, db: Session) -> None:
    review_session = _custom(client, db, mode="locked")
    page = client.get(f"/operator/sessions/{review_session.public_id}/instruments").text
    assert 'data-new-model-rf-held="true"' not in page
    assert "data-linked-structure\n" in page


# --- The cumulative read of rungs 2-5 ---


def _branched(db: Session) -> None:
    """Familiarity (own) governs the held Score; the held Comments, now
    required, anchors the branch (19T Item 11)."""
    from .test_results_not_asked import _familiarity_governs_score

    fields = _familiarity_governs_score(db)
    fields["comment"].required = True
    db.commit()


def test_hiding_an_own_parent_hides_a_held_field_without_a_refusal(
    client: TestClient, db: Session
) -> None:
    review_session = _custom(client, db)
    _branched(db)
    rfs = _band2_rfs(_instrument(db))
    hidden = [{**rf, "selected": False} if rf["name"] == "Familiarity" else rf for rf in rfs]
    reply = _save(client, review_session, hidden)
    assert reply.status_code == 200, reply.text
    fields = {f.field_key: f for f in _instrument(db).response_fields}
    assert not fields["familiarity"].visible and not fields["score"].visible
    # Shown again, the cascade shows the held field again too.
    reply = _save(client, review_session, [{**rf, "selected": True} for rf in rfs])
    assert reply.status_code == 200, reply.text
    assert {f.field_key: f.visible for f in _instrument(db).response_fields}["score"]


def test_a_long_held_text_survives_a_save(client: TestClient, db: Session) -> None:
    review_session = _custom(client, db)
    comment = next(f for f in _instrument(db).response_fields if f.field_key == "comment")
    long_help = "Say why. " * 150  # past the card's 1000 characters
    comment.help_text = long_help
    db.commit()
    score, comment_rf = _band2_rfs(_instrument(db))
    reply = _save(client, review_session, [comment_rf, score])  # a reorder only
    assert reply.status_code == 200, reply.text
    stored = next(f for f in _instrument(db).response_fields if f.field_key == "comment")
    assert stored.help_text == long_help


def test_a_switch_into_custom_holds_what_an_old_instrument_has(
    client: TestClient, db: Session
) -> None:
    from .test_handoff_update import _created as created_with

    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": mock.settings_csv()}
    _, transfer = created_with(client, db, files=files)
    instrument = _instrument(db)
    instrument.held_field_keys = None  # from before the list
    db.commit()
    typed = (
        "field,value,data_type\r\n"
        "instruments[1].name,Gate 1,string\r\n"
        "instruments[1].linked_mode,custom,enum\r\n"
    )
    reply = _resend(client, transfer, _update_bundle(files=_with(typed)))
    assert reply.status_code == 200, reply.text
    assert _instrument(db).held_field_keys == ["score", "comment"]


def test_a_blank_type_cell_leaves_the_type(client: TestClient, db: Session) -> None:
    from .test_handoff_update import _created as created_with

    settings = mock.settings_csv() + "instruments[1].linked_mode,custom,enum\r\n"
    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": settings}
    _, transfer = created_with(client, db, files=files)
    blank = (
        "field,value,data_type\r\n"
        "instruments[1].name,Gate 1,string\r\n"
        "instruments[1].linked_mode,,enum\r\n"
    )
    reply = _resend(client, transfer, _update_bundle(files=_with(blank)))
    assert reply.status_code == 200, reply.text
    assert _instrument(db).linked_mode == "custom"
