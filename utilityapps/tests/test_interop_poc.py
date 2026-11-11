"""The interop proof of concept's page (segment 23A, rung 1): the mock
exercise and the files it would send, behind the super-admin gate."""

from __future__ import annotations

import csv
import io
import json

import pytest
from fastapi.testclient import TestClient

from cordware.settings import identity_settings
from utilityapps.interop_poc import mock
from utilityapps.tests._host import host_with

PAGE = "/utilities/interop-poc/"


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("utilities",))[0])


def test_the_page_shows_the_mock_exercise_and_its_files(client: TestClient) -> None:
    page = client.get(PAGE)
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    assert "<h1>Interop proof of concept</h1>" in page.text
    for application in mock.APPLICATIONS:
        assert application.id in page.text
    assert "admin@example.edu" in page.text  # the signed-in operator is a reviewer
    assert "<code>reviewers.csv</code>" in page.text and "<code>reviewees.csv</code>" in page.text


def test_the_button_posts_to_review_robins_create_route(client: TestClient) -> None:
    text = client.get(PAGE).text
    assert 'id="poc-create"' in text and "disabled" not in text.split('id="poc-create"')[1][:40]
    assert 'data-holding-url="/reviewrobin/operator/handoffs/new"' in text
    assert 'data-create-url="/reviewrobin/operator/handoffs/sessions"' in text
    assert 'redirect: "manual"' in text  # a non-operator's 303 reads as not authorized
    # A refusal starts a new transfer next time; a 5xx or a lost answer
    # keeps it, so a retry finds a session already made (the cold read).
    assert "reply.status >= 500" in text and "if (!keep) transfer = null;" in text
    # An unreadable answer keeps it too: a 201 may have lost its body (Codex).
    assert "if (body === null)" in text and ".catch(function () { return {}; })" not in text
    assert "directory_sign_in:" in text
    # A replay cut off before its rosters saved names the draft it left.
    assert "transfer_incomplete:" in text and "Open the draft" in text
    # A first try still running keeps the transfer (Codex, cordware#202).
    assert 'body.error === "transfer_in_progress"' in text


def test_the_page_carries_the_bundle_less_its_per_click_parts(client: TestClient) -> None:
    text = client.get(PAGE).text
    start = text.index('<script type="application/json" id="poc-bundle">') + len(
        '<script type="application/json" id="poc-bundle">'
    )
    bundle = json.loads(text[start : text.index("</script>", start)])
    assert bundle["protocol"] == "cordware.csv-handoff" and bundle["protocol_version"] == 1
    assert bundle["operation"] == "reviewrobin.create_draft_session"
    assert "transfer_id" not in bundle and "code" not in bundle["session_suggestion"]
    assert set(bundle["files"]) == {"reviewers", "reviewees"}  # rosters only
    assert "SCH27-0006" in bundle["files"]["reviewees"]


def test_the_files_are_review_robins_roster_formats() -> None:
    people = mock.reviewers("Admin", "admin@example.edu")
    reviewers = list(csv.DictReader(io.StringIO(mock.reviewers_csv(people))))
    assert [r["ReviewerEmail"] for r in reviewers][-1] == "admin@example.edu"
    assert set(reviewers[0]) == {"ReviewerName", "ReviewerEmail", "ReviewerTag1"}
    reviewees = list(csv.DictReader(io.StringIO(mock.reviewees_csv())))
    assert len(reviewees) == 6
    assert reviewees[0]["RevieweeEmail"] == "SCH27-0001"  # the application ID, an opaque key
    assert reviewees[0]["ProfileLink"].startswith("https://applydesk.invalid/review/")
    assert len({r["RevieweeEmail"] for r in reviewees}) == 6


def test_someone_not_super_admin_gets_a_plain_403(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    page = client.get(PAGE)
    assert page.status_code == 403 and "<h1>Not available</h1>" in page.text


def test_nobody_signed_in_gets_a_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    assert client.get(PAGE).status_code == 401


def test_the_index_does_not_list_it(client: TestClient) -> None:
    assert "interop" not in client.get("/utilities/").text.lower()
