# ApplyDesk — closed segment plans

Plans whose segments have closed, kept as the record of intended versus
done. Open work is in `applydesk/guide/todo_master.md`.

> **Corrected 2026-11-20 (RRW segment 23H, rung 1).** Every plan below
> says `tools/close_check.py` "reads only RRW's `guide/`", so each was
> closed by hand. That was never so: the tool has read Apply Desk's plans
> since 2026-11-02 (`APP_DIRS` in `tools/close_check/_manifest.py`), ten
> days before AD1 opened. Run over all seventeen on 2026-11-20, fourteen
> pass. AD1G, AD1H and AD1K fail C3 on `applydesk/spec/applications.md`
> only because their close PRs archived the plan before landing its spec
> edits, and the tool's window then ended at the archive commit. 23H's
> rung 2 moves that end to the merge, after which all seventeen pass.
> The plans themselves are left as written (constitution V).

| Plan | Segment |
|---|---|
| `segment_AD1_skeleton.md` | AD1: the package, its mount, health and packaging, then the URL map as placeholder pages on sample data; every page since rebuilt by its own segment (closed 2026-11-19) |
| `segment_AD1B_form_builder.md` | AD1B: the Form page as a working scaffold, cards that move on screen, nothing saved (closed 2026-11-12) |
| `segment_AD1C_applications.md` | AD1C: the Applications page (Dossiers since ruling 25) as the control surface, a row per application and a column per gate and outcome, rules and a CSV applied as a proposal, all or last applications; nothing saved (closed 2026-11-19) |
| `segment_AD1D_chrome.md` | AD1D: an exercise's pages in Review Robin's chrome, Exercise Home with a Setup row and an Operations row, and the status row; its Workflow card built then removed (2026-11-15); nothing saved (closed 2026-11-19) |
| `segment_AD1E_process.md` | AD1E: the Process page as a stack of stage cards, rules on each gate and outcome, and Emails listing the templates it makes owed (ruling 16); nothing saved (closed 2026-11-13) |
| `segment_AD1F_gates_panels.md` | AD1F: Panels as one table after Review Robin's roster page, picked or made on Form and Process; Gates folded into Process with a gate's results; each page keeping edits by its shape (rulings 19–23); nothing saved (closed 2026-11-14) |
| `segment_AD1G_evaluators.md` | AD1G: a gate's evaluators from ranked sources with a Total and a mode, the gate card as ruling 28 lays it out, and each gate's pairs worked by mode on its Evaluations page (rulings 27–29); nothing saved (closed 2026-11-17) |
| `segment_AD1H_ra_exercise.md` | AD1H: the model exercise rebuilt as the RA recruitment (ruling 30), rules with branches, a form answer and the best N, a mean ignoring 0, and a page per gate, paged and sorted; nothing saved (closed 2026-11-17) |
| `segment_AD1I_home.md` | AD1I: Exercise Home in two columns, a timeline by stages the applicant's page shares (horizontal or vertical, each viewer's) with the operator's part beneath, beside Details unlocked to edit; cards sharing a height only when close; nothing saved (closed 2026-11-18) |
| `segment_AD1J_extract.md` | AD1J: Extract data as Review Robin's, download cards that cut the exercise's data into CSVs and ZIPs (applications, by gate, outcomes, the alias key, the setup), shaped by chips kept per viewer, none of it on screen; built from the sample, nothing saved (closed 2026-11-18) |
| `segment_AD1K_stage_status.md` | AD1K: a status per stage (Draft, Published, Overdue, Completed; ruling 35) with Publish and a revert from the last published stage back; typed date-times for each stage and item; everything a published stage holds fixed on every page, its reasons said, only ends editable; each draft's blockers in the timeline; sample only, nothing saved (closed 2026-11-18) |
| `segment_AD1L_emails.md` | AD1L: Emails as a working scaffold, each card a template that stands alone: written, saved in the tab, reset to its kind's default, its merge fields inserted and checked, and previewed from the sample; nothing saved or sent (closed 2026-11-19) |
| `segment_AD1M_gates_to_rr.md` | AD1M: Layer B, each gate's Review Robin card: the session's name and code, the four files it would send (built for real, Review Robin's handoff route taking them), Send and Re-send, Pull and Pull final results, Invite and Remind, closed and detached sample gates; simulated in the tab, nothing sent (closed 2026-11-19) |
| `segment_AD1N_scratch_exercise.md` | AD1N: scratch exercises: *New exercise* makes a blank draft held in this server's memory for one browser (five at most, eight idle hours), and Details, Form, Process, Panels and Emails each save into it, so the whole setup can be walked before AD2; keys kept by the server, references to what was removed kept as removed (closed 2026-11-19) |
| `segment_AD1O_gate_setup.md` | AD1O: gate setup touch-ups: a gate's *Gate* card on Process links to its Review Robin card (ruling 61), and a panel source takes *All* of its panel, its Min, Max and, when every source does, the Total following the panel's size (ruling 62) (closed 2026-11-20) |
| `segment_AD1P_ui_consistency.md` | AD1P: the UI consistency sweep: one look and vocabulary across Apply Desk's pages, recognizably Review Robin's family (ruling 64): one tone map, `Gate N · label`, RRW's roles, tables and headings, and an operator dossier page; ISO operator dates deferred to AD2 (closed 2026-11-20) |
| `segment_AD1Q_gate_links.md` | AD1Q: the gate page's Review Robin card in two columns, its files as 2 × 2 tiles and Progress as a panel; Evaluations, Emails and Panels rows in line; links from a gate card on Process to its page and back, and from an email ticked on Process to its template and back (ruling 65) (closed 2026-11-20) |
| `segment_AD1R_ui_rows.md` | AD1R: the 2026-11-18 assessment's last 14 UI rows after AD1P: one unsaved marker, table hover and button hovers, labels and counts, intros, one empty-state block, Panels' three-state sort (closed 2026-11-21; the author's browser check is a follow-up in `applydesk/guide/todo_master.md`) |
| `segment_AD1S_home_and_copy.md` | AD1S: Home's timeline for every participant (*Applicants*, *Now* on the Now stage, one *Operator only*) and a sweep of spec- and ruling-derived copy from the pages; ruling 68 recorded (closed 2026-11-21; the author's browser check is a follow-up in `applydesk/guide/todo_master.md`) |

## Findings registers

Registers worked to empty, kept as the record of what was found and what fixed it.

| Register | What it held |
|---|---|
| `findings_2026-11-20.md` | Apply Desk's 12 rows from RRW's corpus sweep and codebase assessment of 2026-11-20 (the first to read the packages' prose): the spec against the rulings, the layout table, a 500 on long digits and non-string JSON, the scratch store, the gate download's formula guard. Archived 2026-11-21 (#4078, #4081, #4082, #4089); S1 became ruling 66. |
| `findings_2026-11-18_assessment.md` | The 2026-11-18 assessment of every Apply Desk screen, 125 rows (AD-01 to AD-125). Worked through AD1K, AD1L, AD1P and AD1R; reconciled 2026-11-21, its AD2 rows moved to `applydesk/guide/ad2_deferred_findings.md` and its later-stage rows to `applydesk/guide/ad3_plus_deferred_findings.md`. Archived 2026-11-21. |
