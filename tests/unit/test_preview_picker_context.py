from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services.instruments import ensure_default_instrument
from app.web import views


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


def _reviewer(
    db: Session, session: ReviewSession, *, name: str, email: str
) -> Reviewer:
    r = Reviewer(session_id=session.id, name=name, email=email)
    db.add(r)
    db.flush()
    return r


def _reviewee(
    db: Session, session: ReviewSession, *, name: str, email: str
) -> Reviewee:
    e = Reviewee(
        session_id=session.id, name=name, email_or_identifier=email
    )
    db.add(e)
    db.flush()
    return e


def _assign(
    db: Session,
    session: ReviewSession,
    reviewer: Reviewer,
    reviewee: Reviewee,
    *,
    include: bool = True,
) -> Assignment:
    instrument = ensure_default_instrument(db, session)
    a = Assignment(
        session_id=session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=include,
    )
    db.add(a)
    db.flush()
    return a


def test_empty_session_returns_no_options(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="pp-empty")

    ctx = views.build_preview_picker_context(db, session, "")

    assert ctx.options == []
    assert ctx.current is None
    assert ctx.current_index is None
    assert ctx.prev_email is None
    assert ctx.next_email is None
    assert ctx.reviewee_count == 0
    assert ctx.no_match_query is None
    assert ctx.raw_query == ""


def test_no_query_yields_unselected_state_with_options(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="pp-unsel")
    _reviewer(db, session, name="Alice Smith", email="alice@x.edu")
    _reviewer(db, session, name="Bob Jones", email="bob@x.edu")

    ctx = views.build_preview_picker_context(db, session, "")

    assert [o.email for o in ctx.options] == ["alice@x.edu", "bob@x.edu"]
    assert ctx.current is None
    assert ctx.no_match_query is None
    assert ctx.prev_email is None and ctx.next_email is None


def test_options_sorted_alphabetically_by_email(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="pp-sort")
    _reviewer(db, session, name="Carol", email="carol@x.edu")
    _reviewer(db, session, name="Alice", email="alice@x.edu")
    _reviewer(db, session, name="Bob", email="bob@x.edu")

    ctx = views.build_preview_picker_context(db, session, "")

    assert [o.email for o in ctx.options] == [
        "alice@x.edu",
        "bob@x.edu",
        "carol@x.edu",
    ]


def test_valid_email_resolves_current_and_index(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="pp-resolve")
    _reviewer(db, session, name="Alice", email="alice@x.edu")
    _reviewer(db, session, name="Bob", email="bob@x.edu")
    _reviewer(db, session, name="Carol", email="carol@x.edu")

    ctx = views.build_preview_picker_context(db, session, "bob@x.edu")

    assert ctx.current is not None
    assert ctx.current.email == "bob@x.edu"
    assert ctx.current_index == 1
    assert ctx.prev_email == "alice@x.edu"
    assert ctx.next_email == "carol@x.edu"
    assert ctx.no_match_query is None


def test_email_match_is_case_insensitive(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="pp-case")
    _reviewer(db, session, name="Alice", email="Alice@X.edu")

    ctx = views.build_preview_picker_context(db, session, "ALICE@x.EDU")

    assert ctx.current is not None
    assert ctx.current.email == "Alice@X.edu"


def test_label_format_value_extracts_email(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="pp-label")
    _reviewer(db, session, name="Alice Smith", email="alice@x.edu")

    ctx = views.build_preview_picker_context(
        db, session, "Alice Smith (alice@x.edu)"
    )

    assert ctx.current is not None
    assert ctx.current.email == "alice@x.edu"
    assert ctx.no_match_query is None


def test_unmatched_query_surfaces_no_match(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="pp-nomatch")
    _reviewer(db, session, name="Alice", email="alice@x.edu")

    ctx = views.build_preview_picker_context(db, session, "ghost@x.edu")

    assert ctx.current is None
    assert ctx.current_index is None
    assert ctx.no_match_query == "ghost@x.edu"


def test_whitespace_only_query_is_treated_as_empty(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="pp-ws")
    _reviewer(db, session, name="Alice", email="alice@x.edu")

    ctx = views.build_preview_picker_context(db, session, "   ")

    assert ctx.raw_query == ""
    assert ctx.current is None
    assert ctx.no_match_query is None


def test_prev_wraps_from_first_to_last(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="pp-wrap-first")
    _reviewer(db, session, name="A", email="a@x.edu")
    _reviewer(db, session, name="B", email="b@x.edu")
    _reviewer(db, session, name="C", email="c@x.edu")

    ctx = views.build_preview_picker_context(db, session, "a@x.edu")

    assert ctx.current_index == 0
    assert ctx.prev_email == "c@x.edu"
    assert ctx.next_email == "b@x.edu"


def test_next_wraps_from_last_to_first(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="pp-wrap-last")
    _reviewer(db, session, name="A", email="a@x.edu")
    _reviewer(db, session, name="B", email="b@x.edu")
    _reviewer(db, session, name="C", email="c@x.edu")

    ctx = views.build_preview_picker_context(db, session, "c@x.edu")

    assert ctx.current_index == 2
    assert ctx.prev_email == "b@x.edu"
    assert ctx.next_email == "a@x.edu"


def test_single_reviewer_prev_and_next_wrap_to_self(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="pp-solo")
    _reviewer(db, session, name="Solo", email="solo@x.edu")

    ctx = views.build_preview_picker_context(db, session, "solo@x.edu")

    assert ctx.current_index == 0
    assert ctx.prev_email == "solo@x.edu"
    assert ctx.next_email == "solo@x.edu"


def test_reviewee_count_and_peek_tail_split(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="pp-peek")
    alice = _reviewer(db, session, name="Alice", email="alice@x.edu")
    # Five reviewees, names will sort as Bob, Carol, Dan, Eve, Fred
    revs = [
        _reviewee(db, session, name=n, email=f"{n.lower()}@x.edu")
        for n in ("Bob", "Carol", "Dan", "Eve", "Fred")
    ]
    for r in revs:
        _assign(db, session, alice, r)

    ctx = views.build_preview_picker_context(db, session, "alice@x.edu")

    assert ctx.reviewee_count == 5
    assert ctx.reviewee_peek == ["Bob", "Carol", "Dan"]
    assert ctx.reviewee_tail == ["Eve", "Fred"]


def test_reviewee_excludes_assignments_with_include_false(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="pp-incl")
    alice = _reviewer(db, session, name="Alice", email="alice@x.edu")
    bob = _reviewee(db, session, name="Bob", email="bob@x.edu")
    carol = _reviewee(db, session, name="Carol", email="carol@x.edu")
    _assign(db, session, alice, bob, include=True)
    _assign(db, session, alice, carol, include=False)

    ctx = views.build_preview_picker_context(db, session, "alice@x.edu")

    assert ctx.reviewee_count == 1
    assert ctx.reviewee_peek == ["Bob"]


def test_reviewer_with_no_assignments_has_zero_reviewees(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="pp-zero")
    _reviewer(db, session, name="Lonely", email="lonely@x.edu")

    ctx = views.build_preview_picker_context(db, session, "lonely@x.edu")

    assert ctx.current is not None
    assert ctx.reviewee_count == 0
    assert ctx.reviewee_peek == []
    assert ctx.reviewee_tail == []


def test_option_label_is_name_paren_email(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="pp-label-fmt")
    _reviewer(db, session, name="Alice Smith", email="alice@x.edu")

    ctx = views.build_preview_picker_context(db, session, "")

    assert ctx.options[0].label == "Alice Smith (alice@x.edu)"


def test_isolates_reviewers_to_session(db: Session) -> None:
    """Reviewers belonging to a different session must not appear."""
    user = _user(db)
    s1 = _session(db, user, code="pp-iso-1")
    s2 = _session(db, user, code="pp-iso-2")
    _reviewer(db, s1, name="One", email="one@x.edu")
    _reviewer(db, s2, name="Two", email="two@x.edu")

    ctx = views.build_preview_picker_context(db, s1, "")

    assert [o.email for o in ctx.options] == ["one@x.edu"]
