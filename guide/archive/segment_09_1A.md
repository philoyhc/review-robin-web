# Segment 9.1A Implementation Plan — Session readiness, activation, and response-window gates

**Status:** Implementation plan for Segment 9.1 (single PR). Segment 9 is split
into three PR-sized blocks: **9.1**, **9.2**, **9.3**. This file is the A-plan
for 9.1 only and does **not** further split 9.1.

## 9.1 outcome

Deliver one PR that adds operator-controlled lifecycle gating around when a
session can accept reviewer responses, with auditable transitions, strict
route gating, and pre-positioned schema for later states.

---

## Decisions locked for 9.1

### Lifecycle states
1. `ReviewSession.status` stays a `String(32)` column. A Python
   `Literal["draft","ready","expired","archived"]` (or equivalent enum class)
   holds the canonical value set in the service layer. **No DB CHECK
   constraint.** Active values used in 9.1: `draft`, `ready`. `expired` and
   `archived` are reserved (recognised by the validator, not yet writable from
   any route).
2. The default for new sessions is `draft` (already today).

### Activation gate
3. Readiness validation distinguishes **errors** (block activation) from
   **warnings/info** (do not block, but require explicit operator consent to
   activate).
4. Activation entry point is a **button rendered next to the existing
   "validate" button** on the session detail page (and/or on the validation
   page). The button posts to a new `/operator/sessions/{id}/activate`
   endpoint. When only warnings/info exist, the form includes an explicit
   `acknowledge_warnings` checkbox; activation 400s without it.

### Instrument acceptance
5. Add `Instrument.accepting_responses: bool NOT NULL DEFAULT false`.
   Newly-created Default Instruments are **closed** until session activation
   flips them open.
6. **Session status overrides instrument state.** On activation, all of the
   session's instruments are flipped to `accepting_responses=true` in the
   same transaction as the status change. On revert-to-draft, all instruments
   are flipped to `accepting_responses=false`.
7. Add `Instrument.responses_visible_when_closed: bool NOT NULL DEFAULT false`
   as operator-managed configuration (pre-positioning; reviewer surface honors
   it in 9.1 — see #14 below).
8. Add `Instrument.deadline_closed_at: DateTime|None` to make the lazy
   deadline-close audit emission idempotent (event fires exactly once, the
   first time any reviewer or operator request observes
   `now() >= session.deadline` while the instrument is still flagged
   accepting).

### Revert-to-Draft
9. Operator can revert `ready → draft` from session detail. Action requires a
   confirm checkbox. Side effects in a single transaction:
   - Set `session.status = "draft"`.
   - Set `accepting_responses = false` on all of the session's instruments.
   - **Preserve all existing `Response` rows untouched** (`submitted_at`
     included). Reviewers returning to the surface see it read-only.
   - Emit a single `session.reverted_to_draft` audit event. **No per-instrument
     close events on this path** (the session-level event covers it).

### Edits during Ready / after revert
10. While `status == "ready"`, the following endpoints return **HTTP 409** and
    do not mutate state:
    - `POST /operator/sessions/{id}/edit`
    - `POST /operator/sessions/{id}/delete`
    - `POST /operator/sessions/{id}/reviewers/import`
    - `POST /operator/sessions/{id}/reviewers/delete-all`
    - `POST /operator/sessions/{id}/reviewees/import`
    - `POST /operator/sessions/{id}/reviewees/delete-all`
    - `POST /operator/sessions/{id}/assignments/full-matrix`
    - `POST /operator/sessions/{id}/assignments/manual/import`
    - `POST /operator/sessions/{id}/assignments/delete-all`
    Their corresponding GET pages render an inline "session is Ready — revert
    to Draft to edit" banner and disable the form controls; the 409 is the
    hard backstop.
11. After revert (`status == "draft"` with prior responses still on disk),
    operations that would invalidate existing responses by cascade (roster
    delete-all + re-import, assignment delete-all + regenerate) **warn the
    operator and require an additional acknowledgement checkbox**
    (`acknowledge_response_loss`). A blocking warning lists the affected
    response count. The same acknowledgement gate applies to the
    session-level edit form when changes might invalidate responses (deadline
    moved earlier, code changed) — for 9.1 we apply it conservatively to
    every session edit when any responses exist.

### Reviewer write-path gate
12. A single predicate `session_accepts_responses(session, instrument)` returns
    true iff:
    - `session.status == "ready"`, **and**
    - `instrument.accepting_responses == true`, **and**
    - `session.deadline is None or now() < session.deadline`.
13. `POST /reviewer/sessions/{id}/save|submit|clear` evaluate the predicate
    before any write. On false, they return **403** with a "no longer
    accepting responses" page. Generic message — no per-gate detail.
14. The reviewer surface (`GET /reviewer/sessions/{id}`) renders read-only
    when the predicate is false. Inputs are `disabled`; the action buttons
    are hidden. If `instrument.responses_visible_when_closed == false` and
    the gate is closed because of the instrument flag (or the deadline), the
    saved response values are **not rendered** — the surface shows a
    "responses are not visible while this instrument is closed" notice.
    When the toggle is true, saved values render but remain non-editable.

### Per-instrument sub-page
15. New routes:
    - `GET /operator/sessions/{id}/instruments/{instrument_id}` — page shows
      instrument name, current `accepting_responses`, current
      `responses_visible_when_closed`, **read-only echo of the session
      deadline**, and the lazy `deadline_closed_at` if set.
    - `POST .../open` — sets `accepting_responses = true` (only if session is
      `ready` and `now() < deadline`); otherwise 409.
    - `POST .../close` — sets `accepting_responses = false`. Allowed in any
      session state (idempotent if already false).
    - `POST .../visibility` — toggles `responses_visible_when_closed`.
      Allowed in any session state.
16. Manual close / open events emit `instrument.closed reason=manual` /
    `instrument.opened`. The deadline path is covered by the lazy emitter
    (see #19).

### Lazy deadline close
17. Helper `observe_deadline(session)` is invoked at the top of every reviewer
    GET/POST in this session and on the per-instrument sub-page GET. If
    `session.deadline is not None and now() >= session.deadline`, for each of
    the session's instruments where `accepting_responses == true and
    deadline_closed_at is null`, set `accepting_responses = false`,
    `deadline_closed_at = now()`, and emit a single
    `instrument.closed reason=deadline` audit event per instrument.
    Idempotent because of the `deadline_closed_at` flag.

### Audit events (new)
18. `session.activated` — `detail = {prev_status, override_warnings: bool}`.
19. `session.reverted_to_draft` — `detail = {closed_instrument_ids: [...],
    response_count_at_revert: N}`.
20. `instrument.opened` — `detail = {instrument_id}`.
21. `instrument.closed` — `detail = {instrument_id, reason: "manual"|"deadline"|"revert"}`.
    9.1 only emits `manual` and `deadline`; `revert` reason is reserved (the
    bulk close on revert is captured at the session level).

---

## Implementation slices

### Slice 1 — Schema + migration
- New Alembic migration (`alembic/versions/...session_lifecycle_9_1...`):
  - Add `instruments.accepting_responses BOOLEAN NOT NULL DEFAULT false`.
  - Add `instruments.responses_visible_when_closed BOOLEAN NOT NULL DEFAULT false`.
  - Add `instruments.deadline_closed_at TIMESTAMPTZ NULL`.
- No change to `sessions` (column already exists; canonical values move to
  the service layer).
- Confirm SQLite + Postgres round-trip via existing test infra and CI smoke job.

### Slice 2 — Domain enums + readiness model
- New module `app/services/session_lifecycle.py`:
  - `SessionStatus` literal/enum with all four values.
  - `ReadinessReport` dataclass with `errors`, `warnings`, `info` lists; helper
    `can_activate(report) -> bool` (true iff no errors).
- Extend the existing setup-validation service to populate the new shape.

### Slice 3 — Activation / revert services + routes
- Service: `activate_session(session, *, acknowledge_warnings: bool)` and
  `revert_session_to_draft(session, *, confirm: bool)`.
- Routes: `POST /operator/sessions/{id}/activate`, `POST /operator/sessions/{id}/revert`.
- Templates: button + form on session detail; flash messaging; validation page
  shows the activation button when no errors.

### Slice 4 — Edit-lock enforcement
- Centralised `require_status_draft(session)` dependency or inline guard used
  by the nine listed POST endpoints.
- Templates show the read-only banner + disabled controls when status is
  `ready`.
- Add the `acknowledge_response_loss` checkbox path on roster delete-all,
  roster import (when responses exist), assignment delete-all, assignment
  generation, and the session edit form.

### Slice 5 — Per-instrument sub-page
- Service helpers `open_instrument`, `close_instrument`, `set_visibility`.
- Routes + Jinja template under `app/web/templates/operator/instrument_detail.html`.
- Link from session detail.

### Slice 6 — Reviewer surface gating
- `session_accepts_responses` predicate in
  `app/services/response_acceptance.py` (or co-located).
- Apply to `save`/`submit`/`clear` (403 + dedicated template).
- `GET /reviewer/sessions/{id}` consults the predicate +
  `responses_visible_when_closed` to choose render mode.
- `observe_deadline` helper called from reviewer GET/POSTs and per-instrument
  GET.

### Slice 7 — Audit
- Emit `session.activated`, `session.reverted_to_draft`, `instrument.opened`,
  `instrument.closed` (reasons `manual` and `deadline`).
- Single-event emission semantics on the deadline path enforced by
  `deadline_closed_at`.

### Slice 8 — Tests (~14 tests, SQLite via existing harness)
1. Default Instrument is created with `accepting_responses=false`.
2. Activate succeeds when readiness has no errors and no warnings.
3. Activate 400s when only warnings exist and `acknowledge_warnings` is missing.
4. Activate succeeds with `acknowledge_warnings=true` when only warnings exist.
5. Activate 409s when readiness has errors regardless of acknowledge flag.
6. On activation, all instruments flip to `accepting_responses=true` and
   `session.activated` audit row exists.
7. Revert requires confirm; without confirm 400; with confirm flips status,
   closes instruments, preserves `Response` rows + `submitted_at`, emits
   `session.reverted_to_draft`.
8. While Ready, each of the nine listed POST endpoints returns 409 and does
   not mutate.
9. After revert, deleting roster with existing responses 400s without
   `acknowledge_response_loss`; succeeds with it.
10. Reviewer save/submit/clear 403 when status is draft.
11. Reviewer save/submit/clear 403 when instrument is manually closed.
12. Reviewer save/submit/clear 403 when `now() >= session.deadline`.
13. Reviewer surface renders read-only with no values when
    `responses_visible_when_closed=false`; renders read-only with values when
    true.
14. Lazy deadline close fires exactly one `instrument.closed reason=deadline`
    event per instrument across multiple subsequent reviewer GETs;
    `deadline_closed_at` is set.

---

## Out of scope (explicitly deferred)

- **9.2:** invitation generation, dev outbox table, email send stubs, magic
  links (Segment 16).
- **9.3:** monitoring dashboard, reminder send.
- **Segment 10:** instrument builder (operator-editable response fields).
- **Segment 11+:** export, RuleBased, multi-instrument, production hardening.
- Operator UI for `expired` / `archived` transitions (schema-reserved only).
- Edit-while-Ready workflow + reviewer notification.

---

## Docs to update at PR time

- `docs/status.md`: add Segment 9.1 row, list new endpoints, new audit events,
  new Instrument columns, new Session lifecycle.
- `README.md`: only if dev-loop or test commands change (they shouldn't).
- `ARCHITECTURE.md`: short note that session status is canonical and overrides
  instrument acceptance.
