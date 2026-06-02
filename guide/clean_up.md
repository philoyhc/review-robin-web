# Clean-up backlog

Standing punch-list of small-to-medium follow-ups identified
by code review, not yet shipped. Items here have **already
been acknowledged** by the project (i.e. they're not "first
ask"); the file exists so we can pick one off the top in idle
moments rather than re-discovering them.

When an item ships, strike it through with `~~text~~` and
suffix the merge PR number, or remove it entirely if it
retires for another reason.

## Conventions

- Each item carries a **Severity** tag (Medium / Low / Nit)
  and a **Source** noting where it was first flagged.
- Items are roughly priority-ordered within their severity
  band. Order is suggestive, not binding — promote a Low
  above a Medium when the surface it touches is being
  modified anyway.

## Open items

### Medium

1. ~~**Service-layer lifecycle assertion for `set_cohort_rule`.**~~
   *Closed without action #current — deliberate decision:
   cohort rules govern which parts of response data are
   visible to an observer, not the response data itself or
   the roster shape, so there's no contract that requires
   lifecycle-gating at the service layer. The route still
   calls ``_require_editable`` for parity with other
   Setup-page mutators; if a future product decision opens
   mid-session refinement, only the route gate needs
   lifting. Docstring on ``set_cohort_rule`` captures the
   rationale so the gap doesn't get re-flagged.*

2. ~~**Cohort-rule save failure UX.**~~
   *Shipped #current (partial) — the verbose Pydantic error
   no longer leaks to the operator. ``invalid_cohort_rule``
   now carries the friendly message ``"Couldn't save the
   cohort rule. Check that every rule cell has a field
   selected and an operand."``; the original exception rides
   along via ``from exc`` for dev tracebacks. The full
   re-render-with-editor-state-preserved fix is still
   deferred — see Item 12 of the original review for the
   editor-rehydration complication.*

3. ~~**HTTP-layer test for cross-session `observer_ids`.**~~
   *Shipped #current — integration test pins the 400, service
   message tightened to `"Invalid observer selection."` so the
   foreign id no longer leaks.*

4. ~~**`data-observer-cohort-rule` renders unconditionally.**~~
   *Shipped #current — attribute now gated on `selectable`
   (matches when the cohort editor + checkboxes render).*

5. ~~**`loadEditorFromRule` silently degrades when the saved
   `operand_tag` no longer exists.**~~
   *Shipped #current — ``loadEditorFromRule`` now calls
   ``ensureStaleOption`` against both the field and operand
   selects before assigning, inserting a disabled
   ``<option>`` carrying the saved canonical key suffixed
   with ``(missing label)`` when the value isn't in the live
   dropdown. The operator sees the stale value, can't
   re-select it, and overwrites by picking a valid option.*

6. ~~**Empty `operand_value` on value operators round-trips
   but renders ambiguously.**~~
   *Shipped #current — the summary now renders the empty case
   as `… IS «empty»` to distinguish "filter on blank field"
   from "unfilled cell". The "filter on blank" semantic stays
   available; no schema or parser change.*

### Low

7. ~~**Route-side coercion of `combinator` hides client desyncs.**~~
   *Shipped #current — parser now passes ``combinator``
   through verbatim (uppercase-only). Unknown values 400 via
   ``CohortRuleSet.model_validate`` instead of silently
   landing ``AND``. Integration test exercises a ``"XOR"``
   submission.*

8. ~~**No integration test for byte-identical
   `data-observer-cohort-rule` across rows.**~~
   *Shipped #current — new integration test saves the same
   rule to two observers via the route, then asserts both
   ``data-observer-cohort-rule`` attribute strings are
   byte-identical in the GET response.*

9. ~~**`set_cohort_rule` empty-`observer_ids` no-op
   unreachable from the route.**~~
   *Shipped #current — service now raises
   ``ObserverOperationError("empty_selection", ...)`` instead
   of silently returning ``None``. Route's early 400 block
   dropped — the standard ``except ObserverOperationError``
   handler catches the new code. Unit test renamed +
   updated to assert the raise.*

### Nit

10. ~~**`form: Any` annotation on `_parse_cohort_rule_form`.**~~
    *Shipped #current — typed as
    ``starlette.datastructures.FormData``. Band 1's
    ``_form_rules`` still carries the same nit; defer until
    Band 1 gets touched for another reason.*

11. ~~**Curly quotes in the friendly cohort summary.**~~
    *Shipped #current — value-operator operands now render
    with ASCII straight quotes (``"math"`` instead of
    ``"math"``). The ``«empty»`` rendering from item 6 keeps
    its distinctive look so the "filter on blank field" case
    stays visually unambiguous.*

### Medium-but-deferred

12. ~~**Loosen the cohort-edit lifecycle gate to "not
    archived".**~~
    *Shipped #current — new ``_require_not_archived`` helper
    in ``app/web/routes_operator/_shared.py``; the
    ``observers_cohort_rule_save`` route now uses it. Template
    splits the cohort editor into its own card sibling to (not
    nested in) the Operator actions card, with its own
    visibility gate ``not edit_mode and not is_archived``.
    ``selectable`` widens to the same gate so the table
    checkboxes stay live during ``ready`` / ``expired`` for
    the cohort save flow; the bulk-actions card still hides
    during ``ready`` (lock pattern) so the Edit / Inactivate /
    Activate buttons can't fire. JS null-checks each element
    so it works in any combination. Spec + service docstring
    updated.*

### Observer cohort follow-ups (post-MVP)

The collation MVP shipped 2026-06-02 (#1799 → #1806). Three
deferral notes from that ladder, now logged here so they don't
get lost when ``guide/observers.md`` is sweep-trimmed:

13. **`pair_context.*` left-side rules.** The
    ``CohortRuleSet`` schema accepts ``pair_context.tag1`` /
    ``tag2`` / ``tag3`` as the rule's left field. Today both
    ``observer_cohort.materialize_cohort`` (set-side, used by
    the surface stats rows) and
    ``observer_cohort.assignment_matches_cohort`` (per-row,
    used by the CSV filter) silently treat any
    ``pair_context.*`` rule as unmatched. Lighting it up needs
    a pair-level join against ``relationships`` /
    ``Assignment`` to resolve the per-pair tag value.
    *Source: ``observer_cohort.py`` module docstring (deferred
    case) + ``test_pair_context_rule_returns_empty_for_now``.*

14. **Cross-roster ``operand_tag`` (e.g.
    ``reviewer.tag1 IS THE SAME AS reviewee.tag2``).** The
    schema permits the right-hand operand to point at the
    opposite roster, but the materialiser + per-row
    predicate both treat it as unmatched. Same pair-level
    requirement as item 13. The Cohort match rule editor
    on the Observers Setup page already exposes these
    options in the operand dropdown — the operator can
    author the rule today, it just doesn't fire.
    *Source: ``observer_cohort.py`` ``_rule_matches_row`` +
    ``test_cross_roster_operand_tag_returns_empty_for_now``.*

15. **"Decode token" widget on the Observers Setup page.**
    Per ``guide/observers.md`` token-design decisions, the
    operator should be able to paste an Anonymized token
    (``R-a3f8b2c1``) and get back the underlying
    name + email by re-hashing the roster. Cheap at typical
    roster sizes (≤1000 rows). Not yet implemented; nothing
    in the surface today reveals identification on demand.
    *Source: ``guide/observers.md`` "Token design —
    decisions" (operator decoder bullet).*

16. **Stats-row cohort scope review.** The collation
    surface's Row 1 / Row 2 (reviewer-side / reviewee-side
    aggregates) query ``cohort.reviewer_ids`` /
    ``cohort.reviewee_ids`` independently via the
    set-based materialiser. The CSV download tightened to
    per-row predicate evaluation (PR #1804) because the
    set-based approach degenerated on cross-side OR rules.
    The stats rows have the same vulnerability in theory.
    Worth a review with real data — the stats rows may
    deserve a similar per-row reformulation, or the
    set-based shape may turn out to be the right
    perspective for those rows specifically (since they're
    "side-grouped views", not "row passes/fails" views).
    *Source: PR #1804 description, "Note on stats rows".*

## Workflow

When picking an item up:

1. Skim the source flag (read the review note or the linked
   PR comment) so the framing matches the original concern.
2. Land the fix as its own small PR — these items are
   intentionally independent, so don't bundle.
3. Update this file in the same PR: strike the item, suffix
   the merge PR.
4. If a fix turns up an adjacent bug or design question,
   add a new entry rather than expanding the existing one.
