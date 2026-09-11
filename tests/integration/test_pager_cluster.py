"""The page pager: the cluster renders, in both places, and navigates.

Segment 19J Item 9, rung 2 — wired, and the 19J.5 range strip retired
in the same rung, because a wired cluster beside a working strip is two
pagers on one page.

The strip's reach was a constant two pages per click whatever the
roster size, so crossing a long roster cost a number of clicks linear
in its length: 5 to row 2,400 of 5,861, 50 to the middle of 40,000. The
cluster — ``«‹ [range ▾] ›»`` — reaches any page in one.

``test_the_scaffold_navigates_nowhere`` was written at rung 1 to be
deleted here, and was. Its replacement,
``test_every_cell_navigates_and_agrees_with_the_menu``, asserts the
opposite: every cell is an anchor, and a step's destination is the same
URL the menu entry for that range carries. Two ways to spell one page
turn is how they drift.

Assertions read the rendered cluster — the markup between
``<div class="table-pager-cluster`` and its closing ``</div>`` — rather
than searching the whole body, because every class name here is also
defined in ``base.html``'s inline CSS, which ships on every response
(19J.5 hit that three times, 19J.7 rung 4 again).
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.web.views import PAGE_SIZE

#: Seven pages. Enough that the menu is visibly more than a strip's
#: five-wide window would have been, which is the reason the cluster
#: exists.
PAGING_ROWS = 7 * PAGE_SIZE + 1

#: Three pages. Still more than one, so still a pager: rung 1 rendered
#: the cluster only where the strip elided, on the reasoning that a jump
#: control is noise beside a strip already showing every range. Retiring
#: the strip retired that reasoning, and a short multi-page table would
#: otherwise have had no pager at all.
SHORT_ROWS = 556

#: One page. No pager, as it has been since 19J.5.
ONE_PAGE_ROWS = 12

TEMPLATES = (
    "session_reviewers.html",
    "session_reviewees.html",
    "session_relationships.html",
    "session_observers.html",
    "session_assignments.html",
    "session_invitations.html",
    "session_responses.html",
)


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _reviewers_page(
    client: TestClient, db: Session, *, code: str, rows: int, offset: int = 0
) -> str:
    review_session = _make_session(client, db, code=code)
    csv = b"".join(
        f"Reviewer {i:05d},r{i:05d}@example.edu\n".encode()
        for i in range(rows)
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv", b"ReviewerName,ReviewerEmail\n" + csv, "text/csv"
            )
        },
        follow_redirects=False,
    )
    assert response.status_code in (200, 303), response.status_code
    return client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
        + (f"?offset={offset}" if offset else "")
    ).text


def _clusters(body: str) -> list[str]:
    """Each rendered cluster's markup, opening tag to closing ``</div>``.

    The cluster's only nested element is the ``<details>``, so the
    second ``</div>`` after the opening tag closes the cluster: one for
    the menu panel, one for the cluster itself.
    """
    out: list[str] = []
    for match in re.finditer(r'<div class="table-pager-cluster', body):
        start = match.start()
        depth = 0
        for tag in re.finditer(r"<(/?)div\b", body[start:]):
            depth += -1 if tag.group(1) else 1
            if depth == 0:
                out.append(body[start : start + tag.end() + 1])
                break
    return out


def test_the_cluster_renders_twice_on_a_table_that_pages(
    client: TestClient, db: Session
) -> None:
    """Both places, and that is not optional.

    ``base.html``: *"a 200-row table is several screens tall and a pager
    only at the top makes the operator scroll back to use it."* A
    top-only cluster would mean reading to the bottom of 200 rows and
    scrolling back up to advance.
    """
    body = _reviewers_page(client, db, code="cluster-1", rows=PAGING_ROWS)

    clusters = _clusters(body)
    assert len(clusters) == 2, f"expected two clusters, found {len(clusters)}"

    # The second is the one below the table, and says so.
    assert "table-pager-cluster-bottom" in clusters[1]
    assert "table-pager-cluster-bottom" not in clusters[0]

    # The top one sits in the row it owns, above the strip.
    toolbar = body.index('<div class="table-card-toolbar">')
    assert toolbar < body.index('<div class="table-pager-cluster')
    # …and above the table it pages, where 19I Item 10 put the count
    # sentence the strip used to sit beside.
    assert body.index('<div class="table-pager-cluster') < body.index(
        'id="reviewers-table"'
    )


def test_a_short_multi_page_table_still_gets_a_pager(
    client: TestClient, db: Session
) -> None:
    """The judgment call rung 1 made, and rung 2 had to unmake.

    Rung 1 rendered the cluster only where the strip elided: beside a
    strip already showing every range, a jump control is a second way to
    do what one click does. Retiring the strip retired that reasoning
    with it — three pages and no pager would have been a regression the
    condition was never meant to cause.
    """
    body = _reviewers_page(client, db, code="cluster-2", rows=SHORT_ROWS)

    clusters = _clusters(body)
    assert len(clusters) == 2

    entries = re.findall(
        r'<(?:a|span) class="table-pager-menu-item[^"]*"[^>]*?>([^<]+)</(?:a|span)>',
        clusters[0],
        re.S,
    )
    assert entries == ["1–200", "201–400", f"401–{SHORT_ROWS}"]


def test_one_page_still_gets_no_pager(
    client: TestClient, db: Session
) -> None:
    """Unchanged since 19J.5, and worth pinning through a surface
    change: a control that cannot go anywhere is noise."""
    body = _reviewers_page(client, db, code="cluster-2b", rows=ONE_PAGE_ROWS)

    assert _clusters(body) == []
    assert "table-pager-cluster" not in body.split("</style>")[-1]


def test_the_menu_holds_every_range_in_the_table(
    client: TestClient, db: Session
) -> None:
    """The whole point: eight ranges reachable from any of them.

    The strip it replaced showed a five-wide window, so the middle of a
    long roster took repeated page loads to walk to.
    """
    body = _reviewers_page(client, db, code="cluster-3", rows=PAGING_ROWS)
    cluster = _clusters(body)[0]

    # Both kinds: every range but the one you are on is an anchor, and
    # that one is a span. Matching only one kind would count seven and
    # call it every range.
    entries = re.findall(
        r'<(?:a|span) class="table-pager-menu-item[^"]*"[^>]*?>([^<]+)</(?:a|span)>',
        cluster,
        re.S,
    )
    assert len(entries) == 8, entries
    assert entries[0] == "1–200"
    assert entries[-1] == f"1,401–{PAGING_ROWS:,}"

    # More than 19J.5's window, which is the reason to exist: five
    # ranges could never reach the eighth without stepping.
    assert len(entries) > 5

    # The summary names where you are, so the menu doubles as the
    # position indicator and the strip's bold cell can retire.
    assert "<summary>1–200</summary>" in cluster
    assert cluster.count('aria-current="page"') == 1


def _glyph_states(cluster: str) -> dict[str, str]:
    """Each step glyph against whether it navigates."""
    out: dict[str, str] = {}
    for tag, cls, glyph in re.findall(
        r'<(a|span) class="btn-icon table-pager-step([^"]*)"[^>]*?>([^<]+)</\1>',
        cluster,
        re.S,
    ):
        out[glyph] = "active" if tag == "a" else "inactive"
        assert ("is-inactive" in cls) == (tag == "span"), (
            f"{glyph}: class and element disagree about its state"
        )
    return out


def test_the_ends_are_inactive_at_the_ends(
    client: TestClient, db: Session
) -> None:
    """In place, never absent: absent buttons would shift the other
    cells sideways as the operator pages.

    Read on the first page *and* the last, because a condition wrong in
    one direction passes half of this test.
    """
    first = _clusters(
        _reviewers_page(client, db, code="cluster-4", rows=PAGING_ROWS)
    )[0]
    assert _glyph_states(first) == {
        "«": "inactive",
        "‹": "inactive",
        "›": "active",
        "»": "active",
    }
    assert first.count('aria-disabled="true"') == 2

    last = _clusters(
        _reviewers_page(
            client, db, code="cluster-4b", rows=PAGING_ROWS,
            offset=7 * PAGE_SIZE,
        )
    )[0]
    assert _glyph_states(last) == {
        "«": "active",
        "‹": "active",
        "›": "inactive",
        "»": "inactive",
    }

    # And in the middle every cell goes somewhere.
    middle = _clusters(
        _reviewers_page(
            client, db, code="cluster-4c", rows=PAGING_ROWS,
            offset=3 * PAGE_SIZE,
        )
    )[0]
    assert set(_glyph_states(middle).values()) == {"active"}


def test_every_cell_navigates_and_agrees_with_the_menu(
    client: TestClient, db: Session
) -> None:
    """Replaces rung 1's ``test_the_scaffold_navigates_nowhere``.

    Two things at once, because either alone would pass a broken pager:
    every cell is an anchor, **and** a step's destination is the exact
    URL the menu entry for that same range carries. Two ways to spell
    one page turn is how they drift.
    """
    body = _reviewers_page(
        client, db, code="cluster-5", rows=PAGING_ROWS,
        offset=3 * PAGE_SIZE,
    )
    cluster = _clusters(body)[0]

    menu = dict(
        (label, href)
        for href, label in re.findall(
            r'<a class="table-pager-menu-item"\s+href="([^"]+)">([^<]+)</a>',
            cluster,
        )
    )
    assert len(menu) == 7  # eight ranges, less the one you are on

    steps = dict(
        (glyph, href)
        for href, glyph in re.findall(
            r'<a class="btn-icon table-pager-step"\s+href="([^"]+)"[^>]*>'
            r"([^<]+)</a>",
            cluster,
            re.S,
        )
    )
    assert set(steps) == {"«", "‹", "›", "»"}

    assert steps["«"] == menu["1–200"]
    assert steps["‹"] == menu["401–600"]
    assert steps["›"] == menu["801–1,000"]
    assert steps["»"] == menu[f"1,401–{PAGING_ROWS:,}"]

    # And every one of them lands on the table card (19J.8).
    for href in list(menu.values()) + list(steps.values()):
        assert href.endswith("#reviewers-table-card"), href


def test_a_page_turn_from_the_menu_reaches_that_page(
    client: TestClient, db: Session
) -> None:
    """One move to anywhere — the item's whole reason.

    Follows the menu's own href rather than a URL the test builds, so
    it fails if the link is wrong rather than only if the route is.
    """
    body = _reviewers_page(client, db, code="cluster-6", rows=PAGING_ROWS)
    cluster = _clusters(body)[0]

    href = dict(
        (label, url)
        for url, label in re.findall(
            r'<a class="table-pager-menu-item"\s+href="([^"]+)">([^<]+)</a>',
            cluster,
        )
    )["1,201–1,400"]

    landed = client.get(href).text
    table = landed[landed.index('id="reviewers-table"') :]
    assert "Reviewer 01200" in table
    assert "Reviewer 01399" in table
    assert "Reviewer 01199" not in table

    # The menu now says where you are, which is what let the strip's
    # bold current cell retire.
    assert "<summary>1,201–1,400</summary>" in landed


def test_every_paging_template_carries_the_cluster_in_both_places() -> None:
    """The rename guard, across all seven pages.

    Two includes and one toolbar per template. Checked at source level
    rather than by seeding seven rosters: Relationships and Observers
    need a populated session to render a table at all, and what this
    guards — a template that quietly lost one of its two copies — is a
    fact about the file.
    """
    root = Path("app/web/templates/operator")
    for name in TEMPLATES:
        markup = (root / name).read_text(encoding="utf-8", errors="replace")
        assert markup.count("_pager_cluster.html") == 2, name
        assert "_preview_pager.html" not in markup, (
            f"{name} still includes the retired range strip"
        )
        assert markup.count('<div class="table-card-toolbar">') == 1, name
        assert (
            'cluster_extra_class = "table-pager-cluster-bottom"' in markup
        ), name
        # The toolbar opens inside the anchored card, so a page turn
        # lands showing the cluster (19J.8).
        assert markup.index('id="{{ pager_anchor }}"') < markup.index(
            '<div class="table-card-toolbar">'
        ), name
