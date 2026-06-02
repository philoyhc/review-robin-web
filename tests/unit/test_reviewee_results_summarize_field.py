"""Unit tests for :func:`summarize_field` in the reviewee
results view shape — the per-data-type aggregation that the
"Anonymized summaries" mode emits into each response column.

Multi-value coverage that the integration tests (which seed one
reviewer per session) can't easily exercise. Each test pins one
data-type branch end-to-end.
"""

from __future__ import annotations

from app.db.models import InstrumentResponseField
from app.web.views._reviewee_results import summarize_field


def _field(*, data_type: str, list_csv: str | None = None) -> InstrumentResponseField:
    return InstrumentResponseField(
        instrument_id=1,
        field_key="x",
        label="X",
        required=False,
        order=1,
        _inline_data_type=data_type,
        _inline_list_csv=list_csv,
    )


def test_numerical_aggregates_mean_median_min_max() -> None:
    cell = summarize_field(
        _field(data_type="Integer"),
        ["1", "2", "3", "4", "5"],
    )
    assert cell.response_count == 5
    assert cell.average == 3.0
    assert cell.median == 3.0
    assert cell.min_value == 1.0
    assert cell.max_value == 5.0


def test_numerical_median_diverges_from_mean_on_outlier() -> None:
    # Skewed distribution — median + mean are different. Pins the
    # "show both" guideline that the operator can read for skew.
    cell = summarize_field(
        _field(data_type="Decimal"),
        ["1", "1", "1", "1", "20"],
    )
    assert cell.median == 1.0
    assert cell.average == 4.8
    assert cell.min_value == 1.0
    assert cell.max_value == 20.0


def test_numerical_skips_unparseable_values() -> None:
    # A stray non-numeric stored value (e.g. a downstream-of-edit
    # leftover) is silently skipped, not crash the aggregate.
    cell = summarize_field(
        _field(data_type="Integer"),
        ["3", "abc", "5"],
    )
    assert cell.response_count == 2
    assert cell.average == 4.0


def test_numerical_zero_responses_leaves_metrics_none() -> None:
    cell = summarize_field(_field(data_type="Integer"), [])
    assert cell.response_count == 0
    assert cell.average is None
    assert cell.median is None
    assert cell.min_value is None
    assert cell.max_value is None


def test_list_frequencies_include_percentages() -> None:
    cell = summarize_field(
        _field(data_type="List", list_csv="A,B,C"),
        ["A", "B", "B", "C", "C", "C"],
    )
    assert cell.response_count == 6
    # Choices surface in declared order; each carries (choice,
    # count, pct).
    by_choice = {choice: (count, pct) for choice, count, pct in cell.frequencies}
    assert by_choice["A"] == (1, round(100 / 6, 1))
    assert by_choice["B"] == (2, round(200 / 6, 1))
    assert by_choice["C"] == (3, 50.0)
    # Order preserved.
    assert [c for c, _, _ in cell.frequencies] == ["A", "B", "C"]


def test_list_zero_responses_keeps_options_at_zero() -> None:
    cell = summarize_field(
        _field(data_type="List", list_csv="Yes,No"),
        [],
    )
    assert cell.response_count == 0
    assert cell.frequencies == (("Yes", 0, 0.0), ("No", 0, 0.0))


def test_string_aggregates_total_and_average_length() -> None:
    cell = summarize_field(
        _field(data_type="String"),
        ["hi", "hello", "hey"],
    )
    assert cell.response_count == 3
    assert cell.total_length == 10
    assert cell.average_length == round(10 / 3, 1)


def test_string_zero_responses_leaves_metrics_none() -> None:
    cell = summarize_field(_field(data_type="String"), [])
    assert cell.response_count == 0
    assert cell.total_length == 0
    assert cell.average_length is None
