# Segment 14E — A clock for timed actions (no mail)

**Opened:** 2026-11-02, at the author's request · **Theme:** scheduled steps that send no email fire on time, from an in-app loop, with no page view · **Related:** `guide/no_scheduling_fallback.md`, `guide/segment_14F_manual_email.md`, `guide/post_azure_todo_checklist.md` item 7, `spec/lifecycle.md` §8

## Opportunity

Scheduled activation fires only when an operator next opens Session Home,
an Operations page or the lobby (`observe_scheduled_events_on_load`,
`spec/lifecycle.md` §8.3). A session set to open at 09:00 opens whenever
an operator looks; a reviewer arriving first finds it closed. The deadline
holds without a clock (`observe_deadline` refuses a late save on arrival),
but its instruments stay marked open on operator pages until someone
arrives. Neither needs mail, so neither needs IT (author, 2026-11-02: "just
because you can't do scheduled emails, it doesn't follow you can't do
scheduled actions").

## Decision

**A small loop inside RRW** runs the non-mail half of the scheduled-events
pass every few minutes: scheduled activation, then the deadline close. It
starts with RRW's lifespan (the host runs a mounted app's lifespan,
`cordware/main.py`), and takes a database lock per pass so only one
process runs it.

- **The page-view trigger stays**, as a backstop, unchanged.
- **Invitations and reminders stay on the page view** and outside this
  segment: they need a send path (14F by hand, 14G on a clock).
- **Interval:** `SCHEDULER_INTERVAL_SECONDS`, default 120; `0` turns the
  loop off (tests, and a deployment that wants page views only).

Rejected: *a scheduled workflow in the private deployment repository
calling an internal endpoint.* It keeps the timer outside the app but adds
a route, a credential and a workflow to keep in step
(`guide/email_and_scheduling.md`). Rejected: *firing Start on any reviewer
arrival* (`guide/no_scheduling_fallback.md`'s first draft): a clock makes
it unnecessary, and it would put a state change on a reviewer's GET.

## Semantics

- **Lock:** Postgres `pg_try_advisory_lock` on a fixed key per pass; a
  pass that cannot take it skips. SQLite (local, tests) takes no lock.
  The per-session row lock each trigger already takes (`lock_session`)
  still guards a page view racing the loop.
- **Failure:** activation keeps its retry counter and `failed_persistent`
  state (§8.3); the loop logs and audits as the page view does, and one
  session's failure never stops the pass.
- **Deadline close:** the loop runs `observe_deadline` for `ready` sessions
  past their deadline; it is idempotent, so a reviewer arriving first
  changes nothing.
- **Audit:** the same events the page view writes, with
  `context.trigger = "clock"` so the log says which fired.
- **Shutdown:** the lifespan cancels the loop; a pass in flight finishes
  its current session.

## Judgment calls — decided

- In RRW, not the host: the passes are RRW's services, and the host only
  runs lifespans (2026-11-02).
- No new table or queue: the anchors are already columns (2026-11-02).
- **Interoperability, pre-positioned** (`guide/interoperability.md` §2,
  2026-11-04): the loop fires only what an operator set, never a session
  for being new; it carries timed lifecycle changes only, no export or
  sync; its lock key is RRW's own. With it, a read-only status call sees
  current state without a page view.
- **14C Item 2's report emails** (group C, 2026-11-04): the clock's audit
  events are what those reports will read when 14G mails them, so each
  crossing writes **one** event whichever trigger fires it first (clock
  or page view), and a report keyed on it fires once. A persistent
  activation failure now happens with nobody looking and no mail until
  14G, so 14F's lobby due-action marker includes it.

## Blast radius (measured)

Taken 2026-11-02 at `fffd4c28`.

| What | Count | Command |
|---|---|---|
| Callers of `observe_scheduled_events` in `app/` (excluding its definition) | 5 | `grep -rn "observe_scheduled_events(" app --include=*.py \| grep -v "def " \| wc -l` |
| Test files naming it | 7 | `grep -rln observe_scheduled_events tests --include=*.py \| wc -l` |
| Files naming `observe_deadline` (app + tests) | 20 | `grep -rln observe_deadline app tests --include=*.py \| wc -l` |
| Test files naming `scheduled_activate_at` | 49 | `grep -rln scheduled_activate_at tests --include=*.py \| wc -l` |
| Templates naming the auto-send offsets (rung 0; taken 2026-11-04 at `b2703ab9`) | 4 | `grep -rln "invite_offsets\|reminder_offsets" app/web/templates \| wc -l` |

## Status — closed 2026-11-04

**Intended:** an in-app clock for scheduled activation and the deadline
close, rungs 1–2, then a close. **Done:** that, plus rung 0 (auto-send off,
author's ruling) and two rulings the author's browser test led to. Shipped
in #3577 (rung 0), #3578 and #3579 (the clock), #3582 (the review's end
closes the session), with #3576 and #3580–#3581 for the plan and the test
sequence. The author ran the sequence (A–D) on a local run, 2026-11-04;
it passed.

**Diverged from Semantics:**

- `context.fired_by = "clock"`, not `context.trigger` (taken by
  `session.activated` and `scheduled_event_failed`).
- `pg_try_advisory_xact_lock` on RRW's own key, a gate transaction per
  pass, each session in its own database session; shutdown waits 30 s.
- Activation retries keep a 15-minute spacing on the clock
  (`RETRY_SPACING`); page views keep their own pace.
- With sending on, the clock holds activation for a session with invite
  offsets (no invite-URL builder until 14G).
- Release stamps (`session.release_window_opened` / `_ended`, the
  author's answer) only while `expired`, once per crossing, within a day.
  `session.deadline_reached` carries *n* of *N* (the author's answer).
- **The review's end closes the session** (author): End, or with no End,
  Release from (`lifecycle.review_end`), moves `ready → expired`
  (`session.expired`, no actor, `reason` `deadline` / `release`). The
  `while_ongoing` window ends there too (`is_ongoing`): visibility exists
  only while ongoing and in the release window, which reverses G10's
  "deadline or not" (2026-10-01). Saves and Recall stop at the same end.
  Validate's `session.end_passed` refuses a session whose end has passed
  or comes at or before its Start; with no End, Release from must be on
  or after Start.
- The scheduled pass runs invites, activation, reminders, the end's
  close, then the release stamps; operator page views run the close too.

**Reads:** rung 0 one `diff-reviewer` read (5 findings, all acted on);
rungs 1–2 one cumulative read (12 findings: release stamps on non-expired
sessions, lost invites, a lock on every page view, retry pace, shutdown,
two logging bugs, plan drift; all acted on) and one Codex finding (retry
spacing hid deadlines); #3582 three reads (sessions past an older End,
operator pages, the refused notice; a stuck no-End session, the gate;
a Start after the end, the release reason), all acted on.

## PR ladder

0. **Auto-send off until mail can go on a clock** (added, author,
   2026-11-04; moved from 14F's scaffold). `RRW_SCHEDULED_SEND`, default
   off: the two auto-send fields (`invite_offsets`, `reminder_offsets`;
   New session and Session Home) render disabled with one line
   ("Scheduled sending isn't available on this deployment; send from
   Invitations when it's time"), values kept and the Settings CSV
   round-tripping; the Workflow card drops "System will dispatch
   automatically". Every other date field stays live: with the clock
   they no longer mislead. 14G turns the setting on. Takes its own read
   (a code slice outside the loop's item).
1. **The loop, inert.** `app/services/scheduled_events/_clock.py`: one
   pass (activation, deadline close) callable directly, the lock, the
   setting (default `0` in this rung); unit and integration tests call the
   pass. No lifespan yet.
2. **Switched on.** RRW's lifespan starts the loop when the interval is
   above `0`; default 120. Tests: the lifespan starts and stops it; a
   failing session does not stop the pass. Last build rung: its read.
3. **Close.** `spec/lifecycle.md` §8.3, `spec/settings_inventory.md`,
   `docs/deployment.md`; checklist item 7 narrowed to mail.

## Definition of done

- A session scheduled to open at T is `ready` by T + interval with no page
  view (`tests/integration/test_scheduled_clock.py`, proposed).
- Two processes running the pass activate a session once.
- With `RRW_SCHEDULED_SEND=off`, no auto-send field accepts input and no
  page promises automatic sending; the Settings CSV round-trips the values.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 14E` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **Answered:** default interval 120 s (`SCHEDULER_INTERVAL_SECONDS`).
- **Answered (author, 2026-11-04):** the loop stamps the release
  window's start and end in the audit log, one event per crossing, so
  14C Item 2's "Release window opened or ended" report fires once.
- **Answered (author, 2026-11-04):** the clock's deadline event carries
  *n* of *N* submitted at the moment it fires, for 14C Item 2's
  "Deadline reached" report.

## Out of scope

- Anything that sends mail: 14F (by hand), 14G (on a clock).
- Auto-archive and auto-delete after archive: not built
  (`guide/deferred_consolidated.md`); the loop is where they would run.

## Doc impact

- `spec/lifecycle.md` — §4 and §4.1: the close, the heal and the accept gate at the review's end (End, or with no End, Release from); the `instrument.closed` row (`reason="release"`, `context.release_at`); §2's recovery path (a reverted session with a passed Release from meets `session.end_passed`); the ordering (no End: Release from on or after Start); §1 and §2.7: `expired` also by End (`reason="deadline"`) or, with no End, Release from (`reason="release"`), and the audit table's `session.expired` row; §8.3: the clock beside the page-view trigger, the advisory lock, `context.fired_by`, the retry spacing; §8.2.3: the release moments as stamped events, only while expired; the audit table's three new events and `trigger="release"` / `"deadline"`; §8: auto-send disabled behind the setting (rung 0).
- `spec/visibility_policy.md` — the `while_ongoing` window ends at End (or, with no End, at Release from; `is_ongoing`); End closes the session.
- `spec/reviewer-surface.md` — no read-back past End outside the release window; saves and Recall stop at the review's end; the closed banner's copy; the refused notice past End.
- `spec/role_landing_and_visibility.md` — the `/me` status past End reads Closed.
- `spec/workflow_card.md` — `expired` reached by End or Release from, not only Close session.
- `spec/rrw_functional_spec.md` — the Closed state's cause.
- `spec/validate_page.md` — the `session.end_passed` rule (edited with the rule, 2026-11-04).
- `spec/settings_inventory.md` — `SCHEDULER_INTERVAL_SECONDS`; `RRW_SCHEDULED_SEND` and the two auto-send fields disabled behind it (rung 0).
- `spec/workflow_card.md` — the auto-send caption gone while the setting is off (rung 0).
- `docs/deployment.md` — both settings in its table.
- `spec/session_home.md` — the `expired` row; the disabled offset boxes (added at close, spec-writer's report).
- `spec/sessions_overview.md` — the lobby End edit skips reminder checks while scheduled email is off (added at close).
- `spec/README.md` — the `lifecycle.md` row (added at close).
- `spec/architecture.md` — the accept rule and the close at the review's end (added at close).
- `spec/email_infra_options.md` — the plan's archived path (added at close).
- `guide/post_azure_todo_checklist.md` — item 7 narrowed to mail (at close).
