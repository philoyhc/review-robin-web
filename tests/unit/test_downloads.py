"""``content_disposition`` survives any filename (findings R2)."""

from __future__ import annotations

import pytest

from app.web.downloads import content_disposition


def test_plain_ascii_name_is_sent_as_is() -> None:
    assert content_disposition("SPRING_reviewers.csv") == (
        'attachment; filename="SPRING_reviewers.csv"'
    )


@pytest.mark.parametrize(
    "name, fallback, encoded",
    [
        ("Café_reviewers.csv", "Cafe_reviewers.csv", "Caf%C3%A9_reviewers.csv"),
        ("日本_setup.zip", "___setup.zip", "%E6%97%A5%E6%9C%AC_setup.zip"),
        ('a"b\\c_x.csv', "a_b_c_x.csv", "a%22b%5Cc_x.csv"),
        ("a\r\nb.csv", "a__b.csv", "a%0D%0Ab.csv"),
    ],
)
def test_a_name_a_header_cannot_hold_gets_a_fallback_and_filename_star(
    name: str, fallback: str, encoded: str
) -> None:
    header = content_disposition(name)
    assert header == (
        f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'
    )
    header.encode("latin-1")
