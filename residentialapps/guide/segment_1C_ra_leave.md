# Segment 1C — Residential Operations: RA Leave

**Opened:** 2026-10-27 · **Theme:** RA Leave's screens, phone first, settled on placeholders to firm up Residential's UX conventions; then wired on the shared core · **Related:** `residentialapps/guide/todo_master.md` (ruling 13), `residentialapps/guide/segment_1B_rosters_and_organization.md` (the core RA Leave is wired on; paused after item 1), `residentialapps/docs/ra_leave_management_functional_spec_v0.4.md`, `residentialapps/spec/applications.md` (page map), `residentialapps/spec/residentialops_ui.md` (the conventions)

## Opportunity

Ruling 13 puts RA Leave first among Residential's three pillars: it is the best understood (a functional spec at v0.4, a page map, mockups for its phone screens), so it is where the conventions every later screen follows get settled. Today RA Leave has no package and no pages. The chrome and components in `residentialapps/web/` were drawn for 1B's desktop-oriented screens; nothing yet tests them on the mobile-critical pages that most of Residential's users will see.

## Decision

**A segment of its own, closing as a whole.** Item 1 builds every RA Leave screen as a placeholder on sample data and records the conventions they settle. Items 2–5 wire them once 1B items 2–5 have built the core (databases, identity, organization, rosters).

| Item | Lands | Waits on |
|---|---|---|
| 1. Screens and conventions | Every page-map RA Leave page as a placeholder, phone first; the UX conventions written down | — |
| 2. Cycles and entitlements | The `leave/` pillar's models and migration; the Leave policy (leave types and their rules, blackouts, appeals, cover, approvals), entitlements worked out from it and adjustments; the admin policy and entitlements pages wired | 1B closed |
| 3. Apply and cover | Applications, validation, cover naming and confirmation; Apply, Request extra leave, My cover, application detail and RA home wired | Item 2 |
| 4. Decisions | First and final approval, Master appeals, withdrawal; the queue, Decide and Decided wired | Item 3 |
| 5. Team and records | Team leave, My history, Leave admin applications; the audit events | Item 4 |

Email (§17) is out of scope: delegated Graph `Mail.Send` is a deployment prerequisite not yet in place (§17.1). Items 3–4 write the outbox rows (§17.2), so sending can be added without reshaping them.

**Rejected: folding RA Leave into 1B.** A different pillar, spec and data; 1B's close would be held to RA Leave's, and the plan would pass its budget.

**Rejected: one segment per stage** (screens alone in 1C, wiring in 1D). Item 1's approval gate keeps screens before services already, as 1B's does; a separate segment would close with nothing wired to record.

## Semantics

- **Item 1's gate:** no wiring item starts until the author approves the screens. Each later item may change a page only as far as real data requires; anything further goes back to the author.
- **Sample data is labeled** on every placeholder and lives in one module, `residentialapps/residentialops/sample_leave.py`, deleted in one place by items 2–5.
- **Placeholders answer only on a local run**, behind 1B's `placeholders_local_only`, until wired.
- **Viewing as.** Placeholders cannot know the viewer's role before identity (1B item 3), so each page renders for one sample viewer named on it (an RA, Chloe Lim; a first approver, Daniel Koh; the admin, Rachel Yeo; the Master, Sam Lee). A labeled switch on the sample banner changes viewer; it is sample-only and goes with the sample module.
- **Phone first:** a mobile-critical page is designed at 390 px and widened; a desktop-oriented one is designed at 1280 px and kept usable on a phone (`residentialapps/spec/applications.md`).
- **Paths and names** follow the page map: `/ra-leave/…` for RAs, `/ra-leave/staff/…` for staff, `/ra-leave/admin/…` for sys admins (author, 2026-10-28); route names prefixed `residentialops_leave_`.

## Judgment calls — decided

- Routes and templates for RA Leave live in `residentialapps/residentialops/` (the application); its models and services arrive in `residentialapps/leave/` (the pillar) from item 2, as `residentialapps/spec/architecture.md` lays out.
- The conventions item 1 settles are written to `residentialapps/spec/residentialops_ui.md`, not into `applications.md`: the page map should stay a map. That file was started early, on 2026-10-27, from 1B item 1's screens (author); item 1 extends it. Support Logs keeps its own UI spec.
- A convention item 1 changes in `residentialapps/web/` is applied to 1B's screens in the same rung, so the two never diverge; it does not reopen 1B.
- Item 1 takes its `diff-reviewer` read on the item's cumulative diff at rung 4, its last build rung; each iteration rung after it takes its own (`CLAUDE.md` "Where work runs").

## Blast radius (measured)

Taken 2026-10-27 at `2cba1322`.

| What | Count | Command |
|---|---|---|
| RA Leave pages in the page map | 12 | `grep -c "/ra-leave/" residentialapps/spec/applications.md` |
| Existing `leave/` package | none | `ls residentialapps/leave` |
| Templates in Residential Operations today | 7 | `find residentialapps/ops/templates -name "*.html" \| wc -l` (the package is `residentialops/` since 2026-10-27) |
| RA Leave spec sections | 36 | `grep -c "^# [0-9]" residentialapps/docs/ra_leave_management_functional_spec_v0.4.md` |

The mockups (the author's design canvas, 2026-10-26) cover RA home, Apply, Request extra leave, application detail, My cover, Awaiting my decision, Decide and not registered; Decided, My history, Precinct leave and the five Leave admin pages are drawn first in item 1.

## Status

- **Ladder reordered, 2026-10-28** (author): the admin pages (rung 4) are built first, the rest of RA Leave being downstream of their configuration; rungs 1–3 follow in order. Rung 4 lands first; the cumulative read moves to the item's last build rung.
- **RA pages, 2026-10-28** (author: "RA pages next"): rung 2 lands with rung 1's RA home; the landing at `/` and the viewer switch wait for rung 1's remainder. The sample viewer is Chloe Lim; two applications were added naming her as cover.
- **Landing, 2026-10-29** (author): rung 1's landing at `/`, with its own sample viewer switch (`?as=`: Chloe Lim, Daniel Koh, Rachel Yeo, Sam Lee); RA Leave opens on the viewer's own side. The RA pages' viewer stays fixed to Chloe Lim.
- **Appeals by invitation, 2026-10-29** (author): appeals are open, by invitation or off; by invitation adds the admin Appeals page, and a staff Appeals tab for whoever the policy lets open appeals (chosen as approvers are: slot appointments, Unit appointments or named staff; same day).
- **Staff pages, 2026-10-29** (author: "yes" to the staff pages next): rung 3, with a sample viewer switch on the staff pages (`?as=`: Daniel Koh, Rachel Yeo, Sam Lee), the part of rung 1's switch they need.
- **Iteration, 2026-10-28** (author): Leave policy reworked to the leave policy ruling (`residentialapps/guide/todo_master.md`): leave types with their own earning rule and cap, blackouts by week, appeals and their terms, cover required, named or confirmed. Entitlements follow the rules; its CSV carries adjustments only.

## PR ladder

**Item 1 — Screens and conventions.** Record the base SHA in rung 1's PR body.

1. **Landing and the phone shell.** ~~The Residential Operations home at `/` for an RA … and for an approver~~ (revised 2026-10-28) The landing at `/`, choosing an application; the RA home at `/ra-leave/` (balance, cover asked of you, my applications); the card columns that stack on a phone, the three audiences' tabs, the sample viewer switch; RA Leave live in the switcher.
2. **RA pages.** Apply, Request extra leave, application detail (status timeline, withdraw), My cover, My history.
3. **Staff pages** (`/ra-leave/staff/`). Staff home, Awaiting my decision, Decide (first approval, final approval and a Master appeal), Decided, ~~Team leave~~ Precinct leave with its this-week summary; Appeals for those who may open them (added 2026-10-29).
4. **Leave admin and conventions** (`/ra-leave/admin/`). ~~Cycles and entitlements, applications~~ Leave dashboard, Leave policy, Entitlements, Approval chain, Applications, Appeals (added 2026-10-29); `residentialapps/spec/residentialops_ui.md` extended from rungs 1–4. Last build rung: cumulative read.
5+. Iteration until approved, each with its own read.

**Items 2–5** get their rungs when 1B closes, from what the core turned out to be.

## Definition of done

- The author approved item 1's screens; no RA Leave page shows sample data at close.
- `residentialapps/spec/residentialops_ui.md` states the conventions the screens use, and 1B's screens follow them.
- An RA applies, a covering RA confirms, the first and final approvers decide, and the balance moves, end to end in tests (items 3–4).
- An extra-leave appeal reaches the Master and is decided, with leave charged to normal entitlement and extra leave kept apart (§7.5).
- Every RA Leave action writes an audit event and, where §12 or §17 says, an outbox row.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 1C` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **Leave types and the day count** (§6, §9.1): the leave types are ruled (Leave policy, 2026-10-28; item 1 draws personal and official leave); whether weekends and public holidays count is a Leave policy setting (author, 2026-10-29), every day by default.
- **The close check:** `tools/close_check.py` does not yet find Residential's plans (`residentialapps/guide/todo_master.md`, its stub). Due before 1B or 1C closes, whichever is first.

## Out of scope

- Sending email (§17): waits on its deployment prerequisite (above); the outbox is in scope.
- Teams notifications (§17.3) and RA Events: RA Events is third in ruling 13.
- Support Logs: second in ruling 13.

## Doc impact

- `residentialapps/spec/applications.md` — the RA Leave pages move from contract to built, with any path or name the screens settle (Item 1).
- `residentialapps/spec/residentialops_ui.md` — extended with the conventions RA Leave's screens settle (Item 1).
- `residentialapps/spec/architecture.md` — `residentialapps/leave/` arrives, with its import boundary and its share of the `residentialops` database (Item 2).
- `residentialapps/docs/ra_leave_management_functional_spec_v0.4.md` — revised to what shipped, including §2.5's mobile-critical approvers, already queued (at close).
- `residentialapps/guide/todo_master.md` — the entries this segment finishes, deleted at close.
