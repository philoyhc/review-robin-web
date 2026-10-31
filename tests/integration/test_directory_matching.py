"""Matching by directory account (segment 21F, rung 5): a roster row bound
to an account admits that account's sign-in, and only it; any other row
matches by mail as before. Self-review treats two rows bound to one
account as one person.

Two negative cases the plan names:
- the `office@` collision: a row given by one account's mail never
  admits the other account whose UPN that address is;
- a stored principal ID that differs from the token's binds nothing: the
  match reads this request's sign-in, never ``users.external_principal_id``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Assignment, Observer, Reviewee, Reviewer, ReviewSession, User
from app.services import assignments
from app.services.assignments._self_review import is_self_review
from app.services.instruments import ensure_default_instrument
from app.services.participants import Viewer, disclosable_roles, same_person
from app.services.rules.engine import _is_self_review

from .conftest import _make_client

JANE_OID = "11111111-1111-4111-8111-111111111111"
OFFICE_DESK_OID = "55555555-5555-4555-8555-555555555555"


def _identity(email: str, principal_id: str | None) -> AuthenticatedUser:
    return AuthenticatedUser(principal_id=principal_id, email=email, name="X", provider="aad")


@pytest.fixture
def as_user(db: Session) -> Iterator:
    from _rrw_app import rrw_app

    app = rrw_app()

    def sign_in(email: str, principal_id: str | None) -> TestClient:
        return _make_client(db, _identity(email, principal_id))

    yield sign_in
    app.dependency_overrides.clear()


def _open_session(db: Session, code: str) -> ReviewSession:
    owner = User(email=f"op-{code}@example.edu")
    db.add(owner)
    db.flush()
    review_session = ReviewSession(name=code.title(), code=code, created_by_user_id=owner.id, status="active")
    review_session.observers_enabled = True
    db.add(review_session)
    db.flush()
    return review_session


# --- the Viewer rule ---


def test_a_bound_row_is_its_accounts_alone() -> None:
    row = Reviewer(email="e0123456@example.edu", directory_object_id=JANE_OID)
    assert Viewer.from_parts("jane.tan@example.edu", JANE_OID).matches(row, row.email)
    assert Viewer.from_parts("jane.tan@example.edu", JANE_OID.upper()).matches(row, row.email)
    # Same address, another account, or no principal: no match.
    assert not Viewer.from_parts("e0123456@example.edu", OFFICE_DESK_OID).matches(row, row.email)
    assert not Viewer.from_parts("e0123456@example.edu", None).matches(row, row.email)


def test_an_unbound_row_matches_by_mail_as_before() -> None:
    row = Reviewer(email="Pat@Example.edu")
    assert Viewer.from_parts("pat@example.edu", "any-oid").matches(row, row.email)
    assert not Viewer.from_parts("e0123456@example.edu", JANE_OID).matches(row, row.email)


def test_the_office_collision_admits_neither_wrong_account() -> None:
    """`office@` is Wei Ling's mail and Office Desk's UPN. The roster row
    resolved AMBIGUOUS at upload, so it is unbound and matches by mail:
    Wei Ling, whose mail it is, signs in with it; Office Desk signs in
    with their mail, `office.desk@`, and never matches."""
    row = Reviewer(email="office@example.edu")
    assert Viewer.from_parts("office@example.edu", "44444444-4444-4444-8444-444444444444").matches(row, row.email)
    assert not Viewer.from_parts("office.desk@example.edu", OFFICE_DESK_OID).matches(row, row.email)


# --- through the routes, with the request's own sign-in ---


def test_a_row_given_by_upn_admits_its_account_through_the_gates(db: Session, as_user) -> None:
    session = _open_session(db, "match-gates")
    db.add(Observer(session_id=session.id, email="e0123456@example.edu", directory_object_id=JANE_OID))
    db.commit()
    jane = as_user("jane.tan@example.edu", JANE_OID)
    assert jane.get(f"/me/sessions/{session.public_id}/collation").status_code == 200


def test_a_stored_principal_from_an_earlier_holder_binds_nothing(db: Session, as_user) -> None:
    """The `users` row for `jane.tan@` carries Jane's old object ID, but
    the token is a new account's: the bound row must not follow the
    address to it (Codex, #3424)."""
    session = _open_session(db, "match-stale")
    db.add(User(email="jane.tan@example.edu", external_principal_id=JANE_OID))
    db.add(Observer(session_id=session.id, email="jane.tan@example.edu", directory_object_id=JANE_OID))
    db.commit()
    newcomer = as_user("jane.tan@example.edu", "99999999-9999-4999-8999-999999999999")
    assert newcomer.get(f"/me/sessions/{session.public_id}/collation").status_code == 404


def test_the_dashboard_and_role_disclosure_follow_the_account(db: Session, as_user) -> None:
    session = _open_session(db, "match-dash")
    db.add(Reviewer(session_id=session.id, name="Jane", email="e0123456@example.edu", directory_object_id=JANE_OID))
    db.commit()
    page = as_user("jane.tan@example.edu", JANE_OID).get("/me")
    assert session.name in page.text
    assert disclosable_roles(db, "jane.tan@example.edu", principal_id=JANE_OID) == {"reviewer"}
    assert disclosable_roles(db, "e0123456@example.edu", principal_id=None) == frozenset()


# --- one person across rosters ---


def test_rows_bound_to_one_account_are_one_person() -> None:
    reviewer = Reviewer(email="e0123456@example.edu", directory_object_id=JANE_OID)
    reviewee = Reviewee(email_or_identifier="jane.tan@example.edu", directory_object_id=JANE_OID.upper())
    other = Reviewee(email_or_identifier="e0123456@example.edu", directory_object_id=OFFICE_DESK_OID)
    assert is_self_review(reviewer, reviewee)
    assert _is_self_review(reviewer, reviewee)
    assert same_person(reviewer, reviewer.email, reviewee, reviewee.email_or_identifier)
    # Two bound rows on different accounts are two people, whatever the address.
    assert not is_self_review(reviewer, other)
    assert not _is_self_review(reviewer, other)
    # A bound row and an unbound one fall back to the address.
    unbound = Reviewee(email_or_identifier="e0123456@example.edu")
    assert is_self_review(reviewer, unbound)


def test_group_self_review_finds_a_member_by_account(db: Session) -> None:
    """The whole-group rule's membership comes off the roster: Jane the
    reviewer (by UPN) is a member of the group Jane the reviewee (by
    mail) sits in, so every row in that group is a self-review."""
    session = _open_session(db, "match-group")
    session.status = "draft"
    jane_r = Reviewer(session_id=session.id, name="Jane", email="e0123456@example.edu", directory_object_id=JANE_OID)
    jane_e = Reviewee(
        session_id=session.id, name="Jane", email_or_identifier="jane.tan@example.edu", directory_object_id=JANE_OID
    )
    carol_e = Reviewee(session_id=session.id, name="Carol", email_or_identifier="carol@example.edu")
    db.add_all([jane_r, jane_e, carol_e])
    db.flush()
    instrument = ensure_default_instrument(db, session)
    instrument.group_kind = "both"
    db.flush()
    rows = [
        Assignment(session_id=session.id, reviewer_id=jane_r.id, reviewee_id=e.id, instrument_id=instrument.id)
        for e in (jane_e, carol_e)
    ]
    db.add_all(rows)
    db.flush()
    assignments.recompute_self_review_classification(db, session_id=session.id)
    assert [r.is_self_review for r in rows] == [True, True]
