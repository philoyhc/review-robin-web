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

## 4. Measure whether the deployed slot compresses a response

**Status:** open. Blocked on a deploy — the **dev slot is enough**; this
does not wait for the institutional cutover.

**What.** Take one number: does a response from the deployed app come
back with `Content-Encoding: gzip`, and what is its wire size. Segment
19K Item 9 cannot choose among its three options without it, and **one
of the three changes the architecture** — extracting the stylesheet —
which should not be done on a guess. (The other two are "do nothing"
and one line of middleware.)

**Why it cannot be checked here.** Compression in transit is a property
of the platform, not of the code — `app/main.py` registers no
compression middleware, so whichever answer comes back is Azure's, and
`grep` cannot see it. The agent container also cannot ask: its network
policy refuses the slot, returning `403 CONNECT tunnel failed`
(tried 2026-09-12). This is the second entry here whose blocker is *a*
deploy rather than *the* institutional one, and unlike Item 3 it is not
a thing to look at — it is a header to read.

**Done when** this has been run once, from any machine that can reach
the slot, and the answer is written into 19K Item 9's `## Status`:

```
curl -sS -o /dev/null -D - -H 'Accept-Encoding: gzip' \
  https://app-review-robin-web-dev-a5c9f3gpfudaambf.southeastasia-01.azurewebsites.net/operator/sessions
```

| Record | Where to find it | What it decides |
|---|---|---|
| `Content-Encoding` present or absent | the response headers above, or devtools → Network → Response Headers | Present → the ~200 KB page is ~50 KB on the wire, and 19K.9's answer is probably "do nothing, measured". Absent → the whole 200 KB goes out uncompressed on an F1 plan, and compression middleware is one line |
| `Content-Length` | the same headers; devtools shows it as "transferred" beside "resource" size | The actual wire cost, against the 195.9–244.1 KB rendered sizes measured in the container |

Easy Auth sits in front, so an unauthenticated `curl` may return a
redirect to the login page rather than the operator page. **That answer
still counts if the response is large enough to be worth compressing** —
if it is a short redirect, take the reading from devtools on a real
signed-in page instead, which is the more faithful measurement anyway.

**Where this came from.** `guide/segment_19K_assessment_moves.md` Item 9,
whose rung 1 *is* this measurement and whose three candidate answers
stay open until it exists. The item records the container-side numbers
already taken: the same 157.7 KB of inline CSS is **64.6–80.5% of four rendered
pages**, byte-identical across all of them, re-sent on every navigation
across 34 templates. Three are operator pages; `/guide` serves
participants too.
