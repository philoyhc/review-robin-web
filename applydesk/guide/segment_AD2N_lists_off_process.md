# Segment AD2N — Lists off Process

**Opened:** 2026-11-27 · **Theme:** Process sets an exercise up; the lists it gathers are kept on pages of their own · **Related:** `applydesk/guide/ad2_series.md`, `applydesk/guide/archive/segment_AD2I_who_may_apply.md`, `applydesk/spec/applications.md`, rulings 77, 83 and 84 (`applydesk/guide/todo_master.md`)

## Opportunity

- **Process is for setting up, not running** (author, 2026-11-27). A Form's invite list and Create dossiers' entries each draw a full table inside a Process card; a list of hundreds makes Process long and buries the timeline it exists to set.
- **Neither list has a page.** The tables are the only place to see or remove an invitee or an entry, and before publishing an entry is not yet a dossier, so the Dossiers page cannot show it.

## Decision

- **Invitees, a tab** (author, 2026-11-27): in the Setup row after *Process* and before *Form*, shown only while the Form's *Who may apply* is *Invitees* as saved, and no Create dossiers is on the timeline. Modeled on Panels: a roster card (the count, *Add invitees* with its pills and suggestions, *Upload CSV…*) above a full-width table of the invitees (Name, Email, How added, Added, *Remove*).
- **Create dossiers' list on the Dossiers page** (author, 2026-11-27): a card holding the entries (Name, Email, Title, Added, *Remove*), shown while Create dossiers is in the process, before and after publishing.
- **Process keeps the add rows, not the tables** (author, 2026-11-27): the Form item keeps *Add invitees* and *Upload CSV…*; Create dossiers keeps its search, *Dossiers per person*, *Add* and *Upload CSV…*. Each shows a one-line count with a link, *12 invitees · Manage on Invitees →*, *34 dossiers for 12 people · Manage on Dossiers →*.
- **Warnings stay on the Outline** (`timeline_checks`), as now.

**Rejected:**
- **Create dossiers' list on a tab of its own** like Invitees (author, 2026-11-27): one place for dossiers, the Dossiers page, wins over symmetry.
- **The Dossiers grid listing unpublished entries as rows**: the grid is built for gates, columns and rules; entries are a list, so a card beside it.
- **Keeping the tables, folded**: still a long page once opened; the folding stays only where a list is shown in full.

## Semantics

- **The tab's showing** reads what is saved, not the page's unsaved dropdown: choosing *Invitees* on Process shows the tab after Save, and the Form's link says so until then.
- **The Invitees route** answers whatever *Who may apply* is, so a link or a bookmark never 404s; the tab alone is hidden. With *Anyone signed in* or Dossiers the page says the list is kept but unused, as Process does today.
- **An empty list** on either page reads *No one yet.*; the Outline's warning is unchanged.
- **Removing an entry after publishing** retires its dossier (ruling 83, `dossiers.sync_candidates`); the card says so beside *Remove*.
- **Locks**: neither list is under the Form's or a stage's lock (AD2I, cold read), so both pages stay editable while published.

## Judgment calls — decided

- **One list script, three pages** (2026-11-27): the people-list script moves out of `_process.html` into an include, keyed by `data-cand-kind` as now, so Process, Invitees and Dossiers share it.
- **How added** is shown on Invitees (`via`: Search or CSV), as Panels shows a member's source; Create dossiers' card shows the title instead.

## Blast radius (measured)

Taken 2026-11-27 at `4cf492fb0`.

| What | Count | Command |
|---|---|---|
| Templates drawing a people list | 2 calls, 1 macro | `grep -rn "people_list(" applydesk/templates` |
| List script in `_process.html` | ~380 of 2,366 lines | `grep -n "data-cand-" applydesk/templates/applydesk/operator/_process.html \| wc -l` |
| Test files touching the lists | 5 | `grep -rln "invitee\|data-cand-\|people_list" applydesk/tests --include=*.py` |
| Specs naming the lists | 3 | `grep -rln "Invitees\|invite list\|Create dossiers" applydesk/spec` |
| Nav callers | 9 | `grep -n "SETUP_PAGES\|exercise_nav(" applydesk/*.py` |

## PR ladder

1. **Plan** (this file), the series row. Prose only.
2. **The list script shared.** The people-list script moved into `_people_list_js.html`, included by Process; no behavior change.
3. **Invitees tab, scaffold.** The tab in the Setup row (shown as decided), the page with its roster card and table as static placeholders. Must not wire changes.
4. **Invitees tab, wired.** The roster card's add row and CSV, the table with *Remove*, the count, reading `applydesk/invitees.py` through the existing routes.
5. **Create dossiers on Dossiers.** The card on the Dossiers page, wired the same way through the candidates routes.
6. **Process slimmed.** The Form and Create dossiers items keep their add rows, lose their tables and show their count lines and links; spec.
   - **Last build rung:** `diff-reviewer` on the cumulative diff from rung 2's base.
7. **Close:** `spec-writer` on `applydesk/spec/`; Status compacted; the plan archived.

## Definition of done

- The Invitees tab shows only with *Invitees* saved and no Create dossiers, between Process and Form (a test).
- Invitees and Dossiers each list, add to and remove from their list (tests).
- Process's Form and Create dossiers items show no table, a count and a link (a test).
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2N` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- None open; the author settled the list's home and the tab's place on 2026-11-27.

## Out of scope

- Checking the lists when someone applies (AD4).
- Create dossiers' pill box for several people at once (the author's, later).

## Doc impact

- `applydesk/spec/applications.md` — the Invitees tab, Create dossiers' card on Dossiers, Process's items without their tables.
- `applydesk/spec/architecture.md` — the Invitees section in the module map and pages, `_people_list_js.html`.
- `applydesk/guide/ad2_series.md` — the AD2N row (at plan and close).
