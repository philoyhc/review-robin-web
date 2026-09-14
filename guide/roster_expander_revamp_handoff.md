# Roster pages — expander-row UI revamp (intermediate step)

**Purpose.** Port a *narrow, shippable* piece of the Rosters exploration
into a fresh thread: revamp the existing roster Setup pages to use the
**Session Lobby's row-expander UI**, **without** consolidating the four
pages. Reviewers is the worked case study; the other three follow the same
recipe.

**Why this is worth doing on its own.** The four-pages-into-one
consolidation (`guide/new_ux_ideas.md` §1) is a big, deferrable move. But
its single clearest UX win — the lobby's **selected-row bracket + inline
action expander**, where row actions sit *next to the rows they act on*
instead of in a button strip floating above the table — is independent of
consolidation. It can land per page, one page at a time, each shippable on
its own, and it brings the Session Lobby's interaction model to the roster
pages that today use the older "Operator actions" strip. Nothing about it
commits to consolidation later; it makes consolidation *easier* if it ever
happens, because all four pages would already share the expander.

> **Annotated 2026-09-14 (19O.4). Four of this document's claims were
> falsified when it was checked against the templates. It is not rewritten —
> it records what was proposed — but a reader should know which:**
>
> - **§3's caveat is wrong.** It says the lobby's expander buttons are "a
>   placeholder (`disabled`, only selection-management wired)" and the roster
>   version "must actually wire the buttons". They carry live `formaction`s
>   to `/operator/sessions/bulk-archive` and `/bulk-tags`; only the two
>   `data-expander-delete` buttons are `disabled`, as a two-stage delete gate.
>   The error is inherited, not invented: `sessions_list.html:182-184` still
>   carries a comment saying exactly this, stale since the formactions landed
>   in `d2c8671`.
> - **§7's plan home does not exist.** 19L is archived. The live home is 19O.
> - **§2.4's "bottom cards" miscounts.** The friendly-labels editor is a *top*
>   card inside `card-columns` beside Operator actions, not one of the two
>   bottom cards (`#upload-csv`, `.danger-zone`).
> - **§7's sequencing is backwards.** Reviewers / Reviewees / Relationships are
>   identical in action set, so they cannot falsify the expander's shape;
>   Observers must come second, not fourth. See 19O.4's Decision.
>
> Scheduled as **19O.4** (Reviewers) and **19O.5** (Observers).

**Status: not scheduled.** This is a proposal for an intermediate slice.
It fits the 19L "UX refinements" family (19L Items 1–3 built the lobby
bracket itself). Land it as a new 19L item or a small segment, scaffold-first.

---

## 1. Scope — two variants, same family

Both variants keep the **four pages separate** (own nav tab, URL, heading,
breadcrumb — **no consolidation**, no cross-roster chooser or gating) and
add **no new capabilities** — they re-house existing controls into the
lobby's expander idiom.

- **Variant A (minimal).** Move only the **row-level action controls**
  (Edit / Inactivate / Activate / Delete) into a **bracketed expander
  beneath the selected row(s)**, and mark selected rows with the 19L.2
  bracket. The filter strip stays; the friendly-labels, Upload, and
  Danger-Zone cards stay where they are. Detailed as the case study below.
- **Variant B (more ambitious).** Everything in A, **plus** a **single-row
  "index"** at the top of the page (just this roster) with an **Unlock
  expander** carrying the roster's **metadata + whole-data actions**
  (friendly labels, Upload/replace, Download, Delete-all). This lets you
  **delete the separate friendly-labels, Upload, and Danger-Zone cards** —
  they fold into the one Unlock panel. Detailed in **§2.5**.

Variant B is the recommended target if there's appetite: it removes bottom
cards, and — because each page then *is* one row of the consolidated
Rosters page plus its expanders — it turns the eventual consolidation into
"stack the four index rows into one table," proving that shape per page
first. Variant A is the smaller, faster win if B is too much for one pass.

**In (both):** the row-action expander + 19L.2 bracket; keep the filter
strip (Status + Search + Clear).

**Out (both):** no consolidation; no new capabilities.

---

## 2. Case study: the Reviewers page

### 2.1 What it does today
`app/web/templates/operator/session_reviewers.html`:
- An **"Operator actions" card** doing two jobs at once:
  1. a **filter strip** — Status dropdown + Search box + Clear;
  2. an **action row** — `Edit`, `Inactivate`, `Activate`, `Add`,
     `Delete`, `Search`, plus a "N of M selected" pill and the delete
     confirm checkbox.
- The **preview table** below, each row with a `.reviewer-select`
  checkbox posting to the hidden `reviewers-bulk-form`.
- Selection→action JS enables buttons by **arity**:
  ```js
  setBtn(editBtn, n !== 1);        // Edit: exactly one row
  setBtn(inactivateBtn, n === 0);  // status flips: one or more
  setBtn(reactivateBtn, n === 0);
  ```
  and drives the "N of M selected" pill and the delete gate.
- Selected rows get **no visual marking** beyond the checkbox tick.
- Bottom: **Upload Reviewers** card + **Danger Zone** (Delete all reviewers).

### 2.2 What it becomes
- The action row **leaves** the Operator-actions card. That card keeps
  only the **filter strip** (rename it to just "Search & filter" if
  desired — it no longer holds actions).
- Ticking row checkboxes **marks the rows** with the bracket and **injects
  a bracketed expander** beneath the selection carrying the row actions:
  `Edit`, `Inactivate`, `Activate`, `Delete` (+ the delete confirm), and a
  title `N reviewers selected`.
- **Arity is preserved unchanged**: `Edit` enabled only at exactly one
  selected row; `Inactivate / Activate / Delete` at one or more. Same
  predicates, moved into the expander's render.
- **Add** stays as a page-level affordance (it isn't selection-driven) —
  keep it near the table/filter strip, not in the row expander.
- **Delete-all** stays in the **Danger Zone** card (it's roster-wide, not
  a row selection). Only the selection-Delete moves.

### 2.3 What moves where
| Control | Today | After |
|---|---|---|
| Status / Search / Clear | Operator-actions card | **stays** (filter strip) |
| Edit / Inactivate / Activate / Delete (selection) | Operator-actions action row | **row expander** beneath selection |
| "N of M selected" pill | Operator-actions action row | expander title |
| Delete confirm checkbox | Operator-actions action row | expander (beside Delete, like the lobby's `exp-allow-delete`) |
| Add | Operator-actions action row | page-level (near filter strip) |
| Delete-all | Danger Zone card | **stays** (Danger Zone) |
| Upload / friendly labels | their own cards | **stay** |

### 2.4 The operator actions differ per roster — especially Observers
This matters for the revamp: the expander is **not** a one-size-fits-all
component. It must render **the action set that roster actually has**, so
build it per page (a shared helper that takes each roster's action list is
fine; a shared component that hard-codes one list is not). The four pages
draw from a common vocabulary but do **not** carry the same set — measured
in the templates:

| | Reviewers | Reviewees | Relationships | Observers |
|---|---|---|---|---|
| **Row actions (→ expander)** | Edit · Inactivate · Activate · Delete | *same* | *same* | *same* **+ Edit cohort match rule** |
| Add (page-level) | ✓ | ✓ | ✓ | ✓ |
| Friendly-labels editor | tag labels (3) | tag labels | **Pair-context** labels | **none** |
| Upload columns | Reviewer* | Reviewee* + PhotoLink | Reviewer/Reviewee email + PairContext* | **ObserverEmail only** (+ Name, Tag1) |

**Observers is the outlier and should be treated as the stress test:**
- Its expander carries **one extra row action** — **Edit cohort match
  rule** (per-observer, `Observer.cohort_rule`; enabled at arity ≥ 1, a
  uniform op like status flips). Confirmed in `session_observers.html`
  (there is a "Cohort match rule" control; the other three have no analogue).
- It has **no friendly-labels editor at all** (no `_field_labels_editor`
  include), where the other three do.
- Its **Upload** requires only `ObserverEmail`.

So whatever you prove on Reviewers, **re-check it against Observers** before
calling the pattern done — if the expander render can express Observers'
extra action and the others' absence of it cleanly, it will handle
Reviewees/Relationships trivially. Relationships is the second watch-item:
its rows are reviewer→reviewee **pairs** and its labels are *pair-context*,
so its Edit acts on pair context, not a person.

### 2.5 Variant B — a single-row index + Unlock, and delete the bottom cards
The ambitious version. On top of Variant A, add to each page a **one-row
index** — the same row shape as the consolidated Rosters index, but with
just *this* roster in it — plus its **Unlock expander**.

**What the single index row carries** (per `guide/new_ux_ideas.md` §1):
- **Populated columns** — each header with its filled-row count
  (`Name (154)`, `Email (154)`, `Tutor (150)`…). Free re-house of the
  `col_data` the preview already computes.
- **Status** — the roster-level summary pill.
- **Unlock / Edit** — opens the metadata expander.
- **No "Work on" checkbox** — that affordance only exists to *choose
  between* rosters, and here there is only one. (Keep the row shape
  otherwise identical to the consolidated index so consolidation later is
  a straight stack.)

**What the Unlock expander carries** (the two-column panel from the
consolidated mockup, reused verbatim):
- **Left:** Upload / replace (with the current upload card's copy) +
  Download current CSV + the roster-naming replace confirm.
- **Right:** friendly-label edit boxes across a row → divider →
  Delete-all (with the roster-naming confirm).

**What this removes from the page:** the three separate cards at/near the
bottom — **friendly-labels editor**, **Upload CSV**, **Danger Zone** — all
fold into the one Unlock panel. Net change: the page **loses three cards**
and **gains one index row** (+ its on-demand expander). Tidier, and every
whole-roster action now lives in one deliberate, marked place.

**Resulting page shape** (top to bottom):
1. single-row index (+ Unlock expander when open);
2. **Search & filter** card, half width, flushed right;
3. preview table, with the Variant-A row-action expander on selection.

**Gating.** No cross-roster gate (one roster per page). But the **inner
Unlock gate still applies**: while the metadata expander is open, the
search card + preview go **inert** — you can't edit labels and select rows
at once. Model it on the **Instruments card**, which already does exactly
this at this scope: edit mode is a server-rendered `?editing=` URL marker +
`inert` on the locked region + the dirty/confirm/`beforeunload`
nav-away-discard guard. Reusing that means "nav away discards" is true
rather than aspirational (no client-only edit state to lose).

**Per-roster differences carry straight over (§2.4):** Observers' Unlock
has **no friendly-label editor** (that half of the right column is absent,
not blank); each roster's Upload copy differs. Relationships' labels are
*pair-context*.

**Why B is worth the extra work.** It removes clutter now *and* makes the
consolidation a low-risk follow-on: four pages that are each already "one
index row + expanders" consolidate by moving those rows into a shared
table and adding the chooser/gating — the hard parts (the two-column
Unlock panel, the row-action expander, the per-roster divergences) are
already built and proven per page.

**Visual reference.** The consolidated mockup already renders exactly this
per active roster — one index row, its two-column Unlock panel, the Search
card, and the preview with row expanders. For Variant B, look at a single
selected roster and **ignore the other three index rows and the
cross-roster gating**; what remains is the single-page target.

---

## 3. The pattern to copy — the Session Lobby

Read these before writing anything; the lobby already solved this and
19L Items 1–3 hardened it.

- **`app/web/templates/base.html`** — the bracket CSS (search `body.ui-v2
  .session-expander`, `.session-expander-bracketed`,
  `tr.session-row-selected`). Reuse these classes directly; do **not**
  reinvent the marking. Key facts baked in: selected rows carry **rails
  only, no fill** (a fill swallowed the pale status pills — see the long
  comment there); the panel's single colspan cell takes both rails +
  `--selection-panel-bg`.
- **`app/web/templates/operator/sessions_list.html`**:
  - `<template id="single-session-expander">` (line ~185) and
    `#bulk-session-expander` (~244) — the injected `<tr>` structure.
  - The selection JS: rows get `.session-row-selected`
    added/removed (~567–571); the expander is cloned and inserted
    **beneath the selected row** via `insertBefore`.
  - Note the lobby's single-select title reads *"1 session selected"*
    because the name shows in an editable field below; a roster expander
    has no such field, so its title should name the count plainly
    (`N reviewers selected`) — the identity is the marked row itself.
- **`guide/archive/segment_19L_ux_refinements.md`** — the reasoning behind the
  bracket (rails vs fill, one-row vs scattered, reflow), and the
  precedent for how to write this as a 19L-style item with a manifest +
  `close_check`.

**Caveat the lobby carries:** its expander action buttons are a
**placeholder** (`disabled`, only selection-management wired). The roster
version must actually wire the buttons — but they already work today (the
bulk form + arity JS exist), so this is moving live controls into the
expander, not building them from scratch.

---

## 4. Current Reviewers implementation to modify

`app/web/templates/operator/session_reviewers.html`:
- The `.operator-actions-card` block — split it: keep `.operator-actions-filter`
  (Status/Search), remove the `.filter-actions` action row.
- The bottom selection JS IIFE (`reviewers-edit-btn`, `.reviewer-select`,
  `setBtn(...)`, the "N of M selected" pill, the delete gate) — this logic
  moves into an expander-render/inject function modelled on the lobby's.
  The arity predicates are reused verbatim.
- The `reviewers-bulk-form` hidden form + the `form=` / `formaction`
  wiring on the buttons — carry into the expander's buttons unchanged
  (they post the same routes: `/bulk-inactivate`, `/bulk-reactivate`,
  `/bulk-delete`).
- `base.html` selection→button state helpers already grey `aria-disabled`
  buttons; keep using them inside the expander.

Then apply the same recipe to `session_reviewees.html`,
`session_relationships.html`, `session_observers.html` — but the action
sets differ per page, so render each page's set rather than assuming
Reviewers'. See **§2.4** for the full matrix; the headline is that
**Observers** adds an **Edit cohort match rule** row action and has no
friendly-labels editor, so it's the case that proves the expander render
is roster-specific rather than shared-with-one-hard-coded-list.

---

## 5. Open questions (small, resolve on the way)

1. **Scattered (non-contiguous) selection.** Where does the single
   expander go? Lobby injects beneath *the* selected row; with several
   non-adjacent rows, options are: beneath the last selected row, or a
   single sticky action bar. (The current mockup places it beneath the
   last selected row.) 19L flagged this as a live edge.
2. **Delete confirm placement.** Lobby puts an `exp-allow-delete` checkbox
   on the expander's button row (auto-margin pushes actions right). Reuse
   that; keep the roster-naming confirm copy ("delete these N reviewers…").
3. **"Search & filter" card** — once it holds no actions, does it stay a
   full-width card or shrink? (Out of scope to redesign; leaving it full
   width is fine for this step.)
4. **Ready / non-editable states.** Today the action controls hide on
   `is_ready` / non-editable sessions. The expander must respect the same
   gate — no expander (or a read-only one) when the roster isn't editable.

---

## 6. Visual reference

The interactive mockup — `rosters_mockup.html` (artifact
https://claude.ai/code/artifact/576778b2-7d07-4a4f-a394-05af18cd9403) —
already renders both variants' pieces:
- **Variant A:** the **preview table + its row-selection action row**.
  Ignore everything above the preview.
- **Variant B:** additionally, a **single selected roster's index row +
  its two-column Unlock panel + Search card**. Look at one active roster
  and **ignore the other three index rows and the cross-roster gating** —
  what's left is the single-page Variant-B target.

A dedicated single-page Reviewers mockup (no chooser) can be spun from it
on request.

---

## 7. Landing it

- Fits the **19L "UX refinements"** family; write it as a 19L item (manifest
  + `close_check`) or a small standalone segment.
- **Scaffold-first** per `CLAUDE.md`: land the expander shell (marked rows
  + injected panel with the buttons) on Reviewers first, verify the arity
  + routes still work, then repeat per page.
- **Sequence the variants.** Variant A (row-action expander) is a clean
  first slice on its own. Variant B adds, in a follow-on slice: the
  single-row index, the Unlock metadata expander, and the removal of the
  three bottom cards. No new routes — B re-houses existing upload /
  delete-all / field-label endpoints — but it **does** need an edit-mode
  marker for the Unlock gate: reuse the Instruments card's server-rendered
  `?editing=` + `inert` + `beforeunload` pattern rather than inventing one.
- **Add / update tests** for the selection→arity behaviour in its new home
  (current tests naming `.reviewer-select` / the bulk routes are the start);
  for B, tests that the folded-in upload / delete-all / label endpoints
  still fire from their new location.
- Keep each page a separate PR-sized slice — Reviewers proves the pattern;
  the other three are mechanical once it's proven (Observers last, as the
  divergence check per §2.4).

---

## 8. Source-of-truth files
- `app/web/templates/operator/session_reviewers.html` — the page to revamp.
- `app/web/templates/operator/sessions_list.html` — the lobby expander to copy.
- `app/web/templates/base.html` — `.session-expander*`, `tr.session-row-selected`.
- `guide/archive/segment_19L_ux_refinements.md` — the bracket's design + how to write the item.
- `spec/setup_pages.md` — "Operator actions card" (the strip this step splits) + shared body shape.
- `guide/new_ux_ideas.md` §1 — the parent idea; this step is its
  presentation half, minus consolidation.
