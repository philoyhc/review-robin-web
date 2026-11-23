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


def test_a_stale_save_is_refused_though_the_session_holds_the_exercise(
    session: Session,
) -> None:
    """Codex on #4154: a session that loaded the exercise before another
    saved reads the committed revision under the lock, not its own copy."""
    built = _built(MODEL)
    _save(session, MODEL, built)  # revision 1, the exercise now in this session
    held = session.scalar(select(Exercise).where(Exercise.public_id == MODEL))
    assert held is not None and held.process_revision == 1  # kept, as a caller would
    stored = process_store.load(session, MODEL)
    assert stored is not None
    # Its copy of the exercise kept past the commit (SQLite allows one
    # writer, so this session's read ends first): still at revision 1.
    session.expire_on_commit = False
    session.commit()
    other = db.new_session()
    try:
        process_store.save(other, MODEL, stored.stages, 1, None)
        other.commit()  # revision 2
    finally:
        other.close()
    with pytest.raises(Refused) as stale:
        process_store.save(session, MODEL, stored.stages, 1, None)
    assert stale.value.key == "stale" and held.process_revision == 2


def test_a_weight_on_a_gate_dropped_is_refused_without_a_rule(session: Session) -> None:
    """Codex on #4154: an outcome decided by hand still has its weights
    checked; one naming a dropped gate is refused, not saved dangling."""
    built = _built(MODEL)
    weighed = next(
        c for st in built for c in st.columns if isinstance(c, stages.Outcome) and c.weights
    )
    gone = stages.split_key(weighed.weights[0][0])[0]
    changed = tuple(
        replace(
            st,
            columns=tuple(
                replace(c, rule=None) if c.key == weighed.key else c
                for c in st.columns
                if c.key != gone
            ),
        )
        for st in built
    )
    changed = tuple(
        replace(
            st,
            columns=tuple(
                replace(c, rule=None)
                if isinstance(c, stages.Outcome) and c.key != weighed.key and c.rule
                else c
                for c in st.columns
            ),
        )
        for st in changed
    )
    with pytest.raises(Refused) as dangling:
        process_store.save(session, MODEL, changed, 0, None)
    assert dangling.value.key == "rule_target" and "weighs" in str(dangling.value)


def test_a_single_outcome_value_advances(session: Session) -> None:
    """Codex on #4154: as ``stages.going_on`` reads it, a lone value takes
    an application on; with several, every one but the last does."""
    from applydesk.models import OutcomeValue

    built = _built(MODEL)
    first = next(c for st in built for c in st.columns if isinstance(c, stages.Outcome))
    lone = tuple(
        replace(
            st,
            columns=tuple(
                replace(c, values=("Go",), rule=None) if c.key == first.key else c
                for c in st.columns
            ),
        )
        for st in built
    )
    _save(session, MODEL, lone)
    rows = {v.label: v.advances for v in session.scalars(select(OutcomeValue))}
    assert rows["Go"] is True
    others = [
        c for st in built for c in st.columns if isinstance(c, stages.Outcome) and c is not first
    ]
    for o in others:
        assert [rows[v] for v in o.values] == [True] * (len(o.values) - 1) + [False]


def test_an_outcome_with_a_value_twice_is_refused(session: Session) -> None:
    """Codex on #4154: values are keyed by label, so a repeated one is
    refused, not left to fail the transaction on a duplicate key."""
    built = _built(MODEL)
    first = next(c for st in built for c in st.columns if isinstance(c, stages.Outcome))
    twice = tuple(
        replace(
            st,
            columns=tuple(
                replace(c, values=("Yes", "Yes"), rule=None) if c.key == first.key else c
                for c in st.columns
            ),
        )
        for st in built
    )
    with pytest.raises(Refused) as refused:
        process_store.save(session, MODEL, twice, 0, None)
    assert refused.value.key == "values" and "Yes" in str(refused.value)


def test_a_field_or_result_removed_then_added_again_saves(session: Session) -> None:
    """The cold read on rungs 2-5: the page mints a gate's lowest free field
    key and the next result key, so a removed one comes back; its row is
    revived, not refused (which left Process unsaveable)."""
    built = _built(MODEL)
    _save(session, MODEL, built)
    stored = process_store.load(session, MODEL)
    assert stored is not None
    gate = next(
        c
        for st in stored.stages
        for c in st.columns
        if isinstance(c, stages.Gate) and len(c.fields) > 1 and len(c.results) > 1
    )
    last_field, last_result = gate.fields[-1], gate.results[-1]
    fewer = replace(
        gate,
        fields=gate.fields[:-1],
        results=tuple(
            replace(r, source="", derive="") if r.source == last_field.key else r
            for r in gate.results[:-1]
        ),
    )

    def with_gate(g: stages.Gate) -> tuple[stages.Stage, ...]:
        return tuple(
            replace(st, columns=tuple(g if c.key == g.key else c for c in st.columns))
            for st in stored.stages
        )

    trimmed = _without_reads(with_gate(fewer), f"{gate.key}.{last_result.key}")
    _save(session, MODEL, trimmed)
    # Added again under the same keys, as the page mints them.
    again = process_store.load(session, MODEL)
    assert again is not None
    back = tuple(
        replace(st, columns=tuple(gate if c.key == gate.key else c for c in st.columns))
        for st in again.stages
    )
    _save(session, MODEL, back)
    reloaded = process_store.load(session, MODEL)
    assert reloaded is not None
    got = next(c for st in reloaded.stages for c in st.columns if c.key == gate.key)
    assert isinstance(got, stages.Gate)
    assert [f.key for f in got.fields] == [f.key for f in gate.fields]
    assert [r.key for r in got.results] == [r.key for r in gate.results]


def _without_reads(built: tuple[stages.Stage, ...], result: str) -> tuple[stages.Stage, ...]:
    """Every rule and weight reading ``result`` ("g1.r2") dropped."""

    def clean(c: stages.Gate | stages.Outcome) -> stages.Gate | stages.Outcome:
        if not isinstance(c, stages.Outcome):
            return c
        rule = c.rule
        if rule and any(key == result for when, _ in rule.branches for _k, key, _o, _v in when):
            rule = None
        return replace(c, rule=rule, weights=tuple(w for w in c.weights if w[0] != result))

    return tuple(replace(st, columns=tuple(clean(c) for c in st.columns)) for st in built)


def test_a_stored_time_reads_back_as_utc_wall_clock() -> None:
    """The cold read on rungs 2-5: a timestamptz comes back in the database
    session's zone; the pages' wall clock is the UTC one stored."""
    from datetime import timedelta, timezone

    stored = datetime(2027, 1, 4, 9, 0)
    elsewhere = process_store._stored(stored).astimezone(timezone(timedelta(hours=8)))  # pyright: ignore[reportOptionalMemberAccess, reportPrivateUsage]
    assert process_store._naive(elsewhere) == stored  # pyright: ignore[reportPrivateUsage]


def test_a_weight_in_a_superscript_digit_is_refused() -> None:
    """AD-129: ``"²".isdigit()`` holds and ``int`` refuses it."""
    with pytest.raises(process_save.Refused):
        process_save._outcome(  # pyright: ignore[reportPrivateUsage]
            {"key": "o1", "label": "Shortlist", "values": ["Yes"], "weights": {"g1": "²"}}, 1
        )


def _with_values(
    built: tuple[stages.Stage, ...], key: str, values: tuple[str, ...], value_keys: tuple[str, ...]
) -> tuple[stages.Stage, ...]:
    return tuple(
        replace(
            st,
            columns=tuple(
                replace(c, values=values, value_keys=value_keys, rule=None) if c.key == key else c
                for c in st.columns
            ),
        )
        for st in built
    )


def test_a_renamed_value_keeps_its_key(session: Session) -> None:
    """The values editor (AD-57): a value renamed on Process carries its key,
    so the stored row is relabelled rather than retired and minted anew."""
    from applydesk.models import OutcomeValue

    _save(session, MODEL, _built(MODEL))
    stored = process_store.load(session, MODEL)
    assert stored is not None
    first = next(c for st in stored.stages for c in st.columns if isinstance(c, stages.Outcome))
    assert len(first.value_keys) == len(first.values) and all(first.value_keys)
    renamed = ("Renamed", *first.values[1:])
    _save(session, MODEL, _with_values(stored.stages, first.key, renamed, first.value_keys))
    again = process_store.load(session, MODEL)
    assert again is not None
    now = next(c for st in again.stages for c in st.columns if c.key == first.key)
    assert isinstance(now, stages.Outcome)
    assert now.values == renamed and now.value_keys == first.value_keys
    assert (
        session.scalar(
            select(func.count())
            .select_from(OutcomeValue)
            .where(OutcomeValue.label == first.values[0])
        )
        == 0
    )


def test_a_new_value_named_as_a_renamed_one_takes_a_new_key(session: Session) -> None:
    """A value renamed away and a new value under its old label, the new one
    listed first: the carried key stays with the renamed value."""
    _save(session, MODEL, _built(MODEL))
    stored = process_store.load(session, MODEL)
    assert stored is not None
    first = next(c for st in stored.stages for c in st.columns if isinstance(c, stages.Outcome))
    old, k = first.values[0], first.value_keys[0]
    values = (old, "Renamed", *first.values[1:])
    value_keys = ("", k, *first.value_keys[1:])
    _save(session, MODEL, _with_values(stored.stages, first.key, values, value_keys))
    again = process_store.load(session, MODEL)
    assert again is not None
    now = next(c for st in again.stages for c in st.columns if c.key == first.key)
    assert isinstance(now, stages.Outcome)
    got = dict(zip(now.values, now.value_keys, strict=True))
    assert got["Renamed"] == k and got[old] not in first.value_keys


def test_value_keys_are_read_from_the_snapshot() -> None:
    """`process_save` reads each value's key beside it; a blank value drops
    with its key, and a malformed key is refused."""
    from applydesk.process_save import Refused as SaveRefused

    raw = {
        "key": "o1",
        "label": "Decide",
        "values": ["Yes", "", "No"],
        "value_keys": ["v1", "v9", ""],
    }
    got = process_save._outcome(raw, 1)  # pyright: ignore[reportPrivateUsage]
    assert got.values == ("Yes", "No") and got.value_keys == ("v1", "")
    with pytest.raises(SaveRefused):
        process_save._outcome({**raw, "value_keys": ["v1"]}, 1)  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(SaveRefused):
        process_save._outcome({**raw, "value_keys": ["bad key", "", ""]}, 1)  # pyright: ignore[reportPrivateUsage]
