"""A reviewee sees their own roster entry — participant info Item 4.

`guide/participant_info.md` Item 4: the Reviewees page's "What reviewees
see of their own entry" card and its save, the `Reviewees see:` readout,
the reviewee's own line after the role pills on `/results`, and the
selection's Settings CSV row. The default is name, email or identifier
and profile; tags start off.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession

from ._unlock_panel import panel_columns

LINK = "https://example.edu/alice"


def _session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Cohort A", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _alice(db: Session, rs: ReviewSession, *, profile: str | None = LINK) -> None:
    """`client` signs in as alice@example.edu (tests/conftest.py)."""
    db.add(
        Reviewee(
            session_id=rs.id, name="Alice Reviewee",
            email_or_identifier="alice@example.edu",
            profile_link=profile, tag_1="Blue",
        )
    )
    db.commit()


def _div_at(html: str, marker: str) -> str:
    start = html.rindex("<div", 0, html.index(marker))
    depth = 0
    for m in re.finditer(r"<(/?)div\b", html[start:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return html[start:start + m.end() + 1]
    raise AssertionError(f"{marker} never closes")


def _info(html: str) -> str:
    m = re.search(
        r'<span class="rs-self-info" data-reviewee-self-info>(.*?)</span>\s*</div>',
        html, re.S,
    )
    assert m, "no reviewee info on the role row"
    return m.group(1)


def test_the_readout_reports_the_default(client: TestClient, db: Session) -> None:
    rs = _session(client, db, "rei-readout")
    _alice(db, rs)
    html = client.get(f"/operator/sessions/{rs.public_id}/reviewees").text
    shown = _div_at(html, "data-reviewee-self-readout")
    assert "Reviewees see:" in shown
    assert re.findall(r'<span class="pill pill-count">([^<]*)</span>', shown) == [
        "Name", "Email", "Profile",
    ]


def test_the_card_sits_above_upload_with_a_chip_per_populated_column(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "rei-card")
    _alice(db, rs)
    html = client.get(f"/operator/sessions/{rs.public_id}/reviewees?unlocked=1").text
    _, left, _ = panel_columns(html)
    assert left.index("data-reviewee-self-card") < left.index('id="upload-csv"')
    card = re.search(
        r"<section[^>]*data-reviewee-self-card[^>]*>.*?</section>", html, re.S
    ).group(0)
    assert "What reviewees see of their own entry" in card
    chips = re.findall(
        r'<input type="checkbox"[^>]*value="(\w+)"([^>]*)>([^<]*)</label>', card
    )
    assert [(k, "checked" in rest, label.strip()) for k, rest, label in chips] == [
        ("name", True, "Name"),
        ("email_or_identifier", True, "Email"),
        ("profile_link", True, "Profile"),
        ("tag_1", False, "Tag 1"),
    ]
    # The form posts to its route; Save and Cancel wait for a change.
    assert f'action="/operator/sessions/{rs.public_id}/reviewees/self-fields"' in card
    assert len(re.findall(r"<button[^>]*disabled", card)) == 2


def test_a_failed_import_still_renders_the_card_and_readout(
    client: TestClient, db: Session
) -> None:
    """Item 1's Codex finding, kept: the in-place 400 re-render owes the
    own-entry keys as the GET does."""
    rs = _session(client, db, "rei-badcsv")
    _alice(db, rs)
    response = client.post(
        f"/operator/sessions/{rs.public_id}/reviewees/import",
        files={"file": ("r.csv", b"NotAColumn\nx\n", "text/csv")},
    )
    assert response.status_code == 400, response.status_code
    html = response.text
    assert "data-reviewee-self-card" in html
    shown = _div_at(html, "data-reviewee-self-readout")
    assert re.findall(r'<span class="pill pill-count">([^<]*)</span>', shown) == [
        "Name", "Email", "Profile",
    ]


def test_results_shows_the_reviewees_own_line_after_the_pills(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    rs = _session(client, db, "rei-results")
    _alice(db, rs)
    grant_reviewee_visibility(rs)
    html = client.get(f"/me/sessions/{rs.public_id}/results").text
    nav = _div_at(html, 'class="rs-role-nav"')
    assert nav.index("rs-role-nav-active") < nav.index("data-reviewee-self-info")
    info = _info(html)
    assert "Alice Reviewee" in info and "alice@example.edu" in info
    assert f'<a href="{LINK}">Profile</a>' in info
    assert "Blue" not in info  # tags start off
    assert "data-reviewer-self-info" not in html


def test_a_reviewer_who_is_also_a_reviewee_sees_only_the_active_pages_line(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    """`/results` carries the reviewee line; the reviewer line stays on
    the reviewer pages."""
    rs = _session(client, db, "rei-both")
    _alice(db, rs)
    db.add(Reviewer(session_id=rs.id, name="Alice Reviewer", email="alice@example.edu"))
    db.commit()
    grant_reviewee_visibility(rs)
    html = client.get(f"/me/sessions/{rs.public_id}/results").text
    assert "Alice Reviewee" in _info(html)
    assert "Alice Reviewer" not in _info(html)
    assert "data-reviewer-self-info" not in html


# ── Storing the selection (rung 3) ───────────────────────────────────


def _save(client: TestClient, rs: ReviewSession, **form) -> object:
    return client.post(
        f"/operator/sessions/{rs.public_id}/reviewees/self-fields",
        data=form,
        follow_redirects=False,
    )


def test_a_save_stores_the_selection_and_results_follow(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    rs = _session(client, db, "rei-save")
    _alice(db, rs)
    response = _save(client, rs, fields=["email_or_identifier", "tag_1"])
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{rs.public_id}/reviewees?unlocked=1#roster-card"
    )
    db.refresh(rs)
    assert rs.reviewee_self_fields == ["email_or_identifier", "tag_1"]
    assert rs.reviewer_self_fields is None, "the reviewers' selection moved"
    shown = _div_at(
        client.get(f"/operator/sessions/{rs.public_id}/reviewees").text,
        "data-reviewee-self-readout",
    )
    assert re.findall(r'<span class="pill pill-count">([^<]*)</span>', shown) == [
        "Email", "Tag 1",
    ]
    grant_reviewee_visibility(rs)
    info = _info(client.get(f"/me/sessions/{rs.public_id}/results").text)
    assert "alice@example.edu" in info and "Tag 1: Blue" in info
    assert "Alice Reviewee" not in info and "Profile" not in info


def test_an_empty_save_shows_nothing_after_the_pill(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    rs = _session(client, db, "rei-empty")
    _alice(db, rs)
    assert _save(client, rs).status_code == 303
    db.refresh(rs)
    assert rs.reviewee_self_fields == []
    grant_reviewee_visibility(rs)
    assert "data-reviewee-self-info" not in client.get(
        f"/me/sessions/{rs.public_id}/results"
    ).text


def test_a_key_with_no_chip_survives_a_save(client: TestClient, db: Session) -> None:
    """The NULL default selects profile_link; with no profile in the
    roster the card offers no chip for it, so it rides as `keep`."""
    rs = _session(client, db, "rei-keep")
    _alice(db, rs, profile=None)
    html = client.get(f"/operator/sessions/{rs.public_id}/reviewees?unlocked=1").text
    assert '<input type="hidden" name="keep" value="profile_link">' in html
    assert _save(client, rs, fields=["name"], keep=["profile_link"]).status_code == 303
    db.refresh(rs)
    assert rs.reviewee_self_fields == ["name", "profile_link"]


def test_an_unknown_key_is_refused(client: TestClient, db: Session) -> None:
    rs = _session(client, db, "rei-unknown")
    # `email` is a reviewer key, not a reviewee one.
    assert _save(client, rs, fields=["name", "email"]).status_code == 422
    db.refresh(rs)
    assert rs.reviewee_self_fields is None


def test_a_locked_session_refuses_the_save(client: TestClient, db: Session) -> None:
    rs = _session(client, db, "rei-locked")
    rs.status = "ready"
    db.commit()
    assert _save(client, rs, fields=["name"]).status_code == 409
    db.refresh(rs)
    assert rs.reviewee_self_fields is None


def test_locked_the_readout_stays_and_the_card_goes(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "rei-locked-page")
    _alice(db, rs)
    rs.status = "ready"
    db.commit()
    html = client.get(f"/operator/sessions/{rs.public_id}/reviewees").text
    assert "Reviewees see:" in _div_at(html, "data-reviewee-self-readout")
    assert "data-reviewee-self-card" not in html


def test_a_save_leaves_a_validated_session_validated(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "rei-valid")
    rs.status = "validated"
    db.commit()
    assert _save(client, rs, fields=["name"]).status_code == 303
    db.refresh(rs)
    assert rs.status == "validated"


def test_a_tag_reads_under_the_reviewee_label(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    """The reviewee slot's label, not the reviewer slot's of the same name."""
    from app.db.models import User
    from app.services import field_labels

    rs = _session(client, db, "rei-label")
    _alice(db, rs)
    actor = db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()
    for source_type, label in (("reviewee", "Cohort"), ("reviewer", "Wrong")):
        field_labels.upsert(
            db, rs, source_type=source_type, source_field="tag_1",
            label=label, user=actor,
        )
    db.commit()
    assert _save(client, rs, fields=["name", "tag_1"]).status_code == 303
    shown = _div_at(
        client.get(f"/operator/sessions/{rs.public_id}/reviewees").text,
        "data-reviewee-self-readout",
    )
    assert re.findall(r'<span class="pill pill-count">([^<]*)</span>', shown) == [
        "Name", "Cohort",
    ]
    grant_reviewee_visibility(rs)
    info = _info(client.get(f"/me/sessions/{rs.public_id}/results").text)
    assert "Cohort: Blue" in info and "Wrong" not in info


def test_a_save_writes_one_audit_event(client: TestClient, db: Session) -> None:
    from app.db.models import AuditEvent

    rs = _session(client, db, "rei-audit")
    _save(client, rs, fields=["name"])
    _save(client, rs, fields=["name"])  # a no-op: nothing changed
    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == rs.id,
            AuditEvent.event_type == "session.reviewee_self_fields_set",
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].detail["changes"]["reviewee_self_fields"] == [None, ["name"]]


@pytest.mark.parametrize(
    ("stored", "cell"),
    [(None, ""), ([], "[]"), (["name", "tag_2"], '["name","tag_2"]')],
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

    source = _session(client, db, f"rei-csv-{len(cell)}")
    source.reviewee_self_fields = stored
    db.commit()
    row = next(
        r for r in _session_rows(source) if r[0] == "session.reviewee_self_fields"
    )
    assert row[1] == cell
    plan = _ParsedConfig()
    _apply_session_kv(plan, "session.reviewee_self_fields", row[1])
    target = SimpleNamespace(reviewee_self_fields=["name"])
    _apply_session_metadata(target, plan)
    assert target.reviewee_self_fields == stored


@pytest.mark.parametrize("cell", ['["name","email"]', '{"a":1}', "name"])
def test_the_settings_csv_refuses_a_bad_selection(cell: str) -> None:
    from app.services.session_config_io._apply_session import _apply_session_kv
    from app.services.session_config_io._apply_shared import (
        _ParseError,
        _ParsedConfig,
    )

    with pytest.raises(_ParseError):
        _apply_session_kv(_ParsedConfig(), "session.reviewee_self_fields", cell)
