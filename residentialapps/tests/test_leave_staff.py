"""RA Leave's staff pages (`/ra-leave/staff/`), segment 1C item 1:
placeholders on `sample_leave`, drawn for a sample viewer chosen with
`?as=` (an RF, the admin, the Master)."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from residentialapps.residentialops import sample_leave
from residentialapps.residentialops.main import create_app as ops_app

STAFF = "/ra-leave/staff/"
RACHEL = "?as=Rachel%20Yeo"
SAM = "?as=Sam%20Lee"


def client() -> TestClient:
    return TestClient(ops_app())


def ids(html: str, section: str) -> list[str]:
    part = html.split(f'id="{section}"')[1].split("</section>")[0]
    return re.findall(r'href="/ra-leave/staff/decide/(L-\d+)', part)


def test_every_staff_page_answers_for_each_sample_viewer() -> None:
    c = client()
    for query, name in (("", "Daniel Koh"), (RACHEL, "Rachel Yeo"), (SAM, "Sam Lee")):
        for path in ("", "decide", "decided", "precinct"):
            page = c.get(STAFF + path + query)
            assert page.status_code == 200, (path, query)
            assert "Sample data" in page.text and f"Viewing as {name}" in page.text, (path, query)
            assert 'aria-current="true">' in page.text
    tabs = c.get(STAFF + RACHEL).text.split('class="tabs-in"')[1].split("</nav>")[0]
    assert re.findall(r'<a href="([^"]*)"', tabs) == [
        f"/ra-leave/staff/{p}{RACHEL}" for p in ("", "decide", "decided", "precinct")
    ]
    assert sample_leave.staff_viewer("Nobody") == "Daniel Koh"


def test_each_viewer_s_queue_is_the_decision_theirs_to_make() -> None:
    """Spec §16, §24: first approval for the slot's approver, final for the
    policy's final approver, appeals for the Master; oldest first."""
    c = client()
    assert ids(c.get(STAFF + "decide").text, "queue-h") == ["L-0109", "L-0101", "L-0114"]
    assert ids(c.get(STAFF + "decide" + RACHEL).text, "queue-h") == ["L-0103"]
    assert ids(c.get(STAFF + "decide" + SAM).text, "queue-h") == ["L-0105"]
    home = c.get(STAFF).text
    tiles = re.findall(r'<span class="tile-n">(\d+)</span><span class="tile-l">([^<]*)', home)
    assert tiles == [("3", "Awaiting my decision"), ("2", "Of those, waiting on cover"), ("1", "Decided")]
    waiting = c.get(STAFF + "decide?cover=waiting").text
    assert ids(waiting, "queue-h") == ["L-0109", "L-0114"]
    assert 'href="/ra-leave/staff/decide?as=Sam%20Lee&amp;cover=waiting"' in c.get(STAFF + SAM).text


def test_decide_shows_entitlement_cover_and_precinct_context() -> None:
    c = client()
    hana = c.get(STAFF + "decide/L-0109").text
    assert ">Waiting on cover</span> Chloe Lim has declined; the RA must name new cover" in hana
    assert ">Approve</button>" in hana
    assert "<dt>Available</dt><dd>0 days</dd>" in hana
    appeal = c.get(STAFF + "decide/L-0105" + SAM).text
    assert "Decide the appeal" in appeal and "<dt>Beyond entitlement</dt><dd>4 days</dd>" in appeal
    assert "kept apart from the entitlement" in appeal
    clash = c.get(STAFF + "decide/L-0108" + SAM).text  # Pranav Iyer, decided: read-only
    assert "Decided; shown read-only." in clash and ">Approve</button>" not in clash
    ctx = clash.split('id="ctx-h"')[1].split("</section>")[0]
    assert "Olivia Ng" in ctx


def test_a_staff_member_sees_only_their_scope() -> None:
    """Spec §22: an RF their Precinct(s), the admin and the Master the
    whole Unit; Decide 404s outside the viewer's scope."""
    c = client()
    assert sample_leave.scope("Daniel Koh") == ("Cypress A 04-12",)
    assert len(sample_leave.scope("Marcus Tan")) == 3  # an RSLM: the Maple Wing
    assert len(sample_leave.scope("Sam Lee")) == 9
    assert c.get(STAFF + "decide/L-0105").status_code == 404  # Maple 09-14, not Daniel Koh's
    assert c.get(STAFF + "decide/L-9999" + SAM).status_code == 404
    precinct = c.get(STAFF + "precinct").text
    assert "Isaac Goh" not in precinct and "Ethan Wong" in precinct


def test_decided_lists_the_viewer_s_own_decisions() -> None:
    c = client()
    assert ids(c.get(STAFF + "decided").text, "dec-h") == ["L-0115"]
    rachel = c.get(STAFF + "decided" + RACHEL).text
    assert len(ids(rachel, "dec-h")) == 6 and "Final approval: Approved" in rachel
    assert "None yet." in c.get(STAFF + "decided" + SAM).text


def test_whatever_a_viewer_may_decide_opens(monkeypatch) -> None:
    """Every row in a viewer's queue or Decided list opens Decide, under
    each approval setting, a delegate's and a named approver's included."""
    import itertools

    c = client()
    people = ("Daniel Koh", "Rachel Yeo", "Sam Lee", "Benjamin Chua", "Grace Ho", "Marcus Tan", "Mei Ling Tan")
    settings = (
        {}, {"first_types": ("RF", "RSLM")}, {"first": "none"},
        {"final": "named", "final_names": ("Daniel Koh",)}, {"appeals": "Off"},
    )
    for setting, day in itertools.product(settings, (None, sample_leave.date(2026, 12, 10))):
        with monkeypatch.context() as m:
            for key, value in setting.items():
                m.setitem(sample_leave.POLICY, key, value)
            if day:
                m.setattr(sample_leave, "routes", lambda d=None, _r=sample_leave.routes: _r(day))
            for person in people:
                for a in [a for a, _ in sample_leave.queue(person)] + [a for a, _, _ in sample_leave.decided(person)]:
                    assert sample_leave.can_open(person, a), (setting, day, person, a.id)
    assert c.get(STAFF + "decide/L-0103?as=Benjamin%20Chua").status_code == 404  # not a staff viewer: defaults to Daniel
    assert sample_leave.can_open("Benjamin Chua", sample_leave.by_id("L-0103"))  # standing in for Grace Ho


def test_with_no_first_approval_rejections_belong_to_the_final_approver(monkeypatch) -> None:
    monkeypatch.setitem(sample_leave.POLICY, "first", "none")
    assert ("L-0110", "Final approval", "Rejected") in [(a.id, r, o) for a, r, o in sample_leave.decided("Rachel Yeo")]


def test_decide_shows_the_applicant_s_other_leave_and_precinct_numbers() -> None:
    c = client()
    appeal = c.get(STAFF + "decide/L-0105" + SAM).text.split('id="own-h"')[1].split("</section>")[0]
    assert appeal.count("<li>") == 2 and "17 Aug – 19 Aug" in appeal
    rows = re.findall(r'<td class="strong nowrap">([^<]*)</td><td class="num">(\d+)</td><td class="num">(\d+)</td><td class="num">(\d+)</td>',
                      c.get(STAFF + "precinct" + SAM).text)
    assert ("Willow A 13-25", "4", "2", "0") in rows and len(rows) == 9
