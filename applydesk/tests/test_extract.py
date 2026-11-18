"""Extract data's downloads (segment AD1J, rung 3): each card's CSV and the
ZIPs, built from the sample and shaped by the cards' chips, as the routes
serve them."""

from __future__ import annotations

import csv
import io
import re
import zipfile

import pytest
from fastapi.testclient import TestClient

from applydesk import extract, sample_data
from applydesk.tests._host import host_with

EX = "wa9juxbc2t"  # the RA recruitment: gates 1 and 2 in, gate 3 not sent
BASE = f"/applydesk/operator/exercises/{EX}/extract"


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0])


def _rows(body: bytes) -> list[list[str]]:
    assert body.startswith(b"\xef\xbb\xbf")  # UTF-8 with a BOM (Review Robin's envelope)
    return list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))


def test_applications_csv_a_row_per_application(client: TestClient) -> None:
    r = client.get(f"{BASE}/applications.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert 'filename="applications.csv"' in r.headers["content-disposition"]
    rows = _rows(r.content)
    e = sample_data.exercise(EX)
    assert e is not None
    assert tuple(rows[0]) == extract.of(e).application_columns
    first = dict(zip(rows[0], rows[1], strict=True))
    assert first["applicant"] == "Aisha Bello" and first["Year of study"] == "Year 4"
    assert len(rows) - 1 == 100  # last applications: each applicant's latest submitted
    drafts = _rows(client.get(f"{BASE}/applications.csv?rows=all&drafts=1").content)
    # Drafts, never a withdrawn application (cold read).
    assert {r[4] for r in drafts[1:]} == {"Submitted", "Draft"} and len(drafts) - 1 == 103


def test_a_gate_csv_by_pair_or_by_application(client: TestClient) -> None:
    pairs = _rows(client.get(f"{BASE}/gate_1.csv").content)
    assert pairs[0] == ["dossier_id", "evaluator", "evaluator_email", "Score", "Comment"]
    assert len(pairs) - 1 == 2980
    assert all(0 <= int(r[3]) <= 5 for r in pairs[1:])  # within the field's bounds
    # The same pair answers the same every time (seeded sample answers).
    assert pairs == _rows(client.get(f"{BASE}/gate_1.csv").content)
    named = _rows(client.get(f"{BASE}/gate_2.csv?applicants=names").content)
    assert named[0][:3] == ["dossier_id", "applicant", "email"]
    assert {r[5] for r in named[1:]} <= {"No concerns", "Minor concerns", "Major concerns"}
    by_app = _rows(client.get(f"{BASE}/gate_1.csv?shape=application").content)
    assert by_app[0] == ["dossier_id", "Mean score", "Comments"]
    assert by_app[1][:2] == ["p3bd7kq2wx", "3.81"]  # Dossiers' collated result
    r = client.get(f"{BASE}/gate_1.csv")
    assert 'filename="gate_1_peer_review.csv"' in r.headers["content-disposition"]


def test_a_gate_not_sent_or_missing_has_no_file(client: TestClient) -> None:
    assert client.get(f"{BASE}/gate_3.csv").status_code == 404
    assert client.get(f"{BASE}/gate_9.csv").status_code == 404
    assert client.get(f"{BASE}/nothing.csv").status_code == 404


def test_outcomes_csv(client: TestClient) -> None:
    rows = _rows(client.get(f"{BASE}/outcomes.csv").content)
    head = dict(zip(rows[0], rows[1], strict=True))
    assert head["Shortlisting"] == "Re-appointment" and head["Shortlisting released"] == "6 Nov"
    assert head["Selection"] == "Pending" and head["Selection released"] == ""
    ids = _rows(client.get(f"{BASE}/outcomes.csv?applicants=ids").content)
    assert "applicant" not in ids[0]


def test_the_zips_carry_a_manifest_and_what_the_chips_say(client: TestClient) -> None:
    r = client.get(f"{BASE}/all.zip")
    assert r.headers["content-type"] == "application/zip"
    assert re.search(
        r'filename="ra_2027_extract_\d{4}-\d\d-\d\d\.zip"', r.headers["content-disposition"]
    )
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert z.namelist() == [
        "manifest.csv",
        "applications.csv",
        "gate_1_peer_review.csv",
        "gate_2_office_checks.csv",
        "outcomes.csv",
    ]
    manifest = _rows(z.read("manifest.csv"))
    assert ["gate_3_staff_interview.csv", "", "Not sent"] in manifest
    assert ["gate_1_peer_review.csv", "2980", ""] in manifest
    # Applicants as Dossier IDs: no file names them but the applications'.
    z = zipfile.ZipFile(
        io.BytesIO(client.get(f"{BASE}/all.zip?applicants=ids&carries=gates,outcomes").content)
    )
    assert z.namelist() == [
        "manifest.csv",
        "gate_1_peer_review.csv",
        "gate_2_office_checks.csv",
        "outcomes.csv",
    ]
    assert "applicant" not in _rows(z.read("outcomes.csv"))[0]
    # The other cards' settings ride along (Codex): drafts, the shape, Outcomes' rows.
    z = zipfile.ZipFile(
        io.BytesIO(
            client.get(f"{BASE}/all.zip?rows=all&drafts=1&shape=application&orows=last").content
        )
    )
    assert len(_rows(z.read("applications.csv"))) - 1 == 103
    assert _rows(z.read("gate_1_peer_review.csv"))[0][-2:] == ["Mean score", "Comments"]
    assert len(_rows(z.read("outcomes.csv"))) - 1 == 100
    gates = zipfile.ZipFile(io.BytesIO(client.get(f"{BASE}/gates.zip").content))
    assert gates.namelist()[0] == "manifest.csv" and len(gates.namelist()) == 3


def test_the_page_links_each_download(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{EX}/extract").text
    for f in ("all.zip", "applications.csv", "gate_1.csv", "gate_2.csv", "gates.zip"):
        assert f'data-xd-dl="{f}" href="{BASE}/{f}"' in text
    assert 'data-xd-dl="gate_3.csv"' not in text  # not sent
    blank = client.get("/applydesk/operator/exercises/n5wg8tjr3e/extract").text
    # Nothing submitted: only the setup can be extracted (Semantics).
    assert re.findall(r'data-xd-dl="([^"]+)"', blank) == ["setup.zip"]


def test_a_select_people_answer_is_exported(client: TestClient) -> None:
    """Codex: a Select people question's choices are the nominees."""
    tea = "k7mfr3pq8z"
    rows = _rows(
        client.get(f"/applydesk/operator/exercises/{tea}/extract/applications.csv").content
    )
    col = rows[0].index("Preferred reviewer")
    margaret = next(r for r in rows[1:] if r[2] == "Margaret Liu")
    app = next(a for a in sample_data.applications_of(tea) if a.applicant == "Margaret Liu")
    assert margaret[col] == "; ".join(sample_data.nominees(tea, app, "Preferred reviewer")) != ""


def test_the_alias_key_joins_dossier_to_applicant(client: TestClient) -> None:
    r = client.get(f"{BASE}/alias_key.csv")
    assert 'filename="alias_key.csv"' in r.headers["content-disposition"]
    rows = _rows(r.content)
    assert rows[0] == ["dossier_id", "application_id", "applicant", "email"]
    assert rows[1] == ["p3bd7kq2wx", "m3qx8vkt2n", "Aisha Bello", "aisha.bello@example.edu"]
    assert len(rows) - 1 == 104  # every application, drafts included
    # Never inside Extract all data, whatever it carries (kept apart).
    z = zipfile.ZipFile(
        io.BytesIO(client.get(f"{BASE}/all.zip?carries=applications,gates,outcomes,setup").content)
    )
    assert "alias_key.csv" not in z.namelist()


def test_extract_setup_one_csv_per_setup_page(client: TestClient) -> None:
    r = client.get(f"{BASE}/setup.zip")
    assert re.search(
        r'filename="ra_2027_setup_\d{4}-\d\d-\d\d\.zip"', r.headers["content-disposition"]
    )
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert z.namelist() == ["manifest.csv", "form.csv", "process.csv", "panels.csv", "emails.csv"]
    form = _rows(z.read("form.csv"))
    assert form[0][:4] == ["order", "kind", "type", "label"]
    assert ["1", "section", "", "About you"] == form[1][:4]
    process = _rows(z.read("process.csv"))
    gate1 = next(r for r in process if r[3] == "gate" and r[4] == "1")
    assert gate1[5] == "Peer review" and gate1[7] == "Automatic"
    assert gate1[11] == "Status is Submitted → Entered, else Not entered"
    shortlisting = next(r for r in process if r[5] == "Shortlisting")
    assert shortlisting[9] == "Re-appointment; Interview; Not shortlisted"
    assert ["Current RAs", "Aisha Bello", "aisha.bello@example.edu", "Cendana House"] in _rows(
        z.read("panels.csv")
    )
    assert _rows(z.read("emails.csv"))[1][-1] == "yes"
    # The chips choose the pages; all.zip carries them under setup/.
    z = zipfile.ZipFile(io.BytesIO(client.get(f"{BASE}/setup.zip?carries=form,emails").content))
    assert z.namelist() == ["manifest.csv", "form.csv", "emails.csv"]
    z = zipfile.ZipFile(io.BytesIO(client.get(f"{BASE}/all.zip?carries=setup").content))
    assert z.namelist() == [
        "manifest.csv",
        "setup/form.csv",
        "setup/process.csv",
        "setup/panels.csv",
        "setup/emails.csv",
    ]
    # A draft's setup extracts too.
    draft = client.get("/applydesk/operator/exercises/n5wg8tjr3e/extract/setup.zip")
    assert draft.status_code == 200


def test_every_form_question_has_an_answer(client: TestClient) -> None:
    """Cold read: text, number and photo questions are filled (seeded
    sample answers), not left blank; a photo is its file name."""
    rows = _rows(client.get(f"{BASE}/applications.csv").content)
    first = dict(zip(rows[0], rows[1], strict=True))
    assert first["Photo"] == "p3bd7kq2wx.jpg"
    assert first["Preferred name"] == "Aisha"
    assert re.fullmatch(r"A\d{7}[A-Z]", first["Matriculation number"])
    numbers = rows[0].index("Year of study")
    assert all(r[numbers] for r in rows[1:])
    tea = _rows(
        client.get("/applydesk/operator/exercises/k7mfr3pq8z/extract/applications.csv").content
    )
    months = tea[0].index("Months the project will run")
    assert all(r[months].isdigit() for r in tea[1:])
    gpa = tea[0].index("Cumulative GPA")
    assert all(r[gpa] != "" for r in tea[1:])


def test_zip_all_names_no_one_by_default_on_a_sensitive_exercise(client: TestClient) -> None:
    """Semantics: a confidential gate's file defaults to Dossier IDs; the RA
    exercise's Office checks is confidential, so Zip all starts on IDs."""
    z = zipfile.ZipFile(io.BytesIO(client.get(f"{BASE}/all.zip").content))
    assert "applicant" not in _rows(z.read("gate_2_office_checks.csv"))[0]
    assert "applicant" not in _rows(z.read("outcomes.csv"))[0]
    named = zipfile.ZipFile(io.BytesIO(client.get(f"{BASE}/all.zip?applicants=names").content))
    assert "applicant" in _rows(named.read("gate_2_office_checks.csv"))[0]


def test_a_cell_never_runs_as_a_formula() -> None:
    assert extract.safe("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert extract.safe("@SUM(A1)") == "'@SUM(A1)" and extract.safe("+44 20") == "'+44 20"
    assert extract.safe("-1") == "-1" and extract.safe("3.81") == "3.81"
    assert extract.safe("- a list") == "'- a list"
    body = extract.csv_bytes((("a",), [["=1+1"]])).decode("utf-8-sig")
    assert body.splitlines()[1] == "'=1+1"


def test_process_csv_keeps_each_gate_s_fields_and_results(client: TestClient) -> None:
    """Codex: enough to rebuild a gate, its response fields and how each
    result is derived, not only the results' names."""
    z = zipfile.ZipFile(io.BytesIO(client.get(f"{BASE}/setup.zip").content))
    rows = _rows(z.read("process.csv"))
    assert rows[0][-1] == "detail"
    # Every row as wide as the header (Codex): settings under ``detail``.
    for name in z.namelist():
        table = _rows(z.read(name))
        assert {len(r) for r in table} == {len(table[0])}, name
    detail = {
        (r["kind"], r["label"]): r["detail"]
        for r in csv.DictReader(io.StringIO(z.read("process.csv").decode("utf-8-sig")))
    }
    assert "derive=mean" in detail[("result", "Mean score")]
    score = next(r for r in rows if r[3] == "field" and r[4] == "1" and r[5] == "Score")
    assert "type=integer; min=0; max=5" in score[-1] and "required=yes" in score[-1]
    mean = next(r for r in rows if r[3] == "result" and r[5] == "Mean score")
    assert "derive=mean; source=score" in mean[-1] and "ignore_zero=yes" in mean[-1]
    interview = next(r for r in rows if r[3] == "result" and r[5] == "Interview score")
    assert "at_least=2" in interview[-1]
    selection = next(r for r in rows if r[3] == "outcome" and r[5] == "Selection")
    assert selection[-1] == "weights=g3.r1 1"


def test_zip_all_takes_extract_setup_s_pages(client: TestClient) -> None:
    """Codex: Setup in Zip all carries the pages Extract setup's chips keep."""
    body = client.get(f"{BASE}/all.zip?carries=setup&sparts=form,process").content
    assert zipfile.ZipFile(io.BytesIO(body)).namelist() == [
        "manifest.csv",
        "setup/form.csv",
        "setup/process.csv",
    ]
