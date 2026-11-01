# Post-Azure to-do checklist

**Opened 2026-09-08 (Segment 19G Item 10).** Things that must happen
**once the institutional Azure deployment has concluded** — provisioned,
deployed, serving, verified — and that nothing in the repository will
otherwise remind anyone about.

**Why this file rather than the NUS deployment runbook.** That runbook, kept
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
Item 2 can be worked now; items 7–10 wait on the email choices
in `guide/email_and_scheduling.md` rather than on the host; items 1, 3,
5 and 6 are settled and removed (their numbers are not reused). Item 1,
the visibility constraint's migration log, was read 2026-11-01 from the
release that first migrated the deployed database (2026-10-31):
`normalized 0 instrument_view_policies row(s)`, on an empty database,
so no operator needed telling. Read the same day from the institutional
host (Cordware's records hold the names): a Premium v3 plan, **one
instance**, Always On, and one `uvicorn` process; the gateway in front
allows 120 s per request (raised from its 20 s default) inside App
Service's fixed 230 s; the Postgres server sets no `lock_timeout` or
`statement_timeout`; and the email app registration holds delegated
Graph permissions only. Items 4, 7, 10 and 11 carry what each settles.

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

## 2. Re-scope the Azure deployment documents at the institutional cutover

**Status:** open. Blocked on the deployment.

**What.** The personal Azure environment is left dormant, not retired
(author, 2026-10-24): it is not revived, and its resources stay. Once
the institutional host serves, several documents describe a dormant
environment as if it were the current one, and two more
describe a plan that the outcome has either confirmed or replaced. Work
through them and decide each one's fate. Line counts of the live documents taken 2026-10-08.

| Document | Lines | The question it poses at cutover |
|---|---|---|
| `docs/deployment_dev.md` | 415 | Resource names, env vars, CI/CD and bootstrap for the **personal** slot. Rewrite for NUS, or retire and let the NUS material own it? |
| `docs/operations_runbook.md` | 94 | Opens *"Scoped to the current single Azure **dev** slot"*. Re-scope. |
| `docs/troubleshooting.md` | 76 | Opens *"for the deployed dev slot"*. Re-scope. |
| `docs/backup_restore.md` | 107 | Opens *"Scoped to the current single Azure **dev** slot"* — and backup policy is the one of these that an institutional host may dictate rather than leave to us. |
| `docs/cli_setup.md` | 657 | Workstation CLI setup, **made generic 2026-10-24** when the NUS runbook it accompanied moved out of this repository: its personal-slot test (B.9) is what changes at cutover. |
| `docs/architecture.md` | 144 | Infra topology and the provisioned-resource cost table. Both change at cutover. |
| `azure_ask.md` (root) | 258 | ~~The governance ask. Once IT has answered it, it stops being an ask and becomes a record — and it is **not indexed in `docs/README.md`** except inside another row's prose.~~ **Done 2026-10-25:** answered differently, it has left this repository for the private deployment repository's archive (strategy v1.0 §7). |

**Why it cannot be done now.** Not for want of scheduling: the correct
text depends on facts that do not exist yet. What the NUS environment is
actually called, what IT owns versus what we own, whether backup policy
is dictated to us, and whether the scale-up topology survives contact
with the institutional host are all answers the deployment produces.
Rewriting these documents before then would be guessing, and a confident
guess in a runbook is worse than a stale sentence that says which
environment it is about.

**Why it cannot wait long afterwards.** These four are the documents
someone reaches for when the deployed service misbehaves. A runbook
describing the dormant environment is not merely out of date — it sends
a person to a resource group that serves nothing while the service is
down.

**Done when.** No live document under `docs/` describes the personal
Azure environment as current; each of the seven above has been rewritten,
re-scoped or moved to `docs/archive/`, or has left this repository; and **`docs/README.md` has been
re-taken against the folder**, since that index is hand-maintained and an
archived file gets a row there rather than a separate archive index (the
convention `archive/quickstart.md` already follows). A grep for the
dormant slot's resource-group and web-app names should return only
archived files, `docs/deployment_dev.md` as the dormant slot's record,
and this line.

**Where this came from.** A review of `docs/` on 2026-09-08 that set out
to list the Azure-deployment documents and found that nothing tracked
what the cutover would do to them: an obligation created by a plan,
recorded nowhere the person executing that plan would look.

---

## 4. The inline stylesheet: measure what a page costs on the wire, then decide

**Status:** measured and decided; open until the deployed check below.

**Measured 2026-11-01 (author, signed-in browser on the institutional
host).** The Sessions lobby: `Content-Length: 337506`, **no
`Content-Encoding`**, 338 kB transferred of 338 kB, 110 ms on campus.
Nothing between the app and the browser compresses (`Server: uvicorn`).
The page has grown from September's 216 kB.

**Decided (author, 2026-11-01): option 2, compression.** Built at the
host rather than in `app/main.py`: Starlette's `GZipMiddleware` in
`cordware/main.py` wraps every mount, so RRW, Residential and Utilities
gain it from one setting (`cordware/spec/host.md`, "Compression").
Option 3 stays unchosen; the rule below against landing it alongside
still holds, so extraction needs a fresh measurement of its own.

**Remaining.** After the next release, the same devtools reading on the
lobby shows `Content-Encoding: gzip` and a transferred size near a
quarter of the page's. Then this item is removed.

*The measurement as it was planned, before the host existed:*

**Moved here whole from `guide/archive/segment_19K_assessment_moves.md` Item 9
on 2026-09-12**, so that Segment 19K no longer waits on a header. The
item was opened alongside 19K.6–8 as "unblocked work while Azure is
outstanding", and that framing was two-thirds right: it is unblocked by
*provisioning* and gated on a request the agent container cannot make.
Its first rung is the only one in that group that cannot start in the
container. Everything needed to take the decision is below; nothing has
to be read back out of the segment plan.

### What is wrong

`base.html` carries the app's entire stylesheet as one inline `<style>`
block, and every one of the **34** templates that extend it re-sends
that block on every render. Measured 2026-09-12 at `11cad9c1` by
rendering real pages through `TestClient` and measuring the response
body:

| Page | Total | Inline CSS | CSS share | gzip(whole body) |
|---|---:|---:|---:|---:|
| Assignments | 195.9 KB | 157.7 KB | **80.5%** | 49.5 KB |
| Guide | 213.9 KB | 157.7 KB | 73.7% | 54.2 KB |
| Lobby | 216.1 KB | 157.7 KB | 73.0% | 53.1 KB |
| Session home | 244.1 KB | 157.7 KB | 64.6% | 57.4 KB |

The **157.7 KB is byte-identical on all four** — the same block, paid
again on every navigation, and it cannot be cached separately because it
is not a separate thing. Three of the four are operator pages; `/guide`
is "operator **and participant** documentation"
(`app/web/routes_guide.py`), so the cost is not the operator's alone.

The dev slot this was measured against was an **F1 free App Service
plan with no Always On** (`docs/known_limitations.md`). The institutional
host is a Premium v3 plan with Always On (read 2026-11-01), so cold
starts are gone; the bytes on the wire are not.

### The measurement

**Why it cannot be taken here.** Compression in transit is a property of
the platform, not the code — `app/main.py` registers **no** compression
middleware, so whichever answer comes back is Azure's, and `grep` cannot
see it. The container cannot ask either: its network policy refuses the
slot, `403 CONNECT tunnel failed` (re-tried 2026-09-12; the proxy logs
it as `connect_rejected`, a policy denial rather than a TLS fault).

What the repo *does* settle, and what it does not: the app is served by
`gunicorn -w 2 -k uvicorn.workers.UvicornWorker` on App Service **Linux**
(`docs/deployment_dev.md`), and there is no `web.config`, nginx config
or compression setting anywhere in the repository. So nothing in the
repo turns compression on — which points at options 2 or 3 below without
establishing anything, because a platform behaviour is not a repo fact.

One line, from any machine that can reach the slot:

```
curl -sS -o /dev/null -D - -H 'Accept-Encoding: gzip' \
  https://app-review-robin-web-dev-a5c9f3gpfudaambf.southeastasia-01.azurewebsites.net/operator/sessions
```

| Record | Where to find it | What it decides |
|---|---|---|
| `Content-Encoding` present or absent | the response headers above, or devtools → Network → Response Headers | Present → the ~200 KB page is ~50 KB on the wire, and the answer is probably "do nothing, measured". Absent → the whole 200 KB goes out uncompressed on an F1 plan, and compression middleware is one line |
| `Content-Length` | the same headers; devtools shows it as "transferred" beside "resource" size | The actual wire cost, against the 195.9–244.1 KB rendered sizes measured in the container |

Easy Auth sits in front, so an unauthenticated `curl` may return a
redirect to the login page rather than the operator page. **That answer
still counts if the response is large enough to be worth compressing** —
if it is a short redirect, take the reading from devtools on a real
signed-in page instead, which is the more faithful measurement anyway.

### The three answers it chooses between

1. **Nothing.** If the Azure front end already gzips, ~50 KB per page
   over the wire is unremarkable, and the inline block keeps the
   single-artefact property the architecture chose it for
   (`CLAUDE.md`: no stylesheet, no build step). **If this is the answer
   it is recorded as a measured decision, not left implicit.**
2. **Compression middleware.** One line in `app/main.py`, no
   architectural change, and it compresses the **whole** response rather
   than the CSS alone — the HTML around it is 38–86 KB per page.
3. **Extract the stylesheet.** The only option that makes the CSS
   *cacheable*, so a repeat view pays a 304 rather than the bytes.
   Mechanically cheap — one `<style>` element, **3,869 lines, zero
   Jinja** — and the one that changes the architecture, so it needs the
   strongest evidence.

**Do not land 2 and 3 together.** Compression would mask most of what
extraction buys, making it impossible to say afterwards which was worth
it.

**`_RevalidatingStaticFiles` sets `Cache-Control: no-cache`** (19H Item
4), so an extracted stylesheet would *revalidate* rather than be cached
hard — a 304 on repeat views, not a skipped request. Still far cheaper
than 157.7 KB, but do not claim a stronger caching win than the existing
posture gives. Option 3 also inherits a **stale-stylesheet-after-deploy**
failure class the inline block does not have; the `no-cache` posture is
what answers it.

**Out of scope whatever is chosen:** splitting `base.html` into several
stylesheets (one file in, one file out — a module boundary inside the
CSS is a separate argument with no evidence yet), and any build step
(`CLAUDE.md` rules out a JS/CSS toolchain; extraction is a file move,
not a bundle).

### Blast radius, measured at `11cad9c1`

| What | Count | Command |
|---|---:|---|
| Templates extending `base.html` | **34** | `grep -rl 'extends "base.html"' app/web/templates \| wc -l` |
| `<style>` blocks in `base.html` | **1** | parse |
| CSS lines / file lines | **3,869 / 4,732** | `<style>` spans lines 24–3894 |
| Jinja constructs inside the CSS | **0** | parse |
| Inline CSS, raw / gzipped | **157.7 KB / 39.2 KB** | `len()` + `gzip.compress` |
| CSS share of a rendered page | **64.6–80.5%** | the table above |
| Compression middleware in `app/main.py` | **0** | `grep -n Middleware app/main.py` |
| Existing static mount | 1 (`/static`, revalidating) | `app/main.py:42`, `:97` |

### One finding worth keeping

**The item's own CSS figures were wrong, and the document already
contained the right ones.** The first draft said 3,885 lines / 158.4 KB
/ 39.5 KB. `base.html:9` carries a Jinja comment whose text includes the
literal string `` <style> ``, so a non-greedy `<style[^>]*>(.*?)</style>`
over the raw template matched **that** as the opening tag and swallowed
15 lines of comment and the no-FOUC `<script>` as if they were CSS. The
real element is lines 24–3894.

The instructive part is not the regex. **The page-weight table above
already said 157.7 KB** — measured from a rendered response, where Jinja
has stripped the comment before any regex runs, so it was never exposed
to the bug. Two measurements of one quantity, by two methods,
disagreeing by 0.7 KB in one document, and nobody compared them.
*Measuring twice is worth nothing if the two results are never put
beside each other.* (19K.6 hit the same `<style>`-in-a-comment trap
independently; `tests/unit/_base_css.py` anchors on `:root {` because of
it.)

### Done when

- The wire size of a real page from the dev slot, with its
  `Content-Encoding`, is recorded **here**.
- A decision among the three is taken and written where a reader finds
  it — `spec/architecture.md` if the architecture holds, or the plan of
  whatever segment changes it if not.
- If the answer is "nothing", that is recorded as a measured decision
  rather than left implicit.
- Whatever is built after that is scoped as its own item in a live
  segment; this entry is the evidence, not the build.

---

## 7. Give scheduled sends a trigger that does not wait for a page view

**Status:** open, **incomplete work awaiting Azure** (author's ruling,
2026-10-01, on `guide/archive/findings_2026-10-01_corpus.md` B19).

**What is wrong.** Scheduled activation, invitations and reminders fire
only when an operator opens a page that runs the sweep: Session Home,
the four Operations pages and the Sessions lobby (`spec/lifecycle.md`
§8.3, findings L4). Nothing fires while nobody has the app open, so a
reminder scheduled for 09:00 goes out whenever an operator next looks.

**Why it waits here.** The real fix is a trigger that runs on a clock,
such as a scheduled job, a timer, or an always-on worker. Which one
depends on what the NUS App Service plan and network allow
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
application can, `guide/segment_14B_email_infrastructure.md` Part C): without it the invite and reminder triggers return early
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

## 8. Stamp outbox rows `queued` until a transport has sent them

**Status:** open, **incomplete work awaiting Azure** (author's ruling,
2026-10-02, on `guide/archive/findings_2026-10-01_corpus.md` H20).

**What is wrong.** Nothing sends email yet: no caller reaches the
transport in `app/services/email_send.py`. The send path still writes
each outbox row `queued` and flips it to `sent` in the same call
(`app/services/invitations.py`), so `sent` claims a delivery that never
happened. Invitation status follows it.

**Why it waits here.** The honest status needs the transport that
makes it true. Segment 14B Part A wires the dispatch helper, and which
backend it uses depends on what the NUS tenant allows
(`spec/email_infra_options.md`).

**Do, with the transport.** Leave the row `queued` until the transport
reports success, then stamp `sent` (or `failed`, with
`error_message`). Re-check every reader of `sent` — the invitation
pills, the Workflow card captions, the Responses page — against the
new timing. `README.md` and `docs/known_limitations.md` describe today's
behavior until then.

**Done when** a row reads `queued` until its message leaves, `sent`
only after the transport confirms, and `failed` when it does not.

## 9. Send the responses-received confirmation

**Status:** open, **incomplete work awaiting Azure** (author's ruling,
2026-10-02, on `guide/archive/findings_2026-10-01_corpus.md` G4).

**What is there.** A reviewer's successful submit queues one
`responses_received` outbox row when the session's "Send this
confirmation when a reviewer submits" box is ticked
(`invitations.queue_responses_received`). A reviewer has at most one
queued row (a second submit refreshes it). The row stays `queued`;
nothing transmits it.

**Do, with the transport.** Decide first what happens to the rows
queued before the transport existed — send them, drop them, or cut off
by date — since some confirm submissions made long before. A recall,
a clear-all or Delete Data leaves its queued row in place too, so
decide whether those are dropped or re-checked before sending. The
dispatcher should claim a row (flip it to `sending`) before sending,
since a resubmit rewrites a row that is still `queued`. Then send queued `responses_received` rows like any other,
and stamp them per item 8.

**Done when** a reviewer who submits on a session set to "Send response
confirmation" receives the confirmation, and one set to "Don't send
response confirmation" receives nothing.

## 10. Settle which Graph permission the Graph backend uses

**Status:** open, **awaiting Azure** (author's ruling, 2026-10-02, on
`guide/archive/findings_2026-10-01_corpus.md` F23).

**What is wrong.** The two descriptions of the unbuilt Graph backend
disagree. The `GraphEmailTransport` stub's docstring in
`app/services/email_send.py` describes a delegated send
(`/me/sendMail` with each operator's token), while
`spec/email_infra_options.md` puts delegated permission out of scope
and makes the stub Option B: an application permission on a shared
mailbox (`/users/{mailbox}/sendMail`). The stub sends nothing, so no
behavior depends on either.

**Why it waits here.** Which permission is possible is the NUS tenant's
answer, not the repository's (`spec/email_infra_options.md`, Option B).
**The tenant's answer so far (read 2026-11-01):** the app registration
holds delegated `Mail.Send` and `User.ReadBasic.All` with tenant-wide
consent, and **no application permission**. So a delegated send works
today; a shared-mailbox send waits on the ask in
`guide/email_and_scheduling.md`, choice 2.

**Do, with that answer.** Implement the stub to the permission the
tenant grants, and make its docstring and the spec say the same thing.

**Done when** the docstring and `spec/email_infra_options.md` name the
same permission, and that permission is the one the tenant granted.

## 11. Bound the session-lock wait with a Postgres `lock_timeout`

**Status:** open, **awaiting Azure** (author, 2026-10-08; the open
question of `guide/archive/segment_19U_post_assessment_7oct.md` Item 1).

**What is there.** Every state-gated save, lifecycle transition,
operator invitation action and scheduled pass takes `SELECT … FOR NO
KEY UPDATE` on the session row (`lock_session` in
`app/services/session_guard.py`) and holds it to its commit (19U Item 1,
findings Bc4, Bc5, Bc8). Nothing bounds the wait: a request that holds
the lock and stalls — a slow import, a hung connection — makes every
other request on that session wait until it ends. SQLite, which local
runs and the default test run use, never blocks; the `ci-postgres` job
runs the suite on Postgres (`TEST_DATABASE_URL`, `tests/conftest.py`),
where a two-connection test can show the wait.

**Why it waits here.** The bound depends on the deployed database and
host: the Azure Postgres server, the worker count, and the App Service
request timeout it must sit well inside. So does where it is set — per
role (`ALTER ROLE … SET lock_timeout`), per connection (`connect_args`
in `app/db/session.py`), or per lock (`SET LOCAL` before the
`FOR NO KEY UPDATE`).

**What the deployment says (read 2026-11-01).**
- **The request ceiling.** The gateway in front allows **120 s** per
  request (raised that day from its 20 s default), inside App Service's
  fixed 230 s.
- **No server-wide bound.** The Postgres server leaves `lock_timeout`,
  `statement_timeout` and `idle_in_transaction_session_timeout` at `0`,
  so nothing bounds a lock wait unless the app sets it.
- **Concurrency.** One instance runs one `uvicorn` process, and the
  server's connection limit is far above what one process opens.

So the bound is the app's to set, and it should be a few seconds, far
inside 120 s: a request that waits longer for a session lock is better
answered with the 409 page than left hanging.

**Do, with the deployment.** Choose the value and where it is set.
Decide what a timeout answers: today Postgres's `LockNotAvailable`
would surface as a 500, where the 409 page ("someone else is changing
this session; try again") is probably the right answer. Record the
setting in `docs/database.md`.

**Done when** a request blocked behind a held session lock on the
deployed Postgres fails within the chosen bound with the chosen answer;
a two-connection test in the `ci-postgres` suite holds the lock in one
transaction and asserts that bound and answer from the other; and
`docs/database.md` states the setting.
