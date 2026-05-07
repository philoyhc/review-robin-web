## Quick Setup card — functional spec

A Home-body element on the per-session Control Panel page that lets an operator bulk-populate or replace a session's setup data (Reviewers, Reviewees, Assignments) from files or rules, in one place.

### Location

Renders in the body of the Session Home / Control Panel page (`session_detail.html`, `GET /operator/sessions/{id}`). Not a separate page; not a sub-page; no dedicated URL.

Position in the Home body, top to bottom:

1. Session identity (name, code, lifecycle state).
2. Contextual lifecycle-transition action (Validate / Activate / Close / Reopen).
3. **Quick Setup card.**
4. Setup-readiness summary and pointers into Operations.
5. Sub-page links (Edit Session, Validate detail).

### Visibility

The card is always rendered on Home for `draft` and `validated` sessions. Visibility does not depend on whether setup data exists — the card is a stable, learnable location for bulk setup regardless of session population.

For `ready` and `closed` sessions, the card renders the same body-greying as the default `is_locked=True` treatment in `draft` / `validated` — the body wrapper carries `.quick-setup-body.locked`, and the Lock / Unlock toggle stays visible in every editable-conceivable state. Per `spec/session_home.md` ("Disabled treatment on Home is plain greying-out, not yellow lock cards"), Home does not stack a yellow lock card on top of the body greying. On `ready`, unlocking the card is purely visual — the importer rejects mutating submits at the service layer (`_require_editable`) and the rejection surfaces inline as a scoped `banner-error` carrying "Pause the session before applying setup changes" copy. Current-state indicators (counts, rule label) render in every state.

### Slots

The card contains three independent slots:

**Slot 1 — Reviewers.**
- File upload accepting CSV.
- Passive indicator showing current count: "Reviewers (8 currently)" or "Reviewers (none yet)".
- Submit button scoped to this slot.

**Slot 2 — Reviewees.**
- Same shape as Reviewers.
- Passive indicator: "Reviewees (13 currently)" or "Reviewees (none yet)".

**Slot 3 — Assignments.**

- Two interchangeable input modes:
  - **Rule selector** (default): dropdown or radio group with the supported assignment rules (full matrix, etc. — exact rule set defined elsewhere in the spec).
  - **CSV upload**: alternative to the rule selector for operators who want explicit assignments.
- Passive indicator showing current state: "Assignments (104 currently, full-matrix rule)" / "Assignments (104 currently, uploaded)" / "Assignments (none yet)".
- Submit button scoped to this slot.

The slots are independent: an operator can fill any subset and submit each separately. Submitting one slot does not affect the others.

### CSV format

Each CSV's expected schema (column names, required vs. optional fields, encoding) is defined in the existing per-entity import paths (Reviewers, Reviewees, Assignments). The card reuses the same schemas and the same parsing/validation logic — it does not introduce a new file format. If those schemas are documented elsewhere in the spec, link to them; if not, document them in the same module that handles the existing per-entity uploads.

### Submission semantics

**Per-slot, replace semantics.** Submitting a slot replaces the entire corresponding dataset for the session. Merge semantics are not supported in this card; per-record edits remain on the per-entity Setup pages.

**Replacement confirmation.** A single card-level checkbox sits above the slot grid, inside the `.quick-setup-body` wrapper:

> ☐ This will replace any existing reviewers, reviewees, assignments or settings, according to what is uploaded.

Submitting any slot reads the checkbox state and posts it as `confirm_replace=true|""`. The route gate stays the source of truth: when `existing > 0` and `confirm_replace != "true"`, the submit 303s with `?quick_setup_error={kind}&quick_setup_reason=needs_confirm` and the slot's banner-error directs the operator at the card-level checkbox.

**Empty-slot submissions** ignore the checkbox — the route gate doesn't fire when nothing's there to replace.

**Cascading effects.** Replacing reviewers or reviewees automatically clears existing assignments (they reference reviewer/reviewee IDs); replacing assignments has no cascade (assignments are leaf data). The cascade happens inside the replacement transaction; the card does not auto-regenerate assignments after a reviewer/reviewee replacement, and the operator returns to Slot 3 to regenerate or re-upload.

The single card-level checkbox covers the cascade implicitly — its copy ("any existing reviewers, reviewees, assignments or settings") names every entity that might be cleared by any combination of slot uploads. Per-slot inline cascade banners (formerly the `banner-warning` per slot) are not used.

**Locked state.** The card-level checkbox sits inside `.quick-setup-body`, so it greys along with the H2 title and slot controls when the card is locked.

### Result reporting

After a slot's submission completes, the slot reports the outcome inline:

- **Success:** "8 reviewers loaded." / "104 assignments generated by full-matrix rule." / "104 assignments loaded from file." The passive count indicator updates to reflect the new state.
- **Parse error:** "Could not parse CSV: row 5, column 'email' is empty." Errors are scoped to the offending slot and as specific as the parser can make them. The slot remains populated with the operator's selection so they can see what they uploaded; existing data is not replaced.
- **Validation error:** "Reviewer ID 'r-99' on row 12 is not unique." Same scoping; same non-destructive behavior.

Errors in one slot do not affect other slots' submissions or existing data.

### Validation scope

The card validates each file individually for parse correctness and per-file integrity (unique IDs, required fields, well-formed values). It does **not** perform cross-entity validation — checking whether assignments correctly reference existing reviewers and reviewees, for example, is the existing Validate page's job and is surfaced via the lifecycle-transition action on Home.

### Interaction with per-entity Setup pages

The Quick Setup card and the per-entity Setup pages (Reviewers, Reviewees, Assignments) are independent. After using Quick Setup, the operator can navigate to any per-entity page and edit individual records normally. The per-entity pages' upload affordances (if any) remain functional and behave identically to the card's slots — they share the same parsing, validation, and replacement semantics.

### Out of scope

- Per-record editing within the card (no inline tables, no row-level controls).
- CSV preview before submission (current count + filename is sufficient).
- Wizard-style stepping. Slots are independent; no enforced order.
- Cross-entity validation (handled by Validate).
- Auto-regeneration of assignments after a reviewer/reviewee replacement.
- Undo. Replacement is a destructive action gated by confirmation; there's no rollback affordance after the fact.
- Save-as-template or reuse-across-sessions. The card operates only on the current session.

### Lifecycle and state behavior summary

| Session state | Card behavior |
|---|---|
| `draft` | Fully interactive. All slots usable; confirmations apply when replacing populated data. |
| `validated` | Fully interactive. Same as `draft`. (Re-uploading may invalidate the validated state — see below.) |
| `ready` | Body-greyed via `.quick-setup-body.locked`; Lock / Unlock toggle still visible. Unlocking is cosmetic only — submits 303 → Home with a scoped `banner-error` ("Pause first") via `_require_editable`. Counts / rule still display. |
| `closed` | Same body-greying treatment as `ready`; submits rejected at the service layer. |

**Note on `validated` → re-upload.** If an operator successfully submits a slot on a `validated` session, the session's validated state is invalidated and the session returns to `draft`. This matches existing behavior on the per-entity Setup pages and should reuse the same state-transition logic.

### Doc taxonomy

The card does not appear in the page taxonomy or the chrome. The chrome (two-row navigation, Home anchor, Setup/Operations rows) is unaffected by this work. The only doc change is in the description of what Home's body contains; the page list, the nav model, and the principles (P1–P4) are unchanged.

### Implementation pointers

- Reuse the existing per-entity CSV parsing and validation modules. The card is a UI affordance over the same import paths the Setup pages already expose.
- Reuse the cascading-clearance logic that the per-entity pages already implement (or should implement) when reviewers/reviewees are replaced — the card should not introduce a parallel cascade implementation.
- The card's locked-state styling is a single `.quick-setup-body.locked` body wrapper applied uniformly across `draft` / `validated` / `ready`, and includes the H2 title + the card-level confirmation checkbox alongside the slot controls. The Lock / Unlock toggle is the consistent affordance; lifecycle-driven differences live in the description copy and the route layer's `_require_editable` rejection, not in a separate visual primitive.
- The card-level confirmation checkbox is a plain `<input type="checkbox">` outside any slot form. Inline JS on each form's `submit` event mirrors the checkbox state into a hidden `confirm_replace` input on the form. Server-side `confirm_replace == "true"` gate stays the source of truth — the JS just spares the operator from per-slot bookkeeping.

The intent throughout: Quick Setup is a thin convenience surface over existing import primitives. It should not own meaningful logic of its own.
