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

1. **Service-layer lifecycle assertion for `set_cohort_rule`.**
   The route calls `_require_editable`, but
   `app/services/observers.py::set_cohort_rule` itself has no
   lifecycle guard — every other observer mutator
   (`create_observer` / `update_observer` / `_bulk_set_status`)
   calls `lifecycle.invalidate_if_validated`. Defensible to
   skip (cohort_rule is post-validation configuration), but
   the layering inconsistency means a non-route caller could
   mutate `cohort_rule` on a non-draft session.
   *Source: Observers code review, finding #3 (2026-06-02).*

2. **Cohort-rule save failure UX.** Invalid payloads (or a
   forged `op` / `combinator`) raise
   `ObserverOperationError("invalid_cohort_rule")` which the
   route turns into a bare HTTP 400 page with the raw Pydantic
   error string in the body. Compare to `observers_create` /
   `observers_update`, which re-render the Observers page with
   `edit_error=` set + a banner. Editor cell state re-hydration
   is the harder bit; a flash banner + preserved selection is
   probably enough for MVP.
   *Source: Observers code review, finding #4 (2026-06-02).*

3. **HTTP-layer test for cross-session `observer_ids`.** The
   service-level
   `test_set_cohort_rule_rejects_ids_from_other_session`
   pins the invariant in isolation; no integration test
   confirms the 400 surfaces at
   `POST /operator/sessions/{id}/observers/cohort-rule`. The
   error message also leaks the foreign observer id (low
   info-leak, but worth a deliberate decision — generalize to
   `"Invalid observer selection"`).
   *Source: Observers code review, finding #5 (2026-06-02).*

4. **`data-observer-cohort-rule` renders unconditionally.**
   The attribute lands on every observer row in the rendered
   HTML, even when `edit_mode` / `is_ready` hides the cohort
   editor + the checkboxes. Functionally harmless but ships
   the full saved-rule JSON to anyone who can GET the
   Observers page in those modes. Render the attribute only
   when `selectable` is true.
   *Source: Observers code review, finding #6 (2026-06-02).*

5. **`loadEditorFromRule` silently degrades when the saved
   `operand_tag` no longer exists.** The JS does
   `tagSel.value = entry.operand_tag` — if the operator
   cleared that tag slot's label after the rule was saved,
   the assignment falls through to the first option without
   surfacing the drift. The Cohort-column summary handles
   the same case correctly (falls back to the canonical key).
   Either add a hidden disabled option preserving the saved
   value, or render a small notice when the saved
   `operand_tag` isn't in the dropdown.
   *Source: Observers code review, finding #7 (2026-06-02).*

6. **Empty `operand_value` on value operators round-trips
   but renders ambiguously.** The schema permits it; the
   Cohort summary renders as `… IS “”` (empty quoted
   string), visually indistinguishable from an unfilled cell.
   Decide: treat blank `operand_value` as a blank-cell drop
   in the form parser (mirrors the blank-field guard), or
   pin the current behavior with an integration test +
   surface as a Validate-page warning. No integration
   coverage currently.
   *Source: Observers code review, finding #8 (2026-06-02).*

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
