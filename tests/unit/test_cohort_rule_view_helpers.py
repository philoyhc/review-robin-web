"""Unit tests for the cohort-rule observer view helpers.

Pins the Cohort-cell summary string the Observers Setup table renders,
and `rule_edit_state`, the several-row editor's state (operator pages
Item 4; the signature helper retired with the selection expander's
builder).
"""

from __future__ import annotations

from types import SimpleNamespace

from app.web.views import cohort_rule_summary, rule_edit_state


_TAG_LABELS_FULL = {
    "reviewer": [
        ("reviewer.tag1", "Mentor"),
        ("reviewer.tag2", "Department"),
    ],
    "reviewee": [
        ("reviewee.tag1", "Cohort"),
    ],
    "pair_context": [
        ("pair_context.tag1", "Tutorial"),
    ],
}


def test_summary_none_is_empty() -> None:
    assert cohort_rule_summary(None, tag_labels=_TAG_LABELS_FULL) == ""


def test_summary_empty_rules_is_empty() -> None:
    rule = {"combinator": "AND", "rules": []}
    assert cohort_rule_summary(rule, tag_labels=_TAG_LABELS_FULL) == ""


def test_summary_single_rule_field_operator() -> None:
    rule = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewer.tag1",
                "op": "IS THE SAME AS",
                "operand_tag": "observer.email",
                "operand_value": "",
            }
        ],
    }
    summary = cohort_rule_summary(rule, tag_labels=_TAG_LABELS_FULL)
    assert summary == "Reviewer: Mentor IS THE SAME AS Observer: Email"


def test_summary_single_rule_value_operator_quotes_value() -> None:
    rule = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewee.tag1",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "math",
            }
        ],
    }
    summary = cohort_rule_summary(rule, tag_labels=_TAG_LABELS_FULL)
    assert summary == 'Reviewee: Cohort IS "math"'


def test_summary_value_operator_renders_empty_value_explicitly() -> None:
    """``operand_value == ""`` on a value operator is a
    legitimate "filter on blank field" semantic. The summary
    renders ``«empty»`` so the operator can tell it apart from
    an unfilled cell at a glance."""
    rule = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewee.tag1",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "",
            }
        ],
    }
    summary = cohort_rule_summary(rule, tag_labels=_TAG_LABELS_FULL)
    assert summary == "Reviewee: Cohort IS «empty»"


def test_summary_appends_plus_n_more() -> None:
    rule = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewer.tag1",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "x",
            },
            {
                "field": "reviewer.tag2",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "y",
            },
            {
                "field": "reviewee.tag1",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "z",
            },
        ],
    }
    summary = cohort_rule_summary(rule, tag_labels=_TAG_LABELS_FULL)
    assert summary.endswith("+ 2 more")


def test_summary_falls_back_to_canonical_key_for_missing_label() -> None:
    rule = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewer.tag3",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "x",
            }
        ],
    }
    summary = cohort_rule_summary(rule, tag_labels=_TAG_LABELS_FULL)
    # reviewer.tag3 isn't in the labels dict; fall back to the
    # canonical key rather than dropping the rule.
    assert summary.startswith("reviewer.tag3 ")


_RULE = {"combinator": "AND", "rules": [{
    "field": "reviewee.tag1", "op": "IS",
    "operand_tag": "", "operand_value": "Blue",
}]}


def _rows(*rules: object) -> list[SimpleNamespace]:
    return [SimpleNamespace(id=i, cohort_rule=r) for i, r in enumerate(rules, 1)]


def test_rule_edit_state_shared_rule_loads() -> None:
    state = rule_edit_state(_rows(_RULE, None, _RULE), [3, 1])
    assert (state.ids, state.rule, state.mixed, state.last_id) == (
        [3, 1], _RULE, False, 3)


def test_rule_edit_state_differing_rules_load_nothing() -> None:
    state = rule_edit_state(_rows(_RULE, None), [1, 2])
    assert (state.rule, state.mixed, state.last_id) == (None, True, 2)


def test_rule_edit_state_null_and_empty_set_are_one_rule() -> None:
    empty = {"combinator": "AND", "rules": []}
    assert not rule_edit_state(_rows(None, empty), [1, 2]).mixed


def test_rule_edit_state_drops_ids_the_page_does_not_show() -> None:
    # A stale id (deleted, another session's) is not edited blind; one
    # survivor is the row editor's job, not this mode's.
    state = rule_edit_state(_rows(_RULE, _RULE), [1, 1, 99])
    assert (state.ids, state.rule, state.mixed, state.last_id) == (
        [], None, False, None)
