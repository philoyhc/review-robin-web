"""The Email Address Checker's pages as rung 2 built them: the upload
page, the sample preview and the sample result, each answering on a
local run with its copy, and 404 deployed until rung 5 gates them. The
wired preview is `test_email_check_preview.py`'s."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from utilityapps.email_check import routes
from utilityapps.tests._host import host_with

PAGES = ("/utilities/email-check/", "/utilities/email-check/preview", "/utilities/email-check/result")


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("utilities",))[0])


@pytest.mark.parametrize("path", PAGES[1:])
def test_sample_pages_have_inert_controls(client: TestClient, path: str) -> None:
    page = client.get(path)
    assert page.status_code == 200
    assert "<h1>Email Address Checker</h1>" in page.text
    assert "Placeholder: sample counts" in page.text
    # Every visible control that would act is disabled.
    for tag in re.findall(r"<(?:button|input|select)\b[^>]*>", page.text):
        assert "disabled" in tag or 'type="hidden"' in tag, tag


def test_upload_posts_the_file_to_the_preview(client: TestClient) -> None:
    text = client.get(PAGES[0]).text
    assert 'method="post" action="/utilities/email-check/preview" enctype="multipart/form-data"' in text
    assert '<input id="file" name="file" type="file"' in text


@pytest.mark.parametrize("path", PAGES)
def test_every_app_link_carries_the_mount(client: TestClient, path: str) -> None:
    hrefs = re.findall(r'href="(/[^"]*)"', client.get(path).text)
    for href in hrefs:
        assert href in ("/", "/.auth/logout") or href.startswith("/utilities/"), href


def test_upload_states_the_limits_and_the_caveats(client: TestClient) -> None:
    text = client.get(PAGES[0]).text
    assert "up to 500 rows and 1 MiB" in text
    assert "Nothing you upload is kept" in text
    assert "is not proof that it" in text


def test_preview_offers_the_column_choice_and_counts(client: TestClient) -> None:
    text = client.get(PAGES[1]).text
    assert '<option value="1" selected>Work email</option>' in text
    assert "Nothing has been looked up yet." in text
    assert 'role="alert"' not in text


def test_preview_without_directory_access_says_so(client: TestClient) -> None:
    text = client.get(PAGES[1] + "?state=no-graph").text
    assert 'role="alert"' in text and "The directory can" in text


def test_result_lists_every_status_and_the_coverage(client: TestClient) -> None:
    text = client.get(PAGES[2]).text
    for status in routes.SAMPLE_RESULT:
        assert f'<code class="status">{status.replace("_", "_<wbr>")}</code>' in text
    assert f"Checked {sum(routes.SAMPLE_RESULT.values())} rows" in text
    assert "<code>BASIC_ONLY</code>" in text
    assert "Download checked CSV" in text


@pytest.mark.parametrize("path", PAGES)
def test_placeholders_are_404_deployed(
    client: TestClient, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(routes, "is_local", lambda: False)
    assert client.get(path).status_code == 404
    # The index and the probe are not placeholders.
    assert client.get("/utilities/").status_code == 200
    assert client.get("/utilities/health").status_code == 200
