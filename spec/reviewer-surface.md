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
4. **Description card** — half-width `.card.rs-description-card`
   flushed left, only when `session.description` is set. Collapses to
   full width below the 800px breakpoint.
5. **Flash banners** — saved/submitted/missing-required/session-closed,
   per `spec/visual_style_rrw.md` "Reviewer-surface banners".
6. **Top action row** — `.rs-action-row.rs-action-row-top.rs-action-row-left`,
   flush left under the description card with a wider top margin than
   the default action row. Contents (in left-to-right order):
   - Save draft (Primary).
   - Submit (Secondary).
   - Discard unsaved edits (Secondary anchor — see "Button labels"
     below).
7. **Page selector** — only when the session has more than one
   instrument. See "Page selector" below.
8. **Instrument body** — heading, help-text card(s), reviewer table.
   Exactly one instrument's content renders per page.
9. **Bottom action row** — `.rs-action-row` (default flush-right).
   Same buttons as the top row, in the same order.
10. **Acknowledge checkbox** — when `show_acknowledge` is set
    (server-driven on missing-required submit attempt), renders
    immediately above the bottom action row.
11. **Danger zone** — `.card.danger-zone.rs-danger-zone` with the
    Clear-all-responses form. Half-width, flush right, 24px above the
    foot. Only when `any_accepting and not preview_mode`.

The whole editing surface lives inside a single `<form>` whose scope is
**this instrument only**. Save / Submit / Clear / Discard all act on
the current instrument's responses; navigating to a different page does
not implicitly save.

---

## Page selector

When the session has more than one instrument, a row of page-selector
buttons sits between the top action row and the instrument body:

- One button per instrument, labelled `Page 1`, `Page 2`, …, in the
  same order as the URL position scheme.
- Each button is a Primary `.btn` anchor pointing at
  `/reviewer/sessions/{session_id}/{n}`.
- The button for the **current page** is rendered as disabled
  (`aria-disabled="true"` + `.btn` greyed via the canonical
  `body.ui-v2 .btn[aria-disabled="true"]` rule). It still occupies its
  slot so the reviewer's visual context doesn't shift between pages.
- The selector wraps as needed via flex-wrap; on narrow viewports the
  buttons stack rather than overflow.

Replaces the Previous / Next pair from PR #417 — direct page navigation
is more useful than step-through once the URL is the source of truth
for "which page am I on", and the disabled-current-page treatment is a
clearer "you are here" signal than greying the boundary buttons.

A small `.rs-page-selector` flex container hosts the row:

```css
body.ui-v2 .rs-page-selector {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}
```

The selector renders **even on the first page** (single-instrument
sessions skip it entirely; the test for "more than one instrument" is
the only gate).

---

## Form scope and Save / Submit / Discard semantics

Per-page form scope. All POSTs target
`/reviewer/sessions/{id}/{position}/...` endpoints and act on the
current page's response fields only.

| Button | HTTP | Behavior |
|---|---|---|
| Save draft | POST `…/save` | Persist the visible inputs as draft. 303 → `…/{position}?saved=ok` (banner-success). |
| Submit | POST `…/submit` | Validate + persist + stamp `submitted_at`. On missing required without ack: 400-render with `missing` populated, `show_acknowledge=True`. On success: 303 → `…/{position}?submitted=ok`. |
| Discard unsaved edits | GET `…/{position}` | Plain anchor — re-fetches the page, dropping in-progress unsaved edits. |
| Clear all | POST `…/clear` | Wipe every response on this page (with confirmation checkbox). Does not touch other pages. |

**Cross-page unsaved-edit handling.** Clicking a different `Page N`
button is plain navigation; unsaved edits on the current page are
discarded silently. This matches the per-instrument form scope and
keeps the URL the source of truth. (Future enhancement could add a
`beforeunload` warning when the form is dirty — out of scope here.)

**"Submitted" status.** A reviewer's session-level status ("submitted"
on the dashboard) is the conjunction of all instruments having
`submitted_at` set for every assignment. Per-instrument submit stamps
only that instrument's rows; the dashboard pill rolls up across pages.

---

## Acknowledge missing required flow

Unchanged from the current implementation, but scoped per-page:

1. Reviewer hits Submit on Page 2 with at least one required field
   blank.
2. Server returns 400 + re-renders Page 2 with the missing-required
   `.banner.banner-warning` near the top and `show_acknowledge=True`.
3. The acknowledge checkbox renders immediately above the bottom
   action row: "I acknowledge required fields are missing — submit
   anyway."
4. Reviewer ticks it and clicks Submit again; the server records the
   submit + the `acknowledged_missing: true` audit detail.

The acknowledge checkbox only governs submits on the current page. It
does not pre-acknowledge other pages' missing values; each page
handles its own ack flow.

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
  Discard / Clear). Page selector still renders so the operator can
  walk through all instruments to verify each one's setup.
- Inputs render disabled.

The preview URL stays at `/operator/sessions/{id}/preview` (no
position segment) and lands on Page 1 by default; clicking a page
selector button on the preview navigates to
`/operator/sessions/{id}/preview/{position}` (mirror of the reviewer
URL pattern, prefixed with the operator path).

---

## Button labels

| Where | Old label | New label |
|---|---|---|
| Top + bottom action rows (Cancel) | `Cancel — discard unsaved edits` | `Discard unsaved edits` |
| Page selector | n/a | `Page 1`, `Page 2`, … |

Other labels (`Save draft`, `Submit`, `Clear all`, `Sign out`, `My
Reviews`) are unchanged.

---

## Out of scope

- Per-instrument deadlines (operator-set deadlines that differ between
  instruments). Today every instrument inherits the session deadline;
  per-instrument deadlines remain a Segment 12+ concern.
- `beforeunload` warning for navigating away with unsaved edits.
  Worth adding as a small enhancement once the URL-driven pagination
  is in place.
- Submission-confirmation page (a standalone "thank you" surface). The
  spec calls for it; today it's folded into `?submitted=ok` flash
  banner copy. Defer to whichever segment introduces the standalone
  page.
- Reviewer-side instrument status indicator (per-page "complete" /
  "in progress" pill on the page selector). Could land on the page
  selector buttons later — useful for sessions with many instruments
  — but for now the buttons are pure navigation.
- AG Grid replacement of the reviewer-surface table (catalog
  `unfinished_business.md` #33 — Segment 15).

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
