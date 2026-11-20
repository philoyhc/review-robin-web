"""A stage's status and what it locks (segment AD1K, ruling 35).

A stage is Draft until the operator publishes it. Published, it locks
what it holds, every page reading the locks here so none disagrees with
another (AD-04). It is Completed once its declared end has passed and
every item in it is complete (author, 2026-11-18): its form closed, each
gate's results in, its outcome released. An item still open after the
end leaves it Overdue, saying what is outstanding. Moving the end later,
an extension, keeps it open or reopens it, so a stage's end and its
items' ends stay editable after publish. Sample data: nothing is saved
or audited until AD2.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from applydesk import sample_data, stages, timeline, tones, workflow
from applydesk.sample_data import Exercise

#: The sample's now: midday of its today (the model exercise is mid
#: Stage 3, ruling 30).
NOW = datetime.combine(timeline.TODAY, time(12))


@dataclass(frozen=True)
class Lock:
    """Whether a part is fixed, and the reason a disabled control gives."""

    fixed: bool
    reason: str = ""
    # A released outcome's owed emails: open now, they bar a re-release.
    owed: str = ""
    # Fixed by an opened Review Robin session, which a revert leaves be
    # (ruling 29), rather than by its stage.
    opened: bool = False


OPEN = Lock(False)

#: Each status's chip on the pages, from the one map (ruling 64, U1).
STATUS_CHIP = {s: tones.tone(s) for s in ("Draft", "Published", "Overdue", "Completed")}


def _item_open(e: Exercise, st: stages.Stage, item: stages.Gate | stages.Outcome | None) -> str:
    """What keeps an item from complete, in words; "" when it is complete.
    ``None`` is the stage's form."""
    if item is None:
        return "" if workflow.form_state(e) == "Closed" else "the form is still open"
    if isinstance(item, stages.Gate):
        state, _ = workflow.gate_sent(e.public_id, item.key)
        return "" if state == "Results in" else f"{item.label or 'a gate'}'s results are not in"
    return "" if item.released else f"{item.label or 'the outcome'} is not released"


def outstanding(e: Exercise, st: stages.Stage) -> tuple[str, ...]:
    """What in the stage is not yet complete, in words."""
    items: list[stages.Gate | stages.Outcome | None] = [None] if st.form else []
    items += list(st.columns)
    return tuple(why for why in (_item_open(e, st, i) for i in items) if why)


def stage_status(e: Exercise, st: stages.Stage, now: datetime = NOW) -> str:
    """Draft, Published, Overdue or Completed (ruling 35; Semantics)."""
    if st.status != "Published":
        return "Draft"
    if st.when is None or not st.when.valid or now <= st.when.end:
        return "Published"
    return "Overdue" if outstanding(e, st) else "Completed"


def exercise_status(e: Exercise, now: datetime = NOW) -> str:
    """The exercise's status from its stages: Draft until one is
    published, Completed when every one is, else Published. Closed and
    Archived stay ``Exercise.state``'s until AD3."""
    if e.state in ("Closed", "Archived"):
        return e.state
    plan = stages.plan_of(e.public_id)
    states = [stage_status(e, st, now) for st in plan.stages]
    if all(s == "Draft" for s in states):
        return "Draft"
    return "Completed" if all(s == "Completed" for s in states) else "Published"


def publish_problems(e: Exercise, st: stages.Stage) -> tuple[str, ...]:
    """What keeps a stage from being published (AD-20): its dates, the
    stage before it, Home's details for the first, its form, and its
    gates' and outcomes' setup as Process's Outline names them."""
    plan = stages.plan_of(e.public_id)
    out: list[str] = []
    if st.when is None:
        out.append(f"{st.label} has no start and end.")
    elif not st.when.valid:
        out.append(f"{st.label} ends before it starts.")
    out += stages.date_problems(plan, st)
    before = [s for s in plan.stages if s.number < st.number]
    if before and before[-1].status != "Published":
        out.append(f"{before[-1].label} is not published yet.")
    if not before:
        out += [
            f"{label} is not set." for label, page in sample_data.setup_missing(e) if page == ""
        ]
    if st.form and sample_data.form_is_empty(e.public_id):
        out.append("The application form has no questions.")
    forms = sample_data.list_questions(e.public_id)
    pools = sample_data.panel_pools(e.public_id)
    for c in st.columns:
        if isinstance(c, stages.Gate):
            name = f"Gate {c.number} ({c.label or 'untitled'})"
            sources, total = stages.sources_of(e.public_id, c)
            why = stages.total_problem(sources, total)
            if why == "no evaluators":
                out.append(f"{name} has no evaluators.")
            elif why:
                out.append(f"{name}: {why}.")
            # Each source must give evaluators too (Codex).
            out += [f"{name}: {p}." for p in stages.source_problems(sources, pools)]
        else:
            name = c.label or "The outcome"
            if not c.values:
                out.append(f"{name} has no values.")
        # Process's Outline checks (Codex): what the rule reads must hold.
        out += [f"{name}'s rule {why}." for why in stages.rule_problems(plan, c, forms)]
    return tuple(out)


def _published(e: Exercise, st: stages.Stage) -> Lock:
    if st.status != "Published":
        return OPEN
    return Lock(True, f"{st.label} is published: revert it to draft to change this")


def stage_lock(e: Exercise, st: stages.Stage) -> Lock:
    """A stage's start, name, whether applicants see it, its order and
    deletion (author, 2026-11-18); its end is ``end_lock``'s."""
    return _published(e, st)


def end_lock(e: Exercise, st: stages.Stage) -> Lock:
    """A stage's end and its items' ends: never fixed, an extension being
    how a stage is kept open or reopened (author, 2026-11-18)."""
    return OPEN


def form_lock(e: Exercise) -> Lock:
    """The application form, fixed once the stage holding it is published."""
    st = stages.plan_of(e.public_id).form_stage
    return _published(e, st) if st else OPEN


def _stage_of(e: Exercise, key: str) -> stages.Stage | None:
    return next(
        (st for st in stages.plan_of(e.public_id).stages if any(c.key == key for c in st.columns)),
        None,
    )


def item_lock(e: Exercise, item: stages.Gate | stages.Outcome) -> Lock:
    """A gate's or an outcome's settings and removal: fixed once its
    stage is published; a gate whose Review Robin session has opened
    stays fixed even after a revert (ruling 29)."""
    if isinstance(item, stages.Gate):
        state, line = workflow.gate_sent(e.public_id, item.key)
        if workflow.gate_opened(state, line):
            return Lock(
                True,
                "Its Review Robin session has opened: the gate keeps its settings",
                opened=True,
            )
    st = _stage_of(e, item.key)
    return _published(e, st) if st else OPEN


def cells_lock(e: Exercise, gate: stages.Gate) -> Lock:
    """A gate's entries on Dossiers: fixed once its session has opened,
    as Process says (AD-04)."""
    state, line = workflow.gate_sent(e.public_id, gate.key)
    if workflow.gate_opened(state, line):
        return Lock(True, "Its Review Robin session has opened: who it entered is fixed")
    return OPEN


def release_lock(e: Exercise, outcome: stages.Outcome) -> Lock:
    """An outcome's Released switch (AD-21): off while an email its release
    sends is owed on Emails. A release already made can be withdrawn."""
    owed = [m.name for m in workflow.outcome_emails(e.public_id, outcome.key) if not m.ok]
    why = "Write its emails on Emails first: " + "; ".join(owed) if owed else ""
    if outcome.released:
        # Withdrawn and released again, it waits on them too (Codex).
        return Lock(False, owed=why)
    return Lock(True, why) if owed else OPEN


def blind_lock(e: Exercise) -> Lock:
    """Blind review, fixed once the first stage holding a gate is
    published (author, 2026-11-18; AD-05)."""
    plan = stages.plan_of(e.public_id)
    for st in plan.stages:
        if st.status == "Published" and any(isinstance(c, stages.Gate) for c in st.columns):
            return Lock(True, "A stage holding a gate is published: blind review is fixed")
    return OPEN


def revert_warnings(e: Exercise, st: stages.Stage) -> tuple[str, ...]:
    """What a revert to draft leaves as it is (author, 2026-11-18): an
    opened gate stays fixed; submitted applications stay submitted."""
    out: list[str] = []
    for c in st.columns:
        if isinstance(c, stages.Gate):
            state, line = workflow.gate_sent(e.public_id, c.key)
            if workflow.gate_opened(state, line):
                out.append(f"Gate {c.number}'s Review Robin session has opened: it stays fixed.")
    if st.form:
        n = workflow.counts_of(e.public_id).submitted  # the one count (AD-41)
        if n:
            stays = "application stays" if n == 1 else "applications stay"
            out.append(f"{n:,} submitted {stays} submitted.")
    return tuple(out)


@dataclass(frozen=True)
class StageRow:
    """A stage as the timeline's operator part shows it (segment AD1K):
    its status; for a draft, what blocks publishing, the first stage's
    setup linked to where each is set (``setup``, page and label); for an
    overdue one, what it still waits on."""

    stage: stages.Stage
    status: str
    blocking: tuple[str, ...]
    setup: tuple[tuple[str, str], ...]
    waiting: tuple[str, ...]


def stage_rows(exercise: Exercise) -> list[StageRow]:
    """Each stage's row for the timeline's operator part."""
    plan = stages.plan_of(exercise.public_id).stages
    missing = sample_data.setup_missing(exercise)
    # The first stage's setup is listed with links to where each is set;
    # its problems leave out what that list says.
    linked = {f"{label} is not set." for label, _ in missing}
    if any(label == "Dates" for label, _ in missing) and plan:
        linked.add(f"{plan[0].label} has no start and end.")
    if any(label == "Application form" for label, _ in missing):
        linked.add("The application form has no questions.")
    rows: list[StageRow] = []
    for i, st in enumerate(plan):
        status = stage_status(exercise, st)
        draft = status == "Draft"
        blocking = publish_problems(exercise, st) if draft else ()
        setup: tuple[tuple[str, str], ...] = ()
        if i == 0 and draft:
            blocking = tuple(p for p in blocking if p not in linked)
            setup = tuple(missing)
        waiting = outstanding(exercise, st) if status == "Overdue" else ()
        rows.append(StageRow(st, status, blocking, setup, waiting))
    return rows
