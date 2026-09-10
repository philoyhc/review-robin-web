# Session lifecycle — spec

**The state machine and gating contract that govern every session
mutation.** Four live states (`draft`, `validated`, `ready`,
`archived`), one reserved state (`expired`), the transitions
between them, the route + service gates that enforce them, and
the UI lock-card pattern that exposes them to operators.

This spec is the single source of truth for the lifecycle. Each
per-page spec referencing it should describe only what's
specific to that page; common state-machine rules live here.

Cross-references:

- **`app/services/session_lifecycle.py`** — implementation.
- **`spec/architecture.md`** "Session lifecycle (Segment 9.1)" —
  the original write-path narrative; this doc supersedes the
  scattered fragments there + every per-page spec's
  "lifecycle gating" sub-section.
- **`spec/visual_style_rrw.md`** "Warning surfaces — shared
  brown framing" — visual treatment of the lock card.
- **`spec/operator_ui_concept.md`** principle **P4** —
  *Lifecycle disables, never hides.*

---

## 1. State machine

```
        Validate Setup            Activate Session         Close session
   ┌─────────────────────→  ┌───────────────────────→  ┌──────────────→
draft                    validated                    ready           expired
   ←─────────────────────┘  ←───────────────────────┐  ←──────────────┘
   ↑    invalidate                Pause Session         Revert to draft
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
| `archived` | Archived | Filed out of the active lobby; deletes no data. Written by `archive_session` / `unarchive_session` (Segment 18A Part 3). Since the 18R archive harmonization `archive_session` accepts **any non-archived** starting state (draft / validated / ready / expired) — the Workflow card's per-session Archive button can fire from any state, while the lobby bulk-archive still pre-filters to `draft`. `unarchive_session` restores `archived → draft`. |

The internal enum is `SessionStatus` in
`app/services/session_lifecycle.py`. The display-label divergence
on `ready → "Activated"` is implemented by
`app/services/lifecycle_display.py::lifecycle_label` and applied
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
| `can_archive(session)` | session is **not** `ready` and **not** `archived` — the shared gate for the lobby "Purge and archive" and the Extract-data page's Archive card (18R archive harmonization) |

## 2. Transitions

Each transition is one service function in
`app/services/session_lifecycle.py`. All transitions emit a
single audit event and commit atomically.

### 2.1 `draft → validated` — `mark_validated(...)`

Called by `GET /operator/sessions/{id}/validate?activate=*`, the
validate-now path on Session Home, and (post-18F Part 1)
`POST /operator/sessions/{id}/workflow/prepare` — the Workflow
card's Prepare button runs Generate + Validate and flips
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

The **automatic** form, called from every setup-mutating service.
No-op for any status other than `validated`. The key invariant:
**any setup mutation invalidates a prior validated state**, so
the readiness check stays meaningful.

Call sites (every setup-mutating service in the codebase):

- `app/services/sessions.py` (session metadata edit)
- `app/services/csv_imports.py` (reviewer + reviewee roster
  imports)
- `app/services/reviewers.py` (per-row reviewer CRUD + bulk
  status flips)
- `app/services/reviewees.py` (per-row reviewee CRUD + bulk
  status flips)
- `app/services/relationships.py` (pair-context import +
  delete-all + per-row CRUD)
- `app/services/assignments/` (`replace_assignments` +
  `delete_all_assignments`)
- `app/services/field_labels.py` (per-session friendly-label
  set / clear)
- `app/services/session_config_io/_apply.py::apply_session_config`
  (full settings import)
- `app/services/instruments/_instrument_crud.py`
  (instrument CRUD)
- `app/services/instruments/_response_fields.py` (response
  field CRUD + bulk save)
- `app/services/instruments/_display_fields.py` (display
  field CRUD)

The invariant lives at the **mutation site** — a route that
forgets to wrap its service call no longer silently breaks it.

**Visibility-when-closed exemption.** The
`set_responses_visible_when_closed` service deliberately does
**not** invalidate. The `responses_visible_when_closed` flag is a
display setting that doesn't affect the validation snapshot (an
operator can flip it without re-running validation). *(The bulk
`bulk_set_visibility` and `bulk_set_accepting` services carried the
same exemption but retired in 18R Item 3; per-instrument
open/close on a `ready` session likewise never invalidates, since
the session isn't in `validated` to begin with.)*

### 2.4 `validated → ready` — `activate_session(...)`

Called by `POST /operator/sessions/{id}/activate` and by
`POST /operator/sessions/{id}/workflow/activate` (the Workflow
card's solo Activate button, post-18F Part 1). Flips the
session to `ready` and sets `accepting_responses=true` on every
instrument in the same transaction. Pre-conditions:

- Session is `validated`. (Raises `not_validated`.)
- Readiness report still has no errors. (Raises `has_errors`.)
- If warnings exist, the operator must have set
  `acknowledge_warnings=true` on the request. (Raises
  `needs_acknowledge`.)

Activation also clears `Instrument.deadline_closed_at` on every
instrument — a previously deadline-closed instrument re-opens.

Audit event: `session.activated` with `counts={"warnings": N,
"info": N, "instruments": N}` and `context={"prev_status":
"validated", "override_warnings": bool}`.

### 2.5 `ready`/`expired → draft` — `revert_session_to_draft(...)`

The "Pause Session" path. Called by `POST
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

When the operator clicks "Revert to draft" on a Setup page or on
the Next Action card while the session is `validated`, the
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
untouched** (drafts + submitted), so reviewers with
`responses_visible_when_closed=True` instruments can still read
what they submitted after the close.

Pre-conditions:

- Session is `ready`. (Raises `not_ready`.)

From `expired` the operator reopens the session for editing via
Revert to draft (§2.5), which accepts `expired` alongside `ready`.

Audit event: `session.expired` with
`counts={"closed_instruments": N}`.

## 3. Route-layer gates

Two helpers in `app/web/routes_operator/_shared.py` enforce the
state machine at the request boundary:

### 3.1 `_require_editable(session)`

Raises **HTTP 409 Conflict** when the session is not `draft` or
`validated`. Operator setup-mutation endpoints (session edit,
roster import, roster delete-all, relationships CRUD, assignment
generate, assignment delete-all, Quick Setup, settings import,
etc.) call this **first**.

Two corrections to what this list used to claim, both found by the
`spec-writer` pass on Segment 19I Item 6 and both predating it:

- **Instrument CRUD does not call this helper.** Its ~24 route
  sites call `_require_instrument_editable` →
  `_can_edit_instrument`, a separate helper that since Item 6
  carries the *same* predicate (`is_editable`) and raises the same
  409 with its own detail message. Same rule, different function.
- **The email-template editor calls no lifecycle gate at all**, so
  it never belonged here — §5 below has always said so, and the
  two passages contradicted each other.

Detail message: `"Session is <status>; revert to draft to edit"`.

### 3.2 `_require_response_loss_ack(db, session, ack)`

Raises **HTTP 400 Bad Request** when responses already exist and
the request didn't carry `acknowledge_response_loss=true`. Called
from routes whose mutations would invalidate stored reviewer
responses (roster delete-all, assignment delete-all, full
session delete).

Detail message: `"Existing reviewer responses will be discarded;
tick 'acknowledge response loss' to proceed"`.

### 3.3 `_require_validated_or_ready(session)`

Raises **HTTP 409 Conflict** when the session is `draft`
(invitation actions need at least the assignment pairs to be
settled). Every invitation route in
`app/web/routes_operator/_operations.py` calls it —
`POST /invitations/generate`, `send-all`, `regenerate-all`,
per-row `regenerate` / `send` / `remind`, and the bulk
`remind-incomplete`. 18F Part 2 relaxed this from a stricter
"ready only" gate so an operator can notify reviewers
**before** activation (the Prepared / pre-open scenario);
**Send reminders** and reviewer write-path gates remain
`ready`-only.

Detail message: `"Invitations can only be issued once the
session has been prepared (validated or ready)."`

These three gates are the only thing that stops a direct POST
from bypassing the lifecycle. The corresponding GET pages render
read-only banners but the source of truth is the route gate.

## 4. Per-instrument lifecycle

Within a `ready` session, each instrument has its own
open/close state plus a visibility-when-closed display flag.

| Column | Type | Meaning |
|---|---|---|
| `accepting_responses` | `Boolean` | Reviewers can save / submit. Auto-set on activate, auto-cleared on revert and on deadline-close. |
| `responses_visible_when_closed` | `Boolean` | Whether reviewers can still see their own past responses after `accepting_responses=False`. Operator default; doesn't affect the validation snapshot. |
| `deadline_closed_at` | `DateTime \| None` | Timestamp the deadline-close fired. Used to render the "auto-closed at X" pill. |

**Services:**

- `open_instrument(...)` / `close_instrument(...)` — operator
  flips on the Instruments page. Requires session `ready` and
  pre-deadline. (The legacy group-scoped "no pinned `rule_set_id`"
  gate retired in Wave 5 PR 5.3 — group-scoped instruments now
  default to the synthetic Full Matrix on untouched Band 1 just
  like individual ones, so `activate_session`'s bulk open opens
  every instrument and `open_instrument` no longer raises
  `group_instrument_no_rule`.) Emit `instrument.opened` /
  `instrument.closed reason=operator` audit events.
- `set_responses_visible_when_closed(...)` — operator flips the
  display flag. No lifecycle gating beyond `_require_editable` /
  `_require_status_ready` on its route; **does not invalidate**
  per §2.3.
- `observe_deadline(...)` — lazy deadline-close. Idempotent. Called
  by the reviewer write-path predicate
  `session_accepts_responses` and by operator GETs that render
  per-instrument status. The first request after the deadline
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
upstream of this check (per 18F Part 2):

- If the session is not yet `ready` (draft or validated), the
  route renders the dedicated **pre-open page**
  (`reviewer/pre_open.html`) — "this review hasn't opened yet,
  check back later". The reviewer reached here via roster + an
  invitation token that was sent ahead of activation.
- If the session is `ready` but the per-instrument predicate
  returns `False` (deadline passed, instrument manually closed),
  the existing surface template renders read-only with the "no
  longer accepting responses" banner; the
  `responses_visible_when_closed` toggle decides whether the
  saved values render below.

See `spec/reviewer-surface.md` §"Lifecycle gating" for the full
GET-side rendering rules.

## 5. UI lock-card pattern

**On the four roster Setup pages** (Reviewers / Reviewees /
Relationships / Observers) whenever the session is **not
editable** — i.e. not `draft` and not `validated`: the
mutating-card grid (Upload, Danger Zone) is hidden and a
**yellow lock card** renders in its place, explaining that setup
is locked and offering the way out that state has.

All four render one partial,
`operator/partials/_roster_lock_card.html`, parameterized on the
sentence subject and the page's `return_to` slug (Segment 19H
Item 6). It branches three ways, matching Instruments:

| State | Copy | Control |
|---|---|---|
| `ready` | "cannot be modified while the session is ongoing" | inline revert form |
| `expired` | "cannot be modified because the session is **closed**" | inline revert form |
| `archived` | "cannot be modified because the session is archived" | link to `/operator/sessions/archived`, **no control** |

`expired` displays as **Closed** to an operator
(`app/services/lifecycle_display.py`), so the copy says closed.
`archived` carries no revert form because `/revert` answers 409
from there and a button would be a dead control.

**Instruments answers to the same predicate** (Segment 19I Item 6)
through its own helper: `_require_instrument_editable` →
`_can_edit_instrument`, which is `lifecycle.is_editable(...)`. It
was `not is_ready` until then, which protected the instrument
surface exactly while the session was *collecting* and stopped
protecting it the moment collection **ended** — so on `expired`
and `archived` the page rendered live Delete buttons, the routes
permitted the delete, and the `Instrument` → `assignments` →
`responses` cascade took submitted answers with it. The page's
`can_edit` reads the same predicate, so page and route agree by
construction.

`is_ready` still guards what it actually describes on that page:
the per-instrument **Open** / **Close** controls, which are
collection-phase actions rather than setup mutations.

The page differs from the roster four in shape, not in gate: it
has no Upload or Danger Zone card to hide, and its **lock card
covers all three locked states**, each naming the way out that
state has — `ready` and `expired` carry the inline revert form
(`revert_session_to_draft` accepts both), while `archived` names
the lobby's Unarchive and offers no control, because `/revert`
answers 409 from `archived` and a button there would be a dead
control. See `spec/instruments.md`.

**Every setup-mutation control on those pages answers that one
predicate** as of Segment 19H Item 7. The friendly-label editor was
the last that did not: gated on `is_ready` alone since Segment 15A,
it accepted a save on `expired` and `archived` — 303, not 409 —
while the lock card two elements above said the roster could not be
modified. That contradiction became visible only when Item 6 put the
card on those two states, which is the general shape: a gate nobody
questions stays invisible until something adjacent starts asserting
its opposite. Both halves of the editor's gate — the template's
`disabled` and `_save_field_labels` — now read `is_editable`. See
`spec/setup_pages.md`.

**The gate is `is_editable`, not `is_ready`** (Segment 19I Item 3).
It was the latter until then, which is only `status == "ready"`,
so `expired` and `archived` sessions rendered the Upload and
Danger Zone cards — and, on the roster pages, row checkboxes and a
live Delete — while every route behind them returned 409. The
page now offers what `_require_editable` will accept and nothing
else; §3.1 is the authority and the templates read the same
predicate.

**The roster pages' selection surface follows the same gate**: row
checkboxes, the selection-driven Edit / Inactivate / Activate /
Add / Delete controls, the selected-count pill and the delete
confirmation render only while editable. The read-only half of
the strip — the Status filter, the search box and Clear —
renders in every state, because reading a finished session's
roster is legitimate. So does the preview-count line, which
since Item 4 sits above the **preview table** rather than in the
strip, and since Item 10 is shared by all seven preview pages
(`spec/setup_pages.md`, "Preview tables"). **Observers is the one exception,
on checkboxes only**: theirs stay live until `archived` because
they drive the cohort rule editor (`spec/setup_pages.md`), which
is deliberately usable mid-session; its bulk *card* follows the
common gate.

**The gap 19I.3 left is closed** (Segment 19H Item 6). Between
19I.3 and then, the roster cards were keyed to `is_ready` while
every control on those pages had moved to `is_editable`, so on
`expired` and `archived` the pages were correct and silent —
mutating cards absent, nothing saying why. The card and the
controls now answer the same predicate, so they agree by
construction rather than by coincidence.

The lock card's "Revert to draft" form posts a `return_to` slug so
the operator lands back on the page they were trying to edit. The
route honours it only when it matches `_REVERT_RETURN_TO`
(`app/web/routes_operator/_shared.py`) — `reviewers`, `reviewees`,
`relationships`, `observers`, `assignments`, `instruments`,
`validate`, `previews`, `invitations`, `responses`,
`extract-data` — and otherwise falls through to Session Home. That
fallback is what stops a crafted slug steering the redirect, so the
set is an allowlist rather than a hint.

This paragraph named a page set that never existed until Segment
19H Item 6: it listed `setup-invite`, which is not in the
allowlist and which no template posts, and it listed
`relationships` as though it worked. `relationships` and
`observers` were **missing** from the allowlist while both
templates posted them, so reverting from either card fell through
to Session Home — an operator reverting *so they could edit
relationships* landed on Home, and a 303 to a real page looks like
success. Item 6 rung 1 added both slugs. The prose is recorded
here rather than silently corrected because a spec sentence that
asserts a control works is the reason nobody checked it.

The **Email Template** page is the exception: it renders no lock
card and its routes carry no `_require_editable`, so email copy
stays editable in every lifecycle state — see
`spec/email_template_editor.md` §5.

**Visual treatment:** `accent-amber-dark` border, `accent-amber-bg`
interior, outline-amber button. Documented in
`spec/visual_style_rrw.md` "Warning surfaces — shared brown
framing".

**Session Home is the exception.** The Next Action card carries
its own state-aware copy (per `spec/session_home.md`), so Home
doesn't stack a yellow lock card on top — disabled treatment on
Home is plain greying-out. The Quick Setup card on Home follows
the same convention (body-greyed, Lock/Unlock toggle visible but
inert at the service layer).

**Assignments answers to the same predicate** (Segment 19I Item
8), and splits the way the roster pages do: the selection-driven
half — row checkboxes, select-all, the bulk form, the
selected-count pill, `Inactivate` / `Activate` — renders only
while `is_editable`, which is what its five mutating routes
enforce; the read-only half — the `Search by:` select, the search
box, `Clear` — renders in every state, as does the preview-count
line above the table (Segment 19I Item 10 moved it out of the
strip here too). Its
per-instrument self-review toggle answers to the same predicate but
in the other manner: it **stays on the page and disables**, where
the bulk controls disappear — the row it sits in is a status table
that reads in every state. Its disabled title names each state's own
way out, as the Instruments page's do.

It was gated whole on `not is_ready`, which disagreed with those
routes on **three of five** states in both directions: `expired`
and `archived` offered live controls the routes refuse, and
`ready` lost the search along with them — on the state an operator
is most likely reading that page in. Assignments takes **no lock
card**, for the reason Instruments' presence makes sharper: the
four roster pages still have none, and a third variant would widen
that gap rather than close it. See `spec/assignments.md`.

**Operations pages** (Validate / Assignments / Previews /
Invitations / Responses) while session is `draft` / `validated`:
each page renders its own "session not yet activated" banner if
the surface needs an active session; most Operations surfaces
are read-mostly so they work in any state.

## 6. Audit events (full list)

| Event type | Emitted by | Detail envelope |
|---|---|---|
| `session.validated` | `mark_validated` | `counts={"warnings": N, "info": N}` |
| `session.invalidated` | `invalidate_session` (called via `invalidate_if_validated` or directly) | `reason=<string>` (`setup_mutation`, `operator_revert`, etc.) |
| `session.activated` | `activate_session` | `counts={"warnings": N, "info": N, "instruments": N}` + `context={"prev_status": "validated", "override_warnings": bool}` |
| `session.reverted_to_draft` | `revert_session_to_draft` | `counts={"closed_instruments": N, "responses_at_revert": N}` |
| `session.expired` | `expire_session` (Workflow-card **Close session**) | `counts={"closed_instruments": N}` |
| `session.archived` | `archive_session` | `changes={"status": [<from_status>, "archived"]}` |
| `session.unarchived` | `unarchive_session` | `changes={"status": ["archived", "draft"]}` |
| `session.responses_released` | `release_responses_now` (Workflow-card **Release responses**) | `snapshot={"responses_release_at": …, "cleared_until": bool}` |
| `session.responses_release_stopped` | `stop_responses_release` (Workflow-card **Stop releasing**) | `snapshot={"responses_release_until": …}` |
| `session.workflow_run_started` | `POST /workflow/prepare` and `POST /workflow/activate` (18F Part 1) — bracket the run, once per click | `context={"button": "prepare_session" \| "activate_session"}` |
| `session.workflow_run_failed` | same two routes when the chain raises | `context={"button": …, "step": "generate" \| "validate" \| "activate" \| "precondition", "error_message": …}` |
| `instrument.opened` | `open_instrument` | `refs={"instrument_id": id}` |
| `instrument.closed` | `close_instrument` or `observe_deadline` | `refs={"instrument_id": id}` + `reason=<"operator" \| "deadline">` (+ `context={"deadline": "..."} ` on the deadline path) |
| ~~`instruments.bulk_accepting_responses`~~ / ~~`instruments.bulk_visibility_when_closed`~~ | *Retired 18R Item 3* — the bulk accepting + bulk visibility-when-closed toggles and their emitters were removed. | — |

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
   now actively written states; no `SessionStatus` value is
   purely reserved today.

## 8. Scheduled lifecycle automation (Segment 18G — forthcoming)

The operator-facing automation surface for time-based lifecycle
events. Schema landed in **Segment 18G Part 0** (shipped
2026-05-20 — see
`guide/archive/segment_18G_scheduled_events.md` Part 0); the
consumer services land in Parts 1 → 5, ordered by workflow
sequence (activation → invites → reminders → archive → retention).
This section documents the persistent model + the cross-cutting
rules **all** scheduled triggers obey, so each Part doesn't
re-litigate them.

### 8.1 Model — anchors + offsets

Every scheduled event resolves to one **anchor datetime** plus an
**offset** anchored on it. The operator picks anchors on a
calendar; offsets are operator-set in a human shape ("1 day
before End", "30 days after End") and persisted as ISO 8601
durations.

**Anchors (absolute datetimes on `sessions`):**

| Anchor | Column | Owner | Status |
|---|---|---|---|
| **Start** (auto-activate) | `scheduled_activate_at` | operator-set | **18G Part 0a** |
| **End** (deadline) | `deadline` | operator-set | live today |
| **Release-from** (Participants platform — reviewees / observers can view responses) | `responses_release_at` | operator-set | Wired end-to-end in W14 / PR #1716 — no lead-time floor; operator can backdate. W16 + W17 consume it inside their per-instrument window gates (sections / instrument cards stay empty until the window opens). **Segment 19F PR 4 moved the reviewee half to the route**: `require_reviewee_with_current_grant` refuses `/results` with a bare 404 when no instrument grants that reviewee anything under the windows open now, so the empty-page state no longer exists for them. The observer half is unchanged — `/collation` has no route-level window gate, and instrument cards fall through to the empty state. Since PR 2a the window also requires the session **`expired`**, not merely the anchor reached — so an anchor set by any other path (a backdated one on Session Edit or Quick Setup, or one left behind by `revert_session_to_draft`) no longer opens it. The Workflow card's **Release responses** button is offered only on an expired session and was already gated that way; PR 2a moved the same rule into the predicate (2026-06-02, amended 2026-09-07). |

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
| Auto-send invites | `invite_offsets` | `scheduled_activate_at` | JSON list of ISO 8601 durations, e.g. `["-P1D", "-PT2H"]` | empty (no auto-send) | 18G Part 2 |
| Auto-send reminders | `reminder_offsets` | `deadline` | JSON list of ISO 8601 durations, e.g. `["-P2D", "-PT4H"]` | empty (no auto-send) | 18G Part 3 |
| Auto-archive | `archive_offset` | `deadline` | single ISO 8601 duration, e.g. `"P30D"` | **`P30D`** (gives operator time to download data post-deadline before the session leaves the active lobby) | 18G Part 4 (deferred — see `guide/deferred_consolidated.md`) |
| Release-until | `responses_release_until` (absolute datetime; S12 swap retired `release_until_offset`) | n/a — column carries the absolute close time | DateTime(tz) | unset | Wired end-to-end via W14 (anchor) + S12 (datetime swap). The form input is a `datetime-local`; save-time validator enforces ordering (must close after `responses_release_at`) + 365-day magnitude check. The Workflow card's **Stop releasing** button (2026-06-02) writes the same column (`= now()`). W16 + W17 consume it inside their per-instrument window gates; route-level gate stays unimplemented. |
| Auto-delete after archive | `retention_overrides.delete_after_archive` (JSON key inside `retention_overrides`) | archive timestamp | single ISO 8601 duration | unset (use deployment env-var default) | 18G Part 5 (deferred — see `guide/deferred_consolidated.md`) |

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

This is enforced at **one** call site: a `resolve_offset(session,
anchor_field, offset_field) -> datetime | None` helper that every
scheduler path uses. Anchor-null short-circuits to `None`;
unset offset short-circuits to `None`; otherwise the helper adds
the parsed ISO 8601 duration to the anchor and returns the
resulting datetime.

**8.2.3 Event-precondition guard.** Beyond the anchor, each
scheduled event has its own operational preconditions — system
state that must hold at fire time for the transition to be
legal. The trigger checks the precondition first; if unmet, it
emits a `…_skipped` audit event with `reason=<precondition>`,
clears the relevant column / list entry (one-shot), and returns
without retrying. Per-event preconditions:

| Event | Precondition at fire time | Skip reason |
|---|---|---|
| Scheduled activation (Part 1) | `session.status == "validated"` | `not_validated` |
| Auto-send invites (Part 2) | `session.status in {"validated", "ready"}` (Prepared) **and** invitations already created (the operator ran "Create invitations") | `not_prepared` / `invitations_not_created` |
| Auto-send reminders (Part 3) | `session.status == "ready"` (subsumes Prepared) **and** invitations exist **and** within accepting-responses window | `not_ready` / `no_invitations` / `outside_response_window` |
| Auto-archive (Part 4) | `session.status == "draft"` (18A's draft-only archive) | `not_draft` |
| Auto-delete after archive (Part 5) | `session.status == "archived"` | `not_archived` |
| Release-from (Participants platform) | session has been closed after at least one run (responses exist) | `no_responses_run` |
| Release-until (Participants platform) | Release-from has already fired | `release_not_started` |

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
fire once (archive, release-until, auto-delete) carry a single
ISO 8601 string. Per-list-entry dedup uses the entry's index
(e.g. `reminder:{session_id}:{reviewer_id}:{offset_index}`) so a
re-ordered list doesn't re-fire already-sent reminders.

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

The forms also pin the same chain client-side via `min` /
`max` attributes on each `datetime-local` input and a small
shared partial (`operator/partials/_schedule_ordering_js.html`)
that live-updates the bounds as the operator types. The
client check makes invalid choices grey out in the picker;
the server check is the load-bearing safety net (mobile
pickers silently round around `min` / `max` in some browsers,
and direct POSTs bypass the picker entirely).

### 8.3 Implementation notes

- **Trigger mechanism — lazy observer.** Settled 2026-05-20.
  Scheduled-event triggers extend the lazy deadline-observer
  pattern (§4) rather than running a separate background worker:
  each operator GET to a session-related page (Session Home,
  Operations pages, Sessions lobby) runs the per-anchor sweep
  for that session, fires anything past its scheduled time, and
  short-circuits on no-op. No new processes / cron / queue
  infra. Trade-off: a scheduled event "fires at the next
  operator GET ≥ scheduled time" — which is fine for events
  with reasonable lead time, but constrains *how close to the
  fire moment* the operator can schedule (see the per-event
  minimum-lead-time rule below).
- **Past-time editor rule.** The editor **rejects** an anchor
  or offset on **save** if the resolved fire time is in the
  past at the moment of saving. The operator can't *set* a
  past schedule. But a value that *became* past after saving
  (e.g. the operator set Start for tomorrow, then invalidated
  through the deadline) **stays put**; the fire-time
  precondition guard handles it normally (typically firing on
  the next operator visit if the precondition is also satisfied).
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
  visits — no time-based throttle for MVP.
- **Operator notification on skip / failure.** MVP: audit
  events only, plus a **Session Home banner** on the next
  operator visit ("Scheduled activation skipped at «X» —
  reason: «reason»"). Email notifications via 14B are deferred
  until pilot feedback.
- **Audit events** — each consumer Part defines its own emitters
  (`session.activated`, `session.archived`, `session.invitations_sent`,
  `session.reminder_batch_enqueued`, `session.purged`); each
  scheduled-trigger emit carries `context.trigger="scheduled"`
  to distinguish from operator-initiated fires. The
  *configuration-change* events
  (`session.invite_schedule_updated`,
  `session.reminder_schedule_updated`, etc.) land alongside the
  editor surfaces that write them.
- **Settings CSV round-trip** — every Part 0 column is exported
  / imported in the Settings CSV as the consumer Part lights it
  up (18D Part 5 already rides Part 5 for the retention
  columns).
