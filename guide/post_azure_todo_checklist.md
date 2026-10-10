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
a check that needs a deploy needs a file like this one or it is
forgotten. *Corrected 2026-10-01:* this paragraph first said the author
runs nothing locally, so any browser check needed a deploy. The author
has in fact run the app locally with fake auth from early on (`CLAUDE.md`
→ Where work runs), so a check a local browser can settle belongs here
only if it needs what a deployment adds. Items of this
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
Migration `14db60023e88` (#2833) has since normalized those rows, so
the card should read empty; reading it on real data confirms the
migration ran there. The cell that matters is an **observer** grant of
`Raw` or `Anonymized` on **Session ongoing**: an observer reading
individual responses while the review is still running. The reviewee
readers treat that window as closed, so a reviewee row grants nothing.

It has only ever run against fixtures. On a database with almost no rows
a green card means *"no rows here"*, not *"no bad rows"*, so the check
written specifically to find pre-existing bad data has so far produced no
evidence about pre-existing bad data. Only real data settles it.

**Before any participant-facing window opens**, because that is the
moment a bad row stops being a latent defect and becomes a disclosure.

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
through them and decide each one's fate. Line counts of the live documents taken 2026-10-08.

| Document | Lines | The question it poses at cutover |
|---|---|---|
| `docs/deployment_dev.md` | 415 | Resource names, env vars, CI/CD and bootstrap for the **personal** slot. Rewrite for NUS, or retire and let the NUS material own it? |
| `docs/operations_runbook.md` | 94 | Opens *"Scoped to the current single Azure **dev** slot"*. Re-scope. |
| `docs/troubleshooting.md` | 76 | Opens *"for the deployed dev slot"*. Re-scope. |
| `docs/backup_restore.md` | 107 | Opens *"Scoped to the current single Azure **dev** slot"* — and backup policy is the one of these that an institutional host may dictate rather than leave to us. |
| `docs/deployment_nus.md` | 443 | **A migration runbook whose migration is over.** Does it become the operations reference, or retire to `docs/archive/` with the operational half lifted out first? Easy to forget precisely because it is the document being worked from. |
| ~~`docs/azure_github_setup.md`~~ <!-- path-ref-ok --> | 177 | **Retired 2026-10-03** to `docs/archive/azure_github_setup.md`, superseded by `docs/deployment_nus.md` (findings 2026-10-03 H-retire). |
| `docs/cli_setup.md` | 657 | Companion to the above, and **the largest of the Azure documents** (third-largest in `docs/` when measured, after the status file and the practice audit, both since archived) — workstation CLI setup attached to the plan that was never executed. Its fate follows its parent's. |
| `docs/architecture.md` | 144 | Infra topology and the provisioned-resource cost table. Both change at cutover. |
| `azure_ask.md` (root) | 258 | The governance ask. Once IT has answered it, it stops being an ask and becomes a record — and it is **not indexed in `docs/README.md`** except inside another row's prose. |

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
| Session-nav hover (2026-09-11) | Hover a Setup tab, an Operations tab, and the Home anchor, in **both** themes | Each paints the colors its own selected state uses — no tinted near-white on light, no pale block on dark. The active underline stays on the current tab only. |
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

---

## 5. Verify Session Home's Owners card and the tag typeahead in a browser

**Status:** **checked locally by the author, 2026-10-01**, in a browser
against the app on `localhost` with fake auth. The two rows that name
more than that, the keyboard pick in **Safari** and **a screen reader**,
need no deployment either, so they moved to
`guide/deferred_consolidated.md` Part C rather than waiting here.

**What.** Segment 19S Item 10 gave Session Home's Owners card a card
of its own, where each Add owner and Remove saves at once
(`spec/session_owners.md`; its Lock / Unlock retired 2026-10-09,
`guide/operator_pages_enhancements.md` Item 1), and Item 7 put a typeahead on
the four tag boxes. The suite pins their markup; headless Chromium
drove the scripts, but draws no datalist popup.

**Done when** each has been seen, in a real browser:

| Check | How | Passes when |
|---|---|---|
| The card is live | Open Session Home | The Owners card has no Lock / Unlock; the picker, Add owner and another owner's Remove work at once |
| Add owner saves at once | Session Home → Owners card: pick an operator, **Add owner** | The page reloads at the card with them in the table and gone from the picker; no banner |
| Remove asks, then saves at once | Click **Remove** on another owner's row | The browser's confirm names them; **Cancel** posts nothing. Confirming reloads with that row gone and them back in the picker |
| The last owner cannot go | On a one-owner session | That row's Remove is disabled |
| Removing yourself asks | Click Remove on your own row | The browser's confirm names losing access; **Cancel** posts nothing. Confirming lands on the sessions lobby |
| Any lifecycle state | Repeat the first row on an Activated session | It saves; the details card stays locked |
| Without JavaScript | Disable JavaScript, reload Session Home | Add owner and every Remove still work (plain forms); every Remove skips the confirm |
| Owners sits above the Danger Zone | Session Home, wide and narrow windows | Owners starts level with Quick Setup and the Danger Zone follows it in the right column; narrowed, the order is Quick Setup → Owners → Danger Zone |
| Create is unchanged | Create new session → Owners, JavaScript on and off | On: Add owner stages a row and a staged row's Remove takes it out again, with no confirm; Create session saves what remains. Off: no Add owner; the picker's one address is saved with Create session. *(Off could not pass before #2714, 2026-10-01: Create rendered disabled without script; now `test_create_without_javascript_saves_the_typed_owner` repeats it.)* |
| The tag popup, after each comma | The lobby's row and bulk expanders, Create's Tags card, Session Home's Tags field: type `a` then `pilot, e` | A popup of your existing tags each time, completing only the tag after the last comma, never offering one already in the box |
| The keyboard picks | In each box, arrow to a suggestion and press Enter — **Safari as well as Chromium** | Enter takes the suggestion. In the lobby's expanders it must never submit the form (#2579: Enter in the lobby form does nothing) |
| A screen reader | VoiceOver or NVDA on one box | The suggestions are announced as a list |

**Where this came from.** `guide/archive/segment_19S_post_assessment.md` Item 10
and Item 7, both closed with this check owed; each `### Status` points
here. Settling a row is a dated line there, not a reopening.

## 6. Verify the Instruments response-field rows, action row and small fixes in a browser

**Status:** **checked locally by the author, 2026-10-01**, in a browser
against the app on `localhost` with fake auth. Nothing in the table
needs a deployment.

**What.** Segment 19T Items 1 and 2 reworked Band 3's response-field rows:
- a "+" on each row;
- the last row kept;
- ✓ enabled only when the row differs from its pill;
- R and ≡ saved by Save alone;
- row-ordered ✓, Save and pill drag;
- the 2 : 3 split.

Item 9 then retired ✓ and the response pills: the rows became a table with
an Active checkbox and ▲ ▼, a valid row reaches the preview by itself,
added fields default to a muted "Field N", and Band 3 splits 15 : 85 (1 : 4 until Item 12A).

They also stopped an open card (`?editing`) from disabling the action row.
Item 3 made the Name and Email pills static labels, kept Delete's confirm
checkbox from dirtying the card, and made Band 2's "Who can see what you
wrote" card repaint on a Band 3 Visibility edit. Item 6 put a `*` on the
Required pill, refused fractional Integer bounds and printed Decimal
bounds as entered. Item 7 moved the visibility editor into Band 2's "Who
can see what you wrote" card. Item 8 moved display fields from Band 2's
pills to a table in Band 3's left column. Item 10 added branching: ⑂ puts
optional governed fields under a number or List field (↰ joins more
fields to its branch), shown on
the reviewer surface only while the parent's answer meets a condition. Item 12
added ranges to a number's condition: within or outside two ends,
inclusive or exclusive.
The suite pins the markup, and headless Chromium drove the rows on a
rendered page; the author checked them in a browser.

**Done when** each has been seen in a browser, card unlocked:

| Check | How | Passes when |
|---|---|---|
| The rows | Open an instrument card, one with a branch | One row per saved field in a table. A plain field or a parent reads Active, "+", ⑂, ↰, name, type, bounds, R, ≡, ▲, ▼, X; a governed row shifts one column right before the name (the bar, Active, "+", ↳) and has no ⑂. A rule sits under each plain field and under each branch as a whole — the parent, its condition row and its governed rows share one. X is red; "+", ⑂ and ↰ / ↳ are one width; Band 3 splits 15 : 85 |
| "+" inserts below | "+" on the first of two rows | A row appears between them, its name box showing a grayed "Field N", cursor in it; the preview gains the column |
| Default names | In that row press →; clear the name; type "Rating" then clear it | → turns "Field N" into normal text; cleared, it shows grayed again; after Save and a reload a kept "Field N" reads as normal text |
| The preview follows the row | Type a name; switch the row to Integer and set Max below Min | The preview follows the name at once; the bad Max marks the row amber with the reason on hover, and the preview keeps the last valid shape |
| Active and ▲ ▼ | Untick Active on a field with responses; ▲ on the second row | The "hide this field?" confirm names Active, and cancelling keeps the tick; ▲ swaps the rows and the preview columns, and Save keeps the order |
| R and ≡ alone | Toggle R on a saved field, nothing else | Save enables; after Save and a reload, the field's required state stuck |
| A new field saves twice | "+", Save, rename it, Save again, reload | One field with the new name, not two |
| Order persists | Insert a row between two, name it, Save, reload | It sits between them |
| The last row stays | Delete rows down to one | That row's X is disabled |
| Cancel removes a new row | "+", then Cancel and confirm | The new row is gone |
| An open card doesn't lock the row | Edit, Cancel (URL now `?editing=`), then Lock | Replicate, +Instrument and +Page break stay live; the URL loses `?editing` |
| Delete's checkbox is clean | Tick the Delete confirm box on a clean card | Save stays off; Delete leaves without a "Leave site?" prompt |
| Name and Email are fixed | Click Name's and Email's checkboxes in Band 3's display-field table | They stay ticked and never toggle, with no ▲ ▼; they sit first and second in the preview |
| Email on group rows | Switch Unit to Group, then back | Email dims with "Not shown on group rows", then returns |
| Visibility preview repaints | Cycle You's "Responses released" in Band 2's card, Save, Lock, reload | The locked card shows the new mode and still reads the same after the reload |
| The Required pill's `*` | Open an instrument card with a required field; open the reviewer preview | Both pills read "*Required items completed", legible in capitals beside the `*` headers |
| Integer steps are whole | On an Integer row, set Step 0.5 | The row turns amber with "Integer fields take whole-number Min, Max and Step. Choose Decimal for steps like 0.5." on hover; Save refuses it naming the field; switched to Decimal, the amber clears |
| Integer Step defaults to 1 | Add a field, make it Integer, name it, set Min 1 and Max 5, leave Step blank; Save; reload; open the reviewer preview | Before Save the Step box shows the muted "Step"; after Save it reads 1, and still does after the reload; the constraint line reads "1-5, steps of 1" |
| Decimal bounds as entered | Decimal row 0–1, Step 0.25, Save; open the reviewer preview | The line above the table reads "0-1, steps of 0.25" |
| Display fields table | Unlock an instrument; untick Tag 1, move Tag 2 up with ▲, drag a preview column edge; Save; reload | Band 2 has no display pills; Band 3's left column lists Name and Email ticked and fixed, then the rest as compact rows with name pills. The preview drops Tag 1 and reorders at once; after Save and reload the order, selection and width hold, and the reviewer preview matches. On a group-scoped instrument Email is unticked and fixed |
| A long display label, unlocked | Give a tag a long label; unlock an instrument | In Band 3's left fifth the row's ▲ ▼ stay reachable, scrolling with the table if the label widens it |
| Visibility pills when locked | Lock an instrument card | "Who can see what you wrote" shows each mode as a pill, like the editor's fixed cells; a long display-field label scrolls inside Band 3's left column rather than widening it |
| Visibility in the card | Unlock an instrument; cycle Reviewees' "Responses released" and Observers' "Session ongoing"; Save; Lock | Unlocked, the card shows You (reviewer) / Reviewees / Observers with the note, and Band 3 has no Visibility table. After Save and Lock, the locked card shows the new Reviewees mode and no Observers row; a reload keeps both changes |
| A branch with ⑂ | ⑂ on an Integer row; type 4 in the condition | A condition row ("If the above [=] [4] then [Show the below]", the last a select whose other option is "Require the below (else, optional)") and one grayed "Field N" appear under a broad, pale bar; the condition is amber until a value is typed; the parent's X is off and String is disabled in its type select |
| Join and detach | ↰ on a plain row just below the branch; then ↳ on it | ↰ makes it the branch's last field; ↳ puts it directly below the branch; ↳ on a branch's only field removes the condition too |
| List conditions | A List parent with a branch; pick "is not"; name an option the list lacks | The operator offers "is" and "is not"; the missing option turns the condition amber, naming it |
| Active cascades | Untick a parent's Active, then tick it | Its branch's rows untick and their Active boxes go off; ticking the parent restores them |
| The branch for a reviewer | Save a branched instrument; open the reviewer preview; answer the parent under, then over, the condition | The governed cell is muted and disabled, titled "Opens when …", and opens as the answer meets the condition; text typed there greys, not clears, when the branch closes, and Save deletes it if it's still closed |
| A refused parent keeps the text | With JavaScript off, as a reviewer, save the parent with its branch open; then type 2.5 in the Integer parent and a governed answer; Save | Both come back with their text; the parent reads "Must be a whole number." and the governed one "Kept until … is fixed."; neither was saved. (With script on, the browser refuses 2.5 before Save posts; the operator preview has no Save.) |
| A locked branch | Give a governed field a response; reopen the card | The condition, the branch's "+"s and its fields' X and ↳ are off |
| The export's condition | Download the by-instrument bundle for a branched instrument | The governed field's metadata carries a "Shown when" row ("Rating ≥ 4") |
| A required governed field | Press R on a governed row; Save. Then untick R on every field outside the branch; Save | The first saves, with R pressed. The second is refused, naming the governed field: "…can be required only when the instrument has an active required field outside any branch." In the preview, the "*Required items completed" count doesn't include it |
| Required only while open | As a reviewer, answer the parent under, then over, the condition; submit with the governed field empty each time | Under: it submits; the field's label doesn't say "(required)". Over: the label says "(required)", the pill's total grows by one, and Submit lists the field as missing. Invitations and Responses count the reviewer complete in the first case and not in the second |
| A Require branch | On a branch's condition pick "Require the below (else, optional)"; Save; as a reviewer, answer the parent under, then over, the condition, leaving the governed field empty | In the builder, the governed rows' R grays out, titled "Required while the condition holds", keeping how it was pressed (back to Show restores it); the preview's governed column is no longer muted, gains "*", and counts in "All items" but not "Required items". For the reviewer the governed cell is always open: under, it submits empty; over, its label says "(required)" and Submit lists it as missing. Downloaded by instrument, its metadata reads "Required when". With a governed response saved, the select is off |
| Two levels of branching | On a branch's Integer field press ⑂; name the new field; then ↰ on the plain row below the group, ↳ on it, ▼ on the level-1 parent, and untick its Active; Save; answer as a reviewer | The new condition row and field sit one column further right with their own bar, the name column never moving; ↰ joins the level-2 branch and ↳ steps it back to level 1; ▼ carries the level-1 field's branch with it; unticking it hides its branch. Save keeps the chain; a third level is refused by name. For the reviewer, closing the top field closes the whole chain even if the middle answer still meets its own condition. With a level-2 field answered, both conditions above it lock |
| Range conditions | On a numeric parent's condition, open the operator select; pick "is within (inclusive)"; type 2 and 4; then "is outside (exclusive)"; then "is more than (inclusive)" | Ten spelled-out operators; a range shows a second box after "to", amber until both ends are numbers with the low below the high; the hint reads "Opens when Rating ≥ 2 and ≤ 4", then "Rating < 2 or > 4"; a single-value operator hides and clears the second box. After Save, the reviewer preview opens the branch at 2 and 4 for within (inclusive) and only below 2 or above 4 for outside (exclusive) |
| Item 12A's table adjustments | Open a card with a numeric branch and one with a List branch (or switch a parent between Integer and List); widen and narrow the window | Join reads ↰ and detach ↳; a number condition's boxes stay as wide as the parent's Min box; every Active checkbox sits centered in its cell; after ↰ / ↳ there's a gap two buttons wide before the name; the condition's operator lines up with the name boxes, same width, "If the above" right-aligned just before it; the first value box starts under the type column, with the same gap after the operator as between name and type; on a narrow card, hovering the operator or a long name shows it in full (not while the row is amber; a range shows no symbol; a locked branch adds its reason); on a List parent the operator shrinks to "is not" with its box, the List box's width, and "then [Show the below]" right beside it; display fields take 15% of Band 3; below about a 1390px window the response-field table scrolls sideways while editing, its boxes keeping their size, and scrolling reaches R, ▲ ▼ and X; a locked card's two tables scroll too, as does Band 2's preview once its columns are dragged wider than the card (unlock, drag, Save, lock), their controls still locked, and tabbing through a locked card reaches none of the bands' controls (a scroll box may take focus to scroll); below about a 1330px window Band 1 scrolls sideways (locked too) rather than spilling past its dividers, and a Link 2 rule set to "IS DIFFERENT FROM" fits at any width; on a List parent set to "is not", picking a Quick fill preset keeps "is not" |
| Band 1's buttons keep their size | Unlock an instrument; look at Band 1's rule and unit rows and Band 2's refresh | The "+", AND / OR, THE SAME, operator and X buttons are the size they were before #2659, lined up with their selects |
| Full-size sample rosters | Guide → Sample session → full-size download; upload both files in Quick Setup on a new session | 154 reviewers and reviewees, tag columns Tutor / Group / Team, a Profile column on Reviewees |
| The instrument intro's two columns | As a reviewer, open a session whose instrument has help text on two or more fields, then one with none; narrow the window below 800px. On the Instruments page, lock and unlock the card | On both surfaces the left column is the name card over "Who can see what you wrote", the right every help card in field order, each card its own height; no card moves on resize, typing, Lock or Unlock. With no help text the right half is empty. Below 800px one column: name, visibility, help cards |
| Band 2's name card as the reviewer's | On a one-instrument session set a short label and no description; lock the card; compare with the reviewer's view. Then add a description, Save, Lock; then clear both, Save, Lock | Band 2 reads "Group Peer Review" with no "#1:" and no blank line under it, the reviewer's height; after Save and Lock the new title and description show; with neither, the locked card is not drawn. With two instruments both surfaces read "#2: …" |
| Item 16's small fixes | Open the Band 2 preview and a reviewer table with a Profile and a number column; drag a column to save a width, then open that instrument's reviewer summary and a reviewee's results; open a group-scoped instrument's reviewer table; open Settings at full width and below 800px; click into the App password box; Tab onto a roster's Upload CSV file input | Profile and number columns start at their label's width, not a sliver, on the preview, the reviewer table, the summary and the results, with or without a saved width; the status column is "Status" wide on the group table and once any width is saved; Settings has the SMTP card alone on the left and Date & time over Clear all settings on the right, stacking with a gap when narrow; the password box matches its neighbors; the file input shows the app's focus ring |

**Where this came from.** `guide/archive/segment_19T_advanced_instruments.md` Items 1–4, 6–14, 12A, 16 and 17,
each closed with this check owed. Settling a row is a dated line
there, not a reopening.

## 7. Give scheduled sends a trigger that does not wait for a page view

**Status:** open, **incomplete work awaiting Azure** (author's ruling,
2026-10-01, on `guide/archive/findings_2026-10-01_corpus.md` B19).

**What is wrong.** Scheduled activation, invitations and reminders fire
only when someone opens a session's Session Home:
`scheduled_events.observe_scheduled_events` has one caller,
`app/web/routes_operator/_session_home.py`. `spec/lifecycle.md` §8.3
says the Operations pages and the Sessions lobby run the sweep too, and
the function's own docstring repeats that. Either way, nothing fires
while nobody has the app open, so a reminder scheduled for 09:00 goes
out whenever an operator next looks.

**Why it waits here.** The real fix is a trigger that runs on a clock,
such as a scheduled job, a timer, or an always-on worker. Which one
depends on what the NUS App Service plan and network allow
(`docs/nus_azure_status.md`). Widening the page-view trigger to the
Operations pages and the lobby would still leave the gap, so the author
held it rather than ship a half-step.

**Do, after the cutover.** Choose the trigger the deployment supports
and run `observe_scheduled_events` from it for every session with a
pending anchor. **Pass `build_invite_url`**, built from the deployment's
base URL: without it the invite and reminder triggers return early
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

**Done when** a reviewer who submits on a session with the box ticked
receives the confirmation, and one with it unticked receives nothing.

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
