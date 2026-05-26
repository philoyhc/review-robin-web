"""Pydantic schemas for RuleSets.

These schemas mirror the model in ``spec/rule_based_assignment.md`` §4
and form the typed in-memory shape that the engine (Segment 13A PR 2)
consumes and that the editor (PR 5) saves into
``rule_set_revisions.rules_json``.

The structured form here is the canonical Python representation. The
spec uses a presentation-friendly nested-dict form
(``{"reviewer.tag1": {"same_as": "reviewee.tag1"}}``) to keep examples
concise; the storage and engine forms are this structured shape, which
is round-trippable through ``model_dump()`` / ``model_validate(...)``
without the encoding ambiguity nested dicts introduce.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Combinator(str, Enum):
    """Top-level operator that merges per-rule verdicts. Spec §4.3."""

    ALL_OF = "ALL_OF"
    ANY_OF = "ANY_OF"
    PIPELINE = "PIPELINE"


class RuleSetScope(str, Enum):
    """Storage scope for a RuleSet. Plan DB shape §"DB shape"; spec §5.1
    mentions a future ``shared`` scope which is out of 13A."""

    seed = "seed"
    personal = "personal"


class CompositeOp(str, Enum):
    """Boolean operator on a Composite rule's children. Spec §4.8."""

    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class QuotaScope(str, Enum):
    """Axis a quota is applied along. Spec §4.7."""

    PER_REVIEWER = "PER_REVIEWER"
    PER_REVIEWEE = "PER_REVIEWEE"


class SelectionStrategy(str, Enum):
    """Quota selection algorithm when more candidates than ``max``
    remain. Spec §4.7."""

    RANDOM = "RANDOM"
    ROUND_ROBIN = "ROUND_ROBIN"


PredicateOperator = Literal[
    "equals",
    "not_equals",
    "in",
    "not_in",
    "matches",
    "not_matches",
    "is_empty",
    "is_not_empty",
    "same_as",
    "different_from",
]
"""Spec §4.4. Stored / validated as the literal string."""


# Operators that take no operand at all.
_NULLARY_OPERATORS: frozenset[str] = frozenset(
    {"is_empty", "is_not_empty"}
)
# Operators whose operand is another field on the opposite side
# (cross-side comparison).
_FIELD_OPERATORS: frozenset[str] = frozenset(
    {"same_as", "different_from"}
)
# Operators whose operand is a list of literals.
_LIST_OPERATORS: frozenset[str] = frozenset({"in", "not_in"})
# Operators whose operand is a regex string.
_REGEX_OPERATORS: frozenset[str] = frozenset({"matches", "not_matches"})


# Field-name vocabulary. Operator-facing dotted form. The ORM-column
# mapping (``tag1 → tag_1`` etc.) lives in
# ``app/services/rules/fields.py`` (Segment 13A PR 2) — see plan
# §"Predicate vocabulary mapping".
ALLOWED_PREDICATE_FIELDS: frozenset[str] = frozenset(
    {
        "reviewer.email",
        "reviewer.tag1",
        "reviewer.tag2",
        "reviewer.tag3",
        "reviewee.email",
        "reviewee.tag1",
        "reviewee.tag2",
        "reviewee.tag3",
        "pair_context.tag1",
        "pair_context.tag2",
        "pair_context.tag3",
    }
)


# ---------------------------------------------------------------------------
# Predicate
# ---------------------------------------------------------------------------


class Predicate(BaseModel):
    """A single comparison on a candidate ``(reviewer, reviewee)`` pair.

    See ``spec/rule_based_assignment.md`` §4.4 for the operator set.
    """

    model_config = ConfigDict(extra="forbid")

    field: str
    operator: PredicateOperator
    operand: str | int | float | list[str] | None = None
    case_sensitive: bool = False

    @field_validator("field")
    @classmethod
    def _validate_field(cls, value: str) -> str:
        if value not in ALLOWED_PREDICATE_FIELDS:
            raise ValueError(
                f"unknown predicate field {value!r}; "
                f"allowed fields: {sorted(ALLOWED_PREDICATE_FIELDS)}"
            )
        return value

    @model_validator(mode="after")
    def _validate_operand_for_operator(self) -> Predicate:
        op = self.operator
        operand = self.operand

        if op in _NULLARY_OPERATORS:
            if operand is not None:
                raise ValueError(
                    f"operator {op!r} takes no operand; got {operand!r}"
                )
            return self

        if op in _FIELD_OPERATORS:
            if not isinstance(operand, str):
                raise ValueError(
                    f"operator {op!r} requires a field-name operand "
                    f"(string), got {type(operand).__name__}"
                )
            if operand not in ALLOWED_PREDICATE_FIELDS:
                raise ValueError(
                    f"operator {op!r} operand {operand!r} is not a "
                    "known predicate field"
                )
            # Cross-side: same_as / different_from address the opposite
            # population.
            self_side = self.field.split(".", 1)[0]
            operand_side = operand.split(".", 1)[0]
            if self_side == operand_side:
                raise ValueError(
                    f"operator {op!r} compares across populations; "
                    f"both sides addressed {self_side!r}"
                )
            return self

        if op in _LIST_OPERATORS:
            if not isinstance(operand, list) or not operand:
                raise ValueError(
                    f"operator {op!r} requires a non-empty list of "
                    "literals as operand"
                )
            if not all(isinstance(item, str) for item in operand):
                raise ValueError(
                    f"operator {op!r} operand list must contain strings"
                )
            return self

        if op in _REGEX_OPERATORS:
            if not isinstance(operand, str):
                raise ValueError(
                    f"operator {op!r} requires a regex string operand"
                )
            try:
                re.compile(operand)
            except re.error as exc:
                raise ValueError(
                    f"operator {op!r} regex {operand!r} does not "
                    f"compile: {exc}"
                ) from exc
            return self

        # equals / not_equals — literal scalar.
        if not isinstance(operand, (str, int, float)):
            raise ValueError(
                f"operator {op!r} requires a string / integer / float "
                f"operand, got {type(operand).__name__}"
            )
        return self


# ---------------------------------------------------------------------------
# Rule kinds (discriminated union on ``kind``)
# ---------------------------------------------------------------------------


class _RuleBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, max_length=64)
    enabled: bool = True


class FilterRule(_RuleBase):
    """Removes pairs that match ``predicate``. Spec §4.5."""

    kind: Literal["FILTER"] = "FILTER"
    predicate: Predicate


class MatchRule(_RuleBase):
    """Keeps pairs that match ``predicate``. Spec §4.6."""

    kind: Literal["MATCH"] = "MATCH"
    predicate: Predicate


class QuotaSelection(BaseModel):
    """Selection strategy for a Quota rule. Spec §4.7."""

    model_config = ConfigDict(extra="forbid")

    strategy: SelectionStrategy
    seed: int | None = None


class QuotaRule(_RuleBase):
    """Caps multiplicity of pairs along an axis. Spec §4.7."""

    kind: Literal["QUOTA"] = "QUOTA"
    scope: QuotaScope
    min: int | None = Field(default=None, ge=0)
    max: int | None = Field(default=None, ge=0)
    selection: QuotaSelection

    @model_validator(mode="after")
    def _validate_min_max(self) -> QuotaRule:
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(
                f"quota min ({self.min}) exceeds max ({self.max})"
            )
        return self


class CompositeRule(_RuleBase):
    """Groups child rules under a boolean operator. Spec §4.8."""

    kind: Literal["COMPOSITE"] = "COMPOSITE"
    op: CompositeOp
    rules: list[Rule] = Field(..., min_length=1)


Rule = Annotated[
    Union[FilterRule, MatchRule, QuotaRule, CompositeRule],
    Field(discriminator="kind"),
]
"""Discriminated union over the four rule kinds. The ``kind`` literal
field selects the concrete subclass on ``model_validate(...)``."""


# Pydantic needs a forward-ref rebuild because ``CompositeRule.rules``
# refers to ``Rule`` which depends on ``CompositeRule`` itself.
CompositeRule.model_rebuild()


# ---------------------------------------------------------------------------
# RuleSet shapes
# ---------------------------------------------------------------------------


class RuleSetOptions(BaseModel):
    """RuleSet-level options. Spec §4.9.

    Project-wide policy on ``excludeSelfReviews``: it is ALWAYS
    ``False`` for assignments generation and for the Band 2
    instrument preview tables (see ``spec/assignments.md``
    "Self-review policy"). Operators who want to suppress
    self-reviews should either add a Link 2 rule (e.g.
    ``reviewee.email_or_identifier IS DIFFERENT FROM reviewer.email``)
    or mark the ``(R, R)`` row inactive on the Assignments page.
    """

    model_config = ConfigDict(extra="forbid")

    excludeSelfReviews: bool = False
    seed: int | None = None


class RuleSetMetadata(BaseModel):
    """Bookkeeping fields. Spec §4.9."""

    model_config = ConfigDict(extra="forbid")

    isSeed: bool = False
    createdBy: str | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None


class RuleSetSchema(BaseModel):
    """The full RuleSet shape. Spec §4.9.

    ``id`` is the database id of the ``rule_sets`` row when the
    RuleSet has been persisted; the editor passes ``None`` for an
    unsaved blank.
    """

    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    scope: RuleSetScope = RuleSetScope.personal
    combinator: Combinator
    rules: list[Rule] = Field(default_factory=list)
    options: RuleSetOptions = Field(default_factory=RuleSetOptions)
    metadata: RuleSetMetadata = Field(default_factory=RuleSetMetadata)

    @model_validator(mode="after")
    def _validate_unique_rule_ids(self) -> RuleSetSchema:
        seen: set[str] = set()
        stack: list[Rule] = list(self.rules)
        while stack:
            rule = stack.pop()
            if rule.id in seen:
                raise ValueError(
                    f"duplicate rule id {rule.id!r} within RuleSet"
                )
            seen.add(rule.id)
            if isinstance(rule, CompositeRule):
                stack.extend(rule.rules)
        return self


class RuleSetRevisionSchema(BaseModel):
    """Revision metadata. Mirrors ``rule_set_revisions`` columns."""

    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    rule_set_id: int | None = None
    revision_no: int = Field(..., ge=1)
    combinator: Combinator
    exclude_self_reviews: bool
    seed: int | None = None
    rules_json: list[dict[str, Any]]
    created_at: datetime | None = None
    created_by_user_id: int | None = None
