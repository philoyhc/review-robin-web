"""The upload and the wired preview (segment U1, rung 3): the file goes
in, its counts come back, and it is carried in the page, never kept."""

from __future__ import annotations

import base64
import re

import pytest
from fastapi.testclient import TestClient

from utilityapps.email_check import csvio
from utilityapps.tests._host import host_with

URL = "/utilities/email-check/preview"


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("utilities",))[0])


def _upload(client: TestClient, data: bytes, name: str = "list.csv"):
    return client.post(URL, files={"file": (name, data, "text/csv")})


def _carried(text: str) -> bytes:
    return base64.b64decode(re.search(r'name="content" value="([^"]*)"', text).group(1))


def test_a_file_with_an_email_column_previews_its_counts(client: TestClient) -> None:
    data = b"Name,Email\r\nA,a@x.edu\r\nB,\r\nC,A@x.edu\r\n"
    page = _upload(client, data)
    assert page.status_code == 200
    text = page.text
    assert "Placeholder" not in text
    assert "Preview: <code>list.csv</code>" in text
    assert '<option value="1" selected>Email</option>' in text
    for label, n in [("Rows", 3), ("Addresses to check", 2), ("kept, not checked", 1), ("checked once", 1)]:
        assert re.search(label + r"[^<]*</th><td class=\"n\">" + str(n) + "<", text), label
    assert _carried(text) == data


def test_without_an_email_column_the_operator_chooses(client: TestClient) -> None:
    data = b"Name,Work address\r\nA,a@x.edu\r\n"
    first = _upload(client, data).text
    assert '<option value="" selected>Choose a column' in first
    assert "Addresses to check" not in first
    chosen = client.post(
        URL, files={"content": (None, base64.b64encode(data)), "filename": (None, "list.csv"), "column": (None, "1")}
    )
    assert chosen.status_code == 200
    assert '<option value="1" selected>Work address</option>' in chosen.text
    assert re.search(r"Addresses to check</th><td class=\"n\">1<", chosen.text)
    assert _carried(chosen.text) == data


def test_a_column_out_of_range_is_ignored(client: TestClient) -> None:
    data = b"email\r\na@x.edu\r\n"
    page = client.post(URL, files={"content": (None, base64.b64encode(data)), "column": (None, "9")})
    assert '<option value="0" selected>email</option>' in page.text


@pytest.mark.parametrize(
    ("files", "message"),
    [
        ({"file": ("", b"", "text/csv")}, "Choose a CSV file first."),
        ({"file": ("x.csv", b"email\r\n", "text/csv")}, "header but no rows"),
        ({"content": (None, "not base64!")}, "Upload it again."),
    ],
)
def test_a_refused_file_returns_to_the_upload_page_with_why(
    client: TestClient, files: dict, message: str
) -> None:
    page = client.post(URL, files=files)
    assert page.status_code == 400
    assert 'role="alert"' in page.text and message in page.text
    assert '<input id="file" name="file" type="file"' in page.text


def test_a_file_at_the_byte_limit_round_trips_through_the_page(client: TestClient) -> None:
    """The carried copy is a third larger than the file; the form's part
    limit allows it."""
    row = b"a@x.edu," + b"x" * 2500 + b"\r\n"
    data = b"email,pad\r\n" + row * ((csvio.MAX_BYTES - 20) // len(row))
    assert len(data) <= csvio.MAX_BYTES
    first = _upload(client, data)
    assert first.status_code == 200
    again = client.post(URL, files={"content": (None, base64.b64encode(data)), "column": (None, "0")})
    assert again.status_code == 200 and _carried(again.text) == data


def test_the_check_stays_disabled_until_rung_5(client: TestClient) -> None:
    text = _upload(client, b"email\r\na@x.edu\r\n").text
    assert re.search(r'<button class="btn primary" type="button" disabled>Check addresses', text)


def test_preview_is_404_deployed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from utilityapps.email_check import routes

    monkeypatch.setattr(routes, "is_local", lambda: False)
    assert _upload(client, b"email\r\na@x.edu\r\n").status_code == 404
