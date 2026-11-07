"""Support Logs' frontline pages on sample data, segment 1D item 1 rung 2:
the dashboard, Log encounter and its confirmation, Students, the student
view, Students holding the plans and follow-ups (UI spec screens 1–3,
5–7)."""

from __future__ import annotations

import dataclasses
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.main import create_app
from residentialapps.supportlogs.pages import reaches_student
from residentialapps.tests._host import host_with

PRIYA = "?as=Priya%20Raman"
FRONTLINE_PAGES = (
    "/",
    "/log",
    "/students/",
    "/students/S-03",
    "/log/saved?student=S-02&duration=15%20min&type=Check-in",
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def section(page: str, heading_id: str) -> str:
    return page.split(f'id="{heading_id}"')[1].split("</section>")[0]


def names(html: str) -> list[str]:
    return re.findall(r'<a class="strong" href="[^"]*">([^<]+)</a>', html)


def test_the_dashboard_puts_the_most_urgent_first(client: TestClient) -> None:
    """§10.1: due and overdue, overdue first, each with Log; the chips say
    the state in words."""
    due = section(client.get("/").text, "due-h")
    assert names(due) == ["Clara Tan", "Aiden Chen", "Dev Menon"]
    assert re.findall(r'<span class="chip (chip-\w+)">((?:Overdue|Due)[^<]*)</span>', due) == [
        ("chip-warn", "Overdue 2 days"),
        ("chip-info", "Due today"),
        ("chip-mute", "Due Mon 2 Nov"),
    ]
    assert 'href="/log?student=S-03" aria-label="Log an encounter with Clara Tan">Log</a>' in due
    assert '<span class="chip chip-marker">Safety-plan support</span>' in due


def test_the_dashboard_follows_recent_and_the_last_14_days(client: TestClient) -> None:
    page = client.get("/").text
    following = section(page, "following-h")
    assert "· 4</span>" in following and names(following) == [
        "Clara Tan",
        "Dev Menon",
        "Aiden Chen",
    ]
    assert 'href="/students/">On Students</a>' in following
    assert names(section(page, "recent-h")) == [
        "Farid Osman",
        "Elena Park",
        "Bao Nguyen",
        "Aiden Chen",
    ]
    days = section(page, "mine-h")
    assert (
        "<dt>Encounters</dt><dd>6</dd><dt>Support time</dt><dd>120 min</dd>"
        "<dt>Students</dt><dd>6</dd>" in days
    )
    assert (
        "<dt>Check-in</dt><dd>4</dd>" in days
    )  # the two "…-initiated" encounters became Check-ins
    assert "The flags you raised" in page  # rung 3 fills the flags


def test_log_renders_the_configured_lists_as_choice_chips(client: TestClient) -> None:
    page = client.get("/log").text
    for name, values in [
        ("duration", sample.DURATIONS),
        ("type", sample.ENCOUNTER_TYPES),
        ("mode", sample.MODES),
        ("started", sample.STARTED_BY),
    ]:
        assert re.findall(rf'<input type="radio" name="{name}" value="([^"]+)"', page) == list(
            values
        ), name
    assert re.findall(r'name="concern" value="([^"]+)"', page) == [
        a for a, _ in sample.CONCERN_AREAS
    ]
    assert "data-says-who" not in page  # Who started it? is asked of every type
    assert f'maxlength="{sample.NOTE_LIMIT}"' in page and sample.NOTE_GUIDANCE in page
    assert '<textarea id="note"' in page and 'name="note"' not in page  # a sample sends no note
    assert page.count('data-clear="') == 3  # the optional single choices clear
    assert "<dt>Health and accessibility</dt><dd>medical matters" in page  # guidance without hover
    assert ' title="' not in page.split('id="log-form"')[1]
    assert (
        page.index('id="log-h"') < page.index("Add details") < page.index('id="save"')
    )  # details on the page
    assert 'formaction="/log/safety" formnovalidate>Mark a safety concern</button>' in page


def test_log_offers_the_viewer_s_students_or_the_one_chosen(client: TestClient) -> None:
    log = client.get("/log").text
    offered = re.findall(r'name="student" value="([^"]+)"', log)
    assert offered == list(sample.FAVORITES["Daniel Koh"]) == ["S-03", "S-08"]
    assert "Mark favorites on <a" in log and 'href="/students/">Students</a>' in log
    chosen = client.get("/log?student=S-03").text
    assert '<input type="hidden" name="student" value="S-03" data-plan=' in chosen
    assert '<span class="strong">Clara Tan</span><a href="/log">Change</a>' in chosen
    assert 'name="student" value="S-01"' not in chosen
    assert '<input type="hidden" name="as" value="Priya Raman">' in client.get("/log" + PRIYA).text


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_log_s_script_parses(client: TestClient, tmp_path: Path) -> None:
    scripts = re.findall(r"<script>(.*?)</script>", client.get("/log").text, re.S)
    assert len(scripts) >= 3  # the theme's, the sort's, and the form's
    for n, body in enumerate(scripts):
        source = tmp_path / f"s{n}.js"
        source.write_text(body)
        subprocess.run(["node", "--check", str(source)], check=True)


def test_the_confirmation_says_what_was_saved_and_offers_follow_up(client: TestClient) -> None:
    bao = client.get("/log/saved?student=S-02&duration=15%20min&type=Practical%20support").text
    assert "Practical support with Bao Nguyen, 15 min" in bao
    assert (
        "Bao Nguyen is not on your follow-ups." in bao and ">Add to my follow-ups</button>" in bao
    )
    clara = client.get("/log/saved?student=S-03&duration=15%20min&type=Check-in").text
    assert "Add to my follow-ups" not in clara  # Clara is on a plan already
    added = client.get("/log/saved?student=S-02&duration=15%20min&type=Check-in&follow=yes").text
    assert "Added to your follow-ups." in added
    assert "nothing is stored" in bao
    following = client.get(
        "/log/saved?student=S-03&duration=15%20min&type=Check-in&follow=yes"
    ).text
    assert "Added to your follow-ups." not in following  # on a plan already: nothing was added
    assert ">Open Bao Nguyen</a>" in bao
    stranger = client.get("/log/saved?student=S-09&duration=15%20min&type=Check-in").text
    assert "Open Ivan Seet" not in stranger  # not one of Daniel's: the view would be not found


def test_log_shows_the_plan_a_chosen_student_is_on(client: TestClient) -> None:
    clara = client.get("/log?student=S-03").text
    assert '<p id="on-plan" class="flush">On your plans: weekly, set by Sam Lee.</p>' in clara
    assert 'id="add-follow" hidden' in clara and 'id="cadence-field" hidden' in clara
    aiden = client.get("/log?student=S-01").text
    assert "On your follow-ups: weekly." in aiden and "Keep or change the cadence" in aiden
    assert "<option selected>Weekly</option>" in aiden
    bao = client.get("/log?student=S-02").text
    assert '<p id="on-plan" class="flush" hidden>' in bao and 'id="add-follow">' in bao
    chips = client.get("/log").text  # the favorites carry their plans too
    assert (
        'value="S-03" data-plan="On your plans: weekly, set by Sam Lee." '
        'data-cadence="Weekly" data-formal>' in chips
    )


def test_pages_naming_students_say_they_are_recorded(client: TestClient) -> None:
    for path in (
        "/",
        "/log",
        "/students/",
        "/log/saved?student=S-02&duration=15%20min&type=Check-in",
    ):
        assert "Pages that name students are recorded when opened." in client.get(path).text, path
    assert "Opening this view is recorded." in client.get("/students/S-03").text


def test_a_custom_cadence_says_so() -> None:
    plan = sample.Plan("P-99", "S-01", "Daniel Koh", False, sample.TODAY, "Custom")
    assert sample.due(plan) == ("none", "Custom cadence")


def test_an_incomplete_save_goes_back_to_the_form(client: TestClient) -> None:
    for query in (
        "",
        "?student=S-02&duration=15%20min",
        "?student=S-99&duration=15%20min&type=Check-in",
        "?student=S-02&duration=7%20min&type=Check-in",
    ):
        page = client.get("/log/saved" + query, follow_redirects=False)
        assert (page.status_code, page.headers["location"]) == (303, "/log"), query
    kept = client.get("/log/saved" + PRIYA, follow_redirects=False)
    assert kept.headers["location"] == "/log" + PRIYA


def test_students_lists_the_working_set(client: TestClient) -> None:
    """§4.3: plans and follow-ups first, then everyone seen, the latest
    first; each says why it is the viewer's."""
    page = client.get("/students/").text
    mine = section(page, "mine-h")
    assert names(mine) == [
        "Clara Tan",
        "Dev Menon",
        "Aiden Chen",
        "Elena Park",
        "Farid Osman",
        "Bao Nguyen",
        "Hana Rahim",  # his team's (rung 5), no record of his own
    ]
    assert ">Plan · Counselling</a>" in mine
    assert "bao.nguyen@u.example.edu · seen 24 Oct" in mine
    assert names(section(client.get("/students/" + PRIYA).text, "mine-h")) == [
        "Hana Rahim",
        "Jia Wen Lee",
        "Ivan Seet",
    ]


def test_the_student_view_shows_the_viewer_s_records(client: TestClient) -> None:
    page = client.get("/students/S-03").text
    assert "<h1>Clara Tan</h1>" in page and "clara.tan@u.example.edu" in page
    assert "Opening this view is recorded." in page
    assert re.findall(r'<span class="tile-n">([^<]+)</span><span class="tile-l">([^<]+)', page) == [
        ("Weekly", "Cadence"),
        ("20 Oct", "Last contact"),
        ("27 Oct", "Next due"),
    ]
    assert 'href="/log?student=S-03">Log encounter with Clara Tan</a>' in page
    assert section(page, "enc-h").count("<li>") == 2
    plan = section(page, "plan-h")
    assert "Safety-plan support" in plan and "Overdue 2 days" in plan and "<dd>Sam Lee</dd>" in plan
    assert "Flag for formal assignment" not in plan  # formally assigned already
    bao = client.get("/students/S-02").text
    assert "Not on your follow-ups." in bao and ">Start following up</button>" in bao
    assert 'aria-current="true">Students</a>' in page


def test_a_student_outside_the_working_set_is_not_found(client: TestClient) -> None:
    assert client.get("/students/S-09").status_code == 404  # Priya's, not Daniel's
    assert client.get("/students/S-09" + PRIYA).status_code == 200
    assert client.get("/students/S-99").status_code == 404


def test_students_filters_plans_and_follow_ups(client: TestClient) -> None:
    """My plans folded into Students (author, 2026-11-07): All, Plans or
    Following, kept in the browser; hidden without script, so every row
    shows. Each plan's chip opens it, beside its due state."""
    mine = section(client.get("/students/").text, "mine-h")
    assert "<div data-students-filter hidden>" in mine
    assert re.findall(r'data-show="(\w+)" aria-pressed="(\w+)">([^<]+)<', mine) == [
        ("all", "true", "All"),
        ("plans", "false", "Plans"),
        ("following", "false", "Following"),
        ("teams", "false", "Teams"),
    ]
    kinds = dict(zip(names(mine), re.findall(r'<li data-kinds="([^"]*)">', mine), strict=True))
    assert kinds == {
        "Clara Tan": "plans ",
        "Dev Menon": "plans ",
        "Aiden Chen": "following ",
        "Elena Park": "following ",
        "Farid Osman": "",
        "Bao Nguyen": "",
        "Hana Rahim": "teams",
    }
    assert (
        'href="/plans/P-01" aria-label="Plan · Counselling: Clara Tan">Plan · Counselling</a>'
        in mine
    )
    clara = mine.split("Clara Tan</a>")[1].split("</li>")[0]
    assert '<span class="chip chip-warn">Overdue' in clara  # her plan's due state
    assert "supportlogs-students-show" in client.get("/students/").text
    assert client.get("/plans/").status_code == 404  # My plans is gone


def test_students_rows_carry_my_plans_affordances(client: TestClient) -> None:
    """Author, 2026-11-07: each row's Log, a plan row's last contact and
    safety-plan instruction, and Add a student to follow up."""
    mine = section(client.get("/students/").text, "mine-h")
    logs = re.findall(r'href="/log\?student=(S-\d+)" aria-label="Log an encounter with', mine)
    assert logs == [s.id for s, _, _ in sample.working_set("Daniel Koh")] + ["S-08"]  # team
    clara = mine.split("Clara Tan</a>")[1].split("</li>")[0]
    assert "Weekly check-in; a reminder of the coping plan." in clara
    assert "· last contact 20 Oct" in clara
    dev = mine.split("Dev Menon</a>")[1].split("</li>")[0]
    assert "Fortnightly check-in on settling in." not in dev  # not a safety plan
    aiden = mine.split("Aiden Chen</a>")[1].split("</li>")[0]
    assert "· last contact 22 Oct" in aiden  # a follow-up's row too
    bao = mine.split("Bao Nguyen</a>")[1].split("</li>")[0]
    assert "· seen 24 Oct" in bao and "last contact" not in bao
    assert (
        "<div data-students-add>"
        '<button type="button" class="btn btn-secondary gap-above-sm" disabled>'
        "Add a student to follow up</button>"
    ) in mine


def test_each_plan_on_a_row_carries_its_own_due_state(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A student on a plan and a follow-up is in both filters, each plan
    with its chip and due state."""
    aiden = next(p for p in sample.PLANS if p.id == "P-03")
    extra = dataclasses.replace(aiden, id="P-98", formal=True, source="College")
    monkeypatch.setattr(sample, "PLANS", [*sample.PLANS, extra])
    mine = section(client.get("/students/").text, "mine-h")
    row = mine.split("Aiden Chen</a>")[0].rsplit("<li ", 1)[1]
    assert row.startswith('data-kinds="plans following ')
    after = mine.split("Aiden Chen</a>")[1].split("</li>")[0]
    assert after.count('class="chip chip-info">Due today') == 2
    assert ">Plan · College</a>" in after and ">Following</a>" in after


def test_the_frontline_pages_are_the_frontline_s(client: TestClient) -> None:
    for path in (*FRONTLINE_PAGES[1:], "/students/S-99"):
        assert (
            client.get(path + ("&" if "?" in path else "?") + "as=Sam%20Lee").status_code == 403
        ), path


def test_mounted_frontline_pages_stay_under_the_mount() -> None:
    host, _ = host_with(("supportlogs",))
    mounted = TestClient(host)
    for path in FRONTLINE_PAGES:
        page = mounted.get("/supportlogs" + path)
        assert page.status_code == 200, path
        for link in re.findall(
            r'\b(?:href|action|src)="([^"]*)"', re.sub(r'<link rel="icon"[^>]*>', "", page.text)
        ):
            assert link in ("/", "/.auth/logout") or link.startswith(("/supportlogs/", "#")), (
                path,
                link,
            )
    back = mounted.get("/supportlogs/log/saved", follow_redirects=False)
    assert back.headers["location"] == "/supportlogs/log"


def test_favorites_drive_log_and_are_marked_on_students(client: TestClient) -> None:
    """Author, 2026-11-06 (`residentialapps/guide/1D_refinements.md`): a
    star on Students marks a favorite; Log offers the favorites; three
    durations; no "…-initiated conversation" type."""
    assert sample.DURATIONS == ("15 min", "30 min", "60+ min")
    assert sample.ENCOUNTER_TYPES == ("Check-in", "Welfare follow-up", "Practical support", "Other")
    students = client.get("/students/").text
    pressed = re.findall(
        r'data-favorite aria-pressed="true" aria-label="Favorite ([^"]+)"', students
    )
    assert pressed == ["Clara Tan", "Hana Rahim"]  # Hana: his team's row, not again as shared
    for staff, picks in sample.FAVORITES.items():  # a favorite is a student you reach
        me = sample.viewer(staff)
        assert all(reaches_student(me, sid) for sid in picks), staff
    assert 'aria-pressed="false" aria-label="Favorite Dev Menon" disabled>☆</button>' in students
    assert "★ Favorite" not in students and "☆ Favorite" not in students  # the star alone
    priya = client.get("/log?as=Priya%20Raman").text
    assert re.findall(r'name="student" value="([^"]+)"', priya) == ["S-08", "S-10"]
    assert 'href="/students/?as=Priya%20Raman">Students</a>' in priya  # the hint keeps the viewer
    # A shared favorite saved for is one the viewer can open (cold read).
    saved = client.get("/log/saved?student=S-08&duration=15%20min&type=Check-in").text
    assert 'href="/students/S-08">Open Hana Rahim</a>' in saved


def test_waiting_for_you_holds_every_acknowledgement(client: TestClient) -> None:
    """Sharing screens rung 2 (author, 2026-11-07): a share offered, a team
    invitation, a handover and a senior's share request, each with Agree
    and Decline, inert and named for its row; none names its student until
    agreed, but a request about the staff member's own records."""
    card = section(client.get("/").text, "waiting-h")
    assert card.count("<li>") == len(sample.pending_for("Daniel Koh")) == 4
    for name in ("Ivan Seet", "Jia Wen Lee", "Gwyneth Low"):
        assert name not in card, name  # offered, invited, handed over: unnamed
    for line in (
        "Sam Lee asks you to share your records about Clara Tan",
        "only if you agree, or if a sys admin agrees for you in an emergency",
        "Priya Raman has shared 1 record about a student with you",
        "Sam Lee invites you to a team for a student",
        "Sam Lee is handing Mei Ling Tan's 3 records about a student over to you",
        "Once you and Mei Ling Tan agree, the records become yours; a sys admin"
        " may agree for Mei Ling Tan if they cannot be reached.",
        "only in an emergency can a sys admin agree for you",
    ):
        assert line in card.replace("&#39;", "'"), line
    for verb, role in (("Agree", "primary"), ("Decline", "secondary")):
        labels = re.findall(rf'class="btn btn-{role}" disabled aria-label="{verb} ([^"]+)"', card)
        assert sorted(labels) == sorted(
            [
                "Priya Raman&#39;s share",
                "Sam Lee&#39;s team invitation",
                "Sam Lee&#39;s handover",
                "Sam Lee&#39;s request",
            ]
        ), verb  # each names its row
    assert 'href="/students/' not in card
    assert 'id="waiting-h"' not in client.get("/" + PRIYA).text  # nothing waits on her


def test_an_encounter_can_be_shared_as_it_is_logged(client: TestClient) -> None:
    """Sharing screens rung 4 (author, 2026-11-07): one colleague, this one
    encounter, agreed before they see it; never oneself."""
    log = client.get("/log").text
    share = log.split('id="share"')[1].split("</select>")[0]
    assert re.findall(r"<option>([^<]+)</option>", share) == [
        c for c in sample.FRONTLINE_COLLEAGUES if c != "Daniel Koh"
    ]
    assert '<option value="">No one</option>' in share
    base = "/log/saved?student=S-02&duration=15%20min&type=Check-in"
    sent = client.get(base + "&share=Mei%20Ling%20Tan").text
    assert "Mei Ling Tan is asked to agree to this encounter. Until they do" in sent
    for who in ("", "Daniel%20Koh", "Nobody"):
        assert "is asked to agree" not in client.get(base + "&share=" + who).text, who


def test_share_as_you_log_is_folded_away_and_follows_the_viewer(client: TestClient) -> None:
    """The share sits among the optional details, labelled and described;
    another viewer is offered everyone but themselves."""
    log = client.get("/log").text
    start = log.index('<details class="more gap-above-sm">')
    end = log.index("</details>", log.index('id="note"'))  # the note closes Add details
    assert start < log.index('id="share"') < end  # folded away with the other details
    assert '<label for="share">Share this encounter with</label>' in log
    assert 'aria-describedby="share-what"' in log and 'id="share-what"' in log
    priya = client.get("/log" + PRIYA).text.split('id="share"')[1].split("</select>")[0]
    assert re.findall(r"<option>([^<]+)</option>", priya) == [
        c for c in sample.FRONTLINE_COLLEAGUES if c != "Priya Raman"
    ]


def test_a_team_shows_on_students_and_on_both_pages(client: TestClient) -> None:
    """Sharing screens rung 5 (author, 2026-11-07): Priya Raman and Daniel
    Koh's team for Hana Rahim; Teams filters it; Form a team is inert."""
    for viewer, other in (("", "Priya Raman"), (PRIYA, "Daniel Koh")):
        mine = section(client.get("/students/" + viewer).text, "mine-h")
        row = mine.split("Hana Rahim</a>")[0].rsplit("<li ", 1)[1]
        assert "teams" in row, viewer
        assert f'<span class="chip chip-info">Team</span> with {other}' in mine
    team = section(client.get("/students/S-08").text, "team-h")
    assert "Priya Raman, Daniel Koh" in team and ">Leave the team</button>" in team
    other = section(client.get("/students/S-03").text, "team-h")
    assert ">Form a team</button>" in other and "disabled" in other
    senior = section(client.get("/overview/students/S-03?as=Sam%20Lee").text, "team-h")
    assert ">Form a team</button>" in senior and "You are not in it" in senior
    across = section(client.get("/overview/?as=Sam%20Lee").text, "across-h")
    hana = across.split("Hana Rahim</a>")[1].split("</tr>")[0]
    assert '<span class="chip chip-info">Team</span>' in hana


def test_a_team_reaches_its_student_without_a_share(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A team member reaches the team's student whether or not anyone has
    shared with them; a non-member sees the team, not Form a team."""
    monkeypatch.setattr(sample, "PEER_GRANTS", ())
    assert client.get("/students/S-08").status_code == 200  # Daniel: his team only
    team = section(client.get("/students/S-08").text, "team-h")
    assert ">Leave the team</button>" in team
    other = sample.Team("T-02", "S-03", ("Mei Ling Tan", "Grace Ho"), sample.TODAY, "Grace Ho")
    monkeypatch.setattr(sample, "TEAMS", (*sample.TEAMS, other))
    clara = section(client.get("/students/S-03").text, "team-h")  # Daniel's own student
    assert "Mei Ling Tan, Grace Ho" in clara and "You are not in it." in clara
    assert "Form a team" not in clara
    across = section(client.get("/overview/?as=Sam%20Lee").text, "across-h")
    for row in across.split("<tr>")[1:]:
        named = "Hana Rahim</a>" in row or "Clara Tan</a>" in row
        assert ('<span class="chip chip-info">Team</span>' in row) == named, row[:80]
