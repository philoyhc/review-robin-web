"""Process's *Save* (segment AD1N rung 4; every exercise since AD2C): the
page's snapshot (``applydeskProcessSnapshot``) checked and built back into
the stages the pages read, and the emails its items tick, for
``process_store.save`` to keep.

Shapes are checked, never the plan: what the page itself flags (dates out
of order, a rule left pointing at a removed gate, weights not adding up)
is saved as the operator left it and flagged again on reload. Ruling 15's
shape is the exception (``stages.problems``): nothing else the pages draw
expects a stage holding the form and a gate.

Gates, outcomes and stages keep the keys they were saved under (ruling
37). One the page made (``gnew1``, ``onew1``) is given the server's own,
past every key the exercise has held (``g6``, ``o4``), and every rule,
weight and email tick naming it follows, so a page key never reaches a
row. A rule naming a column the snapshot drops is left as written:
``process_store`` refuses it, naming both (AD-62).
"""

from __future__ import annotations

import re
from contextvars import ContextVar
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
#: A label, a result's name and value, a source's panel or question, an
#: outcome's value, as their columns hold them (``models``: ``String(200)``).
#: Wider text would pass here and fail the write on Postgres (Codex on
#: cordware#230); SQLite does not enforce the width.
_LABEL = 200
#: A field's Min, Max and Step (``GateField``: ``String(32)``).
_BOUND = 32
#: A key the page made for a column it added, replaced on save.
_PAGE_KEY = re.compile(r"([go])new[0-9]+")


#: Building only to check the rules (``build(..., checking=True)``): a
#: field the rules do not read that is still being typed (a date with one
#: end, a weight not yet a whole percent, a count left blank) is read as
#: unset rather than refusing the whole snapshot (Codex on #4156).
_checking: ContextVar[bool] = ContextVar("process_save_checking", default=False)


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
    """A count the page read as a whole number. Blank or not whole, the
    page sends null: refused, never kept as 0 (Codex on #4026)."""
    if v is None:
        if _checking.get():
            return 0
        raise Refused(f"{what} needs whole numbers for its evaluator counts.")
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
    """Both ends, or none. One end alone has nowhere to be kept (a range
    is both or no dates, as ``stages.window``), so it is refused rather
    than dropped (Codex on #4026)."""
    if _checking.get():
        try:
            start, end = _when(a, f"{what}'s start"), _when(b, f"{what}'s end")
        except Refused:
            return None
        return StageDates(start, end) if start and end else None
    start, end = _when(a, f"{what}'s start"), _when(b, f"{what}'s end")
    if (start is None) != (end is None):
        raise Refused(f"{what} needs both a start and an end, or neither.")
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
    # A scale is a number type's (segment AD2S): a List or a String keeps
    # neither the flag nor its labels, as Review Robin's Band 3 clears them.
    # Its bounds are kept as typed; one Review Robin would refuse is the
    # Outline's problem (``stages.field_problems``), not a refused save.
    number = kind in ("integer", "decimal")
    scale = _flag(got.get("scale", False), what) and number
    labels = _text(got.get("scale_labels", ""), what, _TEXT) if scale else ""
    return Field(
        kind,
        _text(got.get("min", ""), what, _BOUND),
        _text(got.get("max", ""), what, _BOUND),
        _text(got.get("step", ""), what, _BOUND),
        _text(got.get("options", ""), what, _TEXT),
        scale,
        stages.scale_labels(labels),
    )


def _gate(v: Any, number: int, panels: frozenset[str], renamed: dict[str, str]) -> Gate:
    what = f"Gate {number}"
    got = _dict(v, what)
    fields = tuple(
        ResponseField(
            _key(f.get("key"), f"{what}'s field key"),
            _text(f.get("label"), f"{what}'s field", _LABEL),
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
        # A result whose field was removed has none, and no derivation,
        # until one is chosen: kept so, as the page shows it ("No field
        # chosen"), not refused with the rest of the page (Codex on #4026).
        if derive and not source:
            derive = ""
        if (source or derive) and derive not in dict(stages.DERIVATIONS):
            raise Refused(f"{what} has a result derived in no known way.")
        results.append(
            GateResult(
                _key(r.get("key"), f"{what}'s result key"),
                _text(r.get("name"), f"{what}'s result", _LABEL),
                by_key[source].field if source else Field(),
                derive,
                _text(r.get("value", ""), f"{what}'s result", _LABEL),
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
        ref = _text(src.get("ref", ""), f"{what}'s source", _LABEL)
        if kind == "panel":
            ref = renamed.get(ref, ref)
            if ref and ref not in panels and ref not in renamed.values():
                raise Refused(f"{what} is evaluated by no panel this exercise has.")
        # Ruling 62: a panel's whole membership, its typed Min and Max kept
        # but unused (the panel's size is read when the gate is).
        whole = _flag(src.get("all_members", False), f"{what}'s source")
        sources.append(
            Source(
                kind,
                ref,
                _whole(src.get("min"), f"{what}'s source"),
                _whole(src.get("max"), f"{what}'s source"),
                whole and kind == "panel",
            )
        )
    total = _dict(got.get("total"), f"{what}'s Total")
    via = _text(got.get("type", "RRW"), what, 20) or "RRW"
    if via not in dict(stages.GATE_TYPES):
        raise Refused(f"{what}'s type is not one of the choices.")
    mode = _text(got.get("mode"), what, 20)
    if mode not in dict(stages.MODES):
        raise Refused(f"{what}'s assignment is not one of the choices.")
    return Gate(
        _key(got.get("key"), f"{what}'s key"),
        number,
        _text(got.get("label"), what, _LABEL),
        via,
        tuple(results),
        _rule(got.get("rule"), f"{what}'s rule"),
        sources=tuple(sources),
        total=Total(_whole(total.get("min"), what), _whole(total.get("max"), what)),
        mode=mode,
        description=_text(got.get("description", ""), f"{what}'s description", _TEXT),
        confidential=_flag(got.get("confidential"), what),
        fields=fields,
        when=_span(got.get("from"), got.get("to"), what),
        own_fields=True,
    )


def _outcome(v: Any, number: int) -> Outcome:
    what = f"Outcome {number}"
    got = _dict(v, what)
    weights: list[tuple[str, float]] = []
    for k, pct in _dict(got.get("weights", {}), f"{what}'s weights").items():
        text = _text(pct, f"{what}'s weights", 20)
        # Whole percents, as the page draws them back (stages.weight_rows):
        # a word, a decimal, NaN or Infinity cannot be kept as typed, so it
        # is refused, never read as 0 or rounded (Codex on #4026; cold read).
        # Blank too: the page flags it, and 0 would read as weighed out
        # on purpose (Codex on #4026).
        # ASCII digits only: "²".isdigit() holds and int() refuses it (AD-129).
        if not re.fullmatch(r"[0-9]+", text):
            if _checking.get():
                continue  # the page says so itself; the rules are still checked
            raise Refused(f"{what}'s weights are not all whole percents.")
        share = int(text) / 100
        weights.append((k, share))
    if len(weights) > MAX_ITEMS:
        raise Refused(f"{what} has too many weights.")
    values = tuple(_text(x, f"{what}'s values", _LABEL) for x in _list(got.get("values"), what))
    # Each value's key, beside it (AD-57): "" for one the page added.
    raw_keys = _list(got.get("value_keys", [""] * len(values)), f"{what}'s values")
    if len(raw_keys) != len(values):
        raise Refused(f"{what}'s values are malformed.")
    value_keys = tuple(_text(k, f"{what}'s values", 16) for k in raw_keys)
    if any(k and not _KEY.fullmatch(k) for k in value_keys):
        raise Refused(f"{what}'s values are malformed.")
    kept = [(v, k) for v, k in zip(values, value_keys, strict=True) if v]
    return Outcome(
        _key(got.get("key"), f"{what}'s key"),
        number,
        _text(got.get("label"), what, _LABEL),
        tuple(v for v, _ in kept),
        _when(got.get("due", ""), f"{what}'s due"),
        "",
        tuple(weights),
        _rule(got.get("rule"), f"{what}'s rule"),
        value_keys=tuple(k for _, k in kept),
    )


def _minted(page_keys: list[str], taken: frozenset[str]) -> dict[str, str]:
    """Each page-made key (``gnew1``) to the server's next of its kind,
    past every key held now or ever (``taken``) and every one the page
    keeps; the rest map to themselves."""
    held = set(taken) | {k for k in page_keys if not _PAGE_KEY.fullmatch(k)}
    top = {"g": 0, "o": 0}
    for k in held:
        if k[:1] in top and k[1:].isascii() and k[1:].isdigit():
            top[k[0]] = max(top[k[0]], int(k[1:]))
    keys: dict[str, str] = {}
    for k in page_keys:
        made = _PAGE_KEY.fullmatch(k)
        if made:
            top[made.group(1)] += 1
            keys[k] = f"{made.group(1)}{top[made.group(1)]}"
        else:
            keys[k] = k
    return keys


def _rekey(text: str, keys: dict[str, str]) -> str:
    """A rule's or a weight's key, "gnew1.r2" or "o1", with its column's
    key as saved; one naming no column on the page is left as written."""
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


def _items(v: Any, key: str) -> list[Any]:
    """``v[key]`` when ``v`` is a dict holding a list there, else none."""
    got = cast(dict[str, Any], v).get(key) if isinstance(v, dict) else None
    return cast(list[Any], got) if isinstance(got, list) else []


def made_panels(sent: Any, exercise_id: str) -> set[str]:
    """The panels the snapshot's gates name that the page made with
    *+ New panel…* (``new-1``), not yet the exercise's."""
    known = sample_data.panel_pools(exercise_id)
    found: set[str] = set()
    for st in _items(sent, "stages"):
        for g in _items(st, "gates"):
            for src in _items(g, "sources"):
                ref = cast(dict[str, Any], src).get("ref") if isinstance(src, dict) else None
                if isinstance(ref, str) and ref.startswith("new-") and ref not in known:
                    found.add(ref)
    return found


def build(
    sent: Any,
    exercise_id: str,
    renamed: dict[str, str] | None = None,
    taken: frozenset[str] = frozenset(),
    *,
    checking: bool = False,
) -> tuple[tuple[Stage, ...], frozenset[tuple[str, str]]]:
    """The stages the snapshot describes, and its (item, audience) emails;
    a gate's panel is one the exercise has, or one the page made, by the
    key ``renamed`` gives it (``panels_store.adopt``). A column the page
    added takes a key past ``taken`` (``process_store.taken_keys``).

    ``checking``: built only to say what its rules read amiss (ruling 78),
    so the page's own keys are kept and ruling 15's shape, which the page
    says itself, is not refused."""
    token = _checking.set(checking)
    try:
        return _build(sent, exercise_id, renamed or {}, taken, checking)
    finally:
        _checking.reset(token)


def _build(
    sent: Any,
    exercise_id: str,
    renamed: dict[str, str],
    taken: frozenset[str],
    checking: bool,
) -> tuple[tuple[Stage, ...], frozenset[tuple[str, str]]]:
    panels = frozenset(sample_data.panel_pools(exercise_id))
    got = _dict(sent, "The process")
    raw = _list(got.get("stages"), "The process's stages", MAX_STAGES)
    if not raw:
        raise Refused("A process has at least one stage.")
    built: list[Stage] = []
    sends: set[tuple[str, str]] = set()
    seen: set[str] = set()
    gates_n = outcomes_n = 0
    for n, x in enumerate(raw, 1):
        st = _dict(x, f"Stage {n}")
        stage_key = _text(st.get("key", ""), f"Stage {n}'s key", 16)
        if stage_key and not _KEY.fullmatch(stage_key):
            raise Refused(f"Stage {n}'s key is malformed.")
        columns: list[Gate | Outcome] = []
        for g in _list(st.get("gates"), f"Stage {n}'s gates", MAX_GATES):
            gates_n += 1
            columns.append(_gate(g, gates_n, panels, renamed))
        form = None if st.get("form") is None else _dict(st.get("form"), f"Stage {n}'s form")
        if form is not None:
            for item in ("receipt", "reminder"):
                if _flag(form.get(item), f"Stage {n}'s form"):
                    sends.add((item, workflow.APPLICANTS))
        if st.get("outcome") is not None:
            outcomes_n += 1
            outcome = _outcome(st.get("outcome"), outcomes_n)
            o = _dict(st.get("outcome"), f"Stage {n}'s outcome")
            if _flag(o.get("applicants_email"), f"Outcome {outcomes_n}"):
                sends.add((outcome.key, workflow.APPLICANTS))
            if _flag(o.get("evaluators_email"), f"Outcome {outcomes_n}"):
                sends.add((outcome.key, workflow.EVALUATORS))
            columns.append(outcome)
        for c in columns:
            if c.key in seen:
                raise Refused("Two gates or outcomes share a key.")
            seen.add(c.key)
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
                key=stage_key,
                candidates=_flag(st.get("candidates", False), f"Stage {n}"),
                revert_reason=_text(st.get("revert_reason", ""), f"Stage {n}'s reason", 500),
            )
        )
    shape = stages.problems(tuple(built))
    if shape and not checking:
        raise Refused(shape[0])
    if checking:
        return tuple(built), frozenset(sends)
    keys = _minted([c.key for st in built for c in st.columns], taken)
    final = tuple(_rekeyed(st, keys) for st in built)
    return final, frozenset((keys.get(item, item), aud) for item, aud in sends)


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
