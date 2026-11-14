# Segment AD1F — Apply Desk: Gates and Panels

**Opened:** 2026-11-13 · **Theme:** Form's *Select people* and each gate picking or making a panel (ruling 19); Gates folded into Process, whose items collapse, and Panels in its slot as one table with a column per panel (ruling 20); every move working in the browser, nothing saved · **Related:** `applydesk/guide/todo_master.md` (rulings 4, 14, 19), `applydesk/guide/archive/segment_AD1E_process.md` (the page shape this repeats), `applydesk/spec/applications.md` ("The Form page", "The Process page")

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

## Decision — amended (ruling 20, 2026-11-13)

After the author's browser check of rungs 2–3: **Gates folds into Process, and Panels takes its slot.** Decisions 1, 3 and 4 above are superseded as follows; 2 and 5 stand.

1. **The Setup row** reads *Process · Form · Panels · Emails*.
2. **Process's items collapse** (author: "make the sub cards (Form, Gate, Outcome) inside each Stage card collapsible too"). An item's head always shows its kicker and name, and chips: a gate's state and panel (*Panel A · 2 people*, or *No panel*); an outcome's release and the emails it owes; the form's state and emails. An open stage shows its items collapsed; an item alone in its stage, or just added, opens.
3. **A gate item gains *Evaluators*** (author: "Process > Gate cards will need the same Evaluators menu with + New panel box"): the shared menu and box, the panel's members, *Panel sees* and its progress; a sent gate's menu is fixed. The Outline names each gate's panel and lists *Gate N has no panel* among its problems. The Gates page and tab retire in the same rung, so a panel is set in one place throughout.
4. **Panels is one table, a column per panel** (author: "one table, one column per panel, with a floating control card to the right"): a row per person (*Name*, *Email*, *Note*), a column per panel ticking who sits on it, its header naming the panel with its count and *Used by*. The control card floats on the right, kept in view: *+ Add person*, *+ Panel*, *Import CSV*, *Export CSV*, the panels with *Copy* and *Retire* (only when unused), the problems, *Save*. *(Layout superseded by rung 6b, 2026-11-14: no floating card; Used by moves to Manage panels and the column's tooltip.)*

**Rejected:** keeping a Gates page beside Process. It set a gate's panel on a second page, away from the gate's other settings, for a view the Outline gives.

## Decision — results (ruling 21, 2026-11-14)

After the author's browser check of ruling 20's rungs: a gate's single *Result* box becomes **up to three results**, each a name, the **response field** each evaluator fills in, and a **derivation**. The derivation sets the result's type (author: "the derivation rule determines the data type of the result so there's no need to a separate definition"):

| Field | Derivations | Result |
|---|---|---|
| Integer, Decimal | mean, median | Decimal, the field's bounds |
| | min, max | the field's type and bounds |
| | sum | the field's type, n × its bounds |
| | count of responses | Integer, from 0 |
| List | share choosing a value | Decimal, 0 to 100 (%) |
| | most common | List, the field's options |
| String | all, joined | String, for reading |
| any (*Entered here*) | entered by hand or a CSV column | the field as defined |

*Amended 2026-11-14 (author): count of responses is any field's, List and String too.*

A result needs a minimum number of responses (default 1), else it has none yet. A List is never mapped to numbers (author: a numeric scale is a numeric field, its help text saying what the numbers mean). On the gate item, results are rows that read as Form's card summaries and edit in place, not a third level of collapsing card; under them, *For Review Robin* lists the fields the session's instrument must ask. Result 1 is the gate's headline. Outcome rules and weights read a gate's named result: numbers are compared and weighed, a list matched, a string read only.

**Rejected:** a second, result-level definition beside the field (the derivation already fixes it); mapping list options to numbers (author).

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

**Closed 2026-11-14**, after the author's browser checks. Intended: Panels as its own tab after Gates, Form and Gates picking a panel (rulings 19). Done: Gates folded into Process and Panels in its slot as one table (ruling 20, after the check of rungs 2–3); a gate's results (ruling 21); Panels rebuilt as Review Robin's roster page and people found in the directory (ruling 22, rungs 6a–6d); each page keeping edits by its shape (ruling 23, rungs 7a–7g). The ladder below records each rung as built.

- **Reads: eleven.** Cumulative on 2–3, 4b–4c, 4d–4e and 5b–5d; one each on 6a–6d and 7a–7g. Defects found and fixed in their PRs, chiefly: a stale panel restored after Form's type change; a replicated stage copying its gates' sent lock and its outcome's release; a removed result's key reused, re-binding a rule; the Applications lock bypassed by Propose, Apply and CSV; an unsaved row copied into a panel (Codex); a refused rename's name taken by another (Codex); retiring an unsaved panel leaving its rows.
- **Ruled at build:** *count* is any field's; a string result is read only; *sum* gives n × the field's bounds; a sent gate keeps its roster; Manage panels' names, added panels and retires wait for its *Save* (rungs 7e–7g, superseding 7d's ✓).
- **Scope that moved:** the draft exercise gained a gate with no panel (rung 3); the spec gained short Applications and Emails sections, as ruling 23 states each page's own way of keeping an edit; *Show columns* is not remembered across a reload until AD2.
- **Latent, for AD2:** a list headline (Result 1) has no value on Applications, whose cells carry a number.

## PR ladder

1. **Plan** (this file), ruling 19, the roadmap row, the README row.
2. **The panels model and Form's picker.** `Panel` and its sample panels; a gate names its panel; Form's *Chosen from* listing panels with *+ New panel…*, the quick create working in the browser. Chromium tests for the quick create. Must not touch Gates' page or add the Panels tab.
3. **Gates as gate cards.** The cards and Outline from the sample, collapsing; the panel menu and *+ New panel…* box (shared with Form's); the Outline following the panel chosen. Chromium tests. Last build rung before the Panels ruling: `diff-reviewer` reads the cumulative diff. *(Built, #3877; folded into Process by ruling 20.)*
4. ~~**Panels**, once its format is chosen~~ — taken by ruling 20's rungs:
4a. **Plan amended**: ruling 20, this section.
4b. **Process's items collapse.** Heads with their chips, open and shut, an open rule editor kept, the Outline opening an item; Process only. Chromium tests.
4c. **Evaluators on gate items; Gates retired.** The menu and *+ New panel*, members, sent gates fixed, the Outline naming panels; the Gates tab, page and its tests removed. Chromium tests. `diff-reviewer` reads 4b–4c.
4d. **Panels scaffold.** The tab in Gates' slot; the table from the sample, a column per panel, and the control card, inert.
4e. **Panels wired.** Rows and panel columns added, edited and removed with their checks; ticking membership; CSV in and out; *Copy*, *Retire*; *Edit on Panels →* on Form and Process. Chromium tests. `diff-reviewer` reads 4d–4e.
5a. **Plan amended**: ruling 21, this section.
5b. **Results on the gate item, scaffold.** The model (a gate's results: name, response field, derivation, minimum responses) and the sample's; the rows drawn with their summaries and *For Review Robin*; the gate's head counting them. Must not touch rules or weights.
5c. **Results edited in the browser.** *+ Result* (three at most), remove, each row's field, derivation and minimum; the derivations a field type allows; the summary, the result type and *For Review Robin* following. Chromium tests.
5d. **Rules and weights read a named result.** The rule editor, `rule_text` and Applications' headers name a gate's result; numbers compared and weighed, a list matched, a string offered to neither. Chromium tests. `diff-reviewer` reads 5b–5d.
6a. **People as Residential's and Review Robin's (ruling 22, after the author's browser check).** *+ New panel*'s Members a token box found in the directory; the Panels table's rows selected to edit, inert otherwise, a verified email a pill. Chromium tests; takes its own read.
6b. **Panels as Review Robin's roster page (author, 2026-11-14, from a mock-up).** No side card: the table full width under a roster card of pills (people, each panel and its count) with *Manage panels* where Review Robin has *Unlock*, holding *Copy*, *Retire*, *+ Panel* and the CSV; Review Robin's toolbar (*Search*, *Add new*), grey header band and ↕ sorts; a *Sent* chip on a sent panel's column; the × column kept on every row, its × on a selected one only; the email text when unselected, a pill without × when selected, clicked to change. No selection strip. *Used by* leaves the column header for *Manage panels* (and the header's tooltip). Search and select-all act on the rows in view; the sorted column shows ↑ or ↓, as Review Robin's badge. Takes its own read.
6c. **Panels refined (author, 2026-11-14, on the browser check).** Fixed column widths, so selecting a row moves nothing; ✓ at a selected row's end keeps its changes (Enter too), and unticking without it puts the row back, a new row unsaved going; no page *Save* and no counts under the table; *Search* renamed *Filter*; in *Manage panels*, each panel's name edited in place and *Copy emails* (to the clipboard, comma-separated), and an *Add new panel* card above *Upload*, blank or with an existing panel's people, folding in *Copy*. Takes its own read.
6d. **Panels touch-ups (author, 2026-11-14).** The new-panel menu reads *Copy from Panel A*; every header left-aligned, a panel's ticks under its name; *Add new* opens its row at the top (an imported row still joins the end). Confirmed, unchanged: *Manage panels* edits already apply at once. Takes its own read.
7a. **Saving by the surface's shape (ruling 23), one PR each, each its own read.** *Applications* as a control surface (author, 2026-11-14: "worked down one column", so one lock for the table, not a row's): locked, every cell, *Set ticked rows*, *Apply rules*, *Upload CSV* and *Released* are inert; *Unlock* opens them, *Lock* keeps the changes, *Undo changes* puts the table back as unlocked; a count of changes and a warning on leaving meanwhile; the toolbar, sticky, carries them; its *Save* goes. Ticks only choose rows.
7b. *Form* and *Process* keep the Outline's *Save*, gaining an *Unsaved changes* marker and a warning on leaving.
7c. *Emails*: a *Save* on each template card; the page's goes.
7d. *Manage panels*: a rename takes ✓ or Enter; Esc or leaving the box puts it back.
7e. **Panels on the browser check (author, 2026-11-14).** A selected row taller, its boxes at the top and a line kept beneath for its message; a verified email a pill whether the row is open or not; *Add new panel*'s blank panel takes *Members* as Form's *Select people* box does (a row added for anyone without one); *Manage panels*, open, shows *Cancel*, *Save* and *Close* at its bottom right, the toggle hidden, names waiting for *Save*, the ✓ by each box gone. Takes its own read.
7f. **A panel added waits for Save (author, 2026-11-14).** *Add panel* an outline button, so *Save* is the card's one primary; a panel added there is marked *not saved yet* until *Save*, and *Cancel* (or *Close*, confirmed) takes it back with the rows it brought, a row saved with its own ✓ staying. Takes its own read.
7g. **Retire waits for Save; the table's columns (author, 2026-11-14).** *Retire* marks a panel *not saved yet*, its heading and chip struck through, until *Save* retires it or *Cancel* keeps it; the filter matches the panels a row is on; a *Show columns:* chip per panel hides and shows its column, after Review Robin's rosters (not remembered across a reload until AD2). Takes its own read.
5. **Iteration rungs**, as the author's browser checks ask.
6. **Close**, only after the author's browser check.

## Definition of done

- The Setup row reads Process, Form, Panels, Emails (test; ruling 20).
- Process's items collapse, each head with its chips; a gate item carries *Evaluators*; the Gates page is gone (tests).
- Panels shows one table, a column per panel with its count and *Used by*, and the control card (test).
- A gate item holds up to three results, each a response field and a derivation fixing its type; rules and weights read a named result (tests; ruling 21).
- In Chromium: a panel made on Form and on Process and chosen; a row added, edited, removed and refused (bad or duplicate email); a CSV imported and exported; a panel copied, and retired only when unused (tests).
- The author has used the pages locally and approved them.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1F` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **The Panels page's format**: one table, a column per panel (ruling 20; laid out as Review Robin's roster page, rung 6b).
- **A panel shared across exercises**: carried to `applydesk/guide/todo_master.md`, for AD5.
- **`close_check.py` reads only RRW's `guide/`**: this close was checked by hand, as AD1E's.

## Out of scope

- **Saving** (AD2); **sending** a gate to Review Robin and the per-assessor assignments (AD5, AD6).
- **Searching the institution's directory** for a member (Graph, with AD4's *Institution-wide*).

## Doc impact

- `applydesk/spec/applications.md` — the Setup row with Panels in Gates' slot; *Chosen from* naming panels and *+ New panel…* in "The Form page"; collapsing items, *Evaluators* and a gate's results (ruling 21) in "The Process page"; a "The Panels page" section after it; how each page keeps an edit (ruling 23: Panels' rows, Applications' lock, Form's and Process's *Save*, Emails' per card) in each page's section (at close).
- `applydesk/spec/architecture.md` — `sample_data.py`'s row: panels in place of the three rosters (rung 2).
- `applydesk/guide/todo_master.md` — rulings 19 to 23 and the AD1F roadmap row (rung 1); the row deleted at close.
- `applydesk/README.md` — this plan's row (rung 1), moved to the archive's index at close.
