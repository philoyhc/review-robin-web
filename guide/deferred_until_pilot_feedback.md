# Deferred until pilot feedback

A common ledger of features that were scoped, designed, and
explicitly deferred — not because they're out of scope forever,
but because **building them speculatively would cost more than
discovering they're unwanted**. Each item carries enough
context that it can be re-activated quickly if pilot feedback
asks for it.

The pattern: small, well-scoped post-MVP slices peeled off
named segments after the MVP shipped, rather than carried as
hard-tail items inside otherwise-archived plans. Living here
keeps the archive clean (one segment plan = one segment) and
makes the deferred set scannable in one place.

When pilot feedback **does** request one of these, lift the
section into a fresh segment plan (or fold it into a related
in-flight segment) and remove the bullet from this doc.

---

## 16C PR 4 — Audit log: entity drill-in (~200 LOC)

> Carved from `guide/archive/segment_16C_richer_audit_views.md`
> 2026-05-11 once 16C PRs 1-3 shipped and the segment retired
> to archive. Plan text below is the original 16C PR 4 spec
> verbatim plus a small "what changed since" note covering
> the 16B / 16C ride-alongs that the renderer now needs to
> handle.

**Ships.**

- The envelope's `refs` slot already carries cross-entity
  int PKs (e.g. `refs.reviewer_id`, `refs.instrument_id`,
  `refs.target_user_id` from 16B PR 2). Per-row anchors
  render alongside the detail rendering — "View reviewer"
  / "View instrument" / "View RuleSet" / "View user"
  deep-linking into the relevant operator-page surface.
- Deleted entities render as a disabled `(deleted)` suffix
  rather than a broken link. The viewer checks for row
  existence via cheap `EXISTS` queries batched per
  page-load.
- Per-entity URL builder
  `views.audit_ref_url(ref_key, ref_id, session) -> str`
  centralises the routing so anchors stay consistent with
  the operator chrome.

**Why deferred.** PRs 1-3's per-row expander already shows
`refs.target_user_id: 42` plain-text. Whether operators want
clickable deep-links vs. just reading the int PK is exactly
the kind of "small UX accelerant" that pilot feedback
surfaces (or doesn't) — building it preemptively risks
matching the wrong navigation pattern.

**Lift trigger.** Operator says "I keep wanting to click on
those IDs to jump to the entity" or analogous.

**Wire-up.** Lives in `app/web/views/_audit_log.py`'s
detail-renderer pipeline. The `format_audit_detail` view
adapter that PR 3 ships already gives the per-section
markup the right hook point — extend `_render_kv` (or split
out a `_render_refs`) to consult `audit_ref_url` and emit
anchors instead of plain `<code>` for known ref keys.

---

## 16C PR 5 — Cross-session workspace audit search (~250 LOC)

> Carved from `guide/archive/segment_16C_richer_audit_views.md`
> 2026-05-11 once 16C PRs 1-3 shipped and the segment retired
> to archive.

**Ships.**

- New workspace-level route `/operator/sys-admin/audit-log`
  (no session id). Same chrome, same table, same filter
  strip — but scoped to every session the sys-admin can
  see, plus workspace-scoped events
  (`workspace.operator_admitted` / `.operator_revoked` /
  `sys_admin.role_promoted` / `.role_demoted` from 16A
  PR 6) which have no `session_id`.
- Sys Admin top nav grows a third tab ("Audit log")
  alongside Sessions Diagnostics + Accounts Management.
- Filter strip gains a session-code dropdown / typeahead.
- Default date range "last 7 days" to keep the query
  bounded; operators can widen explicitly.
- Performance guard: query times measured on a fixture
  with N=10000 events per session × 50 sessions; if it
  bites, add an `(session_id, created_at)` composite index.

**Why deferred.** Per-session viewer (PR 1) is the natural
entry point for "what happened on this session?" — the
question that drove 16C in the first place. Cross-session
search is a different question ("who admitted whom across
all sessions?" / "what did this operator touch this week?")
and the cost is real (new top-nav tab, new query shape,
performance guard). Wait for the question to surface before
building the answer.

**Lift trigger.** Sys-admin says "I need to see what happened
across all sessions in date X" or "I want to audit one
operator's actions wherever they touched the workspace."

**Wire-up.** Reuses the PR 1 reader (with a small
generalisation to drop the `session_id` predicate) plus the
PR 2 filter strip. The new route lives in
`app/web/routes_operator/_sys_admin.py`; the new top-nav
tab lands in `sys_admin_top_nav.html`.

---

## 16C PR 6 — Timeline / activity-stream on Session Home (~250 LOC)

> Carved from `guide/archive/segment_16C_richer_audit_views.md`
> 2026-05-11. Originally retained in the archive as documented
> post-MVP scope; moved here for consistency with the other
> deferred 16C items.

**Ships.**

- New "Recent activity" card on Session Home rendering
  the most recent N (default 10) audit events for the
  session, summarised as one-line prose
  (e.g. `"Alice activated the session"` /
  `"Bob uploaded 47 reviewers"`).
- Per-event summariser `views.summarise_audit_event(event)
  -> str` mapping event_type + envelope → human-readable
  prose. Backed by a per-event-type dispatch dict;
  unknown / new event_types fall through to a generic
  `"<event_type> by <actor>"` formatter.
- Operator-visible — **not** gated to sys-admin. The
  timeline summarises operator-visible state changes
  (activation, deadline shifts, roster uploads) that
  every operator on the session should see.
- Deep-link from each summary line to the corresponding
  row in the PR 1 viewer (sys-admin-gated; non-sys-admin
  operators see the prose but the deep-link is absent or
  disabled).

**Why deferred.** The maintenance burden lives in the
per-event-type dispatch dict — every new emitter (or
renamed event type) has to land a summariser branch, or it
quietly degrades to the generic `"<event_type> by <actor>"`
formatter. Worth paying when operators are asking "what
happened lately on this session?" but not before — PR 1's
sys-admin-gated viewer already answers the same question
for power users.

**Lift trigger.** Operator says "I want to see recent
activity at a glance on the session home page" or
"reviewers are asking what changed and I have to dig into
the audit log every time."

**Wire-up.** New `views.summarise_audit_event` view
adapter; new partial for the Recent activity card; injected
into the Session Home context builder. Reuses
`audit.list_events_for_session` from 16C PR 1.

---

## 17B — Cell-level autosave (reviewer surface)

> Carved from `guide/archive/segment_17B_reviewer_surface_refinements.md`
> 2026-05-16. Listed there as a large-table-ergonomics item;
> deferred rather than built speculatively.

**Ships.**

- A debounced `fetch` to the existing
  `POST /reviewer/sessions/{id}/{position}/save` endpoint on cell
  blur / change, sitting alongside (or replacing) the per-page
  form Save.
- Per-cell status indicator — in-flight / saved / failed.
- Pure progressive enhancement — the `_surface_context` payload is
  already pinned stable for this; template + inline JS + CSS, no
  route or view-adapter change.

**Concurrency note.** The `Response.version` column exists (added
inert by the 13F DB-prep — no migration needed) but is not wired
into the save path; `responses.save_draft` neither reads nor bumps
it. Plain cell autosave is therefore last-write-wins, exactly like
today's per-page Save — acceptable, since one reviewer owns their
own rows. Version-gated optimistic concurrency would be additional
optional work (a small service change, still no schema change).

**Why deferred.** Today's per-page form Save already persists a
page's edits in one click; whether reviewers also want per-cell
autosave is exactly the ergonomic accelerant pilot feedback
surfaces (or doesn't). Building it speculatively risks tuning a
debounce / status-indicator UX nobody asked for.

**Lift trigger.** Reviewers say they lost work because they forgot
to Save, or ask for edits to persist as they go.

**Wire-up.** Template + inline JS in `review_surface.html`; the
debounced `fetch` targets the per-position `/save` route the form
already posts to.

---

## 17B — Filter-to-incomplete toggle (reviewer surface)

> Carved from `guide/archive/segment_17B_reviewer_surface_refinements.md`
> 2026-05-16.

**Ships.**

- A client-side toggle on the reviewer response table that hides
  rows already complete, so a reviewer working a long roster sees
  only what is left.
- Pure progressive enhancement — `_surface_context` already
  computes per-row completion state (`is_complete`); template +
  inline JS + CSS, no route or view-adapter change.

**Why deferred.** The per-instrument progress pills (shipped in
#1077) already tell a reviewer how much is left; whether they also
want to *filter the table* to the incomplete rows depends on how
large real rosters get and how reviewers work them — pilot-feedback
territory.

**Lift trigger.** Reviewers on large rosters say they keep losing
their place hunting for the unfilled rows.

**Wire-up.** Template + inline JS in `review_surface.html`, keying
off the per-row `is_complete` flag already in the payload.

---

## 17B — Return-to-place + reviewer-surface chrome polish

> Carved from `guide/archive/segment_17B_reviewer_surface_refinements.md`
> 2026-05-19, when Segment 17B was closed: PR 1 (the
> `routes_reviewer/` package split), the action-row reorder +
> keyboard navigation (#1076), and the visible-progress pills
> (#1077) shipped; sticky headers were investigated and dropped.
> The remaining polish items are deferred rather than built
> speculatively.

**Ships.**

- **Return-to-place** — after Save / Submit, the reviewer lands
  back at the row / instrument they were working rather than the
  top of the page.
- The remaining chrome polish from the 17B plan — status-card
  location and denser rows.

**Why deferred.** These are ergonomic refinements whose value
depends on how reviewers actually work a real roster; the
visible-progress pills (#1077) already cover the most-requested
orientation need. Tuning row density / status-card placement
without pilot signal risks polishing a layout nobody asked to
change.

**Lift trigger.** Pilot reviewers say they lose their place after
a Save, or that the surface feels sparse / the status card is hard
to find on a long roster.

**Wire-up.** Template + inline JS / CSS in `review_surface.html`;
the post-Save redirect already exists — return-to-place adds a
fragment anchor to it. No route or view-adapter change.

---

## 18G Part 3c — Targeted reminder cohorts (~150 LOC)

> Carved from `guide/segment_18G_scheduled_events.md` 2026-05-21
> on Segment 18G Part 3 close-out. Part 3a/3b (per-session
> reminder offsets + scheduled dispatch) shipped; cohort slicing
> is post-MVP.

**Ships.**

- Beyond the "incomplete" cohort, richer slicing off
  `monitoring.AT_RISK_THRESHOLDS` (At risk / No responses) — per-
  cohort bulk Send buttons on Manage Invitations (and the
  Responses page), optional per-cohort template differentiation
  via the existing `email_template_overrides` JSON.
- A new `session.reminder_cohort_sent` audit event
  (`set_changes` + `context.{cohort, threshold}`).
- The scheduled trigger (`_observe_scheduled_reminders`) gains
  a per-offset cohort selector (e.g. `["-P1D", "-PT4H@at_risk"]`)
  — shape settles at scoping; cohort embedding in the offset
  string keeps `reminder_offsets` schema-stable.

**Why deferred.** Today the "incomplete" cohort covers everyone
who hasn't submitted; cohort slicing only matters if operators
want to nudge at-risk reviewees differently from no-response
ones, or sequence reminders by escalation tone. Whether that's
worth the editor complexity (per-cohort template, per-offset
cohort tag) depends on what operators actually do with the
single-cohort send when 14B Part C lands and the queue is real.

**Lift trigger.** Pilot operators say they want to send a softer
nudge to "almost done" reviewers and a firmer one to "not
started" reviewers, or they want at-risk-only follow-ups
post-deadline.

**Wire-up.** A new cohort selector on the bulk-send and per-
offset surfaces; cohort filter inside the dispatch loop
(`_dispatch_scheduled_reminders` already iterates
`monitoring.per_reviewer_progress` — would gain a cohort
filter); new `session.reminder_cohort_sent` event registered
in `EVENT_SCHEMAS`.

---

## 18G Part 3d — Reminders analytics card (~100 LOC)

> Carved from `guide/segment_18G_scheduled_events.md` 2026-05-21
> on Segment 18G Part 3 close-out. Part 3a/3b shipped; the
> analytics surface is post-MVP.

**Ships.**

- A small "Reminders" info card on Manage Invitations —
  reminders sent (operator + scheduled), delivery success rate
  (reads 14B's `email.sent` / `email.send_failed`), completion-
  after-reminder rate (responses submitted within N hours of a
  reminder).
- No new tables; reads the audit log + outbox.
- A view-shape helper (`views.build_reminders_analytics_card`)
  + a single template block on `session_invitations.html`.

**Why deferred.** Operators today see per-row "Last reminder"
timestamps and a "Reminders sent" pill in the existing info
card. A dedicated analytics card is only useful if operators
want to compare reminder cadences across sessions or tune their
`reminder_offsets` based on response-after-reminder rates —
pilot-feedback territory. Also reads 14B's
`email.sent` / `email.send_failed` audit events, which only
become meaningfully populated once 14B Part C (the real
queue / worker) ships and dispatch isn't synchronous.

**Lift trigger.** Operators ask for reminder-effectiveness
numbers, or post-pilot tuning needs the data to justify a
particular cadence.

**Wire-up.** A view helper in `app/web/views/_workflow_card.py`
(or a new `_invitations_analytics.py` sibling) that aggregates
audit-event counts; the card body in the Manage Invitations
template alongside the existing auto-send captions.

---
