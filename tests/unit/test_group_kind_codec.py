"""Segment 13C PR 2 slice A — the ``group_kind`` boundary-spec codec.

``encode_group_kind`` / ``decode_group_kind`` translate between the
ordered list of boundary ``(source_type, source_field)`` tag pairs
the operator ticks *Group by* and the compact comma-joined code
string stored in ``Instrument.group_kind``.
"""
from __future__ import annotations

from app.services.instruments import (
    GROUP_KIND_SENTINEL,
    decode_group_kind,
    encode_group_kind,
)


def test_encode_empty_yields_sentinel() -> None:
    """No boundary tag encodes to the no-boundary sentinel so the
    column stays non-null (non-null is the group-scoped flag)."""
    assert encode_group_kind([]) == GROUP_KIND_SENTINEL


def test_encode_orders_and_codes_pairs() -> None:
    assert (
        encode_group_kind(
            [("reviewee", "tag_1"), ("pair_context", "2")]
        )
        == "r1,p2"
    )
    assert (
        encode_group_kind(
            [("pair_context", "3"), ("reviewee", "tag_2")]
        )
        == "p3,r2"
    )


def test_encode_skips_non_boundary_pairs() -> None:
    """Name / Email are not boundary-eligible — silently dropped."""
    assert (
        encode_group_kind(
            [("reviewee", "name"), ("reviewee", "tag_1")]
        )
        == "r1"
    )


def test_encode_dedups_repeated_pairs() -> None:
    assert (
        encode_group_kind([("reviewee", "tag_1"), ("reviewee", "tag_1")])
        == "r1"
    )


def test_decode_none_and_sentinel_yield_empty() -> None:
    assert decode_group_kind(None) == []
    assert decode_group_kind(GROUP_KIND_SENTINEL) == []
    assert decode_group_kind("") == []


def test_decode_parses_codes_in_order() -> None:
    assert decode_group_kind("r1,p2") == [
        ("reviewee", "tag_1"),
        ("pair_context", "2"),
    ]


def test_decode_skips_unknown_codes() -> None:
    assert decode_group_kind("r1,zz,p3") == [
        ("reviewee", "tag_1"),
        ("pair_context", "3"),
    ]


def test_round_trip() -> None:
    pairs = [
        ("reviewee", "tag_1"),
        ("reviewee", "tag_3"),
        ("pair_context", "1"),
    ]
    assert decode_group_kind(encode_group_kind(pairs)) == pairs
