from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentDisplayField,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services.instruments import ensure_default_instrument
from app.web.routes_reviewer import (
    _SYNTHETIC_VALUES_BY_SOURCE,
    _make_synthetic_row,
    build_preview_context,
)


def _user(db: Session, *, email: str = "op@example.edu") -> User:
    user = User(email=email, display_name="Op")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, user: User, *, code: str) -> ReviewSession:
    s = ReviewSession(name="Test", code=code, created_by_user_id=user.id)
    db.add(s)
    db.flush()
    return s


def _seed_pair_context_display_fields(db: Session, instrument: Instrument) -> None:
    """Pair-context display fields used to be seeded unconditionally by
    ensure_default_instrument; after the 2026-05-01 lazy-seed change
    (item #14), tests in this module that exercise pair_context preview
    rendering must seed them explicitly."""
    for slot, order in (("1", 0), ("2", 1), ("3", 2)):
        db.add(
            InstrumentDisplayField(
                instrument_id=instrument.id,
                label="",
                source_type="pair_context",
                source_field=slot,
                order=order,
                visible=True,
            )
        )
    db.flush()


def _add_real_assignment(
    db: Session, session: ReviewSession, *, reviewee_email: str
) -> Assignment:
    reviewer = Reviewer(
        session_id=session.id, name="R", email=f"r-{reviewee_email}"
    )
    reviewee = Reviewee(
        session_id=session.id,
        name=f"Reviewee {reviewee_email}",
        email_or_identifier=reviewee_email,
        tag_1="real-tag",
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    instrument = db.execute(
        select(__import__("app").db.models.Instrument).where(
            __import__("app").db.models.Instrument.session_id == session.id
        )
    ).scalar_one()
    from app.db.models import Relationship

    assignment = Assignment(
        session_id=session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
    )
    db.add(assignment)
    # Pair-context tag now lives on the relationships table
    # (15D PR 6b dropped Assignment.context).
    db.add(
        Relationship(
            session_id=session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            tag_1="real-context",
            status="active",
        )
    )
    db.flush()
    return assignment


def test_make_synthetic_row_shape(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="syn-row")
    instrument = ensure_default_instrument(db, session)
    _seed_pair_context_display_fields(db, instrument)
    response_fields = list(instrument.response_fields)
    display_fields = sorted(
        instrument.display_fields, key=lambda f: f.order
    )

    row = _make_synthetic_row(
        instrument=instrument,
        index=0,
        response_fields=response_fields,
        display_fields=display_fields,
    )

    assert row["assignment"].id == -1  # negative id, no real-id collision
    assert row["assignment"].reviewee.name == "Sample Reviewee 1"
    assert row["assignment"].reviewee.email_or_identifier == "sample1@example.edu"
    assert row["accepting"] is False
    assert row["is_complete"] is False
    assert row["missing_count"] == 0
    assert row["submitted_at"] is None

    # Five display_cells: Name + Email (locked rows from
    # ensure_default_instrument) + three pair_context entries.
    assert len(row["display_cells"]) == 5
    pair_context_cells = [
        c for c in row["display_cells"]
        if c["field"].source_type == "pair_context"
    ]
    assert len(pair_context_cells) == 3
    for cell in pair_context_cells:
        assert cell["value"] == "Sample pair context"
        assert cell["is_profile_link"] is False

    # response cells: two seed fields, both empty
    assert [c["value"] for c in row["cells"]] == ["", ""]


def test_synthetic_values_cover_all_d6_sources() -> None:
    expected_pairs = {
        ("reviewee", "name"),
        ("reviewee", "email_or_identifier"),
        ("reviewee", "tag_1"),
        ("reviewee", "tag_2"),
        ("reviewee", "tag_3"),
        ("reviewee", "profile_link"),
        ("pair_context", "1"),
        ("pair_context", "2"),
        ("pair_context", "3"),
    }
    assert set(_SYNTHETIC_VALUES_BY_SOURCE.keys()) == expected_pairs


def test_build_preview_context_zero_assignments_pads_three_synthetic(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user, code="prev-zero")
    instrument = ensure_default_instrument(db, session)
    _seed_pair_context_display_fields(db, instrument)

    context = build_preview_context(db=db, user=user, review_session=session)

    assert context["preview_mode"] is True
    assert len(context["instrument_groups"]) == 1
    rows = context["instrument_groups"][0]["rows"]
    assert len(rows) == 3
    assert all(r["assignment"].id < 0 for r in rows)
    assert [r["assignment"].reviewee.name for r in rows] == [
        "Sample Reviewee 1",
        "Sample Reviewee 2",
        "Sample Reviewee 3",
    ]


def test_build_preview_context_one_real_pads_to_three(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="prev-one")
    instrument = ensure_default_instrument(db, session)
    _seed_pair_context_display_fields(db, instrument)
    real = _add_real_assignment(db, session, reviewee_email="carol@example.edu")

    context = build_preview_context(db=db, user=user, review_session=session)

    rows = context["instrument_groups"][0]["rows"]
    assert len(rows) == 3
    assert rows[0]["assignment"].id == real.id  # real first
    assert rows[0]["assignment"].id > 0
    assert rows[1]["assignment"].id < 0
    assert rows[2]["assignment"].id < 0
    # pair_context_1 from the real assignment renders verbatim:
    real_pc1 = next(
        c for c in rows[0]["display_cells"]
        if c["field"].source_field == "1"
    )
    assert real_pc1["value"] == "real-context"


def test_build_preview_context_three_or_more_real_uses_only_real(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user, code="prev-many")
    instrument = ensure_default_instrument(db, session)
    _seed_pair_context_display_fields(db, instrument)
    a1 = _add_real_assignment(db, session, reviewee_email="c1@example.edu")
    a2 = _add_real_assignment(db, session, reviewee_email="c2@example.edu")
    a3 = _add_real_assignment(db, session, reviewee_email="c3@example.edu")
    _add_real_assignment(db, session, reviewee_email="c4@example.edu")
    _add_real_assignment(db, session, reviewee_email="c5@example.edu")

    context = build_preview_context(db=db, user=user, review_session=session)

    rows = context["instrument_groups"][0]["rows"]
    assert len(rows) == 3
    assert [r["assignment"].id for r in rows] == [a1.id, a2.id, a3.id]
    assert all(r["assignment"].id > 0 for r in rows)


def test_build_preview_context_forces_accepting_false_on_every_row(
    db: Session,
) -> None:
    """Even with a real assignment whose instrument is currently accepting
    responses, preview rows render accepting=False so the template's
    disabled_attr branch fires uniformly."""
    user = _user(db)
    session = _session(db, user, code="prev-accept")
    instrument = ensure_default_instrument(db, session)
    _seed_pair_context_display_fields(db, instrument)
    instrument.accepting_responses = True  # would normally show inputs enabled
    db.flush()
    _add_real_assignment(db, session, reviewee_email="c@example.edu")

    context = build_preview_context(db=db, user=user, review_session=session)
    for row in context["instrument_groups"][0]["rows"]:
        assert row["accepting"] is False


def test_build_preview_context_excludes_invisible_display_fields(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user, code="prev-vis")
    instrument = ensure_default_instrument(db, session)
    _seed_pair_context_display_fields(db, instrument)
    db.refresh(instrument)
    pair_two = next(
        f for f in instrument.display_fields if f.source_field == "2"
    )
    pair_two.visible = False
    db.flush()

    context = build_preview_context(db=db, user=user, review_session=session)
    headers = context["instrument_groups"][0]["display_fields"]
    labels = {h["label"] for h in headers}
    assert "Pair context 2" not in labels
    assert "Pair context 1" in labels
    assert "Pair context 3" in labels
