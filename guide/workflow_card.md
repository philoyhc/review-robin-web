# Next Action card — behavior on the Assignments page

This note documents the actual current behavior of the "Next Action"
card as rendered on the Assignments page
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
`next_action_return_to = "assignments"` so that the Validate Setup
link, the Activate / Revert / Pause forms, and the warnings-detour
Activate link all land back on Assignments instead of Session Home.

## Inputs the card reads

`_render_assignments_hub` (`_assignments.py:178-194, 212-222`) passes
these context keys to the partial:

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
- `validation_summary` — `dict | None`. Populated whenever the page
  was reached with `?validated=1` OR the session is already
  `validated`. Keys:
  - `error_count`, `warning_count`, `info_count` — from the readiness
    report.
  - `can_activate` — `report.can_activate AND is_validated(session)`.
  - `needs_acknowledge` — `report.has_non_blocking_findings`.
- `next_action_return_to` — hard-coded `"assignments"` on this page.

`?validated=1` (the Validate Setup link target) makes
`assignments_hub` run `validate_session_setup` live; if the report is
clean and the session is still in draft, it calls
`lifecycle.mark_validated`, promoting `draft → validated` before the
page renders.

## States and rendered buttons

The card has a constant frame (H2 "Next Action" + blue-bordered card).
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
elif is_ready:             → State 6
```

The bottom button row is only emitted when the session is not
`is_setup_empty` and not `is_ready` — State 6 ships its own buttons
inline within the body (see below).

### State 1 — Setup not yet populated (`is_setup_empty`)

Triggered while the session is in `draft` and any of the following
holds: the reviewer roster is empty, the reviewee roster is empty,
or at least one instrument has no assignment rule pinned (i.e.
`Instrument.rule_set_id IS NULL`). A session with zero instruments
also lands here.

Body copy: *"Session not fully set up. Make sure that reviewers,
reviewees, and relationships (optional), and instruments have been
set up before continuing."*

Buttons: none. (Bottom button row is suppressed by the
`not is_setup_empty and not is_ready` guard at `next_action_card.html:166`.)

### State 1A — Draft, ready to generate (`is_pre_generate`)

Triggered while the session is in `draft`, `is_setup_empty` is `False`
(rosters populated, every instrument has its rule pinned), AND either
no `Assignment` rows have been generated yet OR the session was
reverted to draft (via Revert from `validated` or Pause from `ready`)
after the most recent generation — i.e.
`lifecycle.needs_regeneration_after_revert(db, session_id)` returns
`True`. Reverted sessions land here even though their old assignment
rows still exist, since post-revert the operator typically needs to
regenerate before validating.

Body copy: *"Run generation to create the assignment pairs (note
that doing so will replace any previously generated assignment
pairs)."*

A hidden form `id="next-action-generate-form"` is emitted in the body
posting to `/operator/sessions/{id}/assignments/generate`. The
Generate assignments button below is a
`<button type="submit" form="next-action-generate-form">`.

Buttons:

| Label | Style | Method | Target |
| --- | --- | --- | --- |
| **Generate assignments** | Primary submit | POST | `/operator/sessions/{id}/assignments/generate` (form `next-action-generate-form`) |

POST `/assignments/generate` calls `assignments.replace_assignments`,
materialising one `Assignment` row per `(reviewer, reviewee, instrument)`
triple eligible under the pinned `SessionRuleSet`. Because
`is_pre_generate` requires `existing_count == 0`, no `confirm_replace`
field is needed in this state. Redirect always lands on
`/operator/sessions/{id}/assignments` — the route does not honour
`return_to`, so operators on Session Home end up on Assignments after
the action fires.

### State 2 — Draft, validation not yet run (`is_draft`, no summary)

Body copy: *"Run validation to surface errors and warnings before
activating. Validation never mutates session data."*

Buttons:

| Label | Style | Method | Target |
| --- | --- | --- | --- |
| **Validate Setup** | Primary `<a>` | GET | `/operator/sessions/{id}/assignments?validated=1` |
| **See validation details** | Secondary `<a>` | GET | `/operator/sessions/{id}/validate` |

Validate Setup re-enters this same route with `validated=1`, which
runs validation and (if clean) auto-promotes `draft → validated`
before re-rendering — so the operator typically lands in State 4A or
State 4B on the next paint. If validation fails, they land in State 3.

### State 3 — Draft, validation failed (`is_draft` + `validation_summary`)

Body copy:

- *"Validation didn't pass."*
- Three pills, one each for error / warning / info counts
  (`error_count`, `warning_count`, `info_count`).
- *"Resolve the errors and re-run validation before activating."*

Buttons: same as State 2 (Validate Setup + See validation details).

### State 4A — Validated, no warnings (`is_validated`, `can_activate`, not `needs_acknowledge`)

Body copy: *"The session setup data has successfully validated.
Preview the reviewer surface to make sure that it conforms to your
requirements before activating."*

A hidden form `id="next-action-activate-form"` is emitted in the body
posting to `/operator/sessions/{id}/activate` with a hidden
`return_to=assignments`. The Activate Session button below is a
`<button type="submit" form="next-action-activate-form">`.

A second hidden form `id="next-action-revert-form"` is emitted
posting to `/operator/sessions/{id}/revert` with the same hidden
`return_to`. The Revert to draft button targets that form.

Buttons:

| Label | Style | Method | Target |
| --- | --- | --- | --- |
| **Activate Session** | Primary submit | POST | `/operator/sessions/{id}/activate` (form `next-action-activate-form`) |
| **See validation details** | Secondary `<a>` | GET | `/operator/sessions/{id}/validate` |
| **See previews** | Secondary `<a>` | GET | `/operator/sessions/{id}/previews#reviewer-surface` |
| **Revert to draft** | Secondary submit | POST | `/operator/sessions/{id}/revert` (form `next-action-revert-form`) |

POST `/activate` calls `lifecycle.activate_session(...,
acknowledge_warnings=False)`, transitioning `validated → ready`,
flipping every instrument's `accepting_responses = True` (and clearing
`deadline_closed_at`), and emitting the `session.activated` audit
event. Because `return_to=assignments` is in the allowlist
`_REVERT_RETURN_TO = {"reviewers", "reviewees", "assignments",
"instruments"}`, the 303 redirect lands back on Assignments.

POST `/revert` against a `validated` session dispatches to
`lifecycle.invalidate_session(..., reason="operator_revert")`,
transitioning `validated → draft` and emitting `session.invalidated`.
No confirm checkbox is required in this branch. Redirect goes back to
Assignments.

### State 4B — Validated, warnings to acknowledge (`needs_acknowledge`)

Body copy: same opening paragraph as State 4A, plus a help line:
*"{N} warning(s) — review on Validate before activating."*

No `next-action-activate-form` is emitted in this branch — the
Activate button is an `<a>` instead, deliberately detouring through
the Validate page so the operator sees the warnings inline before
confirming.

Buttons:

| Label | Style | Method | Target |
| --- | --- | --- | --- |
| **Activate Session** | Primary `<a>` | GET | `/operator/sessions/{id}/validate?activate=1&return_to=assignments` |
| **See validation details** | Secondary `<a>` | GET | `/operator/sessions/{id}/validate` |
| **See previews** | Secondary `<a>` | GET | `/operator/sessions/{id}/previews#reviewer-surface` |
| **Revert to draft** | Secondary submit | POST | `/operator/sessions/{id}/revert` (form `next-action-revert-form`) |

The Validate page, when reached with `activate=1`, surfaces the
warnings inline and renders an "Acknowledge and activate" submit that
POSTs `/activate` with `acknowledge_warnings=true` and the same
`return_to`. `lifecycle.activate_session` refuses to transition unless
`acknowledge_warnings=True` when the report has non-blocking findings.

### State 5 — Validated, errors block activation (`is_validated`, not `can_activate`)

This can happen if data changed under a `validated` session and a
re-validation now surfaces errors — the session is still in the
`validated` state but the readiness report says it cannot activate.

Body copy: *"Validation shows that there are error(s). Resolve them
and re-run validation before activating."*

Activate Session is dropped. **See validation details** is promoted
from Secondary to Primary as the single forward action.

Buttons:

| Label | Style | Method | Target |
| --- | --- | --- | --- |
| **See validation details** | Primary `<a>` | GET | `/operator/sessions/{id}/validate` |
| **Revert to draft** | Secondary submit | POST | `/operator/sessions/{id}/revert` (form `next-action-revert-form`) |

### State 6 — Activated (`is_ready`)

The body is split into two sections by an `<hr class="next-action-divider">`,
and the buttons live inline within the body — the outer bottom button
row is suppressed by the `not is_ready` guard at line 166.

**Section 1 — Invitations / monitoring.**

Body copy: *"Session is currently activated. Reviewers can access
forms and save responses. Don't forget to generate and send out emails
to notify the reviewers."*

| Label | Style | Method | Target |
| --- | --- | --- | --- |
| **Manage invitations** | Primary `<a>` | GET | `/operator/sessions/{id}/invitations` |
| **Monitor responses** | Secondary `<a>` | GET | `/operator/sessions/{id}/monitoring` |

**Section 2 — Pause.**

Body copy: *"Pausing returns the session to draft and stops reviewers
from submitting new responses. Existing responses will be preserved."*

A hidden form `id="next-action-pause-form"` posts to
`/operator/sessions/{id}/revert` with `return_to=assignments` and a
required checkbox `name="confirm" value="true"` labeled *"Yes, pause
**{session name}** and return to draft."*. The Pause Session button is
a `<button type="submit" form="next-action-pause-form">`.

| Label | Style | Method | Target |
| --- | --- | --- | --- |
| **Pause Session** | Primary submit | POST | `/operator/sessions/{id}/revert` (form `next-action-pause-form`, requires `confirm=true`) |

POST `/revert` against a `ready` session dispatches to
`lifecycle.revert_session_to_draft(..., confirm=confirm == "true")`,
which:

- Refuses the call unless `confirm` is `True`.
- Transitions `ready → draft`.
- Flips every instrument's `accepting_responses = False`.
- Emits `session.reverted_to_draft`.
- Preserves all reviewer responses (does not delete).

Redirect lands back on Assignments.

## Quick reference: what each POST route does

| Route | Service entry | Allowed prior state | Resulting state | Audit event | Required form field |
| --- | --- | --- | --- | --- | --- |
| `POST /operator/sessions/{id}/activate` | `lifecycle.activate_session` | `validated` | `ready` | `session.activated` | `acknowledge_warnings=true` iff report has non-blocking findings |
| `POST /operator/sessions/{id}/revert` (when `is_validated`) | `lifecycle.invalidate_session` (reason `operator_revert`) | `validated` | `draft` | `session.invalidated` | — |
| `POST /operator/sessions/{id}/revert` (when `is_ready`) | `lifecycle.revert_session_to_draft` | `ready` | `draft` | `session.reverted_to_draft` | `confirm=true` |

All three honour the form field `return_to` against the allowlist
`{"reviewers", "reviewees", "assignments", "instruments"}` and 303 to
the corresponding child page; on the Assignments page that field is
always `"assignments"`.
