"""Support Logs' Who can see what (author, 2026-11-07): the staff
explainer as a page of its own, linked from every screen. Its text is
`residentialapps/docs/support_logs_confidentiality.md`'s, which is not
deployed, so these tests keep the page's headings and quick answers in
step with it."""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from residentialapps.supportlogs.main import create_app
from residentialapps.tests._host import host_with

DOC = Path(__file__).resolve().parents[1] / "docs" / "support_logs_confidentiality.md"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def _words(text: str) -> list[str]:
    """Text as its words, markup gone: Markdown's list marks and emphasis,
    and HTML tags."""
    text = re.sub(r"(?m)^\s*-\s+", " ", text)
    text = re.sub(r"<[^>]+>", " ", html.unescape(text))
    text = re.sub(r"[*_`#]", " ", text)
    return text.split()


def test_the_page_follows_the_doc_word_for_word(client: TestClient) -> None:
    """The page's text from the date line on is the doc's, word for word:
    a changed answer, sentence or bullet fails here, not only a heading."""
    page = client.get("/who-can-see-what").text
    main = page.split("<h1>", 1)[1].split('aria-label="Sample viewer"', 1)[0]
    got = _words(main)
    want = _words(DOC.read_text())
    start = want.index("Agreed")
    assert got[got.index("Agreed") : got.index("Agreed") + len(want) - start] == want[start:]
    assert "<h1>Who can see what" in page


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/students/",
        "/log",
        "/oversight-students/?as=Sam%20Lee",
        "/consultation/?as=Hui%20Min%20Goh",
        "/sys-admin/?as=Rachel%20Yeo",
    ],
)
def test_every_screen_links_to_it_from_the_account_menu(client: TestClient, path: str) -> None:
    signed_in = {"X-MS-CLIENT-PRINCIPAL-NAME": "someone@example.edu"}
    page = client.get(path, headers=signed_in).text
    menu = page.split('aria-label="Account"', 1)[1].split("</nav>", 1)[0]
    assert ">Who can see what</a>" in menu, path


def test_pages_naming_students_link_to_it(client: TestClient) -> None:
    """Every page whose notice says opening it is recorded (spec §6); a
    notice links it once (Home's Waiting for you links it too)."""
    for path in (
        "/",
        "/students/S-03",
        "/plans/P-01",
        "/flags/F-01",
        "/oversight-students/?as=Sam%20Lee",
        "/oversight-students/S-03?as=Sam%20Lee",
        "/oversight-staff/audit?as=Sam%20Lee",
        "/consultation/?as=Hui%20Min%20Goh",
    ):
        main = client.get(path).text.split("<main", 1)[1]
        assert main.count(">Who can see what</a>") == (2 if path == "/" else 1), path


def test_anyone_who_reaches_support_logs_can_read_it(client: TestClient) -> None:
    for name in ("Daniel%20Koh", "Sam%20Lee", "Hui%20Min%20Goh", "Rachel%20Yeo", "Wei%20Jie%20Ong"):
        assert client.get(f"/who-can-see-what?as={name}").status_code == 200, name


def test_the_mounted_page_stays_under_the_mount() -> None:
    host, _ = host_with(("supportlogs",))
    page = TestClient(host).get("/supportlogs/who-can-see-what")
    assert page.status_code == 200
    for link in re.findall(r'\bhref="([^"]*)"', re.sub(r'<link rel="icon"[^>]*>', "", page.text)):
        assert link in ("/", "/.auth/logout") or link.startswith(("/supportlogs/", "#")), link
