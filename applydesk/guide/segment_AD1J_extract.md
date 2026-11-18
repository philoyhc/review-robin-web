# Segment AD1J — Apply Desk: Extract data

**Opened:** 2026-11-18 · **Theme:** Extract data rebuilt after Review Robin's: a page of download cards that shape the exercise's data for offline selection, none of it shown on screen; files built from the sample, nothing saved · **Related:** `applydesk/guide/todo_master.md` (the AD1J row; ruling 14), `applydesk/docs/extract/`, `applydesk/spec/applications.md`, Review Robin's `spec/extract_data.md`

## Opportunity

Extract data (`applydesk/templates/applydesk/operator/_extract.html`) is still AD1D's copy of Reports: an *Evaluation responses* table with a column per gate kind, then an inert *Export bundle* and *Single files*. Since then Dossiers became each application's record, with every part under its own visibility, and each gate has a page of its pairs and results (AD1G, AD1H). The table repeats both, and cannot hold what it promises: every gate's response fields side by side run far wider than a screen (author, 2026-11-18). Nothing on the page says what a file will hold.

## Decision

The author's, 2026-11-18: **Extract data is Review Robin's Extract data**, a workbench that cuts the data into files and shows none of it. Showing stays with Dossiers (one application) and each gate's page (one gate). Mock-up `applydesk/docs/extract/` (v1).

1. **Cards, two to a row**, each a heading, a line saying what its file is and the question it answers, a row of chips, the file's columns in a line, and its download at the foot; one column on a phone.
2. **Extract all data**: one ZIP, a manifest and every file the other cards make as each is set; chips for which files it carries and *Applicants as* (*Names* / *Dossier IDs*).
3. **Applications**: a row per application, who and when, then a column per form question in the form's order; *Last applications* / *All applications*, drafts left out or included.
4. **By gate**: a file per gate, a row per pair (dossier, evaluator, then a column per response field) or a row per application (the gate's results); the gates listed with their row counts, an unsent gate with none; *Applicants as*, *Dossier IDs* by default.
5. **Outcomes**: a row per application, each gate's results as Dossiers collates them, then each outcome's value and when it was released.
6. **Alias key**: Dossier ID to applicant, apart from every other file.
7. **Extract setup**: Form, Process, Panels and Emails as files, to clone an exercise.

Rejected: **an on-screen collation** (the placeholder's table): it repeats Dossiers and the gate pages and cannot fit the width. **Review Robin's Data shaper** (saved custom shapes): later, if the canned files do not serve (Out of scope).

## Semantics

- **The files** are CSV in Review Robin's envelope (`spec/csv_contracts.md` §1: UTF-8 with BOM, a header row); names `applications.csv`, `gate_<n>_<slug>.csv`, `outcomes.csv`, `alias_key.csv`, `manifest.csv`; the ZIP `<code>_extract_<date>.zip`.
- **Applicants as**: *Names* puts the applicant and email beside the Dossier ID; *Dossier IDs* leaves them out. A blind or confidential gate's file defaults to *Dossier IDs*; the operator may still choose *Names* (the files are the operator's).
- **Visibility**: a dossier part's visibility governs what applicants and evaluators see, not the operator's export; every download is the operator's and is logged at AD2.
- **Last / All applications**: as Dossiers (ruling 13); drafts only on *Applications*, left out by default.
- **A form question's column**: its label; a list question one column, items joined by `; `; a photo or file its file name; a section heading no column.
- **A gate not sent** has no file and says *Not sent*; the ZIP leaves it out and the manifest says so.
- **Empty**: no submitted applications, each card says so and its download is off.
- **Draft exercise**: Extract setup works; the others say there is nothing to extract yet.

## Judgment calls — decided

- The files are built by an adapter (`applydesk/extract.py`), the page's chips and the tests reading one shape; the routes stream them.
- Chip state per viewer in `localStorage` (`applydesk-extract-<id>`), as Review Robin's.
- The *Evaluation responses* table and the `RESPONSES` sample go.

## Blast radius (measured)

Taken 2026-11-18 at `31c2f7ff3`.

- Templates: `operator/_extract.html` (replaced); `grep -rln "_extract.html" applydesk/templates` → 1.
- Code: `routes_operator` (the extract route passes `sample_data.RESPONSES`, line 166); `grep -rn "RESPONSES" applydesk/*.py` → 2.
- Tests: `applydesk/tests/test_pages.py` (`test_extract_data_collates_every_evaluation_and_exports`, the empty case).
- Spec: `applydesk/spec/applications.md` (only the Operations row names it; the page's contract is new).

## PR ladder

1. **Plan** (this file), the v1 mock-ups in `applydesk/docs/extract/`, the README rows, the roadmap row.
2. **Scaffold**: the six cards as the mock-up, chips and downloads inert, each card's columns from `applydesk/extract.py`; the old table and `RESPONSES` gone. Must not touch Dossiers or the gate pages.
3. **Downloads**: each card's CSV and the ZIP built from the sample, as the chips say; the chips kept per viewer. Tests read the files.
4. **Alias key and Extract setup**: their files; the draft and empty cases. `diff-reviewer` reads 2–4.
5. **Close**, after the author's browser check.

## Definition of done

- Extract data shows the six cards and no data table (tests).
- Every card downloads its file from the sample, shaped by its chips (tests reading the CSVs and the ZIP's manifest).
- A gate not sent, a draft exercise and no applications each say so (tests).
- The author has used the page locally and approved it.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1J` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **Setup files' format**: CSV per page as Review Robin's, or one JSON; proposed CSV, the author's at rung 4.
- **Interview scores recorded by hand** (the placeholder's *Record interview scores*): a gate run outside Review Robin is not modelled; proposed out (AD2 or later).
- **`close_check.py` reads only RRW's `guide/`**: this close is checked by hand, as AD1G's to AD1I's.

## Out of scope

- **Saving or logging downloads** (AD2).
- **Pulling results from Review Robin** (the handoff, AD5).
- **The Data shaper** and saved shapes: Review Robin's; later if the canned files fall short.
- **Importing setup files** into a new exercise: the export only.

## Doc impact

- `applydesk/spec/applications.md` — an "Extract data" section: the cards, each file's rows and columns, the chips, the alias key, the empty and draft cases (at close).
- `applydesk/guide/todo_master.md` — the AD1J roadmap row (rung 1); deleted at close.
- `applydesk/README.md` — this plan's row and `docs/extract/` (rung 1); the plan's row moved to the archive's index at close.
