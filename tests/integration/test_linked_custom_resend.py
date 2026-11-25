"""A re-send into a custom linked instrument (segment 23G rung 4,
`guide/segment_23G_linked_custom_instrument.md`): held fields update in
place by key and a new one joins at the end; Review Robin's own fields,
the order, the branches and ``required`` stay; a held field the re-send
drops is deleted, and a branch that loses its parent or no longer fits
is dropped, audited as ``instrument.branch_dropped``. A switch to locked
on an unopened draft drops the own fields and the branches."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, InstrumentResponseField
from utilityapps.interop_poc import mock

from ._lookups import detail_of
from .test_handoff_update import _created, _resend, _update_bundle, _with
from .test_handoffs import REVIEWEES, REVIEWERS

SCORE = ("score", "Score", "1-to-5int", "Integer", "1", "5", "1")
COMMENT = ("comment", "Comments", "text", "String", "", "", "")
RECOMMEND = ("recommend", "Recommend?", "list", "List", "", "", "")


def _settings(*fields: tuple[str, ...], mode: str | None = None) -> str:
    rows = ["field,value,data_type", "instruments[1].name,Gate 1,string"]
    if mode:
        rows.append(f"instruments[1].linked_mode,{mode},enum")
    for n, (key, label, response_type, data_type, lo, hi, step) in enumerate(fields, start=1):
        at = f"instruments[1].response_fields[{n}]"
        rows += [
            f"{at}.field_key,{key},string",
            f"{at}.label,{label},string",
            f"{at}.response_type,{response_type},string",
            f"{at}.data_type,{data_type},string",
            f"{at}.required,true,boolean",
        ]
        rows += [
            f"{at}.{k},{v},decimal" for k, v in (("min", lo), ("max", hi), ("step", step)) if v
        ]
        if data_type == "List":
            rows.append(f'{at}.list_csv,"Yes,No",string')
    return "\r\n".join(rows) + "\r\n"


def _instrument(db: Session) -> Instrument:
    db.expire_all()
    return db.scalars(select(Instrument)).one()


def _fields(db: Session) -> dict[str, InstrumentResponseField]:
    return {f.field_key: f for f in _instrument(db).response_fields}


def _order(db: Session) -> list[str]:
    return [f.field_key for f in sorted(_instrument(db).response_fields, key=lambda f: f.order)]


def _own(db: Session, key: str, label: str, order: int) -> InstrumentResponseField:
    instrument = _instrument(db)
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key=key,
        label=label,
        order=order,
        required=True,
        visible=True,
        _inline_data_type="Integer",
        _inline_response_type="1-to-5int",
        _inline_min=0,
        _inline_max=5,
        _inline_step=1,
    )
    db.add(field)
    db.flush()
    return field


def _custom(client: TestClient, db: Session, mode: str = "custom") -> str:
    """A linked gate of ``mode``, as created; its transfer id."""
    settings = mock.settings_csv() + f"instruments[1].linked_mode,{mode},enum\r\n"
    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": settings}
    _, created = _created(client, db, files=files)
    return created


def _set_up(client: TestClient, db: Session) -> str:
    """A custom gate: Familiarity (own) first, governing Score when it is
    at least 1; Comments last, made optional by Review Robin."""
    created = _custom(client, db)
    fields = _fields(db)
    for field in fields.values():
        field.order += 1
    familiarity = _own(db, "familiarity", "Familiarity", 0)
    familiarity.branch_op, familiarity.branch_value = "ge", "1"
    fields["score"].branch_parent_id = familiarity.id
    fields["comment"].required = False
    db.commit()
    assert _order(db) == ["familiarity", "score", "comment"]
    return created


def _dropped(db: Session) -> list[dict[str, object]]:
    return [
        detail_of(e)
        for e in db.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "instrument.branch_dropped")
        )
    ]


def test_a_resend_keeps_own_fields_order_branches_and_required(
    client: TestClient, db: Session
) -> None:
    created = _set_up(client, db)
    reply = _resend(
        client, created, _update_bundle(files=_with(_settings(SCORE, COMMENT, RECOMMEND)))
    )
    assert reply.status_code == 200, reply.text
    assert _order(db) == ["familiarity", "score", "comment", "recommend"]
    fields = _fields(db)
    assert fields["score"].branch_parent_id == fields["familiarity"].id
    assert fields["familiarity"].branch_op == "ge"
    # Required is Review Robin's; a new field starts from the sent one.
    assert not fields["comment"].required and fields["recommend"].required
    assert _instrument(db).held_field_keys == ["score", "comment", "recommend"]
    assert _dropped(db) == []


def test_a_held_field_the_resend_drops_goes_and_its_branch_with_it(
    client: TestClient, db: Session
) -> None:
    created = _set_up(client, db)
    # Score becomes a parent: its own "why" field follows it, governed.
    fields = _fields(db)
    why = _own(db, "why", "Why", 2)
    fields["comment"].order = 3
    familiarity = fields["familiarity"]
    familiarity.branch_op = familiarity.branch_value = None
    fields["score"].branch_parent_id = None
    fields["score"].branch_op, fields["score"].branch_value = "ge", "3"
    why.branch_parent_id = fields["score"].id
    db.commit()
    reply = _resend(client, created, _update_bundle(files=_with(_settings(COMMENT))))
    assert reply.status_code == 200, reply.text
    assert _order(db) == ["familiarity", "why", "comment"]
    assert _fields(db)["why"].branch_parent_id is None
    (dropped,) = _dropped(db)
    assert dropped["reason"] == "field_removed"
    assert dropped["snapshot"] == {"field_key": "score", "label": "Score"}


def test_a_parent_that_no_longer_takes_its_condition_loses_its_branch(
    client: TestClient, db: Session
) -> None:
    created = _set_up(client, db)
    # Familiarity is own; make Score the parent, then send Score as String.
    fields = _fields(db)
    fields["familiarity"].branch_op = fields["familiarity"].branch_value = None
    fields["score"].branch_parent_id = None
    fields["score"].branch_op, fields["score"].branch_value = "ge", "3"
    fields["comment"].branch_parent_id = fields["score"].id
    db.commit()
    as_text = ("score", "Score", "text", "String", "", "", "")
    reply = _resend(client, created, _update_bundle(files=_with(_settings(as_text, COMMENT))))
    assert reply.status_code == 200, reply.text
    fields = _fields(db)
    assert fields["comment"].branch_parent_id is None and fields["score"].branch_op is None
    (dropped,) = _dropped(db)
    assert dropped["reason"] == "no_longer_fits"


def test_a_switch_to_locked_drops_own_fields_and_branches(client: TestClient, db: Session) -> None:
    created = _set_up(client, db)
    reply = _resend(client, created, _update_bundle(files=_with(_settings(mode="locked"))))
    assert reply.status_code == 200, reply.text
    instrument = _instrument(db)
    assert instrument.linked_mode == "locked"
    assert _order(db) == ["score", "comment"]
    assert all(
        f.branch_parent_id is None and f.branch_op is None for f in instrument.response_fields
    )


def test_a_switch_to_locked_with_fields_takes_them_whole(client: TestClient, db: Session) -> None:
    created = _set_up(client, db)
    settings = _settings(COMMENT, SCORE, mode="locked")
    reply = _resend(client, created, _update_bundle(files=_with(settings)))
    assert reply.status_code == 200, reply.text
    assert _order(db) == ["comment", "score"]
    # Locked: required is the gate's again.
    assert _fields(db)["comment"].required


def test_a_switch_to_custom_keeps_everything(client: TestClient, db: Session) -> None:
    created = _custom(client, db, mode="locked")
    before = _order(db)
    reply = _resend(client, created, _update_bundle(files=_with(_settings(mode="custom"))))
    assert reply.status_code == 200, reply.text
    assert _instrument(db).linked_mode == "custom" and _order(db) == before


def test_a_sent_key_naming_an_own_field_is_refused(client: TestClient, db: Session) -> None:
    """Codex on #4219: a new field keyed as one Review Robin added would
    overwrite it and hold it; the re-send is refused, nothing written."""
    created = _set_up(client, db)
    clash = ("familiarity", "Familiarity", "text", "String", "", "", "")
    reply = _resend(client, created, _update_bundle(files=_with(_settings(SCORE, COMMENT, clash))))
    assert reply.status_code == 422 and reply.json()["slot"] == "settings"
    assert "Review Robin added" in reply.json()["details"][0]
    fields = _fields(db)
    assert fields["familiarity"]._inline_data_type == "Integer"
    assert fields["score"].branch_parent_id == fields["familiarity"].id
    assert _instrument(db).held_field_keys == ["score", "comment"]
