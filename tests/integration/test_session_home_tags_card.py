"""19S Item 9 Part B — the Tags card on Session Home's details card.

The card renders below User interface settings in the details card's
right-hand ``.bottom-left`` column, above the Save / Cancel / Lock
cluster. Locked it shows the session's tags as the lobby's pills
(an em dash ``.config-value`` when there are none, like the card's other
empty fields); unlocked it shows a text input prefilled with the tags
comma-joined.

**Rung 2 wires it to the card's own save.** The input joins the
``config-save`` form, so it rides the card's edit window and Save — no
second mechanism. Rung 1's two inertness assertions are inverted here
rather than deleted, so the diff shows the control going live.

The semantics the route owns, each pinned below:

- a typed set is written, normalized, after the config apply — so a
  rejected save writes no tags either;
- an **emptied** box clears the set, as the lobby's row expander does
  (the Create page's empty box writes nothing — there is no set yet);
- a request without the card's ``tags_present`` marker leaves them
  alone — FastAPI cannot tell an absent field from an empty one, and a
  page rendered before the field existed must not clear every tag;
- a save that leaves the box untouched emits no tag events.

The settings-CSV importer is normalized in the same rung, because this
editor's first save would otherwise rewrite any tag imported with
capitals; those tests close the file.
"""

from __future__ import annotations

import csv
import io
import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, User
from app.services import session_tags


def _create(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Tagged", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _tag(db: Session, review_session: ReviewSession, tags: list[str]) -> None:
    user = db.execute(select(User)).scalars().first()
    session_tags.set_tags(db, review_session=review_session, user=user, tags=tags)


def _tags_of(db: Session, review_session: ReviewSession) -> list[str]:
    return session_tags.tags_for_sessions(db, [review_session.id])[
        review_session.id
    ]


def _save(
    client: TestClient,
    review_session: ReviewSession,
    *,
    name: str = "Renamed",
    display_timezone: str = "",
    **extra: str,
):
    """POST the details card's Save, with ``tags=`` only when given.

    Every caller renames the session in the same request and then asserts
    the rename landed, or that it did not: a rejected save also leaves the
    tags alone, so without that control a "tags unchanged" assertion passes
    for the wrong reason.
    """
    data = {
        "name": name,
        "code": review_session.code,
        "description": "",
        "display_timezone": display_timezone,
        **extra,
    }
    if "tags" in extra:
        # What the card sends alongside its Tags field (cold read M3).
        data["tags_present"] = "1"
    return client.post(
        f"/operator/sessions/{review_session.id}/config",
        data=data,
        follow_redirects=False,
    )


def _tag_events(db: Session, review_session: ReviewSession) -> int:
    return len(
        db.execute(
            select(AuditEvent).where(
                AuditEvent.session_id == review_session.id,
                AuditEvent.event_type.in_(
                    ["session.tag_added", "session.tag_removed"]
                ),
            )
        ).scalars().all()
    )


def _settings_csv(tags: list[str]) -> bytes:
    """A settings bundle in the exporter's own shape, carrying only tags."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(("field", "value", "data_type"))
    for i, tag in enumerate(tags):
        writer.writerow((f"session_tags[{i}].tag", tag, "string"))
    return buf.getvalue().encode("utf-8")


def _card(body: str) -> str:
    """The Tags card's own markup — opening tag to its closing one.

    A ``<div>`` depth scan, the shape 19S Item 6's review settled on:
    bounding at the next sibling card falls back to the page's tail when
    there is none, and every ``in card`` assertion then reads the rest of
    the document. ``test_the_card_helper_is_bounded`` guards it.
    """
    anchor = body.find('id="config-tags-card"')
    assert anchor != -1, "the Tags card is missing from Session Home"
    start = body.rfind("<div", 0, anchor)
    depth = 0
    i = start
    while True:
        opened = body.find("<div", i)
        closed = body.find("</div>", i)
        assert closed != -1, "the Tags card's <div> is never closed"
        if opened != -1 and opened < closed:
            depth += 1
            i = opened + len("<div")
            continue
        depth -= 1
        i = closed + len("</div>")
        if depth == 0:
            return body[start:i]


def test_the_card_helper_is_bounded(client: TestClient, db: Session) -> None:
    """Balanced, and something rendered follows it: the card is not the
    page's last element, so a tail slice would carry the Save cluster."""
    review_session = _create(client, db, "HOME-TAGS-BOUND")
    body = client.get(f"/operator/sessions/{review_session.id}").text
    card = _card(body)

    assert card.startswith('<div class="card" id="config-tags-card"')
    assert card.count("<div") == card.count("</div>")
    assert "data-config-save" not in card, (
        "the Save cluster follows the card and is not inside it"
    )
    assert "data-config-save" in body[body.index(card) + len(card):]


def test_the_card_sits_below_ui_settings_and_above_the_save_cluster(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "HOME-TAGS-ORDER")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    ui = body.find('id="config-ui-settings-card"')
    tags = body.find('id="config-tags-card"')
    save = body.find("data-config-save")
    assert -1 not in (ui, tags, save)
    assert ui < tags < save

    # Same .bottom-left column as the UI settings card, so the column's
    # gap spaces the pair (spec/ui_elements.md §10) — no new CSS.
    column = body.rfind('<div class="bottom-left">', 0, ui)
    assert column != -1
    assert body.rfind('<div class="bottom-left">', 0, tags) == column


def test_locked_it_renders_the_lobbys_pills(
    client: TestClient, db: Session
) -> None:
    """One ``.pill.pill-count`` per tag inside ``.session-tags`` — the
    sessions lobby's own markup (author's ruling, 2026-09-23) — under a
    display-only wrapper, since ``.session-tags``'s ``display: flex``
    would outrank edit mode's ``display: none`` on the same element."""
    review_session = _create(client, db, "HOME-TAGS-LOCKED")
    _tag(db, review_session, ["pilot", "2026"])
    card = _card(client.get(f"/operator/sessions/{review_session.id}").text)

    # Nested, not merely following: the wrapper must hold the pills, or
    # they stay visible in edit mode.
    assert re.search(r'<div data-display-only>\s*<div class="session-tags">', card)
    display = card.split("<div data-display-only>", 1)[1].split("<input", 1)[0]
    assert re.findall(r'<span class="pill pill-count">([^<]*)</span>', display) == [
        "2026",
        "pilot",
    ]
    assert "2026, pilot" not in display, "no longer comma-joined"
    assert "Tags (optional)</h3>" in card
    # The heading is the label; there is no second "Tags" above the box.
    assert "<label" not in card
    assert 'aria-labelledby="config-tags-heading"' in card


def test_an_untagged_session_shows_an_em_dash(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "HOME-TAGS-EMPTY")
    card = _card(client.get(f"/operator/sessions/{review_session.id}").text)

    assert '<div class="config-value" data-display-only>—</div>' in card
    assert 'value=""' in card, "and the edit box starts empty"


def test_unlocked_the_input_is_prefilled(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "HOME-TAGS-EDIT")
    _tag(db, review_session, ["pilot", "2026"])
    body = client.get(f"/operator/sessions/{review_session.id}?editing=1").text
    card = _card(body)

    assert 'data-config-mode="edit"' in body
    assert 'value="2026, pilot"' in card
    assert "data-edit-only" in card


def test_the_input_is_wired_to_the_config_form(
    client: TestClient, db: Session
) -> None:
    """The inversion of rung 1's inertness assertion, kept in that shape
    so the diff shows the control going live: a ``name`` is what a browser
    submits, and ``form=`` is what associates a control rendered outside
    ``<form>`` with the card's save."""
    review_session = _create(client, db, "HOME-TAGS-WIRED")
    card = _card(
        client.get(f"/operator/sessions/{review_session.id}?editing=1").text
    )

    assert 'id="config-tags"' in card
    assert 'name="tags"' in card
    assert f'form="config-save-{review_session.id}"' in card


def test_saving_the_card_writes_the_tags(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "HOME-TAGS-WRITE")
    _tag(db, review_session, ["pilot"])

    response = _save(client, review_session, tags="Beta,  alpha ,beta")
    assert response.status_code == 303, response.text
    db.refresh(review_session)
    assert review_session.name == "Renamed", "the save went through"
    assert _tags_of(db, review_session) == ["alpha", "beta"], (
        "a replace, normalized: pilot dropped, case and spaces folded, "
        "the duplicate collapsed"
    )


def test_an_emptied_box_clears_the_tags(client: TestClient, db: Session) -> None:
    """The lobby's meaning, not the Create page's: there is a set to edit."""
    review_session = _create(client, db, "HOME-TAGS-CLEAR")
    _tag(db, review_session, ["pilot", "2026"])

    response = _save(client, review_session, tags="")
    assert response.status_code == 303, response.text
    db.refresh(review_session)
    assert review_session.name == "Renamed"
    assert _tags_of(db, review_session) == []


def test_a_save_from_a_page_without_the_tags_field_leaves_them_alone(
    client: TestClient, db: Session
) -> None:
    """A page rendered before the Tags field existed — a tab left open
    across a deploy — posts neither ``tags`` nor its marker. FastAPI would
    read that as an emptied box, so without the marker its first Save
    would clear every tag (Item 9 close, cold read M3). It now leaves
    them alone, while the rest of the save still lands."""
    review_session = _create(client, db, "HOME-TAGS-ABSENT")
    _tag(db, review_session, ["pilot"])

    response = _save(client, review_session)
    assert response.status_code == 303, response.text
    db.refresh(review_session)
    assert review_session.name == "Renamed", "the save went through"
    assert _tags_of(db, review_session) == ["pilot"]


def test_the_card_posts_the_marker_beside_the_field(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "HOME-TAGS-MARKER")
    card = _card(
        client.get(f"/operator/sessions/{review_session.id}?editing=1").text
    )
    assert 'name="tags_present"' in card
    assert f'form="config-save-{review_session.id}"' in card


def test_an_untouched_box_emits_no_tag_events(
    client: TestClient, db: Session
) -> None:
    """Saving the card for another field resubmits the prefilled tags;
    ``set_tags`` diffs, so nothing is added, removed or audited."""
    review_session = _create(client, db, "HOME-TAGS-QUIET")
    _tag(db, review_session, ["pilot", "2026"])
    before = _tag_events(db, review_session)
    # The control: tagging the session emitted two events, so the counter
    # can see them. Without it, a counter stuck at zero passes this test
    # by comparing 0 with 0 — the mutation run found exactly that.
    assert before == 2

    response = _save(client, review_session, tags="2026, pilot")
    assert response.status_code == 303, response.text
    db.refresh(review_session)
    assert review_session.name == "Renamed"
    assert _tag_events(db, review_session) == before
    assert _tags_of(db, review_session) == ["2026", "pilot"]


def test_one_save_is_one_correlation_id(client: TestClient, db: Session) -> None:
    """The config events and the tag events of one save group as one
    request. ``request_correlation_id`` mints a fresh id per call, so the
    route mints one and hands it to both (Codex, #2569)."""
    review_session = _create(client, db, "HOME-TAGS-CORR")
    _tag(db, review_session, ["pilot"])
    last = db.execute(
        select(AuditEvent.id).order_by(AuditEvent.id.desc())
    ).scalars().first()

    response = _save(client, review_session, tags="pilot, 2026")
    assert response.status_code == 303, response.text
    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == review_session.id, AuditEvent.id > last
        )
    ).scalars().all()
    kinds = {e.event_type for e in events}
    assert "session.tag_added" in kinds, "the save changed a tag"
    assert kinds - {"session.tag_added", "session.tag_removed"}, (
        "and emitted a config event beside it — the rename"
    )
    assert len({e.correlation_id for e in events}) == 1, (
        sorted((e.event_type, e.correlation_id) for e in events)
    )


def test_a_rejected_save_writes_no_tags(client: TestClient, db: Session) -> None:
    """The write runs after the config apply, so a save the card rejects
    writes nothing at all — tags included."""
    review_session = _create(client, db, "HOME-TAGS-REJECT")
    _tag(db, review_session, ["pilot"])

    response = _save(
        client, review_session, display_timezone="Not/AZone", tags="other"
    )
    assert response.status_code == 422, response.text
    db.refresh(review_session)
    assert review_session.name == "Tagged", "the save was rejected"
    assert _tags_of(db, review_session) == ["pilot"]


# --- The importer: tags are lower case everywhere --------------------------


def test_a_settings_csv_tag_is_stored_lower_case_and_the_lobby_can_remove_it(
    client: TestClient, db: Session
) -> None:
    """Both halves of the defect, through the routes.

    Before this rung the importer stored ``Pilot`` raw, and the lobby's
    remove — which normalizes what it is asked for — looked for ``pilot``,
    found nothing and left the tag in place.
    """
    response = client.post(
        "/operator/sessions",
        data={"name": "Imported", "code": "HOME-TAGS-IMPORT", "description": ""},
        files={
            "settings_file": (
                "s.csv", _settings_csv(["Pilot", "  Cohort-A "]), "text/csv"
            )
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "HOME-TAGS-IMPORT")
    ).scalar_one()
    assert _tags_of(db, review_session) == ["cohort-a", "pilot"]

    removed = client.post(
        "/operator/sessions/bulk-tags",
        data={
            "session_ids": [str(review_session.id)],
            "tags": "Pilot",
            "op": "remove",
        },
        follow_redirects=False,
    )
    assert removed.status_code == 303, removed.text
    assert _tags_of(db, review_session) == ["cohort-a"]
