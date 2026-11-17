"""A gate's evaluators per ruling 27 (segment AD1G rung 2): ranked
sources with a min and max, a Total, distinct evaluators, the candidate
never their own, and the work spread across a panel."""

from __future__ import annotations

from applydesk import stages
from applydesk.stages import Gate, Source, Total, fill, total_problem

NOMINATED = Source("nominated", "q-referees", 0, 2)
PANEL_A = Source("panel", "panel-a", 1, 3)
TOTAL = Total(3, 3)
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
    gate = Gate("g1", 1, "Panel Review", "RRW", panel="panel-a")
    sources, total = stages.sources_of("wa9juxbc2t", gate)
    assert len(sources) == 1 and sources[0].kind == "panel" and sources[0].ref == "panel-a"
    assert sources[0].min == sources[0].max == total.min == total.max > 0
    assert stages.sources_of("wa9juxbc2t", Gate("g9", 9, "x", "RRW")) == ((), Total(0, 0))
