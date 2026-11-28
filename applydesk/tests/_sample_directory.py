"""The sample institution standing in as the directory (segment AD2Y), for
the browser tests that type its people into Panels: the directory finds
them, and those on a roster read as bound to it, as a saved roster's
would be."""

from __future__ import annotations

import uuid

import pytest

from applydesk import directory, panels_store, sample_data
from cordware.graph import DirectoryUser, FakeDirectory

#: The sample exercises whose institutions make up the directory here.
_EXERCISES = ("r6tm4kq9wz", "wa9juxbc2t")


def people() -> tuple[tuple[str, str], ...]:
    """The sample institution's people, as (name, email), each once."""
    found: dict[str, tuple[str, str]] = {}
    for exercise in _EXERCISES:
        members: list[tuple[str, str]] = sample_data.people_pools(exercise)["institution"][
            "members"
        ]
        for name, email in members:
            found.setdefault(email.lower(), (name, email))
    return tuple(found.values())


def use(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the sample institution the directory for this test."""
    everyone = people()
    users = tuple(
        DirectoryUser(str(uuid.uuid5(uuid.NAMESPACE_URL, f"mailto:{e.lower()}")), n, e, e)
        for n, e in everyone
    )
    known = {e.lower() for _, e in everyone}
    monkeypatch.setattr(directory, "for_request", lambda request: FakeDirectory(users))
    monkeypatch.setattr(
        panels_store,
        "bound_among",
        lambda addresses: frozenset(a.lower() for a in addresses if a.lower() in known),
    )
