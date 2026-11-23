"""An exercise's timeline in the database (segment AD2C): loaded into the
dataclasses the pages read (`applydesk/stages.py`), and saved whole from
them, replacing the draft (ruling 23).

A save runs under the exercise's row lock, guarded by
``exercise.process_revision`` (ruling 74, as Details is): a page opened
before another save is refused, never merged. Gates, outcomes and stages
keep their keys across saves (ruling 37); a key the snapshot drops is
retired with its row, never reused. A rule naming a gate, result or
outcome the snapshot drops is refused, the rule and the target named
(AD-62), as is a gate's rule reading a gate. What the Outline flags
instead (a value not among a list's options, an outcome read before it
is decided) is saved as left, and flagged again (``stages.rule_problems``).

Outcome values are rows keyed per outcome (AD-57): rules store their
keys, and a value keeps its key while its label stands. The Process page
edits an outcome's values as one list of labels, so a renamed label is a
new value (a new key) and the old one is retired; a rule still naming the
old label is flagged until edited (``stages.rule_problems``). Carrying a
value's key through a rename waits on a values editor that holds keys
(Codex on #4154). The pages keep reading labels, which load and save
translate. A sample gate's fields and sources, read by
``stages.fields_of`` and ``stages.sources_of`` until edited, are saved as
rows of their own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from applydesk import audit, db, sample_data, stages
from applydesk.models import (
    Exercise,
    GateField,
    GateResult,
    GateSource,
    Outcome,
    OutcomeValue,
    OutcomeWeight,
    Person,
)
from applydesk.models import Gate as GateRow
from applydesk.models import Stage as StageRow

#: Rule conditions that read a gate: an outcome's alone (a gate never
#: reads a gate, ruling 13).
GATE_READS = frozenset({"res", "ent", "comb", "top"})


class Refused(Exception):
    """A save that cannot be kept, said to the operator; ``key`` names it."""

    def __init__(self, message: str, key: str = "refused") -> None:
        super().__init__(message)
        self.key = key


def _now() -> datetime:
    return datetime.now(UTC)


def _exercise(session: Session, public_id: str, *, lock: bool = False) -> Exercise:
    query = select(Exercise).where(Exercise.public_id == public_id, Exercise.deleted_at.is_(None))
    # Under the lock, the row as committed now: a copy the session already
    # holds may carry an older revision (Codex on #4154).
    found = session.scalar(
        query.with_for_update().execution_options(populate_existing=True) if lock else query
    )
    if found is None:
        raise Refused("That exercise is no longer on record.", key="gone")
    return found


# --- Rules as JSON (AD-62) -------------------------------------------------

Cond = tuple[str, str, str, str]


def _value_in(value: str, keys: dict[str, str]) -> Any:
    """An outcome value as stored: its key where it is one of the
    outcome's values, else the text as left (the Outline flags it)."""
    return {"value": keys[value]} if value in keys else value


def _value_out(stored: Any, labels: dict[str, str]) -> str:
    if isinstance(stored, dict):
        return labels.get(str(cast(dict[str, Any], stored).get("value", "")), "")
    return str(stored)


def rule_json(
    rule: stages.Rule | None,
    own: dict[str, str],
    values: dict[str, dict[str, str]],
) -> dict[str, Any] | None:
    """``rule`` as stored: each branch's conditions and value, and the
    value otherwise. ``own`` maps the column's own values (an outcome's)
    label to key; ``values`` every outcome's, for an ``out`` condition."""
    if rule is None:
        return None

    def cond(c: Cond) -> list[Any]:
        kind, key, op, value = c
        if kind == "out":
            return [kind, key, op, _value_in(value, values.get(key, {}))]
        return [kind, key, op, value]

    return {
        "branches": [
            {"when": [cond(c) for c in when], "then": _value_in(then, own)}
            for when, then in rule.branches
        ],
        "otherwise": _value_in(rule.otherwise, own),
    }


def rule_of(
    data: dict[str, Any] | None,
    own: dict[str, str],
    values: dict[str, dict[str, str]],
) -> stages.Rule | None:
    """The stored rule as the pages read it: values back to labels."""
    if not data:
        return None

    def cond(c: list[Any]) -> Cond:
        kind, key, op, value = (c + ["", "", "", ""])[:4]
        if kind == "out":
            return (str(kind), str(key), str(op), _value_out(value, values.get(str(key), {})))
        return (str(kind), str(key), str(op), str(value))

    branches = [
        (tuple(cond(list(c)) for c in b.get("when", [])), _value_out(b.get("then", ""), own))
        for b in cast(list[dict[str, Any]], data.get("branches", []))
    ]
    if not branches:
        return None
    first_when, first_then = branches[0]
    return stages.Rule(
        first_when, first_then, _value_out(data.get("otherwise", ""), own), tuple(branches[1:])
    )


def check_references(
    built: tuple[stages.Stage, ...], questions: dict[str, sample_data.ListQuestion]
) -> None:
    """Refuse a rule naming what the snapshot does not hold (AD-62), a
    question the form no longer asks as a List question (``questions``,
    by key: segment AD2D), or a gate's rule reading a gate; other
    problems are the Outline's."""
    plan = stages.Plan(built, ())
    cols = {c.key: c for c in plan.columns}
    for column in plan.columns:
        rule = column.rule
        name = column.label or ("Gate" if isinstance(column, stages.Gate) else "Outcome")
        # An outcome's weights are checked whether or not it has a rule
        # (Codex on #4154).
        for when, _ in rule.branches if rule else ():
            for kind, key, _op, _value in when:
                if kind in GATE_READS and isinstance(column, stages.Gate):
                    raise Refused(
                        f"{name}'s rule reads a gate: a gate's rule may not.", key="rule_scope"
                    )
                if kind == "form" and key not in questions:
                    raise Refused(
                        f"{name}'s rule reads a question the form no longer asks as a"
                        " choose-one List question.",
                        key="rule_target",
                    )
                if kind == "out" and not isinstance(cols.get(key), stages.Outcome):
                    raise Refused(
                        f"{name}'s rule reads an outcome no longer in the process.",
                        key="rule_target",
                    )
                if kind in ("res", "top", "ent"):
                    gate, result = (
                        stages.result_of(plan, key) if kind != "ent" else (cols.get(key), None)
                    )
                    if not isinstance(gate, stages.Gate):
                        raise Refused(
                            f"{name}'s rule reads a gate no longer in the process.",
                            key="rule_target",
                        )
                    if kind != "ent" and result is None:
                        raise Refused(
                            f"{name}'s rule reads a result no longer on {gate.label}.",
                            key="rule_target",
                        )
        if isinstance(column, stages.Outcome):
            for key, _weight in column.weights:
                gate, result = stages.result_of(plan, key)
                if gate is None:
                    raise Refused(
                        f"{name} weighs a gate no longer in the process.", key="rule_target"
                    )
                if result is None:
                    raise Refused(
                        f"{name} weighs a result no longer on {gate.label}.", key="rule_target"
                    )


# --- Load ------------------------------------------------------------------


@dataclass(frozen=True)
class Stored:
    """An exercise's saved timeline, as the pages read it, and the
    revision a save names."""

    stages: tuple[stages.Stage, ...]
    revision: int


def _live[T](rows: list[T]) -> list[T]:
    return [r for r in rows if getattr(r, "retired_at", None) is None]


def load(session: Session, public_id: str) -> Stored | None:
    """The timeline Process last saved, else None (never saved: the pages
    keep the sample's, or a new exercise's single stage)."""
    exercise = session.scalar(select(Exercise).where(Exercise.public_id == public_id))
    if exercise is None or exercise.process_revision < 1:
        return None
    rows = _live(
        list(
            session.scalars(
                select(StageRow)
                .where(StageRow.exercise_id == exercise.id)
                .order_by(StageRow.position)
            )
        )
    )
    gates = _live(
        list(
            session.scalars(
                select(GateRow).where(GateRow.exercise_id == exercise.id).order_by(GateRow.position)
            )
        )
    )
    outcomes = _live(
        list(session.scalars(select(Outcome).where(Outcome.exercise_id == exercise.id)))
    )
    gate_ids = [g.id for g in gates]
    outcome_ids = [o.id for o in outcomes]
    fields = _live(
        list(
            session.scalars(
                select(GateField)
                .where(GateField.gate_id.in_(gate_ids))
                .order_by(GateField.position)
            )
        )
    )
    results = _live(
        list(
            session.scalars(
                select(GateResult)
                .where(GateResult.gate_id.in_(gate_ids))
                .order_by(GateResult.position)
            )
        )
    )
    sources = list(
        session.scalars(
            select(GateSource).where(GateSource.gate_id.in_(gate_ids)).order_by(GateSource.rank)
        )
    )
    values = _live(
        list(
            session.scalars(
                select(OutcomeValue)
                .where(OutcomeValue.outcome_id.in_(outcome_ids))
                .order_by(OutcomeValue.position)
            )
        )
    )
    weights = list(
        session.scalars(select(OutcomeWeight).where(OutcomeWeight.outcome_id.in_(outcome_ids)))
    )
    gate_key = {g.id: g.key for g in gates}
    value_labels: dict[int, dict[str, str]] = {}
    for v in values:
        value_labels.setdefault(v.outcome_id, {})[v.key] = v.label
    by_outcome_key = {o.key: value_labels.get(o.id, {}) for o in outcomes}
    field_by_id = {f.id: f for f in fields}

    def field_def(f: GateField) -> stages.Field:
        return stages.Field(f.type, f.min, f.max, f.step, f.options)

    def gate_of(g: GateRow, number: int) -> stages.Gate:
        own_fields = tuple(
            stages.ResponseField(f.key, f.label, field_def(f), f.required, f.help)
            for f in fields
            if f.gate_id == g.id
        )
        own_results: list[stages.GateResult] = []
        for r in (r for r in results if r.gate_id == g.id):
            src = field_by_id.get(r.field_id) if r.field_id is not None else None
            own_results.append(
                stages.GateResult(
                    r.key,
                    r.name,
                    field_def(src) if src else stages.Field(),
                    r.derive,
                    r.value,
                    r.at_least,
                    src.key if src else "",
                    r.ignore_zero,
                )
            )
        total = (
            stages.Total(g.total_min or 0, g.total_max or 0)
            if g.total_min is not None or g.total_max is not None
            else None
        )
        return stages.Gate(
            g.key,
            number,
            g.label,
            g.via,
            tuple(own_results),
            rule_of(g.rule, {}, by_outcome_key),
            sources=tuple(
                stages.Source(s.kind, s.ref, s.min, s.max, s.all_members)
                for s in sources
                if s.gate_id == g.id
            ),
            total=total,
            mode=g.mode,
            description=g.description,
            confidential=g.confidential,
            fields=own_fields,
            when=_dates(g.review_from, g.review_to),
            own_fields=True,
        )

    def outcome_of(o: Outcome, number: int) -> stages.Outcome:
        own = value_labels.get(o.id, {})
        return stages.Outcome(
            o.key,
            number,
            o.label,
            tuple(own.values()),
            _naive(o.due_at),
            "",
            tuple(
                (gate_key[w.gate_id] + (f".{w.result_key}" if w.result_key else ""), w.weight)
                for w in weights
                if w.outcome_id == o.id
            ),
            rule_of(o.rule, own, by_outcome_key),
            value_keys=tuple(own.keys()),
        )

    built: list[stages.Stage] = []
    gates_n = outcomes_n = 0
    for st in rows:
        columns: list[stages.Gate | stages.Outcome] = []
        for g in (g for g in gates if g.stage_id == st.id):
            gates_n += 1
            columns.append(gate_of(g, gates_n))
        for o in (o for o in outcomes if o.stage_id == st.id):
            outcomes_n += 1
            columns.append(outcome_of(o, outcomes_n))
        built.append(
            stages.Stage(
                st.position,
                st.name or "",
                _dates(st.starts_at, st.ends_at),
                tuple(columns),
                st.holds_form,
                "Published" if st.status == "published" else "Draft",
                st.shown,
                _dates(st.form_opens_at, st.form_closes_at) if st.holds_form else None,
                key=st.key,
                candidates=st.holds_candidates,
            )
        )
    return Stored(tuple(built), exercise.process_revision)


def _naive(at: datetime | None) -> datetime | None:
    """A stored time as the pages hold it: the exercise's wall clock,
    without a zone (``stages.StageDates``, segment AD1K)."""
    # Read back in UTC first: a timestamptz comes back in the database
    # session's zone (the cold read on rungs 2-5).
    if at is None:
        return None
    return at.astimezone(UTC).replace(tzinfo=None) if at.tzinfo else at


def _stored(at: datetime | None) -> datetime | None:
    return at.replace(tzinfo=UTC) if at is not None and at.tzinfo is None else at


def _dates(start: datetime | None, end: datetime | None) -> stages.StageDates | None:
    if start is None or end is None:
        return None
    return stages.StageDates(_naive(start) or start, _naive(end) or end)


def stored_stages(public_id: str) -> tuple[stages.Stage, ...] | None:
    """The stages Process last saved for the exercise, read in a session of
    its own (``stages.plan_of``, which no route hands a session); None if
    never saved."""
    session = db.new_session()
    try:
        found = load(session, public_id)
    finally:
        session.close()
    return found.stages if found is not None else None


def revision(public_id: str) -> int:
    """How many times Process has saved the exercise: a page sends the one
    it opened at, and a save from an older one is refused (``save``)."""
    session = db.new_session()
    try:
        held = session.scalar(
            select(Exercise.process_revision).where(Exercise.public_id == public_id)
        )
    finally:
        session.close()
    return held or 0


# --- Save ------------------------------------------------------------------


def taken_keys(session: Session, public_id: str) -> frozenset[str]:
    """Every gate, outcome and stage key the exercise has ever held, retired
    ones too, and a sample's own (its cells are keyed by them until AD2F
    stores cells, so a new gate must not take one): a new key is minted
    past them (ruling 37)."""
    keys: set[str] = set(stages.sample_keys(public_id))
    exercise = session.scalar(select(Exercise).where(Exercise.public_id == public_id))
    if exercise is None:
        return frozenset(keys)
    for model in (StageRow, GateRow, Outcome):
        keys |= set(session.scalars(select(model.key).where(model.exercise_id == exercise.id)))
    return frozenset(keys)


def _normalized(public_id: str, gate: stages.Gate) -> stages.Gate:
    """A gate as stored: its fields and sources its own (a sample gate's,
    read by ``fields_of`` and ``sources_of``, become rows), each result
    naming its field by key."""
    fields = stages.fields_of(gate)
    results: list[stages.GateResult] = []
    for r in gate.results:
        source = stages.source_field(gate, r)
        results.append(
            stages.GateResult(
                r.key,
                r.name,
                r.field,
                r.derive,
                r.value,
                r.at_least,
                source.key if source else "",
                r.ignore_zero,
            )
        )
    sources, total = stages.sources_of(public_id, gate)
    if not gate.sources:
        # A sample gate naming only a panel reads it whole (ruling 62).
        sources = tuple(
            stages.Source(s.kind, s.ref, s.min, s.max, s.all_members or s.kind == "panel")
            for s in sources
        )
    return stages.Gate(
        gate.key,
        gate.number,
        gate.label,
        gate.via,
        tuple(results),
        gate.rule,
        sources=gate.sources or sources,
        total=gate.total or (total if sources else None),
        mode=gate.mode,
        description=gate.description,
        confidential=gate.confidential,
        fields=fields,
        when=gate.when,
        own_fields=True,
    )


def _check(built: tuple[stages.Stage, ...], questions: dict[str, sample_data.ListQuestion]) -> None:
    if not built:
        raise Refused("A process has at least one stage.", key="no_stage")
    shape = stages.problems(built)
    if shape:
        raise Refused(shape[0], key="shape")
    for st in built:
        spans = [st.when, st.form_when] + [c.when for c in st.columns if isinstance(c, stages.Gate)]
        if any(s is not None and not s.valid for s in spans):
            raise Refused(f"{st.label} has dates ending before they start.", key="dates")
    keys = [c.key for st in built for c in st.columns]
    if len(set(keys)) < len(keys):
        raise Refused("Two gates or outcomes share a key.", key="keys")
    stage_keys = [st.key for st in built if st.key]
    if len(set(stage_keys)) < len(stage_keys):
        raise Refused("Two stages share a key.", key="keys")
    # A value is keyed by its label (AD-57): two alike would be one row
    # (Codex on #4154).
    for c in (c for st in built for c in st.columns if isinstance(c, stages.Outcome)):
        twice = next((v for i, v in enumerate(c.values) if v in c.values[:i]), None)
        if twice is not None:
            name = c.label or "An outcome"
            raise Refused(f"{name} has two values called \u201c{twice}\u201d.", key="values")
    check_references(built, questions)


def _changed_locked(row: StageRow, st: stages.Stage) -> bool:
    """Whether what the page locks on a published stage differs in the
    snapshot: its name, its start and whether applicants see it. Its end
    stays editable, an extension keeping it open (ruling 35)."""
    starts = _stored(st.when.start) if st.when else None
    return (
        (row.name or "") != (st.name or "")
        or _naive(row.starts_at) != _naive(starts)
        or row.shown != st.shown
    )


def _adds_to(
    row: StageRow,
    st: stages.Stage,
    gate_rows: dict[str, GateRow],
    outcome_rows: dict[str, Outcome],
) -> bool:
    """Whether the snapshot puts on a published stage a gate, an outcome or
    the form it did not hold: the page disables its adds (ruling 35)."""
    if st.form and not row.holds_form:
        return True
    for c in st.columns:
        held = gate_rows.get(c.key) if isinstance(c, stages.Gate) else outcome_rows.get(c.key)
        if held is not None and held.retired_at is not None:
            continue  # a retired key brought back: refused as such below
        if held is None or held.stage_id != row.id:
            return True
    return False


def _upsert[R: (StageRow, GateRow, Outcome, GateField, GateResult, OutcomeValue)](
    session: Session,
    existing: dict[str, R],
    key: str,
    make: type[R],
    *,
    revive: bool = False,
    **values: Any,
) -> R:
    """The row under ``key``, made or updated. A stage's, gate's or
    outcome's key is never given again (ruling 37: a link to it must not
    reach something new), so a retired one is refused. A gate's field or
    result is part of its gate: nothing outside the snapshot names it, the
    rules and weights that do are checked at save, and the page mints the
    lowest free key, so a retired one is revived (the cold read on rungs
    2-5: refusing it left Process unsaveable)."""
    row = existing.get(key)
    if row is None:
        row = make(key=key, **values)
        session.add(row)
    else:
        if row.retired_at is not None:
            if not revive:
                raise Refused(f"The key {key} belonged to something removed.", key="keys")
            row.retired_at = None
        for name, value in values.items():
            setattr(row, name, value)
    return row


def _retire_missing[R: (StageRow, GateRow, Outcome, GateField, GateResult, OutcomeValue)](
    existing: dict[str, R], kept: set[str], at: datetime
) -> int:
    gone = 0
    for key, row in existing.items():
        if key not in kept and row.retired_at is None:
            row.retired_at = at
            gone += 1
    return gone


def save(
    session: Session,
    public_id: str,
    built: tuple[stages.Stage, ...],
    opened: int,
    actor: Person | None,
) -> int:
    """Keep ``built`` as the exercise's timeline, replacing the draft, if
    no save came between (``opened``, the revision the page loaded); the
    new revision. Flushed, not committed: the caller's transaction holds
    the change and its audit."""
    exercise = _exercise(session, public_id, lock=True)
    if exercise.archived_at is not None:
        raise Refused("Archived: restore it to change it.", key="archived")
    if opened != exercise.process_revision:
        raise Refused(
            "Not saved: Process was saved since this page opened. Reload to see it.",
            key="stale",
        )
    # A form condition is stored by its question's key (segment AD2D): a
    # page opened before keys names a label, kept as the key it maps to.
    questions = sample_data.list_questions(public_id)
    built = stages.form_keyed(built, public_id)
    _check(built, questions)
    at = _now()
    stage_rows = {
        r.key: r
        for r in session.scalars(select(StageRow).where(StageRow.exercise_id == exercise.id))
    }
    gate_rows = {
        r.key: r for r in session.scalars(select(GateRow).where(GateRow.exercise_id == exercise.id))
    }
    outcome_rows = {
        r.key: r for r in session.scalars(select(Outcome).where(Outcome.exercise_id == exercise.id))
    }
    published_gone = [
        r
        for k, r in stage_rows.items()
        if r.retired_at is None and r.status == "published" and k not in {s.key for s in built}
    ]
    if published_gone:
        raise Refused(
            f"{published_gone[0].name or 'A published stage'} is published: revert it to draft "
            "before removing it.",
            key="published",
        )
    taken = set(stage_rows)
    minted = 0

    def stage_key(st: stages.Stage) -> str:
        nonlocal minted
        if st.key:
            return st.key
        while True:
            minted += 1
            candidate = f"s{minted}"
            if candidate not in taken:
                taken.add(candidate)
                return candidate

    # Outcome values first: rules everywhere name them by key.
    outcome_keys: dict[str, dict[str, str]] = {}
    for st in built:
        for c in st.columns:
            if isinstance(c, stages.Outcome):
                row = outcome_rows.get(c.key)
                had = (
                    {
                        v.label: v.key
                        for v in session.scalars(
                            select(OutcomeValue).where(
                                OutcomeValue.outcome_id == row.id,
                                OutcomeValue.retired_at.is_(None),
                            )
                        )
                    }
                    if row is not None
                    else {}
                )
                used: set[str] = (
                    set(
                        session.scalars(
                            select(OutcomeValue.key).where(OutcomeValue.outcome_id == row.id)
                        )
                    )
                    if row is not None
                    else set[str]()
                )
                keys: dict[str, str] = {}
                n = 0
                # Each label takes, in turn: the live key the page carried
                # beside it (a value renamed keeps its key), else its own
                # label's key if no other label carried it, else a new one.
                # Carried keys go first, so a row's order cannot hand its
                # key to another (AD-57).
                live = set(had.values())
                for label, carried in zip(c.values, c.value_keys, strict=False):
                    if carried in live and carried not in keys.values():
                        keys[label] = carried
                for label in c.values:
                    if label in keys:
                        continue
                    if label in had and had[label] not in keys.values():
                        keys[label] = had[label]
                        continue
                    while True:
                        n += 1
                        if f"v{n}" not in used:
                            break
                    used.add(f"v{n}")
                    keys[label] = f"v{n}"
                outcome_keys[c.key] = keys

    kept_stages: set[str] = set()
    kept_gates: set[str] = set()
    kept_outcomes: set[str] = set()
    counts = {"stages": 0, "gates": 0, "outcomes": 0}
    reverted: list[tuple[StageRow, str]] = []
    # The form's state, and when it opened and closed, go with it to
    # another stage (the cold read; Codex on #4161): a move is not a
    # reopening. A form removed in one save and added back in a later one
    # takes the state its last holder recorded, retired or not, the
    # furthest along if more than one did.
    recorded = [r for r in stage_rows.values() if r.form_state]
    holder = [r for r in recorded if r.holds_form and r.retired_at is None]
    last = holder or sorted(recorded, key=lambda r: _FORM_ORDER.get(r.form_state or "", 0))[-1:]
    form_was = (
        (last[0].form_state, last[0].form_opened_at, last[0].form_closed_at) if last else None
    )
    for position, st in enumerate(built, 1):
        key = stage_key(st)
        kept_stages.add(key)
        counts["stages"] += 1
        before = stage_rows.get(key)
        if before is not None and before.status == "published":
            # Ruling 35: what the page locks on a published stage, the save
            # refuses too; reverting it to draft is its own audited move.
            if st.status == "Published" and _changed_locked(before, st):
                raise Refused(
                    f"{st.label} is published: revert it to draft to change its name, "
                    "start or who sees it.",
                    key="published",
                )
            if st.status == "Published" and _adds_to(before, st, gate_rows, outcome_rows):
                raise Refused(
                    f"{st.label} is published: revert it to draft to add to it.",
                    key="published",
                )
            if st.status != "Published":
                reverted.append((before, st.revert_reason))
        srow = _upsert(
            session,
            stage_rows,
            key,
            StageRow,
            exercise_id=exercise.id,
            position=position,
            name=st.name or None,
            starts_at=_stored(st.when.start) if st.when else None,
            ends_at=_stored(st.when.end) if st.when else None,
            status="published" if st.status == "Published" else "draft",
            shown=st.shown,
            holds_form=st.form,
            holds_candidates=st.candidates,
            form_opens_at=_stored(st.form_when.start) if st.form and st.form_when else None,
            form_closes_at=_stored(st.form_when.end) if st.form and st.form_when else None,
        )
        if st.form and form_was is not None:
            srow.form_state, srow.form_opened_at, srow.form_closed_at = form_was
        elif st.form:
            srow.form_state = srow.form_state or _form_seed(public_id)
        session.flush()
        gate_position = 0
        for c in st.columns:
            if isinstance(c, stages.Gate):
                gate_position += 1
                counts["gates"] += 1
                kept_gates.add(c.key)
                _save_gate(
                    session,
                    exercise,
                    srow,
                    gate_rows,
                    _normalized(public_id, c),
                    gate_position,
                    outcome_keys,
                    at,
                )
            else:
                counts["outcomes"] += 1
                kept_outcomes.add(c.key)
                orow = _upsert(
                    session,
                    outcome_rows,
                    c.key,
                    Outcome,
                    exercise_id=exercise.id,
                    stage_id=srow.id,
                    label=c.label,
                    due_at=_stored(c.due_at),
                    rule=rule_json(c.rule, outcome_keys.get(c.key, {}), outcome_keys),
                )
                session.flush()
                _save_values(session, orow, c, outcome_keys.get(c.key, {}), at)
    session.flush()
    # Weights last: they name gates saved above.
    gate_ids = {
        r.key: r.id
        for r in session.scalars(select(GateRow).where(GateRow.exercise_id == exercise.id))
    }
    for st in built:
        for c in st.columns:
            if isinstance(c, stages.Outcome):
                orow = outcome_rows.get(c.key) or session.scalar(
                    select(Outcome).where(Outcome.exercise_id == exercise.id, Outcome.key == c.key)
                )
                assert orow is not None
                session.execute(delete(OutcomeWeight).where(OutcomeWeight.outcome_id == orow.id))
                merged: dict[tuple[int, str], float] = {}
                for wkey, weight in c.weights:
                    gate_part, _, result_part = wkey.partition(".")
                    merged[(gate_ids[gate_part], result_part)] = weight
                for (gid, result_key), weight in merged.items():
                    session.add(
                        OutcomeWeight(
                            outcome_id=orow.id, gate_id=gid, result_key=result_key, weight=weight
                        )
                    )
    retired = (
        _retire_missing(stage_rows, kept_stages, at)
        + _retire_missing(gate_rows, kept_gates, at)
        + _retire_missing(outcome_rows, kept_outcomes, at)
    )
    exercise.process_revision += 1
    session.flush()
    audit.write_event(
        session,
        event_type="exercise.process_saved",
        actor=actor,
        exercise=exercise,
        payload=audit.counts(**counts, retired=retired),
        context={"revision": exercise.process_revision},
    )
    for row, why in reverted:
        audit.write_event(
            session,
            event_type="exercise.stage_reverted",
            actor=actor,
            exercise=exercise,
            reason=why or None,
            refs={"stage_id": row.id},
        )
    return exercise.process_revision


def _save_gate(
    session: Session,
    exercise: Exercise,
    srow: StageRow,
    gate_rows: dict[str, GateRow],
    gate: stages.Gate,
    position: int,
    outcome_keys: dict[str, dict[str, str]],
    at: datetime,
) -> None:
    total = gate.total
    grow = _upsert(
        session,
        gate_rows,
        gate.key,
        GateRow,
        exercise_id=exercise.id,
        stage_id=srow.id,
        position=position,
        label=gate.label,
        via=gate.via or "RRW",
        description=gate.description,
        confidential=gate.confidential,
        mode=gate.mode,
        total_min=total.min if total else None,
        total_max=total.max if total else None,
        review_from=_stored(gate.when.start) if gate.when else None,
        review_to=_stored(gate.when.end) if gate.when else None,
        rule=rule_json(gate.rule, {}, outcome_keys),
    )
    session.flush()
    fields = {
        f.key: f for f in session.scalars(select(GateField).where(GateField.gate_id == grow.id))
    }
    for n, f in enumerate(gate.fields, 1):
        _upsert(
            session,
            fields,
            f.key,
            GateField,
            revive=True,
            gate_id=grow.id,
            position=n,
            label=f.label,
            type=f.field.type,
            min=f.field.min,
            max=f.field.max,
            step=f.field.step,
            options=f.field.options,
            required=f.required,
            help=f.help,
        )
    _retire_missing(fields, {f.key for f in gate.fields}, at)
    session.flush()
    field_ids = {
        f.key: f.id
        for f in session.scalars(
            select(GateField).where(GateField.gate_id == grow.id, GateField.retired_at.is_(None))
        )
    }
    results = {
        r.key: r for r in session.scalars(select(GateResult).where(GateResult.gate_id == grow.id))
    }
    for n, r in enumerate(gate.results, 1):
        _upsert(
            session,
            results,
            r.key,
            GateResult,
            revive=True,
            gate_id=grow.id,
            position=n,
            name=r.name,
            field_id=field_ids.get(r.source),
            derive=r.derive,
            value=r.value,
            at_least=r.at_least,
            ignore_zero=r.ignore_zero,
        )
    _retire_missing(results, {r.key for r in gate.results}, at)
    session.execute(delete(GateSource).where(GateSource.gate_id == grow.id))
    for rank, s in enumerate(gate.sources, 1):
        session.add(
            GateSource(
                gate_id=grow.id,
                rank=rank,
                kind=s.kind,
                ref=s.ref,
                min=s.min,
                max=s.max,
                all_members=s.all_members,
            )
        )


def _save_values(
    session: Session, orow: Outcome, outcome: stages.Outcome, keys: dict[str, str], at: datetime
) -> None:
    rows = {
        v.key: v
        for v in session.scalars(select(OutcomeValue).where(OutcomeValue.outcome_id == orow.id))
    }
    # Every value but the last takes an application on; a single value is
    # itself (``stages.going_on``; Codex on #4154).
    advancing = set(stages.going_on(outcome))
    for n, label in enumerate(outcome.values, 1):
        key = keys[label]
        row = rows.get(key)
        if row is None:
            session.add(
                OutcomeValue(
                    outcome_id=orow.id,
                    key=key,
                    position=n,
                    label=label,
                    advances=label in advancing,
                )
            )
        else:
            row.position, row.label, row.advances, row.retired_at = (
                n,
                label,
                label in advancing,
                None,
            )
    for key, row in rows.items():
        if key not in set(keys.values()) and row.retired_at is None:
            row.retired_at = at


# --- The form's moves (ruling 76) ---------------------------------------------


def _form_seed(public_id: str) -> str:
    """The state a form takes when its stage is first stored: a draft
    exercise's is a draft; a published one's is open or closed as the
    exercise had it (the sample's ``form_open``), so a save changes
    nothing the pages showed."""
    from applydesk import sample_data

    e = sample_data.sample(public_id)  # an ordinary exercise is a Draft; no read
    if e is None or e.state == "Draft":
        return "draft"
    return "open" if e.form_open else "closed"


#: The form's state on its stage, and the moves Home's next step makes:
#: only forward, draft to open to closed (ruling 24; reopening is not in
#: the MVP).
FORM_MOVES = {"open": "draft", "closed": "open"}
#: How far along each state is: a form only moves forward.
_FORM_ORDER = {"draft": 0, "open": 1, "closed": 2}


def form_state(session: Session, public_id: str) -> str | None:
    """The stored form's state ("draft", "open" or "closed"), None while
    the timeline is not stored or holds no form."""
    exercise = session.scalar(select(Exercise).where(Exercise.public_id == public_id))
    if exercise is None or exercise.process_revision < 1:
        return None
    row = session.scalar(
        select(StageRow).where(
            StageRow.exercise_id == exercise.id,
            StageRow.holds_form.is_(True),
            StageRow.retired_at.is_(None),
        )
    )
    return row.form_state if row is not None else None


def move_form(
    session: Session, public_id: str, to: str, published: bool, actor: Person | None
) -> None:
    """Open or close the application form (ruling 76): ``to`` is "open"
    or "closed", from the state before it only; opening needs the
    exercise published (ruling 24). A timeline never saved is recorded
    first, as Process would save it. Audited; flushed, not committed."""
    if to not in FORM_MOVES:
        raise ValueError(to)
    exercise = _exercise(session, public_id, lock=True)
    if exercise.archived_at is not None:
        raise Refused("Archived: restore it to change it.", key="archived")
    if to == "open" and not published:
        raise Refused("A draft's form opens once the exercise is published.", key="draft")
    if exercise.process_revision < 1:
        try:
            save(session, public_id, stages.plan_of(public_id).stages, 0, actor)
        except Refused as why:
            raise Refused(str(why), key="unsaved") from why
    row = session.scalar(
        select(StageRow).where(
            StageRow.exercise_id == exercise.id,
            StageRow.holds_form.is_(True),
            StageRow.retired_at.is_(None),
        )
    )
    if row is None:
        raise Refused("This exercise has no application form.", key="no_form")
    if (row.form_state or "draft") != FORM_MOVES[to]:
        said = {"open": "The form is open already.", "closed": "The form is not open."}[to]
        raise Refused(said, key="form_state")
    now = _now()
    row.form_state = to
    if to == "open":
        row.form_opened_at = now
    else:
        row.form_closed_at = now
    session.flush()
    if to == "open":
        audit.write_event(
            session, event_type="exercise.form_opened", actor=actor, exercise=exercise
        )
    else:
        audit.write_event(
            session, event_type="exercise.form_closed", actor=actor, exercise=exercise
        )
