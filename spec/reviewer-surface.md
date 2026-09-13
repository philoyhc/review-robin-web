# Reviewer surface — functional + visual spec

Specification of the reviewer-facing app — the pages a signed-in
reviewer sees when they follow an invitation link or visit `/me`
directly. The response surface (`/me/sessions/{id}/{page_n}`)
is the page they spend ~all their time on; the dashboard
(`/me`) and invitation-landing (`/me/invite/{token}`)
exist to land them on it.

The response surface is **multi-instrument aware**: the URL carries an
explicit page segment, the page renders one operator-defined page of
instruments at a time, and an action row at the top *and* bottom of the
surface carries every control — the review-level controls (Save /
Cancel / Submit) and the per-page navigation — in one strip per side,
the two groups separated by a vertical divider. Single-instrument
sessions are a degenerate case of the same model, not a second shape.

Cross-references:

- `spec/visual_style_rrw.md` "Response form layout and instrument
  pacing" — the underlying principle (one page per instrument,
  tabular form, pacing via operator instrument design). This spec
  is the implementation contract for that principle on the live
  surface.
- `spec/visual_style_rrw.md` — top-bar / chrome conventions, banner
  family, status-icon classes.
- `spec/visual_style_general.md` — `.card` / `.btn` / `.pill` / form
  primitives.
- `spec/ui_elements.md` — canonical elements (P6 hover-by-fill, P7
  recovery-action color family).
- `spec/preview_hub.md` — operator-side preview entry-point spec; the
  preview page reuses this surface's template.
- `app/web/templates/reviewer/review_surface.html` — the template this
  spec governs. The operator-side preview route renders the same file.

---

## URL pattern

```
GET  /me/sessions/{session_id}/{page_n}
POST /me/sessions/{session_id}/{page_n}/save
POST /me/sessions/{session_id}/submit
POST /me/sessions/{session_id}/clear
```

`{page_n}` is the **1-indexed operator-defined page number** within the
session. Pages are derived from `Instrument.starts_new_page`:
instruments walk in `Instrument.order, Instrument.id` order and a new
page begins at every instrument whose flag is true. Each page contains
one or more instruments. The slot carries the **page** number and never
the instrument position, which is what keeps a single-page session a
degenerate case of the same model rather than a second shape — `/1` is
then the only valid page.

`GET /me/sessions/{id}` (no page) **303s to
`/me/sessions/{id}/1`** so existing invitation links and dashboard
rows keep working. Out-of-range pages (e.g. `/me/sessions/5/9` when
the session has only 2 pages) return **404**.

The reviewer dashboard at `/me` always links each row to `/1`,
since the dashboard summarises the session as a whole and page 1 is a
safe default landing.

**URL semantics across the four routes.**

- The GET route renders **only the current page's instruments** — every
  instrument the reviewer has assignments on that belongs to the
  operator-defined page at `{page_n}`. Cross-page navigation uses the
  Prev / Next nav row (see "Page anatomy" below); intra-page anchors
  (`#instrument-{id}`) cover the in-page TOC.
- The Save POST is **page-scoped** — `{page_n}` tells the route which
  page's response fields to persist; defense-in-depth filtering drops
  upserts that don't belong to this page. On success, 303s back to
  `/{page_n}`.
- The Submit POST is **session-wide** — no `{page_n}` segment; submits
  the whole review. On success, 303s to `/me/sessions/{id}`
  (which 303s on to `/1`) or to the summary page when the submit closed
  out the whole session.
- The Clear POST is **session-wide** — no `{page_n}` segment; wipes
  everything and 303s to the bare session URL.

---

## Page anatomy

Top-to-bottom, the page renders:

1. **Top bar (reviewer chrome variant)** — per
   `spec/visual_style_rrw.md` "Reviewer-facing pages → Top bar". "Review
   Robin" identity (no version, no breadcrumb), user menu with "Signed
   in as …" + optional "My Reviews" + optional **Guide** + **About** +
   "Sign out". The About link (`/about?return_to=<path>`, skipped on
   `/about` itself) matches the operator chrome's, so `/me` reaches the
   About / access-help page the same way `/operator/sessions` does. The
   Guide link (`/guide?return_to=<path>`) carries the operator chrome's
   condition — the
   `request.state.guide_hidden` hide flag, read fail-open — so it
   renders for a viewer who resolves at least one Guide audience and is
   absent for one who resolves none.
2. **Preview banner** — `body.ui-v2` only (operator preview mode
   reuses this template); rendered as `.banner.banner-info`.
3. **Page header** — `.rs-page-header` flex row carrying the session
   name as H1 plus the deadline inline as `.muted`. The deadline
   renders in the session's resolved zone followed by that zone's
   compact GMT-offset + raw IANA id in parentheses — e.g.
   `Deadline: 2026-06-02 07:59 (GMT+10 Australia/Melbourne)` — via
   `date_formatting.gmt_offset_zone_label`.
4. **Overview card** — a single full-width `.card.rs-status-panel`
   rolling together, top to bottom:
   - The session **description**, when `session.description` is set.
     Renders with `white-space: pre-line` (the `.rs-session-description`
     class) so the operator's line / paragraph breaks are preserved.
   - The transient **session-closed banner** — a
     `.banner.banner-warning` shown inline in the card when the
     session is no longer accepting responses; does not push other
     layout around.
   - **Per-page status pills** — one pill per instrument labelled
     e.g. `Page 1: in progress`, `Page 2: complete`. State computed
     server-side from response data (see "Per-page status" below).

   The card is omitted entirely only when there is neither a
   description nor any status pills. **Save and Submit raise no flash
   banner**: the per-page status pills are the canonical signal, and the
   missing-required and invalid-value warnings render as their own
   full-width cards below rather than inside this one.
5. **Action row (top)** — `.rs-action-row.rs-action-row-top`,
   **left-aligned** so it reads as the lead-in to the form (the
   bottom action row is flush right — see §8). The surface's main
   control strip: one row carrying every action — the review-level
   controls first, then the per-page navigation — in this
   left-to-right order:
   - `Save` (Secondary, `type="submit"`, `data-rs-save`) — submits
     the page `<form>` to persist the current page's inputs. Always
     enabled; there is no dirty-tracking gate (see "Save button
     state" below).
   - `Cancel` (Secondary, rendered as an `<a href>` back to the
     current page URL, `data-rs-discard` — the hook keeps the older
     name) — a plain GET reload of
     the current page. Because unsaved typing lives only in the DOM
     of the current page, reloading throws it away and re-renders
     from the last-saved server values. No JS, no separate write.
   - `Submit` (Primary, `type="submit"` with
     `formaction="…/submit"`) — review-session-wide. Persists the
     current page's inputs and stamps `submitted_at` on every
     assignment. (See §"Form HTML mechanics" below.)
   - **Vertical divider** — a `.rs-action-divider` element separating
     the review-level controls (Save / Cancel / Submit) from the
     per-page navigation cluster. 1px wide, full button-height,
     `border-default` colored, with horizontal margin. Rendered only
     on multi-page sessions (`page_count > 1`); in operator-preview
     mode Save / Cancel / Submit render as inert disabled buttons
     and Prev / Next stay functional.
   - **Prev / Page N of M / Next** — the page-navigation cluster,
     rendered only on multi-page sessions. **Previous page** and
     **Next page** are plain `<a href>` links that round-trip the
     server to the adjacent page URL (`/me/sessions/{id}/{N}`); at a
     boundary the link renders as a disabled `<button>` so the
     layout stays stable. Between them a `Page {N} of {M}` text
     counter (not a button). There is no per-instrument page button
     and no client-side page swap — every page change is a server
     GET.
6. **Instrument body** — heading, help-text card(s), reviewer table.
   Exactly one instrument's content renders per page.
7. **Missing-required warning card** — `.rs-missing-card`, full-width
   below the overview card, two-column flow. Renders only after a
   blocked Submit attempt; enumerates gaps as `Page N: Reviewee X —
   field Y`. Submit is a **hard gate** (no acknowledge-and-submit-
   anyway path); the reviewer fills the gaps and resubmits.
   `data-rs-errors-card` (same chrome) surfaces server-side numeric
   validation rejections, with the typed value preserved in the
   originating input so the reviewer can correct in place.
8. **Action row (bottom)** — `.rs-action-row`, flush right. Mirrors
   the top action row's buttons, order, and divider exactly; it is
   flush right rather than left-aligned (§5) so it reads as a
   trailing control strip. The repetition lets the reviewer act
   without scrolling back to either end of the table.
9. **Danger zone** — `.card.danger-zone.rs-danger-zone` with the
   Clear-all-responses form. Half-width, flush right, 24px above the
   foot. Review-session-wide; wipes every response across all
   instruments. Only when `any_accepting and not preview_mode`.

Mental model: instruments are **chapters of one review session**, not
standalone editing surfaces. The reviewer fills each page (saving
when they like), then **Submit commits the whole review** in one
action. "Page actions" (Save / Cancel / Prev / Next) act on the
current page; "Review-level actions" (Submit / Clear all) act on the
entire session. Page navigation is a plain server round-trip: each
page change re-fetches that page's HTML. Persistence to the database
happens only on explicit Save or Submit, so unsaved typing on the
current page is lost if the reviewer navigates away without saving.

### How the surface works

Each page is its own server-rendered HTML response. The GET route at `/me/sessions/{id}/{page_n}`
filters to **only the current page's instruments** (the run between
the operator-defined `starts_new_page` boundaries) and renders just
those. Cross-page navigation is plain HTTP — Prev / Next links are
`<a href>`s that round-trip the server. Only the current page's
inputs exist in the DOM; other pages' values live in the database
(from prior Saves), not in the current page.

Reviewer-typed values persist across page navigations only after a
Save round-trip; the draft store is the database, not the DOM.
There is **no `beforeunload` guard** in the shipped surface —
navigating away (Prev / Next, address-bar change, close-tab) or
clicking **Cancel** silently drops any unsaved typing on the
current page. A `beforeunload` warning that keys off the same dirty
signal is a deferred progressive enhancement (see
"Designed-for-extensibility").

**The pattern it defers already ships on the operator surface**, so
whoever implements this here has a working reference rather than a blank
page: `operator/instruments_index.html` wires one `beforeunload` listener
that fires only when a card carries
`[data-instrument-dirty="true"]`, and returns early on
`window._newModelIntentionalNav` so a deliberate discard or lock is not
itself treated as an accident. **Both halves are load-bearing** — a guard
without the dirty gate prompts on every navigation, and one without the
intentional-nav escape prompts on the app's own controls.

### Save / Cancel / Page navigation / Submit / Clear all

| Button | Scope | HTTP | Behavior |
|---|---|---|---|
| **Save** | Page | POST `…/{page_n}/save` | Submit the page `<form>` to persist the **current page's** inputs to the database. Always enabled (no dirty-tracking gate). On success: 303 → `…/{page_n}` (no flash; the page-status pill in the overview card is the canonical save indicator). On invalid numeric value: re-render with the `data-rs-errors-card` warning card and the typed value preserved in the input. |
| **Cancel** | Page | GET `…/{page_n}` | An `<a href>` back to the current page URL — a plain server reload. Unsaved typing lives only in the current page's DOM, so the reload re-renders from the last-saved server values, dropping the edits. No JS, no separate write, no audit. Other pages' saved state is untouched. |
| **Prev / Next** | Page | GET `…/{N}` | `<a href>` links to the adjacent page — plain HTTP navigation. Server-side render returns that page's instruments. At a page boundary the link renders as a disabled `<button>`. There is no per-instrument page button and no client-side swap. Unsaved typing on the current page is lost on navigation (no `beforeunload` guard). |
| **Submit** | Review-session | POST `/me/sessions/{id}/submit` | First persist the dirty inputs across **every** page (an implicit save of the whole review), then validate required fields across every instrument and stamp `submitted_at` on every assignment in the session. Submit is a **hard gate** on missing required (no acknowledge-and-submit-anyway path): on missing-required, 400 + re-render the surface with the full-width `.rs-missing-card` enumerating gaps. On invalid numeric value: 400 + re-render with the `data-rs-errors-card` (validation gate fires before missing-required). On success: 303 → `…/{page_n}` (no flash; the per-page pill flips to `submitted` and the status column shows the complete icon on every row whose required fields are filled). |
| **Clear all** | Review-session | POST `/me/sessions/{id}/clear` | Wipe every response across every instrument (confirmation checkbox required). Clears any submitted state. Lives in the half-width-flush-right Danger Zone card at the foot of the surface, not in the action rows. |

### Why Submit is session-wide

Conceptually a review is one document spread across multiple pages.
Per-page submit would require the reviewer to remember to submit
each page individually, which invites missed submissions. The single
review-session-wide Submit affordance — surfaced at the top *and*
bottom of every page — makes "I'm done" a single click no matter
which page the reviewer is on. Submit posts the current page's
`<form>`, so it implicit-saves the current page's inputs before
stamping submission; other pages contribute the drafts they saved
on their own Save round-trips.

### Save button state

The Save button is **always enabled** — it is a plain
`type="submit"` control (`data-rs-save`) with no dirty-tracking
gate. Saving with no edits is a harmless no-op 303 back to the same
page. The `data-rs-save` / `data-rs-discard` / `data-rs-saved-value`
attributes are rendered as hooks for a future dirty-tracking
progressive enhancement (Save-disable-until-dirty, in-place discard,
`beforeunload` guard), but **no JS handler is wired for them today**
— see "Designed-for-extensibility".

### Form HTML mechanics

The whole editing surface lives inside a single `<form>` whose
default `action` is `…/{page_n}/save` and `method="post"`. Save
submits to that default action; Submit overrides via
`formaction="/me/sessions/{id}/submit"`. Both buttons send
the **entire** form body — every input across every instrument
group, since they're all in the DOM. The route distinguishes:

- Save filters the incoming form to inputs whose `name` matches
  response fields belonging to `{page_n}`'s instrument and
  persists those, ignoring everything else.
- Submit accepts the entire form body, persists every value, then
  applies the session-wide submission semantics.

### Persistence semantics

- **Save** upserts `Response` rows in `(assignment_id,
  response_field_id)` shape. An empty submitted value **deletes**
  the matching `Response` row (so absence == empty answer); a
  non-empty value upserts. Save never touches `submitted_at`. The
  filter-by-position keeps Save from accidentally touching another
  page's saved values when only the current page should change.
- **Submit** persists pending writes session-wide (treating the
  whole form body as a session-wide save), then validates required
  fields across every instrument. With acknowledge (or no missing
  required), it stamps `submitted_at` on every Response row in the
  session and writes a `responses.submitted` audit event. Editing a
  previously-submitted required field to empty deletes its
  `Response` row (including the `submitted_at` stamp), which flips
  the dashboard pill back to `in progress` on next render — no
  per-row resubmit required.
- **Clear all** deletes every `Response` row for this reviewer in
  this session, across every instrument. No partial undo. Writes a
  `responses.cleared` audit event.
- **Cancel** is a plain GET reload of the current page (an
  `<a href>`) — no DB write, no audit. The reload re-renders the
  current page's inputs from the server-saved baseline, dropping
  any unsaved typing.

**"Submitted" status on the dashboard.** Once Submit succeeds, every
assignment in the session has `submitted_at` set. The dashboard's
session-level pill ("submitted" / "in progress" / "not started")
follows the same rule it does today (every assignment submitted →
"submitted"). With session-wide Submit, the rollup is always
all-or-nothing rather than "submitted on some pages but not others".

---

## Per-page status

The overview card renders one status pill per instrument,
positioned immediately above any transient flash banners that may
land. Status is computed **server-side from saved response data**;
client-side dirty edits don't shift a pill until the reviewer
clicks Save (and the page re-renders).

| Pill state | Pill class | Condition |
|---|---|---|
| `not started` | `.pill.pill-empty` | No saved Response rows for any of this page's assignments. |
| `in progress` | `.pill.pill-warning` | Some Response rows saved, but at least one required field empty across this page's assignments. |
| `complete` | `.pill.pill-success` | Every required field on every assignment in this page has a saved value. |
| `submitted` | `.pill.pill-success` | Every assignment in this page has `submitted_at` set (i.e. the session has been submitted; all pages flip together). |

Pill copy is `{label}: {state}`, where `label` follows the same
`#{N} {short_label}` (or bare `#{N}` when no short label is set)
convention as the per-instrument heading — e.g. `#1 Skills: in
progress`, `#2: complete`. Single-instrument sessions still show
one pill, since the overview card renders whenever there are
status pills.

The route threads a `page_statuses: list[PageStatus]` into context
(`PageStatus = {position: int, label: str, state: Literal[…]}`),
populated for every instrument regardless of how many there are. The
template iterates and renders one pill per entry.

### Session-wide status pill

Leading the per-page pills — first on the same flex-wrap row — the
overview card renders a single session-wide rollup pill, the
at-a-glance "where is this review overall", set from the per-page
states:

| Pill | Pill class | Condition |
|---|---|---|
| `Submitted` | `.pill.pill-success` | Every page is `submitted`. |
| `Draft` | `.pill.pill-empty` | Every page is `not started`. |
| `Saved but not submitted` | `.pill.pill-warning` | Anything in between — some pages carry saved data, not all submitted. |

The route adds `session_status: Literal["submitted", "saved",
"draft"] | None` to context (`None` when the reviewer has no pages,
so no pill renders — and in operator preview, which passes no
`page_statuses`).

---

## Per-instrument table

Each page renders **one tabular response artifact** for the current
instrument: every assignment the reviewer has on that instrument is
one row, with response fields as columns. Wrapped in
`.table-scroll` so very wide instruments scroll horizontally instead
of forcing the surrounding layout to grow.

Reviewer-table rows use a **tighter vertical cell padding** than the
standard v2 table — half the global row gap, same horizontal
padding — since the table is one input per cell and can run to
hundreds of reviewees, so the denser rows keep vertical scrolling
down. The rule is scoped to the reviewer surface; operator tables
keep the standard spacing.

### Above the table — heading + help block

The per-instrument heading is a `.rs-instrument-heading` flex row
carrying a title (H2) and an optional subtitle on the same baseline,
styled like the page header (H1 + deadline). Title and subtitle
content comes from `Instrument.short_label` and
`Instrument.description` respectively, with composition rules driven
by how many instruments the reviewer is assigned on:

| Case | Title (H2) | Subtitle (`.muted`, body-weight) |
|---|---|---|
| Multi-instrument, `short_label` set | `#{N}: {short_label}` | `description` if set, else nothing |
| Multi-instrument, `short_label` empty | `#{N}` (bare) | `description` if set, else nothing |
| Single-instrument, `short_label` set | `{short_label}` (no `#1:` prefix) | `description` if set, else nothing |
| Single-instrument, both empty | none — no heading row renders | n/a |
| Single-instrument, only `description` set | `{description}` | none |

The `#{N}` prefix is the safety-net default for multi-instrument
sessions: even with `short_label` unset, the reviewer still gets
"which page am I on" context. Single-instrument sessions don't need
the `#1` prefix; the H1 (session name) at the top of the surface
already establishes "this is the review."

The last row is a **deliberate legacy fallback**: a single instrument
with only a description puts that description in the H2 rather than
rendering no heading, so a session authored before `short_label`
existed still shows something. `instrument_heading`
(`app/web/views/_instruments.py`) carries it, and
`test_reviewer_view_helpers.py` pins it.

The view-shape returned by `_surface_context` exposes a structured
heading dict per instrument group:

```python
@dataclass(frozen=True)
class InstrumentHeading:
    title: str | None      # rendered as <h2>; absent when None
    subtitle: str | None   # rendered as a body-weight muted span; absent when None
```

The template renders the H2 heading row only when `heading.title`
is truthy. The instrument card (`.rs-instrument-card`) hosts the
heading + description **only**; the progress pills sit outside it, in
the right-flushed row described next.

**Per-instrument progress pills.** Two `.pill` spans sit in a
single right-flushed flex row (`.rs-progress-row`,
`justify-content: flex-end`) **just above the review table**,
not inside the instrument card. They share the row with the
per-field min/max/step "constraints" reminders
(`.rs-constraints muted`) so the reviewer's eye lands on
completion status alongside the formatting reminders. An *item*
is one response cell (one field for one reviewee):

- `Required items completed: {N}/{M}` — required field-cells filled
  vs total (`.pill-success` when `N == M`, else `.pill-warning`).
- `All items completed: {P}/{Q}` — every response cell filled vs
  total (`.pill-success` when `P == Q`, else `.pill-count`).

`_surface_context` adds a `completion` dict per instrument group
(`required_done` / `required_total` / `all_done` / `all_total`);
`required_done` is DB-accurate, derived from each row's
`missing_count`. The same layout is mirrored on the operator's
Band 2 preview (see `spec/instruments.md` § Band 2 — pills + the
JS-built `buildConstraints` block share the row and rebuild
together on every Band 3 / R toggle).

- **Help block** above the table (below the heading row), listing each
  response field that has both `help_text` set and
  `help_text_visible=true`. One shape, whatever the count: a
  `.rs-help-grid` row of half-width `.rs-help-card` items. **The family
  has no full-width solo variant, and must not grow one.** The
  per-instrument intro is itself a half-width card grid, so a lone help
  card belongs in column 2 beside the heading card; widening it to
  full width breaks that pairing. `.rs-help-card-solo` is therefore not
  part of the contract, and its absence is asserted by
  `tests/integration/test_reviewer_response_flow.py`.

Single-instrument sessions with both `short_label` and `description`
empty render no H2 at all, pinned by
`test_surface_single_instrument_no_description_renders_no_heading`.

### Columns

This column set applies to an ordinary per-reviewee instrument. A
**group-scoped instrument** renders a different column set — a
single composed `Group` column in place of Reviewee + display
columns; see "Group-scoped instruments" below.

In rendered order:

1. **Reviewee** (always first, mandatory; class `.rs-reviewee`):
   reviewee `name` in **bold**, `email_or_identifier` in `<code>`
   beneath. Both are sourced from the `Reviewee` row pointed at by
   the assignment.
2. **Display fields** (in operator-configured `InstrumentDisplayField.order`):
   one column per visible row in `display_fields_by_instrument`.
   Filtered to exclude duplicates of the always-rendered Reviewee
   identity column (i.e. `reviewee.name` /
   `reviewee.email_or_identifier` display fields are suppressed even
   if the operator added them, because they'd duplicate column 1).
   Each cell renders per the field's source:
   - `reviewee.profile_link` → `<a href="{value}">View</a>` when the
     value is non-empty; empty otherwise (no broken anchor).
   - `pair_context.{n}` and the rest → plain text.
   Header carries `class="rs-narrow"` for `profile_link` (URL
   columns are kept narrow); other display headers have no width
   modifier.
3. **Response fields** (in stored `InstrumentResponseField.order`):
   one column per response field. Header text is the field label;
   required fields get a trailing `*`. Header column-width hint is
   driven by the field's `data_type`:
   - `Integer` / `Decimal` → `class="rs-narrow"` (numbers are short).
   - `String` with `validation.max_length > 100` → `class="rs-textlong"`.
   - everything else → no width modifier.
4. **Status indicator** (trailing, narrow): only renders when
   `group.show_status_col` is true (i.e. when at least one row has
   `submitted_at` set or `show_acknowledge` is true after a
   missing-required Submit attempt). Cell content is icon-only:
   - `<span class="status-icon-complete" title="Complete">✓</span>`
     when the row's required fields are all filled.
   - `<span class="status-icon-incomplete" title="N required field
     missing">⚠</span>` when any required field is empty.

   **The icon is the whole cell — there is no per-row ``submitted
   YYYY-MM-DD HH:MM`` subtitle under it.** Submit stamps a single
   ``now()`` across every Response row for the reviewer in one go
   (see the ``app/services/responses`` submit path), so a per-row
   timestamp is always either NULL or uniform-for-the-reviewer;
   printing it per row repeats the session-level submission timestamp
   already shown on the reviewer summary page, once for every
   reviewee.
   ``Response.submitted_at`` itself stays in the data model: it
   drives ``is_complete`` rollups, audit-event counts, the
   session-status pill (``Submitted`` / ``Saved but not
   submitted`` / ``Draft``) on the overview card, and the summary
   page's session-level timestamp.

### Cell renderers

Response field input markup is driven by the field's `data_type`:

| `data_type` | Render |
|---|---|
| `String` with `validation.max_length > 100` | `<textarea rows="N">` where `N` is derived from `max_length` and the operator-set column width via `views.textarea_rows_for` (see below); `min-height: 44px` floor; `resize: vertical` so the corner-drag doesn't push the column out of its operator-defined width; preserves stored value. |
| `String` with `validation.max_length ≤ 100` | `<input type="text">`; the `maxlength` attribute reflects `validation.max_length`. |
| `Integer`, `Decimal` | `<input type="number">`; `min` / `max` / `step` reflect `validation`. |
| `List` | `<select>` over `validation.choices`, with an empty leading option (`value=""`) representing "no answer". |
| anything else | `<input type="text">` (defensive fallback). |

When the assignment isn't accepting (deadline closed or operator-
paused), every input renders `disabled`.

**Textarea height derivation.** Long-text textareas size their
initial `rows` attribute so a typical response — assumed to cluster
around **75%** of the configured `max_length` — fits at the column's
current width:

```
typical_chars = max_length * 0.5
chars_per_row = max(20, column_width_px / 8)
rows          = clamp(ceil(typical_chars / chars_per_row), 2, 8)
```

`column_width_px` comes from `Instrument.column_widths["rf_<id>"]`
(the per-cell width the operator sets via Band 2's column
grippers); when unset, the default is 224px (matching the
`td.rs-textlong { min-width: 14em }` CSS at the default 16px body
font). The 8 px/char ratio is calibrated against the proportional
sans-serif body font stack; the 0.5 factor is named at
`views/_instruments.py::_TYPICAL_RESPONSE_FRACTION`. Reviewers
retain native textarea corner-drag at runtime — this only sets
the initial height. The Band 2 preview cell in
`templates/operator/instruments_index.html` ships a JS port of
the same formula (constants kept in sync) so the operator's
preview matches what the reviewer will see.

**Cell vertical alignment.** Cells inside
`.rs-instrument-group` and `[data-new-model-band2-preview]` carry
`vertical-align: top` so multi-row textareas anchor at the top of
the row rather than centering vertically next to single-line
neighbours.

Stored values are read from `Response` rows keyed by
`(assignment_id, response_field_id)` and rendered as the input's
`value` (or selected `<option>` for `List`, or textarea body for the
long `String` variant).

### View shape

The route builds the table data in `_surface_context` as
`instrument_groups: list[InstrumentGroup]` where each group has:

```python
{
  "instrument": Instrument,
  "heading": str,
  "rows": [
    {
      "assignment": Assignment,
      "cells": [{"field": InstrumentResponseField, "value": str}, …],
      "display_cells": [{"field": …, "label": …, "value": …, "is_profile_link": bool}, …],
      "is_complete": bool,
      "missing_count": int,
      "submitted_at": datetime | None,
      "accepting": bool,
      "show_values": bool,
    },
    …
  ],
  "help_block_items": [InstrumentResponseField, …],
  "display_fields": [{"field": …, "label": …, "is_profile_link": bool}, …],
  "show_status_col": bool,
}
```

Keep this dict shape stable — the large-table ergonomics work
(see "Large-table ergonomics" below) builds on the same
payload, and it would also feed a future JS-driven grid
unchanged should one ever be adopted.

### Group-scoped instruments

A **group-scoped instrument** (`Instrument.group_kind` non-null)
renders differently. Its canonical design lives in
[`spec/instruments.md`](instruments.md) § Band 1 (the operator-
authoring side) and [`spec/assignments.md`](assignments.md) §
group-scoped fan-out (the storage + collapse-on-read side); the
reviewer-surface specifics:

- **One row per group, not per reviewee.** The reviewer's
  rule-eligible assignments for the instrument are partitioned
  into groups — two reviewees share a group iff they share the
  same value for every group-boundary tag (`responses.group_keys`).
  Each group is one table row. `_collapse_group_rows` in
  `routes_reviewer/_surface/_group_collapse.py` does the collapse; the
  lowest-id member assignment is the row's **representative** —
  the response inputs key off it (`response[{rep_id}][{field}]`)
  and the write fan-out spreads the answer to every member of the
  group.
- **`Group` identity column** replaces the `Reviewee` column and
  the per-reviewee display columns. It is composed from the
  group's boundary tag values on one line and, when the
  `RevieweeName` Display Field is Included, the member-name list
  on a second line — the first `GROUP_MEMBER_NAME_LIMIT` (10)
  names, then a `+N more` suffix. No separate display-field
  columns render.
- **Fixed table layout.** The group table is `table-layout: fixed`
  (`table.rs-group-table`): the `Group` column is pinned to a
  third of the table width (`th.rs-group { width: 33% }`), and
  the response columns auto-distribute the rest. A `max-width`
  on an auto-layout cell is only a hint browsers ignore, hence
  the fixed layout. Numeric response columns are pinned to a
  `ch`-width via `views.numeric_column_ch_width(field)` — the
  wider of the header label (plus the `required` mark + sort
  button) and the field's min/max digit span — so a small-range
  input (e.g. a 1-5 Rating) does not sprawl. Their per-type
  `rs-narrow` / `rs-textlong` hints are dropped (under fixed
  layout `width: 1%` would collapse the column).
- **One error / one missing entry per group.** Validation runs
  on the raw upserts before the write fan-out, and
  `_compute_missing_required` reports one entry per
  `(instrument, group_key)` — a bad or missing group answer
  surfaces once, not once per member.
- **Operator preview** renders group-scoped instruments collapsed
  the same way the reviewer surface does, because it goes through the
  same `_surface_context` path. There is deliberately **no**
  preview-only context builder: one that un-collapsed groups is
  exactly the drift the shared path exists to prevent.

The collapsed row carries the same dict shape plus a
`group_identity` block (`tag_line` / `member_names` /
`extra_count` / `show_members`) and a `group_label`; the
instrument group dict carries `is_group: bool`, which the
template branches on.

---

## Missing required flow

Submit is a **hard gate** on missing required, session-wide. There is
no acknowledge-and-submit-anyway path; the reviewer must fill (or the
operator must loosen the `required` constraint on) every required
field before the submit lands.

1. Reviewer hits Submit on any page with at least one required field
   blank anywhere in the session.
2. Server returns 400 + re-renders the page they were on (whichever
   `{page_n}` they submitted from) with the full-width
   `.rs-missing-card` below the overview card, enumerating the gaps as
   `Page N: Reviewee X — field Y` so the reviewer knows where to
   navigate.
3. The reviewer fills the gaps (using the per-page navigation
   to reach each one) and re-clicks Submit. There is no checkbox,
   no `show_acknowledge` template flag, and no
   `acknowledged_missing` audit detail.

The card carries a Cancel link back to the originating instrument
page so the reviewer can also dismiss the warning without scrolling
through the form (URL bar leaves the POST-only `/submit` endpoint
behind).

---

## Lifecycle gating

A reviewer can only mutate state (Save / Submit / Clear) when **all
three** of the following hold:

1. `ReviewSession.status == "ready"` (operator has activated the
   session).
2. The assignment's `Instrument.accepting_responses == true` (the
   per-instrument acceptance switch hasn't been turned off).
3. `now() < ReviewSession.deadline` (deadline hasn't passed; null
   deadline counts as open).

Failing any of those three returns **HTTP 403** on Save / Submit /
Clear POSTs.

GET requests behave differently depending on which gate fails:

- **Session not yet `ready`** (the operator has prepared the
  session and may have already sent out invitations, but hasn't
  activated yet). The route
  short-circuits to the **pre-open page**
  (`reviewer/pre_open.html`): session name in the h1 with an
  "opens later" suffix, an info banner explaining the review
  hasn't opened yet, the deadline + zone if one is set, and a
  link back to the reviewer dashboard. No response form is
  rendered. Applies for `draft` and `validated` lifecycle states
  alike.

- **Session `ready`, response window closed** (per-instrument
  `accepting_responses=false`, typically because the deadline
  passed). The page still renders so the reviewer can read prior
  state. The editing surface degrades to read-only:

  - Every input renders `disabled`.
  - In both action rows: Save / Cancel / Submit hide, plus the
    vertical divider that separated them. The Prev / Next page-nav
    links stay so the reviewer can walk through their other
    instruments (which may or may not also be closed).
  - The Danger Zone card hides (no Clear all).
  - A `.banner.banner-warning` lands inline in the overview card
    explaining the state, e.g. "This session is no longer
    accepting responses." Two variants depending on the
    operator's per-instrument visibility flag:
    - "Your previously saved values remain visible below in
      read-only form." (operator left
      `responses_visible_when_closed=true`).
    - "Your previously saved values are hidden by the operator's
      visibility setting." (operator set
      `responses_visible_when_closed=false`).

  This closed-state machinery deliberately stays on the surface
  template (rather than redirecting to a separate "closed" page)
  so the `responses_visible_when_closed` toggle keeps working —
  a separate template would have to re-render the response data
  to honour the toggle.

### Lazy deadline-close

Deadline expiration is observed lazily, not via a scheduled job.
Every reviewer GET / POST and every operator instruments-page GET
runs `lifecycle.observe_deadline(...)` before reading state. The
first observer past the deadline:

- Flips `Instrument.accepting_responses` to `false` on every
  instrument in the session.
- Stamps `Instrument.deadline_closed_at = now()`.
- Emits one `instrument.closed` audit event per instrument with
  `detail.reason = "deadline"`.

The lazy-close is idempotent — subsequent observers see
`deadline_closed_at` already set and skip the side-effect.

---

## Identity matching

A signed-in user is matched to `Reviewer` rows by **case-insensitive
email equality** (`casefold()` both sides). Only `Reviewer` rows
with `status == "active"` grant access; inactive / removed reviewers
are invisible.

Both rules live in `app/services/responses` (and the per-session
lookup that drives the surface route). The reviewer dashboard, the
session surface, and the invitation-landing email-match check all
use the same rule.

A user can have at most one active `Reviewer` row per session. A
session can have multiple reviewers, each tied to a distinct user.

The same **case-insensitive email equality** rule applies to
`Reviewee.email_or_identifier` (for `require_reviewee_in_session`)
and `Observer.email` (for `require_observer_in_session`) — see
`app/web/deps.py`. The `/me` dashboard uses the same pattern for
its cross-role union query (inline in
`app/web/routes_reviewer/_dashboard.py`).

---

## Operator preview mode

The operator-side preview lives at
`/operator/sessions/{id}/preview-surface/{page_n}` and is reached from
the Previews hub picker card's "Open full preview" button. The route
renders this template through the same `_surface_context` plumbing the
live reviewer route uses, with three `preview_mode=True` adjustments:
the deadline observer is skipped (no DB mutation on a deadline
crossing), `accepting=True` is forced on every row so the form renders
interactive regardless of session lifecycle, and the action-row
Prev/Next URLs are rewritten via a callback so they point back at the
operator-side preview route. **The hub itself carries no embedded copy
of the surface** — a second rendering path is the one thing a
production-parity preview cannot afford. `/preview` (singular) is a
permanent (308) redirect to `/preview-surface/1`, never to a fragment
on the hub.

In preview mode:

- The chrome `top_bar` block calls `super()` so the operator chrome
  (with breadcrumb back to the session) renders instead of the
  reviewer top bar variant.
- `body_class` drops the `reviewer` modifier (stays `body.ui-v2`).
- The preview-mode banner (`.banner.banner-info`) renders at the top
  of the body: "**Preview** — not visible to reviewers. This page
  is operator-only and bypasses session-status / deadline /
  acceptance gates."
- The reviewer write-path `<form>` wrapper is replaced by a plain
  `<div>` so no `formaction=` can re-target a write endpoint. The
  action row still renders (so the operator sees the form chrome
  exactly as the reviewer would), but Save / Cancel / Submit
  render as inert disabled `<button>` elements; Prev / Next remain
  functional and walk the operator through every operator-defined
  page. The danger zone (Clear all responses) doesn't render.
- Inputs render enabled (because `accepting=True` is forced), so
  the operator can type into the form to test it; their keystrokes
  go nowhere because the surrounding `<form>` is a `<div>` and the
  Save/Cancel/Submit buttons are disabled.
- The overview card renders normally — `_surface_context` builds
  the same per-page status pills the reviewer would see.
- **Real-row rendering.** The preview shows the picker-selected
  reviewer's real assignments (no synthetic-row padding). When
  `?reviewer_email=…` is unset, the route defaults to the first
  reviewer in the session (alphabetical-by-email); an unmatched
  value redirects back to the Previews hub with the bad query
  preserved so the picker's "No reviewer matched" hint renders.
- **Read-only side-effects.** The preview GET emits no audit
  events and **does not** call `lifecycle.observe_deadline(...)`
  — opening a preview must never flip `accepting_responses=false`
  even if the session deadline has lapsed.

---

## Dashboard (`/me`)

The participant lobby — where a signed-in user lands directly (no
invitation token) or via "My Reviews" from any session-scoped
chrome. Lists **every session the signed-in user touches in any
participant role** (reviewer / reviewee / observer), as a
cross-role union. The query hits all three rosters
(`reviewers`, `reviewees`, `observers`) with case-insensitive email
matching; only `status == "active"` rows contribute; the result is
deduplicated per session and sorted by `session.updated_at`
descending.

**The `reviewee` role additionally requires a currently-resolving
visibility grant.** An active, email-identified
roster row is necessary but not sufficient: at least one instrument in
the session must grant the reviewee a mode under the windows open right
now (`visibility_policies.reviewee_has_current_grant`). Without one the
`reviewee` entry never enters `roles`, so the session contributes no row
at all unless the user holds another role on it — the role is gated, not
the row. Reviewers and observers are not grant-gated. Full contract in
`spec/participant_model.md` §5 and `spec/role_landing_and_visibility.md`
§4.

Reviewer-specific columns (Reviewer status, deep-link target)
populate only when the user is an active reviewer on that session;
reviewee-/observer-only rows show `—` in those cells.

- **H1** — "Your reviews".
- **Body** — single `.card` containing a `<table>` (one row per
  session). **Eight columns:**
  - **Session** — session name, with per-role pills on a second
    line below it. The session name itself links to
    the highest-priority reachable role in order Reviewer →
    Reviewee → Observer (first role whose `enabled == True`);
    plain text when no role is reachable. Each role pill is an
    `<a class="pill pill-role-{role}">` anchor when reachable,
    a plain `<span>` otherwise.
  - **Start** — `sessions.activated_at` formatted in the
    session's resolved zone, rendered as a `pill-count` chip
    (neutral data); `<span class="muted">—</span>` when null.
  - **End** — `session.deadline` formatted in the session zone,
    rendered as a `pill-error` chip (red) once `now() >=
    deadline` and `pill-count` (neutral) otherwise;
    `<span class="muted">—</span>` when null.
  - **View responses** — placeholder; renders `<span
    class="muted">—</span>`, and **stays one**: the access-window
    question it would answer is already answered by the row. A reviewee
    row exists only while a grant currently resolves, so a dedicated
    window column would restate what the row's presence says.
  - **Until** — placeholder; renders `<span
    class="muted">—</span>` today. Will show the computed
    close time of the results-viewing window once wired.
  - **Timezone** — `pill-count` chip carrying the compact
    GMT-offset (e.g. `GMT+8`) with the raw IANA id (e.g.
    `Asia/Singapore`) on hover via `<abbr title="...">`.
  - **Session status** — pill (`not opened` / `open` /
    `closed`) — see vocabulary below. An **archived** session
    additionally renders a muted `archived` pill beside the
    status: `not opened` is true of a draft session and of an
    archived one for opposite reasons, and the companion says
    which. A companion, **not a fourth value** — the
    `session_status` string is what link enablement tests
    (`!= "not opened"`), so a new value would re-link the
    reviewer surface on an archived session. It sits inline and
    wraps below the status on its own when the column narrows
    (side by side at 1440px, stacked at 1024px and 820px). No CSS
    is added for this — `.pill` is
    `inline-block` with a right margin, so the wrap is the
    browser's, not a breakpoint the app defines. For reviewer rows:
    computed via `lifecycle.session_status_for_reviewer`.
    For reviewee / observer-only rows: computed from session
    lifecycle alone (no reviewer-assignment check).
  - **Reviewer status** — pill (`not started` / `in progress` /
    `submitted`) computed from the reviewer's `Response` rows;
    plus a paired `(N/M)` chip in the same colour. Renders `—`
    when the user is a reviewee / observer only.
- **Empty state** — when the user has no active roster rows
  in any session in any role: a single `.card` with `.muted`
  text "You have no pending reviews ({user.email})."

### Cross-role union and reachability

The route (`app/web/routes_reviewer/_dashboard.py`
`reviewer_dashboard`) builds `role_links` per session — one entry
per role the user holds:

| Role | Target URL | Reachable today |
|---|---|---|
| `reviewer` | `/me/sessions/{id}/summary` (when submitted) or `/me/sessions/{id}/1` | `session_status != "not opened"` |
| `reviewee` | `/me/sessions/{id}/results` | `True` whenever the role is present — the role is itself conditional on a currently-resolving grant, so reaching this row means there is something to link to |
| `observer` | `/me/sessions/{id}/collation` | `True` in every lifecycle state **except `archived`**: archive closes every non-operator grant, so the page is empty by construction there and the row renders unlinked. Per-instrument render gated on Band 3 + the session window inside `build_observer_collation_context` (W17) |

The session-name link uses the first reachable role in priority
order (Reviewer → Reviewee → Observer). Unreachable roles render
as inert `<span>` pills.

The cross-role union is built inline in `_dashboard.py` rather than behind a shared service helper.

### Session-status pill vocabulary

Computed by
`app/services/session_lifecycle.py::session_status_for_reviewer`
— non-mutating; the deadline check flows through
`session_accepts_responses` directly so a past deadline reads
as `closed` even on instruments whose `accepting_responses`
flag hasn't been flipped yet by `observe_deadline`.

| Pill | Style | Condition |
|---|---|---|
| `not opened` | `pill-info` (blue, pending) | Session is `draft` or `validated` — not yet activated. Session column renders plain text (no link). |
| `open` | `pill-success` (green) | Session is `ready` AND at least one assigned instrument is `accepting_responses` AND deadline (if set) hasn't passed. Session column links to the surface. |
| `closed` | `pill-error` (red) | Session is `ready` AND no assigned instruments are accepting (deadline passed or instruments manually closed). Red matches the past-deadline pill in the End column — both say *the window has closed for this reviewer* — and the muted `pill-lifecycle-archived` grey it replaced read as plain text rather than a pill. Session column **still links** so the reviewer can read their saved responses on the read-only surface. |

`closed` also resolves from `session.status == "expired"`, and must:
an expired session reports `closed` rather than `not opened` precisely
so the dashboard keeps its link live, which is what lets the reviewer
still reach `/summary` and the read-only surface after the operator has
closed the session.

### Reviewer-status pill vocabulary

Computed by `app/services/responses::session_pill_for_reviewer`:

| Pill | Style | Condition |
|---|---|---|
| `submitted` | `pill-success` | Every required field on every assignment in the session has a `Response.submitted_at` timestamp. The paired counter chip is also `pill-success`. |
| `in progress` | `pill-warning` | At least one `Response` row exists, but the `submitted` rule doesn't hold. Counter chip is `pill-warning`. |
| `not started` | `pill-info` | No `Response` rows exist for this reviewer in this session. Counter chip is `pill-info`. |

Reviewer Status renders independently of Session Status — even
on a `not opened` session the reviewer sees "Reviewer Status:
not started", which reads naturally alongside the session's
pre-open state. The "Edit / Re-submit" affordance lives on the
surface itself — hitting Submit once doesn't lock the form.
Submitting again replays the same logic and re-stamps
`submitted_at`.

### One row per session, never per page

A multi-page session contributes **one** row to the dashboard table —
there are no per-page sub-rows under it. Page navigation is the response
surface's own job (Prev / Next / `Page N of M`), and a dashboard that
also enumerated pages would carry a second, staler copy of the same
per-page state.

---

## Per-session summary (`/me/sessions/{id}/summary`)

A read-only capstone page that renders once the reviewer has
submitted every assigned row on a session. The surface's
`submit_redirect_url` graduates to
this URL when a submit closes out the last instrument; partial
submits keep the existing "redirect back to surface"
behaviour. The page also stays reachable later from the
dashboard's Session column once Reviewer Status is
`submitted`.

- **Gate** — `responses.reviewer_session_state.pill_state ==
  "submitted"`. Otherwise redirects to `/me` with no
  flash banner; the reviewer can re-submit from the surface.
- **H1** — "Your responses — {session.name}".
- **Caption** — "Submitted on {YYYY-MM-DD HH:MM} ({zone})"
  built from `MAX(response.submitted_at)` across the
  reviewer's rows.
- **Action row** — primary "Download my responses (CSV)"
  button linking to `/me/sessions/{id}/summary.csv`, a
  "Recall my submission" control (`POST /me/sessions/{id}/recall`),
  and a secondary "Your reviewer dashboard" link. Recall renders
  only while the session is still `ready` (`can_recall =
  lifecycle.is_ready`); it rolls the reviewer's submission back to
  draft (nulls `submitted_at`) and 303s to the surface so they can
  keep editing. Handled by `reviewer_recall` in
  `routes_reviewer/_surface/_routes.py`.
- **Sections** — one `.card` per instrument the reviewer
  responded on, in `(Instrument.order, Instrument.id)` order.
  Each section's `<h2>` shows the instrument's short label +
  full name (when both are set); the body is a `<table>` whose
  header is `Reviewee` + one column per response field
  (carrying the field's operator-given label, in the
  instrument's authored field order). Cells render the
  response value or `<span class="muted">—</span>` when blank.
  Group-scoped instruments collapse to one row per group with
  the composed group identity in the Reviewee column,
  mirroring the surface's existing collapse logic.
- **CSV download** — `/me/sessions/{id}/summary.csv`
  emits `{code}_my_responses.csv` (filename via
  `app.services.extracts.filename`). Same 21-column shape as
  the unified Responses CSV (see `spec/csv_contracts.md`
  §2.4), scoped to one reviewer; a per-instrument preamble +
  field dictionary appears for every instrument the reviewer
  responded on. Builds via
  `app.services.extracts.responses_extract.serialize_reviewer_session_summary`,
  which reuses 18H Part 2's `_response_row_tuple` so a
  per-cell rename here flows through to every related file.

### Pre-open page (`/me/sessions/{id}/{page_n}` on a not-yet-ready session)

A dedicated **pre-open** rendering serves a reviewer who follows an
invitation token (or a dashboard link) to a session that's been
Prepared (`validated`) but not yet Activated. Instead of 403-ing or
dropping the reviewer into a silently-disabled form, the
route returns `reviewer/pre_open.html` — h1 with "{session
name} — opens later", an info banner explaining the review
hasn't opened yet, the deadline + zone when one is set, and a
link back to the reviewer dashboard. See
`spec/lifecycle.md` §4.1 "The reviewer write-path predicate"
for the gate semantics.

---

## Reviewee results (`/me/sessions/{id}/results`)

`GET /me/sessions/{id}/results` + `POST /me/sessions/{id}/results/acknowledge`.

**Gate** — `require_reviewee_with_current_grant` in
`app/web/deps.py`, shared by the GET **and** the
`POST …/acknowledge` companion. It composes two conditions:

1. the roster check from `require_reviewee_in_session` — an active
   Reviewee row whose `email_or_identifier` is a valid email matching
   the user's, case-insensitively; confidential reviewees (non-email
   identifiers) never pass; **and**
2. `visibility_policies.reviewee_has_current_grant` — at least one
   instrument granting them a mode under the windows open right now.

**On any failure: a bare HTTP 404**, byte-identical to an unknown
session id. Unknown session, not a reviewee here, an inactive row, a
non-email identifier, and a reviewee with nothing currently granted are
one outcome with one body — a reviewee granted nothing has to be
indistinguishable from a stranger. **Not 403, and no role-naming
`detail`**: either tells the caller both that the session exists and
that they are on it, which is the disclosure the gate exists to refuse.

**No pre-release scaffolding.** A policy authored on `after_release`
whose window has not opened must render nothing — not the section with
the reviewer rows visible and only the values hidden. Rows without
values still name the people lined up to review the reviewee, before
anything has been granted to them. A preview of what a reviewee *will*
see belongs on an operator surface.

**Body** — per-instrument sections built by
`app/web/views/_reviewee_results.py::build_reviewee_results_context`,
filtered through the per-instrument `reviewee` visibility policy.
Three rendering modes:

- **raw** — one row per reviewer, identified (name + email in the identity column).
- **anonymized** — same per-row table, every identification cell (Reviewer + display fields) replaced with a muted em-dash.
- **summarized** — one aggregate row; identity column header "Summary" carrying two counts; per-field cells per data type (Integer/Decimal: Average / Median / Min / Max / N; List: per-choice frequency; String: total + average length). Em-dash placeholders at zero responses.

Full mode / window semantics in `spec/participant_model.md` §4.1 and `spec/visibility_policy.md`.

**Acknowledge card** — always rendered at the foot; bottom-right half-width, blue emphasis (`rs-acknowledge-card` in `base.html`). Checkbox gates the submit button; post-acknowledgement collapses to a confirmation strip + `pill-success` in the page header. `POST …/acknowledge` calls `reviewees_service.acknowledge_results` (idempotent, emits `reviewee.results_acknowledged`), 303 → GET.

Route: `app/web/routes_reviewer/_results.py`. Registered before
the catch-all `_surface` routes in
`app/web/routes_reviewer/__init__.py` so `/results` is not
captured as a `{page_n}` value.

---

## Observer collation surface (`/me/sessions/{id}/collation`)

`GET /me/sessions/{id}/collation`.

**Gate** — `require_observer_in_session` in `app/web/deps.py`:
the authenticated user must have an active Observer row whose
`email` matches (case-insensitive). On mismatch: a bare **HTTP 404**,
byte-identical to an unknown session id. Not a 403, and no role-naming
`detail` — either confirms the session exists to a caller who should
not learn that.

Observers are **not** grant-gated the way reviewees are: being appointed
an observer is not a disclosure *about* the observer, so the surface
opens in every lifecycle state and simply renders nothing until their
window does.

**What renders** — reviewer-surface chrome (`reviewer/collation.html`)
plus the per-instrument 3-row collation table (reviewer-side
aggregates / reviewee-side aggregates / conditional CSV download).
W17; see `guide/archive/observers.md` and the cohort-consumer routes in
`app/web/routes_reviewer/_collation.py`.

Route: `app/web/routes_reviewer/_collation.py`. Also registered
before the `_surface` catch-all.

---

## Role-navigator chip strip

A shared partial rendered below the session-name H1 on
four role-specific surfaces: the response surface
(`review_surface.html`), the summary page (`summary.html`),
the results page (`results.html`), and the collation page
(`collation.html`).

**Template partial** — `reviewer/_role_chips.html`. Included in
each of the four surfaces; suppressed in `preview_mode` on the
reviewer surface (operator preview doesn't have role context).

**Builder** — `build_role_chips(db, *, user, review_session,
active_role)` in `app/web/routes_reviewer/_shared.py`. Queries
all three rosters for the signed-in user's email
(case-insensitive, `status == "active"` only), constructs a chip
list in `_ROLE_PRIORITY` order (`reviewer` → `reviewee` →
`observer`), and returns only the roles the user actually holds.

Each chip carries:

| Key | Type | Meaning |
|---|---|---|
| `role` | `str` | `"reviewer"` / `"reviewee"` / `"observer"` |
| `target` | `str` | URL this chip links to (only used when `active == False` and `enabled == True`) |
| `active` | `bool` | `True` for the current surface's role — full colour, no anchor |
| `enabled` | `bool` | `True` when the role's surface is currently reachable |

**CSS** — `.rs-role-nav` strip in `base.html` with
`.rs-role-nav-active` (full colour, current role) and
`.rs-role-nav-muted` (greyed-out, disabled or inactive role)
modifiers.

Reachability mirrors the dashboard's `role_links.enabled` logic, for
all three roles rather than only the reviewer:

| Role | Chip |
|---|---|
| reviewer | Reachable when `session_status != "not opened"`; greyed otherwise. |
| reviewee | **Omitted entirely** unless `visibility_policies.reviewee_has_current_grant` resolves — not greyed. A greyed chip still says *you are a reviewee on this session*, which is the disclosure `/me` stops making, so the chip goes with the role. |
| observer | Present for any active observer, **greyed on an archived session** (`lifecycle.is_archived`), live otherwise. Being an observer is not a disclosure about the observer, so this one greys rather than disappearing. |

**`build_role_chips` must not answer from roster membership alone.** A
membership-only answer hands a user who holds another role on the
session a live Reviewee chip pointing at the 404 `/results` gives them
— the same contract applied on `/me` and not one door over. Each
surface asks the question for itself: a caller on `/collation` has
passed the observer gate and nothing else, so their reviewee chip needs
its own answer.

**W17 (observer)** still applies the `responses_release_at` +
`responses_release_until` gates inside the per-instrument render only —
instrument cards fall through to the empty state when the window is
closed, with no route-level refusal.

**W16 (reviewee) does not work that way.** The window question is asked
at the *route*: with no instrument granting anything, `/results` answers
404 rather than rendering an empty page that names the session to its
subject. Inside an open page the per-instrument resolver still decides
what renders, so a sparse body is normal.

---

## Invitation landing (`/me/invite/{token}`)

Token redemption + identity check. Lookup is by SHA-256 hash; the
raw token is never persisted, only mailed.

Behaviour:

1. Easy Auth must be signed in (otherwise the platform redirects to
   sign-in and back).
2. Look up the invitation by `sha256(token)`. Not found → **404**.
3. **Email match check** — case-insensitive comparison of the
   signed-in email (`casefold()`) against `Invitation.reviewer_email`.
   On mismatch, render `invite_mismatch.html` (HTTP 403; see
   "Invitation-mismatch page" below).
4. On match, stamp `Invitation.opened_at` once (idempotent on
   subsequent visits — only the first call writes), emit one
   `invitation.opened` audit event on first open, and 303 →
   `/me/sessions/{id}/1`.

### Invitation-mismatch page

A single `.banner.banner-warning` explaining the email mismatch,
followed by a `.btn-pair` with two Secondary anchors:

- **Sign-in details** → `/auth/me/debug` (so the reviewer can confirm
  which account they're signed in as).
- **Your reviewer dashboard** → `/me`.

The remedy is to sign out and sign back in with the invited
account. This is the only reviewer-side page that returns a non-200
status under normal flow **for a caller who is in the right place** —
a 403, and unrelated to the session-scoped gates. Those answer 404 to
anyone they refuse, but that is a caller in the wrong place rather than
a normal flow.

The mismatch page renders with the reviewer chrome variant
(`body.ui-v2 reviewer`) so the operator's identity is suppressed
from the top bar.

---

## Button labels

| Where | Label |
|---|---|
| Action row, page-level slot | `Save` |
| Action row, page-level slot | `Cancel` (hook: `data-rs-discard`) |
| Action row, page-level slot | `Page #{N}: {Instrument.short_label}` when the operator has set a short label; bare `Page #{N}` otherwise |
| Action row, review-level slot, after the divider | `Submit` |
| Danger Zone | `Clear all` — copy explains "every response across every page" |

The only other reviewer-side labels are `Sign out` and `My Reviews`.

### Friendly short label vs. long description

The operator authors **two distinct strings** per instrument, both
optional:

- **`Instrument.short_label`** (`String(32) | None`, nullable) — the
  operator's reviewer-facing framing. Lands on Page button labels
  (`Page #{N}: {short_label}`) and as the per-instrument H2 title.
  Capped at 32 characters at the schema layer so button rows don't
  wrap on typical viewports.
- **`Instrument.description`** (`String(2000) | None`, nullable) — the
  longer per-instrument blurb. Lands as the subtitle next to the H2
  title above each table.

The system handle `Instrument.name` (`String(255)`, auto-generated
as `instrument_N` on instrument create) is **not** reviewer-facing.
It carries audit-event copy and is otherwise invisible.

The 32-char ceiling on `short_label` is a **Setup-side concern** —
this surface trusts the value it's given, and the Instruments Setup
page enforces the cap at create / edit time. As belt-and-braces
against a value that slipped past it, Page buttons carry
`max-width: 16em; text-overflow: ellipsis`.

---

## Out of scope

The following are deliberately deferred. They are not implemented
today but the surface is designed so they can be added later without
re-architecting; see "Designed-for-extensibility" below.

- **`beforeunload` warning** when the form is dirty.
- **Standalone submission-confirmation page for a *partial* submit.**
  A submit that closes out the whole session already has one — the
  per-session summary page. A submit that leaves pages outstanding
  returns to the surface, where the per-page `submitted` pill in the
  overview card and the status column's per-row complete icon are the
  whole signal.
- **Large-table ergonomics** (cell autosave, return-to-place,
  filter-to-incomplete) — owned by Segment 17B, as targeted
  progressive enhancement. A wholesale JS data-grid swap (AG Grid or
  equivalent) is *not* planned; it is overkill for this surface and is
  recorded as an aspirational possibility in
  `guide/deferred_consolidated.md`. See "Large-table ergonomics"
  below.

---

## Designed-for-extensibility

Notes on how this surface keeps the three deferred features above
non-risky to add later. Each item lists the design call this spec
makes today + the small follow-on the deferred work needs.

### beforeunload warning

- **Today.** There is no dirty-tracking and no `beforeunload` guard.
  Every navigation is a server round-trip that drops unsaved typing
  on the current page: **Prev / Next**, **Cancel** (a GET reload),
  **browser-close**, **tab-close**, **address-bar change**, and
  **the chrome's `My Reviews` link** all lose the current page's
  unsaved edits with no prompt. The reviewer avoids loss by clicking
  Save before navigating.
- **Design call.** The template already renders the hooks the
  enhancement needs: `data-rs-save` on Save, `data-rs-discard` on
  Cancel, and a `data-rs-saved-value` baseline on every input. An
  inline `<script>` can read those to add per-page dirty tracking
  (Save-disable-until-dirty + in-place discard) and a `beforeunload`
  listener that prompts only when the form is dirty, skipping the
  intentional-discard controls.
- **Shape of the guard.** A per-page dirty marker, an intentional-nav
  flag raised by Save and Cancel so the app's own controls never
  trigger the prompt, and one `beforeunload` listener registered once.
  Both the dirty gate and the intentional-nav escape are load-bearing
  (see "How the surface works" above).
- **What lands later.** A new inline `<script>` block wiring the
  `data-rs-*` hooks — dirty tracking, in-place discard, and the
  `beforeunload` handler. No template restructuring needed; the
  markup hooks are already in place.

### Standalone submission-confirmation page

- **Where the redirect goes.** A submit that closes out the whole
  session lands on `/me/sessions/{id}/summary`, the read-only capstone
  page specified above. A submit that leaves pages outstanding returns
  to the surface, with no flash banner: the per-page `submitted` pill
  in the overview card and the status column's per-row complete icon
  are the signal.
- **Design call — one helper owns the target.** The submit route's
  redirect target is computed by `submit_redirect_url(...)` rather than
  inlined at the call site, so a new post-submit destination lands
  without touching the submit handler, its validation or its audit
  write.
- **Deferred: a confirmation page for a partial submit** — a
  "page 2 of 4 submitted" surface rather than a silent return. One
  branch in the helper plus one template; the surface itself does not
  move.

### Large-table ergonomics

`spec/visual_style_rrw.md` "Response form layout and instrument
pacing → Large-table ergonomics" pins the following as first-class
requirements (since the app's positioning depends on tabular review
artifacts at scale): auto-save, return-to-place, visible progress,
sticky column headers, filter-to-incomplete, keyboard navigation,
and column-type ergonomics. **Segment 17B owns these**, pursued as
targeted progressive enhancement (debounced `fetch` to `POST /save`,
small inline scripts, CSS) — *not* a JS data-grid framework. (Sticky
column headers are the one item ruled out — see below.) A wholesale
grid swap (AG Grid or equivalent) is off the roadmap as overkill, and
recorded as an aspirational possibility in
`guide/deferred_consolidated.md`. Notes on how the surface stays
compatible either way:

- **Today.** Per-instrument rows render as a plain `<table>` inside
  `.table-scroll`. Column-width hint classes (`.rs-narrow` /
  `.rs-reviewee` / `.rs-textlong`) on `<th>` / `<td>` carry the
  responsive sizing. The data driving each row is built in
  `_surface_context` as a list of dicts with stable, serializable
  keys (`assignment`, `cells`, `display_cells`, `is_complete`,
  `missing_count`, `submitted_at`, `accepting`, `show_values`).
- **Design call.** Keep all table-specific markup confined to
  `review_surface.html`; route handlers and view-shape adapters never
  emit HTML. Field metadata (label / data_type / validation) ships
  alongside the row data, so the ergonomics work needs no route or
  view-adapter change — and the same payload would also feed a
  JS-driven grid unchanged, should one ever be adopted.
- **Visible progress.** The session-wide status pill plus the
  per-instrument `Required items completed` / `All items completed`
  pills carry it (see "Session-wide status pill" and "Above the table"
  above). The action row is ordered Save / Cancel / Submit / divider /
  page navigation.
- **Keyboard navigation.** Tab walks cells across a row, which the
  browser gives for free. **Enter moves focus down a column and
  Shift+Enter up it**, and the handler that does so carries two
  obligations: Enter anywhere in the table must not submit the page
  `<form>`, and Enter inside a `<textarea>` must stay a newline.
- **What lands later.** Return-to-place (preserve scroll position
  across save / reload) is the remaining ergonomics item. Cell
  autosave and filter-to-incomplete are deferred to
  `guide/deferred_consolidated.md` — pure progressive enhancement,
  built only if pilot feedback asks for them. **None of these is
  gated on any other**: each is an independent inline script against
  the markup hooks the surface already renders, and treating them as
  one all-or-nothing bundle is what a grid-library framing does to
  them.
- **Ruled out — sticky column headers.** `visual_style_rrw.md` pins
  them as first-class; they do not work on this surface and are not
  attempted. `position: sticky` on the `<th>` row does nothing useful
  here: the `.table-scroll` wrapper's `overflow-x` forces an
  `overflow-y` scroll context, so the header sticks relative to that
  wrapper rather than the window — and the wrapper has no height, so
  it never scrolls internally. The only working fix is to give the
  table its own vertical scroll viewport (a `max-height` box),
  turning a long reviewee list into an internal scroll region; that
  scroll-model change is not worth a sticky header. The surface keeps
  whole-page scroll and a non-sticky header.

---

## The bare-session URL is load-bearing

`GET /me/sessions/{id}` carries no page segment and **must** 303 to
`/me/sessions/{id}/1`. Three classes of caller depend on it and none of
them can be updated:

- **Invitation emails already sent** embed the token URL
  (`/me/invite/{token}`), which lands on `/me/sessions/{id}` once Easy
  Auth resolves.
- **Bookmarks and returning reviewers** hold the same bare URL.
- **Reviewer dashboard rows** are the one caller that *can* be
  updated, and `reviewer/dashboard.html` links straight at page `1`.

No data migration is involved — the fallback is the whole mechanism.
