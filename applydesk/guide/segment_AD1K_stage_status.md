# Segment AD1K — Apply Desk: a status per stage, and what locks

**Opened:** 2026-11-18 · **Theme:** each stage Draft, Published or Completed (ruling 35), and everything a published stage holds locked, its locks said where they bite; sample data, nothing saved · **Related:** `applydesk/guide/todo_master.md` (rulings 14, 24, 29, 35), `applydesk/guide/findings_2026-11-18_assessment.md` (theme 1 and the rows below), `applydesk/spec/applications.md`

## Opportunity

The exercise has one status (`Exercise.state`: Draft, Published, Closed, Archived, strings with no transitions, AD-37), and almost nothing reads it. The assessment found that **nothing locks once live**:
- **AD-01:** an opened gate says "its settings are fixed here", yet it can be renamed, its rule edited, or removed at one click.
- **AD-02:** the stage holding a closed form with 100 applications deletes at one click.
- **AD-03:** the Form builder is fully live on a published exercise.
- **AD-04:** Dossiers flips entry at a gate whose results are in.
- **AD-05:** blind review stays editable.

Publishing checks only Home's and the dates (AD-20). *Released* releases an undecided outcome whose emails are owed (AD-21).

An exercise runs over months, stage by stage, and its later stages are still being set up while the first runs. So the author ruled (35) that **each stage carries its own status**, and that what locks, locks when its stage is published.

## Decision

The author's, 2026-11-18 (ruling 35).

1. **A stage is Draft, Published or Completed.**
   - **Publish** makes it live and locks what it holds.
   - **Completed** follows when all its items are (Decision amended), locking its results as well.
   - **Revert to draft** takes a Published stage back to Draft. It needs a reason, and the revert is audited at AD2.
2. **The exercise's status follows its stages.**
   - It is a Draft until its first stage is published.
   - It is Published while any stage is Published, or some are still Draft after others went live.
   - It is Completed when every stage is Completed.

   Closed and Archived stay AD3's.
3. **What a published stage locks**, said in place with its reason on every control it disables:
   - **The form**, when its stage holds it: the Form builder becomes read-only.
   - **Its gates:** name, rule, results, sources and removal.
   - **Its outcomes:** values, rule and removal.
   - **The stage itself:** its start, and its deletion. Its end and its items' ends stay editable, as an extension (Decision amended).
   - **Blind review**, once the first stage holding a gate is published.

   Draft stages stay fully editable beside it.
4. **Publish checks what that stage needs** (AD-20):
   - Home's details, for the first stage.
   - Process's Outline problems, for that stage's gates and outcomes.
   - The form, for its stage.

   The Publish card on Home becomes per stage.
5. **Release asks for readiness** (AD-21): *Released* is off while one of the outcome's emails is owed, and warns while reached cells are undecided.

Rejected:
- **One status for the whole exercise, locking everything at publish:** a later stage could no longer be set up while the first runs, which is how exercises are worked.
- **Locks keyed on gate state alone** (sent or opened, as today): that leaves the form, outcomes, dates and blind review with no lock at all, and keeps two notions of "fixed".

## Decision amended (author, 2026-11-18, on the open questions)

- **Completed is derived, not marked.** A stage is completed when all its items are:
  - its form closed;
  - each gate's results in;
  - its outcome released, if it holds one.

  There is no *Mark completed*.
- **Blind review** locks when the first stage holding a gate is published.
- **A revert after a gate has opened** is allowed. The gate stays fixed (ruling 29), and the confirm says so.
- **Every stage declares its dates and times** (author, 2026-11-18). Automatic completion assumes it:
  - a stage cannot be published without a start and an end, each a date and a time in the exercise's time zone;
  - when its end passes, it completes once all its items are;
  - an item still open at its end keeps the stage Published, marked *Overdue* with what is outstanding.

- **An extension is how a stage is kept open or reopened** (author, 2026-11-18): the operator moves the end of the stage and of its items later. A Completed or Overdue stage whose end moves past now is Published again. So a stage's and its items' end dates stay editable after publish, even once completed; its start, and everything else it holds, stays locked.

- **Each item has its own dates inside its stage's** (author, 2026-11-18). A stage holding an outcome cannot end when its gates do, since the outcome is decided after their results are in. So:
  - the stage's start and end bound everything it holds;
  - the form has its open and close, and a gate its review window;
  - an outcome has its due, no sooner than the gates it reads close;
  - an item with none set runs on the stage's dates; an outcome is due at its end.

  Publishing refuses an item outside its stage, or the wrong way round. The stage still completes at its own end (Semantics).

  This makes AD-56's typed dates part of this segment: a stage's start and end are typed date-times, not free text. Process's date fields become date-time inputs, and the three parsers go.

## Semantics

- **Transitions.**
  - Draft → Published: *Publish stage*, refused while that stage's checks name a problem.
  - Published → Completed: by itself, once the stage's declared end has passed and every item is complete. Items done before the end leave it Published until then (Decision amended).
  - Published → Overdue: the end has passed with an item still open. It completes once that item is done.
  - Completed or Overdue → Published: an extension moves the end past now (Decision amended).
  - Published → Draft: *Revert to draft*, with a reason.
  - A stage may not be published before the one before it.
- **Revert while things are under way.** A reverted stage unlocks on Apply Desk's side only:
  - A gate whose Review Robin session has opened stays fixed (ruling 29).
  - Applications already submitted stay submitted.
  - The revert's confirm names both.
- **Locks.** One source decides them: `applydesk/locks.py`, which says for any part whether it is fixed and why. The pages read it, so Process, Form, Dossiers and Home never disagree (AD-04).
- **Sample statuses.**
  - `wa9juxbc2t`: stage 1 Completed (its form closed), stage 2 Completed (Shortlisting released), stage 3 Published (mid-interviews).
  - `k7mfr3pq8z`: stage 1 Completed, stage 2 Published.
  - The drafts: every stage Draft.
- **Time.** Status is the operator's act, not the calendar's. The timeline's Done/Now/Next stay date-derived, and the operator's part shows the status beside them.
- **Nothing is saved.** As every AD1 page, a transition changes the page only, saying so. AD2 stores the status and audits each transition.

## Judgment calls — decided

- The status lives on the stage (`Stage.status`), and the exercise's is derived. The `Exercise.state` string stays only for Closed and Archived until AD3.
- The locks go in a view adapter (`applydesk/locks.py`), not in each template's arithmetic, as `timeline.py` did for dates.
- A disabled control says why in its `title`, and each locked card says so once in a line, as the sent-gate note does today.

## Blast radius (measured)

Taken 2026-11-18 at `d6c20bdf8`.

- **Status reads:** `grep -rn "e.state\b\|exercise.state\|\.state == \"Draft\"\|state != \"Draft\"" applydesk --include=*.py --include=*.html | grep -v tests | wc -l` → 32 matches across 9 files: `extract.py`, `workflow.py`, `routes_operator.py`, `timeline.py`, `home_ops.py`, and the templates `operator/home.html`, `operator/_details.html`, `operator/_evaluations.html`, `me/application.html`.
- **The lock today:** `sent_attr` in `operator/_process_cards.html` (lines 148–213, the gate card only).
- **Publish checks:** `sample_data.setup_missing` (`applydesk/sample_data.py:956`).
- **Tests:** `applydesk/tests/test_pages.py`, `test_process*.py`, `test_form*.py`, `test_dossiers*.py`, `test_home_browser.py`.

## Status

- **Rung 2 built** (2026-11-18):
  - **Typed dates.** A stage's dates are typed (`stages.StageDates`, `span`), each a date and a time. The pages print them as before through `Stage.dates`. The timeline's text parser is gone, and so is `workflow`'s split. Process's two template splits wait for its date-time inputs at rung 3.
  - **Status.** `Stage.status` is Draft or Published on the sample, and `applydesk/locks.py` derives the rest: Overdue, Completed, the exercise's status, publish problems, each part's lock with its reason, and a revert's warnings.
  - **Rung 2a, item dates** (author, 2026-11-18): `Gate.when`, `Outcome.due_at` and `Stage.form_when`, each defaulting to the stage's through `stages.window`; `stages.date_problems` joins the publish checks.
  - **Rung 3 split in two**, so each half is checked in a browser alone: 3a the date-time inputs, 3b the status, Publish, Revert and the locks. A published stage's items are fixed by one fieldset each, after their dates; an opened gate's fieldset stays fixed through a revert. Publish lists the server's checks as the page loaded; only the "stage before it" line follows the page.
  - **Kept in `stages.py`.** `_exercise_span` still reads the two exercise fields, until those are typed at AD2.

## PR ladder

1. **Plan** (this file), its roadmap row and README row.
2. **The model:**
   - Stage start and end as typed date-times on the sample (AD-56), read by one helper; the free-text parsers go.
   - `Stage.status` on the sample stages, and `stages.stage_status`.
   - The exercise's status derived from its stages.
   - `applydesk/locks.py`: what each part's lock is, and its reason.
   - Tests only, no page change.
2a. **Item dates** (Decision amended): each item's typed dates, defaulting to its stage's; publish refuses one outside its stage, reversed, or an outcome due before its gates close. Tests only, no page change.
3. **Process:**
   - Each stage's status chip, with *Publish stage* and *Revert to draft* (with a reason), page-only, with confirms.
   - The stage's and its items' dates as date-time inputs; Publish refuses a stage without both.
   - A published stage's parts locked, reasons shown (AD-01, AD-02).
   - Publish checks the stage's Outline (AD-20).
   - Chromium tests.
4. **The other pages:**
   - The Form builder read-only when its stage is published (AD-03).
   - Dossiers' cells fixed for a published or opened gate (AD-04).
   - Blind review locked (AD-05).
   - *Released* gated on owed emails and undecided cells (AD-21).
   - Chromium tests.
5. **Home and the lobby:**
   - The Publish card per stage.
   - Statuses in the timeline's operator part and the lobby.
   - The exercise's derived status in the status row.
   - `diff-reviewer` reads rungs 2–5.
6. **Close**, after the author's browser check. The register's rows AD-01 to AD-05, AD-20, AD-21 and AD-56 are struck.

## Definition of done

- Every stage shows its status, and its transitions behave as Semantics says (tests, Chromium tests).
- A published stage's form, gates, outcomes and dates refuse change, each with its reason, on every page that shows them (tests).
- Publish names the stage's problems, and Release is gated (tests).
- The register's rows AD-01 to AD-05, AD-20, AD-21 and AD-56 are struck with this segment's PRs.
- Every stage's dates are typed date-times; Publish refuses a stage without them (tests).
- The author has used the pages locally and approved them.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1K` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~When blind review locks~~: when the first stage holding a gate is published (author, 2026-11-18).
- ~~When a stage completes~~: when all its items are, so there is no *Mark completed* (author, 2026-11-18).
- ~~Revert after a gate opened~~: allowed, the gate staying fixed (author, 2026-11-18).
- **`close_check.py` reads only RRW's `guide/`:** this close is checked by hand, as AD1G's to AD1J's.

## Out of scope

- **Saving and auditing transitions** (AD2).
- **Exercise Closed and Archived** (AD3).
- **Sending gates and reading results** (AD5).
- **The register's other themes**, in their own slices.

## Doc impact

- `applydesk/spec/applications.md` — a stage's status and transitions; what a published stage locks on each page; the per-stage Publish card; the release guard.
- `applydesk/guide/todo_master.md` — the AD1K roadmap row (rung 1), deleted at close.
- `applydesk/guide/findings_2026-11-18_assessment.md` — AD-01 to AD-05, AD-20, AD-21 and AD-56 struck at close.
- `applydesk/README.md` — this plan's row (rung 1), moved to the archive's index at close.
