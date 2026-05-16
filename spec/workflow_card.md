# Workflow card

The **Workflow card** is the single persistent action card at the
top of every operator session page. It carries state-aware
explanatory copy, a uniform seven-stage button stepper, and a
right-column status / errors aside. The card is the canonical
entry-point for every lifecycle-advancing action on a session —
from generating assignments through to sending reminders.

The card was originally called "Next Action" and the template /
CSS class names still use the `next_action` prefix; the H2 title
operators read is "Workflow".

## Where it renders

The card renders on every session-scoped operator page that's
useful while the session is mid-lifecycle:

- **Session Home** (`/operator/sessions/{id}`) — full-width, just
  below the chrome.
- **Operations-row pages** — full-width, just below the chrome,
  on Assignments / Validate / Previews / Invitations / Responses.

The card does not render on Setup-row pages (Reviewers /
Reviewees / Relationships / Instruments) or on the per-session
edit / extract / outbox sub-pages.

Each host page sets `next_action_return_to` to its operations-row
slug so that every POST the card emits — `/workflow/activate`,
`/revert`, `/invitations/generate`, `/invitations/send-all`,
`/invitations/remind-incomplete` — 303s back to the page that
rendered the card. Allowed slugs:

- `home` (Session Home; resolved server-side to
  `/operator/sessions/{id}`)
- `reviewers` / `reviewees` / `assignments` / `instruments` (Setup
  + Assignments)
- `validate` / `previews` / `invitations` / `responses` (the
  remaining Operations-row pages)

The allowlist is `_REVERT_RETURN_TO` in
`app/web/routes_operator/_shared.py`.

## Inputs the card reads

Every page route builds the card's context with one call to
`views.build_workflow_card_context(db, review_session, *,
return_to, validated_just_ran=False, super_failure=None,
activate_confirm=None, user=None, correlation_id=None)` and merges
the returned dict into
its template context via `**workflow_ctx`. The builder lives in
`app/web/views/_workflow_card.py`. It returns:

- `is_draft` / `is_validated` / `is_ready` — lifecycle booleans
  from `lifecycle.is_*`.
- `is_setup_empty` — `True` iff session is in draft AND any of:
  reviewer count is 0, reviewee count is 0, or at least one
  instrument has no assignment rule pinned (checked via
  `instruments.has_unpinned`, which also returns `True` when the
  session has zero instruments).
- `is_pre_generate` — `True` iff session is in draft,
  `is_setup_empty` is `False`, AND either no `Assignment` rows
  exist yet OR the most recent revert
  (`session.invalidated` or `session.reverted_to_draft`) is newer
  than the most recent `assignments.generated` event
  (`lifecycle.needs_regeneration_after_revert`).
- `invitations_generated` — `True` iff at least one `Invitation`
  row exists for the session (`invitations.has_invitations`).
- `invitations_sent` — `True` iff at least one `Invitation` row
  has a non-NULL `sent_at` (`invitations.has_sent_invitations`).
- `validation_summary` — `dict | None`. Populated when
  `validated_just_ran=True` OR the session is already
  `validated`. Keys: `error_count` / `warning_count` /
  `info_count` (from the readiness report); `can_activate`
  (`report.can_activate AND is_validated(session)`);
  `needs_acknowledge` (`report.has_non_blocking_findings`).
- `validation_issues_by_severity` — `dict[str, list]` with
  `errors` / `warnings` / `info` lists from
  `lifecycle.build_readiness_report`.
- `setup_checklist` — three-boolean dict (`reviewers_ok`,
  `reviewees_ok`, `instruments_pinned_ok`) for the State 1 / 1A
  right-column checklist.
- `super_failure` — `dict | None` decoded from the redirect's
  `?super_status=failed&super_step=...&super_error=...` query-
  param triple via `views.parse_super_failure`. Drives the
  right-column failure banner.
- `activate_confirm` — `dict | None`. Populated
  (`responses_deleted` / `deleted_pairs` keys) when the builder is
  called with `activate_confirm="responses"` AND a dry-run
  reconcile (`assignments.reconcile_impact`) shows a run would
  delete one or more responses. Drives the saved-response
  confirmation banner in the card body. `None` outside the
  super-button's `?activate_confirm=responses` detour and whenever
  a run would delete no responses.
- `next_action_return_to` — the `return_to` slug, passed
  through.

When `validated_just_ran=True` (the page was reached with
`?validated=1`) AND the readiness report is clean AND the session
is still in draft, the builder also calls
`lifecycle.mark_validated` to flip `draft → validated` before
populating the rest of the context. `user` and `correlation_id`
must be passed in for that path to fire.

A companion helper `views.parse_super_failure(super_status,
super_step, super_error)` decodes the workflow super-button's
redirect query-param triple into the `super_failure` dict (or
`None`).

## State machine

The card has ten states. The body and right column are chosen by
this cascade in `next_action_card.html`:

```
if is_setup_empty:           → State 1
elif is_pre_generate:        → State 1A
elif is_draft:
    if validation_summary:   → State 3
    else:                    → State 2
elif is_validated:
    if can_activate:
        if needs_acknowledge: → State 4B
        else:                 → State 4A
    else:                    → State 5
elif is_ready:
    if not invitations_generated: → State 6
    elif not invitations_sent:    → State 7
    else:                         → State 8
```

### Per-state body copy

| State | Trigger | Body |
| --- | --- | --- |
| **1** | `is_setup_empty` | "Session not fully set up. Make sure that reviewers, reviewees, and relationships (optional), and instruments have been set up before continuing." |
| **1A** | `is_pre_generate` | "Run generation to create the assignment pairs (note that doing so will replace any previously generated assignment pairs)." |
| **2** | `is_draft`, no `validation_summary` | "Run validation to surface errors and warnings before activating. Validation never mutates session data." |
| **3** | `is_draft` + `validation_summary` | "Validation didn't pass." + "Resolve the errors and re-run validation before activating." (pill row + per-issue list moves to the right column.) |
| **4A** | `is_validated` + `can_activate` + not `needs_acknowledge` | "The session setup data has successfully validated. Preview the reviewer surface to make sure that it conforms to your requirements before activating." |
| **4B** | `is_validated` + `can_activate` + `needs_acknowledge` | Same as 4A plus help-line: "{N} warning(s) — review on Validate before activating." |
| **5** | `is_validated`, not `can_activate` | "Validation shows that there are error(s). Resolve them and re-run validation before activating." |
| **6** | `is_ready`, no Invitation rows yet | "Session is currently activated. Reviewers can access forms and save responses. Don't forget to generate and send out emails to notify the reviewers." |
| **7** | `is_ready`, Invitation rows exist, none `sent_at` | "Session is currently activated. Reviewers can access forms and save responses. Don't forget to send out emails to notify the reviewers." |
| **8** | `is_ready`, at least one Invitation with `sent_at` | "Session is currently activated. Reviewers can access forms and save responses. You may remind reviewers if needed." |

## Layout

The card uses a two-column inner grid via CSS:

```
┌── Workflow (H2) ─────────────────────────────────────────────┐
│                                                              │
│  ┌─ .next-action-main ────────┐ ┌─ .next-action-status ────┐ │
│  │ <p>State-specific body</p> │ │ State-specific status /  │ │
│  │                            │ │ errors aside.            │ │
│  │ <div .next-action-buttons>│ │                          │ │
│  │   Seven stepper buttons   │ │                          │ │
│  │ </div>                    │ │                          │ │
│  └────────────────────────────┘ └──────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

`grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)`. The left
column carries a 1px right border that reads as a vertical
divider between the two columns; below ~720px viewport width the
columns collapse to a single stacked column and the divider
becomes a horizontal rule above the right-column content.

CSS lives in `app/web/templates/base.html` next to the
`.card.next-action` rules.

## Workflow stepper — uniform 7-button row

Every state renders the same seven-stage bottom row, in the same
order — Revert to draft sits leftmost, then the forward stages in
their workflow order:

```
Revert to draft · Generate assignments · Validate setup · Activate session · Create invites · Send invites · Send reminders
```

Each slot is either **live** (Primary or Secondary, clickable) or
**inert** (`<button disabled aria-disabled="true">`, rendered in
the Secondary style for visual consistency).

The matrix below shows what each slot does per state. `Pri` =
Primary live, `Sec` = Secondary live, `—` = inert preview / past
stage. Revert to draft is rendered in Secondary style whenever
it's live — the stepper never promotes it to Primary.

| Slot | 1 | 1A | 2 | 3 | 4A | 4B | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Revert to draft | — | — | — | — | Sec | Sec | Sec | Sec | Sec | Sec |
| Activate session | — | **Pri** | **Pri** | **Pri** | **Pri** | **Pri** | — | — | — | — |
| Create invites | — | — | — | — | — | — | — | **Pri** | Sec | Sec |
| Send invites | — | — | — | — | — | — | — | — | **Pri** | Sec |
| Send reminders | — | — | — | — | — | — | — | — | — | **Pri** |

(`Generate assignments` and `Validate setup` no longer render as
their own stepper slots — they collapse into the **Activate
session** super-button, which runs Generate → Validate → Activate
in sequence. The two retired slots' state-specific behaviour is
documented in §"Activate session super-button" below.)

### Activate session super-button

The Activate session button POSTs to a single
`/operator/sessions/{id}/workflow/activate` route in
`_workflow.py` that runs three lifecycle steps in sequence:

1. **Generate.** `assignments.replace_assignments(...)` —
   materialises one `Assignment` row per `(reviewer, reviewee,
   instrument)` triple eligible under each instrument's pinned
   rule. It **reconciles** the existing rows (see
   `spec/reconciling_regeneration.md`) — inserting newly eligible
   pairs, deleting pairs the rule no longer produces along with
   their responses, and leaving matched pairs and their responses
   untouched. The saved-response confirmation detour below gates
   this step when it would delete responses.
2. **Validate.** `validation.validate_session_setup(...)` →
   `lifecycle.build_readiness_report(...)`. When the report is
   clean, `lifecycle.mark_validated(...)` flips `draft →
   validated`. When the report has errors, the chain stops here.
3. **Activate.** `lifecycle.activate_session(...)` flips
   `validated → ready`, opens every instrument
   (`accepting_responses = True`), and emits
   `session.activated`.

The route runs Validate + Activate from any `draft` / `validated`
starting state, and the Generate step runs on every click.

#### Saved-response confirmation detour

A session reverted from `ready` back to `draft` keeps its
responses (`revert_session_to_draft` preserves them). The Generate
step's reconcile deletes responses for any pair the rule no longer
produces (see `spec/reconciling_regeneration.md`), so re-activating
such a session could destroy recorded data without warning.

The detour is **impact-driven**: it fires only when a run would
actually delete a response, not whenever responses merely exist.
When the session is editable, has responses, and the POST carried
no `acknowledge_response_loss` field, the route dry-runs the
reconcile via `assignments.reconcile_impact(...)`. If that impact's
`responses_deleted` is zero, the run proceeds straight through —
no confirmation. If it is non-zero, the route 303s back to the host
page with `?activate_confirm=responses`.

The workflow card decodes that param (via the `activate_confirm`
builder kwarg, which re-runs `reconcile_impact` to populate the
`responses_deleted` / `deleted_pairs` counts) and renders a
confirmation banner in the card body:

- **Regenerate & activate** posts back to `/workflow/activate` with
  `acknowledge_response_loss=true`, which skips the detour so the
  run proceeds: the reconcile deletes the responses on the orphaned
  pairs, keeps the rest, and Validate + Activate follow.
- **Cancel** is a plain link back to the host page — nothing runs.

Like the warnings detour, the confirmation detour writes no
`workflow_run_failed` event — the run is paused at the
operator-choice step, not failed.

#### Warnings detour

When the readiness report has non-blocking findings (warnings or
info), the super-button does NOT fire `/activate` directly.
Instead it 303s to
`/operator/sessions/{id}/validate?activate=1&return_to=...`. The
Validate page renders a yellow `.banner.banner-warning` with the
warnings inline + an "Acknowledge and activate" submit; the
operator clicks Acknowledge, and the existing `/activate` POST
fires from that banner with `acknowledge_warnings=true`.

In State 4B the workflow card renders the Activate session button
as an `<a>` to the same warnings-detour URL so operators reach the
acknowledgement step without going through the super-button POST
in the first place.

#### Failure handling

Each step is wrapped in a try/except that catches
`lifecycle.LifecycleError`, `ValueError`, and the route's
internal `_StepFailed` sentinel. The handling differs per step:

- **Generate raises.** No rollback (the route didn't get past
  step 1). The redirect target carries
  `?super_status=failed&super_step=generate&super_error=<msg>`.
  Card lands in State 1 or State 1A on next render.
- **Validate finds errors.** No rollback. The fresh assignments
  stay; the next render computes `validation_summary` with errors
  populated and the card lands in State 3 (left-column prose,
  right-column pill row + per-issue list). The redirect target
  carries `?super_status=failed&super_step=validate&super_error=<msg>`
  so the right-column failure banner sits above the issue list.
- **Activate raises.** The session has already been promoted to
  `validated` at this point. The except branch calls
  `lifecycle.invalidate_session(reason="workflow_run_rollback")`,
  which emits a `session.invalidated` audit event. That event is
  in the `revert_events` set checked by
  `needs_regeneration_after_revert`, so the predicate trips and
  the card resolves to State 1A on the next render. Redirect
  carries `?super_status=failed&super_step=activate&super_error=<msg>`.

The super-button itself emits two audit events bracketing the
run:

- `session.workflow_run_started` — once per click, with
  `context.button="activate_session"`.
- `session.workflow_run_failed` — emitted in the except branch
  with `context.step` (`generate` / `validate` / `activate` /
  `precondition`) and `context.error_message`. Successful end-to-
  end runs are documented by the per-step events
  (`assignments.generated` + `session.validated` +
  `session.activated`) — no separate "succeeded" envelope.

The warnings-detour path does NOT write a `workflow_run_failed`
event — the run is paused at the operator-acknowledgement step,
not failed.

Pre-flight gates:

- Session is already `ready` → 303 with
  `?super_status=failed&super_step=precondition&super_error=Session+is+already+activated.`
- `is_setup_empty` is True → currently no defensive gate at the
  route layer; the workflow card renders the button as inert in
  State 1 so the form can't post.

### Other stepper buttons

- **Create invites** posts to
  `/operator/sessions/{id}/invitations/generate` via
  `next-action-generate-invites-form`. Calls
  `invitations.generate_invitations`, which idempotently creates
  one `Invitation` row per assigned active reviewer (skipping
  reviewers with no `include=True` assignment and reviewers
  already invited).
- **Send invites** posts to
  `/operator/sessions/{id}/invitations/send-all` via
  `next-action-send-invites-form`. Iterates every pending
  invitation and dispatches via `invitations.send_invitation`.
- **Send reminders** posts to
  `/operator/sessions/{id}/invitations/remind-incomplete` via
  `next-action-send-reminders-form`. Calls
  `invitations.send_reminders_to_incomplete` for reviewers whose
  assignments aren't complete.

All three invitation forms emit on every ready state (6 / 7 / 8)
so the Secondary "re-run an earlier stage" buttons stay wired;
only the corresponding Primary slot's live state changes. Each
form carries a hidden `return_to=<slug>` field; the route's
`_invitation_redirect_url` helper consults
`_REVERT_RETURN_TO` + the special `"home"` slug to resolve the
303 target. Direct form posts elsewhere (e.g. tests hitting the
route without the form's hidden field) fall back to
`/operator/sessions/{id}/invitations`.

- **Revert to draft** posts to `/operator/sessions/{id}/revert`:
  - States 4A / 4B / 5 (`is_validated`): via
    `next-action-revert-form`. Route dispatches to
    `lifecycle.invalidate_session(reason="operator_revert")` →
    `validated → draft`, audit `session.invalidated`.
  - States 6 / 7 / 8 (`is_ready`): via `next-action-pause-form`
    with hidden `confirm=true`. Route dispatches to
    `lifecycle.revert_session_to_draft` → `ready → draft`,
    audit `session.reverted_to_draft`. Instruments flip
    `accepting_responses = False`; responses are preserved.

## Right column — per state

The right column is a `<aside class="next-action-status"
id="next-action-status">` block. Per-state content:

| State | Right column content |
| --- | --- |
| **1** (setup empty) | Setup-completion checklist (`Setup checklist` heading + three `<li>` rows: Reviewers, Reviewees, Instruments (all rules pinned), each with a ✓ or ✗ pill + a deep link to the relevant Operations-row page). |
| **1A** (pre-generate) | Same checklist as State 1; in State 1A all three rows read ✓. Keeps the right column from reflowing as setup completes. |
| **2** (draft, no summary) | Empty. |
| **3** (validation failed) | `Validation issues` heading + pill row (error / warning / info counts) + per-issue list (rendered by `operator/partials/_next_action_issue_list.html`). |
| **4A** (validated, no warnings) | `Status` heading + "Setup validated." |
| **4B** (validated + warnings) | "Setup validated." + a per-warning pill row + the per-issue list inline so the operator sees what they're about to acknowledge before clicking the detour. |
| **5** (validated + errors) | `Validation issues` heading + pill row + per-issue list, same shape as State 3. |
| **6 / 7 / 8** | Currently empty (invitation-status counters deferred to a future iteration). |

### Super-button failure banner

When `super_failure` is populated (i.e. the page was hit with
`?super_status=failed&super_step=<step>&super_error=<msg>`), the
right column also renders a `.banner.banner-error` block at the
top of the aside. Headline: "Activate session failed at step N of
3: <step name>." The per-state right-column content above
continues to render below the banner; the failure banner doesn't
suppress State 3 / 5 issue lists.

## POST routes

Quick reference. Every action ultimately resolves to one of these
routes:

| Route | Service | Allowed prior state | Resulting state | Audit event |
| --- | --- | --- | --- | --- |
| `POST /operator/sessions/{id}/workflow/activate` | `assignments.replace_assignments` → `lifecycle.mark_validated` → `lifecycle.activate_session` | `draft` or `validated` (`is_editable`) | `ready` (or detour to Validate page in warnings case, or to the host page in the saved-response confirmation case) | `session.workflow_run_started` + per-step events; `session.workflow_run_failed` on failure |
| `POST /operator/sessions/{id}/assignments/generate` | `assignments.replace_assignments` | `draft` or `validated` | unchanged | `assignments.generated` |
| `POST /operator/sessions/{id}/activate` | `lifecycle.activate_session` | `validated` | `ready` | `session.activated` |
| `POST /operator/sessions/{id}/revert` (when `is_validated`) | `lifecycle.invalidate_session` | `validated` | `draft` | `session.invalidated` |
| `POST /operator/sessions/{id}/revert` (when `is_ready`) | `lifecycle.revert_session_to_draft` | `ready` | `draft` | `session.reverted_to_draft` |
| `POST /operator/sessions/{id}/invitations/generate` | `invitations.generate_invitations` | `ready` | unchanged | `invitations.generated` |
| `POST /operator/sessions/{id}/invitations/send-all` | `invitations.send_invitation` (per pending) | `ready` | unchanged | per-invitation send events |
| `POST /operator/sessions/{id}/invitations/remind-incomplete` | `invitations.send_reminders_to_incomplete` | `ready` | unchanged | per-reminder send events |

The per-step `/assignments/generate` and `/activate` routes
remain alive even though the Workflow card no longer POSTs to
them directly. `/activate` is load-bearing for the Validate page's
warnings-detour banner. `/assignments/generate` has no UI consumer
but stays as a small surface for direct callers (test fixtures,
the legacy programmatic-validate hooks).

All `/activate` and `/revert` routes honour the form field
`return_to` against the
`_REVERT_RETURN_TO` allowlist and 303 to the corresponding child
page; values outside the allowlist (including `home`) 303 to
`/operator/sessions/{id}`.

## Source-of-truth pointers

- Partial: `app/web/templates/operator/partials/next_action_card.html`
- Right-column issue list partial:
  `app/web/templates/operator/partials/_next_action_issue_list.html`
- Context builder: `app/web/views/_workflow_card.py`
- Super-button route: `app/web/routes_operator/_workflow.py`
- Per-step lifecycle routes: `app/web/routes_operator/_session_home.py`
  (`session_activate` / `session_revert_to_draft`),
  `app/web/routes_operator/_assignments.py` (`assignments_generate`)
- Per-step invitation routes: `app/web/routes_operator/_operations.py`
  (`invitations_generate` / `invitations_send_all` /
  `invitations_remind_incomplete`)
- Lifecycle service: `app/services/session_lifecycle.py`
- Invitations service: `app/services/invitations.py`
- Audit-event registry: `app/services/audit.py` (`EVENT_SCHEMAS`)
- CSS: `app/web/templates/base.html` (`.card.next-action` family)
