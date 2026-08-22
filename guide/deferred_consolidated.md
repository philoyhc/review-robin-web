# Deferred work — consolidated ledger

**Every scoped-but-not-scheduled item in one place.** This ledger
consolidates the three former deferral docs — `deferred_infra.md`,
`deferred_until_pilot_feedback.md`, and `future_possibilities.md`
(retired to `guide/archive/` 2026-08-19) — into a single reference,
ordered by **disposition**: how likely the work is to land, and what
would trigger it.

`guide/todo_master.md` remains the committed segment sequence —
everything there is intended to ship. This file is the opposite: work
that has been designed enough to record but consciously **not**
scheduled. Three dispositions, most-likely-to-land first:

- **[Part A — Deferred pending pilot feedback](#part-a--deferred-pending-pilot-feedback).**
  Small, well-scoped post-MVP slices peeled off named segments after
  the MVP shipped. Expected but paused, because **building them
  speculatively would cost more than discovering they're unwanted**.
  Each carries a **Lift trigger** — the pilot signal that re-activates
  it. When one fires, lift the section into a fresh segment plan (or
  fold it into a related in-flight segment) and delete its entry here.
- **[Part B — Deferred infrastructure & platform hardening](#part-b--deferred-infrastructure--platform-hardening).**
  Infra- and database-platform hardening that needs the Azure portal or
  destructive Postgres-only migrations, so it sits outside the in-app
  feature and hardening segments. Inherited debt; lands opportunistically
  when a real deployment forces the question.
- **[Part C — Future possibilities (off-roadmap)](#part-c--future-possibilities-off-roadmap).**
  Ideas that are plausible and worth recording so the design doesn't
  foreclose them, but which the project has consciously decided **not**
  to plan for. An item here may never be built, and that is the expected
  outcome unless something specific changes the call.

Each entry keeps its original **Ships / Why deferred / Lift trigger /
Wire-up** shape and its provenance note (the segment it was carved
from). Consolidated 2026-08-19; content otherwise unchanged.

---

## Part A — Deferred pending pilot feedback

Scoped, designed, and explicitly deferred pending real usage data.
Grouped by the surface they touch rather than by segment number.

### Reviewer response surface

#### 17B — Cell-level autosave (reviewer surface)

> Carved from `guide/archive/segment_17B_reviewer_surface_refinements.md`
> 2026-05-16. Listed there as a large-table-ergonomics item;
> deferred rather than built speculatively.

**Ships.**

- A debounced `fetch` to the existing
  `POST /me/sessions/{id}/{position}/save` endpoint on cell
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

#### 17B — Filter-to-incomplete toggle (reviewer surface)

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

#### 17B — Return-to-place + reviewer-surface chrome polish

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

### Audit & activity views

#### 16C PR 4 — Audit log: entity drill-in (~200 LOC)

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

#### 16C PR 5 — Cross-session workspace audit search (~250 LOC)

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

#### 16C PR 6 — Timeline / activity-stream on Session Home (~250 LOC)

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

### Reminders & scheduled dispatch

#### 18G Part 3c — Targeted reminder cohorts (~150 LOC)

> Carved from `guide/archive/segment_18G_scheduled_events.md` 2026-05-21
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

#### 18G Part 3d — Reminders analytics card (~100 LOC)

> Carved from `guide/archive/segment_18G_scheduled_events.md` 2026-05-21
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

### Scheduled lifecycle — auto-archive & purge

#### 18G Part 4 — Auto-archive (~200 LOC + migration index)

> Carved from `guide/archive/segment_18G_scheduled_events.md` 2026-05-21.
> The schema (`sessions.archive_offset`, Part 0b) shipped inert
> on 2026-05-20; the scheduled trigger and editor wiring are
> deferred. Operators have the manual Archive button on the
> Sessions-lobby row expander (Segment 18A), and the lobby
> already supports bulk archive across multiple selected
> sessions, so the scheduled variant is operationally
> nice-to-have rather than essential.

**Ships.**

- New `_observe_scheduled_archive(session)` in
  `app/services/scheduled_events.py` modelled on
  `_observe_scheduled_activation` — anchored on `deadline`,
  fires `archive_session` (18A's shipped service) at
  `deadline + archive_offset`. Per-session one-shot dedup via
  audit-event check.
- Precondition guard: `session.status == "draft"` (18A's locked
  `draft ⇄ archived` archive model). A running `ready` session
  must be reverted first. Skip with `reason="not_draft"`, audit
  `session.scheduled_archive_skipped`, clear the offset.
- Two new audit events registered in `EVENT_SCHEMAS`:
  `session.scheduled_archive_fired` (`refs.archive_event_id` +
  `context.{anchor_at, offset, scheduled_at, actual_fired_at}`)
  and `session.scheduled_archive_skipped`
  (`reason` + `context.{anchor_at, offset, scheduled_at}`).
- `archive_offset` editor input on Create / Edit Session enabled
  (currently a disabled placeholder). New parser
  `parse_and_validate_archive_offset` in `scheduled_events.py`
  mirroring `parse_and_validate_invite_offsets` but accepting
  positive durations (fires AFTER deadline). The 10-day cap
  doesn't apply — the default is `P30D`; relax to e.g. 365 days
  or no cap.
- Workflow card / Sessions lobby caption: amber when the session
  is `ready` (must revert first), green calm when `draft` and
  the resolved fire moment is upcoming.

**Why deferred.** Two pragmatic reasons:

1. Manual archiving from the Sessions-lobby row expander
   (Segment 18A) already handles single-session archiving in
   one click, and the lobby's bulk-expander handles many
   sessions at once. Operators routinely sweep the lobby and
   bulk-archive after data download. A scheduled variant adds
   editor complexity (`archive_offset` save-time validation +
   the new caption) and observer wiring for a marginal time
   saving.
2. Auto-archive needs the session to be in `draft` — but the
   typical post-deadline session is in `ready` (or has been
   manually closed). Without a paired auto-revert-on-deadline
   trigger, the auto-archive trigger would skip more often
   than not. Scoping that pair properly is itself a design
   question best answered with pilot data.

**Lift trigger.** Pilot operators say either (a) lobby-driven
bulk archiving is too slow / too easy to forget after a busy
review window, or (b) they want a "fire-and-forget" schedule on
sessions they know they won't touch again post-deadline.

**Wire-up.** `_observe_scheduled_archive` in
`scheduled_events.py`; `parse_and_validate_archive_offset`
helper; editor enable + per-tone caption (mirrors the
auto-send-invites / reminders captions); two
`EVENT_SCHEMAS` registrations.

---

#### 18G Part 5 — Scheduled / policy-driven purge (~300 LOC + env config)

> Carved from `guide/archive/segment_18G_scheduled_events.md` 2026-05-21.
> Like Part 4, the schema (`sessions.retention_exception` /
> `sessions.retention_overrides`, Part 0c) shipped inert on
> 2026-05-20; the scheduled trigger + policy resolution + editor
> are deferred. The operator-triggered selective purge shipped
> in Segment 18C (the "Purge and archive" expander action) and
> covers the immediate "I want to clear this session's data
> now" need; the scheduled / policy-driven half stays parked.

**Ships.**

- **Per-deployment policy** — three env vars in `app/config.py`
  (`RETENTION_RESPONSE_DAYS` / `RETENTION_AUDIT_DAYS` /
  `RETENTION_SESSION_ARCHIVED_DAYS`; unset = no auto-purge), a
  scheduled worker / cron, and a `retention.policy_run` audit
  event with a `counts` envelope.
- **Per-session override** — Settings-page editor for the
  `sessions.retention_exception` Boolean (opt a session out;
  e.g. legal hold) and the `sessions.retention_overrides` JSON
  (`response_days` / `audit_days` / `archived_days` /
  `delete_after_archive` keys). A
  `session.retention_policy_updated` emitter.
- **Per-session auto-delete offset** —
  `retention_overrides.delete_after_archive` (ISO 8601
  duration, anchored on the system-stamped archive time).
  When set, an archived session is hard-deleted this far past
  its archive timestamp. Editor surfaces this on Edit Session
  (currently the disabled `delete_after_archive` placeholder).
- **Trigger** — new `_observe_scheduled_purge(session)` in
  `scheduled_events.py`. Precondition: `session.status ==
  "archived"`. Skip with `reason="not_archived"`, audit
  `session.scheduled_purge_skipped`. Reuses 18C's
  `session_purge` service for the actual deletes.
- **Ride-along: 18D Part 5.** The Settings-CSV round-trip of
  the retention columns (`retention_exception` /
  `retention_overrides`) — Segment 18D's Part 5 — was handed
  to this part. Adds the `retention.*` rows to the Settings CSV
  serialiser / importer as part of Part 5.

**Why deferred.** Three pragmatic reasons:

1. The operator-triggered Purge action on the Sessions-lobby
   row expander (Segment 18C) already gives operators
   per-session control. The bulk-expander handles many
   sessions at once. A deployment-wide auto-purge worker is a
   real operations burden (cron schedule, monitoring, dry-run
   surface) for what is currently a "occasionally tidy up"
   need.
2. Retention policy is fundamentally a deployment concern.
   Until a pilot deployment surfaces real policy needs
   (compliance, storage, GDPR), defaults like "purge responses
   after 90 days" are speculation.
3. Auto-delete after archive is operationally similar to
   manual delete from the `/operator/sessions/archived` lobby
   — already shipped as a bulk action.

**Lift trigger.** A pilot deployment cites a retention-policy
requirement (regulatory or storage-driven) that needs to be
enforced automatically, or operators on a long-running
deployment report that the archived lobby grows unmanageably
without a periodic sweep.

**Wire-up.** `_observe_scheduled_purge` in
`scheduled_events.py`; three env vars in `app/config.py` +
a startup validation; Settings-page editor + JSON
read/write helper for `retention_overrides`; one
`retention.policy_run` event and one
`session.scheduled_purge_skipped` event registered in
`EVENT_SCHEMAS`. The 18D Part 5 Settings-CSV ride-along
(added alongside).

---

### Assignment-engine performance

#### 18J Rec B — Engine fast path: `find_first_n_pairs` (~150 LOC)

> Carved from `guide/archive/new_model_instruments_outstanding.md`
> 2026-05-26 alongside the Wave 5 + Wave 6 closeout. Recs A
> + D1 shipped as PR #1393; Recs B / C / D2 / D3 / E parked
> here because pilot rosters haven't surfaced the latency
> the cost model anticipates.

**Ships.** A new `find_first_n_pairs(rule_set, *, reviewers,
reviewees, limit, pair_context_lookup)` entry point next to
`engine.evaluate` in `app/services/rules/engine.py`. Same
predicate vocabulary, but iterates `(reviewer, reviewee)`
pairs lazily (generator), short-circuits the moment `limit`
matches accumulate, and skips the candidates sort + quota
assignment (preview doesn't need a deterministic ordering of
the full result). `find_sample_in_scope_reviewee` swaps over
to `find_first_n_pairs(limit=1)` for Individual mode and a
small `limit` for Group mode. Refresh-preview latency on a
1k × 1k roster drops from 1-3s to typically <100ms; only
narrow / no-match rules hit the worst case.

**Why deferred.** Pilot rosters haven't exceeded a few
hundred reviewers × reviewees; the 1-3s Refresh latency the
cost model anticipates on 1k × 1k just doesn't show up at
those scales. Operators have not flagged the existing
Refresh path as slow.

**Lift trigger.** A pilot deployment scales past mid-three-
digit reviewer / reviewee counts and the operator reports
the Refresh button feeling sluggish (~>1s), or a synthetic
benchmark on a representative roster confirms the cost
model's projection.

**Wire-up.** New module function in
`app/services/rules/engine.py`; `find_sample_in_scope_reviewee`
in `app/services/instruments/_band1.py` switches over (currently
calls `engine.evaluate(...)` and takes `result.pairs[0]`).
No schema change; no template change. Unit test covers (a) the
fast-path return for typical rules, (b) parity with
`engine.evaluate` on edge cases (narrow rules, group-mode
boundary).

---

#### 18J Rec C — Single-side predicate indexes + roster-upload cache (~400 LOC)

> Carved from `guide/archive/new_model_instruments_outstanding.md`
> 2026-05-26. Layered on top of Rec B; only worth landing
> if Rec B's worst case still bites real pilot rosters.

**Ships.** Pre-compute a `(side, tag_slot, value) → id_set`
dict at evaluation start (cheap, `O(N + M)`). For single-side
`equals` / `not_equals` / `in` / `not_in` / `is_empty` /
`is_not_empty` rules, intersect / subtract id sets before
materialising any pair. Cross-side `same_as` / `different_from`
still iterate per pair but over a much smaller surviving set.
Optionally persist the index on a new `sessions.roster_index_json`
column populated at import (or lazily on first eval and
invalidated on roster edit, mirroring the existing
`cached_eligibility_stamp` pattern).

**Why deferred.** Conditional on Rec B's worst case being
observed in practice. For the broad-rule cases pilot operators
are likely to author, Rec B alone should keep latencies well
under 100ms on 1k × 1k.

**Lift trigger.** Rec B has shipped, but a Refresh on a narrow
rule (e.g. `reviewer.tag1 = "Lead"` against a roster with only
a handful of Leads) still runs past ~500ms, or a synthetic
benchmark shows the worst case is realistic.

**Wire-up.** Index builder in
`app/services/rules/engine.py` (or a sibling
`_roster_index.py`); engine evaluator consumes the index when
present, falls back to today's brute walk otherwise. If
persisted, a new column on `sessions` + a roster-upload hook
that updates / invalidates it.

---

#### 18J Rec D2 + D3 — Single roster JSON blob + skip on-load preview rebuild in view mode (~200 LOC)

> Carved from `guide/archive/new_model_instruments_outstanding.md`
> 2026-05-26. D1 (single roster query per render) shipped as
> part of PR #1393; D2 + D3 stayed parked together because
> they touch the same template + JS surface.

**Ships.**

- **D2.** Lift the per-card `data-new-model-band2-roster='…'`
  JSON attribute onto a single page-level
  `<script type="application/json" id="new-model-roster-data">`
  block keyed by session id; rewrite the on-load JS in
  `instruments_index.html` to read from that single block when
  rebuilding each card's preview. HTML payload drops from
  `K × 100KB` to `1 × 100KB` (where K = number of instruments
  on the page).
- **D3.** Add `data-edit-mode="{{ 1 if is_editing else 0 }}"`
  on the per-instrument card root (or read the existing
  `[data-new-model-band2-editable]` `inert` flag — the card
  root doesn't currently expose an edit-mode signal). Have
  the on-load preview-rebuild loop in `instruments_index.html`
  skip cards in view mode. In view mode the server already
  rendered the correct preview table HTML; the JS rebuild is
  a no-op that re-runs filter logic only to produce the same
  DOM. Skipping it removes `K` JS rebuilds + the JSON parse
  on the view-mode hot path.

**Why deferred.** Same as Rec B — pilot rosters / instrument
counts haven't pushed the page-load time into operator-
visible territory. Today the per-card JSON blob and the
view-mode rebuild are both noise next to the engine cost
that Rec A already addressed.

**Lift trigger.** A pilot deployment carries enough
instruments per session (`K` ≥ ~12) that the duplicated
roster payload becomes measurable, or page-load profiling
shows the on-load preview rebuild blocking interactivity for
long enough that operators notice.

**Wire-up.** Both sub-recs touch
`app/web/templates/operator/instruments_index.html` and its
inline JS (the `data-new-model-band2-roster` attribute +
the `newModelRefreshBand2` loop). D2 also touches
`app/web/views/_instruments.py` to thread the
session-level roster into the page context once instead of
per-card. No schema change.

---

#### 18J Rec E — Verify Band 1 no-op Save stays cache-warm (~50 LOC)

> Carved from `guide/archive/new_model_instruments_outstanding.md`
> 2026-05-26. Tiny safety-net follow-on to Rec A — never
> blocking, but worth doing once someone is in
> `evaluate_session_rule_eligibility` for another reason.

**Ships.**

- Observability: a counter / log line in
  `evaluate_session_rule_eligibility`
  (`app/services/session_library.py`) distinguishing cache
  hit vs miss. Confirms post-deploy whether no-op Saves on a
  per-instrument card actually hit the
  `session_rule_sets.cached_eligibility_stamp` cache. If they
  don't, the rules serialiser is drifting — fix the
  comparison rather than the cache.
- Drift check: a regression test that opens + closes the lock
  with no field changes and asserts the stamp value is
  unchanged. Cheap insurance against future edits to the
  rule-serialise path silently invalidating every no-op Save.

**Why deferred.** Doesn't fix a user-visible problem — Rec A
already removed the engine cost from the Save redirect, so a
stale-cache miss costs nothing today either. The check
mainly protects against future regressions.

**Lift trigger.** Someone is editing the rule-serialiser path
for another reason and wants the regression test in place
first, or a routine perf-audit benchmarks the no-op Save and
finds the cache is missing.

**Wire-up.** Touch `evaluate_session_rule_eligibility` for the
log / counter; new test in
`tests/integration/test_instrument_builder_routes.py` (or a
new `test_band1_no_op_save_cache.py`) that opens the lock,
posts an unmodified Band 1 form, and asserts
`SessionRuleSet.cached_eligibility_stamp` is unchanged.

---

### Data integrity & template maintainability

#### Codex Slice D — Storage-level uniqueness guard on email-bearing identities (~100 LOC + migration)

> Carved from
> `guide/archive/weaknesses_and_bugs_found_by_codex.md` (Slice
> D) 2026-06-28 when that addendum retired. Slices A + B + C
> shipped as PRs #1836 + #1837 (the case-insensitive lookups
> + the historical-duplicates safeguard); Slice D is the
> defense-in-depth migration that was always scoped to follow
> the behavioral fix after dev-slot bake.

**Ships.**

- A lower-expression unique index on `users.email`,
  `reviewers.email`, `reviewees.email_or_identifier`, and
  `observers.email` (per-session for the three roster
  tables). Postgres syntax:
  `CREATE UNIQUE INDEX … ON <table> (lower(<col>))` or
  per-session pair `(session_id, lower(<col>))`.
- Alternative shape (preferred for portability if pilot
  data has any duplicate clusters to deal with): normalize
  email-bearing identities on write — every service call
  that inserts or updates an email lowercases at the
  service-layer boundary, and the migration backfills
  existing rows. Trades the index complexity for a one-time
  data migration.
- Migration round-trips on SQLite + Postgres per the
  portability note in `CLAUDE.md`. SQLite supports
  expression indexes via the same syntax as Postgres; both
  branches of the alternative are portable.

**Why deferred.** The behavioral fix in PRs #1836 + #1837
prevents new duplicate-by-casing rows from being created
through any current service path. The schema guard is durable
defense-in-depth — it would catch a future bug that bypasses
the service layer (e.g. a raw SQL admin script, a future ORM
write that forgot the `.lower()`). Without that future bug,
the migration ships zero observable benefit and costs one
dev-slot migration window. The shape of the migration also
depends on a question we haven't answered: how many
case-variant duplicate clusters exist in production data
right now? Zero → clean unique-index migration; non-zero →
needs a deduplication step first, with operator-visible
decisions about which row to keep.

**Lift trigger.**

- The duplicate-cluster audit returns a non-zero result (any
  pair of `(lower(email), session_id)` collisions in
  `reviewers` / `observers`, or `lower(email_or_identifier)`
  + `session_id` in `reviewees`, or `lower(email)` in
  `users`). That's the trigger to ship Slice D as **the
  deduplication-first variant** — a one-time migration that
  reports the clusters, prompts on which row to keep, then
  enforces the unique index.
- OR a future code change adds a new write path on one of
  these tables (e.g. a Segment 14B magic-link landing route
  inserts a participant row) — ship Slice D as the
  unique-index variant before that path lands, so the new
  surface can't regress.
- OR pilot feedback surfaces a duplicate-identity bug we
  can't otherwise explain (e.g. an operator reports "Alice
  appears twice in my Reviewers list and I never typed her
  twice").

**Pre-work.** Run the read-only audit query before drafting
the migration:

```sql
-- users (workspace-scope)
SELECT lower(email) AS lower_email, COUNT(*) AS dupes
FROM users
GROUP BY lower(email)
HAVING COUNT(*) > 1;

-- reviewers / observers (per-session scope)
SELECT session_id, lower(email) AS lower_email, COUNT(*) AS dupes
FROM reviewers
GROUP BY session_id, lower(email)
HAVING COUNT(*) > 1;
-- (repeat for observers)

-- reviewees (per-session scope; both email and anonymous
-- identifiers — the per-row check is case-insensitive
-- unconditionally so the audit query mirrors it)
SELECT session_id, lower(email_or_identifier) AS lower_id, COUNT(*) AS dupes
FROM reviewees
GROUP BY session_id, lower(email_or_identifier)
HAVING COUNT(*) > 1;
```

**Wire-up.** Migration lives in `alembic/versions/`. The
service-layer normalize-on-write variant touches the four
mutating service paths (`get_or_create_user`,
`create_reviewer` + `update_reviewer`, `create_reviewee` +
`update_reviewee`, `create_observer` + `update_observer`) —
each gets a `clean_email = email.strip().lower()` at the
entry point, with the existing duplicate-check then matching
exact equality on the stored lowercase value (which is what
the existing `func.lower()` query already returns from the
database).

---

#### Codex Slice E — Carve down the three large templates

> Carved from
> `guide/archive/weaknesses_and_bugs_found_by_codex.md` (Slice
> E) 2026-06-28 when that addendum retired. P3 in the
> original Codex assessment — flagged as maintainability risk,
> not a runtime defect.

**Ships.** A four-PR sequence that carves the three offending
templates into per-concern partials:

| Template | LOC (2026-06-05) | Carve target |
|---|---:|---|
| `app/web/templates/operator/instruments_index.html` | 5,342 | Per-band partials: `_band3_card.html` (PR E1, ~1,700 LOC, largest single block first), `_band1_card.html` (PR E2, ~650 LOC, includes mid-file `<script>`), `_band2_card.html` (PR E3, ~2,150 LOC including dynamic preview JS — riskiest carve because Band 2 JS reads Band 3 row state; lands last so the Band 3 partial boundary is already proven). |
| `app/web/templates/operator/session_extract_data.html` | 2,610 | `_extract_lens_card.html` macro (PR E4, ~400 LOC of per-instrument card markup). JS blocks stay in place. |
| `app/web/templates/base.html` | 3,231 | **No carve.** 87% is one `<style>` block whose extraction `CLAUDE.md` explicitly defers; every other template keys off classes defined here. |

Each carve PR ships in two commits: (a) verbatim move into
the partial (reviewable via `git diff --color-moved`),
(b) any cleanup. Each PR also adds a snapshot test asserting
byte-identical render for a known fixture before/after.

**Why deferred.** Pure-churn refactor with no behavior change
and no known runtime defect tied to file size. Cost is
concrete (4 PRs of diff review, snapshot-test infra
build-out, render-regression risk, opportunity cost vs P1);
benefit is speculative ("easier reviews of changes that may
or may not happen"). The deferred-ledger note in this file
is the parking lot until either lift trigger arrives.

**Lift trigger.**

- A real functional change queued against one of the
  offenders — then carving a cohesive partial in the same PR
  is cheap because the reviewer is already in that file.
  Take only the partial closest to the functional change,
  not the whole sequence.
- Measured friction: repeated reports of "I lost my place in
  this file" or "I shipped a bug because I missed a
  downstream consumer in the other half of the file."

**Wire-up.** Standard `{% include "operator/partials/<name>.html" with context %}`
include pattern (matches existing `_quick_setup_card.html` /
`_extract_data_card.html` siblings). Use
`include with context` rather than `{% macro %}` because the
Band partials each consume ~15 outer variables — macro arg
lists at that size are worse than `with`-context.

#### Runtime interaction tests for the template-JS surfaces (Playwright smoke layer)

> Flagged by the 2026-08-19 codebase assessment (§5, "the instrument card's
> behaviour still lives in inline template JS"). Recurring weakness, not tied
> to a single segment.

**The gap.** The instrument card's behaviour — the lock/unlock state machine,
the Band 1 rule editor, the `?editing=1` display↔edit swap (shared with the
Session Home config card), live preview render, +Page break / reorder — is
hand-written inline JS in `instruments_index.html` with **no build step** (a
deliberate `CLAUDE.md` constraint, not a defect). The problem is the *test*
gap, not the inline-ness: the suite asserts the JS **exists and parses**
(`node --check` + string-presence), never that it **does the right thing**, so
the interaction-regression class is only catchable by hand on the dev slot.
Two such bugs already slipped structural tests — the 18R space-key
card-collapse (#1914 → #1915) and the lost-column-width-on-save (#1920).

**Ships.**

- A thin **Playwright** smoke layer (`tests/e2e/` or similar) driving the
  highest-risk interaction paths in a real browser against `uvicorn` +
  `ALLOW_FAKE_AUTH`: unlock → edit → save on the instrument card; the
  `?editing=1` swap on Session Home; add/remove a Band 1 rule; +Page break;
  the reviewer-surface Save / Prev / Next. **No new dependency and no build
  step** — Chromium + Playwright are already provisioned in the agent env
  (`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`), driving the existing
  server-rendered pages + inline JS.
- A **separate, non-blocking CI track** (the repo already runs two — SQLite
  `pytest` + `ci-postgres`); browser tests are slower/flakier and need the app
  running, so they don't gate the fast suite.
- *(Optional, secondary — not required for the above.)* Extract the card's
  `<script>` bodies into a static `app/web/static/*.js` (still no build step;
  it already reads inputs from `data-*` attributes) so the JS is lintable +
  unit-testable in isolation with Node's built-in test runner. This is an
  organisation win, not a correctness one — extracted-but-untested JS is no
  safer — so it rides along only if the inline JS gets hard to navigate.

**Why deferred.** Not blocking and not next: recommended-move #1 stays 14B
email. The cost gap is real but bounded (two caught bugs over the window), and
a browser-test track is its own maintenance surface (flake management, a third
CI job) that shouldn't be stood up speculatively — scope it tight or it becomes
the problem it was meant to catch. Catches *interaction logic*, not visual/CSS
(dev-slot eyeballing still owns the pixels).

**Lift trigger.** Any of: (a) a third interaction regression slips the
structural-only tests; (b) someone is next doing substantial work in the
instrument-card JS — land a couple of interaction tests alongside the change
rather than as a standalone project; (c) a deliberate pre-pilot hardening pass
once 14B email is in and the surface is stable.

**Wire-up.** New `tests/e2e/` dir + a Playwright config pinned to the
provisioned Chromium (`executablePath: '/opt/pw-browsers/chromium'` if a
project ever pins a different `@playwright/test`; do **not** run
`playwright install`). A fixture that boots `uvicorn app.main:app` with
`ALLOW_FAKE_AUTH=true` on a throwaway SQLite db, seeds one session, and drives
it. A new `.github/workflows/` job (browser track), allowed-to-fail-soft or on
a nightly cadence at first. Start with the instrument card (bitten twice),
grow outward.

### Operator theming

#### 19C — Operator theme tweaker (Stretch)

> Carved from the theme-customizer design (`guide/theme_customizer.md`
> "Plan B — Stretch") 2026-08-22. **First** — the developer designer — is
> scheduled as 19C Item 5; **Stretch** was split off and deferred.

**Ships.**

- A **Display-mode section on `/operator/settings`** where an operator tweaks
  the light + dark themes for **their own view** — **seed controls only** (the
  full per-token grid stays developer-only), live preview, and a hard **AA
  contrast save-gate**.
- **Browser-local** persistence: Save → `localStorage["rrw-theme-custom"]`; a
  synchronous head script (placed **after** `base.html`'s `<style>` so the
  override wins the cascade) injects it before first paint;
  Revert-to-last-saved + Reset-to-defaults.
- Reuses **19C Item 5's editor core** verbatim — Stretch = that core + a thin
  app shell (page + localStorage + runtime-apply). **No database, no
  migration** — per-browser, exactly like the light/dark choice; participants
  (other browsers) unaffected.

**Why deferred.** No demonstrated need yet, and it depends on Item 5 (the shared
editor core) landing first. Browser-local scope is a *personal preference*, not
branding — limited value until operators actually ask to adjust colours.

**Lift trigger.** A pilot operator wants to tweak the palette (readability, mild
brand alignment) for their own view.

**Wire-up.** `guide/theme_customizer.md` "Plan B — Stretch" (settings host,
seeds-only depth, the `rrw-theme-custom` key, runtime-apply placement,
scaffold-first slices, AA gate). A DB-backed **shared / persistent** theme
(cross-user, pushed to participants) is a further future beyond Stretch — it's
the only part that needs a migration (a `themes` table + scope + governance).

---

## Part B — Deferred infrastructure & platform hardening

Infrastructure- and database-platform hardening that has been
**deferred** — items that need the Azure portal, or destructive
Postgres-only migrations, and so sit outside the in-app feature
and hardening segments.

Carved out of **Segment 14A — Production hardening**
(`guide/archive/segment_14A_production_hardening.md`) on 2026-05-18.
14A's PR ladder is the *in-app* hardening — logging, error
handling, indexes, permissions, accessibility, runbooks; the
items below are out of that ladder. They are inherited debt
from Segments 4A and 5A.

There is **no single "deferred infra" segment** — each item
lands opportunistically as its own small change with its own
verification, when a real pilot deployment forces the question.
14A's runbook (PR 6) documents the Azure items as deployment
prerequisites.

---

### 1. Azure infrastructure (needs the Azure portal)

Not agent-implementable — these require Azure portal / IaC
actions. Inherited from Segment 5A
(`guide/archive/segment_05A.md`), which provisioned dev Postgres
with the simplest acceptable infrastructure choices.

- **Move `DATABASE_URL` (and any other secrets) to Key Vault
  references.** Segment 5A stored the connection string as a
  plain App Service App Setting and as a GitHub Actions secret.
  For staging/production, switch the App Setting to a Key Vault
  reference and assign the App Service a managed identity with
  `Get` permissions on the relevant secrets.
- **VNet integration / private endpoints for Azure Postgres.**
  Segment 5 used public access with firewall rules. For
  staging/production, put the database behind a private
  endpoint, integrate the App Service into the VNet, and remove
  "Allow Azure services" plus the developer-IP firewall rules.
- **Migration-on-deploy safety controls.** Segment 5A's
  migrate-on-deploy step fails the workflow if migration fails,
  but does not gate destructive migrations. Add: a
  manual-approval gate for staging/production deploys, a
  "long migration" detector, and a documented rollback
  playbook.
- **Staging slot / environment.** A staging App Service slot (or
  separate App Service) so the deploy flow is
  `main → dev/staging → verify → manual-approve → production`.
- **Application Insights resource.** Segment 14A PR 1 ships
  structured logging that is App-Insights-ingestible;
  provisioning the resource and wiring its connection string is
  the remaining portal step.

---

### 2. Postgres platform migrations (destructive, Postgres-only)

Inherited from Segment 4A (`guide/archive/segment_04A.md`),
which deliberately used cross-dialect column types so the same
migration runs on SQLite (tests) and PostgreSQL (deployed).
The items below break that contract — they are Postgres-only
and need their own careful pass.

- **Migrate JSON columns to `JSONB`.** `AuditEvent.detail` and
  the other JSON columns should move to `JSONB` for indexing
  and operator-friendly queries. Postgres-only migration; tests
  continue on SQLite using `JSON`.
- **Migrate string-UUID columns to native `UUID`.** Where
  Segment 4 used `String(36)` for UUID-shaped columns, swap to
  Postgres `UUID` for storage efficiency and constraint
  correctness; add explicit casting in application code if
  needed.
- **Consider DB-level enums.** Where Segment 4 used `String` +
  Python enum validation (e.g. `AuditEvent.event_type` /
  `severity`), decide per column whether a Postgres `ENUM` type
  is worth the migration cost.
- **Postgres-specific indexes.** GIN indexes on `JSONB` columns
  where queried; partial indexes for frequently-filtered
  subsets; expression indexes if any. These depend on the
  `JSONB` migration above. (14A's index review, by contrast,
  adds only cross-dialect B-tree indexes.)

The Postgres-against-Docker CI job — also a Segment 4A
deferral — has since **shipped**: the `ci-postgres` workflow
runs the full `pytest` suite against `postgres:16`, so dialect
drift is caught in CI.

---

### 3. Other inherited debt (deferred, not strictly infra)

- **CSS extraction + design pass.** `base.html` carries inline
  `<style>` blocks; extract to static assets, decide on a
  design language, and migrate `me_debug.html` to extend
  `base.html`. Per `CLAUDE.md`, CSS extraction is a
  Segment-14-era concern. Cosmetic — no functional dependency.
- **First-time-user creation auditing.** First sign-in creates
  a `User` row without writing an audit event. Decide whether
  first-sign-in deserves its own audit event, or whether the
  Easy-Auth-side sign-in record is sufficient.

---

### See also

- `guide/archive/segment_14A_production_hardening.md` — the in-app
  hardening 14A *does* cover, and its 6-PR ladder.
- `spec/blob_storage.md` — candidate uses for object storage if a storage
  account is ever provisioned (§1 above is the portal-side prerequisite).
- `guide/segment_18Q_blob.md` — the blob-storage build plan (seam +
  first consumers). Institutional provisioning is now **requested**
  (account awaiting finalization); the storage-account + managed-identity
  role assignment in §1 above is that segment's active portal prerequisite.

---

## Part C — Future possibilities (off-roadmap)

Aspirational directions deliberately *not* on the roadmap. Each entry states the idea, why it is off the roadmap, what is being done instead, and what evidence would move it back on.

### AG Grid (or an equivalent JS data-grid) for the reviewer surface

**The idea.** Replace the reviewer surface's plain HTML
`<table>` of `<input>` / `<textarea>` / `<select>` cells with a
client-side data-grid component (AG Grid was the candidate).
That would bundle, in one library, virtualised row rendering,
column resize / freeze, rich cell editors, and a built-in
cell-edit lifecycle.

**Why it is off the roadmap.** A JS data-grid is judged
**overkill** for this app's actual surfaces:

- *Operator side* — the Setup-page tables took the opposite
  route and shipped per-row inline edit on plain HTML tables
  (Segment 15F). That settled the operator question: no grid
  framework needed.
- *Reviewer side* — a reviewer reviews a **bounded** set of
  reviewees (a handful to a few dozen), so the one genuinely
  grid-only feature, row virtualisation, solves a problem the
  domain does not really have. The features that *do* matter —
  cell-level autosave, sticky headers, return-to-place,
  visible progress — are achievable as targeted progressive
  enhancement without a grid library.
- *Cost* — AG Grid would be the project's **first JS bundle**
  and would force a Community-vs-Enterprise licensing
  decision, against a server-rendered monolith whose `CLAUDE.md`
  explicitly rules out a framework / build pipeline while
  allowing targeted inline progressive-enhancement JS.

**What is being done instead.** The valuable reviewer-surface
ergonomics that `spec/visual_style_rrw.md` pins as first-class
(auto-save, return-to-place, visible progress, sticky headers,
filter-to-incomplete, keyboard navigation) are pursued
incrementally as **vanilla progressive enhancement under
Segment 17B** — debounced `fetch` to the existing `POST /save`
endpoint, CSS `position: sticky`, and small inline scripts.
The reviewer-surface view-shape payload (`_surface_context`'s
list-of-dicts) is already stable and serializable, so it would
*also* feed a JS grid unchanged — keeping this option open at
zero ongoing cost.

**What would move it back onto the roadmap.** Pilot evidence
that reviewers routinely face genuinely large tables (on the
order of 100+ rows per reviewer) where virtualisation, column
freeze, or grid-native keyboard navigation materially change
completion rates — i.e. a real problem the progressive-
enhancement path cannot reach. Absent that, the
progressive-enhancement path is the plan.

*History: this was briefly a roadmap segment — numbered 17,
then 17A, then 22 — before being moved here on 2026-05-16. The
superseded segment plan is recoverable from git history
(`guide/segment_22_ag_grid_replacement.md`).*

---

### Randomizer / grouper

**The idea.** A facility to assign reviewers to reviewees — or to
partition either roster into groups — **at random**, individually
or by group, rather than by an explicit rule. For example: "randomly
pair each student with 3 peers," or "randomly split the cohort into
review groups of 5, everyone reviews their group."

**Why it is off the roadmap.** Random assignment at generate-time
fights the engine's **idempotency** contract. Assignments are not
authored row-by-row; they are *generated* by a deterministic
per-instrument rule pass (Band 1 → the rule engine), and the app
**re-runs that pass repeatedly** — on **Prepare**, and on the
reconcile + regenerate path — precisely because regeneration must be
safe to repeat without disturbing saved responses (responses are
keyed to stable `(reviewer, reviewee, instrument)` pairs). A random
draw *inside* generate is non-deterministic: every re-run would
reshuffle the pairings, orphaning saved responses, and any
**subsequent redraft** (add/remove a person, tweak a field, re-open
setup) would silently re-draw *everyone*. Randomness at the generate
step is fundamentally incompatible with a re-runnable generate.

**What is being done / could be done instead.** Move the randomness
**out of generate-time and into the data, once** — then let the
existing deterministic, tag-based rules do the assignment. The concrete
shape is a **dedicated randomizer / grouper page (or function)** that
takes in **simple requirements** — e.g. "groups of 5," "each reviewer
gets 3 random reviewees," "split the cohort evenly into N groups" — and
**writes its output into persisted inputs**, as **either**:

- **relationships rows** (random pairings, feeding pair-context), or
- **reviewer / reviewee tags** (a randomly-drawn group label, e.g.
  `RevieweeTag2 = "Group C"`).

After that, assignment is an ordinary deterministic function of roster +
rules (Band 1 filters on the group tag, or the relationships feed
pair-context), and **Prepare / regenerate stay idempotent** — re-running
never re-draws, because the draw is now fixed data. **Seed the shuffle**
(persist the seed) for reproducibility and an audit trail.

Because the tag output has to land *somewhere*, the tag mode **requires a
free tag column**: the randomizer targets an **unused** `ReviewerTag*` /
`RevieweeTag*` slot (or the operator explicitly picks which slot it may
overwrite). The relationships mode has the analogous prerequisite that
relationships are enabled for the session.

This is a **pre-processing utility**, **not a rule-engine mode** — which
is exactly why it can be added without touching the idempotent generate
path. And it is *already achievable manually today*: randomize in a
spreadsheet, drop the groups into a spare tag column, upload the CSV, and
use a tag-based rule (the same tag → rule flow the quickstart describes
for tutorial groups).

**What would move it back onto the roadmap.** Pilot evidence that
operators want random grouping / pairing often enough that the manual
spreadsheet route is real friction. The shape to build then is the
**seeded, data-materializing** "shuffle into tags / random pairings"
pre-step above — deliberately never a non-deterministic generate mode.

### Page-level error banner for the setup pages' bulk / delete-all actions (consistency-audit R3)

**The idea.** The four setup pages (Reviewers / Reviewees / Observers /
Relationships) redisplay a failed **row create / edit** as an inline
banner inside the add/edit form (`edit_error` → `_render_*_page`). Their
**bulk status-flip** and **delete-all** handlers instead raise
`HTTPException(400)`, which the global handler renders as a generic error
page. Consistency-audit R3 flagged the split. "One redisplay contract"
would give the bulk / delete-all handlers the same inline treatment —
which requires a **new page-level error banner** in all four setup
templates (the existing `edit_error` banner only renders inside
`{% if edit_mode %}`, so a bulk error has nowhere to show) plus threading
the value through each `_render_*_page` helper.

**Why it is off the roadmap.** Every error path in scope is
**unreachable through the UI**: the bulk `not_in_session` /
`invalid_status` errors only fire for ids/statuses the checkbox UI never
produces, and the delete-all `confirm` guard fires only when the
confirm checkbox (which disables the button until ticked) is bypassed.
All three require a **forged or buggy client**. So the work is a
four-template UI build whose only visible effect is on responses a real
operator cannot trigger. The service + audit + docs for the whole route
sweep (R1–R11) were finished 2026-08-19; R3 was **accepted as-is** by
the maintainer rather than built.

**What is being done instead.** The convention is documented in
`spec/architecture.md` § "Route conventions": inline re-render is the
**form-error** contract (row create/edit); the forged-only bulk /
delete-all guards intentionally surface the shared error page. No
behaviour change.

**What would move it back onto the roadmap.** Any change that makes one
of these error paths **reachable through the UI** — e.g. a bulk action
that can legitimately partially fail (some rows accepted, some rejected)
and needs to report which — at which point the page-level banner becomes
a real operator-facing surface worth building across the four pages.
