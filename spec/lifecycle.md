# Session lifecycle — spec

**The state machine and gating contract that govern every session
mutation.** Five live states (`draft`, `validated`, `ready`,
`expired`, `archived`) — every one of them written by a service in
`app/services/session_lifecycle.py`, none reserved — the
transitions between them, the route + service gates that enforce
them, and the UI lock-card pattern that exposes them to
operators.

This spec is the single source of truth for the lifecycle. Each
per-page spec referencing it should describe only what's
specific to that page; common state-machine rules live here.

Cross-references:

- **`app/services/session_lifecycle.py`** — implementation.
- **`spec/architecture.md`** "Session lifecycle" — the write-path
  narrative at architectural altitude. This spec wins over it and
  over every per-page spec's "lifecycle gating" sub-section.
- **`spec/visual_style_rrw.md`** "Warning surfaces — shared
  brown framing" — visual treatment of the lock card.
- **`spec/operator_ui_concept.md`** principle **P4** —
  *Lifecycle disables, never hides.*

---

## 1. State machine

```
        Prepare session           Activate Session         Close session
   ┌─────────────────────→  ┌───────────────────────→  ┌──────────────→
draft                    validated                    ready           expired
   ←─────────────────────┘  ←───────────────────────┐  ←──────────────┘
   ↑    invalidate              Revert to draft       Revert to draft
   │    (any setup mutation)     (with confirm)
   │
   └──── unarchive ──── archived ←──── archive (from any non-archived state)
```

| State | Display label | Meaning |
|---|---|---|
| `draft` | Draft | Setup is open; reviewer surface read-only. |
| `validated` | Validated | Readiness check passed; setup still open but signals "ready to activate". |
| `ready` | **Activated** | Reviewer surface accepting writes; setup locked. |
| `expired` | Closed | Session closed by the operator's Workflow-card **Close session** button (`ready → expired`, `expire_session`), or by the review's end passing: End, or with no End, Release responses from (`session_lifecycle.review_end`; `observe_deadline`, §4). Every instrument is closed; responses (drafts + submitted) are preserved. From `expired` the operator can Revert to draft (`revert_session_to_draft`) to reopen for editing. |
| `archived` | Archived | Filed out of the active lobby; deletes no data. Written by `archive_session` / `unarchive_session`. `archive_session` accepts **any non-archived** starting state (draft / validated / ready / expired), so the Workflow card's `/workflow/archive` route can fire from any state, though the card renders its Archive button only in `expired` (`archive_visible`); the lobby's **Purge and archive** and the Extract data page's Archive card both go through `session_purge.purge_and_archive`, which skips any session failing `can_archive` (so `draft`, `validated` and `expired` archive, and `ready` does not). `archive_session` sets `accepting_responses=false` on every instrument in the same transaction, as every other exit from `ready` does, so `unarchive_session`, which restores `archived → draft`, lands with nothing accepting. |

The internal enum is `SessionStatus` in
`app/services/session_lifecycle.py`. The display-label divergence
on `ready → "Activated"` is implemented by
`app/services/lifecycle_display.py::lifecycle_display_label`
(registered as the Jinja filter `lifecycle_label`) and applied
to every operator-facing surface; the enum value remains `ready`
in URLs, logs, audit events, and CSS classes.

**Helpers:**

| Function | Returns |
|---|---|
| `is_draft(session)` | session is `draft` |
| `is_validated(session)` | session is `validated` |
| `is_ready(session)` | session is `ready` |
| `is_expired(session)` | session is `expired` |
| `is_archived(session)` | session is `archived` |
| `is_editable(session)` | session is `draft` OR `validated` (the **editable-state predicate** that every route-layer gate consults) |
| `can_archive(session)` | session is **not** `ready` and **not** `archived` — the shared gate for the lobby "Purge and archive" and the Extract-data page's Archive card |

## 2. Transitions

Each transition is one service function in
`app/services/session_lifecycle.py`. All transitions emit a
single audit event and commit atomically. Each locks and re-reads the
session row before testing its precondition (§8.3, *Concurrency
safety*). One qualification: the automatic `validated → draft` flip
(§2.3) does not commit. It lands in its caller's commit, or in the one
commit of a route's `unit_of_work.single_commit` (the Instrument card's
Save), and is rolled back with it when that Save is refused
(`spec/instruments.md`, *Action row*). Only the operator's Revert
(§2.2) commits the flip alone.

### 2.1 `draft → validated` — `mark_validated(...)`

Called only by `POST /operator/sessions/{id}/workflow/prepare` — the
Workflow card's Prepare button runs Generate + Validate + Invite and flips
`draft → validated` on a clean report. Idempotent (no-op when
already `validated`). Raises `LifecycleError(code="has_errors")`
when the readiness report carries blocking errors.

- Warnings are implicitly acknowledged at the moment of
  transition (info-severity findings are advisory only — they
  don't trigger the acknowledgment ceremony).
- Audit event: `session.validated` with
  `counts={"warnings": N, "info": N}`. The Prepare-button run
  brackets with `session.workflow_run_started/_failed`
  carrying `context.button="prepare_session"`; the Activate
  run does the same with `"activate_session"` (see
  `spec/workflow_card.md`).

### 2.2 `validated → draft` — `invalidate_session(...)`

The explicit form, reached only through `operator_revert` (§2.6), and
the one `validated → draft` flip that commits on its own (through
`unit_of_work.commit`). Idempotent (no-op when already `draft`). Raises `LifecycleError(code="not_validated")` when the session
is in any other status.

- Reason string is required at the call site and surfaces in the
  audit event's `reason` slot.
- Audit event: `session.invalidated` with `reason=<string>`.

### 2.3 `validated → draft` — `invalidate_if_validated(...)`

The **automatic** form, called from every service that mutates what
the readiness check reads. No-op for any status other than
`validated`. The key invariant: **any setup mutation that could change
the check's verdict invalidates a prior validated state**, so the
readiness check stays meaningful.

**The rule:** every service that mutates what the readiness check
reads — rosters (per-row, bulk and CSV import),
relationships, observers, instruments and their Band 1 links, fields
and pagination, visibility policies, field labels, assignment
generate, and the full settings import — calls
`invalidate_if_validated`. The Assignments page's include toggles
(per-row Inactivate / Activate and the per-instrument Self review
toggle) do not, and are allowed in `validated`. A list of call
sites goes stale with the next setup service;
`grep -rln invalidate_if_validated app/services` gives the current
one.

**The session's own Details do not.** `sessions.update_session`, behind
Session Home's Details card and the lobby expander's Save, leaves a
`validated` session `validated`: no field it writes can change the check's verdict. Name and code
are checked only for being present and the form requires both, help
contact adds an info note only, and the rest (description, deadline,
Start, offsets, the release window, the two Setup-tab toggles) are not
read. The other writes on those two forms do not invalidate either:
the timezone (`sessions.set_session_display_timezone`) and the tags
(`session_tags.set_tags`) are not checked, nor are owners.

The invariant lives at the **mutation site**, not the route, so a
route that forgets to wrap its service call cannot silently break
it.

**It flushes and does not commit, and takes no lock of its own.** The
calling service has already locked and re-read the row through
`require_editable` (§3.1), so the `validated` it tests is the committed
one, and the lock holds from that gate through the edit: a commit here
would release it before the edit landed. The flip, its
`session.invalidated` row and the edit therefore commit together. A
caller that fails after the flip and commits nothing loses the flip with
the edit; one that catches the failure and commits anyway commits the
flip too.

### 2.4 `validated → ready` — `activate_session(...)`

Called by `POST /operator/sessions/{id}/activate` and by
`POST /operator/sessions/{id}/workflow/activate` (the Workflow
card's solo Activate button). Flips the
session to `ready` and sets `accepting_responses=true` on every
instrument in the same transaction. Pre-conditions:

- Session is `validated`, as re-read under the session lock, so an
  Activate that lost a race to the scheduled trigger (or to another
  Activate) raises `not_validated` rather than activating twice.
  (Raises `not_validated`.)
- Readiness report still has no errors. (Raises `has_errors`.)
- If warnings exist, the operator must have set
  `acknowledge_warnings=true` on the request. (Raises
  `needs_acknowledge`.) The scheduled trigger (§8.2.3) passes
  `acknowledge_warnings=true` itself, so warnings never stop a
  scheduled activation.

Activation also clears `Instrument.deadline_closed_at` on every
instrument — a previously deadline-closed instrument re-opens. In
the same transaction it clears `scheduled_activate_at` (a manual
Activate and the scheduled trigger both consume the schedule) and
stamps `activated_at` if it is still NULL.

Audit event: `session.activated` with `counts={"warnings": N,
"info": N, "instruments": N}` and `context={"prev_status":
"validated", "override_warnings": bool, "trigger": "operator" |
"scheduled"}`.

### 2.5 `ready`/`expired → draft` — `revert_session_to_draft(...)`

The **Revert to draft** path. Called by `POST
/operator/sessions/{id}/revert`. Flips to `draft` and sets
`accepting_responses=false` on every instrument in the same
transaction. **Existing `Response` rows are preserved untouched**
— the reviewer surface returns to read-only, but the data is
intact.

Accepts both `ready` (the live mid-session pause) and `expired`
(the recovery path after the session was closed, by **Close session**
or by the review's end, and the operator wants to reopen it for
editing) as the starting state. A session reverted with an End, or with
no End a Release from, already in the past meets Validate's
`session.end_passed` (`spec/validate_page.md`) until that date is moved
or cleared, since activating would close it at once.

Pre-conditions:

- Session is `ready` or `expired`. (Raises `not_ready`.)
- The route layer passes `confirm=true` from the confirm
  checkbox. (Raises `needs_confirm`.)

Audit event: `session.reverted_to_draft` with
`counts={"closed_instruments": N, "responses_at_revert": N}`. No
per-instrument `instrument.closed` events fire on this path — the
single session-level event covers them.

### 2.6 Direct `validated → draft` (operator-initiated)

When the operator clicks the Workflow card's "Revert to draft"
while the session is `validated` (a `validated` session is editable,
so the Setup pages show no lock card and no revert form), the
`/revert` route calls `operator_revert`, which locks and re-reads the
session and then dispatches by that status, not the row loaded with the
request: `validated → draft` calls
`invalidate_session(reason="operator_revert")`. The `ready`/`expired →
draft` branch calls `revert_session_to_draft` instead (per 2.5). So a
scheduled activation that committed after the page loaded `validated`
is never overwritten with `draft`: the `validated` form sends no
`confirm`, so the `ready` branch refuses with `needs_confirm` (400) and
the session stays `ready`; the operator reverts from the page
re-rendered in `ready`, whose form confirms.

### 2.7 `ready → expired` — `expire_session(...)`

The "Close session" path. The review's end closes a session the same
way, unattended (`observe_deadline`, §4): `ready → expired` with no
actor, writing `session.expired` with `reason="deadline"` (End) or
`reason="release"` (no End, Release from), not through
`expire_session`.
 Called by `POST
/operator/sessions/{id}/workflow/close` — Row 2's **Close
session** button on the Workflow card. Flips `ready → expired`
and sets `accepting_responses=false` on every instrument in the
same transaction. **Existing `Response` rows are preserved
untouched** (drafts + submitted); whether a reviewer can still read
theirs after the close is the visibility policy's call
(`spec/reviewer-surface.md` "Lifecycle gating").

Pre-conditions:

- Session is `ready`. (Raises `not_ready`.)

From `expired` the operator reopens the session for editing via
Revert to draft (§2.5), which accepts `expired` alongside `ready`.

Audit event: `session.expired` with
`counts={"closed_instruments": N}`; the operator's close carries no
`reason`.

## 3. Route-layer gates

Route helpers enforce the state machine at the request boundary:
`_require_editable` and `_require_response_loss_ack` in
`app/web/routes_operator/_shared.py` (with `_require_not_ready`, the
Danger Zone's gate, described under §3.1), and the two invitation gates
in `app/web/routes_operator/_operations.py`.

### 3.1 `_require_editable(session)`

Raises **HTTP 409 Conflict** when the session is not `draft` or
`validated`. Operator setup-mutation endpoints (session edit,
roster import, roster delete-all, relationships CRUD, assignment
generate, etc.) call this **first**.

Six exceptions to that list, all easy to mis-read:

- **Quick Setup and the settings import do not call this helper.**
  Their handlers in `app/web/routes_operator/_quick_setup.py` test
  `lifecycle.is_editable` inline — the same predicate — and on failure
  return the `lifecycle` reason token, which the route turns into
  Session Home rendered again at 422 with the slot's lifecycle banner
  rather than a 409 (`spec/quick_setup_card_spec.md`, "Result
  reporting").

- **The lobby expander's Save (`{id}/lobby-edit`) does not call this
  helper either.** It tests `lifecycle.is_editable` inline — the same
  predicate, Session Home's — and off it **ignores** Name / Code /
  Deadline rather than refusing the post, so its always-editable Tags
  still save (`spec/sessions_overview.md`).

- **Instrument CRUD does not call this helper.** Its route
  sites call `_require_instrument_editable` →
  `_can_edit_instrument`, a separate helper carrying the *same*
  predicate (`is_editable`) and raising the same 409 with its own
  detail message. Same rule, different function — a change to one
  has to be made in the other.
- **The email-template editor refuses only `archived`**, through
  `email_templates.lock_for_edit` (`session_lifecycle.require_not_archived`
  under the session lock), so its copy stays editable through `ready`
  and `expired`; §5 states the same.
- **The Observers roster calls `_require_not_archived` instead**, a
  genuinely *wider* predicate rather than the same one under another
  name. **Every mutating route of its takes it** — `create`,
  `update`, `bulk-inactivate`, `bulk-reactivate`, `bulk-delete`,
  `delete-all`, `import`, `cohort-rule` and `self-fields` — so the
  roster accepts through `ready` and `expired` and 409s only on
  `archived`. §5
  carries the reason, and the rule that governs a second such
  exception.
- **Session Home's Delete Data and Delete session call
  `_require_not_ready` instead** (`_shared.py`), which 409s only in
  `ready`, so both work on a `draft`, `validated`, `expired` or
  `archived` session. The lobby's bulk Delete
  accepts `draft`, `validated` and `expired` (`is_editable` or
  `is_expired`); archived sessions go through the archived page.

Detail message: `"Session is <status>; revert to draft to edit"`.

**The route helper is an early refusal; the service decides.** Every
service that writes a session's roster, relationships, assignments,
instruments, visibility policies or own settings, the delete
services, and the operator's invitation sends, regenerates and
reminders, opens with a wrapper in `app/services/session_lifecycle.py`
over `session_guard.require_state`, which locks the row (`SELECT … FOR NO
KEY UPDATE`, `populate_existing`) and re-reads it:

| Wrapper | Refuses | `code` |
|---|---|---|
| `require_editable` | not `draft`/`validated` | `not_editable` |
| `require_not_archived` | `archived` (the Observers roster) | `archived` |
| `require_not_ready` | `ready` (Delete Data, Delete session) | `session_ready` |
| `require_validated_or_ready` | not `validated`/`ready` (invitation Send and Regenerate, per row and bulk, §3.3) | `not_prepared` |
| `require_ready` | not `ready` (reminders, per row and bulk, §3.4) | `not_ready` |
| `require_accepting_responses` | not `ready`, or past the deadline (the reviewer's Save, Submit, Clear and Recall, §8.3) | `not_accepting_responses` |

A refusal raises `SessionStateConflict`, a `LifecycleError`, which an
app-level handler (`app/web/error_handlers.py`) renders as the same 409
page, so a route needs no `try`. The service check is on the committed
status and can only refuse more than the route's, which stays as the
cheap first answer. The lobby's bulk Delete skips a row the guard
refuses, as it skips a `ready` one up front.

**The wait for the lock is bounded** on Postgres (`LOCK_TIMEOUT_MS`,
5 s; `docs/database.md`, "The session lock and its timeout"). A request
still waiting then raises `SessionBusy`, which is not a
`SessionStateConflict`: the state did not refuse. An app-level handler
renders it as the 409 page, "Someone else is changing this session right
now. Try again in a moment.", from operator and reviewer routes alike;
the reviewer's Save, Submit, Clear and Recall do not turn it into their
in-form refusal banner (accepted 2026-11-01: the wait means an operator
held the session for over 5 s). Prepare's failure record names it as an
unexpected error.

### 3.2 `_require_response_loss_ack(db, session, ack)`

Raises **HTTP 400 Bad Request** when responses already exist and
the request didn't carry `acknowledge_response_loss=true`. Called
from routes whose mutations would invalidate stored reviewer
responses: reviewer and reviewee delete-all, assignment Generate, and
Quick Setup's roster and settings replaces (which answer `needs_confirm`
rather than 400). The Reviewers and Reviewees Setup-page CSV import
(`roster_import.py` `_handle_import`) applies the same gate inline and
answers its 400 in the upload card's banner rather than an error page
(`spec/setup_pages.md`).
A change that clears group answers is a second gate, not this one: it
asks through `acknowledge_response_loss=<N>`, below.

**Delete Data does not call it**: its own confirm tick names the loss
("Yes, delete every reviewer response on …") and is the
acknowledgement. Delete session does not
call it either; its tick ("Yes, delete <name> and all its data")
confirms the whole deletion.

Detail message: `"Existing reviewer responses will be discarded;
tick 'acknowledge response loss' to proceed"`.

**The four roster bulk-deletes call a narrower variant**,
`_require_selected_response_loss_ack` (`_shared.py`). It counts the
responses on the selected rows' cascade (`roster_bulk.cascade_counts`)
and raises the 400 only when that count is non-zero and the request
lacks `acknowledge_response_loss=true`; its detail names the number
("Deleting the selected rows will discard N saved responses; …").
Observers and Relationships cascade to no response, so on those two
pages it never fires.

**The group-clear gate.** A group instrument's subject is the group, so
a Save that adds a member to a group deletes that group's answers
(`responses.clear_changed_groups`, `spec/assignments.md` "Group-scoped
fan-out"); a group that only shrank keeps its answer. Every operator Save
that would do so refuses, persists nothing, and offers itself again with
"This change clears N saved responses on groups whose members it changes."
(singular at one) and a `Yes, clear them` tick. The tick's value is the
count it showed, sent as `acknowledge_response_loss=<N>`, never `true`, so
a stale tick cannot approve a different clear. The service parameter
`acknowledged_loss: int | None` raises `GroupAnswersWouldClear(count)`
(`app/services/responses/_group_reconciliation.py`) unless it equals the
rows the change would delete; the route rolls back and re-renders. A
count of zero never asks. `None`, the default, deletes without asking:
Generate, Rehydrate, and every other service caller that is not an
operator Save. The cascade gate above never applies here, and a
reviewee delete only shrinks groups, so it keeps its own gate unchanged.

Twelve routes carry it. Surfaces and ticks are in `spec/setup_pages.md`
§ *Saves that clear group answers* and `spec/instruments.md` § *Action row*.
Quick Setup's Relationships slot refuses with its own sentence and no
tick, since its card is locked whenever answers exist
(`spec/quick_setup_card_spec.md` "Result reporting").

| Route | Refusal |
|---|---|
| `POST …/instruments/{iid}/save` | 422 JSON with `confirm_group_clear`; the card's banner adds the tick |
| `POST …/instruments/{iid}/fields/save` | bare 422 `HTTPException` carrying the line; no re-offer |
| `POST …/reviewees/{id}/update` | 400, row editor re-rendered |
| `POST …/relationships/create` and `…/relationships/{id}/update` | 400, row editor re-rendered |
| `POST …/relationships/import` | 400, upload card re-rendered |
| `POST …/relationships/delete-all` | 400, Danger Zone re-rendered; the page's own form sends the count its tick named, so this is a post with no count or a stale one |
| `POST …/relationships/bulk-inactivate`, `bulk-reactivate`, `bulk-delete` | 400, page re-rendered with the selection kept |
| `POST …/quick-setup/submit-all` and `…/quick-setup/relationships` | 422, Session Home re-rendered with the slot's banner; no tick |

### 3.3 `_require_validated_or_ready(session)`

Raises **HTTP 409 Conflict** when the session is `draft`
(invitation actions need at least the assignment pairs to be
settled). The invitation routes that issue or send a link in
`app/web/routes_operator/_operations.py` call it: per-row `send` and
`regenerate`, and bulk `send-all` and `regenerate-all`. (Prepare, which
creates the invitations, is gated by its own `is_editable` precondition
rather than this one.) It is deliberately looser than "ready only" so
an operator can notify reviewers **before** activation (the Prepared /
pre-open scenario); a reviewer who follows an early link lands on the
pre-open page. The bulk sends are separately off behind `RRW_BULK_SEND`
(§3.5).

Detail message: `"Invitations can only be issued once the
session has been prepared (validated or ready)."`

### 3.4 `_require_ready(session)`

The stricter invitation gate, in the same module: per-row `remind`
and the bulk `remind-incomplete` answer **409** outside `ready`, since
a reminder is about a review that is open.

Detail message: `"This action is available only once the session is
Activated."`

Both route helpers are early refusals on the loaded row, as in §3.1:
the invitation services (`app/services/invitations.py`) decide under
the session lock with `require_validated_or_ready` / `require_ready`,
so a Revert or a close committing after the page loaded is refused
rather than mailed past. The bulk Send and the bulk reminder commit
once, after every row, so that lock holds through the batch. The
corresponding GET pages render read-only banners, but the source of
truth is the service gate.

A per-row Send is also refused unless the invitation is still `pending`
(checked under the lock): a second click would mint a new link and kill
the first. The route answers with `?email=already_sent` on Invitations.

### 3.5 `_require_bulk_send()`

The bulk invitation routes (`send-all`, `remind-incomplete`) answer
**409** while `RRW_BULK_SEND` is off (default off,
`docs/deployment.md`), whatever the session's state; the buttons render
disabled, so only a direct POST reaches it. Per-row Send and Send
reminder are not bulk and are not held by it. The gate order on a bulk
route is the flag, then §3.3 or §3.4.

## 4. Per-instrument lifecycle

Each instrument carries an `accepting_responses` flag. It is set and cleared
session-wide, below, so within a `ready` session every instrument is
open or every instrument is closed.

| Column | Type | Meaning |
|---|---|---|
| `accepting_responses` | `Boolean` | Reviewers can save / submit. **Session-wide in practice:** set on every instrument by activate, cleared on every instrument by revert, Close session, archive and the close at the review's end. No operator control sets it per instrument. |
| `deadline_closed_at` | `DateTime \| None` | Timestamp the close at the review's end fired. Read by `observe_deadline`, which skips an instrument already stamped, and by `closed_at_deadline`, which tells the refused-save notice whether End closed the session; cleared by Activate and by a reopen while live (a `ready` session whose review end is unset or moved into the future). No surface renders it. |

What a reviewer reads back after close is the visibility policy's call
(`spec/reviewer-surface.md` "Lifecycle gating").

**Services:**

- **No per-instrument open or close.** Accepting is session-wide:
  `activate_session` opens every instrument (a group-scoped one
  included, since one with no stored Band 1 rule evaluates as the
  synthetic Full Matrix), and `revert_session_to_draft`,
  `expire_session`, `archive_session` and `observe_deadline` close
  them all. So once
  a session is activated, an instrument is never closed while another
  in it accepts (a settings import can set the flag per instrument,
  but only on an editable session, and activation then opens all),
  and the reviewer write gate (`spec/reviewer-surface.md`
  "Lifecycle gating") is session-wide with it.
- **The heal.** `observe_deadline`, which runs on every reviewer
  request, on the Instruments page and in the scheduled pass (§8.3), reopens any closed instrument
  while the session is `ready` and before the review's end, emitting
  `instrument.opened reason="session_wide"`; past it, it closes them
  instead. Nothing in the UI reopens a single instrument,
  and one left closed would make the gate refuse every write.
- **The review's end.** `review_end(session)` is End, or with no End,
  Release responses from; `None` when neither is set, and the review
  then runs until the operator closes it. Everything End governs follows
  it: the accept gate and Recall (`deadline_has_passed`), the
  `while_ongoing` visibility window (`is_ongoing`: `ready` and before
  the review's end) and the close below.
- `observe_deadline(...)` — the close at the review's end. Idempotent. Called
  on the reviewer surface — its GET (`review_surface` and
  `_surface_context`; the operator preview skips it), Recall, and the write gate
  `_write_refusal` ahead of save / submit / clear — by
  the operator Instruments page GET (`instruments_index`) and by the
  scheduled pass (§8.3). The
  predicate `session_accepts_responses` does not call it; it compares
  `now()` with the review's end itself (§4.1). The first trigger after the end
  passes, whichever it is, sets `accepting_responses=False`, stamps
  `deadline_closed_at`, emits one `instrument.closed` per instrument
  (`reason="deadline"`, `context.deadline`; with no End,
  `reason="release"`, `context.release_at`) and moves `ready → expired`,
  writing `session.expired` (no actor; `reason="deadline"` or
  `"release"`, same context, `counts.closed_instruments`). With a real
  End it also writes `session.deadline_reached`
  (`counts.submitted` of `counts.assigned` at that moment); a release that
  ends the review is not a deadline and writes none. The session closes
  also when its instruments were already shut (an earlier request
  closed them before the session closed), once. A release window set
  beforehand therefore opens unattended (§8.2.3).

### 4.1 The reviewer write-path predicate

`session_accepts_responses(session, instrument)` gates every
reviewer write (save / submit / clear). Returns `True` iff:

1. Session status is `ready`,
2. `instrument.accepting_responses` is `True`,
3. the review's end has not passed: `now() < review_end(session)` (or
   `review_end` is `None`).

POST routes (save / submit / clear) gate on it through
`_write_refusal`, which also refuses a session that isn't `ready` or
`expired` and a reviewer with no included assignment; a refusal is a
403 that renders the page again with the cause and what was typed
(`spec/reviewer-surface.md` "Lifecycle gating"). The reviewer-surface **GET** route branches
upstream of this check:

- If the session is `draft` or `validated`, the route renders the
  dedicated **pre-open page**
  (`reviewer/pre_open.html`) — "This review is not currently open."
  for both (participant audit M3), with the scheduled opening on
  a `validated` session, the deadline, and the help contact
  (`spec/reviewer-surface.md` "Pre-open page"). An `archived` session
  never reaches the route: the gate answers 404.
- If the review's end has passed, `observe_deadline` has already
  moved the session to `expired` (this request runs it first), and the
  surface renders read-only with the closed banner; the saved values
  render only inside a release window the policy grants
  (`spec/reviewer-surface.md` "Lifecycle gating"), since the
  `while_ongoing` window ends at the review's end (`is_ongoing`), also
  before the close has run.

See `spec/reviewer-surface.md` §"Lifecycle gating" for the full
GET-side rendering rules.

## 5. UI lock-card pattern

**On three of the four roster Setup pages** (Reviewers / Reviewees /
Relationships) whenever the session is **not editable** — i.e. not
`draft` and not `validated`: the mutating cards (Upload, Danger Zone)
are hidden and a **yellow lock card** renders in its place, explaining
that setup is locked and offering the way out that state has.
**Observers is a stated exception**, below.

**What is hidden is the same on all four pages.** The two destructive
cards, plus the tag-label editor on the three pages that have one, are
inside the roster card's **Unlock panel**, and it is the whole panel
that is suppressed.
Same predicate, one gate, and the Unlock control
itself goes with it: a locked page offers no way to open a panel
whose contents its routes would refuse. The tag-label editor has no
copy outside the panel; a locked page reads the labels from the
populated columns' headers and the roster index's pills.

**Observers uses a WIDER predicate.** Its mutating surface reads
`not is_archived`, so the roster stays editable through `ready` and
`expired` and only `archived` closes it. Every mutating route of its
takes `_require_not_archived`, so the page and its routes agree and
the surface is suppressed exactly where they refuse. §3.1 lists them.

The reason is what an observer *is*. They never appear in assignments
and never produce responses, and the readiness rules that read them
(`observers.duplicate_email`, `observers.cross_roster_identity`) check
only who the observer is, not anything the session's work depends on —
so freezing their roster at Activate protects nothing, while refining who
sees what mid-session is a legitimate flow. The lock card still
renders, on the archived-only condition, so it never contradicts a
live roster beneath it.

**§3.1's rule gets its mirror here.** Nothing may use a predicate
*narrower* than the lifecycle's, and nothing may use a **wider** one
either without saying why in this section. Observers is the only entry;
a second page claiming the exception without a reason stated here is a
defect, not a precedent. (Session Home's Danger Zone is not a Setup page
and carries its own wider gate, with its reason, in §3.1.)

All four render one partial,
`operator/partials/_roster_lock_card.html`, parameterized on the
sentence subject and the page's `return_to` slug. It branches
three ways, matching Instruments:

| State | Copy | Control |
|---|---|---|
| `ready` | "cannot be modified while the session is ongoing" | inline revert form |
| `expired` | "cannot be modified because the session is **closed**" | inline revert form |
| `archived` | "cannot be modified because the session is archived" | link to `/operator/sessions/archived`, **no control** |

`expired` displays as **Closed** to an operator
(`app/services/lifecycle_display.py`), so the copy says closed.
`archived` carries no revert form because `/revert` answers 409
from there and a button would be a dead control.

**Instruments answers to the same predicate** through its own
helper: `_require_instrument_editable` → `_can_edit_instrument`,
which is `lifecycle.is_editable(...)`. It must not be `not
is_ready`: that protects the surface only while the session is
*collecting* and stops the moment collection **ends**, so on
`expired` and `archived` the page would render live Delete buttons
over finished data — and deleting an instrument runs the
`Instrument` → `assignments` → `responses` cascade, taking
submitted answers with it. The page's `can_edit` reads the same
predicate, so page and route agree by construction.

`is_ready` still guards what it actually describes on that page:
the lock card's copy for a session that is collecting responses.

The page differs from the roster four in shape, not in gate: it
has no Upload or Danger Zone card to hide, and its **lock card
covers all three locked states**, each naming the way out that
state has — `ready` and `expired` carry the inline revert form
(`revert_session_to_draft` accepts both), while `archived` names
the lobby's Unarchive and offers no control, because `/revert`
answers 409 from `archived` and a button there would be a dead
control. See `spec/instruments.md`.

**Every setup-mutation control on those pages answers that one
predicate**, the friendly-label editor included: both halves of its
gate — the Unlock panel's suppression and `_save_field_labels` — read
`is_editable`. On `is_ready` alone it would accept a save on
`expired` and `archived` (303, not 409) while the lock card two
elements above says the roster cannot be modified. See
`spec/setup_pages.md`.

**The gate is `is_editable`, not `is_ready`.** `is_ready` is only
`status == "ready"`, so under it an `expired` or `archived` session
renders the Upload and Danger Zone cards — on Reviewers, the Unlock
panel holding them — and, on the roster
pages, row checkboxes and a live Delete — while every route behind
them answers 409. The page offers what `_require_editable` will
accept and nothing else; §3.1 is the authority and the templates
read the same predicate.

**The roster pages' selection surface follows the same gate**: row
checkboxes, the selection-driven Edit / Inactivate / Activate /
Add / Delete controls, the selected count and the delete
confirmation render only while editable. The read-only half of
the strip — the Status filter, the search box and Clear —
renders in every state, because reading a finished session's
roster is legitimate. So does the preview-count line, which sits
above the **preview table** rather than in the strip and is shared
by all seven preview pages (`spec/setup_pages.md`, "Preview
tables"). **Observers is the one exception**: its whole selection
surface — the row checkboxes, the bulk controls and the Unlock
panel — stays live until `archived`, on the wider predicate above
("Observers uses a WIDER predicate"), because observers drive the
cohort rule editor (`spec/setup_pages.md`), which is deliberately
usable mid-session.

**The card and the controls answer the same predicate**, and have
to. Key the card to `is_ready` while the controls read
`is_editable` and an `expired` or `archived` page is correct but
silent — the mutating cards are absent and nothing on the page
says why.

The lock card's "Revert to draft" form posts a `return_to` slug so
the operator lands back on the page they were trying to edit. The
route honours it only when it matches `_REVERT_RETURN_TO`
(`app/web/routes_operator/_shared.py`) — `reviewers`, `reviewees`,
`relationships`, `observers`, `assignments`, `instruments`,
`validate`, `invitations`, `responses`,
`extract-data` — and otherwise falls through to Session Home. That
fallback is what stops a crafted slug steering the redirect, so the
set is an allowlist rather than a hint.

Every slug a template posts must be in that set, and a missing one
fails **silently**: the revert succeeds, the redirect falls through
to Session Home, and a 303 to a real page looks like success — so
an operator reverting *in order to edit relationships* lands on
Home with nothing to explain it.

The **Email Template** page is the exception: it renders no lock
card and its routes carry no `_require_editable`, so email copy
stays editable in every lifecycle state but `archived`, where its
writes answer 409 under the session lock and its fields render
disabled — see `spec/email_template_editor.md` §5.

**Visual treatment:** `--card-warning-border` border,
`--card-warning-bg` interior, outline-amber button. Documented in
`spec/visual_style_rrw.md` "Warning surfaces — shared brown
framing".

**Session Home is the exception.** The Workflow card carries
its own state-aware copy (per `spec/session_home.md`), so Home
doesn't stack a yellow lock card on top — disabled treatment on
Home is plain greying-out. The Quick Setup card on Home follows
the same convention: available on the same `is_editable` predicate
while the session has no responses, and otherwise body-greyed with
its controls disabled (`spec/quick_setup_card_spec.md`).

**Assignments answers to the same predicate**, and splits the way
the roster pages do: the selection-driven
half — row checkboxes, select-all, the bulk form, the
selected count, `Inactivate` / `Activate` — renders only
while `is_editable`, which is what its four mutating routes
enforce; the read-only half — the `Search by:` select, the search
box, `Clear` — renders in every state, as does the preview-count
line above the table. Its
per-instrument self-review toggle answers to the same predicate but
in the other manner: it **stays on the page and disables**, where
the bulk controls disappear — the row it sits in is a status table
that reads in every state. Its disabled title names each state's own
way out, as the Instruments page's do.

Gating the page whole on `not is_ready` would disagree with those
routes on **three of five** states in both directions: `expired`
and `archived` would offer live controls the routes refuse, and
`ready` would lose the search along with them — on the state an
operator is most likely reading that page in. Assignments takes
**no lock card**: its mutating controls disappear rather than
being explained, and a third lock-card variant would add a shape
without removing one. See `spec/assignments.md`.

**Operations pages** (Validate / Assignments / Invitations /
Responses) while session is `draft` / `validated`:
each page renders its own "session not yet activated" banner if
the surface needs an active session; most Operations surfaces
are read-mostly so they work in any state.

## 6. Audit events

The events the lifecycle transitions and the scheduled triggers write.
`EVENT_SCHEMAS` in `app/services/audit.py` registers every event type.

| Event type | Emitted by | Detail envelope |
|---|---|---|
| `session.validated` | `mark_validated` | `counts={"warnings": N, "info": N}` |
| `session.invalidated` | `invalidate_if_validated` (the automatic flip; lands in the caller's commit) and `invalidate_session` (the Revert; commits itself) | `reason=<string>` naming the caller: the mutation for `invalidate_if_validated` (e.g. `reviewer_created`, `assignments_generated`), `operator_revert` from `/revert`. A failed Activate writes none: the session stays `validated` |
| `session.activated` | `activate_session` | `counts={"warnings": N, "info": N, "instruments": N}` + `context={"prev_status": "validated", "override_warnings": bool, "trigger": "operator" \| "scheduled"}` |
| `session.reverted_to_draft` | `revert_session_to_draft` | `counts={"closed_instruments": N, "responses_at_revert": N}` |
| `session.expired` | `expire_session` (Workflow-card **Close session**); `observe_deadline` at the review's end | `counts={"closed_instruments": N}`. The end's close has no actor and adds `reason="deadline"` (End) or `"release"` (no End, Release from) + `context={"deadline": …}` / `{"release_at": …}` |
| `session.deadline_reached` | `observe_deadline`, only for a real End | `counts={"submitted": N, "assigned": N}` + `context={"deadline": …}` |
| `session.release_window_opened` / `session.release_window_ended` | `observe_release_window` (§8.2.3) | `context={"release_at": …}` / `{"release_until": …}` |
| `session.archived` | `archive_session` | `changes={"status": [<from_status>, "archived"]}` |
| `session.unarchived` | `unarchive_session` | `changes={"status": ["archived", "draft"]}` |
| `session.responses_released` | `release_responses_now` (Workflow-card **Release responses**) | `snapshot={"responses_release_at": …, "cleared_until": bool}` |
| `session.responses_release_stopped` | `stop_responses_release` (Workflow-card **Stop releasing**) | `snapshot={"responses_release_until": …}` |
| `session.workflow_run_started` | `POST /workflow/prepare` and `POST /workflow/activate` — bracket the run, once per click | `context={"button": "prepare_session" \| "activate_session"}` |
| `session.workflow_run_failed` | same two routes when the chain raises | `context={"button": …, "step": "generate" \| "validate" \| "invite" \| "activate", "error_message": …}`. **Not `precondition`** — every precondition return in `_workflow.py` happens *before* the `workflow_run_started` write and redirects with `super_step="precondition"` instead, so no audit row ever carries it. `precondition` is a `super_step` value (the redirect query param the card reads), not a `context.step` one. |
| `session.activation_scheduled` | `sessions.update_session` when `scheduled_activate_at` changes | `changes={"scheduled_activate_at": [old, new]}` |
| `session.invite_schedule_updated` / `session.reminder_schedule_updated` | `sessions.update_session` when `invite_offsets` / `reminder_offsets` change | `changes={"invite_offsets" \| "reminder_offsets": [old, new]}` |
| `session.scheduled_activation_skipped` | the scheduled activation trigger (§8.2.3) | `reason=<skip code>` + `context={"scheduled_at": …, "status_at_fire": …}` |
| `session.scheduled_activation_retry` / `session.scheduled_activation_failed_persistent` | the scheduled activation trigger on a transition error (§8.3) | `reason=<error text>` + `context={"scheduled_at": …, "attempt" \| "attempts": N}` |
| `session.scheduled_invites_fired` / `session.scheduled_reminders_fired` | the invite / reminder triggers, once per offset fired | `counts={"sent": N}` + `context={"anchor_at", "offset_index", "offset", "scheduled_at", "actual_fired_at"}` |
| `session.scheduled_invites_skipped` / `session.scheduled_reminders_skipped` | the invite / reminder triggers, once per offset skipped (§8.2.3) | `reason=<skip code>` + `context={"anchor_at", "offset_index", "offset", "scheduled_at"}` |
| `session.scheduled_invites_handled` / `session.scheduled_reminders_handled` | `due_actions.mark_done` (Workflow-card **Mark as done**, §8.2.6), the operator's actor | `context={"anchor_at", "offset_index", "offset", "scheduled_at"}` |
| `session.scheduled_event_failed` | `observe_scheduled_events` when a trigger raises (§8.3) | `reason=<error text>` + `context={"trigger": "invites" \| "activation" \| "reminders" \| "deadline" \| "release"}` |
| `instrument.opened` | `observe_deadline`'s heal (§4) | `refs={"instrument_id": id}` + `reason="session_wide"`. Older rows, from the retired per-instrument Open, carry no reason. |
| `instrument.closed` | `observe_deadline` | `refs={"instrument_id": id}` + `reason="deadline"` + `context={"deadline": "..."}`; with no End, `reason="release"` + `context={"release_at": "..."}`. Past rows may carry `reason="manual"` from the retired per-instrument close. |

An event written inside the clock's pass (§8.3) also carries
`context.fired_by="clock"` where its schema allows `context`; one written
on a page view carries none. Each crossing writes one event whichever
trigger reaches it first.

See `spec/architecture.md` "Audit-event detail schema" for the
canonical envelope contract these events follow.

## 7. Implementation principles

1. **Service-layer invariants over route-layer gates.** The
   `_require_editable` route gate is an early refusal; the state gate
   is the service's `require_editable` (§3.1), decided under the
   session lock, and the actual `validated → draft` flip lives inside
   each mutating service via `invalidate_if_validated`. A future caller
   that bypasses the route layer still gets both.

2. **Idempotent transitions.** Every state-machine function
   no-ops when the target state is already current. Callers
   don't need to guard with `if not is_X`.

3. **Atomic commits.** Each transition commits its status flip,
   any side effects (per-instrument flag changes), and its audit
   event in one transaction. The automatic `validated → draft` flip
   (§2.3) is the exception: it commits with the edit that caused it.

4. **Naive datetimes treated as UTC** for deadline comparison
   (SQLite stores naive timestamps even with
   `DateTime(timezone=True)`). The `_aware` helper in the
   lifecycle module wraps every comparison.

5. **Enum values are constrained at the application layer, not
   via a DB CHECK.** Every state — including `expired` and
   `archived` — is enum-constrained in Python. Both `expired`
   (Workflow-card Close session, §2.7) and `archived` (§1) are
   actively written states; no `SessionStatus` value is reserved.

## 8. Scheduled lifecycle automation

The operator-facing automation surface for time-based lifecycle
events. The activation, invite and reminder triggers are live
(`app/services/scheduled_events/`); the end's close and the release
window's stamps run beside them, and the window itself is read by the
participant surfaces;
auto-archive and auto-delete-after-archive are columns with no
consumer at all (`guide/deferred_consolidated.md`). This section
documents the persistent model + the cross-cutting rules **all**
scheduled triggers obey, so no individual trigger re-litigates
them.

### 8.1 Model — anchors + offsets

Every scheduled event resolves to one **anchor datetime** plus an
**offset** anchored on it. The operator picks anchors on a
calendar; offsets are operator-set in a human shape ("1 day
before End", "30 days after End") and persisted as ISO 8601
durations.

**Anchors (absolute datetimes on `sessions`):**

| Anchor | Column | Owner | Status |
|---|---|---|---|
| **Start** (auto-activate) | `scheduled_activate_at` | operator-set | live |
| **End** (deadline) | `deadline` | operator-set | live |
| **Release-from** (Participants platform — reviewees / observers can view responses) | `responses_release_at` | operator-set | Live, with **no lead-time floor** — the operator may backdate it. The reviewee and observer surfaces consume it inside their per-instrument window gates. The two halves refuse differently, deliberately: `/results` is gated at the route by `require_reviewee_with_current_grant`, which answers a bare 404 when no instrument grants that reviewee anything under a window open now, so a reviewee never sees an empty results page; `/collation` has **no** route-level window gate, so an observer's instrument cards fall through to the empty state. **The window also requires the session to be `expired`**, not merely the anchor reached — otherwise an anchor set by any other path (a backdated one on the config card or Quick Setup, or one left behind by `revert_session_to_draft`) would open it. The Workflow card's **Release responses** button is offered only on an expired session, and the predicate enforces the same rule so the two cannot disagree. |

Two existing system-stamped datetimes (`activated_at` and the
in-memory archive timestamp) also serve as anchors for offsets:

- `activated_at` — system-stamped on the first `→ ready`
  transition (see §2.4). Used today only as a display value
  ("Start" column on the reviewer lobby).
- The **archive timestamp** (i.e. `updated_at` at the moment
  `archive_session` runs) anchors the auto-delete-after-archive
  offset.

**Offsets (anchor-relative configs on `sessions`):**

| Offset | Column | Anchor | Shape | Default | Consumer |
|---|---|---|---|---|---|
| Auto-send invites | `invite_offsets` | `scheduled_activate_at` | JSON list of ISO 8601 durations, e.g. `["-P1D", "-PT2H"]` | empty (no auto-send) | with `RRW_SCHEDULED_SEND` on, the observers send (`app/services/scheduled_events/_invites.py`); off, the entries time due prompts (below) |
| Auto-send reminders | `reminder_offsets` | `deadline` | JSON list of ISO 8601 durations, e.g. `["-P2D", "-PT4H"]` | empty (no auto-send) | with `RRW_SCHEDULED_SEND` on, the observers send (`app/services/scheduled_events/_reminders.py`); off, the entries time due prompts (below) |
| Auto-archive | `archive_offset` | `deadline` | single ISO 8601 duration, e.g. `"P30D"` | intended **`P30D`** once auto-archive is wired (gives the operator time to download data post-deadline before the session leaves the active lobby); the column has no default today, so it stays NULL unless a Settings CSV import sets it | deferred — column only (`guide/deferred_consolidated.md`) |
| Release-until | `responses_release_until` — an absolute datetime, not an offset | n/a — column carries the absolute close time | DateTime(tz) | unset | Live. The form input is a date-time field (`spec/ui_elements.md` §8); the save-time validator enforces ordering (must close after `responses_release_at`) + a 365-day magnitude check. The Workflow card's **Stop releasing** button writes the same column (`= now()`). The reviewee and observer surfaces consume it inside their per-instrument window gates; there is no route-level gate on it. |
| Auto-delete after archive | `retention_overrides.delete_after_archive` (JSON key inside `retention_overrides`) | archive timestamp | single ISO 8601 duration | unset (use deployment env-var default) | deferred — column only (`guide/deferred_consolidated.md`) |

**Auto-send is off by default.** `RRW_SCHEDULED_SEND` (`scheduled_send`
in `app/config.py`, default off; read through
`scheduled_events.scheduled_send_enabled`) stays off until mail can go on
the clock. While it is off:

- the two offset fields stay live as **prompts**, labeled "Prompt to send
  invites" and "Prompt to send reminders", with the line
  "Scheduled email under development" beneath; they are stored and validated
  exactly as when on (Session Home, New session and the lobby's End
  editor), and each entry shows its **due moment** (Start or End plus the
  offset);
- the scheduled pass fires no invite or reminder, and activation, with no
  invites to wait for, runs as usual;
- an entry whose moment has passed, with someone left to act on, is a
  **due prompt** on the Workflow card (`spec/workflow_card.md`) and raises
  the lobby's **Due** pill (`spec/sessions_overview.md`); the operator
  acts by hand or marks it done (§8.2.6). With the flag on nothing is due
  here: the observers send;
- the Workflow card's auto-send captions, the schedule timeline's
  auto-send rows and the manual-activate confirm that warns of cancelling
  scheduled sends are not shown, and the Guide says so;
- the Settings CSV still exports both columns' values.

The "End" anchor (`deadline`) is also the anchor for the close at the
review's end (§4), which is live, and with no End the review's end is
Release-from (`session_lifecycle.review_end`).

### 8.2 Cross-cutting rules

**8.2.1 Always editable; effectiveness decided at fire time.**
Anchor datetimes and offset configs are **always editable while
the session is operator-mutable** (`draft` or `validated`) —
including at session-creation time, *before* any of the
preconditions that make the schedule actually fire are
satisfied. The operator declares intent on a calendar; the
system decides at fire time whether the intent is honourable.
There is **no editor-side lock-out** for any scheduled-event
field. The UI signals "not currently effective" (see §8.2.2);
the system enforces safety at fire time (see §8.2.3).

**8.2.2 Anchor-null inertness.** An offset is **inert when its
anchor is null**: the scheduler skips it, the editor shows the
field as not-effective (visual treatment only, not a hard
lock-out), and any other reader treats the resolved time as
"no scheduled fire". Examples:

- `invite_offsets` set but `scheduled_activate_at = NULL` → no scheduled
  invitation dispatch (operator must click manually).
- `archive_offset = "P30D"` but `deadline = NULL` → no scheduled
  archive (operator must archive manually from the lobby).
- `responses_release_until` set but `responses_release_at = NULL` →
  no scheduled close of the response-viewing window (you can't
  have an end without a start; treat the window as inert).

There is no single call site: each reader of an offset applies
the rule itself. The two list-valued schedules resolve every entry
to "no fire time" when the anchor is null —
`_resolve_invite_fires` in
`app/services/scheduled_events/_invites.py` against
`scheduled_activate_at`, and `_resolve_reminder_fires` in
`app/services/scheduled_events/_reminders.py` against `deadline` —
and each trigger also returns early on a null anchor. The schedule
captions in `app/web/views/_workflow_card.py` show such offsets as
inactive. The release window is open only once
`responses_release_at` is set and reached
(`session_lifecycle.is_response_release_window_open`), so a
`responses_release_until` with no start is inert. A new reader of an
anchor + offset pair owes the same rule. The single-valued helper
`resolve_offset` in `app/services/scheduled_events/_duration.py`
implements it.

**8.2.3 Event-precondition guard.** Beyond the anchor, each
scheduled event has its own operational preconditions — system
state that must hold at fire time for the transition to be
legal. The trigger checks the precondition first; if unmet, it
emits a `…_skipped` audit event with `reason=<precondition>` and
returns without retrying. The skip is one-shot: scheduled activation
clears `scheduled_activate_at`; an invite or reminder offset stays in
its list and is consumed by the skip event itself, since each trigger
treats an offset index with a `…_fired` or `…_skipped` row for the
current anchor as done. Per-event preconditions:

| Event | Precondition at fire time | Skip reason |
|---|---|---|
| Scheduled activation | `session.status == "validated"` **and** a fresh readiness report has no errors; warnings are acknowledged by the trigger itself (§2.4) | `not_validated` / `has_errors` (`needs_acknowledge` is mapped to a skip too, but cannot arise) |
| Auto-send invites | `session.status in {"validated", "ready"}` (Prepared) **and** invitations already created (Prepare creates them) | `not_prepared` / `invitations_not_created` |
| Auto-send reminders | `session.status == "ready"` (subsumes Prepared) **and** invitations exist **and** within accepting-responses window | `not_ready` / `no_invitations` / `outside_response_window` |

Release-from and Release-until are not fired events. The release
window is evaluated at read time by
`session_lifecycle.is_response_release_window_open` and is open only
on an `expired` session, so there is no fire-time guard and no skip
reason. Each moment is also **stamped** as an audit event for reports to
read: `observe_release_window` writes `session.release_window_opened`
when `responses_release_at` has passed and
`session.release_window_ended` when `responses_release_until` has, once
per crossing (a moved moment is a new crossing), whichever trigger reaches
it first. It stamps only while the session is `expired`, and only a
moment within `STAMP_GRACE` (one day) of now: an older crossing is not
backfilled. It checks without a lock first, so a page view after the
stamps exist takes none, and stamps under the session lock. It changes
nothing about what is visible. Auto-archive and auto-delete-after-archive have no trigger at
all (§8, above), so neither has a guard or a skip event either. The
`not_draft` and `not_archived` codes exist only as the manual Validate
and Unarchive transitions' refusals.

The review's end (End, or with no End, Release-from) is the trivial
case: it's conditional on activation (`status == "ready"`) because
there's nothing to close in a draft session — the close (§4) only runs
on a `ready` session. Validate's `session.end_passed` refuses to
activate a session whose end has already passed (`spec/validate_page.md`).

**Why this shape.** The operator's planning window is wide
("when I create the session, I know it should activate Monday
9am, send invites Sunday 8pm, remind Friday 2pm, and archive
30 days later"). Letting them declare all of that at creation
keeps intent durable across the inevitable status churn
(invalidations, reverts, re-runs). The fire-time guard then
makes the system safe regardless of state at trigger time.

**8.2.4 Offset format.** ISO 8601 duration strings (`P30D`,
`PT2H`, `-P1D`, `-PT4H`) — dialect-neutral, CSV-round-trippable,
human-readable. Negative durations mean "before the anchor";
positive durations mean "after". The parser accepts the standard
designators only (`P[n]Y[n]M[n]DT[n]H[n]M[n]S` with optional
leading `-`); fractional values and weeks (`P1W`) are rejected at
the editor.

**8.2.5 Operator-determined, not derived.** Every offset is
operator-set. The system never silently re-anchors based on
other fields (e.g. switching `archive_offset` from `deadline` to
`responses_release_at` when the latter is set). If a richer
policy is needed later, it lands as an explicit operator-facing
control, not as derived behaviour.

**8.2.6 Multiple offsets per event.** Events that fire on a
sequence (invites, reminders) carry a JSON list; events that
fire once (archive, auto-delete) carry a single ISO 8601 string.
Per-list-entry dedup is by position on the anchor. An entry is
**sent, skipped or handled**: *handled* is the operator's **Mark as done**
on a due prompt (`due_actions.mark_done`, writing
`session.scheduled_invites_handled` / `session.scheduled_reminders_handled`),
consumed by `scheduled_events.fired_offsets` as a sent entry is, so a
later scheduled send never sends it and a save may not put another entry
on its position. The observers'
`session.scheduled_*_fired` / `_skipped` / `_handled` audit rows record
`context.offset_index` and the entry (`context.offset`), and a recorded
position never fires again on that anchor, whatever entry sits there.
So a Session Home save, a lobby End edit or a Settings import that
would put a different entry on a position already sent, skipped or handled, on
the anchor the session will hold, is refused
(`scheduled_events.fired_offset_errors`; findings Bc1, ruled
2026-10-07): a sent entry (or a handled one) stays at its position, new entries go after
it, and one kept in place skips the lead-time floor. A list whose
entries and anchor both stay as stored is not checked, so a save that
leaves the schedule alone is never refused over it. The record belongs
to the anchor's value, so moving Start or End frees the list and moving
it back restores that value's record. The reminder outbox
key `reminder:{session_id}:{reviewer_id}:{offset_index}` carries no
anchor, deliberately: a reviewer gets scheduled reminder *n* at most once
per session, so moving End does not resend it (author's ruling,
2026-10-07, findings Bc2). An operator who wants another sends it by
hand, with the Workflow card's **Send reminders** or a row's **Send
reminder** on Manage Invitations; neither carries that key, so neither
is held back by it (`spec/operations_pages.md`).

**8.2.7 Save-time datetime ordering.** Independently of the
fire-time guard (§8.2.3), the four operator-set anchor
datetimes carry an inherent order checked at save time on the
Edit / Create routes:

> `scheduled_activate_at  ≤  deadline  ≤  responses_release_at  <  responses_release_until`

Each pair is checked only when both members are non-NULL;
NULL slots impose no constraint, with one exception: with no End,
Release-from is the review's end, so it must be on or after Start. The
Start ↔ End, End ↔ Release-from and no-End Start ↔ Release-from pairs are enforced by
`scheduled_events.validate_schedule_ordering`, called after
the per-field parsers succeed; the Release-from ↔ Release-
until pair (strict-greater-than, plus the 365-day magnitude
check) lives inside
`parse_and_validate_responses_release_until` along with that
field's parse. Violations raise `ScheduledActivateError` and
translate to HTTP 422 with the per-pair error message:

| Pair | Error message |
|---|---|
| End < Start | `End must be on or after Start.` |
| Release-from < End | `Release responses from must be on or after End — reviewees can only view results after the review window closes.` |
| No End, Release-from < Start | `With no End, Release responses from must be on or after Start: the release ends the review.` |
| Release-until ≤ Release-from | `Release responses until must be after Release responses from.` |
| Release-until > Release-from + 365d | `Release responses until must be within 365 days of Release responses from.` |

On Session Home's details card a pair whose two boxes both still hold
their stored values (in the seeded or, after a Timezone change, the
submitted zone: `spec/session_home.md` §4) is not checked, as the
import below skips a pair it leaves alone, so a Save is never refused
over a stored pair nobody edited (the closed-then-released session
below holds one). That covers all three pairs, the Release-from ↔
Release-until order and its 365-day cap included: an import, or Stop
releasing a year after Release and then a Revert, can store a window
past the cap (findings L1).

The **Settings CSV import** enforces the chain too, in its parse phase, so a violating file is refused
whole and nothing is applied. It checks the pairs through
`validate_schedule_ordering` (which takes `responses_release_until`
for this caller, since the import has no per-field parser), on the
values the session would hold after the apply — End is a fallback
key, so the destination's own End stands where it has one. A pair the
file supplies neither side of is not checked, so an import is never
refused over a schedule it leaves alone. The lead-time floor and the
365-day cap are not checked there: a restore may carry moments that
have since passed. A session closed before its End and then released
holds Release-from before End (**Release responses** stamps the moment
of release), so its own export is refused until Release-from is
cleared or moved in the file (`spec/csv_contracts.md`).

The create form (`session_new.html`) also checks the same chain
client-side, in a small partial
(`operator/partials/_schedule_ordering_js.html`). As the operator types
it compares each adjacent pair (Start ≤ End, End ≤ Release-from,
Release-from < Release-until) only when both boxes hold a time, as the
server does, and marks the later box invalid with the table's wording
(`setCustomValidity`), so the browser blocks the submit. It sets no
`min` / `max` on the text boxes; it bounds each box's hidden picker to
its neighbors. Session Home's Details card runs no client check. Either
way the server check is the load-bearing safety net: direct POSTs bypass
the page entirely.

### 8.3 Implementation notes

- **Trigger mechanism — two triggers, one pass.** The scheduled steps
  run in one order, `scheduled_events.observe_scheduled_events`:
  invites (only with `RRW_SCHEDULED_SEND` on), then activation, then
  reminders (same condition), then the close at the review's end
  (`observe_deadline`, for a `ready` session past `review_end`), then the
  release-window stamps (§8.2.3). Two triggers run that pass: the
  page view below and the **clock** (next bullet). Either may reach a
  step first; the per-session lock makes it happen once.
- **The clock.** `app/services/scheduled_events/_clock.py`, started by
  RRW's lifespan (`app/main.py`) when `SCHEDULER_INTERVAL_SECONDS`
  (default `120`; `0` turns it off, as the test suite does) is above `0`.
  Each pass takes a Postgres transaction-level advisory lock on RRW's own
  key (`LOCK_KEY`; SQLite takes none) and skips if another process holds
  it, so one process runs it. It visits only sessions with a step due
  (`due_session_ids`): a Start that has passed, a `ready` session past its
  review end, an `expired` one with a release moment within `STAMP_GRACE`;
  never an `archived` session. Each session runs in its own database
  session under the per-session lock, so one session's failure or
  contention never stops the pass. Events it writes carry
  `context.fired_by="clock"` (`audit.fired_by`; not `context.trigger`,
  which names which trigger raised in `session.activated` and
  `session.scheduled_event_failed`). It sends no mail: with sending on and
  no invite-URL builder (it has none) the clock holds activation for a
  session with invite offsets, since activating would clear the Start the
  offsets resolve against. Shutdown waits up to 30 s for a pass in flight,
  then abandons it. The page-view trigger stays as a backstop, so a
  deployment with the clock off behaves as before.
- **Trigger mechanism — page view.**
  Each operator GET to a session-related page runs the per-anchor
  sweep for that session, fires anything past its scheduled time, and
  short-circuits on no-op. The pages are Session Home, the four
  Operations pages of §5 (Validate, Assignments, Invitations,
  Responses) and the Sessions lobby, which runs it for each session
  its table lists that can still fire (every one the operator owns
  that is neither `expired` nor `archived`: an expired session has
  nothing left for the lobby to fire, and its past entries would cost a
  lock on every load; its release stamps wait for the clock or its own
  pages). All go
  through `observe_scheduled_events_on_load`
  (`app/web/routes_operator/_shared.py`), which runs
  `scheduled_events.observe_scheduled_events` once per session per
  request; a session with nothing due returns before any query, and
  one with a due entry already sent pays a lock and an audit read per
  trigger. No new processes / cron / queue
  infra. Trade-off: a scheduled event "fires at the next
  operator GET ≥ scheduled time" — which is fine for events
  with reasonable lead time, but constrains *how close to the
  fire moment* the operator can schedule (the lead-time floors
  are in `spec/settings_inventory.md` §2). With the clock on, Start and
  the review's end fire within one interval of their time with no page
  view.
- **Past-time editor rule.** The values that fire — Start and
  each invite and reminder offset — are **rejected** on **save**
  when their resolved fire time is closer than the operational
  lead-time floor (`spec/settings_inventory.md` §2), so the
  operator can't *set* a past firing. End, Release-from and
  Release-until have no floor of their own: End gates the
  deadline observer, and Release-from may be backdated to release
  immediately. End still meets the floor indirectly while reminder
  offsets are set, because each reminder fires at `deadline +
  offset` and is checked against the new End, so a past or
  near-future End is refused through them. A value that *became* past after saving (Start
  set for tomorrow, and tomorrow has come while the session sat
  in `draft`) **stays put**; the fire-time precondition guard
  handles it normally, typically on the next operator visit. So does
  an offset already sent at its position on the anchor the save keeps
  (§8.2.6).
- **Concurrency safety.** Two concurrent operator GETs racing
  the observer could fire the same trigger twice, and a schedule save
  racing one could move an entry the observer is sending. Each trigger
  takes `lock_session` (`SELECT … FOR NO KEY UPDATE` on the session
  row, flushing first and then re-reading it) and decides from what
  that reads: activation checks its column is set and due in the same
  transaction as the column clear, and the
  invite and reminder passes decide, send and record **one entry per
  transaction**, re-locking before the next (findings Bc3, ruled
  2026-10-07). A second racer re-reads after the first commits and
  no-ops, if the first commits within the lock's 5 s bound (§3.1);
  otherwise the observer's pass stops quietly at the first trigger that
  meets the busy lock, writing no `session.scheduled_event_failed`, and
  the page renders as usual. The next visit tries again. The schedule saves take the same lock first, before reading
  anything (the Session Home save, the lobby's row expander and the
  Settings import, each before its editability gate), and hold it until the schedule is written,
  so the editability gate, the stored schedule and the sent-entry
  record (§8.2.6) are read as they stand, a send
  being recorded is committed before a save reads the record, and an
  observer arriving after a save sees the saved lists. Session Home
  writes the display zone, and the lobby its tags, after the schedule
  for that reason, since each of those writes commits. `FOR NO KEY UPDATE` does not block other transactions'
  inserts that reference the session (audit rows, tags). A failure
  part-way through an entry rolls the entry back whole; the next visit
  sends it again (safe while sends only write outbox rows; a transport
  that delivers inside the transaction would need its own guard).
  Postgres only: SQLite has one writer.

  **Every state-gated save and every transition is decided under the
  same lock, in the service.** Each transition locks and re-reads the row
  before its precondition, so a manual Activate that read `validated` and
  lost the race to the scheduled activation raises `not_validated`. Each
  state-gated save opens with `require_editable` / `require_not_archived`
  / `require_not_ready` (§3.1), so a roster, relationship, assignment,
  instrument, visibility or session save cannot land on a session that
  went `ready` after the request loaded it; each operator invitation
  action opens with `require_validated_or_ready` / `require_ready`, so a
  send, regenerate or reminder cannot land on one reverted or closed
  since (findings Bc5); and the reviewer's Save, Submit, Clear and
  Recall open with `require_accepting_responses` (`ready`, before the
  deadline), so none lands after a Close or Revert (findings L3). That
  one lock is shared (`FOR SHARE`): a transition waits for the write,
  but reviewers writing at once do not wait on each other, since no
  write updates the session row or locks it again. Its refusal is not
  the 409 page: the route re-renders the refused write as its own
  check would (`spec/reviewer-surface.md`, *Lifecycle gating*). The gate is
  `session_guard.require_state`; the route-level `_require_*` checks stay
  as early refusals and the service check can only refuse more. The
  Instruments page's display-field repair
  (`instruments.repair_display_fields`, findings Bc8) is the one gate that
  skips rather than refuses: when the loaded session looks editable it
  re-checks under the same lock, through `lock_session` and `is_editable`
  rather than `require_state`, and it commits on every path.
  - **Re-entrant.** Several guarded calls in one request re-lock and
    re-read; `lock_session` flushes first, so an unflushed edit survives.
  - **Held to the commit.** The lock lasts until the transaction ends, so
    a save that must keep the state it gated on through its edit commits
    once (`unit_of_work.atomic`; the callers are listed in that module's
    docstring), and the automatic `validated → draft` flip (§2.3) rides
    that commit. The invitation batches and the scheduled passes do the
    same without `atomic`: each row is written with `commit=False` and
    the batch commits once, the request rolling back on a raise.
  - **Async handlers** await their body, then run the guarded part
    through `run_in_threadpool`, so a lock wait never blocks the event
    loop.
- **Retry policy.** If a precondition passes but the underlying
  transition raises (transient DB error, etc.), the trigger
  emits `session.scheduled_X_retry` (audit only — no schedule
  clear). Subsequent operator GETs re-attempt the same trigger.
  The trigger counts `scheduled_X_retry` events for the current
  scheduled-fire moment from the audit log; **after 3 failed
  retries** it emits `session.scheduled_X_failed_persistent`,
  clears the schedule, and stops. Page-view retries are paced by operator
  visits, with no throttle. On the clock a retry waits `RETRY_SPACING`
  (15 minutes) after the last one, so the three do not spend themselves
  in a few passes with nobody looking; the spacing holds back a Start
  only, never a close or stamp due on the same session. **Only activation
  implements this.** For invites and reminders the retry and
  terminal state are work in progress awaiting Azure
  (`guide/post_azure_todo_checklist.md` item 7). Until then
  `observe_scheduled_events` runs each trigger guarded: one that
  raises has its uncommitted work rolled back (the entry it was on,
  sends and all; entries it already recorded stay) and is logged,
  `session.scheduled_event_failed` records it (`context.trigger`,
  `reason`; not repeated while that trigger's latest one says the
  same, checked under the session-row lock), the page still renders,
  and the next visit tries again with no attempt cap. A failed invites
  pass holds activation for that pass: activation clears
  `scheduled_activate_at`, the anchor the invite offsets resolve
  against, so activating would strand the failed invitations. The guard also covers activation: if writing its own
  retry or skip row fails, that attempt is rolled back uncounted, so
  the three-retry cap above holds only while those writes succeed. An
  audit-schema error is re-raised — it only raises in strict mode,
  where it is the test suite's gate — except inside activation's own
  transition handler, which records one raised by `activate_session`
  as a retry like any other error.
- **Operator notification on skip / failure.** Audit events, plus,
  for activation only, a **signal line on the Workflow card**
  ("Scheduled activation at «X» — reason: «reason»."), shown while
  the session's newest audit event is the skip or the persistent
  failure (`spec/workflow_card.md` § *Scheduled-activation signal*).
  Email notification is deferred.
- **Audit events** — a scheduled activation emits `session.activated`
  with `context.trigger="scheduled"`; the invite and reminder triggers
  emit `session.scheduled_invites_fired` /
  `session.scheduled_reminders_fired`, one per offset fired. Skips and
  failures have their own events, and the *configuration-change*
  events (`session.activation_scheduled`,
  `session.invite_schedule_updated`,
  `session.reminder_schedule_updated`) are written by the editor
  surfaces; §6 lists them all. Purging is not scheduled:
  `session_purge.purge_and_archive` (the lobby's **Purge and archive**
  and the Extract data page's Archive card) writes
  `session.responses_purged`, `session.rosters_purged` and
  `session.audit_log_purged` for the categories ticked.
- **Settings CSV round-trip** — every scheduled-event column,
  including the two with no consumer yet, is exported and
  imported in the Settings CSV, so a round-trip never silently
  drops an operator's schedule.
