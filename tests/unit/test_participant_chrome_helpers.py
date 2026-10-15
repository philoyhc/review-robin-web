"""Pure helpers behind participant audit M8, M9 and M11
(`app/web/views/_participant_chrome.py`)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.web import views


@pytest.mark.parametrize(
    ("address", "masked"),
    [
        ("rae@example.edu", "r•••@example.edu"),
        ("R@x.org", "R•••@x.org"),
        ("@x.org", "•••@x.org"),
        ("not-an-address", "•••"),
        ("", "•••"),
        (None, "•••"),
    ],
)
def test_masked_email(address: str | None, masked: str) -> None:
    assert views.masked_email(address) == masked


def test_only_known_notices_show() -> None:
    assert views.me_notice("summary")
    assert views.me_notice("organizers")
    assert views.me_notice("<script>") is None
    assert views.me_notice(None) is None


@pytest.mark.parametrize(
    ("user", "participant"),
    [
        (None, True),
        (SimpleNamespace(is_operator=False, is_sys_admin=False), True),
        (SimpleNamespace(is_operator=True, is_sys_admin=False), False),
        (SimpleNamespace(is_operator=False, is_sys_admin=True), False),
        (SimpleNamespace(), True),  # a header identity carries neither flag
    ],
)
def test_uses_participant_chrome(user: object, participant: bool) -> None:
    assert views.uses_participant_chrome(user) is participant
