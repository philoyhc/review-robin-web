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

12. **Loosen the cohort-edit lifecycle gate to "not
    archived".** Today the route handler
    (`observers_cohort_rule_save`) calls `_require_editable`,
    which allows only draft + validated states. Cohort
    rules govern *which parts of response data are visible
    to an observer* — they don't affect roster shape or
    response data — so the operator can legitimately
    refine them mid-session (active / expired states),
    and only `archived` is a real hard stop. Two pieces of
    work:

    - **Route:** swap `_require_editable` for a check that
      blocks only `archived` (or just delete the call —
      whatever pattern the rest of the codebase grows when
      a similar mid-session-edit case lands).
    - **Template:** the cohort editor currently nests inside
      the operator-actions card, which the whole-card lock
      pattern hides when `is_ready`. Either split the
      cohort editor out into its own card with looser
      visibility gating, or selectively render the
      operator-actions card during active states with the
      bulk-action buttons disabled while the cohort
      controls stay live.

    Defer until the W17 collation consumer surface ships —
    at that point the mid-session-edit use case becomes
    concrete (operator notices observer cohort needs
    refinement after observers start accessing the
    surface) and the right UX shape will be clearer.
    *Source: Item 1 revisited (2026-06-02) — see commit
    closing item 1 for the original rationale, and
    https://github.com/philoyhc/review-robin-web/pull/1794
    for the docstring on ``set_cohort_rule`` capturing the
    "no service-layer lifecycle gate" decision.*

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
