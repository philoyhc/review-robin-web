# Segment 10 Plan — Instrument Builder MVP

**Project:** Review Robin Web  
**Repository:** <https://github.com/philoyhc/review-robin-web>  
**Segment:** 10 of the low-intensity workplan  
**Purpose:** Let operators rename, edit, add, reorder, and delete response fields on the session's single Default Instrument before activation

---

## 1. Segment goal

Until now, every session has used the auto-created Default
Instrument with two seed response fields: `rating` (integer 1–5,
required) and `comments` (long text, optional). This is fine for
proving out the reviewer surface, but real review cycles need
custom questions: a different rating scale, a "decision" yes/no
field, multiple text prompts.

Segment 10 introduces an operator-facing builder that mutates the
session's Instrument's response fields. Multi-instrument sessions
(more than one Instrument under a session) remain Segment 13;
this segment only touches the single Default Instrument.

By the end of Segment 10, an operator should be able to:

- view the current response fields on a session's Instrument;
- add a new field (key, label, type, required, validation, order);
- edit an existing field's label, required-ness, validation, order;
- reorder fields;
- delete a field, with a cascade warning when saved responses exist;
- rely on the reviewer surface auto-rendering whatever the
  Instrument now contains.

---

## 2. Success criteria

Segment 10 is complete when:

1. An operator has a page at
   `/operator/sessions/{id}/instrument` listing the session's
   Instrument's response fields with current type, required,
   validation, and order.
2. Add-field, edit-field, delete-field, reorder actions are
   functional and audited.
3. Field types `integer` (with min/max), `short_text`, `long_text`,
   and `yes_no` are supported. The reviewer surface renders all
   four correctly.
4. Deleting a field with saved `Response` rows shows a warning
   with the affected count and requires explicit confirm.
5. Field-key uniqueness within an instrument is enforced (already
   in the schema; the builder respects it).
6. New audit event types are written: `instrument.field_added`,
   `instrument.field_updated`, `instrument.field_deleted`,
   `instrument.fields_reordered`.
7. Tests cover the new routes, cascade behaviour, and the reviewer
   surface auto-adapting to a changed field set.

---

## 3. Deliberately out of scope

Do not include:

- multi-instrument sessions (more than one Instrument under a
  session) — that's Segment 13;
- conditional / branching / dependent field logic;
- file-upload or media response types;
- richer validation than `min`/`max` on integers and `required` on
  text;
- migrating existing responses when a field's validation tightens
  (existing values that violate the new rule still display; nothing
  is auto-rejected);
- editing the instrument after activation locks it (Segment 9
  introduces activation; revisit later if needed);
- CSV bulk-edit of fields. The form-driven editor suffices for the
  small field counts realistic in this segment.

---

## 4. Branch strategy

Single PR against `main`:

```bash
git checkout -b claude/segment-10-instrument-builder
```

Suggested PR title:

```text
Segment 10: Add instrument builder MVP
```

Estimated size: ~700–900 LOC including tests. Tightly coupled —
splitting routes from cascades from tests just produces awkward
partial states.

---

## 5. Operator surface

A new page at `/operator/sessions/{id}/instrument` (singular: the
Default Instrument until Segment 13). Renders:

- the Instrument's current name (operator-editable);
- a table of response fields with columns Key, Label, Type,
  Required, Validation, Order, Actions (edit / delete);
- an Add field form below the table;
- a small Reorder control (up/down arrows, or drag handle if easy).

A new section on the existing session detail page links to the
builder.

---

## 6. Schema considerations

The schema already supports everything this segment needs:

- `instruments` table for the Instrument row.
- `instrument_response_fields` table with `field_key`, `label`,
  `response_type`, `required`, `order`, `validation` JSON.
- Unique constraint `(instrument_id, field_key)`.
- `responses` cascade-on-delete from `response_field_id`, so
  deleting a field automatically removes saved responses for it.

No migration needed for Segment 10. Schema changes are deferred to
Segment 13 where multi-instrument may grow new columns on
`instruments`.

---

## 7. Decisions to lock in 10A

These are the design decisions worth confirming before
implementation:

### 7.1 Field-key mutability

Once a field is saved, its `field_key` is **immutable** — the
edit form does not expose it. Renaming would break downstream
exports keyed by field key, and add no real user value (the
operator can always delete and re-add). The user-facing label is
freely editable.

### 7.2 Required toggle on a populated field

Optional → required is allowed at any time, and on save the
operator sees a warning listing how many existing reviewer rows
now have at least one missing required answer (because some
reviewers had left the previously-optional field blank).
Required → optional is unconditional.

### 7.3 Order reassignment

`order` integer column already exists. The builder repacks orders
to a contiguous 0..N-1 sequence on every save to keep numbers
small. Reorder UI: per-row up/down buttons that swap the row's
order with its neighbour.

### 7.4 Deleting a field with saved responses

Two-step warn-and-override:

1. `POST /operator/sessions/{id}/instrument/fields/{field_id}/delete`
   without `confirm=true` — re-renders the page with HTTP 400 and
   a warning card listing the count of existing `Response` rows
   for this field.
2. Same POST with `confirm=true` — cascade-deletes the field and
   its responses, audit `instrument.field_deleted` records both
   the field's old config and the deleted-response count.

### 7.5 Field-type support

Four types in v1:

| `response_type` | UI input | Validation |
|---|---|---|
| `integer` | `<input type="number">` | optional `{"min": N, "max": M}` |
| `short_text` | `<input type="text">` | none |
| `long_text` | `<textarea>` | none |
| `yes_no` | `<select>` with options `yes` / `no` | none |

Adding new types in later segments only requires a template
update to the reviewer surface and a new validation block.

### 7.6 Scope of the builder vs activation

The builder is operator-only. Once Segment 9's activation lands,
activation **locks the instrument** — no add / edit / delete /
reorder while the session is active. Re-opening a session
(allowed only as an admin escape today) re-enables the builder.
The builder route returns 409 when the instrument is locked.

### 7.7 Default seed fields

`ensure_default_instrument` already seeds `rating` + `comments`.
Operators can edit / delete those just like any other field.
Deleting all fields is allowed — the session would simply have an
Instrument with no questions until the operator adds one. The
reviewer surface gracefully renders the empty-instrument case
(no inputs; status remains "not started" trivially).

---

## 8. Audit event shapes

```python
AuditEvent(
    event_type="instrument.field_added",
    summary=f"Added field '{label}' ({field_key}) to instrument {instrument_name}",
    detail={
        "instrument_id": ...,
        "session_id": ...,
        "field_key": ...,
        "label": ...,
        "response_type": ...,
        "required": ...,
        "validation": ...,
    },
)

AuditEvent(
    event_type="instrument.field_updated",
    summary=f"Updated field '{label}' on instrument {instrument_name}",
    detail={
        "instrument_id": ...,
        "session_id": ...,
        "field_key": ...,
        "changes": {"label": [old, new], "required": [True, False], ...},
    },
)

AuditEvent(
    event_type="instrument.field_deleted",
    summary=f"Deleted field '{label}' from instrument {instrument_name}",
    detail={
        "instrument_id": ...,
        "session_id": ...,
        "field_key": ...,
        "snapshot": {...},  # the field's full config before delete
        "cascaded_response_count": N,
    },
)

AuditEvent(
    event_type="instrument.fields_reordered",
    summary=f"Reordered fields on instrument {instrument_name}",
    detail={
        "instrument_id": ...,
        "session_id": ...,
        "old_order": [...field_keys...],
        "new_order": [...field_keys...],
    },
)
```

---

## 9. Routes

| Method | Path | What it does |
|---|---|---|
| GET | `/operator/sessions/{id}/instrument` | Builder page |
| POST | `/operator/sessions/{id}/instrument/fields` | Add a new field |
| POST | `/operator/sessions/{id}/instrument/fields/{field_id}/edit` | Edit a field |
| POST | `/operator/sessions/{id}/instrument/fields/{field_id}/delete` | Delete a field (confirm checkbox required when responses exist) |
| POST | `/operator/sessions/{id}/instrument/fields/{field_id}/move` | Move a field up or down (form param `direction=up\|down`) |
| POST | `/operator/sessions/{id}/instrument/edit` | Rename the instrument |

All gated on `require_session_operator`. All return 409 when the
instrument is locked (post-activation, once Segment 9 ships).

---

## 10. Tests

Minimum tests, ~15 across unit and integration:

### Unit (`tests/unit/test_instrument_builder.py`)

1. Add field appends and persists with correct order.
2. Add field with duplicate `field_key` → error, no row written.
3. Edit field updates label / required / validation.
4. Edit cannot change `field_key`.
5. Move-up / move-down repacks orders contiguously.
6. Delete field with no responses succeeds.
7. Delete field with responses requires confirm.
8. Delete with confirm cascades to responses (count audited).

### Integration (`tests/integration/test_instrument_builder_routes.py`)

9. GET builder renders current fields.
10. POST add-field creates and redirects.
11. POST edit-field round-trips.
12. POST delete-field without confirm 400s when responses exist.
13. POST delete-field with confirm cascade-deletes.
14. Reviewer surface auto-renders a newly added `yes_no` field.
15. Reviewer surface auto-removes a deleted field.
16. Non-operator user gets 403.
17. (Once Segment 9 lands) Locked instrument returns 409 on every
    mutating route.

---

## 11. Documentation

- `docs/status.md`: add an "Instruments" capability section,
  add the four new audit event types to the audit table, remove
  the "Instrument builder" row from "What's deliberately not yet
  there".
- `ARCHITECTURE.md`: update "When operator-controlled instrument
  editing lands" prose to "Operator-controlled instrument editing
  ships in Segment 10" with a back-reference to this file.
- A `docs/instruments.md` user-facing guide is **not** added in
  this segment. The form labels + the audit log suffice; a real
  guide can land alongside the operator polish segment.

---

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| An operator deletes a field and loses all reviewer responses for it | Two-step warn with the count of affected responses; audit records the snapshot for support to reverse manually. |
| Operator changes integer min/max while existing responses violate the new rule | Existing `Response.value` strings stay as-is; they display, but won't validate on next save. The operator sees a warning when they tighten validation. |
| Operator renames a field's label between save and submit by reviewers | The reviewer's saved `Response` rows are keyed by `response_field_id`, not label, so renaming has no data-correctness impact. The reviewer's next page load just shows the new label. |
| Two operators on the same session edit the instrument concurrently | Last-write-wins per field; for MVP we accept this. Real conflict handling defers to a later segment. |
| A field is deleted between a reviewer's GET surface and POST save | The POST silently drops upserts that target a missing `(assignment, field_id)` pair (already handled in `_apply_upserts`). The reviewer reloads to see the new shape. |

---

## 13. Done when

- Operator can add / edit / delete / reorder response fields on a
  session's Instrument from the operator UI.
- All four supported field types render correctly on the reviewer
  surface without template changes.
- Cascade-delete of responses warns and audits.
- Four new audit event types are written, each with the shape in
  §8.
- All ~15 new tests pass; full suite green.

Next segment after this PR merges: **Segment 11 — Export, audit,
and retention MVP**.

---

## 14. Update (2026-04-30) — split into Segments 10A and 10B

After §1–§13 above were drafted, additional decisions emerged that
broaden Segment 10's scope beyond what fits in a single PR. Segment
10 is now split into two PR-sized blocks. **Detailed slice plans
(`guide/segment_10A.md`, `guide/segment_10B.md`) are not yet
drafted.** This section captures the segment-level split and the
locked decisions that supersede parts of §1–§13.

The high-level prose summary already lives in `ARCHITECTURE.md`
under "Conceptual hierarchy → When operator-controlled instrument
editing lands (Segment 10):" (merged in PR #82, 2026-04-30).

### 14.1 Why split

The original §4 estimate of one ~700–900 LOC PR no longer holds.
Locked decisions added:

- **Per-field help text** + visibility — schema migration on
  `instrument_response_fields` (`help_text`, `help_text_visible`).
- **Display-field picker** — operator-configurable choice of
  reviewee tags / pair contexts that appear as columns alongside
  the response fields. Uses the existing `instrument_display_fields`
  table (no new table; one migration to backfill seed rows).
- **Operator preview** — read-only `/operator/sessions/{id}/preview`
  rendering of the reviewer surface.
- **Reviewer-surface refactor** to loop-by-instrument (forward-compat
  for Segment 13 multi-instrument) — section heading + per-field
  help block + table per instrument.
- **Consolidated `/operator/sessions/{id}/instruments` page** —
  subsumes the 9.1 sub-page at `/instruments/{instrument_id}` (no
  separate GET on that URL anymore; action POSTs keep
  `{instrument_id}` in their path).
- **Global CSS width bump** from 900px to 1400px in `base.html`
  with a `.table-scroll` overflow utility for ultra-wide tables.

Two PRs, not one.

### 14.2 Segment 10A — Response-field builder + reviewer-surface refactor

**Goal.** Operator can add / edit / delete / reorder response fields
on the session's single instrument, set per-field help text + its
visibility, and edit a friendly description for the instrument.
Reviewer surface refactors to loop-by-instrument (N=1 today) with
section heading + per-field help block + table.

**Scope.**
- Alembic migration: add `help_text` (Text, NULL) and
  `help_text_visible` (Bool, default `true`) to
  `instrument_response_fields`.
- Consolidated `/operator/sessions/{id}/instruments` page —
  per-instrument card carrying friendly description, accepting /
  visibility toggles (existing 9.1 behaviours), fields table,
  add-field form, per-row edit / delete / reorder controls.
- Action routes:
  - `POST /operator/sessions/{id}/instruments/{instrument_id}/edit`
    — edit description (system `name` is immutable).
  - `POST /operator/sessions/{id}/instruments/{instrument_id}/fields`
    — add field.
  - `POST .../fields/{field_id}/edit` — edit field.
  - `POST .../fields/{field_id}/delete` — delete (warn-and-confirm
    when responses exist).
  - `POST .../fields/{field_id}/move` — reorder up / down.
  - Existing 9.1 POSTs (`open` / `close` / `visibility`) keep their
    URL but redirect to `/instruments` instead of the now-removed
    sub-page.
- `GET /operator/sessions/{id}/instruments/{instrument_id}` — 303
  to `/instruments` for backward compat with bookmarks.
- Audit events: `instrument.field_added`, `instrument.field_updated`,
  `instrument.field_deleted`, `instrument.fields_reordered`,
  `instrument.described`. All field mutations + `instrument.described`
  invalidate `validated → draft` via the existing
  `_invalidate_if_validated` helper. (Open / close / visibility do
  **not** invalidate, matching 9.5A's existing carve-out.)
- Reviewer-surface refactor: loop over instruments (today: N=1),
  render section heading from `Instrument.description` (fallback to
  system `name`), help block above table listing each response
  field where `help_text` is non-empty AND `help_text_visible` is
  true, then the response table.
- CSS: `body { max-width: 1400px }` globally in
  `app/web/templates/base.html`; add `.table-scroll { overflow-x:
  auto }` utility class.

**Out of scope (deferred to 10B).**
- Display-field picker UI and any change to
  `instrument_display_fields`.
- `pair_context_1/2/3` rendering on the reviewer surface stays
  hard-coded (just hoisted into the per-instrument loop) until 10B
  switches it to `InstrumentDisplayField`-driven.
- Operator preview route.

**Deliverable shape.** One PR, ~1000–1100 LOC including tests
(~15–20 covering routes, audit, reviewer-surface help block,
locked-when-ready 409, validated invalidation, required-toggle
banner, width-bump non-regression).

### 14.3 Segment 10B — Display-field picker + operator preview

**Goal.** Operator can choose which reviewee tags / pair contexts
appear as columns on the reviewer surface alongside the response
fields, and preview what reviewers will see before activation.

**Scope.**
- Alembic migration: backfill `InstrumentDisplayField` rows for
  `pair_context_1/2/3` (visible=true, order 1..3) on every
  existing instrument. Update `ensure_default_instrument` to seed
  them on new sessions.
- Per-instrument card on `/instruments` extends with a display-field
  picker section: the available sources are reviewee `tag1` /
  `tag2` / `tag3` / `photo_link` and `pair_context_1` / `2` / `3`.
  `assignment_context_*` is deliberately excluded (preserves the
  reviewer-facing / logic-engaging distinction; see ARCHITECTURE.md
  "Pair-level vs assignment-level context").
- Bulk-save action `POST .../instruments/{instrument_id}/display-
  fields/save` replaces the instrument's display-field set in one
  transaction. Visibility toggle, optional label override, and
  reorder are part of the same form.
- Reviewer surface: replace the hard-coded `pair_context_*`
  rendering with `InstrumentDisplayField`-driven render. Reviewee
  identity stays as a fixed first column (name + email beneath in
  smaller font, same cell — matching the current screenshot
  evidence).
- New route `GET /operator/sessions/{id}/preview` — read-only
  render of the reviewer surface with a "Preview — not visible to
  reviewers" banner. Uses real assignments if any; falls back to
  one synthetic placeholder row when zero. All inputs disabled /
  static; no save / submit / clear forms reachable.
- Audit events: `instrument.display_fields_saved` (single bulk
  event with old / new comparison). Display-field changes invalidate
  `validated → draft`.

**Out of scope.**
- Multi-instrument session support (Segment 13).
- Operator-driven export of the configured surface (Segment 11).
- Anonymous-preview link or shareable preview URL — preview is
  operator-only.

**Deliverable shape.** One PR, ~700–800 LOC including tests
(~10 covering picker, render, preview, backfill migration,
assignment_context exclusion).

### 14.4 Locked decisions that supersede §1–§13

When the original §1–§13 disagrees with this section, this section
wins. Quick map:

| Original | Supersede |
|---|---|
| §4 Branch strategy: one PR | Two PRs: `claude/segment-10a-…` then `claude/segment-10b-…`. |
| §5 Operator surface: `/operator/sessions/{id}/instrument` (singular) | `/operator/sessions/{id}/instruments` (plural, consolidated; one card per instrument). |
| §6 "No migration needed" | 10A migration adds `help_text` + `help_text_visible`. 10B migration backfills `InstrumentDisplayField` rows. |
| §7.5 Four field types only | Field types unchanged, but each field also carries `help_text` (Text NULL) + `help_text_visible` (Bool default true). |
| §7.6 Lock predicate | Keys on `session.status == ready` today. Predicate written as `_can_edit_instrument(instrument, session)` so Segment 13 can refine to per-instrument keying. |
| §7.7 Default seed fields, instrument named "Default" | System `name` is `instrument_1` (etc.), immutable. Existing rows keep their `"Default"` value (code-only change, no rename migration). Operator-editable friendly text moves to `Instrument.description`. |
| §9 Routes — singular `/instrument` | All routes consolidated under `/instruments/{instrument_id}/...` for actions; single GET at `/instruments`. Old `GET /instruments/{instrument_id}` 303s to `/instruments`. |
| §8 Audit event shapes | Add `instrument.described` (description edit). 10B adds `instrument.display_fields_saved`. |
| §10 Tests (~15 in one PR) | Split: 10A ~15–20, 10B ~10. |
| §11 Documentation | `docs/status.md` updated at end of 10A, again at end of 10B. `ARCHITECTURE.md` already updated (PR #82). `spec/target_operator_map.md` needs an update to reflect the consolidated `/instruments` page (its current text describes a separate `/instruments/{instrument_id}` page). |

### 14.5 Recommended sequencing

1. **10A** — schema migration, builder, reviewer-surface refactor,
   CSS width bump. Lands first because it owns the `help_text`
   migration and the reviewer-surface loop refactor that 10B
   extends.
2. **10B** — display-field picker, preview. Builds on 10A's
   per-instrument card and reviewer-surface loop.

10B cannot land before 10A: the display-field picker UI lives on
10A's per-instrument card, and the preview route renders 10A's
reviewer surface.

### 14.6 Cross-references

- `ARCHITECTURE.md` "Conceptual hierarchy" — operator-controlled
  instrument editing prose (PR #82, 2026-04-30).
- `ARCHITECTURE.md` "Tabular response artifacts" — within-instrument
  vs across-instrument framing for the reviewer surface.
- `guide/segment_09_invitation_monitoring_reminder_split_plan.md` —
  Segment 9's split-plan, the structural precedent for this update.
- `guide/segment_10A.md`, `guide/segment_10B.md` — detailed slice
  plans, **not yet drafted**.
- `spec/target_operator_map.md` — needs an update to reflect the
  consolidated `/instruments` page (deferred until 10A lands).

## 15. Follow-up: Reviewer/Reviewee CSV cross-table identity check

Tighten the upload validators in `app/services/csv_imports.py` so
that **email is the unique person-identifier across both reviewer
and reviewee tables in the same session**, while name is treated
purely as the human-facing label.

Rules to enforce on upload:

- Every row must have non-empty Name and Email (already
  enforced).
- Within the uploaded CSV, the same email may not appear with
  different names → error. (Same email + same name still
  collapses to a duplicate-row error as today.)
- **Cross-table:** when uploading reviewers, look up each row's
  email in the existing reviewees of the same session — if found
  with a *different* name, error. Same name = allow (the person
  is both reviewer and reviewee, common in peer review). Vice
  versa for reviewee uploads.
- The same name may appear with multiple distinct emails — no
  uniqueness on name.

Out of scope here but adjacent: assignments-CSV emails imply a
person; same cross-table consistency could be checked there in a
later pass.

Lands as a small slice on top of the current validators; new
tests cover the four cases (intra-CSV same name + same email,
intra-CSV same email + different name, cross-table same email +
same name, cross-table same email + different name).
