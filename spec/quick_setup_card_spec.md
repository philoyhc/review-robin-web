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

The card contains four slots — three live (Reviewers, Reviewees, Assignments) and one inert pending Segment 12A PR 6 (Session settings). Slots 1 / 2 / 4 share a "file upload" shape; slot 3 (Assignments) carries an extra rule selector.

**Layout.** A two-column grid hosts the slots. Reviewers, Reviewees, and Session settings stack in the left column; Assignments stands alone in the right column. There is no horizontal divider between the slot groups.

**Slot 1 — Reviewers** (left column, top).
- File upload accepting CSV.
- Passive indicator showing current count: "Reviewers (8 currently)" or "Reviewers (none yet)".

**Slot 2 — Reviewees** (left column, middle).
- Same shape as Reviewers.
- Passive indicator: "Reviewees (13 currently)" or "Reviewees (none yet)".

**Slot 3 — Assignments** (right column).
- Two interchangeable input modes:
  - **"Generate by rule" dropdown** (default): populated with every visible RuleSet — seeds first in install order, then caller-owned Personal RuleSets — same canonical ordering as the Rule Based card on the Assignments page (§7 of `spec/rule_based_assignment.md`). The default option is a `"— —"` sentinel that means "skip the assignments slot at submit time"; the operator may not want Quick Setup to generate assignments and can leave the dropdown alone.
  - **"or upload a CSV." file upload**: alternative to the rule selector for operators who want explicit assignments. File-takes-precedence over rule when both are provided.
- A self-review checkbox sits below the pair of inputs. Override only — the underlying RuleSet revision's `excludeSelfReviews` value still travels with the audit row.
- Passive indicator showing current state: "Assignments (104 currently, rule_based)" / "Assignments (104 currently, manual)" / "Assignments (none yet)".

**Slot 4 — Session settings** (left column, bottom).
- File upload accepting a session-settings CSV. Wired in Segment 12A PR 6; until then renders disabled with a wiring tooltip.
- No count copy (the slot is inert; populating one would imply the wiring exists).

There is **no** per-slot Submit button. The card carries a single bottom Submit (see "Submission semantics" below) that runs every slot whose input is present.

### CSV format

Each CSV's expected schema (column names, required vs. optional fields, encoding) is defined in the existing per-entity import paths (Reviewers, Reviewees, Assignments). The card reuses the same schemas and the same parsing/validation logic — it does not introduce a new file format. If those schemas are documented elsewhere in the spec, link to them; if not, document them in the same module that handles the existing per-entity uploads.

### Submission semantics

**Single bottom Submit.** The card carries one Submit button at the bottom, on the same row as the Lock / Unlock toggle. Submit sits left, Lock / Unlock sits right; both render `btn secondary`. Clicking Submit posts every slot's input in one form to `POST /operator/sessions/{id}/quick-setup/submit-all`.

**Submit-enable gate.** The Submit button starts `disabled` and enables only when at least one `<input type="file">` on any slot has a file selected. Inline JS toggles the `disabled` attribute on `change`. Selecting a non-default option in the assignments rule dropdown alone does **not** enable Submit — operators wanting rule-based generation without a file use the Rule Based card on the Assignments page instead. (The handler still runs the assignments slot's rule when Submit fires from another slot's file selection — the gate is only on button enable, not on what runs.)

**Replace semantics.** Each slot replaces the entire corresponding dataset for the session. Merge semantics are not supported; per-record edits remain on the per-entity Setup pages. Replacing reviewers or reviewees automatically clears existing assignments (cascade inside the replacement transaction).

**Replacement confirmation.** A single card-level checkbox sits above the slot grid, inside the `.quick-setup-body` wrapper:

> ☐ This will replace any existing reviewers, reviewees, assignments or settings, according to what is uploaded.

Inline JS mirrors the checkbox state into the form's hidden `confirm_replace` input on submit. The route gate stays the source of truth: when any slot whose `existing > 0` runs without `confirm_replace == "true"`, the submit 303s with `?quick_setup_error={kind}&quick_setup_reason=needs_confirm` and the slot's banner-error directs the operator at the card-level checkbox.

**Per-slot dispatch.** The submit-all handler dispatches each slot whose input is present, in order: Reviewers → Reviewees → Assignments. On the first slot's failure it 303s with that slot's `quick_setup_error` flag and later slots don't run. The Assignments slot runs when either an `assignments_file` is attached (manual CSV) or a positive `rule_set_id` is sent (rule-based via `engine.evaluate`); the `"— —"` sentinel value resolves to "skip the slot".

**Empty submissions** are clean no-op redirects — submit-all without any input 303s back to Home with no slot fragment.

**Cascading effects.** Replacing reviewers or reviewees automatically clears existing assignments (they reference reviewer/reviewee IDs); replacing assignments has no cascade (assignments are leaf data). The cascade happens inside the replacement transaction; the card does not auto-regenerate assignments after a reviewer/reviewee replacement, and the operator returns to Slot 3 to regenerate or re-upload.

The single card-level checkbox covers the cascade implicitly — its copy ("any existing reviewers, reviewees, assignments or settings") names every entity that might be cleared by any combination of slot uploads. Per-slot inline cascade banners (formerly the `banner-warning` per slot) are not used.

**Locked state.** The card-level checkbox sits inside `.quick-setup-body`, so it greys along with the H2 title and slot controls when the card is locked.

**Lock state on navigation.** Unlocking the card sets a per-session cookie (`qsu_{session_id}=1`, scoped to `/operator/sessions/{id}`) that survives form submissions on Session Home itself — the operator can unlock once, upload through several slots, and stay unlocked. Navigating to **any other page** (per-entity Setup pages, Operations tabs, the sessions lobby, any other operator route) expires the cookie via a Starlette HTTP middleware. Returning to Session Home then renders the card locked again. The Quick Setup endpoints themselves (`/quick-setup/lock`, `/quick-setup/submit-all`, and the legacy per-slot endpoints retained for fixture compatibility) are whitelisted so the card's own form submissions don't trigger the relock.

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

| Session state | Persisted responses? | Card behavior |
|---|---|---|
| `draft` | None | **Available.** Fully interactive. Lock / Unlock toggle visible; unlocking reveals the slot controls. |
| `draft` | Any | **Unavailable.** Body greyed via `.quick-setup-body.locked`; Lock / Unlock toggle hidden entirely. Operator routes to per-entity Setup pages (which have the response-loss-acknowledgment flow) for any further changes. |
| `validated` | (any) | **Unavailable.** Same body-greying + no-toggle treatment as `draft`-with-responses. The validated state is meant to be a final-check state; bulk re-uploads route through per-entity Setup pages instead. |
| `ready` | (any) | **Unavailable.** Same treatment. Counts / rule still display in the greyed body for context. |
| `closed` | (any) | Same as `ready`. |

The single description copy ("Available only when session is in draft mode and does not have any responses.") covers the rule from the operator's vantage point — both gates show up as the same visual signal (greyed body, no toggle). Defense-in-depth route gates (`_require_editable` + `_require_response_loss_ack`) stay in place but never fire from this surface because the submit forms aren't reachable when the body's locked.

### Doc taxonomy

The card does not appear in the page taxonomy or the chrome. The chrome (two-row navigation, Home anchor, Setup/Operations rows) is unaffected by this work. The only doc change is in the description of what Home's body contains; the page list, the nav model, and the principles (P1–P4) are unchanged.

### Implementation pointers

- Reuse the existing per-entity CSV parsing and validation modules. The card is a UI affordance over the same import paths the Setup pages already expose.
- Reuse the cascading-clearance logic that the per-entity pages already implement (or should implement) when reviewers/reviewees are replaced — the card should not introduce a parallel cascade implementation.
- The card's locked-state styling is a single `.quick-setup-body.locked` body wrapper applied uniformly across `draft` / `validated` / `ready`, and includes the H2 title + the card-level confirmation checkbox alongside the slot controls. The Lock / Unlock toggle is the consistent affordance; lifecycle-driven differences live in the description copy and the route layer's `_require_editable` rejection, not in a separate visual primitive.
- The card-level confirmation checkbox is a plain `<input type="checkbox">` outside any slot form. Inline JS on each form's `submit` event mirrors the checkbox state into a hidden `confirm_replace` input on the form. Server-side `confirm_replace == "true"` gate stays the source of truth — the JS just spares the operator from per-slot bookkeeping.

The intent throughout: Quick Setup is a thin convenience surface over existing import primitives. It should not own meaningful logic of its own.
