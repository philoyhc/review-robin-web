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

import datetime as _dt

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Relationship,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)

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


def _with_a_response(db: Session, rs: ReviewSession) -> None:
    """One saved response, which is what flips `delete_discards_responses`
    on the Reviewees page. Mirrors `test_setup_bulk_delete_routes._with_responses`."""
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == rs.id)
    ).scalars().first()
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == rs.id)
    ).scalars().first()
    instrument = Instrument(session_id=rs.id, name="I", order=0)
    db.add(instrument)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="f0",
        label="F0",
        _inline_data_type="Integer",
        _inline_response_type="Likert5",
        order=0,
    )
    db.add(field)
    assignment = Assignment(
        session_id=rs.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
        created_by_mode="rule_based",
    )
    db.add(assignment)
    db.flush()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=field.id,
            value="1",
            saved_at=_dt.datetime(2026, 9, 9, tzinfo=_dt.timezone.utc),
            version=1,
        )
    )
    db.commit()


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
    """`.operator-actions-card` rules with no markup left to match them.
    Dead CSS in a 5,000-line inline stylesheet is not inert: it is a
    reader's evidence that a layout still exists.

    Five went when the roster pages left. The last two went at 19P.5
    rung 1 with Assignments' filter strip — the card holds no `<form>`
    and no `.filter-row` now, so `form { margin: 0 }` and the
    `flex: 4` on `label.filter-search` matched nothing. The scope is
    empty; rung 2 deletes the card and the heading with it.
    """
    base = (TEMPLATES.parent / "base.html").read_text()
    for gone in (
        ".operator-actions-card .filter-confirm {",
        ".operator-actions-card .operator-actions-main.is-locked {",
        ".operator-actions-card .operator-actions-divider {",
        ".operator-actions-card .operator-actions-buttons {",
        ".operator-actions-card form { margin: 0; }",
        ".operator-actions-card .filter-row > label.filter-search",
    ):
        assert gone not in base, gone


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


def test_the_delete_sentence_names_what_goes_per_page(
    client: TestClient, db: Session
) -> None:
    """The sentence names what the tick agrees to, and the two pages do
    not agree on what that is: a relationship carries neither flag
    (`_setup_relationships.py` passes `delete_discards_*` as `False`
    outright), so its sentence is the bare one, while a reviewee with
    responses gets the longest of the three.

    Read from the **rendered builder**, because the branch is evaluated
    server-side and baked into the JS literal — the template only shows
    that a branch exists, which is what an earlier version of this test
    asserted while its docstring claimed otherwise.
    """
    rs = _make_session(client, db, "ex-sent")
    _seed(db, rs.id, "reviewees")
    _seed(db, rs.id, "relationships")

    rev = _builder(client.get(_base(rs.id, "reviewees")).text, "reviewees")
    rel = _builder(client.get(_base(rs.id, "relationships")).text, "relationships")

    # No assignments and no responses yet: both pages say the bare thing.
    assert '"Yes, delete these"' in rev, rev[:300]
    assert '"Yes, delete these"' in rel
    assert "reviewer responses" not in rel, (
        "Relationships cannot discard responses and must not say it does"
    )

    # Give the reviewee a response, and only its sentence grows.
    _with_a_response(db, rs)
    rev = _builder(client.get(_base(rs.id, "reviewees")).text, "reviewees")
    rel = _builder(client.get(_base(rs.id, "relationships")).text, "relationships")
    assert (
        '"Yes, delete these and their associated assignments and reviewer responses"'
        in rev
    ), rev[:400]
    assert '"Yes, delete these"' in rel, "Relationships' sentence moved with it"


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


@pytest.mark.parametrize("page,noun", PAGES)
def test_every_data_row_carries_the_status_the_panel_reads(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """`rows()` selects `tr[data-status]`. That attribute is doing two
    jobs, and losing it breaks both silently:

      - it is how the expander tells a DATA row from the editor row and
        from the panel it injects itself, so without it `rows()` returns
        **nothing** — no panel, no selection, no row actions at all;
      - it is what `statusActions()` reads to decide whether the
        selection admits `Inactivate`, `Activate` or both.

    A mutation deleting it passed the entire suite. Nothing server-side
    asserted the panel's only input, because every other guard here reads
    the builder — which still ships perfectly while having no rows to
    build against.
    """
    rs = _make_session(client, db, f"ex-st-{page[:4]}")
    ids = _seed(db, rs.id, page)
    html = _markup(client.get(_base(rs.id, page)).text)

    for rid in ids:
        row_at = html.index(f'id="{noun}-row-{rid}"')
        row = html[row_at : html.index(">", row_at)]
        assert 'data-status="active"' in row, (rid, row)

    assert html.count("data-status=") == len(ids), (
        "a row the expander cannot see, or one it should not"
    )


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_add_row_is_bracketed_too(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """Both rows carry the bracket, and both need it: the bar reads as
    attached to the row above it only because that row is highlighted.

    Guarded separately from the edited row because the two carry the
    **identical class string**, so a mutation aimed at one lands on
    whichever comes first in the file — which is how this gap was found.
    The edited-row test above looks the row up by id; this one by the
    add row's own anchor.
    """
    rs = _make_session(client, db, f"ex-ab-{page[:4]}")
    _seed(db, rs.id, page)
    html = _markup(client.get(_base(rs.id, page) + "?add=1").text)

    row = re.search(rf'<tr class="{noun}-edit-row[^"]*"[^>]*id="{page}-row-editor"', html)
    assert row, "the add row is not marked as the editor"
    assert "session-row-selected" in row.group(0), "the add row is not bracketed"


@pytest.mark.parametrize("page,noun", PAGES)
def test_edit_is_gated_on_a_selection_of_exactly_one(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """Arity. `Edit` opens one row's editor, so a selection of two has
    nothing for it to open — the panel renders it disabled.

    **This is a source assertion, and weaker than it looks.** The gate is
    JS evaluated against a live selection, so what the suite can see is
    that the expression ships, not that it works. Replacing it with
    `var editable = true;` passed every other test here. The behaviour is
    measured in Chromium instead: at two rows the panel renders
    `Edit(off)`, at one `Edit` with that row's id.
    """
    rs = _make_session(client, db, f"ex-ar-{page[:4]}")
    _seed(db, rs.id, page)
    builder = _builder(client.get(_base(rs.id, page)).text, page)

    assert "var editable = sel.length === 1;" in builder
    # The disabled branch itself, as the template writes it: a plain JS
    # literal, so plain quotes.
    assert """' disabled aria-disabled="true"'""" in builder, (
        "the disabled branch of the arity gate is gone"
    )


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_bars_colspan_is_computed_not_written(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """A source assertion, deliberately, because the rendered value
    cannot distinguish the two.

    `edit_col_count` is **always its maximum**: the bar only renders in
    edit mode, and edit mode forces every optional column on so the
    operator can type into a tag that is empty today. Measured — the list
    view renders 6 columns on both pages, against 9 in edit mode on
    Reviewees and 8 on Relationships — Relationships has no profile-link
    column. So hardcoding the number is behaviour-preserving right now,
    and a mutation replacing the expression with a literal passes every
    behavioural test there is, including the one above that compares
    colspan to the row's cells.

    The reason to compute it is therefore not today's rendering but the
    first time a column is gated differently, at which point a written
    number goes quietly wrong. That claim is about the source, so it is
    asserted against the source.
    """
    source = (TEMPLATES / f"session_{page}.html").read_text()
    assert "{% set edit_col_count = 3" in source
    assert "+ (1 if show_tag[1] else 0)" in source
    assert '<td colspan="{{ col_count }}">' in source, "the bar hardcodes its span"


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_status_actions_are_chosen_by_the_selection_not_always_both(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """`Inactivate` acts on active rows and `Activate` on inactive ones,
    so a selection that is all one status admits exactly one of them.
    Rendering both offers a control that would no-op on every row.

    Another source assertion, and the same caveat as the arity gate:
    replacing the two conditions with unconditional pushes passed every
    other test here. Measured in Chromium instead — an inactive row alone
    offers `Edit / Activate / Delete`, one of each offers all four.
    """
    rs = _make_session(client, db, f"ex-sa-{page[:4]}")
    _seed(db, rs.id, page)
    script = _script(client.get(_base(rs.id, page)).text, page)

    assert 'if (hasActive) out.push("Inactivate");' in script
    assert 'if (hasInactive) out.push("Activate");' in script
    assert 'row.dataset.status === "active"' in script, (
        "the labels are chosen from something other than the row's status"
    )


@pytest.mark.parametrize("page,noun", PAGES)
def test_select_all_keeps_its_indeterminate_state(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """A partial selection reads as a dash rather than an empty box
    claiming nothing is selected. The retired card script never set this;
    it arrived with the expander, which is the only owner of selection
    state now.

    Source assertion — `indeterminate` is a DOM property, never an
    attribute, so it cannot appear in a response at all. Measured in
    Chromium: true on every partial selection, false at 8 of 8.
    """
    rs = _make_session(client, db, f"ex-in-{page[:4]}")
    _seed(db, rs.id, page)
    script = _script(client.get(_base(rs.id, page)).text, page)

    assert "selectAll.indeterminate = (n > 0 && n < all.length);" in script
    assert "selectAll.checked = (n > 0 && n === all.length);" in script


@pytest.mark.parametrize("page,noun", PAGES)
def test_sorting_takes_the_panel_out_and_puts_it_back(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """Sorting reorders `tbody`'s children. The panel carries no sort
    cells, so it compares null and sorts to the bottom — away from the
    rows it belongs to — and being present when `base.html` stamps
    `rrwOriginalIndex` would shift every index after it, corrupting the
    unsorted restore order too.

    **The mechanism is measured, not assumed.** With this binding removed
    and one row selected, a header click moved the panel from index 2 of
    9 to index 8 of 9 — last child, stranded. With it, the panel stays at
    index 2, still anchored to its row.

    Capture phase matters: the header's own inline `onclick` does the
    sorting, so this has to run first to take the panel out before the
    reorder sees it.
    """
    rs = _make_session(client, db, f"ex-so-{page[:4]}")
    _seed(db, rs.id, page)
    body = client.get(_base(rs.id, page)).text
    script = _script(body, page)

    assert 'if (!event.target.closest(".rrw-sort-btn")) return;' in script
    assert "}, true);" in script, "the sort binding is not capture-phase"
    # Vacuity guard: a page that stopped shipping sortable headers would
    # make the binding unreachable and this test meaningless.
    assert "rrw-sort-btn" in _markup(body), "the table is no longer sortable"


@pytest.mark.parametrize("page,noun", PAGES)
def test_a_selection_restored_by_the_server_gets_its_panel(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """The bulk routes redirect through `_redirect_keeping_selection`,
    which carries the acted-on ids as `?selected=` and the server
    re-checks those boxes. Without the bootstrap the restored rows would
    have neither rails nor a panel until the operator toggled something.

    The server half is asserted here — the boxes really do come back
    checked, which is what the bootstrap has to find. The JS half is a
    source assertion, with Chromium confirming the result: two ids in the
    query give two checked boxes, two rails, a panel after the second
    row, and "2 of 8 selected".
    """
    rs = _make_session(client, db, f"ex-rs-{page[:4]}")
    ids = _seed(db, rs.id, page)
    url = f"{_base(rs.id, page)}?selected={ids[0]}&selected={ids[2]}"
    body = client.get(url).text

    assert _markup(body).count("checked") >= 2, (
        "the server did not restore the selection the bootstrap reads"
    )
    script = _script(body, page)
    assert "if (box && box.checked) tickOrder.push(row.id);" in script
    # The bootstrap's own `render()` is the LAST statement of the IIFE —
    # `_script()` slices to `</script>`, so the closing `})();` follows
    # it. Matched as the tail pair rather than by `endswith("render();")`,
    # which the closer defeats.
    assert script.rstrip().endswith("render();\n      })();"), script[-120:]


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_add_rows_first_field_takes_the_caret(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """`Add new` navigates to a fragment, and a fragment navigation moves
    focus to its target — which beats the `autofocus` attribute. So the
    caret is set in script, against `.row-editor-first-field`, and the
    marker has to be on the field the operator should start in.

    On the **add** row only: an Edit arrives with the row already filled,
    and stealing focus there fights an operator heading for a different
    cell. Measured in Chromium — the caret lands in `name` on Reviewees
    and `reviewer_pick` on Relationships.
    """
    rs = _make_session(client, db, f"ex-cf-{page[:4]}")
    ids = _seed(db, rs.id, page)

    add = _markup(client.get(_base(rs.id, page) + "?add=1").text)
    assert add.count("row-editor-first-field") == 1, "no caret marker, or two"
    marker_at = add.index("row-editor-first-field")
    field = add[add.rindex("<input", 0, marker_at) : add.index(">", marker_at) + 1]
    expected = "name" if page == "reviewees" else "reviewer_pick"
    assert f'name="{expected}"' in field, field

    edit = _markup(client.get(_base(rs.id, page) + f"?edit_id={ids[0]}").text)
    assert "row-editor-first-field" not in edit, (
        "an Edit steals focus from the cell the operator was heading for"
    )


# ── Three claims both precedents guard, transcribed ───────────────────
#
# Added after a cold read found them missing. The item's whole stated
# risk is drift from the precedent, and each of these is guarded on
# Reviewers (`test_reviewers_roster_card_scaffold.py`) and Observers
# (`test_observers_expander.py`) but had no counterpart here — which the
# rung's own mutation set did not think to probe either.


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_anchor_prunes_on_untick_and_rebuilds_on_select_all(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """The panel anchors after the most recently ticked row that is STILL
    selected, with DOM order as the fallback — the rule 19L settled for
    the lobby (`sessions_list.html:585`).

    Both halves are load-bearing. A single remembered id clears on any
    untick and the panel jumps back up the table; and without the prune,
    a row unticked and re-ticked leaves a stale entry that anchors the
    panel at that row instead of the last one. Select-all rebuilds the
    order wholesale rather than appending.

    Source assertions — the order is JS state with no server-side
    counterpart. Measured in Chromium: with rows 1 and 3 ticked the panel
    renders after row 3, not row 8.
    """
    rs = _make_session(client, db, f"ex-an-{page[:4]}")
    _seed(db, rs.id, page)
    script = _script(client.get(_base(rs.id, page)).text, page)

    assert "tickOrder = tickOrder.filter(function (id) { return id !== row.id; });" in script, (
        "the prune is gone; a re-ticked row would anchor the panel"
    )
    assert "if (event.target.checked) tickOrder.push(row.id);" in script
    assert "(currentAnchor() || sel[sel.length - 1])" in script, (
        "the anchor collapsed to DOM order, losing the tick-order rule"
    )
    assert '.insertAdjacentElement("afterend", panel)' in script
    assert "tickOrder = selectAll.checked" in script, (
        "select-all appends rather than rebuilding the order"
    )


@pytest.mark.parametrize("page,noun", PAGES)
def test_edit_navigates_to_the_row_it_is_about_to_edit(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """`Edit` is a client-side GET, not a form post, so it carries its own
    landing anchor — and the anchor is the row's id, not the editor
    anchor `Add new` uses. With the editor card gone there is nothing
    else for it to name.

    Measured in Chromium: the click goes to
    `?edit_id=2#reviewee-row-2` and the edit row renders.
    """
    rs = _make_session(client, db, f"ex-ed-{page[:4]}")
    _seed(db, rs.id, page)
    script = _script(client.get(_base(rs.id, page)).text, page)

    assert 'BULK_BASE + "?edit_id=" +' in script
    assert f'"#{noun}-row-" + encodeURIComponent(editId)' in script, (
        "Edit lands somewhere other than the row it opens"
    )
    assert f"{page}-row-editor" not in script, (
        "Edit names the add row's anchor, which is not the row it opens"
    )


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_panel_stays_a_pill_free_zone(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """`spec/ui_elements.md` `.session-row-selected`: the panel's fill
    resolves to `--status-info-bg`'s primitive, so a `.pill-count`
    rendered inside it reopens the collision one storey down — both
    tokens are `--blue-pale` light and `--blue-abyss` dark, which makes
    the pill invisible.

    The count the card rendered as a pill is bare text here, as the lobby
    renders the same fact. Both templates carry a comment citing that
    spec; this is what holds them to it.
    """
    rs = _make_session(client, db, f"ex-pf-{page[:4]}")
    _seed(db, rs.id, page)
    builder = _builder(client.get(_base(rs.id, page)).text, page)

    assert "pill" not in builder, f"a pill came back into the panel: {builder[:400]}"
    assert '<span class="row-expander-count"><strong>' in builder, (
        "the count is not rendered as bare text"
    )
