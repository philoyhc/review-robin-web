"""Process in the database (segment AD2C rung 4, `applydesk/process_store.py`):
the timeline saved whole and loaded back as the pages read it; keys kept
across saves and never reused; a stale save, a rule naming what the
snapshot drops, a gate's rule reading a gate, reversed dates and a
published stage's removal refused; each save audited."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from applydesk import db, process_save, process_store, stages
from applydesk.models import AuditEvent, Exercise
from applydesk.models import Gate as GateRow
from applydesk.process_store import Refused

SAMPLES = tuple(stages._STAGES)  # pyright: ignore[reportPrivateUsage]  -- every sample timeline
MODEL = "wa9juxbc2t"


@pytest.fixture
def session() -> Iterator[Session]:
    s = db.new_session()
    yield s
    s.close()


def _built(public_id: str) -> tuple[stages.Stage, ...]:
    return stages.plan_of(public_id).stages


def _as_read(public_id: str, built: tuple[stages.Stage, ...]) -> list[object]:
    """What the pages read of a timeline: each stage's own settings, and
    each gate and outcome as `fields_of`, `sources_of` and the rules show
    them, keys included."""
    out: list[object] = []
    for st in built:
        out.append((st.name, st.when, st.form, st.status, st.shown, st.form_when))
        for c in st.columns:
            if isinstance(c, stages.Gate):
                n = process_store._normalized(public_id, c)  # pyright: ignore[reportPrivateUsage]
                out.append(
                    (
                        n.key,
                        n.label,
                        n.mode,
                        n.description,
                        n.confidential,
                        n.when,
                        n.rule,
                        n.fields,
                        tuple(
                            (r.key, r.name, r.derive, r.value, r.at_least, r.source)
                            for r in n.results
                        ),
                        stages.sources_of(public_id, n),
                    )
                )
            else:
                out.append((c.key, c.label, c.values, c.due_at, c.weights, c.rule))
    return out


def _save(session: Session, public_id: str, built: tuple[stages.Stage, ...]) -> int:
    revision = session.scalar(
        select(Exercise.process_revision).where(Exercise.public_id == public_id)
    )
    saved = process_store.save(session, public_id, built, revision or 0, None)
    session.commit()
    return saved


@pytest.mark.parametrize("public_id", SAMPLES)
def test_every_sample_timeline_round_trips(session: Session, public_id: str) -> None:
    built = _built(public_id)
    assert process_store.load(session, public_id) is None  # never saved
    assert _save(session, public_id, built) == 1
    stored = process_store.load(session, public_id)
    assert stored is not None and stored.revision == 1
    assert _as_read(public_id, stored.stages) == _as_read(public_id, built)
    # Stages took keys; a second save keeps them.
    keys = [st.key for st in stored.stages]
    assert all(keys) and len(set(keys)) == len(keys)
    assert _save(session, public_id, stored.stages) == 2
    again = process_store.load(session, public_id)
    assert again is not None and [st.key for st in again.stages] == keys


def test_a_stale_save_is_refused(session: Session) -> None:
    built = _built(MODEL)
    _save(session, MODEL, built)
    with pytest.raises(Refused) as stale:
        process_store.save(session, MODEL, built, 0, None)  # opened before the first save
    assert stale.value.key == "stale"


def test_a_removed_gate_is_retired_and_its_key_never_reused(session: Session) -> None:
    built = _built(MODEL)
    _save(session, MODEL, built)
    stored = process_store.load(session, MODEL)
    assert stored is not None
    first = next(c for st in stored.stages for c in st.columns if isinstance(c, stages.Gate))
    # Drop the first gate and every rule or weight naming it.
    trimmed = _without(stored.stages, first.key)
    _save(session, MODEL, trimmed)
    row = session.scalar(select(GateRow).where(GateRow.key == first.key))
    assert row is not None and row.retired_at is not None
    assert first.key in process_store.taken_keys(session, MODEL)
    reloaded = process_store.load(session, MODEL)
    assert reloaded is not None
    assert first.key not in {c.key for st in reloaded.stages for c in st.columns}
    # Bringing it back under its old key is refused: a link to it must not
    # reach something new.
    with pytest.raises(Refused) as reused:
        process_store.save(session, MODEL, stored.stages, 2, None)
    assert reused.value.key == "keys"


def _without(built: tuple[stages.Stage, ...], gate_key: str) -> tuple[stages.Stage, ...]:
    def clean(c: stages.Gate | stages.Outcome) -> stages.Gate | stages.Outcome:
        if isinstance(c, stages.Outcome):
            weights = tuple(w for w in c.weights if stages.split_key(w[0])[0] != gate_key)
            rule = c.rule
            if rule and any(
                stages.split_key(key)[0] == gate_key
                for when, _ in rule.branches
                for _k, key, _o, _v in when
            ):
                rule = None
            return replace(c, weights=weights, rule=rule)
        return c

    return tuple(
        replace(st, columns=tuple(clean(c) for c in st.columns if c.key != gate_key))
        for st in built
    )


def test_a_rule_naming_a_dropped_gate_is_refused(session: Session) -> None:
    built = _built(MODEL)
    outcome = next(
        c
        for st in built
        for c in st.columns
        if isinstance(c, stages.Outcome)
        and c.rule
        and any(k in ("res", "top") for when, _ in c.rule.branches for k, *_ in when)
    )
    read = next(
        stages.split_key(key)[0]
        for when, _ in (outcome.rule.branches if outcome.rule else ())
        for k, key, _o, _v in when
        if k in ("res", "top")
    )
    dropped = tuple(
        replace(st, columns=tuple(c for c in st.columns if c.key != read)) for st in built
    )
    with pytest.raises(Refused) as gone:
        process_store.save(session, MODEL, dropped, 0, None)
    assert gone.value.key == "rule_target"
    assert "no longer" in str(gone.value)


def test_a_gates_rule_reading_a_gate_is_refused(session: Session) -> None:
    built = _built(MODEL)
    gates = [c for st in built for c in st.columns if isinstance(c, stages.Gate)]
    reading = replace(
        gates[1], rule=stages.Rule((("res", f"{gates[0].key}.r1", "ge", "3"),), "Entered", "")
    )
    changed = tuple(
        replace(st, columns=tuple(reading if c.key == reading.key else c for c in st.columns))
        for st in built
    )
    with pytest.raises(Refused) as scope:
        process_store.save(session, MODEL, changed, 0, None)
    assert scope.value.key == "rule_scope"


def test_reversed_dates_are_refused(session: Session) -> None:
    built = _built(MODEL)
    backwards = stages.StageDates(datetime(2026, 9, 30), datetime(2026, 9, 1))
    changed = (replace(built[0], when=backwards), *built[1:])
    with pytest.raises(Refused) as dates:
        process_store.save(session, MODEL, changed, 0, None)
    assert dates.value.key == "dates"


def test_a_published_stage_is_not_removed_by_a_save(session: Session) -> None:
    built = _built(MODEL)
    published = tuple(replace(st, status="Published") for st in built)
    _save(session, MODEL, published)
    stored = process_store.load(session, MODEL)
    assert stored is not None
    last = stored.stages[-1]
    keep = tuple(
        st for st in stored.stages if st.key != last.key
    )  # the outcome's stage may be read by none: drop the last
    with pytest.raises(Refused) as published_gone:
        process_store.save(session, MODEL, _drop_reads(keep, last), 1, None)
    assert published_gone.value.key == "published"


def _drop_reads(built: tuple[stages.Stage, ...], gone: stages.Stage) -> tuple[stages.Stage, ...]:
    keys = {c.key for c in gone.columns}
    out = built
    for key in keys:
        out = _without(out, key)
    return out


def test_each_save_is_audited_with_its_counts(session: Session) -> None:
    _save(session, MODEL, _built(MODEL))
    event = session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "exercise.process_saved")
    ).one()
    counts = event.detail["counts"]
    built = _built(MODEL)
    assert counts["stages"] == len(built)
    assert counts["gates"] == sum(isinstance(c, stages.Gate) for st in built for c in st.columns)
    assert event.detail["context"]["revision"] == 1


def test_outcome_values_keep_their_keys_by_label(session: Session) -> None:
    built = _built(MODEL)
    _save(session, MODEL, built)
    from applydesk.models import OutcomeValue

    before = {v.label: v.key for v in session.scalars(select(OutcomeValue))}
    stored = process_store.load(session, MODEL)
    assert stored is not None
    _save(session, MODEL, stored.stages)
    after = {
        v.label: v.key
        for v in session.scalars(select(OutcomeValue).where(OutcomeValue.retired_at.is_(None)))
    }
    assert after == before
    assert (
        session.scalar(select(func.count()).select_from(OutcomeValue))
        == len(before)  # nothing new minted for the same labels
    )


def test_a_weight_in_a_superscript_digit_is_refused() -> None:
    """AD-129: ``"²".isdigit()`` holds and ``int`` refuses it."""
    with pytest.raises(process_save.Refused):
        process_save._outcome(  # pyright: ignore[reportPrivateUsage]
            {"key": "o1", "label": "Shortlist", "values": ["Yes"], "weights": {"g1": "²"}}, 1
        )
