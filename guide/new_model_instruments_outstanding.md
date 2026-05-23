# New-model instruments — outstanding integration

The new-model instrument card (the "Pilot"-flagged flavour
introduced in Segment-equivalent slices via PRs #1336–#1371,
gated on `instruments.is_new_model`) lights up the operator's
design surface for the Instrument Builder concept test. Most of
the card writes through the existing schema; two pieces are
stored as JSON metadata on `instruments.band2_state` instead and
do **not** flow into the assignment engine or the reviewer
surface yet.

This doc lists what's connected today and what would close each
remaining gap, in priority order if/when the operator's choices
need to drive what the reviewer actually sees.

## Where new-model writes flow

| Operator surface | Storage | Read-path |
|---|---|---|
| Identity (name, short label, description) | `instruments.name` / `short_label` / `description` | Reviewer surface heading + setup pages — same as ordinary instruments. |
| Band 1 Link 1 + Link 2 (assignment rules) | `session_rule_sets.rules_json` via `instruments.rule_set_id` | Assignment engine (`app/services/rules/engine.py`) — same as ordinary instruments. |
| Band 1 Link 3 (unit of review) | `instruments.group_kind` | Reviewer surface group-row composition + the rule engine's group-pair-count cache — same as group-scoped instruments. |
| Band 2 column widths | `instruments.column_widths` JSON | Reviewer surface table renders `<col>` widths + opts into `table-layout: fixed` when any width is set. |
| Band 2 display-field order | `instrument_display_fields.order` | Reviewer surface column order + Setup-page display fields list — same as ordinary instruments. |

## Where new-model writes are JSON-only

These pieces persist on `instruments.band2_state` but don't
update the existing schema rows the reviewer surface + assignment
engine actually consume.

### 1. Pill selection (which display columns appear)

**What the operator sees.** Clicking a pill in Band 2's pill row
adds the corresponding column to the preview table inside the
new-model card.

**What persists.** The pill's canonical key
(`reviewee.name`, `reviewee.tag_1`, etc.) is added to
`band2_state.selected_display_keys`. The corresponding
`InstrumentDisplayField.visible` flag is **not** updated.

**Gap.** The reviewer surface filters columns by
`InstrumentDisplayField.visible`, not by the pill selection. So
the operator can deselect a pill in the preview but the
reviewer still sees that column.

**To close.** On each pill toggle, mirror the selection to the
matching `InstrumentDisplayField.visible` row. The
`set_band2_state` service already validates against
`_BAND2_ALLOWED_DISPLAY_KEYS`; extending it to also call the
existing `instruments_service.set_display_field_visibility`
helper would be the bulk of the work. Edge cases to think
through: locked display fields (Name, Email — already filtered
out of the visibility toggle on the standard surface), and
whether the operator can ever *gain* a column they didn't pre-
select (today they can only see what `display_fields` lists).

### 2. Response fields (the Band 3 Response fields rows)

**What the operator sees.** The "Response fields" right column
of Band 3 lets the operator define rows
(name + data type + bounds), commit them with ✓, and toggle the
resulting pills into the preview.

**What persists.** Each row's `{name, data_type, min, max, step,
list_options, selected}` is appended to
`band2_state.response_fields`. No `InstrumentResponseField` rows
are created; no `ResponseTypeDefinition` rows either.

**Gap.** The reviewer surface renders input controls from
`InstrumentResponseField` rows (each pointing at an RTD that
carries the type + bounds). New-model instruments only have the
default response fields the standard `create_instrument` flow
seeds — the operator's Band 3 entries are invisible to the
reviewer.

**To close.** Significantly bigger work:

- Each Band 3 row needs a real `InstrumentResponseField` row on
  the instrument, pointed at a `ResponseTypeDefinition`.
- For numerical + string types: today every bounds combination
  needs a dedicated RTD row (`min` / `max` / `step` /
  `max_length`). Either auto-create a per-instrument RTD on each
  ✓ save, or wait on the
  [RTD-library retirement](./instrument_builder.md#d-rtd--response-field-type-inlining)
  that inlines bounds onto the response field directly (Part 1d
  in the sequencing plan).
- For list types: the row's `list_options` would create or
  reference a List RTD on the session.
- The ✓ → save flow would write through
  `instruments_service.add_response_field` /
  `update_response_field`; the X → delete flow would call
  `delete_response_field` (or its cascade-aware sibling when the
  field has saved responses).
- The pill's `selected` flag would mirror to a per-instrument
  flag — there's no existing "include in surface" concept for
  response fields (every response field renders on the surface
  today), so this might need a new boolean column or simply
  rely on "if it's in the table, it's shown".

The RTD-library retirement design (`guide/instrument_builder.md`
§D-RTD + §1d) is the prerequisite cleanup that makes the
numerical / string side of this much less ceremonial. Tackling
the integration before that retirement means accepting per-
instrument RTD bloat.

## When the integration matters

For the current pilot phase the gap is benign — the operator's
Band 2 / Band 3 choices visibly shape the preview row inside
the new-model card, which is enough for design feedback. The
gap matters once the new-model card stops being a concept test
and starts driving real reviewer-facing instruments.

Trigger conditions:

- A pilot operator wants a reviewer to actually fill in one of
  the new-model card's Band 3 response fields, end-to-end.
- A pilot operator wants pill selection to act as a true
  visibility toggle (deselect = column doesn't appear on the
  reviewer surface).

At that point Gap 1 (pill selection → visibility) is the
smaller of the two and should land first.
