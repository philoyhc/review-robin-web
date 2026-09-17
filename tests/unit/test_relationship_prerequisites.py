"""The two rosters a relationship depends on, as a pure function.

19O.5 rung 4. The page-level tests in
`tests/integration/test_relationship_cascade_accounting.py` exercise
this through rendered HTML, which is where the copy has to be right.
This file is the sibling of `test_preview_count_line.py`: four inputs,
every derived string, no request.

It earns its place because the **grammar** lives here now. The number
agreement was spelled out twice — once in `add_disabled_title` and once
in Jinja for the empty state — so the two surfaces shared which roster
was missing but not how to say it. A cold read caught that; this pins
the single answer.
"""

from __future__ import annotations

import pytest

from app.web.views import relationship_prerequisites


@pytest.mark.parametrize(
    "has_reviewers,has_reviewees,labels",
    [
        (False, False, ["Reviewers", "Reviewees"]),
        (True, False, ["Reviewees"]),
        (False, True, ["Reviewers"]),
        (True, True, []),
    ],
)
def test_it_names_exactly_the_empty_rosters(
    has_reviewers: bool, has_reviewees: bool, labels: list[str]
) -> None:
    """Including the order, which is the nav's and the CSV's."""
    prereqs = relationship_prerequisites(
        has_reviewers=has_reviewers, has_reviewees=has_reviewees
    )
    assert [roster.label for roster in prereqs.missing] == labels
    assert prereqs.satisfied is (not labels)


def test_the_slug_is_the_setup_page_it_links_to() -> None:
    """The template builds `/operator/sessions/<id>/<slug>` from it, so
    a typo here is a 404 on the one link the operator is told to use."""
    prereqs = relationship_prerequisites(
        has_reviewers=False, has_reviewees=False
    )
    assert [roster.slug for roster in prereqs.missing] == [
        "reviewers",
        "reviewees",
    ]


@pytest.mark.parametrize(
    "has_reviewers,has_reviewees,noun,clause",
    [
        (False, False, "rosters", "rosters both have rows"),
        (True, False, "roster", "roster has rows"),
        (False, True, "roster", "roster has rows"),
    ],
)
def test_both_surfaces_agree_about_number(
    has_reviewers: bool,
    has_reviewees: bool,
    noun: str,
    clause: str,
) -> None:
    prereqs = relationship_prerequisites(
        has_reviewers=has_reviewers, has_reviewees=has_reviewees
    )
    assert prereqs.roster_noun == noun
    assert prereqs.empty_state_clause == clause


@pytest.mark.parametrize(
    "has_reviewers,has_reviewees,expected",
    [
        (
            False,
            False,
            "Add rows to the Reviewers and Reviewees rosters first — "
            "a relationship needs one of each.",
        ),
        (
            True,
            False,
            "Add rows to the Reviewees roster first — "
            "a relationship needs one of each.",
        ),
        (
            False,
            True,
            "Add rows to the Reviewers roster first — "
            "a relationship needs one of each.",
        ),
    ],
)
def test_the_tooltip_in_full(
    has_reviewers: bool, has_reviewees: bool, expected: str
) -> None:
    """It read *"Add a reviewer and a reviewee first"* in all three
    cases, so an operator with a full Reviewers roster was told to add a
    reviewer. Asserted whole rather than by substring: the defect it
    replaces was a sentence that was wrong as a sentence."""
    assert (
        relationship_prerequisites(
            has_reviewers=has_reviewers, has_reviewees=has_reviewees
        ).add_disabled_title
        == expected
    )


def test_nothing_missing_has_nothing_to_say() -> None:
    """The template renders the live button in this state, so the
    tooltip is never read — empty rather than a sentence that would be
    false if it ever were."""
    prereqs = relationship_prerequisites(
        has_reviewers=True, has_reviewees=True
    )
    assert prereqs.satisfied
    assert prereqs.add_disabled_title == ""
