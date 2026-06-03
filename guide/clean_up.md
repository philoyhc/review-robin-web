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

13. ~~**`pair_context.*` left-side rules.**~~
    *Closed by removing the option from the UI #current — the
    Cohort match rule editor's field + operand_tag dropdowns no
    longer surface ``pair_context.*`` entries on the Observers
    Setup page, so an operator can't author such a rule. The
    schema still accepts the value and the materialiser +
    per-row predicate still treat it as unmatched, so legacy
    saved rules (none expected in practice) degrade safely.
    The pair-level join remains deferred — when a future
    product decision asks for pair-context cohort filters, the
    work is to add the UI back + light up the
    ``observer_cohort.py`` branches.*

14. ~~**Cross-roster ``operand_tag`` (e.g.
    ``reviewer.tag1 IS THE SAME AS reviewee.tag2``).**~~
    *Closed by removing the option from the UI #current —
    the right-side ``operand_tag`` dropdown now only carries
    the three ``Observer:`` attributes; the cross-roster
    ``Reviewer:`` / ``Reviewee:`` options + the separator
    row are gone. Schema + materialiser + per-row predicate
    still recognise cross-roster operands defensively
    (legacy saved rules degrade to an empty cohort). The
    pair-level join remains deferred — if a future product
    decision asks for it, the work is to restore the
    dropdown rows and light up the ``observer_cohort.py``
    cross-roster branches.*

15. ~~**"Decode token" widget on the Observers Setup page.**~~
    *Closed via the Extract data tab #current — instead of a
    paste-a-token widget, the operator downloads
    ``participant_tokens.csv`` from the new Token keys card on
    the Extract data page (or via the ``Token keys`` chip on
    the intro card's Zip-all bundle) and Ctrl-Fs the token.
    Same deanonymization use case (cheap roster lookup), no
    new JS / per-lookup audit machinery. Service:
    ``app/services/extracts/participant_tokens_extract.py``;
    route: ``GET /sessions/{id}/export/participant_tokens.csv``;
    bundle inclusion gated on ``observers_enabled`` (tokens
    have no consumer without observers today).*

16. ~~**Stats-row cohort scope review.**~~
    *Closed #current — the surface stats rows now honour the
    partition model: ``materialize_cohort_assignments`` walks
    per-(observer, instrument) assignments via the per-row
    predicate, returning the in-cohort assignment id set + the
    two side-distinct counts. ``build_cohort_stats_for_instrument``
    runs one aggregate query against the pool and returns Row 1 +
    Row 2 sharing the same ``field_cells`` + ``response_count``;
    only the ``distinct_count`` headcount differs per row. The
    pre-existing ``CohortIds`` set-based materialiser + Row 2's
    "(anyone) writing about the cohort's reviewees" framing are
    gone. Cross-side OR / single-side rule degeneracies fixed at
    the source.*

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
