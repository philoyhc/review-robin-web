"""Integration coverage for Segment 15D PR 6b — drop
``Assignment.context`` JSON column.

PR 6b retires the column entirely:
- ``pair_context_*`` keys lifted to the ``relationships`` table in
  PR 5; readers in ``_display_fields.py`` and ``assignments.py``
  rewrite to consult the relationships table at PR 6b.
- ``assignment_context_*`` keys retire entirely (no remaining
  consumer; manual-CSV path silently ignores the columns).
- The ``Assignment.context`` ORM attribute is gone; the column is
  dropped from the schema.

These tests pin the post-PR-6b shape: no ``context`` attribute,
no production code path writing context, lazy-seeding fires from
the relationships save instead of the manual CSV save.
"""

from __future__ import annotations

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.db.models import Assignment, InstrumentDisplayField, ReviewSession


def test_assignment_orm_class_has_no_context_attribute() -> None:
    """The ORM model loses the ``context`` attribute alongside the
    column drop. Code that still references ``Assignment.context``
    raises ``AttributeError`` at lookup time."""

    assert not hasattr(Assignment, "context")


def test_assignments_table_lacks_context_column(db: Session) -> None:
    """Schema-level: the ``context`` column is gone from the
    ``assignments`` table after PR 6b's migration runs."""

    columns = {col["name"] for col in inspect(db.bind).get_columns("assignments")}
    assert "context" not in columns
    # Sanity: other columns still there.
    assert {"include", "session_id", "reviewer_id", "reviewee_id"}.issubset(
        columns
    )


def test_replace_assignments_signature_drops_contexts_param() -> None:
    """``replace_assignments`` no longer accepts ``contexts``. The
    parameter retired alongside the 15D PR 6b column drop. The
    ``includes`` / ``pairs`` / ``rule_set_revision`` / ``filename`` /
    ``excluded_counts`` parameters retired with 15B Slice 1 when the
    function flipped to reading each instrument's pinned
    ``rule_set_id`` and running the engine internally."""

    import inspect as inspect_mod

    from app.services import assignments

    params = inspect_mod.signature(assignments.replace_assignments).parameters
    for retired in (
        "contexts", "includes", "pairs",
        "rule_set_revision", "filename", "excluded_counts",
    ):
        assert retired not in params, retired
    assert "instrument_id" in params


def test_lazy_seed_fires_from_relationships_save(
    client, db: Session
) -> None:
    """Uploading a Relationships CSV with populated tags lazy-seeds
    pair_context display fields on every instrument (post-15D PR 6b
    the seeding hook moved from ``replace_assignments`` to
    ``save_relationships``)."""

    response = client.post(
        "/operator/sessions",
        data={"name": "Seed", "code": "lazy-seed-rel", "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(
            ReviewSession.code == "lazy-seed-rel"
        )
    ).scalar_one()
    review_session.relationships_enabled = True
    db.commit()

    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/relationships/import",
        files={
            "file": (
                "rel.csv",
                (
                    b"ReviewerEmail,RevieweeEmail,PairContextTag2\n"
                    b"alice@example.edu,carol@example.edu,Cohort A\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    # Look up any instrument on the session.
    from app.db.models import Instrument

    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalars().first()
    assert instrument is not None

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
    ).scalars().all()
    pairs = {(r.source_type, r.source_field) for r in rows}
    # Only slot 2 is populated → only that display field gets seeded.
    assert ("pair_context", "2") in pairs
    assert ("pair_context", "1") not in pairs
    assert ("pair_context", "3") not in pairs


def test_backfill_service_function_retired() -> None:
    """The PR 5 ``backfill_from_assignment_context`` service helper
    retires alongside the column drop. The Alembic migration
    (PR 5's data lift) is the historical record; no production
    callers remain."""

    from app.services import relationships as relationships_service

    assert not hasattr(
        relationships_service, "backfill_from_assignment_context"
    )
