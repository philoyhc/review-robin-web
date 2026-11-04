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

## Blast radius (measured)

Taken 2026-11-02 at `fffd4c28`.

| What | Count | Command |
|---|---|---|
| Callers of `observe_scheduled_events` in `app/` (excluding its definition) | 5 | `grep -rn "observe_scheduled_events(" app --include=*.py \| grep -v "def " \| wc -l` |
| Test files naming it | 7 | `grep -rln observe_scheduled_events tests --include=*.py \| wc -l` |
| Files naming `observe_deadline` (app + tests) | 20 | `grep -rln observe_deadline app tests --include=*.py \| wc -l` |
| Test files naming `scheduled_activate_at` | 49 | `grep -rln scheduled_activate_at tests --include=*.py \| wc -l` |

## PR ladder

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
- `## Doc impact` section present and current
- `python3 tools/close_check.py 14E` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- Default interval: 120 s proposed. Author.
- Should the loop also stamp the release window's start and end in the
  audit log? Proposed no: the window is checked on arrival. Author.

## Out of scope

- Anything that sends mail: 14F (by hand), 14G (on a clock).
- Auto-archive and auto-delete after archive: not built
  (`guide/deferred_consolidated.md`); the loop is where they would run.

## Doc impact

- `spec/lifecycle.md` — §8.3: the clock beside the page-view trigger, the lock, `context.trigger`.
- `spec/settings_inventory.md` — `SCHEDULER_INTERVAL_SECONDS`.
- `docs/deployment.md` — the setting in its table.
- `guide/post_azure_todo_checklist.md` — item 7 narrowed to mail (at close).
