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

## Status snapshot (2026-05-11 late evening) — ✅ all merged

Every F / C / S item from the sweep has landed on `main`. The
proposal is closed.

| Item | PR | Notes |
|---|---|---|
| F1 — architecture pair-level context | #803 | merged |
| F2 — architecture "Practical implications today" | #798 | merged |
| F3 — operator_ui_concept tab taxonomy | #799 | merged (rebased + codex finding folded in: `pair_context.tag_N` → `pair_context.tag1/2/3` per the actual `FIELD_MAP`) |
| F4 — setup_pages Relationships section | #804 | merged |
| F5 — quick_setup_card slot inventory | #800 | merged |
| F6 — session_home Extract Data card | #801 | merged |
| F7 — operator_button_audit chrome refresh | #805 | merged |
| F8 — settings_inventory Assignment.context ghosts | #802 | merged |
| C1 — domain_assumptions UI section retire | #811 → #814 | merged (consolidated into the C2 PR #814 after the stack #810/#811 was redone) |
| C2 — ui_elements Parts 2-3 archive | #810 → #814 | merged (consolidated into #814) |
| C3 — functional_spec retire to archive | #797 | merged |
| C4 — unfinished_business cross-refs | #809 | merged (second redo after main moved; final scope shrank from 5 files to 3 since #814 covered domain_assumptions.md + ui_elements.md) |
| C5 — spec/README regroup | #808 | merged |
| S1–S5 — Tranche 2 style touch-ups | #807 | merged |
| (bonus) Tier 1/2/3 coverage-gap section | #806 | merged |
| (bonus) Four-file rename | #812 | merged (assumptions → domain_assumptions, enhanced_instruments → group_scoped_instruments, operations_renew → operations_pages, all_buttons → operator_button_audit) |
| (bonus) Sweep-doc status refresh | #813 | merged |
| (bonus) Tail cleanup (this PR) | — | three drift pockets (`pair_context.tag_N` literal in 3 specs, `domain_assumptions.md` mis-described as "UI vocabulary" in 4 cross-refs) |

The C1/C2/C4 stack had to be redone after PRs above merged out
of order during the day. Final landing order from `git log`:
F7 (early) → C3 → S1-S5 → renames → Tier list → F4/F1/F8/F6/F5/F2 →
F3 → C5 → C2+C1 (#814) → C4 → tail cleanup.

---

## F1. `architecture.md` — Pair-level vs assignment-level context

**Status:** ✅ Merged (PR #803).
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

**Status:** ✅ Merged (PR #798).
**Lines:** ~85–113.

**Stale:** Anchored to "end-of-Segment-10C" (2026-05-01); 10+ days
out of date. Cross-refs `guide/archive/unfinished_business.md`
#27 / #28 / #29 as live tracking, but that catalog retired 2026-05-10.

**Fix:** Drop the dated anchor; point at `docs/status.md`
"Capabilities today" as the ship-state source. Drop the
`unfinished_business.md` cross-refs — #27 / #28 / #29 are absorbed
into 15B or moot post-15D.

## F3. `operator_ui_concept.md` — Setup / Operations tab taxonomy

**Status:** ✅ Merged (PR #799 — rebased with codex finding fold-in: `pair_context.tag_N` → `pair_context.tag1/2/3`).
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

**Status:** ✅ Merged (PR #804).
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
  `operations_pages.md`, since the page is now Operations not Setup.
- Add a Relationships Setup section (mirrors Reviewers / Reviewees:
  stats card, single-line counts pill, preview table, upload card,
  Danger Zone).
- Update preview-table column lists.

## F5. `quick_setup_card_spec.md` — slot inventory

**Status:** ✅ Merged (PR #800).
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

**Status:** ✅ Merged (PR #801).
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

## F7. `operator_button_audit.md` — missing Relationships, stale Assignments

**Status:** ✅ **Merged 2026-05-11 (PR #805).**
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

**Status:** ✅ Merged (PR #802).
**Lines:**
- ~218 references "`Assignment.context.pair_context_*` JSON as the
  home for" something.
- ~370 row for `source_type` mentions "Widening to
  `assignment_context` is gated on 15B Slice 7 (deferred)."

**Stale:** Both refer to entities that retired with 15D PR 6b.

**Fix:** Drop the `assignment_context` row and rephrase the
pair-context home-for-X line to name `relationships.tag_N`.

---

## C1. Retire `domain_assumptions.md` UI section

**Status:** ✅ Merged via PR #814 (the consolidated C2+C1 redo that replaced the original #810/#811 stack).
**File:** `spec/domain_assumptions.md` (192 LOC pre-PR; 65 LOC after).

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
- Shrink `domain_assumptions.md` to ~50 LOC: Domain section + a
  cross-reference index. Or absorb the surviving Domain content
  into `architecture.md` and retire the file entirely.

**Saving:** ~140 LOC removed from active specs.

## C2. Trim `ui_elements.md` Parts 2–3

**Status:** ✅ Merged via PR #814 (the consolidated C2+C1 redo).
**File:** `spec/ui_elements.md` (662 LOC pre-PR; 578 LOC after).

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

**Status:** ✅ Merged (PR #809, second redo — final scope: settings_inventory.md, instruments.md, sort_by_reviewee.md).
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

**Status:** ✅ Merged (PR #808, fresh rewrite of `spec/README.md`).
**File:** `spec/README.md` (35 LOC).

**Status:** README table lists 22 files but doesn't signal the
hierarchy among visual-style docs. A new contributor opening
`spec/` doesn't know whether to look at `visual_style_general.md`,
`visual_style_rrw.md`, `ui_elements.md`, `domain_assumptions.md`, or
`operator_button_audit.md` first.

**Recommendation:** Group the README table by concern (e.g.
"Conceptual map" / "Per-page contracts" / "Visual system" /
"Reference indexes") with a 1-line reading-order hint at the top
of each group.

---

> **S1–S5 status: ✅ Merged 2026-05-11 (PR #807, Tranche 2 single-sweep PR).**
> S1 and S3 were both skipped at landing time — S1 because the
> `51 → 62` drift only ever appeared in the dated
> `guide/codebase_assessment_09may.md` snapshot (correctly
> preserved as-is); S3 because the "inert pending Segment 12A
> PR 6" copy is overwritten by F5 (PR #800) and F6 (PR #801)
> which both rewrite the surrounding sections.

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
`group_scoped_instruments.md`, `instruments.md`,
`operator_ui_concept.md`, `settings_inventory.md`, `setup_pages.md`.
`group_scoped_instruments.md` is forward-looking (13C) and still drafts
against `Assignment.context` — needs a substantial rewrite to
target post-15D primitives (probably a new column on `assignments`
or a sibling table). Flag for the 13C plan revision per
`guide/todo_master.md` queue entry #2.

---

## Suggested execution order — ✅ all three tranches complete

**Tranche 1 — F-fixes (drift):** F1, F2, F3, F4, F5, F6, F7, F8.
✅ All 8 merged.

**Tranche 2 — S-fixes (style touch-ups):** S1–S5 shipped as a
single sweep PR. ✅ Merged (PR #807). S1 + S3 skipped at landing
time per the banner above each section.

**Tranche 3 — C-consolidation:** C1, C2, C3, C4, C5. ✅ All
merged. C3 shipped as a `functional_spec.md` retire-to-archive
(PR #797); C1+C2 consolidated into a single redo PR #814 after
the original #810/#811 stack got tangled when intermediate PRs
landed out of order; C4 was redone twice as the file moved
under it.

**Outside the F/C/S framing:** PR #806 added the Tier 1/2/3
coverage-gap section to this doc; PR #812 renamed four spec
files to more informative names (assumptions →
domain_assumptions, enhanced_instruments →
group_scoped_instruments, operations_renew → operations_pages,
all_buttons → operator_button_audit); PR #813 added an in-flight
status refresh to this doc.

**This PR (tail cleanup)** mops up three small drift pockets
that emerged during the sweep's own landings:

1. **`pair_context.tag_N`** (the abstract pattern) lingered in
   3 specs after F3's codex fix only touched
   `operator_ui_concept.md`. Replaced with
   `pair_context.tag1` / `pair_context.tag2` /
   `pair_context.tag3` (the literal field names the rule
   engine's `FIELD_MAP` accepts) in `architecture.md`,
   `setup_pages.md`, `quick_setup_card_spec.md`.
2. **`domain_assumptions.md` mis-described as "UI vocabulary"**
   in 4 cross-refs in `visual_style_rrw.md`, `instruments.md`
   (×2), `spec/README.md`. Post-C1 the file is Domain-only;
   button-modifier mechanics live in `ui_elements.md` §6.
3. **Sweep-doc status refresh** — every F/C/S item now marked
   merged; the status-snapshot table replaces the stale
   "Open / draft" table.

## Headline numbers

- **22 spec files / 9,713 LOC** today.
- **Drift fixes (F1–F8):** affect ~600 LOC across 8 files; net
  delta near zero (rewrites, not deletions).
- **Consolidation savings if all C-recommendations land:**
  ~1,200 LOC removed (domain_assumptions.md UI section, ui_elements.md
  Parts 2-3, functional_spec.md option (b) trim).
- **Post-sweep target:** ~8,500 LOC across 20 files (down from
  9,713 / 22) if C1 + C2 + C3(b) all land; 13% smaller, with the
  remaining content factually correct against the codebase.

---

## Spec coverage gaps — new specs to consider writing

The sweep above corrects drift and proposes consolidation. A
parallel exercise — mapping every shipped surface against
`spec/` — surfaced shipped subsystems with **no dedicated spec
file** (today the contract for them is implicit in the code
and scattered across other specs). Captured here so they
don't get lost; sequencing is up to the user.

**Reviewed 2026-05-11 evening.** The Tier 1 / 2 / 3 list below
is unchanged in scope since it landed in PR #806 — none of the
12 items have specs written for them yet, and no new
subsystems landed in the meantime. Cross-refs throughout this
section name the post-rename file paths (operator_button_audit,
operations_pages, etc.).

### Tier 1 — sizeable shipped subsystems with no dedicated spec

1. **Validate page (`session_validate.html`).** Segment 11G
   shipped a substantial subsystem — a `ValidationRule` registry
   with `key` / `severity` / `why` / `fix_url` /
   `fix_page_label`, the find-and-fix surface (setup-coverage
   grid + severity chip strip + per-issue "Fix on X ↗"
   deep-links + activate-warns detour banner), and the
   orchestrator. **No dedicated spec.** Bits scattered in
   `architecture.md` and `operator_button_audit.md` §11.
   **Suggested file:** `spec/validate_page.md`.

2. **Lifecycle state machine + invalidation hooks.**
   Cross-cutting load-bearing logic: the `draft → validated →
   ready → closed` state machine, `invalidate_if_validated()`,
   the `_require_editable` gate, the per-page lock card pattern.
   Currently scattered across `architecture.md` (one paragraph),
   `session_lifecycle.py` docstring, and every per-page spec's
   "lifecycle gating" sub-section. Worth a single doc.
   **Suggested file:** `spec/lifecycle.md`.

3. **CSV import + export contracts.** Per-entity column shapes,
   header normalization, encoding, validation rules, two-phase
   parse-then-apply, round-trip stability rules (the post-12A-3
   byte-stability guarantee). `docs/imports.md` covers importer
   implementation but isn't a contract; `settings_inventory.md`
   §10 has a coverage table but not column-level shapes.
   **Suggested file:** `spec/csv_contracts.md`.

4. **Email Template editor (`session_setupinvite.html`).**
   Three-tab editor (Invitation / Reminder / Responses-received),
   per-template merge-tag set, per-field "Reset to default",
   "Send when reviewer submits?" toggle, encrypted credential
   plumbing. Only partial coverage in `operator_ui_concept.md`
   §Email Template + `operator_button_audit.md` §10.
   **Suggested file:** `spec/email_template_editor.md`.

5. **Permissions / authorization.** `SessionOperator` table,
   `require_session_operator` dependency, operator-only vs
   reviewer-only route gates, 403 semantics. Auth posture is in
   `audience_and_identity_model.md`; authorization (who-can-do-
   what per route) is not anywhere.
   **Suggested file:** `spec/permissions.md`.

### Tier 2 — flagged elsewhere but partial / incomplete

6. **Relationships Setup page.** Already addressed in sweep F4
   (PR #804 adds a section in `setup_pages.md`).

7. **Operations Assignments page.** Already partially addressed
   in sweep F4 / F7 (cross-refs in `setup_pages.md` +
   `operator_button_audit.md` §11.5). Could still warrant its own spec or
   a dedicated section in `operations_pages.md` covering the
   post-15D Rule Based card + Self-reviews toggle + "Assignment
   pairs" preview.

8. **Operator Settings page (`/operator/settings`).** Encrypted
   SMTP credential storage flow, `?return_to=` plumbing. Partial
   coverage in `settings_inventory.md` SMTP rows + `operator_button_audit.md`
   §15. Worth a small standalone spec or a dedicated section in
   `email_infra_options.md`.

### Tier 3 — smaller surfaces, probably OK as-is

9. **Edit Session page (`session_edit.html`).** Field-level
   lifecycle restrictions. Sub-page of Home; small surface;
   could live as a sub-section in `session_home.md`.

10. **New session page (`session_new.html`).** Code generation,
    deadline validation, Quick Setup Create-Session variant. The
    Quick Setup part is in `quick_setup_card_spec.md`; the form
    itself isn't formally specced but is small.

11. **Drill-in pages** (`session_invitations_reviewer_detail.html`,
    `session_responses_reviewee_detail.html`). `operations_pages.md`
    calls them "scaffolds"; per-assignment / per-response detail
    is deferred. Probably fine until pilot feedback.

12. **Outbox.** Explicitly excluded from the operator-page
    taxonomy in `operator_ui_concept.md` §114 as a dev-diagnostic
    surface. No spec needed unless promoted (Segment 16 Sys Admin
    is the likely promotion path).

### Recommended sequencing

If three Tier-1 specs land, in priority order:

1. **`spec/lifecycle.md`** — ✅ **Shipped 2026-05-11.**
   Cross-cutting load-bearer; every per-page spec currently
   re-states bits of it. Single authoritative source pays off
   everywhere.
2. **`spec/csv_contracts.md`** — round-trip stability is now a
   real contract (post-12A-3) but lives only as test assertions.
   Documenting the contract surfaces the guarantee.
3. **`spec/validate_page.md`** — substantial unspecced
   subsystem; Segment 14 (production hardening) will need this
   anyway to document the readiness gate for pilot.

Permissions (#5) is a close fourth; Email Template editor (#4)
is the smallest Tier-1 spec and could ride along with any of
the others.
