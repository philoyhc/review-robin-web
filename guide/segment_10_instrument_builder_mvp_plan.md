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
