"""Pydantic schemas for ``Observer.cohort_rule``.

The persisted shape on the ``observers.cohort_rule`` JSON
column is the dict produced by ``CohortRuleSet.model_dump()``
— a ``combinator`` plus a list of per-cell ``CohortRule``
dicts. ``cohort_rule`` is nullable; ``NULL`` means the operator
hasn't authored a rule for this observer yet.

The rule dict shape mirrors Band 1 Link 2's storage idiom
(``{"field", "op", "operand_tag", "operand_value"}``) — the UI
labels (``IS THE SAME AS`` / ``IS DIFFERENT FROM`` / ``IS`` /
``IS NOT`` / ``CONTAINS`` / ``DOES NOT CONTAIN``) are stored
as-is, with the engine-side translation happening at
evaluation time (when the cohort resolver lands).

See ``guide/archive/observers.md`` "Match-axis schema — decided" for
the design notes.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CohortCombinator(str, Enum):
    AND = "AND"
    OR = "OR"


CohortOperator = Literal[
    "IS THE SAME AS",
    "IS DIFFERENT FROM",
    "IS",
    "IS NOT",
    "CONTAINS",
    "DOES NOT CONTAIN",
]


ALLOWED_LEFT_FIELDS: frozenset[str] = frozenset(
    {
        "reviewer.tag1",
        "reviewer.tag2",
        "reviewer.tag3",
        "reviewee.tag1",
        "reviewee.tag2",
        "reviewee.tag3",
        "pair_context.tag1",
        "pair_context.tag2",
        "pair_context.tag3",
    }
)
"""Canonical keys allowed in the ``field`` slot — the
cross-roster attribute the cohort filter matches against.
Same vocabulary as the assignment-engine predicate fields
(``app/schemas/rules.py::ALLOWED_PREDICATE_FIELDS``)."""


ALLOWED_OBSERVER_FIELDS: frozenset[str] = frozenset(
    {
        "observer.name",
        "observer.email",
        "observer.tag1",
    }
)
"""Canonical keys for the observer-side identity attributes
the cohort filter can compare a roster attribute against."""


ALLOWED_RIGHT_FIELDS: frozenset[str] = (
    ALLOWED_OBSERVER_FIELDS | ALLOWED_LEFT_FIELDS
)
"""Right-side operand vocabulary for the ``IS THE SAME AS`` /
``IS DIFFERENT FROM`` operators — observer-side attributes plus
the same left-side cross-roster attributes (so a cohort rule
can express, e.g., ``Reviewer: Tag 1 IS THE SAME AS Reviewee:
Tag 2`` for a session-wide filter that doesn't reference the
observer)."""


_FIELD_OPERATORS: frozenset[str] = frozenset(
    {"IS THE SAME AS", "IS DIFFERENT FROM"}
)
_VALUE_OPERATORS: frozenset[str] = frozenset(
    {"IS", "IS NOT", "CONTAINS", "DOES NOT CONTAIN"}
)


class CohortRule(BaseModel):
    """A single rule cell within the cohort-rule set.

    Both ``operand_tag`` and ``operand_value`` ride along in
    storage; the consumer picks the right one based on ``op``
    (matching Band 1 Link 2's idiom in
    ``app/services/instruments/_band1.py::_form_rules``).
    """

    model_config = ConfigDict(extra="forbid")

    field: str
    op: CohortOperator
    operand_tag: str = ""
    operand_value: str = ""

    @model_validator(mode="after")
    def _validate_shape(self) -> CohortRule:
        if self.field not in ALLOWED_LEFT_FIELDS:
            raise ValueError(
                f"unknown cohort-rule field {self.field!r}; "
                f"allowed: {sorted(ALLOWED_LEFT_FIELDS)}"
            )
        if self.op in _FIELD_OPERATORS:
            if not self.operand_tag:
                raise ValueError(
                    f"operator {self.op!r} requires operand_tag"
                )
            if self.operand_tag not in ALLOWED_RIGHT_FIELDS:
                raise ValueError(
                    f"unknown cohort-rule operand_tag "
                    f"{self.operand_tag!r}; allowed: "
                    f"{sorted(ALLOWED_RIGHT_FIELDS)}"
                )
        return self


class CohortRuleSet(BaseModel):
    """The full ``observers.cohort_rule`` payload — what the
    Cohort match rule editor persists for one observer.

    Empty ``rules`` represents an explicitly-saved empty rule
    (distinct from ``cohort_rule IS NULL``, which means the
    operator hasn't authored anything yet). The resolver's
    interpretation of each state lands when the cohort
    materialiser service lands.
    """

    model_config = ConfigDict(extra="forbid")

    combinator: CohortCombinator = CohortCombinator.AND
    rules: list[CohortRule] = Field(default_factory=list)
