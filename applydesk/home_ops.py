"""The operator's part of Home's timeline (segment AD1I, Decision amended
again): per stage, beneath the rule that the participants' part stops at,
the form's state and counts, each gate's state, mode, evaluators, pairs and
progress, and each outcome's state and counts. Operator-only by design, so
it lives apart from `applydesk/timeline.py`, which the applicant's page
draws; nothing here reaches that page.
"""

from __future__ import annotations

from dataclasses import dataclass

from applydesk import sample_data, stages, workflow
from applydesk.sample_data import Exercise


@dataclass(frozen=True)
class Row:
    """One operator row: what it is, its state chip and tone, a line of
    figures, and where it is worked (``target``: "dossiers" or a gate's
    number; "" for no link, a draft's gates having no page yet)."""

    label: str
    state: str
    tone: str  # ok, info, warn, mute: the chip's
    detail: str
    target: str


_GATE_TONE = {"Results in": "ok", "Sent": "info", "Closed": "info", "Ready": "info"}


def _form(e: Exercise) -> Row:
    counted = workflow.counts_of(e.public_id)  # the one count (AD-41)
    state = workflow.form_state(e)
    detail = f"{counted.submitted:,} submitted" + (
        f" · {workflow.plural(counted.drafts, 'draft')}" if counted.drafts else ""
    )
    return Row("Form", state, "warn" if state == "Draft" else "info", detail, "dossiers")


def _gate(e: Exercise, g: stages.Gate) -> Row:
    state, progress = workflow.gate_state(e.public_id, g.key)
    sources, total = stages.sources_of(e.public_id, g)
    pools = sample_data.panel_pools(e.public_id)
    rows, _ = stages.assignments(e.public_id, g)
    pairs = len([p for p in stages.pairs_of(rows) if p.email])
    parts = [dict(stages.MODES).get(g.mode, g.mode)]
    if sources:
        parts.append(stages.sources_summary(sources, total, pools))
    parts.append(f"{pairs:,} {'pair' if pairs == 1 else 'pairs'}")
    parts.append(progress or ("not sent" if state in ("Ready", "Not ready") else ""))
    return Row(
        g.label or "Untitled gate",
        state,
        _GATE_TONE.get(state, "warn"),
        " · ".join(p for p in parts if p),
        "" if e.state == "Draft" else str(g.number),
    )


def _outcome(e: Exercise, o: stages.Outcome, plan: stages.Plan) -> Row:
    """Dossiers' column tally (`stages.counts`) and, as the Workflow card
    says it, *Released* or *Pending* (cold read: one vocabulary)."""
    detail = stages.counts(plan, o)
    if o.released:
        when, _, to = o.released.partition(" · ")
        detail += f" · released {when}" + (f" {to}" if to else "")
        return Row(o.label or "Untitled outcome", "Released", "ok", detail, "dossiers")
    return Row(o.label or "Untitled outcome", "Pending", "mute", detail, "dossiers")


def of(e: Exercise) -> tuple[tuple[Row, ...], ...]:
    """The operator's rows, one tuple per stage in the timeline's order."""
    plan = stages.plan_of(e.public_id)
    out: list[tuple[Row, ...]] = []
    for st in plan.stages:
        rows: list[Row] = [_form(e)] if st.form else []
        for c in st.columns:
            rows.append(_gate(e, c) if isinstance(c, stages.Gate) else _outcome(e, c, plan))
        out.append(tuple(rows))
    return tuple(out)
