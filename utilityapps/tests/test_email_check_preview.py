"""The upload and the preview (segment U1, rung 3; the check button rung
5's): the file goes in, its counts come back, and it is carried in the
page, never kept."""

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
    for label, n in [("Rows", 3), ("kept, not checked", 1), ("checked once", 1), ("Addresses to check", 1)]:
        assert re.search(label + r"[^<]*</th><td class=\"n\"[^>]*>" + str(n) + "<", text), label
    assert _carried(text) == data


def test_the_counts_read_as_a_subtraction(client: TestClient) -> None:
    """Rows, less blanks, less repeats, leaves the lookups: listed in that
    order, the last the distinct addresses (segment U2)."""
    data = b"email\r\na@x.edu\r\nnot an address\r\nB@x.edu\r\nA@x.edu\r\nb@x.edu\r\nc@x.edu\r\n"
    text = _upload(client, data).text
    labels = ["Rows", "kept, not checked", "checked once", "Addresses to check"]
    numbers = [
        int(re.search(label + r"[^<]*</th><td class=\"n\"[^>]*>(\d+)<", text).group(1)) for label in labels
    ]
    assert numbers == [6, 1, 2, 3]
    assert numbers[0] - numbers[1] - numbers[2] == numbers[3]
    assert [text.index(label) for label in labels] == sorted(text.index(label) for label in labels)


def test_without_an_email_column_the_operator_chooses(client: TestClient) -> None:
    data = b"Name,Work address\r\nA,a@x.edu\r\n"
    first = _upload(client, data).text
    assert '<option value="" selected>Choose a column' in first
    assert "Addresses to check" not in first
    chosen = client.post(
        URL, data={"content": base64.b64encode(data).decode(), "filename": "list.csv", "column": "1"}
    )
    assert chosen.status_code == 200
    assert '<option value="1" selected>Work address</option>' in chosen.text
    assert re.search(r"Addresses to check</th><td class=\"n\"[^>]*>1<", chosen.text)
    assert _carried(chosen.text) == data


def test_a_column_out_of_range_is_ignored(client: TestClient) -> None:
    data = b"email\r\na@x.edu\r\n"
    page = client.post(URL, data={"content": base64.b64encode(data).decode(), "column": "9"})
    assert '<option value="0" selected>email</option>' in page.text


@pytest.mark.parametrize(
    ("files", "message"),
    [
        ({"file": ("", b"", "text/csv")}, "Choose a CSV file first."),
        ({"file": ("x.csv", b"email\r\n", "text/csv")}, "header but no rows"),
        ({"content": (None, "not base64!")}, "Upload it again."),
        ({"content": (None, "x" * (2 * 1024 * 1024))}, "larger than 1024 KiB"),
    ],
)
def test_a_refused_file_returns_to_the_upload_page_with_why(
    client: TestClient, files: dict, message: str
) -> None:
    page = client.post(URL, files=files)
    assert page.status_code == 400
    assert 'role="alert"' in page.text and message in page.text
    assert '<input id="file" name="file" type="file"' in page.text


def test_a_file_near_the_byte_limit_round_trips_through_the_page(client: TestClient) -> None:
    """The upload's whole request is held to `MAX_BYTES`, the form's own
    few hundred bytes included; the carried copy, a third larger, posts
    URL-encoded under its own limit."""
    row = b"a@x.edu," + b"x" * 2500 + b"\r\n"
    data = b"email,pad\r\n" + row * ((csvio.MAX_BYTES - 4096) // len(row))
    assert len(data) <= csvio.MAX_BYTES - 4096
    first = _upload(client, data)
    assert first.status_code == 200
    again = client.post(URL, data={"content": base64.b64encode(data).decode(), "column": "0"})
    assert again.status_code == 200 and _carried(again.text) == data


def test_an_upload_over_the_limit_is_refused_before_it_is_read(client: TestClient) -> None:
    page = _upload(client, b"email\r\n" + b"a@x.edu\r\n" * (csvio.MAX_BYTES // 9))
    assert page.status_code == 400 and "larger than 1024 KiB" in page.text


def test_an_upload_without_a_length_is_refused(client: TestClient) -> None:
    # A streamed body goes chunked, with no `Content-Length`.
    request = client.build_request(
        "POST", URL, content=iter([b"x"]), headers={"content-type": "multipart/form-data; boundary=b"}
    )
    page = client.send(request)
    assert page.status_code == 400 and "did not say its size" in page.text


@pytest.mark.parametrize("column", ["²", "-1", " 1", "1.0"])
def test_a_column_that_is_not_a_plain_index_is_ignored(client: TestClient, column: str) -> None:
    data = b"email\r\na@x.edu\r\n"
    page = client.post(URL, data={"content": base64.b64encode(data).decode(), "column": column})
    assert page.status_code == 200 and '<option value="0" selected>email</option>' in page.text


def test_the_check_posts_the_carried_file_to_the_check(client: TestClient) -> None:
    text = _upload(client, b"email\r\na@x.edu\r\n").text
    assert re.search(
        r'<button class="btn primary" type="submit" id="check-button" formaction="/utilities/email-check/check">Check addresses',
        text,
    )
    assert "no-store" in _upload(client, b"email\r\na@x.edu\r\n").headers["cache-control"]


def test_the_check_is_disabled_until_a_column_is_chosen(client: TestClient) -> None:
    text = _upload(client, b"Name,Work\r\nA,a@x.edu\r\n").text
    assert re.search(r'formaction="/utilities/email-check/check" disabled>Check addresses', text)
