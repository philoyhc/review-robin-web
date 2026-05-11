# Segment 16 — Sys admin page

**Status:** Planning — stub created 2026-05-10. Captures
the home for operator-internal / dev-only surfaces that
exist today but lack a dedicated chrome surface, plus a
few that retire from operator-facing routes under the
13E → 12C → 15D → 12A-3 block and will land here.

> **Working notes scratchpad** at the bottom — capture
> decisions, scope tweaks, and open questions as they
> come up. Once the shape settles, lift the durable
> parts into a proper "Goal / Scope / PR sequence / Out
> of scope" structure.

## Goal

A single dedicated **Sys Admin page** (or section)
gathering surfaces that are useful for diagnostics /
support / dev workflows but **shouldn't sit on the
operator-facing chrome alongside the everyday Setup +
Operations tabs**. The internal capabilities for the
two anchor items already exist as code paths — Segment
16 wires them under one chrome roof.

## Anchor items (capabilities already exist)

### 1. Outbox

**Today.** `GET /operator/sessions/{id}/outbox` route
already implemented at `app/web/routes_operator/_operations.py:510-527`
with template `app/web/templates/operator/session_outbox.html`.
Reachable today from a "View outbox" button on the
Manage Invitations page (`session_invitations.html:43`).
Backed by `invitations.list_outbox_for_session(...)` in
the invitations service.

**Under Segment 16.** The page **moves under the Sys
Admin chrome** rather than being a per-session
diagnostic surface tucked behind a per-page button.
Everything functional already exists — the move is a
chrome / placement change. The chrome partial
(`session_top_nav.html`) currently calls out the
Outbox page as "reachable from a View outbox button on
Invitations and is not a chrome tab — it's a
dev-diagnostic surface, not part of the Operations row
taxonomy"; Segment 16 makes that taxonomy explicit by
giving the dev-diagnostic surface its own chrome row.

### 2. Manual assignment upload

**Today.** `POST` route at
`app/web/routes_operator/_assignments.py:199` uses
`assignments.parse_manual_csv(...)` to write directly
into the assignments table; also reachable via Quick
Setup slot 3 (`_quick_setup.py:529`). Both paths
exposed in the operator UI.

**Under Segment 15D.** Operator-facing surfaces retire
— Quick Setup slot 3 retires (15D PR 7) and the
Setup-page Assignments form retires (15D PR 6 +
chrome restructure). The underlying
`parse_manual_csv` / `replace_assignments` route +
handler **stay as a dev-only feature** per the
2026-05-10 codebase-check decision (no operator UI;
route + handler accessible for tests + admin
tooling).

**Under Segment 16.** The dev-only manual upload
gets a discoverable home on the Sys Admin page —
explicitly labelled as dev-only with the operator-
facing alternative (Relationships table → Generate)
called out alongside. Operators who *need* to bypass
the rules engine (one-off custom pairings, debugging
the engine output, restoring a known-good assignments
table) hit the Sys Admin page deliberately rather
than stumbling into it via Quick Setup.

### 3. Audit log download

**Today.** `GET /operator/sessions/{id}/export/audit_log.csv`
route shipped in **Segment 12B PR 1** (2026-05-10) at
`app/web/routes_operator/_extracts.py`. 8-column wide CSV
(`EventType` / `Severity` / `Summary` / `ActorEmail` /
`CorrelationId` / `CreatedAt` / `DetailJson`) with the
canonical Segment 11K detail envelope JSON-encoded in
the trailing column. Backed by
`app.services.extracts.audit_events_extract.serialize_audit_events`,
streamed via `yield_per(1000)`. `session.audit_log_extracted`
audit event registered in `EVENT_SCHEMAS`. The route is
live and reachable directly — but **there is no operator-
facing UI surface today** (the Extract Data card tile was
deliberately omitted in favour of relocating the surface to
Sys Admin per industry best practice; see "Why a separate
sys admin page" below).

**Under Segment 16.** The Sys Admin page gets a Download
audit log button (or tile) wiring the existing route.
Per industry best practice (GitHub, Stripe, Slack, Notion,
Atlassian) audit data sits behind an admin / diagnostics
doorway rather than alongside everyday data exports —
Sys Admin is that doorway. No new service code needed; the
move is pure chrome placement.

## Why a separate sys admin page

Today's chrome reads as "operator-facing setup +
operations." Surfaces that don't fit that taxonomy
either get tucked behind buttons (Outbox) or sit
awkwardly on a Setup tab they'll outgrow (manual
assignment upload). A dedicated Sys Admin page:

- Keeps the operator-facing chrome focused on the
  rule-based workflow that 15D centres on.
- Gives the dev-diagnostic surfaces a discoverable
  home (no more "where did the View outbox button
  go?" treasure hunts).
- Makes it explicit when a capability is dev /
  support / admin scope rather than everyday
  operator scope.

## Likely surface

> Sketchy — settle during PR scoping.

- Chrome row (or sub-section under the existing
  Operations row, or a separate `/operator/sessions/{id}/sys-admin`
  page).
- Sections:
  - **Outbox** (read-only diagnostic; reuses
    `session_outbox.html` template).
  - **Manual assignment upload** (dev-only form;
    reuses `parse_manual_csv` / `replace_assignments`).
  - **Audit log download** (download button wiring
    the existing 12B PR 1 route; reuses
    `serialize_audit_events` + the `/export/audit_log.csv`
    route).
  - Future: one-off SMTP test send, anything else
    dev / support scope picks up over time.

## Out of scope

- New service code for outbox or manual upload —
  both already exist.
- Operator-facing UX changes to the rule-based
  workflow — those live in 15D and 12A-3.

## Security / access — proposal (decide before PR scoping)

The Sys Admin surfaces sit above the everyday operator
permission set (every authenticated operator is already
trusted with their own session's data via
`require_session_operator`). The question is **which
authenticated operators get the additional "I can break
things deliberately" power** that Manual assignment
upload, audit log download, and future SMTP test-send
imply.

### Threat model

- *Accidental damage* — wrong click on Manual assignment
  upload silently wipes a live session's pairings via
  `replace_assignments`.
- *Deliberate misuse* — operator overrides the rule
  engine on a colleague's session, or pulls another
  session's audit log they shouldn't see.
- *Information leak* — audit log download surfaces
  correlation IDs / actor emails / lifecycle history;
  Outbox surfaces queued email bodies (incl. invite
  tokens pre-send).

Risk per surface:

| Surface | Risk | Mitigation lean |
|---|---|---|
| Outbox (read-only) | Low | Authz gate is plenty |
| Audit log download | Low–medium | Authz gate + per-download audit event (already emitted as `session.audit_log_extracted` by 12B PR 1) |
| Manual assignment upload | **High** (writes, bypasses rules) | Authz gate + confirmation + audit |
| Future SMTP test-send | Medium | Authz gate + audit |

### Defence in depth (any chosen option below should layer all four)

1. **Authentication** — Entra Easy Auth (already
   enforced; nothing new).
2. **Authorization** — `require_sys_admin` FastAPI
   dependency that 403s non-admins.
3. **UI gating** — Sys Admin chrome tab / link only
   renders when authorized; no leaked navigation for
   non-admins (avoids the "what's that I can't click"
   discoverability problem).
4. **Audit + confirmation** — every mutating Sys Admin
   action writes an `audit_event` with `actor_user_id`;
   destructive actions (manual upload) need an explicit
   "I'm overriding the rule engine" checkbox before
   submit.

### Authorization options

**A. Entra app role (`RR_SysAdmin`).** Define an app
role in the Entra app registration; assign it to
specific users in the directory. Easy Auth surfaces the
`roles` claim on `X-MS-CLIENT-PRINCIPAL`;
`require_sys_admin` checks for `RR_SysAdmin ∈ roles`.
*Pros:* standard pattern, scales, no new app code beyond
the dependency, role assignment lives in the directory
where it belongs. *Cons:* one-time Entra app-role
registration + per-user assignment; local dev needs
`ALLOW_FAKE_AUTH` to inject a synthetic role
(`FAKE_AUTH_SYS_ADMIN=true`).

**B. Per-user `users.is_sys_admin` boolean.** New
column, default False, manageable via a (yet-to-build)
Sys Admin promotion UI + bootstrapped from a
`SYS_ADMIN_EMAILS` env var on user-create. *Pros:*
self-contained, no Entra coordination, can grow into a
richer per-user permission story. *Cons:* adds a second
source of truth alongside Entra; bootstrap needs care;
manageable only via env or UI we haven't built.

**C. Env-allowlist (`SYS_ADMIN_EMAILS=alice@…,bob@…`).**
`require_sys_admin` checks `current_user.email in
settings.sys_admin_emails`. *Pros:* simplest possible —
no schema, no Entra coordination; deployment-time
toggle. *Cons:* redeploy to add / remove; doesn't scale
past ~5 admins; no audit trail of who's an admin (the
env var is the trail).

**D. Shared secret / "magic URL".** Single token in
env, operator must supply it. *Reject* — no per-user
accountability; embarrassing security hygiene.

### Recommendation (not yet decided)

**Ship Segment 16 with Option C (env allowlist) + the
four defence-in-depth layers. Plan migration to Option
A (Entra app role) when operator scale or org policy
demands it — likely Segment 14A (production hardening).**

Reasoning: today's operator population is small (a
handful, all known to the deployer); Option C covers it
with one env var + ~10 lines of code. Option A is the
right long-term home but pulls in Entra app-registration
coordination that's more work than Segment 16 itself.
Option B (per-user flag) is the tempting middle path
but overlaps with Entra without replacing it — better
to skip the half-measure and migrate C → A directly.

### Concrete shape if Option C is chosen

- `app/config.py` gains `sys_admin_emails: list[str]`
  (parsed from comma-separated env var).
- `app/web/deps.py` gains `require_sys_admin = Depends(…)`.
  Returns the `User` on hit; 403s with `"sys_admin
  required"` detail on miss.
- Sys Admin routes declare `_user: User =
  Depends(require_sys_admin)` instead of
  `get_or_create_user`.
- Chrome partial renders the Sys Admin tab conditionally
  on a `request.state.is_sys_admin` flag set by
  middleware (or computed in the view layer).
- `ALLOW_FAKE_AUTH=true` honours a new
  `FAKE_AUTH_SYS_ADMIN=true` toggle so local dev can
  exercise the gate.
- Audit-event registrations on the mutating Sys Admin
  surfaces:
  - `sys_admin.manual_assignments_uploaded` (`counts`
    envelope).
  - `session.audit_log_extracted` — already shipped by
    12B PR 1; consider keeping the event_type name even
    after the surface moves under Sys Admin chrome (the
    *event* is a session-scoped extract; the *route* is
    sys-admin-scoped).
  - `sys_admin.outbox_viewed` — optional, read-only;
    skip if it spams the log.
- Tests: per-route 403 for non-admin, 200 for admin,
  audit emission on mutating actions, chrome rendering
  conditional on the flag.

### Open questions / decisions deferred

- Option A vs C for the MVP? — C recommended; A is the
  next-step upgrade.
- Sys Admin chrome **per-session** (lives at
  `/operator/sessions/{id}/sys-admin`, scoped to that
  session) or **workspace-level** (lives at
  `/operator/sys-admin`, spans all sessions)? The three
  anchor surfaces are all per-session today; a
  workspace-level chrome would need adapter work
  per-surface (Outbox + Manual upload + Audit log all
  take a session in their existing routes).
- Destructive-action confirmation shape — single
  checkbox (matches the existing Quick Setup
  replace-confirmation pattern) or two-step "type the
  session code" (GitHub-repo-delete style)?
- Should `sys_admin.outbox_viewed` exist, or is read-only
  view too low-signal to audit?

## Working notes / open questions

- _(placeholder)_
- Should Segment 16 also absorb today's
  `/operator/sessions/{id}/edit` or similar?
- Should the Sys Admin chrome row sit per-session or
  per-deployment (operator-global)?

## Related context

- **Segment 15D — Assignments revamp**
  (`guide/archive/segment_15D_assignments_revamp.md`). PR 7's
  decision to keep `parse_manual_csv` /
  `replace_assignments` as a dev-only feature
  established the route's continued existence; 16
  picks up where the operator-facing surface
  retires.
- **Segment 12B — Audit retention**
  (`guide/segment_12B_audit_retention.md`). The
  `audit_events` export shipped 2026-05-10 (PR #788)
  with the route live but no operator-facing UI
  surface; Segment 16 wires the existing route under
  the Sys Admin chrome (see Anchor item §3).
- **Outbox today.**
  `app/web/routes_operator/_operations.py:510-527`
  (route + handler);
  `app/web/templates/operator/session_outbox.html`
  (template);
  `app.services.invitations.list_outbox_for_session`
  (data source).
- **Manual upload today.**
  `app/web/routes_operator/_assignments.py:199`
  (POST handler);
  `app.services.assignments.parse_manual_csv` +
  `replace_assignments` (service).
- **Chrome partial.**
  `app/web/templates/operator/partials/session_top_nav.html`
  — gains a "Sys Admin" tab (or sub-row) when this
  segment ships. Note: 15D restructures the chrome
  in the same broad time-frame; coordinate the
  taxonomy change with 15D's PR 6.
