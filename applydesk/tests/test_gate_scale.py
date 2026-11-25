"""A gate's response field as Review Robin's scale (segment AD2S rung 2,
`applydesk/guide/segment_AD2S_gate_scale.md`): the flag and its labels
saved and read back, a List or a String keeping neither, and a scale
Review Robin would refuse named and blocking its stage's publishing."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from applydesk import db, locks, process_save, process_store, sample_data, stages
from applydesk.models import Exercise

RA = "wa9juxbc2t"


def _scale(**kw: Any) -> stages.Field:
    return stages.Field(
        **{"type": "integer", "min": "1", "max": "5", "step": "1", "scale": True, **kw}
    )


@pytest.mark.parametrize(
    ("field", "why"),
    [
        (_scale(), ""),
        (_scale(type="decimal", min="0", max="1", step="0.25"), ""),
        (_scale(type="decimal", min="0", max="0.3", step="0.1"), ""),  # float noise
        (_scale(scale=False, min="", max=""), ""),  # not a scale: nothing to say
        (_scale(type="list"), "is a scale but not an Integer or a Decimal"),
        (_scale(max=""), "is a scale with no Min or Max"),
        (_scale(step=""), "is a scale with no Step"),
        (_scale(step="0"), "is a scale with no Step"),
        (_scale(max="1"), "is a scale whose Max is not above its Min"),
        (_scale(step="0.5"), "is an Integer scale with a bound or Step not whole"),
        (_scale(max="6", step="2"), "is a scale whose Max is not Min plus a whole number of Steps"),
        (_scale(max="nan"), "is a scale with no Min or Max"),
        # A plain decimal only, as the page script reads one (the read).
        (_scale(max="1_0"), "is a scale with no Min or Max"),
        (_scale(max="0x10"), "is a scale with no Min or Max"),
        (_scale(max="inf"), "is a scale with no Min or Max"),
        (_scale(min="-1", max="1e1", step=".5", type="decimal"), ""),
    ],
)
def test_a_scale_s_bounds_are_checked_as_review_robin_does(field: stages.Field, why: str) -> None:
    assert stages.scale_problem(field) == why


def test_labels_are_trimmed_cut_and_blank_when_empty() -> None:
    assert stages.scale_labels(" Weak | | Strong ") == "Weak||Strong"
    assert stages.scale_labels("||") == ""
    assert stages.scale_labels("") == ""
    assert stages.scale_labels("a|b|c|d") == "a|b|c"
    assert stages.scale_labels("x" * 80) == "x" * stages.SCALE_LABEL_MAX + "||"


def _field_json(**kw: Any) -> dict[str, Any]:
    return {
        "key": "f1",
        "label": "Score",
        "type": "integer",
        "min": "1",
        "max": "5",
        "step": "1",
        "options": "",
        "required": True,
        "help": "",
        **kw,
    }


def test_save_reads_the_flag_and_cuts_the_labels() -> None:
    got = process_save._field_def(  # pyright: ignore[reportPrivateUsage]  -- the parser alone
        _field_json(scale=True, scale_labels="Weak|" + "y" * 70 + "|Strong"), "Gate 1's field"
    )
    assert got.scale and got.scale_labels == "Weak|" + "y" * 60 + "|Strong"
    # A page that sends no flag (before the card's rung) saves no scale.
    assert not process_save._field_def(_field_json(), "f").scale  # pyright: ignore[reportPrivateUsage]  -- as above


def test_a_list_or_a_string_keeps_no_scale() -> None:
    for kind in ("list", "string"):
        got = process_save._field_def(  # pyright: ignore[reportPrivateUsage]  -- the parser alone
            _field_json(type=kind, scale=True, scale_labels="a|b|c"), "f"
        )
        assert (got.scale, got.scale_labels) == (False, "")


def test_a_flag_not_a_boolean_is_refused() -> None:
    with pytest.raises(process_save.Refused, match="malformed"):
        process_save._field_def(_field_json(scale="yes"), "f")  # pyright: ignore[reportPrivateUsage]  -- the parser alone


@pytest.fixture
def session() -> Iterator[Session]:
    s = db.new_session()
    yield s
    s.close()


def test_a_scale_round_trips_through_the_database(session: Session) -> None:
    built = stages.plan_of(RA).stages
    gate = next(c for st in built for c in st.columns if isinstance(c, stages.Gate) and c.fields)
    first = gate.fields[0]
    scaled = replace(
        first, field=replace(first.field, type="integer", min="1", max="5", step="1",
                             scale=True, scale_labels="Weak||Strong")
    )  # fmt: skip
    changed = replace(gate, fields=(scaled, *gate.fields[1:]))
    with_scale = tuple(
        replace(st, columns=tuple(changed if c.key == gate.key else c for c in st.columns))
        for st in built
    )
    revision = session.scalar(select(Exercise.process_revision).where(Exercise.public_id == RA))
    process_store.save(session, RA, with_scale, revision or 0, None)
    session.commit()
    stored = process_store.load(session, RA)
    assert stored is not None
    back = next(c for st in stored.stages for c in st.columns if c.key == gate.key)
    assert isinstance(back, stages.Gate)
    assert (back.fields[0].field.scale, back.fields[0].field.scale_labels) == (True, "Weak||Strong")
    assert not any(f.field.scale for f in back.fields[1:])


def test_a_scale_review_robin_would_refuse_blocks_publishing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    e = sample_data.exercise(RA)
    assert e is not None
    model = stages._STAGES[RA]  # pyright: ignore[reportPrivateUsage]  -- a sample's shape
    interviews = model[2]
    g3, o2 = interviews.columns
    assert isinstance(g3, stages.Gate) and g3.fields
    bad = replace(g3.fields[0], field=_scale(max="6", step="2"))
    broken = replace(interviews, columns=(replace(g3, fields=(bad, *g3.fields[1:])), o2))
    monkeypatch.setitem(stages._STAGES, RA, (*model[:2], broken))  # pyright: ignore[reportPrivateUsage]  -- as above
    assert locks.publish_problems(e, broken) == (
        f"Gate 3 · Staff interview: field 1 ({bad.label}) is a scale whose Max is not"
        " Min plus a whole number of Steps.",
    )
    assert stages.field_problems(replace(g3, fields=(replace(bad, field=_scale()),))) == ()


# --- Rung 3: the card's texts, the handoff and the extract ---


def test_a_scale_reads_as_one_and_its_results_as_numbers() -> None:
    f = _scale(scale_labels="Weak||Strong")
    assert stages.field_text(f) == "Integer scale 1 to 5, step 1, labelled Weak / Strong"
    assert stages.field_text(replace(f, scale=False)) == "Integer 1 to 5, step 1"
    r = stages.GateResult("r1", "Score", f, "max")
    assert stages.result_type(r) == "Integer 1 to 5, step 1"
    assert stages.result_summary(r).startswith("Integer 1 to 5, step 1 · ")


def test_the_handoff_carries_the_flag_and_labels() -> None:
    from applydesk import handoff

    e = sample_data.exercise(RA)
    assert e is not None
    gate = stages.gate_numbered(stages.plan_of(RA), 3)
    assert gate is not None and len(gate.fields) > 1
    fields = (
        replace(gate.fields[0], field=_scale(scale_labels="Weak||Strong")),
        replace(gate.fields[1], field=_scale(type="decimal", min="0", max="1", step="0.1")),
        *gate.fields[2:],
    )
    rows = handoff.settings_csv(e, replace(gate, fields=fields)).splitlines()
    at = "instruments[1].response_fields"
    assert f"{at}[1].scale,true,boolean" in rows
    assert f"{at}[1].scale_labels,Weak||Strong,string" in rows
    assert f"{at}[1].data_type,Integer,string" in rows
    assert f"{at}[2].scale,true,boolean" in rows
    assert not any(r.startswith(f"{at}[2].scale_labels") for r in rows)  # none set
    assert not any(r.startswith(f"{at}[3].scale") for r in rows)


def test_the_page_offers_band_3_s_menu_and_marks_a_saved_scale(session: Session) -> None:
    from fastapi.testclient import TestClient

    from applydesk.tests._host import host_with

    built = stages.plan_of(RA).stages
    gate = next(c for st in built for c in st.columns if isinstance(c, stages.Gate) and c.fields)
    scaled = replace(gate.fields[0], field=_scale(scale_labels="Weak|Fair|"))
    changed = replace(gate, fields=(scaled, *gate.fields[1:]))
    revision = session.scalar(select(Exercise.process_revision).where(Exercise.public_id == RA))
    process_store.save(
        session,
        RA,
        tuple(
            replace(st, columns=tuple(changed if c.key == gate.key else c for c in st.columns))
            for st in built
        ),
        revision or 0,
        None,
    )
    session.commit()
    client = TestClient(host_with(("applydesk",))[0])
    page = client.get(f"/applydesk/operator/exercises/{RA}/process").text
    assert [label for _, label in stages.FIELD_CHOICES] == [
        "Integer",
        "Integer (scale)",
        "Decimal",
        "Decimal (scale)",
        "List",
        "String",
    ]
    assert '<option value="integer:scale" selected>Integer (scale)</option>' in page
    assert 'data-q="scale_start" maxlength="60" value="Weak"' in page
    assert 'data-q="scale_middle" maxlength="60" value="Fair"' in page
    assert "Integer scale 1 to 5, step 1, labelled Weak / Fair" in page
