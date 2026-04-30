# Segment 10A Implementation Plan — Response-field builder + reviewer-surface refactor

**Status:** Stub — decisions locked, slice breakdown still to be drafted.
First of two PR-sized blocks for Segment 10. See
`guide/segment_10_instrument_builder_mvp_plan.md` §14 for the
segment-level split.

- **10A (this doc):** consolidated `/operator/sessions/{id}/instruments`
  page with per-instrument cards; add / edit / delete / reorder of
  response fields; per-field help text + visibility; per-instrument
  friendly description; session-wide "Instruments Settings" card with
  a bulk accepting-responses toggle; reviewer-surface loop-by-instrument
  refactor with section heading + help block + table; global CSS width
  bump to 1400px.
- **10B (next):** display-fields picker + operator preview.

---

## Decisions locked for 10A

### D1 — Migration scope

Single Alembic revision, two columns on `instrument_response_fields`:

- `help_text` — `Text`, nullable.
- `help_text_visible` — `Boolean`, NOT NULL, server default `true`.

Nothing on `instruments`. The friendly-description column
(`Instrument.description`, `String(2000)` nullable) is **already**
provisioned in the schema and will simply start being read / written
in 10A. The system handle column (`Instrument.name`) stays
`String(255)` NOT NULL; existing rows keep their `"Default"` value
(no rename migration — code-only change for new sessions per §14.4).

10B's `InstrumentDisplayField` backfill is a separate migration, not
part of 10A.

### D2 — `field_key` format

Server-side regex `^[a-z][a-z0-9_]*$`, max length 64. Enforced at the
route layer on add-field; rejects with HTTP 400 + an inline error.

Auto-derive a default `field_key` from the operator-typed `label` via
slugify (lowercase, non-alnum → `_`, collapse repeats, strip leading
digits / underscores), but the form lets the operator override before
submitting. Once saved, `field_key` is immutable per §7.1 of the
parent plan.

The two seed keys (`rating`, `comments`) already conform.

### D3 — Empty-instrument handling

A session whose instrument has zero response fields **cannot
activate**. The Segment 9.5A `validated` precondition is extended:

- `validate_setup` adds a blocking error
  `"Instrument '<description-or-name>' has no response fields"` when
  any instrument under the session has zero `InstrumentResponseField`
  rows.
- `is_validated` therefore stays `false` for such a session, and the
  existing `_invalidate_if_validated` path on field-delete already
  flips a previously-validated session back to `draft` when the last
  field is removed.
- Reviewers never see an empty-instrument surface because activation
  is blocked. Per-instrument applicability filtering for the
  multi-instrument case is deferred to Segment 13.

### D4 — Instruments Settings card (session-wide)

A new card at the top of `/operator/sessions/{id}/instruments`,
above the per-instrument cards. Hosts session-wide settings that
apply across every instrument under the session:

- **Accepting responses (all instruments)** — three-state
  affordance (`all on` / `all off` / `mixed`). Click flips every
  instrument's `accepting_responses` in one transaction.
  Ready-only; gated identically to the per-instrument open / close
  routes (session must be `ready`, pre-deadline).
- (Forward-compat slot for future session-wide instrument settings;
  10A ships only the bulk-accepting-responses toggle.)

Routes:

- `POST /operator/sessions/{id}/instruments/accepting/all-on`
- `POST /operator/sessions/{id}/instruments/accepting/all-off`

Per-instrument `accepting_responses` and
`responses_visible_when_closed` toggles **still live on each
per-instrument card below** so individual override remains possible.
The two card layers are not in conflict — bulk is convenience; the
per-instrument card is the source of truth.

Audit: one `instruments.bulk_accepting_responses` event per bulk
toggle, with `detail.changed_instrument_ids` and `detail.target`
(`true` / `false`). Per-instrument open / close events are **not**
also written for the same bulk action.

### D5 — Per-instrument card layout

One card per instrument on the consolidated page. Sections, top to
bottom:

1. **System handle pill** — read-only `instrument_1` (etc.). Internal
   only; never reviewer-visible.
2. **Friendly description** edit form — single textarea bound to
   `Instrument.description`. Shown on the reviewer surface as the
   instrument's section heading (with fallback to system handle when
   `description` is null / blank). Audit: `instrument.described`.
3. **Acceptance + visibility toggles** — `accepting_responses` and
   `responses_visible_when_closed`, both fed by the existing 9.1
   POSTs (URLs unchanged; redirect targets switch from the legacy
   sub-page to `/instruments`).
4. **Response fields table** — Key, Label, Type, Required,
   Validation, Help text (preview), Help-visible toggle, Order,
   Actions (edit / delete / move up / move down).
5. **Add field form** — below the table.

The per-instrument card is the only home for friendly description.
The Instruments Settings card at the top stays focused on
session-wide settings.

### D6 — Required-toggle warning UX

Optional → required transitions render a flash banner on the next
GET via the post-redirect-get pattern: the edit POST 303s to
`/instruments?required_warning=<count>&field_id=<fid>`, the GET
renders a one-shot warning card naming the field and the count of
existing reviewer rows now missing the required answer. Banner is
single-shot (no sticky state, no acknowledgment column).

The banner is informational only. It does **not** block the save —
the optional → required transition is allowed unconditionally; the
banner just surfaces the consequence.

Required → optional is unconditional, no banner.

### D7 — Help-text rendering

`InstrumentResponseField.help_text` is rendered as plain text with
`white-space: pre-wrap`, server-side HTML-escaped. No markdown, no
HTML pass-through. Linebreaks in the textarea preserve as
linebreaks in the help block on the reviewer surface.

Per-field visibility toggle: when
`help_text_visible == false` OR `help_text` is null / empty, the
field's row is omitted from the help block above the table on the
reviewer surface (the field's input still renders in the table).

### D8 — Reorder UI

Per-row up / down buttons. Each click POSTs
`/operator/sessions/{id}/instruments/{instrument_id}/fields/{field_id}/move`
with `direction=up|down`, swaps the field with its neighbour, and
repacks orders contiguously to `0..N-1` on every save (per §7.3 of
the parent plan). No bulk-save reorder form in 10A.

Audit: one `instrument.fields_reordered` event per move with
`detail.old_order` and `detail.new_order` (full key list, not just
the swapped pair) so the audit trail captures the resulting
sequence.

### D9 — Width bump

`body { max-width: 1400px }` globally in
`app/web/templates/base.html`, replacing today's 900px. Uniform
across every page (no per-page narrow overrides in 10A — styling
polish lands in a future segment). Add a `.table-scroll {
overflow-x: auto }` utility class for the response-fields table on
narrow viewports.

### D10 — Validated → draft invalidation

All response-field mutations (`field_added`, `field_updated`,
`field_deleted`, `fields_reordered`) and `instrument.described` go
through the existing
`app.web.views._invalidate_if_validated` helper before mutating, so
a `validated` session flips back to `draft` with dedicated
`session.invalidated` audit. Matches the 9.5A pattern.

`instruments.bulk_accepting_responses`, per-instrument open / close,
and the visibility toggle do **not** invalidate — consistent with
the 9.5A carve-out for instrument open / close / visibility.

### D11 — Locked-when-ready predicate

Field mutations + description edit return HTTP 409 when
`session.status == "ready"`. Same predicate as the existing
`_require_draft_or_validated` helper used by setup-mutating routes.
Implementation lives in a single `_can_edit_instrument(instrument,
session)` helper so Segment 13 can refine to per-instrument keying
without rewriting every route.

Acceptance / visibility / bulk-accepting-responses routes stay
allowed in `ready` (they are response-window controls, not setup).

### D12 — Route consolidation

Routes for the consolidated page:

| Method | Path | Purpose |
|---|---|---|
| GET | `/operator/sessions/{id}/instruments` | Consolidated page (settings card + per-instrument cards) |
| GET | `/operator/sessions/{id}/instruments/{iid}` | 303 → `/instruments` (back-compat for bookmarks) |
| POST | `/operator/sessions/{id}/instruments/{iid}/edit` | Edit description (system `name` immutable) |
| POST | `/operator/sessions/{id}/instruments/{iid}/fields` | Add field |
| POST | `/operator/sessions/{id}/instruments/{iid}/fields/{fid}/edit` | Edit field |
| POST | `/operator/sessions/{id}/instruments/{iid}/fields/{fid}/delete` | Delete field (warn-and-confirm when responses exist) |
| POST | `/operator/sessions/{id}/instruments/{iid}/fields/{fid}/move` | Reorder up / down |
| POST | `/operator/sessions/{id}/instruments/{iid}/open` | (existing 9.1) accept responses |
| POST | `/operator/sessions/{id}/instruments/{iid}/close` | (existing 9.1) stop accepting |
| POST | `/operator/sessions/{id}/instruments/{iid}/visibility` | (existing 9.1) toggle `responses_visible_when_closed` |
| POST | `/operator/sessions/{id}/instruments/accepting/all-on` | Bulk: open every instrument |
| POST | `/operator/sessions/{id}/instruments/accepting/all-off` | Bulk: close every instrument |

All gated on `require_session_operator`. Existing 9.1 POSTs keep
their URL but switch their redirect target from the legacy sub-page
to `/instruments`.

### D13 — Reviewer-surface refactor

`/reviewer/sessions/{id}` refactors to loop over the session's
instruments. With N=1 today this renders a single section, but the
template structure already handles N > 1 for Segment 13.

Per instrument:
- **Section heading** = `Instrument.description` (fallback to
  `Instrument.name` when null / blank).
- **Help block** above the table — list each response field where
  `help_text` is non-empty AND `help_text_visible == true`, rendered
  as `label: help_text` with `white-space: pre-wrap`.
- **Table** = today's reviewer surface (one row per assignment, one
  input per response field). `pair_context_*` rendering stays
  hard-coded but moves inside the per-instrument loop (10B replaces
  it with `InstrumentDisplayField`-driven rendering).

Save / submit / clear endpoints unchanged.

### D14 — `target_operator_map.md` update

Deferred to 10B. 10A ships the consolidated `/instruments` page and
the per-instrument card; 10B adds the display-fields picker and
preview. Updating the spec once at the end of 10B avoids a
two-edit churn for the same page.

---

## Audit events added in 10A

- `instrument.field_added`
- `instrument.field_updated`
- `instrument.field_deleted` (incl. `cascaded_response_count`)
- `instrument.fields_reordered`
- `instrument.described`
- `instruments.bulk_accepting_responses`

Shapes per §8 of the parent plan, with `instrument.described` and
`instruments.bulk_accepting_responses` added.

---

## Out of scope for 10A (explicitly deferred)

- Display-fields picker UI + `InstrumentDisplayField` backfill
  migration → 10B.
- `pair_context_*` migration to `InstrumentDisplayField`-driven
  render → 10B.
- Operator preview route → 10B.
- Multi-instrument operator UI (Add / Delete instrument buttons stay
  disabled per 9.4C) → Segment 13.
- Per-instrument applicability filtering on the reviewer dashboard
  → Segment 13.
- `spec/target_operator_map.md` update → end of 10B.
- Any width / styling polish beyond the uniform 1400px bump → future
  segment.

---

## To draft next

This stub locks the decisions. The implementation slice breakdown
(parallel to `segment_09_4A.md` Slices 1–5: migration → service
layer → routes → templates → tests with ~15–20 cases) is **not yet
drafted** and is the next deliverable on this branch.
