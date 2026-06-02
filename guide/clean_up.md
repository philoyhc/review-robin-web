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

7. **Route-side coercion of `combinator` hides client desyncs.**
   `_parse_cohort_rule_form` falls back to `"AND"` for any
   non-`OR` value. If the JS ever desyncs the hidden mirror
   (a future `observerToggleCombinator` change), the save
   silently lands `AND` instead of failing loud. Pass
   `combinator` through verbatim (or only uppercase it) and
   let `CohortRuleSet.model_validate` gatekeep.
   *Source: Observers code review, finding #11 (2026-06-02).*

8. **No integration test that two rows sharing the same saved
   rule produce byte-identical `data-observer-cohort-rule`
   attributes.** The mixed-state JS depends on byte-identity
   of the rendered attribute strings (it does a string-set
   distinct-count). If the template ever rendered the
   attribute through a different path for one row vs another,
   the cross-row-shared-rule UX would silently break.
   *Source: Observers code review, finding #12 (2026-06-02).*

9. **`set_cohort_rule` empty-`observer_ids` no-op is
   unreachable from the route.** The route 400s on empty
   selection before reaching the service. The service still
   docstring-promises a no-op and a unit test pins it. Either
   lift the empty-selection 400 into the service (single
   source of truth) or accept the duplication and note in
   the route docstring that the service is forgiving.
   *Source: Observers code review, finding #13 (2026-06-02).*

### Nit

10. **`form: Any` annotation on `_parse_cohort_rule_form`.**
    Should be `starlette.datastructures.FormData`. Band 1's
    `_form_rules` carries the same nit — fix both together
    if either gets touched.
    *Source: Observers code review, finding #14 (2026-06-02).*

11. **Curly quotes in the friendly cohort summary.** The
    summary string uses U+201C / U+201D for value-operator
    operands; would render oddly in CSV / shell exports if
    the summary text ever leaves the rendered HTML. Plain
    quotes + CSS-side typography prettification is the
    long-term fix.
    *Source: Observers code review, finding #15 (2026-06-02).*

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
