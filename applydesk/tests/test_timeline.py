"""Exercise Home's timeline and Details (segment AD1I, rung 2): the
timeline drawn from Process's stages by `applydesk/timeline.py`, and Home
in two columns with the old fact cards folded away."""

from __future__ import annotations

import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from applydesk import clock, sample_data, stages, timeline, tones
from applydesk.tests._host import host_with

EX = "wa9juxbc2t"  # the RA recruitment, mid Stage 3
DRAFT = "c4xh2ndv6s"  # no dates set
PCG = "r6tm4kq9wz"  # one stage across the year's end


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0])


def _of(exercise_id: str, today: date = clock.SAMPLE_TODAY) -> timeline.Timeline:
    e = sample_data.exercise(exercise_id)
    assert e is not None
    return timeline.of(e, today)


def test_each_stage_has_its_dates_state_and_progress() -> None:
    t = _of(EX)
    assert [(s.name, s.when, s.state) for s in t.stages] == [
        ("Applications", "1–30 Sep 2026", "Closed"),
        ("Review", "1 Oct – 6 Nov 2026", "Done"),
        ("Interviews", "9 Nov – 4 Dec 2026", "Now"),
    ]
    assert (t.start, t.end) == (date(2026, 9, 1), date(2026, 12, 4))
    assert t.now is t.stages[2] and t.stages[2].progress == pytest.approx(8.5 / 26)


def test_a_stage_s_state_follows_today() -> None:
    before = _of(EX, date(2026, 8, 1))
    assert [s.state for s in before.stages] == ["Next", "Next", "Next"]
    after = _of(EX, date(2027, 1, 1))
    assert [s.state for s in after.stages] == ["Closed", "Done", "Done"]
    e = sample_data.exercise(EX)
    assert e is not None
    assert timeline.next_step(e, after) == "Every stage is done."
    assert timeline.next_step(e, before) == "Next: Applications, from 1 Sep."


def test_dates_roll_over_the_year_and_undated_stages_wait() -> None:
    pcg = _of(PCG)
    assert (pcg.stages[0].start, pcg.stages[0].end) == (date(2026, 11, 1), date(2027, 1, 31))
    assert pcg.stages[0].state == "Now"
    draft = _of(DRAFT)
    assert [(s.when, s.state, s.progress) for s in draft.stages] == [
        ("Dates not set", "Next", 0.0),
        ("Dates not set", "Next", 0.0),
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
    # The stage under way's outcome due is its Next item (AD1S).
    assert t.stages[2].items[-1] == timeline.Item(
        "next", "Next: Outcome · expected December 2026", "Selection."
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
    assert 'data-tl-p="32.7"' in home
    # Equal widths (Decision amended): no proportions ride the page.
    assert "data-tl-flex" not in home and "tl-scale" not in home
    # Three stages start Horizontal; the switch shows once the script runs.
    assert 'data-timeline data-layout="h" data-tl-count="3"' in home
    assert '<div class="tl-switch" role="group" aria-label="Timeline layout" hidden>' in home
    # Now on the timeline itself (AD1S): the marker, and the Next item;
    # no line under the timeline while a stage is under way.
    assert "<span>Now · until 4 Dec</span>" in home
    assert "<b>Next: Outcome · expected December 2026</b>Selection." in home
    assert "Now: " not in home and "data-tl-next" not in home
    # The old fact cards are gone: their facts are the status row's and
    # the timeline's.
    for gone in ("Where it stands", "<h2>Counts</h2>", "<h2>Next step</h2>", 'class="lede"'):
        assert gone not in home, gone
    assert "100 submitted · 3 drafts" in home
    # Details: Description where Summary was, locked until rung 4.
    details = home[home.index('id="details"') :]
    assert "<dt>Description</dt>" in details and "Summary" not in details
    assert 'data-dt-lock title="Unlock the details to change them">Unlock' in details
    # The Now stage's operator part points to where the stage is worked:
    # its gate's row links that gate's page (AD-24); no second row repeats
    # the link once the line under the timeline is gone (AD1S).
    now = home[home.index('data-tl-stage="3"') :]
    now = now[: now.index("</ol>")]  # the last stage: up to the list's end
    link = f'<a href="/applydesk/operator/exercises/{EX}/evaluations/gate_3">Open Gate 3 →</a>'
    assert now.count(link) == 1
    assert "data-tl-next" not in home


def test_a_draft_s_home_says_what_publishing_needs(client: TestClient) -> None:
    home = client.get(f"/applydesk/operator/exercises/{DRAFT}").text
    assert home.count("Dates not set") == 2 and 'class="tl-today"' not in home
    assert "A draft: the timeline is what participants will see once it is published." in home
    # What blocks each stage, in the operator part (AD1K, at the author's
    # check: no Publish card); a published exercise has none to show.
    assert home.count("Blocking publication") == 2
    published = client.get(f"/applydesk/operator/exercises/{EX}").text
    assert "Blocking publication" not in published and "data-hm-publish" not in published


def test_a_stage_s_dates_are_typed_and_printed_as_before() -> None:
    """Segment AD1K (AD-56): a stage declares its start and end as
    date-times, so nothing parses text; a bare day's end is its last
    minute, and the pages print the days as before."""
    when = stages.span(stages.day(2026, 9, 1), stages.day(2026, 9, 30))
    assert when.end == stages.day(2026, 9, 30, 23, 59)
    st = stages.Stage(1, "Applications", when, form=True)
    assert st.dates == "1–30 Sep 2026"
    assert stages.Stage(2, "", None).dates == "Dates not set"
    # A year's turn needs no inference: the dates say it.
    pcg = _of(PCG)
    assert (pcg.stages[0].start, pcg.stages[0].end) == (date(2026, 11, 1), date(2027, 1, 31))


def test_today_between_stages_is_said_and_marked() -> None:
    gap = _of(EX, date(2026, 11, 7))
    assert [s.state for s in gap.stages] == ["Closed", "Done", "Next"]
    assert gap.today_text == "Today, 7 Nov, is between Review and Interviews."
    assert _of(EX, date(2026, 8, 1)).today_text == "Today, 1 Aug, is before Applications."
    assert _of(EX, date(2026, 11, 6)).stages[1].state == "Now"  # its last day is in it
    assert _of(DRAFT).today_text == ""


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


def test_past_four_stages_the_timeline_starts_vertical(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decision 3: an exercise of five stages starts Vertical."""
    from dataclasses import replace

    from applydesk import stages

    plan = stages.plan_of(EX)
    more = tuple(replace(plan.stages[2], number=n) for n in (4, 5))
    monkeypatch.setattr(stages, "plan_of", lambda _: replace(plan, stages=(*plan.stages, *more)))
    home = client.get(f"/applydesk/operator/exercises/{EX}").text
    assert 'data-timeline data-layout="v" data-tl-count="5"' in home


def test_the_status_row_says_one_draft(client: TestClient) -> None:
    text = client.get("/applydesk/operator/exercises/r6tm4kq9wz").text
    assert "1 submitted · 1 draft<" in text


def test_the_applicant_s_page_shows_the_same_timeline_and_nothing_operator_only(
    client: TestClient,
) -> None:
    """Rung 5: the partial Home draws, as applicants see it; no Next step
    line, no link into operator pages, and none of Process's machinery:
    panels, their members, modes, rules or pair counts."""
    from applydesk import stages

    mine = client.get(f"/applydesk/me/exercises/{EX}").text
    home = client.get(f"/applydesk/operator/exercises/{EX}").text

    def stages_of(page: str) -> str:
        return page[
            page.index('<ol class="tl-stages">') : page.index(
                "</ol>", page.index('<ol class="tl-stages">')
            )
        ]

    # The participants' part alike; Home adds only its operator part, and
    # names each stage by its status where applicants read where it
    # stands (ruling 64, U2).
    home_part = re.sub(
        r'\s*<div class="tl-op" data-tl-op>.*?\n      </div>', "", stages_of(home), flags=re.S
    )
    assert "data-tl-op" in home and "data-tl-op" not in mine

    def heads(part: str) -> str:
        return re.sub(
            r'(<h3 class="tl-name">[^<]*)<span class="chip[^"]*">[^<]*</span>', r"\1", part
        )

    assert re.sub(r"\s+", " ", heads(home_part)) == re.sub(r"\s+", " ", heads(stages_of(mine)))
    assert re.findall(r'class="tl-name">[^<]*<span class="chip[^"]*">([^<]*)', home) == [
        "Completed",
        "Completed",
        "Published",
    ]
    assert "Today, 17 Nov, is in Interviews." in mine
    assert "Results expected December 2026 (an estimate)." in mine
    timeline_card = mine[
        mine.index("data-timeline") : mine.index("</section>", mine.index("data-timeline"))
    ]
    # The header's Operator Lobby link is the signed-in operator's, not the card's.
    assert "data-tl-next" not in timeline_card and "/operator/" not in timeline_card
    plan = stages.plan_of(EX)
    pools = sample_data.panel_pools(EX)
    operator_only = [p["name"] for p in pools.values()]
    operator_only += [name for p in pools.values() for name, _ in p["members"]]
    operator_only += [label for _, label in stages.MODES]
    operator_only += [stages.rule_text(plan, c) for c in plan.columns if stages.rule_text(plan, c)]
    operator_only += ["pairs", "Evaluations", "≥"]
    for text in operator_only:
        assert text not in timeline_card, text


def test_home_s_operator_part_says_how_each_stage_stands() -> None:
    """Decision amended again: per stage, the form's state and counts, each
    gate's state, mode, evaluators, pairs and progress, each outcome's
    state and counts; a draft's gates link nowhere yet."""
    from applydesk import home_ops

    e = sample_data.exercise(EX)
    assert e is not None
    rows = home_ops.of(e)
    assert [[r.label for r in st] for st in rows] == [
        ["Form"],
        # A gate as Gate N · label (U4, AD-91); an outcome by its label.
        ["Gate 1 · Peer review", "Gate 2 · Office checks", "Shortlisting"],
        ["Gate 3 · Staff interview", "Selection"],
    ]
    form, (g1, _, o1), (g3, o2) = rows[0][0], rows[1], rows[2]
    assert (form.state, form.detail) == ("Closed", "100 submitted · 3 drafts")
    assert (g1.state, g1.target) == ("Results in", "1")
    assert "2,980 pairs · 100 of 100 reviewed" in g1.detail
    assert g3.detail == (
        "Suggested, then approved · Residential staff 2 · Total 2 · 80 pairs"
        " · 40 dossiers to approve"
    )
    assert (o1.state, o1.detail) == (
        "Released",
        "15 re-appointment · 40 interview · released 6 Nov to applicants",  # Dossiers' tally
    )
    assert (o2.state, o2.detail, o2.target) == ("Pending", "55 pending", "dossiers")
    # Each tone by the one map, as Dossiers': Pending amber (AD-75).
    assert (o1.tone, o2.tone) == ("ok", "warn")
    assert all(r.tone == tones.TONE[r.state] for st in rows for r in st if r.state in tones.TONE)
    draft = sample_data.exercise(DRAFT)
    assert draft is not None
    assert home_ops.of(draft)[1][0].target == ""


def test_home_draws_the_operator_part_and_links_where_it_is_worked(client: TestClient) -> None:
    home = client.get(f"/applydesk/operator/exercises/{EX}").text
    assert home.count("data-tl-op") == 3 and 'class="card tl tl-ops"' in home
    assert f'href="/applydesk/operator/exercises/{EX}/evaluations/gate_3">Open Gate 3 →</a>' in home
    assert f'href="/applydesk/operator/exercises/{EX}/dossiers">Open Dossiers →</a>' in home


def test_a_stage_not_shown_to_applicants_is_not_on_theirs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling 46, AD-09: Process's *Shown to applicants* is modelled: a
    stage left unticked is hidden from the applicant's timeline only."""
    import dataclasses

    plan = stages.plan_of(EX)
    hidden = plan.stages[1]
    sts = tuple(dataclasses.replace(s, shown=False) if s is hidden else s for s in plan.stages)
    monkeypatch.setattr(stages, "plan_of", lambda _id: dataclasses.replace(plan, stages=sts))
    e = sample_data.exercise(EX)
    assert e is not None
    mine = [v.number for v in timeline.of(e, applicant=True).stages]
    theirs = [v.number for v in timeline.of(e).stages]
    assert hidden.number not in mine and hidden.number in theirs
    process = client.get(f"/applydesk/operator/exercises/{EX}/process").text
    assert 'data-pc="shown"> Shown to applicants' in process  # its tick unticked


def test_the_timeline_names_its_audience_and_carries_now() -> None:
    """Segment AD1S: participants are applicants and evaluators alike, so
    no item says *You*; while a stage is under way the timeline carries
    Now and Next, and the line under it says nothing."""
    t = _of(EX)
    assert t.stages[0].items[0] == timeline.Item(
        "applicants", "Applicants", "Apply online with the application form."
    )
    said = [i.kicker for s in t.stages for i in s.items]
    assert "You" not in said and not any(k.startswith("You ") for k in said)
    e = sample_data.exercise(EX)
    assert e is not None
    assert timeline.next_step(e, t) == ""
    # Only the stage under way has a Next item, and only for an outcome
    # still due: mid Stage 2, Shortlisting is released, Selection is later.
    stage2 = _of(EX, date(2026, 10, 20))
    assert not [i for s in stage2.stages for i in s.items if i.kind == "next"]
    assert stage2.stages[2].items[-1].kind == "outcome-due"


def test_the_applicant_s_timeline_carries_now_but_no_operator_row(client: TestClient) -> None:
    page = client.get(f"/applydesk/me/exercises/{EX}").text
    mine = page[page.index("data-timeline") : page.index("</section>", page.index("data-timeline"))]
    assert "<span>Now · until 4 Dec</span>" in mine
    assert "<b>Next: Outcome · expected December 2026</b>Selection." in mine
    assert "<b>Applicants</b>Apply online" in mine and "<b>You</b>" not in mine
    for operator in ("Operator only", "tl-op", "Open Gate"):
        assert operator not in mine, operator
