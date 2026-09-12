# Post-Azure to-do checklist

**Opened 2026-09-08 (Segment 19G Item 10).** Things that must happen
**once the institutional Azure deployment has concluded** — provisioned,
deployed, serving, verified — and that nothing in the repository will
otherwise remind anyone about.

**Why this file rather than `docs/deployment_nus.md`.** That runbook is
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

**This is not a runbook.** It does not describe how to deploy. It
describes what is owed *after* deploying, in an order nobody has fixed
yet.

**Admission widened by the author, 2026-09-11.** Item 3 is the first
entry here whose blocker is *a* deploy rather than *the* institutional
one — a UI behaviour no test can reach, waiting on the dev slot.
Recorded rather than quietly filed, because the rule above says
"blocked on the deployment itself" and this is blocked on something
cheaper. The justification is the same one that makes the rule work:
this author runs nothing locally (`CLAUDE.md` → Where work runs), so a
check that needs a browser needs a deploy, and a check that needs a
deploy needs a file like this one or it is forgotten. Items of this
kind leave as soon as they are settled and do not wait for the
cutover.

---

## 1. Run the visibility-grid audit against real data, before any reviewee-facing window opens

**Status:** open. Blocked on the deployment.

**What.** Sign in as a sys admin and read the **Visibility grid audit**
card on `/operator/sys-admin/sessions`.

**Why it cannot wait, and why it cannot be done now.** The card exists to
find `instrument_view_policies` rows written *before* the Settings-CSV
import learned to refuse an illegal cell (Segment 19C Item 9, PR #2188).
The guard is prospective: a bad row written before it is still stored,
and `resolve_mode` honours it like any other. The cell that matters is a
**reviewee** grant on **Session ongoing** — a reviewee reading responses
while the review is still running.

It has only ever run against fixtures. On a database with almost no rows
a green card means *"no rows here"*, not *"no bad rows"*, so the check
written specifically to find pre-existing bad data has so far produced no
evidence about pre-existing bad data. Only real data settles it.

**Before any reviewee-facing window opens**, because that is the moment
a bad row stops being a latent defect and becomes a disclosure.

**Done when.** The card has been read on the deployed workspace with
real sessions present, and either it lists no findings — recorded with
the date and roughly how many instruments were in scope, since a green
card over three instruments proves little — or each finding has been
resolved by the operator who owns that session, on that instrument's
Band 3 editor. The card is read-only by design; clearing a cell is a
judgment about a live review and does not belong to whoever runs the
check.

**Where this came from.** `guide/archive/segment_19C_refinements.md`
Item 10 planned the first real run and recorded it in the item. The item
then closed and was archived, and the 08sep assessment §5 carried the
weakness while the instruction itself lived nowhere a deployer would
look — which is the failure this file exists to stop repeating.

---

## 2. Re-scope the Azure deployment documents once the personal environment is retired

**Status:** open. Blocked on the deployment.

**What.** `docs/deployment_nus.md` §11 retires the personal Azure
environment as the migration's final step. At that moment several
documents describe an environment that no longer exists, and two more
describe a plan that the outcome has either confirmed or replaced. Work
through them and decide each one's fate.

| Document | Lines | The question it poses at cutover |
|---|---|---|
| `docs/deployment_dev.md` | 405 | Resource names, env vars, CI/CD and bootstrap for the **personal** slot. Rewrite for NUS, or retire and let the NUS material own it? |
| `docs/operations_runbook.md` | 84 | Opens *"Scoped to the current single Azure **dev** slot"*. Re-scope. |
| `docs/troubleshooting.md` | 71 | Opens *"for the deployed dev slot"*. Re-scope. |
| `docs/backup_restore.md` | 83 | Opens *"Scoped to the current single Azure **dev** slot"* — and backup policy is the one of these that an institutional host may dictate rather than leave to us. |
| `docs/deployment_nus.md` | 452 | **A migration runbook whose migration is over.** Does it become the operations reference, or retire to `docs/archive/` with the operational half lifted out first? Easy to forget precisely because it is the document being worked from. |
| `docs/azure_github_setup.md` | 177 | The forward-looking PRD/NPRD scale-up, a `v0.1 draft` carrying a banner saying it is *not* the current plan. Is it still the shape to grow into, or has the NUS reality superseded it? |
| `docs/cli_setup.md` | 641 | Companion to the above, and **the largest of the Azure documents** (third-largest in `docs/`, after `status.md` and the practice audit) — workstation CLI setup attached to the plan that was never executed. Its fate follows its parent's. |
| `docs/architecture.md` | 124 | Infra topology and the provisioned-resource cost table. Both change at cutover. |
| `azure_ask.md` (root) | 244 | The governance ask. Once IT has answered it, it stops being an ask and becomes a record — and it is **not indexed in `docs/README.md`** except inside another row's prose. |

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
describing a retired environment is not merely out of date — it sends a
person to a resource group that is gone while the service is down.

**Done when.** No live document under `docs/` describes the personal
Azure environment as current; each of the nine above has been rewritten,
re-scoped or moved to `docs/archive/`; and **`docs/README.md` has been
re-taken against the folder**, since that index is hand-maintained and an
archived file gets a row there rather than a separate archive index (the
convention `archive/quickstart.md` already follows). A grep for the
retired resource-group and web-app names should return only archived
files and this line.

**Where this came from.** A review of `docs/` on 2026-09-08 that set out
to list the Azure-deployment documents and found that nothing tracked
what the cutover would do to them — the same shape as item 1: an
obligation created by a plan, recorded nowhere the person executing that
plan would look.


---

## 3. Verify the navigation busy indicator in a browser

**Status:** open. Blocked on a deploy — the **dev slot is enough**; this
does not wait for the institutional cutover.

**What.** Segment 19J.4 shipped a busy indicator in `base.html`: a 3px
indeterminate bar plus a visually-hidden `role="status"` region, armed
~200 ms after a same-origin link click or form submit. Three of its
behaviours have never run in a browser.

**Why it cannot be checked here.** Nothing in pytest clicks a link. The
suite pins what it can reach — the markup renders on operator and
reviewer pages, the bar ships `hidden`, every attachment anchor carries
`download`, and the script never sets `disabled` on a submitter — and
those all pass. What no Python test can observe is whether the thing
*behaves*, which is the whole feature.

**Done when** each of these has been seen, on the deployed slot:

| Check | How | Passes when |
|---|---|---|
| Arms on a slow page | Open a session with a large roster, click **Invitations** or **Responses** | The bar appears and runs until the new page paints |
| Never flashes on a fast page | Click between two small pages — Session Home → Reviewers on a small session | No bar appears at all. A flash on every navigation is the failure this feature would be worth reverting for |
| Back button leaves no bar behind | Navigate to a slow page, wait for it, then press Back | The restored page shows **no** bar. This is the `pageshow` handler; bfcache restores the DOM exactly as it was, bar included, if it regresses |
| Downloads do not arm it | Click **Download CSV** on the sys-admin audit log, and **Zip all** on Extract data | The file downloads and **no bar appears** — those links carry `download`, which the script reads. A bar that appears and stays is the twelve-anchor bug the build found |
| Reduced motion | Set the OS "reduce motion" preference, repeat the first check | The bar is static and full-width rather than a travelling highlight |
| Session-nav hover (2026-09-11) | Hover a Setup tab, an Operations tab, and the Home anchor, in **both** themes | Each paints the colours its own selected state uses — no tinted near-white on light, no pale block on dark. The active underline stays on the current tab only. A "coming soon" tab on the Previews page does **not** highlight |
| Chip edge (2026-09-11, 19J.7) | Open **Assignments** (column toggles), the **sessions lobby** (tag filters, Clear, AND/OR) and an instrument card's **Band 2** pill row, in **both** themes | Every chip carries a visible 2px accent edge at rest — no hovering needed. Selected chips are unchanged: solid accent fill. Nothing static beside them has an edge, and no table row has shifted height |
| Amber survives the edge (2026-09-11, 19J.7) | On an instrument card, find a **Band 1 link chip that is not set** | It is still **amber**, now with an accent edge. Amber = not set, edge = you can fix it. If the amber is gone the rule blanked a status colour, which is the one outcome this rung was designed to avoid |
| An inert chip stays inert | Same card, a Band 1 chip for a **link that is not active** (struck through, faded) | **No** accent edge on it. It sets `cursor: default`, so wearing the shade would be a lie |
| Validated is no longer accent blue (2026-09-11, 19J.7) | Session Home's status row on a **validated** session, both themes | The pill reads a deeper blue (`#1e40af` light, `#93c5fd` dark) on the same pale fill — distinguishable at a glance from a chip's accent edge beside it |
| Row pager reads as links (2026-09-11, 19J.7) | Any roster over 200 rows — Reviewers is easiest | Ranges are underlined links in the page's link colour, **not** tinted blocks. The current page is bold body text with no fill |
| A page turn keeps your place (2026-09-11, 19J.8) | Same roster: scroll to the pager **below** the table and click the next range | The new page opens showing the **table card's top edge**, then the column chips, then the page links, then the first new row — everything the operator needs to turn the next page, without scrolling. The address bar shows the `#…-table-card` fragment, which is expected |

**Also worth a glance while you are there:** the bar's colour is
`--btn-primary-bg` and it sits fixed at the very top of the viewport,
above the chrome. Neither was reviewable from a template diff.

**Where this came from.** `guide/archive/segment_19J_assessment_moves.md` Item
4 (and, for the hover row, the hover standardisation of 2026-09-11 —
same reason: a colour no Python test can see), whose Definition of done names these and whose index row holds the
item **built, not closed**, until they are seen. Closing 19J.4 is this
check plus a dated line in its `### Status`.

The five 19J.7 rows come from the same place for the same reason: the
pill rationalisation is entirely colour and edge, and the suite can
check that a rule *declares* them but never that the result reads
right. Closing 19J.7 is those five rows plus a dated line in its
`### Status`.

The 19J.8 row is here for a different reason: the suite can prove the
fragment is emitted and that it names a real id, but not that the
browser stops somewhere an operator finds useful. Closing 19J.8 is that
row plus a dated line in its `### Status`.

---

## 4. The inline stylesheet: measure what a page costs on the wire, then decide

**Status:** open. Blocked on a deploy — the **dev slot is enough**; this
does not wait for the institutional cutover.

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

The deployment is an **F1 free App Service plan with no Always On**
(`docs/known_limitations.md`), so this is not a surface where bandwidth
and cold-start latency are free.

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
