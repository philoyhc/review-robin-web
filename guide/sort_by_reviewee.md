# Sort by Reviewee — functional spec

**Status.** Forward-looking design spec for **Segment 13B**
(reviewer-surface sort UX, split out of the original Segment 13
during the 2026-05-07 wrap-up). Locks in the decisions reached
during the Segment 11 §2.6 discussion (2026-05-03); promoted
from sketch. The sibling rule-builder work lives in **Segment
13A** (`guide/segment_13A_rulebased_assignment_builder.md`); the
two are independent.

This file is the source of truth for the design. Segment 13B
work implements against it; subsequent edits go here and
propagate to the implementation, not the other way around.

---

## Rationale

The reviewer surface renders one row per assignment per instrument. Today the row order is **implicit insertion order** — whatever the assignments service produced. The operator has no way to set a deliberate default, and the reviewer has no way to re-sort during their working flow.

Two distinct needs:

- **Operator side:** "Sort by cohort, then by name" before the reviewer ever sees the form. A deliberate default that frames the work the way the operator wants the reviewer to encounter it.
- **Reviewer side:** "Let me sort by my own scores so I can see what I rated high." Live, working-flow ergonomics during the review.

Sort is **row sorting**, distinct from **Order** (column ordering on the same surface). Order is already shipped via ▲/▼ buttons. The two are independent: the operator sets columns left-to-right via Order, and rows top-to-bottom via Sort.

---

## Scope: Display Fields only on the operator side

The operator's default sort is restricted to **Display Fields** — reviewee attributes that exist at form-render time (name, email, profile_link, tag_1/2/3, pair_context_1/2/3).

**Response Fields are excluded** from the operator-side sort. No response data exists when the form first renders, so sorting by it would produce empty-cell sorts that shuffle as the reviewer types — surprising and useless.

The reviewer-side override at view time spans **both display and response fields** — once the reviewer has data, sorting by their own ratings is natural.

---

## Operator UI: a "Sort" column on the Display Fields table

### Single column, no new card

A new **Sort** column joins the existing per-row controls (Friendly Label, Visible, Order ▲/▼) on the per-instrument card's Display Fields table. **No new card, no separate sort-builder dialog.** Existing Save/Edit locked state machine governs interaction — Sort cells are interactive when the card is unlocked, read-only when locked.

This is a deliberate constraint. Adding a separate sort-builder card would proliferate the per-instrument surface. The Sort column lives next to Order on the same row because the two ideas are siblings (column-ordering vs row-ordering of the same data).

### Click semantics: tri-state with priority

Each row's Sort cell is a tri-state widget:

| State | Render | Meaning |
|---|---|---|
| **Empty** | `☐` | This field is not part of the sort spec. |
| **Priority N ascending** | `N↑` | This field is the Nth sort key, ascending. |
| **Priority N descending** | `N↓` | This field is the Nth sort key, descending. |
| **Disabled** | `☐` greyed | Three priorities are already assigned and this row isn't one of them. |

Transitions on click:

- Empty → `N↑`, where `N` is the next free priority slot (1, 2, or 3).
- `N↑` → `N↓`.
- `N↓` → Empty. **Other slots auto-compact** — if "2" is removed, the existing "3" becomes "2". This keeps priority numbers contiguous so the operator never has to think about "wait, where did 2 go?"
- Empty (when 3 already assigned) → no-op (cell renders disabled).

The widget is server-rendered for read state; the unlocked-state interactions are JS-driven. The operator's live state is `[(display_field_id, dir), ...]` in click order; on Save the form serializes the same list.

### Visual mock

```
| Source              | Friendly Label | Visible | Order | Sort         |
|---------------------|----------------|---------|-------|--------------|
| reviewee.name       | Name           |   ✓     |  ▲▼  | 1↑           |
| reviewee.email      | Email          |   ✓     |  ▲▼  | 3↓           |
| reviewee.tag_1      | Cohort         |   ✓     |  ▲▼  | 2↑           |
| reviewee.tag_2      | (—)            |         |  ▲▼  | ☐            |
| reviewee.profile... | Photo          |   ✓     |  ▲▼  | ☐ (disabled) |
```

In this state: rows would render on the reviewer surface sorted by Name (ascending) → Cohort (ascending) → Email (descending).

### Locked / unlocked

Same as the rest of the Display Fields card:

- **Locked (default):** Sort cells render their current state in plain text; not clickable.
- **Unlocked (Edit clicked):** Sort cells become interactive per the click semantics above.
- **Save:** persists the sort spec; emits audit event; lifecycle-invalidates `validated → draft`.
- **Cancel:** discards uncommitted Sort changes alongside other discarded edits.

---

## Reviewer UI: clickable column headers, live-only override

The reviewer surface table renders by default with the operator's configured sort applied. The reviewer can override at view time by clicking column headers:

- **Click empty header** → ascending sort by that column.
- **Click ascending header** → descending.
- **Click descending header** → remove from sort spec (revert to operator default for that column's slot).
- **Shift-click** → add as secondary (subsequent shift-clicks add tertiary).
- **Reset link** → snap back to operator's full sort spec.

The reviewer's override **spans both display and response columns**. Sort by display field is a read on existing reviewee data; sort by response field is a read on the reviewer's own response values (their `100int` rating, their `Yes_no` choice, etc.).

**Persistence: live only.** No localStorage, no server-side per-reviewer state. Refresh returns to operator default. This is deliberate — keeps the state model simple and avoids the "I sorted then refresh and lost it / kept it / synced to my other device" question. If a pilot operator asks for persistence, it can be revisited.

---

## Storage

New JSON column on `Instrument`:

```python
sort_display_fields: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
```

Shape:

```json
[
  {"display_field_id": 5,  "dir": "asc"},
  {"display_field_id": 12, "dir": "asc"},
  {"display_field_id": 7,  "dir": "desc"}
]
```

- Up to 3 entries; service-enforced (DB doesn't enforce a length cap).
- `dir ∈ {"asc", "desc"}` — service validates.
- `display_field_id` references `instrument_display_fields(id)` — service validates the id belongs to this instrument.
- Empty list `[]` or NULL → fall back to **implicit insertion order** (today's behaviour, zero change for existing sessions).

JSON over three explicit FK columns: simpler schema, easier to extend to 4+ slots later if it ever matters, and the FK-orphan risk is small (handled by render-time defense + auto-compact on next save). See "Cascade behaviour" below.

---

## Cascade behaviour

When a Display Field is deleted (cascade from instrument or per-row delete):

- **Render-time defense:** the reviewer-surface sort code skips any `sort_display_fields` entry whose `display_field_id` no longer exists. Render falls back to the next-priority slot, then to insertion order.
- **Auto-compact on next save:** when the operator next saves the instrument card, the service drops any stale references and re-numbers the remaining priorities to be contiguous. Audit event captures the cleanup as part of the same `instrument.sort_fields_updated` diff.

No explicit FK / cascade migration is needed. The defense is one if-statement at render and a service-side filter at save.

---

## Default state and migrations

- New column added via Alembic migration with a NULL default.
- Backfill is a no-op — every existing instrument starts with `sort_display_fields = NULL`, which renders as today's implicit insertion order.
- New instruments default to NULL.

Zero behaviour change for any existing session until an operator explicitly configures sort.

---

## Audit event

`instrument.sort_fields_updated` with detail:

```json
{
  "before": [
    {"display_field_id": 5, "dir": "asc"}
  ],
  "after": [
    {"display_field_id": 5, "dir": "asc"},
    {"display_field_id": 7, "dir": "desc"}
  ],
  "diff": {
    "added":   [{"display_field_id": 7, "dir": "desc", "position": 2}],
    "removed": [],
    "reordered": []
  }
}
```

Mirrors the existing `instrument.display_fields_saved` D11 diff shape. The `before` / `after` snapshots are explicit (not derivable from the diff alone) so the audit row stands on its own without requiring a join to the previous event.

---

## Lifecycle behaviour

Sort config edits **invalidate `validated → draft`** via `lifecycle.invalidate_if_validated()`, mirroring every other instrument-mutating service per item #3. Setting a sort doesn't change assignment data, but it changes the reviewer-facing form render, which the validation snapshot covers.

The instrument's `is_ready` lock applies — when the session is `ready`, Sort cells render locked alongside the rest of the Display Fields card, and the operator must Revert to draft to change them (same yellow lock card pattern as elsewhere).

Reviewer-side override is view-only and never invalidates anything.

---

## Multi-instrument sessions

Each instrument has its own `sort_display_fields` spec, independent of other instruments. A reviewer with assignments across two instruments sees each instrument's table sorted by that instrument's own configuration.

The Display Fields available to sort are scoped to the instrument's own display fields — the operator can't reference another instrument's display field as a sort key.

---

## Out of scope for the initial slice

- Sort by **Response Fields** on the operator side. Excluded by design (see "Scope" above).
- **Persistence** of reviewer-side override across sessions or refreshes. Live-only by design.
- **Multi-column sort beyond 3.** Diminishing returns; the catalog can re-open the cap if a real session needs it.
- A separate **sort-builder card or dialog**. The design constraint is "no new card; one Sort column on the Display Fields table."
- Sort by **computed values** (e.g., per-reviewer "completion %"). Display fields and response fields only.
- Sort **across instruments** (e.g., a session-wide sort applied to every instrument). Each instrument is independent by design.
- Mass operator UI for "apply this sort to every instrument" (could be added later as a bulk action).

---

## Implementation pointers (for Segment 13)

These are notes for whoever picks this up; the spec above is the contract.

- **Schema migration:** add `sort_display_fields` JSON column to `instruments` table. NULL default. One-line Alembic migration.
- **Service:** new `instruments.set_sort_display_fields(db, *, instrument, fields, user, correlation_id)` taking a list of `(display_field_id, dir)` tuples. Validates: max 3 entries, ids belong to this instrument, dir in `{asc, desc}`. Lifecycle-invalidates. Emits `instrument.sort_fields_updated`.
- **Operator template** (`instruments_index.html`): the per-instrument Display Fields table gains a Sort column. Locked-state render is plain text (`1↑`, `2↓`, ☐). Unlocked-state interaction is JS-driven over hidden form inputs — same pattern as the existing JS-deferred Add Row / Delete Row mechanics on the same card.
- **Reviewer template** (`review_surface.html`): server-side default sort applied to assignment iteration per instrument. Header rows gain JS click handlers for live override.
- **Reviewer-side JS:** small inline script (~50 lines) tracking sort state in memory, re-sorting the visible rows via DOM reorder, attaching to header clicks. No localStorage. Reset link clears state.
- **Tests:**
  - Unit (`tests/unit/test_instruments_service.py`): `set_sort_display_fields` validates max 3, rejects unknown ids, rejects ids from other instruments, emits correct audit detail, lifecycle-invalidates.
  - Integration: operator sets sort via instruments-page form, save, render reviewer surface, verify row order matches.
  - Integration: cascade-clean — delete a sort-referenced display field, save instrument, verify the sort spec auto-compacts.
  - Render: reviewer-side override JS reorders visible rows; reset link returns to default. (Probably JS-via-Selenium; if too costly for this segment, defer to a follow-on PR with explicit deferral note.)
- **Spec cross-ref updates:** when this lands, update `spec/operator_ui_concept.md` Display Fields section to describe the Sort column; update `spec/reviewer-surface.md` to describe the header-click override.

---

## Doc cross-references

- **`spec/operator_ui_concept.md`** — per-instrument Display Fields card layout. The Sort column lands here when implemented.
- **`spec/reviewer-surface.md`** — review surface table. The header-click override lands here when implemented.
- **`spec/quick_setup_card_spec.md`** — adjacent operator-card design pattern (single source of truth for an operator-side feature spec).
- **`guide/segment_13_rulebased_assignment_builder_plan.md`** — the segment plan that picks this up.
- **`guide/unfinished_business.md`** — catalog stub pointing here.
- **`docs/status.md`** "What's deliberately not yet there" — entry pointing here, target Segment 13.
