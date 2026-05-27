# Segment 18K — Completing instrument visibility (Band 3) on the reviewer surface

> **Status: drafting (stub created 2026-05-27).** No PRs yet. The
> scope below is a working sketch — confirm policy choices with the
> human author before landing PR 1.
>
> **Predecessors.** Segment 17B Phase 2 shipped the reviewer
> summary page; Segment 18J Wave 6 cluster B re-aligned the
> operator-side Band 2 → reviewer-surface pipeline. The
> `instruments.is_new_model` flag retired in Wave 5; Band 3 fields
> are now real DB rows on `instrument_response_fields`. The
> reviewer-side visibility audit
> (`guide/visibility_audit.md`) is the authoritative reference
> for what each reviewer-facing route renders in each state.
>
> **Sibling segments.** **18F** (workflow optimisation,
> archived), **18G** (scheduled events, archived), and **17B**
> (reviewer surface refinements, archived) — the visibility
> story this segment closes is the per-field tail end of the
> per-instrument story 17B / 18F / 18G already wired.

## Goal

Make `InstrumentResponseField.visible` behave **consistently
across every reviewer-facing surface**, and bring the spec in
line with the actual operator-side UX (the Band 2 pill is the
visibility control — there is no per-row "Visible" checkbox on
Band 3 even though `spec/instruments.md` still describes one).

The two-line summary of where things stand today, established
by 2026-05-27 codebase reading:

- **Reviewer surface form** (`routes_reviewer/_surface.py:364`):
  filters response fields by `InstrumentResponseField.visible.is_(True)`.
  Correct.
- **Reviewer summary HTML** (`app/web/views/_reviewer_summary.py:391`):
  walks `instrument.response_fields` directly — **no `visible`
  filter**. A response field flipped off after responses were
  saved still renders as a summary column with the stored value.
- **Reviewer summary CSV** (`app/services/extracts/responses_extract.py:551`):
  same shape as the HTML — walks `instrument.response_fields`
  without filtering by `visible`. Hidden columns appear in the
  preamble *and* are joined into the data rows.
- **Operator side**: the "visibility" toggle for a Band 3 row
  is the **Band 2 chip** (`data-source-type="response"`); ticking
  / un-ticking the pill writes
  `InstrumentResponseField.visible` via
  `bulk_save_fields` (`_instrument_crud.py:1422`). The Band 3 row
  template (`instruments_index.html:3407-3496`) carries R, ≡, ✓, X
  buttons — **no per-row visible checkbox** despite
  `spec/instruments.md:434` claiming one. The spec lags the UI.

This segment closes both gaps and pins a clear policy for
hidden-with-saved-responses.

## Scope (sketch — to be confirmed)

### Part 1 — Filter response fields by `visible` on the reviewer summary

**HTML** — `_reviewer_summary.py` walks
`instrument.response_fields` in two places (the `field_cols`
composition around line 390 and the cell-index walk that
loads responses, around line 320). Both should restrict to
`visible=True` rows so the summary table matches what the
reviewer saw on the form.

**CSV** — `serialize_reviewer_session_summary` in
`responses_extract.py` should mirror the HTML's filter. The
function is shared with operator bundle exports
(`serialize_responses` family) — confirm whether the per-bundle
path *should* keep hidden fields (for audit) or also drop them
(consistent with the reviewer-facing CSV). Likely answer: the
**reviewer-record** path filters; the **operator bundle** path
includes hidden fields with a marker.

Decision points to confirm before coding:
- Do we **also** suppress *responses to hidden fields* (i.e.
  not join them at all), or just hide the columns and silently
  drop the cell values?
- For the bundle-export side: do we mark hidden fields with a
  pill in the preamble (`field_key (hidden)`)?

### Part 2 — Drop the stale "Visible checkbox" line from `spec/instruments.md`

The Band 3 column table currently lists `Visible | yes
(checkbox) | "visible". Reviewer surface only shows visible=True
rows.` That row should rewrite to point at the Band 2 chip as
the source of truth, with cross-reference to Band 2's
`response_fields` pill loop. Two sentences max — this is doc
hygiene, not a behaviour change.

Also confirm the spec's "Visible" prose elsewhere (line ~574 mentions
`accepting_responses` / `responses_visible_when_closed` but the
per-RF flag should be called out alongside Band 2 pill
semantics).

### Part 3 — Policy for hidden-with-saved-responses

Today the model permits an operator to toggle a Band 2 chip off
mid-session **even if responses already exist**. The reviewer
loses the column; the values stay in the DB. Open questions:

1. Should the operator UX warn before un-pinning a chip whose
   field already has saved responses, the way the Band 3
   `data_type` / bounds locks do for `rf.has_responses`?
2. Should the reviewer surface render a banner ("This instrument
   was changed by the operator — N of your answers are no longer
   collected") when the reviewer next loads the form after a
   visible-flag flip?
3. What does the operator's "Replicate this instrument" do with
   hidden RFs — clone them as hidden? (Today: `_instrument_crud.py`
   replicate path copies `visible` as-is. Likely fine but worth a
   one-line confirmation.)

Default recommendation pending discussion: **(1) yes —
confirm-style guard on un-pinning a chip with responses; (2)
no banner — the values are preserved and the operator owns the
change; (3) confirm current replicate semantics with a test.**

### Part 4 — Reviewer summary cross-instrument coverage

Edge cases to lock down via integration tests on the summary
view:

- Visible RF appears on summary HTML and CSV.
- Hidden RF does **not** appear on summary HTML or
  reviewer-record CSV; the data row no longer references it.
- Operator toggles a Band 2 response chip off **after**
  reviewer has submitted: column drops, but the reviewer's
  `pill_state` stays `submitted` (no recall trigger) — the
  reviewer is still "done".
- Operator toggles a Band 2 response chip **back on**: the
  preserved value rehydrates into the summary column. Saved
  in the DB, never lost.
- Group-scoped instruments: same visibility rule applies; the
  group-fan-out invariant carries through.

Each scenario lands a parametrised test in
`tests/integration/test_reviewer_summary_visibility.py` (new file).

### Part 5 (optional, pilot-feedback contingent) — UI affordance for "show hidden fields" on summary

Out of scope for the initial cut. If pilot operators flag the
silent drop as confusing, a Band 2 "Show hidden response columns"
toggle on the summary page (operator preview only — reviewers
never see hidden columns) would be a follow-up.

## Out of scope

- Changes to `Instrument.accepting_responses` /
  `Instrument.responses_visible_when_closed` semantics. The
  per-instrument visibility story is already complete (rows 7–13
  of the visibility audit matrix).
- Changes to `InstrumentDisplayField.visible`. The Band 2
  pill-driven display-field visibility is wired correctly on
  both surface and summary (`_surface.py:375` /
  `_reviewer_summary.py:219`).
- New affordances on the reviewer surface itself. The surface
  already does the right thing — this segment is about the
  surfaces *adjacent* to it (summary HTML + CSV) and the
  operator-side guard rails.

## Risk notes

- The summary HTML + CSV filter changes are small and local but
  do touch a path the reviewer downloads as part of their record.
  Confirm that **already-shipped responses on now-hidden fields
  remain in the DB** — we suppress visibility, not data.
- The operator-side confirm-before-hiding guard (Part 3) is the
  riskiest piece because it changes the chip click contract.
  Land it as its own PR with a clear test for both paths
  (responses present / responses absent).
- Bundle-export semantics (Part 1, CSV branch) intersect with
  operator audit expectations. Default to **include hidden
  fields with a marker** in the operator-bundle path unless the
  human author says otherwise.

## Sequencing

Suggested PR sequence, each a small reviewable slice:

1. **PR 1** — Summary HTML filters response fields by `visible`.
   New integration test file covering the basic visible /
   hidden / round-trip cases. (Part 1 HTML half + Part 4 first
   three scenarios.)
2. **PR 2** — Reviewer-record CSV filters response fields by
   `visible`. Mirrors the HTML test cases against the CSV
   serializer. (Part 1 CSV half + Part 4 remaining scenarios.)
3. **PR 3** — `spec/instruments.md` Band 3 column-table fix +
   cross-references. Pure doc. (Part 2.)
4. **PR 4** — Operator-side confirm guard on un-pinning a Band 2
   response chip that has saved responses. (Part 3 item 1.)
5. **PR 5** — Replicate-semantics test. (Part 3 item 3.) Likely
   a no-op behaviour change — the test pins current behaviour.

Parts 3.2 ("banner on the reviewer surface") and 5 ("show
hidden fields on summary") stay out of the initial cut; carve
to `deferred_until_pilot_feedback.md` if they're not chosen.

## Cross-refs

- `guide/visibility_audit.md` — per-route × per-state visibility
  matrix (the master reference for what this segment is closing
  the per-field tail of).
- `spec/instruments.md` Band 3 + Band 2 sections — the spec
  this segment patches in Part 2.
- `app/web/views/_reviewer_summary.py` — the file Part 1 HTML
  modifies.
- `app/services/extracts/responses_extract.py` — the file Part 1
  CSV modifies.
- `app/services/instruments/_instrument_crud.py:1422` — where
  `InstrumentResponseField.visible` is written from Band 2's
  pill "selected" state.
- `app/web/routes_reviewer/_surface.py:364` — the canonical
  filter the other surfaces should match.
