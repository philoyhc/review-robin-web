"""The preview gate (`residentialapps/web/pages.py`): deployed, the
placeholder screens answer the platform super-admin and the accounts a
preview list names, by mail, sign-in name or address, and 404 everyone
else; locally they answer anyone, and health always answers."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cordware.identity import Identity
from cordware.settings import IdentitySettings
from residentialapps.residentialops.main import create_app as ops_app
from residentialapps.supportlogs.main import create_app as support_app
from residentialapps.web import pages as web_pages

LIST = """# Residential preview

Who may open the placeholder screens. One address per list item.

- `rf.one@example.edu` (RF, Tower A)
* RA.Two@Example.edu
- not an address, a note
- staff.three@example.edu, trailing prose
  - `nested@example.edu` is indented, so not read

Prose naming prose@example.edu is not a list item.
"""


@pytest.fixture
def preview_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "residential_preview.md"
    path.write_text(LIST, encoding="utf-8")
    monkeypatch.setattr(web_pages, "PREVIEW_FILE", path)
    monkeypatch.setattr(web_pages, "is_local", lambda: False)
    web_pages.preview_addresses.cache_clear()
    yield path
    web_pages.preview_addresses.cache_clear()


def signed_in(monkeypatch: pytest.MonkeyPatch, identity: Identity | None) -> None:
    monkeypatch.setattr(web_pages, "current_identity", lambda request: identity)


def person(*, mail: str | None = None, upn: str | None = None, email: str | None = None) -> Identity:
    return Identity(
        principal_id="p", email=email or mail or upn, name="Someone", mail=mail, upn=upn,
        resolved_with=IdentitySettings(super_admin_emails=["boss@example.edu"]),
    )


def test_the_list_reads_list_items_whose_first_word_is_an_address(preview_file: Path) -> None:
    assert web_pages.preview_addresses(preview_file) == frozenset(
        {"rf.one@example.edu", "ra.two@example.edu", "staff.three@example.edu"}
    )


def test_no_file_names_nobody(tmp_path: Path) -> None:
    assert web_pages.preview_addresses(tmp_path / "absent.md") == frozenset()


@pytest.mark.parametrize(
    "identity",
    [
        person(mail="rf.one@example.edu"),
        person(mail="RA.two@EXAMPLE.edu"),
        person(upn="ra.two@example.edu", mail="someone.else@example.edu"),
        person(mail="staff.three@example.edu"),
        person(email="boss@example.edu"),  # the platform super-admin, unlisted
    ],
)
def test_a_previewer_reaches_both_applications(
    preview_file: Path, monkeypatch: pytest.MonkeyPatch, identity: Identity
) -> None:
    signed_in(monkeypatch, identity)
    assert TestClient(ops_app()).get("/").status_code == 200
    assert TestClient(ops_app()).get("/ra-leave/").status_code == 200
    assert TestClient(support_app()).get("/").status_code == 200


@pytest.mark.parametrize(
    "identity",
    [None, person(mail="prose@example.edu"), person(mail="nested@example.edu"),
     person(mail="rf.one@example.edu.sg"), person()],
)
def test_anyone_else_gets_404_and_health_still_answers(
    preview_file: Path, monkeypatch: pytest.MonkeyPatch, identity: Identity | None
) -> None:
    signed_in(monkeypatch, identity)
    for app in (ops_app(), support_app()):
        client = TestClient(app)
        assert client.get("/").status_code == 404
        assert client.get("/health").status_code == 200


def test_a_local_run_answers_anyone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_pages, "is_local", lambda: True)
    signed_in(monkeypatch, None)
    assert TestClient(ops_app()).get("/").status_code == 200
    assert TestClient(support_app()).get("/").status_code == 200


def test_comments_and_fenced_code_do_not_name_anyone() -> None:
    text = """- kept@example.edu
<!--
- commented.out@example.edu
-->
<!-- - one.line@example.edu -->
```
- fenced@example.edu
```
~~~
- tilde.fenced@example.edu
~~~
- after@example.edu
<!-- unterminated
- tail@example.edu
"""
    assert web_pages.parse_preview_list(text) == frozenset({"kept@example.edu", "after@example.edu"})


@pytest.mark.parametrize(
    ("item", "address"),
    [
        ("- end.dot@example.edu.", "end.dot@example.edu"),
        ("- <angled@example.edu>", "angled@example.edu"),
        ("+ `tight@example.edu`(RF)", "tight@example.edu"),
        ("- two@at@example.edu", None),
        ("- no-domain@example", None),
        ("- [linked@example.edu](mailto:linked@example.edu)", None),
    ],
)
def test_an_item_s_first_word_is_trimmed_then_must_be_one_address(item: str, address: str | None) -> None:
    assert web_pages.parse_preview_list(item) == (frozenset({address}) if address else frozenset())


def test_an_unreadable_list_names_nobody(tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_bytes(b"- \xff\xfe@example.edu\n")
    web_pages.preview_addresses.cache_clear()
    assert web_pages.preview_addresses(tmp_path / "bad.md") == frozenset()
    assert web_pages.preview_addresses(tmp_path) == frozenset()  # a directory
    web_pages.preview_addresses.cache_clear()


def test_a_fence_closes_only_on_its_own_marker_at_least_as_long() -> None:
    text = """~~~markdown
```
- inner.backticks@example.edu
```
- still.fenced@example.edu
~~~
````
```
- short.inner@example.edu
````
- open.again@example.edu
"""
    assert web_pages.parse_preview_list(text) == frozenset({"open.again@example.edu"})


def test_indented_lines_never_name_anyone() -> None:
    text = """- parent item

    ```
    - in.indented.fence@example.edu
    ```
        - in.indented.code@example.edu
  - nested.item@example.edu
- top.level@example.edu
"""
    assert web_pages.parse_preview_list(text) == frozenset({"top.level@example.edu"})


def test_an_over_indented_marker_does_not_close_a_fence() -> None:
    text = """```
    ```
- inside.still@example.edu
```
    ~~~
    - nested.opened@example.edu
      ~~~
- also.inside@example.edu
    ~~~
- after@example.edu
"""
    assert web_pages.parse_preview_list(text) == frozenset({"after@example.edu"})


def test_comments_are_literal_inside_a_fence_and_only_ever_remove() -> None:
    text = """```
``` <!-- still code -->
- in.fence@example.edu
```
<!-- c -->- made.by.stripping@example.edu
- before.comment@example.edu <!-- a note -->
<!-- opens
- hidden@example.edu
--> - on.the.closing.line@example.edu
<!-- a --> <!-- b
- hidden.too@example.edu
-->
<!--
```
- fence.inside.comment@example.edu
-->
- after@example.edu
"""
    assert web_pages.parse_preview_list(text) == frozenset({"before.comment@example.edu", "after@example.edu"})
