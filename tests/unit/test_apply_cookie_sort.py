"""`views.apply_cookie_sort` resolves each row's values once (author,
2026-10-15): a resolver can build a key (the session tables'
`text_sort_value` splits text with a regex), and a sort compares
O(n log n) times. The ordering rules are unchanged."""

from __future__ import annotations

from app.web import views


def test_each_row_is_resolved_once_per_key() -> None:
    calls: list[tuple[int, str]] = []

    def resolver(row: dict, key: str):
        calls.append((row["id"], key))
        return row[key]

    rows = [{"id": i, "a": (i * 7) % 10, "b": i % 3} for i in range(50)]
    views.apply_cookie_sort(rows, [("b", "asc"), ("a", "desc")], value_resolver=resolver)
    assert sorted(calls) == sorted((i, key) for i in range(50) for key in ("b", "a"))


def test_empty_and_none_sort_last_both_ways_ties_cascade_and_stay_stable() -> None:
    rows = [
        {"id": 1, "a": "x", "b": 2},
        {"id": 2, "a": None, "b": 3},
        {"id": 3, "a": "x", "b": 1},
        {"id": 4, "a": "", "b": 1},
        {"id": 5, "a": "w", "b": 9},
        {"id": 6, "a": "x", "b": 1},
    ]

    def ids(spec: list[tuple[str, str]]) -> list[int]:
        out = views.apply_cookie_sort(rows, spec, value_resolver=lambda r, k: r[k])
        return [r["id"] for r in out]

    # Rows 2 and 4 are both empty on `a`, input in the wrong `b` order,
    # so they come out 4, 2 only if a both-empty tie falls through to `b`.
    assert ids([("a", "asc"), ("b", "asc")]) == [5, 3, 6, 1, 4, 2]
    assert ids([("a", "desc"), ("b", "asc")]) == [3, 6, 1, 5, 4, 2]
    assert ids([]) == [1, 2, 3, 4, 5, 6]
