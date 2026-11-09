"""The preview gate (`residentialapps/web/pages.py`): deployed, the
placeholder screens answer the platform super-admin and the accounts a
preview list names, by mail, sign-in name or address, and 404 everyone
else; locally they answer anyone, and health always answers."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from cordware.identity import Identity
from cordware.settings import IdentitySettings
from residentialapps.residentialops import routes_leave_ra
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
def preview_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    path = tmp_path / "residential_preview.md"
    path.write_text(LIST, encoding="utf-8")
    monkeypatch.setattr(web_pages, "PREVIEW_FILE", path)
    monkeypatch.setattr(web_pages, "is_local", lambda: False)
    web_pages.preview_lists.cache_clear()
    yield path
    web_pages.preview_lists.cache_clear()


def signed_in(monkeypatch: pytest.MonkeyPatch, identity: Identity | None) -> None:
    monkeypatch.setattr(web_pages, "current_identity", lambda request: identity)


def person(
    *, mail: str | None = None, upn: str | None = None, email: str | None = None
) -> Identity:
    return Identity(
        principal_id="p",
        email=email or mail or upn,
        name="Someone",
        mail=mail,
        upn=upn,
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
    [
        None,
        person(mail="prose@example.edu"),
        person(mail="nested@example.edu"),
        person(mail="rf.one@example.edu.sg"),
        person(),
    ],
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
    assert web_pages.parse_preview_list(text) == frozenset(
        {"kept@example.edu", "after@example.edu"}
    )


@pytest.mark.parametrize(
    ("item", "address"),
    [
        ("- end.dot@example.edu.", "end.dot@example.edu"),
        ("- <angled@example.edu>", "angled@example.edu"),
        ("- <closed@example.edu>.", "closed@example.edu"),
        ("- <listed@example.edu>,", "listed@example.edu"),
        ("+ `tight@example.edu`(RF)", "tight@example.edu"),
        ("- two@at@example.edu", None),
        ("- no-domain@example", None),
        ("- [linked@example.edu](mailto:linked@example.edu)", None),
    ],
)
def test_an_item_s_first_word_is_trimmed_then_must_be_one_address(
    item: str, address: str | None
) -> None:
    assert web_pages.parse_preview_list(item) == (frozenset({address}) if address else frozenset())


def test_an_unreadable_list_names_nobody(tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_bytes(b"- \xff\xfe@example.edu\n")
    web_pages.preview_lists.cache_clear()
    assert web_pages.preview_addresses(tmp_path / "bad.md") == frozenset()
    assert web_pages.preview_addresses(tmp_path) == frozenset()  # a directory
    web_pages.preview_lists.cache_clear()


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
    assert web_pages.parse_preview_list(text) == frozenset(
        {"before.comment@example.edu", "after@example.edu"}
    )


def _gated_routes(
    routes: Sequence[Any], gates: tuple[object, ...] = ()
) -> Iterator[tuple[Any, set[object]]]:
    """Every route under ``routes`` with the dependencies that guard it:
    its own dependency tree plus each enclosing include's (FastAPI nests
    an included router behind its include context)."""
    for route in routes:
        context = getattr(route, "include_context", None)
        if context is not None:
            outer = tuple(d.dependency for d in context.dependencies or ())
            yield from _gated_routes(context.included_router.routes, gates + outer)
            continue
        calls: set[object] = set(gates)
        pending = list(route.dependant.dependencies if hasattr(route, "dependant") else ())
        while pending:
            dependant = pending.pop()
            calls.add(dependant.call)
            pending.extend(dependant.dependencies)
        yield route, calls


#: The only routes that answer without the preview gate.
UNGATED = {"/health"}


@pytest.mark.parametrize("factory", [ops_app, support_app])
def test_every_route_but_health_carries_the_gate(factory) -> None:
    """Findings register N1: the gate was tested at ``GET /`` only, so a
    new router that forgot ``Depends(placeholders_previewers_only)``
    would have passed. This walks every route the application builds.
    RA Leave's RA pages and the landing take the RA previewers' gate
    instead (author, 2026-11-09), and only they."""
    routes = list(_gated_routes(factory().routes))
    assert len(routes) > len(UNGATED)
    missing, ra_gated = [], []
    for route, calls in routes:
        if route.path in UNGATED:
            continue
        if web_pages.ra_pages_previewers in calls:
            ra_gated.append(route.path)
        elif web_pages.placeholders_previewers_only not in calls:
            missing.append(route.path)
    assert missing == []
    if factory is support_app:
        assert ra_gated == []  # Support Logs has no RA previewers
    else:
        ra_router = {r.path for r in routes_leave_ra.router.routes if isinstance(r, APIRoute)}
        assert set(ra_gated) == {"/"} | ra_router


SECTIONED = """# Residential preview

- full@example.edu

## RA previewers

Some RAs, to try RA Leave's RA pages.

- ra.one@example.edu
- `Ra.Two@Example.edu` (RA, Cypress)
- both@example.edu
<!--
## Not a heading: commented out
-->
- still.ra@example.edu
Tan Wei Ling <Wei.Ling@example.edu>; Lim, Jun <jun.lim@example.edu>;
    Indented <indented@example.edu> is not read.
Prose naming bare@example.edu names nobody.

## Staff

- staff@example.edu
- both@example.edu
"""


def test_the_ra_previewers_heading_starts_an_ra_only_section() -> None:
    """Author, 2026-11-09: addresses under "RA previewers" reach only RA
    Leave's RA pages and the landing; any other heading ends the section,
    and an address named in both is a full previewer."""
    full, ra = web_pages.parse_preview_sections(SECTIONED)
    assert full == frozenset({"full@example.edu", "staff@example.edu", "both@example.edu"})
    assert ra == frozenset(
        {
            "ra.one@example.edu",
            "ra.two@example.edu",
            "still.ra@example.edu",
            # A distribution list pasted as a mail client copies it.
            "wei.ling@example.edu",
            "jun.lim@example.edu",
        }
    )
    assert web_pages.parse_preview_list(SECTIONED) == full | ra
    # A heading in a fence or indented changes no section.
    fenced = "```\n## RA previewers\n```\n- fenced.heading@example.edu\n"
    assert web_pages.parse_preview_sections(fenced).full == {"fenced.heading@example.edu"}


@pytest.fixture
def sectioned_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    path = tmp_path / "residential_preview.md"
    path.write_text(SECTIONED, encoding="utf-8")
    monkeypatch.setattr(web_pages, "PREVIEW_FILE", path)
    monkeypatch.setattr(web_pages, "is_local", lambda: False)
    web_pages.preview_lists.cache_clear()
    yield path
    web_pages.preview_lists.cache_clear()


RA_PAGES = (
    "/",
    "/ra-leave/",
    "/ra-leave/apply",
    "/ra-leave/cover",
    "/ra-leave/history",
    "/ra-leave/applications/L-0101",
)
NOT_RA_PAGES = (
    "/ra-leave/staff/",
    "/ra-leave/staff/decide",
    "/ra-leave/admin/",
    "/ra-leave/admin/policy",
    "/rosters/",
    "/sys-admin/",
)


def test_an_ra_previewer_reaches_the_ra_pages_and_the_landing_only(
    sectioned_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    signed_in(monkeypatch, person(mail="ra.one@example.edu"))
    ops = TestClient(ops_app())
    for path in RA_PAGES:
        assert ops.get(path).status_code == 200, path
    for path in NOT_RA_PAGES:
        assert ops.get(path).status_code == 404, path
    assert TestClient(support_app()).get("/").status_code == 404
    # The landing is the sample RA's, with no viewer to switch to.
    landing = ops.get("/?as=Sam%20Lee").text
    assert "Viewing as Chloe Lim" in landing and 'id="sample-viewer"' not in landing
    assert 'href="/ra-leave/"' in landing and "/ra-leave/admin/" not in landing


def test_a_full_previewer_keeps_the_landing_s_viewers(
    sectioned_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    signed_in(monkeypatch, person(mail="both@example.edu"))
    ops = TestClient(ops_app())
    assert ops.get("/ra-leave/admin/").status_code == 200
    landing = ops.get("/?as=Sam%20Lee").text
    assert 'id="sample-viewer"' in landing and "Viewing as Sam Lee" in landing


@pytest.mark.parametrize(
    "heading",
    [
        "## RA previewers",
        "RA previewers\n=============",
        "  ## RA previewers",
        "## RA previewers:",
        "## RA previewers (RA Leave only)",
        "**RA previewers**",
        "##RA previewers",
        "## RA  previewers",
        "### ra previewer",
        "RA previewers, to try RA Leave:",
    ],
)
def test_a_heading_written_differently_still_keeps_ra_previewers_ra_only(heading: str) -> None:
    """The cold read: the section fails safe. However the heading is
    written, those under it never become full previewers."""
    text = f"- full@example.edu\n\n{heading}\n\n- ra@example.edu\nName <pasted@example.edu>\n"
    full, ra = web_pages.parse_preview_sections(text)
    assert full == {"full@example.edu"}
    assert ra == {"ra@example.edu", "pasted@example.edu"}


def test_a_list_item_or_address_saying_ra_previewers_starts_no_section() -> None:
    text = "- ra.previewers@example.edu\n- note: RA previewers come later\n- after@example.edu\n"
    assert web_pages.parse_preview_sections(text).full == {
        "ra.previewers@example.edu",
        "after@example.edu",
    }


@pytest.mark.parametrize(
    "line",
    [
        "Questions to <owner@example.edu>.",
        "> <quote@example.edu>",
        "| <table@example.edu> |",
        "Ask <a@example.edu> or <b@example.edu> about it: soon",
    ],
)
def test_only_a_whole_distribution_line_names_its_addresses(line: str) -> None:
    text = f"## RA previewers\n\n{line}\n"
    assert web_pages.parse_preview_sections(text) == (frozenset(), frozenset())


def test_an_ra_previewer_s_landing_chip_is_not_a_dead_link(
    sectioned_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    signed_in(monkeypatch, person(mail="ra.one@example.edu"))
    landing = TestClient(ops_app()).get("/").text
    assert 'href="#sample-viewer"' not in landing
