"""A gate's evaluators per ruling 27 (segment AD1G rung 2): ranked
sources with a min and max, a Total, distinct evaluators, the candidate
never their own, and the work spread across a panel."""

from __future__ import annotations

import pytest

from applydesk import sample_data, stages
from applydesk.stages import Gate, Source, Total, fill, total_problem

NOMINATED = Source("nominated", "q-referees", 0, 2)
PANEL_A = Source("panel", "panel-a", 1, 3)
TOTAL = Total(3, 3)
RA = "wa9juxbc2t"
PANEL = ("p1@x.edu", "p2@x.edu", "p3@x.edu", "p4@x.edu")


def _emails(result: stages.Filling) -> list[str]:
    return [email for email, _ in result.evaluators]


def test_the_authors_examples() -> None:
    """Nominated 0-2, Panel A 1-3, Total 3-3: no nominee gets three from
    Panel A; two nominees get one."""
    none = fill((NOMINATED, PANEL_A), TOTAL, ((), PANEL))
    assert [rank for _, rank in none.evaluators] == [1, 1, 1] and none.filled
    two = fill((NOMINATED, PANEL_A), TOTAL, (("n1@x.edu", "n2@x.edu"), PANEL))
    assert [rank for _, rank in two.evaluators] == [0, 0, 1] and two.filled


def test_a_lower_source_gives_only_what_the_total_needs() -> None:
    result = fill((NOMINATED, PANEL_A), Total(1, 5), (("n1@x.edu", "n2@x.edu"), PANEL))
    # The first gives what it has; Panel A its own min, the Total met.
    assert [rank for _, rank in result.evaluators] == [0, 0, 1]


def test_room_is_kept_for_a_lower_sources_min() -> None:
    result = fill((NOMINATED, PANEL_A), Total(1, 2), (("n1@x.edu", "n2@x.edu"), PANEL))
    assert [rank for _, rank in result.evaluators] == [0, 1] and result.filled


def test_evaluators_are_distinct_and_never_the_candidate() -> None:
    """Someone nominated and on the panel counts once, for the nomination;
    the candidate is never their own evaluator."""
    result = fill(
        (NOMINATED, PANEL_A),
        TOTAL,
        (("P1@x.edu", "cand@x.edu"), PANEL),
        candidate="Cand@x.edu",
    )
    emails = [e.casefold() for e in _emails(result)]
    assert len(emails) == len(set(emails)) == 3
    assert "cand@x.edu" not in emails
    assert result.evaluators[0] == ("P1@x.edu", 0)


def test_a_dossier_that_cannot_be_filled_is_short() -> None:
    result = fill((PANEL_A,), Total(3, 3), (("p1@x.edu",),))
    assert result.short == 2 and not result.filled
    unmet = fill((PANEL_A,), Total(1, 3), ((),))
    assert unmet.unmet == (0,) and not unmet.filled


def test_a_panel_spreads_its_work_evenly() -> None:
    load: dict[str, int] = {}
    for _ in range(4):
        fill((Source("panel", "panel-a", 1, 1),), Total(1, 1), (PANEL,), load=load)
    assert sorted(load.values()) == [1, 1, 1, 1]


def test_a_nominated_dossier_counts_toward_the_load() -> None:
    """Codex on rung 2: Alice nominated four times is not the least-loaded
    panel member for the next dossier; Bob, with none, is."""
    sources = (Source("nominated", "q", 0, 1), Source("panel", "p", 0, 1))
    total, panel = Total(1, 2), ("alice@x.edu", "bob@x.edu")
    load: dict[str, int] = {}
    for _ in range(4):
        fill(sources, total, (("alice@x.edu",), panel), load=load)
    assert load == {"alice@x.edu": 4}
    result = fill(sources, Total(1, 1), ((), panel), load=load)
    assert result.evaluators == (("bob@x.edu", 1),)


def test_the_totals_bounds() -> None:
    sources = (NOMINATED, PANEL_A)
    assert stages.total_bounds(sources) == (1, 5)
    assert total_problem(sources, TOTAL) == ""
    assert "min is below" in total_problem(sources, Total(0, 3))
    assert "max is above" in total_problem(sources, Total(3, 6))
    assert "above its max" in total_problem(sources, Total(4, 3))
    assert total_problem((), Total(0, 0)) == "no evaluators"


def test_a_sample_gate_reads_its_panel_as_its_source() -> None:
    gate = Gate("g1", 1, "Panel review", "RRW", panel="panel-a")
    sources, total = stages.sources_of("k7mfr3pq8z", gate)
    assert len(sources) == 1 and sources[0].kind == "panel" and sources[0].ref == "panel-a"
    assert sources[0].min == sources[0].max == total.min == total.max > 0
    assert stages.sources_of("k7mfr3pq8z", Gate("g9", 9, "x", "RRW")) == ((), Total(0, 0))


def test_the_head_warns_as_the_page_script_does() -> None:
    """The cold read on rungs 2-4: the server's chip warns on what the
    script's ``sourceProblems`` names, not only on the Total."""
    pools: dict[str, sample_data.Pool] = {
        "panel-a": {"name": "Panel A", "members": [("A", "a@x.edu")]}
    }
    ok = (Source("panel", "panel-a", 1, 1),)
    assert not stages.sources_warn(ok, Total(1, 1), pools)
    assert stages.sources_warn((Source("panel", "gone", 1, 1),), Total(1, 1), pools)
    assert stages.sources_warn((Source("nominated", "", 0, 1),), Total(0, 1), pools)
    assert stages.sources_warn((Source("panel", "panel-a", 2, 1),), Total(1, 2), pools)
    assert stages.sources_warn((), Total(0, 0), pools)


# --- AD1G rung 5: each gate's assignments, for Evaluations ---


def _gate(exercise_id: str, key: str) -> Gate:
    return next(
        c for c in stages.plan_of(exercise_id).columns if isinstance(c, Gate) and c.key == key
    )


def test_a_gate_s_dossiers_are_filled_and_its_panel_spread_evenly() -> None:
    """The RA recruitment (ruling 30): every current RA reviews every
    applicant but themselves; two residential staff interview each
    shortlisted, the load spread evenly."""
    rows, spread = stages.assignments("wa9juxbc2t", _gate("wa9juxbc2t", "g1"))
    plan = stages.plan_of("wa9juxbc2t")
    entered = [r for r in plan.rows if r.cells["g1"].value == "Entered"]
    assert [a.application for a in rows] == [r.application for r in entered]
    assert all(a.application.email not in {e for _, e, _ in a.evaluators} for a in rows)
    ras = {m.email for m in sample_data.CURRENT_RAS}
    for a in rows:
        assert len(a.evaluators) == (29 if a.application.email in ras else 30) and not a.short
    assert sum(len(a.evaluators) for a in rows) == 2_980
    ((panel, counts),) = spread
    assert panel == "Current RAs" and len(counts) == 30
    assert stages.assignment_counts(rows) == "100 dossiers · 100 filled"
    rows, spread = stages.assignments("wa9juxbc2t", _gate("wa9juxbc2t", "g3"))
    assert len(rows) == 40 and all(len(a.evaluators) == 2 for a in rows)
    ((panel, counts),) = spread
    loads = [n for _, n in counts]
    assert panel == "Residential staff" and sum(loads) == 80 and max(loads) - min(loads) <= 1


def test_a_row_s_state_follows_the_mode() -> None:
    g3 = _gate("wa9juxbc2t", "g3")
    rows, _ = stages.assignments("wa9juxbc2t", g3)
    assert g3.mode == "suggested"
    assert stages.assignment_state(g3, True, rows[0]) == "Approved"
    assert stages.assignment_state(g3, False, rows[0]) == "Suggested"
    short = stages.Assignment(rows[0].application, (), 2, ())
    assert stages.assignment_state(g3, False, short) == "Short by 2"
    assigned = Gate("g9", 9, "x", "RRW", mode="assigned")
    assert stages.assignment_state(assigned, False, short) == "Not assigned"
    assert stages.assignment_counts((short,)) == "1 dossier · 0 filled · 1 short"


def test_a_nominee_comes_from_the_question_s_pool() -> None:
    ex = "r6tm4kq9wz"  # the conference grant's form asks for a preferred reviewer
    pool = {e for _, e in sample_data.people_pools(ex)["pool"]["members"]}
    apps = sample_data.applications_of(ex)
    named = [sample_data.nominees(ex, a, "Preferred evaluator") for a in apps]
    assert all(len(n) <= 1 and set(n) <= pool for n in named)
    assert sample_data.nominees(ex, apps[0], "No such question") == ()
    # The RA recruitment asks for none (ruling 30).
    assert stages.nominee_questions("wa9juxbc2t") == ()


def test_a_result_reads_its_chosen_field() -> None:
    """Ruling 28 (the cold read on 4c-4d): a result's derivation and type
    read the field it names; a gate listing its fields assumes none."""
    likert = stages.Field("integer", "1", "5", "1")
    words = stages.Field("string", max="100")
    r = stages.GateResult("r1", "Rating", words, "mean", source="rating")
    g = Gate("g9", 9, "x", "RRW", (r,), fields=(stages.ResponseField("rating", "Rating", likert),))
    src = stages.source_field(g, r)
    assert src is not None and stages.result_type(stages.collated(r, src)) == "Decimal 1 to 5"
    unnamed = stages.GateResult("r2", "Other", likert, "mean")
    g2 = Gate("g9", 9, "x", "RRW", (unnamed,), fields=g.fields)
    assert stages.source_field(g2, unnamed) is None


def _g3(monkeypatch: pytest.MonkeyPatch, *, stage: object = None, **changes: object) -> None:
    """The model exercise's Gate 3, not sent, changed for one test."""
    from dataclasses import replace

    model = stages._STAGES[RA]  # pyright: ignore[reportPrivateUsage]  -- a sample's shape
    staged = tuple(
        replace(
            st,
            columns=tuple(replace(c, **changes) if c.key == "g3" else c for c in st.columns),
            **({"status": stage} if stage and any(c.key == "g3" for c in st.columns) else {}),
        )
        for st in model
    )
    monkeypatch.setitem(stages._STAGES, RA, staged)  # pyright: ignore[reportPrivateUsage]  -- as above


@pytest.mark.parametrize(
    ("changes", "why"),
    [
        ({}, "40 dossiers to approve"),  # Suggested, nothing saved approved
        ({"mode": "automatic"}, ""),  # filled, every dossier: Ready
        ({"mode": "assigned"}, "40 dossiers to assign"),
        ({"results": ()}, "No result yet"),
        ({"stage": "Draft"}, "Its stage is not published"),
    ],
)
def test_a_gate_is_ready_only_as_rulings_24_and_27_say(
    monkeypatch: pytest.MonkeyPatch, changes: dict[str, object], why: str
) -> None:
    """AD-33: a gate not sent is Ready only once its stage is published,
    it has a result and evaluators, its entry is decided and every dossier
    entered is filled, and, Suggested, approved (ruling 34)."""
    from applydesk import workflow

    _g3(monkeypatch, **changes)
    assert workflow.gate_state(RA, "g3") == (("Not ready", why) if why else ("Ready", ""))


def test_a_gate_with_no_evaluators_or_undecided_entry_is_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from applydesk import workflow

    _g3(monkeypatch, mode="automatic")
    plan = stages.plan_of(RA)
    first = next(r for r in plan.rows if r.application.state == "Submitted")
    undecided = replace(first, cells={**first.cells, "g3": stages.Cell("—")})
    rows = tuple(undecided if r is first else r for r in plan.rows)
    monkeypatch.setattr(stages, "plan_of", lambda _id: replace(plan, rows=rows))
    assert workflow.gate_state(RA, "g3") == ("Not ready", "1 entry to decide")
    monkeypatch.setattr(stages, "sources_of", lambda _e, _g: ((), Total(0, 0)))
    assert workflow.gate_state(RA, "g3") == ("Not ready", "No evaluators yet")
    # Sent or complete, the state is Review Robin's, never derived.
    assert workflow.gate_sent(RA, "g1") == ("Results in", "100 of 100 reviewed")
    assert workflow.gate_sent(RA, "g3") == ("Not sent", "")
