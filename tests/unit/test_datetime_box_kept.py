"""``sessions.datetime_box_kept``: which details-card boxes a Save keeps
at their stored instant (findings L8, author's ruling)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.date_formatting import format_datetime_local
from app.services.sessions import converted_box_names, datetime_box_kept

_STORED = datetime(2027, 3, 1, 2, 0, 45, tzinfo=timezone.utc)
_SGT = format_datetime_local(_STORED, "Asia/Singapore")
_NY = format_datetime_local(_STORED, "America/New_York")


def _kept(text: str, *, converted: bool) -> bool:
    return datetime_box_kept(
        _STORED,
        text,
        seeded_zone="Asia/Singapore",
        submitted_zone="America/New_York",
        converted=converted,
    )


def test_old_zone_text_is_kept_without_script() -> None:
    assert _kept(_SGT, converted=False)


def test_new_zone_text_is_kept_either_way() -> None:
    assert _kept(_NY, converted=False)
    assert _kept(_NY, converted=True)


def test_old_zone_text_in_a_re_rendered_box_is_an_edit() -> None:
    assert not _kept(_SGT, converted=True)


def test_other_text_is_an_edit() -> None:
    assert not _kept("2027-03-01T09:00", converted=False)


def test_converted_box_names_ignores_blanks_and_spaces() -> None:
    assert converted_box_names("") == frozenset()
    assert converted_box_names(" deadline, ,responses_release_at") == frozenset(
        {"deadline", "responses_release_at"}
    )
