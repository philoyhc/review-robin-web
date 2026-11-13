# Segment AD1F — Apply Desk: Gates and Panels

**Opened:** 2026-11-13 · **Theme:** Form's *Select people* and each gate picking or making a panel (ruling 19); the Gates page rebuilt as Process and Form are, gate cards beside an Outline; then Panels as its own Setup tab, its format the author's to choose; every move working in the browser, nothing saved · **Related:** `applydesk/guide/todo_master.md` (rulings 4, 14, 19), `applydesk/guide/archive/segment_AD1E_process.md` (the page shape this repeats), `applydesk/spec/applications.md` ("The Form page", "The Process page")

## Opportunity

Gates is AD1D's placeholder: one plain card per gate, with Gate 1 showing every assessment panel and the rest *No roster yet*, and the reviewer pool and interviewers hanging off the foot. Ruling 14 folded Panels into Gates, but the rosters serve two pages: a *Select people* question on Form chooses from one (the reviewer pool), and each gate is evaluated by one. The author (2026-11-13): after the rosters are set up, "there might be occasion to make smaller adjustments. For that purpose, an RRW roster page style table is a much better affordance", and several tables on Gates "over stuffs the page". Hence ruling 19.

## Decision

**Panels is a Setup tab after Gates; Form and Gates pick a panel and may make one in place** (ruling 19):

1. **The Setup row** reads *Process · Form · Gates · Panels · Emails*. Panels comes before Emails because Emails depends on what Process ticks, not on who is on a panel.
2. **Form's *Select people* card** (first, author: "start by modifying the Select people card on Form"): *Chosen from* lists *Institution-wide* then each panel by name, then *+ New panel…*. That choice opens a box under the row: *Panel name*, *Members* (pasted emails or `Name <email>`, one per line or comma-separated), *Create panel* and *Cancel*. A created panel joins every *Chosen from* menu on the page and Preview's lookup, and is selected. Beside the menu, *Edit on Panels →* links to the chosen panel (hidden for *Institution-wide*), once Panels is built (rung 4).
3. **Gates** takes Process's and Form's arrangement (author): a gate card per gate, in timeline order, on the left; the Outline card on the right, kept in view. A gate card collapses to *Gate N · its name*, its stage, and chips for its state and its panel (*Panel A · 2 people*, or *No panel*). Open, it shows how it runs and its result (set on Process, linked), what the panel sees, and **Evaluators**: the same panel menu and *+ New panel…* box as Form's, *Edit on Panels →*, and the panel's members. A gate already sent says it keeps the roster it was sent with. Gates are not added, moved or deleted here: Process owns the timeline.
4. **Panels**, built last (author, 2026-11-13: "Don't do the Panels page. Do the others first"), its format open between two (Open questions). One: the same arrangement, a collapsible card per panel holding its roster as a table (author: "collapsible cards holding the tables"), in Review Robin's roster-page style: *Name*, *Email*, *Note* (a role or an area) and a row's *Remove*; *+ Add person*; *Import CSV* and *Export CSV*; each row checked as typed (an email's shape, a duplicate in the panel). The card's head: its name, *Used by* (*Form: Preferred reviewer · Gate 1: Peer Review*) or *Not used yet*, and a count. The card's foot: *Copy panel*, *+ Panel*, *Retire* (disabled, with its reason, while anything uses it). The Outline lists each panel, its count and its uses, and names problems (a panel in use with nobody on it, an invalid or duplicate email). The other (author, 2026-11-13): **everyone in one table, a column per panel** marking who sits on which. Whichever is chosen keeps *Used by*, the checks, CSV, *Copy panel* and retiring only when unused.
5. **The model**: `sample_data.Panel` (a key, a name, members) replaces the three separate rosters; a gate names its panel (`stages.Gate.panel`); a *Select people* question names one in `pool`. *Used by* is worked out from both.

**Rejected:**
- **Panels folded into Gates** (ruling 14): several tables under the gate definitions over-stuff the page, and a roster serves Form too.
- **Panels only on their own page, picked by name elsewhere**: the operator would set up Panels before Form and Gates, going backwards through Setup; the quick create keeps it forward.
- **Panels before Gates in the row**: a panel is needed by what Form and Gates set up; it is fleshed out after them.

## Semantics

- **A panel's key**, not its name, is what a question or gate holds; renaming a panel renames it everywhere on the page.
- **Members**: an email is required and unique within a panel (case-insensitive); a name is optional (shown as the email). A pasted list or a CSV adds only the rows whose email is new, and says what it skipped and why. *+ New panel*'s box is stricter (2026-11-13): it makes nothing until every entry is an email listed once, naming those that are not, since nothing it makes can be edited until Panels.
- **CSV**: header `Name,Email,Note` (any order, case-insensitive; *Email* required); export writes the table as shown.
- **Retire** only when nothing uses it. **Copy panel** makes *Copy of …*, unused, with the same members.
- **A gate already sent** (`workflow.gate_state`: *Sent*, *Results in*) keeps its roster: its panel's card says so, as does the gate's.
- **A panel made on Form or Gates** exists on that page only, as everything else here: nothing is saved until AD2, and a reload restores the sample.

## Judgment calls — decided

- **Gate cards neither move nor are added here**: the timeline is Process's; Gates links to it.
- **Who reviews which application** (ruling 9's per-assessor list) is not a panel's: it comes with Review Robin's assignments (AD5, AD6), so Gates drops AD1D's *Asked to review* column.

## Blast radius (measured)

Taken 2026-11-13 at `fb6785690`.

| What | Count | Command |
|---|---|---|
| The Gates partial replaced | 89 lines | `wc -l applydesk/templates/applydesk/operator/_gates.html` |
| Files reading the three rosters | 7 | `grep -rln "people_pools\|pool_label\|assessors_of\|pool_of\|interviewers_of" applydesk --include=*.py --include=*.html` |
| Test lines naming gates, pools or panels | 21, 14, 6 | `grep -c "gates\|pool\|panel" applydesk/tests/test_pages.py applydesk/tests/test_form.py applydesk/tests/test_form_browser.py` |

## Status

- **Rungs 1–3 built** (#3875 plan, #3876 Form's picker, rung 3 Gates). The Panels page waits for the author's choice of format (Open questions); Form and Gates came first at the author's word.
- **The draft exercise gained a selection gate with no panel** (rung 3): every other sample gate is sent, so its menu is fixed, and Gates had nothing to pick on.
- **Reads: one**, cumulative on rungs 2–3 (base `8b4fa6484`, main after the plan): one defect, the picker restoring a stale panel after Form's type change, also found by Codex on #3876 and fixed there; on Gates, a link to Process on the card and assessment-panel membership kept once (in `PANELS`). The quick create refusing a repeated email, where a table would skip it, is recorded in Semantics. Rung 4 takes its own read.

## PR ladder

1. **Plan** (this file), ruling 19, the roadmap row, the README row.
2. **The panels model and Form's picker.** `Panel` and its sample panels; a gate names its panel; Form's *Chosen from* listing panels with *+ New panel…*, the quick create working in the browser. Chromium tests for the quick create. Must not touch Gates' page or add the Panels tab.
3. **Gates as gate cards.** The cards and Outline from the sample, collapsing; the panel menu and *+ New panel…* box (shared with Form's); the Outline following the panel chosen. Chromium tests. Last build rung before the Panels ruling: `diff-reviewer` reads the cumulative diff.
4. **Panels**, once its format is chosen: the tab and its page (scaffold, then wired, as the ruling sizes it), *Edit on Panels →* on Form and Gates. It takes its own read.
5. **Iteration rungs**, as the author's browser checks ask.
6. **Close**, only after the author's browser check.

## Definition of done

- The Setup row reads Process, Form, Gates, Panels, Emails (test).
- Gates shows each gate as a card in timeline order with its panel, and the Outline (test).
- Panels shows each panel as a card with its roster table and *Used by* (test).
- In Chromium: a panel made on Form and on Gates and chosen; a row added, edited, removed and refused (bad or duplicate email); a CSV imported and exported; a panel copied, and retired only when unused (tests).
- The author has used the pages locally and approved them.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1F` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **The Panels page's format** (the author's): a card per panel holding its table, or everyone in one table with a column per panel (Decision 4).
- **A panel shared across exercises** (an institution's standing pool): the author's, when AD5 stores panels.
- **`close_check.py` reads only RRW's `guide/`**: this close is checked by hand, as AD1E's was.

## Out of scope

- **Saving** (AD2); **sending** a gate to Review Robin and the per-assessor assignments (AD5, AD6).
- **Searching the institution's directory** for a member (Graph, with AD4's *Institution-wide*).

## Doc impact

- `applydesk/spec/applications.md` — the Setup row with Panels; *Chosen from* naming panels and *+ New panel…* in "The Form page"; "The Gates page" and "The Panels page" sections, after "The Process page" (at close).
- `applydesk/spec/architecture.md` — `sample_data.py`'s row: panels in place of the three rosters (rung 2).
- `applydesk/guide/todo_master.md` — ruling 19 and the AD1F roadmap row (rung 1); the row deleted at close.
- `applydesk/README.md` — this plan's row (rung 1), moved to the archive's index at close.
