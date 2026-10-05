"""Route-layer coverage for the Display Fields Sort column —
Segment 13B PR 2.

Pins:

- The bulk-save POST parses parallel
  ``sort_display_field_id`` + ``sort_dir`` arrays and persists
  via ``instruments.set_sort_display_fields``.
- Validator rejections (over-cap / unknown direction /
  misaligned arrays) redirect with ``sort_save_error`` and
  ``sort_save_error_instrument_id`` query parameters, or answer 422
  JSON on the consolidated save. An id that is not this instrument's is dropped, not
  rejected (findings A24).
- Empty arrays clear the spec back to the unsorted default.

The PR 1 tests already cover the service-layer behaviour
end-to-end; this file is the small route-shaped surface tied
to the operator UI.
"""
from __future__ import annotations

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


def test_rejected_sort_spec_renders_the_error_banner(
    db: Session, client: TestClient
) -> None:
    """The redirect target shows the rejection: a page reached with the
    flash params renders the banner, with a Cancel back to the card in
    edit mode; the same page without them renders none."""
    review_session = _make_session(client, db, code="dfsort-banner")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session)
    f1, _ = _seed_display_fields_via_get(client, review_session) or _lookup_two_display_fields(db, instrument)
    form = _bulk_save_form(instrument)
    form["sort_display_field_id"] = [str(f1.id)]
    form["sort_dir"] = []
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments"
        f"/{instrument.id}/fields/save",
        data=form,
        follow_redirects=False,
    )
    assert response.status_code == 303
    body = client.get(response.headers["location"]).text
    assert 'id="sort-save-error-banner"' in body
    assert "Could not save the sort order:</strong> Sort spec arrays misaligned." in body
    assert (
        f'href="/operator/sessions/{review_session.id}/instruments'
        f'?editing={instrument.id}#instrument-{instrument.id}">Cancel</a>'
    ) in body
    assert '<div class="banner-actions">' in _banner(body, "sort-save-error-banner")

    clean = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
        f"?editing={instrument.id}"
    ).text
    assert 'id="sort-save-error-banner"' not in clean


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


# ─────────────────────────────────────────────────────────────────
# Segment 18R Item 2 PR 3 — consolidated Save route (JSON /save)
# ─────────────────────────────────────────────────────────────────


def test_consolidated_save_returns_ok_json_and_persists(
    db: Session, client: TestClient
) -> None:
    """The JSON ``/save`` twin of ``/fields/save`` applies the same
    payload and returns ``{"ok": true}`` (200) — no redirect. Persists
    the sort spec so the client can stay unlocked with no reload."""
    review_session = _make_session(client, db, code="save-json-ok")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session)
    f1, _ = _seed_display_fields_via_get(client, review_session) or _lookup_two_display_fields(db, instrument)
    form = _bulk_save_form(instrument)
    form["sort_display_field_id"] = [str(f1.id)]
    form["sort_dir"] = ["asc"]
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments"
        f"/{instrument.id}/save",
        data=form,
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    db.refresh(instrument)
    assert instrument.sort_display_fields == [
        {"display_field_id": f1.id, "dir": "asc"}
    ]


def test_consolidated_save_drops_a_sort_key_whose_field_was_deleted(
    db: Session, client: TestClient
) -> None:
    """The card posts the stored sort spec back. Once a display field
    it names is deleted, the save drops that key and succeeds, where it
    used to answer 422 until a sort click rebuilt the inputs
    (``spec/sort_by_reviewee.md`` "Cascade behaviour"; findings A24)."""
    review_session = _make_session(client, db, code="save-json-stale")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session)
    f1, f2 = _seed_display_fields_via_get(client, review_session) or _lookup_two_display_fields(db, instrument)
    stale_id = f1.id
    db.delete(f1)
    db.commit()
    form = _bulk_save_form(instrument)
    form["sort_display_field_id"] = [str(stale_id), str(f2.id)]
    form["sort_dir"] = ["asc", "desc"]
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments"
        f"/{instrument.id}/save",
        data=form,
        follow_redirects=False,
    )
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    db.refresh(instrument)
    assert instrument.sort_display_fields == [
        {"display_field_id": f2.id, "dir": "desc"}
    ]


def test_consolidated_save_misaligned_returns_422_json(
    db: Session, client: TestClient
) -> None:
    """A validation failure returns ``{"ok": false, "errors": [...]}``
    (422) instead of a 303 redirect — the client renders the summary
    banner from ``errors`` and keeps the operator's edits."""
    review_session = _make_session(client, db, code="save-json-misalign")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session)
    f1, _ = _seed_display_fields_via_get(client, review_session) or _lookup_two_display_fields(db, instrument)
    form = _bulk_save_form(instrument)
    form["sort_display_field_id"] = [str(f1.id)]
    form["sort_dir"] = []  # misaligned arrays
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments"
        f"/{instrument.id}/save",
        data=form,
        follow_redirects=False,
    )
    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert any("misaligned" in e for e in body["errors"])


def test_consolidated_save_over_cap_returns_422_json(
    db: Session, client: TestClient
) -> None:
    """A service-level SortSpecError (sort over the 3-field cap)
    surfaces as a JSON error, not a redirect."""
    review_session = _make_session(client, db, code="save-json-cap")
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
        f"/{instrument.id}/save",
        data=form,
        follow_redirects=False,
    )
    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert any("maximum" in e for e in body["errors"])


def _banner(body: str, banner_id: str) -> str:
    """The banner's markup, from its id to its closing ``</div>``."""
    start = body.index(f'id="{banner_id}"')
    return body[start : body.index("</div>\n    </div>", start)]


def test_instruments_error_banners_use_the_banner_actions_row(
    db: Session, client: TestClient
) -> None:
    """Both Instruments error banners put Cancel in ``.banner-actions``
    rather than an inline flex row (findings Ec5, 2026-10-05)."""
    review_session = _make_session(client, db, code="dfsort-banner-row")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
        "?rf_save_error=Boom"
    ).text
    banner = _banner(body, "rf-save-error-banner")
    assert "<strong>Could not save:</strong> Boom" in banner
    assert '<div class="banner-actions">' in banner
    assert "display: flex" not in banner
