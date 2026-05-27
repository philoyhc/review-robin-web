# Segment 18K — Completing instrument visibility (Band 3) on the reviewer surface

> **Status: in flight.** Stub created 2026-05-27; Parts 1+2
> shipped same day (PR #1487). Part 3 policy choices confirmed
> 2026-05-27 — Parts 4–6 below cover the operator-side confirm
> guard, the reviewer-surface banner, and the replicate test
> respectively. Part 5 ("show hidden fields on summary") retired
> by policy — hidden = gone, internally preserved for audit.
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

### Part 1 — Filter response fields by `visible` on the reviewer summary — shipped 2026-05-27

**Shipped.** `_reviewer_summary.py` filters
`instrument.response_fields` by `f.visible` when composing
`field_cols`; the cell-index lookups gracefully ignore the now-
unreferenced response rows.
`serialize_reviewer_session_summary` in `responses_extract.py`
mirrors the same filter on the preamble walk and the data-row
query (an explicit `.where(InstrumentResponseField.visible.is_(True))`
on the response select). Both surfaces now match
`routes_reviewer/_surface.py`'s long-standing filter.

The operator-side bundle export
(`serialize_responses` / `serialize_responses_for_instrument`)
is untouched — operators get the full audit view; only the
**reviewer-record** path filters.

Pinned by `tests/integration/test_reviewer_summary_visibility.py`:
hidden field absent from HTML + CSV; visible field present;
toggle-back rehydrates the column (responses survive in the
DB through visibility flips).

### Part 2 — Rewrite "Band 3 — Response fields" in `spec/instruments.md` to match the codebase — shipped 2026-05-27

**Shipped.** The Band 3 section in `spec/instruments.md` is
rewritten to describe the **actual** inline row layout
(Name input, Type select with quick-fill List presets, inline
Bounds, R / ≡ / ✓ / X buttons) instead of the obsolete table
shape (no Order drag handle on Band 3, no per-row Visible
checkbox, no per-row Label / Help-text columns). A new
sub-section "Per-field visibility lives on the Band 2 pill"
pins where `InstrumentResponseField.visible` is actually
toggled and which surfaces filter on it.

### Part 3 — Policy for hidden-with-saved-responses

Today the model permits an operator to toggle a Band 2 chip off
mid-session **even if responses already exist**. The reviewer
loses the column; the values stay in the DB.

**Decisions (confirmed 2026-05-27).** All three open questions
land **yes**:

1. **Yes — confirm-style guard on un-pinning a Band 2 response
   chip whose field has saved responses.** Mirrors the existing
   Band 3 `data_type` / bounds locks for `rf.has_responses`. The
   confirm() message names the field and how many responses are
   currently visible to reviewers, so the operator can't silently
   strand answered fields.
2. **Yes — reviewer surface banner on next load after a
   visible-flag flip.** When a reviewer's saved response on
   `field` is no longer collected (because the operator hid the
   field), the next reviewer-side GET surfaces a one-line banner
   listing the dropped field(s). No action required — informational
   only. (The reviewer's previously saved answer is preserved
   internally for audit per Part 5 below; the banner just makes
   the disappearance visible.)
3. **Yes — Replicate copies `visible` as-is.** Current behaviour
   in `_instrument_crud.py` already does this; the segment lands a
   test pinning it. A cloned card inherits its source's per-field
   visibility unchanged.

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

### Part 5 — Hidden = gone, internally preserved for audit

**Decision (confirmed 2026-05-27).** No follow-on "show hidden
fields on summary" affordance. The reviewer-facing contract is
that **a hidden field is gone**: it disappears from every
reviewer-facing render (form, summary HTML, reviewer-record
CSV) and the reviewer has no way to surface it. The underlying
`Response` rows stay in the DB so the operator-side audit /
bundle export retains the full history — that's the "internally
preserved for audit" half.

This pins the operator's mental model: un-pinning a chip is
**not** a "soft hide" the reviewer might still discover; it's a
hard drop from the reviewer's view, with the audit trail intact.

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

PR sequence, each a small reviewable slice. **PRs 1–3 shipped
2026-05-27** (commits / PR list captured in the per-Part
status lines above).

1. **PR 1 — shipped (#1487).** Summary HTML + reviewer-record CSV
   filter response fields by `visible`; new integration test
   file (`tests/integration/test_reviewer_summary_visibility.py`)
   pins visible / hidden / round-trip across both surfaces.
   (Part 1 + Part 4 first three scenarios.)
2. **PR 2 — shipped (folded into #1487).** CSV branch landed
   in the same PR as the HTML branch — the diff stayed small
   enough that splitting would have been busywork.
3. **PR 3 — shipped (#1487).** `spec/instruments.md` Band 3
   section rewrite + the new "Per-field visibility lives on the
   Band 2 pill" cross-reference subsection. (Part 2.)
4. **PR 4 — pending.** Operator-side confirm guard on un-pinning
   a Band 2 response chip that has saved responses. (Part 3
   item 1.)
5. **PR 5 — pending.** Reviewer-surface banner naming the
   dropped field(s) on the next load after a visible-flag flip.
   (Part 3 item 2.)
6. **PR 6 — pending.** Replicate-semantics test pinning
   `_instrument_crud.py` clone-with-`visible`-as-is behaviour.
   (Part 3 item 3.)

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
