"""Integration coverage for Segment 12A-3 PR 4 — Quick Setup
Settings slot graduation.

PR 4 flips the Settings slot (slot 4 in the post-15D layout)
to live, pointing at PR 3's ``POST /import-config`` route. The
slot consumes a Settings CSV (the 3-column ``field,value,
data_type`` shape 12A-1 produces) and rehydrates the session
into the same shape via ``apply_session_config``.

The submit-all chain runs reviewers → reviewees →
relationships → settings; the create-session handler dispatches
the same per-slot pipeline when uploads are staged on the new-
session page.
"""

from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Instrument,
    ReviewSession,
)
from app.web import views


REVIEWER_CSV = b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n"
REVIEWEE_CSV = b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n"


def _settings_csv(rows: list[tuple[str, str, str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(("field", "value", "data_type"))
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "QSCfg", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


# --------------------------------------------------------------------------- #
# View-shape tests
# --------------------------------------------------------------------------- #


def test_quick_setup_settings_slot_is_wired_live(
    client: TestClient, db: Session
) -> None:
    """Slot 4 (Settings) graduates to live in 12A-3 PR 4 with
    ``wire_url`` pointing at the import-config route shipped in
    PR 3."""

    review_session = _make_session(client, db, code="qsc-wire")
    context = views.build_quick_setup_context(db, review_session)
    by_key = {slot.key: slot for slot in context.slots}
    assert by_key["settings"].is_wired is True
    assert by_key["settings"].wire_url == (
        f"/operator/sessions/{review_session.id}/import-config"
    )
    assert by_key["settings"].coming_in is None


def test_new_session_quick_setup_settings_slot_is_wired(
    db: Session,
) -> None:
    """The Create-New-Session variant of Quick Setup also wires
    the Settings slot — its file input associates with the
    create-session form via ``form="..."`` so the upload rides
    along with the session-creation POST."""

    from app.db.models import User

    user = User(email="newsess-cfg@example.edu", display_name="N")
    db.add(user)
    db.flush()
    context = views.build_new_session_quick_setup_context(db, user)
    by_key = {slot.key: slot for slot in context.slots}
    assert by_key["settings"].is_wired is True
    assert by_key["settings"].coming_in is None


# --------------------------------------------------------------------------- #
# Per-slot route
# --------------------------------------------------------------------------- #


def test_import_config_route_via_quick_setup_slot(
    client: TestClient, db: Session
) -> None:
    """The Settings slot's file input posts directly to
    ``/import-config`` (per its ``wire_url``). Verify the route
    accepts the multipart upload and rehydrates the session."""

    review_session = _make_session(client, db, code="qsc-route")
    payload = _settings_csv(
        [
            ("instruments[1].name", "Eval", "string"),
        ]
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/import-config",
        files={"file": ("config.csv", payload, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "config_imported=ok" in response.headers["location"]
    instruments = (
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        )
        .scalars()
        .all()
    )
    assert [i.name for i in instruments] == ["Eval"]


# --------------------------------------------------------------------------- #
# Submit-all chain
# --------------------------------------------------------------------------- #


def test_submit_all_runs_settings_after_rosters_and_relationships(
    client: TestClient, db: Session
) -> None:
    """Chain order: reviewers → reviewees → relationships →
    settings. A submit-all POST with all four files runs them in
    sequence and last_fragment lands on the Settings slot."""

    review_session = _make_session(client, db, code="qsc-chain")
    settings_payload = _settings_csv(
        [
            ("instruments[1].name", "Eval", "string"),
        ]
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/submit-all",
        files={
            "reviewers_file": ("r.csv", REVIEWER_CSV, "text/csv"),
            "reviewees_file": ("e.csv", REVIEWEE_CSV, "text/csv"),
            "settings_file": (
                "config.csv",
                settings_payload,
                "text/csv",
            ),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    # Last fragment is the settings slot since it's the final
    # step in the chain.
    assert response.headers["location"].endswith("#quick-setup-settings")
    instruments = (
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        )
        .scalars()
        .all()
    )
    assert [i.name for i in instruments] == ["Eval"]


def test_submit_all_settings_parse_error_surfaces_in_settings_slot(
    client: TestClient, db: Session
) -> None:
    """A malformed Settings CSV in the submit-all chain redirects
    with the settings slot's error scope."""

    review_session = _make_session(client, db, code="qsc-err")
    bad_payload = _settings_csv(
        [
            # Missing required ``instruments[1].name`` ⇒ cross-row error.
            ("instruments[1].short_label", "X", "string"),
        ]
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/submit-all",
        files={"settings_file": ("c.csv", bad_payload, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "quick_setup_error=settings" in location
    assert "quick_setup_reason=parse" in location


# --------------------------------------------------------------------------- #
# Create New Session dispatch
# --------------------------------------------------------------------------- #


def test_create_session_with_settings_file_processes_upload(
    client: TestClient, db: Session
) -> None:
    """POST /operator/sessions with reviewers + reviewees +
    settings files dispatches all through the same pipeline.
    The new session is created first, then the Settings CSV
    rehydrates instruments and other config."""

    settings_payload = _settings_csv(
        [
            ("instruments[1].name", "MidEval", "string"),
        ]
    )
    response = client.post(
        "/operator/sessions",
        data={
            "name": "NewQSCfg",
            "code": "qsc-newsess",
            "description": "d",
        },
        files={
            "reviewers_file": ("r.csv", REVIEWER_CSV, "text/csv"),
            "reviewees_file": ("e.csv", REVIEWEE_CSV, "text/csv"),
            "settings_file": (
                "config.csv",
                settings_payload,
                "text/csv",
            ),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "qsc-newsess")
    ).scalar_one()
    instruments = (
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        )
        .scalars()
        .all()
    )
    assert [i.name for i in instruments] == ["MidEval"]
    # Audit event is emitted as part of the apply.
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.settings_imported",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    assert event.detail.get("counts", {}).get("instruments") == 1


# --------------------------------------------------------------------------- #
# Card markup
# --------------------------------------------------------------------------- #


def test_quick_setup_card_renders_settings_slot_live(
    client: TestClient, db: Session
) -> None:
    """The Settings slot renders as a live file input (not the
    inert ``disabled`` shape) and uses the ``settings_file``
    form-field name."""

    review_session = _make_session(client, db, code="qsc-render")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    assert 'id="quick-setup-settings"' in body
    assert "Session settings" in body
    # File-upload control under the live name.
    assert 'name="settings_file"' in body
