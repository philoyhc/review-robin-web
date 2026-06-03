# Workflow card

The **Workflow card** is the single persistent action card at the
top of every operator session page. It carries state-aware
explanatory copy, a **single row of action buttons** (≤ 4 visible
buttons per state, each fixed at 25% of the column width, inactive
hidden), and a right-column status aside. The card is the canonical
entry-point for every lifecycle-advancing action on a session —
from preparing the assignment pairs through to sending reminders,
manually releasing responses, closing, and archiving.

The H2 the operator reads is "Workflow". The template / CSS
class names use the `next_action` prefix (the card's earlier
name); the prefix is kept to avoid touching every consumer.

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

Each host page sets `next_action_return_to` to its Operations-row
slug so that every POST the card emits — `/workflow/prepare`,
`/workflow/activate`, `/workflow/close`,
`/workflow/release-responses`, `/workflow/stop-release`,
`/workflow/archive`, `/revert`, `/invitations/generate`,
`/invitations/send-all`, `/invitations/remind-incomplete` —
303s back to the page that rendered the card (except Archive,
which 303s to `/operator/sessions/archived`). Allowed slugs:

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
prepare_confirm=None, user=None, correlation_id=None)` and merges
the returned dict into its template context via `**workflow_ctx`.
The builder lives in `app/web/views/_workflow_card.py`. It
returns:

- `is_draft` / `is_validated` / `is_ready` / `is_expired` /
  `is_archived` — lifecycle booleans from `lifecycle.is_*`.
- `is_setup_empty` — `True` iff the session is in draft AND any of:
  reviewer count is 0, reviewee count is 0, or at least one
  instrument is not configured (checked via
  `instruments.has_unconfigured`, which returns `True` when the
  session has zero instruments OR any instrument fails the
  per-model `is_configured(instrument)` predicate). Legacy
  instruments are configured iff `rule_set_id IS NOT NULL`;
  new-model instruments are configured iff they have at least
  one `visible=True` response field (Wave 4 PR 2 — replaces
  the previous rule-set-centric `has_unpinned` predicate).
- `is_pre_generate` — retained for external consumers; the card's
  state cascade no longer branches on it.
- `invitations_generated` — `True` iff at least one `Invitation`
  row exists for the session.
- `invitations_sent` — `True` iff at least one `Invitation` row
  has a non-NULL `sent_at`.
- Ten `*_visible` flags — one per button slot (`revert_visible`,
  `prepare_visible`, `create_invites_visible`,
  `send_invites_visible`, `activate_visible`,
  `send_reminders_visible`, `close_visible`,
  `release_responses_visible`, `stop_release_visible`,
  `archive_visible`). The single-row layout renders only the
  visible buttons. See "Workflow stepper — single-row button
  layout" below for the per-slot formula + the contract that
  every state caps at ≤ 4 visible.
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
  `reviewees_ok`, `instruments_configured_ok`) driving the
  State 1 right-column checklist.
- `super_failure` — `dict | None` decoded from the redirect's
  `?super_status=failed&super_button=...&super_step=...&super_error=...`
  query-param set via `views.parse_super_failure`. Slots:
  `button` (`"prepare"` / `"activate"`), `step`, `error`. Drives
  the workflow-failure signal line.
- `prepare_confirm` — `dict | None`. Populated
  (`responses_deleted` / `deleted_pairs` keys) when the builder
  is called with `prepare_confirm="responses"` AND a dry-run
  reconcile shows a Prepare run would delete one or more
  responses. Drives the saved-response confirmation banner in
  the card body.
- `scheduled_activation_caption` — `dict | None` shaped
  `{"tone": ..., "text": ...}`, built by
  `build_scheduled_activation_caption`. Drives the scheduled-
  activation signal line. `None` when there's nothing to surface.
- `auto_send_invites_caption` — `dict | None` of the same shape,
  built by `build_auto_send_invites_caption`. Drives the auto-
  send invites signal line.
- `auto_send_reminders_caption` — `dict | None` of the same shape,
  built by `build_auto_send_reminders_caption`. Drives the auto-
  send reminders signal line.
- `manual_activate_cancellation` — `dict | None`. Confirmation-
  modal payload for the Activate button when a manual Activate
  click would cancel pending auto-sends, built by
  `build_manual_activate_cancellation`. Shape:
  `{"text": "N scheduled auto-send(s) will be cancelled…",
  "count": int, "pending_fires": list[str]}`. `None` when nothing
  would be cancelled. The modal lives on the button itself, not
  the right column — see §"Manual-activate cancellation modal".
- `next_action_return_to` — the `return_to` slug, passed
  through.

When `validated_just_ran=True` (the page was reached with
`?validated=1`) AND the readiness report is clean AND the session
is still in draft, the builder also calls
`lifecycle.mark_validated` to flip `draft → validated` before
populating the rest of the context. `user` and `correlation_id`
must be passed in for that path to fire.

A companion helper `views.parse_super_failure(super_status,
super_step, super_error, super_button)` decodes the workflow
buttons' redirect failure params into the `super_failure` dict
(or `None`). The `super_button` slot identifies which button
failed (`"prepare"` or `"activate"`) so the failure line's copy
varies accordingly; when absent on a legacy URL it falls back
from the step name (`generate` / `validate` → `"prepare"`;
`activate` → `"activate"`; `precondition` → `"prepare"`).

## State machine

The card has twelve states. The body and right column are
chosen by this cascade in `next_action_card.html`:

```
if is_setup_empty:                              → State 1
elif is_draft and validation_summary:           → State 3
elif is_draft:                                  → State 2
elif is_validated:
    if not validation_summary.can_activate:     → State 4Err
    elif needs_acknowledge:                     → State 4W
    elif invitations.none:                      → State 4
    elif invitations.generated_not_sent:        → State 5
    else (invitations.sent):                    → State 6
elif is_ready:
    if invitations.none:                        → State 7
    elif invitations.generated_not_sent:        → State 8
    else (invitations.sent):                    → State 9
elif is_expired:                                → State 10
```

State 4Err is defensive — `mark_validated` only flips
`draft → validated` on a clean report, so re-running Validate in
the `validated` lifecycle and finding errors is rare (it requires
a setup edit that the lifecycle's `invalidate_if_validated` hook
missed).

### Per-state body copy

| State | Trigger | Body |
| --- | --- | --- |
| **1** | `is_setup_empty` | "Session not fully set up. Make sure that reviewers, reviewees, relationships (optional), and instruments have been set up before continuing." |
| **2** | `is_draft`, no `validation_summary` | "Run **Prepare session** to generate the assignment pairs and validate that the setup is ready for prime time. Nothing goes live until you activate." |
| **3** | `is_draft` + `validation_summary` | "**Validation didn't pass.** Resolve the errors and re-run **Prepare session**." |
| **4** | `is_validated` + `can_activate` + no warnings + no invitations | "Setup is prepared and the reviewer surface is previewable. Create invites and send them ahead of Activation, or Activate to receive responses." |
| **4W** | `is_validated` + `can_activate` + `needs_acknowledge` | Same as 4 plus help-line: "{N} warning(s) — review on Validate before activating." |
| **4Err** | `is_validated`, not `can_activate` (defensive) | "Validation shows that there are error(s). Resolve them and re-run **Prepare session** before activating." |
| **5** | `is_validated`, invites generated, none sent | "Invitations are ready to send. Send them ahead of Activation to notify reviewers, or Activate now and send afterwards." |
| **6** | `is_validated`, invites sent | "Reviewers have been notified that the review will open. Activate the session when you're ready to receive responses." |
| **7** | `is_ready`, no Invitation rows yet | "Session is open for responses. Create invites and send them so reviewers know they can start." |
| **8** | `is_ready`, invites generated, none sent | "Session is open. Send the prepared invitations so reviewers know they can start." |
| **9** | `is_ready`, invites sent | "Session is open. Send reminders if reviewers fall behind." |
| **10** | `is_expired` (post-Close-session) | "Session is closed. No further responses are being accepted. Revert to draft to reopen for editing — responses are preserved." |

## Layout

Two-column inner grid: the body copy and a **single row of
action buttons** in the left column, the per-state status aside
in the right column:

```
┌── Workflow (H2) ──────────────────────────────────────────────┐
│ ┌─ .next-action-main (~55%) ─┐ ┌─ .next-action-status (~45%) ┐│
│ │ <p>State-specific body</p> │ │ Per-state status detail +   ││
│ │                            │ │ signal lines (failure /     ││
│ │ (reserved vertical space)  │ │ scheduled / auto-send).     ││
│ │                            │ │                             ││
│ │ ┌── button row (25% × 4) ─┐│ │                             ││
│ │ │ A │ B │ C │ D            ││ │                             ││
│ │ └─────────────────────────┘│ │                             ││
│ └────────────────────────────┘ └─────────────────────────────┘│
└───────────────────────────────────────────────────────────────┘
```

`grid-template-columns: minmax(0, 11fr) minmax(0, 9fr)` — the
left column takes ~55% and the right column ~45% (the left
column carries up to four buttons in its row, so it gets
slightly more room than 50/50). The left column carries a 1px
right border that reads as a vertical divider; below ~720 px
viewport width the columns collapse to a single stacked column
and the divider becomes a horizontal rule above the right-column
content.

The button row is a `.next-action-buttons.next-action-buttons-row`
CSS grid (`grid-template-columns: repeat(4, 1fr)`) so each
visible button locks at exactly 25% of the column width
regardless of how many slots render. With N ≤ 4 visible
buttons the row left-aligns naturally — the empty grid cells
on the right collapse.

**Stable card height.** The `.next-action-body` div flex-grows
(`flex: 1 1 auto`) and carries `min-height: 7.5em` — enough to
reserve the vertical space that the previous multi-row layout
occupied, so the single button row lands at the same Y position
the old run-phase row sat at. The card doesn't grow / shrink as
the state-specific copy or the visible-button count varies.
Multi-paragraph states (e.g. State 3's two-line body) or the
prepare-confirm banner still expand the body beyond the min —
the rule sets a floor, not a ceiling.

CSS lives in `app/web/templates/base.html` next to the
`.card.next-action` rules.

## Workflow stepper — single-row button layout

The left column hosts a **single row of action buttons** at the
bottom of the column. **Every state surfaces ≤ 4 visible
buttons; inactive buttons are not rendered at all.** The row
uses a 4-column CSS grid so each visible button locks at 25% of
the column width regardless of how many slots render; the row
left-aligns naturally as the empty grid cells collapse on the
right.

**Two-line labels.** Each button's text wraps to two lines via a
literal `<br>` after the first word — `Revert<br>to draft`,
`Prepare<br>session`, `Release<br>responses`, etc. The only
three-word label, `Stop releasing<br>responses`, keeps the verb
phrase together on the first line. Two-line labels stabilise
the row height across states (regardless of which buttons
render, every cell is the same height) and absorb the narrower
visual width the 25% column-width grid gives each button.

The body div above the buttons carries a `min-height` that
reserves the vertical space previously occupied by the older
two-row layout, so the card height stays stable when the
visible-button count drops from 4 to 0 (and the buttons land at
the same Y position the old Row 2 occupied).

The 10 conceptual button slots (preserving the legacy
prep-then-run ordering) are:

```
1. Revert to draft   2. Prepare session   3. Create invites   4. Send invites
5. Activate session  6. Send reminders   7. Close session     8. Release responses
9. Stop releasing                        10. Archive session
```

### Visibility gates

The view-builder (``views.build_workflow_card_context``) emits
one boolean per slot. Inactive buttons are hidden:

| Slot | ``*_visible`` formula |
|---|---|
| Revert to draft | `is_validated or is_ready or is_expired` |
| Prepare session | `(is_draft and not is_setup_empty) or is_validated` |
| Create invites | `(is_validated or is_ready) and not invitations_generated` |
| Send invites | `(is_validated or is_ready) and invitations_generated and not invitations_sent` |
| Activate session | `is_validated` (warnings-detour link when `validation_summary.needs_acknowledge`) |
| Send reminders | `is_ready and invitations_sent` |
| Close session | `is_ready` |
| Release responses | `is_expired and not is_archived and not response_release_window_open` |
| Stop releasing | `response_release_window_open and is_expired and not is_archived` |
| Archive session | `is_expired` |

Two slot pairs are mutually exclusive by construction so they
never co-render: Create invites disappears once invites exist
and Send invites disappears once they're sent; Release responses
and Stop releasing share a slot, flipping on
`is_response_release_window_open`, and both stay hidden until
the session has **closed (expired)** — the operator only takes
the manual release shortcut post-deadline.

### Per-state visible-button table

`Pri` = Primary style, `Sec` = Secondary style, `Dgr` = Danger
style, blank = not rendered. Order preserved across the row;
blank cells collapse so the row reads left-to-right with no
gaps.

| Button | 1 | 2 | 3 | 4 | 4W | 4Err | 5 | 6 | 7 | 8 | 9 | 10 | 10‡ |
| --- | - | - | - | - | -- | ---- | - | - | - | - | - | -- | --- |
| Revert to draft | | | | Sec | Sec | Sec | Sec | Sec | Sec | Sec | Sec | Sec | Sec |
| Prepare session | | Pri | Pri | Sec | Sec | Sec | Sec | Sec | | | | | |
| Create invites | | | | Pri | Pri | | | | Pri | | | | |
| Send invites | | | | | | | Pri | | | Pri | | | |
| Activate session | | | | Pri | Pri (→detour) | | Pri | Pri | | | | | |
| Send reminders | | | | | | | | | | | Pri | | |
| Close session | | | | | | | | | Sec | Sec | Sec | | |
| Release responses | | | | | | | | | | | | Sec | |
| Stop releasing | | | | | | | | | | | | | Sec |
| Archive session | | | | | | | | | | | | Dgr | Dgr |
| **Visible total** | **0** | **1** | **1** | **4** | **4** | **3** | **4** | **3** | **3** | **3** | **3** | **3** | **3** |

‡ = `is_response_release_window_open(session)` is True in the `expired` state (i.e. the operator has run Release responses post-close, or a scheduled release has fired). Release and Stop are both gated on `is_expired` — they stay hidden in every pre-expired state regardless of any backdated `responses_release_at`, so the ≤4-button contract holds for every state.

Each state caps at 4 visible buttons; today's worst case is 4
(states 4 / 4W / 5). The pruning rules above (drop Create invites
once generated, drop Send invites once sent, hide Archive
outside `expired`, hide Release/Stop outside `expired`,
Release/Stop share a slot when both eligible) are what keep
the total within budget — without them states 5 / 8 / 9 would
surface 5+ buttons.

`Generate assignments` and `Validate setup` don't render as their
own slots — they live inside **Prepare session**, which runs
Generate + Validate in sequence (see below).

### Prepare session

The Prepare session button POSTs to
`/operator/sessions/{id}/workflow/prepare` in `_workflow.py`,
which runs two lifecycle steps in sequence:

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
   clean and the session is still `draft`,
   `lifecycle.mark_validated(...)` flips `draft → validated`.
   When the report has errors, the chain stops here — assignment
   pairs survive, the session stays in `draft`, and the right-
   column issue list surfaces the diagnostic.

Pre-flight: Prepare runs only while the session is editable
(`draft` / `validated`). A `ready` session must be reverted first.

#### Saved-response confirmation detour

A session reverted from `ready` back to `draft` keeps its
responses (`revert_session_to_draft` preserves them). The
Generate step's reconcile deletes responses for any pair the rule
no longer produces, so re-preparing such a session could destroy
recorded data without warning.

The detour is **impact-driven**: it fires only when a run would
actually delete a response, not whenever responses merely exist.
When the session has responses and the POST carried no
`acknowledge_response_loss` field, the route dry-runs the
reconcile via `assignments.reconcile_impact(...)`. If that
impact's `responses_deleted` is zero, the run proceeds straight
through — no confirmation. If it is non-zero, the route 303s
back to the host page with `?prepare_confirm=responses`.

The workflow card decodes that param (via the `prepare_confirm`
builder kwarg, which re-runs `reconcile_impact` to populate the
`responses_deleted` / `deleted_pairs` counts) and renders a
confirmation banner in the card body:

- **Regenerate & prepare** posts back to `/workflow/prepare`
  with `acknowledge_response_loss=true`, which skips the detour
  so the run proceeds: the reconcile deletes the responses on
  the orphaned pairs, keeps the rest, and Validate follows.
- **Cancel** is a plain link back to the host page — nothing
  runs.

Like the warnings detour on Activate, the confirmation detour
writes no `workflow_run_failed` event — the run is paused at the
operator-choice step, not failed.

### Activate session

The Activate session button POSTs to
`/operator/sessions/{id}/workflow/activate`. Pre-flight requires
`validated` (Prepare must have run first) and refuses `ready`
(already activated).

The route recomputes the readiness report so a setup edit
between Prepare and Activate is caught before the live flip.
When the report has non-blocking findings, the route 303s to
the **warnings detour** at `/validate?activate=1`; the operator
acknowledges warnings inline and the Validate page's banner
re-POSTs to `/workflow/activate` with
`acknowledge_warnings=true`. When the report has errors (a
regression vs the Prepare report), Activate raises and the route
303s back with `super_status=failed`.

On clean activation, `lifecycle.activate_session(...)` flips
`validated → ready`, opens every instrument
(`accepting_responses = True`), and emits `session.activated`.

If Activate raises after `mark_validated`'s promotion (defensive
— `activate_session` itself is the only mutator), the except
branch calls `lifecycle.invalidate_session(...)` to roll the
session back to `draft`.

#### Warnings detour

When the Activate route's recomputed readiness report has
non-blocking findings, the route does NOT fire `activate_session`
directly. Instead it 303s to
`/operator/sessions/{id}/validate?activate=1&return_to=...`. The
Validate page renders a yellow `.banner.banner-warning` with the
warnings inline + an "Acknowledge and activate" submit; the
operator clicks Acknowledge, and a follow-up `/workflow/activate`
POST fires from that banner with `acknowledge_warnings=true`.

In State 4W the workflow card renders the Activate session
button as an `<a>` to the same warnings-detour URL so operators
reach the acknowledgement step without going through the Activate
POST in the first place.

#### Failure handling

Both routes wrap their step chain in a try/except that catches
`lifecycle.LifecycleError`, `ValueError`, and the route's
internal `_StepFailed` sentinel. The redirect URL carries
`super_status=failed&super_button=<prepare|activate>&super_step=<step>&super_error=<msg>`
so the workflow-failure signal line adapts.

**Prepare failures:**

- **Generate raises.** No rollback. Redirect carries
  `super_button=prepare&super_step=generate&super_error=<msg>`.
  Card lands in State 2 (draft, no summary) on next render.
- **Validate finds errors.** No rollback. The fresh assignments
  stay; the next render computes `validation_summary` with
  errors populated and the card lands in State 3. Redirect
  carries `super_button=prepare&super_step=validate`. The audit
  event records the failure for observability.

**Activate failures:**

- **Activate raises.** The except branch calls
  `lifecycle.invalidate_session(reason="workflow_run_rollback")`
  if the session was promoted to `validated`, which emits a
  `session.invalidated` audit event (the predicate
  `needs_regeneration_after_revert` then resolves the card to a
  draft state on the next render). Redirect carries
  `super_button=activate&super_step=activate`.

Each route emits two audit events bracketing the run:

- `session.workflow_run_started` — once per click, with
  `context.button` carrying `"prepare_session"` or
  `"activate_session"`.
- `session.workflow_run_failed` — emitted in the except branch
  with `context.button`, `context.step`, and
  `context.error_message`. Successful runs are documented by the
  per-step events (`assignments.generated` + `session.validated`
  for Prepare; `session.activated` for Activate) — no separate
  "succeeded" envelope.

The warnings detour and the saved-response confirmation detour
both write no `workflow_run_failed` event — the run is paused at
the operator-choice step, not failed.

Pre-flight gates:

- **Prepare** — session not editable (already `ready`) → 303
  with `super_button=prepare&super_step=precondition`.
- **Activate** — session already `ready` → 303 with
  `super_button=activate&super_step=precondition&super_error=Session+is+already+activated.`
- **Activate** — session not yet `validated` → 303 with
  `super_button=activate&super_step=precondition&super_error=Run+Prepare+session+before+activating.`
- `is_setup_empty` is True → no defensive gate at the route
  layer; the workflow card renders the Prepare button as inert
  in State 1 so the form can't post.

### Other button slots

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

Each invitation form is rendered alongside its visible button —
Create invites renders only when `create_invites_visible` is True
(`(is_validated or is_ready) and not invitations_generated`),
Send invites only when `send_invites_visible` is True
(generated but not sent), Send reminders only when
`send_reminders_visible` is True (`is_ready and invitations_sent`).
Each form carries a hidden `return_to=<slug>` field; the route's
`_invitation_redirect_url` helper consults `_REVERT_RETURN_TO` +
the special `"home"` slug to resolve the 303 target. Direct form
posts elsewhere (e.g. tests hitting the route without the form's
hidden field) fall back to `/operator/sessions/{id}/invitations`.
The underlying routes accept POSTs from `validated` / `ready`
regardless of the form's visibility — deep-link / curl callers
still work as defense-in-depth.

- **Revert to draft** posts to `/operator/sessions/{id}/revert`:
  - States 4 / 4W / 4Err / 5 / 6 (`is_validated`): via
    `next-action-revert-form`. Route dispatches to
    `lifecycle.invalidate_session(reason="operator_revert")` →
    `validated → draft`, audit `session.invalidated`.
  - States 7 / 8 / 9 (`is_ready`) + State 10 (`is_expired`):
    via `next-action-pause-form` with hidden `confirm=true`.
    Route dispatches to `lifecycle.revert_session_to_draft` →
    `ready → draft` or `expired → draft` (the route accepts
    both starting states), audit `session.reverted_to_draft`.
    Instruments flip `accepting_responses = False`; responses
    are preserved.

### Close / Release / Stop / Archive buttons

The four post-activation buttons share a workflow-routes
sub-module (`app/web/routes_operator/_workflow.py`):

- **Close session** posts to
  `/operator/sessions/{id}/workflow/close` via
  `next-action-close-form`. Live in State 9 only
  (`close_visible = is_ready`). Calls `lifecycle.close_session`
  → `ready → expired` + closes every instrument
  (`accepting_responses = False`); the per-instrument
  `responses_visible_when_closed` toggle then governs whether
  reviewers can still see what they submitted post-close. Emits
  `session.closed`.
- **Release responses** posts to
  `/operator/sessions/{id}/workflow/release-responses` via
  `next-action-release-responses-form`. Live in State 10 only,
  when the release window isn't currently open
  (`release_responses_visible = is_expired and not is_archived
  and not response_release_window_open`) — the operator only
  takes the manual release shortcut after a session has closed.
  Calls `lifecycle.release_responses_now` → stamps
  `responses_release_at = now()` and clears any prior
  `responses_release_until`. Emits `session.responses_released`.
- **Stop releasing** posts to
  `/operator/sessions/{id}/workflow/stop-release` via
  `next-action-stop-release-form`. Live in State 10 only, when
  the release window is currently open
  (`stop_release_visible = response_release_window_open and
  is_expired and not is_archived`) — the `is_expired` gate
  prevents a backdated `responses_release_at` on a pre-close
  session from surfacing the button. Calls
  `lifecycle.stop_responses_release` → stamps
  `responses_release_until = now()` (the release window closes
  immediately). Emits `session.responses_release_stopped`.
- **Archive session** posts to
  `/operator/sessions/{id}/workflow/archive` via
  `next-action-archive-form`. Live in State 10 only
  (`archive_visible = is_expired`) — the operator must click
  Close session first. The underlying
  `lifecycle.archive_session` service is permissive (accepts
  any non-archived state) so deep-link / curl POSTs from
  `ready` still work; the chrome focuses on the
  close-then-file-away sequence to keep the per-state button
  count manageable. Emits `session.archived`. Redirects to
  `/operator/sessions/archived` so the operator sees their
  just-archived row in context (this is the only post-activation
  button whose 303 target isn't the host page).

## Right column

The right column is a `<aside class="next-action-status"
id="next-action-status">` block. It carries up to two layers,
stacked top-to-bottom:

1. **Per-state status detail** — a heading + content block
   (checklist, issue list, or short status copy), keyed on the
   workflow state.
2. **Signal lines** — inline icon-prefixed paragraphs (no
   background, no border). Up to four lines render depending on
   the data; they're driven by `super_failure`,
   `scheduled_activation_caption`, `auto_send_invites_caption`,
   and `auto_send_reminders_caption`. The signals are largely
   state-independent — they appear in any state when their
   source caption is non-None.

### Right-column content by state

The cell shows the per-state status detail. Any non-None signal
line (failure / scheduled-activation / auto-send invites / auto-
send reminders) renders below the detail; the per-signal
condition tables in the next section say when each is non-None.

Each row is a single inline paragraph — the bold label (e.g.
**Setup checklist**, **Validation issues**, **Status**) leads,
an em dash follows, then the content flows inline. Lists wrap as
needed but the label stays on the same line as the first content
item; there's no separate heading row.

| State | Per-state status detail |
| --- | --- |
| **1** (setup empty) | **Setup checklist** — three inline entries (Reviewers / Reviewees / Instruments (all rules pinned)) each prefixed by a ✓ or ✗ pill and linked to the relevant Operations-row page. Wraps on narrow viewports. |
| **2** (draft, not yet validated) | (no detail) |
| **3** (draft + validation errors) | **Validation issues** — error / warning / info count pills inline, followed by the per-issue list (rendered by `operator/partials/_next_action_issue_list.html`). |
| **4** (validated, no warnings, no invites) | **Status** — "Setup validated." |
| **4W** (validated + warnings) | **Status** — "Setup validated." followed by a per-warning pill row + the per-issue list inline, so the operator sees what they're about to acknowledge before clicking the detour. |
| **4Err** (validated + errors, defensive) | Same shape as State 3 — **Validation issues** + pill row + per-issue list. |
| **5** (validated + invites generated) | Same as State 4 — **Status** — "Setup validated." |
| **6** (validated + invites sent) | Same as State 4 — **Status** — "Setup validated." |
| **7** (ready, no invitations yet) | (no detail) |
| **8** (ready, invites generated) | (no detail) |
| **9** (ready, invites sent) | (no detail) |
| **10** (expired) | (no detail) |

States 5 / 6 currently share State 4's status block; an
invite-counter / deadline aside can land as a follow-up.
States 7 / 8 / 9 / 10 have no detail block yet — invitation-status
counters + a "closed at «X»" stamp are deferred.

### Signal lines

All signal lines live inside a `.next-action-signals` flex column
beneath the per-state status detail. Each line is a
`.next-action-signal.next-action-signal--<tone>` paragraph with a
leading `.next-action-signal-icon` span. No banner background, no
border — the icon tone carries the urgency cue:

| Tone | Icon | Meaning |
| --- | --- | --- |
| `error` | ✗ (error colour) | Workflow failure (Prepare or Activate). |
| `amber-warning` | ⚠ (warning colour) | Caption is configured but precondition not yet met. |
| `amber-grey` | ⓘ (muted text colour) | Caption is configured but inert (anchor-null, or post-skip one-shot). |
| `green` | ✓ (success colour) | Caption is effective (will fire / dispatch as scheduled). |

Lines render in this top-to-bottom order: failure first (most
urgent), then scheduled-activation, then auto-send invites, then
auto-send reminders.

#### Workflow-failure signal

Renders when `super_failure` is populated (i.e. the page was hit
with `?super_status=failed&super_button=<prepare|activate>&super_step=<step>&super_error=<msg>`).
Bold headline: **"Prepare session failed at the <step>."** or
**"Activate session failed at the <step>."** — the button name
comes from `super_failure.button`, and the step maps via
`_step_label_map` (`generate` → "Generate assignments",
`validate` → "Validate setup", `activate` → "Activate session",
`precondition` → "pre-flight check"). The error detail (when
present) renders inline below the headline. State 3 / 4Err
issue lists continue to render in the per-state detail block —
the failure signal doesn't suppress them.

#### Scheduled-activation signal

Built by `views.build_scheduled_activation_caption` from session
state × `sessions.scheduled_activate_at` (the operator-set Start
anchor):

| Session state | `scheduled_activate_at` | Signal |
| --- | --- | --- |
| `draft` | unset | (none) |
| `draft` | set, in future | ⚠ "Scheduled activation at «X» — currently inactive: Prepare session before then or the schedule will skip." |
| `draft` | set, in past (after a skip) | ⓘ "Scheduled activation at «X» skipped — session was not validated." One-shot, clears on next operator interaction. |
| `validated` | unset | (none) |
| `validated` | set, in future | ✓ "System will auto-activate at «X». You can also click Activate now." |
| `ready` | (any — moot post-activation) | (none — the existing "Activated at «X»" treatment covers it) |

See `guide/archive/segment_18G_scheduled_events.md` Part 1 for the
service-side contract (editor gate, persistence across
invalidation, fire-time skip semantics).

#### Auto-send invites signal

Built by `views.build_auto_send_invites_caption` from
`sessions.invite_offsets` + `scheduled_activate_at` + session
state + whether any `Invitation` rows exist. Two preconditions
gate the trigger:

- **Prepared** — `session.status` is `validated` or `ready`. The
  trigger refuses to dispatch from `draft` because manual Send
  also refuses (via the operator route's
  `_require_validated_or_ready` gate). The skip reason is
  `not_prepared`.
- **Invitations created** — at least one `Invitation` row exists
  for the session. The skip reason is `invitations_not_created`.

| `invite_offsets` | `scheduled_activate_at` | Prepared? | Invitations created? | Signal |
| --- | --- | --- | --- | --- |
| empty / null | (any) | (any) | (any) | (none) |
| set | unset | (any) | (any) | ⓘ "Auto-send invites are configured but currently inactive — no Start to anchor against. They reactivate when Start is re-set." |
| set | set | no (draft) | (any) | ⚠ "Auto-send scheduled at «X» — currently inactive: Prepare session before then or these will skip." |
| set | set | yes | no | ⚠ "Auto-send scheduled at «X» — currently inactive: create invitations before then or these will skip." |
| set | set | yes | yes | ✓ "Auto-send scheduled at «X». System will dispatch automatically; you can also Send all now." |

#### Auto-send reminders signal

Built by `views.build_auto_send_reminders_caption` from
`sessions.reminder_offsets` + `deadline` + session state +
whether any `Invitation` rows exist. Two preconditions gate the
trigger:

- **Prepared + activated** — `session.status == "ready"`. This
  subsumes the auto-send-invites "Prepared" condition; reminders
  fire only after the session has opened.
- **Invitations created** — reminders piggyback on existing
  `Invitation` rows (each reminder reuses the previously-issued
  invitation URL), so the trigger requires invitations to be
  **created**, not necessarily sent. The skip reason is
  `no_invitations`.

| `reminder_offsets` | `deadline` | Session `ready`? | Invitations created? | Signal |
| --- | --- | --- | --- | --- |
| empty / null | (any) | (any) | (any) | (none) |
| set | unset | (any) | (any) | ⓘ "Auto-send reminders are configured but currently inactive — no End to anchor against. They reactivate when End is re-set." |
| set | set | no | (any) | ⚠ "Auto-send reminders scheduled at «X» — currently inactive: activate the session before then or these will skip." |
| set | set | yes | no | ⚠ "Auto-send reminders scheduled at «X» — currently inactive: create invitations before then or these will skip." |
| set | set | yes | yes | ✓ "Auto-send reminders scheduled at «X». System will dispatch automatically; you can also Send reminders to incomplete now." |

### Manual-activate cancellation modal

Drives a browser confirm dialog on the Activate button, not a
right-column signal. The `manual_activate_cancellation` context
key is populated when a manual Activate click would cancel
pending auto-sends — i.e. when `scheduled_activate_at` is set in
the future or one or more `invite_offsets` entries still resolve
to a future fire moment. Payload: a count, a list of pending-fire
labels, and the prose ("N scheduled auto-send(s) will be
cancelled. Continue with manual activation?"). On confirm, the
existing `/workflow/activate` POST runs and `scheduled_activate_at`
clears in the same transaction; `invite_offsets` stays on the
column but becomes inert via the §8.2.2 anchor-null rule (per
`spec/lifecycle.md`).

## POST routes

Quick reference. Every action ultimately resolves to one of these
routes:

| Route | Service | Allowed prior state | Resulting state | Audit event |
| --- | --- | --- | --- | --- |
| `POST /operator/sessions/{id}/workflow/prepare` | `assignments.replace_assignments` → `lifecycle.mark_validated` (on clean Validate) | `draft` or `validated` (`is_editable`) | `validated` (or `draft` on Validate errors; detour to host page with `prepare_confirm=responses` in the saved-response case) | `session.workflow_run_started` with `context.button="prepare_session"` + per-step events; `session.workflow_run_failed` on failure |
| `POST /operator/sessions/{id}/workflow/activate` | `lifecycle.activate_session` (re-validates first) | `validated` | `ready` (or detour to Validate page in the warnings case) | `session.workflow_run_started` with `context.button="activate_session"`; `session.workflow_run_failed` on failure |
| `POST /operator/sessions/{id}/workflow/close` | `lifecycle.close_session` | `ready` | `expired` (every instrument flips `accepting_responses = False`) | `session.closed` |
| `POST /operator/sessions/{id}/workflow/release-responses` | `lifecycle.release_responses_now` | not `archived` | unchanged (stamps `responses_release_at = now()`, clears `responses_release_until`) | `session.responses_released` |
| `POST /operator/sessions/{id}/workflow/stop-release` | `lifecycle.stop_responses_release` | not `archived` | unchanged (stamps `responses_release_until = now()`) | `session.responses_release_stopped` |
| `POST /operator/sessions/{id}/workflow/archive` | `lifecycle.archive_session` | any non-archived state | `archived`; 303 → `/operator/sessions/archived` | `session.archived` |
| `POST /operator/sessions/{id}/assignments/generate` | `assignments.replace_assignments` | `draft` or `validated` | unchanged | `assignments.generated` |
| `POST /operator/sessions/{id}/activate` | `lifecycle.activate_session` | `validated` | `ready` | `session.activated` |
| `POST /operator/sessions/{id}/revert` (when `is_validated`) | `lifecycle.invalidate_session` | `validated` | `draft` | `session.invalidated` |
| `POST /operator/sessions/{id}/revert` (when `is_ready` or `is_expired`) | `lifecycle.revert_session_to_draft` | `ready` or `expired` | `draft` | `session.reverted_to_draft` |
| `POST /operator/sessions/{id}/invitations/generate` | `invitations.generate_invitations` | `validated` or `ready` (via `_require_validated_or_ready`) | unchanged | `invitations.generated` |
| `POST /operator/sessions/{id}/invitations/send-all` | `invitations.send_invitation` (per pending) | `validated` or `ready` | unchanged | per-invitation send events |
| `POST /operator/sessions/{id}/invitations/remind-incomplete` | `invitations.send_reminders_to_incomplete` | `ready` | unchanged | per-reminder send events |

The per-step `/assignments/generate` and `/activate` routes
remain alive even though the Workflow card no longer POSTs to
them directly. `/activate` is load-bearing for the Validate
page's warnings-detour banner; `/assignments/generate` has no UI
consumer but stays as a small surface for direct callers (test
fixtures, programmatic-validate hooks).

All `/activate` and `/revert` routes honour the form field
`return_to` against the `_REVERT_RETURN_TO` allowlist and 303 to
the corresponding child page; values outside the allowlist
(including `home`) 303 to `/operator/sessions/{id}`.

## Source-of-truth pointers

- Partial: `app/web/templates/operator/partials/next_action_card.html`
- Right-column issue list partial:
  `app/web/templates/operator/partials/_next_action_issue_list.html`
- Context builder: `app/web/views/_workflow_card.py`
- Prepare + Activate routes: `app/web/routes_operator/_workflow.py`
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
