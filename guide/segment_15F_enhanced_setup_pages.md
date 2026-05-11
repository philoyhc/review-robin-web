# Segment 15F — Enhanced Setup pages

**Status:** Stub. Carved out 2026-05-10 from the original
`guide/archive/segment_15_operator_polish_and_documentation.md` once it
became clear the per-row Manage-page enhancements are a
distinct scope from the documentation pass (now Segment 20).

15F lives alongside the other 15-family extensions —
15A (friendly labels), 15B (per-instrument assignments),
15C (operator RTD / RuleSet libraries), 15E (Next Action
revamp), 16 (Sys Admin page) — as a focused per-row UX
improvement for the three Setup pages that operators iterate
on most.

## Goal

Bring per-row affordances to the Reviewers / Reviewees /
Relationships Manage pages so operators don't have to drop
to CSV upload + replace to fix a single name, demote one
person to inactive, or rewrite one pair-context tag. Two
linked surfaces:

1. **Inline edit** — operator clicks a row, edits cells in
   place, saves the row. No bulk CSV round-trip needed for
   single-row changes.
2. **Inactivate / Reactivate** — per-row button toggling
   `status` between `active` and `inactive`. Schema already
   supports both states; the affordance is what's missing.

## Why one segment

The two items move together because they share:

- **The same three pages** (Reviewers / Reviewees /
  Relationships Manage pages, all under `/operator/sessions/{id}/…`).
- **The same row-state UX** — clicking a row's Inactivate
  button is a degenerate form of inline edit (one column
  changes). Building the inline-edit machinery first, then
  layering Inactivate as a one-click cell-change, keeps the
  surface coherent.
- **The same row-level conflict story** — when an operator
  edits a row that the rule engine is about to consume, the
  service layer needs to gate the write against lifecycle
  state. Solving the conflict story once for inline edit
  covers Inactivate too.

## Background

- **Inline-editable rows** — officially deferred from
  Segment 11 (originally 10E §2.5). The catalog entry
  flagged it needs a design pass before code; 15F is the
  design + implementation pass.
- **Operator Inactivate UI** — officially deferred from
  Segment 11 Tier 3 §2.4 on 2026-05-03. The Reviewer +
  Reviewee tables already filter on `status` defensively;
  the affordance to flip the column is missing. The
  relationships table picked up `status` in 15D PR 2 and
  has the same gap.

## Likely scope (sketchy)

> Detail settles during PR scoping.

### Pages touched

- `/operator/sessions/{id}/reviewers` — `Reviewer` rows
  with `name` / `email` / `tag_1..3` / `status`.
- `/operator/sessions/{id}/reviewees` — `Reviewee` rows
  with `name` / `email_or_identifier` / `profile_link` /
  `tag_1..3` / `status`.
- `/operator/sessions/{id}/relationships` — `Relationship`
  rows with `reviewer` / `reviewee` (FKs, not editable) /
  `tag_1..3` / `status`.

### Inline-edit UX

- Edit affordance: per-row pencil icon (or click-to-edit
  cells). Lock down the pattern during PR scoping — the
  per-instrument card on `/instruments` already has a
  state-machine Edit / Save / Cancel pair which is the
  obvious precedent.
- Validation: client-side immediate (matching the existing
  CSV importer's per-column rules); server-side
  authoritative.
- Save shape: per-row POST with the row id, replacing the
  current CSV-only flow. The CSV importer stays for
  bulk-replace.
- Cross-table integrity: editing a reviewer's email after
  the rule engine has materialised assignments is
  surfaced (assignments stay pointing at the row id, not
  the email; but the audit trail may want to flag the
  edit). Decide during PR scoping.

### Inactivate / Reactivate UX

- Per-row toggle button (or status-cell click). The Setup
  status row partial's pill treatment already distinguishes
  `active` / `inactive` — flipping the cell is the
  affordance.
- Inactive rows stay visible in the preview table; the
  status column makes it clear. The rule engine + downstream
  surfaces already filter on `status == "active"` per the
  defence-in-depth pattern from Segment 11A.
- Audit event: `reviewer.status_changed` /
  `reviewee.status_changed` /
  `relationship.status_changed`, with the canonical
  `changes` envelope per Segment 11K.

### Lifecycle gate

- All mutations land via the existing `_require_editable`
  helper. `validated` → `draft` invalidation via
  `lifecycle.invalidate_if_validated` (same pattern every
  other Setup-page mutation uses).
- Edits on `ready` sessions: rejected at the route layer.
  Operator must revert to draft first (matches the existing
  Setup-page pattern; the lock card explains why).

## Out of scope

- **Bulk per-row operations** (select N rows → inactivate).
  Single-row affordances first; bulk is a follow-on.
- **Per-row Delete on Reviewers / Reviewees / Relationships
  pages.** The Danger Zone bulk-delete shipped post-15D
  cleanup; per-row Delete is a separate ask if it surfaces
  in pilot feedback.
- **Inline edit on the Assignments preview table.**
  Assignments are derived post-15D — the operator-facing
  edit affordance is the Rule Builder + Relationships table.
- **Soft-delete vs hard-delete.** Inactivate is the
  operator's soft-delete affordance; hard-delete stays on
  the Danger Zone Delete-all flow.

## Working notes / open questions

- _(placeholder)_
- Per-row edit pattern: pencil icon → modal? Pencil icon →
  inline expand? Click-the-cell-to-edit? Pick during PR
  scoping; the per-instrument card pattern is the precedent.
- Should the per-row Inactivate button be visible inside the
  preview table, or via the same edit affordance as the
  other cells? Probably the same affordance — single edit
  pattern for the whole row.

## Related context

- **Segment 11** Tier 3 §2.4 — original Inactivate-UI
  filing.
- **Segment 10E** §2.5 — original inline-editable rows
  filing.
- **Segment 15A** (`guide/segment_15A_friendly_labels.md`)
  — friendly labels for tag headers. Sequenced before 15F
  is fine (the tag columns 15F edits inherit the friendly
  labels) but not strictly required.
- **Segment 15D** (`guide/archive/segment_15D_assignments_revamp.md`)
  PR 2 — the Relationships Setup page that 15F extends.
- **`spec/setup_pages.md`** — Setup Pages shared body
  shape; 15F adds inline-edit / Inactivate to the
  contract.
