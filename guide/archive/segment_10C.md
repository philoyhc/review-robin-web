# Segment 10C — Operator UI Clean-Up (First Round)

**Status:** Recap of work that landed iteratively across PRs #~140–~190.
Captures the surface changes, cross-cutting conventions, and
deliberately-deferred items so the next round of UI work has a clear
baseline. Not a forward-looking plan — items still owed are listed in
§5 with pointers to where they belong.

This sat between Segment 10B (instrument builder + preview) and
Segment 12 (export / audit retention). It is not a new feature
segment; it consolidates the operator-facing surface so the new
multi-instrument/builder shape introduced in 10B is consistent across
every page.

---

## 1. Pages restructured

### 1.1 Session detail (`/operator/sessions/{id}`)

- Adopted the **page-grid** two-column desktop layout: Session
  Details (top-left), Session Setup (right-spans-two-rows), Run
  Session (bottom-left), Danger Zone in a separate `bottom-grid`.
- Mobile (≤800px) stacks DOM-order: Session Details → Session
  Setup → Run Session → Danger Zone.
- Setup card uses a 4-column `setup-grid` with Manage CTAs and
  inline values.
- Run Session card uses a 4-up `btn-row` of CTA-style buttons
  (`Validate`, `Preview`, `Manage Invitations`, `Extract Data`).
- Yellow lock card at top of page when `is_ready`; the inline
  revert form inside the Session Details card is removed (replaced
  by the lock card).

### 1.2 Sessions list (`/operator/sessions`)

- Added `Created by` column.
- Action column tightened with `col-shrink` so the two trailing
  buttons hug the right edge.

### 1.3 Create / Edit session forms

- Title, code, deadline, description split for clearer hierarchy.
- Edit form uses the same shape as new.

### 1.4 Reviewers / Reviewees / Assignments (the three setup pages)

All three follow the same info-card design:

- Top info card has the **Session** button as the first item in
  the nav, then `Reviewers`, `Reviewees`, `Assignments`,
  `Instruments`, `Email Invites`. Nav row anchors to the
  bottom-right.
- Two stacked status rows on the left:
  - `Number of {reviewers/reviewees/N · M}: {pill}`.
  - `Fields with data: {pill, pill, …}` listing the CSV column
    names that hold at least one non-empty value.
- Yellow lock card with the standard message + `Yes, revert
  {session} to draft` checkbox + `Revert to draft` button when
  `is_ready`. Posts `return_to=reviewers` (or reviewees /
  assignments / instruments) so the operator stays on the same
  page after the round-trip.
- While locked, the upload / Danger Zone cards are hidden and the
  data-preview tables continue to render.

### 1.5 Instruments (`/operator/sessions/{id}/instruments`)

- Top info card carries only the 6 nav buttons (bottom-right);
  the legacy "Preview Reviewer Surface" anchor moved off this
  card.
- The page-grid that used to hold `All Instrument Status` +
  `Add/Delete Instruments` collapsed to a single full-width
  **All Instrument Status** card. The Add/Delete card and its
  Add 1 / Delete 1 / Go to #N buttons are gone.
- All Instrument Status reports three pill rows (deadline, count
  with accepting / not accepting, visibility-when-closed) and
  carries the bulk Open/Close toggles, the bulk Show/Don't Show
  toggles, and a disabled `Preview reviewer surface` button.
- Yellow lock card matches the other three setup pages.
- Per-instrument card uses pastel-tint cycling (sky-blue, mint,
  lavender, peach, rose, amber). Inside each:
  - Top `bottom-grid`: invisible left card (Instrument #N title,
    description, Edit toggle) and white right card (This
    Instrument's Status: accepting/showing pills + per-instrument
    Open/Close + Show/Don't show buttons).
  - Field builder `bottom-grid` (`field-builder` class): two
    invisible-border half cards side-by-side — **Display Fields**
    and **Response Fields**.
  - Preview Instrument #N table renders below — see §3.5.
  - Save / Edit / "Add an instrument" / Delete button row at
    bottom-right (see §3.4).

### 1.6 Multi-instrument data structures

- Schema is fully multi-instrument-aware (`Instrument.session_id`,
  `order`, `assignment.instrument_id`, FK cascades).
- Service helpers `create_instrument(after_instrument_id=…)` and
  `delete_instrument(...)` exist and persist correctly (with
  `instrument.created` / `instrument.deleted` audit events,
  cascade delete-orphan, order repack).
- **UI surface for multi-instrument is intentionally deferred**:
  `Add an instrument` is rendered as a disabled button
  (tooltip: "Multi-instrument support is still in progress;
  coming back later."); `Delete` is hidden when only one
  instrument exists. Routes remain in place for when the UI
  comes back.

---

## 2. Cross-cutting layout primitives (in `base.html`)

| Class | Purpose |
|---|---|
| `.page-grid` | Two-column grid with `align-items: stretch` for equal-height cards. |
| `.bottom-grid` | Two-column grid with `align-items: start` for natural-height pairs. |
| `.card-tl / .card-r / .card-bl / .card-l / .card-tr / .card-br` | Placement classes inside `.page-grid` for the L-shape Session-detail layout. |
| `.setup-nav` | Equal-width 140px nav buttons row, wraps on narrow viewports. |
| `.setup-grid` | 4-column grid — Manage CTA + content. |
| `.btn-row` / `.btn-pair` | Equal-flex button rows. |
| `.fill-col` | Flex column where last child grows (e.g. textarea fills card). |
| `.col-shrink` | `width: 1%; white-space: nowrap` to make table actions hug right. |
| `.session-meta-row` / `.session-status-row` | Inline meta rows on Session Details. |
| `.field-builder` / `.field-builder.locked` | Wrapper for the Display + Response Fields side-by-side cards; `.locked` disables inputs and hides edit/add/delete affordances. |
| `.display-edit` | `<details>` shell for inline edit forms; CSS rules in `base.html` hide summary when open. |

Mobile (≤800px) collapses every grid to one column, drops
`card-half`'s max-width, and stacks cards in DOM order.

---

## 3. UI conventions confirmed

### 3.1 Six button styles

Documented in `spec/domain_assumptions.md`. All `<a>` and `<button>` actions
in operator pages should use one of:

| Class | Use |
|---|---|
| `.btn` | Primary (filled blue). |
| `.btn.secondary` | Primary Outline. |
| `.btn.alert` | Alert Outline (orange border, white). |
| `.btn.alert-solid` | Alert (filled orange). |
| `.btn.danger` | Danger Outline. |
| `.btn.danger-solid` | Danger (filled red). |

`.btn-cta` is a layout variant of Primary used in the Session
Setup / Run Session grids. `.btn[disabled]` and `.btn.disabled`
render at 0.5 opacity with `cursor: not-allowed`. `.btn[hidden]`
honors the standard hidden attribute (overrides `display:
inline-block`).

`AGENTS.md` carries the convention: when working on a page,
migrate any inline-styled buttons on it to one of the six named
classes; ask first if a button doesn't cleanly fit one of those
styles.

### 3.2 Yellow "session ongoing" lock card

Reusable pattern across Session detail, Reviewers, Reviewees,
Assignments, Instruments. Markup:

```html
<div class="card" style="border-color: #d97706; background: #fef3c7;">
  <p>The {scope} cannot be modified while the session is ongoing.
     Revert the session to draft if you wish to modify anything.</p>
  <form method="post" action="/operator/sessions/{id}/revert">
    <input type="hidden" name="return_to" value="{page}">
    <p><label><input type="checkbox" name="confirm" value="true" required>
       Yes, revert <strong>{session.name}</strong> to draft.</label></p>
    <p><button class="btn alert-solid" type="submit">Revert to draft</button></p>
  </form>
</div>
```

`return_to` allowlist (in `routes_operator.py`):
`reviewers`, `reviewees`, `assignments`, `instruments`. The
session-detail revert omits the field and lands on session
detail.

### 3.3 CSV column names as canonical labels

- `assignments.reviewer_fields_with_data(db, session_id)`,
  `reviewee_fields_with_data`, `assignment_fields_with_data`
  return the actual CSV column names (`ReviewerName`,
  `ReviewerEmail`, `RevieweeName`, `RevieweeEmail`, `PhotoLink`,
  `RevieweeTag1..3`, `PairContext1..3`, `AssignmentContext1..3`,
  `IncludeAssignment`) for fields with at least one non-empty
  value.
- These strings flow into the "Fields with data" pills and into
  the per-instrument Display Fields placeholder Source column.
- `display_source_presence` composes from the three helpers so
  the Instruments page reuses the same queries the three setup
  pages already issue.
- The Reviewees Upload card was corrected to advertise
  `PhotoLink` (the actual CSV column) instead of the never-read
  `RevieweeProfileLink`.

### 3.4 Per-instrument card button row

Bottom-right of each per-instrument card, in this order:

1. **Back** (Primary) — smooth-scrolls to top.
2. **Save** (Primary) / **Edit** (Alert filled) — toggles
   `field-builder.locked`. Save closes any open inline editors
   (resetting their inputs to the displayed label first) and
   disables every input/select. Edit reverses both. Only one of
   the pair is visible at a time (via `hidden` attribute).
3. **Add an instrument** (Alert filled) — currently disabled
   with "Multi-instrument support is still in progress" tooltip.
4. **Delete** (Danger filled) — only rendered when more than
   one instrument exists; submits to
   `/instruments/{id}/delete`, guarded by `confirm()`.

### 3.5 Inline label edit (`<details>` + tick/cross)

Used on Display Fields Friendly Label, Response Fields Friendly
Label, the per-instrument description, etc.:

```html
<details class="display-edit">
  <summary>{label} ✎</summary>
  <form>{input} <button type="submit">✓</button> <a onclick=cancelLabelEdit>✗</a></form>
</details>
```

CSS rule `.display-edit[open] > summary { display: none }` hides
the closed-state row when editing. The summary's flex layout
lives in an inner span so the inline `display: flex` doesn't
override the rule. JS helpers `applyLabelEdit(form)` and
`cancelLabelEdit(link)` keep the input value in sync with the
displayed label, so reopening always shows the live value (no
stale draft text).

For controls spanning multiple `<td>`s (each row's label + type
+ required + delete + add), per-row hidden forms
(`<form id="rf-edit-{field_id}">`) are placed outside the table
and inputs reference them via the HTML5 `form` attribute.

### 3.6 Live preview on the per-instrument card

The `Preview Instrument #N` table at the bottom of each
per-instrument card is rendered client-side from the current
state of the Display Fields and Response Fields tables:

- Columns = visible Display Fields (in DOM order) followed by
  every Response Field (in DOM order). Friendly Label is the
  column header.
- Three mock rows seeded per source/type. `long_text` columns
  render with `min-width: 240px`. `PhotoLink` cells render as
  `<a target="_blank">View</a>`.
- Re-renders on:
  - Display Fields Visible checkbox toggle
  - Response Fields Type / Required change
  - Friendly Label save (tick) on either table
  - Add / delete Response Fields row (post-redirect render at
    DOMContentLoaded)
- Reads response type from `data-response-type` on each
  Response Fields `<tr>` (the `<select>` is currently disabled
  for display only).

### 3.7 Typography

Confirmed in `base.html`: `html { font-size: 100% }` (was the
default; explicit knob now in place). `body { line-height: 1.35 }`,
heading `line-height: 1.25`, h1 `margin-bottom: 16px`, paragraph
`margin: 0 0 6px 0`, `<ul/ol/dl>` `margin: 0 0 6px 0`,
`<li>` `margin-bottom: 2px`. Card border 2px #bbb; danger and
alert variants override.

---

## 4. Persistence wired

| Surface | Status |
|---|---|
| Session description / metadata | Wired (existing). |
| Reviewers CSV import / delete-all | Wired (existing). |
| Reviewees CSV import / delete-all | Wired (existing). |
| Assignments CSV import / full-matrix / delete-all | Wired (existing). |
| Per-instrument description edit | Wired (existing). |
| Per-instrument Open/Close/Show/Don't-show + bulk variants | Wired (existing). |
| Add an instrument | Service + route exist (`create_instrument`); UI **disabled** pending multi-instrument design. |
| Delete an instrument | Service + route + UI all wired (`delete_instrument`). |
| Response Fields Friendly Label edit | Wired (per-row hidden form → existing `/fields/{id}/edit`). |
| Response Fields Required toggle | Wired (same form, auto-submits onchange). |
| Response Fields Add row | Wired (new `add_default_response_field` service + `/fields/add-row` route). |
| Response Fields Delete row | Wired (existing `/fields/{id}/delete`). |
| Display Fields Friendly Label / Visible / Sort | **Placeholder only** — see §5. |
| Response Fields Type | **Read-only by design** — `update_response_field` doesn't accept type changes (risky once response data exists). UI shows a disabled select. |

---

## 5. Deferred items (next round / dependent segments)

- **Display Fields persistence.** The placeholder iterates a
  hardcoded list of six CSV columns
  (`RevieweeName`, `RevieweeEmail`, `PhotoLink`, `RevieweeTag1..3`).
  The schema's `_VALID_DISPLAY_SOURCES` only knows
  `pair_context.{1,2,3}`, `reviewee.tag_{1,2,3}`,
  `reviewee.profile_link`. To wire this up:
  1. Extend `_DEFAULT_DISPLAY_LABELS` / `_VALID_DISPLAY_SOURCES`
     with `("reviewee", "name")` and
     `("reviewee", "email_or_identifier")`.
  2. Extend `display_field_value` (and the reviewer-surface
     render path) to resolve those new sources.
  3. Seed all six reviewee display fields per instrument in
     `ensure_default_instrument` and `create_instrument`.
  4. Wire the Visible checkbox + Friendly Label edit on the
     placeholder to upsert/update the corresponding row.
- **Sort / Order column** on Display Fields. Currently a muted
  dash. Probably ties into the existing `bulk_save_fields`
  endpoint or a new lightweight per-row order setter.
- **Cross-table CSV identity check** — tracked in
  `guide/unfinished_business.md` item 12 (moved there from
  `segment_10_instrument_builder_mvp_plan.md` §15 as part of the
  stabilization sweep).
- **Multi-instrument operator UI** — Add an instrument button is
  disabled; Add 1 / Delete 1 / Go to #N controls are removed.
  Reintroduce when the multi-instrument flow is designed.
- **Response Fields Type changes** — out of scope on purpose.
  If type editing is ever needed, it has to migrate the response
  data too; that belongs in Segment 13 or a dedicated slice.

---

## 6. Cross-references

- `spec/domain_assumptions.md` — six button styles, typography knob.
- `spec/operator_map.md` — page layout conventions, `.page-grid`
  / `.bottom-grid` placement classes.
- `guide/ui_checklist.md` — page-by-page restructure checklist.
- `CLAUDE.md` / `AGENTS.md` — refreshed conventions, button
  migration rule.
- `guide/archive/segment_10_instrument_builder_mvp_plan.md` §14 — the
  umbrella that 10A / 10B / now 10C sit under.
- `guide/unfinished_business.md` — stabilization todo (CSV
  identity check carried over there as item 12).
