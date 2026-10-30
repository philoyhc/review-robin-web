"""Support Logs' Your records on sample data, segment 1D item 1 rung 7
(author, 2026-10-30): a section at the end of Students and My plans,
locked until confirmed, to download the viewer's own encounters or plans
as CSV by term or all, upload a CSV, or purge them all; a purge hides and
keeps, and only a sys admin deletes."""

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


def test_purge_hides_and_sys_admin_alone_deletes(client: TestClient) -> None:
    card = client.get(f"/students/?{OPEN}").text.split('id="purge-h"')[1].split("</section>")[0]
    assert "Nothing is deleted" in card and "alone can delete" in card
    assert 'aria-label="Purge all your encounters">Purge all</button>' in card and "disabled" in card
    audit = client.get("/sys-admin/audit?as=Rachel%20Yeo").text.split('id="purged-h"')[1].split("</section>")[0]
    assert "Grace Ho: 6 encounters" in audit and 'aria-label="Delete permanently: Grace Ho\'s purged encounters"' in audit
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
    for name in ("Siti Rahman", "Kenneth Lau", "Daniel Koh", "Rachel Yeo", "Hui Min Goh"):
        q = name.replace(" ", "%20")
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
    for what, columns in (("encounters", sample.ENCOUNTER_COLUMNS), ("plans", sample.PLAN_COLUMNS)):
        template = rows(client.get(f"/overview/records-template.csv?{SAM}&{OPEN}&what={what}").text)
        assert template == [["Staff", *columns]], what


def test_purged_records_filter_by_staff_and_term(client: TestClient) -> None:
    def shown(params: str) -> list[str]:
        card = client.get(f"/overview/records?{SAM}&{OPEN}{params}").text.split('id="purged-h"')[1].split("</section>")[0]
        return re.findall(r'<span class="strong">([^<]+)</span>', card)

    assert shown("") == ["Grace Ho: 6 encounters", "Arjun Nair: 2 plans"]
    assert shown("&staff=Arjun%20Nair") == ["Arjun Nair: 2 plans"]
    assert shown(f"&term={sample.CURRENT_TERM.key}") == ["Grace Ho: 6 encounters"]
    assert shown("&staff=Grace%20Ho&term=AY2025-2026.3") == []
    card = client.get(f"/overview/records?{SAM}&{OPEN}&staff=Grace%20Ho").text.split('id="purged-h"')[1]
    assert 'class="btn btn-danger gap-above-sm" disabled aria-label="Delete permanently the 1 purged records shown"' in card
    assert "for Grace Ho and all terms" in card


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
