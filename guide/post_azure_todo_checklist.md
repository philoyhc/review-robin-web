# Post-Azure to-do checklist

**Opened 2026-09-08 (Segment 19G Item 10).** Things that must happen
**once the institutional Azure deployment has concluded** — provisioned,
deployed, serving, verified — and that nothing in the repository will
otherwise remind anyone about.

**Why this file rather than the institutional deployment runbook.** That runbook, kept
privately with the deployment since 2026-10-24, is
the migration procedure and will be rewritten repeatedly as details are
settled with IT; an item parked in a section that is about to be
rewritten is an item about to be lost. This file is small, stable and
has one job: survive until the deployment is over. Its items move into
the runbook, a spec, or a segment plan when they are done — or when the
runbook stops moving.

**How an item earns a place here.** It is *blocked on the deployment
itself*, not merely unscheduled. Work that is simply not next belongs in
`guide/todo_master.md` or `guide/deferred_consolidated.md`; work waiting
on a host belongs here. Each item names what to do, where to do it, and
**how to tell it is done** — a checklist item nobody can settle is a
note, not a task.

**State, 2026-11-01.** The institutional host is provisioned and has
served Review Robin since 2026-10-31 (the first release with migrations).
Items 7, 9 and 10 wait on the email choices in
`guide/email_and_scheduling.md` rather than on the host; item 12, the dev
slot's leftover deploy credentials, is the author's to remove; items 1, 2, 3,
4, 5, 6, 8 and 11 are settled and removed (their numbers are not reused).
Item 2, the Azure documents, closed 2026-11-02 (author: "move as much of
it out of rrw repo as possible, keeping one document describing a general
picture"): `docs/deployment.md` is that picture; the dev slot's notes,
topology and cost table, the database's backup and the host's diagnosis
went to the private deployment repository; the workstation CLI guide was
already there; the application's own data and failure modes joined
`docs/operations_runbook.md`; the dev slot's deploy workflow was deleted.
Item 8, the honest outbox, closed 2026-11-02 (author: "settle Item 8"):
every outbox row stays `queued` until a transport sends it, and the
invitation's `sent` records the operator's send, not a delivery; the
transport stamps `sent` or `failed` when it lands.
Item 4, page weight on the wire, closed 2026-11-01: the host now gzips,
and the lobby went from 338 kB to 89 kB (`docs/performance.md`
Finding 5).
Item 11, the session-lock bound, closed 2026-11-01 at 5 s, answered
with the 409 page (`docs/database.md`, "The session lock and its
timeout"). Item 1,
the visibility constraint's migration log, was read 2026-11-01 from the
release that first migrated the deployed database (2026-10-31):
`normalized 0 instrument_view_policies row(s)`, on an empty database,
so no operator needed telling. Read the same day from the institutional
host (Cordware's records hold the names): a Premium v3 plan, **one
instance**, Always On, and one `uvicorn` process; the gateway in front
allows 120 s per request (raised from its 20 s default) inside App
Service's fixed 230 s; the Postgres server sets no `lock_timeout` or
`statement_timeout`; and the email app registration holds delegated
Graph permissions only. Items 7 and 10 carry what each settles.

**This is not a runbook.** It does not describe how to deploy. It
describes what is owed *after* deploying, in an order nobody has fixed
yet.

**Admission widened by the author, 2026-09-11.** Item 3 (since
settled and removed) was the first entry here whose blocker is *a* deploy rather than *the* institutional
one — a UI behaviour no test can reach, waiting on the dev slot.
Recorded rather than quietly filed, because the rule above says
"blocked on the deployment itself" and this is blocked on something
cheaper. The justification is the same one that makes the rule work:
a check that needs a deploy needs a file like this one or it is
forgotten. *Corrected 2026-10-01:* this paragraph first said the author
runs nothing locally, so any browser check needed a deploy. The author
has in fact run the app locally with fake auth from early on (`CLAUDE.md`
→ Where work runs), so a check a local browser can settle belongs here
only if it needs what a deployment adds. Items of this
kind leave as soon as they are settled and do not wait for the
cutover.

---

## 7. Give scheduled mail a trigger that does not wait for a page view

**Status:** open, **narrowed to mail** (2026-11-04). Segment 14E built
the trigger: an in-app clock (`app/services/scheduled_events/_clock.py`,
`SCHEDULER_INTERVAL_SECONDS`) runs scheduled activation, the close at the
review's end and the release stamps with no page view
(`spec/lifecycle.md` §8.3, `guide/archive/segment_14E_clock.md`). What is
left is mail: scheduled invitations and reminders, off behind
`RRW_SCHEDULED_SEND` until 14G gives the clock an invite-URL builder and
a send path. The rest of this item is for 14G.

**What is wrong (before 14E).** Scheduled activation, invitations and reminders fired
only when an operator opened a page that ran the sweep: Session Home,
the four Operations pages and the Sessions lobby (`spec/lifecycle.md`
§8.3, findings L4). Nothing fired while nobody had the app open, so a
reminder scheduled for 09:00 went out whenever an operator next looked.

**Why it waits here.** The real fix is a trigger that runs on a clock,
such as a scheduled job, a timer, or an always-on worker. Which one
depends on what the institutional App Service plan and network allow
(recorded privately with the deployment). The page-view trigger now covers the
Operations pages and the lobby (findings L4), which narrows the gap but
does not close it.

**What the host allows (read 2026-11-01).** Always On, one instance and
one `uvicorn` process, so a loop inside the app (the recommendation in
`guide/email_and_scheduling.md`) would run exactly once and never idle
out. It still wants a lock, since a later scale-out would add a second
process.

**Do, after the cutover.** Choose the trigger the deployment supports
and run `observe_scheduled_events` from it for every session with a
pending anchor. **Pass `build_invite_url`**, built from the deployment's
base URL, which is the host's `CORDWARE_PUBLIC_ORIGIN` (segment 21E; today
only `CordwareSettings` reads it, so the worker needs it moved where an
application can; was 14B Part C, now 14G): without it the invite and reminder triggers return early
(`_invites.py`, `_reminders.py`) and only activation runs. A page view
gets that URL from its request; a clock does not. Keep the page-view
sweep as a backstop. `spec/lifecycle.md` §8.3, the minimum-lead-time
rule beside it, and the docstring then say what ships.

**Fix the auto-send caption with it** (author's ruling, 2026-10-02:
scheduled send is work in progress awaiting Azure). The Workflow
card's caption treats `expired` and `archived` as prepared and can
promise "System will dispatch automatically" where the trigger skips
with `not_prepared`. `build_auto_send_invites_caption` in
`app/web/views/_workflow_card.py` should use the trigger's own test,
`validated` or `ready`; `spec/workflow_card.md` "Auto-send invites
signal" records it as a known defect until then.

**Give invites and reminders a retry with it** (author's ruling,
2026-10-02, on `guide/archive/findings_2026-10-01_corpus.md` B20). Scheduled
activation retries and marks `failed_persistent` when it keeps failing;
scheduled invites and reminders have no retry. They can already fail
before any transport exists, at a render or an outbox or audit write.
Since 2026-10-02 (B20, author's second ruling) `observe_scheduled_events`
catches that: it rolls back, logs, writes `session.scheduled_event_failed`
and lets the page render, retrying on the next visit with no cap and no
terminal state. A reminder already queued in a pass that then fails
keeps its dedupe stamp, which commits with its outbox row, so the next
visit does not queue it again (`guide/archive/findings_2026-10-01_corpus.md`
B31, fixed 2026-10-03). Give the clock trigger the same retry and terminal state
as activation for both, covering those queue-stage failures as well as
transport ones.

**Done when** a scheduled invitation and a scheduled reminder each go
out at their set time on the deployed app with no operator page open.
Both the audit events' times and the outbox rows' times show it, and the
links in the outbox rows open on the deployed host.

## 9. Send the responses-received confirmation

**Status:** open, **incomplete work awaiting Azure** (author's ruling,
2026-10-02, on `guide/archive/findings_2026-10-01_corpus.md` G4).

**What is there.** A reviewer's successful submit queues one
`responses_received` outbox row when the session's "Send this
confirmation when a reviewer submits" box is ticked
(`invitations.queue_responses_received`). A reviewer has at most one
queued row (a second submit refreshes it). The row stays `queued`;
nothing transmits it.

**Settled by 14F (2026-11-06).** The dispatcher claims a row
(`queued` → `sending`) before sending (`email_dispatch.dispatch`), and the
invitation and reminder backlog is never sent: a per-row Send or Send
reminder dispatches only the row it has just queued, so rows queued
before the transport, or superseded since, stay `queued`.

**Do, in 14G.** Send queued `responses_received` rows from 14E's clock.
Decide first what happens to rows queued before then — send, drop, or
cut off by date — since some confirm submissions made long before, and
whether a recall, a clear-all or Delete Data drops its queued row.

**Done when** a reviewer who submits on a session set to "Send response
confirmation" receives the confirmation, and one set to "Don't send
response confirmation" receives nothing.

## 12. Remove the dev slot's deploy credentials

**Status:** open, the author's (added 2026-11-02, when item 2 deleted the
dev slot's deploy workflow).

**What is left.** The deleted `main_app-review-robin-web-dev.yml` signed
in to the personal Azure subscription by OIDC and migrated with a stored
database URL. Its workflow is gone, but what it read is not, and no
workflow in this repository reads any of it now (`.github/workflows/`
uses no secret or variable):

- **GitHub, this repository's Actions secrets** (Settings → Secrets and
  variables → Actions):
  - `AZUREAPPSERVICE_CLIENTID_BE4891FDE16B4522926171BF7D1D779F`
  - `AZUREAPPSERVICE_TENANTID_3B9A113C68284F578982060D01073DFE`
  - `AZUREAPPSERVICE_SUBSCRIPTIONID_4290DEED4C5F409AB737C5CF65DC8A20`
  - `DATABASE_URL`, the personal slot's Postgres connection string, a
    password included.
- **Azure, the personal subscription:** the federated credential on the
  app registration (or managed identity) whose client ID the first secret
  holds, trusting this repository's `main`. Remove that credential; the
  registration itself can stay with the dormant slot or go with it.
- **Optionally, the personal slot's database password:** rotate it, or
  retire the slot's Postgres server, since the value sat in a GitHub
  secret. The slot stays dormant, not retired (author, 2026-10-24), so
  this is the author's call.

**Done when** this repository's Actions secrets list is empty (or holds
none of the four), the federated credential is gone from the personal
subscription, and a line here records the date.
