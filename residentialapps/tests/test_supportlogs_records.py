"""Support Logs' Your records on sample data, segment 1D item 1 rung 7
(author, 2026-10-30): a section at the end of Students and My plans,
locked until confirmed, to download the viewer's own encounters or plans
as CSV by term or all, upload a CSV, or purge them all; a purge hides and
keeps, and only senior identifiable access deletes, a whole purge at a time."""

from __future__ import annotations

import csv
import io
import re
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.main import create_app
from residentialapps.tests._host import host_with

TERMS_CSV = Path(__file__).resolve().parents[1] / "docs" / "sample_data" / "terms.csv"
OPEN = "records=open&understood=yes"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def rows(body: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(body)))


def test_the_terms_are_the_rosters(client: TestClient) -> None:
    with TERMS_CSV.open(newline="") as f:
        terms = [(f"{r['Year']}.{r['Term']}", r["Name"], r["Start"], r["End"]) for r in csv.DictReader(f)]
    assert [(t.key, t.name, t.start.isoformat(), t.end.isoformat()) for t in sample.TERMS] == terms
    assert sample.CURRENT_TERM.label == "AY2026-2027, Term 1 · Sem 1 + Winter break"  # as Rosters and setup shows it
    assert sample.CURRENT_TERM.key == "AY2026-2027.1"


@pytest.mark.parametrize("page", ["/students/", "/plans/"])
def test_the_section_is_locked_until_confirmed(client: TestClient, page: str) -> None:
    locked = client.get(page).text
    card = locked.split('id="records-h"')[1]
    assert ">Locked</span>" in card and 'name="understood" value="yes" required' in card
    assert "records.csv" not in locked and "Purge all" not in locked
    assert "records.csv" not in client.get(page + "?records=open").text  # not without the confirmation
    unlocked = client.get(f"{page}?{OPEN}").text
    assert ">Unlocked</span>" in unlocked and "records.csv" in unlocked and "Lock again" in unlocked
    terms = re.findall(r'<option value="([^"]+)"( selected)?>', unlocked.split('id="dl-term"')[1].split("</select>")[0])
    assert [k for k, _ in terms] == [t.key for t in sample.TERMS] + ["all"]
    assert [k for k, s in terms if s] == [sample.CURRENT_TERM.key]


def test_the_unlock_keeps_the_page_s_own_filter(client: TestClient) -> None:
    form = client.get("/plans/?show=week").text.split('id="records-h"')[1].split("</form>")[0]
    assert '<input type="hidden" name="show" value="week">' in form
    assert '<input type="hidden" name="show"' not in client.get("/plans/").text.split('id="records-h"')[1]


def test_encounters_download_by_term_or_all(client: TestClient) -> None:
    current = client.get(f"/students/records.csv?{OPEN}&term={sample.CURRENT_TERM.key}")
    assert current.headers["content-disposition"] == 'attachment; filename="support-logs-encounters-AY2026-2027.1.csv"'
    assert current.headers["content-type"].startswith("text/csv")
    got = rows(current.text)
    assert tuple(got[0]) == sample.ENCOUNTER_COLUMNS
    assert len(got) - 1 == len(sample.encounters_by("Daniel Koh"))
    assert {r[2] for r in got[1:]} <= {sample.student(e.student).email for e in sample.encounters_by("Daniel Koh")}
    assert len(rows(client.get(f"/students/records.csv?{OPEN}&term=AY2025-2026.2").text)) == 1  # the header only
    everything = client.get(f"/students/records.csv?{OPEN}&term=all")
    assert "all-terms" in everything.headers["content-disposition"] and len(rows(everything.text)) == len(got)
    unknown = client.get(f"/students/records.csv?{OPEN}&term=no-such-term")
    assert sample.CURRENT_TERM.key in unknown.headers["content-disposition"]  # an unknown term reads as the current one


def test_a_term_bounds_both_ends() -> None:
    """A part-term, the sample's encounters all falling in the current one:
    its first and last days count, the days outside do not."""
    part = sample.Term("x.1", "Part", date(2026, 10, 15), date(2026, 10, 22))
    got = [r[0] for r in sample.encounter_rows("Daniel Koh", part)]
    assert got == sorted(e.when.date().isoformat() for e in sample.encounters_by("Daniel Koh")
                         if date(2026, 10, 15) <= e.when.date() <= date(2026, 10, 22))
    assert got[0] == "2026-10-15" and got[-1] == "2026-10-22"
    before = sample.Term("x.0", "Before", date(2026, 9, 1), date(2026, 10, 1))
    assert [r[1] for r in sample.plan_rows("Daniel Koh", before)] == ["Clara Tan"]  # P-01 began 21 Sep


def test_only_the_viewer_s_own_records(client: TestClient) -> None:
    """Hana Rahim is Priya's, shared with Daniel: never in his download."""
    daniel = client.get(f"/students/records.csv?{OPEN}&term=all").text
    assert "hana.rahim@" not in daniel
    priya = rows(client.get(f"/students/records.csv?as=Priya%20Raman&{OPEN}&term=all").text)
    assert len(priya) - 1 == len(sample.encounters_by("Priya Raman"))


def test_plans_download_and_both_templates(client: TestClient) -> None:
    plans = rows(client.get(f"/plans/records.csv?{OPEN}&term=all").text)
    assert tuple(plans[0]) == sample.PLAN_COLUMNS and len(plans) - 1 == len(sample.plans_of("Daniel Koh"))
    assert {r[2] for r in plans[1:]} == {"Formal assignment", "Follow-up"}
    for page, columns in (("students", sample.ENCOUNTER_COLUMNS), ("plans", sample.PLAN_TEMPLATE_COLUMNS)):
        template = client.get(f"/{page}/records-template.csv?{OPEN}")
        assert rows(template.text) == [list(columns)] and "template" in template.headers["content-disposition"]
    assert "Kind" not in sample.PLAN_TEMPLATE_COLUMNS  # an upload makes follow-ups, never a formal assignment
    assert "never makes one" in client.get(f"/plans/?{OPEN}").text


def test_the_forms_carry_the_viewer(client: TestClient) -> None:
    locked = client.get("/students/?as=Priya%20Raman").text.split('id="records-h"')[1]
    assert '<input type="hidden" name="as" value="Priya Raman">' in locked
    unlocked = client.get(f"/students/?as=Priya%20Raman&{OPEN}").text.split('id="dl-h"')[1].split("</form>")[0]
    assert '<input type="hidden" name="as" value="Priya Raman">' in unlocked
    assert 'records-template.csv?as=Priya%20Raman&amp;records=open&amp;understood=yes' in client.get(f"/students/?as=Priya%20Raman&{OPEN}").text


def test_a_download_without_the_unlock_goes_back(client: TestClient) -> None:
    for path in ("/students/records.csv", "/students/records-template.csv", "/plans/records.csv?as=Priya%20Raman"):
        back = client.get(path, follow_redirects=False)
        assert back.status_code == 303 and back.headers["location"].split("?")[0] in ("/students/", "/plans/"), path
    assert client.get("/plans/records.csv?as=Priya%20Raman", follow_redirects=False).headers["location"] == "/plans/?as=Priya%20Raman"


def test_a_cell_that_opens_like_a_formula_stays_text() -> None:
    from residentialapps.supportlogs.routes_records import _cell

    assert [_cell(v) for v in ("=SUM(A1)", "+1", "-2", "@x", "\tx", "\rx", "plain", "")] == [
        "'=SUM(A1)", "'+1", "'-2", "'@x", "'\tx", "'\rx", "plain", ""]


def test_only_the_frontline_downloads(client: TestClient) -> None:
    for name in ("Sam Lee", "Rachel Yeo", "Kenneth Lau", "Wei Jie Ong"):
        q = name.replace(" ", "%20")
        for path in ("/students/records.csv", "/plans/records.csv", "/plans/records-template.csv"):
            assert client.get(f"{path}?as={q}&{OPEN}").status_code == 403, (name, path)


def test_purge_hides_and_deletion_is_others(client: TestClient) -> None:
    card = client.get(f"/students/?{OPEN}").text.split('id="purge-h"')[1].split("</section>")[0]
    assert "Nothing is deleted" in card and "only senior staff with identifiable access can delete them" in card
    assert 'aria-label="Purge all your encounters">Purge all</button>' in card and "disabled" in card
    choices = re.findall(r"<option>([^<]+)</option>", card.split('id="purge-student"')[1].split("</select>")[0])
    assert choices == ["All your students", *(st.name for st in sample.record_students("Daniel Koh", "students"))]  # a purge can take one student's
    audit = client.get("/sys-admin/audit?as=Rachel%20Yeo").text.split('id="purged-h"')[1].split("</section>")[0]
    assert "Grace Ho: 6 encounters" in audit and "<button" not in audit  # only senior staff delete (author, 2026-10-30)
    assert f'<span class="count">· {sum(p.count for p in sample.PURGES)}</span>' in audit  # records, as on Overview
    assert not any(s.name in audit for s in sample.STUDENTS)


def test_the_records_pages_answer_only_on_a_local_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from residentialapps.web import pages as web_pages

    monkeypatch.setattr(web_pages, "is_local", lambda: False)
    deployed = TestClient(create_app())
    for path in ("/students/records.csv", "/plans/records-template.csv"):
        assert deployed.get(f"{path}?{OPEN}").status_code == 404, path


def test_mounted_records_stay_under_the_mount() -> None:
    host, _ = host_with(("supportlogs",))
    mounted = TestClient(host)
    for path in (f"/students/?{OPEN}", f"/plans/?show=week&{OPEN}", "/students/"):
        page = mounted.get("/supportlogs" + path)
        assert page.status_code == 200, path
        for link in re.findall(r'\b(?:href|action|formaction|src)="([^"]*)"', re.sub(r'<link rel="icon"[^>]*>', "", page.text)):
            assert link == "/" or link.startswith(("/supportlogs/", "#")), (path, link)
    back = mounted.get("/supportlogs/students/records.csv", follow_redirects=False)
    assert back.headers["location"] == "/supportlogs/students/"


# --- Records across staff (rung 8): senior identifiable access.

SAM = "as=Sam%20Lee"


def test_records_across_staff_is_senior_only_and_locked(client: TestClient) -> None:
    assert 'href="/overview/records?as=Sam%20Lee">Open records</a>' in client.get(f"/overview/?{SAM}").text
    assert "/overview/records" not in client.get("/overview/?as=Siti%20Rahman").text
    locked = client.get(f"/overview/records?{SAM}").text
    assert ">Locked</span>" in locked and "records.csv" not in locked and 'value="yes" required' in locked
    unlocked = client.get(f"/overview/records?{SAM}&{OPEN}").text
    assert "/overview/records.csv" in unlocked and "Every upload, download and deletion here is recorded" in unlocked
    for v in sample.VIEWERS:
        if sample.holds(v, sample.SENIOR):
            continue
        q = v.name.replace(" ", "%20")
        name = v.name
        for path in ("/overview/records", "/overview/records.csv", "/overview/records-template.csv"):
            assert client.get(f"{path}?as={q}&{OPEN}").status_code == 403, (name, path)
    back = client.get(f"/overview/records.csv?{SAM}", follow_redirects=False)
    assert (back.status_code, back.headers["location"]) == (303, "/overview/records?as=Sam%20Lee")


def test_downloads_by_staff_and_term(client: TestClient) -> None:
    everyone = client.get(f"/overview/records.csv?{SAM}&{OPEN}&what=encounters&term=all")
    assert everyone.headers["content-disposition"] == 'attachment; filename="support-logs-encounters-all-staff-all-terms.csv"'
    got = rows(everyone.text)
    assert tuple(got[0]) == ("Staff", *sample.ENCOUNTER_COLUMNS)
    assert len(got) - 1 == sum(len(sample.encounters_by(n)) for n in sample.FRONTLINE_COLLEAGUES)
    assert {r[0] for r in got[1:]} == {e.staff for e in sample.ENCOUNTERS}
    arjun = client.get(f"/overview/records.csv?{SAM}&{OPEN}&what=plans&staff=Arjun%20Nair&term={sample.CURRENT_TERM.key}")
    assert "plans-arjun-nair-AY2026-2027.1" in arjun.headers["content-disposition"]
    assert [r[0] for r in rows(arjun.text)[1:]] == ["Arjun Nair"]
    assert len(rows(client.get(f"/overview/records.csv?{SAM}&{OPEN}&what=encounters&term=AY2025-2026.2").text)) == 1


def test_the_staff_templates_name_the_staff_column(client: TestClient) -> None:
    for what in ("encounters", "plans"):
        template = rows(client.get(f"/overview/records-template.csv?{SAM}&{OPEN}&what={what}").text)
        assert template == [["Staff", *sample.STAFF_TEMPLATE_COLUMNS[what]]], what
    plans = sample.STAFF_TEMPLATE_COLUMNS["plans"]
    assert "Kind" in plans and "Source" in plans and "Status" not in plans  # senior staff make formal assignments


def test_purged_records_filter_by_staff_and_student(client: TestClient) -> None:
    def shown(params: str) -> list[str]:
        card = client.get(f"/overview/records?{SAM}&{OPEN}{params}").text.split('id="purged-h"')[1].split("</section>")[0]
        return re.findall(r'<span class="strong">([^<]+)</span>', card)

    assert shown("") == ["Grace Ho: 6 encounters", "Arjun Nair: 2 plans"]
    assert shown("&staff=Arjun%20Nair") == ["Arjun Nair: 2 plans"]
    # Each record is about one student; a purge holds a staff member's records about several.
    assert shown("&student=S-06") == ["Grace Ho: 2 encounters about Farid Osman, of 6"]
    assert shown("&student=S-02") == ["Grace Ho: 4 encounters about Bao Nguyen, of 6"]
    assert shown("&student=S-09") == ["Arjun Nair: 2 plans about Ivan Seet, of 2"]
    assert shown("&staff=Arjun%20Nair&student=S-06") == []
    assert shown("&staff=Nobody") == [] and shown("&student=S-99") == []  # unknown matches no one, never everyone
    card = client.get(f"/overview/records?{SAM}&{OPEN}").text.split('id="purged-h"')[1]
    assert 'id="p-term"' not in card  # no delete by term (author, 2026-10-30)
    assert '<span class="count">· 8</span>' in card
    assert 'disabled aria-label="Delete permanently: 8 purged records"' in card
    assert "Deletes the whole purges shown, of all staff." in card
    one = client.get(f"/overview/records?{SAM}&{OPEN}&student=S-06").text.split('id="purged-h"')[1]
    assert '<span class="count">· 2</span>' in one  # only Farid's records count, and only they would go
    assert 'aria-label="Delete permanently: 2 purged records"' in one
    assert "Deletes only Farid Osman's purged records; the rest of each purge stays." in one
    lost = client.get(f"/overview/records?{SAM}&{OPEN}&student=S-99").text.split('id="purged-h"')[1]
    assert '<option value="?" selected>Unknown student</option>' in lost  # Show again does not widen to everyone
    assert "Deletes nothing: the filter names no one." in lost
    nobody = client.get(f"/overview/records?{SAM}&{OPEN}&staff=Nobody").text.split('id="purged-h"')[1]
    assert '<option value="?" selected>Unknown staff</option>' in nobody  # Show again stays at none


def test_unknown_values_never_widen(client: TestClient) -> None:
    nobody = client.get(f"/overview/records.csv?{SAM}&{OPEN}&staff=Arjun%20Nar&term=all", follow_redirects=False)
    assert (nobody.status_code, nobody.headers["location"]) == (303, "/overview/records?as=Sam%20Lee&records=open&understood=yes")
    bogus = client.get(f"/overview/records.csv?{SAM}&{OPEN}&staff=Daniel%20Koh&term=bogus")
    assert f"daniel-koh-{sample.CURRENT_TERM.key}" in bogus.headers["content-disposition"]
    missing = client.get(f"/overview/records.csv?{SAM}&{OPEN}&staff=Daniel%20Koh")
    assert f"daniel-koh-{sample.CURRENT_TERM.key}" in missing.headers["content-disposition"]  # as Your records defaults


def test_a_term_picks_the_right_rows_for_a_staff_member(client: TestClient) -> None:
    got = rows(client.get(f"/overview/records.csv?{SAM}&{OPEN}&what=encounters&staff=Priya%20Raman"
                          f"&term={sample.CURRENT_TERM.key}").text)
    assert [r[0] for r in got[1:]] == ["Priya Raman"] * len(sample.encounters_by("Priya Raman"))
    assert sorted(r[1] for r in got[1:]) == sorted(e.when.date().isoformat() for e in sample.encounters_by("Priya Raman"))


def test_the_unlock_keeps_the_purge_filter(client: TestClient) -> None:
    form = client.get(f"/overview/records?{SAM}&staff=Grace%20Ho&student=S-06").text.split('id="records-h"')[1].split("</form>")[0]
    assert '<input type="hidden" name="staff" value="Grace Ho">' in form and '<input type="hidden" name="student" value="S-06">' in form


def test_downloads_filter_by_student(client: TestClient) -> None:
    """Staff's own and senior staff's downloads both take a student."""
    mine = client.get(f"/students/records.csv?{OPEN}&term=all&student=S-03")
    assert "all-terms-S-03" in mine.headers["content-disposition"]
    assert {r[2] for r in rows(mine.text)[1:]} == {"clara.tan@u.example.edu"}
    assert len(rows(mine.text)) - 1 == len(sample.encounters_by("Daniel Koh", "S-03"))
    def offered(page: str) -> list[str]:
        return re.findall(r'<option value="(S-\d+)">', client.get(f"/{page}/?{OPEN}").text.split('id="dl-student"')[1].split("</select>")[0])

    assert offered("students") == [st.id for st in sample.record_students("Daniel Koh", "students")]
    assert set(offered("plans")) == {p.student for p in sample.PLANS if p.staff == "Daniel Koh"}  # only students with plans
    assert "S-06" in offered("students") and "S-06" not in offered("plans")
    plans = rows(client.get(f"/plans/records.csv?{OPEN}&term=all&student=S-01").text)
    assert [r[1] for r in plans[1:]] == ["Aiden Chen"]
    senior = client.get(f"/overview/records.csv?{SAM}&{OPEN}&what=encounters&term=all&student=S-08")
    assert "all-staff-all-terms-S-08" in senior.headers["content-disposition"]
    assert sorted(r[0] for r in rows(senior.text)[1:]) == sorted(e.staff for e in sample.ENCOUNTERS if e.student == "S-08")
    for path in (f"/students/records.csv?{OPEN}&student=S-99", f"/overview/records.csv?{SAM}&{OPEN}&student=nope"):
        assert client.get(path, follow_redirects=False).status_code == 303, path  # an unknown student downloads nothing


def test_purge_is_outline_red(client: TestClient) -> None:
    """Purge all takes the Destructive role, outline red (author, 2026-10-30)."""
    page = client.get(f"/students/?{OPEN}").text
    assert '<button type="button" class="btn btn-danger" disabled aria-label="Purge all your encounters">Purge all</button>' in page


def test_mounted_senior_records_stay_under_the_mount() -> None:
    host, _ = host_with(("supportlogs",))
    mounted = TestClient(host)
    for path in (f"/overview/records?{SAM}", f"/overview/records?{SAM}&{OPEN}&staff=Grace%20Ho"):
        page = mounted.get("/supportlogs" + path)
        assert page.status_code == 200, path
        for link in re.findall(r'\b(?:href|action|formaction|src)="([^"]*)"', re.sub(r'<link rel="icon"[^>]*>', "", page.text)):
            assert link == "/" or link.startswith(("/supportlogs/", "#")), (path, link)
    back = mounted.get(f"/supportlogs/overview/records.csv?{SAM}", follow_redirects=False)
    assert back.headers["location"] == "/supportlogs/overview/records?as=Sam%20Lee"
