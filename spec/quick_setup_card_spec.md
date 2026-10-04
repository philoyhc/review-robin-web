## Quick Setup card — functional spec

A Home-body element on the per-session Control Panel page that lets an operator bulk-populate or replace a session's setup data (Reviewers, Reviewees, Relationships, Settings) from CSV files, in one place.

### Location

Renders in the body of the Session Home / Control Panel page (`session_detail.html`, `GET /operator/sessions/{id}`). Not a separate page; not a sub-page; no dedicated URL.

Position in the Home body, top to bottom:

1. **Workflow card** — the contextual lifecycle-transition action
   (Prepare / Activate / Close / Revert to draft), full-width.
2. **Session details card** — the consolidated config
   display ↔ edit surface (`?editing=1`), full-width. There is no
   separate Edit Session sub-page; every config field is edited in
   place here — see `spec/session_home.md` §4.
3. **Quick Setup card** — bottom-left of the `.bottom-grid`,
   paired with the Owners card over the Danger Zone on the right
   (`spec/session_home.md` §3a).

### Visibility

The card is always rendered on Home, in every state. Visibility does not depend on whether setup data exists — the card is a stable, learnable location for bulk setup regardless of session population.

The card is **available** only in `draft` with no persisted responses (`is_available` in `app/web/views/_quick_setup.py`). There the Lock / Unlock toggle renders, and the card still defaults to locked. In every other state — `draft` with responses, `validated`, `ready`, `expired` — the body is greyed (`.quick-setup-body.locked`) and the **toggle is hidden** (`show_lock_toggle = is_available`), so the operator cannot unlock it; the lifecycle table below gives each state. Per `spec/session_home.md` ("Disabled treatment on Home is plain greying-out, not yellow lock cards"), Home does not stack a yellow lock card on top of the body greying. The card shows no current-state indicators (see **Slots**).

### Slots

The card contains four always-present live slots (Reviewers, Reviewees, Relationships, Settings) and one conditional slot (Observers). All five share a "file upload" shape — no rule selectors or other slot-specific input modes. **The card must not gain an Assignments slot.** Assignments are a materialized derivative — the Workflow card's **Prepare session** generates one row per eligible `(reviewer, reviewee, instrument)` triple from each instrument's rule (`spec/assignments.md`) — not a dataset an operator uploads.

**Layout.** A two-column grid hosts the slots. Reviewers + Reviewees stack in the left column; Relationships + Settings (+ Observers when visible) stack in the right column. There is no horizontal divider between the slot groups.

**No count indicators.** Each slot's heading is its label and the inline action "Upload a CSV"; it does not show how many rows the session holds. The per-slot counts were removed deliberately in `40bc2549`, and the removal stands (author's ruling, 2026-10-02, findings C2): the per-entity Setup pages carry the counts.

**Slot 1 — Reviewers** (left column, top).
- File upload accepting CSV.

**Slot 2 — Reviewees** (left column, bottom).
- Same shape as Reviewers.

**Slot 3 — Relationships** (right column, top).
- File upload accepting a Relationships CSV (`ReviewerEmail`, `RevieweeEmail`, `PairContextTag1..3`, `Status`).
- The CSV's `tag_N` slots flow through to the rule engine via the `pair_context.tag1` / `pair_context.tag2` / `pair_context.tag3` predicate field names; `status` defaults to `active` when omitted.

**Slot 4 — Settings** (right column, bottom).
- File upload accepting a session-settings CSV (the inverse shape of `serialize_session_config`'s wide CSV output — see `app/services/session_config_io/`).
- Applies through `apply_session_config(...)`. The two-phase parse + apply contract validates every row first, then wipes and replaces; round-trip stable on the export's own output.

There is **no** per-slot Submit button. The card carries a single bottom Submit (see "Submission semantics" below) that runs every slot whose input is present.

**The per-slot routes still exist and no UI calls them** — zero references in any template. Four of them take the `POST …/quick-setup/{kind}` shape (`reviewers`, `reviewees`, `relationships`, `observers`); the Settings slot's is `POST …/import-config`, which predates the card and never moved under the `quick-setup` prefix. They stay as backend entry points, exercised by tests; the card reaches the same per-slot pipeline through `submit-all`. Anything that describes them as reachable from the card is describing the pre-consolidation shape.

### CSV format

Each CSV's expected schema (column names, required vs. optional fields, encoding) is defined in the existing per-entity import paths (Reviewers, Reviewees, Relationships, Settings). The card reuses the same schemas and the same parsing/validation logic — it does not introduce a new file format. If those schemas are documented elsewhere in the spec, link to them; if not, document them in the same module that handles the existing per-entity uploads.

### Submission semantics

**Single bottom Submit.** The card carries one Submit button at the bottom, on the same row as the Lock / Unlock toggle. Submit sits left, Lock / Unlock sits right; both render `btn secondary`. Clicking Submit posts every slot's input in one form to `POST /operator/sessions/{id}/quick-setup/submit-all`.

**Submit-enable gate.** The Submit button starts `disabled` and enables only when **both** (1) at least one `<input type="file">` on any slot has a file selected AND (2) the card-level confirm-replace checkbox is ticked. Inline JS toggles the `disabled` attribute on both the file inputs' `change` event and the checkbox's `change` event. The checkbox renders only on the existing-session variant; on the new-session variant the create-session button drives submission and this gate doesn't apply.

**Replace semantics.** Each slot replaces the entire corresponding dataset for the session; what a replacement takes with it is `spec/setup_pages.md` § *What a delete takes with it*, which governs every reviewer-delete surface alike. Merge semantics are not supported; per-record edits remain on the per-entity Setup pages. Replacing reviewers or reviewees automatically clears existing assignments and relationships (cascade inside the replacement transaction).

**Replacement confirmation.** A single card-level checkbox sits below the slot grid, inside the `.quick-setup-body` wrapper and just above the footer's Submit:

> ☐ Yes, replace existing reviewers, reviewees or settings, according to what is uploaded. A settings file rebuilds every instrument and deletes its assignments.

Inline JS mirrors the checkbox state into the form's hidden `confirm_replace` input on submit. The route gate stays the source of truth: when any roster slot whose `existing > 0` runs, or the Settings slot runs on an existing session, without `confirm_replace == "true"`, the submit 303s with `?quick_setup_error={kind}&quick_setup_reason=needs_confirm` and the slot's banner-error directs the operator at the card-level checkbox. Where responses exist, the Reviewers, Reviewees and Settings slots also need `acknowledge_response_loss=true` (Relationships and Observers check the tick only) (`spec/lifecycle.md` §3.2); the card never sends it, because it is locked whenever responses exist, so only a direct POST that bypasses the card can reach that case (findings C3). A refusal on the missing acknowledgement shows the same `needs_confirm` banner as a missing tick, as the Reviewers and Reviewees slots do.

**Per-slot dispatch.** The submit-all handler dispatches each slot whose input is present, in order: Reviewers → Reviewees → Relationships → Observers → Settings. On the first slot's failure it 303s with that slot's `quick_setup_error` flag and later slots don't run. Each slot routes through the same helper the per-slot route and the create-session POST use — `_run_quick_setup_import` for Reviewers / Reviewees, `_run_quick_setup_relationships` for Relationships, `_run_quick_setup_observers` for Observers, `_run_quick_setup_settings` for Settings — and those helpers call the per-entity save primitives one layer down. The distinction matters: the four helpers are the **only** save sites behind every Quick Setup upload route, which is what makes a fix at one of them reach all of them (19R Item 4).

**Empty submissions** are clean no-op redirects — submit-all without any input 303s back to Home with no slot fragment.

**Cascading effects.** Replacing reviewers or reviewees automatically clears existing assignments and relationships (they reference reviewer / reviewee IDs); replacing relationships has no cascade beyond its own dataset, except that a pair it moves to another pair-context group gives up the group answer copy it carried (`spec/assignments.md` "Group-scoped fan-out"). Replacing **settings** rebuilds every instrument, which deletes the session's assignments and any responses with them (findings C3). Replacing **reviewers** also clears their invitations, and unlinks — rather than deletes — the `email_outbox` rows that reference them. The cascade happens inside the replacement transaction; the card does not auto-regenerate assignments after a reviewer / reviewee / relationships replacement. Regeneration fires from Session Home's Workflow card stepper, which is where every other lifecycle action starts; the Assignments page carries the same action for an operator already on it.

The single card-level checkbox covers the cascade: its copy (quoted under **Replacement confirmation** above) names the reviewers, reviewees and settings an upload replaces and says outright that a settings file rebuilds every instrument and deletes its assignments; a roster replace's own cascade (assignments, relationships, invitations) it covers implicitly. Per-slot inline cascade banners are not used.

**Locked state.** The card-level checkbox sits inside `.quick-setup-body`, so it greys along with the H2 title and slot controls when the card is locked. Greying is not the only signal: when the card is locked, the slot file inputs **and** the replacement-confirmation checkbox also carry the HTML `disabled` attribute, so a locked card cannot have a file staged or the box ticked — not merely a greyed-but-live surface.

**Lock state on navigation.** Unlocking the card sets a per-session cookie (`qsu_{session_id}=1`, path `/`) that survives form submissions on Session Home itself — the operator can unlock once, upload through several slots, and stay unlocked. Navigating to **any other page** (per-entity Setup pages, Operations tabs, the sessions lobby, another session's Home, any other operator route) expires the cookie via a Starlette HTTP middleware. Returning to Session Home then renders the card locked again. The Quick Setup endpoints themselves (`/quick-setup/lock`, `/quick-setup/submit-all`, and the per-slot `/quick-setup/{kind}` endpoints) are allowlisted so the card's own form submissions don't trigger the relock, as are Session Home's Owners card endpoints (`/owners/...`), whose own `oou_` unlock cookie shares the middleware (`spec/session_owners.md` §2). The Settings slot's per-slot route, `POST …/import-config`, sits outside the `quick-setup` prefix and is not allowlisted, so a direct POST to it relocks the card; no UI calls it.

### Result reporting

The card reports failures only; success messages and the roster slots' per-row errors were removed with the counts in `40bc2549`, and the removal stands (findings C2). The Settings slot is the exception below: it has no Setup page to send the operator to.

- **Success:** no message. Submit redirects back to Home at the last slot that ran (`#quick-setup-{kind}`).
- **Failure:** a `banner-error` above the slot grid, tied to the failing slot by its `quick-setup-{kind}-error-banner` id, carrying one short sentence from `_quick_setup_error_message` in `app/web/views/_quick_setup.py`. A file that fails to parse or validate reads "Could not import reviewers. Open the Reviewers Setup page for per-row error details." — the per-entity Setup page is where per-row errors are shown. A Settings CSV that fails validation reads "Could not import session settings." and lists its errors under that sentence, one line each (`Row 3, instruments[1].name: …`), five at most and then "…and N more.", as `spec/csv_contracts.md` §3.3 asks; the lines travel in the redirect as `quick_setup_detail` values. A missing confirmation tick and a lifecycle refusal each have their own sentence.

A failing slot replaces nothing of its own dataset. Slots run in the order given under **Per-slot dispatch**, so a slot that succeeded before the failure stays applied, and the slots after it do not run.

### Validation scope

The card validates each file individually for parse correctness and per-file integrity (unique IDs, required fields, well-formed values). Beyond that it performs **one** cross-roster check, and only the one the write paths perform everywhere else: `check_cross_table_identity` on each roster slot, rejecting a row whose email another roster already holds under a different name (`spec/csv_contracts.md` §3.1; the Observers slot joined at 19Q Item 7). Everything else is left to the Validate page — whether assignments correctly reference existing reviewers and reviewees, for example, is its job and is surfaced via the lifecycle-transition action on Home.

### Interaction with per-entity Setup pages

The Quick Setup card and the per-entity Setup pages (Reviewers, Reviewees, Relationships) are independent. After using Quick Setup, the operator can navigate to any per-entity page and edit individual records normally. The per-entity pages' upload affordances remain functional and behave identically to the card's slots — they share the same parsing, validation, and replacement semantics. Settings has no dedicated Setup page; the Quick Setup Slot 4 + the Settings extract download on the Extract Setup card (on the Extract data Operations tab) are the round-trip pair.

### Out of scope

- Per-record editing within the card (no inline tables, no row-level controls).
- CSV preview before submission (the browser's file input shows the filename).
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
| `ready` | (any) | **Unavailable.** Same treatment. |
| `expired` | (any) | Same as `ready`. |

The description copy explains the rule from the operator's vantage point. It has two variants: the default ("Available only when session is in draft mode and does not have any responses.") and a responses-specific one shown when the session holds responses — typically a session activated then reverted to draft, which keeps its responses and so lands `draft`-but-locked. The responses variant names the reason ("Quick Setup is locked because this session already holds reviewer responses from a prior activation.") and points the operator at the per-entity Setup pages. Both gates otherwise show up as the same visual signal (greyed body with disabled controls, no toggle). Defense-in-depth route gates (`_require_editable` + `_require_response_loss_ack`) stay in place but never fire from this surface because the submit forms aren't reachable when the body's locked.

### New-session variant (`/operator/sessions/new`)

The Quick Setup card also renders on the create-new-session page, below the Session details form. The variant has three differences from the Home version:

- **Title.** "Quick setup (optional)" — flags that the operator can fill it in alongside the session details, but doesn't have to.
- **Lock / Unlock toggle suppressed.** There's no session row to lock; the card is always-unlocked. The footer row that holds Submit + Lock on Home doesn't render.
- **No card-level replacement-confirmation checkbox.** A freshly-created session has nothing to replace, so the "Yes, replace existing reviewers, reviewees or settings…" tick is omitted. The body wrapper still exists; only the checkbox is suppressed.

**Submission semantics.** The card has no Submit button of its own. Each slot's inputs associate with the create-session form via the HTML `form="create-session-form"` attribute, so the single "Create session" button submits both the session details and any staged Quick Setup uploads in one POST. After `POST /operator/sessions` creates the session, the handler dispatches each provided slot through the same per-slot pipeline the Home consolidated submit-all uses — `_run_quick_setup_import` for Reviewers / Reviewees, `_run_quick_setup_relationships` for Relationships, `_run_quick_setup_observers` for Observers, `_run_quick_setup_settings` for Settings. The routes themselves are thin wrappers over them — see **Per-slot dispatch** above for why that matters. `confirm_replace` is implicitly `"true"` on this path for the roster slots — there's nothing to overwrite, so the route layer's gate is satisfied trivially — and the Settings slot is called with `replacing=False`, which skips its gate for the same reason.

**Two things run after the last slot.** The Create page's Tags box (19S Item 6) and its Owners card (19S Item 9) are not Quick Setup slots — they are separate cards outside this partial — but their writes are ordered by this dispatch. `session_tags.set_tags` runs *after* the Settings slot, which is what makes a typed tag beat the bundle's `session_tags[]` rows; the staged co-owners are written after that. `spec/csv_contracts.md` § *Settings CSV — apply precedence* owns that rule. Every slot, the tag write and the owner writes share the request's one correlation id.

**Failure mode.** Session creation runs first; if it succeeds and a downstream slot fails, the operator lands on Session Home with that slot's `?quick_setup_error=…&quick_setup_reason=…` flag and the slot's banner-error rendered in place. The session row stays — the operator retries the failing slot from the Home Quick Setup card. **A typed tag and a staged owner survive that bail-out**: both writes run on the error redirect too, so the operator sent back to fix a CSV does not also lose what they typed or staged. It is safe on every slot because each returns its failure token *before* any mutation — a slot that failed wrote nothing, and one that never ran cannot have — so the error path is still "after the Settings slot" in the only sense the ordering rule needs.

### Doc taxonomy

The card does not appear in the page taxonomy or the chrome. The chrome (two-row navigation, Home anchor, Setup/Operations rows) is unaffected by this work. The only doc change is in the description of what Home's body contains; the page list, the nav model, and the principles (P1–P4) are unchanged.

### Implementation pointers

- Reuse the existing per-entity CSV parsing and validation modules. The card is a UI affordance over the same import paths the Setup pages already expose.
- Reuse the cascading-clearance logic that the per-entity pages already implement (or should implement) when reviewers/reviewees are replaced — the card should not introduce a parallel cascade implementation.
- The card's locked-state styling is a single `.quick-setup-body.locked` body wrapper, the same in every state that applies it, and includes the H2 title + the card-level confirmation checkbox alongside the slot controls. On top of the greying, a locked card's slot file inputs and confirmation checkbox carry the HTML `disabled` attribute (the `quick_setup_slot` macro takes a `locked` flag; the checkbox keys off `quick_setup.is_locked`) so the controls are genuinely inert, not merely dimmed. The Lock / Unlock toggle renders only while the card is available (Visibility, above); otherwise the differences live in the description copy, not in a separate visual primitive.
- The card-level confirmation checkbox is a plain `<input type="checkbox">` outside any slot form. Inline JS on each form's `submit` event mirrors the checkbox state into a hidden `confirm_replace` input on the form. Server-side `confirm_replace == "true"` gate stays the source of truth — the JS just spares the operator from per-slot bookkeeping.

The intent throughout: Quick Setup is a thin convenience surface over existing import primitives. It should not own meaningful logic of its own.
