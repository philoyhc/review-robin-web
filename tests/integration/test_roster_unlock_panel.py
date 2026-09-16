"""The Unlock panel on Reviewees and Relationships.

19P.3 rung 4 — the roster card, its readouts, and a panel holding the
tag-labels editor, the `Danger Zone` and `Upload`.

**This file exists because the rung shipped without one.** Rung 4 landed
leaning on two pre-existing tests that happened to fail, and a mutation
pass then found **fifteen** survivors across twenty-four mutations — the
panel shipping open, `?unlocked=1` ignored, a labels save closing the
panel, both of Relationships' 400 paths shipping it closed, the
delete-all gate removed, the readouts deleted, the Lock control orphaned.
Almost every one of those is plain rendered markup a server-side test can
read. They survived because nothing looked.

**Both pages, parametrized**, for the reason 19P.3's other files give:
the item's whole risk is drift between two pages that should be
identical.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Relationship, Reviewee, Reviewer, ReviewSession

#: ``(page, noun, Noun)`` — the two pages this rung moves.
PAGES = [
    ("reviewees", "reviewee", "Reviewees"),
    ("relationships", "relationship", "Relationships"),
]


def _markup(body: str) -> str:
    """The page with `<style>` and `<script>` stripped.

    `base.html` inlines the whole app's CSS on every page and defines
    `.danger-zone` / `.bottom-grid` / `.card-columns` rules, so
    `"bottom-grid" not in body` is unfalsifiable — it fails on a page
    rendering no such element, because the RULE is always there. Every
    absence claim here reads this.
    """
    body = re.sub(r"<style\b.*?</style>", "", body, flags=re.S)
    return re.sub(r"<script\b.*?</script>", "", body, flags=re.S)


def _card(body: str, page: str) -> str:
    """The roster card's MARKUP only.

    Bounded by the preview table's card, which is the next thing on the
    page, and stripped of the toggle script — which lives inside this
    card and contains BOTH labels (`open ? "Unlock" : "Lock"`). Read with
    the script in, an assertion that the collapsed card reads "Unlock"
    passes on the open one too. Observers' file learned this the hard
    way; this one inherits the lesson rather than repeating it.
    """
    start = body.index('id="roster-card"')
    end = body.index(f'id="{page}-table-card"', start)
    return _markup(body[start:end])


def _toggle_button(card: str) -> str:
    """The toggle button's own text.

    Off the `<button>`, not the card: the card also carries a
    `<noscript>` twin of the control, so "Unlock" in the card is true
    with the BUTTON relabelled `Lock`.
    """
    m = re.search(r'<button[^>]*id="roster-unlock-btn"[^>]*>(.*?)</button>',
                  card, re.S)
    assert m, "no toggle button in the card"
    return m.group(1).strip()


def _panel_tag(card: str) -> str:
    """The panel's opening tag, where `hidden` does or does not sit."""
    m = re.search(r'<div class="unlock-panel"[^>]*>', card)
    assert m, "no Unlock panel in the card"
    return m.group(0)


def _mk(client: TestClient, db: Session, code: str) -> ReviewSession:
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


def _seed(db: Session, sid: int, page: str, n: int = 3, *, profiles: int = 0):
    reviewers = [
        Reviewer(session_id=sid, name=f"Rr{i}", email=f"rr{i}@example.org")
        for i in range(n)
    ]
    reviewees = [
        Reviewee(
            session_id=sid,
            name=f"Re{i}",
            email_or_identifier=f"re{i}@example.org",
            profile_link="https://example.org/p" if i < profiles else None,
        )
        for i in range(n)
    ]
    db.add_all(reviewers + reviewees)
    db.commit()
    for r in reviewers + reviewees:
        db.refresh(r)
    if page == "relationships":
        db.add_all([
            Relationship(
                session_id=sid,
                reviewer_id=reviewers[i].id,
                reviewee_id=reviewees[i].id,
            )
            for i in range(n)
        ])
        db.commit()


def _get(client: TestClient, rs: ReviewSession, page: str, suffix: str = "") -> str:
    return client.get(f"/operator/sessions/{rs.id}/{page}{suffix}").text


# ── The panel's starting state ────────────────────────────────────────


@pytest.mark.parametrize("page,noun,Noun", PAGES)
def test_the_panel_ships_hidden_and_unlocked_opens_it(
    client: TestClient, db: Session, page: str, noun: str, Noun: str
) -> None:
    """`hidden` is the whole of the closed state — there is no second
    gate — so a panel that stops shipping it is permanently open, and a
    `?unlocked=1` that stops being read is permanently shut. Both
    mutations passed the entire suite.
    """
    rs = _mk(client, db, f"up-h-{page[:4]}")
    _seed(db, rs.id, page)

    closed = _card(_get(client, rs, page), page)
    assert "hidden" in _panel_tag(closed), "the panel ships open"
    assert _toggle_button(closed) == "Unlock"
    assert 'aria-expanded="false"' in closed

    opened = _card(_get(client, rs, page, "?unlocked=1"), page)
    assert "hidden" not in _panel_tag(opened), "`?unlocked=1` did not open it"
    assert _toggle_button(opened) == "Lock"
    assert 'aria-expanded="true"' in opened


@pytest.mark.parametrize("page,noun,Noun", PAGES)
def test_the_lock_control_starts_inside_the_panel_when_it_arrives_open(
    client: TestClient, db: Session, page: str, noun: str, Noun: str
) -> None:
    """One element, two homes. Collapsed it is the card's last child;
    open it belongs under the upload card, inside the panel. The toggle
    MOVES it rather than rendering two copies — so a page that arrives
    open has to start it in the panel, or the first Lock click moves it
    out of a place it was never in.

    Read by position: the control is inside `.unlock-right` when open and
    outside the panel when closed.
    """
    rs = _mk(client, db, f"up-l-{page[:4]}")
    _seed(db, rs.id, page)

    closed = _card(_get(client, rs, page), page)
    panel_at = closed.index('id="roster-unlock-panel"')
    actions_at = closed.index('class="roster-card-actions"')
    assert actions_at > closed.index("</div>", panel_at), (
        "the control renders inside a closed panel, where it is invisible"
    )

    opened = _card(_get(client, rs, page, "?unlocked=1"), page)
    right_at = opened.index('class="unlock-stack unlock-right"')
    assert opened.index('class="roster-card-actions"') > right_at, (
        "arriving open, the control is not in the panel's right column"
    )


@pytest.mark.parametrize("page,noun,Noun", PAGES)
def test_the_toggle_moves_one_control_rather_than_rendering_two(
    client: TestClient, db: Session, page: str, noun: str, Noun: str
) -> None:
    """Two copies of one control is how they drift apart. Source
    assertion on the script, with the behaviour measured in Chromium:
    the control's parent goes `.card.roster-card` -> `.unlock-stack
    .unlock-right` -> back on each click.
    """
    body = _get(client, _mk(client, db, f"up-m-{page[:4]}"), page)
    assert body.count('class="roster-card-actions"') == 1, (
        "two copies of the Lock control"
    )
    assert 'panel.querySelector(".unlock-right").appendChild(actions)' in body, (
        "the control has no second home; opening the panel orphans it"
    )
    assert "card.appendChild(actions)" in body


@pytest.mark.parametrize("page,noun,Noun", PAGES)
def test_the_panel_is_reachable_without_javascript(
    client: TestClient, db: Session, page: str, noun: str, Noun: str
) -> None:
    """The panel ships `hidden` and is opened only by a JS button, so
    without the `<noscript>` link this page loses the CSV import, the
    delete-all and the labels editor in one step. `?unlocked=1` is a
    state the server already supports, so the fallback is a link to it.
    """
    rs = _mk(client, db, f"up-n-{page[:4]}")
    _seed(db, rs.id, page)
    card = _card(_get(client, rs, page), page)

    m = re.search(r"<noscript>\s*(<a[^>]*>)\s*Unlock\s*</a>", card, re.S)
    assert m, f"no no-JS way into the panel: {card[-700:]}"
    assert "?unlocked=1#roster-card" in m.group(1), m.group(1)


# ── What the panel holds ──────────────────────────────────────────────


@pytest.mark.parametrize("page,noun,Noun", PAGES)
def test_both_cards_moved_in_and_nothing_stays_below(
    client: TestClient, db: Session, page: str, noun: str, Noun: str
) -> None:
    rs = _mk(client, db, f"up-b-{page[:4]}")
    _seed(db, rs.id, page)
    body = _get(client, rs, page, "?unlocked=1")
    card = _card(body, page)

    assert 'id="upload-csv"' in card, "the upload card is not in the panel"
    assert 'class="card danger-zone"' in card, "the Danger Zone is not in the panel"
    assert "field-labels-form" in card, "the labels editor is not in the panel"
    # And nothing is left below the preview table.
    assert 'class="bottom-grid"' not in _markup(body)
    assert _markup(body).count('id="upload-csv"') == 1


@pytest.mark.parametrize("page,noun,Noun", PAGES)
def test_the_labels_editor_goes_left_over_the_danger_zone(
    client: TestClient, db: Session, page: str, noun: str, Noun: str
) -> None:
    """Reviewers' arrangement: editor over Danger Zone on the left,
    Upload on the right."""
    rs = _mk(client, db, f"up-a-{page[:4]}")
    _seed(db, rs.id, page)
    card = _card(_get(client, rs, page, "?unlocked=1"), page)

    left_at = card.index('class="unlock-stack"')
    right_at = card.index('class="unlock-stack unlock-right"')
    assert left_at < right_at
    assert left_at < card.index("field-labels-form") < right_at
    assert left_at < card.index('class="card danger-zone"') < right_at
    assert card.index('id="upload-csv"') > right_at


@pytest.mark.parametrize("page,noun,Noun", PAGES)
def test_the_danger_zone_is_gated_on_rows_and_upload_is_not(
    client: TestClient, db: Session, page: str, noun: str, Noun: str
) -> None:
    """The route does NOT refuse an empty delete-all — it answers 303 and
    writes an audit row reading "Deleted all 0". Worse, `_delete_all`
    opens with `invalidate_if_validated(...)` before it counts anything,
    so an ungated Delete-all knocks a `validated` session back to `draft`
    while deleting nothing at all.

    Upload is not gated: an empty roster is exactly when it is needed.
    """
    rs = _mk(client, db, f"up-g-{page[:4]}")
    empty = _card(_get(client, rs, page, "?unlocked=1"), page)
    assert 'class="card danger-zone"' not in empty, (
        "Delete-all offered on an empty roster"
    )
    assert 'id="upload-csv"' in empty, "Upload hidden on the roster that needs it"

    _seed(db, rs.id, page)
    filled = _card(_get(client, rs, page, "?unlocked=1"), page)
    assert 'class="card danger-zone"' in filled


@pytest.mark.parametrize("page,noun,Noun", PAGES)
def test_each_confirm_sentence_is_one_flex_item(
    client: TestClient, db: Session, page: str, noun: str, Noun: str
) -> None:
    """`.confirm-label` is `display: flex`, so every bare text node
    becomes its own flex item with the row's 8px `gap` between them —
    which detaches the closing "." from the pill before it. Measured on
    Observers at 19P.2 rung 6: 12px where 4 was intended. The gap is for
    the checkbox, not for the words.

    So each label holds exactly one `<span>` wrapping the whole sentence
    (plus the pills nested inside it), and the sentence's last character
    is inside that span.
    """
    rs = _mk(client, db, f"up-f-{page[:4]}")
    _seed(db, rs.id, page)
    card = _card(_get(client, rs, page, "?unlocked=1"), page)

    labels = re.findall(r'<label class="confirm-label">(.*?)</label>', card, re.S)
    assert len(labels) == 2, f"expected the upload + delete-all confirms, got {len(labels)}"
    for body in labels:
        text_after_input = body[body.index(">", body.index("<input")) + 1:]
        assert text_after_input.lstrip().startswith("<span>"), (
            f"the sentence is not wrapped: {text_after_input[:120]!r}"
        )
        assert text_after_input.rstrip().endswith("</span>"), (
            f"the wrapper closes early: {text_after_input[-120:]!r}"
        )


@pytest.mark.parametrize("page,noun,Noun", PAGES)
def test_each_confirm_key_appears_exactly_once(
    client: TestClient, db: Session, page: str, noun: str, Noun: str
) -> None:
    """`base.html` resolves a confirm to its button with a first-match
    `querySelector`, so a duplicated key gates the wrong button."""
    rs = _mk(client, db, f"up-k-{page[:4]}")
    _seed(db, rs.id, page)
    body = _markup(_get(client, rs, page, "?unlocked=1"))
    for key in ("delete-all", "replace-roster"):
        assert body.count(f'data-delete-confirm="{key}"') == 1, key
        assert body.count(f'data-delete-btn="{key}"') == 1, key


# ── The readouts ──────────────────────────────────────────────────────


@pytest.mark.parametrize("page,noun,Noun", PAGES)
def test_the_index_reports_the_roster_and_its_populated_columns(
    client: TestClient, db: Session, page: str, noun: str, Noun: str
) -> None:
    rs = _mk(client, db, f"up-r-{page[:4]}")
    _seed(db, rs.id, page, n=3)
    card = _card(_get(client, rs, page), page)

    m = re.search(
        rf'roster-readout-label">{Noun} roster:</span>\s*'
        r'<span class="pill pill-count">(.*?)</span>',
        card, re.S,
    )
    assert m, "no roster readout"
    assert " ".join(m.group(1).split()) == f"3 {noun}s"

    chips = re.findall(r'<span class="pill pill-count">([^<]*)</span>', card)
    assert any("(3)" in c for c in chips), chips
    assert "none yet" not in card


@pytest.mark.parametrize("page,noun,Noun", PAGES)
def test_an_empty_roster_lists_its_identity_columns_at_zero(
    client: TestClient, db: Session, page: str, noun: str, Noun: str
) -> None:
    """A zero on an identity column is itself worth seeing — it is what
    an operator who has uploaded nothing, or uploaded a CSV missing a
    required column, needs to be told.

    **`none yet` cannot render, on any roster page.** The chip row's
    `{% else %}` branch fires only when `col_readouts` is empty, and all
    four `*_column_state` helpers emit their identity entries
    unconditionally — so the list is never empty and
    `.roster-readout-empty` is dead markup. Checked across all four
    helpers, not inferred from these two.

    This test was written asserting `none yet` and failed, which is how
    that was found. The dead branch is NOT removed here: it sits in all
    four templates, and deleting it on the two this rung touches would
    leave the very drift 19P.3 exists to remove. Recorded for rung 5's
    sweep.
    """
    rs = _mk(client, db, f"up-e-{page[:4]}")
    card = _card(_get(client, rs, page), page)

    m = re.search(
        rf'roster-readout-label">{Noun} roster:</span>\s*'
        r'<span class="pill pill-count">(.*?)</span>',
        card, re.S,
    )
    assert m and " ".join(m.group(1).split()) == f"0 {noun}s", card[:400]

    chips = re.findall(r'<span class="pill pill-count">([^<]*)</span>', card)
    identity = [c.strip() for c in chips if "(0)" in c]
    assert len(identity) == 2, (
        f"expected both identity columns listed at zero, got {chips}"
    )
    assert "none yet" not in card, (
        "the dead `{% else %}` branch became reachable — if that is "
        "deliberate, this test is the place to say so"
    )


def test_the_reviewees_index_lists_a_column_only_where_it_is_populated(
    client: TestClient, db: Session
) -> None:
    """The rule the readouts follow: they mirror the columns the preview
    table renders, and the table hides an optional column with no data.

    `Profile` is the sharpest case — the one non-tag optional column on
    any roster page. A mutation rendering it unconditionally passed the
    whole suite.
    """
    rs = _mk(client, db, "up-prof")
    _seed(db, rs.id, "reviewees", n=4, profiles=0)
    card = _card(_get(client, rs, "reviewees"), "reviewees")
    assert "Profile" not in card, "an unpopulated column is listed"

    rs2 = _mk(client, db, "up-prof2")
    _seed(db, rs2.id, "reviewees", n=4, profiles=2)
    card2 = _card(_get(client, rs2, "reviewees"), "reviewees")
    assert re.search(r"Profile \(2\)", card2), card2[:600]


def test_the_relationships_index_chips_are_tautological_and_say_so() -> None:
    """`reviewer_id` / `reviewee_id` are non-nullable foreign keys, so
    this page's two identity chips can only ever equal the roster total.

    Rendered anyway — `ColumnReadout.count` means "rows carrying a
    value", and giving one page's chips a different meaning would be the
    per-page drift 19P.3 exists to remove. This pins the DECISION, so a
    later reader who thinks the chips are broken finds the reasoning
    rather than silently "fixing" them into something else.
    """
    import inspect

    from app.web.views import _setup

    doc = inspect.getdoc(_setup.relationship_column_state) or ""
    assert "tautological" in doc
    assert "non-nullable foreign keys" in doc


# ── The panel-open contract through its own controls ──────────────────


@pytest.mark.parametrize("page,noun,Noun", PAGES)
def test_a_labels_save_returns_with_the_panel_still_open(
    client: TestClient, db: Session, page: str, noun: str, Noun: str
) -> None:
    """A Save does not close the card; the Lock control does. The editor
    lives inside the panel, so a bare redirect closes the panel the
    operator was working in."""
    rs = _mk(client, db, f"up-s-{page[:4]}")
    _seed(db, rs.id, page)
    field = "tag_1" if page == "reviewees" else "1"
    response = client.post(
        f"/operator/sessions/{rs.id}/{page}/field-labels",
        data={field: "Tutor"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"] == (
        f"/operator/sessions/{rs.id}/{page}?unlocked=1#roster-card"
    )


@pytest.mark.parametrize("page,noun,Noun", PAGES)
def test_delete_all_returns_with_the_panel_still_open(
    client: TestClient, db: Session, page: str, noun: str, Noun: str
) -> None:
    rs = _mk(client, db, f"up-d-{page[:4]}")
    _seed(db, rs.id, page)
    response = client.post(
        f"/operator/sessions/{rs.id}/{page}/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"] == (
        f"/operator/sessions/{rs.id}/{page}?unlocked=1#roster-card"
    )


@pytest.mark.parametrize("page,noun,Noun", PAGES)
def test_a_failed_import_arrives_with_the_panel_open(
    client: TestClient, db: Session, page: str, noun: str, Noun: str
) -> None:
    """The issue list renders inside the upload card, which is inside the
    panel — and a 400 re-renders in place rather than redirecting, so
    `?unlocked=1` cannot reach it. A panel that shipped collapsed here
    would show the operator a closed panel and no errors at all.

    **Relationships has two such paths where the shared handler has
    one** — a blocked CSV, and the `missing_confirm` replace state
    Reviewees has no equivalent of. Both mutations survived the suite.
    """
    rs = _mk(client, db, f"up-i-{page[:4]}")
    _seed(db, rs.id, page)
    response = client.post(
        f"/operator/sessions/{rs.id}/{page}/import",
        files={"file": ("r.csv", b"NotAColumn\nx\n", "text/csv")},
    )
    assert response.status_code == 400, response.status_code
    card = _card(response.text, page)
    assert "hidden" not in _panel_tag(card), (
        "a failed import shows a closed panel and no errors"
    )


def test_the_relationships_replace_confirmation_also_arrives_open(
    client: TestClient, db: Session
) -> None:
    """The second of Relationships' two in-place 400 paths: a valid CSV
    over a non-empty roster, with no `confirm_replace` tick. Its notice
    renders in the upload card like the issue list does."""
    rs = _mk(client, db, "up-mc")
    _seed(db, rs.id, "relationships", n=2)
    reviewer = db.execute(select(Reviewer)).scalars().first()
    reviewee = db.execute(select(Reviewee)).scalars().first()
    csv = (
        "ReviewerEmail,RevieweeEmail\n"
        f"{reviewer.email},{reviewee.email_or_identifier}\n"
    ).encode()
    response = client.post(
        f"/operator/sessions/{rs.id}/relationships/import",
        files={"file": ("r.csv", csv, "text/csv")},
    )
    assert response.status_code == 400, response.text[:400]
    card = _card(response.text, "relationships")
    assert "hidden" not in _panel_tag(card), (
        "the replace confirmation renders inside a closed panel"
    )


@pytest.mark.parametrize("page,noun,Noun", PAGES)
def test_both_panel_cards_right_align_their_action_with_no_inline_style(
    client: TestClient, db: Session, page: str, noun: str, Noun: str
) -> None:
    """Three inline styles retired on the way in: two
    `<label style="font-weight: normal;">` confirms (covered by the
    flex-item test above) and the upload card's
    `<div class="btn-pair" style="margin-top: 20px;">`.

    `.btn-pair` and `.unlock-col-actions` do NOT compute alike —
    `.btn-pair` is a 16px-gap row starting at the LEFT, this is an 8px
    flex-end row. So the Upload button moves left -> right and its top
    margin 20px -> 12px. Chosen, not inherited: both cards in this panel
    right-align their action, `.btn-pair` names a pair and this is one
    button, and `CLAUDE.md` asks for a class over an inline style.

    A mutation putting `.btn-pair` and its inline margin back passed the
    whole suite, this file included, until this test.
    """
    rs = _mk(client, db, f"up-st-{page[:4]}")
    _seed(db, rs.id, page)
    card = _card(_get(client, rs, page, "?unlocked=1"), page)

    assert "style=" not in card, (
        f"an inline style came back into the panel: "
        f"{card[max(0, card.find('style=') - 120):card.find('style=') + 80]!r}"
    )
    assert "btn-pair" not in card, "the upload action row reverted to `.btn-pair`"
    # Both cards — Upload and Delete-all — use the panel's own row.
    assert card.count('class="unlock-col-actions"') == 2, (
        "one of the panel's two cards does not right-align its action"
    )
