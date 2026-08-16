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
or not a per-row `✓` was clicked. The per-row **✓** either becomes a pure
"apply to preview" affordance (no persistence meaning) or is retired in favour
of live-on-edit preview — *open design choice*.

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
- `spec/instruments.md` + `spec/operator_ui_concept.md` (lock card /
  Save-Edit toggle) updated to the harmonized model; the audit
  (`guide/instrument_card_ux_audit.md`) cited as origin.
- Full suite + `ruff` green.

**Open questions.**

- Fate of the per-row **✓** (preview-apply vs retire).
- Column-width drag is a live direct-manipulation gesture; keep it immediate
  for responsiveness *and* also capture on Save, or fully stage it (preview
  updates live, server write only on Save)? **Default: fully staged** for
  consistency.
- Unsaved-changes guard on Unlock → navigate-away: confirm vs auto-discard.
- Does **Save and Lock** run the same validation the current Save does?

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
