"""What stops a roster's directory check, and why addresses went
unchecked (segment 20G): `directory_accounts.sign_in_stop` and
`unchecked_reason`, carried on `csv_imports.DirectoryCheck`. Only an
expired token (Graph's ``unauthorized``) stops an upload and asks to
renew (author, 2026-11-03); every other failure saves, and the import
records why."""

from __future__ import annotations

from app.services import csv_imports, directory_accounts
from cordware.graph import FakeDirectory, GraphError


class _Refuses(FakeDirectory):
    """Graph failing every lookup with ``kind``."""

    def __init__(self, kind: str, status: int) -> None:
        super().__init__()
        self._error = (kind, status)

    def find_users(self, address: str):
        raise GraphError(*self._error)


ADDRESSES = ["a@example.edu", "b@example.edu", None, "not an address"]


def test_only_an_expired_token_stops_the_upload() -> None:
    check = csv_imports.directory_check(_Refuses("unauthorized", 401), ADDRESSES)
    assert check.stopped == directory_accounts.RENEWABLE_KIND == "unauthorized"
    assert check.unchecked_reason == "unauthorized"


def test_no_token_and_forbidden_save_and_say_why() -> None:
    """Renewing cures neither: no token means the token store is off or
    the sign-in did not ask for Graph, and ``forbidden`` is consent or
    scope. They save, unchecked, with the reason recorded."""
    none = csv_imports.directory_check(None, ADDRESSES)
    assert none.stopped is None and none.unchecked_reason == directory_accounts.NO_TOKEN
    forbidden = csv_imports.directory_check(_Refuses("forbidden", 403), ADDRESSES)
    assert forbidden.stopped is None and forbidden.unchecked_reason == "forbidden"


def test_an_outage_or_throttling_saves_and_says_why() -> None:
    for kind, status in (("server", 503), ("throttled", 429)):
        check = csv_imports.directory_check(_Refuses(kind, status), ADDRESSES)
        assert check.stopped is None and check.unchecked_reason == kind and check.unchecked


def test_every_address_answered_records_no_reason() -> None:
    check = csv_imports.directory_check(FakeDirectory(), ADDRESSES)
    assert check.stopped is None and check.unchecked_reason is None
    assert csv_imports.directory_check(None, [None, "not an address"]).unchecked_reason is None


def test_each_roster_of_one_request_reads_its_own_outcomes() -> None:
    """Quick Setup and rehydrate check several rosters in one lookup: a
    roster with no address stops on nothing, whatever the others met."""
    first, empty = csv_imports.directory_checks(
        _Refuses("unauthorized", 401), [["a@example.edu"], []]
    )
    assert first.stopped == "unauthorized" and empty.stopped is None
