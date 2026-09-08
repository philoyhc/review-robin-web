"""Segment 19C Item 9 — the Settings-CSV import refuses a Band 3
visibility cell the editor would refuse.

Two writers create ``instrument_view_policies`` rows.
``visibility_policies.upsert_policy`` validates the
``(audience, window)`` cell against ``_PER_CELL_VALID_MODES``; the import
writer (``session_config_io/_apply_instrument``) builds the row from the
parsed plan and, until this item, checked only the *vocabulary* —
``row`` / ``aggregated``, ``identified`` / ``deidentified`` — never the
cell those values landed in.

The cell that mattered is ``("reviewee", "while_ongoing")``, whose only
legal mode is ``None``: a reviewee may never read responses while the
review is running. An imported row saying otherwise was honoured by
``resolve_mode`` like any other, so on a ``ready`` session the reviewee
got a ``/me`` row and a 200 on ``/results`` — found by Segment 19F's
close audit, pre-dating 19F itself (the writer arrived with 18P PR A2).

The first test here is the one that matters most: a round-trip of an
editor-authored session must still apply clean. The serializer emits all
four cells for every audience, so a legitimate export carries empty
strings in the forbidden cell; if this item rejected those, it would
break backup-and-restore for everyone to close a hole almost nobody has.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentViewPolicy,
    ReviewSession,
    User,
)
from app.services import visibility_policies
from app.services.session_config_io import (
    Row,
    apply_session_config,
    serialize_session_config,
)


def _session(db: Session, *, code: str) -> ReviewSession:
    user = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    return review_session


def _policies(db: Session, review_session: ReviewSession):
    return (
        db.execute(
            select(InstrumentViewPolicy)
            .join(Instrument)
            .where(Instrument.session_id == review_session.id)
        )
        .scalars()
        .all()
    )


def _cell_rows(audience: str, window: str, mode: str) -> list[Row]:
    granularity, identification = visibility_policies.MODE_LABELS[mode]
    prefix = f"instruments[1].view_policies[{audience}]"
    return [
        Row("instruments[1].name", "Survey", "string"),
        Row(f"{prefix}.{window}_granularity", granularity, "string"),
        Row(f"{prefix}.{window}_identification", identification, "string"),
    ]


# ── The regression that matters most ─────────────────────────────────


def test_round_trip_of_an_editor_authored_session_still_applies(
    db: Session,
) -> None:
    """Export → import of a session the editor produced is unaffected.

    ``_serialize`` emits all four cells for every audience, so the
    forbidden ``reviewee`` / ``while_ongoing`` pair leaves as two empty
    strings, parses back to ``None``, and ``None`` is that cell's legal
    mode. Without this test the item would be indistinguishable from one
    that breaks every restore."""
    src = _session(db, code="vp-rt")
    instrument = Instrument(session_id=src.id, name="Survey", order=1)
    db.add(instrument)
    db.flush()
    granularity, identification = visibility_policies.MODE_LABELS["raw"]
    db.add(
        InstrumentViewPolicy(
            instrument_id=instrument.id,
            audience="reviewee",
            after_release_granularity=granularity,
            after_release_identification=identification,
        )
    )
    db.commit()

    rows = serialize_session_config(db, src)
    # The forbidden cell really is present in the export, and empty —
    # otherwise this test would pass for the wrong reason.
    emitted = {
        r.field: r.value
        for r in rows
        if "view_policies[reviewee]" in r.field
    }
    assert (
        emitted["instruments[1].view_policies[reviewee]"
                ".while_ongoing_granularity"] == ""
    )

    target = _session(db, code="vp-rt2")
    result = apply_session_config(db, target, rows)
    assert result.errors == []
    applied = _policies(db, target)
    assert [p.audience for p in applied] == ["reviewee"]
    assert applied[0].after_release_granularity == granularity


# ── The cell the disclosure hangs on ─────────────────────────────────


def test_reviewee_while_ongoing_is_rejected(db: Session) -> None:
    review_session = _session(db, code="vp-re")
    result = apply_session_config(
        db, review_session, _cell_rows("reviewee", "while_ongoing", "raw")
    )
    assert not result.ok
    assert result.counts == {}
    [error] = [
        e for e in result.errors if "view_policies" in e.field
    ]
    assert error.field == (
        "instruments[1].view_policies[reviewee].while_ongoing_granularity"
    )
    assert "only accepts modes in" in error.message
    assert "'raw'" in error.message


def test_a_rejected_import_writes_no_policy_row(db: Session) -> None:
    """Asserted by querying, not inferred from ``errors`` — the point of
    validating in the parse phase is that ``_apply_plan`` never runs."""
    review_session = _session(db, code="vp-nowrite")
    apply_session_config(
        db, review_session, _cell_rows("reviewee", "while_ongoing", "raw")
    )
    assert _policies(db, review_session) == []
    assert (
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        )
        .scalars()
        .all()
        == []
    )


def test_reviewee_after_release_is_accepted(db: Session) -> None:
    """The positive control for the pair above: the *other* window on
    the same audience takes the same mode happily."""
    review_session = _session(db, code="vp-ok")
    result = apply_session_config(
        db, review_session, _cell_rows("reviewee", "after_release", "raw")
    )
    assert result.errors == []
    [policy] = _policies(db, review_session)
    assert policy.after_release_granularity == "row"


# ── The same code path covers the other audiences ────────────────────


def test_observer_while_ongoing_raw_is_rejected(db: Session) -> None:
    """``observer`` / ``while_ongoing`` accepts only ``None`` or
    ``summarized`` — the check reads the shared table rather than
    special-casing the reviewee."""
    review_session = _session(db, code="vp-ob")
    result = apply_session_config(
        db, review_session, _cell_rows("observer", "while_ongoing", "raw")
    )
    assert not result.ok
    assert any("observer" in e.message for e in result.errors)


def test_observer_while_ongoing_summarized_is_accepted(
    db: Session,
) -> None:
    review_session = _session(db, code="vp-ob-ok")
    result = apply_session_config(
        db,
        review_session,
        _cell_rows("observer", "while_ongoing", "summarized"),
    )
    assert result.errors == []


def test_peer_reviewer_while_ongoing_summarized_is_rejected(
    db: Session,
) -> None:
    """``peer_reviewer`` / ``while_ongoing`` accepts only ``raw``."""
    review_session = _session(db, code="vp-pr")
    result = apply_session_config(
        db,
        review_session,
        _cell_rows("peer_reviewer", "while_ongoing", "summarized"),
    )
    assert not result.ok
    assert any("peer_reviewer" in e.message for e in result.errors)


# ── Pairs that are not modes at all ──────────────────────────────────


def test_a_half_set_cell_is_its_own_error(db: Session) -> None:
    """Granularity without identification is not a mode.
    ``decode_pair_to_mode`` reads a half-pair as "off", so without a
    distinct check a half-authored cell would import silently as
    ``None`` rather than telling the operator their file is wrong."""
    review_session = _session(db, code="vp-half")
    rows = [
        Row("instruments[1].name", "Survey", "string"),
        Row(
            "instruments[1].view_policies[reviewee]"
            ".after_release_granularity",
            "row",
            "string",
        ),
    ]
    result = apply_session_config(db, review_session, rows)
    assert not result.ok
    [error] = [e for e in result.errors if "view_policies" in e.field]
    assert "half-set" in error.message
    assert "set both or neither" in error.message


def test_the_incoherent_pair_is_its_own_error(db: Session) -> None:
    """``aggregated`` + ``identified`` is reserved and decodes to no
    mode. ``decode_pair_to_mode`` swallows it as ``None``; the import
    names it instead."""
    review_session = _session(db, code="vp-incoherent")
    prefix = "instruments[1].view_policies[observer]"
    rows = [
        Row("instruments[1].name", "Survey", "string"),
        Row(f"{prefix}.after_release_granularity", "aggregated", "string"),
        Row(f"{prefix}.after_release_identification", "identified", "string"),
    ]
    result = apply_session_config(db, review_session, rows)
    assert not result.ok
    [error] = [e for e in result.errors if "view_policies" in e.field]
    assert "not a valid stored mode" in error.message


def test_every_offending_cell_is_reported(db: Session) -> None:
    """The parse phase collects every error before reporting; one bad
    cell must not mask the next."""
    review_session = _session(db, code="vp-many")
    rows = [Row("instruments[1].name", "Survey", "string")]
    for audience in ("reviewee", "peer_reviewer"):
        granularity, identification = visibility_policies.MODE_LABELS[
            "summarized"
        ]
        prefix = f"instruments[1].view_policies[{audience}]"
        rows.append(
            Row(f"{prefix}.while_ongoing_granularity", granularity, "string")
        )
        rows.append(
            Row(
                f"{prefix}.while_ongoing_identification",
                identification,
                "string",
            )
        )
    result = apply_session_config(db, review_session, rows)
    offending = [e for e in result.errors if "view_policies" in e.field]
    assert len(offending) == 2
    assert {"reviewee", "peer_reviewer"} == {
        e.field.split("[")[2].split("]")[0] for e in offending
    }
