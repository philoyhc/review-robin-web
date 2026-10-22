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

The card is **available** while setup is editable — `draft` or `validated`, the single `lifecycle.is_editable` predicate its routes gate on (author's ruling, 2026-10-07) — and the session has no persisted responses (`is_available` in `app/web/views/_quick_setup.py`). There it is **live on load**: there is no Lock / Unlock, and the card-level replacement checkbox gates every replacing submit. Otherwise — any session with responses, `ready`, `expired`, `archived` — the card is **locked** (`is_locked = not is_available`): the body is greyed (`.quick-setup-body.locked`) and its controls disabled; the lifecycle table below gives each state. Per `spec/session_home.md` ("Disabled treatment on Home is plain greying-out, not yellow lock cards"), Home does not stack a yellow lock card on top of the body greying. The card shows no current-state indicators (see **Slots**).

### Slots

The card contains five live slots on both variants — Reviewers, Reviewees, Relationships, Observers, Session settings — whatever the session's `relationships_enabled` / `observers_enabled` toggles say. All five share a "file upload" shape — no rule selectors or other slot-specific input modes. **The card must not gain an Assignments slot.** Assignments are a materialized derivative — the Workflow card's **Prepare session** generates one row per eligible `(reviewer, reviewee, instrument)` triple from each instrument's rule (`spec/assignments.md`) — not a dataset an operator uploads.

**Layout.** A two-column grid hosts the slots. Reviewers + Reviewees stack in the left column; Relationships, Observers and Session settings stack in the right column, in that order. There is no horizontal divider between the slot groups.

**No count indicators.** Each slot's heading is its label and the inline action "Upload a CSV"; it does not show how many rows the session holds. The per-entity Setup pages carry the counts.

**Slot 1 — Reviewers** (left column, top).
- File upload accepting CSV.

**Slot 2 — Reviewees** (left column, bottom).
- Same shape as Reviewers.

**Slot 3 — Relationships** (right column, top).
- File upload accepting a Relationships CSV (`ReviewerEmail`, `RevieweeEmail`, `PairContextTag1..3`, `Status`).
- The CSV's `tag_N` slots flow through to the rule engine via the `pair_context.tag1` / `pair_context.tag2` / `pair_context.tag3` predicate field names; `status` defaults to `active` when omitted.

**Slot 4 — Observers** (right column, middle).
- Same shape as Reviewers, saved through the Observers importer. Renders whatever `observers_enabled` says; an upload that saves rows turns it on (**Turning tabs on**).

**Slot 5 — Session settings** (right column, bottom).
- File upload accepting a session-settings CSV: the three-column `field,value,data_type` form `serialize_session_config` writes (`spec/csv_contracts.md` §3.3; `app/services/session_config_io/`).
- Applies through `apply_session_config(...)`. The two-phase parse + apply contract validates every row first, then wipes and replaces; round-trip stable on the export's own output.

There is **no** per-slot Submit button. The card carries a single bottom Submit (see "Submission semantics" below) that runs every slot whose input is present.

**The per-slot routes exist and no UI calls them** — no template references them. Four of them take the `POST …/quick-setup/{kind}` shape (`reviewers`, `reviewees`, `relationships`, `observers`); the Settings slot's is `POST …/import-config`, outside the `quick-setup` prefix. They stay as backend entry points, exercised by tests; the card reaches the same per-slot pipeline through `submit-all`.

### CSV format

Each CSV's expected schema (column names, required vs. optional fields, encoding) is defined in the existing per-entity import paths (Reviewers, Reviewees, Relationships, Settings). The card reuses the same schemas and the same parsing/validation logic — it does not introduce a new file format. If those schemas are documented elsewhere in the spec, link to them; if not, document them in the same module that handles the existing per-entity uploads.

### Submission semantics

**Single bottom Submit.** The card carries one Submit button at the bottom right, alone in its footer row, `btn secondary`. Clicking Submit posts every slot's input in one form to `POST /operator/sessions/{id}/quick-setup/submit-all`.

**Submit-enable gate.** The Submit button starts `disabled` and enables only when **both** (1) at least one `<input type="file">` on any slot has a file selected AND (2) the card-level confirm-replace checkbox is ticked. Inline JS toggles the `disabled` attribute on both the file inputs' `change` event and the checkbox's `change` event. The checkbox renders only on the existing-session variant; on the new-session variant the create-session button drives submission and this gate doesn't apply.

**Replace semantics.** Each slot replaces the entire corresponding dataset for the session; what a replacement takes with it is `spec/setup_pages.md` § *Deleting the selected rows* ("What a delete takes with it"), which governs every reviewer-delete surface alike. Merge semantics are not supported; per-record edits remain on the per-entity Setup pages. Replacing reviewers or reviewees automatically clears existing assignments and relationships (cascade inside the replacement transaction).

**Replacement confirmation.** A single card-level checkbox sits below the slot grid, inside the `.quick-setup-body` wrapper and just above the footer's Submit:

> ☐ Yes, replace existing reviewers, reviewees or settings, according to what is uploaded. A settings file rebuilds every instrument and deletes its assignments.

Inline JS mirrors the checkbox state into the form's hidden `confirm_replace` input on submit. The route gate stays the source of truth: when any roster slot whose `existing > 0` runs, or the Settings slot runs on an existing session, without `confirm_replace == "true"`, the submit is refused with the `needs_confirm` reason and the slot's banner-error directs the operator at the card-level checkbox (**Result reporting**). Where responses exist, the Reviewers, Reviewees and Settings slots also need `acknowledge_response_loss=true` (Relationships and Observers check the tick only) (`spec/lifecycle.md` §3.2); the card never sends it, because it is locked whenever responses exist, so only a direct POST that bypasses the card can reach that case. A refusal on the missing acknowledgement shows the same `needs_confirm` banner as a missing tick, as the Reviewers and Reviewees slots do. The Relationships slot asks before clearing saved group answers, as the Relationships page's upload card does (findings S1, author's ruling 2026-10-22): a file that would clear any (`spec/assignments.md` "Group-scoped fan-out") is refused whole with the `clears_group_answers` reason and a banner naming the count, unless `acknowledge_response_loss` carries that count. The banner offers no tick, since the card is locked whenever answers exist; it sends the operator to the Relationships page, which asks. The refusal holds no file.

**Per-slot dispatch.** The submit-all handler takes each slot whose input is present, in order: Reviewers → Reviewees → Relationships → Observers → Settings. It **checks every file first, then saves them all in one unit** (`_run_quick_setup`): each slot in order runs its file's own checks, then its replacement gates (the tick, and the response-loss acknowledgement where it applies), and the first slot to refuse is reported (**Result reporting**) with **nothing saved**. Only when every file has passed are they saved, in the same order, inside one `unit_of_work.atomic` and under one correlation id, so the per-entity savers nest and nothing commits until the last slot has saved; a refusal met during the saves — a Settings error only `apply_session_config` finds, or a lifecycle change the savers' lock sees — rolls every slot back and is reported on the slot that met it. The per-slot routes and the create-session POST run the same pipeline, with one file and with the staged files respectively, so it is the **only** save site behind every Quick Setup upload route, which is what makes a fix there reach all of them.

**Turning tabs on.** A submit that saves at least one Observers or Relationships row turns that session's `observers_enabled` / `relationships_enabled` on if it was off — the converse of the lock-on-data invariant (`spec/participant_model.md`), so rows never sit behind a hidden tab. It runs inside the unit after every slot, Settings included, so a settings file saying `false` cannot hide rows the same submit saved, and a refusal leaves the toggles as they were. A header-only file saves no rows and turns nothing on. A submit that turns any on writes one `session.feature_toggled` event carrying every flip, with `reason="quick_setup_upload"`, measured against the toggles as they stood before the submit — so a toggle that a Settings file in the same submit set off and the upload turned back on records nothing (`sessions.turn_on_populated_features`).

**Empty submissions** are clean no-op redirects — submit-all without any input 303s back to Home with no slot fragment.

**Cascading effects.** Replacing reviewers or reviewees automatically clears existing assignments and relationships (they reference reviewer / reviewee IDs); replacing relationships has no cascade beyond its own dataset, except that a pair it moves to another pair-context group clears the group it joins, if that group already had members (`spec/assignments.md` "Group-scoped fan-out"), which the slot asks before doing (above). Replacing **settings** rebuilds every instrument, which deletes the session's assignments and any responses with them. Replacing **reviewers** also clears their invitations, and unlinks — rather than deletes — the `email_outbox` rows that reference them. The cascade happens inside the replacement transaction; the card does not auto-regenerate assignments after a reviewer / reviewee / relationships replacement. Regeneration fires from Session Home's Workflow card stepper, which is where every other lifecycle action starts; the Assignments page carries the same action for an operator already on it.

The single card-level checkbox covers the cascade: its copy (quoted under **Replacement confirmation** above) names the reviewers, reviewees and settings an upload replaces and says outright that a settings file rebuilds every instrument and deletes its assignments; a roster replace's own cascade (assignments, relationships, invitations) it covers implicitly. Per-slot inline cascade banners are not used; the one second question is a Settings file's that deletes instruments it does not name, asked only once the file is in (**Result reporting**). A Relationships file that would clear group answers is refused with the count, and the question is asked on the Relationships page (above).

**Locked state.** The card is locked only when unavailable. The card-level checkbox sits inside `.quick-setup-body`, so it greys along with the H2 title and slot controls when the card is locked. Greying is not the only signal: when the card is locked, the slot file inputs **and** the replacement-confirmation checkbox also carry the HTML `disabled` attribute, so a locked card cannot have a file staged or the box ticked — not merely a greyed-but-live surface.

### Result reporting

The card reports failures only: no success message, and no per-row errors for the roster slots — a roster slot names its file's kinds of problem but never a row. The Settings slot lists its errors with their rows: they are not per-row kinds of problem.

- **Success:** no message. Submit redirects back to Home at the last slot that ran (`#quick-setup-{kind}`).
- **Failure:** Session Home **rendered again at 422** by the route that refused, not a redirect (findings O7, author's ruling): the file's own lines never ride a URL, so no link can put text on the page. The page names Home's own path in the address bar as it loads (`history.replaceState`), so its in-place Unlock / Lock and a reload address Home, not the POST-only route, and it does not run the scheduled-event pass, which the next GET of Home does (`spec/lifecycle.md` §8.3). The banner is a `banner-error` above the slot grid, tied to the failing slot by its `quick-setup-{kind}-error-banner` id and naming its reason as `data-quick-setup-reason`, carrying one short sentence from `_quick_setup_error_message` in `app/web/views/_quick_setup.py`. The New session page is the exception (**New-session variant**, "Failure mode"): it redirects with a fixed code and shows no lines. Session Home's `?quick_setup_error=…&quick_setup_reason=…` reads only that code (`views.quick_setup_url_failure`); any other pair shows nothing, as an unlisted `super_error` does. A roster file that fails to parse or validate reads "Could not import reviewers. The file has these problems:" and lists each kind of problem once, with how many rows have it — "ReviewerEmail is blank (2 rows)", "Status is not active or inactive (1 row)" — or, for a problem with the file itself, its own message ("Missing required column: ReviewerEmail"). The line is the issue's row-free `problem` (`app/schemas/validation.py`), which every row-level issue the roster parsers raise carries; `views.problem_kinds` groups them — the same lines the per-entity Setup pages' upload cards show for the same file — and `views.roster_problem_details` caps them, five at most and then "…and N more.", as the Settings lines. Neither surface lists rows or points at the other: a refused file is never saved, so no page holds its rows. With no lines to list the sentence is "Could not import reviewers." A Settings CSV that fails validation reads "Could not import session settings." and lists its errors under that sentence, one line each (`instruments[1].name: name is required`, with `Row N, ` ahead of it when the error belongs to one row), five at most (fewer when the quoted values make them long) and then "…and N more." — this is how the route surfaces them, which `spec/csv_contracts.md` §3.3 requires. A missing confirmation tick and a lifecycle refusal each have their own sentence.
- **Instruments the Settings file deletes** (findings S4): on an existing session, a valid Settings file that does not bring back every instrument the session holds (`spec/csv_contracts.md` §3.3, phase 2) is refused before anything is saved. The banner reads "Nothing was imported. This settings file deletes 2 instruments it does not name, with their fields:", lists them by label, capped as the other lines are, and offers a tick, "Yes, delete them. Then Submit." ("it" for one), whose value is the count, sent as `acknowledge_instrument_deletion` with the submit-all form. The file is held and the replace box renders ticked (**Held files**, below), so the tick and Submit are the whole answer; a count that no longer matches is refused again, as the group-clear tick is. A file too large to hold reads "Yes, delete them. Choose the file again, then Submit."; the replace box is ticked either way, since the ask is reached only with it ticked. A file that deletes no instrument never asks, and neither does the New session page. Nor does the session's Default instrument while it is still as Create made it (`spec/csv_contracts.md` §3.3): a blank session set up here takes the same files as the New session page, with no question.

A refusal on any slot leaves every slot as it was: no file of the submit is applied, however far down the order the refusal came (**Per-slot dispatch**).

**Held files.** The submit-all route holds every file of a refused submit when the refusal asks a question a tick answers: `needs_confirm` (the replace tick) and `deletes_instruments`. They are held in `held_uploads` under one token, one row per slot.

- **The card.** Each held slot names its file under its input ("Holding `x.csv` from your last Submit…"). The form carries a hidden `held_token`, and Submit counts a held slot as a chosen file.
- **The next submit.** It takes the held file for any slot left empty; a newly chosen one wins.
- **The replace box.** It renders ticked after the deletion ask, which was reached with it ticked. After a missing-tick ask it renders unticked.
- **A lapsed hold.** A submit naming a hold that has lapsed saves nothing, newly chosen files included. Home renders at 422 with a banner above the slots: "Nothing was saved. The files held from your last Submit have expired; choose them again."
- **Ending the hold.** A save ends it, and so does any other refusal. So does the banner's Dismiss, which is then a submit of the card's form to `POST …/quick-setup/dismiss`; that route deletes the hold and lands on `#quick-setup`. A banner with nothing held keeps the in-place Dismiss above.
- **Not covered.** The per-slot routes, which nothing in the UI posts to, and the New session page, which never asks, hold nothing.
- **Scope and lifetime.** A hold belongs to one operator and one session, lapses after an hour, and skips a file over 1 MiB (`docs/backup_restore.md` § *Import files*).

### Validation scope

The card validates each file individually for parse correctness and per-file integrity (unique IDs, required fields, well-formed values). Beyond that it performs **one** cross-roster check, the one the write paths perform everywhere else, rejecting a row whose email another roster holds under a different name (`spec/csv_contracts.md` §3.1). Files uploaded together are checked against **each other** and against the existing rosters they do **not** replace (`check_incoming_identity`; a single file is `check_cross_table_identity`'s case), so a rename made in every roster file at once goes through; a clash between two uploads reads "ReviewerEmail is used under a different name in the uploaded Reviewees file". A Relationships file's emails must be on an uploaded roster file where one is attached, and on the current roster otherwise. Everything else is left to the Validate page — whether assignments correctly reference existing reviewers and reviewees, for example, is its job and is surfaced via the lifecycle-transition action on Home.

### Interaction with per-entity Setup pages

The Quick Setup card and the per-entity Setup pages (Reviewers, Reviewees, Relationships, Observers) are independent. After using Quick Setup, the operator can navigate to any per-entity page and edit individual records normally. The per-entity pages' upload affordances remain functional and behave identically to a card slot given one file — they share the same parsing, validation, and replacement semantics. Only the card takes several files at once, so only it checks files against each other and Relationships against an uploaded roster file. Settings has no dedicated Setup page; the Quick Setup Slot 5 + the Settings extract download on the Extract Setup card (on the Extract data Operations tab) are the round-trip pair.

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
| `draft` | None | **Available.** Fully interactive on load; no Lock / Unlock. |
| `draft` | Any | **Unavailable.** Body greyed via `.quick-setup-body.locked`, controls disabled. Operator routes to per-entity Setup pages (which have the response-loss-acknowledgment flow) for any further changes. |
| `validated` | None | **Available.** Same as `draft` with none; an import demotes the session to `draft`, as every roster and settings import does. |
| `validated` | Any | **Unavailable.** Same treatment as `draft` with responses. |
| `ready` | (any) | **Unavailable.** Same treatment. |
| `expired` | (any) | Same as `ready`. |
| `archived` | (any) | Same as `ready`. |

The description copy explains the rule from the operator's vantage point. It has two variants: the default ("Available only while setup is editable (draft or validated) and the session has no responses.") and a responses-specific one shown when the session holds responses — typically a session activated then reverted to draft, which keeps its responses and so lands `draft`-but-locked. The responses variant names the reason ("Quick Setup is locked because this session already holds reviewer responses from a prior activation.") and points the operator at the per-entity Setup pages. Both gates otherwise show up as the same visual signal (greyed body with disabled controls). Defense-in-depth gates stay in place in the pipeline — it checks `lifecycle.is_editable` before reading any file and refuses with the `lifecycle` reason, and the Reviewers, Reviewees and Settings slots call `_require_response_loss_ack` — but never fire from this surface because the submit forms aren't reachable when the body's locked.

### New-session variant (`/operator/sessions/new`)

The Quick Setup card also renders on the create-new-session page, below the Session details form. The variant has three differences from the Home version:

- **Title.** "Quick setup (optional)" — flags that the operator can fill it in alongside the session details, but doesn't have to.
- **No footer.** The card is always live, and the footer row that holds Submit on Home doesn't render: Create session submits the uploads.
- **No card-level replacement-confirmation checkbox.** A freshly-created session has nothing to replace, so the "Yes, replace existing reviewers, reviewees or settings…" tick is omitted. The body wrapper still exists; only the checkbox is suppressed.

Its slots are Home's five. The form's Relationships and Observers boxes need not be ticked for those slots: an upload is saved either way and turns its tab on (**Turning tabs on**, above).

**Submission semantics.** The card has no Submit button of its own. Each slot's inputs associate with the create-session form via the HTML `form="create-session-form"` attribute, so the single "Create session" button submits both the session details and any staged Quick Setup uploads in one POST. After `POST /operator/sessions` creates the session, the handler runs the provided slots through the same pipeline the Home submit-all uses (`_run_quick_setup`; see **Per-slot dispatch** above for why that matters). `confirm_replace` is implicitly `"true"` on this path for the roster slots — there's nothing to overwrite, so the route layer's gate is satisfied trivially — and the Settings slot is called with `replacing=False`, which skips its gate for the same reason. When every staged file applies, Create lands at the top of Session Home, with no slot fragment: the new session as a whole, not the last slot that ran (Home's own Submit keeps its slot landing, above). With nothing staged it opens the details card for editing (`?editing=1`, no fragment); a refusal follows **Failure mode** below.

**Two things run after the last slot.** The Create page's Tags box and its Owners card are not Quick Setup slots — they are separate cards outside this partial — but their writes are ordered by this dispatch. `session_tags.set_tags` runs *after* the Settings slot, which is what makes a typed tag beat the bundle's `session_tags[]` rows; the staged co-owners are written after that. `spec/csv_contracts.md` § *Settings CSV — apply precedence* owns that rule. Every slot, the tag write and the owner writes share the request's one correlation id.

**Failure mode.** Session creation runs first and commits; if it succeeds and a staged file is refused, the operator lands on Session Home with that slot's `?quick_setup_error={kind}&quick_setup_reason=refused` code (no slot fragment; Home's banner script scrolls to the shown banner on load) and the slot's banner-error rendered in place, reading "The reviewers file was refused, so none of the files uploaded with the new session were saved. Upload them again in Quick Setup to see why." It stays a 303, not the existing session's 422 re-render, because rendering Home at the create's URL would replay the create on a refresh; so the file's lines are not shown, and no URL carries them (findings O7). The session row stays, deliberately, and **none** of the staged files is saved — the operator retries from the Home Quick Setup card. **A typed tag and a staged owner survive that bail-out**: both writes run on the error redirect too, so the operator sent back to fix a CSV does not also lose what they typed or staged. It is safe because a refused upload saved nothing, the Settings file included, so the error path is still "after the Settings slot" in the only sense the ordering rule needs.

### Doc taxonomy

The card does not appear in the page taxonomy or the chrome (two-row navigation, Home anchor, Setup/Operations rows); it is part of Home's body only.

### Implementation pointers

- Reuse the existing per-entity CSV parsing and validation modules. The card is a UI affordance over the same import paths the Setup pages already expose.
- Reuse the cascading-clearance logic that the per-entity pages implement when reviewers/reviewees are replaced — the card should not introduce a parallel cascade implementation.
- The card's locked-state styling is a single `.quick-setup-body.locked` body wrapper, the same in every state that applies it, and includes the H2 title + the card-level confirmation checkbox alongside the slot controls. On top of the greying, a locked card's slot file inputs and confirmation checkbox carry the HTML `disabled` attribute (the `quick_setup_slot` macro takes a `locked` flag; the checkbox keys off `quick_setup.is_locked`) so the controls are genuinely inert, not merely dimmed. The states otherwise differ only in the description copy, not in a separate visual primitive.
- The card-level confirmation checkbox is a plain `<input type="checkbox">` outside any slot form. Inline JS on each form's `submit` event mirrors the checkbox state into a hidden `confirm_replace` input on the form. Server-side `confirm_replace == "true"` gate stays the source of truth — the JS just spares the operator from per-slot bookkeeping.

The intent throughout: Quick Setup is a thin convenience surface over existing import primitives. It should not own meaningful logic of its own.
