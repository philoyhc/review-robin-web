"""Findings S4 (author's ruling): a Settings import keeps replace-all,
and warns. Before applying, a file that would delete instruments it does
not name is refused naming them, with a tick carrying their count; the
next submit with that tick applies it. A file that deletes no instrument
never asks, and Create, with nothing of the operator's to lose, never
asks either. Nor does Quick Setup about a session's Default instrument
while it is still as Create made it (the author, 2026-10-19): a fresh
session set up from Session Home behaves as one set up on Create."""

from __future__ import annotations

import csv
import io

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession, User
from app.services.instruments import is_untouched_default
from app.services.session_config_io import (
    InstrumentsWouldDelete,
    Row,
    apply_session_config,
    instruments_deleted_by,
)
from app.services.session_config_io._apply_parse import _parse_rows

from ._quick_setup_refusal import refusal


def _settings_csv(rows: list[tuple[str, str, str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(("field", "value", "data_type"))
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _make_session(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    """A session holding its Default instrument, given a description so
    it is the operator's work, plus a second labelled Peer review."""
    response = client.post(
        "/operator/sessions",
        data={"name": "S4", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    default = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    default.description = "Edited by the operator"
    db.add(
        Instrument(
            session_id=review_session.id,
            name="peer",
            short_label="Peer review",
            order=1,
        )
    )
    db.commit()
    return review_session


def _names(db: Session, review_session: ReviewSession) -> list[str]:
    db.expire_all()
    return sorted(
        db.execute(
            select(Instrument.name).where(
                Instrument.session_id == review_session.id
            )
        ).scalars()
    )


def test_a_file_that_drops_an_instrument_names_it_then_applies_on_the_tick(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="s4-drop")
    url = f"/operator/sessions/{review_session.public_id}/import-config"
    payload = _settings_csv([("instruments[1].name", "Default", "string")])

    response = client.post(
        url,
        data={"confirm_replace": "true"},
        files={"file": ("c.csv", payload, "text/csv")},
        follow_redirects=False,
    )
    refused = refusal(response)
    assert (refused.kind, refused.reason) == ("settings", "deletes_instruments")
    assert refused.details == ["Peer review"]
    assert refused.lead == (
        "Nothing was imported. This settings file deletes 1 instrument it "
        "does not name, with its fields:"
    )
    assert (
        'name="acknowledge_instrument_deletion"\n'
        '                 value="1"\n'
        '                 form="quick-setup-submit-all-form"'
    ) in response.text
    assert _names(db, review_session) == ["Default", "peer"]

    response = client.post(
        url,
        data={"confirm_replace": "true", "acknowledge_instrument_deletion": "1"},
        files={"file": ("c.csv", payload, "text/csv")},
        follow_redirects=False,
    )
    assert response.headers["location"].endswith("#quick-setup-settings")
    assert "quick_setup_error" not in response.headers["location"]
    assert _names(db, review_session) == ["Default"]


def test_a_file_with_no_instrument_rows_names_every_instrument(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="s4-none")
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/quick-setup/submit-all",
        data={"confirm_replace": "true"},
        files={
            "settings_file": (
                "c.csv",
                _settings_csv([("session.description", "x", "string")]),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    refused = refusal(response)
    assert refused.reason == "deletes_instruments"
    assert refused.details == ["Instrument_1", "Peer review"]
    assert 'value="2"' in response.text
    assert _names(db, review_session) == ["Default", "peer"]


def test_a_tick_for_another_count_is_refused_again(
    client: TestClient, db: Session
) -> None:
    """The tick carries the count rather than ``true``, so a tick left
    on for one file cannot approve another that deletes more."""
    review_session = _make_session(client, db, code="s4-stale")
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/import-config",
        data={"confirm_replace": "true", "acknowledge_instrument_deletion": "1"},
        files={
            "file": (
                "c.csv",
                _settings_csv([("instruments[1].name", "Other", "string")]),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    refused = refusal(response)
    assert refused.reason == "deletes_instruments"
    assert "deletes 2 instruments" in refused.lead
    assert _names(db, review_session) == ["Default", "peer"]


def test_a_file_that_deletes_no_instrument_never_asks(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="s4-keep")
    payload = _settings_csv(
        [
            ("instruments[1].name", "Default", "string"),
            ("instruments[2].name", "peer", "string"),
            ("instruments[3].name", "added", "string"),
        ]
    )
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/import-config",
        data={"confirm_replace": "true"},
        files={"file": ("c.csv", payload, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "quick_setup_error" not in response.headers["location"]
    assert _names(db, review_session) == ["Default", "added", "peer"]


def test_create_never_asks(client: TestClient, db: Session) -> None:
    """A new session holds only its Default instrument, which a file
    naming others replaces without a question."""
    payload = _settings_csv([("instruments[1].name", "Eval", "string")])
    response = client.post(
        "/operator/sessions",
        data={"name": "S4 new", "code": "s4-create", "description": ""},
        files={"settings_file": ("c.csv", payload, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "quick_setup_error" not in response.headers["location"]
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "s4-create")
    ).scalar_one()
    assert _names(db, review_session) == ["Eval"]


def test_a_file_with_errors_reports_them_before_asking(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="s4-errors")
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/import-config",
        data={"confirm_replace": "true"},
        files={
            "file": (
                "c.csv",
                _settings_csv([("instruments[1].short_label", "X", "string")]),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert refusal(response).reason == "parse"


def test_instruments_deleted_by_matches_one_row_per_instrument(
    db: Session,
) -> None:
    """Two instruments sharing a name need two rows to survive; the
    service raises only for a caller that asks."""
    user = User(email="s4-unit@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="S4 unit", code="s4-unit", created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    for order, label in enumerate(("First", "Second")):
        db.add(
            Instrument(
                session_id=review_session.id,
                name="same",
                short_label=label,
                order=order,
            )
        )
    db.flush()

    rows = [Row("instruments[1].name", "same", "string")]
    plan, errors = _parse_rows(rows)
    assert errors == []
    assert instruments_deleted_by(db, review_session, plan) == ["Second"]

    try:
        apply_session_config(db, review_session, rows, acknowledged_deletions=0)
    except InstrumentsWouldDelete as exc:
        assert exc.labels == ["Second"]
        assert exc.count == 1
    else:
        raise AssertionError("expected InstrumentsWouldDelete")

    result = apply_session_config(db, review_session, rows)
    assert result.ok
    assert _names(db, review_session) == ["same"]


def _fresh_session(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "S4 fresh", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_quick_setup_on_a_fresh_session_never_asks(
    client: TestClient, db: Session
) -> None:
    """The author's case: a blank session set up from Session Home's
    Quick Setup takes the file as Create would, with no question about
    the Default instrument it never touched."""
    review_session = _fresh_session(client, db, code="s4-fresh")
    payload = _settings_csv([("instruments[1].name", "Eval", "string")])

    response = client.post(
        f"/operator/sessions/{review_session.public_id}/quick-setup/submit-all",
        data={"confirm_replace": "true"},
        files={"settings_file": ("c.csv", payload, "text/csv")},
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert "quick_setup_error" not in response.headers["location"]
    assert _names(db, review_session) == ["Eval"]


def _touch_short_label(instrument: Instrument) -> None:
    instrument.short_label = "Team"


def _touch_field_label(instrument: Instrument) -> None:
    instrument.response_fields[0].label = "Score"


def _touch_field_required(instrument: Instrument) -> None:
    instrument.response_fields[1].required = True


def _touch_display_label(instrument: Instrument) -> None:
    instrument.display_fields[0].label = "Student"


def _touch_display_hidden(instrument: Instrument) -> None:
    instrument.display_fields[1].visible = False


def _touch_group_kind(instrument: Instrument) -> None:
    instrument.group_kind = "r1"


@pytest.mark.parametrize(
    "touch",
    [
        _touch_short_label,
        _touch_field_label,
        _touch_field_required,
        _touch_display_label,
        _touch_display_hidden,
        _touch_group_kind,
    ],
)
def test_a_default_the_operator_changed_is_named(
    client: TestClient, db: Session, touch
) -> None:
    """Any change makes the Default instrument the operator's, and the
    import asks before deleting it."""
    review_session = _fresh_session(client, db, code=f"s4-{touch.__name__[7:]}")
    default = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    touch(default)
    db.commit()

    plan, errors = _parse_rows([Row("instruments[1].name", "Eval", "string")])
    assert errors == []
    assert instruments_deleted_by(db, review_session, plan) == [
        "Team" if touch is _touch_short_label else "Instrument_1"
    ]


def test_a_fresh_default_counts_as_untouched(client: TestClient, db: Session) -> None:
    review_session = _fresh_session(client, db, code="s4-untouched")
    default = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    assert is_untouched_default(default)


def test_quick_setup_takes_a_fresh_sessions_whole_set_up(
    client: TestClient, db: Session
) -> None:
    """The browser checklist's groups files (01, 12, 13, 14), all in one
    Quick Setup submit on a blank session, apply as they do on Create."""
    import pathlib

    folder = (
        pathlib.Path(__file__).resolve().parents[2]
        / "guide/browser_check_files/checklist"
    )
    review_session = _fresh_session(client, db, code="s4-checklist")
    slots = {
        "reviewers_file": "01_reviewers.csv",
        "reviewees_file": "12_groups_reviewees.csv",
        "relationships_file": "13_groups_relationships.csv",
        "settings_file": "14_groups_settings.csv",
    }
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/quick-setup/submit-all",
        data={"confirm_replace": "true"},
        files={
            slot: (name, (folder / name).read_bytes(), "text/csv")
            for slot, name in slots.items()
        },
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert "quick_setup_error" not in response.headers["location"]
    assert len(_names(db, review_session)) == 2
