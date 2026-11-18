"""Extract data's downloads (segment AD1J, rung 3): each card's CSV and the
ZIPs, built from the sample and shaped by the cards' chips, as the routes
serve them."""

from __future__ import annotations

import csv
import io
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
    assert len(drafts) - 1 == 104 and {"Draft"} <= {r[4] for r in drafts[1:]}


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
    assert 'filename="ra_2027_extract.zip"' in r.headers["content-disposition"]
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
    gates = zipfile.ZipFile(io.BytesIO(client.get(f"{BASE}/gates.zip").content))
    assert gates.namelist()[0] == "manifest.csv" and len(gates.namelist()) == 3


def test_the_page_links_each_download(client: TestClient) -> None:
    text = client.get(f"/applydesk/operator/exercises/{EX}/extract").text
    for f in ("all.zip", "applications.csv", "gate_1.csv", "gate_2.csv", "gates.zip"):
        assert f'data-xd-dl="{f}" href="{BASE}/{f}"' in text
    assert 'data-xd-dl="gate_3.csv"' not in text  # not sent
    blank = client.get("/applydesk/operator/exercises/n5wg8tjr3e/extract").text
    assert "data-xd-dl=" not in blank  # nothing to extract: no link
