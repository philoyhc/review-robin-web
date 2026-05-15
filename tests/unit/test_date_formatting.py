"""Canonical date / time display formatting — Segment 18B PR 1 / PR 2."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.services.date_formatting import (
    format_date,
    format_datetime,
    resolve_zone,
)


def test_format_datetime_none_is_empty_string() -> None:
    assert format_datetime(None) == ""


def test_format_datetime_aware_utc() -> None:
    value = datetime(2026, 5, 15, 17, 0, tzinfo=timezone.utc)
    assert format_datetime(value) == "2026-05-15 17:00"


def test_format_datetime_naive_assumed_utc() -> None:
    # SQLite returns stored timestamps naive; they are UTC.
    value = datetime(2026, 5, 15, 17, 0)
    assert format_datetime(value) == "2026-05-15 17:00"


def test_format_datetime_aware_non_utc_converted() -> None:
    # +08:00 17:00 is 09:00 UTC — the helper normalises before format.
    value = datetime(
        2026, 5, 15, 17, 0, tzinfo=timezone(timedelta(hours=8))
    )
    assert format_datetime(value) == "2026-05-15 09:00"


def test_format_date_none_is_empty_string() -> None:
    assert format_date(None) == ""


def test_format_date_from_date() -> None:
    assert format_date(date(2026, 5, 15)) == "2026-05-15"


def test_format_date_from_datetime_drops_time() -> None:
    value = datetime(2026, 5, 15, 17, 0, tzinfo=timezone.utc)
    assert format_date(value) == "2026-05-15"


def test_format_date_from_datetime_uses_utc_date() -> None:
    # 01:00 at +08:00 is the previous day in UTC.
    value = datetime(
        2026, 5, 15, 1, 0, tzinfo=timezone(timedelta(hours=8))
    )
    assert format_date(value) == "2026-05-14"


# ── Segment 18B PR 2 — zone-aware rendering (no zone token) ──────────────


def test_format_datetime_in_named_zone() -> None:
    # 09:00 UTC is 17:00 in Singapore — the value is converted, but
    # no zone token is appended.
    value = datetime(2026, 5, 15, 9, 0, tzinfo=timezone.utc)
    assert format_datetime(value, "Asia/Singapore") == "2026-05-15 17:00"


def test_format_datetime_utc_zone() -> None:
    value = datetime(2026, 5, 15, 17, 0, tzinfo=timezone.utc)
    assert format_datetime(value, "UTC") == "2026-05-15 17:00"


def test_format_datetime_unknown_zone_falls_back_to_utc() -> None:
    value = datetime(2026, 5, 15, 17, 0, tzinfo=timezone.utc)
    assert format_datetime(value, "Bogus/Zone") == "2026-05-15 17:00"


def test_format_datetime_none_with_zone_is_empty_string() -> None:
    assert format_datetime(None, "Asia/Singapore") == ""


def test_format_date_in_named_zone_rolls_to_next_day() -> None:
    # 23:00 UTC on the 15th is 07:00 on the 16th in Singapore.
    value = datetime(2026, 5, 15, 23, 0, tzinfo=timezone.utc)
    assert format_date(value, "Asia/Singapore") == "2026-05-16"


def test_resolve_zone_unknown_and_none_fall_back_to_utc() -> None:
    assert resolve_zone("Bogus/Zone").key == "UTC"
    assert resolve_zone(None).key == "UTC"
    assert resolve_zone("Asia/Singapore").key == "Asia/Singapore"
