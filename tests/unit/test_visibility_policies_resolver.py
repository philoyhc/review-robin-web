"""Unit tests for ``visibility_policies.resolve_mode`` +
``decode_pair_to_mode``.

Pins the resolver contract used by the reviewee / observer
results surfaces: given a persisted policy row + the two
window-open booleans, pick the operator-facing mode that
applies right now (or ``None`` for "off").

See ``spec/visibility_policy.md`` §3 and
``guide/archive/participant_model_upgrade.md`` §3.3.
"""

from __future__ import annotations

from app.db.models import InstrumentViewPolicy
from app.services import visibility_policies


def _policy(
    *,
    audience: str = "reviewee",
    while_ongoing_granularity: str | None = None,
    while_ongoing_identification: str | None = None,
    after_release_granularity: str | None = None,
    after_release_identification: str | None = None,
    observer_tag: str | None = None,
) -> InstrumentViewPolicy:
    """Build a detached policy row in memory — the resolver only
    reads attributes, no Session attachment required."""
    return InstrumentViewPolicy(
        instrument_id=1,
        audience=audience,
        while_ongoing_granularity=while_ongoing_granularity,
        while_ongoing_identification=while_ongoing_identification,
        after_release_granularity=after_release_granularity,
        after_release_identification=after_release_identification,
        observer_tag=observer_tag,
    )


# ── decode_pair_to_mode ──────────────────────────────────────────────


def test_decode_pair_to_mode_three_coherent_modes() -> None:
    assert (
        visibility_policies.decode_pair_to_mode("row", "identified")
        == "raw"
    )
    assert (
        visibility_policies.decode_pair_to_mode("row", "deidentified")
        == "anonymized"
    )
    assert (
        visibility_policies.decode_pair_to_mode("aggregated", "deidentified")
        == "summarized"
    )


def test_decode_pair_to_mode_null_either_side_is_off() -> None:
    assert visibility_policies.decode_pair_to_mode(None, "identified") is None
    assert visibility_policies.decode_pair_to_mode("row", None) is None
    assert visibility_policies.decode_pair_to_mode(None, None) is None


def test_decode_pair_to_mode_reserved_incoherent_pair_returns_none() -> None:
    """``aggregated`` + ``identified`` is reserved-incoherent —
    decoder returns ``None`` rather than raising so a corrupt row
    renders as "off" instead of 500ing on render."""
    assert (
        visibility_policies.decode_pair_to_mode("aggregated", "identified")
        is None
    )


# ── resolve_mode ─────────────────────────────────────────────────────


def test_resolve_mode_returns_none_for_missing_policy() -> None:
    assert (
        visibility_policies.resolve_mode(
            None, while_ongoing_open=True, after_release_open=True
        )
        is None
    )


def test_resolve_mode_returns_none_when_both_windows_closed() -> None:
    """A persisted policy with both windows on still reads as
    off when no session-level window is currently open."""
    policy = _policy(
        while_ongoing_granularity="row",
        while_ongoing_identification="identified",
        after_release_granularity="row",
        after_release_identification="identified",
    )
    assert (
        visibility_policies.resolve_mode(
            policy, while_ongoing_open=False, after_release_open=False
        )
        is None
    )


def test_resolve_mode_picks_while_ongoing_when_only_that_window_open() -> None:
    policy = _policy(
        while_ongoing_granularity="row",
        while_ongoing_identification="identified",
        after_release_granularity="row",
        after_release_identification="deidentified",
    )
    assert (
        visibility_policies.resolve_mode(
            policy, while_ongoing_open=True, after_release_open=False
        )
        == "raw"
    )


def test_resolve_mode_picks_after_release_when_only_that_window_open() -> None:
    policy = _policy(
        while_ongoing_granularity="row",
        while_ongoing_identification="identified",
        after_release_granularity="aggregated",
        after_release_identification="deidentified",
    )
    assert (
        visibility_policies.resolve_mode(
            policy, while_ongoing_open=False, after_release_open=True
        )
        == "summarized"
    )


def test_resolve_mode_after_release_wins_when_both_open() -> None:
    """When both windows are currently open at once,
    ``after_release`` takes precedence — operator's
    "this is what they see once the release window opens" is
    the more explicit choice."""
    policy = _policy(
        while_ongoing_granularity="row",
        while_ongoing_identification="identified",
        after_release_granularity="row",
        after_release_identification="deidentified",
    )
    assert (
        visibility_policies.resolve_mode(
            policy, while_ongoing_open=True, after_release_open=True
        )
        == "anonymized"
    )


def test_resolve_mode_falls_back_to_while_ongoing_when_after_release_pair_null() -> (
    None
):
    """An open after_release window with a NULL pair falls back
    to the while_ongoing mode (when its window is also open).
    Useful when the operator picked while_ongoing-only on a
    session whose release window has also opened."""
    policy = _policy(
        while_ongoing_granularity="row",
        while_ongoing_identification="identified",
        after_release_granularity=None,
        after_release_identification=None,
    )
    assert (
        visibility_policies.resolve_mode(
            policy, while_ongoing_open=True, after_release_open=True
        )
        == "raw"
    )


def test_resolve_mode_returns_none_when_open_window_pair_is_null() -> None:
    """When the only currently-open window has a NULL pair (off
    in that window), the resolver returns None — even if the
    other (closed) window has a saved mode."""
    policy = _policy(
        while_ongoing_granularity=None,
        while_ongoing_identification=None,
        after_release_granularity="row",
        after_release_identification="identified",
    )
    assert (
        visibility_policies.resolve_mode(
            policy, while_ongoing_open=True, after_release_open=False
        )
        is None
    )
