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
Revert to draft · Generate assignments · Validate setup · Start session · Create invites · Send invites · Send reminders
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
| Create invites | — | — | — | — | — | — | — | **Pri** | Sec | Sec |
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
- **Create invites** posts to
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

## Appendix A: collapsing Generate + Validate + Start session into a single "Activate session" super-button

This appendix sketches what it would take to fuse the first three
live forward stages of the stepper into one **Activate session**
button that runs all three actions in sequence, stops at the first
failure, and surfaces the underlying error message in the card's
right column. Per-failure end states are spelled out in A.2; the
natural answer is State 3 for a Validate-failure (so the pill
counts surface the diagnostic) and a rolled-back State 1A for an
Activate-failure.

Decisions baked in (settled with the spec author):

- **Super-button label is "Activate session"** — matches the
  existing chrome status pill ("Activated") and verb form ("Activate
  the session...") in body copy. The earlier candidate "Run setup"
  / "Start session" / "Go live" workshop landed here because it
  keeps the operator's vocabulary consistent end-to-end without
  forcing a chrome / body-copy sweep. PR 3 also rolls back the
  earlier `Activate Session` → `Start session` rename on the
  third-stage button — that label retires with the button anyway,
  but the inert preview labels in States 1 / 1A / 2 / 5 / 6 / 7 /
  8 read as "Activate session" until PR 3 collapses the stepper.
- **The super-button replaces the three individual stage buttons**
  rather than sitting alongside them. The stepper drops from seven
  slots to five.
- **The card adopts a two-column inner layout.** Left column carries
  the existing body + stepper row; right column carries lifecycle
  status reports, validation summaries, and super-button error
  messages. Wired up in PR 1 (#968); right-column per-state
  content filled in PR 2 (#970).
- **The super-button always runs all three steps** (Generate →
  Validate → Activate) regardless of which state the operator
  clicks from. The wasteful re-Generate in State 4A is harmless
  in practice (no responses exist in `draft` / `validated`
  states, so the hidden `acknowledge_response_loss=true` field
  on the form lets the loss-ack pass without UI; the resulting
  assignment rows are identical to the prior generation unless
  inputs changed between clicks). Smart-skip ("only run the
  missing steps") is an optional optimisation for a future PR;
  unconditional re-run keeps the route body simple and the
  semantics predictable.
- **Warnings keep their inline detour** through
  `/validate?activate=1` rather than auto-acknowledging on
  super-button click. Operators see warnings before they fire.
  Specifically: when Validate succeeds and the readiness report
  has non-blocking findings, the super-button route 303s to the
  `/validate?activate=1&return_to=...` URL before calling
  Activate. From the Validate page banner the operator
  acknowledges and the existing `/activate` POST fires.
- **Audit events:** new `session.workflow_run_started` and
  `session.workflow_run_failed` envelope rows distinguish
  super-button invocations from their individual per-step audit
  trail. Successful runs are documented by the existing per-step
  events (`assignments.generated` + `session.validated` +
  `session.activated`) — no separate "succeeded" envelope.
- **Failure messages plumbed through query params on the
  redirect target**, matching the existing
  `quick_setup_error` / `quick_setup_reason` pattern used on
  Session Home. Concretely:
  `?super_status=failed&super_step=<step>&super_error=<urlencoded>`.
  LifecycleError + ValueError messages stay short enough that
  URL-encoded query string is fine.

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

The three forward stages (Generate assignments + Validate setup +
the third stage formerly labeled "Start session") collapse into one
**Activate session** button. The stepper drops from seven slots to
five:

```
Revert to draft · Activate session · Create invites · Send invites · Send reminders
```

Per-state matrix (`Pri` = Primary live, `Sec` = Secondary live, `—`
= inert preview / past stage):

| Slot | 1 | 1A | 2 | 3 | 4A | 4B | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Revert to draft | — | — | — | — | Sec | Sec | Sec | Sec | Sec | Sec |
| Activate session | — | **Pri** | **Pri** | **Pri** | **Pri** | **Pri** | — | — | — | — |
| Create invites | — | — | — | — | — | — | — | **Pri** | Sec | Sec |
| Send invites | — | — | — | — | — | — | — | — | **Pri** | Sec |
| Send reminders | — | — | — | — | — | — | — | — | — | **Pri** |

Notes:
- Activate session is the single Primary across the entire setup
  phase (States 1A / 2 / 3 / 4A / 4B). The route always runs
  Generate + Validate + Activate in sequence; the operator doesn't
  have to reason about which step is next.
- State 4B (warnings present) routes Activate session through the
  `/validate?activate=1` detour same as today's third-stage button
  — the super-button renders as an `<a>` link rather than a submit
  button in this state, with `return_to` carried through so the
  operator lands back on the workflow card after acknowledging.
  The route itself ALSO catches the `needs_acknowledge` case
  programmatically (in case the operator hits the super-button
  POST endpoint directly) and 303s to the same detour URL.
- State 5 (errors block activation): Activate session inert.
  Revert is the only live forward path.
- States 6 / 7 / 8: Activate session inert (the session is
  already activated). The three invitation buttons take over.

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

1. **New route.** `POST /operator/sessions/{id}/workflow/activate`
   in a new `_workflow.py` slice under `routes_operator/` (rather
   than tucking it into the already-busy `_session_home.py` —
   keeps the super-button isolated for the eventual PR 4 cleanup).
   Form fields: `return_to` (same allowlist as the existing
   actions). No `acknowledge_warnings` — warnings still detour
   through the Validate page in State 4B. Pre-flight gates: 409
   if session is already `ready`, 409 if `is_setup_empty` (the
   Operations top-nav Manage links remain the recovery path).
2. **Route body.** Sequential best-effort run with structured
   per-step error capture. Audit-event emission flanks the chain
   (`workflow_run_started` at entry; `workflow_run_failed` in the
   except branch — successful runs are documented by the per-step
   audit events from the underlying service calls):

   ```python
   step = None
   audit_started(db, review_session, user, correlation_id)
   try:
       step = "generate"
       if not lifecycle.is_editable(review_session):
           raise _StepFailed("Session can't be edited from its current state.")
       assignments.replace_assignments(db, ..., correlation_id=correlation_id)

       step = "validate"
       issues = validation.validate_session_setup(db, review_session)
       report = lifecycle.build_readiness_report(issues)
       if not report.can_activate:
           # Stays in draft; State 3 surfaces the pills + right-column issue list.
           # Note: the per-issue diagnostic is already in the right column on
           # the next render via the existing validation_summary plumbing —
           # we don't even need a banner. Audit event still fires for
           # observability ("workflow_run_failed" / step="validate").
           audit_failed(db, review_session, user, step="validate",
                        error_message="Validation reported errors",
                        correlation_id=correlation_id)
           return _redirect(review_session, return_to)
       lifecycle.mark_validated(db, ..., report=report, correlation_id=correlation_id)

       step = "activate"
       if report.has_non_blocking_findings:
           # Warnings: redirect to the Validate page's activate-ack flow.
           # No audit emission here — the operator hasn't failed; they're
           # in the middle of an explicit acknowledgement step.
           return _redirect_to_warnings_detour(review_session, return_to)
       lifecycle.activate_session(
           db, ..., report=report, acknowledge_warnings=False,
           correlation_id=correlation_id,
       )
   except (_StepFailed, lifecycle.LifecycleError, ValueError) as exc:
       # If we got past Validate, the session is now `validated` — roll
       # it back so the card resolves to State 1A on the next render.
       if step == "activate" and lifecycle.is_validated(review_session):
           lifecycle.invalidate_session(
               db, ..., reason="workflow_run_rollback",
               correlation_id=correlation_id,
           )
       audit_failed(db, review_session, user, step=step,
                    error_message=str(exc), correlation_id=correlation_id)
       return _redirect(
           review_session,
           return_to,
           super_status="failed",
           super_step=step,
           super_error=str(exc),
       )
   ```

3. **Error display.** Right-column banner driven by query params on
   the redirect target —
   `?super_status=failed&super_step=<step>&super_error=<urlencoded>`
   — matching the existing `quick_setup_error` / `quick_setup_reason`
   flow on Session Home (`_session_home.py:86`). Concretely:
   - `_render_assignments_hub` picks up the three params and passes
     a small `super_failure` dict (or `None`) into the partial.
   - In the partial, the right column renders a
     `.banner.banner-error` block at the top of the aside when
     `super_failure` is set, with headline "Activate session failed
     at step N of 3: <step name>" + the error message. The
     per-state right-column content (pill row + issue list for
     State 3 / 5, etc.) continues to render below.
   - When the failure path is `super_step=validate` and the session
     is still draft with `validation_summary` populated, the State 3
     pill row + issue list IS the diagnostic — the super-button
     banner serves as the "you clicked this and it didn't work"
     context. No double-rendering needed.
4. **New audit events.** Register
   `session.workflow_run_started` and `session.workflow_run_failed`
   in `EVENT_SCHEMAS` (`app/services/audit.py`). Payload envelopes:
   - `started`: `audit.context(button="activate_session")` or
     similar — minimal, just marks the run.
   - `failed`: `audit.context(step="generate" | "validate" |
     "activate", error_code=..., error_message=...)`.
   Successful end-to-end runs are documented by the per-step events
   (`assignments.generated` + `session.validated` +
   `session.activated`) — no separate `workflow_run_succeeded`
   envelope.
5. **Template restructure.** In `next_action_card.html`:
   - Replace the three independent stage-button slots (Generate
     assignments / Validate setup / the third-stage button currently
     labeled "Start session") with one **Activate session** slot
     in their place. The stepper drops from seven buttons to five.
   - Retire the three forms in the body block:
     `next-action-generate-form`, `next-action-activate-form`,
     and the warnings-detour link helper. Replace with one
     `next-action-activate-session-form` posting to the new
     `/workflow/activate` route, carrying `return_to`. The pause
     and revert forms stay; the three invitation forms stay.
   - State 4B's super-button renders as `<a href="...detour...">`
     instead of a `<button type="submit">` so the operator hits the
     Validate page warnings banner before any POST fires.
6. **Right-column failure banner.** Add a `.banner.banner-error`
   block at the top of the `.next-action-status` aside, rendered
   only when `super_failure` is set. The State 3 / 5 pill rows
   and issue lists already in PR 2 continue to render below.
7. **Stay-on-page redirect.** Same `return_to` allowlist as the
   other workflow-card actions; honour `assignments` / `home` /
   `reviewers` / `reviewees` / `instruments` plus the
   warnings-detour case where the super-button redirects to
   `/validate?activate=1&return_to=...` so the existing detour UI
   does the acknowledgment.
8. **In-PR rename: third-stage button label.** Folded into PR 3
   per the spec author's decision (2026-05-14): the "Start session"
   label introduced in PR #961 reverts to "Activate session"
   alongside the super-button collapse. Once PR 3 ships there's no
   third-stage button anyway, but tests asserting `"Start
   session"` need to flip to `"Activate session"` — the same
   string the new super-button carries.
9. **Retire old routes deferred to PR 4.** The individual
   `POST /assignments/generate` and `POST /activate` routes stay
   live during PR 3 so the Validate page's `?activate=1`
   warnings-banner POST keeps working through the detour. PR 4
   decides which (if any) of those routes still has external
   callers and retires the orphans.

### A.6 Tests to add

- End-to-end success from each starting state (1A / 2 / 3 / 4A) →
  session ends `ready`, no warnings, no banners, redirect honours
  `return_to`. Audit log contains the four expected event rows
  (workflow_run_started + assignments.generated + session.validated
  + session.activated) per success.
- End-to-end success from each starting state (1A / 2 / 3 / 4A) →
  session ends `ready`, no warnings, no banner, redirect honours
  `return_to`. Audit log contains
  `workflow_run_started` + `assignments.generated` +
  `session.validated` + `session.activated` per success.
- Generate step raises → session still `draft`, no fresh
  assignments, right-column banner surfaces the error message.
  Card lands in State 1A or State 1 depending on input state.
  Audit log: `workflow_run_started` + `workflow_run_failed`
  (step=`generate`).
- Validate-found-errors → session still `draft`, fresh assignments,
  `validation_summary` populated on next render. Card resolves to
  State 3 (left-column prose, right-column pill row + per-issue
  list). Banner reads "Activate session failed at step 2 of 3:
  Validate setup. See the issues at right." Audit log:
  `workflow_run_started` + `assignments.generated` +
  `workflow_run_failed` (step=`validate`).
- Activate raises `LifecycleError(has_errors)` after Validate
  somehow passed (race / re-entrancy) → session is rolled back
  to `draft` via `invalidate_session`; the
  `needs_regeneration_after_revert` predicate trips; card resolves
  to State 1A. Audit log: `workflow_run_started` +
  `assignments.generated` + `session.validated` +
  `session.invalidated` + `workflow_run_failed` (step=`activate`).
- Warnings-only → request 303s to the Validate page's
  `?activate=1&return_to=...` detour. From there the operator
  acknowledges and the existing `/activate` flow fires. The chain
  doesn't roll back; the inline ack is the explicit gate. Audit
  log: `workflow_run_started` + `assignments.generated` +
  `session.validated` (no `workflow_run_failed`; the run isn't
  complete yet — it's paused at the operator-acknowledgement
  step).
- Pre-condition: `is_setup_empty` → 4xx, no audit events written.
- Pre-condition: session already `ready` → 4xx with a clear
  banner ("Session is already activated.").
- The State 3 / 5 right-column issue list still renders even
  when the super-button's failure banner sits above it (i.e. the
  banner doesn't suppress the per-state right-column content).
- The third-stage button label rename test (asserting `"Start
  session"` retires) flips to assert the super-button carries
  `"Activate session"`.

### A.7 Decisions resolved

1. **Super-button label is "Activate session".** Matches the
   chrome status pill ("Activated") and the existing verb form in
   body copy. The earlier `"Start session"` rename folds back into
   `"Activate session"` as part of PR 3.
2. **Super-button replaces the three individual buttons.** Stepper
   drops to five slots.
3. **Super-button always runs all three steps** regardless of
   starting state. Smart-skip is a future optimisation.
4. **Two-column card layout.** Left = body + stepper row. Right =
   status / errors. CSS via grid; collapses to a stack on narrow
   viewports.
5. **Warnings: keep the existing inline detour** through
   `/validate?activate=1`.
6. **Failure plumbing via query params** on the redirect target —
   `super_status` / `super_step` / `super_error` — following the
   existing `quick_setup_error` / `quick_setup_reason` pattern.
7. **Audit event naming:** `session.workflow_run_started` /
   `session.workflow_run_failed`, with `context.step` and
   `context.error_message` carrying the diagnostic. Successful
   runs are documented by the existing per-step events; no
   separate "succeeded" envelope.

### A.8 Suggested rollout

- **PR 0 (shipped 2026-05-14, #967):** retire the Workflow card from
  Session Home so the card and the super-button work only have to
  reason about the Operations-row pages. Template-only on the card
  side. The `session_detail` route handler still computes the
  (now-unused) workflow-card context keys and honours `?validated=1`
  on Home — those test-helper hooks defer to a later cleanup PR.
- **PR 1 (shipped 2026-05-14, #968):** restructure the card on the
  Assignments page into two columns with the right column wired up
  but empty (placeholder `<aside>`). Tests confirm the layout
  renders and the existing body / stepper still works.
- **PR 2 (shipped 2026-05-14, #970):** move the State 3 pills into
  the right column and add the per-state right-column content from
  the A.4 table for States 1 / 1A / 3 / 4A / 4B / 5. State 6 / 7 /
  8 right-column status (invitation counts) defers to a follow-up.
  Also adds a vertical divider between the two columns of the card
  (1px border on the left column's right edge; collapses to a
  horizontal rule on the stacked mobile layout).
- **PR 3 (shipped 2026-05-14):** new `POST /workflow/activate`
  route + new `_workflow.py` slice; collapsed the three forward
  stage buttons in the partial (Generate assignments / Validate
  setup / the third-stage button formerly labeled "Start session")
  into one **Activate session** button; wired the right-column
  failure banner via `super_status` / `super_step` / `super_error`
  query params; registered `session.workflow_run_started` /
  `session.workflow_run_failed` audit events; folded the
  `"Start session"` → `"Activate session"` rename into the same
  PR.
- **PR 4 (shipped 2026-05-14):** cleanup pass. Migrated the ~30
  test helpers that hit `/operator/sessions/{id}?validated=1` to
  the equivalent `/operator/sessions/{id}/assignments?validated=1`
  URL (deferred from PR 0), then stripped the Home route's
  `?validated=1` plumbing and the workflow-card-only context keys
  (`is_setup_empty`, `is_pre_generate`, `invitations_generated`,
  `invitations_sent`, `validation_summary`,
  `next_action_generate`, `is_draft`, `is_validated`) plus the
  unused imports (`assignments`, `csv_imports`,
  `instruments_service`, `invitations`) from
  `_session_home.py:session_detail`. The
  `/assignments/generate` and `/activate` routes stay live —
  `/assignments/generate` has no UI consumer but the orphan
  surface is harmless, and `/activate` is load-bearing for the
  Validate-page warnings-detour banner (the super-button itself
  303s to that page in State 4B).
- **PR 5 (shipped 2026-05-14):** extracted the shared workflow-card
  context builder into `app/web/views/_workflow_card.py`. Two
  entry points:
  - `views.build_workflow_card_context(db, review_session, *,
    return_to, validated_just_ran, super_failure, user,
    correlation_id)` returns the 12-key context dict the partial
    expects (lifecycle booleans + state predicates +
    `validation_summary` + `validation_issues_by_severity` +
    `setup_checklist` + invitation flags + `super_failure` +
    `next_action_return_to`). The builder also owns the inline
    `?validated=1` validate-and-promote step that used to live
    in the Assignments route.
  - `views.parse_super_failure(super_status, super_step,
    super_error)` decodes the workflow super-button's redirect
    query-param triple into the `super_failure` dict (or
    `None`).
  `_render_assignments_hub` now calls both helpers and merges the
  returned dict into its template context with `**workflow_ctx`.
  Each PR-6+ page route follows the same one-call pattern.
- **PR 6 (shipped 2026-05-14):** restore the Workflow card to
  Session Home (the card is now Operations-page chrome generally;
  Session Home is no exception). Include the partial full-width
  just below the chrome; call `views.build_workflow_card_context`
  with `return_to="home"`; plumb the `super_status` /
  `super_step` / `super_error` query params. Same PR replaces the
  2×2 page-card grid with two independent flex columns so Extract
  Data sits directly below Quick Setup without row-alignment
  forcing (the user-facing rationale: Danger Zone in the left
  column tends to be taller than the right-column counterpart,
  and forcing row-2 cards to start at `max(left_row2_height,
  right_row2_height)` made Extract Data drift down with a large
  visual gap above it). The retired
  `.bottom-grid > .card-tl/tr/bl/br` placement rules + the
  `extra_card_class` Jinja variable on the two card partials
  retire as cruft.
- **PR 7 (shipped 2026-05-14):** Workflow card on the Validate
  page. New `return_to="validate"` slug added to
  `_REVERT_RETURN_TO` in `_shared.py` (alongside `previews`,
  `invitations`, and `responses`, which the remaining rollout
  PRs will pick up). Route handler in `_operations.py:validate_session`
  now calls `views.build_workflow_card_context` + merges
  `**workflow_ctx` into its template context. The pre-existing
  lifecycle / readiness keys (`is_draft`, `is_validated`, etc.)
  collapse into the builder's output. The Validate-page warnings
  banner (rendered on `?activate=1`) keeps its own template
  block — it's the State 4B detour landing surface and stays
  separate from the workflow stepper.
- **PR 8 (shipped 2026-05-14):** Workflow card on the Previews
  page. Same drop-in pattern PR 7 set up — include the partial,
  add the `super_status` / `super_step` / `super_error` query
  params on the route, call
  `views.build_workflow_card_context(return_to="previews", ...)`,
  merge `**workflow_ctx`.
- **PRs 9 / 10 (planned):** Workflow card on the Invitations and
  Responses pages respectively. Same drop-in pattern.

Splitting this way keeps each PR reviewable; the template + content
moves are cosmetic and the route work is the only behaviour change.

