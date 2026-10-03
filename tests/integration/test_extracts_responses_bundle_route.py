"""Integration tests for ``GET
/operator/sessions/{id}/export/responses_bundle.zip`` — the Extract
data tab's intro-card "Zip all".

D28 (author, 2026-10-03): the bundle is a pass-through of the other
cards. It always carries ``{code}_responses.csv``, the file Rehydrate
reads; each intro chip that is on adds exactly what that card's own
button downloads, as the card is configured, under the same name. The
tests below hold that by comparing bundle members to the cards' own
downloads byte for byte.
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
)


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "RespBundle", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    # A roster and an assignment on each instrument with no responses,
    # so ``all=0`` / ``all_rows=0`` have rows to drop and the
    # pass-through is observable.
    reviewer = Reviewer(
        session_id=review_session.id, name="Ann", email="ann@example.edu"
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Bo",
        email_or_identifier="bo@example.edu",
    )
    db.add_all(
        [
            reviewer,
            reviewee,
            Instrument(
                session_id=review_session.id,
                name="Second instrument",
                short_label="Second",
                order=2,
            ),
        ]
    )
    db.flush()
    for instrument_id in _instrument_ids(db, review_session):
        db.add(
            Assignment(
                session_id=review_session.id,
                reviewer_id=reviewer.id,
                reviewee_id=reviewee.id,
                instrument_id=instrument_id,
            )
        )
    db.commit()
    return review_session


def _instrument_ids(db: Session, review_session: ReviewSession) -> list[int]:
    return list(
        db.execute(
            select(Instrument.id)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )


def _bundle(
    client: TestClient, review_session: ReviewSession, query: str = ""
) -> zipfile.ZipFile:
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/export/responses_bundle.zip{query}"
    )
    assert response.status_code == 200, response.text
    return zipfile.ZipFile(io.BytesIO(response.content))


def _download(
    client: TestClient, path: str
) -> tuple[str, bytes]:
    """``(filename, body)`` of a card's own download."""
    response = client.get(path)
    assert response.status_code == 200, response.text
    match = re.search(
        r'filename="([^"]+)"', response.headers["content-disposition"]
    )
    assert match
    return match.group(1), response.content


def _card_zip(client: TestClient, path: str) -> dict[str, bytes]:
    response = client.get(path)
    assert response.status_code == 200, response.text
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    return {name: archive.read(name) for name in archive.namelist()}


def test_responses_bundle_route_streams_zip_with_canonical_filename(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-fname")
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/responses_bundle.zip"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"] == (
        'attachment; filename="rb-fname_responses.zip"'
    )


def test_every_card_passes_through_as_configured(
    client: TestClient, db: Session
) -> None:
    """Each card's non-default chip state reaches the bundle, and the
    member equals that card's own download with the same query."""
    review_session = _make_session(client, db, code="rb-pass")
    first, second = _instrument_ids(db, review_session)
    base = f"/operator/sessions/{review_session.id}/export"

    by_instrument = _card_zip(
        client,
        f"{base}/by_instrument_bundle.zip?instrument={second}&meta=0"
        "&all_rows=0",
    )
    reviewer_name, reviewer_body = _download(
        client,
        f"{base}/reviewer_metadata.csv?instrument={first}&all=0"
        "&self_review_handling=both",
    )
    reviewee_name, reviewee_body = _download(
        client,
        f"{base}/reviewee_metadata.csv?instrument={first}&all=0"
        "&self_review_handling=exclude_self",
    )
    archive = _bundle(
        client,
        review_session,
        f"?by_instrument.instrument={second}&by_instrument.meta=0"
        "&by_instrument.all_rows=0"
        f"&reviewer_metadata.instrument={first}&reviewer_metadata.all=0"
        "&reviewer_metadata.self_review_handling=both"
        f"&reviewee_metadata.instrument={first}&reviewee_metadata.all=0"
        "&reviewee_metadata.self_review_handling=exclude_self",
    )

    # Each option the byte comparison alone can't see is shown to
    # change its card's file, so a bundle that dropped it would fail
    # below. (Dropping ``meta`` or ``instrument`` changes the bytes or
    # the member names, which the asserts below already pin.)
    assert by_instrument != _card_zip(
        client, f"{base}/by_instrument_bundle.zip?instrument={second}&meta=0"
    )
    for kind, body, queries in (
        (
            "reviewer_metadata",
            reviewer_body,
            (
                "all=0&self_review_handling=both",
                f"instrument={first}&self_review_handling=both",
                f"instrument={first}&all=0",
            ),
        ),
        (
            "reviewee_metadata",
            reviewee_body,
            (
                "all=0&self_review_handling=exclude_self",
                f"instrument={first}&self_review_handling=exclude_self",
                f"instrument={first}&all=0",
            ),
        ),
    ):
        for query in queries:
            assert _download(client, f"{base}/{kind}.csv?{query}")[1] != body
    assert reviewer_name == "rb-pass_reviewer_metadata_both.csv"
    assert reviewee_name == "rb-pass_reviewee_metadata_noself.csv"
    assert len(by_instrument) == 1
    assert sorted(archive.namelist()) == sorted(
        ["rb-pass_responses.csv", reviewer_name, reviewee_name]
        + list(by_instrument)
    )
    for name, body in by_instrument.items():
        assert archive.read(name) == body
    assert archive.read(reviewer_name) == reviewer_body
    assert archive.read(reviewee_name) == reviewee_body


def test_omitted_options_take_each_card_routes_defaults(
    client: TestClient, db: Session
) -> None:
    """No query at all: every card rides with its own route's
    defaults, and the stats and per-instrument long files that used
    to ride along are gone."""
    review_session = _make_session(client, db, code="rb-def")
    base = f"/operator/sessions/{review_session.id}/export"
    by_instrument = _card_zip(client, f"{base}/by_instrument_bundle.zip")
    reviewer_name, reviewer_body = _download(
        client, f"{base}/reviewer_metadata.csv"
    )
    reviewee_name, reviewee_body = _download(
        client, f"{base}/reviewee_metadata.csv"
    )

    archive = _bundle(client, review_session)
    assert sorted(archive.namelist()) == sorted(
        ["rb-def_responses.csv", reviewer_name, reviewee_name]
        + list(by_instrument)
    )
    assert len(by_instrument) == 2
    for name, body in by_instrument.items():
        assert archive.read(name) == body
    assert archive.read(reviewer_name) == reviewer_body
    assert archive.read(reviewee_name) == reviewee_body
    for name in archive.namelist():
        assert "_stats" not in name
        assert not re.search(r"_instrument_\d+\.csv$", name)


def test_chips_off_leave_only_responses(
    client: TestClient, db: Session
) -> None:
    """``responses.csv`` is not behind a chip: with every card off it
    is the whole bundle."""
    review_session = _make_session(client, db, code="rb-off")
    archive = _bundle(
        client,
        review_session,
        "?by_instrument=0&reviewer_metadata=0&reviewee_metadata=0"
        "&data_shapes=0&tokens=0",
    )
    assert archive.namelist() == ["rb-off_responses.csv"]

    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.responses_bundle_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    assert "context" not in cast(dict, event.detail)


def test_saved_shapes_ride_as_their_download_buttons_name_them(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-shapes")
    created = client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json={
            "name": "My Shape",
            "axis": "reviewer",
            "instrument_id": None,
            "response_field_id": None,
            "column_chip_slots": ["reviewer:name", "reviewer:email"],
            "self_review_handling": "exclude_self",
        },
    )
    assert created.status_code in (200, 201), created.text
    shape_id = created.json()["id"]
    name, body = _download(
        client,
        f"/operator/sessions/{review_session.id}"
        f"/extract-data/shapes/{shape_id}/download.csv",
    )
    assert name == "rb-shapes_My_Shape_noself.csv"

    archive = _bundle(client, review_session)
    assert archive.read(name) == body
    assert name not in _bundle(
        client, review_session, "?data_shapes=0"
    ).namelist()


def test_a_shape_named_like_another_member_does_not_replace_it(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-dup")
    client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json={
            "name": "reviewer_metadata",
            "axis": "reviewer",
            "instrument_id": None,
            "response_field_id": None,
            "column_chip_slots": ["reviewer:name"],
        },
    )
    archive = _bundle(client, review_session)
    names = archive.namelist()
    assert len(names) == len(set(names))
    # The card's file keeps its card name; the shape takes the ``_2``.
    _, reviewer_body = _download(
        client,
        f"/operator/sessions/{review_session.id}/export/reviewer_metadata.csv",
    )
    assert archive.read("rb-dup_reviewer_metadata_self.csv") == reviewer_body
    assert archive.read("rb-dup_reviewer_metadata_self_2.csv") != reviewer_body


def test_responses_bundle_route_emits_audit_event(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-aud")
    _bundle(
        client,
        review_session,
        "?reviewee_metadata=0&reviewer_metadata.self_review_handling=both",
    )

    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.responses_bundle_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = cast(dict, event.detail)
    assert detail["counts"] == {
        "responses": 0,
        "by_instrument_files": 2,
        "reviewer_metadata_files": 1,
        "reviewee_metadata_files": 0,
        "data_shapes": 0,
        "participant_tokens": 0,
    }
    assert detail["context"] == {
        "reviewer_metadata_self_review_handling": "both"
    }


def test_extract_data_page_surfaces_zip_all_button(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-page")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    assert 'id="extract-data-zip-all"' in body
    assert (
        f'href="/operator/sessions/{review_session.id}'
        f'/export/responses_bundle.zip"' in body
    )
    assert "a complete set" in body
    assert "of response data, plus whichever files are selected" in body


def test_half_width_cards_follow_the_authors_order(
    client: TestClient, db: Session
) -> None:
    """Left column: Reviewer then Reviewee response metadata; right
    column: By instrument then Extract all data (D28)."""
    review_session = _make_session(client, db, code="rb-order")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text
    grid = body[: body.index('id="extract-data-shaper"')]
    columns = grid.split('<div class="extract-data-column">')[1:]
    assert len(columns) == 2
    left, right = columns
    assert left.index('id="extract-data-by-reviewer"') < left.index(
        'id="extract-data-by-reviewee"'
    )
    assert 'id="extract-data-intro"' not in left
    assert right.index('id="extract-data-by-instrument"') < right.index(
        'id="extract-data-intro"'
    )


def test_all_instruments_stands_for_every_instrument_chip(
    client: TestClient, db: Session
) -> None:
    """Codex on #2769: the page sends ``all_instruments=1`` rather than
    one id per chip when every chip is on, so the Zip-all link stays
    under a gateway's URL limit. It means exactly the full list, on the
    card's own route and in the bundle."""
    review_session = _make_session(client, db, code="rb-allinst")
    ids = _instrument_ids(db, review_session)
    base = f"/operator/sessions/{review_session.id}/export"
    listed = "&".join(f"instrument={i}" for i in ids)
    for kind in ("reviewer_metadata", "reviewee_metadata"):
        name, body = _download(client, f"{base}/{kind}.csv?{listed}")
        assert _download(
            client, f"{base}/{kind}.csv?all_instruments=1"
        ) == (name, body)
        assert _download(client, f"{base}/{kind}.csv")[1] != body
        archive = _bundle(
            client, review_session, f"?{kind}.all_instruments=1"
        )
        assert archive.read(name) == body
        # It wins over an explicit list, on the card and in the bundle.
        # Naming only the field-less second instrument would change the
        # file, so a list that won would fail here.
        assert _download(client, f"{base}/{kind}.csv?instrument={ids[1]}")[
            1
        ] != body
        assert _download(
            client, f"{base}/{kind}.csv?all_instruments=1&instrument={ids[1]}"
        )[1] == body
        archive = _bundle(
            client,
            review_session,
            f"?{kind}.all_instruments=1&{kind}.instrument={ids[1]}",
        )
        assert archive.read(name) == body
