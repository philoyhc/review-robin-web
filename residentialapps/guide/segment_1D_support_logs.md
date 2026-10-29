# Segment 1D — Support Logs

**Opened:** 2026-10-29 · **Theme:** Support Logs' screens on placeholders, phone first for the frontline, as RA Leave's were; then wired on the shared core · **Related:** `residentialapps/guide/todo_master.md` (rulings 1–14), `residentialapps/docs/residentialapps_roles.md` (holds over the functional spec until its next version), `residentialapps/guide/segment_1B_rosters_and_organization.md` (the core Support Logs reads), `residentialapps/guide/segment_1C_ra_leave.md` (the pattern this follows), `residentialapps/docs/resident_support_log_functional_spec_v0.3.md` (the functional spec, cited as §), `residentialapps/docs/support_logs_ui_spec_v0.1.md` (the draft UI spec, cited as UI §), `residentialapps/spec/applications.md` (page map)

## Opportunity

Support Logs has a factory and a health route at `/supportlogs` and nothing else: no pages, no templates, no sample data. It has a functional spec at v0.3 and a draft UI spec with nine phone screens, six of them mocked up on a design canvas (UI §2), but the two disagree with the page map on its navigation: the UI spec has a bottom bar of Home, Log, Students and Follow-ups, the page map four areas (`/encounters/`, `/plans/`, `/dashboard/`, `/sys-admin/`). Neither has been tried as real pages, and the surfaces beyond the frontline (oversight, opportunity review, audit, administration) are drawn nowhere. RA Leave showed that placeholder screens settle these questions faster than prose.

## Decision

**Screens now, wiring after the core** (author, 2026-10-29: "we might as well complete the screens for supportlogs too"). Ruling 13's order stays for the wiring; item 1 is pulled forward, as 1C's was.

| Item | Lands | Waits on |
|---|---|---|
| 1. Screens and conventions | Every Support Logs page as a placeholder on sample data, the frontline phone first; the UI spec settled and written to `residentialapps/spec/` | — |
| 2. Authorizations and configuration | The `supportlogs` models and first migration; authorization types over the Staff roster (§3.5), configured lists (§5.5–5.10), clusters (§10.5); Sys admin wired | 1B closed |
| 3. Encounters and safety | Encounter logging, students and the local working set (§4), informal follow-up (§6), safety flags (§5.10); the frontline pages wired | Item 2 |
| 4. Plans and sharing | Formal assignments and conversion (§7, §8), peer-view grants (§11.1), the student view and full history (§9) | Item 3 |
| 5. Oversight and review | The senior dashboard (§10.2–10.6), consultation check (§10.7–10.8), the support-activity audit (§11.3) | Item 4 |

Email and Teams are out of scope: v1 reminds in-app only (§17).

**Rejected: wait for the core, then plan screens and wiring together.** The UI questions below are independent of the data, and settling them now lets 1B's wiring serve both applications' screens at once.

**Rejected: Support Logs' screens inside Residential Operations' chrome.** UI §1 item 6 and the one-accent rule (UI §6) set Support Logs apart: its own name, navigation and teal accent.

**What already overrides the two Support Logs specs** (a scan of `residentialapps/`, 2026-10-29), so the screens follow it, not the specs:
- **Authorizations** (`residentialapps/docs/residentialapps_roles.md`): every Staff-roster member is eligible for every type, with no qualifying appointment (rule 9; §3.5 still says otherwise); Support Logs sys admin is granted by the super-admin only (rule 1), who administers and sees no content (§3.4); a sixth type, **Other Staff view**, aggregate or identifiable, read-only (rule 8); no self-action, a last-sys-admin floor (rule 6).
- **Pages** (`residentialapps/spec/applications.md`): four areas, Encounter log, Plans, Dashboard and Sys admin; **Plans** are check-in plans, assigned (often by Counselling, a formal assignment, §7) or self-set (§10.1); the home at the bare mount lists what the viewer reaches or redirects; the not-registered page in its fixed wording (`residentialapps/docs/residentialapps_identity.md` §6); a `403` page for a linked viewer who reaches nothing.
- **No neutral screens** (ruling 3): the UI spec's sign-in landing and switcher are dropped (UI §6, §9 Q5).
- **Chrome: RA Leave's RA layout, no bottom bar** (author, 2026-10-29; `residentialapps/spec/residentialops_ui.md` §2, 2026-10-26): the slim top bar with the switcher, page tabs under it, phone lists (`ul.items`), the main action a full-width Primary on the page, and a form's Save at the form's end, as Apply's is, not in a fixed footer; the UI spec's bottom bar and fixed footer go. The favicon is already Support Logs' notepad on teal.
- **Inherited from 1B and 1C:** placeholders local only, the sample viewer card, disabled not hidden, 44 px touch targets, kept sorts with None last, column chips, person tokens, derived pills, `url()`, gated steps.

## Semantics

- **Item 1's gate:** no wiring item starts until the author approves the screens; later items change a page only as far as real data requires.
- **Sample data is labeled** and lives in one module, `residentialapps/supportlogs/sample_support.py`, deleted in one place by items 2–5. Its staff are the Staff roster's mock people (`residentialapps/docs/sample_data/`), copied, not imported: `supportlogs` may not import `residentialops` (`residentialapps/spec/architecture.md`, "Import boundaries"); a test holds the copy to the mock.
- **No real-looking support content.** Sample students are invented, notes bland and short (§5.8), safety flags generic; nothing reads as a real case.
- **Placeholders answer only on a local run**, as 1B's and 1C's do, until wired.
- **Viewing as.** One sample viewer per authorization type (§3.5, roles rule 8): a frontline RF, a frontline recipient, a senior identifiable Master, a safety-flag recipient without frontline access, a consultation checker, Other Staff with aggregate view and with identifiable view, someone reaching two pages (so Home lists them), a Support Logs sys admin, the super-admin (administration only), and someone with no authorization (the `403` page); switched by a labeled sample card (`?as=`), sample-only, independent of the local fake-auth user.
- **Access is managed in Support Logs alone** (author, 2026-10-29): Sys admin's **Access** page (`/sys-admin/`) lists every active Staff-roster member, read from `residentialops` as the eligibility list, and grants each of them the authorization types, kept in `supportlogs`; the roster shows no access and Support Logs never writes to it (roles rule 9).
  - One row per person: name and appointment (read-only, a derived pill), then a column per type — Frontline, Senior identifiable, Safety-flag recipient, Consultation check, Other Staff view (None, Aggregate or Identifiable), Sys admin — each a Toggle, with a filter box and chips for With access and No access.
  - A grant or revocation asks for a reason, a senior grant whose request it answers (the Master's, §3.5), and is audited (§11.3).
  - **Lapsed grants** head the page: a grant whose holder no longer has an active Staff-roster entry (retired, or no appointment on it current) stops at once and is listed until a sys admin revokes it (§3.5); which appointment they hold never matters (roles rule 9).
  - The Sys admin column is the super-admin's alone; a sys admin sees it read-only. No self-action, and the last Support Logs sys admin cannot be revoked (roles rules 1, 6). The super-admin holds administration from the platform, named in a note, never a row.
- **Names and tabs** (author, 2026-10-29):
  - **Consultation check**, not *opportunity review*: a list of students in, and whom to consult out, for any approved purpose (§10.7, §17 Q12). Its states are *No consultation indicated*, *Consultation suggested* and *Consultation required*; the first never means a student is well or suitable.
  - **No Safety flags tab**: flags are listed on Home for the frontline and on Overview for recipients, each opening its detail page; a recipient with neither frontline nor senior access lands on a Home holding only the flags.
  - **Senior staff get an Overview tab**, beside the tabs their other grants give them, for workload, hotspots, clusters, coverage, every plan and the flags; not a separate set of pages.
- **Scope is the grant, not the slot.** A frontline user sees what §11.1 gives them; nothing is derived from who oversees whom in Assignments, which covers RAs only (`residentialapps/guide/todo_master.md`, 2026-10-29), without a ruling.
- **Reads are actions** (§11.3): every placeholder that shows a named student says the view is recorded, as the real page will.
- **Configured lists are never hard-coded in templates** (UI §3, "Configured lists"): the sample module holds the seeded defaults and the pages render from it.

## Judgment calls — decided

- What both applications' pages need goes to `residentialapps/web/` in rung 1, since neither application may import the other: `placeholders_local_only`, the person and table macros, and a sample title and viewer card (`_sample.html`). Each application keeps its own render helper (its areas and tabs differ); Residential Operations' hand-rolled viewer cards adopt the shared one when next touched (rung 1, 2026-10-29).
- The settled conventions go to a new `residentialapps/spec/supportlogs_ui.md`, citing `residentialapps/spec/residentialops_ui.md` for what is shared (devices, the base styles, sort and chips) rather than restating it; the draft UI spec is retired to `docs/` history at the close.
- Item 1 takes its `diff-reviewer` read once per code PR, as 1C's did from rung 4 (`CLAUDE.md` "Where work runs").

## Blast radius (measured)

Taken 2026-10-29 at `de0bf729`.

| What | Count | Command |
|---|---|---|
| Support Logs files today | 3 (`__init__`, `main`, `routes_health`) | `ls residentialapps/supportlogs/*.py` |
| Screens in the draft UI spec | 9, six mocked up | `sed -n 26,36p residentialapps/docs/support_logs_ui_spec_v0.1.md \| grep -c "^\| [0-9]"` |
| Areas in the page map | 4 | `residentialapps/spec/applications.md`, "Support Logs" table |
| Functional spec sections | 86 | `grep -c "^## \|^### " residentialapps/docs/resident_support_log_functional_spec_v0.3.md` |
| Residential Operations templates, for scale | 34 | `find residentialapps/residentialops/templates -name "*.html" \| wc -l` |
| Authorization types | 6 (§3.5's five, Other Staff view), plus the super-admin | `residentialapps/docs/residentialapps_roles.md` rules 1, 8 |
| Shared macros to move to `web/` | 2 (`_people.html`, `_tables.html`) | `find residentialapps/residentialops/templates -maxdepth 2 -name "_*.html"` |

## Status

- **Rung 1, 2026-10-29** (author: "start rung 1"): the shared pieces in `residentialapps/web/` (`pages.py`, `_people.html`, `_tables.html`, the new `_sample.html`); the teal accent; Home, the `403` and not-registered pages, and the other pages as placeholders, at the paths in `residentialapps/spec/applications.md`, tabs by grant. Base SHA for the item's read: `d15502e0`.
- **Rung 2, 2026-10-29** (author: "start rung 2"): the frontline pages on sample data — the dashboard, Log encounter with its details on the page and the confirmation after saving, Students, the student view (`/students/{id}`) and My plans; flags and sharing stay placeholders for rungs 3 and 4. Built on open question 3's proposals, for the author to confirm: choice chips as native radios and checkboxes styled as pills, and status chips in sentence case with words ("Overdue 2 days"); Mark a safety concern is outline red until rung 3 settles its role. "This week" (UI spec screen 6) is read as the next seven days, so a Monday due date shows on a Thursday; the cold read asked for it to be recorded.
- **Rung 3, 2026-10-29** (author: "start rung 3"): Safety concern (`/log/safety`, reached from Log encounter with what is chosen so far) and its confirmation, a flag's detail (`/flags/{id}`), and the flags on Home (a raiser's own; a recipient's all, with closed ones for a recipient with nothing else) and Overview (senior recipients), the unacknowledged count on that tab. UI spec §9 Q1–Q2 built with existing roles, for the author to confirm: Mark a safety concern Destructive (outline red), Save and raise safety flag Primary on a screen framed in the safety color. Crisis contacts and steps are placeholders (§17 Q7).
- **Rung 4, 2026-10-29** (author: "start rung 4"): a plan's detail (`/plans/{id}`) with its history, its owner's cadence, senior staff's conversion of a follow-up and status, Other Staff identifiable view read-only; Flag for formal assignment (no reason asked, a suggested cadence); Share with a colleague, grants listed with Revoke, records shared with the viewer labelled by their owner; Overview lists every plan for identifiable viewers and the flagged students for senior staff, ahead of rung 5. Peer-view scope built as the grantor's records for one student, encounters and plans, read-only (§17 Q10, open); senior staff make no grants on others' behalf (§17 Q11, open).
- **Rung 5, 2026-10-29** (author: "start rung 5"): the Overview on sample data — team workload with load weighted by cadence (§10.3), coverage, hotspots (14 days against the 14 before; Rising, never a score), clusters; a senior's student history across staff (`/overview/students/{id}`) and the support-activity audit (`/overview/audit`), each marked as an audited read, recorded once item 4 wires the audit. Other Staff aggregate view sees counts only, no student named; whether small counts (a cluster or a colleague with one student) must also be suppressed is for the author to rule, as the spec is silent. Clusters are shown as the assignments file's Precincts until the author rules what a cluster is, and §10.5's trend over time waits on real data (§10.5).
- **Rung 6, 2026-10-29** (author: "rung 6"): lands as three PRs, the Consultation check, Sys admin, then `residentialapps/spec/supportlogs_ui.md`. **6a, Consultation check** (`/consultation/`, `…/check`): a purpose and a pasted list in; each student's state from named reasons (§10.8: an unresolved safety escalation or safety-plan support requires consultation; a formal assignment, a follow-up, a marked increase or several staff suggest it), the strongest first, and whom to consult; no notes, no score, and the meaning of *No consultation indicated* stated on the result. A formal assignment is read as suggesting, not requiring, until thresholds are set (§17). Whom to consult adds whoever raised an active flag; an entry with no address is listed as not read, never as a state; the viewer sees only their own past checks (§11.3 keeps everyone's runs for senior staff). Consultation requested or done is a disabled select per positive row. The sample sends the list in the query string; wired, it is posted.
  **6b, Sys admin** (`/sys-admin/`, `…/configuration`, `…/clusters`, `…/audit`): Access lists the Staff roster's active members once each, lapsed grants first, a column per type with Other Staff view's scope as a select, the viewer's own row marked; Sys admin read-only to a sys admin; the super-admin a note, never a row. Configuration renders every seeded list from the sample module, the note limit and the consultation rules; Clusters the list's names only; the audit administrative events only. No page shows support content. Each per-row grant is a native checkbox, as Residential Operations' per-row flags are, for the author to confirm against the plan's Toggle; the Sys admin column and the viewer's own row are marked in the markup for item 2. Clusters' Add, Rename and Retire presume clusters are Support Logs' own list, one answer to open question 2. Support Logs' last placeholder goes with it.
  **6c, the UI spec**: `residentialapps/spec/supportlogs_ui.md` written from rungs 1–6; the draft UI spec carries a banner pointing to it, and `residentialapps/spec/residentialops_ui.md` points there for Support Logs' chrome. Rung 6 is item 1's last build rung; rung 7+ iterates on the author's review.

## PR ladder

**Item 1 — Screens and conventions.** Record the base SHA in rung 1's PR body.

1. **Chrome and home.** The shared pieces moved to `residentialapps/web/`; the teal accent under `data-app="supportlogs"`; Support Logs' switcher and tabs (open question 1); the home at the bare mount, listing what the viewer reaches or redirecting; the `403` page; the sample module and the viewer card. Every other page a static placeholder.
2. **Frontline, phone first.** Log encounter with its optional details and the after-save confirmation; Students; the student view; My follow-ups; the personal dashboard (UI screens 1–3, 5–7; §4–§6, §9, §10.1).
3. **Safety.** Safety concern; safety flag detail; the active and closed flags listed on Home for the frontline and on Overview for recipients, not a tab of their own, with the unacknowledged count in the navigation (UI screens 4, 8, 9; §5.10).
4. **Plans and sharing.** Formal assignments with source, cadence and the safety-plan marker; conversion from a follow-up (§7, §8); Flag for formal assignment; peer-view grants (§11.1).
5. **Overview.** Senior staff's Overview tab: workload with load weighting, hotspots, clusters, due coverage (§10.2–10.6); senior student history; the support-activity audit (§11.3).
6. **Consultation check and Sys admin.** A check run, its three states and reasons, the consultation record (§10.7–10.8); Sys admin: Access (above, Semantics), configured lists, the cluster list, the administrative audit (§3.3). `residentialapps/spec/supportlogs_ui.md` written from rungs 1–6.
7+. Iteration until approved, each with its own read.

**Items 2–5** get their rungs when 1B closes.

## Definition of done

- The author approved item 1's screens; no Support Logs page shows sample data at close.
- `residentialapps/spec/supportlogs_ui.md` states the conventions the screens use; the draft UI spec's open questions are each answered there or carried to the plan.
- A frontline user logs a routine encounter in one screen and a safety flag reaches a recipient who acknowledges and closes it, end to end in tests (item 3).
- Every identifiable read and every change writes a `supportlogs` audit event, split administrative from support activity (§11.3; items 2–5).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 1D` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

1. **Navigation** — answered: RA Leave's RA layout, no bottom bar (author, 2026-10-29; Decision). The frontline's tabs are the UI spec's four destinations, Home, Log, Students and Plans (My follow-ups); senior, review and admin viewers get their own tab sets, as RA Leave's staff and admin sides do. Paths are settled in rung 1 against the page map's areas, the page map revised to match.
2. **Clusters** (§10.5): the core's Wings or Precincts, or a list of Support Logs' own (`residentialapps/docs/residentialapps_roster_structure.md` avoids the word for this reason). Proposed: the sample shows Precincts, labeled as clusters, until ruled.
3. **UI §9's questions** (author, at the rung that first needs each): the Safety button role and the filled red Save and raise (rung 3); choice chips as styled radios and checkboxes (rung 2); sentence-case status labels (rung 2); Residential's customizer (out of item 1, below).
4. **The crisis protocol** (§17 Q7) is placeholder text and numbers until the institution supplies it; the screen shows that it is.
5. **The close check:** `tools/close_check.py` does not yet find Residential's plans (`residentialapps/guide/todo_master.md`, its stub). Due before 1B, 1C or 1D closes.

## Out of scope

- The §17 policy questions (retention, who holds which authorization, signal thresholds): decided before Support Logs goes live (`residentialapps/guide/todo_master.md`), not before its screens.
- Residential's customizer and contrast audit page (UI §9 Q6): its own slice, after the screens.
- Email and Teams reminders: in-app only in v1 (§15, §17).
- RA Events: third in ruling 13.

## Doc impact

- `residentialapps/spec/supportlogs_ui.md` — new: the conventions Support Logs' screens settle, from the draft UI spec (Item 1).
- `residentialapps/spec/applications.md` — the Support Logs page map, with any path the screens settle, from contract to built (Item 1).
- `residentialapps/spec/residentialops_ui.md` — its pointer to Support Logs' UI spec, and the shared pieces moved to `residentialapps/web/` (Item 1).
- `residentialapps/spec/architecture.md` — what `residentialapps/web/` holds for both applications (Item 1); the `supportlogs` models and their database (Item 2).
- `residentialapps/docs/support_logs_ui_spec_v0.1.md` — a banner pointing to the settled spec (Item 1).
- `residentialapps/docs/resident_support_log_functional_spec_v0.3.md` — revised to what shipped, with the revisions already queued (at close).
- `residentialapps/docs/residentialapps_roster_structure.md` — §6's "effective system roles" indicators, stale against roles rule 9 (Item 1).
- `residentialapps/guide/todo_master.md` — ruling 14 now; the entries this segment finishes, deleted at close.
