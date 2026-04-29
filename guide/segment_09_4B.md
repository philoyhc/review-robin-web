# Segment 9.4B Implementation Plan — Session detail four-card restructure + inline validate-summary + Delete Data

**Status:** Draft in progress — locked decisions recorded, slice plan not yet written. Second of three PR-sized blocks for Segment 9.4 (operator UI restructure to the target page map). Sits between 9.4A (shipped) and 9.4C (not yet drafted).

- **9.4A (shipped):** chrome, breadcrumbs, `/about`, sessions list reshape.
- **9.4B (this doc):** session detail four-card restructure + inline validate-summary card + `Delete Data`.
- **9.4C (next):** reviewers / reviewees / assignments Manage page reshapes, instruments index, `/setupinvite` + `/extract` stubs, closing-segment doc + spec refresh.

See `segment_09_4_operator_ui_restructure_plan.md` for the segment-level plan and `spec/target_operator_map.md` for the design target.

---

## Decisions locked for 9.4B

1. **Setup table helper lives in `app/web/views.py`** (new module, view-shape adapter co-located with the route). Returns the row tuples `[(label, count_or_status, manage_url, optional_delete_url, ...)]` consumed by `session_detail.html`. Service modules stay business-logic-only.
2. **Setup table rows for 9.4C-only surfaces render disabled.** Both **Instruments** (collapsed → `/instruments` index) and **Set up invites** (`/setupinvite`) render in the table now, with their Manage buttons disabled and a "lands in 9.4C" tooltip. Preserves the visual shape so 9.4C is purely additive lighting-up of buttons.
3. **Validate-on-session-detail = `POST /operator/sessions/{id}/validate-summary`.** Re-renders `session_detail.html` with the summary card populated above the Run Session card. Sticky for that response only — refresh loses the card. The existing `/validate` GET stays unchanged (its only edit in 9.4B is removing the activate form, see #4).
4. **`/validate` becomes read-only.** The activate form is removed from `session_validate.html`; the page stays as the "View detailed validation" deep-dive target. Activation is single-source: only on the inline summary card.
5. **Danger zone = one card, two stacked confirm-checkbox forms.** Delete data form sits above Delete session form inside the existing Danger zone card. Default button label: **Delete data** (matches plan wording). Audit event: `responses.deleted_all` with `detail = {"deleted_count": N}`. Allowed in any session status (including ready).
6. **Edit-lock semantics in 9.4B = unchanged from today.** Setup-card Manage links stay clickable when `status="ready"` (read-only nav, today's behaviour). **Edit details** on the Session card is hidden when ready. **Revert to draft** appears as a contextual button on the Session card when ready. **Delete Session** in Danger zone is disabled when ready (today's "deletion locked while ready" message). **Delete Data** is allowed in any status, including ready. The richer lifecycle (a new stored `validated` state between `draft` and `ready`) is deferred to its own segment — see "Deferred to Segment 9.5" below.

---

## Deferred to Segment 9.5 — Setup-readiness lifecycle states

Locked here so 9.4B's UI doesn't paint itself into a corner. **Not implemented in 9.4B.** Segment 9.5 will add a new stored state `validated` to the existing `SessionStatus` enum and rewire the activation flow against it.

- **D1 — `validated` is a stored state**, not derived. Sticky across renders so the inline summary card has a real home (rather than one-shot per validate POST).
- **D2 — Invalidation triggers (`validated → draft`):** every setup-mutating route that can affect validation outcome. Today's set: reviewer import + delete-all, reviewee import + delete-all, assignment generate + delete-all, session edit (name/code/description/deadline). Instrument open/close/visibility do **not** invalidate (they don't change validation results).
- **D3 — Acknowledge-warnings is implicit in `validated`.** Entering the `validated` state means "no blocking conditions" — warnings, if any, are acknowledged at the moment of transition. No separate `warnings_acknowledged_at` column.
- **D4 — Revert from `ready` lands on `draft`**, not `validated`. Forces the operator to re-run validation before the next activation.
- **D5 — "Locked but invalid" is unreachable.** Activation requires `can_activate` (no errors); revert always drops to `draft`. No transition reaches "locked + invalid."
- **D6 — Scope split.** 9.4B ships against today's two-state semantics (`draft`/`ready`); 9.5 introduces `validated` and rewrites every mutating route's invalidation hook. Keeps 9.4B's diff focused on UI restructure.

Full-state target after 9.5: `draft` → `validated` → `ready` → `expired` (Segment 9.3+) → `archived` (Segment 11+).

---

## Implementation slices

_Not yet drafted. Will land once Decision 6 is locked._

---

## Out of scope (explicitly deferred)

_Not yet drafted._

---

## Docs to update at PR time

_Not yet drafted._

---

## Risk notes

_Not yet drafted._
