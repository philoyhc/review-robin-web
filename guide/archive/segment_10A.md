# Segment 10A Implementation Plan — Response-field builder + reviewer-surface refactor

**Status:** First of two PR-sized blocks for Segment 10. See
`guide/archive/segment_10_instrument_builder_mvp_plan.md` §14 for the
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

## Implementation slices

### Slice 1 — Alembic migration + model columns

- New revision under `alembic/versions/` adding two columns to
  `instrument_response_fields`:
  - `help_text` `Text`, nullable.
  - `help_text_visible` `Boolean`, NOT NULL, server default `true`.
  Both `add_column` calls; SQLite-safe. `downgrade()` drops both.
  No backfill needed — `server_default=true` covers existing rows
  for `help_text_visible`; `help_text` defaults to NULL.
- `app/db/models/instrument_field.py`: add the matching
  `Mapped[str | None]` / `Mapped[bool]` attributes on
  `InstrumentResponseField`. Keep the `from sqlalchemy import Text`
  add minimal — no `sqlalchemy.dialects.postgresql` import per
  AGENTS.md.
- `app/services/instruments.py::ensure_default_instrument`: leave
  the seed fields' `help_text` at `None` and rely on the column
  default for `help_text_visible`. No behaviour change for new
  sessions.
- Land this slice atomically: the model + migration must travel
  together so the `postgres-migration` smoke job in PR CI exercises
  the upgrade against a real Postgres before any route reads the
  new columns.

### Slice 2 — Service layer

New module-level functions in `app/services/instruments.py`
(matching the existing module style):

- `_FIELD_KEY_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")` and
  `_FIELD_KEY_MAX_LEN = 64` constants (per D2).
- `slugify_field_key(label: str) -> str` — lowercase, non-alnum →
  `_`, collapse repeats, strip leading digits / underscores, trim
  to 64. Pure function, easy to unit-test.
- `class FieldKeyError(ValueError)` and
  `class ResponsesPresentError(Exception)` (carries
  `cascaded_response_count`) for route-layer translation to
  HTTP 400 / 409.
- `add_response_field(db, *, instrument, field_key, label,
  response_type, required, validation, help_text,
  help_text_visible, actor) -> InstrumentResponseField`:
  - validate `field_key` against regex + length;
  - reject duplicate `(instrument_id, field_key)` early with a
    friendly error (the unique constraint is the safety net);
  - assign `order = max(existing) + 1` then repack to
    `0..N-1` for cleanliness;
  - audit `instrument.field_added` per §8 of the parent plan.
- `update_response_field(db, *, field, label, required, validation,
  help_text, help_text_visible, actor)
  -> tuple[InstrumentResponseField, int]`:
  - diff inputs against current values; build `changes` dict for
    audit (`{key: [old, new], ...}`) excluding unchanged keys;
  - when `required` flips `False → True`, count existing
    `Response` rows under this `instrument` that lack a non-blank
    answer for this `response_field_id` across reviewers who have
    at least one Response on the instrument (the "now-missing"
    population per D6); return that count for the route to surface
    in the redirect query.
  - audit `instrument.field_updated`.
- `delete_response_field(db, *, field, confirm: bool, actor)`:
  - count existing `Response` rows for the field;
  - when count > 0 and not `confirm`: raise
    `ResponsesPresentError(count)`;
  - else: snapshot the field config, delete (cascade removes
    responses), audit `instrument.field_deleted` with `snapshot`
    and `cascaded_response_count`.
- `move_response_field(db, *, field, direction: Literal["up",
  "down"], actor)`:
  - load all fields under the instrument ordered by `order`;
  - swap `field` with its neighbour in the requested direction
    (no-op + 400 at the route when at boundary);
  - repack `0..N-1`;
  - audit `instrument.fields_reordered` with `old_order` /
    `new_order` lists of `field_key` (D8).
- `update_instrument_description(db, *, instrument, description,
  actor)`:
  - normalise empty string to `None`;
  - audit `instrument.described` with `[old, new]` description
    pair.
- `bulk_set_accepting(db, *, session, target: bool, actor)
  -> list[int]`:
  - flip `accepting_responses` on every instrument under the
    session whose current value differs from `target`;
  - return the list of changed instrument ids;
  - emit a single `instruments.bulk_accepting_responses` event
    with `detail.target` and `detail.changed_instrument_ids`
    (per D4) — explicitly **not** the per-instrument
    `instrument.opened` / `instrument.closed` events.

`app/services/validation.py` (where `validate_setup` lives):

- Extend the blocking-error list with one entry per instrument
  under the session that has zero `InstrumentResponseField` rows
  (D3): `"Instrument '<description-or-name>' has no response
  fields"`. Use the friendly description when set, else the
  system handle. The session detail card consumes this through
  the existing validation report shape; no caller change.

### Slice 3 — Routes

In `app/web/routes_operator.py`:

- New helper `_can_edit_instrument(instrument, session) -> bool`
  returning `session.status != SessionStatus.ready` (D11). All
  description / field-mutation routes guard on this and raise
  `HTTPException(409)` when false.
- Rewrite the `instruments_index` view (`GET
  /sessions/{id}/instruments`) to render the consolidated page:
  load instruments, response fields (eager), and pass a
  `required_warning` tuple decoded from query params (D6) plus
  the bulk-toggle three-state value (`all-on` / `all-off` /
  `mixed`) computed across instruments.
- Replace `instrument_detail` GET (`/instruments/{instrument_id}`)
  with a 303 redirect to `/instruments` (D12 back-compat for
  bookmarks).
- Add POST handlers per the D12 table:
  - `…/{iid}/edit` → `update_instrument_description`. Pre-call:
    `_can_edit_instrument` (else 409) + `_invalidate_if_validated`.
    303 → `/instruments`.
  - `…/{iid}/fields` → `add_response_field`. Auto-derive
    `field_key` via `slugify_field_key(label)` when the operator
    leaves the field-key input blank. Pre-call: `_can_edit` + 
    `_invalidate_if_validated`. On `FieldKeyError` re-render the
    page with HTTP 400 + inline error. 303 → `/instruments` on
    success.
  - `…/{iid}/fields/{fid}/edit` → `update_response_field`. Same
    pre-call gates. On `required_warning_count > 0`, 303 →
    `/instruments?required_warning=<count>&field_id=<fid>`.
  - `…/{iid}/fields/{fid}/delete` → `delete_response_field`.
    On `ResponsesPresentError`, re-render with HTTP 400 + a
    confirm card showing the count and a hidden `confirm=true`
    submit. On confirm, redirect to `/instruments`.
  - `…/{iid}/fields/{fid}/move` → `move_response_field`,
    `direction` from form. Same pre-call gates. 303 → 
    `/instruments`.
  - `…/accepting/all-on`, `…/accepting/all-off` →
    `bulk_set_accepting(target=True|False)`. Gated identically to
    the per-instrument open / close routes (status `ready`,
    pre-deadline). **No** `_invalidate_if_validated` (D10). 303 →
    `/instruments`.
- Existing 9.1 POSTs (`/instruments/{iid}/open`, `/close`,
  `/visibility`) keep their paths; switch their `RedirectResponse`
  target from `/instruments/{iid}` to `/instruments`.
- `app/web/breadcrumbs.py`: confirm `operator_session_child(s,
  "Instruments")` is what the consolidated page uses; no other
  trail change.

### Slice 4 — Templates + CSS

- Rewrite `app/web/templates/operator/instruments_index.html` into
  the consolidated page:
  - **Instruments Settings card** (D4) at the top:
    three-state bulk-accepting label + two POST forms (`all-on`,
    `all-off`); render the third state as static text `"Mixed —
    use the per-instrument toggle below"`. Disabled when session
    is not `ready` (matches per-instrument toggles).
  - **One `<section class="card">` per instrument** following the
    D5 layout: system-handle pill, friendly-description form,
    acceptance form, visibility form, response-fields table
    inside `<div class="table-scroll">`, add-field form. The
    response-fields table renders one row per field with: key
    (`<code>`), label, type, required pill, validation summary,
    help-text preview (`<pre>` with `white-space: pre-wrap` per
    D7), help-visible checkbox-form, up/down move buttons (POST
    forms with `direction` hidden), Edit (anchor that toggles a
    sibling edit-row form via `<details>` for MVP — no JS), and
    Delete (POST form with confirm checkbox surfaced inline when
    the prior delete attempt 400'd).
  - **Required-toggle warning banner** at the top of the per-
    instrument card whose `field_id` matches `?field_id=…` (D6),
    text: `"Field '<label>' is now required; <count> existing
    reviewer row(s) currently lack an answer."` Banner is
    one-shot (no acknowledgment column).
  - Disabled Add / Delete instrument anchors stay at the very
    top, matching today's 9.4C placeholders.
- Delete `app/web/templates/operator/instrument_detail.html` —
  its content (acceptance form, visibility form) is fully
  subsumed into the per-instrument card. Update any template
  references; `_require_instrument_in_session` stays for the
  POST handlers.
- `app/web/templates/base.html`: bump `body { max-width: 1400px }`
  (D9), and add `.table-scroll { overflow-x: auto; }` plus a
  small `.pill.pill-handle { font-family: monospace; }` rule for
  the system-handle pill.
- Reviewer surface refactor (D13) — `app/web/templates/reviewer/
  review_surface.html`:
  - Wrap today's response table in `{% for instrument in
    instruments %}`; section heading is `<h2>{{
    instrument.description or instrument.name }}</h2>`.
  - Above the table, render a help block:
    `{% if instrument.help_block_items %}<dl>…</dl>{% endif %}`.
    Each item is `<dt>{{ field.label }}</dt><dd>{{
    field.help_text }}</dd>` rendered with `white-space:
    pre-wrap` (server-side escaping is automatic via Jinja).
    Item set computed by the view: fields with non-empty
    `help_text` AND `help_text_visible == True`.
  - Today's `pair_context_*` rendering moves inside the loop,
    unchanged otherwise; 10B replaces it with
    `InstrumentDisplayField`-driven rendering.
- `app/web/views.py` (or the reviewer surface helper that
  populates the template context): build a list-of-instruments
  shape: `[{"id", "name", "description", "fields",
  "help_block_items", …}]`. Save / submit / clear endpoints stay
  on today's `(assignment_id, response_field_id)` keying — the
  field-set the reviewer sees is just the union over the
  instruments loop.

### Slice 5 — Tests

Aim for ~18 cases across two new files plus targeted additions to
existing files. Unit tests use the in-memory SQLite fixture; route
tests use the existing `client` fixture.

**Unit (`tests/unit/test_instrument_builder.py`)**

1. `slugify_field_key("Overall Rating")` → `"overall_rating"`;
   `"1st choice"` → `"st_choice"`; `"a__b"` → `"a_b"`; truncates
   at 64.
2. `add_response_field` rejects `field_key` that fails the regex
   (raises `FieldKeyError`); no row written.
3. `add_response_field` rejects duplicate `field_key` within an
   instrument; first row preserved.
4. `add_response_field` appends at end and repacks orders to
   `0..N-1`; audit `instrument.field_added` written with the
   shape from §8.
5. `update_response_field` records only the changed keys in
   `detail.changes` (a no-op edit produces an empty `changes`
   dict but still audits — assert one event).
6. `update_response_field` returns `required_warning_count > 0`
   when an optional field flips required and existing reviewer
   rows have a blank answer; returns `0` when none do; `0`
   unconditionally for required → optional.
7. `delete_response_field` without `confirm` raises
   `ResponsesPresentError(count)` when responses exist; with
   `confirm=True` cascades and audits `cascaded_response_count`.
8. `move_response_field("up"/"down")` swaps with neighbour and
   repacks; audits `old_order` / `new_order` as `field_key`
   lists.
9. `update_instrument_description("")` normalises to `None` and
   audits `[old, None]`.
10. `bulk_set_accepting(target=False)` flips only the instruments
    whose state differed; emits exactly one
    `instruments.bulk_accepting_responses` event; **no**
    per-instrument `instrument.closed` events written.
11. `validate_setup` adds a blocking error per zero-field
    instrument; report's `can_activate` is False.

**Integration (`tests/integration/test_instrument_builder_routes.py`)**

12. `GET /operator/sessions/{id}/instruments` renders the
    Settings card and one card per instrument; system-handle pill
    visible; friendly description rendered when set.
13. `GET /operator/sessions/{id}/instruments/{iid}` returns 303 →
    `/instruments` (back-compat).
14. `POST …/{iid}/edit` updates description; redirects to
    `/instruments`. From `validated`, status flips to `draft` and
    a `session.invalidated` event is written.
15. `POST …/{iid}/fields` with blank `field_key` auto-slugifies
    from `label`; row visible on the next GET.
16. `POST …/{iid}/fields/{fid}/edit` flipping optional → required
    redirects to `…/instruments?required_warning=N&field_id=F`;
    next GET renders the one-shot banner naming the field and
    the count.
17. `POST …/{iid}/fields/{fid}/delete` with responses present
    re-renders the page with HTTP 400 + a confirm card; second
    POST with `confirm=true` cascade-deletes.
18. `POST …/{iid}/fields/{fid}/move` repacks orders; audit
    captures the full key sequence.
19. `POST …/accepting/all-off` flips every instrument's
    `accepting_responses` in one transaction and writes one
    `instruments.bulk_accepting_responses` event; no per-
    instrument open/close events. From `ready`, **no**
    `session.invalidated` event (D10).
20. Locked-when-`ready`: every description / field-mutation
    route returns 409; bulk-accepting routes still 200/303.
21. Reviewer surface: response table renders fields under a
    section heading from `Instrument.description`; help block
    above the table lists only fields whose `help_text` is
    non-empty AND `help_text_visible == True`. Adding a new
    `yes_no` field via the operator route makes the input appear
    on the next reviewer GET (regression-guard for the
    auto-render contract).
22. Activation blocked when an instrument has zero response
    fields: `validate_setup` reports the error;
    `GET …?validated=1` does **not** flip status to
    `validated`; activate POST returns the existing
    "validation required" path.

**Targeted additions to existing files**

- `tests/integration/test_chrome_breadcrumbs.py` (or wherever the
  width assertion lives): grep-guard the `1400px` value.
- `tests/integration/test_session_lifecycle.py`: assert the
  description / field-mutation routes flip `validated → draft`
  while open / close / visibility / bulk-accepting do **not**
  (D10).

Existing instrument-route tests in
`tests/integration/test_instrument_routes.py` (or equivalent)
need their redirect-target assertions updated from
`/instruments/{iid}` to `/instruments` (the open / close /
visibility POSTs now land on the consolidated page).

---

## Docs to update at PR time

- `docs/status.md`:
  - Timeline row: `2026-04-NN | Segment 10A shipped (response-
    field builder + reviewer-surface refactor)`.
  - Segments-shipped row: `10A | Consolidated /instruments page
    with response-field builder, friendly description, per-field
    help text + visibility, bulk accepting toggle, reviewer-
    surface loop-by-instrument refactor, body width 1400px |
    <date>`.
  - "Instruments" capability section: replace the 9.4C
    placeholder bullet with a paragraph describing the consolidated
    page.
  - Audit table: add `instrument.field_added`,
    `instrument.field_updated`, `instrument.field_deleted`,
    `instrument.fields_reordered`, `instrument.described`,
    `instruments.bulk_accepting_responses`.
  - "What's deliberately not yet there": remove the "Instrument
    builder" row; keep the "Display-fields picker / preview"
    row (10B).
- `AGENTS.md`: bump "Current stage" to mention 10A (consolidated
  `/instruments`, builder, help text + visibility, reviewer-
  surface loop, 1400px width).
- `spec/target_operator_map.md`: deferred to end of 10B per D14
  (avoids two-edit churn for the same page).
- `spec/operator_map.md` (as-is map): update to reflect the
  consolidated `/instruments` page replacing the per-instrument
  detail sub-page.
- `README.md`: only if a tooling / dependency change ships in 10A
  (none expected).

---

## Risk notes

- **Wide diff, two surface areas.** Slices 3 + 4 touch the
  operator instruments surface and the reviewer surface in the
  same PR. Land Slice 1 + Slice 2 first as a self-contained
  schema + service change so the route + template work has stable
  ground; reviewers can model the contract before the wide UI
  diff.
- **Server-default vs ORM-default for `help_text_visible`.** The
  migration uses `server_default=true` so existing rows are
  back-filled at upgrade time. The model uses `default=True` so
  ORM-created rows match. Forgetting one of these surfaces as a
  NOT NULL violation on the first add-field POST after upgrade —
  the `postgres-migration` smoke job catches it.
- **`InstrumentDisplayField` table lookups in 10A.** The
  reviewer-surface refactor loops over instruments but does
  **not** start reading `InstrumentDisplayField` — `pair_context_*`
  rendering stays hard-coded inside the loop until 10B. Avoid
  importing the model in the reviewer view; otherwise diff churn
  doubles when 10B lands.
- **Empty-instrument validation.** D3 makes a zero-field
  instrument a blocking validation error. Existing test fixtures
  that build a session but never call `ensure_default_instrument`
  (or that delete the seed fields) will start failing
  `can_activate` — sweep `tests/` for fixtures that touch
  `InstrumentResponseField` directly before merging.
- **Banner one-shot semantics.** D6 keeps the required-toggle
  warning state in the redirect query string only. A second GET
  without the query params clears the banner; reviewers won't
  see it. Document this in the route's docstring so a future
  contributor doesn't add a sticky `acknowledged_at` column "for
  consistency."
- **Locked-when-`ready` predicate placement.** D11 specifies a
  single `_can_edit_instrument(instrument, session)` helper.
  Resist the temptation to inline the `session.status == ready`
  check at each route; Segment 13's per-instrument keying refines
  the helper, not every route.
- **Width bump regression surface.** `body { max-width: 1400px }`
  may visually regress a few existing pages designed for 900px
  (notably the sessions list and the new-session form). 10A
  ships the uniform bump; per-page narrow overrides are out of
  scope (D9). Spot-check the chrome + breadcrumb tests still
  pass — they grep on text, not layout.
- **Back-compat redirect on `/instruments/{iid}`.** D12 keeps
  this URL alive as a 303 to `/instruments`. Tests that hit it
  for the GET need updating; tests that hit it for POSTs (open /
  close / visibility) keep working — only the redirect target
  changes.
