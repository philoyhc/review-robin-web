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
| `expired` | Closed | Session closed by the operator's Workflow-card **Close session** button (`ready → expired`, `expire_session`). Every instrument is closed; responses (drafts + submitted) are preserved. From `expired` the operator can Revert to draft (`revert_session_to_draft`) to reopen for editing. |
| `archived` | Archived | Filed out of the active lobby; deletes no data. Written by `archive_session` / `unarchive_session`. `archive_session` accepts **any non-archived** starting state (draft / validated / ready / expired), so the Workflow card's `/workflow/archive` route can fire from any state, though the card renders its Archive button only in `expired` (`archive_visible`); the lobby's **Purge and archive** and the Extract data page's Archive card both go through `session_purge.purge_and_archive`, which skips any session failing `can_archive` (so `draft`, `validated` and `expired` archive, and `ready` does not). `unarchive_session` restores `archived → draft`. |

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
single audit event and commit atomically. One qualification:
`invalidate_session` commits through `unit_of_work.commit`, so
inside a route's `unit_of_work.single_commit` (the Instrument card's
Save) the `validated → draft` flip lands with that route's one commit,
or is rolled back with it when the Save is refused
(`spec/instruments.md`, *Action row*).

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

The explicit form. Idempotent (no-op when already `draft`).
Raises `LifecycleError(code="not_validated")` when the session
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
`validated` session `validated` (author's ruling, 2026-10-05, findings
Cc5): no field it writes can change the check's verdict. Name and code
are checked only for being present and the form requires both, help
contact adds an info note only, and the rest (description, deadline,
Start, offsets, the release window, the two Setup-tab toggles) are not
read. The other writes on those two forms do not invalidate either:
the timezone (`sessions.set_session_display_timezone`) and the tags
(`session_tags.set_tags`) are not checked, nor are owners.

The invariant lives at the **mutation site**, not the route, so a
route that forgets to wrap its service call cannot silently break
it.

### 2.4 `validated → ready` — `activate_session(...)`

Called by `POST /operator/sessions/{id}/activate` and by
`POST /operator/sessions/{id}/workflow/activate` (the Workflow
card's solo Activate button). Flips the
session to `ready` and sets `accepting_responses=true` on every
instrument in the same transaction. Pre-conditions:

- Session is `validated`. (Raises `not_validated`.)
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
(the recovery path after the operator closed the session with
**Close session** and wants to reopen it for editing) as the
starting state.

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
`/revert` route dispatches by current status: `validated → draft`
calls `invalidate_session(reason="operator_revert")`. The
`ready → draft` branch calls `revert_session_to_draft` instead
(per 2.5).

### 2.7 `ready → expired` — `expire_session(...)`

The "Close session" path. Called by `POST
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
`counts={"closed_instruments": N}`.

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
  return the `lifecycle` reason token, which the route turns into a
  303 carrying `quick_setup_error=…&quick_setup_reason=lifecycle`
  rather than a 409.

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
- **The email-template editor calls no lifecycle gate at all**, so
  it does not belong on this list; §5 states the same.
- **The Observers roster calls `_require_not_archived` instead**, a
  genuinely *wider* predicate rather than the same one under another
  name. **All eight of its mutating routes take it** — `create`,
  `update`, `bulk-inactivate`, `bulk-reactivate`, `bulk-delete`,
  `delete-all`, `import` and `cohort-rule` — so the roster accepts
  through `ready` and `expired` and 409s only on `archived`. §5
  carries the reason, and the rule that governs a second such
  exception.
- **Session Home's Delete Data and Delete session call
  `_require_not_ready` instead** (`_shared.py`), which 409s only in
  `ready`, so both work on a `draft`, `validated`, `expired` or
  `archived` session. The lobby's bulk Delete
  accepts `draft`, `validated` and `expired` (`is_editable` or
  `is_expired`); archived sessions go through the archived page.

Detail message: `"Session is <status>; revert to draft to edit"`.

### 3.2 `_require_response_loss_ack(db, session, ack)`

Raises **HTTP 400 Bad Request** when responses already exist and
the request didn't carry `acknowledge_response_loss=true`. Called
from routes whose mutations would invalidate stored reviewer
responses: reviewer and reviewee delete-all, the Reviewers and
Reviewees Setup-page CSV import (`_shared.py` `_handle_import`),
assignment Generate, and Quick Setup's roster and
settings replaces (which answer `needs_confirm` rather than 400).
**Relationship changes do not call it**, although moving a pair to
another pair-context group deletes the group answer copy it carried
(`spec/assignments.md` "Group-scoped fan-out"), as a reviewee tag edit
does.
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

### 3.3 `_require_validated_or_ready(session)`

Raises **HTTP 409 Conflict** when the session is `draft`
(invitation actions need at least the assignment pairs to be
settled). The two **bulk** invitation routes in
`app/web/routes_operator/_operations.py` call it — `send-all` and
`regenerate-all`. (Prepare, which creates the invitations, is gated
by its own `is_editable` precondition rather than this one.) It is
deliberately looser than "ready
only" so an operator can notify reviewers **before** activation
(the Prepared / pre-open scenario).

Detail message: `"Invitations can only be issued once the
session has been prepared (validated or ready)."`

### 3.4 `_require_ready(session)`

The stricter invitation gate, in the same module: per-row `send` /
`regenerate` / `remind` and the bulk `remind-incomplete` answer
**409** outside `ready`.

Detail message: `"This action is available only once the session is
Activated."`

These gates are the only thing that stops a direct POST
from bypassing the lifecycle. The corresponding GET pages render
read-only banners but the source of truth is the route gate.

## 4. Per-instrument lifecycle

Each instrument carries an `accepting_responses` flag. It is set and cleared
session-wide, below, so within a `ready` session every instrument is
open or every instrument is closed.

| Column | Type | Meaning |
|---|---|---|
| `accepting_responses` | `Boolean` | Reviewers can save / submit. **Session-wide in practice:** set on every instrument by activate, cleared on every instrument by revert, Close session and deadline-close. No operator control sets it per instrument. |
| `deadline_closed_at` | `DateTime \| None` | Timestamp the deadline-close fired. Read only by `observe_deadline`, which skips an instrument already stamped; cleared by Activate and by a reopen while live (a `ready` session whose deadline is unset or moved into the future). No surface renders it. |

What a reviewer reads back after close is the visibility policy's call
(`spec/reviewer-surface.md` "Lifecycle gating").

**Services:**

- **No per-instrument open or close.** Accepting is session-wide:
  `activate_session` opens every instrument (a group-scoped one
  included, since it defaults to the synthetic Full Matrix on an
  untouched Band 1), and `revert_session_to_draft`,
  `expire_session` and `observe_deadline` close them all. So once
  a session is activated, an instrument is never closed while another
  in it accepts (a settings import can set the flag per instrument,
  but only on an editable session, and activation then opens all),
  and the reviewer write gate (`spec/reviewer-surface.md`
  "Lifecycle gating") is session-wide with it.
- **The heal.** `observe_deadline`, which runs on every reviewer
  request and on the Instruments page, reopens any closed instrument
  while the session is `ready` and before its deadline, emitting
  `instrument.opened reason="session_wide"`; past the deadline it
  closes them instead. Nothing in the UI reopens a single instrument,
  and one left closed would make the gate refuse every write.
- `observe_deadline(...)` — lazy deadline-close. Idempotent. Called
  on the reviewer surface — its GET (`review_surface` and
  `_surface_context`; the operator preview skips it), Recall, and the write gate
  `_require_session_accepting` ahead of save / submit / clear — and by
  the operator Instruments page GET (`instruments_index`). The
  predicate `session_accepts_responses` does not call it; it compares
  `now()` with the deadline itself (§4.1). The first request after the deadline
  passes sets `accepting_responses=False` + stamps
  `deadline_closed_at` + emits one `instrument.closed
  reason=deadline` audit event per instrument.

### 4.1 The reviewer write-path predicate

`session_accepts_responses(session, instrument)` gates every
reviewer write (save / submit / clear). Returns `True` iff:

1. Session status is `ready`,
2. `instrument.accepting_responses` is `True`,
3. `now() < session.deadline` (or `session.deadline is None`).

POST routes (save / submit / clear) call this directly and 403
on failure. The reviewer-surface **GET** route branches
upstream of this check:

- If the session is neither `ready` nor `expired` (draft,
  validated or archived), the route renders the dedicated
  **pre-open page**
  (`reviewer/pre_open.html`) — "this review hasn't opened yet,
  check back later". The reviewer reached here via roster + an
  invitation token that was sent ahead of activation. An `archived`
  session renders the same page with closed copy ("this review has
  closed"), no deadline line.
- If the session is `ready` but the predicate returns `False`
  (the deadline passed),
  the existing surface template renders read-only with the "no
  longer accepting responses" banner; the saved values render below,
  since a `ready` session is in the reviewer's `while_ongoing` window
  (`spec/reviewer-surface.md` "Lifecycle gating").

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
whose contents its routes would refuse. The tag-label editor is the
one exception and deliberately so — it re-renders outside the panel
with its inputs disabled and its buttons dropped, because a locked
page must still let an operator *read* the labels.

**Observers uses a WIDER predicate.** Its mutating surface reads
`not is_archived`, so the roster stays editable through `ready` and
`expired` and only `archived` closes it. All eight of its mutating
routes take `_require_not_archived`, so the page and its routes agree
and the surface is suppressed exactly where they refuse. §3.1 lists
all eight.

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
gate — the template's `disabled` and `_save_field_labels` — read
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
tables"). **Observers is the one exception,
on checkboxes only**: theirs stay live until `archived` because
they drive the cohort rule editor (`spec/setup_pages.md`), which
is deliberately usable mid-session; its bulk *card* follows the
common gate.

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
stays editable in every lifecycle state — see
`spec/email_template_editor.md` §5.

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
the Lock / Unlock toggle hidden (`spec/quick_setup_card_spec.md`).

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
| `session.invalidated` | `invalidate_session` (called via `invalidate_if_validated` or directly) | `reason=<string>` naming the caller: the mutation for `invalidate_if_validated` (e.g. `reviewer_created`, `assignments_generated`), `operator_revert` from `/revert`. A failed Activate writes none: the session stays `validated` |
| `session.activated` | `activate_session` | `counts={"warnings": N, "info": N, "instruments": N}` + `context={"prev_status": "validated", "override_warnings": bool, "trigger": "operator" \| "scheduled"}` |
| `session.reverted_to_draft` | `revert_session_to_draft` | `counts={"closed_instruments": N, "responses_at_revert": N}` |
| `session.expired` | `expire_session` (Workflow-card **Close session**) | `counts={"closed_instruments": N}` |
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
| `session.scheduled_event_failed` | `observe_scheduled_events` when a trigger raises (§8.3) | `reason=<error text>` + `context={"trigger": …}` |
| `instrument.opened` | `observe_deadline`'s heal (§4) | `refs={"instrument_id": id}` + `reason="session_wide"`. Older rows, from the retired per-instrument Open, carry no reason. |
| `instrument.closed` | `observe_deadline` | `refs={"instrument_id": id}` + `reason="deadline"` + `context={"deadline": "..."}`. Past rows may carry `reason="manual"` from the retired per-instrument close. |

See `spec/architecture.md` "Audit-event detail schema" for the
canonical envelope contract these events follow.

## 7. Implementation principles

1. **Service-layer invariants over route-layer gates.** The
   `_require_editable` route gate is defence-in-depth; the
   actual `validated → draft` flip lives inside each mutating
   service via `invalidate_if_validated`. A future caller that
   bypasses the route layer still gets the invariant.

2. **Idempotent transitions.** Every state-machine function
   no-ops when the target state is already current. Callers
   don't need to guard with `if not is_X`.

3. **Atomic commits.** Each transition commits its status flip,
   any side effects (per-instrument flag changes), and its audit
   event in one transaction.

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
(`app/services/scheduled_events/`), and the release-window anchors
are consumed by the participant surfaces rather than by a trigger;
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
| Auto-send invites | `invite_offsets` | `scheduled_activate_at` | JSON list of ISO 8601 durations, e.g. `["-P1D", "-PT2H"]` | empty (no auto-send) | live (`app/services/scheduled_events/_invites.py`) |
| Auto-send reminders | `reminder_offsets` | `deadline` | JSON list of ISO 8601 durations, e.g. `["-P2D", "-PT4H"]` | empty (no auto-send) | live (`app/services/scheduled_events/_reminders.py`) |
| Auto-archive | `archive_offset` | `deadline` | single ISO 8601 duration, e.g. `"P30D"` | **`P30D`** (gives operator time to download data post-deadline before the session leaves the active lobby) | deferred — column only (`guide/deferred_consolidated.md`) |
| Release-until | `responses_release_until` — an absolute datetime, not an offset | n/a — column carries the absolute close time | DateTime(tz) | unset | Live. The form input is a `datetime-local`; the save-time validator enforces ordering (must close after `responses_release_at`) + a 365-day magnitude check. The Workflow card's **Stop releasing** button writes the same column (`= now()`). The reviewee and observer surfaces consume it inside their per-instrument window gates; there is no route-level gate on it. |
| Auto-delete after archive | `retention_overrides.delete_after_archive` (JSON key inside `retention_overrides`) | archive timestamp | single ISO 8601 duration | unset (use deployment env-var default) | deferred — column only (`guide/deferred_consolidated.md`) |

The "End" anchor (`deadline`) is also the anchor for the lazy
deadline observer (§4 — per-instrument auto-close); that's the
one scheduled lifecycle effect already live.

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
implements it but has no callers.

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
reason. Auto-archive and auto-delete-after-archive have no trigger at
all (§8, above), so neither has a guard or a skip event either. The
`not_draft` and `not_archived` codes exist only as the manual Validate
and Unarchive transitions' refusals.

The "End" anchor (`deadline`) is the trivial case: it's
conditional on activation (`status == "ready"`) because there's
nothing to close in a draft session — the lazy deadline observer
(§4) already short-circuits when the session isn't `ready`.

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
Per-list-entry dedup is by position on the anchor: the observers'
`session.scheduled_*_fired` / `_skipped` audit rows record
`context.offset_index` and the entry (`context.offset`), and a recorded
position never fires again on that anchor, whatever entry sits there.
So a Session Home save, a lobby End edit or a Settings import that
would put a different entry on a position already sent or skipped, on
the anchor the session will hold, is refused
(`scheduled_events.fired_offset_errors`; findings Bc1, ruled
2026-10-07): a sent entry stays at its position, new entries go after
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
NULL slots impose no constraint. The Start ↔ End and End ↔
Release-from pairs are enforced by
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
| Release-until ≤ Release-from | `Release responses until must be after Release responses from.` |
| Release-until > Release-from + 365d | `Release responses until must be within 365 days of Release responses from.` |

The **Settings CSV import** enforces the chain too (findings G22,
ruled 2026-10-06), in its parse phase, so a violating file is refused
whole and nothing is applied. It checks the three pairs through
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
cleared or moved in the file (author's ruling, 2026-10-06;
`spec/csv_contracts.md`).

The create form (`session_new.html`) also pins the same chain
client-side via `min` / `max` attributes on each `datetime-local`
input and a small partial
(`operator/partials/_schedule_ordering_js.html`) that live-updates
the bounds as the operator types, so invalid choices grey out in
the picker. Session Home's Details card sets no bounds on its
inputs. Either way the server check is the load-bearing safety net
(mobile pickers silently round around `min` / `max` in some
browsers, and direct POSTs bypass the picker entirely).

### 8.3 Implementation notes

- **Trigger mechanism — lazy observer.**
  Scheduled-event triggers extend the lazy deadline-observer
  pattern (§4) rather than running a separate background worker:
  each operator GET to a session-related page (Session Home,
  Operations pages, Sessions lobby) runs the per-anchor sweep
  for that session, fires anything past its scheduled time, and
  short-circuits on no-op. No new processes / cron / queue
  infra. Trade-off: a scheduled event "fires at the next
  operator GET ≥ scheduled time" — which is fine for events
  with reasonable lead time, but constrains *how close to the
  fire moment* the operator can schedule (the lead-time floors
  are in `spec/settings_inventory.md` §2).
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
  the observer could fire the same trigger twice. Each trigger
  opens with `SELECT … FOR UPDATE` on the session row plus an
  idempotency check (`if session.scheduled_X_at is None: return`),
  both inside the same transaction as the column clear. The
  second racer sees `None` after the first racer commits and
  no-ops.
- **Retry policy.** If a precondition passes but the underlying
  transition raises (transient DB error, etc.), the trigger
  emits `session.scheduled_X_retry` (audit only — no schedule
  clear). Subsequent operator GETs re-attempt the same trigger.
  The trigger counts `scheduled_X_retry` events for the current
  scheduled-fire moment from the audit log; **after 3 failed
  retries** it emits `session.scheduled_X_failed_persistent`,
  clears the schedule, and stops. Retries are paced by operator
  visits — no time-based throttle for MVP. **Only activation
  implements this.** For invites and reminders the retry and
  terminal state are work in progress awaiting Azure
  (`guide/post_azure_todo_checklist.md` item 7). Until then
  `observe_scheduled_events` runs each trigger guarded: one that
  raises has its uncommitted work rolled back (anything it already
  committed, such as sent invitations, stays) and is logged,
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
