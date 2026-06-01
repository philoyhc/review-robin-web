"""Integration coverage for the Observers extract — closes the
Extract Setup leg of L2 from ``guide/participant_model_remainder.md``.

Asserts the per-row export route + the bundle inclusion when the
session's ``observers_enabled`` toggle is on, and the Extract
Setup card surfaces the Observers row in the right column when
the toggle's on (collapsing back to the original 3-row shape
when off).
"""

from __future__ import annotations

import csv
import io
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession
from app.web import views


OBSERVER_CSV = (
    b"ObserverName,ObserverEmail,ObserverTag1\n"
    b"Oren,oren@example.edu,Mentor\n"
)


def _make_session(
    client: TestClient,
    db: Session,
    *,
    code: str,
    observers_enabled: bool = True,
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Obs", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    review_session.observers_enabled = observers_enabled
    db.commit()
    return review_session


def _seed_observers(
    client: TestClient, review_session: ReviewSession
) -> None:
    client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/observers",
        files={"file": ("obs.csv", OBSERVER_CSV, "text/csv")},
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# Extract Setup card view shape
# ---------------------------------------------------------------------------


def test_extract_setup_card_renders_observers_row_only_when_toggle_on(
    client: TestClient, db: Session
) -> None:
    """The Observers row sits between Relationships and Session
    settings in the right column when ``observers_enabled``;
    drops out when off."""
    rs_off = _make_session(
        client, db, code="ext-obs-off", observers_enabled=False
    )
    context_off = views.build_extract_data_context(db, rs_off)
    assert [r.key for r in context_off.col_two] == [
        "relationships",
        "settings",
    ]
    assert all(r.key != "observers" for r in context_off.rows)

    rs_on = _make_session(client, db, code="ext-obs-on")
    context_on = views.build_extract_data_context(db, rs_on)
    assert [r.key for r in context_on.col_two] == [
        "relationships",
        "observers",
        "settings",
    ]
    by_key = {r.key: r for r in context_on.rows}
    # 0 observers seeded yet — row stays grey (no download URL).
    assert by_key["observers"].count == 0
    assert by_key["observers"].is_wired is False


def test_observers_row_lights_up_after_population(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ext-obs-live")
    _seed_observers(client, review_session)

    context = views.build_extract_data_context(db, review_session)
    by_key = {r.key: r for r in context.rows}
    assert by_key["observers"].count == 1
    assert by_key["observers"].is_wired is True
    assert by_key["observers"].download_url == (
        f"/operator/sessions/{review_session.id}/export/observers.csv"
    )


def test_zip_all_count_summary_reflects_observers_toggle(
    client: TestClient, db: Session
) -> None:
    """The Zip-all row's count-summary copy includes 5 setup CSVs
    when observers_enabled, 4 when off."""
    rs_off = _make_session(
        client, db, code="ext-obs-zip-off", observers_enabled=False
    )
    rs_on = _make_session(client, db, code="ext-obs-zip-on")
    assert "4 setup CSVs" in (
        views.build_extract_data_context(db, rs_off).bundle.count_summary
    )
    assert "5 setup CSVs" in (
        views.build_extract_data_context(db, rs_on).bundle.count_summary
    )


# ---------------------------------------------------------------------------
# Per-row export route
# ---------------------------------------------------------------------------


def test_export_observers_csv_round_trips_uploaded_row(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ext-obs-csv")
    _seed_observers(client, review_session)

    response = client.get(
        f"/operator/sessions/{review_session.id}/export/observers.csv"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        f'filename="{review_session.code}_observers.csv"'
        in response.headers["content-disposition"]
    )

    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == [
        "ObserverEmail",
        "ObserverName",
        "ObserverTag1",
        "Status",
    ]
    assert rows[1][0] == "oren@example.edu"
    assert rows[1][1] == "Oren"
    assert rows[1][2] == "Mentor"
    assert rows[1][3] == "active"

    # Audit event emitted.
    ext_events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.observers_extracted"
        )
    ).scalars().all()
    assert len(ext_events) == 1


# ---------------------------------------------------------------------------
# Setup-bundle inclusion
# ---------------------------------------------------------------------------


def test_setup_bundle_includes_observers_when_toggle_on(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ext-obs-bundle")
    _seed_observers(client, review_session)

    response = client.get(
        f"/operator/sessions/{review_session.id}/export/bundle.zip"
    )
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert (
        f"{review_session.code}_observers.csv" in archive.namelist()
    )


def test_setup_bundle_omits_observers_when_toggle_off(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(
        client, db, code="ext-obs-bundle-off", observers_enabled=False
    )

    response = client.get(
        f"/operator/sessions/{review_session.id}/export/bundle.zip"
    )
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert all(
        "observers" not in name for name in archive.namelist()
    )
