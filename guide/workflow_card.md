# Workflow card — behavior on the Assignments page

This note documents the actual current behavior of the "Workflow"
card (formerly titled "Next Action"; the template + CSS class names
still use the ``next_action`` prefix) as rendered on the Assignments
page
(`/operator/sessions/{session_id}/assignments`), derived directly from
the code:

- Template: `app/web/templates/operator/partials/next_action_card.html`
- Route + context wiring: `app/web/routes_operator/_assignments.py`
  (`assignments_hub` and `_render_assignments_hub`)
- Lifecycle service: `app/services/session_lifecycle.py`
- Lifecycle POST handlers: `app/web/routes_operator/_session_home.py`
  (`session_activate`, `session_revert_to_draft`)

The same partial renders on Session Home and on every Operations-row
page. The only thing the Assignments page does differently is set
`next_action_return_to = "assignments"` so that the Validate setup
link, the Start session / Revert forms, and the warnings-detour
Start session link all land back on Assignments instead of Session
Home.

## Inputs the card reads

`_render_assignments_hub` passes these context keys to the partial:

- `session` — `ReviewSession` ORM object.
- `is_draft`, `is_validated`, `is_ready` — booleans from
  `lifecycle.is_draft / is_validated / is_ready`.
- `is_setup_empty` — `True` iff session is in draft AND any of:
  reviewer count is 0, reviewee count is 0, or at least one
  instrument has no assignment rule pinned (checked via
  `instruments.has_unpinned`, which also returns `True` when the
  session has zero instruments).
- `is_pre_generate` — `True` iff session is in draft, `is_setup_empty`
  is `False`, AND either no `Assignment` rows exist yet OR the most
  recent revert (`session.invalidated` or `session.reverted_to_draft`)
  is newer than the most recent `assignments.generated` event
  (`lifecycle.needs_regeneration_after_revert`). Surfaces the
  Generate prompt before the operator can validate, including after
  a Revert / Pause that returns the session to draft.
- `invitations_generated` — `True` iff at least one `Invitation` row
  exists for the session (`invitations.has_invitations`). Splits
  the ready phase into State 6 (not yet generated) vs States 7 / 8.
- `invitations_sent` — `True` iff at least one `Invitation` row has
  a non-NULL `sent_at` (`invitations.has_sent_invitations`). Splits
  States 7 (none sent yet) vs 8 (some / all sent).
- `validation_summary` — `dict | None`. Populated whenever the page
  was reached with `?validated=1` OR the session is already
  `validated`. Keys:
  - `error_count`, `warning_count`, `info_count` — from the readiness
    report.
  - `can_activate` — `report.can_activate AND is_validated(session)`.
  - `needs_acknowledge` — `report.has_non_blocking_findings`.
- `next_action_return_to` — hard-coded `"assignments"` on this page.

`?validated=1` (the Validate setup link target) makes
`assignments_hub` run `validate_session_setup` live; if the report is
clean and the session is still in draft, it calls
`lifecycle.mark_validated`, promoting `draft → validated` before the
page renders.

## States

The card has a constant frame (H2 "Workflow" + blue-bordered card).
The body and the bottom button row are chosen by this cascade in
`next_action_card.html`:

```
if is_setup_empty:        → State 1
elif is_pre_generate:     → State 1A
elif is_draft:
    if validation_summary: → State 3
    else:                  → State 2
elif is_validated:
    if can_activate:
        if needs_acknowledge: → State 4B
        else:                 → State 4A
    else:                  → State 5
elif is_ready:
    if not invitations_generated: → State 6
    elif not invitations_sent:    → State 7
    else:                         → State 8
```

### Per-state body copy

| State | Trigger | Body |
| --- | --- | --- |
| **1** | `is_setup_empty` | *"Session not fully set up. Make sure that reviewers, reviewees, and relationships (optional), and instruments have been set up before continuing."* |
| **1A** | `is_pre_generate` | *"Run generation to create the assignment pairs (note that doing so will replace any previously generated assignment pairs)."* |
| **2** | `is_draft`, no summary | *"Run validation to surface errors and warnings before activating. Validation never mutates session data."* |
| **3** | `is_draft` + `validation_summary` | *"Validation didn't pass."* + error / warning / info pill row + *"Resolve the errors and re-run validation before activating."* |
| **4A** | `is_validated` + `can_activate` + not `needs_acknowledge` | *"The session setup data has successfully validated. Preview the reviewer surface to make sure that it conforms to your requirements before activating."* |
| **4B** | `is_validated` + `can_activate` + `needs_acknowledge` | Same as 4A plus help-line: *"{N} warning(s) — review on Validate before activating."* |
| **5** | `is_validated`, not `can_activate` | *"Validation shows that there are error(s). Resolve them and re-run validation before activating."* |
| **6** | `is_ready`, no Invitation rows yet | *"Session is currently activated. Reviewers can access forms and save responses. Don't forget to generate and send out emails to notify the reviewers."* |
| **7** | `is_ready`, Invitation rows exist, none `sent_at` | *"Session is currently activated. Reviewers can access forms and save responses. Don't forget to send out emails to notify the reviewers."* |
| **8** | `is_ready`, at least one Invitation with `sent_at` | *"Session is currently activated. Reviewers can access forms and save responses. You may remind reviewers if needed."* |

## Workflow stepper — uniform 7-button row

Every state renders the same seven-stage bottom row, in the same
order — Revert to draft sits leftmost, then the forward stages in
their workflow order:

```
Revert to draft · Generate assignments · Validate setup · Start session · Generate invites · Send invites · Send reminders
```

Each slot is either **live** (Primary or Secondary, clickable) or
**inert** (`<button disabled aria-disabled="true">`, rendered in the
Secondary style for visual consistency).

The matrix below shows what each slot does per state. `Pri` = Primary
live, `Sec` = Secondary live, `—` = inert preview / past stage.
Revert to draft is rendered in Secondary style whenever it's live —
the stepper never promotes it to Primary.

| Slot | 1 | 1A | 2 | 3 | 4A | 4B | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Revert to draft | — | — | — | — | Sec | Sec | Sec | Sec | Sec | Sec |
| Generate assignments | — | **Pri** | Sec | Sec | Sec | Sec | — | — | — | — |
| Validate setup | — | — | **Pri** | **Pri** | — | — | — | — | — | — |
| Start session | — | — | — | — | **Pri** | **Pri** | — | — | — | — |
| Generate invites | — | — | — | — | — | — | — | **Pri** | Sec | Sec |
| Send invites | — | — | — | — | — | — | — | — | **Pri** | Sec |
| Send reminders | — | — | — | — | — | — | — | — | — | **Pri** |

Notes:
- **Generate assignments** posts to
  `/operator/sessions/{id}/assignments/generate` via the
  `next-action-generate-form` hidden form. The form ships hidden
  `confirm_replace=true` + `acknowledge_response_loss=true`, so
  clicking Generate fires without surfacing the route's confirm
  dialogs (the operator's acknowledgment lives in the button
  label). The form is emitted only in states where Generate is
  live (1A / 2 / 3 / 4A / 4B); other states render the inert
  preview.
- **Validate setup** is an `<a>` whose `href` is
  `/operator/sessions/{id}/{return_to}?validated=1` (or
  `/?validated=1` off the Assignments page). Re-entering the page
  with `?validated=1` runs `validate_session_setup` live and, when
  clean, calls `lifecycle.mark_validated` to promote `draft →
  validated` before render.
- **Start session** in State 4A is a `<button type="submit">` posting
  to `/operator/sessions/{id}/activate` via `next-action-activate-form`
  (carries hidden `return_to` when set). In State 4B (warnings
  present) it's instead an `<a>` to
  `/operator/sessions/{id}/validate?activate=1&return_to=...`, routing
  the operator through the Validate page to acknowledge warnings
  inline before the `/activate` POST fires from that page's banner.
- **Generate invites** posts to
  `/operator/sessions/{id}/invitations/generate` via
  `next-action-generate-invites-form`. Calls
  `invitations.generate_invitations`, which idempotently creates one
  `Invitation` row per assigned active reviewer (skipping reviewers
  with no `include=True` assignment and reviewers already invited).
- **Send invites** posts to
  `/operator/sessions/{id}/invitations/send-all` via
  `next-action-send-invites-form`. The route iterates every pending
  invitation and dispatches via `invitations.send_invitation`.
- **Send reminders** posts to
  `/operator/sessions/{id}/invitations/remind-incomplete` via
  `next-action-send-reminders-form`. Calls
  `invitations.send_reminders_to_incomplete` for reviewers whose
  assignments aren't complete.
- All three invitation forms emit on every ready state (6 / 7 / 8)
  so the Secondary "re-run an earlier stage" buttons stay wired;
  only the corresponding Primary slot's live state changes. Each
  form carries a hidden `return_to=<page>` field so the post-action
  303 lands back on the page that rendered the card. The value is
  `assignments` on the Assignments page, `home` on Session Home
  (resolved server-side to `/operator/sessions/{id}`), or one of
  the other operations-row slugs (`reviewers` / `reviewees` /
  `instruments`) if a future page adopts the card. Direct form
  posts elsewhere (e.g. the standalone Invitations page) omit
  `return_to` and the route falls back to its historical default
  of `/operator/sessions/{id}/invitations`.
- **Revert to draft**:
  - States 4A / 4B / 5 (validated): Secondary submit via
    `next-action-revert-form` to `/operator/sessions/{id}/revert`.
    Route dispatches to `lifecycle.invalidate_session` (validated →
    draft, audit `session.invalidated`).
  - States 6 / 7 / 8 (ready): Secondary submit via
    `next-action-pause-form` to the same `/revert` endpoint with
    hidden `confirm=true`. Route dispatches to
    `lifecycle.revert_session_to_draft` (ready → draft, audit
    `session.reverted_to_draft`; instruments flip
    `accepting_responses = False`; responses preserved).

## Things that retired with the workflow-stepper refresh

- Standalone "Generate assignments" card on the Assignments page
  (`<section id="assignments-generate-card">`), including its
  pre-Generate "pin rules first" disabled nudge, inline
  `confirm_replace` checkbox, and "Pairs may be stale" badge. The
  per-instrument status blocks below it still render eligible /
  generated counts.
- Yellow `.card.lock` "Assignments cannot be modified while the
  session is ongoing" notice on the Assignments page (when
  `is_ready`).
- Inline "See validation details" / "See previews" / "Pause Session"
  buttons inside the Next Action card body. The Validate and Previews
  pages remain reachable via the chrome top-nav.

## Quick reference: what each POST route does

| Route | Service entry | Allowed prior state | Resulting state | Audit event | Required form field |
| --- | --- | --- | --- | --- | --- |
| `POST /operator/sessions/{id}/assignments/generate` | `assignments.replace_assignments` | `draft` or `validated` (`is_editable`) | unchanged | `assignments.generated` | `confirm_replace=true` (when count > 0) and `acknowledge_response_loss=true` (when responses exist) — both pre-set in the workflow form |
| `POST /operator/sessions/{id}/activate` | `lifecycle.activate_session` | `validated` | `ready` | `session.activated` | `acknowledge_warnings=true` iff report has non-blocking findings |
| `POST /operator/sessions/{id}/revert` (when `is_validated`) | `lifecycle.invalidate_session` (reason `operator_revert`) | `validated` | `draft` | `session.invalidated` | — |
| `POST /operator/sessions/{id}/revert` (when `is_ready`) | `lifecycle.revert_session_to_draft` | `ready` | `draft` | `session.reverted_to_draft` | `confirm=true` |

All `/activate` and `/revert` routes honour the form field `return_to`
against the allowlist `{"reviewers", "reviewees", "assignments",
"instruments"}` and 303 to the corresponding child page; on the
Assignments page that field is always `"assignments"`.

## Appendix A: combining Generate + Validate + Start session into a single "Run setup" super-button

This appendix sketches what it would take to fuse the first three
live forward stages of the stepper into one **Run setup** button that
runs all three actions in sequence, stops at the first failure, and
surfaces the underlying error message in the card's new right column.
Per-failure end states are spelled out in A.2; the natural answer is
State 3 for a Validate-failure (so the pill counts surface the
diagnostic) and a rolled-back State 1A for an Activate-failure.

Decisions baked in (settled with the spec author):

- **The super-button replaces the three individual stage buttons**
  rather than sitting alongside them. The stepper drops from seven
  slots to five.
- **The card adopts a two-column inner layout.** Left column carries
  the existing body + stepper row; right column carries lifecycle
  status reports, validation summaries, and super-button error
  messages. The reduced stepper width makes the split fit.
- **Warnings keep their inline detour** through
  `/validate?activate=1` rather than auto-acknowledging on
  super-button click. Operators see warnings before they fire.
- **Audit events:** new `session.workflow_run_started` and
  `session.workflow_run_failed` envelope rows distinguish
  super-button invocations from their individual per-step audit
  trail.

### A.1 What the three steps look like today

| Step | Route | Service | Commits its own transaction | Documented failure modes |
| --- | --- | --- | --- | --- |
| **Generate assignments** | `POST /operator/sessions/{id}/assignments/generate` (`_assignments.py:267`) | `assignments.replace_assignments` (`app/services/assignments.py:588`) | Yes — flushes / commits per instrument and writes one `assignments.generated` audit event per processed instrument. | `_require_editable` raises 409 if session is `ready`. `ValueError` if a specific instrument is unpinned (workflow card form scopes to all instruments, so this path is unreachable). Silent no-op `(0, 0)` if zero instruments have pinned rules. |
| **Validate setup** | `GET /operator/sessions/{id}/{return_to}?validated=1` (`_assignments.py:52`, `_session_home.py:92`) — note this is a GET, not a POST | `validation.validate_session_setup` (read-only) → `lifecycle.build_readiness_report` → `lifecycle.mark_validated` (`session_lifecycle.py:108`) — the last only fires when `report.can_activate`. | `mark_validated` commits when it flips draft → validated. No commit otherwise. | `mark_validated` raises `LifecycleError(code="not_draft")` if session isn't already in `draft`/`validated`, and `LifecycleError(code="has_errors")` if errors slipped past the caller's gate. The route catches neither today — it relies on `report.can_activate` to gate the call. |
| **Start session** | `POST /operator/sessions/{id}/activate` (`_session_home.py:311`) | `lifecycle.activate_session` (`session_lifecycle.py:224`) | Yes — flips `validated → ready`, opens every instrument, writes `session.activated`. | `LifecycleError(code="not_validated")` if state precondition is wrong; `LifecycleError(code="has_errors")` if the readiness report has errors; `LifecycleError(code="needs_acknowledge")` if the report has non-blocking findings and `acknowledge_warnings` wasn't passed. The route maps these to 4xx via `_lifecycle_error_response`. |

### A.2 Failure-mode handling

The super-button runs the three steps sequentially, catches
exceptions / failure-summary signals at each step, and lets the
session settle into whichever state the per-failure handling
specifies:

- **Generate raises** → no rollback. Session was `draft`, still is.
  Whatever state the card was in pre-click (typically 1A) is what
  it falls back to.
- **Validate finds errors** → no rollback. The fresh assignments
  stay; `validation_summary` is populated; the card renders State
  **3** with the pill row + per-issue list in the right column.
- **Activate raises** → roll back via
  `lifecycle.invalidate_session(reason="workflow_run_rollback")`.
  The audit event it writes (`session.invalidated`) is already in
  the `revert_events` set checked by
  `needs_regeneration_after_revert`, so the predicate trips and the
  card lands in State **1A** on the next render.

We considered atomic single-transaction wrapping — cleanest
semantic, but requires service-API changes across three services
plus their existing callers, plus batching the per-instrument
`assignments.generated` audit trail. Not worth the churn for a UX
shortcut. We also considered a dedicated
`workflow_pending_retry` column / event for state resolution; the
existing `session.invalidated` event on the Activate-rollback path
already gives us what we need, so we don't co-opt the audit log
into new state-machine plumbing.

### A.3 The chosen stepper layout — five buttons

The three forward stages collapse into one **Run setup** button.
The stepper grows from seven slots to five:

```
Revert to draft · Run setup · Generate invites · Send invites · Send reminders
```

Per-state matrix (`Pri` = Primary live, `Sec` = Secondary live, `—`
= inert preview / past stage):

| Slot | 1 | 1A | 2 | 3 | 4A | 4B | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Revert to draft | — | — | — | — | Sec | Sec | Sec | Sec | Sec | Sec |
| Run setup | — | **Pri** | **Pri** | **Pri** | **Pri** | **Pri** | — | — | — | — |
| Generate invites | — | — | — | — | — | — | — | **Pri** | Sec | Sec |
| Send invites | — | — | — | — | — | — | — | — | **Pri** | Sec |
| Send reminders | — | — | — | — | — | — | — | — | — | **Pri** |

Notes:
- Run setup is the single Primary across the entire setup phase
  (States 1A / 2 / 3 / 4A / 4B). The route always runs Generate +
  Validate + Activate in sequence; the operator doesn't have to
  reason about which step is next. Re-Generate is idempotent for a
  session without responses; for a session with responses, the
  hidden `acknowledge_response_loss=true` field on the form lets
  the chain proceed (matching the existing single-button Generate
  behaviour).
- State 4B (warnings present) routes Run setup through the
  `/validate?activate=1` detour same as today's Start-session
  button — Run setup renders as an `<a>` link rather than a submit
  button in this state, with `return_to` carried through so the
  operator lands back on the workflow card after acknowledging.
- State 5 (errors block activation): Run setup inert. Revert is
  the only live forward path.
- States 6 / 7 / 8: Run setup inert (the session is already
  running). The three invitation buttons take over.

### A.4 Two-column card layout

The card grows a right column dedicated to status reports / error
messages so the left column's body + stepper row no longer have to
carry both the prose and the diagnostic detail. The reduced
five-button stepper width makes the split fit.

```
┌── .card.workflow (was .card.next-action) ────────────────────┐
│ <h2>Workflow</h2>                                            │
│ ┌─ left column ──────────────┐ ┌─ right column ────────────┐ │
│ │ <p>State-specific body</p> │ │ <h3>Status / errors</h3>  │ │
│ │ <div .workflow-buttons>    │ │ <state-specific content>  │ │
│ │   Revert · Run setup …     │ │                           │ │
│ │ </div>                     │ │                           │ │
│ └────────────────────────────┘ └───────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

Right-column content by state (proposed):

| State | Right column content |
| --- | --- |
| 1 (setup empty) | Setup-completion checklist — reviewers ✓/✗, reviewees ✓/✗, all instruments pinned ✓/✗. Deep links to the relevant Operations-row pages. |
| 1A | "Ready to run setup." (optional summary of assignment-row counts pinned per instrument, mirroring the per-instrument status blocks below the card on the Assignments page.) |
| 2 | Empty / minimal — assignment-row counts. |
| 3 | The pill row (`pill-error` / `pill-empty` / `pill-count`) + the per-issue summary list (each issue's `summary` text + `fix_url` deep link). Moves out of the left-column body. |
| 4A | "Setup validated." status line. Optionally a one-line summary of how many warnings / info findings were dismissed. |
| 4B | Same as 4A + the warning details inline (so the operator sees what they're about to acknowledge before clicking the detour). |
| 5 | Error-issue summary list (same shape as State 3). |
| 6 / 7 / 8 | Invitation status counts — reviewers invited / sent / opened / completed (Phase 2 candidate; not blocking the super-button work). |

On super-button failure, the right column also renders a
`banner-error`-styled block with the captured error message(s) at
the top, above whatever state-specific content was going to render.
A small `<p class="form-help">` below the banner names the step that
failed ("Failed at step 2 of 3: Validate setup") so the operator
knows where to look.

Stepper-only states (no card-wide redesign needed elsewhere): the
existing layouts on other operator pages that use the
`.bottom-grid` two-column shell continue to work — the card itself
becomes a wider single-card sub-grid rather than a row in the outer
grid. Session Home's `.bottom-grid` already gives the card the full
left column; on the Assignments page the card is full-width above
the pair table, so it naturally has room for the inner split.

### A.5 Implementation tasks

1. **New route.** `POST /operator/sessions/{id}/workflow/run-setup`
   in either `_session_home.py` or a new `_workflow.py` slice under
   `routes_operator/`. Form fields: `return_to` (same allowlist as
   the existing actions). No `acknowledge_warnings` — warnings still
   detour through the Validate page in State 4B.
2. **Route body.** Sequential best-effort run with structured
   per-step error capture:

   ```python
   step = None
   try:
       step = "generate"
       if not lifecycle.is_editable(review_session):
           raise _StepFailed("Session can't be edited from its current state.")
       assignments.replace_assignments(db, ...)

       step = "validate"
       issues = validation.validate_session_setup(db, review_session)
       report = lifecycle.build_readiness_report(issues)
       if not report.can_activate:
           # Stays in draft; State 3 surfaces the pills + right-column issue list.
           return _redirect(review_session, return_to, run_status="validation_failed")
       lifecycle.mark_validated(db, ..., report=report)

       step = "activate"
       if report.has_non_blocking_findings:
           # Warnings: redirect to the Validate page's activate-ack flow.
           return _redirect_to_warnings_detour(review_session, return_to)
       lifecycle.activate_session(
           db, ..., report=report, acknowledge_warnings=False,
       )
   except (_StepFailed, lifecycle.LifecycleError, ValueError) as exc:
       # If we got past Validate, the session is now `validated` — roll
       # it back so the card resolves to State 1A on the next render.
       if step == "activate" and lifecycle.is_validated(review_session):
           lifecycle.invalidate_session(
               db, ..., reason="workflow_run_rollback",
           )
       _audit_workflow_run_failed(db, review_session, step, exc)
       return _redirect(
           review_session,
           return_to,
           run_status="failed",
           run_step=step,
           run_error=str(exc),
       )
   ```

3. **Error display.** Right-column banner driven by query params on
   the redirect target — `?run_status=failed&run_step=...&run_error=...`
   — or by session-scoped cookies if the URL gets unwieldy. The
   `_render_*_hub` builders read these and pass `run_failure` (a
   small dict) into the partial. Pattern matches the existing
   `quick_setup_error` / `quick_setup_reason` flow on Session Home
   (`_session_home.py:86`).
4. **New audit events.** Register
   `session.workflow_run_started` and `session.workflow_run_failed`
   in `EVENT_SCHEMAS` (`app/services/audit.py`). Payload envelope:
   `context` carrying `step` (`generate` / `validate` / `activate`)
   and `error_code` / `error_message`. Successful end-to-end runs
   write `workflow_run_started` + the existing per-step events; we
   don't need a `workflow_run_succeeded` since the trio of step
   events already documents success.
5. **Card template restructure.** Split `next_action_card.html`
   into a two-column layout. Left column keeps the existing body +
   `.next-action-buttons` row, trimmed to five buttons (Revert ·
   Run setup · Generate invites · Send invites · Send reminders).
   Right column is a new `.next-action-status` div with
   state-conditional content from the table in A.4. CSS goes in
   `base.html` next to the existing `.card.next-action` rules
   (display: grid; grid-template-columns: minmax(0, 1fr) minmax(0,
   1fr); gap: var(--space-4)). On narrow viewports the columns
   collapse to a stack.
6. **Move State 3 pills into the right column.** Today they live in
   the body block at `next_action_card.html:64-73`. They become the
   default right-column content for State 3 (and State 5, with the
   same shape but error-only pills). The left-column body keeps
   the prose intro ("Validation didn't pass.") + the wrap-up
   ("Resolve the errors and re-run validation before activating.").
7. **Retire the three forms in the partial.** `next-action-generate-form`,
   `next-action-activate-form`, and the warnings-detour `<a>`
   collapse into one `next-action-run-setup-form` (or, for the
   detour case, a single `<a>` whose `href` carries the same
   `return_to=...`). The pause and revert forms stay.
8. **Permission / lifecycle gate.** The route rejects when:
   - Session is `ready` → 4xx with "Session is already running."
     (Run setup is inert in States 6 / 7 / 8 anyway; this is the
     defensive gate.)
   - `is_setup_empty` is True → 4xx with "Fill rosters and pin
     instrument rules first." (Run setup is inert in State 1, but
     a stale form post could still arrive.)
9. **Stay-on-page redirect.** Same `return_to` allowlist as the
   other workflow-card actions; honour `assignments` / `home` /
   `reviewers` / `reviewees` / `instruments` plus the
   warnings-detour case where Run setup redirects to
   `/validate?activate=1&return_to=...` so the existing detour UI
   does the acknowledgment.
10. **Retire old routes only after the super-button ships.** The
    individual `POST /assignments/generate` and `POST /activate`
    routes stay live during the transition. Once Run setup is the
    default and tests cover every path, decide whether to retire
    the individual routes or keep them as the lower-level surface
    (the standalone Assignments page may still want them; the
    Validate page certainly wants `/activate`).

### A.6 Tests to add

- End-to-end success from each starting state (1A / 2 / 3 / 4A) →
  session ends `ready`, no warnings, no banners, redirect honours
  `return_to`. Audit log contains the four expected event rows
  (workflow_run_started + assignments.generated + session.validated
  + session.activated) per success.
- Generate step raises → session still `draft`, no fresh
  assignments, right-column banner surfaces the error message.
  Card lands in State 1A or State 1 depending on input state.
- Validate-found-errors → session still `draft`, fresh assignments,
  `validation_summary` populated on next render. Card resolves to
  State 3 (left-column prose, right-column pill row + per-issue
  list). Banner reads "Failed at step 2 of 3: Validate setup. See
  the issues at right."
- Activate raises `LifecycleError(has_errors)` after Validate
  somehow passed (race / re-entrancy) → session is rolled back
  to `draft` via `invalidate_session`; the
  `needs_regeneration_after_revert` predicate trips; card resolves
  to State 1A. Audit log shows workflow_run_started +
  assignments.generated + session.validated + session.invalidated
  + workflow_run_failed.
- Warnings-only → request 303s to the Validate page's
  `?activate=1&return_to=...` detour. From there the operator
  acknowledges and the existing `/activate` flow fires. The chain
  doesn't roll back; the inline ack is the explicit gate.
- Pre-condition: `is_setup_empty` → 4xx, no audit events written.
- Pre-condition: session already `ready` → 4xx with a clear banner
  ("Session is already running.").

### A.7 Decisions resolved

1. **Super-button replaces the three individual buttons.** Stepper
   drops to five slots.
2. **Two-column card layout.** Left = body + stepper row. Right =
   status / errors. CSS via grid; collapses to a stack on narrow
   viewports.
3. **Warnings: keep the existing inline detour** through
   `/validate?activate=1`.
4. **Audit event naming:** `session.workflow_run_started` /
   `session.workflow_run_failed`, with `context.step` and
   `context.error_code` / `context.error_message` carrying the
   diagnostic. Successful runs are documented by the existing
   per-step events; no separate "succeeded" envelope.

### A.8 Suggested rollout

- **PR 0 (shipped 2026-05-14, #967):** retire the Workflow card from
  Session Home so the card and the super-button work only have to
  reason about the Operations-row pages. Template-only on the card
  side. The `session_detail` route handler still computes the
  (now-unused) workflow-card context keys and honours `?validated=1`
  on Home — those test-helper hooks defer to a later cleanup PR.
- **PR 1 (template-only):** restructure the card on the Assignments
  page into two columns with the right column wired up but empty
  (placeholder `<aside>`). Tests confirm the layout renders and the
  existing body / stepper still works.
- **PR 2 (right-column content):** move the State 3 pills and add
  the per-state right-column content from the A.4 table for States
  1 / 1A / 3 / 4A / 4B / 5. State 6 / 7 / 8 right-column status
  (invitation counts) can defer to a follow-up.
- **PR 3 (super-button):** new route, retire the three individual
  buttons in the partial (replace with `Run setup`), wire the
  banner / right-column error rendering. Tests cover every
  failure path.
- **PR 4 (cleanup):** decide whether to retire the now-orphaned
  `/assignments/generate` and `/activate` routes — leave them if
  any other page still posts to them; remove if not. Drop the
  acknowledge-warnings query plumbing if Run setup absorbs that
  path too. Migrate the test helpers that hit
  `/operator/sessions/{id}?validated=1` (deferred from PR 0) to use
  the Assignments URL instead, and strip the Home route's
  `?validated=1` plumbing + unused context keys.

Splitting this way keeps each PR reviewable; the template + content
moves are cosmetic and the route work is the only behaviour change.

