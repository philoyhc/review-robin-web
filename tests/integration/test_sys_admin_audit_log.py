"""Coverage for the Sys Admin audit-log child page — Segment 16C PR 1.

Mirrors the Outbox child-page tests under
``test_sys_admin_outbox_child.py`` — same chrome / back-link /
gate convention.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


# --- Gate ------------------------------------------------------------------


def test_audit_log_page_403_for_non_admin(
    db: Session,
    client: TestClient,
) -> None:
    """Plain operator (creator of the session, but no sys-admin
    role) cannot reach the audit-log child page — the gate is
    require_sys_admin."""
    review_session = _make_session(client, db, code="audit-page-403")
    response = client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log",
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_audit_log_page_renders_for_sys_admin(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="audit-page-200")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
    )
    assert response.status_code == 200
    # Chrome conventions: back-link + Admin nav + audit-log section
    # heading + Download CSV affordance.
    assert "Back to Sessions Diagnostics" in response.text
    assert "<h1>Admin</h1>" in response.text
    assert "Sessions Diagnostics" in response.text  # tab strip
    assert f"Audit log — {review_session.name}" in response.text
    assert (
        f'href="/operator/sessions/{review_session.id}/export/audit_log.csv"'
        in response.text
    )
    assert "Download CSV" in response.text


def test_audit_log_page_404s_on_missing_session(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    bob_client = make_client(bob)
    response = bob_client.get(
        "/operator/sys-admin/sessions/99999/audit-log",
        follow_redirects=False,
    )
    assert response.status_code == 404


# --- Content + columns -----------------------------------------------------


def test_audit_log_page_renders_seeded_events(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The session creation flow emits a ``session.created`` audit
    event. The child page should render that row + the 8 column
    headers."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="audit-seeded")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
    )
    body = response.text
    # All 8 column headers present.
    for header in (
        "Event",
        "Severity",
        "Summary",
        "Actor",
        "Correlation",
        "When",
        "Detail",
    ):
        assert f">{header}<" in body
    # session.created emits during _make_session; should appear.
    assert "session.created" in body
    assert "alice@example.edu" in body


# --- Pagination ------------------------------------------------------------


def test_audit_log_page_renders_next_link_when_page_fills(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the table has more events than the page size (50),
    the "Older events →" anchor renders, carrying the last row's
    id as the cursor."""
    from app.services import audit

    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="audit-page-fill")
    # Seed 55 extra info events so page 1 of 50 fills and there's
    # leftover. Each emits a canonical envelope.
    for i in range(55):
        audit.write_event(
            db,
            event_type="session.activated",
            summary=f"seed {i}",
            session=review_session,
            payload=audit.counts(i=i),
        )

    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
    )
    assert response.status_code == 200
    body = response.text
    assert "Older events" in body
    # Anchor encodes a cursor.
    assert "?cursor=" in body


def test_audit_log_pagination_round_trip(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Page 2 follows ``?cursor=<id>``; its top row is strictly
    older (lower id) than page 1's bottom row."""
    from app.services import audit

    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="audit-page-rt")
    for i in range(60):
        audit.write_event(
            db,
            event_type="session.activated",
            summary=f"rt seed {i}",
            session=review_session,
            payload=audit.counts(i=i),
        )

    bob_client = make_client(bob)
    page1 = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
    )
    assert page1.status_code == 200
    # Pull the cursor out of the rendered next-page anchor.
    import re

    match = re.search(r"\?cursor=(\d+)", page1.text)
    assert match is not None, "Page 1 should advertise a cursor"
    cursor = int(match.group(1))

    page2 = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}"
        f"/audit-log?cursor={cursor}"
    )
    assert page2.status_code == 200
    # Page 2 should contain events older than the cursor; the
    # specific ``rt seed 0`` row sits near the bottom of the
    # full set and lands on page 2 with 60 seeds (5 leftover) +
    # one creator row.
    assert "rt seed 0" in page2.text
    assert "rt seed 0" not in page1.text


def test_audit_log_page_no_events_renders_empty_copy(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Past a cursor that exhausts the table the page renders
    "No audit events ... older than the requested cursor"."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="audit-empty-cursor")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}"
        f"/audit-log?cursor=1"
    )
    assert response.status_code == 200
    assert "older than the requested cursor" in response.text


# --- Diagnostics row link migration ---------------------------------------


def test_diagnostics_row_audit_log_link_points_at_child_page(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The per-row Audit log affordance on Sessions Diagnostics
    now opens the child viewer rather than streaming the CSV
    directly."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="audit-row-link")
    response = client.get("/operator/sys-admin/sessions")
    assert response.status_code == 200
    assert (
        f'href="/operator/sys-admin/sessions/{review_session.id}/audit-log">Audit log</a>'
        in response.text
    )
    # The old direct-CSV link no longer renders.
    assert (
        f"/operator/sessions/{review_session.id}/export/audit_log.csv"
        not in response.text
    )


# --- Filter strip (Segment 16C PR 2) ---------------------------------------


def _seed_mixed_events(db, review_session, *, n_info=3, n_warn=2) -> None:
    """Drop a few events of mixed severity onto the session so
    filter-narrowing has something to bite on."""
    from app.services import audit

    for i in range(n_info):
        audit.write_event(
            db,
            event_type="session.activated",
            summary=f"info {i}",
            session=review_session,
            payload=audit.counts(i=i),
        )
    for i in range(n_warn):
        audit.write_event(
            db,
            event_type="session.invalidated",
            summary=f"warn {i}",
            session=review_session,
            severity="warning",
            reason="setup_mutation",
        )


def test_audit_log_filter_strip_renders(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The filter form renders with event-type multiselect,
    severity checkboxes, actor typeahead, and date inputs."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="filter-render")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
    )
    assert response.status_code == 200
    body = response.text
    assert 'name="event_type"' in body
    assert 'name="severity"' in body
    assert 'name="actor"' in body
    assert 'name="from"' in body
    assert 'name="to"' in body
    # No "Clear filters" link when no filter is active.
    assert "Clear filters" not in body


def test_audit_log_filter_by_event_type_narrows_table(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="filter-event-type")
    _seed_mixed_events(db, review_session)
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
        "?event_type=session.activated"
    )
    assert response.status_code == 200
    body = response.text
    # Event-type column wraps in <code>; the filter form's
    # <option> elements also embed the event-type strings, so
    # assert against the table-row shape rather than substring.
    assert "<code>session.activated</code>" in body
    assert "<code>session.invalidated</code>" not in body
    assert "<code>session.created</code>" not in body
    # Filter strip persists state — option marked selected.
    assert 'value="session.activated" selected' in body
    # "Clear filters" link shows up when a filter is active.
    assert "Clear filters" in body


def test_audit_log_filter_by_severity_narrows_table(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="filter-severity")
    _seed_mixed_events(db, review_session)
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
        "?severity=warning"
    )
    assert response.status_code == 200
    body = response.text
    # Only warn rows should be present.
    assert "warn 0" in body
    assert "info 0" not in body
    # Severity checkbox marked checked.
    assert 'value="warning" checked' in body


def test_audit_log_filter_by_actor_narrows_table(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filtering by an actor email that exists yields rows; an
    unknown actor yields an empty table."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="filter-actor")
    bob_client = make_client(bob)
    # Alice is the session creator → on session.created rows.
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
        "?actor=alice@example.edu"
    )
    assert response.status_code == 200
    assert "session.created" in response.text

    # Unknown actor → empty.
    empty = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
        "?actor=ghost@example.edu"
    )
    assert empty.status_code == 200
    assert "match the current filter" in empty.text


def test_audit_log_combined_filters_and_together(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``event_type=session.activated&severity=warning`` returns no
    rows because activated rows are info."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="filter-combined")
    _seed_mixed_events(db, review_session)
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
        "?event_type=session.activated&severity=warning"
    )
    assert response.status_code == 200
    assert "info 0" not in response.text
    assert "warn 0" not in response.text


def test_audit_log_download_button_carries_filter_query_string(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Download CSV button rewrites to include the current
    filter state so the spreadsheet honours the same filters."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="filter-csv-link")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
        "?event_type=session.activated&severity=info"
    )
    assert response.status_code == 200
    body = response.text
    # The Download CSV anchor should embed both filter slots.
    assert (
        f'href="/operator/sessions/{review_session.id}/export/audit_log.csv'
        "?event_type=session.activated&amp;severity=info" in body
    )


def test_audit_log_csv_route_honours_filters(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CSV download narrows rows when filter params land on the
    route."""
    import csv
    import io

    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="filter-csv-rows")
    _seed_mixed_events(db, review_session)
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}/export/audit_log.csv"
        "?event_type=session.activated"
    )
    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.text)))
    # Header + only the activated rows.
    event_types = [r[0] for r in rows[1:]]
    assert event_types and all(et == "session.activated" for et in event_types)


def test_audit_log_csv_emits_context_slot_on_filtered_extract(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``session.audit_log_extracted`` carries the filter set
    in its ``context`` slot when filters are active. Unfiltered
    extracts emit no ``context``."""
    from app.db.models import AuditEvent
    from sqlalchemy import select

    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="filter-csv-audit")
    bob_client = make_client(bob)
    # Filtered hit.
    bob_client.get(
        f"/operator/sessions/{review_session.id}/export/audit_log.csv"
        "?event_type=session.activated&severity=info"
    )

    db.expire_all()
    events = (
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.event_type == "session.audit_log_extracted")
            .where(AuditEvent.session_id == review_session.id)
            .order_by(AuditEvent.id)
        )
        .scalars()
        .all()
    )
    assert events, "filtered extract should emit an audit event"
    last_detail = events[-1].detail
    assert "context" in last_detail, last_detail
    assert last_detail["context"]["event_types"] == "session.activated"
    assert last_detail["context"]["severities"] == "info"


def test_audit_log_csv_no_context_on_unfiltered_extract(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unfiltered CSV extract emits the canonical audit event
    without a ``context`` slot."""
    from app.db.models import AuditEvent
    from sqlalchemy import select

    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="filter-csv-noctx")
    bob_client = make_client(bob)
    bob_client.get(
        f"/operator/sessions/{review_session.id}/export/audit_log.csv"
    )
    db.expire_all()
    event = (
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.event_type == "session.audit_log_extracted")
            .where(AuditEvent.session_id == review_session.id)
        )
        .scalars()
        .one()
    )
    assert "context" not in event.detail


def test_audit_log_filter_url_param_round_trip(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """URL params round-trip into rendered filter state — selected
    options + value attributes match the submitted query string."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="filter-rt")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
        "?event_type=session.activated"
        "&severity=info&severity=warning"
        "&actor=alice@example.edu"
        "&from=2026-01-01&to=2026-12-31"
    )
    assert response.status_code == 200
    body = response.text
    assert 'value="session.activated" selected' in body
    assert 'value="info" checked' in body
    assert 'value="warning" checked' in body
    assert 'id="filter-actor"' in body
    assert 'value="alice@example.edu"' in body
    assert 'value="2026-01-01"' in body
    assert 'value="2026-12-31"' in body


def test_audit_log_filter_invalid_date_422s(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed ``?from=`` bookmark returns 422 rather than
    silently ignoring — surfaces the typo to the operator."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="filter-bad-date")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
        "?from=2026-13-99"
    )
    assert response.status_code == 422


def test_audit_log_filter_unknown_event_type_silently_dropped(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown event-type tokens silently drop — the operator
    can't filter on types that don't exist, and propagating a
    400 here would be a UX papercut on a stale bookmark."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="filter-unknown-et")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
        "?event_type=does.not.exist"
    )
    assert response.status_code == 200
    # No "Clear filters" since the filter parsed empty.
    assert "Clear filters" not in response.text


def test_audit_log_pagination_carries_filter_state(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Older events → anchor preserves the filter query string so
    subsequent pages stay narrowed."""
    from app.services import audit

    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="filter-page-state")
    for i in range(55):
        audit.write_event(
            db,
            event_type="session.activated",
            summary=f"page {i}",
            session=review_session,
            payload=audit.counts(i=i),
        )
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
        "?event_type=session.activated"
    )
    assert response.status_code == 200
    body = response.text
    # The pagination anchor carries both the cursor and the
    # event-type filter forward.
    assert "?cursor=" in body
    assert "event_type=session.activated" in body


# --- Detail-JSON pretty-printer (Segment 16C PR 3) -------------------------


def test_format_audit_detail_changes_envelope() -> None:
    from app.web.views import format_audit_detail

    render = format_audit_detail(
        "session.updated",
        {
            "session_id": 17,
            "session_code": "CS101",
            "changes": {"name": ["Spring", "Spring v2"]},
        },
    )
    assert not render.is_empty
    [section] = render.sections
    assert section.kind == "changes"
    assert section.label == "Changes"
    [change] = section.change_rows
    assert change.label == "name"
    assert change.before == "Spring"
    assert change.after == "Spring v2"


def test_format_audit_detail_snapshot_envelope() -> None:
    from app.web.views import format_audit_detail

    render = format_audit_detail(
        "session.created",
        {
            "session_id": 17,
            "session_code": "CS101",
            "snapshot": {"name": "Final Review", "code": "CS101"},
        },
    )
    [section] = render.sections
    assert section.kind == "snapshot"
    assert section.label == "Snapshot"
    rows = {kv.label: kv.value for kv in section.kv_rows}
    assert rows == {"name": "Final Review", "code": "CS101"}


def test_format_audit_detail_counts_envelope() -> None:
    from app.web.views import format_audit_detail

    render = format_audit_detail(
        "assignments.generated",
        {
            "session_id": 17,
            "session_code": "CS101",
            "counts": {"assignments": 104, "pairs": 13},
        },
    )
    [section] = render.sections
    assert section.kind == "counts"
    rows = {kv.label: kv.value for kv in section.kv_rows}
    assert rows == {"assignments": "104", "pairs": "13"}


def test_format_audit_detail_set_changes_envelope() -> None:
    from app.web.views import format_audit_detail

    render = format_audit_detail(
        "instrument.display_fields_saved",
        {
            "session_id": 17,
            "session_code": "CS101",
            "set_changes": {
                "added": [{"field": "rating"}],
                "removed": [],
                "updated": [{"field": "comments"}],
            },
            "refs": {"instrument_id": 7},
        },
    )
    payload = render.sections[0]
    assert payload.kind == "set_changes"
    assert payload.set_changes is not None
    assert payload.set_changes.added == ['{"field":"rating"}']
    assert payload.set_changes.removed == []
    assert payload.set_changes.updated == ['{"field":"comments"}']
    # Refs renders as its own section after the payload.
    refs = render.sections[1]
    assert refs.kind == "refs"
    [kv] = refs.kv_rows
    assert kv.label == "instrument_id"
    assert kv.value == "7"


def test_format_audit_detail_reason_orthogonal_slot() -> None:
    from app.web.views import format_audit_detail

    render = format_audit_detail(
        "session.invalidated",
        {
            "session_id": 17,
            "session_code": "CS101",
            "reason": "setup_mutation",
        },
    )
    [section] = render.sections
    assert section.kind == "reason"
    assert section.text == "setup_mutation"


def test_format_audit_detail_context_orthogonal_slot() -> None:
    from app.web.views import format_audit_detail

    render = format_audit_detail(
        "session.audit_log_extracted",
        {
            "session_id": 17,
            "session_code": "CS101",
            "counts": {"rows": 12},
            "context": {"event_types": "session.activated"},
        },
    )
    kinds = [s.kind for s in render.sections]
    assert "counts" in kinds
    assert "context" in kinds


def test_format_audit_detail_legacy_pre11k_falls_through_to_fallback() -> None:
    """Legacy rows from before the canonical envelope landed
    (Segment 11K, 2026-05-07) don't carry any recognised key.
    They should render under a generic "Detail" section rather
    than crashing or rendering blank."""
    from app.web.views import format_audit_detail

    render = format_audit_detail(
        "legacy.thing",
        {"some_legacy_key": "value", "instrument_id_inlined": 7},
    )
    [section] = render.sections
    assert section.kind == "fallback"
    # Unrecognised top-level keys fall under "Other".
    assert section.label == "Other"
    labels = {kv.label for kv in section.kv_rows}
    assert labels == {"some_legacy_key", "instrument_id_inlined"}


def test_format_audit_detail_empty_returns_empty_render() -> None:
    from app.web.views import format_audit_detail

    render = format_audit_detail("some.event", None)
    assert render.is_empty
    assert render.sections == ()
    assert render.raw_json == ""


def test_audit_log_page_renders_expander_with_structured_detail(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The page renders a <details> expander per row, with the
    pretty-printed sections inside."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="audit-detail-render")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
    )
    assert response.status_code == 200
    body = response.text
    # Each row owns a "Show detail" expander.
    assert ">Show detail<" in body
    # And a nested "Raw JSON" expander.
    assert ">Raw JSON<" in body
    # session.created emits a snapshot envelope; the section
    # heading should be present.
    assert "Snapshot" in body

