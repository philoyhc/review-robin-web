# Segment 22G — Diagnostics

**Opened:** 2026-11-04, parked; Item 1 planned 2026-11-05 · **Theme:** a
small set of status reports that say whether the deployed host is doing
what it should, without reading logs · **Related:**
`guide/archive/segment_14E_clock.md` (the clock Item 1 reports on)

## Item 1 — System Status, a third Admin tab

### Opportunity

On Azure, what the app is doing in the background is visible only in
the logs. The clock (14E) is the first case: it runs in-process every
`SCHEDULER_INTERVAL_SECONDS` (`0` turns it off), skips a pass when another process holds
its advisory lock, and logs a failure, but nothing on a page says
whether it is running or when it last passed. An operator who sees a
scheduled Start not fire cannot tell a stopped clock from a refused
activation without the author opening the logs.

### Decision

A third tab on the Admin page, **System Status**
(`/operator/sys-admin/system`, `sys_admin_system.html`), after Sessions
Diagnostics and Accounts Management, behind `require_sys_admin` like
them (author, 2026-11-05). Read-only; four cards:

1. **Clock** — on or off and its interval; the last pass (start,
   duration, sessions visited, or "none yet since start"); the last
   failure (time, exception type) with a failure count and a busy-skip
   count since the process started.
2. **Due next** — across the workspace: the next scheduled Start, the
   next End close, the next release-window stamp; and **stuck work**,
   sessions `due_session_ids` would pick now (one that stays listed pass
   after pass is not being moved), plus
   `session.scheduled_activation_failed_persistent` events from the last
   7 days, each linking to its row on Sessions Diagnostics.
3. **Sending** — whether `RRW_SCHEDULED_SEND` is on.
4. **This instance** — `app_version`, process start and uptime, the
   database dialect, and the schema revision against the head this code
   expects.

**Rejected: a card on Session Home.** The clock is the host's, not a
session's; an operator cannot act on it, and per-session copies of one
host fact would disagree only by time of render. **Rejected: extending
`/health`.** It is unauthenticated and machine-read by the deploy's
health check; host state does not belong on it.

### Semantics

- **The clock's state is in memory, per process.** A `ClockStatus`
  record in `_clock.py`, written by `run_forever` / `run_pass`, read
  through one accessor. It resets on restart, so every count says
  "since <process start>". Azure runs one instance and one process, so
  it is exact there; with several, the page reports the process that
  served it, and says so.
- **Off** (`SCHEDULER_INTERVAL_SECONDS=0`): the Clock card says off,
  and Due next still renders, since page views still fire steps.
- **A pass held by another process** (`run_pass` returns `-1`) counts
  as a skip, not a pass, and leaves the last pass as it was.
- **Due next** reads the same columns `due_session_ids` does, so the
  two cannot disagree; archived sessions are left out as there.
- **Schema head.** The deploy ships no `alembic/` (Cordware's
  `release.yml` keeps it off the import path), so the app cannot read
  the head from scripts. The head is a constant in `app/db/`, and a
  unit test fails when it differs from `alembic heads`.
- **No institutional identifier** reaches the page: no tenant, host
  name, address, or connection string; the dialect name only.

### Judgment calls — decided

- Counts since process start, not persisted: a persisted heartbeat is
  a table and a write per pass for what the logs already keep.
- The 7-day window on persistent failures: long enough to see over a
  weekend, short enough that a fixed one drops off.
- A tab, not a card on Sessions Diagnostics: that page is a table of
  sessions; host state would sit above it on every visit.

### Blast radius (measured)

Taken 2026-11-05 at `a5aa3284`.

- Tab strip: 1 partial, `sys_admin_top_nav.html` (2 tabs today).
- Routes: `app/web/routes_operator/_sys_admin.py`, one new GET; the URL
  crawl (`tests/integration/test_url_crawl.py`) fails on an unvisited
  GET, so it gains a row.
- Clock: `_clock.py` is 197 lines, with `run_pass` and `run_forever`
  the two writers; started at one site (`grep -n run_forever app/main.py`).
- Tests naming `sys-admin`: 41 files (`grep -rln "sys-admin" tests --include=*.py | wc -l`),
  `tests/integration/test_sys_admin_chrome.py` the tab-strip one.
- Specs: `spec/operator_ui_concept.md` §6 lists the Admin tabs;
  `spec/operator_button_audit.md` §21 carries the tab-strip rows
  #248–249 (`grep -rln "Sessions Diagnostics" spec/`).
- Migrations: 102 files in `alembic/versions/`.

### PR ladder

1. **Scaffold.** The tab, the route, the template with the four cards as
   static placeholders (real headings and copy, every value "—"), a
   crawl row and a chrome test. Touches no service.
2. **Clock.** `ClockStatus` and its accessor; the writers record into
   it; the Clock card wired. Tests drive `run_pass` with a fake factory.
3. **Due next.** A service query over the `due_session_ids` columns plus
   the persistent-failure events; a view adapter; the card wired.
4. **Sending and This instance.** The settings read, the schema-head
   constant with its test, uptime; both cards wired. Last build rung:
   `diff-reviewer` reads rungs 1–4 cumulatively.
5. **Close.** Spec sweep, Status, archive.

### Definition of done

- `GET /operator/sys-admin/system` renders the four cards for a
  sys-admin and refuses an operator, per `require_sys_admin`.
- A test fails when the schema-head constant differs from `alembic heads`.
- The Clock card's counts move under a test that runs a pass, a busy
  skip and a failure.
- `spec/operator_ui_concept.md` §6 and `spec/operator_button_audit.md`
  list the third tab.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 22G.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

- **`APP_VERSION` on Azure.** RRW shows `dev` unless the host sets it;
  whether Cordware's release should set it to the imported commit is a
  Cordware change. Author, at rung 4.

### Out of scope

- Host request logging: the Cordware stub in `guide/todo_master.md`
  ("Cordware host logging, events 4 and 5").
- CPU, memory, requests and logs: Azure's own pages.
- Later candidates, for a later item if wanted: the outbox across
  sessions, configuration sanity, identity and Graph reachability, data
  counts, audit-schema drift.

### Doc impact

- `spec/operator_ui_concept.md` — §6 gains the System Status tab and its four cards.
- `spec/operator_button_audit.md` — the tab-strip row for System Status beside #248–249, and the page's own section.
- `guide/todo_master.md` — delete the segment's entry at the item's close.
