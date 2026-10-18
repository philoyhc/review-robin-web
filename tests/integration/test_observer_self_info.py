"""An observer sees their own roster entry — participant info Item 5.

`guide/participant_info.md` Item 5: the Observers page's "What observers
see of their own entry" card and its save, the `Observers see:` readout,
the observer's own line after the role pills on `/collation`, and the
selection's Settings CSV row. The default is name and email; the tag
starts off. The save is refused only when archived, the Observers
roster's own gate.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, ReviewSession

from ._unlock_panel import panel_columns


def _session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Cohort A", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    rs.observers_enabled = True
    db.commit()
    return rs


def _alice(db: Session, rs: ReviewSession, *, tag: str | None = "Panel") -> None:
    """`client` signs in as alice@example.edu (tests/conftest.py)."""
    db.add(Observer(
        session_id=rs.id, email="alice@example.edu",
        display_name="Alice Observer", status="active", tag_1=tag,
    ))
    db.commit()


def _div_at(html: str, marker: str) -> str:
    start = html.rindex("<div", 0, html.index(marker))
    depth = 0
    for m in re.finditer(r"<(/?)div\b", html[start:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return html[start:start + m.end() + 1]
    raise AssertionError(f"{marker} never closes")


def _card(html: str) -> str:
    return re.search(
        r"<section[^>]*data-observer-self-card[^>]*>.*?</section>", html, re.S
    ).group(0)


def _chips(card: str) -> list[tuple[str, bool, str]]:
    return [
        (key, "checked" in rest, label.strip())
        for key, rest, label in re.findall(
            r'<input type="checkbox"[^>]*value="(\w+)"([^>]*)>([^<]*)</label>',
            card,
        )
    ]


def _readout(html: str) -> list[str]:
    shown = _div_at(html, "data-observer-self-readout")
    assert "Observers see:" in shown
    return re.findall(r'<span class="pill pill-count">([^<]*)</span>', shown)


def test_the_readout_reports_the_default(client: TestClient, db: Session) -> None:
    rs = _session(client, db, "obi-readout")
    _alice(db, rs)
    html = client.get(f"/operator/sessions/{rs.public_id}/observers").text
    assert _readout(html) == ["Name", "Email"]


def test_the_card_heads_the_right_column_at_the_default(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "obi-card")
    _alice(db, rs)
    html = client.get(f"/operator/sessions/{rs.public_id}/observers?unlocked=1").text
    _, _, right = panel_columns(html)
    assert right.index("data-observer-self-card") < right.index("danger-zone")
    card = _card(html)
    assert "What observers see of their own entry" in card
    assert _chips(card) == [
        ("display_name", True, "Name"),
        ("email", True, "Email"),
        ("tag_1", False, "Tag"),
    ]
    # The form posts to its route; Save and Cancel wait for a change.
    assert f'action="/operator/sessions/{rs.public_id}/observers/self-fields"' in card
    assert len(re.findall(r"<button[^>]*disabled", card)) == 2


def test_the_tag_is_offered_only_while_a_row_holds_one(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "obi-notag")
    _alice(db, rs, tag=None)
    card = _card(client.get(f"/operator/sessions/{rs.public_id}/observers?unlocked=1").text)
    assert [key for key, _, _ in _chips(card)] == ["display_name", "email"]


def test_an_empty_roster_still_renders_the_card(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "obi-empty")
    html = client.get(f"/operator/sessions/{rs.public_id}/observers?unlocked=1").text
    assert [key for key, _, _ in _chips(_card(html))] == ["display_name", "email"]
    assert _readout(html) == ["Name", "Email"]


def test_a_failed_import_still_renders_the_card_and_readout(
    client: TestClient, db: Session
) -> None:
    """Item 1's Codex finding, kept: the in-place 400 re-render owes the
    own-entry keys as the GET does."""
    rs = _session(client, db, "obi-badcsv")
    _alice(db, rs)
    response = client.post(
        f"/operator/sessions/{rs.public_id}/observers/import",
        files={"file": ("o.csv", b"ObserverName\nX\n", "text/csv")},
    )
    assert response.status_code == 400, response.status_code
    assert "data-observer-self-card" in response.text
    assert _readout(response.text) == ["Name", "Email"]


def _info(html: str) -> str:
    m = re.search(
        r'<span class="rs-self-info" data-observer-self-info>(.*?)</span>\s*</div>',
        html, re.S,
    )
    assert m, "no observer info on the role row"
    return m.group(1)


def test_collation_shows_the_observers_own_line_after_the_pills(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "obi-collation")
    _alice(db, rs)
    html = client.get(f"/me/sessions/{rs.public_id}/collation").text
    nav = _div_at(html, 'class="rs-role-nav"')
    assert nav.index("rs-role-nav-active") < nav.index("data-observer-self-info")
    info = _info(html)
    assert "Alice Observer" in info
    assert "alice@example.edu" in info
    assert "Panel" not in info  # the tag starts off
    assert "data-reviewer-self-info" not in html
    assert "data-reviewee-self-info" not in html


def test_a_reviewer_who_is_also_an_observer_sees_only_the_active_pages_line(
    client: TestClient, db: Session
) -> None:
    """`/collation` carries the observer line; the reviewer line stays on
    the reviewer pages."""
    from app.db.models import Reviewer

    rs = _session(client, db, "obi-both")
    _alice(db, rs)
    db.add(Reviewer(session_id=rs.id, name="Alice Reviewer", email="alice@example.edu"))
    db.commit()
    html = client.get(f"/me/sessions/{rs.public_id}/collation").text
    assert "Alice Observer" in _info(html)
    assert "Alice Reviewer" not in _info(html)
    assert "data-reviewer-self-info" not in html

# ── Storing the selection (rung 3) ───────────────────────────────────


def _save(client: TestClient, rs: ReviewSession, **form) -> object:
    return client.post(
        f"/operator/sessions/{rs.public_id}/observers/self-fields",
        data=form,
        follow_redirects=False,
    )


def test_a_save_stores_the_selection_and_collation_follows(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "obi-save")
    _alice(db, rs)
    response = _save(client, rs, fields=["email", "tag_1"])
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{rs.public_id}/observers?unlocked=1#roster-card"
    )
    db.refresh(rs)
    assert rs.observer_self_fields == ["email", "tag_1"]
    assert rs.reviewer_self_fields is None and rs.reviewee_self_fields is None
    html = client.get(f"/operator/sessions/{rs.public_id}/observers").text
    assert _readout(html) == ["Email", "Tag"]
    info = _info(client.get(f"/me/sessions/{rs.public_id}/collation").text)
    assert "alice@example.edu" in info and "Tag: Panel" in info
    assert "Alice Observer" not in info


def test_an_empty_save_shows_nothing_after_the_pill(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "obi-none")
    _alice(db, rs)
    assert _save(client, rs).status_code == 303
    db.refresh(rs)
    assert rs.observer_self_fields == []
    assert "data-observer-self-info" not in client.get(
        f"/me/sessions/{rs.public_id}/collation"
    ).text


def test_a_key_with_no_chip_survives_a_save(client: TestClient, db: Session) -> None:
    """A stored tag stays selected after the last tagged row loses it:
    the card offers no Tag chip then, so the key rides as `keep`."""
    rs = _session(client, db, "obi-keep")
    _alice(db, rs, tag=None)
    rs.observer_self_fields = ["display_name", "tag_1"]
    db.commit()
    html = client.get(f"/operator/sessions/{rs.public_id}/observers?unlocked=1").text
    assert '<input type="hidden" name="keep" value="tag_1">' in html
    assert _save(client, rs, fields=["email"], keep=["tag_1"]).status_code == 303
    db.refresh(rs)
    assert rs.observer_self_fields == ["email", "tag_1"]


def test_an_unknown_key_is_refused(client: TestClient, db: Session) -> None:
    rs = _session(client, db, "obi-unknown")
    # `name` is a reviewer and reviewee key; the observer's is `display_name`.
    assert _save(client, rs, fields=["name"]).status_code == 422
    db.refresh(rs)
    assert rs.observer_self_fields is None


@pytest.mark.parametrize("state", ["validated", "ready", "expired"])
def test_the_save_follows_the_roster_and_stays_open_until_archived(
    client: TestClient, db: Session, state: str
) -> None:
    """The Observers roster's gate, not `is_editable`; display-only, so a
    `validated` session stays validated."""
    rs = _session(client, db, f"obi-{state}")
    rs.status = state
    db.commit()
    assert _save(client, rs, fields=["display_name"]).status_code == 303
    db.refresh(rs)
    assert rs.observer_self_fields == ["display_name"]
    assert rs.status == state


def test_an_archived_session_refuses_the_save(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "obi-archived")
    rs.status = "archived"
    db.commit()
    assert _save(client, rs, fields=["display_name"]).status_code == 409
    db.refresh(rs)
    assert rs.observer_self_fields is None


def test_archived_the_readout_stays_and_the_card_goes(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "obi-archived-page")
    _alice(db, rs)
    rs.status = "archived"
    db.commit()
    html = client.get(f"/operator/sessions/{rs.public_id}/observers").text
    assert _readout(html) == ["Name", "Email"]
    assert "data-observer-self-card" not in html


def test_a_save_writes_one_audit_event(client: TestClient, db: Session) -> None:
    from app.db.models import AuditEvent

    rs = _session(client, db, "obi-audit")
    _save(client, rs, fields=["email"])
    _save(client, rs, fields=["email"])  # a no-op: nothing changed
    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == rs.id,
            AuditEvent.event_type == "session.observer_self_fields_set",
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].detail["changes"]["observer_self_fields"] == [None, ["email"]]


@pytest.mark.parametrize(
    ("stored", "cell"),
    [(None, ""), ([], "[]"), (["email", "tag_1"], '["email","tag_1"]')],
)
def test_the_settings_csv_round_trips_the_selection(
    client: TestClient, db: Session, stored: list[str] | None, cell: str
) -> None:
    from app.services.session_config_io._apply_session import (
        _apply_session_kv,
        _apply_session_metadata,
    )
    from app.services.session_config_io._apply_shared import _ParsedConfig
    from app.services.session_config_io._serialize import _session_rows

    source = _session(client, db, f"obi-csv-{len(cell)}")
    source.observer_self_fields = stored
    db.commit()
    row = next(
        r for r in _session_rows(source) if r[0] == "session.observer_self_fields"
    )
    assert row[1] == cell
    plan = _ParsedConfig()
    _apply_session_kv(plan, "session.observer_self_fields", row[1])
    target = SimpleNamespace(observer_self_fields=["email"])
    _apply_session_metadata(target, plan)
    assert target.observer_self_fields == stored


@pytest.mark.parametrize("cell", ['["name"]', '{"a":1}', "email"])
def test_the_settings_csv_refuses_a_bad_selection(cell: str) -> None:
    from app.services.session_config_io._apply_session import _apply_session_kv
    from app.services.session_config_io._apply_shared import (
        _ParseError,
        _ParsedConfig,
    )

    with pytest.raises(_ParseError):
        _apply_session_kv(_ParsedConfig(), "session.observer_self_fields", cell)
