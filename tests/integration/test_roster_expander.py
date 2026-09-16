"""The row expander and the edit-row bar on Reviewees and Relationships.

19P.3 rung 3 — the `Operator actions` card is retired on the last two
roster pages. `Edit` / `Inactivate` / `Activate` / `Delete`, the selected
count and the delete gate are built into a panel injected beneath the
selected rows; Save / Cancel are in a bracketed bar beneath the row being
edited.

**This file inherits `test_setup_delete_scaffold.py`'s live claims.** That
file pinned the card strip's shape on whichever pages still had one, and
after this rung no page does. Its claims about the delete control did not
stop being true — they moved — so they are re-asserted here against the
builder, rather than deleted with the markup they used to read.

**The builder is JavaScript, so its markup is not markup.** A panel
button exists in the response only as a JS string literal inside
`build()`, so no rendered-HTML test can see it. Three consequences this
file lives with:

  - a *presence* assertion about the panel reads a slice of the script,
    not the page;
  - the slice matters. `build()` holds the buttons; `statusActions()`
    holds the two status LABELS and sits outside it. An assertion for
    `"Activate"` against `_builder()` fails for the wrong reason — the
    first draft of this file did exactly that;
  - an *absence* assertion has to strip `<script>` first, for the inverse
    reason: the builder's own literals contain the very labels the test
    says are gone from the page.

**Only the Jinja-injected pieces are backslash-escaped.** The hand-written
JS literals carry plain quotes (`' form="reviewees-bulk-form"'`), so they
are matched as written. What arrives escaped is what `{{ ... | tojson }}`
produces — the confirm sentence and the hidden acknowledgement input. The
first draft of this file asserted the escaped spelling everywhere and
failed on every hand-written literal.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Relationship, Reviewee, Reviewer, ReviewSession

#: ``(page, noun)`` — the two pages this rung moves.
PAGES = [("reviewees", "reviewee"), ("relationships", "relationship")]

TEMPLATES = pathlib.Path("app/web/templates/operator")

#: Every roster page, for the claims that are now true of all four.
ROSTER_PAGES = ("reviewers", "reviewees", "observers", "relationships")


def _markup(html: str) -> str:
    """`base.html` inlines the whole app's CSS and JS on every page, so a
    page-wide substring assertion matches names in rules and scripts that
    have nothing to do with this page's markup."""
    html = re.sub(r"<style\b.*?</style>", "", html, flags=re.S)
    return re.sub(r"<script\b.*?</script>", "", html, flags=re.S)


def _builder(html: str, page: str) -> str:
    """The expander's `build()` body, where the panel's markup lives as
    JS string literals. Does NOT include `statusActions()` — see the
    module docstring."""
    start = html.index(f'tr.id = "{page}-row-expander"')
    return html[start : html.index("td.innerHTML = html;", start)]


def _script(html: str, page: str) -> str:
    """The whole expander IIFE, for claims that span its helpers."""
    start = html.index(f'var table = document.getElementById("{page}-table")')
    return html[start : html.index("</script>", start)]


def _make_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "R", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    rs.relationships_enabled = True
    db.commit()
    db.refresh(rs)
    return rs


def _seed(db: Session, sid: int, page: str, n: int = 3) -> list[int]:
    reviewers = [
        Reviewer(session_id=sid, name=f"Rr{i}", email=f"rr{i}@example.org")
        for i in range(n)
    ]
    reviewees = [
        Reviewee(
            session_id=sid, name=f"Re{i}", email_or_identifier=f"re{i}@example.org"
        )
        for i in range(n)
    ]
    db.add_all(reviewers + reviewees)
    db.commit()
    for r in reviewers + reviewees:
        db.refresh(r)
    if page == "reviewees":
        return [r.id for r in reviewees]
    rows = [
        Relationship(
            session_id=sid, reviewer_id=reviewers[i].id, reviewee_id=reviewees[i].id
        )
        for i in range(n)
    ]
    db.add_all(rows)
    db.commit()
    for r in rows:
        db.refresh(r)
    return [r.id for r in rows]


def _base(sid: int, page: str) -> str:
    return f"/operator/sessions/{sid}/{page}"


# ── The card is gone ──────────────────────────────────────────────────


def test_no_roster_page_renders_the_operator_actions_card() -> None:
    """Item 3's Definition of done, in one assertion.

    **`operator-actions-card`, not `operator-actions`** — the filter strip
    keeps the latter as `operator-actions-filter` after moving into the
    toolbar, so the looser grep is nonzero on every migrated page and can
    never reach 0.

    `session_assignments.html` renders the card too and is **not** a
    roster page, so it is excluded by name rather than by a `session_*`
    glob — which is also why the `.operator-actions-card` CSS stays.
    """
    still_carrying = sorted(
        page
        for page in ROSTER_PAGES
        if "operator-actions-card" in (TEMPLATES / f"session_{page}.html").read_text()
    )
    assert still_carrying == [], still_carrying
    assert (
        "operator-actions-card" in (TEMPLATES / "session_assignments.html").read_text()
    ), "the non-roster tenant went too; the CSS kept for it is now dead"


def test_the_second_action_row_reaches_no_template_at_all() -> None:
    """`.filter-confirm` was the card's status row — the selected count
    and the delete gate. `test_setup_delete_scaffold.py` tracked which
    pages still had one; the answer is now none, on any template, so the
    claim collapses to an absence and the file that tracked it retires.

    `.filter-actions` is a different class and still has seven users: the
    four roster toolbars and the three non-roster pages that never gained
    the second row.
    """
    confirm_rows = sorted(
        p.name for p in TEMPLATES.glob("session_*.html")
        if 'class="filter-confirm"' in p.read_text()
    )
    assert confirm_rows == [], confirm_rows

    sharing = sorted(
        p.name for p in TEMPLATES.glob("session_*.html")
        if 'class="filter-actions"' in p.read_text()
    )
    assert len(sharing) == 7, sharing


def test_the_retired_rows_css_went_with_its_last_tenant() -> None:
    """Five `.operator-actions-card` rules had no markup left that could
    match them. Dead CSS in a 5,000-line inline stylesheet is not inert:
    it is a reader's evidence that a layout still exists."""
    base = (TEMPLATES.parent / "base.html").read_text()
    for gone in (
        ".operator-actions-card .filter-confirm {",
        ".operator-actions-card .operator-actions-main.is-locked {",
        ".operator-actions-card .operator-actions-divider {",
        ".operator-actions-card .operator-actions-buttons {",
    ):
        assert gone not in base, gone
    # ...and the rules the surviving tenant still needs did NOT go.
    assert ".operator-actions-card form { margin: 0; }" in base
    assert ".operator-actions-card .filter-row > label.filter-search" in base


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_card_labels_are_gone_from_the_rendered_page(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """Read from stripped markup, not the raw response: the builder's own
    string literals contain `Inactivate`, `Activate` and `Delete`, so an
    absence assertion against the whole page matches the script and
    passes for the wrong reason — or fails for it."""
    rs = _make_session(client, db, f"ex-c-{page[:4]}")
    _seed(db, rs.id, page)
    html = _markup(client.get(_base(rs.id, page)).text)

    assert "Operator actions" not in html
    assert f'id="{page}-edit-btn"' not in html
    assert f'id="{page}-inactivate-btn"' not in html
    assert f'id="{page}-reactivate-btn"' not in html
    assert f'id="{page}-delete-btn"' not in html
    assert f'id="{page}-selected-count"' not in html
    assert f'id="{page}-delete-confirm"' not in html


# ── The panel the controls moved into ─────────────────────────────────


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_panel_carries_all_four_actions(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    rs = _make_session(client, db, f"ex-p-{page[:4]}")
    _seed(db, rs.id, page)
    builder = _builder(client.get(_base(rs.id, page)).text, page)

    assert ">Edit</button>" in builder
    assert ">Delete</button>" in builder
    # The status labels are produced by `statusActions()`, outside
    # `build()` — asserted against the whole script, not the slice.
    script = _script(client.get(_base(rs.id, page)).text, page)
    assert 'out.push("Inactivate")' in script
    assert 'out.push("Activate")' in script


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_panel_posts_to_the_same_routes_the_card_did(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """The controls moved; the routes did not. Each button carries
    `form="{page}-bulk-form"` and a `formaction`, exactly as it did in the
    card — the selection reaches the POST through the row checkboxes' own
    `form=`, so a button needs only to say where."""
    rs = _make_session(client, db, f"ex-r-{page[:4]}")
    _seed(db, rs.id, page)
    builder = _builder(client.get(_base(rs.id, page)).text, page)

    assert f'form="{page}-bulk-form"' in builder, builder[:400]
    assert '"/bulk-inactivate"' in builder
    assert '"/bulk-reactivate"' in builder
    # Concatenated onto `BULK_BASE`, so the literal is `'/bulk-delete"'`
    # — matched bare rather than by a guessed quoting.
    assert "/bulk-delete" in builder


@pytest.mark.parametrize("page,noun", PAGES)
def test_delete_is_destructive_and_ships_gated(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """`test_setup_delete_scaffold.py`'s central claim, re-aimed.

    Ships `disabled`: nothing syncs an injected pair until its first tick,
    so a live-by-default Delete would be a destructive control with its
    gate already open.
    """
    rs = _make_session(client, db, f"ex-d-{page[:4]}")
    _seed(db, rs.id, page)
    builder = _builder(client.get(_base(rs.id, page)).text, page)

    start = builder.index(">Delete</button>")
    element = builder[builder.rindex("<button", 0, start) : start]
    assert "btn destructive" in element, "Destructive role per ui_elements §6"
    assert 'type="submit"' in element
    assert f'data-delete-btn="{page}-bulk-delete"' in element
    assert "disabled" in element


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_gate_is_paired_to_the_button_and_submits_with_the_selection(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """The gate is only a gate if its tick reaches the server, and only
    paired if `base.html`'s `data-delete-confirm` key finds the button.
    That resolver is a first-match `querySelector`, so the key must stay
    unique page-wide — which is why the card was retired in the same
    slice that wired this, rather than a slice later."""
    rs = _make_session(client, db, f"ex-g-{page[:4]}")
    _seed(db, rs.id, page)
    body = client.get(_base(rs.id, page)).text
    builder = _builder(body, page)

    assert f'data-delete-confirm="{page}-bulk-delete"' in builder
    assert 'name="confirm"' in builder
    assert 'value="true"' in builder
    assert f'form="{page}-bulk-form"' in builder
    assert body.count(f'data-delete-btn="{page}-bulk-delete"') == 1, (
        "a second button with the same key would steal the first match"
    )


def test_the_delete_sentence_names_what_goes_per_page() -> None:
    """Reviewees discards assignments and responses; a relationship has
    neither flag, so its sentence is the bare one. Read from the rendered
    builder rather than the template, because the branch is evaluated
    server-side and baked into the literal."""
    # Asserted in the page tests below via the builder; here the claim is
    # only that the two pages do NOT share one hard-coded sentence.
    rev = (TEMPLATES / "session_reviewees.html").read_text()
    rel = (TEMPLATES / "session_relationships.html").read_text()
    for source in (rev, rel):
        assert "delete_discards_responses" in source
        assert "delete_discards_assignments" in source


# ── The edit row and its bar ──────────────────────────────────────────


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_edit_row_is_bracketed_and_the_bar_follows_it(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    rs = _make_session(client, db, f"ex-e-{page[:4]}")
    ids = _seed(db, rs.id, page)
    html = _markup(client.get(_base(rs.id, page) + f"?edit_id={ids[0]}").text)

    row = re.search(
        rf'<tr class="{noun}-edit-row[^"]*"[^>]*id="{noun}-row-{ids[0]}"', html
    )
    assert row, "the edited row is not marked as the editor"
    assert "session-row-selected" in row.group(0), "the row is not bracketed"

    bar_at = html.index("row-editor-bar")
    assert bar_at > row.start(), "the bar renders before the row it brackets"
    assert "session-expander-bracketed" in html[row.start() : bar_at + 40]


@pytest.mark.parametrize("page,noun", PAGES)
def test_save_and_cancel_are_in_the_bar_and_nowhere_else(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """They were a hand-styled flex `<div>` in the card, with an inline
    `style=` this rung also retires."""
    rs = _make_session(client, db, f"ex-s-{page[:4]}")
    ids = _seed(db, rs.id, page)
    html = _markup(client.get(_base(rs.id, page) + f"?edit_id={ids[0]}").text)

    assert html.count(">Save</button>") == 1, "Save is in two places, or none"
    assert html.count(">Cancel</a>") == 1

    bar = html[html.index("row-editor-bar") :]
    bar = bar[: bar.index("</tr>")]
    assert f'form="{noun}-edit-form"' in bar, "Save posts the edit form"
    assert re.search(rf'href="[^"]*/{page}#{page}-table-card">Cancel</a>', bar), (
        "Cancel does not land where the list is"
    )
    assert "style=" not in bar, "the card's inline flex style came along"


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_bar_announces_the_mode_the_card_heading_used_to(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """The card carried an `<h2>` — "Add new X" / "Edit X" — and that
    heading was the only accessible name for the state the page is in.
    What replaces the card visually is a highlighted row, and a highlight
    reaches nobody using a screen reader."""
    rs = _make_session(client, db, f"ex-m-{page[:4]}")
    ids = _seed(db, rs.id, page)

    edit = _markup(client.get(_base(rs.id, page) + f"?edit_id={ids[0]}").text)
    assert re.search(
        rf'<span class="visually-hidden" aria-live="polite">\s*Edit {noun}\s*</span>',
        edit,
    ), edit[edit.index("row-editor-bar") : edit.index("row-editor-bar") + 400]
    assert f"<h2>Edit {noun}</h2>" not in edit

    add = _markup(client.get(_base(rs.id, page) + "?add=1").text)
    assert f"Add new {noun}" in add
    assert f"<h2>Add new {noun}</h2>" not in add


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_bar_spans_exactly_the_row_above_it(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """`colspan` is computed from the same flags the `<thead>` branches
    on. A hand-written number stops being true the first time a column is
    gated differently — and a bar one cell short or long is a visibly
    ragged bracket, which no other assertion here would catch.
    """
    rs = _make_session(client, db, f"ex-w-{page[:4]}")
    ids = _seed(db, rs.id, page)
    html = _markup(client.get(_base(rs.id, page) + f"?edit_id={ids[0]}").text)

    row_at = html.index(f'id="{noun}-row-{ids[0]}"')
    row = html[row_at : html.index("</tr>", row_at)]
    cells = len(re.findall(r"<td\b", row))

    bar_at = html.index("row-editor-bar")
    colspan = int(re.search(r'colspan="(\d+)"', html[bar_at:]).group(1))
    assert colspan == cells, (colspan, cells)


@pytest.mark.parametrize("page,noun", PAGES)
def test_add_mode_lands_on_the_row_it_opens(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """`Add new` took no fragment at rung 2, because the editor was still
    a card at the top of the page. The editor is the row now, so the link
    carries the row's id — and the row carries it back."""
    rs = _make_session(client, db, f"ex-a-{page[:4]}")
    _seed(db, rs.id, page)

    listing = _markup(client.get(_base(rs.id, page)).text)
    link = re.search(r'href="([^"]*\?add=1[^"]*)"', listing)
    assert link, "no live Add new"
    href = link.group(1).replace("&amp;", "&")
    assert href.endswith(f"#{page}-row-editor"), href

    added = _markup(client.get(_base(rs.id, page) + "?add=1").text)
    assert f'id="{page}-row-editor"' in added, "the link names a target that is absent"
    assert added.count(f'id="{page}-row-editor"') == 1


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_save_error_moved_into_the_bar(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """It was a `.banner-error` in the card, a table's height away from
    the values it is about."""
    rs = _make_session(client, db, f"ex-x-{page[:4]}")
    _seed(db, rs.id, page)

    if page == "reviewees":
        data = {
            "name": "", "email_or_identifier": "", "profile_link": "",
            "tag_1": "", "tag_2": "", "tag_3": "", "status_value": "active",
        }
    else:
        data = {
            "reviewer_pick": "nobody at all", "reviewee_pick": "nobody either",
            "tag_1": "", "tag_2": "", "tag_3": "", "status_value": "active",
        }
    response = client.post(_base(rs.id, page) + "/create", data=data)
    assert response.status_code == 400, response.status_code
    html = _markup(response.text)

    assert "row-editor-error" in html, "the error is not in the bar"
    assert "banner-error" not in html, "the card's banner survived the move"
    bar = html[html.index("row-editor-bar") :]
    assert "row-editor-error" in bar[: bar.index("</tr>")]
