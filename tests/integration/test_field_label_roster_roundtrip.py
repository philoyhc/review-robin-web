"""Segment 19C Item 1 — roster-CSV friendly labels: full round-trip.

Import (header suffix → ``session_field_labels``) → resolve → export
(``session_field_labels`` → header suffix), plus the bare-header-clears
rule that mirrors the roster's wipe-and-replace semantics. Exercises the
save-function path, which is the same one rehydrate calls.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, User
from app.services import csv_imports, field_labels, relationships
from app.services.extracts import (
    relationships_extract,
    reviewers_extract,
)


def _b(text: str) -> bytes:
    return text.encode("utf-8")


def _seed(db: Session, code: str = "flrt") -> tuple[User, ReviewSession]:
    user = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="FL round-trip", code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    return user, review_session


def _import_reviewers(
    db: Session, user: User, session: ReviewSession, csv_text: str
) -> None:
    parsed = csv_imports.parse_reviewer_csv(_b(csv_text))
    assert not parsed.is_blocked, parsed.issues
    csv_imports.save_reviewers(
        db,
        session=session,
        user=user,
        rows=parsed.rows,
        filename="reviewers.csv",
        correlation_id="t",
        field_labels_captured=parsed.field_labels,
    )
    db.expire_all()


def test_reviewer_label_imports_from_header(db: Session) -> None:
    user, session = _seed(db, "fl-imp")
    _import_reviewers(
        db,
        user,
        session,
        "ReviewerName,ReviewerEmail,ReviewerTag1.Tutor\n"
        "Alice,alice@example.edu,senior\n",
    )
    assert field_labels.resolve(session, "reviewer", "tag_1") == "Tutor"


def test_reviewer_label_exports_into_header(db: Session) -> None:
    user, session = _seed(db, "fl-exp")
    _import_reviewers(
        db,
        user,
        session,
        "ReviewerName,ReviewerEmail,ReviewerTag1.Tutor\n"
        "Alice,alice@example.edu,senior\n",
    )
    header = next(iter(reviewers_extract.serialize_reviewers(db, session)))
    assert "ReviewerTag1.Tutor" in header
    # A slot on its default stays bare (no fabricated "Tag 2" suffix).
    assert "ReviewerTag2" in header
    assert "ReviewerTag2." not in "".join(header)


def test_reexport_reimport_round_trips(db: Session) -> None:
    user, session = _seed(db, "fl-rt")
    _import_reviewers(
        db,
        user,
        session,
        "ReviewerName,ReviewerEmail,ReviewerTag1.Tutor\n"
        "Alice,alice@example.edu,senior\n",
    )
    rows = list(reviewers_extract.serialize_reviewers(db, session))
    # Rebuild a CSV from the export and re-import it into a fresh session.
    csv_text = "\n".join(",".join(r) for r in rows) + "\n"
    user2, session2 = _seed(db, "fl-rt2")
    _import_reviewers(db, user2, session2, csv_text)
    assert field_labels.resolve(session2, "reviewer", "tag_1") == "Tutor"


def test_bare_header_clears_existing_label(db: Session) -> None:
    """Wipe-and-replace: re-importing with a bare tag header clears the
    override (mirrors the tag value re-importing as NULL)."""
    user, session = _seed(db, "fl-clear")
    _import_reviewers(
        db,
        user,
        session,
        "ReviewerName,ReviewerEmail,ReviewerTag1.Tutor\n"
        "Alice,alice@example.edu,senior\n",
    )
    assert field_labels.resolve(session, "reviewer", "tag_1") == "Tutor"

    # Re-import the same roster with a bare tag header.
    _import_reviewers(
        db,
        user,
        session,
        "ReviewerName,ReviewerEmail,ReviewerTag1\n"
        "Alice,alice@example.edu,senior\n",
    )
    # Cleared → resolves back to the built-in default.
    assert field_labels.resolve(session, "reviewer", "tag_1") == "Tag 1"


def test_absent_tag_column_clears_label(db: Session) -> None:
    """A roster file that omits the tag column entirely also clears its
    label — the file is the complete truth."""
    user, session = _seed(db, "fl-absent")
    _import_reviewers(
        db,
        user,
        session,
        "ReviewerName,ReviewerEmail,ReviewerTag1.Tutor\n"
        "Alice,alice@example.edu,senior\n",
    )
    _import_reviewers(
        db,
        user,
        session,
        "ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
    )
    assert field_labels.resolve(session, "reviewer", "tag_1") == "Tag 1"


def test_pair_context_label_round_trips(db: Session) -> None:
    user, session = _seed(db, "fl-pair")
    _import_reviewers(
        db,
        user,
        session,
        "ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
    )
    reviewees_parse = csv_imports.parse_reviewee_csv(
        _b("RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n")
    )
    csv_imports.save_reviewees(
        db,
        session=session,
        user=user,
        rows=reviewees_parse.rows,
        filename="reviewees.csv",
        correlation_id="t",
        field_labels_captured=reviewees_parse.field_labels,
    )
    db.expire_all()

    roster_reviewers = list(
        db.execute(
            select(Reviewer).where(Reviewer.session_id == session.id)
        ).scalars()
    )
    roster_reviewees = list(
        db.execute(
            select(Reviewee).where(Reviewee.session_id == session.id)
        ).scalars()
    )
    rel_parse = relationships.parse_relationship_csv(
        _b(
            "ReviewerEmail,RevieweeEmail,PairContextTag1.Mentor of\n"
            "alice@example.edu,carol@example.edu,cohort-a\n"
        ),
        reviewers=roster_reviewers,
        reviewees=roster_reviewees,
    )
    assert not rel_parse.is_blocked, rel_parse.issues
    relationships.save_relationships(
        db,
        session=session,
        user=user,
        rows=rel_parse.rows,
        filename="relationships.csv",
        correlation_id="t",
        field_labels_captured=rel_parse.field_labels,
    )
    db.expire_all()

    assert field_labels.resolve(session, "pair_context", "1") == "Mentor of"
    header = next(
        iter(relationships_extract.serialize_relationships(db, session))
    )
    assert "PairContextTag1.Mentor of" in header
