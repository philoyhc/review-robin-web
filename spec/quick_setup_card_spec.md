## Quick Setup card — functional spec

A Home-body element on the per-session Control Panel page that lets an operator bulk-populate or replace a session's setup data (Reviewers, Reviewees, Relationships, Settings) from CSV files, in one place.

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

The card contains four live slots: Reviewers, Reviewees, Relationships, Settings. All four share a "file upload" shape — no rule selectors or other slot-specific input modes. The Assignments slot retired in Segment 15D PR 7a (assignments are a materialised derivative post-15D, generated from the Operations Assignments page rather than uploaded directly); Relationships took its position in 15D PR 7c, and Settings graduated from inert to wired in 12A-3 PR 4 (post-cleanup polish #768 settled the final two-column layout).

**Layout.** A two-column grid hosts the slots. Reviewers + Reviewees stack in the left column; Relationships + Settings stack in the right column. There is no horizontal divider between the slot groups.

**Slot 1 — Reviewers** (left column, top).
- File upload accepting CSV.
- Passive indicator showing current count: "Reviewers (8 currently)" or "Reviewers (none yet)".

**Slot 2 — Reviewees** (left column, bottom).
- Same shape as Reviewers.
- Passive indicator: "Reviewees (13 currently)" or "Reviewees (none yet)".

**Slot 3 — Relationships** (right column, top).
- File upload accepting a Relationships CSV (`ReviewerEmail`, `RevieweeEmail`, `PairContextTag1..3`, `Status`).
- Passive indicator: "Relationships (87 currently)" or "Relationships (none yet)".
- The CSV's `tag_N` slots flow through to the rule engine via the `pair_context.tag1` / `pair_context.tag2` / `pair_context.tag3` predicate field names; `status` defaults to `active` when omitted.

**Slot 4 — Settings** (right column, bottom).
- File upload accepting a session-settings CSV (the inverse shape of `serialize_session_config`'s wide CSV output — see `app/services/session_config_io.py`).
- Passive indicator: a "Settings configured" pill (always populated — a session always has settings).
- Wired in Segment 12A-3 PR 4 against `apply_session_config(...)`. The two-phase parse + apply contract validates every row first, then wipes and replaces; round-trip stable on the export's own output.

There is **no** per-slot Submit button. The card carries a single bottom Submit (see "Submission semantics" below) that runs every slot whose input is present.

### CSV format

Each CSV's expected schema (column names, required vs. optional fields, encoding) is defined in the existing per-entity import paths (Reviewers, Reviewees, Relationships, Settings). The card reuses the same schemas and the same parsing/validation logic — it does not introduce a new file format. If those schemas are documented elsewhere in the spec, link to them; if not, document them in the same module that handles the existing per-entity uploads.

### Submission semantics

**Single bottom Submit.** The card carries one Submit button at the bottom, on the same row as the Lock / Unlock toggle. Submit sits left, Lock / Unlock sits right; both render `btn secondary`. Clicking Submit posts every slot's input in one form to `POST /operator/sessions/{id}/quick-setup/submit-all`.

**Submit-enable gate.** The Submit button starts `disabled` and enables only when at least one `<input type="file">` on any slot has a file selected. Inline JS toggles the `disabled` attribute on `change`.

**Replace semantics.** Each slot replaces the entire corresponding dataset for the session. Merge semantics are not supported; per-record edits remain on the per-entity Setup pages. Replacing reviewers or reviewees automatically clears existing assignments and relationships (cascade inside the replacement transaction).

**Replacement confirmation.** A single card-level checkbox sits above the slot grid, inside the `.quick-setup-body` wrapper:

> ☐ Yes, replace existing reviewers, reviewees or settings, according to what is uploaded.

Inline JS mirrors the checkbox state into the form's hidden `confirm_replace` input on submit. The route gate stays the source of truth: when any slot whose `existing > 0` runs without `confirm_replace == "true"`, the submit 303s with `?quick_setup_error={kind}&quick_setup_reason=needs_confirm` and the slot's banner-error directs the operator at the card-level checkbox.

**Per-slot dispatch.** The submit-all handler dispatches each slot whose input is present, in order: Reviewers → Reviewees → Relationships → Settings. On the first slot's failure it 303s with that slot's `quick_setup_error` flag and later slots don't run. Each slot routes through the same per-entity import primitive the per-entity Setup pages use (`_handle_quick_setup_import` for Reviewers / Reviewees, `save_relationships` for Relationships, `apply_session_config` for Settings).

**Empty submissions** are clean no-op redirects — submit-all without any input 303s back to Home with no slot fragment.

**Cascading effects.** Replacing reviewers or reviewees automatically clears existing assignments and relationships (they reference reviewer / reviewee IDs); replacing relationships or settings has no cascade beyond its own dataset. The cascade happens inside the replacement transaction; the card does not auto-regenerate assignments after a reviewer / reviewee / relationships replacement, and the operator returns to the Operations Assignments page to regenerate.

The single card-level checkbox covers the cascade implicitly — its copy ("any existing reviewers, reviewees, relationships or settings") names every entity that might be cleared by any combination of slot uploads. Per-slot inline cascade banners (formerly the `banner-warning` per slot) are not used.

**Locked state.** The card-level checkbox sits inside `.quick-setup-body`, so it greys along with the H2 title and slot controls when the card is locked. Greying is not the only signal: when the card is locked, the slot file inputs **and** the replacement-confirmation checkbox also carry the HTML `disabled` attribute, so a locked card cannot have a file staged or the box ticked — not merely a greyed-but-live surface.

**Lock state on navigation.** Unlocking the card sets a per-session cookie (`qsu_{session_id}=1`, scoped to `/operator/sessions/{id}`) that survives form submissions on Session Home itself — the operator can unlock once, upload through several slots, and stay unlocked. Navigating to **any other page** (per-entity Setup pages, Operations tabs, the sessions lobby, any other operator route) expires the cookie via a Starlette HTTP middleware. Returning to Session Home then renders the card locked again. The Quick Setup endpoints themselves (`/quick-setup/lock`, `/quick-setup/submit-all`, and the legacy per-slot endpoints retained for fixture compatibility) are whitelisted so the card's own form submissions don't trigger the relock.

### Result reporting

After a slot's submission completes, the slot reports the outcome inline:

- **Success:** "8 reviewers loaded." / "87 relationships loaded." / "Settings applied." The passive count indicator updates to reflect the new state.
- **Parse error:** "Could not parse CSV: row 5, column 'email' is empty." Errors are scoped to the offending slot and as specific as the parser can make them. The slot remains populated with the operator's selection so they can see what they uploaded; existing data is not replaced.
- **Validation error:** "Reviewer ID 'r-99' on row 12 is not unique." Same scoping; same non-destructive behavior.

Errors in one slot do not affect other slots' submissions or existing data.

### Validation scope

The card validates each file individually for parse correctness and per-file integrity (unique IDs, required fields, well-formed values). It does **not** perform cross-entity validation — checking whether assignments correctly reference existing reviewers and reviewees, for example, is the existing Validate page's job and is surfaced via the lifecycle-transition action on Home.

### Interaction with per-entity Setup pages

The Quick Setup card and the per-entity Setup pages (Reviewers, Reviewees, Relationships) are independent. After using Quick Setup, the operator can navigate to any per-entity page and edit individual records normally. The per-entity pages' upload affordances remain functional and behave identically to the card's slots — they share the same parsing, validation, and replacement semantics. Settings has no dedicated Setup page; the Quick Setup Slot 4 + the Settings extract download on the Extract Data card are the round-trip pair.

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

The description copy explains the rule from the operator's vantage point. It has two variants: the default ("Available only when session is in draft mode and does not have any responses.") and a responses-specific one shown when the session holds responses — typically a session activated then reverted to draft, which keeps its responses and so lands `draft`-but-locked. The responses variant names the reason ("Quick Setup is locked because this session already holds reviewer responses from a prior activation.") and points the operator at the per-entity Setup pages. Both gates otherwise show up as the same visual signal (greyed body with disabled controls, no toggle). Defense-in-depth route gates (`_require_editable` + `_require_response_loss_ack`) stay in place but never fire from this surface because the submit forms aren't reachable when the body's locked.

### New-session variant (`/operator/sessions/new`)

The Quick Setup card also renders on the create-new-session page, below the Session details form. The variant has three differences from the Home version:

- **Title.** "Quick setup (optional)" — flags that the operator can fill it in alongside the session details, but doesn't have to.
- **Lock / Unlock toggle suppressed.** There's no session row to lock; the card is always-unlocked. The footer row that holds Submit + Lock on Home doesn't render.
- **No card-level replacement-confirmation checkbox.** A freshly-created session has nothing to replace, so the "This will replace any existing reviewers, reviewees, relationships or settings…" affordance is omitted. The body wrapper still exists; only the checkbox is suppressed.

**Submission semantics.** The card has no Submit button of its own. Each slot's inputs associate with the create-session form via the HTML `form="create-session-form"` attribute, so the single "Create session" button submits both the session details and any staged Quick Setup uploads in one POST. After `POST /operator/sessions` creates the session, the handler dispatches each provided slot through the same per-slot pipeline (`_handle_quick_setup_import` for Reviewers / Reviewees, `save_relationships` for Relationships, `apply_session_config` for Settings) the Home consolidated submit-all uses. `confirm_replace` is implicitly `"true"` on this path — there's nothing to overwrite, so the route layer's gate is satisfied trivially.

**Failure mode.** Session creation runs first; if it succeeds and a downstream slot fails, the operator lands on Session Home with that slot's `?quick_setup_error=…&quick_setup_reason=…` flag and the slot's banner-error rendered in place. The session row stays — the operator retries the failing slot from the Home Quick Setup card.

### Doc taxonomy

The card does not appear in the page taxonomy or the chrome. The chrome (two-row navigation, Home anchor, Setup/Operations rows) is unaffected by this work. The only doc change is in the description of what Home's body contains; the page list, the nav model, and the principles (P1–P4) are unchanged.

### Implementation pointers

- Reuse the existing per-entity CSV parsing and validation modules. The card is a UI affordance over the same import paths the Setup pages already expose.
- Reuse the cascading-clearance logic that the per-entity pages already implement (or should implement) when reviewers/reviewees are replaced — the card should not introduce a parallel cascade implementation.
- The card's locked-state styling is a single `.quick-setup-body.locked` body wrapper applied uniformly across `draft` / `validated` / `ready`, and includes the H2 title + the card-level confirmation checkbox alongside the slot controls. On top of the greying, a locked card's slot file inputs and confirmation checkbox carry the HTML `disabled` attribute (the `quick_setup_slot` macro takes a `locked` flag; the checkbox keys off `quick_setup.is_locked`) so the controls are genuinely inert, not merely dimmed. The Lock / Unlock toggle is the consistent affordance; lifecycle-driven differences live in the description copy and the route layer's `_require_editable` rejection, not in a separate visual primitive.
- The card-level confirmation checkbox is a plain `<input type="checkbox">` outside any slot form. Inline JS on each form's `submit` event mirrors the checkbox state into a hidden `confirm_replace` input on the form. Server-side `confirm_replace == "true"` gate stays the source of truth — the JS just spares the operator from per-slot bookkeeping.

The intent throughout: Quick Setup is a thin convenience surface over existing import primitives. It should not own meaningful logic of its own.
