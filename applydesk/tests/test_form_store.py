"""The form in the database (segment AD2D rung 3, `applydesk/form_store.py`):
the form saved whole and loaded back as the pages read it; keys kept through
a rename, minted by the server and never reused; a stale save, a published
form and a bad snapshot refused; each save audited."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from applydesk import db, form_store, sample_data
from applydesk.form_store import Refused
from applydesk.models import AuditEvent, Exercise
from applydesk.models import FormCard as CardRow

MODEL = "wa9juxbc2t"
POOLS = ("institution",)


@pytest.fixture
def session() -> Iterator[Session]:
    s = db.new_session()
    yield s
    s.close()


def _sample() -> list[dict[str, Any]]:
    return [asdict(c) for c in sample_data.sample_form(MODEL)]


def _revision(session: Session) -> int:
    return session.scalar(select(Exercise.form_revision).where(Exercise.public_id == MODEL)) or 0


def _save(session: Session, cards: list[dict[str, Any]], title: str = "Apply") -> int:
    form = form_store.parse(
        {"title": title, "description": "", "cards": cards},
        sample_data.people_pools(MODEL),
        {},
    )
    got = form_store.save(session, MODEL, form, _revision(session), None, published=False)
    session.commit()
    return got


def _keys(session: Session) -> list[str]:
    stored = form_store.load(session, MODEL)
    assert stored is not None
    return [c.key for c in stored.cards]


def test_nothing_is_stored_until_the_first_save(session: Session) -> None:
    assert form_store.load(session, MODEL) is None
    assert form_store.revision(MODEL) == 0


def test_a_sample_s_first_save_keeps_its_keys_and_loads_back_as_sent(session: Session) -> None:
    sent = _sample()
    assert _save(session, sent, title="  The RA form ") == 1
    stored = form_store.load(session, MODEL)
    assert stored is not None
    assert stored.title == "The RA form"
    assert stored.cards == sample_data.sample_form(MODEL)
    assert [c.key for c in stored.cards] == [f"q{n}" for n in range(1, len(sent) + 1)]
    event = session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "exercise.form_saved")
    ).one()
    fields = sum(1 for c in sent if c["kind"] == "field")
    assert event.detail["counts"] == {"cards": len(sent), "fields": fields, "retired": 0}


def test_a_rename_keeps_the_key_and_a_new_card_passes_every_key_held(session: Session) -> None:
    sent = _sample()
    held = len(sent)
    _save(session, sent)
    renamed = [{**sent[1], "label": "Renamed"}, *sent[2:]]  # the first card dropped
    _save(session, [*renamed, {**sent[1], "key": "", "label": "New"}])
    keys = _keys(session)
    assert keys[0] == "q2"  # renamed, same key
    assert keys[-1] == f"q{held + 1}"  # past the sample's keys
    retired = session.scalars(select(CardRow).where(CardRow.key == "q1")).one()
    assert retired.retired_at is not None
    # The dropped card's key is never revived, even if a page sends it.
    _save(session, [{**sent[0], "key": "q1"}, *renamed])
    assert _keys(session)[0] == f"q{held + 2}"


def test_a_card_copied_with_its_key_is_given_its_own(session: Session) -> None:
    sent = _sample()
    _save(session, sent)
    _save(session, [*sent, {**sent[1], "label": "Copy"}])
    keys = _keys(session)
    assert keys[1] == "q2" and keys[-1] not in keys[:-1]


def test_sections_and_page_breaks_are_keyed_too(session: Session) -> None:
    _save(session, [{"kind": "section", "label": "A"}, {"kind": "pagebreak"}])
    stored = form_store.load(session, MODEL)
    assert stored is not None
    assert [(c.kind, bool(c.key)) for c in stored.cards] == [("section", True), ("pagebreak", True)]


def test_a_stale_save_is_refused(session: Session) -> None:
    _save(session, _sample())
    form = form_store.parse({"title": "", "description": "", "cards": []}, POOLS, {})
    with pytest.raises(Refused) as why:
        form_store.save(session, MODEL, form, 0, None, published=False)
    assert why.value.key == "stale"


def test_a_published_form_is_refused(session: Session) -> None:
    form = form_store.parse({"title": "", "description": "", "cards": []}, POOLS, {})
    with pytest.raises(Refused) as why:
        form_store.save(session, MODEL, form, 0, None, published=True)
    assert why.value.key == "published"
    session.rollback()
    assert form_store.load(session, MODEL) is None


def _field(**over: Any) -> dict[str, Any]:
    return {**asdict(sample_data.FormCard("field")), **over}


@pytest.mark.parametrize(
    ("sent", "said"),
    [
        ([], "malformed"),
        ({"title": 1, "description": "", "cards": []}, "malformed"),
        ({"title": "x" * 201, "description": "", "cards": []}, "title is at most 200"),
        ({"title": "", "description": "", "cards": [_field()] * 201}, "at most 200 cards"),
        ({"title": "", "description": "", "cards": [{"kind": ["field"]}]}, "no known kind"),
        ({"title": "", "description": "", "cards": [_field(type="essay")]}, "not one of"),
        ({"title": "", "description": "", "cards": [_field(label="x" * 501)]}, "too long"),
        ({"title": "", "description": "", "cards": [_field(required="yes")]}, "malformed"),
        ({"title": "", "description": "", "cards": [_field(key=7)]}, "malformed"),
        ({"title": "", "description": "", "cards": [_field(pool="panel-99")]}, "no panel"),
    ],
)
def test_a_bad_snapshot_is_refused(sent: Any, said: str) -> None:
    with pytest.raises(Refused, match=said):
        form_store.parse(sent, POOLS, {})


def test_a_page_s_new_panel_is_named_by_its_stored_key() -> None:
    form = form_store.parse(
        {"title": "", "description": "", "cards": [_field(type="people", pool="new-1")]},
        POOLS,
        {"new-1": "panel-7"},
    )
    assert form["cards"][0]["pool"] == "panel-7"
