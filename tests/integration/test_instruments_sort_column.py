"""Route-layer coverage for the Display Fields Sort column —
Segment 13B PR 2.

Pins:

- The Sort column header + per-row Sort cell render on the
  per-instrument editing surface.
- The bulk-save POST parses parallel
  ``sort_display_field_id`` + ``sort_dir`` arrays and persists
  via ``instruments.set_sort_display_fields``.
- Validator rejections (over-cap / unknown direction /
  duplicates / cross-instrument id) surface as a per-instrument
  banner via the redirect.
- Empty arrays clear the spec back to the unsorted default.

The PR 1 tests already cover the service-layer behaviour
end-to-end; this file is the small route-shaped surface tied
to the operator UI.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentDisplayField,
    ReviewSession,
)


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


def _instrument(db: Session, review_session: ReviewSession) -> Instrument:
    return db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()


def _populate_rosters(client: TestClient, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nR,r@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    # Populate Tag1 + Tag2 so the matching reviewee display
    # fields survive ``prune_unpopulated_display_fields`` on
    # every subsequent GET — without them, the seeded tag_1 /
    # tag_2 display fields silently disappear before the page
    # renders.
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail,RevieweeTag1,RevieweeTag2\n"
                b"A,a@example.edu,t1,t2\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )


def _lookup_two_display_fields(
    db: Session, instrument: Instrument
) -> tuple[InstrumentDisplayField, InstrumentDisplayField]:
    """``_populate_rosters`` imports reviewees with Tag1 + Tag2
    columns; ``seed_display_fields_from_reviewees`` auto-creates
    the matching display fields on the default instrument. This
    helper looks them up so tests can reference real, populated,
    won't-be-pruned display fields without recreating them."""
    # Trigger a GET so the auto-seeding side effects run.
    return (
        db.execute(
            select(InstrumentDisplayField)
            .where(InstrumentDisplayField.instrument_id == instrument.id)
            .where(InstrumentDisplayField.source_field == "tag_1")
        ).scalar_one(),
        db.execute(
            select(InstrumentDisplayField)
            .where(InstrumentDisplayField.instrument_id == instrument.id)
            .where(InstrumentDisplayField.source_field == "tag_2")
        ).scalar_one(),
    )


def _seed_display_fields_via_get(
    client: TestClient, review_session: ReviewSession
) -> None:
    """Trigger the lazy seed of the tag_1 / tag_2 display fields
    on the default instrument by hitting the Instruments page
    (which runs the seed inside the view builder)."""
    client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    )


def _bulk_save_form(
    instrument: Instrument,
) -> dict[str, list[str]]:
    """Construct the minimum form payload the bulk-save route
    expects — one row per existing display field + one row per
    existing response field, with the existing labels / order
    preserved. Returned as a dict-of-lists so httpx encodes the
    repeated keys correctly; callers can append sort entries
    by mutating the lists in place."""
    out: dict[str, list[str]] = {
        "kind": [],
        "id": [],
        "order": [],
        "label": [],
        "visible_ids": [],
        "required_ids": [],
        "help_text_id": [],
        "help_text": [],
        "help_text_visible_ids": [],
        "sort_display_field_id": [],
        "sort_dir": [],
    }
    for idx, df in enumerate(
        sorted(instrument.display_fields, key=lambda f: (f.order, f.id))
    ):
        out["kind"].append("display")
        out["id"].append(str(df.id))
        out["order"].append(str(idx))
        out["label"].append(df.label or "")
        if df.visible:
            out["visible_ids"].append(str(df.id))
    for idx, rf in enumerate(
        sorted(instrument.response_fields, key=lambda f: (f.order, f.id))
    ):
        out["kind"].append("response")
        out["id"].append(str(rf.id))
        out["order"].append(str(idx))
        out["label"].append(rf.label or "")
        if rf.required:
            out["required_ids"].append(str(rf.id))
        if rf.help_text is not None:
            out["help_text_id"].append(str(rf.id))
            out["help_text"].append(rf.help_text)
        if rf.help_text_visible:
            out["help_text_visible_ids"].append(str(rf.id))
    return out


def _query_param(url: str, name: str) -> str | None:
    qs = parse_qs(urlparse(url).query)
    values = qs.get(name) or []
    return values[0] if values else None


# --- Render --------------------------------------------------------------


def test_display_fields_table_renders_sort_column(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="dfsort-header")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session)
    response = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
        f"?editing={instrument.id}"
    )
    assert response.status_code == 200
    body = response.text
    # Header cell.
    assert "<th>Sort</th>" in body
    # At least one Sort button (locked rows still get one for
    # editing-mode display).
    assert 'class="sort-btn"' in body


def test_existing_sort_spec_renders_as_priority_badges(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="dfsort-badge")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session)
    f1, f2 = _seed_display_fields_via_get(client, review_session) or _lookup_two_display_fields(db, instrument)
    instrument.sort_display_fields = [
        {"display_field_id": f1.id, "dir": "asc"},
        {"display_field_id": f2.id, "dir": "desc"},
    ]
    db.commit()

    response = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
        f"?editing={instrument.id}"
    )
    body = response.text
    # Priority + arrow badges.
    assert "1↑" in body
    assert "2↓" in body
    # Hidden inputs in the slot for the existing spec.
    assert 'name="sort_display_field_id"' in body


# --- Bulk-save persistence -----------------------------------------------


def test_bulk_save_persists_sort_spec(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="dfsort-save")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session)
    f1, f2 = _seed_display_fields_via_get(client, review_session) or _lookup_two_display_fields(db, instrument)
    form = _bulk_save_form(instrument)
    form["sort_display_field_id"] = [str(f1.id), str(f2.id)]
    form["sort_dir"] = ["asc", "desc"]

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments"
        f"/{instrument.id}/fields/save",
        data=form,
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.expire_all()
    refreshed = db.execute(
        select(Instrument).where(Instrument.id == instrument.id)
    ).scalar_one()
    assert refreshed.sort_display_fields == [
        {"display_field_id": f1.id, "dir": "asc"},
        {"display_field_id": f2.id, "dir": "desc"},
    ]


def test_bulk_save_empty_sort_arrays_clear_the_spec(
    db: Session, client: TestClient
) -> None:
    """Submitting the bulk-save form with no
    ``sort_display_field_id`` inputs clears any previously-set
    spec back to the unsorted default."""
    review_session = _make_session(client, db, code="dfsort-clear")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session)
    f1, _ = _seed_display_fields_via_get(client, review_session) or _lookup_two_display_fields(db, instrument)
    instrument.sort_display_fields = [
        {"display_field_id": f1.id, "dir": "asc"}
    ]
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments"
        f"/{instrument.id}/fields/save",
        data=_bulk_save_form(instrument),
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.expire_all()
    refreshed = db.execute(
        select(Instrument).where(Instrument.id == instrument.id)
    ).scalar_one()
    assert refreshed.sort_display_fields == []


# --- Validation errors → banner ------------------------------------------


def test_bulk_save_misaligned_arrays_redirects_with_banner(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="dfsort-misalign")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session)
    f1, _ = _seed_display_fields_via_get(client, review_session) or _lookup_two_display_fields(db, instrument)
    form = _bulk_save_form(instrument)
    form["sort_display_field_id"] = [str(f1.id)]
    # No matching sort_dir → misaligned arrays.
    form["sort_dir"] = []
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments"
        f"/{instrument.id}/fields/save",
        data=form,
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert (
        _query_param(location, "sort_save_error_instrument_id")
        == str(instrument.id)
    )
    assert "misaligned" in (_query_param(location, "sort_save_error") or "")


def test_bulk_save_over_cap_redirects_with_banner(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="dfsort-cap")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session)
    f1, f2 = _seed_display_fields_via_get(client, review_session) or _lookup_two_display_fields(db, instrument)
    f3 = InstrumentDisplayField(
        instrument_id=instrument.id,
        source_type="reviewee",
        source_field="tag_3",
        label="Tag 3",
        order=max(df.order for df in instrument.display_fields) + 1,
        visible=True,
    )
    db.add(f3)
    db.commit()

    form = _bulk_save_form(instrument)
    form["sort_display_field_id"] = [
        str(f1.id), str(f2.id), str(f3.id), str(f1.id)
    ]
    form["sort_dir"] = ["asc", "asc", "asc", "desc"]
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments"
        f"/{instrument.id}/fields/save",
        data=form,
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    msg = _query_param(location, "sort_save_error") or ""
    assert "maximum is 3" in msg or "maximum" in msg


def test_bulk_save_unknown_dir_redirects_with_banner(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="dfsort-bad-dir")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session)
    f1, _ = _seed_display_fields_via_get(client, review_session) or _lookup_two_display_fields(db, instrument)
    form = _bulk_save_form(instrument)
    form["sort_display_field_id"] = [str(f1.id)]
    form["sort_dir"] = ["sideways"]
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments"
        f"/{instrument.id}/fields/save",
        data=form,
        follow_redirects=False,
    )
    assert response.status_code == 303
    msg = _query_param(response.headers["location"], "sort_save_error") or ""
    assert "sideways" in msg or "not one of" in msg


def test_sort_error_banner_renders_on_redirect_target(
    db: Session, client: TestClient
) -> None:
    """Following the redirect, the per-instrument card renders
    the error banner anchored to the offending instrument."""
    review_session = _make_session(client, db, code="dfsort-banner")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session)
    f1, _ = _seed_display_fields_via_get(client, review_session) or _lookup_two_display_fields(db, instrument)
    form = _bulk_save_form(instrument)
    form["sort_display_field_id"] = [str(f1.id)]
    form["sort_dir"] = ["sideways"]
    redirect = client.post(
        f"/operator/sessions/{review_session.id}/instruments"
        f"/{instrument.id}/fields/save",
        data=form,
        follow_redirects=False,
    )
    follow = client.get(redirect.headers["location"])
    assert follow.status_code == 200
    body = follow.text
    # Banner with the error message rendered as banner-error.
    assert "banner banner-error" in body
    assert re.search(r"sideways|not one of", body)
