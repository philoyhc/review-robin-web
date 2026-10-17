"""``content_disposition`` survives any filename (findings R2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.web.downloads import content_disposition

APP = Path(__file__).resolve().parents[2] / "app"


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
        ("a%41_x.csv", "a_41_x.csv", "a%2541_x.csv"),
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


def test_every_download_route_builds_its_header_with_the_helper() -> None:
    """A raw ``attachment; filename=`` is how R2 happened."""
    raw = [
        str(path.relative_to(APP))
        for path in APP.rglob("*.py")
        if path.name != "downloads.py" and "attachment; filename=" in path.read_text()
    ]
    assert raw == []
