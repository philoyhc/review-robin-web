"""The interop proof of concept's page (segment 23A, rung 1): the mock
exercise and the files it would send, behind the super-admin gate."""

from __future__ import annotations

import csv
import io

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


def test_the_button_is_inert_until_rung_3(client: TestClient) -> None:
    text = client.get(PAGE).text
    assert '<button class="btn primary" type="button" disabled aria-disabled="true">' in text


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
