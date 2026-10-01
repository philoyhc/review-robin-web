"""What a reviewer reads back of their own answers (post_assessment G10).

``visibility_policies.reviewer_sees_own_responses`` decides from the
instrument's ``peer_reviewer`` policy (``spec/reviewer-surface.md``
"Lifecycle gating"): always while ``ready``; after close only for a Raw
"Responses released" cell inside the release window; never once
archived, and never in ``draft`` / ``validated``.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

from app.services import session_lifecycle as lifecycle
from app.services import visibility_policies

_NOW = dt.datetime(2026, 10, 1, 12, tzinfo=dt.timezone.utc)
_PAIRS = {
    "raw": ("row", "identified"),
    "summarized": ("aggregated", "deidentified"),
    None: (None, None),
}


def _session(status: str, *, released: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        responses_release_at=_NOW - dt.timedelta(hours=1) if released else None,
        responses_release_until=None,
    )


def _policy(after_release: str | None) -> SimpleNamespace:
    granularity, identification = _PAIRS[after_release]
    return SimpleNamespace(
        while_ongoing_granularity="row",
        while_ongoing_identification="identified",
        after_release_granularity=granularity,
        after_release_identification=identification,
    )


@pytest.mark.parametrize(
    ("status", "released", "after_release", "expected"),
    [
        ("ready", False, None, True),
        ("expired", True, "raw", True),
        ("expired", True, "summarized", False),
        ("expired", True, None, False),
        ("expired", False, "raw", False),
        ("draft", True, "raw", False),
        ("validated", True, "raw", False),
        ("archived", True, "raw", False),
    ],
)
def test_the_rule(
    status: str, released: bool, after_release: str | None, expected: bool
) -> None:
    assert (
        visibility_policies.reviewer_sees_own_responses(
            _session(status, released=released), _policy(after_release), now=_NOW
        )
        is expected
    )


def test_ready_shows_even_with_no_policy_row() -> None:
    """The ``while_ongoing`` reviewer cell is Raw by rule, so a missing
    row reads the same while the session is ready."""
    assert visibility_policies.reviewer_sees_own_responses(
        _session("ready"), None, now=_NOW
    )


def test_archived_is_refused_before_any_window_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The archive check is its own guard, not an accident of the window
    predicates (``spec/visibility_policy.md`` §3.3): relax them and an
    archived session still shows nothing."""
    monkeypatch.setattr(lifecycle, "is_ready", lambda _session: True)
    monkeypatch.setattr(lifecycle, "is_expired", lambda _session: True)
    monkeypatch.setattr(
        lifecycle, "is_response_release_window_open", lambda *a, **k: True
    )
    assert not visibility_policies.reviewer_sees_own_responses(
        _session("archived", released=True), _policy("raw"), now=_NOW
    )
