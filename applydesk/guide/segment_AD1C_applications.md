# Segment AD1C — ApplyDesk: the Applications page, a working scaffold

**Opened:** 2026-11-13 · **Theme:** the Applications tab as the exercise's control surface: every application, its status, and where it stands at each gate and outcome; every move working in the browser, nothing saved · **Related:** `applydesk/guide/todo_master.md` (rulings 5, 9, 10, 13), `applydesk/guide/archive/segment_AD1B_form_builder.md` (the scaffold pattern this repeats), `applydesk/spec/applications.md` (the URL map, the Form page)

## Opportunity

The Applications tab is a placeholder: a list with *Generate applicant profiles* and *Import outcomes* (AD1). Evaluation had no shape on screen: ruling 1 sends assessment to Review Robin, but nothing showed how an application moves from peer review to interview to a result, or where an operator decides who goes on. The author set the model through three mock-ups on 2026-11-12/13 (ruling 13): rounds of gates and outcomes, driven from one table.

## Decision

**One table, one row per application, a column per gate and per outcome, grouped under the Application stage and each round** (author, mock-up v3):

1. **Application stage** (three columns): *Application* (the application ID, linking to its application file), *Applicant* (name, email), *Status* (Submitted / Draft / Withdrawn, its date under the chip).
2. **Each round**, its From–To dates in the group header (from the Timeline): its gates, then any outcome placed after them. The sample: *Round 1* (Gate 1 Peer Review, Gate 2 Faculty Panel Review, Outcome 1 Shortlist for interview), *Round 2* (Gate 3 Interview, Outcome 2 Finalists), *Final* (Outcome 3 Final results). Every gate is a Review Robin session in the sample.
3. **A gate cell** is a chip that cycles *Pending → Selected → Not selected*; under it, the gate's result from Review Robin ("Rating 4.6 · 3 of 3") or why it was set ("Excluded: not eligible").
4. **An outcome cell** is a menu of that outcome's values, the date it was decided under it (or "Due …" from the Timeline). Each outcome header carries a **Released** switch and when and to whom it was released.
5. **Column headers count** their column across every application ("86 selected · 2 pending").
6. **A toolbar**: search (ID, name, email), a status filter, *Fill by rule…*, *Upload CSV*, *Set selected rows*, *Save*; after the rows, *All applications* or *Last applications* (each applicant's last submitted).
7. **The application file** replaces "applicant profile" in what shows (ruling 13).

**Rejected:**
- **Setting up rounds and gates on this page** ("does not belong on the Applications page", author): Setup and the Timeline own them; this page reads them.
- **A three-part switch per gate cell**: clearer, but the table would no longer fit; the author chose the cycling chip.
- **A separate Date column and a separate Profile link**: the date sits under the status, the ID links to the file (author, v2–v3).

## Semantics

- **Columns come from the exercise's setup**, here `sample_data`: rounds in order; within one, gates then outcomes in their set order. No round, no columns past *Status*.
- **A draft** has "—" in every gate and outcome: it has entered nothing. **A withdrawn application** keeps what it had, and "—" where it was never admitted.
- **Gate admittance** is per application and per gate; an outcome's value is one of that outcome's values, or *Pending*.
- **Counts** follow every change on screen.
- **Fill by rule…** takes a target column, an earlier gate's result, an operator and a threshold; it shows the rows it would change (from, to) and changes nothing until *Apply*. Rows it cannot judge (no result yet) are listed and left alone.
- **Upload CSV** takes `Application ID` and one column per gate or outcome, named as in the header; unknown IDs, unknown columns and values that are not the column's are listed, and nothing applies until the operator confirms. The same review step as a rule.
- **Set selected rows** applies one value to one column for the ticked rows.
- **Released** toggles per outcome; turning it on asks to confirm, and says what the Timeline's setup will do (here, sample text). Nothing is sent.
- **Last applications**: per applicant (by email), the latest submitted application; an applicant with none submitted shows their latest of any status.
- **Nothing is saved.** *Save* is disabled until AD2; a reload restores the sample.

## Judgment calls — decided

- **The table renders on the server, moves happen in one inline script**, as AD1B: the server renders every cell from `sample_data`; the script cycles chips, opens menus, recounts and filters.
- **`wa9juxbc2t` (Undergraduate Research Fellowship 2027) is the model exercise** (author, 2026-11-13): it carries the full setup and is built out further as segments land; the other exercises keep a smaller setup (`k7mfr3pq8z`: one round), and the blank one none.
- **The model exercise has about 100 applications**, generated deterministically in `sample_data` (a fixed seed), so counts and paging read as a real exercise; ten are written by hand for the cases (two applications from one applicant, a draft, a withdrawal, an exclusion, a manual addition).
- **"Application file" renames what shows**: the button, the page title and the route `/me/exercises/<id>/files/<file id>`; the code's `profile_id` becomes `file_id`. All are placeholders; nothing stored depends on the old names.

## Blast radius (measured)

Taken 2026-11-13 at `34f3d4b`.

| What | Count | Command |
|---|---|---|
| The Applications partial replaced | 1 file, 19 lines | `wc -l applydesk/templates/applydesk/operator/_applications.html` |
| "profile" in ApplyDesk code and templates | 49 lines | `grep -rni "profile" applydesk --include=*.py --include=*.html \| grep -v archive \| wc -l` |
| "profile" in ApplyDesk spec, to-do, README | 10 lines | `grep -rni "profile" applydesk/spec applydesk/guide/todo_master.md applydesk/README.md \| wc -l` |
| Page tests that reach Applications or profiles | 31 tests in `test_pages.py` | `grep -c "def test" applydesk/tests/test_pages.py` |

## Status

Building. Base `34f3d4b` for the cumulative read.
- Rung 2: the table. The rounds and each row's cells in `applydesk/rounds.py`; 98 generated applications join the model exercise's three in `sample_data` (101). The model exercise moves to mid-review (author, 2026-11-13: applications 1 Sep – 15 Oct, Round 2 under way), so a new sample exercise, *Postgraduate Conference Grant 2027* (`r6tm4kq9wz`), is the one open for applications. *Set ticked rows* sits under the table beside *All / Last applications*, keeping the toolbar on one line. *Fill by rule…* and *Upload CSV* render, inert until rung 3.
- Rung 3: *Fill by rule…* (Set a column to a value where an earlier gate's Rating or Score is ≥ or < a threshold, otherwise a value or as is; Pending cells only unless unticked) and *Upload CSV* (`Application ID`, then columns named as their headers, with or without "Gate 1:") share one proposal panel: what would change, what was left and why; *Apply* or *Cancel*. A gate cell carries its finished result (`Cell.result`) for the rule; an unfinished one is named, not guessed. *Download CSV* gives the table in the shape an upload reads.

## PR ladder

1. **Plan** (this file), ruling 13, its README and roadmap rows.
2. **The table.** Rounds, gates and outcomes in `sample_data`, about 100 sample applications with their cells; the grouped header with dates and counts; the Application, Applicant and Status columns; gate chips that cycle; outcome menus with dates; the release switches with their confirmation; search, status filter, *Set selected rows*, All / Last applications. Tests: the columns follow the setup; a Chromium test cycles a chip, picks an outcome, sees the counts follow, filters, switches to Last applications. Also carries the AD1B preview banner fix (its close, flag 1).
3. **Fill by rule… and Upload CSV**: the proposal and its review, applied on screen. Tests for both, including the rows a rule cannot judge and a CSV's unknown IDs and values. Last build rung: `diff-reviewer` reads the cumulative diff.
4. **The application file**: the rename of labels, page title, route and `profile_id`, with the spec's URL map. Its own read.
5. **Iteration rungs**, as the author's browser checks ask.
6. **Close.**

## Definition of done

- The columns follow the sample setup: three rounds, three gates, three outcomes, in order, with their dates (test).
- In Chromium: a chip cycles, an outcome is picked and dated, counts follow, a release asks to confirm, search and status filter, Set selected rows, All / Last applications, Fill by rule… and Upload CSV proposing then applying (tests).
- "Profile" no longer shows anywhere an operator, reviewer or applicant reads (test).
- The author has used the page locally and approved it.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1C` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **Where Setup holds rounds, gates and outcomes**, and how the Timeline sets what a release does: a later segment builds Setup's side; this page reads `sample_data` until then (author).
- **The Review tab**: with gates here, does it fold into Applications or become each gate's detail (author).
- **`close_check.py` reads only RRW's `guide/`**: this close is checked by hand, as AD1B's was.

## Out of scope

- **Saving** any of it, and the real link to Review Robin (gate sessions, results coming back): AD2 gives the database, AD6 the handoff (`applydesk/guide/todo_master.md`, roadmap).
- **Setting up rounds, gates and outcomes** (Setup, the Timeline) and **what a release sends**: their own segment, after this page shows what they must hold.
- **Rules beyond one threshold** (combining gates, ranking a top N): later, if the author asks.

## Doc impact

- `applydesk/spec/applications.md` — "The Applications page" section (at close); the URL map's file route (rung 4).
- `applydesk/guide/todo_master.md` — ruling 13 and the AD1C roadmap row (rung 1); the row deleted at close.
- `applydesk/guide/segment_AD1_skeleton.md` — the URL map's profile row renamed to the application file (rung 4).
- `applydesk/README.md` — this plan's row (rung 1), moved to the archive's index at close.
