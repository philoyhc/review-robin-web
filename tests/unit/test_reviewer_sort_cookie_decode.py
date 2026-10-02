"""``decode_cookie_sort_spec_for_reviewer_surface``: ``None`` vs ``[]``.

``None`` means "no override, render the operator default"; ``[]`` means
"the operator default is overridden by an empty sort". A spec holding a
``response:N`` key is ``None`` (ruling A27): the server cannot apply it,
the on-load script does, and the script's tie-break must read the
operator default, which is the order a click on a page with no stored
sort finds.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from app.web.views import decode_cookie_sort_spec_for_reviewer_surface

NAME_DF = SimpleNamespace(id=11, source_type="reviewee", source_field="name")
TAG_DF = SimpleNamespace(id=12, source_type="reviewee", source_field="tag_1")
COOKIE = "rrw-sort-rs-1-2"


def _decode(spec: object) -> list[dict[str, object]] | None:
    return decode_cookie_sort_spec_for_reviewer_surface(
        cookies={COOKIE: quote(json.dumps(spec))},
        session_id=1,
        instrument_id=2,
        display_fields=[NAME_DF, TAG_DF],
    )


def test_no_cookie_is_none() -> None:
    assert (
        decode_cookie_sort_spec_for_reviewer_surface(
            cookies={}, session_id=1, instrument_id=2, display_fields=[NAME_DF]
        )
        is None
    )


def test_explicitly_empty_cookie_is_an_empty_override() -> None:
    assert _decode([]) == []


def test_display_only_cookie_decodes() -> None:
    assert _decode(
        [{"key": "reviewee.name", "dir": "desc"}, {"key": "display:12", "dir": "asc"}]
    ) == [
        {"display_field_id": 11, "dir": "desc"},
        {"display_field_id": 12, "dir": "asc"},
    ]


@pytest.mark.parametrize(
    "spec",
    [
        [{"key": "response:5", "dir": "asc"}],
        [{"key": "response:5", "dir": "desc"}, {"key": "reviewee.name", "dir": "asc"}],
        [{"key": "display:12", "dir": "asc"}, {"key": "response:5", "dir": "asc"}],
    ],
    ids=["response-only", "response-first", "response-second"],
)
def test_any_response_key_leaves_the_operator_default(spec: list[dict]) -> None:
    assert _decode(spec) is None


def test_malformed_entries_drop_before_the_cap() -> None:
    """``_rrwReadCookie`` filters bad entries, then keeps 3; the server
    does the same, so a response key behind three bad entries still
    counts."""
    bad = {"key": "reviewee.name", "dir": "sideways"}
    assert _decode(["x", {"dir": "asc"}, bad, {"key": "response:5", "dir": "asc"}]) is None
    assert _decode(
        [bad, bad, bad, {"key": "reviewee.name", "dir": "asc"}]
    ) == [{"display_field_id": 11, "dir": "asc"}]


def test_unknown_keys_count_toward_the_cap() -> None:
    """A well-formed entry naming no column still takes one of the 3
    slots, as it does in the browser."""
    assert _decode(
        [
            {"key": "display:999", "dir": "asc"},
            {"key": "other", "dir": "asc"},
            {"key": "display:12", "dir": "asc"},
            {"key": "response:5", "dir": "asc"},
        ]
    ) == [{"display_field_id": 12, "dir": "asc"}]


def test_a_malformed_response_entry_does_not_count() -> None:
    """The browser drops an entry with a bad ``dir`` before it looks for
    response keys, so the server does too."""
    assert _decode(
        [{"key": "response:5", "dir": "up"}, {"key": "reviewee.name", "dir": "asc"}]
    ) == [{"display_field_id": 11, "dir": "asc"}]
