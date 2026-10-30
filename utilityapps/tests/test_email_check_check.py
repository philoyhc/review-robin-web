"""The check: classification, duplicate groups, failures, and the result
page with its download (spec §§5–7 and acceptance tests 1–10; segment
U1, rung 5)."""

from __future__ import annotations

import base64
import csv
import io
import logging
import re

import pytest
from fastapi.testclient import TestClient

from cordware.graph import DirectoryUser, FakeDirectory, GraphError
from utilityapps.email_check import check, csvio, routes
from utilityapps.tests._host import host_with

JANE = DirectoryUser("id-jane", "Jane Tan", "jane.tan@example.edu", "e0123456@example.edu")
LAB = DirectoryUser("id-lab", "Lab", None, "lab01@example.edu")
OTHER = DirectoryUser("id-other", "Other", "other@example.edu", "e0999999@example.edu")


class Recording:
    """A directory answering from a table, recording each lookup."""

    def __init__(self, table: dict[str, list[DirectoryUser] | Exception]) -> None:
        self.table = table
        self.asked: list[str] = []

    def find_users(self, address: str) -> list[DirectoryUser]:
        self.asked.append(address)
        answer = self.table.get(address, [])
        if isinstance(answer, Exception):
            raise answer
        return answer


def _rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


@pytest.mark.parametrize(
    ("key", "users", "status", "match"),
    [
        ("jane.tan@example.edu", [JANE], "OK", "PRIMARY_MAIL"),
        ("e0123456@example.edu", [JANE], "USE_PRIMARY", "UPN"),
        ("lab01@example.edu", [LAB], "FOUND_NO_PRIMARY", "UPN"),
        ("nobody@example.edu", [], "NOT_FOUND", "NONE"),
        ("office@example.edu", [JANE, OTHER], "AMBIGUOUS", "MULTIPLE"),
        ("jane.tan@example.edu", [JANE, JANE], "OK", "PRIMARY_MAIL"),
        ("something@example.edu", [JANE], "AMBIGUOUS", "MULTIPLE"),
    ],
)
def test_classify(key: str, users: list[DirectoryUser], status: str, match: str) -> None:
    outcome = check.classify(key, users)
    assert (outcome.status, outcome.match_type) == (status, match)


def test_a_run_keeps_every_row_and_column_in_order() -> None:
    data = (
        b"Name,email,Role\r\n"
        b"Jane,Jane.Tan@example.edu,Reviewer\r\n"
        b"Jane again,e0123456@example.edu,Reviewer\r\n"
        b"Blank,,Reviewer\r\n"
        b"Jane,jane.tan@example.edu ,Observer\r\n"
        b"Nobody,nobody@example.edu,Reviewer\r\n"
    )
    upload = csvio.parse(data)
    directory = Recording({"jane.tan@example.edu": [JANE], "e0123456@example.edu": [JANE]})
    result = check.run(upload, 1, directory)
    rows = _rows(result.csv)
    assert [(r["Name"], r["email"], r["Role"]) for r in rows] == [
        ("Jane", "Jane.Tan@example.edu", "Reviewer"),
        ("Jane again", "e0123456@example.edu", "Reviewer"),
        ("Blank", "", "Reviewer"),
        ("Jane", "jane.tan@example.edu ", "Observer"),
        ("Nobody", "nobody@example.edu", "Reviewer"),
    ]
    assert [r["status"] for r in rows] == ["OK", "USE_PRIMARY", "INVALID_INPUT", "OK", "NOT_FOUND"]
    assert rows[1]["recommended_email"] == "jane.tan@example.edu"
    assert rows[1]["user_principal_name"] == "e0123456@example.edu"
    assert rows[0]["entra_object_id"] == "id-jane"
    assert {r["lookup_coverage"] for r in rows} == {"BASIC_ONLY"}
    assert rows[4]["notes"] == "No user-directory match" and rows[4]["recommended_email"] == ""
    # Each distinct key once; the blank row never asked.
    assert sorted(directory.asked) == ["e0123456@example.edu", "jane.tan@example.edu", "nobody@example.edu"]
    assert result.lookups == 3 and result.rows == 5
    assert result.counts == {
        "OK": 2, "USE_PRIMARY": 1, "FOUND_NO_PRIMARY": 0, "NOT_FOUND": 1,
        "AMBIGUOUS": 0, "INVALID_INPUT": 1, "ERROR": 0,
    }


def test_two_addresses_for_one_account_form_a_group_and_repeats_do_not() -> None:
    data = (
        b"email\r\n"
        b"jane.tan@example.edu\r\n"      # Jane by mail
        b"other@example.edu\r\n"         # Other, twice by the same address
        b"OTHER@example.edu\r\n"
        b"e0123456@example.edu\r\n"      # Jane by UPN
    )
    directory = Recording(
        {"jane.tan@example.edu": [JANE], "e0123456@example.edu": [JANE], "other@example.edu": [OTHER]}
    )
    result = check.run(csvio.parse(data), 0, directory)
    groups = [r["duplicate_account_group"] for r in _rows(result.csv)]
    assert groups == ["1", "", "", "1"]
    assert result.groups == 1


@pytest.mark.parametrize("kind", ["throttled", "server", "network", "bad_response"])
def test_a_failed_lookup_is_error_never_not_found(kind: str) -> None:
    directory = Recording({"a@example.edu": GraphError(kind), "b@example.edu": [JANE]})
    result = check.run(csvio.parse(b"email\r\na@example.edu\r\njane@x.edu\r\n"), 0, directory)
    rows = _rows(result.csv)
    assert rows[0]["status"] == "ERROR" and kind in rows[0]["notes"]
    assert rows[1]["status"] == "NOT_FOUND"
    assert result.error_kinds == (kind,)


@pytest.mark.parametrize("kind", ["unauthorized", "forbidden"])
def test_a_refused_sign_in_stops_the_lookups_not_yet_started(
    kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each would fail the same way: one request, not one per address
    (diff-reviewer, `#3411`)."""
    monkeypatch.setattr(check, "WORKERS", 1)
    directory = Recording({"a@example.edu": GraphError(kind)})
    data = b"email\r\na@example.edu\r\nb@example.edu\r\nc@example.edu\r\n"
    result = check.run(csvio.parse(data), 0, directory)
    assert directory.asked == ["a@example.edu"]
    rows = _rows(result.csv)
    assert [r["status"] for r in rows] == ["ERROR"] * 3
    assert all("sign out and in again" in r["notes"] for r in rows)
    assert result.error_kinds == (kind,)


def test_lookups_past_the_budget_are_error_and_the_rest_download() -> None:
    import threading

    release = threading.Event()

    class Stuck:
        def find_users(self, address: str) -> list[DirectoryUser]:
            if address == "slow@example.edu":
                release.wait(5)
            return [JANE] if address == "jane.tan@example.edu" else []

    try:
        outcomes = check.look_up_all(Stuck(), ["jane.tan@example.edu", "slow@example.edu"], budget=0.2)
    finally:
        release.set()
    assert outcomes["jane.tan@example.edu"].status == "OK"
    assert outcomes["slow@example.edu"].status == "ERROR"
    assert outcomes["slow@example.edu"].error_kind == "timeout"


def test_the_result_page_says_to_sign_in_again_after_a_refusal(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(routes, "directory_for", lambda request: Recording({"a@x.edu": GraphError("unauthorized")}))
    text = _post_check(client, b"email\r\na@x.edu\r\n").text
    assert "sign out and in again" in text


def test_lookups_run_at_most_four_at_once() -> None:
    import threading
    import time

    lock, live, peak = threading.Lock(), [0], [0]

    class Slow:
        def find_users(self, address: str) -> list[DirectoryUser]:
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.01)
            with lock:
                live[0] -= 1
            return []

    keys = [f"u{i}@example.edu" for i in range(20)]
    check.look_up_all(Slow(), keys)
    assert 1 < peak[0] <= check.WORKERS


# --- the pages -------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("utilities",))[0])


def _post_check(client: TestClient, data: bytes, column: str = "") -> object:
    fields = {"content": base64.b64encode(data).decode(), "filename": "list.csv"}
    if column:
        fields["column"] = column
    return client.post("/utilities/email-check/check", data=fields)


def _download(text: str) -> tuple[str, str]:
    href, name = re.search(r'href="data:text/csv;charset=utf-8;base64,([^"]+)" download="([^"]+)"', text).groups()
    return base64.b64decode(href).decode("utf-8-sig"), name


def test_the_check_against_the_fake_directory_renders_counts_and_the_download(client: TestClient) -> None:
    data = (
        b"Who,Work email\r\n"
        b"Jane,jane.tan@example.edu\r\n"
        b"Jane,e0123456@example.edu\r\n"
        b"Lab,lab01@example.edu\r\n"
        b"Shared,office@example.edu\r\n"
        b"Busy,throttled@example.edu\r\n"
        b"Bad,not an address\r\n"
        b"Who,=HYPERLINK(\"x\")\r\n"
    )
    page = _post_check(client, data, column="1")
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    text = page.text
    assert "Checked 7 rows" in text
    assert "<strong>1</strong> account appears under more than one address" in text
    assert 'role="alert">1 row' in text  # the throttled lookup
    body, name = _download(text)
    assert re.fullmatch(r"email-check-results-\d{8}\.csv", name)
    rows = _rows(body)
    assert [r["status"] for r in rows] == [
        "OK", "USE_PRIMARY", "FOUND_NO_PRIMARY", "AMBIGUOUS", "ERROR", "INVALID_INPUT", "INVALID_INPUT",
    ]
    assert rows[6]["Work email"] == "'=HYPERLINK(\"x\")"
    assert list(rows[0])[:2] == ["Who", "Work email"]


def test_the_check_without_a_column_returns_to_the_preview(client: TestClient) -> None:
    page = _post_check(client, b"Name,Work\r\nA,a@x.edu\r\n")
    assert page.status_code == 200 and "Choose a column" in page.text


def test_without_a_token_nothing_is_checked(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_token(request: object) -> FakeDirectory:
        raise GraphError("no_token")

    monkeypatch.setattr(routes, "directory_for", no_token)
    page = _post_check(client, b"email\r\njane.tan@example.edu\r\n")
    assert page.status_code == 503
    assert "The directory can" in page.text and "nothing was checked" in page.text
    assert "data:text/csv" not in page.text
    assert re.search(r'formaction="/utilities/email-check/check" disabled>', page.text)


def test_the_log_carries_counts_never_the_file(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="utilityapps")
    _post_check(client, b"email,name\r\njane.tan@example.edu,Jane Tan\r\noutage@example.edu,X\r\n")
    (record,) = [r for r in caplog.records if getattr(r, "event", "") == "email_check.completed"]
    assert record.rows == 2 and record.lookups == 2 and record.error_kinds == ["server"]
    assert record.counts["OK"] == 1 and record.counts["ERROR"] == 1
    everything = " ".join(r.getMessage() + repr(r.__dict__) for r in caplog.records)
    for secret in ("jane.tan", "Jane Tan", "outage@", "11111111-1111"):
        assert secret not in everything


@pytest.mark.parametrize("path", ["/utilities/email-check/preview", "/utilities/email-check/check"])
def test_a_step_reached_by_address_starts_again(client: TestClient, path: str) -> None:
    page = client.get(path, follow_redirects=False)
    assert page.status_code == 303 and page.headers["location"] == "/utilities/email-check/"
