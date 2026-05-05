# Reviewer surface — functional + visual spec

The page a reviewer lands on after opening their invitation token (or
clicking a session row on `/reviewer`). It hosts the editing affordance
for a single instrument's response fields against a fixed set of
reviewees and is the single most important surface for the reviewer
audience.

This spec rewrites the page around **multi-instrument awareness**: the
URL carries an explicit instrument segment, the page renders one
instrument at a time, and a page selector at the top of the body lets
the reviewer move between instruments. Single-instrument sessions are a
degenerate case of the same model.

Cross-references:

- `spec/visual_style_rrw.md` — top-bar / chrome conventions, banner
  family, status-icon classes.
- `spec/visual_style_general.md` — `.card` / `.btn` / `.pill` / form
  primitives.
- `spec/ui_elements.md` — canonical elements (P6 hover-by-fill, P7
  recovery-action color family).
- `app/web/templates/reviewer/review_surface.html` — current
  implementation (single-form-multi-instrument-stack); this spec is the
  target.

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

## Session-not-accepting behavior

When the session (or this instrument specifically) is no longer
accepting responses (deadline passed, operator-paused), the page
renders read-only:

- Inputs render `disabled` (existing per-row logic in
  `_surface_context`).
- Top action row hides Save / Submit (preserves Discard? — no, the
  whole action row hides since there's nothing to act on).
- Page selector still renders so the reviewer can see what other
  instruments exist; navigating to one of them shows the same
  read-only state if it's also closed.
- Danger zone (Clear all) hides; the operator may set
  `responses_visible_when_closed=true` to keep prior values visible
  but the reviewer can't mutate them.
- A `.banner.banner-warning` near the top explains the state ("This
  session is no longer accepting responses.").

---

## Operator preview mode

`/operator/sessions/{id}/preview` reuses this template via
`build_preview_context`. In preview mode:

- The chrome `top_bar` block calls `super()` so the operator chrome
  (with breadcrumb back to the session) renders instead of the
  reviewer top bar variant.
- `body_class` drops the `reviewer` modifier (stays `body.ui-v2`).
- The preview-mode banner (`.banner.banner-info`) renders at the top
  of the body.
- The reviewer write-path forms are suppressed (no Save / Submit /
  Discard / Clear). The Page N anchors still render in their slot so
  the operator can walk through every instrument to verify setup —
  but the rest of the page-actions row collapses to just the page
  buttons, and the review-level rows + danger zone don't render at
  all.
- Inputs render disabled.
- The right-half status panel renders without the per-page status
  pills (preview is read-only and synthetic; per-page state is moot).

The preview URL stays at `/operator/sessions/{id}/preview` (no
position segment) and lands on Page 1 by default; clicking a Page N
anchor on the preview navigates to
`/operator/sessions/{id}/preview/{position}` (mirror of the reviewer
URL pattern, prefixed with the operator path).

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

### AG Grid table

- **Today.** Per-instrument rows render as a `<table>` inside
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
  becomes the implicit AG Grid column-defs source.
- **What lands later.** A new partial (`reviewer/_response_grid.html`
  or similar) loads AG Grid and mounts against a JSON payload built
  from the same `_surface_context` shape. The current `<table>` block
  is replaced; nothing else moves.

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
