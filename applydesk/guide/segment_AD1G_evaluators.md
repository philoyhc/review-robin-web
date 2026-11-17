# Segment AD1G — Apply Desk: a gate's evaluators and the Evaluations page

**Opened:** 2026-11-15 · **Theme:** a gate's evaluators drawn from ranked sources on Process, and their assignments shown and worked on Evaluations (ruling 27); nothing saved · **Related:** `applydesk/guide/todo_master.md` (rulings 9, 19, 24, 26, 27), `applydesk/guide/archive/segment_AD1F_gates_panels.md` (the gate item and Panels this extends), `applydesk/spec/applications.md` ("The Process page", "The Evaluations page")

## Opportunity

A gate item names one panel (`stages.Gate.panel`, AD1F) and says nothing of who evaluates which dossier. Ruling 27 (author, 2026-11-15) settles it: ranked sources, each with a min and max per dossier, a Total row, three assignment modes, and Apply Desk making the pairs it sends to Review Robin. Evaluations is a placeholder table of gates and their states (`_evaluations.html`, 35 lines) with nowhere to see or change an assignment.

## Decision

**A gate's *Evaluators* becomes a ranked list of sources with a Total; Evaluations shows each gate's dossier-by-evaluator assignments and their operations, per the gate's mode.** Built as AD1F was: a scaffold first, then wired in the browser, on sample data.

1. **The gate item's *Evaluators*** (Process), replacing the single panel menu:
   - a row per **source**, ranked (moved up and down), each a kind, its min and max per dossier, and a remove: **nominated evaluators** (a *Select people* question on Form, picked by its label; offered only when the form has one) or a **panel** (the shared menu and *+ New panel…*, AD1F). *+ Source* adds a row;
   - a **Total** row: its min and max, held within the sources' mins together and maxes together (the author: the sum of maxes is the ceiling);
   - **Assignment**: *Automatic*, *Suggested, then approved*, *Assigned by the operator* (a segmented choice);
   - the head's chip reads the sources (*Nominated 0–2 · Panel A 1–3 · Total 3*), or *No evaluators*.
2. **Evaluations**, per gate (a card each, collapsed to its head):
   - the gate's mode and counts (*42 dossiers · 40 filled · 2 short*);
   - a table, a row per entered dossier: the candidate (or the blind label), then its evaluators as pills, each marked by source (*Nominated*, *Panel A*), and the row's state (*Filled*, *Short by 1*, *Suggested*, *Approved*);
   - by mode: *Automatic* shows the pairs read-only, with *Re-run*; *Suggested* adds *Approve* per row and *Approve all*, a pill removable and an evaluator addable before approval; *Assigned by the operator* starts empty, each row taking evaluators from the gate's sources;
   - a load line per panel member (*Ana: 6 · Ben: 5 …*), so the spread shows.
3. **The filling rule** (`stages.fill`): sources in rank order, each giving as many as it has up to its max; lower ones topping up to the Total's min, never under their own min; never past the Total's max; distinct evaluators, a person in two sources counted for the higher; the candidate never their own evaluator. A dossier it cannot fill is *Short*. Automatic and the suggestion spread each panel's load evenly.

**Rejected:**
- **Assigning on Process.** Process sets rules for a gate before there are dossiers; pairs need the dossiers (ruling 27: Evaluations works them).
- **A source's own *N per dossier* without a min and max.** Ruling 27 gives each a min and max; *N* is min = max.
- **Leaving pairs to Review Robin's rules.** Apply Desk must know them for dossier access (ruling 9) and the *assigned evaluators* audience (ruling 26).

## Decision amended (author, 2026-11-17): the rest of Process > Gates

Review Robin's side of a linked gate is built (RRW 23F, `spec/linked_sessions.md`). What a gate item on Process must collect from the operator for it (`applydesk/guide/todo_master.md`, "What a linked Review Robin gate needs", layer A) joins this segment; Evaluations > Gates' sending, status and results (layer B) is a later segment. On a gate run in Review Robin:

1. **The gate's own fields**:
   - a **description**, beside its name (Review Robin's instrument description);
   - **Start** and **End**, date-times, shown in the **exercise's timezone**, defaulting from the gate's stage, Start before End; a line says a sent Start opens the session once Review Robin's operator prepares it;
   - **Confidential**, a switch on the gate (author: per gate), and what Review Robin will show for each reviewee (the name or *Name redacted*, and the key);
   - the exercise's **help contact** and **timezone** are shown on the gate, read-only: they are the exercise's (Setup), each defaulted from Apply Desk's operator settings, as Review Robin's are (author, 2026-11-17).
2. **Each result's fields**, in its editor: **required** (a switch), **help text** (what Review Robin shows the evaluator under the field), and its **field key**, shown read-only (prescribed: what Review Robin reports the answers under).
2a. **Setup** gains the exercise's **help contact** and **timezone**, prefilled from the operator settings' defaults (a sample value until AD2).
3. **The *For Review Robin* line** grows into a short summary of what will be sent: the instrument's name, its fields with required and help, the window, the tag `applydesk`.

Nothing is sent or saved here: the fields live in the browser, a reload restoring the sample, as the rest of the segment.

## Semantics

- **The Total's bounds** are recomputed as sources change; a Total outside them is shown as a problem on the Outline, not silently clamped.
- **No source**: the gate has no evaluators, a problem on the Outline (replacing AD1F's *Gate N has no panel*).
- **A nominated-evaluators source** reads each dossier's answer to its question; a dossier with no answer gives none. Referees are not a source (ruling 2).
- **A sent gate** keeps its sources and pairs (ruling 24: changes before the session opens are re-sent, later made in Review Robin); its Evaluators and its Evaluations card are read-only, as AD1F's sent gate is.
- **Nothing is saved** until AD2; Evaluations' operations work in the browser, a reload restoring the sample.

## Judgment calls — decided

- **`Gate.panel` gives way to `Gate.sources`**, a panel being one kind of source; the sample's gates become a panel source each, min = max = their current panel's size, so nothing they show changes until edited.
- **Who gives what** (2026-11-17, rung 2): the first-ranked source gives as many as it has, up to its max; each lower one gives what the Total's min still needs, never fewer than its own min; the first keeps room for the lower sources' mins. Both of ruling 27's examples hold; the author's to confirm at the rung 3 check.
- **Until the pages move (rung 3)**, `Gate.panel` stays and a gate with no `sources` reads as its panel, min = max = the panel's size (`stages.sources_of`).
- **Conflicts are the ones the data knows**: the candidate, and a person in two sources. Department or tag conflicts wait for a ruling.

## Blast radius (measured)

Taken 2026-11-15 at `31465d3cc`.

| What | Count | Command |
|---|---|---|
| The gate item and its script | 228, 868 lines | `wc -l applydesk/templates/applydesk/operator/_process_cards.html applydesk/templates/applydesk/operator/_process.html` |
| Evaluations' placeholder | 35 lines | `wc -l applydesk/templates/applydesk/operator/_evaluations.html` |
| Lines reading `.panel`, outside tests | 29 | `grep -rn "\.panel\b" applydesk --include=*.py --include=*.html \| grep -v tests \| wc -l` |
| The model and sample | 715, 816 lines | `wc -l applydesk/stages.py applydesk/sample_data.py` |

## Status

- **Rung 3 built** (2026-11-17): the Evaluators as ranked source rows, the Total with its bounds, *+ Source* and the Assignment choice, drawn from `stages.sources_of`; the model exercise's Peer Review gate shows ruling 27's shape (*Preferred reviewer* 0–1, Panel A 1–2, Total 2–2).
- **Rung 4 built** (2026-11-17): every source row carries both menus (the question, the shared panel picker), the kind showing one; ↑ ↓ rank, × removes, *+ Source* adds a panel of one; the head's chip (`stages.sources_summary`) and the Outline read the sources; the Outline names a source with no panel or question, a min above its max, a missing number, and a Total outside its bounds (as `stages.total_problem`). A new gate starts with no sources (*No evaluators*), not AD1F's empty panel menu. `stages.fill` counts a nominated dossier toward the load too (Codex on rung 2).
- **Reads, rungs 2–4**: Codex on rung 2, one finding (the load), fixed. `diff-reviewer` on the cumulative diff (`7e0322828..1c2ec878c`), six findings, none blocking, all fixed in rung 4: the *+ New panel* box shut when a source turns Nominated; the Total's inputs named for screen readers; the server's chip warning as the script's (`stages.sources_warn`); a replica test pinned to its three menus; choosing the chosen mode no change; the sent line naming its evaluators. `Gate.panel` still feeds `stages.panel_uses` and `workflow`'s sends; they read the sources with Evaluations (rung 5). A panel used twice, or a max above its panel's size, is not flagged: for the author at the rung 4 check.
- **Rung 5 built** (2026-11-17): Evaluations keeps its Gates table and gains *Assignments*, a card per gate collapsed to its head (mode, *92 dossiers · 92 filled*), a row per entered dossier with its evaluators as pills marked by source and its state, and a load line per panel (`stages.assignments`, `assignment_state`, `assignment_counts`). The sample's nominations are `sample_data.nominees`: from the question's pool, one applicant in five naming no one. Faculty Panel Review becomes *Suggested, then approved*, so the sample shows two modes. Every sample gate is sent, so its operations show disabled, saying why; rung 6 needs an unsent gate to work them on, for the author at the rung 5 check.
- **Rung 4a** (author, 2026-11-17, at the rung 4 check): the source rows' controls aligned under one header row (*Kind*, *Source*, *Min*, *Max*), with room kept under every menu for its *Edit on Panels* link; ▲ ▼ for rank, as Review Robin's builders; a row's **+** before × adds the next source, *+ Source* showing only when there are none; and a rule between a gate's main sections (rule, Evaluators, Assignment, Runs as, Results) and an outcome's (weights, rule, release), and the form's release. Its cold read: nothing blocking; the link's padding, the Total's spacing, two test pins and this line's overclaim, all fixed.

## PR ladder

1. **Plan** (this file), its README row, the roadmap row.
2. **The model and the rule.** `stages.Source`, `Gate.sources` and the Total, mode; `stages.fill` with its tests (the author's two examples, distinctness, shortfall, the Total's bounds); the sample's gates as panel sources. Must not change a page.
3. **Evaluators on the gate, scaffold.** The rows, Total and mode drawn from the sample; the head's chip; the Outline's problems; inert controls.
4. **Evaluators wired.** Add, rank, remove a source; min and max; the Total's bounds; the mode. Chromium tests. `diff-reviewer` reads 2–4.
5. **Evaluations scaffold.** A card per gate, its table and load line drawn from `stages.fill` on the sample's dossiers; inert controls.
6. **Evaluations wired.** The three modes' operations in the browser. Chromium tests. `diff-reviewer` reads 5–6.
7. ~~**Close**, after the author's browser check.~~ Moved to 10 by the amendment.
8. **The gate's and results' fields, scaffold** (amendment): description, Start and End with the timezone, Confidential; Setup's help contact and timezone; each result's required, help text and field key; the fuller *For Review Robin* summary; drawn from the sample, inert. `stages` gains the fields, the sample filling them.
9. **The fields wired**: edited in the browser, Start before End, a required switch and help text per result, the summary following; a sent gate read-only. Chromium tests. `diff-reviewer` reads 8–9.
10. **Close**, after the author's browser check.

## Definition of done

- A gate holds ranked sources, a Total and a mode; `stages.fill` fills per ruling 27 (tests, the author's examples among them).
- Process edits the Evaluators in the browser, the Total held within its bounds (Chromium tests).
- Evaluations shows each gate's assignments and works its mode (Chromium tests).
- A gate run in Review Robin collects its description, window and confidentiality, Setup the exercise's help contact and timezone, and each result its required, help text and field key; the *For Review Robin* summary shows them (Chromium tests).
- The author has used the pages locally and approved them.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1G` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **The Total's label**: *Total*, proposed with ruling 27; the author's at the rung 3 check.
- **Suggested mode's re-run**: whether a re-run keeps approved rows; proposed yes, settled at rung 6.
- ~~**Confidential per gate or per exercise**~~: per gate (author, 2026-11-17).
- ~~**The help contact and the timezone's home**~~: the exercise's, each defaulted from Apply Desk's operator settings as Review Robin's are (author, 2026-11-17); Setup carries them.
- **`close_check.py` reads only RRW's `guide/`**: this close is checked by hand, as AD1E's and AD1F's.

## Out of scope

- **Sending** the pairs (AD6) and saving them (AD2); Evaluations > Gates' Send, re-send, status and results (a later segment, author 2026-11-17).
- **Referees** as a source (ruling 2).
- **Tag or department conflicts**, until ruled.

## Doc impact

- `applydesk/spec/applications.md` — "The Process page": a gate's Evaluators as ranked sources, the Total and the mode, and (amendment) a gate's description, window, timezone, help contact, confidentiality and each result's required, help text and field key; "The Evaluations page": a section for its assignments and operations (at close).
- `applydesk/guide/todo_master.md` — the AD1G roadmap row (rung 1); deleted at close.
- `applydesk/README.md` — this plan's row (rung 1), moved to the archive's index at close.
