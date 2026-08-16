# 18R Item 2 — testing checklist

Manual / end-to-end things to verify for the Save·Lock harmonization
ladder (`guide/segment_18R_ux_refine.md`). The `pytest` suite covers the
rendered markup and the persistence routes; **this file is for the
behaviour the suite can't exercise** — real browser interaction (the
client lock-state machine, `inert`, CSS swaps, fetch-Save, drag/resize)
that only shows up on the Azure dev slot after deploy.

All operator checks are on **Setup → Instruments** for a session still in
the editable (pre-`ready`) window unless noted. Use a session with at
least **two instrument cards** — several items only show with more than
one card on the page.

**Shipped so far (all merged — test these now):** PR 1 scaffold (#1905) +
help-pencil fix (#1906), PR 2 dirty-tracking + staging harness (#1907),
PR 3 consolidated JSON Save route (#1908), PR 4 inline-editor retirement
(#1909).

**Not built yet:** PR 5 (Band 2 state → staging + lost-edit fix), PR 6
(identity/order fold-in), PR 7 (cleanup). Their sections are at the bottom
so you don't test behaviour that isn't wired yet.

Legend: ☐ = to verify.

---

# A. Ready to test now (PRs 1–4, merged)

## A1. Lock / Unlock toggle
- ☐ A card loads **locked**: the **Unlock** button shows; Save / Cancel /
  Lock are hidden.
- ☐ Clicking **Unlock** flips the card to edit in-place — **no page reload,
  no scroll jump** — and the cluster swaps to **Lock · Save · Cancel**.
- ☐ Clicking **Lock** (nothing edited) flips straight back to the locked
  view, no reload.
- ☐ Both the **heading-row** and **bottom-row** toggles work and keep the
  whole card in sync.
- ☐ The **Locked / Unlocked pill** in the card title matches the state after
  each toggle.
- ☐ An in-page Unlock does **not** add `?editing=<id>` to the URL (client
  toggle, not navigation).

## A2. Read-only enforcement while locked (`inert`)
- ☐ On a locked card you **cannot** focus or change any Band 1 rule control,
  Band 2 preview control, or Band 3 visibility chip / Response-Field input.
- ☐ Locked editable regions show the faded (read-only) look; unlocking
  restores full opacity.
- ☐ The Band 2 **↻ Refresh sample** button is hidden while locked, shown
  when unlocked.

## A3. Inline text boxes follow the lock state (PR 4 — the ✎/✓ retirement)
The three text boxes — **card-title short label**, **Band 2 description**,
and each **Band 2 per-field help-text** box — no longer have ✎ / ✓ buttons.
- ☐ There is **no ✎ pencil or ✓ tick** anywhere on the card for these boxes.
- ☐ **Unlock** → all three become directly editable fields (the help boxes
  render as textareas in the preview; the short label as an input in the
  heading; the description as a textarea).
- ☐ **Lock** → each box **collapses to plain rendered text** (not an empty
  or disabled input box). A cleared short label shows the `Instrument_<id>`
  fallback.
- ☐ Edit the short label → **Save** → **Lock**: the card heading **and** the
  reviewer-preview `#N: <label>` both show the new label, **no reload**.
- ☐ Edit a help-text box → **Save** → reload the page → the help text stuck.
- ☐ Editing any of these boxes enables **Save / Cancel** (marks the card
  dirty) — same as any other edit.
- ☐ Locking a card with unsaved text fires the unsaved-changes confirm
  (see A4); if you lock anyway, the box shows your typed (unsaved) text —
  that's intended (consistent with the other controls). **Cancel** is how
  you truly revert.

## A4. Dirty-aware Save / Cancel + Lock guard
- ☐ Save + Cancel start **disabled (greyed)** on a freshly unlocked card.
- ☐ Editing anything (Band 1 select, a Band 3 tick, a Response-Field label,
  a sort-badge click, one of the A3 text boxes) **enables** both Save and
  Cancel, on the heading and bottom rows in lockstep.
- ☐ **Lock while dirty** → "unsaved changes" confirm. Declining keeps the
  card unlocked with edits intact; accepting locks it.
- ☐ **Unlock never prompts** (entering edit can't lose work).
- ☐ **Cancel** → confirm → discards (the page reloads to the last-saved
  state).

## A5. One card editable at a time (PR 2)
- ☐ Unlock card A and **edit** it (now dirty). Click **Unlock on card B** →
  blocked with an alert: *"Another instrument has unsaved changes. Save or
  cancel it before editing this one."* Card B stays locked.
- ☐ Unlock card A but **don't** edit it (clean). Click **Unlock on card B**
  → card A locks silently and card B unlocks. Only one card is ever
  unlocked at a time.

## A6. Nav-away guard (PR 2)
- ☐ Unlock + edit a card (dirty), then try to **close the tab / navigate
  away** → the browser's "Leave site? Changes may not be saved" prompt.
- ☐ After a successful **Save** (card clean), navigating away does **not**
  prompt.
- ☐ *Known interim quirk:* because Band 2 field pills and column-width drag
  still save immediately (see A7), clicking one marks the card dirty even
  though it already persisted — so the nav-away prompt can fire when nothing
  is truly unsaved. This tightens in PR 5; not a bug to report.

## A7. Consolidated Save — no reload + validation banner (PR 3)
- ☐ Unlock → edit → **Save**: the card **stays unlocked**, **no reload / no
  scroll jump**, and Save + Cancel grey back out (card is clean again).
- ☐ Reload the page afterwards → the edits persisted.
- ☐ **Force a validation error:** set **4 sort badges** on the Band 2 preview
  header (the cap is 3) → **Save** → a **red summary banner** appears at the
  top of the (still-unlocked) card listing the blocker; your edits stay.
  Remove a badge → Save → the banner clears and it saves.

## A8. What persists on Save vs immediately (current hybrid)
Persist on **Save** (unlock → edit → Save → reload to confirm):
- ☐ Band 1 assignment-rule links + Link 3 unit of review.
- ☐ Band 3 visibility chips + Response-Field required / help toggles.
- ☐ Sort-badge order.
- ☐ Short label + description + per-field help text (A3).

Still save **immediately on click** (persist without Save — PR 5 folds
these into Save):
- ☐ Band 2 **field pills** (selecting / deselecting a response field, type /
  bounds) — persist on click.
- ☐ **Column-width drag-resize** — persists on drag-end.

## A9. No-JS fallback
- ☐ With JavaScript disabled: **Unlock** navigates to `?editing=<id>` and the
  server renders that card unlocked; **Lock** navigates back to the bare URL;
  **Save** posts the form and reloads. (Progressive enhancement intact.)

## A10. Multi-card / regression
- ☐ Replicate / Delete / +Instrument / +Page break still work from a card in
  either state.
- ☐ Collapsible card open/close chevron still works; the just-saved card
  stays expanded.
- ☐ Group-scoped instrument card renders and toggles the same way.
- ☐ A `ready` (post-setup) session: cards are force-locked and the toggle is
  disabled — no way to edit.

---

# B. Not built yet — don't test (PR 5+)

## PR 5 — Band 2 state → staging + lost-edit fix
- Band 2 field pills + column-width drag **stop** immediate-POSTing (Network
  tab shows no `/band2-state` or `/column-widths` until Save).
- Response-Field **✓** becomes push-to-preview only.
- The **lost-edit bug** is fixed (a Response Field typed into a new row but
  never committed is captured on Save).
- Once this lands, the A6 nav-away quirk and the A8 "immediate" list go away.

## PR 6 — identity + display order fold-in
- `/identity` retired from the card; display-field reorder folds into Save.

## PR 7 — cleanup
- Retired endpoints gone; final button-state-matrix pass; dead ✎/✓ handlers
  swept.

---

# C. Cross-cutting regression sweep (quick pass)
- ☐ Quick Setup card still saves and locks-on-nav.
- ☐ Session Home / Setup nav / breadcrumbs unaffected.
- ☐ Reviewer surface + reviewee `/results` + observer `/collation` unaffected
  (Instruments-page changes don't leak).
- ☐ Dark-mode / typography-knob render of the cards.
- ☐ **No console errors** on load or on any toggle / Save / Lock.
