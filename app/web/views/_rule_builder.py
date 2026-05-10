"""Rule Builder + Rule Based card view-shapes (Segment 13A) —
the largest slice in the §12.B ladder.

Slice 10 of the §12.B ladder (``guide/major_refactor.md``) — the
final slice; with this file in place, ``_legacy.py`` is gone and
the views package is fully sliced.

Owns:

- **Rule Based card on Setup → Assignments** (Segment 13A PR 0
  scaffold + PRs 4-5 wiring) — ``RuleBasedSelectorOption`` /
  ``RuleBasedLastGenerated`` / ``RuleBasedCardContext`` +
  ``build_rule_based_card_context``.
- **Rule Builder page** (Segment 13A-1) — ``RuleLine`` /
  ``EditableRule`` / ``RuleBuilderOption`` /
  ``AvailableRuleSetEntry`` / ``RuleBuilderContext`` +
  ``build_rule_builder_context`` plus the in-file rule-rendering
  helpers (``_render_field_reference`` /
  ``_render_predicate_sentence`` / ``_render_quota_sentence`` /
  ``_flatten_rule_lines`` / ``_operand_to_text``) and the
  blank-draft / default-description constants
  (``RULE_BUILDER_BLANK_SENTINEL_ID`` /
  ``RULE_BUILDER_DRAFT_DEFAULT_DESCRIPTION``).

Source range in pre-PR-10 ``_legacy.py``: the entire file post-
PR-9 strip (~1,245 LOC).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services.rules import engine, library





# Segment 13A PR 0 — Rule Based card scaffold on Setup → Assignments.
# Mirrors the 11H pattern: ship the visual shape first behind a single
# ``is_wired`` flag, then PRs 4 and 5 flip it live and supply real
# selector options + handlers without re-laying-out the partial.
# PR 4 flipped the card live with seed-only library entries; PR 5
# extends the selector to include Personal RuleSets owned by the
# operator and adds the Build / Edit rules button.


@dataclass(frozen=True)
class RuleBasedSelectorOption:
    id: int
    label: str
    description: str
    exclude_self_reviews: bool
    is_seed: bool
    eligible_pair_count: int = 0
    """Pairs the engine produces when this RuleSet is evaluated
    against the current reviewer / reviewee populations. Surfaces
    in the card as a "Number of eligible pairs found: {n}" pill so
    the operator can see the dry-run count before clicking
    Generate. Zero when populations are empty or the engine bails
    on the schema."""


@dataclass(frozen=True)
class RuleBasedLastGenerated:
    """One-line summary of the most recent rule-based generation.

    Reads from ``assignments.generated`` audit rows where
    ``context.mode == 'rule_based'``. Empty when no rule-based
    generation has happened yet on this session.

    ``rule_set_name`` is the name of the RuleSet at the time of the
    generation if the row is still resolvable (including
    soft-deleted Personal RuleSets — ``library.load_rule_set`` does
    not filter on ``deleted_at``). Falls back to ``None`` if the
    audit row predates the refs slot or the RuleSet has been hard-
    deleted in the past."""

    pair_count: int
    when: datetime
    rule_set_name: str | None = None
    assignment_count: int | None = None
    """Total Assignment rows written by the run (= pair_count
    × instrument count). Surfaced alongside the unique-pair count so
    operators on multi-instrument sessions can read both numbers
    inline. ``None`` for older audit rows that wrote ``new`` under a
    different key."""


@dataclass(frozen=True)
class RuleBasedCardContext:
    is_wired: bool
    assignment_count: int
    edit_url: str
    coming_in: str
    options: list[RuleBasedSelectorOption]
    selected_option_id: int | None
    selected_description: str
    selected_exclude_self_reviews: bool
    selected_eligible_pair_count: int
    needs_confirm_replace: bool
    error_kind: str | None
    last_generated: RuleBasedLastGenerated | None


def build_rule_based_card_context(
    db: Session,
    review_session: ReviewSession,
    *,
    user: User | None = None,
    assignment_count: int,
    error_kind: str | None = None,
) -> RuleBasedCardContext:
    """Build the live context for the Rule Based card.

    PR 4 ships the seed-only library; ``user`` is accepted now so PR 5
    can extend the query to include the operator's Personal RuleSets
    without further surgery here.
    """

    from app.db.models import AuditEvent
    from app.schemas.rules import (
        Combinator,
        RuleSetOptions,
        RuleSetSchema,
    )
    from app.services import assignments as assignments_service


    rule_adapter = TypeAdapter(__import__(
        "app.schemas.rules", fromlist=["Rule"]
    ).Rule)

    options: list[RuleBasedSelectorOption] = []
    selected_option_id: int | None = None
    if user is not None:
        # Load populations once so each option's engine.evaluate call
        # iterates the same in-memory lists rather than re-querying.
        reviewers = assignments_service.list_reviewers(db, review_session.id)
        reviewees = assignments_service.list_reviewees(db, review_session.id)

        rule_sets = library.list_visible_rule_sets(db, user=user)
        for rs in rule_sets:
            revision = rs.current_revision
            exclude_self = (
                revision.exclude_self_reviews if revision is not None else True
            )
            eligible_pair_count = 0
            if revision is not None:
                try:
                    rule_set_schema = RuleSetSchema(
                        id=rs.id,
                        name=rs.name,
                        description=rs.description or "",
                        scope=rs.scope,  # type: ignore[arg-type]
                        combinator=Combinator(revision.combinator),
                        rules=[
                            rule_adapter.validate_python(payload)
                            for payload in revision.rules_json
                        ],
                        options=RuleSetOptions(
                            excludeSelfReviews=revision.exclude_self_reviews,
                            seed=revision.seed,
                        ),
                    )
                    result = engine.evaluate(
                        rule_set_schema,
                        reviewers=reviewers,
                        reviewees=reviewees,
                        revision_seed=revision.id,
                    )
                    eligible_pair_count = len(result.pairs)
                except Exception:
                    # Swallow — a malformed schema shouldn't crash the
                    # card; surface 0 so the operator sees the option
                    # produces no pairs and can fix the ruleset.
                    eligible_pair_count = 0
            options.append(
                RuleBasedSelectorOption(
                    id=rs.id,
                    label=rs.name,
                    description=rs.description or "",
                    exclude_self_reviews=exclude_self,
                    is_seed=rs.is_seed,
                    eligible_pair_count=eligible_pair_count,
                )
            )
        # Default selection: the first seed in install order (Full
        # Matrix). The list is short enough that the operator scrolls
        # the dropdown either way; pinning the default to the
        # install-order-first row keeps the rendered UI free of any
        # special-casing on seed name.
        seed_options = [opt for opt in options if opt.is_seed]
        if seed_options:
            selected_option_id = seed_options[0].id
        elif options:
            selected_option_id = options[0].id

    # Resolve the selected option's description and exclude-self-
    # reviews default in Python, not Jinja. ``{% set %}`` inside a
    # ``{% for %}`` is loop-scoped in Jinja and resets when the loop
    # exits, which left ``selected_description`` blank on first
    # render and only populated after a JS-driven change event.
    selected_description = ""
    selected_exclude_self_reviews = True
    selected_eligible_pair_count = 0
    for option in options:
        if option.id == selected_option_id:
            selected_description = option.description
            selected_exclude_self_reviews = option.exclude_self_reviews
            selected_eligible_pair_count = option.eligible_pair_count
            break

    last_generated: RuleBasedLastGenerated | None = None
    last_event = db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.session_id == review_session.id,
            AuditEvent.event_type == "assignments.generated",
        )
        .order_by(AuditEvent.created_at.desc())
    ).scalars().first()
    if last_event is not None and last_event.detail is not None:
        ctx = last_event.detail.get("context") or {}
        if ctx.get("mode") == "rule_based":
            counts = last_event.detail.get("counts") or {}
            pair_count = counts.get("pairs")
            if isinstance(pair_count, int):
                rule_set_name: str | None = None
                refs = last_event.detail.get("refs") or {}
                rule_set_id = refs.get("rule_set_id")
                if isinstance(rule_set_id, int):
                    loaded = library.load_rule_set(db, rule_set_id)
                    if loaded is not None:
                        rule_set_name = loaded[0].name
                new_count = counts.get("new")
                last_generated = RuleBasedLastGenerated(
                    pair_count=pair_count,
                    when=last_event.created_at,
                    rule_set_name=rule_set_name,
                    assignment_count=(
                        new_count if isinstance(new_count, int) else None
                    ),
                )

    # Segment 13A-1 PR 4a — the assignments-page Rule Based card's
    # "Edit ruleset" link now points at the new single-card Rule
    # Builder surface (``/assignments/rule-based-editor``). The
    # legacy ``/assignments/rule-based/edit/{id}`` GET handler still
    # 303-redirects to the same place so any bookmarks / external
    # links keep working.
    if selected_option_id is not None:
        edit_url = (
            f"/operator/sessions/{review_session.id}"
            f"/assignments/rule-based-editor"
            f"?rule_set_id={selected_option_id}"
        )
    else:
        # Inert-branch placeholder — every session with at least one
        # seed has a selected option, so this only fires when the
        # card renders unwired (PR 0 fallback).
        edit_url = (
            f"/operator/sessions/{review_session.id}"
            "/assignments/rule-based-editor"
        )

    return RuleBasedCardContext(
        is_wired=user is not None,
        assignment_count=assignment_count,
        edit_url=edit_url,
        coming_in="The Rule Based editor child page ships in Segment 13A PR 5.",
        options=options,
        selected_option_id=selected_option_id,
        selected_description=selected_description,
        selected_exclude_self_reviews=selected_exclude_self_reviews,
        selected_eligible_pair_count=selected_eligible_pair_count,
        needs_confirm_replace=assignment_count > 0,
        error_kind=error_kind,
        last_generated=last_generated,
    )


# Segment 13A PR 5a — RuleSet editor child page (read-only scaffold).
# Renders the loaded RuleSet's metadata + rule tree as the locked
# sentence-shaped surface form (segment plan §"Rule semantics surface
# form"). PR 5a only ships the read-only view + a Copy action that
# duplicates the loaded RuleSet into a new Personal-scope RuleSet.
# PR 5b adds the inline-JS predicate / quota editors that mutate
# the rule list before Save / Save As.


_COMBINATOR_LABELS: dict[str, str] = {
    "ALL_OF": "All of",
    "ANY_OF": "Any of",
    "PIPELINE": "In sequence",
}

_OPERATOR_PHRASES: dict[str, str] = {
    "equals": "is",
    "not_equals": "is not",
    "in": "is one of",
    "not_in": "is not one of",
    "matches": "matches the pattern",
    "not_matches": "does not match the pattern",
    "is_empty": "is empty",
    "is_not_empty": "is set",
    "same_as": "is the same as",
    "different_from": "is different from",
}

_COMPOSITE_PREFIXES: dict[str, str] = {
    "AND": "All of:",
    "OR": "Any of:",
    "NOT": "None of:",
}


# Segment 13A PR 5b — Picker option lists for the editor surface.
# Field picker: tag1/2/3 on each side, plus the new ``pair_context``
# family from Segment 15D PR 3 (per-pair attributes — see
# ``guide/segment_15D_assignments_revamp.md``). Email is intentionally
# omitted: operator-authored rules don't reach for email comparisons
# (the engine's excludeSelfReviews desugar handles that case
# implicitly).
_FIELD_PICKER_VALUES: list[str] = [
    "reviewer.tag1",
    "reviewer.tag2",
    "reviewer.tag3",
    "reviewee.tag1",
    "reviewee.tag2",
    "reviewee.tag3",
    "pair_context.tag1",
    "pair_context.tag2",
    "pair_context.tag3",
]

# Operator picker labels match the locked sentence-form vocabulary
# (segment plan §"Rule semantics surface form").
_OPERATOR_PICKER_OPTIONS: list[tuple[str, str]] = [
    ("equals", "is"),
    ("not_equals", "is not"),
    ("in", "is one of"),
    ("not_in", "is not one of"),
    ("matches", "matches the pattern"),
    ("not_matches", "does not match the pattern"),
    ("is_empty", "is empty"),
    ("is_not_empty", "is set"),
    ("same_as", "is the same as"),
    ("different_from", "is different from"),
]

_KIND_PICKER_OPTIONS: list[tuple[str, str]] = [
    ("MATCH", "Include pairs where"),
    ("FILTER", "Exclude pairs where"),
    ("QUOTA", "Cap the number of"),
]

_COMBINATOR_PICKER_OPTIONS: list[tuple[str, str]] = [
    ("ALL_OF", "All of"),
    ("ANY_OF", "Any of"),
    ("PIPELINE", "In sequence"),
]

_QUOTA_SCOPE_OPTIONS: list[tuple[str, str]] = [
    ("PER_REVIEWEE", "reviewers per reviewee"),
    ("PER_REVIEWER", "reviewees per reviewer"),
]

_QUOTA_STRATEGY_OPTIONS: list[tuple[str, str]] = [
    ("RANDOM", "chosen randomly"),
    ("ROUND_ROBIN", "round-robin"),
]

_COMPOSITE_OP_OPTIONS: list[tuple[str, str]] = [
    ("AND", "All of:"),
    ("OR", "Any of:"),
    ("NOT", "None of:"),
]


@dataclass(frozen=True)
class RuleLine:
    """One rendered line on the read-only rule list.

    ``indent`` drives the left guideline / padding for nested
    composite children. ``text`` is the sentence-shaped rule body.
    ``kind`` lets the template apply per-kind classes (e.g. a
    different colour for FILTER vs MATCH if needed)."""

    indent: int
    text: str
    rule_id: str
    kind: str
    enabled: bool


@dataclass(frozen=True)
class EditableRule:
    """A rule rendered for in-place editing on Personal RuleSets.

    Carries the structured shape so the template can populate the
    field/operator/operand pickers and the quota-editor inputs.
    Composite rules render their op picker + an "Add child rule"
    button; their children render as full edit rows immediately
    after the parent with ``indent`` bumped (Segment 13A PR 5c).
    The JS serialiser walks the rendered DOM order and reconstructs
    the nested tree from each row's ``data-indent`` attribute.
    """

    rule_id: str
    kind: str  # MATCH / FILTER / QUOTA / COMPOSITE
    enabled: bool
    indent: int
    # MATCH / FILTER:
    field: str | None = None
    operator: str | None = None
    operand_text: str | None = None  # rendered as form-input value
    # QUOTA:
    quota_scope: str | None = None
    quota_min: int | None = None
    quota_max: int | None = None
    quota_strategy: str | None = None
    quota_seed: int | None = None
    # COMPOSITE:
    composite_op: str | None = None


def _render_field_reference(dotted: str) -> str:
    """``reviewer.tag1`` → ``reviewer tag1``. The dotted operator-
    facing form lives in the schema; the editor surface renders the
    side and attr space-separated so the sentence reads cleanly
    without an apostrophe (which Jinja's auto-escape would render as
    ``&#39;``)."""

    side, attr = dotted.split(".", 1)
    return f"{side} {attr}"


def _render_predicate_sentence(predicate: dict[str, Any]) -> str:
    field = predicate.get("field", "")
    op = predicate.get("operator", "")
    operand = predicate.get("operand")
    field_label = _render_field_reference(field) if field else "?"
    op_phrase = _OPERATOR_PHRASES.get(op, op)

    if op in ("is_empty", "is_not_empty"):
        return f"{field_label} {op_phrase}"

    if op in ("same_as", "different_from"):
        if isinstance(operand, str) and "." in operand:
            return f"{field_label} {op_phrase} {_render_field_reference(operand)}"
        return f"{field_label} {op_phrase} {operand!r}"

    if op in ("in", "not_in"):
        if isinstance(operand, list):
            items = ", ".join(repr(item) for item in operand)
            return f"{field_label} {op_phrase} [{items}]"
        return f"{field_label} {op_phrase} {operand!r}"

    if op in ("matches", "not_matches"):
        return f"{field_label} {op_phrase} /{operand}/"

    # equals / not_equals — literal scalar.
    return f"{field_label} {op_phrase} {operand!r}"


def _render_quota_sentence(rule: dict[str, Any]) -> str:
    scope = rule.get("scope", "")
    axis_target = "reviewee" if scope == "PER_REVIEWEE" else "reviewer"
    axis_obligor = "reviewer" if scope == "PER_REVIEWEE" else "reviewee"
    min_v = rule.get("min")
    max_v = rule.get("max")
    selection = rule.get("selection") or {}
    strategy = selection.get("strategy", "ROUND_ROBIN")
    seed = selection.get("seed")

    bound: str
    if min_v is not None and max_v is not None:
        bound = f"{min_v} to {max_v}" if min_v != max_v else f"{min_v}"
    elif max_v is not None:
        bound = f"up to {max_v}"
    elif min_v is not None:
        bound = f"at least {min_v}"
    else:
        bound = "any number of"

    strategy_phrase = (
        "chosen randomly" if strategy == "RANDOM" else "round-robin"
    )
    if strategy == "RANDOM" and seed is not None:
        strategy_phrase = f"{strategy_phrase} (seed={seed})"

    return (
        f"Cap at {bound} {axis_obligor}{'s' if bound not in ('1', 'at least 1') else ''} "
        f"per {axis_target}, {strategy_phrase}"
    )


def _flatten_rule_lines(
    rules: list[dict[str, Any]], *, indent: int = 0
) -> list[RuleLine]:
    lines: list[RuleLine] = []
    for rule in rules:
        kind = rule.get("kind", "")
        rule_id = str(rule.get("id", ""))
        enabled = bool(rule.get("enabled", True))

        if kind in ("MATCH", "FILTER"):
            verb = (
                "Include pairs where"
                if kind == "MATCH"
                else "Exclude pairs where"
            )
            sentence = f"{verb} {_render_predicate_sentence(rule.get('predicate', {}))}."
            lines.append(
                RuleLine(
                    indent=indent,
                    text=sentence,
                    rule_id=rule_id,
                    kind=kind,
                    enabled=enabled,
                )
            )
        elif kind == "QUOTA":
            lines.append(
                RuleLine(
                    indent=indent,
                    text=_render_quota_sentence(rule) + ".",
                    rule_id=rule_id,
                    kind=kind,
                    enabled=enabled,
                )
            )
        elif kind == "COMPOSITE":
            op = rule.get("op", "AND")
            prefix = _COMPOSITE_PREFIXES.get(op, "All of:")
            lines.append(
                RuleLine(
                    indent=indent,
                    text=prefix,
                    rule_id=rule_id,
                    kind=kind,
                    enabled=enabled,
                )
            )
            lines.extend(
                _flatten_rule_lines(
                    rule.get("rules") or [], indent=indent + 1
                )
            )
        else:
            lines.append(
                RuleLine(
                    indent=indent,
                    text=f"(unknown rule kind {kind!r})",
                    rule_id=rule_id,
                    kind=kind,
                    enabled=enabled,
                )
            )
    return lines


def _operand_to_text(rule: dict[str, Any]) -> str | None:
    """Render the operand value for a form input.

    ``in`` / ``not_in`` operands are stored as ``list[str]`` and
    presented as a comma-separated text field that the JS serialiser
    splits back on submit. Other operators carry the operand as a
    string (or None for nullary operators)."""

    predicate = rule.get("predicate") or {}
    operator = predicate.get("operator")
    operand = predicate.get("operand")
    if operator in ("is_empty", "is_not_empty"):
        return None
    if operator in ("in", "not_in"):
        if isinstance(operand, list):
            return ", ".join(str(item) for item in operand)
        return ""
    if operand is None:
        return ""
    return str(operand)


def _flatten_editable_rules(
    rules: list[dict[str, Any]], *, indent: int = 0
) -> list[EditableRule]:
    """Walk the rule tree and emit per-rule edit-form rows.

    Composite rules emit one parent row + one full edit row per
    composite child (Segment 13A PR 5c). The JS serialiser walks
    rendered DOM order and reconstructs the nested tree from each
    row's ``data-indent`` attribute — children are the consecutive
    rows with strictly greater indent following a composite.
    """

    out: list[EditableRule] = []
    for rule in rules:
        kind = str(rule.get("kind", ""))
        rule_id = str(rule.get("id", ""))
        enabled = bool(rule.get("enabled", True))
        if kind in ("MATCH", "FILTER"):
            predicate = rule.get("predicate") or {}
            out.append(
                EditableRule(
                    rule_id=rule_id,
                    kind=kind,
                    enabled=enabled,
                    indent=indent,
                    field=predicate.get("field"),
                    operator=predicate.get("operator"),
                    operand_text=_operand_to_text(rule),
                )
            )
        elif kind == "QUOTA":
            selection = rule.get("selection") or {}
            out.append(
                EditableRule(
                    rule_id=rule_id,
                    kind=kind,
                    enabled=enabled,
                    indent=indent,
                    quota_scope=rule.get("scope"),
                    quota_min=rule.get("min"),
                    quota_max=rule.get("max"),
                    quota_strategy=selection.get("strategy"),
                    quota_seed=selection.get("seed"),
                )
            )
        elif kind == "COMPOSITE":
            children = rule.get("rules") or []
            out.append(
                EditableRule(
                    rule_id=rule_id,
                    kind=kind,
                    enabled=enabled,
                    indent=indent,
                    composite_op=rule.get("op"),
                )
            )
            out.extend(
                _flatten_editable_rules(children, indent=indent + 1)
            )
    return out


# Segment 13A-1 — single-card Rule Builder page.
#
# PR 1 shipped the read-only scaffold. PR 2 extends the same context
# with editable form state for Personal RuleSets and "draft from
# source" state for Copy. PR 3 wires the blank-draft sentinel for
# real. The dataclass keeps both surfaces — read-only seed view + the
# editable Personal form — branchable from a single template.

# Sentinel id used in dropdown / query params to mean "+ New blank
# RuleSet". An int doesn't collide with any real RuleSet primary key
# and round-trips through ``int`` query params unchanged.
RULE_BUILDER_BLANK_SENTINEL_ID = -1


@dataclass(frozen=True)
class RuleBuilderOption:
    """One entry in the Rule Builder dropdown.

    ``id`` is the RuleSet primary key for real entries, or
    ``RULE_BUILDER_BLANK_SENTINEL_ID`` for the "+ New blank RuleSet"
    sentinel that PR 3 wires up. ``is_blank_sentinel`` lets the
    template branch on the sentinel without comparing magic numbers.
    """

    id: int
    label: str
    is_seed: bool
    is_personal: bool
    is_blank_sentinel: bool


# Default description seeded into the textarea on a fresh Copy /
# blank draft. Operators are expected to overwrite this with a
# friendlier explanation; saved-Personal selections preserve their
# stored description across reloads.
RULE_BUILDER_DRAFT_DEFAULT_DESCRIPTION = "User created ruleset"


@dataclass(frozen=True)
class AvailableRuleSetEntry:
    """One row in the sibling "Available rulesets" card.

    Carries the description so the card can show the operator-facing
    helper sentence next to the name. ``is_active`` lets the
    template highlight the row matching the current Rule Builder
    selection."""

    id: int
    name: str
    description: str
    is_seed: bool
    is_personal: bool
    is_active: bool


@dataclass(frozen=True)
class RuleBuilderContext:
    """Render context for the Rule Builder single-card page.

    Three render branches:

    - **Seeded RuleSet (read-only):** ``rule_lines`` carry the
      sentence-shaped predicates; only the Copy action is exposed.
    - **Saved Personal RuleSet (editable):** ``editable_rules`` +
      ``rules_json_initial`` populate PR 5b/5c's inline form; full
      Copy + Save + Cancel + Delete action row.
    - **Unsaved draft from a source (Copy):** rules / combinator /
      seed are loaded from the source RuleSet but the row isn't
      persisted yet — Save creates it (Save-As semantics). No Delete
      (nothing to delete).

    PR 3 ships the blank-sentinel branch (``selected_is_blank=True``
    with empty rules) on the same context.
    """

    options: list[RuleBuilderOption]
    selected_id: int  # RuleSet pk, RULE_BUILDER_BLANK_SENTINEL_ID, or 0 for draft
    selected_is_blank: bool
    selected_is_seed: bool
    selected_is_personal: bool
    selected_is_draft: bool
    """True when the current selection is an unsaved draft (Copy
    from a source). The form has no ``rule_set_id`` and Save creates
    the row from scratch."""
    editable: bool
    """True for saved-Personal and unsaved-draft branches; drives
    the editable rule-form vs. read-only sentence rendering."""
    name: str
    description: str
    combinator: str  # e.g., "ALL_OF" — form select value
    combinator_label: str  # e.g., "All of" — read-only display
    exclude_self_reviews: bool
    seed_value: int | None
    rule_lines: list[RuleLine]
    editable_rules: list[EditableRule]
    rules_json_initial: str
    """JSON-serialised initial value for the form's hidden
    ``rules_json`` field. The PR 5b/5c JS keeps it in sync with the
    visible controls before submit."""
    draft_source_id: int | None
    """For a draft branch: the source RuleSet id that Save-As pins
    in the audit's ``refs.source_rule_set_id`` slot."""
    draft_auto_name: bool
    """True iff the draft name still equals the literal "Copy of …"
    default. The Save route uses this to decide whether to apply
    the auto-suffix on collision (``" (n)"``) — operator-edited
    names get a 422 instead so a duplicate isn't created silently."""
    previous_id: int | None
    """For a draft branch: the dropdown selection the operator was
    on before clicking Copy. Cancel reverts to this id."""
    can_save: bool
    can_cancel: bool
    can_delete: bool
    can_copy: bool
    copy_url: str
    save_url: str
    delete_url: str
    cancel_url: str
    page_url: str
    error_kind: str | None
    error_message: str | None
    saved_flash: bool
    # Picker option lists for the editable form. Lifted from the
    # PR 5b/5c module-level tuples so the new card reuses the same
    # vocabulary (and the JS serialiser sees the same field/operator
    # values).
    field_options: list[str]
    operator_options: list[tuple[str, str]]
    kind_options: list[tuple[str, str]]
    combinator_options: list[tuple[str, str]]
    quota_scope_options: list[tuple[str, str]]
    quota_strategy_options: list[tuple[str, str]]
    composite_op_options: list[tuple[str, str]]
    available_rulesets: list[AvailableRuleSetEntry]
    """Rows for the sibling "Available rulesets" card. Same ordering
    as the dropdown — seeds first in install order, then caller-
    owned Personal."""


_RULE_BUILDER_ERROR_MESSAGES: dict[str, str] = {
    "empty_name": "Pick a name for the new RuleSet before clicking Save.",
    "malformed_json": "The edited rule list could not be parsed.",
    "validation": (
        "One or more rules failed validation. Check operator-"
        "operand pairings, regexes, and quota bounds."
    ),
    "bad_combinator": "Pick a combinator (All / Any / In sequence).",
    "bad_seed": "RuleSet seed must be an integer.",
    "name_collision": (
        "A RuleSet with that name already exists in your library. "
        "Pick a different name and try again."
    ),
    "needs_delete_confirm": (
        "Delete not confirmed. Tick the confirm checkbox before "
        "clicking Delete."
    ),
    "empty_rules": (
        "Add at least one rule before saving the new RuleSet."
    ),
}


def _rule_builder_blank_draft(
    review_session: ReviewSession,
    options: list[RuleBuilderOption],
    *,
    error_kind: str | None,
    saved_flash: bool,
    name_override: str | None = None,
    description_override: str | None = None,
    available_rulesets: list[AvailableRuleSetEntry] | None = None,
) -> RuleBuilderContext:
    """Live blank-draft context (Segment 13A-1 PR 3).

    Replaces the PR 1/PR 2 placeholder branch — selecting
    ``+ New blank RuleSet`` from the dropdown now renders an
    editable form with zero rules, default combinator ``ALL_OF``,
    and the auto-generated name ``"New RuleSet"``. Save is gated
    server-side until at least one rule exists; the Save button is
    also gated client-side via the inline JS in
    ``_rule_builder_card.html``."""

    return RuleBuilderContext(
        options=options,
        selected_id=RULE_BUILDER_BLANK_SENTINEL_ID,
        selected_is_blank=True,
        selected_is_seed=False,
        selected_is_personal=False,
        selected_is_draft=True,
        editable=True,
        name=name_override or "New RuleSet",
        description=(
            description_override
            if description_override is not None
            else RULE_BUILDER_DRAFT_DEFAULT_DESCRIPTION
        ),
        combinator="ALL_OF",
        combinator_label=_COMBINATOR_LABELS.get("ALL_OF", "All of"),
        exclude_self_reviews=True,
        seed_value=None,
        rule_lines=[],
        editable_rules=[],
        rules_json_initial="[]",
        draft_source_id=None,
        draft_auto_name=False,
        previous_id=None,
        can_save=True,
        can_cancel=True,
        can_delete=False,
        can_copy=False,
        copy_url=_rule_builder_url(review_session, "copy"),
        save_url=_rule_builder_url(review_session, "save"),
        delete_url=_rule_builder_url(review_session, "delete"),
        cancel_url=_rule_builder_url(review_session, ""),
        page_url=_rule_builder_url(review_session, ""),
        error_kind=error_kind,
        error_message=_RULE_BUILDER_ERROR_MESSAGES.get(error_kind or ""),
        saved_flash=saved_flash,
        field_options=list(_FIELD_PICKER_VALUES),
        operator_options=list(_OPERATOR_PICKER_OPTIONS),
        kind_options=list(_KIND_PICKER_OPTIONS),
        combinator_options=list(_COMBINATOR_PICKER_OPTIONS),
        quota_scope_options=list(_QUOTA_SCOPE_OPTIONS),
        quota_strategy_options=list(_QUOTA_STRATEGY_OPTIONS),
        composite_op_options=list(_COMPOSITE_OP_OPTIONS),
        available_rulesets=available_rulesets or [],
    )


# Back-compat alias: the PR 1/PR 2 default-blank fallback is now the
# same shape as the live blank-draft branch. Defensive fallbacks
# (no visible RuleSets, stale id) reuse it.
_rule_builder_default_blank = _rule_builder_blank_draft


def _rule_builder_url(review_session: ReviewSession, suffix: str) -> str:
    """Build a path under ``/assignments/rule-based-editor``.

    Empty ``suffix`` yields the bare page URL; otherwise returns
    ``/<suffix>``. Centralised so the route module and the context
    builder stay in lockstep."""

    base = (
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor"
    )
    return f"{base}/{suffix}" if suffix else base


def _build_rule_builder_options(
    db: Session, *, user: User
) -> tuple[list[RuleBuilderOption], list, list, dict[int, object]]:
    """Pull the visible RuleSets once and shape them into the
    dropdown options + the seed/personal lists used for fallback
    selection. Returns ``(options, seeds, personal, by_id)``."""


    visible = list(library.list_visible_rule_sets(db, user=user))
    seeds = [rs for rs in visible if rs.is_seed]
    personal = [rs for rs in visible if not rs.is_seed]

    options: list[RuleBuilderOption] = []
    for rs in seeds:
        options.append(
            RuleBuilderOption(
                id=rs.id,
                label=rs.name,
                is_seed=True,
                is_personal=False,
                is_blank_sentinel=False,
            )
        )
    for rs in personal:
        options.append(
            RuleBuilderOption(
                id=rs.id,
                label=rs.name,
                is_seed=False,
                is_personal=True,
                is_blank_sentinel=False,
            )
        )
    options.append(
        RuleBuilderOption(
            id=RULE_BUILDER_BLANK_SENTINEL_ID,
            label="+ New blank RuleSet",
            is_seed=False,
            is_personal=False,
            is_blank_sentinel=True,
        )
    )
    by_id = {rs.id: rs for rs in visible}
    return options, seeds, personal, by_id


def _build_available_rulesets(
    seeds: list, personal: list, *, active_id: int | None
) -> list[AvailableRuleSetEntry]:
    """Shape the visible RuleSet list for the sibling
    "Available rulesets" card. Same ordering as the dropdown:
    seeds first in install order, then caller-owned Personal.
    ``active_id`` is the currently-selected RuleSet id (or None
    when the operator is on a draft / blank); the matching row
    renders highlighted."""

    rows: list[AvailableRuleSetEntry] = []
    for rs in seeds:
        rows.append(
            AvailableRuleSetEntry(
                id=rs.id,
                name=rs.name,
                description=rs.description or "",
                is_seed=True,
                is_personal=False,
                is_active=(active_id == rs.id),
            )
        )
    for rs in personal:
        rows.append(
            AvailableRuleSetEntry(
                id=rs.id,
                name=rs.name,
                description=rs.description or "",
                is_seed=False,
                is_personal=True,
                is_active=(active_id == rs.id),
            )
        )
    return rows


def build_rule_builder_context(
    review_session: ReviewSession,
    *,
    db: Session,
    user: User,
    selected_id: int | None = None,
    as_draft_from: int | None = None,
    previous_id: int | None = None,
    error_kind: str | None = None,
    saved_flash: bool = False,
    draft_name_override: str | None = None,
) -> RuleBuilderContext:
    """Build the Rule Builder card context.

    ``selected_id`` resolves a real RuleSet (or the blank sentinel
    when equal to ``RULE_BUILDER_BLANK_SENTINEL_ID``). When
    ``as_draft_from`` is set, the page renders an *unsaved draft*
    cloning the source RuleSet's rules + combinator + seed, with the
    name auto-generated as ``"Copy of <source>"`` (locked decision
    #5). ``previous_id`` is the dropdown selection the operator was
    on before clicking Copy; the Cancel button reverts to it.

    Stale or non-visible ids fall back to the first seed — refresh
    must always render rather than 404, since the URL bar is
    intentionally clean of selection state.
    """


    options, seeds, _personal, by_id = _build_rule_builder_options(db, user=user)

    if as_draft_from is not None:
        return _build_draft_context(
            review_session,
            db=db,
            options=options,
            source_id=as_draft_from,
            previous_id=previous_id,
            user=user,
            error_kind=error_kind,
            saved_flash=saved_flash,
            draft_name_override=draft_name_override,
            seeds=seeds,
            personal=_personal,
        )

    if selected_id == RULE_BUILDER_BLANK_SENTINEL_ID:
        return _rule_builder_blank_draft(
            review_session,
            options,
            error_kind=error_kind,
            saved_flash=saved_flash,
            available_rulesets=_build_available_rulesets(
                seeds, _personal, active_id=None
            ),
        )

    if selected_id is None or selected_id not in by_id:
        if seeds:
            selected_id = seeds[0].id
        else:
            return _rule_builder_blank_draft(
                review_session,
                options,
                error_kind=error_kind,
                saved_flash=saved_flash,
                available_rulesets=_build_available_rulesets(
                    seeds, _personal, active_id=None
                ),
            )

    loaded = library.load_rule_set(db, selected_id)
    if loaded is None:
        if seeds:
            selected_id = seeds[0].id
            loaded = library.load_rule_set(db, selected_id)
        if loaded is None:
            return _rule_builder_blank_draft(
                review_session,
                options,
                error_kind=error_kind,
                saved_flash=saved_flash,
                available_rulesets=_build_available_rulesets(
                    seeds, _personal, active_id=None
                ),
            )
    rule_set, revision = loaded

    rules = revision.rules_json or []
    is_seed = bool(rule_set.is_seed)
    is_personal = (
        not is_seed
        and rule_set.owner_user_id == user.id
        and rule_set.deleted_at is None
    )
    editable = is_personal

    return RuleBuilderContext(
        options=options,
        selected_id=rule_set.id,
        selected_is_blank=False,
        selected_is_seed=is_seed,
        selected_is_personal=is_personal,
        selected_is_draft=False,
        editable=editable,
        name=rule_set.name,
        description=rule_set.description or "",
        combinator=revision.combinator,
        combinator_label=_COMBINATOR_LABELS.get(
            revision.combinator, revision.combinator
        ),
        exclude_self_reviews=bool(revision.exclude_self_reviews),
        seed_value=revision.seed,
        rule_lines=_flatten_rule_lines(rules),
        editable_rules=_flatten_editable_rules(rules) if editable else [],
        rules_json_initial=_dump_rules_json(rules) if editable else "[]",
        draft_source_id=None,
        draft_auto_name=False,
        previous_id=None,
        can_save=editable,
        can_cancel=editable,
        can_delete=editable,
        can_copy=True,
        copy_url=_rule_builder_url(review_session, "copy"),
        save_url=_rule_builder_url(review_session, "save"),
        delete_url=_rule_builder_url(review_session, "delete"),
        cancel_url=_rule_builder_url(review_session, "")
        + f"?rule_set_id={rule_set.id}",
        page_url=_rule_builder_url(review_session, ""),
        error_kind=error_kind,
        error_message=_RULE_BUILDER_ERROR_MESSAGES.get(error_kind or ""),
        saved_flash=saved_flash,
        field_options=list(_FIELD_PICKER_VALUES),
        operator_options=list(_OPERATOR_PICKER_OPTIONS),
        kind_options=list(_KIND_PICKER_OPTIONS),
        combinator_options=list(_COMBINATOR_PICKER_OPTIONS),
        quota_scope_options=list(_QUOTA_SCOPE_OPTIONS),
        quota_strategy_options=list(_QUOTA_STRATEGY_OPTIONS),
        composite_op_options=list(_COMPOSITE_OP_OPTIONS),
        available_rulesets=_build_available_rulesets(
            seeds, _personal, active_id=rule_set.id
        ),
    )


def _build_draft_context(
    review_session: ReviewSession,
    *,
    db: Session,
    options: list[RuleBuilderOption],
    source_id: int,
    previous_id: int | None,
    user: User,
    error_kind: str | None,
    saved_flash: bool,
    draft_name_override: str | None,
    draft_description_override: str | None = None,
    seeds: list,
    personal: list,
) -> RuleBuilderContext:
    """Render the page as an unsaved draft cloning ``source_id``'s
    rules + combinator + seed (Copy from seed/Personal). Falls back
    to the default selection when the source can't be resolved or
    isn't visible to the caller — same posture as a stale
    ``rule_set_id`` query param."""


    loaded = library.load_rule_set(db, source_id)
    if loaded is None:
        if seeds:
            return build_rule_builder_context(
                review_session,
                db=db,
                user=user,
                selected_id=seeds[0].id,
                error_kind=error_kind,
                saved_flash=saved_flash,
            )
        return _rule_builder_blank_draft(
            review_session,
            options,
            error_kind=error_kind,
            saved_flash=saved_flash,
            available_rulesets=_build_available_rulesets(
                seeds, personal, active_id=None
            ),
        )
    source_rule_set, source_revision = loaded
    if (
        not source_rule_set.is_seed
        and source_rule_set.owner_user_id != user.id
    ):
        # Non-visible Personal RuleSet — redirect to default rather
        # than expose its existence via 403. Matches the
        # ``rule_set_id`` fallback posture.
        if seeds:
            return build_rule_builder_context(
                review_session,
                db=db,
                user=user,
                selected_id=seeds[0].id,
                error_kind=error_kind,
                saved_flash=saved_flash,
            )
        return _rule_builder_blank_draft(
            review_session,
            options,
            error_kind=error_kind,
            saved_flash=saved_flash,
            available_rulesets=_build_available_rulesets(
                seeds, personal, active_id=None
            ),
        )

    rules = source_revision.rules_json or []
    auto_name = f"Copy of {source_rule_set.name}"
    rendered_name = draft_name_override or auto_name
    rendered_description = (
        draft_description_override
        if draft_description_override is not None
        else RULE_BUILDER_DRAFT_DEFAULT_DESCRIPTION
    )
    cancel_url = _rule_builder_url(review_session, "")
    if previous_id is not None and previous_id > 0:
        cancel_url = f"{cancel_url}?rule_set_id={previous_id}"

    return RuleBuilderContext(
        options=options,
        # Drafts have no row in the DB yet; the dropdown stays on
        # the source's id so the operator can see what they cloned.
        selected_id=source_rule_set.id,
        selected_is_blank=False,
        selected_is_seed=False,
        selected_is_personal=False,
        selected_is_draft=True,
        editable=True,
        name=rendered_name,
        description=rendered_description,
        combinator=source_revision.combinator,
        combinator_label=_COMBINATOR_LABELS.get(
            source_revision.combinator, source_revision.combinator
        ),
        exclude_self_reviews=bool(source_revision.exclude_self_reviews),
        seed_value=source_revision.seed,
        rule_lines=_flatten_rule_lines(rules),
        editable_rules=_flatten_editable_rules(rules),
        rules_json_initial=_dump_rules_json(rules),
        draft_source_id=source_rule_set.id,
        draft_auto_name=(rendered_name == auto_name),
        previous_id=previous_id,
        can_save=True,
        can_cancel=True,
        can_delete=False,
        can_copy=False,
        copy_url=_rule_builder_url(review_session, "copy"),
        save_url=_rule_builder_url(review_session, "save"),
        delete_url=_rule_builder_url(review_session, "delete"),
        cancel_url=cancel_url,
        page_url=_rule_builder_url(review_session, ""),
        error_kind=error_kind,
        error_message=_RULE_BUILDER_ERROR_MESSAGES.get(error_kind or ""),
        saved_flash=saved_flash,
        field_options=list(_FIELD_PICKER_VALUES),
        operator_options=list(_OPERATOR_PICKER_OPTIONS),
        kind_options=list(_KIND_PICKER_OPTIONS),
        combinator_options=list(_COMBINATOR_PICKER_OPTIONS),
        quota_scope_options=list(_QUOTA_SCOPE_OPTIONS),
        quota_strategy_options=list(_QUOTA_STRATEGY_OPTIONS),
        composite_op_options=list(_COMPOSITE_OP_OPTIONS),
        available_rulesets=_build_available_rulesets(
            seeds, personal, active_id=source_rule_set.id
        ),
    )


def _dump_rules_json(rules: list[dict[str, Any]]) -> str:
    """Serialise the rule tree for the form's hidden ``rules_json``
    field. The PR 5b/5c JS reads this on first paint and keeps it
    in sync with the visible controls."""

    import json as _json

    return _json.dumps(rules, separators=(",", ":"))

