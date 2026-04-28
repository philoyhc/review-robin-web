from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, User
from app.services.assignments import parse_manual_csv


def _user(db: Session) -> User:
    user = User(email="op@example.edu")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, user: User) -> ReviewSession:
    s = ReviewSession(name="Spring", code="spring", created_by_user_id=user.id)
    db.add(s)
    db.flush()
    return s


def _reviewer(db: Session, session_id: int, name: str, email: str) -> Reviewer:
    r = Reviewer(session_id=session_id, name=name, email=email)
    db.add(r)
    db.flush()
    return r


def _reviewee(db: Session, session_id: int, name: str, ident: str) -> Reviewee:
    r = Reviewee(session_id=session_id, name=name, email_or_identifier=ident)
    db.add(r)
    db.flush()
    return r


def test_valid_manual_csv_parses(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    alice = _reviewer(db, session.id, "Alice", "alice@example.edu")
    bob = _reviewer(db, session.id, "Bob", "bob@example.edu")
    carol = _reviewee(db, session.id, "Carol", "carol@example.edu")
    dan = _reviewee(db, session.id, "Dan", "dan-2026")

    csv = (
        b"ReviewerEmail,RevieweeEmail\n"
        b"alice@example.edu,carol@example.edu\n"
        b"bob@example.edu,dan-2026\n"
    )
    result = parse_manual_csv(csv, [alice, bob], [carol, dan])

    assert result.issues == []
    assert len(result.rows) == 2
    assert result.rows[0].reviewer_id == alice.id
    assert result.rows[0].reviewee_id == carol.id
    assert result.rows[0].include is True


def test_unknown_reviewer_email_blocks(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    alice = _reviewer(db, session.id, "Alice", "alice@example.edu")
    carol = _reviewee(db, session.id, "Carol", "carol@example.edu")

    csv = (
        b"ReviewerEmail,RevieweeEmail\n"
        b"ghost@example.edu,carol@example.edu\n"
    )
    result = parse_manual_csv(csv, [alice], [carol])

    assert result.is_blocked
    assert result.rows == []
    assert any("Unknown reviewer" in i.message for i in result.issues)


def test_unknown_reviewee_identifier_blocks(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    alice = _reviewer(db, session.id, "Alice", "alice@example.edu")
    carol = _reviewee(db, session.id, "Carol", "carol@example.edu")

    csv = (
        b"ReviewerEmail,RevieweeEmail\n"
        b"alice@example.edu,ghost@example.edu\n"
    )
    result = parse_manual_csv(csv, [alice], [carol])

    assert result.is_blocked
    assert any("Unknown reviewee" in i.message for i in result.issues)


def test_duplicate_pair_blocks_and_points_to_prior_row(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    alice = _reviewer(db, session.id, "Alice", "alice@example.edu")
    carol = _reviewee(db, session.id, "Carol", "carol@example.edu")

    csv = (
        b"ReviewerEmail,RevieweeEmail\n"
        b"alice@example.edu,carol@example.edu\n"
        b"alice@example.edu,carol@example.edu\n"
    )
    result = parse_manual_csv(csv, [alice], [carol])

    assert result.is_blocked
    dup = next(i for i in result.issues if "Duplicate" in i.message)
    assert dup.row_number == 2
    assert "row 1" in dup.message


def test_include_assignment_truthy_falsy_and_default(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    alice = _reviewer(db, session.id, "Alice", "alice@example.edu")
    bob = _reviewer(db, session.id, "Bob", "bob@example.edu")
    eve = _reviewer(db, session.id, "Eve", "eve@example.edu")
    carol = _reviewee(db, session.id, "Carol", "carol@example.edu")

    csv = (
        b"ReviewerEmail,RevieweeEmail,IncludeAssignment\n"
        b"alice@example.edu,carol@example.edu,true\n"
        b"bob@example.edu,carol@example.edu,no\n"
        b"eve@example.edu,carol@example.edu,\n"
    )
    result = parse_manual_csv(csv, [alice, bob, eve], [carol])

    assert result.issues == []
    by_reviewer_email = {r.reviewer_email: r for r in result.rows}
    assert by_reviewer_email["alice@example.edu"].include is True
    assert by_reviewer_email["bob@example.edu"].include is False
    assert by_reviewer_email["eve@example.edu"].include is True


def test_unparseable_include_blocks(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    alice = _reviewer(db, session.id, "Alice", "alice@example.edu")
    carol = _reviewee(db, session.id, "Carol", "carol@example.edu")

    csv = (
        b"ReviewerEmail,RevieweeEmail,IncludeAssignment\n"
        b"alice@example.edu,carol@example.edu,maybe\n"
    )
    result = parse_manual_csv(csv, [alice], [carol])

    assert result.is_blocked
    assert any("not a recognised true/false" in i.message for i in result.issues)


def test_assignment_context_columns_carried(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    alice = _reviewer(db, session.id, "Alice", "alice@example.edu")
    carol = _reviewee(db, session.id, "Carol", "carol@example.edu")

    csv = (
        b"ReviewerEmail,RevieweeEmail,AssignmentContext1,AssignmentContext2\n"
        b"alice@example.edu,carol@example.edu,morning,room-A\n"
    )
    result = parse_manual_csv(csv, [alice], [carol])

    assert result.issues == []
    row = result.rows[0]
    assert row.assignment_context_1 == "morning"
    assert row.assignment_context_2 == "room-A"
    assert row.assignment_context_3 is None
    assert row.pair_context_1 is None


def test_pair_context_columns_carried(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    alice = _reviewer(db, session.id, "Alice", "alice@example.edu")
    carol = _reviewee(db, session.id, "Carol", "carol@example.edu")

    csv = (
        b"ReviewerEmail,RevieweeEmail,PairContext1,PairContext2,PairContext3\n"
        b"alice@example.edu,carol@example.edu,morning,room-A,note\n"
    )
    result = parse_manual_csv(csv, [alice], [carol])

    assert result.issues == []
    row = result.rows[0]
    assert row.pair_context_1 == "morning"
    assert row.pair_context_2 == "room-A"
    assert row.pair_context_3 == "note"
    assert row.assignment_context_1 is None


def test_pair_and_assignment_context_columns_independent(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    alice = _reviewer(db, session.id, "Alice", "alice@example.edu")
    carol = _reviewee(db, session.id, "Carol", "carol@example.edu")

    csv = (
        b"ReviewerEmail,RevieweeEmail,PairContext1,AssignmentContext1\n"
        b"alice@example.edu,carol@example.edu,room-A,panel-1\n"
    )
    result = parse_manual_csv(csv, [alice], [carol])

    assert result.issues == []
    row = result.rows[0]
    assert row.pair_context_1 == "room-A"
    assert row.assignment_context_1 == "panel-1"


def test_missing_required_column_blocks(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    alice = _reviewer(db, session.id, "Alice", "alice@example.edu")
    carol = _reviewee(db, session.id, "Carol", "carol@example.edu")

    csv = b"ReviewerEmail\nalice@example.edu\n"
    result = parse_manual_csv(csv, [alice], [carol])

    assert result.is_blocked
    assert any(i.field == "RevieweeEmail" for i in result.issues)


def test_parsed_rows_carry_roster_names(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    alice = _reviewer(db, session.id, "Alice Example", "alice@example.edu")
    carol = _reviewee(db, session.id, "Carol Example", "carol@example.edu")

    csv = (
        b"ReviewerEmail,RevieweeEmail\n"
        b"alice@example.edu,carol@example.edu\n"
    )
    result = parse_manual_csv(csv, [alice], [carol])

    assert result.issues == []
    row = result.rows[0]
    assert row.reviewer_name == "Alice Example"
    assert row.reviewee_name == "Carol Example"
