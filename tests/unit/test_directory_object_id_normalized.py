"""Directory object ids are stored normalized (segment 20G rung 4):
stripped and lower-cased, so matching compares plainly. An answer with
no id binds nothing."""

from __future__ import annotations

from app.services import directory_accounts
from cordware.graph import DirectoryUser, Outcome


def _user(object_id: str) -> DirectoryUser:
    return DirectoryUser(
        id=object_id, display_name="Jane",
        mail="jane@example.edu", user_principal_name="e0123456@example.edu",
    )


def test_a_bound_account_is_stored_normalized() -> None:
    account = directory_accounts.account_of(
        Outcome("OK", "MAIL", user=_user(" 1A2B3C4D-AAAA-4BBB-8CCC-DDDDEEEEFFFF\t"))
    )
    assert account is not None
    assert account.object_id == "1a2b3c4d-aaaa-4bbb-8ccc-ddddeeeeffff"


def test_an_answer_with_no_id_binds_nothing() -> None:
    assert directory_accounts.account_of(Outcome("OK", "MAIL", user=_user("  "))) is None
