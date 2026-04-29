# Segment 9 (Superseding Plan) — split into 9.1 through 9.5

**Status:** This document supersedes `guide/segment_09_superseded_single_plan.md`. Current ship status:

- **9.1, 9.2, 9.3, 9.4A** — shipped (see `docs/status.md`).
- **9.4B** — planned, decisions locked (see `guide/segment_09_4B.md`); slice plan not yet drafted.
- **9.4C** — segment-level scope known (see `guide/segment_09_4_operator_ui_restructure_plan.md`); per-PR plan not yet drafted.
- **9.5** — decisions pre-locked inside `guide/segment_09_4B.md`'s "Deferred to Segment 9.5" section; standalone segment plan not yet drafted.

## Why split Segment 9
Based on the current codebase, `assumptions.md`, and the resolved decisions in `seg9stuff`, Segment 9 is too broad for a single PR-sized delivery. It mixes lifecycle controls, reviewer-access gating, invitations/email plumbing, monitoring, reminders, operator-UI restructuring, and a richer setup-readiness lifecycle.

This superseding plan breaks Segment 9 into smaller deliverables that can each ship safely with focused tests. 9.1–9.3 are the lifecycle/invitation/monitoring foundation; 9.4 reshapes the operator UI on top of that foundation; 9.5 enriches the lifecycle that 9.1 introduced.

---

## Segment 9.1 — Session readiness + activation lifecycle + response-window control [SHIPPED]

### Goal
Ship the operator controls that determine when a session is review-ready and when responses are accepted.

### Scope
- Session lifecycle foundation for MVP:
  - Introduce/confirm session states for **Draft** and **Ready** in this segment.
  - Keep **Expired** / **Archived** reserved for later segments, with optional lightweight pre-positioning only if low-cost.
- Activation flow:
  - Readiness validation gates activation.
  - Activation creates auditable state transition to Ready.
  - Allow revert from Ready back to Draft (per assumptions/decisions), also audited.
- Edit policy:
  - Block operator edits while Ready (no edit-while-active workflow yet).
- Per-instrument acceptance controls:
  - Keep `accepting_responses: bool` model.
  - Session deadline is authoritative for response acceptance.
  - Add `responses_visible_when_closed: bool` pre-position toggle.
  - Manual stop/resume accepting responses via operator sub-page.
- Reviewer route-level enforcement:
  - Save/submit/clear blocked when instrument/session is not accepting.
  - Reviewer page can render read-only state.
- Audit coverage:
  - Activation/revert and instrument open/close actions audited.
  - Lazy deadline-close audit event allowed.

### Out of scope
- Invitation generation/sending.
- Monitoring dashboard.
- Reminders.
- Magic-link/anonymous auth (Easy Auth sign-in remains required).

### Deliverable shape
One PR focused on lifecycle and gating mechanics with migration(s), service updates, route guards, and tests.

---

## Segment 9.2 — Invitations + dev outbox + reviewer-access links [SHIPPED]

### Goal
Ship invitation creation and delivery plumbing needed to bring reviewers into active sessions.

### Scope
- Invitation model/table and statuses (minimal MVP state machine).
- Invitation generation for assigned reviewers on activation-ready sessions.
- Token strategy aligned with decisions:
  - Strong token generation/hash approach.
  - Lifetime model without short expiry cutoff in this segment.
- Delivery behavior:
  - Dev-mode outbox table as primary implementation in this segment.
  - Real SMTP/provider integration deferred.
- Operator invitation visibility/actions sufficient for MVP.
- Audit coverage for invitation actions.

### Out of scope
- Monitoring aggregates.
- Reminder sends.
- Production email backend/provider hardening.

### Deliverable shape
One PR that is data-model + service + operator workflow focused, independent of reminder/dashboard complexity.

---

## Segment 9.3 — Monitoring + reminders [SHIPPED]

### Goal
Ship operator feedback loops after invitations are in place.

### Scope
- Monitoring page with per-reviewer progress and summary counts.
- “Send reminder to incomplete reviewers” action.
- Incomplete targeting includes:
  - not submitted, and
  - required missing cases (including warn-and-override path decision).
- Reminder audit events + last-reminder tracking.

### Out of scope
- Advanced analytics/charts.
- Complex reminder segmentation rules.
- Queue-based bulk delivery infrastructure.

### Deliverable shape
One PR focused on reporting + reminder behavior, using invitation plumbing from 9.2.

---

## Segment 9.4 — Operator UI restructure to the target page map

Implements the operator surface shape defined in `spec/target_operator_map.md`. Behavior from 9.1–9.3 is unchanged; only the navigation, page layout, and a small new `Delete Data` action change. Split into three PR-sized blocks for review-ability — see `guide/segment_09_4_operator_ui_restructure_plan.md` for the segment-level plan.

### 9.4A — Page chrome + breadcrumbs + sessions list reshape [SHIPPED]
- Global chrome on `base.html`: app-identity link to `/about`, breadcrumb partial, signed-in user card with Sign out.
- `app/web/breadcrumbs.py` factories; `_partials/breadcrumb.html`. Trails populated for every existing operator and reviewer page.
- Sessions list: per-row Access + Delete buttons; Create-new-session below the table.
- New `/about` stub. Per-page back-links removed from every operator and reviewer template.
- Detail: `guide/segment_09_4A.md`.

### 9.4B — Session detail four-card restructure + inline validate-summary + Delete Data [PLANNED]
- Session detail page restructured into four cards: **Session**, **Session setup** (table), **Run Session**, **Danger zone**.
- Inline validate-summary card surfaced via `POST /operator/sessions/{id}/validate-summary`; Activate button moves onto this card. The standalone `/validate` page becomes read-only.
- New `POST /operator/sessions/{id}/delete-data` wipes responses, preserves setup; emits `responses.deleted_all` audit event. Allowed in any session status.
- Setup-table rows for 9.4C-only surfaces (Instruments index, Set up invites) render now with their Manage buttons disabled.
- Edit-lock semantics unchanged from today (the richer `validated` state is deferred to 9.5).
- Detail: `guide/segment_09_4B.md` (decisions locked; slice plan still to come).

### 9.4C — Manage page reshapes + instruments index + placeholder pages [PLANNED]
- Reviewers / reviewees / assignments Manage pages: fold `…/import` GETs into anchored Upload-CSV cards on the Manage page; add disabled **Edit** buttons.
- Assignments page: add toggleable **Assign by Rules** placeholder card (no POST yet).
- New `/instruments` index page (single-card today; Add / Delete disabled until Segment 13).
- New `/setupinvite` and `/extract` stub pages.
- Closing-segment doc + `spec/operator_map.md` regen + `docs/status.md` refresh.
- Detail: not yet drafted.

### Out of scope (entire 9.4)
- Inline-editable tables for reviewers / reviewees / assignments (buttons disabled until a follow-on UX PR designs the inline-edit pattern once and reuses it across all three).
- Real `/assignments/rules` rule engine — Segment 12.
- Real `/setupinvite` email template editor — Segment 15.
- Real `/extract` data export — Segment 11.
- Add / delete instruments — Segment 13.
- Session-status changes — `validated` state lives in 9.5.

---

## Segment 9.5 — Setup-readiness lifecycle states [PLANNED]

### Goal
Add a stored `validated` state between `draft` and `ready` so operators can affirm "I've checked, looks good" without committing to lock. Decouples the two concerns today's single `status="ready"` conflates: edit-lock vs. validation-passed.

### Scope
- Add `validated` to the `SessionStatus` enum (string column already supports it; no schema migration beyond enum constants).
- Stamp `validated` from a successful validate-summary POST when there are no blocking errors and any warnings are acknowledged at the moment of transition (acknowledgment is implicit in the state).
- Invalidate `validated → draft` on every setup-mutating route that can affect validation outcome:
  - Reviewer import + delete-all.
  - Reviewee import + delete-all.
  - Assignment generate + delete-all.
  - Session edit (name/code/description/deadline).
  - Instrument open/close/visibility do **not** invalidate (they don't change validation results).
- Rewire the activation flow:
  - `draft` → run validation → on success, stamp `validated` (sticky).
  - `validated` → activate (lock) → `ready`. No re-validation needed at the activation moment.
  - `ready` → revert → `draft` (not `validated`; force re-confirmation).
- Inline summary card on session detail (shipped in 9.4B as a one-shot per validate POST) becomes sticky — renders whenever the session is `validated`, with the Activate button on it.
- "Locked but invalid" remains unreachable: activation requires `can_activate` (no errors); revert always lands on `draft`.
- Audit coverage: new `session.validated` event when `draft → validated`; existing `session.activated` and `session.reverted_to_draft` keep their semantics.
- Reviewer write-path gates (`is_ready` check) keep treating `validated` as not-yet-shippable — invitations and reviewer write only when status is `ready`.

### Out of scope
- `expired` (Segment 9.3+ deadline-driven state) — separate concern.
- `archived` (Segment 11+ retention state) — separate concern.
- Splitting `is_draft` / `is_ready` into independent Boolean columns — rejected; the richer string enum captures the same states without a column-shape migration.
- UI restructure beyond the inline summary card sticky behavior — that's 9.4B's domain.

### Deliverable shape
One focused PR: enum constant + state-transition helpers + invalidation hooks on every mutating route + activation rewire + audit event + tests. Touches every gate predicate, so the test suite (`test_session_lifecycle.py`, `test_validation_routes.py`, `test_session_edit_delete.py`) needs review.

### Detail
Decisions D1–D6 already locked in `guide/segment_09_4B.md`'s "Deferred to Segment 9.5" section. Standalone segment plan not yet drafted.

---

## Recommended sequencing

1. **9.1** — establishes authoritative session/instrument gating and lifecycle safety. **[done]**
2. **9.2** — adds invitation mechanics on top of stable activation behavior. **[done]**
3. **9.3** — completes the operator monitoring/reminder loop. **[done]**
4. **9.4A** — chrome/breadcrumb foundation; preconditions every later UI restructure. **[done]**
5. **9.4B** — session detail four-card restructure + inline validate-summary + Delete Data. **[next]**
6. **9.4C** — Manage page reshapes, instruments index, placeholder pages, segment close-out.
7. **9.5** — `validated` state + invalidation hooks + activation rewire. Lands after 9.4 closes so the inline summary card has its sticky home.

9.5 must come after 9.4B (the inline summary card is born in 9.4B as one-shot, then gains sticky semantics in 9.5). It can land in parallel with 9.4C if convenient — they touch disjoint files (9.4C is templates + routes; 9.5 is models + lifecycle service + every mutating route).

---

## Notes captured from assumptions and seg9 decisions
- Ready→Draft reversion is allowed.
- Block edits while Ready for this segment set (relaxed in 9.5: `validated` allows edits while showing green-light affordance).
- Easy Auth sign-in required; magic links deferred to Segment 16.
- Session deadline supersedes instrument acceptance timing.
- Dev outbox table is preferred in this phase.
- Lazy deadline-close audit emission is acceptable.
- Operator UI shape follows `spec/target_operator_map.md`; spec sync + decisions on previously-open notes are folded in.
- 9.5's `validated` state is captured as a richer string enum value rather than a Boolean-pair refactor — same expressiveness, no column-shape migration.
