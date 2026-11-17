"""Exercise Home's timeline and Details (segment AD1I, rung 2): the
timeline drawn from Process's stages by `applydesk/timeline.py`, and Home
in two columns with the old fact cards folded away."""

from __future__ import annotations

import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from applydesk import sample_data, timeline
from applydesk.tests._host import host_with

EX = "wa9juxbc2t"  # the RA recruitment, mid Stage 3
DRAFT = "c4xh2ndv6s"  # no dates set
PCG = "r6tm4kq9wz"  # one stage across the year's end


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0])


def _of(exercise_id: str, today: date = timeline.TODAY) -> timeline.Timeline:
    e = sample_data.exercise(exercise_id)
    assert e is not None
    return timeline.of(e, today)


def test_each_stage_has_its_dates_state_and_share() -> None:
    t = _of(EX)
    assert [(s.name, s.when, s.state) for s in t.stages] == [
        ("Applications", "1 Sep – 30 Sep", "Closed"),
        ("Review", "1 Oct – 6 Nov", "Done"),
        ("Interviews", "9 Nov – 4 Dec", "Now"),
    ]
    assert (t.start, t.end) == (date(2026, 9, 1), date(2026, 12, 4))
    assert sum(s.share for s in t.stages) == pytest.approx(1.0)
    # A share is the stage's days: Review's 37 of 93 days.
    assert t.stages[1].share == pytest.approx(37 / 93)
    assert t.now is t.stages[2] and t.stages[2].progress == pytest.approx(8.5 / 26)
    # Today along the track, in the same shares the segments are drawn in.
    assert t.today_at == pytest.approx(t.stages[2].offset + t.stages[2].share * 8.5 / 26)
    assert t.stages[2].offset == pytest.approx(t.stages[0].share + t.stages[1].share)


def test_a_stage_s_state_follows_today() -> None:
    before = _of(EX, date(2026, 8, 1))
    assert [s.state for s in before.stages] == ["Next", "Next", "Next"]
    after = _of(EX, date(2027, 1, 1))
    assert [s.state for s in after.stages] == ["Closed", "Done", "Done"]
    e = sample_data.exercise(EX)
    assert e is not None
    assert timeline.next_step(e, after) == "Every stage is done."
    assert timeline.next_step(e, before) == "Next: Applications, from 1 Sep."


def test_dates_roll_over_the_year_and_undated_stages_share_equally() -> None:
    pcg = _of(PCG)
    assert (pcg.stages[0].start, pcg.stages[0].end) == (date(2026, 11, 1), date(2027, 1, 31))
    assert pcg.stages[0].state == "Now"
    draft = _of(DRAFT)
    assert [(s.when, s.state, s.share) for s in draft.stages] == [
        ("Dates not set", "Next", 0.5),
        ("Dates not set", "Next", 0.5),
    ]
    assert draft.start is None


def test_items_say_what_happens_and_nothing_operator_only() -> None:
    t = _of(EX)
    assert [(i.kind, i.kicker, i.text) for i in t.stages[1].items] == [
        ("step", "Step", "Peer review."),
        ("step", "Step", "Office checks."),
        (
            "outcome",
            "Outcome · released 6 Nov",
            "Shortlisting: Re-appointment, Interview or Not shortlisted.",
        ),
    ]
    assert t.stages[2].items[-1] == timeline.Item(
        "outcome-due", "Outcome · expected December 2026", "Selection."
    )
    said = " ".join(i.kicker + i.text for s in t.stages for i in s.items)
    for operator_only in (
        "Current RAs",
        "Residential staff",
        "Automatic",
        "Suggested",
        "≥",
        "pairs",
    ):
        assert operator_only not in said


def test_home_is_the_timeline_beside_details(client: TestClient) -> None:
    home = client.get(f"/applydesk/operator/exercises/{EX}").text
    grid = home[home.index('<div class="hm-grid">') :]
    assert grid.index("data-timeline") < grid.index('id="details"')
    assert re.findall(r'data-tl-stage="(\d)"', home) == ["1", "2", "3"]
    assert 'data-tl-flex="0.3978"' in home and 'data-tl-p="32.7"' in home
    assert "Today · 17 Nov" in home
    assert "Now: Interviews, until 4 Dec. Next: Selection, expected December 2026." in home
    # The old fact cards are gone: their facts are the status row's and
    # the timeline's.
    for gone in ("Where it stands", "<h2>Counts</h2>", "<h2>Next step</h2>", 'class="lede"'):
        assert gone not in home, gone
    assert "100 submitted · 3 drafts" in home
    # Details: Description where Summary was, locked until rung 4.
    details = home[home.index('id="details"') :]
    assert "<dt>Description</dt>" in details and "Summary" not in details
    assert 'data-dt-lock disabled title="Editing the details comes later"' in details
    # The line under the timeline points to where the stage is worked.
    assert f'<a href="/applydesk/operator/exercises/{EX}/evaluations">Go to Evaluations</a>' in home


def test_a_draft_s_home_says_what_publishing_needs(client: TestClient) -> None:
    home = client.get(f"/applydesk/operator/exercises/{DRAFT}").text
    assert home.count("Dates not set") == 2 and "Today ·" not in home
    assert "A draft: the timeline is what applicants will see once it is published." in home
    assert "Still to set up before it can be published:" in home
    published = client.get(f"/applydesk/operator/exercises/{EX}").text
    assert "<h2>Publish</h2>" not in published


def test_dates_hold_to_what_a_stage_says() -> None:
    """Cold read of rung 2: an impossible day or an end before its start
    is no dates; a year rolls over from the stage before; a hyphen serves
    as the dash; one date is a one-day stage."""
    after = date(2026, 9, 1)
    assert timeline._dates("31 Feb – 3 Mar", after) == (None, None)  # pyright: ignore[reportPrivateUsage]  -- the parser itself
    assert timeline._dates("3 Oct 2026 – 1 Oct 2026", after) == (None, None)  # pyright: ignore[reportPrivateUsage]  -- as above
    assert timeline._dates("5 Jan - 30 Jan", date(2026, 12, 20)) == (  # pyright: ignore[reportPrivateUsage]  -- as above
        date(2027, 1, 5),
        date(2027, 1, 30),
    )
    assert timeline._dates("30 Sep", after) == (date(2026, 9, 30), date(2026, 9, 30))  # pyright: ignore[reportPrivateUsage]  -- as above
    assert timeline._dates("1 September 2026 – 3 Oct", after)[0] == date(2026, 9, 1)  # pyright: ignore[reportPrivateUsage]  -- as above


def test_today_between_stages_is_said_and_marked() -> None:
    gap = _of(EX, date(2026, 11, 7))
    assert [s.state for s in gap.stages] == ["Closed", "Done", "Next"]
    assert gap.today_text == "Today, 7 Nov, is between Review and Interviews."
    assert gap.today_at == pytest.approx(gap.stages[2].offset)
    assert _of(EX, date(2026, 8, 1)).today_text == "Today, 1 Aug, is before Applications."
    assert _of(EX, date(2026, 11, 6)).stages[1].state == "Now"  # its last day is in it
    assert _of(DRAFT).today_at is None and _of(DRAFT).today_text == ""


def test_an_outcome_released_to_others_reads_as_to_come(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from applydesk import stages

    plan = stages.plan_of(EX)
    o1 = next(c for c in plan.columns if isinstance(c, stages.Outcome) and c.key == "o1")
    hidden = replace(o1, released="6 Nov · to panels")
    monkeypatch.setattr(
        stages,
        "plan_of",
        lambda _: replace(
            plan,
            stages=tuple(
                replace(st, columns=tuple(hidden if c is o1 else c for c in st.columns))
                for st in plan.stages
            ),
        ),
    )
    items = _of(EX).stages[1].items
    assert items[-1] == timeline.Item(
        "outcome-due", "Outcome · expected December 2026", "Shortlisting."
    )


def test_a_mix_of_dated_and_undated_stages_shares_the_track(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two dated stages take two-thirds, by their days; the undated one
    the third that is left."""
    from dataclasses import replace

    from applydesk import stages

    plan = stages.plan_of(EX)
    undated = replace(plan.stages[2], dates="Dates not set")
    monkeypatch.setattr(
        stages, "plan_of", lambda _: replace(plan, stages=(*plan.stages[:2], undated))
    )
    t = _of(EX)
    assert [round(s.share, 4) for s in t.stages] == [
        round(30 / 67 * 2 / 3, 4),
        round(37 / 67 * 2 / 3, 4),
        round(1 / 3, 4),
    ]
    assert t.stages[2].state == "Next" and sum(s.share for s in t.stages) == pytest.approx(1.0)


def test_the_status_row_says_one_draft(client: TestClient) -> None:
    text = client.get("/applydesk/operator/exercises/r6tm4kq9wz").text
    assert "1 submitted · 1 draft<" in text
