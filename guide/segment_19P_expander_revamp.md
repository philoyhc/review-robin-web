# Segment 19P — the expander revamp

**Opened:** 2026-09-14 · **Theme:** re-house selection-driven controls into the
Session Lobby's row-expander idiom, page by page · **Related:**
`guide/roster_expander_revamp_handoff.md`, `guide/new_ux_ideas.md` §1,
`spec/setup_pages.md`

Split out of 19O at 175 lines, when the Reviewers item outgrew the ~120-line
item budget: the work retires three cards, changes five specs and spans four
rungs across six pages. **19O keeps bug fixes**; this segment carries the
revamp.

**Items close independently**, so each carries its own `### Doc impact` and
`### Status`, and there is **no segment-level `## Doc impact`**.
`python3 tools/close_check.py 19P.1` reads Item 1's manifest.

**Items 2–4 are stubs.** They record the sequence and why, not a plan; each is
planned in full when it is taken up.

---

## Item 1 — Reviewers moves to the lobby's expander idiom

Pilot for `guide/roster_expander_revamp_handoff.md` — **Variant B on Reviewers**,
the presentation half of `guide/new_ux_ideas.md` §1, minus consolidation.

### Opportunity

The *"Operator actions"* card does two jobs — a filter strip **and** an action
row whose buttons act on rows selected below, with nothing marking which rows
those are. 19L solved this for the lobby; the roster pages never got it.

Separately, **three cards** hold whole-roster affordances away from the roster
they act on: `#upload-csv` and `.danger-zone` at the bottom, and the
`_field_labels_editor` card at the top, in the left column of `card-columns`.
The author's target: **retire all three** into a roster-level Unlock expander.

### Decision

**Variant B on Reviewers, targeted directly** — author's call, not staged
behind a shippable Variant A. B contains A, so the row expander still lands;
it simply is not a milestone of its own. Reuse `base.html`'s
`.session-expander*` / `tr.session-row-selected` rather than reinventing the
marking. The one-row roster index and its **Unlock** expander absorb all three
cards, which are then deleted.

*The trade:* staging A would leave a shipped fallback if B's surface is wrong.
Rung 1 answers that instead — the whole shape, inert, looked at before wiring.

**The expander renders each roster's own action set** — a helper taking an
action list, not one hard-coding it. Observers has a fourth action
(`cohort-rule`) and no labels editor, so a fixed list is the "list someone must
remember to extend" that 19N.1 inverted its test to escape.

**The Unlock gate extends the page's existing `edit_mode`**, not a ported
`?editing=`. `session_reviewers.html:14` already computes
`edit_mode = (edit_id is not none) or add_mode`; `:102` locks the actions card
and `:276` sets `selectable = not edit_mode and is_editable`. Unlock is a
second mode of the same shape.

**Rejected: Observers last** (the handoff's order). The first three pages are
*identical* in action set, so they cannot falsify the render's shape — finding
on page four that it cannot express Observers means reworking three shipped
pages. Observers goes second, as 19P.2.

### Semantics

- **Arity is preserved verbatim.** `Edit` at exactly one row;
  `Inactivate / Activate / Delete` at one or more.
- **`Add` stays page-level**, and keeps its own `is_ready` gate
  (`session_reviewers.html:160`) — which this item does not touch.
- **Routes are unchanged** — the three bulk routes, the upload POST and
  `delete-all` keep their URLs and hidden-form wiring.
- **No expander when the session is not editable.** One gate, `is_editable`
  (`:146`), matching what hides the action row today.
- **The expander anchors after the most recently ticked row still selected**,
  with DOM order only as fallback — `sessions_list.html:585`
  (`currentAnchor() || selected[selected.length - 1]`). 19L **settled** this
  rather than leaving it open; do not restate it as "the last selected row".
- **Unlock and row-selection are mutually exclusive** — that is the gate.

### Judgment calls — decided

- **2026-09-14.** Reviewers only; Observers next as 19P.2, so the divergence is
  proven before the mechanical pages are touched.
- **2026-09-14.** **No Variant-A milestone** — author's call. A shipped
  row-expander-only step would have to be un-shipped by B's index row two
  slices later, and the handoff's case for A standing alone assumes the cards
  stay, which here they do not.
- **2026-09-14.** All three cards are **deleted**, not hidden behind a flag —
  author's call, confirming what `guide/new_ux_ideas.md:67-76` already put in
  the roster row. A flag leaves two live surfaces for one action.
- **2026-09-14.** `.session-row-selected` is promoted past "**Not a general
  primitive**" (`spec/ui_elements.md:592`), which withheld the transfer and
  named a Rosters index as the speculative third caller — this is that caller.
  The edge it was not designed against (`new_ux_ideas.md:270-279`: *the row can
  sit above a tall panel or scroll off*) is live here, since Unlock is such a
  panel; rung 1 answers it on the dev slot, not in a test.
- **2026-09-14.** **No Download.** The handoff's Unlock panel has one; this page
  has none (`grep -cin 'download\|export'` → 0) — the roster CSV is on Extract
  data (`_extracts.py:108`). Adding it would be a new capability.

### Blast radius (measured)

At `46688cb`:

- `wc -l app/web/templates/operator/session_reviewers.html` → **728**;
  `grep -c operator-actions` → **5**; `grep -c edit_mode` → **19**.
- Cards retired: `#upload-csv` (`:624`), `.danger-zone` (`:690`) and the
  `_field_labels_editor` card (`:91`, 111 lines). The last sits inside
  `card-columns` (`:48`) — which **stays a two-column container**: page
  guidance shares that left `<div>` (`:49-78`) and remains. `spec/setup_pages.md:94`
  becomes "guidance alone on the left"; `.card-columns` itself is not removed,
  and `:78-91` argues at length that it must not be.
- `grep -oE 'formaction="[^"]*"' | sort -u | wc -l` → **3 / 3 / 3 / 4** and
  `grep -c 'setBtn('` → **4 / 4 / 4 / 5** across
  reviewers / reviewees / relationships / observers.
- `grep -c 'session-expander\|session-row-selected' base.html` → **18**;
  `#single-session-expander` (`sessions_list.html:185`) and `#bulk-expander`
  (`:243`) carry live `formaction`s — only the two `data-expander-delete`
  buttons (`:237`, `:285`) are `disabled`, a two-stage gate. The template's
  comment (`:182-184`) still calls them placeholders, **stale** since
  `d2c8671` — the handoff's error came from there, and rung 1 fixes it.
- `grep -rl 'reviewers/bulk-\|reviewers/delete-all\|danger-zone\|upload-csv'
  tests/ --include=*.py | wc -l` → **15**; narrowed to
  `reviewers/bulk-\|reviewers/delete-all` → **6**. Two of that six move —
  `test_reviewers_page_mutate.py`, `test_setup_danger_zone_delete_all.py`.
  `test_setup_selection_lifecycle.py` also moves and is **not** in either
  count: it parameterizes the page (`f".../{page}/bulk-delete"`), so no
  literal matches.
- Specs, by `grep -ci` on *danger zone* / *upload card* / *operator actions*:
  `setup_pages.md` **12/8/16** (the owner), `operator_button_audit.md`
  **12/0/28**, `operator_ui_concept.md` **7/2/3**, `ui_elements.md` 1/0/2,
  `rrw_functional_spec.md` 4/1/0 — all five are in the manifest.

### PR ladder

1. **Scaffold — the whole B surface, inert.** Bracket, row expander, one-row
   index and Unlock panel, with real copy and layout and no wiring; the three
   cards still present and still live. This is the slice that gets looked at
   on the dev slot before anything moves. Must not touch `spec/`.
2. **Wire the row actions.** They move into the expander, arity preserved,
   routes unchanged; the action row leaves the card, which keeps the filter
   strip. Must not touch `spec/`.
3. **Wire Unlock and retire the three cards.** Upload, Delete-all and the
   friendly labels move into Unlock; `#upload-csv`, `.danger-zone` and the
   `_field_labels_editor` card are deleted; the gate extends `edit_mode`.
   Must not touch `spec/`.
4. **The specs, last** — after the cold readers, so the pre-push `spec-writer`
   pass is the final word; the ordering 19O.3's close left untested. **The
   shared-shape problem is this rung's:** `setup_pages.md:47` and `:525` state
   one shape for all **four** pages; `operator_ui_concept.md:258` states one for
   the **three** roster Setup pages. This item changes one, so rung 4 states
   **two** shapes in each — Reviewers' and the others' — naming 19P.2 next.

### Definition of done

- The rendered page carries the bracket class and an expander node beneath the
  anchor row, asserted server-side. *No JS runtime in the suite, so tests assert
  the mechanism — classes, markup, routes — not appearance; 19L stated the same
  limit (`archive/segment_19L_ux_refinements.md:207-209`).*
- `Edit` enabled at exactly one row, the other three at one or more, asserted.
- `grep -c 'id="upload-csv"\|danger-zone' session_reviewers.html` → 0, and the
  `_field_labels_editor` include appears **once**, inside the Unlock panel —
  the partial survives as a file (Reviewees and Relationships still include it)
  and is re-used there, not duplicated.
- Upload, delete-all and the label save each fire from inside Unlock,
  asserted by route.
- `edit_mode`-style locking: with Unlock open the preview renders
  non-selectable, asserted server-side.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19P.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. **Does the filter card shrink** once it holds no actions? Full width is fine
   for this item.

### Out of scope

- **Consolidating the four pages.** `guide/new_ux_ideas.md` §1; unchanged.
- **A shippable Variant A.** Declined above; B contains it.
- **The other three rosters.** Observers is 19P.2 and proves the divergence.
- **New capabilities** — including **Download**, per the judgment call above.

### Doc impact

- `spec/setup_pages.md` — § *Shared body shape* items 4 and 6 and its `.card-columns` table row (`:94`, which sites the tag-label editor in the left column), § *Operator actions card*, § *Deleting the selected rows*, § *Per-row Edit / Add / bulk actions*, the Reviewers § *Body grid* and § *Implementation pointers* re-describe the expander and the Unlock panel. The two bottom-card sections lose their **card** description; their **route contract** — `confirm` / `confirm_replace` / `acknowledge_response_loss`, the failure modes, the three-state wording — is preserved verbatim, only re-homed (Item 1).
- `spec/operator_button_audit.md` — the Reviewers actions-strip rows move to the expander; rows **105 / 106** (`:220-221`, the tag-label Cancel / Save labels) and rows **35 / 37** (`:223`, `:233`, whose cells site the button "below the preview table") are **re-sited into Unlock, not retired** — their routes and destructive role survive; the `> Upload and Danger Zone buttons — must be absent, not disabled` gate (`:211`) is reframed around an Unlock panel rather than two cards; and the `.btn.destructive` "outside a danger zone" sentence (sibling of `ui_elements.md:368`) is restated for the expander (Item 1).
- `spec/operator_ui_concept.md` — the shared Setup shape (`:258`, stated for the **three** roster pages) changes at items 3, **4** (`:265`, the leftmost checkbox column "drives the operator-actions selection" — after this it drives the injected expander), 5 and 6, and gains the roster index row (Item 1).
- `spec/ui_elements.md` — `.session-expander*` and `tr.session-row-selected` stop being lobby-only, and §6's `.btn.destructive` note stops siting the roster Delete "between `Add` and `Search`" (Item 1).
- `spec/rrw_functional_spec.md` — the Danger Zone and Upload card descriptions at §§ around `:1044`, `:1111`, `:1113` retire (Item 1).
- `guide/roster_expander_revamp_handoff.md` — dated annotation recording the four claims 19O.4 falsified (Item 1).

- `spec/settings_inventory.md` — §2.5's *Surface → Edit* line (`:140-141`) sites the labels editor as an "Inline editor card **above the data table** on `/operator/sessions/{id}/reviewers`"; that is the position this item moves, stated per page (Item 1).

*Not in the manifest, deliberately:* `spec/csv_contracts.md` — its one editor mention (`:77`) is non-positional, and the friendly-label **header grammar** it owns is untouched by where the control renders.

---

## Item 2 — Observers, the divergence proof

**Not yet planned.** Second, deliberately, and not fourth. Observers is the only
roster that differs: **4** `formaction` targets and **5** `setBtn(` lines against
3 and 4 on the other three, an extra row action (`cohort-rule`), and **no**
`_field_labels_editor` — so its Unlock panel is missing that half of the right
column rather than rendering it blank.

Reviewers / Reviewees / Relationships are *identical* in action set and so
cannot falsify the expander's shape. Proving it on Reviewers and then Observers
tests both ends in two items; leaving Observers until last risks reworking
three shipped pages. 19N.1 paid for the same mistake — a blast radius that
counted callers could not falsify the claim it was making, and took three
verification passes to close.

---

## Item 3 — Reviewees and Relationships

**Not yet planned.** Mechanical once Items 1 and 2 land, and measurably so:
both match Reviewers exactly on action set (3 / 3) and arity (4 / 4), and both
carry a labels editor. Likely one item, possibly one PR each.

The one watch-item is Relationships: its rows are reviewer→reviewee **pairs**
and its labels are *pair-context*, so its `Edit` acts on a pair, not a person.

---

## Item 4 — Invitations and Responses — a different move, not the same recipe

**Not yet planned, and not the same work.** Measured on `session_invitations.html`
(298 lines) and `session_responses.html` (221): **zero** `operator-actions`
cards, **zero** `formaction`s, **zero** `setBtn(` lines, **zero** selection
checkboxes. Their `<thead>` buttons are column sorts, and each row carries a
single link to a detail page (`session_invitations_reviewer_detail.html`,
`session_responses_reviewee_detail.html`).

So there is **nothing to re-house**. The roster revamp moves existing controls;
here the equivalent move is a redesign — replacing *navigate to a detail page*
with *select a row, see its detail in the expander* — which would add selection
where none exists and make two detail pages redundant or secondary.

That may well be right, and it is the same principle (put the thing beside the
row it belongs to). But it is a **new capability**, so it needs its own
Opportunity and its own decision about the two detail pages, and it should not
inherit the roster items' "re-houses, adds nothing" justification. Sequenced
last, contingent on the idiom proving out on the four rosters.
