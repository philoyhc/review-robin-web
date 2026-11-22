"""Apply Desk's one clock and its date words (segment AD2B rung 4,
AD-40 and AD-97)."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from applydesk import clock, extract, sample_data, timeline


@pytest.mark.parametrize(
    ("a", "b", "said"),
    [
        (date(2026, 9, 1), date(2026, 9, 30), "1–30 Sep 2026"),
        (date(2026, 9, 1), date(2026, 12, 4), "1 Sep – 4 Dec 2026"),
        (date(2026, 12, 30), date(2027, 1, 4), "30 Dec 2026 – 4 Jan 2027"),
        (date(2026, 9, 3), date(2026, 9, 3), "3 Sep 2026"),
    ],
)
def test_a_range_says_its_year_once(a: date, b: date, said: str) -> None:
    assert clock.span(a, b) == said


def test_a_stored_moment_is_printed_in_the_exercise_s_zone() -> None:
    naive_utc = datetime(2026, 8, 4, 1, 12)  # as SQLite returns it
    assert clock.stamp(naive_utc, "Asia/Singapore") == "2026-08-04 09:12"
    assert clock.stamp(naive_utc, "Europe/London") == "2026-08-04 02:12"


def test_today_is_the_sample_s_while_frozen() -> None:
    assert clock.today("Pacific/Kiritimati") == clock.SAMPLE_TODAY
    assert clock.today("Pacific/Pago_Pago") == clock.SAMPLE_TODAY


def test_unfrozen_today_is_the_exercise_s_own(monkeypatch: pytest.MonkeyPatch) -> None:
    """AD-40: a stage's state turns at the exercise's local midnight. At
    one instant, the two ends of the date line stand on different days."""
    monkeypatch.setattr(clock, "FROZEN", None)
    east, west = clock.today("Pacific/Kiritimati"), clock.today("Pacific/Pago_Pago")
    assert (east - west).days in (1, 2)  # UTC+14 against UTC-11


def test_every_page_takes_today_from_the_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "FROZEN", date(2026, 9, 15))
    ra = sample_data.exercise("wa9juxbc2t")
    assert ra is not None
    tl = timeline.of(ra)
    assert tl.today == date(2026, 9, 15)
    assert tl.now is not None and tl.now.name == "Applications"
    assert extract.zip_name(ra, "all").endswith("_2026-09-15.zip")
