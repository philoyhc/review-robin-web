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

**Also worth a glance while you are there:** the bar's colour is
`--btn-primary-bg` and it sits fixed at the very top of the viewport,
above the chrome. Neither was reviewable from a template diff.

**Where this came from.** `guide/segment_19J_assessment_moves.md` Item
4, whose Definition of done names these and whose index row holds the
item **built, not closed**, until they are seen. Closing 19J.4 is this
check plus a dated line in its `### Status`.
