"""The rule engine (segment AD2C rung 6, ruling 78): the one evaluator of
the rules Process sets on gates and outcomes. Dossiers' *Apply rules* asks
it what each column's rule would change in the table as it stands, and
shows the answer as a proposal; nothing changes until Apply.

Every column is taken in table order, so a rule reading an earlier outcome
sees the value this run gives it. A condition that cannot be judged yet
(a result not in, an outcome undecided, a ranking someone could still
join) leaves the cell as it is and names it. By default only undecided
cells are proposed, never one set by hand unless asked (segment AD1C).

The table comes in as ``Dossier`` rows: each submitted or withdrawn
application's cells, by column key, as the page holds them (its own hand
changes included, which the server has not seen), with the gate results
the server knows. Ranking, combining and the order of branches follow
ruling 30 and the comments on #3955.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from applydesk import stages
from applydesk.sample_data import Application
from applydesk.stages import Rule

#: A gate cell's values; "Not entered" leaves an application out of the gate.
NOT_ENTERED = "Not entered"
_UNKNOWN = "—"
_FLOAT = re.compile(r"\s*[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_INT = re.compile(r"\s*[+-]?\d+")


def _number(text: str) -> float:
    """A number read as a browser's ``parseFloat`` reads it: its leading
    digits, else not a number."""
    found = _FLOAT.match(text)
    return float(found.group()) if found else math.nan


def _whole(text: str) -> int | None:
    """A whole number read as ``parseInt`` reads it, else None."""
    found = _INT.match(text)
    return int(found.group()) if found else None


def undecided(value: str) -> bool:
    return value in (_UNKNOWN, "Pending", "")


@dataclass(frozen=True)
class Cell:
    """One cell: its value, the gate's results by key ("r1" first, as
    text), and whether a hand set it."""

    value: str
    results: Mapping[str, str] = field(default_factory=lambda: dict[str, str]())
    by_hand: bool = False


@dataclass(frozen=True)
class Dossier:
    """One application's row: its ID, its name on screen, its state, its
    place among the applicant's last submitted (None when not among them),
    its answers to the form's List questions, and its cells that can be
    set (a cell it has none of is absent)."""

    app: str
    name: str
    status: str
    rank: int | None
    answers: Mapping[str, str]
    cells: Mapping[str, Cell]


@dataclass(frozen=True)
class Column:
    """A gate or an outcome as the engine reads it: its rule, an
    outcome's gates in scope and its weights (``gate.result``, share),
    and whether its Review Robin session has opened (fixed)."""

    key: str
    kind: str  # "gate" or "outcome"
    label: str
    rule: Rule | None
    scope: tuple[str, ...] = ()
    weights: tuple[tuple[str, float], ...] = ()
    fixed: bool = False


@dataclass(frozen=True)
class Change:
    app: str
    key: str
    old: str
    new: str


@dataclass(frozen=True)
class Proposal:
    changes: tuple[Change, ...]
    skipped: tuple[str, ...]


def _gate_key(key: str) -> str:
    return key.split(".")[0]


def _result_at(cell: Cell | None, key: str) -> str | None:
    """The result a key names on a gate's cell ("g1.r2"); a bare gate key
    reads its first."""
    if cell is None:
        return None
    parts = key.split(".")
    return cell.results.get(parts[1] if len(parts) > 1 and parts[1] else "r1")


Value = Callable[[Dossier, str], "str | None"]


def combined(column: Column, row: Dossier, val: Value) -> float | None:
    """An outcome's combined result: the weighted average of the finished
    results it weighs. A gate the application was not entered into is
    left out and the rest rescaled; one entered with no result yet, or
    not yet decided, leaves it unknown (None), as an outcome with no
    weights or every weight at 0 does."""
    total = weight = 0.0
    for key, share in column.weights:
        if not share or math.isnan(share):
            continue  # weighed at 0%: no part in it
        gate = _gate_key(key)
        cell = row.cells.get(gate)
        value = val(row, gate)
        if cell is None or value == NOT_ENTERED:
            continue
        x = _result_at(cell, key)
        if value == _UNKNOWN or x is None:
            return None
        total += share * _number(x)
        weight += share
    if not weight:
        return None
    return math.floor(total / weight * 100 + 0.5) / 100


def propose(
    columns: Sequence[Column],
    rows: Sequence[Dossier],
    *,
    only_pending: bool,
    replace_hand: bool,
) -> Proposal:
    """What applying every column's rule would change, in column order,
    and what it left as is and why."""
    by_key = {c.key: c for c in columns}
    shadow: dict[tuple[str, str], str] = {}
    changes: list[Change] = []
    skipped: list[str] = []

    def val(row: Dossier, key: str) -> str | None:
        if (row.app, key) in shadow:
            return shadow[(row.app, key)]
        cell = row.cells.get(key)
        return cell.value if cell is not None else None

    def not_reached(row: Dossier, okey: str) -> bool:
        """An outcome none of whose gates the application entered."""
        scoped = by_key[okey].scope
        return bool(scoped) and all(val(row, g) in (None, NOT_ENTERED) for g in scoped)

    def holds(row: Dossier, cond: tuple[str, str, str, str], okey: str) -> bool | None:
        kind, key, op, want = cond

        def cmp(x: float) -> bool:
            t = _number(want)
            return x >= t if op == "ge" else x < t

        if kind == "status":
            return row.status == want
        if kind == "form":  # ruling 30: the answer to a List question
            return row.answers.get(key) == want
        if kind == "top":
            # Ranked across the branch; one not entered at the gate has no
            # place in it, so the branch fails it now (Codex on #3955).
            got = val(row, _gate_key(key))
            return got is not None and got != NOT_ENTERED
        if kind == "last":
            limit = _whole(want)
            return row.rank is not None and limit is not None and row.rank <= limit
        if kind in ("ent", "out"):
            got = val(row, key)
            if got is None:
                return False  # a cell this application has not
            if kind == "out" and got == "" and not_reached(row, key):
                return False
            if got != want and undecided(got):
                return None  # not decided yet: wait
            return got == want
        if kind == "res":
            gate = _gate_key(key)
            got, x = val(row, gate), _result_at(row.cells.get(gate), key)
            if got is None or got == NOT_ENTERED:
                return False
            if got == _UNKNOWN or x is None:
                return None
            return x == want if op == "is" else cmp(_number(x))  # a list is matched
        value = combined(by_key[okey], row, val)  # comb
        return cmp(value) if value is not None else None

    def sent_on(row: Dossier, okey: str, rule: Rule) -> bool:
        """A branch reading earlier outcomes and nothing of its own gates,
        all of whose conditions hold: it decides without the gates."""
        for when, _ in rule.branches:
            outs = [c for c in when if c[0] == "out"]
            if (
                outs
                and len(outs) == len([c for c in when if c[0] != "form"])
                and all(holds(row, c, okey) is True for c in when)
            ):
                return True
        return False

    for column in columns:
        rule = column.rule
        if rule is None:
            continue
        key = column.key
        if column.fixed:
            skipped.append(f"{column.label}: fixed, its Review Robin session has opened.")
            continue
        reach: list[Dossier] = []
        for row in rows:
            if key not in row.cells or row.status != "Submitted":
                continue  # a draft, a cell that cannot be set, a withdrawn one's own
            # An outcome none of whose gates it entered is not reached,
            # unless its cell is open or a branch takes it on an earlier
            # outcome alone (ruling 30: re-appointment skips the interview).
            if (
                column.kind == "outcome"
                and val(row, key) == ""
                and not_reached(row, key)
                and not sent_on(row, key, rule)
            ):
                continue
            reach.append(row)
        verdicts: dict[str, str | None] = {}
        left, held = list(reach), list[Dossier]()
        for when, then in rule.branches:
            tops = [c for c in when if c[0] == "top"]
            passing: list[Dossier] = []
            rest: list[Dossier] = []
            unsure: list[Dossier] = []

            def could_join(
                row: Dossier,
                when: tuple[tuple[str, str, str, str], ...] = when,
                key: str = key,
            ) -> bool:
                return all(holds(row, c, key) is not False for c in when)

            for row in left:
                verdict: bool | None = True
                for cond in when:
                    if verdict is False:
                        break
                    x = holds(row, cond, key)
                    if x is False:
                        verdict = False
                    elif x is None:
                        verdict = None
                if verdict is None:
                    verdicts[row.app] = None
                    unsure.append(row)
                elif verdict:
                    passing.append(row)
                else:
                    rest.append(row)
            for top in tops:
                if not passing:
                    continue
                gate = _gate_key(top[1])
                scored: list[tuple[Dossier, float]] = []
                for row in passing:
                    got, x = val(row, gate), _result_at(row.cells.get(gate), top[1])
                    if got is None or got == NOT_ENTERED:
                        rest.append(row)  # no place in its ranking: on to the next branch
                    elif got == _UNKNOWN or x is None:
                        scored.append((row, math.nan))
                    else:
                        scored.append((row, _number(x)))
                passing = [row for row, _ in scored]
                waiting = bool(unsure) or any(could_join(h) for h in held)
                if waiting or any(math.isnan(x) for _, x in scored):
                    for row in passing:
                        verdicts[row.app] = None
                        unsure.append(row)
                    passing = []
                    continue
                scored.sort(key=lambda s: -s[1])
                n = _whole(top[3]) or 0
                cut = scored[n - 1][1] if n > 0 and len(scored) > n else -math.inf
                kept = [s for i, s in enumerate(scored) if i < n or s[1] == cut]
                if len(kept) > n > 0:
                    skipped.append(f"{column.label}: {len(kept)} at the cut of {n}: tied.")
                keep = {row.app for row, _ in kept}
                rest += [row for row in passing if row.app not in keep]
                passing = [row for row in passing if row.app in keep]
            for row in passing:
                verdicts[row.app] = then
            held += unsure
            left = rest
        for row in left:
            verdicts[row.app] = rule.otherwise
        unjudged: list[str] = []
        for row in reach:
            cell = row.cells[key]
            if not replace_hand and cell.by_hand:
                continue
            if only_pending and not undecided(cell.value):
                continue
            to = verdicts.get(row.app)
            if to is None:
                unjudged.append(row.name)
                continue
            if to == cell.value:
                continue
            shadow[(row.app, key)] = to
            changes.append(Change(row.app, key, cell.value, to))
        if unjudged:
            count = len(unjudged)
            noun = " dossier cannot" if count == 1 else " dossiers cannot"
            skipped.append(
                f"{column.label}: {count}{noun} be judged yet (a result not in), left as is: "
                f"{', '.join(unjudged)}."
            )
    return Proposal(tuple(changes), tuple(skipped))


# --- The table, as Dossiers draws it -----------------------------------------

Sent = Mapping[str, Mapping[str, tuple[str, bool]]]


def columns_of(plan: stages.Plan, fixed: Callable[[stages.Gate], bool]) -> tuple[Column, ...]:
    """Every gate and outcome in table order, as the engine reads them;
    ``fixed`` says whether a gate's Review Robin session has opened."""
    out: list[Column] = []
    for c in plan.columns:
        if isinstance(c, stages.Gate):
            out.append(Column(c.key, "gate", c.label, c.rule, fixed=fixed(c)))
        else:
            scoped = tuple(g.key for g in stages.scope(plan, c))
            out.append(Column(c.key, "outcome", c.label, c.rule, scoped, c.weights))
    return tuple(out)


def _results(cell: stages.Cell) -> dict[str, str]:
    """A gate cell's results as the page holds them: its first as the
    template prints it (``str`` of the number), the others as text."""
    out = {"r1": str(cell.result)} if cell.result is not None else {}
    out.update(dict(cell.extra))
    return out


def rows_of(
    plan: stages.Plan,
    answers: Callable[[Application], Mapping[str, str]],
    sent: Sent,
) -> tuple[Dossier, ...]:
    """Each application's row: the server's results, ranks and answers,
    and the page's own values and hand marks for the cells the page can
    set (``sent``, by application ID then column key; a cell the page did
    not send keeps the server's value). A cell is one the page can set
    when it has a value, or is a submitted application's outcome."""
    rank = stages.submitted_rank(plan.rows)
    out: list[Dossier] = []
    for row in plan.rows:
        d = row.dossier
        own = sent.get(d.key, {})
        cells: dict[str, Cell] = {}
        for c in plan.columns:
            cell = row.cells.get(c.key, stages.Cell(""))
            gate = isinstance(c, stages.Gate)
            if not cell.value and (gate or d.state != "Submitted"):
                continue
            value, hand = own.get(c.key, (cell.value, cell.by_hand))
            cells[c.key] = Cell(value, _results(cell) if gate else {}, hand)
        name = d.key if d.state == "Draft" else d.public_id
        said: Mapping[str, str] = answers(d.application) if d.application is not None else {}
        out.append(Dossier(d.key, name, d.state, rank.get(d.key), said, cells))
    return tuple(out)
