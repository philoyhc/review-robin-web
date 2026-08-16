# Segment 18R — UX refinement

**Status:** In progress — **Item 1 shipped 2026-08-16 (PR #1899)**; **Item 2
planned**. A holding segment for **operator-UX refinement** on
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

**The problem.** The per-instrument card mixes **three** persistence paths
(full audit: `guide/instrument_card_ux_audit.md`):

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
- **Save runs the full current validation set** (listed in Decisions
  #4); a validation failure leaves the card unlocked with edits intact.
- `spec/instruments.md` + `spec/operator_ui_concept.md` (lock card /
  Save-Edit toggle) updated to the harmonized model; the audit
  (`guide/instrument_card_ux_audit.md`) cited as origin.
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
   - **Field key** — required; ≤ 64 chars; matches `^[a-z][a-z0-9_]*$`;
     **unique within the instrument** (`FieldKeyError` / `_band2_unique_field_key`).
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
  unsaved-changes confirm if the card is dirty). Lands in PR 4 (help text)
  and PR 5 (description + short_label).
- **One card editable at a time.** A page-level "currently-unlocked instrument"
  state; unlocking card B while card A is unlocked-and-dirty first prompts to
  **Save / Cancel** card A.
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
4. **Migrate Band 2 → staging.** Pills / help text / column widths stop
   immediate-POSTing and flow through the store + the consolidated save;
   Response Fields **R / ≡ / ✓ / X** apply the button-state matrix, **✓**
   becomes push-to-preview only, and the **lost-edit is fixed** (all named
   rows are captured). The per-field **help-text ✎/✓ retires** — the help
   box is a plain field when unlocked, rendered read-only text when locked
   (per the inline-editors decision above), committed on Save. Retire
   `/band2-state`, `/column-widths` from the card.
5. **Migrate identity + display order → staging.** Name / short_label /
   description stop immediate-POSTing (retire `/identity` from the card);
   the **short_label + description ✎/✓ retire** — plain fields when
   unlocked, rendered read-only text when locked, committed on Save.
   Display-field reorder folds into the payload (retire in-card
   `/display-fields/order`). Band 1 + Band 3 (already staged) route into the
   consolidated save instead of `/fields/save`.
6. **Cleanup + tests.** Retire now-unused endpoints (or keep server-side only
   where a verified non-card caller needs them); final button-state-matrix
   pass; update `spec/instruments.md` + `spec/operator_ui_concept.md`. Tests:
   the button-state matrix (locked / unlocked-clean / unlocked-dirty), staged
   round-trips per area, the fixed lost-edit, "nothing persists before Save
   and Lock", validation-failure keeps edits + shows the banner, the
   one-card-at-a-time guard, and the nav-away confirm.

**Endpoint disposition** (retire *from the card*; check for non-card callers
before deleting server-side): `/band2-state`, `/identity`, `/column-widths`,
in-card `/display-fields/order`, and the old `/fields/save` are all replaced
by the single `…/save`.

---

## Future items (add as they come up)

This segment is the landing place for further small operator-UX identity /
label refinements. Log new ones here as `Item N` with the same
problem / fix / scope / done-when shape, and keep each a self-contained slice.

---

## Doc impact

- `spec/instruments.md`, `spec/assignments.md` — "Band 1" → "Instrument assignment rule"
  and the Link relabels (Who does the review / Who is being reviewed / Unit of
  review), per Item 1.
- `docs/quickstart.md` §4c — update the three Link labels to match Item 1.
- `spec/instruments.md`, `spec/operator_ui_concept.md` — the harmonized
  save / lock model + per-state button bar, per Item 2 (cites
  `guide/instrument_card_ux_audit.md`).
- `docs/status.md` — note the rename (Item 1) and the save/lock
  rationalization (Item 2) when they ship.
- `docs/quickstart.md` — keep §4c wording + the screenshot slot consistent.
