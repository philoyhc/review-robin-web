"""Rehydrate ships gated off. Segment 19N.

The pipeline works for unproblematic cases, which is exactly why the gate
needs a guard rather than a note: nothing in the running app looks wrong.
It was gated because a responses row the regenerated rules could not
place was dropped with a warning **surfaced nowhere** — not the
``session.rehydrated`` audit counts, not the route, not the operator —
against a ``spec/rehydrate.md`` §9 that promised *"no response is lost"*.
19N.1 slices 3a and 3b closed that: the row is dropped with a reason,
counted in the audit event, and handed to the operator as a CSV. **The
gate stays shut regardless**, because the author's reason was broader
than the one defect — nobody has run this on real data, and not every
detail is worked out. Re-opening it is a decision, not a consequence of
this file going green.

**Why this file exists.** ``tests/conftest.py`` sets
``REHYDRATE_ENABLED=true`` for the whole suite so the machinery stays
covered by its existing tests. That is the right trade, but it means every
other test runs with the gate *open* — a change that flipped the shipped
default would pass all of them. The first test below reads the default off
the ``Settings`` class rather than the live object, so the suite's own
environment cannot mask it.
"""

from __future__ import annotations

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.config import Settings


def test_the_shipped_default_is_off() -> None:
    """Read the field default, not ``settings.rehydrate_enabled``.

    The live object is ``True`` under this suite; what a deployment gets
    with no env var set is the question worth pinning.
    """
    assert Settings.model_fields["rehydrate_enabled"].default is False, (
        "rehydrate_enabled now ships ON. 19N.1 closed the data-loss "
        "defect that prompted the gate, but the author gated this on a "
        "broader reason — nobody has run it on real data. Flipping the "
        "default is their call, not a side effect of a green suite."
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/operator/sessions/rehydrate"),
        ("post", "/operator/sessions/rehydrate/validate"),
        ("post", "/operator/sessions/rehydrate/commit"),
        ("get", "/operator/sessions/rehydrate/dropped.csv"),
    ],
)
def test_every_route_404s_when_the_gate_is_shut(
    client: TestClient, monkeypatch, method: str, path: str
) -> None:
    """All three, because hiding the lobby button is not a gate.

    The validate and commit endpoints accept a POST from anyone who knows
    the path, so a gate on the page alone would leave the pipeline — and
    its data-loss case — reachable.

    The client is authenticated: an unauthenticated request returns 401
    before the gate runs, which would pass a naive "not 200" assertion
    while proving nothing about the gate.
    """
    from app.config import settings as live_settings

    monkeypatch.setattr(live_settings, "rehydrate_enabled", False)
    response = getattr(client, method)(path)
    assert response.status_code == status.HTTP_404_NOT_FOUND, (
        f"{method.upper()} {path} returned {response.status_code} "
        f"with the gate shut"
    )


def test_the_lobby_hides_the_button_when_the_gate_is_shut(
    client: TestClient, monkeypatch
) -> None:
    """A rendered button pointing at a 404 is worse than no button."""
    from app.config import settings as live_settings

    monkeypatch.setattr(live_settings, "rehydrate_enabled", False)
    body = client.get("/operator/sessions").text
    assert "/operator/sessions/rehydrate" not in body

    monkeypatch.setattr(live_settings, "rehydrate_enabled", True)
    body = client.get("/operator/sessions").text
    assert "/operator/sessions/rehydrate" in body, (
        "the button no longer renders even with the gate open, so the "
        "feature would be unreachable when 19N re-opens it"
    )
