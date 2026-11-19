"""Process's *Save* on a scratch exercise (segment AD1N rung 4): the page's
snapshot (``applydeskProcessSnapshot``) checked and built back into the
stages the sample's lookups return, and the emails its items tick.

Shapes are checked, never the plan: what the page itself flags (dates out
of order, a rule left pointing at a removed gate, weights not adding up)
is saved as the operator left it and flagged again on reload. Ruling 15's
shape is the exception (``stages.problems``): nothing else the pages draw
expects a stage holding the form and a gate.

Gates and outcomes are renumbered in timeline order, ``g1``... and
``o1``..., the keys the page minted for new ones (``gnew1``) rewritten in
every rule and weight that names them, so a key never outlives a reload.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime
from typing import Any, cast

from applydesk import sample_data, stages, workflow
from applydesk.stages import (
    Field,
    Gate,
    GateResult,
    Outcome,
    ResponseField,
    Rule,
    Source,
    Stage,
    StageDates,
    Total,
)


class Refused(Exception):
    """A snapshot that cannot be kept, said to the operator."""


MAX_STAGES = 20
MAX_GATES = 10  # per stage
MAX_ITEMS = 50  # fields, sources, conditions, values: per list
_KEY = re.compile(r"[a-z][a-z0-9]{0,15}")
_COND_KINDS = ("status", "last", "out", "res", "ent", "comb", "form", "top")
_TEXT = 2000


def _dict(v: Any, what: str) -> dict[str, Any]:
    if not isinstance(v, dict):
        raise Refused(f"{what} is malformed.")
    return cast(dict[str, Any], v)


def _list(v: Any, what: str, most: int = MAX_ITEMS) -> list[Any]:
    if not isinstance(v, list):
        raise Refused(f"{what} is malformed.")
    got = cast(list[Any], v)
    if len(got) > most:
        raise Refused(f"{what} has more than {most}.")
    return got


def _text(v: Any, what: str, most: int = 500) -> str:
    if not isinstance(v, str):
        raise Refused(f"{what} is malformed.")
    if len(v) > most:
        raise Refused(f"{what} is too long.")
    return v.strip()


def _flag(v: Any, what: str) -> bool:
    if not isinstance(v, bool):
        raise Refused(f"{what} is malformed.")
    return v


def _whole(v: Any, what: str) -> int:
    """A count the page read as a whole number, or null for blank (0)."""
    if v is None:
        return 0
    if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 10_000:
        raise Refused(f"{what} is malformed.")
    return v


def _when(v: Any, what: str) -> datetime | None:
    """A datetime-local value, "2027-01-04T09:00", or blank."""
    text = _text(v, what, 40)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise Refused(f"{what} is not a date and time.") from None


def _span(a: Any, b: Any, what: str) -> StageDates | None:
    """Both ends, or none: one end alone is no dates (as ``stages.window``)."""
    start, end = _when(a, f"{what}'s start"), _when(b, f"{what}'s end")
    return StageDates(start, end) if start and end else None


def _key(v: Any, what: str) -> str:
    text = _text(v, what, 16)
    if not _KEY.fullmatch(text):
        raise Refused(f"{what} is malformed.")
    return text


def _conds(v: Any, what: str) -> tuple[tuple[str, str, str, str], ...]:
    out: list[tuple[str, str, str, str]] = []
    for c in _list(v, what):
        parts = _list(c, what, 4)
        if len(parts) != 4 or not all(isinstance(p, str) for p in parts):
            raise Refused(f"{what} is malformed.")
        kind, key, op, value = (_text(p, what, 500) for p in parts)
        if kind not in _COND_KINDS:
            raise Refused(f"{what} reads nothing known.")
        out.append((kind, key, op, value))
    return tuple(out)


def _rule(v: Any, what: str) -> Rule | None:
    if v is None:
        return None
    got = _dict(v, what)
    more = tuple(
        (_conds(_dict(b, what).get("when"), what), _text(_dict(b, what).get("then", ""), what))
        for b in _list(got.get("more", []), what)
    )
    return Rule(
        _conds(got.get("when"), what),
        _text(got.get("then", ""), what),
        _text(got.get("otherwise", ""), what),
        more,
    )


def _field_def(got: dict[str, Any], what: str) -> Field:
    kind = _text(got.get("type"), what, 20)
    if kind not in dict(stages.FIELD_TYPES):
        raise Refused(f"{what}'s type is not one of the choices.")
    return Field(
        kind,
        _text(got.get("min", ""), what, 40),
        _text(got.get("max", ""), what, 40),
        _text(got.get("step", ""), what, 40),
        _text(got.get("options", ""), what, _TEXT),
    )


def _gate(v: Any, number: int, panels: frozenset[str]) -> Gate:
    what = f"Gate {number}"
    got = _dict(v, what)
    fields = tuple(
        ResponseField(
            _key(f.get("key"), f"{what}'s field key"),
            _text(f.get("label"), f"{what}'s field"),
            _field_def(f, f"{what}'s field"),
            _flag(f.get("required"), f"{what}'s field"),
            _text(f.get("help", ""), f"{what}'s field help", _TEXT),
        )
        for f in (_dict(x, what) for x in _list(got.get("fields"), f"{what}'s fields"))
    )
    if len({f.key for f in fields}) < len(fields):
        raise Refused(f"{what} has two fields with one key.")
    by_key = {f.key: f for f in fields}
    results: list[GateResult] = []
    for x in _list(got.get("results"), f"{what}'s results", 3):
        r = _dict(x, what)
        source = _text(r.get("source", ""), f"{what}'s result", 16)
        if source and source not in by_key:
            raise Refused(f"{what} has a result reading no field of its own.")
        derive = _text(r.get("derive"), f"{what}'s result", 20)
        if derive not in dict(stages.DERIVATIONS):
            raise Refused(f"{what} has a result derived in no known way.")
        results.append(
            GateResult(
                _key(r.get("key"), f"{what}'s result key"),
                _text(r.get("name"), f"{what}'s result"),
                by_key[source].field if source else Field(),
                derive,
                _text(r.get("value", ""), f"{what}'s result"),
                max(1, _whole(r.get("at_least"), f"{what}'s result")),
                source,
                _flag(r.get("ignore_zero"), f"{what}'s result"),
            )
        )
    sources: list[Source] = []
    for x in _list(got.get("sources"), f"{what}'s sources"):
        src = _dict(x, what)
        kind = _text(src.get("kind"), f"{what}'s source", 20)
        if kind not in dict(stages.SOURCE_KINDS):
            raise Refused(f"{what} has a source of no known kind.")
        ref = _text(src.get("ref", ""), f"{what}'s source")
        if kind == "panel" and ref and ref not in panels:
            # Made with *+ New panel…* on this page, kept once Panels saves.
            raise Refused(
                f"{what} is evaluated by a panel made on this page, which is not kept yet:"
                " choose an existing panel."
            )
        sources.append(
            Source(
                kind,
                ref,
                _whole(src.get("min"), f"{what}'s source"),
                _whole(src.get("max"), f"{what}'s source"),
            )
        )
    total = _dict(got.get("total"), f"{what}'s Total")
    mode = _text(got.get("mode"), what, 20)
    if mode not in dict(stages.MODES):
        raise Refused(f"{what}'s assignment is not one of the choices.")
    return Gate(
        _key(got.get("key"), f"{what}'s key"),
        number,
        _text(got.get("label"), what),
        "RRW",
        tuple(results),
        _rule(got.get("rule"), f"{what}'s rule"),
        sources=tuple(sources),
        total=Total(_whole(total.get("min"), what), _whole(total.get("max"), what)),
        mode=mode,
        description=_text(got.get("description", ""), f"{what}'s description", _TEXT),
        confidential=_flag(got.get("confidential"), what),
        fields=fields,
        when=_span(got.get("from"), got.get("to"), what),
    )


def _outcome(v: Any, number: int) -> Outcome:
    what = f"Outcome {number}"
    got = _dict(v, what)
    weights: list[tuple[str, float]] = []
    for k, pct in _dict(got.get("weights", {}), f"{what}'s weights").items():
        text = _text(pct, f"{what}'s weights", 20)
        try:
            weights.append((k, float(text) / 100 if text else 0.0))
        except ValueError:
            # Kept as a fraction, so a word typed as a weight cannot be
            # kept as typed: refused, not read as 0.
            raise Refused(f"{what}'s weights are not all numbers.") from None
    if len(weights) > MAX_ITEMS:
        raise Refused(f"{what} has too many weights.")
    values = tuple(_text(x, f"{what}'s values") for x in _list(got.get("values"), what))
    return Outcome(
        _key(got.get("key"), f"{what}'s key"),
        number,
        _text(got.get("label"), what),
        tuple(x for x in values if x),
        _when(got.get("due", ""), f"{what}'s due"),
        "",
        tuple(weights),
        _rule(got.get("rule"), f"{what}'s rule"),
    )


def _rekey(text: str, keys: dict[str, str]) -> str:
    """A rule's or a weight's key, "gnew1.r2" or "o1", with its column's
    new key."""
    head, dot, tail = text.partition(".")
    return keys.get(head, head) + dot + tail


def _rekey_rule(rule: Rule | None, keys: dict[str, str]) -> Rule | None:
    if rule is None:
        return None

    def conds(
        when: tuple[tuple[str, str, str, str], ...],
    ) -> tuple[tuple[str, str, str, str], ...]:
        return tuple(
            (k, _rekey(key, keys) if k in ("out", "res", "ent", "top") else key, op, v)
            for k, key, op, v in when
        )

    return Rule(
        conds(rule.when),
        rule.then,
        rule.otherwise,
        tuple((conds(w), then) for w, then in rule.more),
    )


def build(sent: Any, exercise_id: str) -> tuple[tuple[Stage, ...], frozenset[tuple[str, str]]]:
    """The stages the snapshot describes, and its (item, audience) emails;
    a gate's panel is one the exercise has."""
    panels = frozenset(sample_data.panel_pools(exercise_id))
    got = _dict(sent, "The process")
    raw = _list(got.get("stages"), "The process's stages", MAX_STAGES)
    if not raw:
        raise Refused("A process has at least one stage.")
    built: list[Stage] = []
    sends: set[tuple[str, str]] = set()
    keys: dict[str, str] = {}
    gates_n = outcomes_n = 0
    for n, x in enumerate(raw, 1):
        st = _dict(x, f"Stage {n}")
        columns: list[Gate | Outcome] = []
        for g in _list(st.get("gates"), f"Stage {n}'s gates", MAX_GATES):
            gates_n += 1
            gate = _gate(g, gates_n, panels)
            if gate.key in keys:
                raise Refused("Two gates or outcomes share a key.")
            keys[gate.key] = f"g{gates_n}"
            columns.append(gate)
        form = None if st.get("form") is None else _dict(st.get("form"), f"Stage {n}'s form")
        if form is not None:
            for item in ("receipt", "reminder"):
                if _flag(form.get(item), f"Stage {n}'s form"):
                    sends.add((item, workflow.APPLICANTS))
        if st.get("outcome") is not None:
            outcomes_n += 1
            outcome = _outcome(st.get("outcome"), outcomes_n)
            if outcome.key in keys:
                raise Refused("Two gates or outcomes share a key.")
            new = f"o{outcomes_n}"
            keys[outcome.key] = new
            o = _dict(st.get("outcome"), f"Stage {n}'s outcome")
            if _flag(o.get("applicants_email"), f"Outcome {outcomes_n}"):
                sends.add((new, workflow.APPLICANTS))
            if _flag(o.get("evaluators_email"), f"Outcome {outcomes_n}"):
                sends.add((new, workflow.EVALUATORS))
            columns.append(outcome)
        built.append(
            Stage(
                n,
                _text(st.get("name", ""), f"Stage {n}'s name", 200),
                _span(st.get("from"), st.get("to"), f"Stage {n}"),
                tuple(columns),
                form is not None,
                "Published" if _flag(st.get("published"), f"Stage {n}") else "Draft",
                _flag(st.get("shown"), f"Stage {n}"),
                _span(form.get("from"), form.get("to"), "The form") if form else None,
            )
        )
    shape = stages.problems(tuple(built))
    if shape:
        raise Refused(shape[0])
    final = tuple(_rekeyed(st, keys) for st in built)
    return final, frozenset(sends)


def _rekeyed(st: Stage, keys: dict[str, str]) -> Stage:
    columns = tuple(
        replace(c, key=keys[c.key], rule=_rekey_rule(c.rule, keys))
        if isinstance(c, Gate)
        else replace(
            c,
            key=keys[c.key],
            rule=_rekey_rule(c.rule, keys),
            weights=tuple((_rekey(k, keys), w) for k, w in c.weights),
        )
        for c in st.columns
    )
    return replace(st, columns=columns)
