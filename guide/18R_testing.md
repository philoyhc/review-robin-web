# 18R Item 2 — testing checklist

Manual / end-to-end things to verify for the Save·Lock harmonization
ladder (`guide/segment_18R_ux_refine.md`). The `pytest` suite covers the
rendered markup and the persistence routes; **this file is for the
behaviour the suite can't exercise** — real browser interaction (the
client lock-state machine, `inert`, CSS cluster-swap, drag/resize), and
the cross-page flows that only show up on the Azure dev slot after deploy.

All operator checks are on **Setup → Instruments** for a session still in
the editable (pre-`ready`) window unless noted. Use a session with at
least **two instrument cards** — several bugs only show with more than one
card on the page.

Legend: ☐ = to verify. Mark the PR each item first applies to.

---

## PR 1 — client lock-state scaffold (#1905)

The suite asserts the markup (always-rendered controls, `data-instrument-locked`
seeding, `inert` regions, cluster markers). It does **not** click anything.
Verify the live behaviour:

### Lock / Unlock toggle (the core surface)
- ☐ A card loads **locked**: edit controls visible but read-only, the
  **Unlock** button shown, Save/Cancel/Lock hidden.
- ☐ Clicking **Unlock** flips the card to edit in-place — **no page
  reload / no scroll jump** — controls become interactive, and the button
  cluster swaps to **Lock · Save · Cancel**.
- ☐ Clicking **Lock** (nothing edited) flips straight back to the locked
  read-only view, no reload.
- ☐ Both the **heading-row** and **bottom-row** Lock/Unlock toggles work
  and stay in sync (toggling one updates the whole card).
- ☐ The **Locked / Unlocked pill** in the card title matches the current
  state after each toggle.
- ☐ URL does **not** gain `?editing=<id>` on an in-page Unlock (client
  toggle, not navigation).

### `inert` / read-only enforcement while locked
- ☐ On a locked card you **cannot** focus or edit any Band 1 rule control,
  Band 2 preview control, or Band 3 visibility chip / Response-Field input
  (they're `inert`).
- ☐ Locked editable regions render at the faded (0.75 opacity) read-only
  look; unlocking restores full opacity.
- ☐ The card-title ✎ and the Band 2 intro ✎ are **hidden** while locked,
  and appear once unlocked.
- ☐ The Band 2 **↻ Refresh sample** button is hidden while locked.

### Dirty-aware Save / Cancel
- ☐ Save + Cancel start **disabled** on a freshly unlocked card.
- ☐ Editing anything (Band 1 select, a Band 3 tick, a Response-Field
  label, a sort-badge click) **enables** both Save and Cancel, on both the
  heading and bottom rows in lockstep.
- ☐ **Lock while dirty** prompts the "unsaved changes" confirm; declining
  keeps the card unlocked with edits intact; accepting locks it.
- ☐ **Unlock never prompts** (entering edit can't lose work).
- ☐ **Cancel** confirms, then discards (reloads to persisted state).

### Persistence unchanged (PR 1 must not regress saving)
- ☐ Unlock → edit Band 1 links → **Save** persists and the card stays
  unlocked (Save owns persistence, Lock owns the gate).
- ☐ Band 3 visibility chips + Response-Field required/help edits still
  save via the existing routes.
- ☐ Column-width **drag-resize** still persists (still immediate-POST in
  PR 1 — not yet staged).
- ☐ Card-title ✎ and intro-description ✎ still save immediately via
  `/identity`.
- ☐ Sort-badge clicks still round-trip into the saved sort spec.

### No-JS fallback
- ☐ With JavaScript disabled, **Unlock** still navigates to
  `?editing=<id>` and the server renders the card unlocked; **Lock**
  navigates back to the bare URL. (Progressive enhancement intact.)

### Multi-card / regression
- ☐ With several cards, unlocking card B does **not** disturb card A
  (each card's cluster and lock state are independent).
- ☐ Replicate / Delete / +Instrument / +Page break still work from a
  card in either state.
- ☐ Collapsible card open/close chevron still works; the edited/just-saved
  card auto-expands.
- ☐ Group-scoped instrument card renders and toggles the same way.
- ☐ A `ready` (post-setup) session: cards are force-locked and the toggle
  is disabled — no way to edit.

---

## PR 2 — dirty-tracking + staging harness (upcoming)
- ☐ Edits stage client-side and **nothing persists** until Save.
- ☐ **One card at a time**: unlocking card B while card A is dirty prompts
  to Save/Cancel A first.
- ☐ **Nav-away / tab-close** with unsaved edits triggers the `beforeunload`
  confirm.
- ☐ Cancel discards staged edits **without** a server round-trip.

## PR 3 — consolidated Save route (upcoming)
- ☐ Save fetch-POSTs the full payload; on success the dirty flag clears
  and the card **stays unlocked with no reload**.
- ☐ **Validation failure** keeps the card unlocked with edits intact and
  shows the summary banner at the top of the card, listing the blockers.
- ☐ One Save writes Band 1 + Band 2 + Band 3 + identity + sort + column
  widths **atomically** (all-or-nothing).

## PR 4 — Band 2 → staging (upcoming)
- ☐ Pills / help text / column-width drag stop immediate-POSTing (Network
  tab shows **no** `/band2-state` or `/column-widths` calls until Save).
- ☐ Response-Field **✓** becomes push-to-preview only (no persist).
- ☐ The **lost-edit bug is fixed**: every named/edited row is captured on
  Save.

## PR 5 — identity + display order → staging (upcoming)
- ☐ Name / short_label / description stop immediate-POSTing; they ride the
  consolidated Save (no `/identity` calls until Save).
- ☐ Display-field reorder folds into the Save payload (no in-card
  `/display-fields/order` calls).

## PR 6 — cleanup (upcoming)
- ☐ Retired endpoints return 404/405 from the card (or are kept only where
  a verified non-card caller needs them).
- ☐ Full button-state matrix (locked / unlocked-clean / unlocked-dirty)
  behaves across every card type.

---

## Cross-cutting regression sweep (run once per PR on the dev slot)
- ☐ Quick Setup card still saves and locks-on-nav.
- ☐ Session Home / Setup nav / breadcrumbs unaffected.
- ☐ Reviewer surface + reviewee `/results` + observer `/collation`
  unaffected (Instruments-page changes don't leak).
- ☐ Dark-mode / typography knob render of the cards.
- ☐ No console errors on load or on any toggle/save.
