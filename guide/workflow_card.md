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
