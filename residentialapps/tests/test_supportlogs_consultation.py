"""Support Logs' Consultation check on sample data, segment 1D item 1 rung
6: a purpose and a list in, each student's state, its named reasons and
whom to consult out, never a score or a suitability decision (functional
spec §10.7–10.8, §11.2)."""

from __future__ import annotations

import re
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.main import create_app
from residentialapps.tests._host import host_with

MARCUS = "Marcus Tan"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def check(client: TestClient, emails: str, purpose: str = "Overseas field trip", who: str = MARCUS, **kw):
    return client.get("/consultation/check?" + urlencode({"as": who, "purpose": purpose, "emails": emails}), **kw)


def rows(page: str) -> list[tuple[str, str]]:
    """(email, state) per result row, in order."""
    body = page.split("<tbody>")[1].split("</tbody>")[0]
    return [(re.search(r'<span class="subtle">([^<]+@[^<]+)</span>', r).group(1), re.search(r'class="chip [a-z-]+">([^<]+)<', r).group(1))
            for r in re.findall(r"<tr>(.*?)</tr>", body, re.S)]


def test_each_state_comes_from_named_reasons() -> None:
    clara = sample.consultation("clara.tan@u.example.edu")
    assert (clara.state, clara.reasons, clara.consult) == (
        sample.REQUIRED, ("Active safety-plan support", "Active formal check-in assignment"), ("Daniel Koh",))
    hana = sample.consultation("Hana.Rahim@u.example.edu ")  # case and spaces do not matter
    assert (hana.state, hana.reasons, hana.consult) == (
        sample.SUGGESTED, ("Active informal follow-up", "Several staff recently involved"), ("Priya Raman", "Arjun Nair"))
    assert sample.consultation("jia.wen.lee@u.example.edu").reasons == ("Unresolved safety escalation",)
    farid = sample.consultation("farid.osman@u.example.edu")  # a student with past support, none current
    assert (farid.state, farid.reasons, farid.consult) == (sample.NONE_INDICATED, (), ())
    unknown = sample.consultation("someone.else@u.example.edu")
    assert (unknown.student, unknown.state) == (None, sample.NONE_INDICATED)


def test_every_reason_brings_a_configured_state() -> None:
    assert {state for _, state in sample.CONSULTATION_REASONS} <= set(sample.CONSULTATION_STATES)
    assert sample.NONE_INDICATED not in {state for _, state in sample.CONSULTATION_REASONS}


def test_the_result_lists_the_strongest_first_and_says_what_none_means(client: TestClient) -> None:
    page = check(client, "\n".join(sample.SAMPLE_EMAILS)).text
    states = [state for _, state in rows(page)]
    assert states == sorted(states, key=sample.CONSULTATION_STATES.index)
    assert len(states) == len(sample.SAMPLE_EMAILS)
    assert sample.NONE_MEANS in page and "This check is recorded" in page
    assert "No Support Logs record" in page and "score" not in page.split("<tbody>")[1].split("</tbody>")[0]
    assert "Overseas field trip · 6 students" in page


def test_the_result_shows_no_note_and_no_encounter(client: TestClient) -> None:
    page = check(client, "\n".join(sample.SAMPLE_EMAILS)).text
    for e in sample.ENCOUNTERS:
        if e.note:
            assert e.note not in page, e.id
    assert "/students/" not in page and "/plans/" not in page and "/flags/" not in page


def test_a_pasted_list_is_split_and_deduplicated(client: TestClient) -> None:
    assert sample.emails_in("a@x.edu, b@x.edu;A@x.edu\n  c@x.edu not-an-email") == ["a@x.edu", "b@x.edu", "c@x.edu"]
    assert [email for email, _ in rows(check(client, "farid.osman@u.example.edu, FARID.OSMAN@u.example.edu").text)] == [
        "farid.osman@u.example.edu"]


def test_a_check_needs_a_purpose_and_a_list(client: TestClient) -> None:
    for purpose, emails in (("", "farid.osman@u.example.edu"), ("Trip", ""), ("  ", "no emails here")):
        back = check(client, emails, purpose, follow_redirects=False)
        assert (back.status_code, back.headers["location"]) == (303, "/consultation/?as=Marcus%20Tan"), (purpose, emails)


def test_the_form_fills_with_the_sample_list(client: TestClient) -> None:
    form = client.get("/consultation/?as=Marcus%20Tan&sample=1").text
    assert all(email in form for email in sample.SAMPLE_EMAILS)
    assert 'href="/consultation/?as=Marcus%20Tan&amp;sample=1"' in client.get("/consultation/?as=Marcus%20Tan").text
    past = form.split('id="runs-h"')[1]
    assert all(r.purpose in past for r in sample.CHECK_RUNS)


def test_only_the_consultation_check_grant_reaches_it(client: TestClient) -> None:
    for name in ("Daniel Koh", "Sam Lee", "Siti Rahman", "Rachel Yeo", "Hui Min Goh"):
        q = name.replace(" ", "%20")
        assert client.get(f"/consultation/?as={q}").status_code == 403, name
        assert check(client, "farid.osman@u.example.edu", who=name).status_code == 403, name
    assert client.get("/consultation/?as=Nadia%20Hassan").status_code == 200


def test_the_consultation_pages_answer_only_on_a_local_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from residentialapps.web import pages as web_pages

    monkeypatch.setattr(web_pages, "is_local", lambda: False)
    deployed = TestClient(create_app())
    assert deployed.get("/consultation/?as=Marcus%20Tan").status_code == 404
    assert check(deployed, "farid.osman@u.example.edu").status_code == 404


def test_mounted_consultation_pages_stay_under_the_mount() -> None:
    host, _ = host_with(("supportlogs",))
    mounted = TestClient(host)
    q = urlencode({"as": MARCUS, "purpose": "Trip", "emails": "\n".join(sample.SAMPLE_EMAILS)})
    for path in ("/consultation/?as=Marcus%20Tan", "/consultation/?as=Marcus%20Tan&sample=1", "/consultation/check?" + q):
        page = mounted.get("/supportlogs" + path)
        assert page.status_code == 200, path
        for link in re.findall(r'\b(?:href|action|formaction|src)="([^"]*)"', re.sub(r'<link rel="icon"[^>]*>', "", page.text)):
            assert link == "/" or link.startswith(("/supportlogs/", "#")), (path, link)
    back = mounted.get("/supportlogs/consultation/check?as=Marcus%20Tan&purpose=&emails=", follow_redirects=False)
    assert back.headers["location"] == "/supportlogs/consultation/?as=Marcus%20Tan"
