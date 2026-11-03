"""``acknowledged_loss`` reads the ``Yes, clear them`` tick's count
(findings register L1: a count past Python's 4,300-digit ``int`` limit
answered 500)."""

from __future__ import annotations

import pytest

from app.web.routes_operator._shared import acknowledged_loss


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, 0),
        ("", 0),
        ("3", 3),
        (" 007 ", 7),
        ("0", 0),
        ("9" * 18, int("9" * 18)),
        ("9" * 19, 0),
        ("9" * 5000, 0),
        ("0" * 5000 + "5", 5),
        ("0" * 5000, 0),
        ("1_000", 0),
        ("-3", 0),
        ("²", 0),
    ],
)
def test_the_count_is_read_or_reads_as_no_tick(raw: object, expected: int) -> None:
    assert acknowledged_loss(raw) == expected
