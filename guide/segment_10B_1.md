# Segment 10B-1 Implementation Plan — Data-driven reviewer-surface render

**Status:** Stub — decisions locked, slice breakdown still to be drafted.
First of three PR-sized blocks for Segment 10B (display-fields picker
+ operator preview). See `guide/segment_10B.md` for the umbrella stub
that breaks 10B into 10B-1 / 10B-2 / 10B-3, and
`guide/segment_10_instrument_builder_mvp_plan.md` §14 for the
segment-level split. 10B-1 follows 10A (shipped) and precedes 10B-2.

- **10B-1 (this doc):** Alembic backfill migration, `ensure_default_instrument`
  seeding three pair-context rows, reviewer-surface refactor to render
  from `InstrumentDisplayField` (replacing hard-coded `pair_context_*`),
  reviewee identity column wiring, default-label inference. **Ships
  behavior-preserving** — no operator UI yet.
- **10B-2 (next):** display-field picker UI on the per-instrument card
  (row-level add / edit / delete POSTs + shared bulk "field order &
  visibility" form), invalidation + locked-when-ready gating, the four
  new audit events.
- **10B-3 (last):** `GET /operator/sessions/{id}/preview` with synthetic
  rows, disabled inputs, banner.

---

## 10B-1 outcome

One PR that ships:

- One Alembic revision that backfills three `InstrumentDisplayField`
  rows per existing instrument (`pair_context_1/2/3`), and updates
  `ensure_default_instrument` to seed the same three rows on every
  newly created instrument.
- The reviewer surface (`reviewer/review_surface.html`) refactored to
  loop over each instrument's `InstrumentDisplayField` rows in their
  stored order, with the reviewee identity column always rendered as
  the fixed first column.
- A small label-inference helper used by the renderer when an
  `InstrumentDisplayField.label` is NULL or empty.

Behavior unchanged otherwise: no operator-facing UI for managing
display fields yet (10B-2), no preview route yet (10B-3). On every
existing session, reviewers see the same three columns in the same
order they see today; the change is purely how those columns are
sourced.

---

## Decisions locked for 10B-1

### D2 — Backfill migration scope

Single Alembic revision. For every existing instrument, write three
`InstrumentDisplayField` rows for `pair_context_1/2/3`
(`source_type="pair_context"`, `source_field="1"|"2"|"3"`,
`visible=true`, `order=0..2`, `label=NULL`) **unconditionally** —
including instruments that already carry display-field rows. Picks
option (b) from the original 10B open question:
destructive-but-consistent.

`ensure_default_instrument` updates to seed the same three rows on
every newly created instrument.

No new columns on `instrument_display_fields` — the existing schema
(`label`, `source_type`, `source_field`, `order`, `visible`) is
already sufficient.

### D4 — Reviewee identity column is fixed

Always-first column on the reviewer surface: reviewee `name`
(primary) with `email_or_identifier` beneath in smaller font, same
cell. **Mandatory.** Not represented by an `InstrumentDisplayField`
row, not toggleable, not reorderable. Renderer hard-codes this
column ahead of the display-field loop.

### D6 — Default labels are inferred

When a display field's `label` is NULL or empty, the reviewer
surface column header falls back to an inferred string:

| `source_type` | `source_field` | Inferred label |
|---|---|---|
| `reviewee` | `tag_1` | "Tag 1" |
| `reviewee` | `tag_2` | "Tag 2" |
| `reviewee` | `tag_3` | "Tag 3" |
| `reviewee` | `profile_link` | "Profile" |
| `pair_context` | `1` | "Pair context 1" |
| `pair_context` | `2` | "Pair context 2" |
| `pair_context` | `3` | "Pair context 3" |

A small helper (e.g. `display_field_label(field)`) does the lookup.
Operator-typed labels are stored verbatim and round-tripped — the
helper only kicks in for NULL / empty.

The four `reviewee` sources are listed here so the helper covers them
end-to-end; only the three `pair_context` sources are seeded by the
backfill in 10B-1, the `reviewee` rows enter via the picker in 10B-2.

### D5 (partial) — Default ordering on a freshly seeded instrument

Display fields first, in slot order — `pair_context_1/2/3` at
`order=0..2`, then response fields at `order=0..N-1` (their existing
seed order). Reviewer-surface columns render left to right as:

1. Reviewee identity (always first; D4).
2. Visible display fields and response fields, **interleaved** by
   merged sort across `(table, order)` pairs.
3. Per-row submitted-status indicator (rightmost; today's behavior).

In 10B-1 there is no operator interleaving — display fields all sort
before response fields by construction (display `order=0..2`,
response `order=0..N-1`, table tiebreaker puts display first). The
bulk form that lets the operator interleave lands in 10B-2; the
renderer in 10B-1 already implements the merged-sort rule so 10B-2
adds zero render-side change.

### D6.1 — `profile_link` rendering

When `source_type="reviewee"` and `source_field="profile_link"`, the
cell renders as a plain `<a>` to the stored URL with the URL as link
text (no truncation, no icon). Empty / NULL values render as an
empty cell.

This is the only display-field source whose cell is not a plain text
escape; locking it in 10B-1 keeps the picker decision in 10B-2 from
having to revisit cell-level rendering.

---

## Audit events added in 10B-1

None. 10B-1 ships data-driven render only; mutations land in 10B-2.

The Alembic backfill itself does not emit application-level audit
events (consistent with prior backfill migrations in this codebase —
e.g. the `Instrument.description` provisioning).

---

## Out of scope for 10B-1 (explicitly deferred)

- Display-field picker UI on the per-instrument card → 10B-2.
- Row-level add / edit / delete POSTs for display fields → 10B-2.
- Shared bulk "field order & visibility" form → 10B-2.
- The four new audit events (`instrument.display_field_added` /
  `_updated` / `_deleted` / `instrument.display_fields_saved`) → 10B-2.
- `_invalidate_if_validated` + `_can_edit_instrument` gating on
  display-field mutations → 10B-2.
- `GET /operator/sessions/{id}/preview` route, synthetic-row helper,
  disabled-inputs render, banner → 10B-3.
- `assignment_context_*` as a display-field source — deliberately
  excluded per 10B D1 (umbrella stub).
- `spec/target_operator_map.md` rewrite → separate post-10B PR per
  10B D12.

---

## To draft next

This stub locks the decisions for 10B-1. The implementation slice
breakdown (parallel to `segment_10A.md` Slices 1–5: migration →
service / renderer → templates → tests) is **not yet drafted** and
is the next deliverable on this branch.
