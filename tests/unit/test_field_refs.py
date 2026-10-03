"""The field-reference helpers behind A28: an instrument's default sort
and column widths carried across a copy by id map or by CSV position."""

from __future__ import annotations

from app.services.instruments._field_refs import (
    repoint_sort,
    repoint_widths,
    sort_from_positions,
    sort_to_positions,
    widths_from_positions,
    widths_to_positions,
)


def test_positions_round_trip_through_new_ids() -> None:
    sort = [
        {"display_field_id": 11, "dir": "desc"},
        {"display_field_id": -1, "dir": "asc"},
        {"display_field_id": 99, "dir": "asc"},  # names no field: dropped
    ]
    widths = {"identity": 200, "df_11": 150, "rf_21": 90, "rf_99": 10}
    exported_sort = sort_to_positions(sort, {10: 1, 11: 2})
    exported_widths = widths_to_positions(
        widths, display_positions={10: 1, 11: 2}, field_positions={21: 1}
    )
    assert exported_sort == [
        {"display_field": 2, "dir": "desc"},
        {"display_field_id": -1, "dir": "asc"},
    ]
    assert exported_widths == {"identity": 200, "df@2": 150, "rf@1": 90}
    assert sort_from_positions(exported_sort, {1: 501, 2: 502}) == [
        {"display_field_id": 502, "dir": "desc"},
        {"display_field_id": -1, "dir": "asc"},
    ]
    assert widths_from_positions(
        exported_widths,
        display_ids_by_position={1: 501, 2: 502},
        field_ids_by_position={1: 601},
    ) == {"identity": 200, "df_502": 150, "rf_601": 90}


def test_hand_edited_positions_are_checked() -> None:
    """``true`` is no position (it would read as 1), and a field or the
    Group sentinel named twice keeps its first entry."""
    entries = [
        {"display_field": True, "dir": "asc"},
        {"display_field_id": -1, "dir": "asc"},
        {"display_field": 2, "dir": "desc"},
        {"display_field": 2, "dir": "asc"},
        {"display_field_id": -1, "dir": "desc"},
    ]
    assert sort_from_positions(entries, {1: 501, 2: 502}) == [
        {"display_field_id": -1, "dir": "asc"},
        {"display_field_id": 502, "dir": "desc"},
    ]


def test_a_string_position_is_not_read() -> None:
    assert sort_from_positions([{"display_field": "1"}], {1: 501}) == []


def test_old_id_keys_and_bad_shapes_are_dropped_on_import() -> None:
    assert sort_from_positions(
        [{"display_field_id": 7, "dir": "asc"}], {1: 501}
    ) == []
    assert sort_from_positions("not a list", {}) == []
    assert widths_from_positions(
        {"df_7": 100, "rf_8": 50},
        display_ids_by_position={1: 501},
        field_ids_by_position={1: 601},
    ) is None
    assert widths_from_positions(
        [1, 2], display_ids_by_position={}, field_ids_by_position={}
    ) is None


def test_id_maps_repoint_and_drop_strays() -> None:
    assert repoint_sort(
        [{"display_field_id": 1, "dir": "asc"}, {"display_field_id": 5}],
        {1: 9},
    ) == [{"display_field_id": 9, "dir": "asc"}]
    assert repoint_widths(
        {"identity": 1, "df_1": 2, "rf_3": 4, "rf_8": 5},
        display_ids={1: 9},
        field_ids={3: 7},
    ) == {"identity": 1, "df_9": 2, "rf_7": 4}
    assert repoint_sort(None, {}) is None
    assert repoint_widths(None, display_ids={}, field_ids={}) is None
