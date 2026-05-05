# Reviewer surface — functional + visual spec

Specification of the reviewer-facing app — the pages a signed-in
reviewer sees when they follow an invitation link or visit `/reviewer`
directly. The response surface (`/reviewer/sessions/{id}/{position}`)
is the page they spend ~all their time on; the dashboard
(`/reviewer`) and invitation-landing (`/reviewer/invite/{token}`)
exist to land them on it.

This spec rewrites the response surface around **multi-instrument
awareness**: the URL carries an explicit instrument segment, the page
renders one instrument at a time, and a page-actions row lets the
reviewer move between instruments. Single-instrument sessions are a
degenerate case of the same model.

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
- `app/web/templates/reviewer/review_surface.html` — current
  implementation (single-form-multi-instrument-stack); this spec is
  the target.

---

## URL pattern

```
GET  /reviewer/sessions/{session_id}/{instrument_position}
POST /reviewer/sessions/{session_id}/{instrument_position}/save
POST /reviewer/sessions/{session_id}/{instrument_position}/submit
POST /reviewer/sessions/{session_id}/{instrument_position}/clear
```

`{instrument_position}` is the **1-indexed position** of the instrument
within the session (`Instrument.order`-sorted, then `Instrument.id`).
Position is preferred over the DB id because:

- It produces stable, predictable URLs for the reviewer (Page 1 / Page
  2 / …).
- The "Page N" label in the UI matches the URL segment.
- Operators rarely reorder instruments after activation; if they do,
  bookmark URLs simply land on whichever instrument now sits at that
  position, which is reasonable behavior.

Single-instrument sessions still carry the segment: the only valid
position is `1`. `GET /reviewer/sessions/{id}` (no position) **303s to
`/reviewer/sessions/{id}/1`** so existing invitation links and dashboard
rows keep working.

Out-of-range positions (e.g. `/reviewer/sessions/5/9` when the session
has only 2 instruments) return **404**.

The reviewer dashboard at `/reviewer` always links each row to position
`1`, since the dashboard summarises the session as a whole and Page 1 is
a safe default landing.

---

## Page anatomy

Top-to-bottom, the page renders:

1. **Top bar (reviewer chrome variant)** — per
   `spec/visual_style_rrw.md` "Reviewer-facing pages → Top bar". "Review
   Robin" identity (no version, no breadcrumb), user menu with "Signed
   in as …" + optional "My Reviews" + "Sign out".
2. **Preview banner** — `body.ui-v2` only (operator preview mode
   reuses this template); rendered as `.banner.banner-info`.
3. **Page header** — `.rs-page-header` flex row carrying the session
   name as H1 plus the deadline inline as `.muted`. (D7 — settled in
   Segment 11D PR C and adjusted post-merge.)
4. **Description + status bar** — a `.bottom-grid` 2-column row with:
   - **Description card** — half-width `.card.rs-description-card`
     flushed left, only when `session.description` is set. Collapses
     to full width below the 800px breakpoint.
   - **Flash + status panel** — half-width on the right. Always
     renders (collapses to full width below 800px). Hosts:
     - Per-page status pills — one pill per instrument labelled
       e.g. `Page 1: in progress`, `Page 2: complete`. State
       computed server-side from response data (see "Per-page status"
       below).
     - Transient flash banners (saved / submitted / missing-required
       / session-closed) inline within the panel when applicable;
       they do not push other layout around.
5. **Review-level action row (top)** — single right-flushed row
   carrying just `Submit` (Primary). Submit is review-session-wide;
   it commits every saved response across all instruments. (See
   "Form scope" below.)
6. **Page actions row (top)** — `.rs-action-row.rs-action-row-top.rs-action-row-left`,
   flush left. Contents (in left-to-right order):
   - `Save` (Primary) — saves the current page's inputs.
   - `Discard` (Secondary anchor) — discards the current page's
     in-progress edits.
   - `Page 1`, `Page 2`, … — one anchor per instrument, Primary
     style; the anchor for the current page renders disabled
     (`aria-disabled="true"`).
7. **Instrument body** — heading, help-text card(s), reviewer table.
   Exactly one instrument's content renders per page.
8. **Page actions row (bottom)** — `.rs-action-row` (flush-right). Same
   contents as the top page actions row, same order.
9. **Acknowledge missing checkbox** — when `show_acknowledge` is set
   (server-driven on a session-wide Submit attempt that hits required
   gaps), renders immediately above the bottom review-level row.
10. **Review-level action row (bottom)** — single right-flushed row
    carrying `Submit` again. Mirrors the top review-level row.
11. **Danger zone** — `.card.danger-zone.rs-danger-zone` with the
    Clear-all-responses form. Half-width, flush right, 24px above the
    foot. Review-session-wide; wipes every response across all
    instruments. Only when `any_accepting and not preview_mode`.

Mental model: instruments are **chapters of one review session**, not
standalone editing surfaces. The reviewer fills each page (saving as
they go), then **Submit commits the whole review** in one action.
"Page actions" act on the current page; "Review-level actions" act on
the entire session.

| Button | Scope | HTTP | Behavior |
|---|---|---|---|
| **Save** | Page | POST `…/{position}/save` | Persist the visible inputs as draft. 303 → `…/{position}?saved=ok` (transient flash in the right-half status panel). |
| **Discard** | Page | GET `…/{position}` | Plain anchor — re-fetches the page, dropping in-progress unsaved edits. No server state change. |
| **Page N** | Page | GET `…/{n}` | Plain anchor — navigates to instrument N. Silently drops in-progress unsaved edits on the current page (URL is the source of truth). The current page's button is disabled. |
| **Submit** | Review-session | POST `/reviewer/sessions/{id}/submit` | Save the current page's inputs (so the in-flight edits aren't lost), then validate every saved response across **all** instruments and stamp `submitted_at` on every assignment in the session. On missing-required without ack: 400, re-render the surface with `missing` populated and `show_acknowledge=True`. On success: 303 → `…/{position}?submitted=ok`. |
| **Clear all** | Review-session | POST `/reviewer/sessions/{id}/clear` | Wipe every response across every instrument (with confirmation checkbox). Clears any submitted state. Lives in the half-width-flush-right Danger Zone card at the foot of the surface, not in the action rows. |

**Why Submit is session-wide, not per-page.** Conceptually a review is
one document spread across multiple pages. Per-page submit would
require the reviewer to remember to submit each page individually,
which invites missed submissions. The single review-session-wide
Submit affordance — surfaced at the top *and* bottom of every page —
makes "I'm done" a single click no matter which page the reviewer is
on. Submit also acts as an implicit Save for the current page first
so an in-flight edit on Page 2 isn't lost when the reviewer hits
Submit there.

**Form HTML mechanics.** The whole editing surface lives inside a
single `<form>` whose default `action` is `…/{position}/save`. The
Save button submits to that default action; the Submit button
overrides via `formaction="/reviewer/sessions/{id}/submit"`. Both
buttons send the current page's input values. The Save route persists
those inputs and 303s back to the page; the Submit route persists
those inputs *and* applies the session-wide submission semantics.

**Cross-page unsaved-edit handling.** Clicking `Page N` (or `Discard`)
is plain navigation; unsaved edits on the current page are discarded
silently. The future `beforeunload` warning (see
"Designed-for-extensibility") prompts before navigating away from a
dirty form; intentional-discard controls (`Page N` / `Discard` /
chrome `My Reviews` link) are tagged so they bypass the prompt.

**Persistence semantics.**

- **Save** upserts `Response` rows in `(assignment_id,
  response_field_id)` shape. An empty submitted value **deletes** the
  matching `Response` row (so absence == empty answer); a non-empty
  value upserts. Save never touches `submitted_at`. Returns 303 →
  `…/{position}?saved=ok`.
- **Submit** persists pending writes the same way Save does, then
  validates required fields across **all** instruments. With
  acknowledge (or no missing required), it stamps `submitted_at` on
  every Response row in the session and writes a
  `responses.submitted` audit event. Editing a previously-submitted
  required field to empty deletes its `Response` row (including the
  `submitted_at` stamp), which flips the dashboard pill back to
  `in progress` on next render — no per-row resubmit required.
- **Clear all** deletes every `Response` row for this reviewer in
  this session, across every instrument. No partial undo. Writes a
  `responses.cleared` audit event.
- **Discard** is a plain `<a>` re-fetch of the current page; no DB
  write, no audit. Drops in-progress unsaved edits by re-reading
  saved values.

**"Submitted" status on the dashboard.** Once Submit succeeds, every
assignment in the session has `submitted_at` set. The dashboard's
session-level pill ("submitted" / "in progress" / "not started")
follows the same rule it does today (every assignment submitted →
"submitted"). With session-wide Submit, the rollup is always
all-or-nothing rather than "submitted on some pages but not others".

---

## Per-page status

The right-half panel renders one status pill per instrument,
positioned immediately above any transient flash banners that may
land. Status is computed server-side from response data:

| Pill state | Pill class | Condition |
|---|---|---|
| `not started` | `.pill.pill-empty` | No saved Response rows for any of this page's assignments. |
| `in progress` | `.pill.pill-warning` | Some Response rows saved, but at least one required field empty across this page's assignments. |
| `complete` | `.pill.pill-success` | Every required field on every assignment in this page has a saved value. |
| `submitted` | `.pill.pill-success` | Every assignment in this page has `submitted_at` set (i.e. the session has been submitted; all pages flip together). |

Pill copy: `Page 1: in progress`, `Page 2: complete`, etc. Single-
instrument sessions still show one pill (`Page 1: …`), since the
status panel always renders.

The route threads a `page_statuses: list[PageStatus]` into context
(`PageStatus = {position: int, label: str, state: Literal[…]}`),
populated for every instrument regardless of how many there are. The
template iterates and renders one pill per entry.

---

## Per-instrument table

Each page renders **one tabular response artifact** for the current
instrument: every assignment the reviewer has on that instrument is
one row, with response fields as columns. Wrapped in
`.table-scroll` so very wide instruments scroll horizontally instead
of forcing the surrounding layout to grow.

### Above the table — heading + help block

- **H2 section heading** from `Instrument.description` (fall back to
  the system handle / `Instrument.name` when the description is
  empty). Single-instrument sessions with empty descriptions render
  no H2 at all (regression-tested; see
  `test_surface_single_instrument_no_description_renders_no_heading`).
- **Help block** above the table, listing each response field that
  has both `help_text` set and `help_text_visible=true`. Two
  variants:
  - Multiple visible help items → `.rs-help-grid` (responsive grid
    of `.rs-help-card` items).
  - Exactly one visible help item → `.rs-help-card.rs-help-card-solo`
    (full-width single-card variant).

### Columns

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
   driven by the field's RTD `data_type`:
   - `Integer` / `Decimal` → `class="rs-narrow"` (numbers are short).
   - `String` with `validation.max_length > 100` → `class="rs-textlong"`.
   - everything else → no width modifier.
4. **Status indicator** (trailing, narrow): only renders when
   `group.show_status_col` is true (i.e. when at least one row has
   `submitted_at` set or `show_acknowledge` is true after a
   missing-required Submit attempt). Cell content:
   - `<span class="status-icon-complete" title="Complete">✓</span>`
     when the row's required fields are all filled.
   - `<span class="status-icon-incomplete" title="N required field
     missing">⚠</span>` when any required field is empty.
   - Plus a small `.muted` line below the icon: `submitted YYYY-MM-DD HH:MM`
     when `submitted_at` is set.

### Cell renderers

Response field input markup is driven by the RTD's `data_type`
(per Slice 4a; pre-Slice-4a code branched on legacy literal type
names):

| `data_type` | Render |
|---|---|
| `String` with `validation.max_length > 100` | `<textarea rows="2">` (with `min-height: 44px`); preserves stored value. |
| `String` with `validation.max_length ≤ 100` | `<input type="text">`; the `maxlength` attribute reflects `validation.max_length`. |
| `Integer`, `Decimal` | `<input type="number">`; `min` / `max` / `step` reflect `validation`. |
| `List` | `<select>` over `validation.choices`, with an empty leading option (`value=""`) representing "no answer". |
| anything else | `<input type="text">` (defensive fallback). |

When the assignment isn't accepting (deadline closed or operator-
paused), every input renders `disabled`.

Stored values are read from `Response` rows keyed by
`(assignment_id, response_field_id)` and rendered as the input's
`value` (or selected `<option>` for `List`, or textarea body for the
long `String` variant).

### View shape

The route builds the table data in `_surface_context` (and its
operator-side mirror `build_preview_context`) as
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

Keep this dict shape stable — the AG Grid migration (see
"Designed-for-extensibility") mounts against the same payload.

---

## Acknowledge missing required flow

Acknowledge is now **session-wide**, since Submit is session-wide:

1. Reviewer hits Submit on any page with at least one required field
   blank anywhere in the session.
2. Server returns 400 + re-renders the page they were on (whichever
   `{position}` they submitted from) with:
   - The missing-required `.banner.banner-warning` inside the right-
     half flash/status panel, listing which page each missing field
     lives on (so the reviewer knows where to navigate).
   - `show_acknowledge=True`.
3. The acknowledge checkbox renders immediately above the bottom
   review-level action row: "I acknowledge required fields are
   missing — submit anyway."
4. The reviewer can either navigate to the offending page and fill
   the gaps, or tick the checkbox and click Submit again. Ticking the
   checkbox session-wide-acknowledges; the server records the submit
   + `acknowledged_missing: true` audit detail.

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

GET requests don't 403 — the page still renders so the reviewer can
read prior state. When the gate is closed, the editing surface
degrades to read-only:

- Every input renders `disabled`.
- The top + bottom review-level rows (Submit) hide.
- The Save / Discard buttons hide from the page actions row, but the
  Page N anchors stay so the reviewer can walk through their other
  instruments (which may or may not also be closed).
- The Danger Zone card hides (no Clear all).
- A `.banner.banner-warning` lands in the right-half status panel
  explaining the state, e.g. "This session is no longer accepting
  responses." Two variants depending on the operator's per-
  instrument visibility flag:
  - "Your previously saved values remain visible below in read-only
    form." (operator left `responses_visible_when_closed=true`).
  - "Your previously saved values are hidden by the operator's
    visibility setting." (operator set `responses_visible_when_closed=false`).

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

Both rules live in `app/services/responses.py` (and the per-session
lookup that drives the surface route). The reviewer dashboard, the
session surface, and the invitation-landing email-match check all
use the same rule.

A user can have at most one active `Reviewer` row per session. A
session can have multiple reviewers, each tied to a distinct user.

---

## Operator preview mode

`/operator/sessions/{id}/preview` reuses this template via
`build_preview_context`. In preview mode:

- The chrome `top_bar` block calls `super()` so the operator chrome
  (with breadcrumb back to the session) renders instead of the
  reviewer top bar variant.
- `body_class` drops the `reviewer` modifier (stays `body.ui-v2`).
- The preview-mode banner (`.banner.banner-info`) renders at the top
  of the body: "**Preview** — not visible to reviewers. This page
  is operator-only and bypasses session-status / deadline /
  acceptance gates."
- The reviewer write-path forms are suppressed (no Save / Submit /
  Discard / Clear). The `<form>` wrapper is replaced by a plain
  `<div>` so no `formaction=` can re-target a write endpoint. The
  Page N anchors still render in their slot so the operator can
  walk through every instrument to verify setup — but the rest of
  the page-actions row collapses to just the page buttons, and the
  review-level rows + danger zone don't render at all.
- Inputs render disabled.
- The right-half status panel renders without the per-page status
  pills (preview is read-only and synthetic; per-page state is
  moot).
- **Synthetic-row padding.** Up to three real assignments render
  first (sorted by `Assignment.id` ascending). When there are fewer
  than three, the table is padded with synthetic placeholders
  (`Sample Reviewee 1/2/3` / `sample{n}@example.edu` / per-source
  sample values) so the operator always has something to look at.
  Synthetic rows expose only the attributes the template actually
  reads (`assignment.id` negative to avoid colliding with real
  autoincrement ids; `reviewee.name` / `email_or_identifier`); a
  unit test guards the exposed shape against silent
  AttributeErrors when a future template edit adds a new attribute
  reference.
- **Read-only side-effects.** The preview GET emits no audit
  events and **does not** call
  `lifecycle.observe_deadline(...)` — opening a preview must never
  flip `accepting_responses=false` even if the session deadline
  has lapsed.

The preview URL stays at `/operator/sessions/{id}/preview` (no
position segment) and lands on Page 1 by default; clicking a Page N
anchor on the preview navigates to
`/operator/sessions/{id}/preview/{position}` (mirror of the reviewer
URL pattern, prefixed with the operator path).

---

## Dashboard (`/reviewer`)

The reviewer's lobby — where they land when signing in directly
(without an invitation token) or clicking "My Reviews" from the
chrome on a session surface. Lists every session the signed-in user
is an active reviewer on, with a per-session progress pill.

- **H1** — "Your reviews".
- **Body** — single `.card` containing a `<table>` (one row per
  session). Columns:
  - **Session** — `<a>` to `/reviewer/sessions/{id}/1` (always
    lands on Page 1; the surface itself handles which page is
    "current").
  - **Deadline** — ISO timestamp, or `<span class="muted">—</span>`
    when null.
  - **Status** — pill (`not started` / `in progress` /
    `submitted`) computed from the reviewer's `Response` rows; plus
    a muted `(completed_rows / total_assignments)` count alongside.
- **Empty state** — when the user has no active reviewer rows in
  any session: a single `.card` with `.muted` text "You have no
  pending reviews ({user.email})."

### Pill state machine

Computed by `app/services/responses.py::session_pill_for_reviewer`:

| Pill | `pill-success` / `pill-warning` / `pill-info` | Condition |
|---|---|---|
| `submitted` | `pill-success` | Every required field on every assignment in the session has a `Response.submitted_at` timestamp. |
| `in progress` | `pill-warning` | At least one `Response` row exists, but the `submitted` rule doesn't hold. |
| `not started` | `pill-info` | No `Response` rows exist for this reviewer in this session. |

The "Edit / Re-submit" affordance lives on the surface itself —
hitting Submit once doesn't lock the form. Submitting again replays
the same logic and re-stamps `submitted_at`.

---

## Invitation landing (`/reviewer/invite/{token}`)

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
   `/reviewer/sessions/{id}/1`.

### Invitation-mismatch page

A single `.banner.banner-warning` explaining the email mismatch,
followed by a `.btn-pair` with two Secondary anchors:

- **Sign-in details** → `/me/debug` (so the reviewer can confirm
  which account they're signed in as).
- **Your reviewer dashboard** → `/reviewer`.

The remedy is to sign out and sign back in with the invited
account. This is the only reviewer-side page that returns a non-200
status under normal flow (HTTP 403).

The mismatch page renders with the reviewer chrome variant
(`body.ui-v2 reviewer`) so the operator's identity is suppressed
from the top bar.

---

## Button labels

| Where | Old label | New label |
|---|---|---|
| Page actions row | `Save draft` | `Save` |
| Page actions row | `Cancel — discard unsaved edits` | `Discard` |
| Page actions row | n/a | `Page 1`, `Page 2`, … |
| Review-level rows | `Submit` | `Submit` (unchanged) |
| Danger Zone | `Clear all` | `Clear all` (unchanged; copy explains "every response across every page") |

Other labels (`Sign out`, `My Reviews`) are unchanged.

---

## Out of scope

The following are deliberately deferred. They are not implemented
today but the surface is designed so they can be added later without
re-architecting; see "Designed-for-extensibility" below.

- **`beforeunload` warning** when the form is dirty.
- **Standalone submission-confirmation page** ("thank you" surface).
  Today the post-submit signal is the `?submitted=ok` flash banner in
  the right-half status panel.
- **AG Grid replacement of the reviewer-surface `<table>`** (catalog
  `unfinished_business.md` #33 — Segment 15).

---

## Designed-for-extensibility

Notes on how this surface keeps the three deferred features above
non-risky to add later. Each item lists the design call this spec
makes today + the small follow-on the deferred work needs.

### beforeunload warning

- **Today.** Clicking a `Page N` button or `Discard` is plain
  navigation; unsaved edits are silently dropped.
- **Design call.** The editing form carries a stable id (`id="rs-form"`
  or similar), and every intentional-discard control (`Discard`
  anchor + `Page N` anchors + `My Reviews` chrome link) carries a
  `data-discards-edits` attribute. A future hook attaches a
  `beforeunload` listener tied to a `dirty` flag on the form (set on
  first `input` event); clicks that match `[data-discards-edits]` set
  an `intentional` flag that the listener reads and lets through
  without prompting.
- **What lands later.** A small inline `<script>` block in the same
  shape as the existing rs-paginated handler. No template
  restructuring needed.

### Standalone submission-confirmation page

- **Today.** `POST /reviewer/sessions/{id}/submit` 303s to
  `…/{position}?submitted=ok`, which re-renders the surface with a
  `.banner.banner-success` inside the right-half status panel.
- **Design call.** The submit route's redirect target is computed via
  a small helper (call it `submit_redirect_url(review_session,
  position)`) rather than inlined. Today the helper returns
  `f"/reviewer/sessions/{id}/{position}?submitted=ok"`. Tomorrow it
  can return `f"/reviewer/sessions/{id}/submitted"` (session-level
  thank-you) without touching any other code path.
- **What lands later.** A new template (`reviewer/submitted.html` or
  similar) plus the helper change. The surface itself doesn't move.

### AG Grid table + large-table ergonomics

`spec/visual_style_rrw.md` "Response form layout and instrument
pacing → Large-table ergonomics" pins the following as first-class
requirements (since the app's positioning depends on tabular review
artifacts at scale): auto-save, return-to-place, visible progress,
sticky column headers, filter-to-incomplete, keyboard navigation,
and column-type ergonomics. None of those land in this surface
spec; they belong in the forthcoming `response_form_component_spec.md`
that picks up the AG-Grid (or equivalent) implementation. Notes on
how the surface stays compatible:

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
  alongside the row data so a future JS-driven grid can render the
  same view shape without a second round-trip. The dict shape
  becomes the implicit AG Grid column-defs source. None of today's
  routes need to change to swap the rendering layer.
- **What lands later.** A new partial (`reviewer/_response_grid.html`
  or similar) loads AG Grid and mounts against a JSON payload built
  from the same `_surface_context` shape. The current `<table>` block
  is replaced; nothing else moves. The grid component picks up
  auto-save, return-to-place, visible progress, sticky headers,
  filter-to-incomplete, and keyboard navigation as part of the
  same change — the principle treats them as one bundle, not as
  individual follow-on features.

---

## Migration notes

The URL change from `/reviewer/sessions/{id}` to
`/reviewer/sessions/{id}/{position}` is a breaking change for:

- **Existing invitation emails** — already-sent invitation emails
  embed the old token URL (`/reviewer/invite/{token}`), which redirects
  via `/reviewer/sessions/{id}` after Easy Auth resolves. The
  bare-session URL must 303 to `/reviewer/sessions/{id}/1` to keep old
  invitation links working.
- **Reviewer dashboard rows** — link generation in
  `reviewer/dashboard.html` updates to point at position `1`.
- **Bookmarks / returning reviewers** — same 303 covers them.

The 303 fallback covers all known callers; no data migration is
needed. The fanout fix shipped in PR #418 ensures that
multi-instrument sessions actually have multiple `instrument_groups`
visible to each reviewer, which is the precondition for the page
selector to render at all.
