# Segment 18R — UX refinement

**Status:** Planning. A holding segment for **operator-UX refinement** on
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

## Item 1 — Instrument card identity (retire "Band 1" → "Assignment rule")

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

1. **Give the top band a card title** — **"Assignment rule"** (alternative
   considered: "Response assignment rule"; go with the shorter unless review
   prefers the longer). It should read as a peer of the Response Fields /
   Visibility / Preview cards: same heading treatment, sitting between the
   Instrument Name (above) and the Preview review instrument card (below).
2. **Strengthen every section's identity in the same pass** — make the card
   set on the instrument card self-describing and visually consistent
   (Instrument Name → Assignment rule → Preview review instrument →
   Visibility → Response Fields). Titles / headings only; no behaviour or
   layout-logic change.
3. **Rename the operator-facing "Band 1" wording** in `spec/instruments.md`
   and `spec/assignments.md` to "Assignment rule". The **internal** `band1`
   code identifiers (`_band1.py`, `set_band1_assignment_rules`,
   `new_model_band1_state`, CSS/data attributes, the `band1_touched_links`
   column) **stay** — renaming those is churn with no user benefit; this item
   is about the *operator-facing* name only.

**Scope / size.** A **small** template slice on `instruments_index.html`
(add the heading, tidy the section identities) + the two spec wording
updates. No route, service, model, or migration change. No test change
expected beyond any template-string assertion that greps for the old label
(check `tests/` for "Band 1" before pushing).

**Definition of done.**

- The instrument card's top band shows a clear **"Assignment rule"** title;
  the five sections read as consistently-identified cards.
- `spec/instruments.md` / `spec/assignments.md` say "Assignment rule" for the
  operator-facing name (internal `band1` identifiers unchanged, with a
  one-line note that the code name is retained).
- `docs/quickstart.md` §4c already says "Assignment rule" / "top band" — keep
  it consistent (its `08-band1-rule.png` screenshot slot can be recaptioned
  to `08-assignment-rule.png` when screenshots are produced).
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

The card has two states, with a fixed button set governed entirely by
edit-state and dirtiness. (This item governs **only** the edit / save / lock
cluster. The card / session action buttons — **Replicate, Delete,
+Instrument, +Page break** — are explicitly **out of scope** and unaffected.)

| Card state | Editable? | Buttons in the edit/save/lock cluster |
|---|---|---|
| **Locked** (default) | No | **Unlock** — nothing else |
| **Unlocked, no pending edits** | Yes | **Lock** · **Cancel** *(greyed)* |
| **Unlocked, pending edits** | Yes | **Save and Lock** · **Cancel** *(active)* |

- The primary slot switches by dirty state: **"Save and Lock"** when there
  are unsaved edits, **"Lock"** when there are none. There is **no**
  standalone "Save without locking" and **no** editing while locked —
  committing and re-locking are the same gesture.
- **Cancel** discards all pending edits and returns to **Locked**; greyed out
  when nothing has been edited.

**Unified persistence.** Every editable / changeable element **stages** its
change client-side (into one per-card pending-edit set / dirty tracker) and is
persisted **only** by **Save and Lock**. This retires the in-card immediate
POSTs: the current path-B controls fold into a single Save writer
(`…/fields/save` or a consolidated commit route). The live **preview** still
updates as you edit (client render), but **nothing hits the server until Save
and Lock**.

**This fixes the lost-edit bug for free** — with all editable elements in the
framework, a newly-typed Response Field is captured by Save and Lock whether
or not the per-row control was clicked. The per-row **✓** is **re-glyphed as
an upward-pointing arrow (⬆, pointing at the preview)** and becomes a
**push-to-preview** affordance: clicking it registers the row's edit into the
live preview but **does not persist** — persistence happens only on Save and
Lock. (So its job is purely "reflect my edit in the preview now"; the arrow
pointing up at the preview says exactly that.)

**Dirty tracking.** One per-card dirty flag drives the primary button's label
(Save-and-Lock vs Lock), Cancel's enabled/greyed state, and an
unsaved-changes guard on navigating away. Every editable control flips the
flag on change.

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
case, and a "nothing persists before Save and Lock" assertion.

**Definition of done.**

- Locked card shows **only Unlock**. Unlocked card shows **Save and Lock** /
  **Lock** (by dirty state) + **Cancel** (greyed when clean).
- Editing any element — Assignment rule, Preview/Band 2 (pills, help, column
  widths), Visibility, Response Fields (incl. brand-new rows), instrument
  name / short_label / description — is **staged**; **nothing persists until
  Save and Lock**; **Cancel** discards cleanly.
- The un-`✓`'d-new-field lost-edit is gone.
- The card no longer fires the in-card immediate POSTs (`/band2-state`,
  `/identity`, `/column-widths`, in-card `/display-fields/order`); those
  endpoints are removed or retained only for any non-card caller.
- The per-row control is an **⬆ push-to-preview** arrow (updates the preview,
  persists nothing); **column-width drag is fully staged** (live preview, no
  server write until Save and Lock).
- Leaving an unlocked card with pending edits **warns/confirms** before
  discarding.
- **Save and Lock runs the full current validation set** (listed in Decisions
  #4); a validation failure leaves the card unlocked with edits intact.
- `spec/instruments.md` + `spec/operator_ui_concept.md` (lock card /
  Save-Edit toggle) updated to the harmonized model; the audit
  (`guide/instrument_card_ux_audit.md`) cited as origin.
- Full suite + `ruff` green.

**Decisions (resolved 2026-08-16).**

1. **Per-row ✓ → an upward-pointing arrow (⬆).** It becomes a
   **push-to-preview** control: register the row's edit into the live preview,
   **no persistence** until Save and Lock. (Covered in the body above.)
2. **Column-width drag → fully staged.** The preview updates live as you drag,
   but the server write happens **only** on Save and Lock — the immediate
   `/column-widths` POST is retired. Chosen for consistency with every other
   editable element.
3. **Unsaved-changes guard → confirm/warn.** On Unlock → navigate-away (or any
   attempt to leave with pending edits), **warn that there are unsaved edits**
   and require confirmation before discarding.
4. **Save and Lock runs the same validation the current Save does — yes.**
   Because Save and Lock becomes the single writer for the whole card, it must
   run the union of the validations the current per-endpoint writers run. The
   current set (to preserve):

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

   The consolidated **Save and Lock** must surface each of these as a blocking
   error (or its existing confirm gate) rather than silently dropping the edit
   — and, per the new model, a failed validation keeps the card **unlocked
   with edits intact** so the operator can fix and retry.

---

## Future items (add as they come up)

This segment is the landing place for further small operator-UX identity /
label refinements. Log new ones here as `Item N` with the same
problem / fix / scope / done-when shape, and keep each a self-contained slice.

---

## Doc impact

- `spec/instruments.md`, `spec/assignments.md` — "Band 1" → "Assignment rule"
  (operator-facing name), per Item 1.
- `spec/instruments.md`, `spec/operator_ui_concept.md` — the harmonized
  save / lock model + per-state button bar, per Item 2 (cites
  `guide/instrument_card_ux_audit.md`).
- `docs/status.md` — note the rename (Item 1) and the save/lock
  rationalization (Item 2) when they ship.
- `docs/quickstart.md` — keep §4c wording + the screenshot slot consistent.
