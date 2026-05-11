# spec/ sweep — drift + consolidation proposal (2026-05-11)

**As of:** end of the 13E → 12C → 15D → 12A-3 → 12B sweep
(2026-05-10). Audit of all 22 spec files (9,713 LOC) against the
shipped codebase, looking for drift (stale facts) and
consolidation opportunities (overlap, retired content, dead
cross-refs).

Findings sorted by:
- **F1–F8** — drift fixes (factual mismatches with the codebase)
- **C1–C5** — consolidation / compression
- **S1–S5** — style-only touch-ups

---

## F1. `architecture.md` — Pair-level vs assignment-level context

**Lines:** ~202–247.

**Stale:** Describes the dropped `Assignment.context` JSON column
plus `pair_context_1/2/3` and `assignment_context_1/2/3` slot
families. 15D PR 6b dropped the column; `AssignmentContext1/2/3`
retired entirely; pair-context now lives on the first-class
`relationships` table read via `relationships.pair_context_lookup`.

**Fix:**
- Drop the `Assignment.context` section.
- Replace with a short "Pair-level context" section describing:
  - `relationships(reviewer_id, reviewee_id, tag_1, tag_2, tag_3, status)`
    as the home for pair-level context.
  - Rule engine reads via `pair_context.tag_N` grammar with an
    eager `pair_context_lookup` dict built once per
    `engine.evaluate` call (15D PR 4).
  - CSV columns are `PairContextTag1/2/3` (Relationships extract /
    importer).
- The lazy display-field seeding sub-section also needs an update —
  `pair_context_N` display fields now seed off the relationships
  set, not legacy assignment context.

## F2. `architecture.md` — "Practical implications today"

**Lines:** ~85–113.

**Stale:** Anchored to "end-of-Segment-10C" (2026-05-01); 10+ days
out of date. Cross-refs `guide/archive/unfinished_business.md`
#27 / #28 / #29 as live tracking, but that catalog retired 2026-05-10.

**Fix:** Drop the dated anchor; point at `docs/status.md`
"Capabilities today" as the ship-state source. Drop the
`unfinished_business.md` cross-refs — #27 / #28 / #29 are absorbed
into 15B or moot post-15D.

## F3. `operator_ui_concept.md` — Setup / Operations tab taxonomy

**Lines:** ~73–112 (per-page tables); ~144–159 (chrome / status row).

**Stale:** Setup row listed as 5 tabs (Reviewers / Reviewees /
Assignments / Instruments / Email Template); Operations row listed
as 4 tabs (Validate / Previews / Invitations / Responses); status
row mentions "five Setup-entity counts."

**Actual chrome** (per `app/web/templates/operator/partials/session_top_nav.html`):
- Setup row (5 tabs): Reviewers / Reviewees / **Relationships** /
  Instruments / Email Template.
- Operations row (5 tabs): Validate / **Assignments** /
  Previews / Invitations / Responses.

Assignments moved Setup → Operations in 15D PR 6a (it's a
materialised derivative now, not a Setup primitive).
Relationships took its place as the new Setup home for pair-level
context. Setup-entity count rises 5 → 6 (Relationships becomes a
counted entity).

**Fix:** Update both tables; rewrite the ASCII chrome diagram at
~149; update the status-row count.

## F4. `setup_pages.md` — Assignments + missing Relationships

**Lines:** ~148–201 (Assignments page); no Relationships section.

**Stale:** §148–171 describes a Setup-row Assignments page with
"Upload Manual Assignment" card + 15-column preview table including
`AssignmentContext1/2/3` (cols 12–14). Post-15D:
- Page lives in Operations row, not Setup row.
- Manual-upload card retired (15D PR 6a).
- Preview renamed "Current pairs" → "Assignment pairs"; the
  AssignmentContext columns dropped; the bulk Include-self-reviews
  toggle is the new affordance.
- No Relationships Setup section despite that being a new
  full-fledged Setup page since 15D PR 2.

**Fix:**
- Move the Assignments section to a new spec file
  (`spec/assignments_operations.md`) or merge into
  `operations_renew.md`, since the page is now Operations not Setup.
- Add a Relationships Setup section (mirrors Reviewers / Reviewees:
  stats card, single-line counts pill, preview table, upload card,
  Danger Zone).
- Update preview-table column lists.

## F5. `quick_setup_card_spec.md` — slot inventory

**Lines:** ~23–47 (Slots), 121–132 (Create-session variant).

**Stale:** Slots described as Reviewers / Reviewees / Assignments
/ Session settings, with Slot 3 (Assignments) live and Slot 4
(Session settings) inert pending Segment 12A PR 6.

**Actual** (post-15D + 12A-3):
- Slots are Reviewers / Reviewees / **Relationships** / **Settings**.
- Assignments slot retired in 15D PR 7a; Relationships slot
  introduced in 15D PR 7c.
- Settings slot graduated to `is_wired=True` in 12A-3 PR 4 with
  `POST /import-config`.
- All four slots are now live.

**Fix:** Rewrite the Slots section; drop the rule selector +
self-review checkbox copy (Assignments slot is gone); add the
Relationships slot shape (file upload, no rule selector); update
the Settings slot from inert-tooltip to wired.

## F6. `session_home.md` — Extract Data card

**Lines:** ~174–195.

**Stale:** Card described as scaffolded with five inert download
rows (Session settings / Reviewers / Reviewees / Assignments /
Responses) plus zip-bundle footer, all `aria-disabled="true"`,
pending Segment 12A wiring.

**Actual** (post-12A-1 + 12A-3 + #781 polish):
- Five **live** download tiles, in DOM order: Reviewers, Settings,
  Reviewees, Responses, Relationships.
- Reviewers / Reviewees / Relationships / Responses **grey out
  when their underlying count is 0** (#781 polish).
- Settings always live (configuration always has rows).
- Audit-events tile **never shipped** to Extract Data — relocates
  to Sys Admin in Segment 16.
- Zip-all footer is the only remaining inert button.

**Fix:** Rewrite the tile list, audit affordance, and "Out of
scope" para (12A is shipped, not pending).

## F7. `all_buttons.md` — missing Relationships, stale Assignments

**Lines:** ~191–207 (Section 8 Assignments Setup).

**Stale + gap:**
- No Section for Relationships Setup
  (`/operator/sessions/{id}/relationships`).
- Section 8 still lists Button #46 "Upload Manual Assignment"
  with the retired Setup-page Assignments layout.
- Section numbering needs a re-cut — the Operations Assignments
  page is missing entirely (a separate section between Validate
  and Previews, since the page moved).

**Fix:**
- Add a new Section 7.5 (or renumber) "Relationships Setup
  (`/operator/sessions/{id}/relationships`)".
- Rewrite Section 8 as "Assignments Operations
  (`/operator/sessions/{id}/assignments`)" with the post-15D
  button set (Rule-Based generate, bulk include-self-reviews
  toggle, preview table).
- Update the chrome top-nav button list in Section 1 to include
  Relationships and reflect the new row groupings.

## F8. `settings_inventory.md` — `Assignment.context` ghosts

**Lines:**
- ~218 references "`Assignment.context.pair_context_*` JSON as the
  home for" something.
- ~370 row for `source_type` mentions "Widening to
  `assignment_context` is gated on 15B Slice 7 (deferred)."

**Stale:** Both refer to entities that retired with 15D PR 6b.

**Fix:** Drop the `assignment_context` row and rephrase the
pair-context home-for-X line to name `relationships.tag_N`.

---

## C1. Retire `assumptions.md` UI section

**File:** `spec/assumptions.md` (192 LOC).

**Status:** UI section has a "Superseded (2026-05-03)" banner.
Migration to `visual_style_general.md` + `visual_style_rrw.md` +
`ui_elements.md` has been "pending" for 8 days. The Domain section
(15 LOC) is still load-bearing; the UI section (135 LOC) is
duplicative.

**Recommendation:**
- Move "Inline error / warning banners" (~30 LOC) into
  `ui_elements.md` (closest fit — banner is an element family).
- Drop the Button styles section + the Layout primitives table
  (both replicated in `ui_elements.md` and `visual_style_*`).
- Shrink `assumptions.md` to ~50 LOC: Domain section + a
  cross-reference index. Or absorb the surviving Domain content
  into `architecture.md` and retire the file entirely.

**Saving:** ~140 LOC removed from active specs.

## C2. Trim `ui_elements.md` Parts 2–3

**File:** `spec/ui_elements.md` (659 LOC).

**Status:** Part 2 (Drift catalogue) and Part 3 (Restyle bundle
PR split) framed the seven-PR migration; the migration shipped.
Both parts are historical.

**Recommendation:**
- Keep Part 1 (Element catalogue) — still the canonical reference.
- Move Part 2 + Part 3 to a small `guide/archive/` artefact and
  drop them from the active spec, OR fold the still-relevant
  audit notes from Part 2 into Part 1's per-element entries.
- Trim "Pilot decisions worth remembering" (lines ~627+) into a
  named subsection of Part 1.

**Saving:** ~250–300 LOC removed.

## C3. Decide `functional_spec.md`'s role — **decided: retire to archive (2026-05-11)**

**File:** `spec/functional_spec.md` (1,138 LOC — largest spec).

**Status:** Pre-implementation forward-looking spec with an honest
"⚠ destination not map" warning at the top. ~70% of its content
either re-describes shipped functionality (now better-described in
per-page specs) or carries open-policy questions (§24) that have
been answered by the shipped product. The "concrete divergences"
list in the warning is non-exhaustive and itself outdated (it cites
CSV export as a divergence; CSV export shipped 2026-05-10).

**Options:**
- **(a) Status quo** — leave it as a destination doc; refresh only
  the warning header.
- **(b) Trim to founding-requirements doc (~300 LOC)** — keep §1
  (Purpose), §2 (Functional goals), §3 (Non-goals), §20
  (Functional parity with Review Robin), §23 (Acceptance criteria),
  §25 (Summary). Drop §§4–19 (now better-covered in per-page
  specs + `docs/status.md`), §§21–22 (re-describes MVP + expanded
  release that have shipped), §24 (open-policy decisions —
  mostly settled).
- **(c) Move to `guide/archive/`** — let `docs/status.md` +
  per-page specs be canonical; keep this as historical context.

**Recommended: (b).** The original framing-intent material (§1–3,
§20, §23) is still useful as a "what is this thing for?" anchor;
the rest has aged out. ~800 LOC removed.

**Decision (2026-05-11):** option (c). The doc has been moved
to `guide/archive/functional_spec.md` with a retirement banner.
Per-page specs in `spec/` now cover every surface the original
doc anticipated; `docs/status.md` carries the URL-by-URL
ship-state. ~1,138 LOC removed from active `spec/`.

## C4. Drop dead cross-refs to `unfinished_business.md`

**Files:** `architecture.md`, `ui_elements.md`, `settings_inventory.md`,
and others.

**Status:** `guide/archive/unfinished_business.md` retired 2026-05-10
(all items shipped or absorbed into segment plans). The file still
exists at the path so links don't 404, but the framing "tracked
at `guide/archive/unfinished_business.md` #XX" is misleading — it
implies an active catalogue.

**Recommendation:** `grep -rn "unfinished_business" spec/` and
either:
- replace each occurrence with the relevant segment plan
  cross-ref (e.g. "tracked under Segment 15B" instead of
  "tracked at `unfinished_business.md` #28"), or
- drop the cross-ref entirely if the catalog entry was the only
  context.

About 8 occurrences across spec/.

## C5. Consolidate visual-style cross-refs in `spec/README.md`

**File:** `spec/README.md` (35 LOC).

**Status:** README table lists 22 files but doesn't signal the
hierarchy among visual-style docs. A new contributor opening
`spec/` doesn't know whether to look at `visual_style_general.md`,
`visual_style_rrw.md`, `ui_elements.md`, `assumptions.md`, or
`all_buttons.md` first.

**Recommendation:** Group the README table by concern (e.g.
"Conceptual map" / "Per-page contracts" / "Visual system" /
"Reference indexes") with a 1-line reading-order hint at the top
of each group.

---

## S1. Audit-event count: 51 → 62

**Status:** May 9 codebase had 51 registered event types; today
62 (post-15D / 12A-3 / 12B). Some specs cite the older number.

**Sweep:** `grep -nE "51 (event types|audit|distinct)" spec/` and
update to 62 where seen.

## S2. 11K verb tense

**Status:** `architecture.md` line ~258–261: "a future Pydantic
write-validation gate (Segment 11K PR 8) will catch drift." 11K
shipped 2026-05-07; gate is live.

**Fix:** Change "will catch" to "catches" (or similar past tense).

## S3. "Inert pending Segment 12A PR 6" → "wired in 12A-3 PR 4"

**Status:** `quick_setup_card_spec.md` (~25, ~45, ~130, ~135),
`session_home.md` (~256–259). Settings slot graduated.

**Fix:** Rewrite the inert-pending phrasing wherever it appears.

## S4. "Segment 15" mentions point at retired umbrella

**Status:** Various specs reference "Segment 15" as the
catch-all home for items now split across 15A / 15B / 15C / 15E
/ 15F / 17 / 20. The umbrella retired 2026-05-10.

**Sweep:** `grep -rn "Segment 15\b" spec/` — repoint each
mention at the specific successor segment.

## S5. `Assignment.context` lingering references

**Status:** Beyond F1 + F8, scan for any other references to the
dropped column.

**Sweep:** `grep -rn "Assignment\.context\|assignment_context\|AssignmentContext" spec/`.
Confirmed surfaces (already covered): `architecture.md`,
`enhanced_instruments.md`, `instruments.md`,
`operator_ui_concept.md`, `settings_inventory.md`, `setup_pages.md`.
`enhanced_instruments.md` is forward-looking (13C) and still drafts
against `Assignment.context` — needs a substantial rewrite to
target post-15D primitives (probably a new column on `assignments`
or a sibling table). Flag for the 13C plan revision per
`guide/todo_master.md` queue entry #2.

---

## Suggested execution order

Group into three landing tranches:

**Tranche 1 — F-fixes (drift, mostly mechanical):** F2, F3, F5,
F6, F8, then F1 + F4 + F7 (heavier rewrites). Each can ship as a
separate small PR. ~8 PRs.

**Tranche 2 — S-fixes (style touch-ups):** S1–S5. Single sweep
PR, ~50-line diff.

**Tranche 3 — C-consolidation (judgment calls; ask user first):**
- C3 is the biggest call — does `functional_spec.md` survive in
  any form?
- C1 (retire assumptions.md UI) is the next biggest reshape.
- C2, C4, C5 are smaller polish.

Recommend **completing Tranche 1 + 2 before touching any
C-consolidation** — fix what's wrong before reshaping what's
present.

## Headline numbers

- **22 spec files / 9,713 LOC** today.
- **Drift fixes (F1–F8):** affect ~600 LOC across 8 files; net
  delta near zero (rewrites, not deletions).
- **Consolidation savings if all C-recommendations land:**
  ~1,200 LOC removed (assumptions.md UI section, ui_elements.md
  Parts 2-3, functional_spec.md option (b) trim).
- **Post-sweep target:** ~8,500 LOC across 20 files (down from
  9,713 / 22) if C1 + C2 + C3(b) all land; 13% smaller, with the
  remaining content factually correct against the codebase.
