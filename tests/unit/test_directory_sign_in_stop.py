"""Why a roster's directory check stopped on the sign-in (segment 20G
rung 1): `directory_accounts.sign_in_stop`, carried on
`csv_imports.DirectoryCheck.stopped`. Nothing reads it yet."""

from __future__ import annotations

from cordware.graph import FakeDirectory, GraphError
from app.services import csv_imports, directory_accounts


class _Refuses(FakeDirectory):
    """Graph refusing the operator's token with ``kind``."""

    def __init__(self, kind: str, status: int) -> None:
        super().__init__()
        self._error = (kind, status)

    def find_users(self, address: str):
        raise GraphError(*self._error)


class _Down(FakeDirectory):
    """Graph failing for a reason renewing cannot cure."""

    def find_users(self, address: str):
        raise GraphError("server", 503)


ADDRESSES = ["a@example.edu", "b@example.edu", None, "not an address"]


def test_a_refused_token_is_a_sign_in_stop() -> None:
    assert csv_imports.directory_check(_Refuses("unauthorized", 401), ADDRESSES).stopped == "unauthorized"
    assert csv_imports.directory_check(_Refuses("forbidden", 403), ADDRESSES).stopped == "forbidden"


def test_no_token_is_a_sign_in_stop_when_there_was_an_address() -> None:
    assert csv_imports.directory_check(None, ADDRESSES).stopped == directory_accounts.NO_TOKEN
    assert csv_imports.directory_check(None, [None, "not an address"]).stopped is None
    assert csv_imports.directory_check(None, []).stopped is None


def test_an_answer_or_another_failure_is_not() -> None:
    assert csv_imports.directory_check(FakeDirectory(), ADDRESSES).stopped is None
    down = csv_imports.directory_check(_Down(), ADDRESSES)
    assert down.stopped is None and down.unchecked  # not checked, but not the sign-in


def test_each_roster_of_one_request_reads_its_own_outcomes() -> None:
    """Quick Setup and rehydrate check several rosters in one lookup: a
    roster with no address stops on nothing, whatever the others met."""
    first, empty = csv_imports.directory_checks(
        _Refuses("unauthorized", 401), [["a@example.edu"], []]
    )
    assert first.stopped == "unauthorized" and empty.stopped is None
