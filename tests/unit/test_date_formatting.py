"""Canonical date / time display formatting — Segment 18B PR 1 / PR 2."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.services import date_formatting
from app.services.date_formatting import (
    format_date,
    format_datetime,
    parse_local_datetime,
    resolve_zone,
    timezone_label,
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


# ── Segment 18B follow-up — the SHOW_ZONE_TOKEN switch ───────────────────


def test_zone_token_off_by_default() -> None:
    assert date_formatting.SHOW_ZONE_TOKEN is False


def test_format_datetime_appends_token_when_switch_on(monkeypatch) -> None:
    monkeypatch.setattr(date_formatting, "SHOW_ZONE_TOKEN", True)
    value = datetime(2026, 5, 15, 9, 0, tzinfo=timezone.utc)
    assert format_datetime(value, "UTC") == "2026-05-15 09:00 UTC"
    assert format_datetime(value, "Asia/Singapore") == "2026-05-15 17:00 +08"


def test_format_date_ignores_zone_token_switch(monkeypatch) -> None:
    # The token only ever rode the date-time render, never date-only.
    monkeypatch.setattr(date_formatting, "SHOW_ZONE_TOKEN", True)
    value = datetime(2026, 5, 15, 9, 0, tzinfo=timezone.utc)
    assert format_date(value, "Asia/Singapore") == "2026-05-15"


# ── CLDR zone display names — timezone_label ─────────────────────────────


def test_timezone_label_returns_cldr_name() -> None:
    assert timezone_label("Asia/Singapore") == "Singapore Standard Time"


def test_timezone_label_picks_standard_or_daylight_from_at() -> None:
    # June is winter in Australia (standard), January is summer (daylight).
    winter = datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc)
    summer = datetime(2026, 1, 2, 8, 0, tzinfo=timezone.utc)
    assert (
        timezone_label("Australia/Melbourne", at=winter)
        == "Australian Eastern Standard Time"
    )
    assert (
        timezone_label("Australia/Melbourne", at=summer)
        == "Australian Eastern Daylight Time"
    )


def test_timezone_label_none_resolves_to_utc_name() -> None:
    assert timezone_label(None) == "Coordinated Universal Time"


# ── compact GMT-offset labels — gmt_offset_label ─────────────────────────


def test_gmt_offset_label_whole_hour() -> None:
    assert date_formatting.gmt_offset_label("Asia/Singapore") == "GMT+8"


def test_gmt_offset_label_half_hour() -> None:
    assert date_formatting.gmt_offset_label("Asia/Kolkata") == "GMT+5:30"


def test_gmt_offset_label_negative() -> None:
    # New York is GMT-5 in January (standard time).
    winter = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
    assert date_formatting.gmt_offset_label("America/New_York", at=winter) == "GMT-5"


def test_gmt_offset_label_utc_and_none() -> None:
    assert date_formatting.gmt_offset_label("UTC") == "UTC"
    assert date_formatting.gmt_offset_label(None) == "UTC"


# ── GMT-offset + raw IANA zone — gmt_offset_zone_label ───────────────────


def test_gmt_offset_zone_label_offset_plus_iana() -> None:
    assert (
        date_formatting.gmt_offset_zone_label("Asia/Singapore")
        == "GMT+8 Asia/Singapore"
    )
    assert (
        date_formatting.gmt_offset_zone_label("Asia/Kolkata")
        == "GMT+5:30 Asia/Kolkata"
    )


def test_gmt_offset_zone_label_dedupes_bare_utc() -> None:
    assert date_formatting.gmt_offset_zone_label("UTC") == "UTC"
    assert date_formatting.gmt_offset_zone_label(None) == "UTC"


# ── datetime-local parsing — parse_local_datetime ────────────────────────


def test_parse_local_datetime_converts_zone_wall_clock_to_utc() -> None:
    # 17:00 in Singapore (+08) is 09:00 UTC; the result is naive.
    result = parse_local_datetime("2026-06-02T17:00", "Asia/Singapore")
    assert result == datetime(2026, 6, 2, 9, 0)
    assert result.tzinfo is None


def test_parse_local_datetime_utc_is_identity() -> None:
    assert parse_local_datetime("2026-06-02T17:00", "UTC") == datetime(
        2026, 6, 2, 17, 0
    )


def test_parse_local_datetime_rejects_unparseable_string() -> None:
    with pytest.raises(ValueError):
        parse_local_datetime("not-a-date", "UTC")
