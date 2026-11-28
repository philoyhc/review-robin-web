"""Addresses looked up in the directory on ingest (segment AD2Y rung 2):
`directory_check.look_up` asks and counts, `bind` stores what was found."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from applydesk import db, directory_check, people
from applydesk.models import Person
from cordware.graph import DirectoryUser, FakeDirectory, GraphError

pytestmark = pytest.mark.usefixtures("applydesk_db")

TENANT = "local-tenant"


def test_each_answer_is_counted() -> None:
    found = directory_check.look_up(
        FakeDirectory(),
        [
            "arun.kumar@example.edu",  # by mail
            "Arun.Kumar@example.edu ",  # the same address, once
            "e0123456@example.edu",  # by UPN, the account has a mail
            "lab01@example.edu",  # by UPN, no mail
            "nobody@example.edu",  # not found
            "office@example.edu",  # one account's mail, another's UPN
            "throttled@example.edu",  # not checked
        ],
    )
    assert found.counts == directory_check.Counts(
        by_mail=1, by_upn=2, not_found=1, ambiguous=1, not_checked=1
    )
    assert found.counts.found == 3
    assert found.unchecked_reason == "throttled"
    assert not found.stop
    assert found.resolved("ARUN.KUMAR@example.edu") is not None
    assert found.resolved("nobody@example.edu") is None


def test_no_directory_checks_nothing() -> None:
    found = directory_check.look_up(None, ["a@example.edu", "b@example.edu", "A@example.edu"])
    assert found.counts == directory_check.Counts(not_checked=2)
    assert found.unchecked_reason == directory_check.NO_TOKEN
    assert not found.stop


def test_nothing_to_look_up() -> None:
    found = directory_check.look_up(FakeDirectory(), ["", "  "])
    assert found.counts == directory_check.Counts() and found.unchecked_reason == ""


class _Expired:
    def find_users(self, address: str) -> list[DirectoryUser]:
        raise GraphError("unauthorized", 401)


def test_an_expired_sign_in_stops_the_upload() -> None:
    found = directory_check.look_up(_Expired(), ["a@example.edu", "b@example.edu"])
    assert found.stop
    assert found.counts.not_checked == 2 and found.unchecked_reason == "unauthorized"


def test_forbidden_does_not_stop() -> None:
    """Only an expired sign-in holds the upload (Review Robin's 20G):
    consent or scope saves, counted as not checked."""
    found = directory_check.look_up(FakeDirectory(), ["denied@example.edu"])
    assert not found.stop and found.unchecked_reason == "forbidden"


def test_bind_binds_what_was_found_and_leaves_the_rest() -> None:
    session = db.new_session()
    try:
        waiting = people.pending(session, "arun.kumar@example.edu", None)
        found = directory_check.look_up(
            FakeDirectory(), ["arun.kumar@example.edu", "e0123456@example.edu", "nobody@x.edu"]
        )
        bound = directory_check.bind(session, found, TENANT, None)
        session.commit()
        assert set(bound) == {"arun.kumar@example.edu", "e0123456@example.edu"}
        # The pending person is bound in place, keeping what they hold.
        assert bound["arun.kumar@example.edu"].id == waiting.id
        assert bound["arun.kumar@example.edu"].object_id == "22222222-2222-4222-8222-222222222222"
        # A UPN binds the account, its address the account's mail.
        assert bound["e0123456@example.edu"].email == "jane.tan@example.edu"
        assert session.scalar(select(Person).where(Person.email == "nobody@x.edu")) is None
    finally:
        session.close()


def test_bind_without_a_tenant_binds_nothing() -> None:
    session = db.new_session()
    try:
        found = directory_check.look_up(FakeDirectory(), ["arun.kumar@example.edu"])
        assert directory_check.bind(session, found, "", None) == {}
    finally:
        session.close()
