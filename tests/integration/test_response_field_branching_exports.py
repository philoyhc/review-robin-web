"""19T Item 10 rung 8 — exports: the by-instrument extract's metadata
block states the condition that shows each governed field, and a closed
branch's cells export blank, as a skipped field's do (no N/A marker).

The default instrument gets a branch directly: Rating (Integer 1–5)
governs Comments while Rating ≥ 4."""

from __future__ import annotations

import csv
import io

from sqlalchemy.orm import Session

from app.db.models import InstrumentResponseField, Response
from app.schemas.responses import ResponseUpsert
from app.services import responses as responses_service
from app.services.extracts.by_instrument_extract import serialize_by_instrument

from .test_responses_service import _seed


def _branched(db: Session, instrument_id: int) -> dict[str, InstrumentResponseField]:
    fields = {
        f.field_key: f
        for f in db.query(InstrumentResponseField).filter_by(instrument_id=instrument_id)
    }
    fields["rating"].branch_op, fields["rating"].branch_value = "ge", "4"
    fields["comments"].branch_parent_id = fields["rating"].id
    db.flush()
    return fields


def _rows(db: Session, review_session, instrument) -> list[list[str]]:
    lines = serialize_by_instrument(db, review_session, instrument, position=1)
    buffer = io.StringIO()
    csv.writer(buffer).writerows(lines)
    return list(csv.reader(io.StringIO(buffer.getvalue())))


def test_the_metadata_states_each_governed_fields_condition(db: Session) -> None:
    op, reviewer, review_session, assignment = _seed(db)
    _branched(db, assignment.instrument_id)
    instrument = assignment.instrument
    rows = _rows(db, review_session, instrument)
    meta = rows[: rows.index([])]
    labels = [row[0] for row in meta]
    # The condition follows the governed field's own sub-block, after its
    # Helptext; the parent's sub-block gains nothing.
    comments = labels.index("Response field", labels.index("Response field") + 1)
    assert meta[comments] == ["Response field", "Comments"]
    assert meta[comments + 4] == ["Shown when", "Rating ≥ 4"]
    assert labels.count("Shown when") == 1


def test_an_instrument_without_a_branch_exports_as_before(db: Session) -> None:
    _, _, review_session, assignment = _seed(db)
    rows = _rows(db, review_session, assignment.instrument)
    assert all(row[:1] != ["Shown when"] for row in rows)


def test_a_closed_branch_exports_blank(db: Session) -> None:
    """The save rule leaves no value in a closed branch, so its cell is
    blank, as a skipped field's is."""
    op, reviewer, review_session, assignment = _seed(db)
    _branched(db, assignment.instrument_id)
    responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[
            ResponseUpsert(assignment_id=assignment.id, field_key="rating", value="2"),
            ResponseUpsert(assignment_id=assignment.id, field_key="comments", value="x"),
        ],
        correlation_id="corr",
    )
    assert db.query(Response).filter_by(assignment_id=assignment.id).count() == 1
    rows = _rows(db, review_session, assignment.instrument)
    data = rows[rows.index([]) + 1 :]
    header, first = data[0], data[1]
    assert first[header.index("Rating")] == "2"
    assert first[header.index("Comments")] == ""
