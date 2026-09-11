"""The page-turn cluster renders, in both places, and goes nowhere yet.

Segment 19J Item 9, rung 1 — the scaffold.

The strip's reach is a constant two pages per click whatever the roster
size, so crossing a long roster costs a number of clicks linear in its
length: 5 to row 2,400 of 5,861, 50 to the middle of 40,000. The cluster
— ``«‹ [range ▾] ›»`` — reaches any page without stepping.

This rung lands it inert, beside the strip that still works. So these
assertions are about **presence, placement and state**, not behaviour:
that it renders twice, that it renders only where the strip cannot show
every range, that the menu holds every range rather than the strip's
five, that the ends are inactive at the ends — and that nothing in it
navigates.

``test_the_scaffold_navigates_nowhere`` is the one test here written to
be **deleted** by rung 2. It pins the boundary between the two rungs so
that wiring the cluster is a deliberate act rather than something that
leaks in sideways.

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

#: Seven pages: the strip shows five links plus Last, so page 6 is
#: unreachable and the cluster earns its place. Six pages would not —
#: every range is on screen and one click already reaches any of them.
PAGING_ROWS = 7 * PAGE_SIZE + 1

#: Three pages. The strip shows all of them, so no cluster.
SHORT_ROWS = 556

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
    client: TestClient, db: Session, *, code: str, rows: int
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


def test_the_cluster_renders_twice_where_the_strip_cannot_reach(
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
    assert body.index('<div class="table-pager-cluster') < body.index(
        '<nav class="table-pager'
    )


def test_no_cluster_when_the_strip_already_shows_every_range(
    client: TestClient, db: Session
) -> None:
    """A control that is a second way to do what one click does is
    noise — the same argument that makes ``build_pager`` return ``None``
    for a single page."""
    body = _reviewers_page(client, db, code="cluster-2", rows=SHORT_ROWS)

    assert _clusters(body) == []
    # And the absence is about elision, not about the pager: the strip
    # itself is right there. Without this the test would pass on a page
    # that had lost its pager entirely.
    assert '<nav class="table-pager' in body


def test_the_menu_holds_every_range_not_the_strip_s_window(
    client: TestClient, db: Session
) -> None:
    """The whole point: the strip's five against the table's seven."""
    body = _reviewers_page(client, db, code="cluster-3", rows=PAGING_ROWS)
    cluster = _clusters(body)[0]

    entries = re.findall(
        r'<span class="table-pager-menu-item[^"]*"[^>]*>([^<]+)</span>',
        cluster,
    )
    assert len(entries) == 8, entries
    assert entries[0] == "1–200"
    assert entries[-1] == f"1,401–{PAGING_ROWS:,}"

    # Strictly more than the strip offers, which is the reason to exist.
    strip = body[body.index('<nav class="table-pager') :]
    strip = strip[: strip.index("</nav>")]
    assert len(re.findall(r"table-pager-link", strip)) < len(entries)

    # The summary names where you are, so the menu doubles as the
    # position indicator and the strip's bold cell can retire.
    assert "<summary>1–200</summary>" in cluster
    assert cluster.count('aria-current="page"') == 1


def test_the_ends_are_inactive_at_the_ends(
    client: TestClient, db: Session
) -> None:
    """In place, never absent: absent buttons would shift the other
    cells sideways as the operator pages."""
    body = _reviewers_page(client, db, code="cluster-4", rows=PAGING_ROWS)
    cluster = _clusters(body)[0]

    steps = re.findall(
        r'<span class="btn-icon table-pager-step([^"]*)"[^>]*>([^<]+)</span>',
        cluster,
    )
    assert [glyph for _, glyph in steps] == ["«", "‹", "›", "»"]

    state = dict((glyph, cls) for cls, glyph in steps)
    # On the first page, back and first cannot go anywhere.
    assert "is-inactive" in state["«"] and "is-inactive" in state["‹"]
    assert "is-inactive" not in state["›"] and "is-inactive" not in state["»"]
    assert cluster.count('aria-disabled="true"') == 2


def test_the_scaffold_navigates_nowhere(
    client: TestClient, db: Session
) -> None:
    """**Rung 2 deletes this test.**

    It pins the rung boundary: the scaffold is for looking at, and
    wiring it should be a deliberate act in its own PR rather than
    something that arrives sideways. Meanwhile the 19J.5 strip below is
    still the working pager, which is why an inert cluster costs the
    operator nothing.
    """
    body = _reviewers_page(client, db, code="cluster-5", rows=PAGING_ROWS)

    for cluster in _clusters(body):
        assert "href" not in cluster
        assert "<a " not in cluster

    # The strip still works, so the page is not without a pager.
    assert re.search(r'<a class="table-pager-link"\s+href="[^"]+"', body)


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
        assert markup.count('<div class="table-card-toolbar">') == 1, name
        assert (
            'cluster_extra_class = "table-pager-cluster-bottom"' in markup
        ), name
        # The toolbar opens inside the anchored card, so a page turn
        # lands showing the cluster (19J.8).
        assert markup.index('id="{{ pager_anchor }}"') < markup.index(
            '<div class="table-card-toolbar">'
        ), name
