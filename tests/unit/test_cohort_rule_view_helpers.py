"""Unit tests for the cohort-rule observer view helpers.

Pins the signature (mixed-state JS comparison key) + the
Cohort-cell summary string the Observers Setup table renders.
"""

from __future__ import annotations

from app.web.views import cohort_rule_signature, cohort_rule_summary


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


def test_signature_none_is_empty_string() -> None:
    assert cohort_rule_signature(None) == ""


def test_signature_is_stable_across_key_order() -> None:
    a = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewer.tag1",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "x",
            }
        ],
    }
    b = {
        "rules": [
            {
                "operand_value": "x",
                "field": "reviewer.tag1",
                "op": "IS",
                "operand_tag": "",
            }
        ],
        "combinator": "AND",
    }
    assert cohort_rule_signature(a) == cohort_rule_signature(b)


def test_signature_differs_for_distinct_rules() -> None:
    a = {"combinator": "AND", "rules": []}
    b = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewer.tag1",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "x",
            }
        ],
    }
    assert cohort_rule_signature(a) != cohort_rule_signature(b)


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
    assert summary == "Reviewee: Cohort IS “math”"


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
