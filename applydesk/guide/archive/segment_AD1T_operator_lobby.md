# Segment AD1T — The Operator Lobby as Review Robin's

**Opened:** 2026-11-21 · **Theme:** the Operator Lobby laid out as Review Robin's, as a scaffold on sample data · **Related:** `applydesk/spec/applications.md`, `app/web/templates/operator/sessions_list.html`

## Opportunity

Apply Desk's Operator Lobby is a bare table with *New exercise* in the title row. Its columns are Exercise, Exercise code, State, Stage, Submitted and Applications close. Review Robin's lobby, which operators use every day, has a different layout:
- two cards over the table: counts with a tag filter, and a Filter box with the page's actions;
- sortable columns: who created a session, when, its timezone, its status and its tags;
- a tick column whose rows open an inline panel, to edit one session or act on several.

The author asked for Apply Desk's lobby to match it (2026-11-21). A mock-up was agreed in this conversation.

## Decision

The lobby takes Review Robin's layout (the author's rulings, 2026-11-21):

- **Cards over the table:**
  - ***Exercises*:** counts by status (exercises, Draft, Published, Completed, Archived), then *Show exercises tagged with:* tag chips, *OR* and *Clear*.
  - ***Filter*:** a box for name, code or tag, with *Clear*, *New exercise* (moved here from the title row) and *Go to Archive*.
- **Columns:** Exercise, Exercise code, Created by, Created (date and time), Timezone, Status, Tags, and a tick box. Every column except Tags and the tick sorts; Created newest first.
  - Status is the state chip over *Stage N of M*, with the stage's name when it has one.
  - Submitted and Applications close go (ruling).
- **Ticking (ruling: Review Robin's style):** ticked rows are highlighted, and a panel opens under the last ticked one.
  - **One exercise:** *Name*, *Exercise code*, *Tags*; *Yes, delete*; *Archive after purging* with Applications, Dossiers and Audit log. Buttons: *Save*, *Cancel*, *Duplicate*, *Duplicate settings only*, *Purge and archive* (Outline-amber), *Delete* (Destructive).
  - **More than one:** *Tags*, the same delete and purge controls. Buttons: *Cancel*, *Unselect others*, *Unselect all*, *All tags to all*, *Remove from all*, *Purge and archive all*, *Delete all*.
  - There is no *Deadline* field: an exercise's dates are its stages', set on Process.
- **A scaffold (ruling):**
  - **Working now:** the rows, the counts and *New exercise* (scratch, as now). Ticking opens and closes the panel in the browser.
  - **Inert, saying "… is not built yet":** sorting, the tag chips, the filter, *Go to Archive* and every action in the panel.
  - **Sample values:** Created by, Created and Tags come from sample data, as every AD1 page's do.
  - **Later:** wiring waits for AD2B, when exercises reach the database.

Rejected: a separate *With ticked exercises* bar above the table, as first mocked. Review Robin's inline panel is the house style, and the author chose it.

## Semantics

- **Scratch exercises:**
  - Created by is the viewer and Created is when it was made.
  - A scratch exercise has no tags.
  - It keeps its *Scratch* chip and its *Discard*, which still works.
- **Timezone** is the exercise's own, or the operator settings' default. It is shown as its offset now (`GMT+8`), with the zone's name as the title.
- **Stage N of M** counts the exercise's stages on Process. N is the stage holding its next step, or the last once every step is done (`workflow.current_stage`).
- **The tick panel:**
  - it follows the last ticked row;
  - unticking every row closes it;
  - the header box ticks every row shown and shows a dash when only some are ticked.

## Judgment calls — decided

- The purge options are Applications, Dossiers and Audit log, in place of Review Robin's Responses, Rosters and Audit log.
- The panel takes Apply Desk's accent tint, not Review Robin's blue.
- Created by reads the signed-in operator's name on every row, sample and scratch, until AD2B records who made each (2026-11-22): the sample exercises are the viewer's own in AD1's sample, as the author read them.
- The rows stand newest first, as Created's arrow says; clicking a header stays inert (2026-11-22).
- The panel's *Cancel*, *Unselect others* and *Unselect all* work, since they only untick rows in the browser; every other action is inert. *Cancel* unticks the row the panel sits under, which moves it back to the row ticked before, as Review Robin's (2026-11-22, cold read).
- *New exercise* now stamps the scratch exercise's Created, in UTC with its offset, so Created follows a timezone Details sets later; the ladder's "must not touch scratch creation" yields to Semantics here, and nothing else in creation changed (2026-11-22, cold read).
- The Exercises card counts Closed too, every status in `locks.STATUS_ORDER`, so the chips add up to the total (2026-11-22, cold read).

## Blast radius (measured)

Taken 2026-11-21 at `f4978a9a5`.

| What | Count | Command |
|---|---|---|
| Template | 1 (`operator/exercises.html`) | the lobby's own |
| Route | 1 (`routes_operator.exercises`) | `grep -n '"/exercises"' applydesk/routes_operator.py` |
| Tests naming the lobby's markup | 3 (`test_pages.py`, `test_scratch.py`, `test_scratch_browser.py`) | `grep -rln "data-nx-open\|Submitted</th>\|data-scratch-chip" applydesk/tests` |
| Specs | 1 (`applications.md`, "The Operator Lobby") | `grep -n "Operator Lobby" applydesk/spec/applications.md` |

## Status

Closed 2026-11-22. Intended versus done:
- **Ladder as planned:** the plan (#4125), the scaffold (#4126), and this close.
- **Done as decided,** with these build decisions (Judgment calls, 2026-11-22):
  - Created by is the viewer's name;
  - rows are newest first;
  - the panel's *Cancel* and the two *Unselect* buttons work in the browser;
  - Closed is counted;
  - the scratch Created is stamped at creation, which the ladder's "must not touch" yields to.
- **Beyond the plan:** Status finds its stage by number (`workflow.stage_position`, a `stage` on each `Step`), since two stages may share a name.
- **Reads:** one `diff-reviewer` read of the unit (from `f4978a9a5`) found 8 findings, no blocker; all were acted on in #4126. `spec-writer` at the close rewrote "The Operator Lobby" in `applydesk/spec/applications.md` and flagged only the Closed and stage-number points above.
- **Owed:** the author's browser check of the lobby and its panel.

## PR ladder

1. **PR 1 — this plan.**
2. **PR 2 — the scaffold.**
   - Lands: the cards, the columns, the sample Created by, Created and Tags, the tick panel's markup and its open and close, and the inert controls.
   - Must not touch: scratch creation and *Discard*, beyond moving *New exercise*.
3. **PR 3 — close.**

## Definition of done

- The lobby shows the two cards and the eight columns. Status reads *Stage N of M*, and the panel opens for one and for several ticks (`test_pages.py`, `test_lobby_browser.py`).
- *New exercise* and *Discard* still work (`test_scratch.py`, `test_scratch_browser.py`).
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1T` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

None open. The author ruled on the columns, Review Robin's tick panel and building the scaffold now, on 2026-11-21.

## Out of scope

- **Wiring:** sorting, the tag filter, the filter box, *Go to Archive*, and every action in the panel (*Save*, *Duplicate*, purge, delete, tags). This waits for AD2B, when exercises and their tags reach the database (`applydesk/guide/ad2_series.md`).

## Doc impact

- `applydesk/spec/applications.md` — "The Operator Lobby": the cards, the columns, Status as *Stage N of M*, the tick panel, and what is inert until AD2B.
- `applydesk/guide/ad2_series.md` — AD2B's row takes the lobby's wiring (sorting, tags, filter, archive, the panel's actions).
- `applydesk/guide/todo_master.md` — the queue entry deleted at close.
- `applydesk/README.md` — the plan's index row, moved at close.
