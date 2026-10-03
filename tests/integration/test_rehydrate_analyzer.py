"""18P PR G1 — the rehydrate pre-flight analyzer.

Builds a real extract file set from a seeded session (via the actual
serializers), then asserts the analyzer's verdict + preview across the
clean case and the common failure modes.
"""

from __future__ import annotations

import csv
import datetime as dt
import io

from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionOperator,
    User,
)
from app.services.session_config_io import serialize_session_config
from app.services.extracts.reviewees_extract import serialize_reviewees
from app.services.extracts.reviewers_extract import serialize_reviewers
from app.services.extracts.responses_extract import serialize_responses
from app.services.session_rehydrate import (
    _resolve_files,
    analyze_rehydrate_set,
    derive_rehydrate_name,
)

_INLINE = dict(
    _inline_data_type="Integer",
    _inline_response_type="Likert5",
    _inline_min=1.0,
    _inline_max=5.0,
    _inline_step=1.0,
)


def _to_csv(rows) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _seed(db: Session) -> tuple[User, ReviewSession]:
    user = User(email="op@e.edu", display_name="Op")
    db.add(user)
    db.flush()
    rs = ReviewSession(name="Spring", code="spring", created_by_user_id=user.id)
    db.add(rs)
    db.flush()
    db.add(SessionOperator(session_id=rs.id, user_id=user.id, role="owner"))
    inst = Instrument(
        session_id=rs.id, name="Inst", short_label="INST", order=1
    )
    db.add(inst)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=inst.id,
        field_key="q1",
        label="Q1",
        order=1,
        visible=True,
        **_INLINE,
    )
    db.add(field)
    db.flush()
    rvr = Reviewer(session_id=rs.id, name="Ana", email="ana@e.edu")
    rve = Reviewee(session_id=rs.id, name="Bo", email_or_identifier="bo@e.edu")
    db.add_all([rvr, rve])
    db.flush()
    a = Assignment(
        session_id=rs.id,
        reviewer_id=rvr.id,
        reviewee_id=rve.id,
        instrument_id=inst.id,
        include=True,
        is_self_review=False,
    )
    db.add(a)
    db.flush()
    db.add(
        Response(
            assignment_id=a.id,
            response_field_id=field.id,
            value="4",
            saved_at=dt.datetime(2026, 6, 1, 9, 0, tzinfo=dt.timezone.utc),
            submitted_at=dt.datetime(2026, 6, 1, 10, 0, tzinfo=dt.timezone.utc),
            version=1,
        )
    )
    db.flush()
    return user, rs


def _file_set(db: Session, rs: ReviewSession) -> dict[str, bytes]:
    settings_rows = [("field", "value", "data_type")] + [
        (r.field, r.value, r.data_type)
        for r in serialize_session_config(db, rs)
    ]
    return {
        f"{rs.code}_settings.csv": _to_csv(settings_rows),
        f"{rs.code}_reviewers.csv": _to_csv(serialize_reviewers(db, rs)),
        f"{rs.code}_reviewees.csv": _to_csv(serialize_reviewees(db, rs)),
        f"{rs.code}_responses.csv": _to_csv(serialize_responses(db, rs)),
    }


def test_clean_set_passes_with_preview(db: Session) -> None:
    user, rs = _seed(db)
    report = analyze_rehydrate_set(db, files=_file_set(db, rs), user=user)
    assert report.ok, report.errors
    assert report.errors == []
    assert report.preview["name"] == "Spring_REHYD"
    assert report.preview["code"] == "spring-rehyd"
    assert report.preview["reviewers"] == 1
    assert report.preview["reviewees"] == 1
    assert report.preview["instruments"] == 1
    assert report.preview["responses"] == 1


def test_a_by_instrument_file_named_like_a_kind_is_ignored(
    db: Session,
) -> None:
    """D28: the Zip-all bundle can carry By-instrument CSVs, named
    after the instrument's short label. One labelled ``reviewers``
    ends in ``reviewers.csv``; read first, it must not stand in for
    the reviewer roster."""
    user, rs = _seed(db)
    files = {
        f"{rs.code}_by_instrument_reviewers.csv": b"Instrument,#1\r\n",
        **_file_set(db, rs),
    }
    report = analyze_rehydrate_set(db, files=files, user=user)
    assert report.ok, report.errors


def test_a_code_containing_the_by_instrument_mark_is_reported_missing(
    db: Session,
) -> None:
    """The accepted limitation (spec/rehydrate.md §4): every file of a
    session whose code contains the mark, or ends in ``_by_instrument``,
    is skipped, and rehydrate says the files are missing rather than
    misreading any of them."""
    user, rs = _seed(db)
    for code in ("x_by_instrument_spring", "Peer_BY_INSTRUMENT"):
        files = {
            name.replace(rs.code, code, 1): content
            for name, content in _file_set(db, rs).items()
        }
        assert all(code in name for name in files)
        report = analyze_rehydrate_set(db, files=files, user=user)
        assert not report.ok
        assert any("settings.csv" in e for e in report.errors)


def test_a_by_instrument_file_never_stands_in_for_an_optional_file() -> None:
    """D28: relationships and observers are optional, so a
    By-instrument file named after one has no real file to lose to. It
    must still not be read as one."""
    resolved = _resolve_files(
        {
            "s_settings.csv": b"",
            "s_reviewers.csv": b"",
            "s_reviewees.csv": b"",
            "s_responses.csv": b"",
            "s_by_instrument_Peer_relationships.csv": b"wide",
            "s_by_instrument_Observers.csv": b"wide",
        }
    )
    assert set(resolved) == {"settings", "reviewers", "reviewees", "responses"}
    # Loosely renamed kind files, an untouched
    # By-instrument file. It is still never read as relationships.
    resolved = _resolve_files(
        {
            "settings.csv": b"",
            "reviewers.csv": b"",
            "reviewees.csv": b"",
            "responses.csv": b"",
            "S_by_instrument_Peer_relationships.csv": b"wide",
        }
    )
    assert set(resolved) == {"settings", "reviewers", "reviewees", "responses"}


def test_missing_required_file_blocks(db: Session) -> None:
    user, rs = _seed(db)
    files = _file_set(db, rs)
    del files[f"{rs.code}_responses.csv"]
    report = analyze_rehydrate_set(db, files=files, user=user)
    assert not report.ok
    assert any("responses.csv" in e for e in report.errors)
    assert report.preview == {}


def test_cross_session_reviewer_mix_blocks(db: Session) -> None:
    user, rs = _seed(db)
    files = _file_set(db, rs)
    # Swap in a reviewers.csv that doesn't contain ana@e.edu — the
    # responses reference an email the roster no longer has.
    files[f"{rs.code}_reviewers.csv"] = _to_csv(
        [
            ("ReviewerName", "ReviewerEmail"),
            ("Zed", "zed@e.edu"),
        ]
    )
    report = analyze_rehydrate_set(db, files=files, user=user)
    assert not report.ok
    assert any(
        "reviewer email" in e and "responses.csv" in e for e in report.errors
    )


def test_observers_enabled_but_missing_file_blocks(db: Session) -> None:
    user, rs = _seed(db)
    rs.observers_enabled = True
    db.flush()
    files = _file_set(db, rs)  # no observers.csv
    report = analyze_rehydrate_set(db, files=files, user=user)
    assert not report.ok
    assert any("observers.csv is missing" in e for e in report.errors)


def test_malformed_responses_header_blocks(db: Session) -> None:
    user, rs = _seed(db)
    files = _file_set(db, rs)
    files[f"{rs.code}_responses.csv"] = _to_csv([("nope", "not", "a header")])
    report = analyze_rehydrate_set(db, files=files, user=user)
    assert not report.ok
    assert any("header" in e.lower() for e in report.errors)


def test_derive_name_suffixes_on_collision(db: Session) -> None:
    user, rs = _seed(db)
    # An existing "Spring_REHYD" the operator owns forces the _1 suffix.
    existing = ReviewSession(
        name="Spring_REHYD", code="spring-rehyd", created_by_user_id=user.id
    )
    db.add(existing)
    db.flush()
    db.add(SessionOperator(session_id=existing.id, user_id=user.id, role="owner"))
    db.flush()
    assert (
        derive_rehydrate_name(db, user=user, original_name="Spring")
        == "Spring_REHYD_1"
    )
