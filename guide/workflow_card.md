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

This appendix sketches what it would take to fuse the first three live
forward stages of the stepper into one button that runs all three
actions in sequence, stops at the first failure, surfaces a banner
with the underlying error message(s), and leaves the session in a
state that the workflow card resolves to **State 1A** so the operator
can retry by clicking the same button again.

### A.1 What the three steps look like today

| Step | Route | Service | Commits its own transaction | Documented failure modes |
| --- | --- | --- | --- | --- |
| **Generate assignments** | `POST /operator/sessions/{id}/assignments/generate` (`_assignments.py:267`) | `assignments.replace_assignments` (`app/services/assignments.py:588`) | Yes — flushes / commits per instrument and writes one `assignments.generated` audit event per processed instrument. | `_require_editable` raises 409 if session is `ready`. `ValueError` if a specific instrument is unpinned (workflow card form scopes to all instruments, so this path is unreachable). Silent no-op `(0, 0)` if zero instruments have pinned rules. |
| **Validate setup** | `GET /operator/sessions/{id}/{return_to}?validated=1` (`_assignments.py:52`, `_session_home.py:92`) — note this is a GET, not a POST | `validation.validate_session_setup` (read-only) → `lifecycle.build_readiness_report` → `lifecycle.mark_validated` (`session_lifecycle.py:108`) — the last only fires when `report.can_activate`. | `mark_validated` commits when it flips draft → validated. No commit otherwise. | `mark_validated` raises `LifecycleError(code="not_draft")` if session isn't already in `draft`/`validated`, and `LifecycleError(code="has_errors")` if errors slipped past the caller's gate. The route catches neither today — it relies on `report.can_activate` to gate the call. |
| **Start session** | `POST /operator/sessions/{id}/activate` (`_session_home.py:311`) | `lifecycle.activate_session` (`session_lifecycle.py:224`) | Yes — flips `validated → ready`, opens every instrument, writes `session.activated`. | `LifecycleError(code="not_validated")` if state precondition is wrong; `LifecycleError(code="has_errors")` if the readiness report has errors; `LifecycleError(code="needs_acknowledge")` if the report has non-blocking findings and `acknowledge_warnings` wasn't passed. The route maps these to 4xx via `_lifecycle_error_response`. |

### A.2 What "drop back to State 1A" means in terms of session state

State 1A's predicate (`is_pre_generate` in `_session_home.py` /
`_assignments.py`):

```
is_draft AND not is_setup_empty AND (
    assignment_count == 0
    OR lifecycle.needs_regeneration_after_revert(db, session_id)
)
```

`needs_regeneration_after_revert` (`session_lifecycle.py`) returns
`True` iff the most recent `session.invalidated` /
`session.reverted_to_draft` audit event id is greater than the most
recent `assignments.generated` id.

So, after the super-button fails midway, the session needs to satisfy
at least one of:

1. session status is `draft` AND no `Assignment` rows exist, **or**
2. session status is `draft` AND a revert-class audit event is newer
   than any assignment-generation event.

Today's failure paths violate this:

- **Generate succeeds, Validate fails (errors found):** session
  status stays `draft`, but assignments are fresh and there's no new
  revert event. Predicate evaluates to State **2 / 3** (depending
  on whether `validation_summary` is populated), not 1A.
- **Generate succeeds, Validate succeeds, Activate fails:** session
  is `validated`, fresh assignments, no revert event. Predicate
  evaluates to State **4A / 4B / 5**, not 1A.

The card resolves to State 1A naturally only when the failure leaves
the session in `draft` with either an empty assignment table or a
revert-newer-than-generate audit pair.

### A.3 Design options for "drop back to State 1A"

**Option 1 — Single-transaction wrap (atomic).** Refactor
`replace_assignments`, `mark_validated`, and `activate_session` to
accept a `commit: bool = True` flag (or move their `db.commit()` calls
to their callers). The super-button route would call each with
`commit=False`, then `db.commit()` only after all three succeed; on
any exception, `db.rollback()` cleanly undoes every preceding step.
Audit events would also need to land inside the same transaction
(they do today — they go through `audit.write_event` which uses the
same session).

- Pros: cleanest semantic — the partial state genuinely doesn't
  exist. No audit-event noise from rolled-back attempts. No special
  predicate plumbing needed; on failure the session was never
  touched, so it's still in whatever pre-button state it was in
  (which the caller can constrain to State 1A by only exposing the
  button when the predicate is already true).
- Cons: API change across three services + their existing callers.
  ~20 call sites to audit. Risk: `replace_assignments` flushes /
  commits per-instrument today to keep the audit log readable when a
  multi-instrument generate run hits an error halfway; a single
  transaction means a single audit event or atomic batch is needed
  there too.
- Effort: largest. Probably 2 PRs (services + route).

**Option 2 — Inverse-step rollback on failure.** Keep service
commit semantics as-is. The super-button route runs each step
sequentially, catches exceptions / failure-summary signals, and
explicitly undoes any committed steps before returning the error:
- Validate fails after Generate succeeded → call
  `invalidate_if_validated` (no-op here, since session is still
  `draft`) AND either (a) write a synthetic
  `session.reverted_to_draft` audit event so
  `needs_regeneration_after_revert` trips, or (b) delete the
  freshly-created `Assignment` rows.
- Activate fails after Validate succeeded → call
  `invalidate_session(reason="super_button_rollback")`. That writes
  `session.invalidated`, which IS in the `revert_events` set in
  `needs_regeneration_after_revert`, so the predicate trips and the
  card lands in State 1A. Free of new schema or new audit-event
  types.
- Generate fails first → no rollback needed; session was draft going
  in, draft coming out, with no new audit events.

- Pros: each service stays as-is. Activate-failure rollback is
  already free (the existing `invalidate_session` event satisfies
  the predicate). Smallest code footprint.
- Cons: the Validate-failure case is awkward. Writing a synthetic
  `session.reverted_to_draft` event when no actual revert happened
  is a misuse of the audit log — the audit envelope is supposed to
  reflect real lifecycle transitions, and registering a fake one
  pollutes downstream analytics. Deleting freshly-created
  assignments is destructive and the audit log would record both
  the create and the delete, which is noisy too.
- Effort: small (~one route + one helper) but the semantic
  cleanliness is poor on the Validate-failure path.

**Option 3 — New "super-button-failed" marker.** Add a small piece
of state (column, audit event, or transient signal) that explicitly
forces State 1A independent of assignment counts and revert history.
Cleared on next successful Generate or Validate.

- Sub-variant 3a: new column `review_sessions.workflow_pending_retry`
  (or similar). Migration + model field. State 1A predicate widens
  to `... OR review_session.workflow_pending_retry`.
- Sub-variant 3b: new audit event type
  `session.workflow_chain_failed`. State 1A predicate widens to
  treat it as a revert-class event for the audit-history check.

- Pros: cleanest separation of concerns — the marker exists
  precisely for this purpose; doesn't co-opt revert semantics.
- Cons: more moving parts. 3a needs a schema migration. 3b needs an
  event-schema registration and a tweak to the audit-history
  predicate.
- Effort: medium. Worth it only if Option 2's semantic muddle
  bothers reviewers.

**Recommendation.** Option 2 with a narrow Validate-failure rollback
strategy: **leave the fresh assignments in place but skip the State
1A coercion**. Concretely:

- Failure mode "Generate raised" → session was draft, still is.
  Resolves to State 1A (or State 1) naturally. Banner shows the
  Generate error.
- Failure mode "Validate found errors" → session is draft, fresh
  assignments. **Resolves to State 3** (validation failed; pills in
  the body show the counts; banner adds the same diagnostic context
  with `validation_summary` already populated). This is arguably the
  more useful end state than 1A — the operator gets the pill counts
  AND the error banner.
- Failure mode "Activate raised" → call
  `invalidate_session(reason="super_button_rollback")`, session flips
  back to draft, the `session.invalidated` event trips
  `needs_regeneration_after_revert`, card resolves to State 1A. ✓

This trades strict adherence to the spec ("always drop back to 1A")
for a more legible failure surface. If the spec is non-negotiable,
escalate the Validate-failure branch to Option 1 (single-transaction
wrap) so the freshly-committed assignments roll back too.

### A.4 Implementation tasks for the recommended path (Option 2 / mixed)

1. **New route.** `POST /operator/sessions/{id}/workflow/run-setup`
   (or similar) in either `_session_home.py` or a new
   `_workflow.py` slice under `routes_operator/`. Form fields:
   `return_to` (same allowlist as the existing actions),
   `acknowledge_warnings` (mirrors the existing State-4B detour).
2. **Route body.** Sequential best-effort run with structured
   per-step error capture:

   ```python
   errors: list[str] = []

   # Step 1: Generate
   if not lifecycle.is_editable(review_session):
       errors.append("Session can't be edited from its current state.")
   else:
       try:
           assignments.replace_assignments(db, ...)
       except ValueError as exc:
           errors.append(str(exc))

   if errors:
       return _redirect_with_flash(review_session, return_to, errors)

   # Step 2: Validate (always runs; readiness drives next step)
   issues = validation.validate_session_setup(db, review_session)
   report = lifecycle.build_readiness_report(issues)
   if not report.can_activate:
       # Stays in draft; let State 3 surface the pills.
       return _redirect_with_validation_summary(...)
   try:
       lifecycle.mark_validated(db, ..., report=report)
   except lifecycle.LifecycleError as exc:
       errors.append(str(exc))
       return _redirect_with_flash(...)

   # Step 3: Activate
   try:
       lifecycle.activate_session(
           db, ..., report=report,
           acknowledge_warnings=acknowledge_warnings == "true",
       )
   except lifecycle.LifecycleError as exc:
       # Rollback validated → draft so the card lands in State 1A.
       lifecycle.invalidate_session(
           db, ..., reason="super_button_rollback",
       )
       errors.append(str(exc))
       return _redirect_with_flash(...)

   return _redirect_to_ready_landing(review_session, return_to)
   ```

3. **Banner / flash mechanism.** The card currently has no
   inline-error rendering. Easiest hook is a query param on the
   redirect target (e.g. `?super_error=<urlencoded>`) plus a
   `super_error` context key passed into the partial that renders a
   `.banner.banner-error.banner-scroll-target` above the workflow
   card. Pattern already used by `missing-confirm-banner` in
   `session_assignments.html:138`. The card body can additionally
   carry a state-conditional "Last attempt failed at step N — see
   banner above" line.
4. **New audit event.** Register
   `session.workflow_run_started` (start) and
   `session.workflow_run_failed` (stop) in `EVENT_SCHEMAS`
   (`app/services/audit.py`) so the operator's history page reflects
   the super-button attempt distinct from the per-step `assignments.generated`
   / `session.validated` / `session.activated` / `session.invalidated`
   trail. Optional but useful for diagnosing pilot reports of "I
   clicked the button and nothing happened".
5. **Workflow card.** Add a new stage button — e.g. **"Run setup"**
   — in either of two layouts:
   - **Replacement.** Collapse the three live forward stages
     (Generate / Validate / Start) into one slot positioned between
     Revert to draft and Generate invites. States 1A / 2 / 4A drop
     to a single "Run setup" Primary; State 5 still surfaces the
     errors but the operator's single live action is Revert.
   - **Addition.** Keep the three individual buttons (so the
     operator can still run one step at a time) and add "Run setup"
     as an eighth slot. Primary on whichever of 1A / 2 / 4A is
     currently the live state; inert elsewhere.

   The replacement layout matches the user's "one super button"
   intent better; the addition layout preserves the granular control
   the existing stepper offers, which is useful while debugging
   setup-data problems.
6. **Form holder.** New `next-action-run-setup-form` posting to the
   route, carrying `return_to` and (when the readiness report has
   warnings) a hidden `acknowledge_warnings=true`. Mirrors the
   existing pattern.
7. **Permission / lifecycle gate.** The route should reject when the
   session is `ready` (matches the natural "you've already done
   this" path) and when `is_setup_empty` is True (no rule pins yet
   → Generate would no-op). Both checked upstream of the
   try/except chain so the error banner reads cleanly.
8. **State 4B / warnings.** If the readiness report has non-blocking
   findings, the existing flow detours through `/validate?activate=1`
   so the operator acknowledges warnings inline. The super-button
   either inherits that detour on Validate-clean + warnings (i.e.
   305 to the warnings page) or accepts an implicit "ack-via-super-
   button" by submitting `acknowledge_warnings=true` directly. The
   second is more in the spirit of a one-click action; the first is
   safer.

### A.5 Tests to add

- Each step in isolation succeeding → session ends `ready`,
  redirect honours `return_to`.
- Generate path raises → session still `draft`, no fresh
  assignments, banner surfaces the error message.
- Validate-found-errors → session still `draft`, fresh assignments
  exist, `validation_summary` populated on the next page render
  (State 3 not 1A), banner surfaces the per-issue summary.
- Activate raises `LifecycleError(has_errors)` after Validate
  somehow passed (race / re-entrancy) → session is back in `draft`
  via the `invalidate_session` rollback step; predicate trips
  `needs_regeneration_after_revert`; card resolves to State 1A.
- Warnings-only → either auto-acknowledged (path A) or detoured to
  Validate page (path B) — pick one and pin it.
- Pre-condition: `is_setup_empty` → 4xx, no audit events written.
- Pre-condition: session already `ready` → 4xx with a clear banner
  ("Session is already running").

### A.6 Open questions / decisions to settle before coding

1. **Does the super-button replace the three individual stage
   buttons, or sit alongside them?** (Section A.4 step 5.)
2. **Validate-failure end state: State 3 (recommended) or strict
   State 1A?** If strict, we need either Option 1 (atomic wrap) or
   destructive assignment deletion; flag the trade-off in the PR
   description.
3. **Warnings handling: auto-acknowledge on super-button click, or
   keep the inline warnings detour?** Recommend keeping the
   detour — operators should see warnings, even if the button is
   intended to be one-click.
4. **Audit-event naming.** `session.workflow_run_started` /
   `session.workflow_run_failed` are placeholders; pick names that
   match existing conventions (the `session.*` prefix already
   covers lifecycle transitions, so this naming fits).
5. **Stay-on-page redirect target.** Same `return_to` allowlist as
   the existing actions; honor `assignments` / `home` consistent
   with the rest of the workflow card.

