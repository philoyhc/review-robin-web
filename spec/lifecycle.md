# Session lifecycle — spec

**The state machine and gating contract that govern every session
mutation.** Three live states (`draft`, `validated`, `ready`),
two reserved states (`expired`, `archived`), the transitions
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
        Validate Setup            Activate Session
   ┌─────────────────────→  ┌───────────────────────→
draft                    validated                    ready
   ←─────────────────────┘  ←───────────────────────┐
        invalidate                Pause Session
        (any setup mutation)     (with confirm)
```

| State | Display label | Meaning |
|---|---|---|
| `draft` | Draft | Setup is open; reviewer surface read-only. |
| `validated` | Validated | Readiness check passed; setup still open but signals "ready to activate". |
| `ready` | **Activated** | Reviewer surface accepting writes; setup locked. |
| `expired` | Expired | Reserved (Segment 9.3+, deadline-passed terminal state). Not written by any current route. |
| `archived` | Archived | Reserved (Segment 12+, post-export retention). Not written by any current route. |

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
| `is_editable(session)` | session is `draft` OR `validated` (the **editable-state predicate** that every route-layer gate consults) |

## 2. Transitions

Each transition is one service function in
`app/services/session_lifecycle.py`. All transitions emit a
single audit event and commit atomically.

### 2.1 `draft → validated` — `mark_validated(...)`

Called by `GET /operator/sessions/{id}/validate?activate=*` and
the validate-now path on Session Home. Idempotent (no-op when
already `validated`). Raises `LifecycleError(code="has_errors")`
when the readiness report carries blocking errors.

- Warnings are implicitly acknowledged at the moment of transition
  (info-severity findings are advisory only — they don't trigger
  the acknowledgment ceremony).
- Audit event: `session.validated` with
  `counts={"warnings": N, "info": N}`.

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
- `app/services/csv_imports.py` (reviewer + reviewee imports)
- `app/services/relationships.py` (pair-context import +
  delete-all)
- `app/services/assignments.py` (`replace_assignments` +
  `delete_all_assignments`)
- `app/services/session_config_io.py::apply_session_config` (full
  settings import)
- `app/services/instruments/_instrument_crud.py`
  (instrument CRUD)
- `app/services/instruments/_rtds.py` (RTD CRUD + cascade
  delete)
- `app/services/instruments/_response_fields.py` (display +
  response field CRUD + bulk save)

The invariant lives at the **mutation site** — a route that
forgets to wrap its service call no longer silently breaks it.

**Visibility-when-closed exemption.** Two services deliberately
do **not** invalidate: `bulk_set_visibility` and
`set_responses_visible_when_closed`. The
`responses_visible_when_closed` flag is a display setting that
doesn't affect the validation snapshot (an operator can flip it
without re-running validation). Same logic exempts the bulk
accepting toggle (operators flipping `accepting_responses` on a
`ready` session don't invalidate anything because the session
isn't in `validated` to begin with).

### 2.4 `validated → ready` — `activate_session(...)`

Called by `POST /operator/sessions/{id}/activate`. Flips the
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

### 2.5 `ready → draft` — `revert_session_to_draft(...)`

The "Pause Session" path. Called by `POST
/operator/sessions/{id}/revert`. Flips to `draft` and sets
`accepting_responses=false` on every instrument in the same
transaction. **Existing `Response` rows are preserved untouched**
— the reviewer surface returns to read-only, but the data is
intact.

Pre-conditions:

- Session is `ready`. (Raises `not_ready`.)
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

## 3. Route-layer gates

Two helpers in `app/web/routes_operator/_shared.py` enforce the
state machine at the request boundary:

### 3.1 `_require_editable(session)`

Raises **HTTP 409 Conflict** when the session is not `draft` or
`validated`. Every operator setup-mutation endpoint (session
edit, roster import, roster delete-all, instrument CRUD,
relationships CRUD, assignment generate, assignment delete-all,
Quick Setup, settings import, email-template editor, etc.) calls
this **first**.

Detail message: `"Session is <status>; revert to draft to edit"`.

### 3.2 `_require_response_loss_ack(db, session, ack)`

Raises **HTTP 400 Bad Request** when responses already exist and
the request didn't carry `acknowledge_response_loss=true`. Called
from routes whose mutations would invalidate stored reviewer
responses (roster delete-all, assignment delete-all, full
session delete).

Detail message: `"Existing reviewer responses will be discarded;
tick 'acknowledge response loss' to proceed"`.

These two gates are the only thing that stops a direct POST from
bypassing the lifecycle. The corresponding GET pages render
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
  pre-deadline. Emit `instrument.opened` /
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

This is the **only** lifecycle check the reviewer surface
performs. If it returns `False`, the route returns 403 with a
"session is no longer accepting responses" surface and the
reviewer-side template renders read-only (inputs disabled, no
Save / Submit buttons).

## 5. UI lock-card pattern

**On Setup pages** (Reviewers / Reviewees / Relationships /
Instruments / Email Template) while session is `ready`: the
mutating-card grid (Upload, Danger Zone) is hidden and a
**yellow lock card** renders in its place with copy explaining
that setup is locked and offering a "Revert to draft" inline
form.

The lock card's "Revert to draft" form carries a `return_to`
query param scoped to the page set (`reviewers`, `reviewees`,
`relationships`, `instruments`, `setupinvite`) so the operator
lands back on the page they were trying to edit after the
revert.

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
| `instrument.opened` | `open_instrument` | `refs={"instrument_id": id}` |
| `instrument.closed` | `close_instrument` or `observe_deadline` | `refs={"instrument_id": id}` + `reason=<"operator" \| "deadline">` (+ `context={"deadline": "..."} ` on the deadline path) |
| `instrument.bulk_accepting_responses` | bulk open/close on the All Instrument Status card | `counts={"opened": N, "closed": N}` + `context={"target": "open" \| "close"}` |
| `instrument.bulk_visibility_when_closed` | bulk visibility toggle | `counts={"showing": N, "hidden": N}` + `context={"target": "show" \| "hide"}` |

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

5. **Reserved enum values are real values.** `expired` and
   `archived` are in the canonical enum even though no route
   writes them today — the column is constrained at the
   application layer, not via a DB CHECK.
