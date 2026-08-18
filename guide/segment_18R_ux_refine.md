# Segment 18R — UX refinement

**Status:** In progress — **Item 1 shipped 2026-08-16 (PR #1899)**; **Item 2
shipped 2026-08-17 (save/lock harmonization; PR ladder 1–7 incl. 5c, cleanup
closed by PR #1921)**; **Item 3 open (instrument-card UX tweaks; first two
shipped 2026-08-17, PR #1923; +vertical-only textarea resize app-wide
2026-08-18)**; **Item 4 in progress (consolidate session config onto Session
Home + retire the Edit page — Option 2; Slices 1–5b + the sessions/new
alignment done 2026-08-18 (config save + owners wired, Edit page fully retired,
create page mirrors Home's bottom row))**; **Item 5 done 2026-08-18 (Archive
session card wired on the Extract data page — reuses the Workflow archive
route, gated on `is_expired`; promoted from Item 4 Slice 6)**. A holding segment for **operator-UX refinement** on
already-shipped surfaces — clarifying what each card / control *is*,
tightening labels, strengthening visual identity, and **rationalizing
inconsistent interaction models**. Most items are small identity / label
polish (no behaviour change); some — like the save/lock harmonization
(Item 2) — are larger structural rationalizations. Items land as independent
slices; the segment stays open as a home for further UX refinements.

> Consequential-UI note: per `CLAUDE.md` → "Working approach", anything that
> adds a card / nav / affordance lands **scaffold-first**. The items here are
> mostly *re-labelling and identity* on existing cards, so most are a single
> reviewable template slice; call out scaffold-first only where an item adds a
> genuinely new surface.

---

## Item 1 — Instrument card identity (retire "Band 1" → "Instrument assignment rule") — ✅ shipped (PR #1899, 2026-08-16)

**Shipped:** the top band is now the bold **Instrument assignment rule** card;
the three Links read **Who does the review / Who is being reviewed / Unit of
review** (unbold). Operator-facing labels only — internal `band1` / `link1`–
`link3` ids retained. Specs (`instruments.md`, `assignments.md`) + quickstart
§4c updated. Full suite green. The problem / fix record is kept below for
history.

**The problem.** On the per-instrument card (Instruments page,
`app/web/templates/operator/instruments_index.html`), the **top band** — the
three assignment-rule **Links** (Pool of reviewers / Pool of those reviewed /
Unit of review) — renders directly under the editable **Instrument Name**
with **no card title of its own**. It's referred to informally as "**Band 1**"
(an internal build-era name), which leaks into operator-facing docs. The cards
*below* it (Preview review instrument, Visibility, Response Fields) each read
as a clearly identified card; the top band does not, so operators have no
name for the single most important control on the page.

**The fix.**

1. **Give the top band a card title — "Instrument assignment rule"**, **bold**,
   styled to **match the other card names** on the instrument card (e.g.
   "Preview review instrument"): same heading treatment, sitting between the
   Instrument Name (above) and the Preview review instrument card (below). (The
   "Instrument" prefix disambiguates the card from the Operations-row
   **Assignments** page; chosen over plain "Assignment rule" for that reason.)
2. **Relabel the three Links** (the sub-headings inside the card) to plainer
   operator language. These stay **unbold** — the bold card title vs unbold
   link labels gives the visual hierarchy:

   | Current label | New label |
   |---|---|
   | Pool of reviewers | **Who does the review** |
   | Pool of those reviewed | **Who is being reviewed** |
   | Unit of review | *Unit of review* (unchanged) |

3. **Strengthen every section's identity in the same pass** — make the card
   set on the instrument card self-describing and visually consistent
   (Instrument Name → Instrument assignment rule → Preview review instrument →
   Visibility → Response Fields). Titles / headings / labels only; no
   behaviour or layout-logic change.
4. **Rename the operator-facing "Band 1" wording** in `spec/instruments.md`
   and `spec/assignments.md` to "Instrument assignment rule", and the Link labels to
   match #2 (both specs describe the three Links by their old names). The
   **internal** `band1` code identifiers (`_band1.py`,
   `set_band1_assignment_rules`, `new_model_band1_state`, CSS/data attributes,
   the `band1_touched_links` column) and the internal `link1`/`link2`/`link3`
   ids **stay** — renaming those is churn with no user benefit; this item is
   about the *operator-facing* names only.

**Scope / size.** A **small** template slice on `instruments_index.html`
(add the bold card title, relabel the three Link sub-headings, tidy the
section identities) + the spec/quickstart wording updates. No route, service,
model, or migration change — the Link `link1`/`link2`/`link3` ids and all
`band1` internals are untouched. No test change expected beyond any
template-string assertion that greps for an old label (check `tests/` for
"Band 1" / "Pool of reviewers" / "Pool of those reviewed" before pushing).

**Definition of done.**

- The instrument card's top band shows a **bold "Instrument assignment rule"** title,
  styled like the other card names; the five sections read as
  consistently-identified cards.
- The three Links read **Who does the review / Who is being reviewed / Unit of
  review** (unbold).
- `spec/instruments.md` / `spec/assignments.md` say "Instrument assignment rule" and the
  new Link labels for the operator-facing names (internal `band1` / `linkN`
  identifiers unchanged, with a one-line note that the code names are
  retained).
- `docs/quickstart.md` §4c updated to the new Link labels (it currently uses
  "Pool of reviewers / Pool of those reviewed / Unit of review"); its
  `08-band1-rule.png` screenshot slot recaptioned to `08-assignment-rule.png`
  when screenshots are produced.
- Full suite green; `ruff` clean.

---

## Item 2 — Harmonize the save / lock model (one persistence path)

**Status: ✅ Completed 2026-08-17.** PR ladder 1–7 (incl. 5c) shipped;
cleanup closed by PR #1921. The card now drives a single consolidated
`/save`; the per-concern routes are retired from the card but kept
server-side (see the Route-retirement outcome note below).

**The problem.** The per-instrument card mixes **three** persistence paths
(full audit: `guide/archive/instrument_card_ux_audit.md`):

- **A — staged → Save** (Assignment rule / Band 1; Visibility / Band 3);
- **B — immediate async POST on click** (most of Preview / Band 2 — field
  pills, help text, column widths; the Response-Field `R` / `✓` / `X`; the
  instrument name — via `/band2-state`, `/identity`, `/column-widths`,
  `/display-fields/order`);
- **C — client-only**.

This is inconsistent and produces a **lost-edit bug**: a Response Field typed
into a new row but never `✓`'d is silently dropped on Save. There's also no
single, predictable "am I editing / have I saved?" model — the lock toggle,
the bottom Save button, and the per-control auto-saves don't add up to one
contract.

**The target model — one framework, every editable element inside it.**

**Keep the current button trio — Save · Lock · Cancel — in their current
positions** (revised 2026-08-16 after hands-on testing). Save and Lock are
**separate** so the operator can *save progressively* ("lock in" edits along
the way) and only **Lock** the instrument when fully done. This item governs
**only** the edit / save / lock cluster; the card / session action buttons —
**Replicate, Delete, +Instrument, +Page break** — are explicitly **out of
scope** and unaffected.

| Card state | Editable? | Buttons in the edit/save/lock cluster |
|---|---|---|
| **Locked** (default) | No | **Unlock** — nothing else |
| **Unlocked, clean** (no unsaved edits) | Yes | **Save** *(greyed)* · **Lock** · **Cancel** *(greyed)* |
| **Unlocked, dirty** (unsaved edits) | Yes | **Save** *(active)* · **Lock** · **Cancel** *(active)* |

- **Save** — persists **all** staged edits (the consolidated writer below) and
  **stays unlocked** with the card now clean; greyed when there's nothing to
  save. This is the progressive "save along the way" gesture.
- **Lock** — returns the card to read-only. If there are unsaved edits, it
  fires the **unsaved-changes guard** (warn → Save or discard first) — the same
  guard as navigating away.
- **Cancel** — discards all staged edits and returns the card to
  **unlocked-clean** (still editable); greyed when there's nothing to discard.
- **Unlock** — the only control on a locked card; enters edit mode.

**Unified persistence.** Every editable / changeable element **stages** its
change client-side (into one per-card pending-edit set / dirty tracker) and is
persisted **only** by **Save**. This retires the in-card immediate POSTs: the
current path-B controls fold into a single consolidated Save writer. The live
**preview** still updates as you edit (client render), but **nothing hits the
server until Save**.

**This fixes the lost-edit bug for free** — with all editable elements in the
framework, a newly-typed Response Field is captured by **Save** whether or not
the per-row control was clicked. The per-row **✓** becomes a pure
**push-to-preview** affordance: clicking it registers the row's edit into the
live preview but **does not persist** — persistence happens only on **Save**.
**Glyph:** keep the **✓ tick** (the earlier ⬆ idea is optional — now that its
meaning is "reflect my edit in the preview", the tick reads fine).

**Per-row button states (R / ≡ / ✓ / X).** The Response-Field row controls
follow the same lock-gated framework. Target behaviour:

- **Locked card:** **all four inactive** (the whole card is read-only).
- **Unlocked card:**
  - **R** (required) and **≡** (help-text visibility): **inactive for a blank
    row** awaiting input; active once the row has a field name. *(Today they
    are always active — `newModelRfRecomputeActionStates` doesn't touch them
    — so this is a new gate.)*
  - **✓** (push-to-preview): **inactive** when the row is **empty** (no name /
    invalid shape) **or** when the field is **already reflected in the preview
    with no pending edits** (nothing to push); **active** otherwise (a new
    named row, or an existing field with unsynced edits). *(Today ✓ only
    gates on blank-name + invalid-shape; the "already in preview, unchanged"
    gate is new and rides the per-row dirty tracking Item 2 introduces.)*
  - **X** (delete): **keep current behaviour** — verified in code
    (`newModelRfRecomputeActionStates` + the row template): **disabled when
    the field has saved responses** (title "Cannot delete — this field has
    saved responses"; must clear responses first) and **disabled on a blank
    row** (title "Empty row — nothing to delete"); **active** otherwise
    (deletes the row and its paired pill).

**Reinforce response-field shape protection (make it look inactive).** When a
response field **has saved responses**, its **shape** is frozen — the field
**type** (`data_type`) and the **bounds** (`min` / `max` / `step` / **list
options**) — while its **name / Required / Help** stay editable (the confirmed
semantics; server-guarded by `ResponseFieldShapeChangeError`). Those shape
inputs already carry the `disabled` attribute, **but they don't *look*
inactive**: `base.html` styles disabled *buttons* (which is why the **X**
delete button reads correctly greyed) but has **no** disabled styling for
`<input>` / `<select>`, so an operator moves to click into the box and only
then discovers it's locked. **Fix:** give disabled shape inputs a clear
inactive treatment — greyed background/text + `cursor: not-allowed`, matching
the X button — so the freeze is obvious at a glance. Keep the "Clear responses
first" tooltip. (Small CSS addition in `base.html` for disabled
`input`/`select`, or a scoped class on the shape inputs; no logic change — the
functional lock + server guard already exist.)

**Dirty tracking.** One per-card dirty flag drives **Save**'s and **Cancel**'s
enabled/greyed state, and the **unsaved-changes guard** fired on **Lock** and
on navigating away. Every editable control flips the flag on change; a
successful Save clears it. (Lock is always clickable; Cancel/Save gate on the
flag.)

**Scaffold-first (consequential UI).** This changes the button set **and** the
persistence contract, so land it scaffold-first (`CLAUDE.md` → Working
approach): first the **button-bar shape** per lock state (inert / re-rendered,
agree it), then wire staged persistence behind it **one control-group at a
time** (Band 1 + Band 3 are already staged; migrate Band 2, Response Fields,
identity, and column widths into the stage), and retire the immediate-POST
endpoints **last** (remove, or keep server-side only if a non-card caller
still needs them).

**Scope / size.** Larger than Item 1 — the card's button bar + client
dirty-tracking / staging JS + consolidating the save route(s) + standing down
the per-control POST paths. Likely **several PRs** (scaffold → per-band wiring
→ endpoint cleanup). Tests: the button-state matrix (locked / unlocked-clean /
unlocked-dirty), staged round-trips per control group, the fixed lost-edit
case, and a "nothing persists before Save" assertion.

**Definition of done.**

- Locked card shows **only Unlock**. Unlocked card shows the trio **Save ·
  Lock · Cancel** (Save + Cancel greyed when clean; Lock always active, warns
  on unsaved edits).
- Editing any element — Assignment rule, Preview/Band 2 (pills, help, column
  widths), Visibility, Response Fields (incl. brand-new rows), instrument
  name / short_label / description — is **staged**; **nothing persists until
  Save**; **Cancel** discards to clean-unlocked.
- The un-`✓`'d-new-field lost-edit is gone.
- The card no longer fires the in-card immediate POSTs (`/band2-state`,
  `/identity`, `/column-widths`, in-card `/display-fields/order`); those
  endpoints are removed or retained only for any non-card caller.
- The per-row **✓** is push-to-preview only (updates the preview, persists
  nothing); **column-width drag is fully staged** (live preview, no server
  write until Save).
- The per-row **R / ≡ / ✓ / X** button states follow the matrix above (all
  inactive when locked; R/≡ inactive on a blank row; ✓ inactive when empty or
  already-in-preview-unchanged; X keeps its saved-responses / blank-row
  gates).
- On a field with saved responses, the frozen **shape inputs** (type +
  min/max/step/list) **look** inactive (greyed + `cursor: not-allowed`,
  matching the X button), not just carry a silent `disabled` attribute; name /
  Required / Help stay editable.
- Leaving an unlocked card with pending edits **warns/confirms** before
  discarding.
- **No unlocked-and-collapsed card:** collapsing an unlocked card Locks it
  (usual unsaved-changes confirm; decline re-expands); expanding never changes
  lock state.
- **Save runs the full current validation set** (listed in Decisions
  #4); a validation failure leaves the card unlocked with edits intact.
- `spec/instruments.md` + `spec/operator_ui_concept.md` (lock card /
  Save-Edit toggle) updated to the harmonized model; the audit
  (`guide/archive/instrument_card_ux_audit.md`) cited as origin.
- Full suite + `ruff` green.

**Decisions (resolved 2026-08-16).**

1. **Per-row ✓ → push-to-preview.** It registers the row's edit into the live
   preview, **no persistence** until Save. **Keep the ✓ tick glyph**
   (the earlier ⬆ idea is optional). The R / ≡ / ✓ / X **button-state matrix**
   is specified in the body above (locked → all inactive; unlocked → R/≡ gated
   on a non-blank row, ✓ gated on empty / already-in-preview-unchanged, X
   unchanged).
2. **Column-width drag → fully staged.** The preview updates live as you drag,
   but the server write happens **only** on Save — the immediate
   `/column-widths` POST is retired. Chosen for consistency with every other
   editable element.
3. **Unsaved-changes guard → confirm/warn.** On Unlock → navigate-away (or any
   attempt to leave with pending edits), **warn that there are unsaved edits**
   and require confirmation before discarding.
4. **Save runs the full current validation set — yes.**
   Because the consolidated **Save** becomes the single writer for the whole
   card, it must run the union of the validations the current per-endpoint
   writers run. The current set (to preserve):

   *Response fields (`_response_fields` / `_band2.set_band2_state`):*
   - **Field key** — *(audit 2026-08-17: not an operator-facing gate on this
     card)*. `set_band2_state` **auto-generates** a unique, well-formed field
     key from each field's name (`_band2_unique_field_key`), so the
     `FieldKeyError` required/format/uniqueness checks belong to the retired
     legacy table path, not the new-model card. `/save` reproduces the four
     exceptions `set_band2_state` actually raises (below); it does not need a
     `FieldKeyError` block.
   - **Label** — required (non-empty) when adding a field.
   - **Inline shape well-formed** (`InvalidResponseFieldShapeError`, Wave 3
     PR ii): `max ≥ min`; `step > 0`; List has ≥ 1 option; String
     `max_length > 0`.
   - **Shape-change lock when responses exist** (`ResponseFieldShapeChangeError`):
     can't change a field's `data_type` or numeric/list bounds once it has
     saved responses — clear responses first.
   - **Delete-with-responses confirm** (`ResponsesPresentError`): deleting a
     field that has saved responses needs an explicit cascade acknowledgement.
   - **Un-pin-with-responses acknowledgement** (`ResponseFieldDropAcknowledgementRequired`,
     18K PR 4): un-pinning a Band 2 response chip whose field has saved
     responses needs `acknowledged_drop=true`.

   *Assignment rule (Band 1, `set_band1_assignment_rules`):*
   - **Payload well-formed** (`Band1ParseError`): the parallel rule arrays for
     a link must align; chosen tags must be a subset of that link's allowed
     tag set.

   *Visibility (Band 3):* structural only — mode values must be valid; no
   extra operator-facing block.

   *Cross-cutting side effect (not a block, keep it):* a successful save
   **invalidates a `validated` session back to `draft`**
   (`lifecycle.invalidate_if_validated`), and the locked default rows
   (Name / Email) stay pinned at the top.

   The consolidated **Save** must surface each of these as a blocking
   error (or its existing confirm gate) rather than silently dropping the edit
   — and, per the new model, a failed validation keeps the card **unlocked
   with edits intact** so the operator can fix and retry.

---

### Item 2 — implementation (decisions + PR ladder)

> **Accuracy review vs current code (2026-08-16).** A pass over the live
> implementation corrected the *starting point* the earlier plan assumed:
> **the consolidated save largely already exists**, and **Save already stays
> unlocked** (the trio semantics the operator asked for are already the
> behaviour). What genuinely changes is narrower than "build a new endpoint" —
> see the corrected Save-writer decision below. Verified-accurate claims: the
> three persistence paths; band2 → `/band2-state`; the lost-edit bug; column
> widths → `/column-widths` + snapshot mirror; the inline `/identity` pencil;
> `/display-fields/order`; the shape-field visual gap; **no migration**; and
> the per-row button-state facts.

**Decisions (2026-08-16).**

- **Save writer → extend the existing consolidated route; don't build anew.**
  The current **Save** already POSTs the dfsave form to
  `POST …/instruments/{iid}/fields/save` (`instrument_bulk_save_fields`),
  which **already writes most of the card in one transaction / one commit**:
  Band 1 (Links 1+2), Link 3 / Unit of review, column widths (from the
  `column_widths_snapshot` mirror), sort spec, **identity**
  (`short_label` / `description`), **and Band 3 visibility policies** — via
  `set_band1_assignment_rules` / `set_unit_of_review` / `set_column_widths` /
  `set_sort_display_fields` / `update_short_label` +
  `update_instrument_description` / `visibility_policies.upsert_many`. The
  **only** area *not* in it is **Band 2 response-field state** (pills +
  type / bounds / required / help), which the new-model card persists
  separately via `POST …/band2-state` (`set_band2_state`). So "consolidate" =
  **fold `band2_state` into `fields/save`** (add `set_band2_state` to the same
  transaction + validation pass) and retire the immediate-POST siblings —
  **not** a brand-new endpoint, and **not** `bulk_save_fields` (that's the
  legacy table path, not rendered on the new-model card). Return
  JSON (`{ok, errors}`) *iff* we move off the current form-POST→303 redirect
  (see the enter-edit decision).
- **Save already stays unlocked — keep it.** The route deliberately preserves
  `?editing=<id>` on Save ("Save doesn't re-lock … Lock/Unlock owns the
  gating; Save owns persistence") and flashes `?saved=<id>`. So the
  **Save · Lock · Cancel** trio with progressive save is *already* how it
  works — the harmonization is about the *edit controls* feeding one save, not
  about the button semantics.
- **Enter-edit UX → client-side toggle (no reload). Confirmed 2026-08-16**
  (kept after the accuracy review, eyes open — see caveat). Every edit control
  is **always rendered in the DOM**; when the card is **locked** they are
  disabled and styled read-only. `newModelLockClick` becomes a client
  **state machine** (locked ↔ unlocked) that enables/disables the controls,
  swaps the button cluster, and drives the per-row button-state matrix — no
  round-trip to enter/leave edit. (The server `?editing=<id>` gating is
  retired; keep `?editing` only as an optional initial-unlock deep-link.) The
  form Save (POST → 303) becomes a **JSON `…/save`** (fetch; on `ok` clear
  dirty + stay unlocked, on `!ok` show the banner).
  **Caveat (accepted):** the current Save/Lock flow is **entirely reload-based
  and already works** — Save is a form POST → 303 that preserves `?editing`,
  Lock/Unlock is a `?editing` nav, and it already delivers the trio +
  progressive save. So "no reload" is knowingly the **largest** slice of Item 2:
  it rewrites a working flow (always-render controls + JSON save + client state
  machine). The smaller reload-only alternative (fold band2 into the form Save,
  retire the immediate POSTs, keep reloads) was **considered and declined** in
  favour of the smoother no-reload feel.
- **Inline ✎/✓ text editors retire — the boxes follow the card's lock
  state (decided 2026-08-16).** The three per-field inline editors
  (card-title `short_label`, Band 2 intro `description`, Band 2 preview
  per-field help text) drop their ✎ (open) / ✓ (commit) affordance and
  their immediate `/identity` + `/band2-state` POSTs. Instead:
  **unlocked** → the box is a plain editable field (as if ✎ were already
  clicked for all of them); editing marks the card **dirty**; **Save**
  commits them via the consolidated `…/save`. **Locked** → the box
  **disappears, showing just the rendered read-only text** (not a disabled
  input) — i.e. the box is a view/edit swap keyed on the card lock state,
  not an always-rendered-disabled control. Commit is **Save**, never Lock
  (Lock only closes the boxes to their read-only view, with the standard
  unsaved-changes confirm if the card is dirty). Lands as its own focused
  PR — all three boxes together — ahead of the remaining Band 2 state
  staging and identity work (PR 4 in the ladder below).
- **One card editable at a time.** A page-level "currently-unlocked instrument"
  state; unlocking card B while card A is unlocked-and-dirty first prompts to
  **Save / Cancel** card A.
- **Collapse ⇒ lock (no unlocked-but-collapsed card) — added 2026-08-17.**
  Expand / collapse (the card's `<details>`) and lock state are coupled in one
  direction: **collapsing an unlocked card triggers a Lock** (running the usual
  unsaved-changes confirm — decline re-expands the card and leaves it
  unlocked). **Expanding never changes the lock state.** Invariant: a card is
  never *unlocked **and** collapsed* — editing controls are only reachable on
  an expanded card. (Programmatic open-state changes — the on-reload open-state
  restore and Expand-/Collapse-all — must not fire the confirm; the bulk
  Collapse-all locks the open card as part of collapsing it.)
- **Validation errors → summary banner at the top of the (still-unlocked)
  card**, listing the blocking issues; edits stay intact.

**No migration.** All targets are existing columns / relationships
(`name` / `short_label` / `description`, `band1_touched_links` + `rule_set_id`
/ `session_rule_sets`, `band2_state`, `sort_display_fields`, `column_widths`,
`instrument_view_policies`, `response_fields` / `display_fields`). Staging is
client-side (no server "draft" state); the consolidated route reuses the
existing writers. **No Alembic migration.**

**Key risk / where effort concentrates.** The template currently renders
*different markup* for `is_editing` vs view (inputs vs text). "No reload"
means **always rendering the editable controls** and presenting them as
read-only when locked — a real template refactor. Scaffold-first de-risks it:
agree the always-rendered / toggle shape before wiring persistence.

**PR ladder.**

**Status (2026-08-17):** PRs 1–6 + 5c **shipped and merged**, plus several
dev-slot follow-up fixes not in the original ladder (Cancel keeps the card
unlocked + preserves per-card open state on its discard reload; the
instrument-name input no longer collapses the card on click/Space/Enter).
**PR 7 (cleanup) is up as #1921** — dead ✎/✓ handler sweep + spec / template-
comment alignment. Item 2's ladder is functionally complete; the segment
**stays open** for further Item N refinements.

Audited against code 2026-08-17 — the ladder below reflects what actually
shipped: PR 6 was essentially just **display-field reorder staging** (the rest
of its original scope shipped in PRs 3–4), plus the **collapse ⇒ lock**
behaviour; PR 7 is cleanup.

**Route-retirement outcome (PR 7, 2026-08-17).** The "check for non-card
callers before deleting server-side" gate below (Endpoint disposition) was
run: `/fields/save`, `/band2-state`, `/column-widths`,
`/display-fields/order`, and `/identity` have **~92 direct test call sites
across 7 integration files** (`fields/save` 26, `band2-state` 53, the rest a
handful each). They are **retired from the card** (the page drives only
`/save`) but **kept server-side** — the precondition for deletion (card is
the sole caller) is false, so deleting them would be a ~92-site test refactor
+ dropping the no-JS `<form>` fallback for no user-facing gain. This revises
the earlier "make `/save` the sole writer / drop the no-JS fallback" decision.
Full server-side deletion + test migration is logged as an **optional** Future
item below.

1. **Scaffold (inert).** The button cluster per state (Locked → **Unlock**;
   Unlocked → **Save · Lock · Cancel**, with Save + Cancel greyed until
   dirty) driven by a client lock-state machine, with all edit controls
   present-but-disabled when locked. Current persistence untouched (existing
   endpoints still fire). Agree the surface.
2. **Dirty-tracking + staging harness.** A per-card client store collecting
   every edit; wire the state machine to it — Save + Cancel greyed/active by
   the dirty flag, the one-card-at-a-time guard, and the unsaved-changes
   confirm on **Lock** + nav-away (`beforeunload`). Not yet the server writer.
3. **Consolidated Save route.** The new `…/save` endpoint (full payload →
   validate → atomic apply via existing writers → JSON). Wire the **Save**
   button to fetch-POST it; on `ok` clear the dirty flag and stay unlocked, on
   `!ok` render the summary banner and stay unlocked with edits intact.
4. **Retire the inline ✎/✓ text editors (all three boxes together).**
   Per the inline-editors decision above: card-title `short_label`, Band 2
   `description`, and Band 2 per-field help text drop their ✎/✓ affordance.
   Unlocked → plain editable field; locked → rendered read-only text (a
   view/edit swap keyed on lock state). `short_label` + `description` ride
   the dfsave form → `/save` (which already accepts them); help text stages
   into the band2 state the Save flow flushes. Retire the ✓-triggered
   `/identity` + `/band2-state` immediate saves from these boxes. Done as one
   focused, self-contained PR — smaller than folding into the Band 2 state
   migration, and matches how the three boxes read as a single change.
5. **Migrate Band 2 state → staging.** Pills / column widths stop
   immediate-POSTing and flow through the store + the consolidated save;
   Response Fields **R / ≡ / ✓ / X** apply the button-state matrix, **✓**
   becomes push-to-preview only, and the **lost-edit is fixed** (all named
   rows are captured). Fold the band2 help-text persistence (UI already done
   in PR 4) fully into `/save`. Retire `/band2-state`, `/column-widths` from
   the card.
6. **Display-field reorder staging + collapse ⇒ lock.** *(Audit 2026-08-17 —
   the rest of the original "identity + display order" scope already shipped:
   `short_label` / `description` route through `/save` since PR 4, the card
   makes no `/identity` calls since PR 4, and Band 1 + Band 3 route into `/save`
   since PR 3. The only staging left is display-field reorder.)*
   - **Display-field reorder → `/save`.** Dragging a *display* pill still fires
     an immediate `POST /display-fields/order` (`saveBand2DisplayFieldOrder`);
     stage the order into the payload (a hidden snapshot input, like
     `column_widths_snapshot`) and apply it in `/save`, retiring the in-card
     immediate POST. (Response-pill reorder already stages via `saveBand2State`
     since PR 5b.) This closes the last "nothing persists before Save" gap.
   - **Collapse ⇒ lock.** Wire the invariant above: collapsing an unlocked card
     Locks it (with the unsaved-changes confirm; decline re-expands), expanding
     never changes lock state, and no card is ever unlocked-and-collapsed.
7. **Cleanup + tests.** ✅ **Shipped as #1921 (2026-08-17).** Swept the dead
   ✎/✓ handlers (`cardTitleEdit` / `cardTitleSave` / `newModelIntroEdit` /
   `newModelIntroSave` / `newModelHelpCardEditClick` /
   `newModelHelpCardSaveClick`) confirmed unreferenced by the audit, and
   aligned `spec/instruments.md` + `spec/operator_ui_concept.md` + the stale
   in-template comment blocks to the harmonized model. **Endpoints kept
   server-side, not deleted** — the card-only-caller precondition is false
   (~92 test call sites; see the Route-retirement outcome note above), so
   `/band2-state`, `/column-widths`, `/identity`, `/display-fields/order`, and
   `/fields/save` (with its no-JS `<form>` fallback) all stay. Tests: the
   button-state matrix (locked / unlocked-clean / unlocked-dirty), staged
   round-trips per area, the fixed lost-edit, "nothing persists before Save
   and Lock", validation-failure keeps edits + shows the banner, the
   one-card-at-a-time guard, the nav-away confirm, and the collapse ⇒ lock
   invariant.

**Endpoint disposition** (retire *from the card*; check for non-card callers
before deleting server-side): `/band2-state`, `/identity`, `/column-widths`,
in-card `/display-fields/order`, and the old `/fields/save` are all replaced
*from the card* by the single `…/save`. **Outcome (2026-08-17):** the
non-card-caller check found ~92 direct test call sites, so the server-side
routes are **kept** (retired from the card only). The earlier "retire
`/fields/save` / `/save` is the sole writer / drop the no-JS fallback"
decision is **superseded** by this check; full server-side deletion + the
test migration it requires is an optional Future item.

---

## Item 3 — Instrument-card UX tweaks (open-ended)

A running home for **small, self-contained polish on the per-instrument
card** — layout, control ordering, affordance sizing — that doesn't warrant
its own item. Each tweak is a bullet with a one-line problem → fix and its
shipping PR; land them individually or batched as convenient.

**Shipped:**

- **Taller description edit box** (PR #1923). The preview-band instrument
  description edit box only used `min-height: 4em`, leaving dead space now
  that the inline ✎/✓ buttons are retired (Item 2). Grown to `6.5em` so the
  box reclaims that space; the locked read view is unchanged, so the card's
  resting height doesn't grow.
- **Link 2 operator-cycle reorder** (PR #1923). "Who is being reviewed"
  (Link 2) cycled `IS → IS NOT → IS THE SAME AS → IS DIFFERENT FROM`. Reordered
  to lead with the cross-side tag operators:
  `IS THE SAME AS → IS DIFFERENT FROM → IS → IS NOT`, so the Reviewer-tag
  relationship is the default for a fresh Link 2 rule (the common
  reviewee-matches-reviewer case; the last two keep the freeform value box).
  `newModelAddRule` now seeds a cloned cell's operand box from the cycle's
  default operator rather than a hardcoded `IS`, so a newly-added Link 2 row
  shows the tag dropdown.
- **Vertical-only textarea resize (app-wide).** Textareas could be dragged
  wider than their column via the browser's default two-axis resize grip,
  breaking the page grid. Started as an instrument-card fix, then generalized:
  a single global `body.ui-v2 textarea { resize: vertical }` rule in
  `base.html` (beside the shared textarea styling) locks *every* textarea in
  the app to up/down resizing only — the instrument cards (server-rendered +
  JS-generated help / preview boxes), the Session details description
  (18R Item 4), the reviewer long-text response surface, the setup-invite
  message fields, and the new / edit session description boxes. The earlier
  per-page rule and the inline `resize: vertical` on the Session details
  mock were removed in favour of the one base.html rule.

**Open** — log further card tweaks here as they come up.

---

## Item 4 — Consolidate session config onto Session Home (retire the Edit page)

**Status: in progress. Slices 1–2 ✅ + the display/edit *UX* finalized
2026-08-18.**

- **Slice 1 ✅** — Quick Setup relocated to Session Home's bottom-left; Extract
  Setup moved to the Extract data page (bottom-left) with a placeholder
  **Archive session** card (half-width) reserved to its right.
- **Slice 2 (display scaffold) ✅ + the whole display↔edit *presentation*
  iterated to sign-off ✅.** The **Session details** card now renders, as a
  finalized mock: the unified fields block (name / code / description / help
  contact / timezone + the schedule datetime fields, each a display value that
  swaps to an input in edit mode); resolved send datetimes shown inline beside
  each invite / reminder offset (Schedule timeline card retired); an **Owners**
  sub-card (Email / Name / Role / Added + edit-mode Action + Add-owner form) and
  a **User interface settings** sub-card side by side; a **Save / Cancel /
  Unlock·Lock** cluster with client-side dirty tracking; the whole-card
  display↔edit swap driven by `data-config-mode`; and a **Danger Zone** mock in
  Home's bottom-right. Textareas are vertical-resize-only app-wide.
  **The operator has signed off on this display/edit UX — it is frozen; no
  further visual iteration on the Session details card is expected.** What
  remains is **wiring** (below): the edit-mode controls are still inert mocks
  (Save / Cancel / Add / Remove / the UI-settings checkboxes do not yet
  persist).

**Slices 3–5b ✅ done 2026-08-18** — config-card Save persistence (Slice 3),
Owners Add/Remove wired (Slice 4), Edit page retired from the UI + Danger Zone
on Home (Slice 5), the old metadata card retired with Quick Setup moved up, and
the `/edit` routes + template deleted (Slice 5b — ~55 test sites migrated to
`/config` + Home; `/edit` now 301-redirects), and the **`sessions/new`
alignment** (create page mirrors Home's Quick-Setup-left / UI-settings-right
bottom row). Remaining: **Slice 6** (Archive card).

**The decision (Option 2, as scoped down).** Consolidate the session's
config **display + edit onto Session Home** and **retire the separate Edit
page** (`/operator/sessions/{id}/edit`). This is *not* the instrument-card
per-card lock harness — it's a plain **display ↔ edit** swap for one config
region (one Edit button flips the whole region; Save/Cancel commits, reusing
the existing Edit-page form + dirty Save/Cancel + schedule-bounds JS). No
collapsible cards (config sits low on the page; the operator scrolls only when
needed).

Considered and rejected: **Option 1** (distribute — keep Edit as a separate
config page, move Quick Setup off Home onto Edit, Home becomes a dashboard).
Option 1 is lower-effort and needs no new interaction model, but the operator
prefers the single-canonical-page end state (view + edit in one place, no hop).
Option 2 is the bigger rebuild but produces the preferred shape.

### Target layout (Session Home)

- **Top (unchanged):** chrome nav + setup-status row + **Workflow card**.
- **Middle — Session config card** (new): sub-cards for **Details**
  (name / code / description / help contact / timezone) and **Schedule**
  (the 3×2 anchors/offsets grid) and **Owners** and **UI settings**
  (relationships / observers toggles). Renders **display mode** (read-only
  values) by default; an **Edit** button flips the whole card to **edit mode**
  (the forms, reusing the current Edit page's `#edit-session-form` + dirty
  Save/Cancel + `_schedule_ordering_js`). Edit-mode state carried on a **URL
  param** (`?editing=1`, matching the app's existing `?editing=` convention —
  survives reload, no-JS friendly).
- **Bottom of Session Home — two half-width cards side by side:** **Quick Setup**
  (bottom-**left**; kept a *distinct* card with its own existing lock/greying
  model — it does **not** fold into the config card's display/edit swap) and
  **Danger Zone** (bottom-**right**; Delete data / Delete session, confirm-gated,
  arrives when the Edit page is retired).
- **Bottom of the Extract data page — two half-width cards side by side:**
  **Extract Setup** (bottom-**left**; relocated off Session Home — the
  porting/archival download list, `_extract_data_card.html`) and a planned
  **Archive session card** (bottom-**right**, half-width — ***for later***:
  reserve the slot now, build in a follow-up). Gives the Extract data page a
  coherent "wrap-up" row: **export + archive**.
- **Retire** `session_edit.html` + the `/edit` GET/POST routes; redirect
  `/edit` → Home; re-point any links (the "← Back to Session Home" link, the
  Session Details card's Edit button, the sys-admin Diagnostics "Details"
  action — see Auth below).

### Decisions (locked 2026-08-17)

1. **Quick Setup — distinct card**, not part of the config display/edit swap
   (its lock model + Home cookie differ). Sits bottom-left, half-width, beside
   Danger Zone.
2. **Auth — fix the sys-admin-edits-non-owned-session gap.** Today the Edit
   page uses the looser `require_sys_admin_or_session_operator` (a sys-admin can
   reach a non-owned session's Edit), while Home uses `require_session_operator`
   (a non-owner sys-admin can't even *view* Home). Retiring Edit onto Home must
   not silently either strip or widen that. **Best practice = least privilege +
   explicit, audited elevation:** a sys-admin (incl. super-admin) editing a
   session they don't own **adds themselves as an owner first** (the one-click,
   audited `session.owner_added` gesture from Segment 16B), then edits via the
   normal operator path. So: **retire the looser gate with the Edit page**; the
   consolidated config on Home stays `require_session_operator`-gated; the
   sys-admin **Diagnostics → "Details"** action becomes "self-add as owner →
   open session". No shadow editing; every config edit is by a recorded owner.
   *This authorization change is now logged as **18S Item 3** (tighten
   sys-admin cross-session writes to explicit ownership + self-add/clone
   bootstrap) — **land 18S Item 3 before the Edit-retirement slice** so it
   inherits a clean gate. Updates `spec/audience_and_identity_model.md` §4/§4b.*
3. **Edit-mode state — URL param** (`?editing=1`), not a pure client toggle.
4. **Extract Setup → Extract data page bottom-left** — relocate the card off
   Session Home to the Operations-strip Extract data page (loose coupling,
   mostly a template move). This is the **opening slice** (Slice 1), not a
   "whenever" orthogonal.
5. **Archive session card — planned, later.** A half-width card at the Extract
   data page bottom-**right**, beside the relocated Extract Setup (export +
   archive "wrap-up" row). Reserve the slot in Slice 1; build it as its own
   follow-up (Slice 6). Distinct from the Workflow card's existing Archive
   button and from Danger Zone's *delete* — this is the lifecycle **archive**
   surfaced next to the extract flow.

### Sequence (UI-first)

Per the operator: **iterate on the UI before wiring.** Scaffold-first per
`CLAUDE.md`. **Start with the low-risk relocations** (pure template moves, no
new mechanism), then the config-consolidation work.

1. **Relocations. ✅ done 2026-08-18.**
   - **Quick Setup → Session Home bottom-left.** Repositioned *within* Home —
     kept distinct; its lock/greying model + Home cookie stayed put.
   - **Extract Setup → Extract data page bottom-left.** Moved
     `_extract_data_card.html` off Home onto the Operations-strip Extract data
     page.
   - **Reserved the Extract data page bottom-right** for the planned Archive
     session card (Slice 6).
2. **Display scaffold + display↔edit presentation. ✅ done 2026-08-18 (UX
   frozen).** Built the Session details card below Workflow with all sub-cards,
   the whole-card `data-config-mode` display↔edit swap, the Save/Cancel/Lock
   cluster (client dirty-tracking), and the Danger Zone mock (bottom-right).
   Iterated to operator sign-off. **All edit-mode controls are still inert
   mocks** — the swap flips text↔input and shows the buttons, but nothing
   persists yet. Edit page stays live.
3. **Wire edit-mode persistence (Save). ← next / main business.** Make the mock
   real: on **Save**, POST the details + schedule + **UI-settings** fields and
   persist them, then re-render Home in display mode; **Cancel** discards edits
   and returns to display; keep the card's dirty-tracking + schedule-bounds
   validation. Gate: `require_session_operator` (owners only).
   - **Edit-mode state — resolved (2026-08-18): match the instruments card.**
     `?editing=1` is the **canonical server state** (the `session_detail` GET
     reads it → `data-config-mode`), the existing `data-config-mode` JS is the
     **instant-swap enhancement**, and the **Unlock / Lock / Cancel controls are
     anchors that keep real `?editing=` hrefs** so no-JS degrades to navigation.
     No pure-client toggle — every other edit surface in the app is
     server-recoverable (roster pages + instruments use `?…` params, Quick Setup
     a cookie), and this keeps the config card consistent with that universal
     assumption. See "Edit-mode persistence assumptions" below.
   - **Route** — reuse the Edit route's parse/validate/persist body (extract it
     to a shared helper `_apply_session_config_form(...)`); add a Home-side
     `POST /operator/sessions/{id}/config` that calls it and redirects to
     `…/{id}#session-config` (display mode). The existing `/edit` POST keeps
     calling the same helper (redirect to `/edit`) until Slice 5 retires it.
   - **UI-settings toggles ride in this form, not Slice 4.** `update_session`
     applies the whole `SessionCreate` payload (it diffs every field including
     `relationships_enabled` / `observers_enabled`), so the toggles must post
     **atomically with the details** — omitting them could flip a toggle off.
     The card uses the HTML5 `form="config-save-{id}"` association (same trick as
     the instruments `dfsave-` textareas) so the details/schedule inputs and the
     two UI-settings checkboxes submit as one form without physically nesting
     inside the Owners sub-card.
4. **Wire Owners Add / Remove. ✅ done 2026-08-18.** The inert Owners controls
   are live POST forms (reuse `session_owners`); Add is its own `<form>`,
   separate from the config form; each Remove is an inline form. Owner-route
   redirects now land on Home's config card in edit mode
   (`?editing=1#config-owners-card`), and errors surface via an inline banner
   on the Owners sub-card (`owners_error` param, mirroring the Edit page).
   *(UI-settings moved up into Slice 3, so this slice is Owners only.)*
   - **Known gap for Slice 5:** the Owners forms live inside the card's
     `data-edit-only` region, so they only show when the card is in edit mode —
     which is gated on the session being draft/validated. Owner management on an
     **activated** session therefore still relies on the (not-yet-retired) Edit
     page. Slice 5 must give owners an always-available affordance (owners are a
     permission concern, not lifecycle-gated content) before deleting Edit —
     e.g. an independent edit toggle on the Owners sub-card, or allowing the
     card into edit mode for owners-only on activated sessions.
5. **Retire the Edit page from the UI. ✅ done 2026-08-18.** No operator
   surface links to `/edit` any more; Session Home is the sole config surface.
   - Removed the last UI paths to `/edit`: the working-card **Edit button**
     (that card is now read-only session metadata); the validation **"fix"
     links** (`_session_edit_url` → `…?editing=1#session-config`); the **clone**
     landing redirect; the bare-**create** / **quick-setup** fallback redirect.
     All now open Home's Session details card in edit mode.
   - **Danger Zone wired on Home** (bottom-right) — real Delete Data / Delete
     session forms posting to the existing `/delete-data` + `/delete` routes,
     each gated by a `required` confirm checkbox (no-JS-safe); Delete session
     stays disabled + `_require_editable`-gated while Activated.
   - **Auth:** no gate change needed — the Edit routes already use
     `require_session_operator` (18S Item 3 narrowed them), and Diagnostics
     "Details" is already the self-add-as-owner **adopt** flow (18S Item 3).
     The looser `require_sys_admin_or_session_operator` stays for clone +
     owners-add self-add, as 18S Item 3 set it.
   - **Kept, deprecated:** the `/edit` GET/POST routes + `session_edit.html`
     survive **only** as the config/schedule/timezone/offsets persistence +
     render **test harness** (~55 call sites, ~18 files). Annotated as
     deprecated; no UI links to them. Mirrors the "dead-from-the-card,
     kept-for-tests" pattern used for the per-concern instrument routes.

5b. **Delete the `/edit` routes + template. ✅ done 2026-08-18.** Migrated all
   ~55 test call sites off `GET/POST /edit` onto `POST /config` + Home
   `?editing=1` (pure test refactor — they share `_apply_session_config_form`,
   so behaviour is identical), then deleted `session_edit_form` /
   `session_edit_submit` / `session_edit.html`. A thin `GET /edit` →
   `?editing=1#session-config` **301 redirect** (still `require_session_operator`-
   gated) preserves stale bookmarks. No user-facing change.
   - **De-dupe the working "Session Details" metadata card. ✅ done 2026-08-18.**
     The operator chose to **retire** the read-only card outright (rather than
     fold): it duplicated `#session-config`'s name / code / description / help
     contact / timezone, and its unique **Created by / Created / Modified**
     fields were dropped. **Quick Setup moved up** to the top of the bottom-left
     column to take its place; the now-dead `.session-meta-row` /
     `.session-detail-code` / `.session-detail-description` CSS was removed.
     (Route + template deletion above is the remaining 5b work.)
6. **Archive session card — promoted to its own Item 5** (see below). Wires the
   placeholder card reserved on the Extract data page bottom-right (Slice 1).

### Follow-up — align `operator/sessions/new` with the finalized Home layout. ✅ done 2026-08-18

The **New session** page (`session_new.html`) now echoes Session Home's frozen
bottom row so create and view/edit feel like one surface:

- **Quick Setup (left) + User interface settings (right)** now sit side by side
  in **one** `.bottom-grid` (previously two stacked grids with UI-settings on
  top-left and Quick Setup below). This moved Quick Setup **up** next to the
  details form and UI settings **to the right**.
- The UI-settings card was re-styled onto Home's **`.ui-settings-row` /
  `.ui-setting`** primitives (inline checkbox-after-label, normal font),
  replacing the page's one-off flex layout.

Pure presentation on the create page; no route/persistence change (the two
toggles still submit via `form="create-session-form"`).

### Edit-mode persistence assumptions (survey, 2026-08-18)

How every existing edit surface holds its "am I in edit mode" state — the basis
for the Slice 3 resolution above. **No surface uses a pure ephemeral client-only
toggle; every one is server-recoverable and survives reload.**

- **Roster setup pages** (Reviewers / Reviewees / Observers / Relationships) —
  pure server state from URL query params:
  `edit_mode = (edit_id is not none) or add_mode`, with `?edit_id=<row>` /
  `?add=1` arriving as GET params. Edit/Add is a real navigation; Save is a
  POST→redirect (PRG) back to the param-less list. Stale-id safety drops edit
  mode if the id no longer matches a row. No client toggle; fully no-JS.
- **Instruments page** *(closest analog — in-place display↔edit on one card
  with a Lock/Unlock affordance)* — **hybrid**: `?editing=<id>` URL param is
  canonical (`is_editing = editing_instrument_id == instrument.id`), plus a
  client JS layer for instant swap (`data-instrument-locked` toggled by
  `data-instrument-unlock-toggle`; CSS `[data-unlock-only]` / `[data-lock-only]`).
  The Lock/Unlock controls are **anchors that keep real `?editing=` hrefs** —
  JS toggles instantly, no-JS navigates. Save/Lock strips `?editing`.
- **Quick Setup card** — lock held in a per-session `HttpOnly` cookie
  (`qsu_{id}`), flipped by `POST /quick-setup/lock`, redirect-based; visual only
  (greying + disabling inputs). Survives reload + cross-page nav (cookie path
  `/`), per-operator.
- **Edit page itself** — no edit-mode concept; the whole page is the form.
  Dirty-tracking JS only manages Save/Cancel enabled state; Cancel resets fields
  client-side; Save is POST→redirect.
- **Cross-cutting** — write-protection is a **separate server-side lifecycle
  gate** (`_require_editable`: session must be draft/validated), enforced at POST
  time regardless of how the UI entered edit mode. There is **no per-user edit
  lock / concurrency token** anywhere.

**Implication (locked):** the Session details card matches the instruments card
— canonical `?editing=1`, JS enhancement, anchor hrefs for no-JS — rather than
becoming the app's first pure-client edit toggle.

### Cost / risk notes

Bigger rebuild than Option 1, but "more build," not "new hard mechanism" — the
display/edit swap is a whole-region toggle, not the instrument lock harness.
Real work: building read-only display renderings for every config aspect (Owners
table, UI settings, schedule) that today only exist as forms; relocating Quick
Setup's Home coupling stays put (it's already on Home); the auth-gate change
(Decision 2) is the one item with cross-cutting security reach.

---

## Item 5 — Archive session card (Extract data page)

Wire the placeholder **Archive session** card reserved on the Extract data page
bottom-right (Slice 1 of Item 4), next to the relocated Extract Setup card, so
the operator can archive a finished session right after extracting its data.
(Promoted from "Item 4 Slice 6" to its own item 2026-08-18.)

### Audit — the current archiving function (2026-08-18)

Archiving already exists with **two distinct entry points** plus an archived
index; the service is reversible and destroys no data.

- **Service** (`app/services/session_lifecycle.py`):
  - `archive_session(...)` — flips **any non-archived** state → `archived`;
    reversible; deletes no data; emits `session.archived` with the from-state;
    raises `LifecycleError("already_archived")` if already archived.
  - `unarchive_session(...)` — `archived → draft` (**always back to draft**;
    the original lifecycle state is not restored); emits `session.unarchived`;
    raises `not_archived` otherwise.
  - `is_archived(...)` reader; `_require_not_archived` route guard blocks
    mutations on archived sessions.
- **Entry point 1 — sessions lobby "Purge and archive"** (per-row expander →
  `POST /operator/sessions/archive-selected`, `_lobby.py`): **draft-only**
  (server-side `is_draft` filter; non-draft rows silently skipped), with
  optional **purge** of `audit_log` / `responses` / `rosters` first (checkboxes,
  run in audit→responses→rosters order) via `session_purge`. Intent: abandon /
  clean up a draft you never ran. Redirects to the lobby.
- **Entry point 2 — Workflow card "Archive session"**
  (`POST /operator/sessions/{id}/workflow/archive`, `_workflow.py`): calls
  `archive_session` for **any non-archived** state, **no purge, no confirm**, but
  the button is only *surfaced* when `archive_visible = is_expired`
  (`_workflow_card.py`). Intent: wrap up a finished / expired session. Redirects
  to `/operator/sessions/archived`.
- **Archived index** (`GET /operator/sessions/archived` + bulk expander):
  lists archived sessions; bulk **Unarchive** (`unarchive-selected` → draft) and
  **Delete** (`delete-archived-selected`, gated by an "Allow delete" confirm →
  hard `delete_session`). Archived sessions are excluded from the main lobby and
  counted in the lobby's `archived` pill.

**Key finding — two gating rules for one service.** The lobby path is
*draft-only + optional purge*; the Workflow-card path is *any-state, surfaced
when expired, no purge*. The **Extract data page card's intent matches the
Workflow-card path** (archive a finished session whose data was just extracted —
keep the data, don't purge, stay reversible), so it should reuse
`POST /workflow/archive` rather than the draft-only lobby route.

### Plan — ✅ built 2026-08-18

- **Reused `POST /operator/sessions/{id}/workflow/archive`** — no new route. The
  Extract-data route already spreads `**workflow_ctx`, so `is_archived` /
  `archive_visible` were already in the template.
- **Wired the placeholder card** (`#extract-data-archive-session`): the inert
  `aria-disabled` button is now a real `btn destructive` submit (matching the
  Workflow card's archive button). Copy says archiving files the session out of
  the active lobby, **keeps every response + setup row**, and is **reversible**
  from the archived page.
- **Gating — resolved: mirror the Workflow card.** The button is active only when
  `archive_visible` (= `is_expired`) **and** not `is_archived`; otherwise it's an
  inert `aria-disabled` affordance with an "available once the session has ended"
  title. One consistent archive-availability rule across the Workflow card and
  the Extract data page.
- **No confirm gate** (parity with the Workflow card; archiving is reversible).
  Shows an "Already archived" state when `is_archived`.
- Tests (`test_extract_data_scaffold.py`): active form when expired; inert +
  no-form when draft; "Already archived" when archived. (The archive route +
  redirect + audit are already pinned by `test_workflow_row3_buttons.py`.)

---

## Future items (add as they come up)

This segment is the landing place for further small operator-UX identity /
label refinements. Log new ones here as `Item N` with the same
problem / fix / scope / done-when shape, and keep each a self-contained slice.

- **(Optional) Full server-side retirement of the per-concern instrument
  routes.** `/band2-state`, `/column-widths`, `/identity`,
  `/display-fields/order`, and `/fields/save` are dead from the card
  (everything routes through `/save`) but kept server-side because ~92
  integration-test call sites still exercise them directly. Retiring them
  means migrating those tests to POST `/save` snapshots (or to call the
  service writers directly) and dropping the no-JS `<form>` fallback. Pure
  cleanup, no user-facing change — do it only if the route surface is worth
  shrinking. Scope: 7 test files (`test_instrument_builder_routes`,
  `test_route_persistence`, `test_display_field_routes`,
  `test_reviewer_summary_visibility`, `test_reviewee_results_body`,
  `test_instrument_view_policy_routes`, `test_instruments_sort_column`).

---

## Doc impact

- `spec/instruments.md`, `spec/assignments.md` — "Band 1" → "Instrument assignment rule"
  and the Link relabels (Who does the review / Who is being reviewed / Unit of
  review), per Item 1.
- `docs/quickstart.md` §4c — update the three Link labels to match Item 1.
- `spec/instruments.md`, `spec/operator_ui_concept.md` — the harmonized
  save / lock model + per-state button bar, per Item 2 (cites
  `guide/archive/instrument_card_ux_audit.md`).
- `docs/status.md` — note the rename (Item 1) and the save/lock
  rationalization (Item 2) when they ship.
- `docs/quickstart.md` — keep §4c wording + the screenshot slot consistent.
