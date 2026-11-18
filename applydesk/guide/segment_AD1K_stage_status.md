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
   - **Mark completed** ends it, locking its results as well.
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
   - **The stage itself:** its dates, and its deletion.
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

## Semantics

- **Transitions.**
  - Draft → Published: *Publish stage*, refused while that stage's checks name a problem.
  - Published → Completed: *Mark completed*, offered once the stage's outcomes are released, or once its form has closed for a form stage.
  - Published → Draft: *Revert to draft*, with a reason.
  - Completed is final in the MVP.
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

## PR ladder

1. **Plan** (this file), its roadmap row and README row.
2. **The model:**
   - `Stage.status` on the sample stages, and `stages.stage_status`.
   - The exercise's status derived from its stages.
   - `applydesk/locks.py`: what each part's lock is, and its reason.
   - Tests only, no page change.
3. **Process:**
   - Each stage's status chip, with *Publish stage*, *Mark completed* and *Revert to draft* (with a reason), page-only, with confirms.
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
6. **Close**, after the author's browser check. The register's rows AD-01 to AD-05, AD-20 and AD-21 are struck.

## Definition of done

- Every stage shows its status, and its transitions behave as Semantics says (tests, Chromium tests).
- A published stage's form, gates, outcomes and dates refuse change, each with its reason, on every page that shows them (tests).
- Publish names the stage's problems, and Release is gated (tests).
- The register's rows AD-01 to AD-05, AD-20 and AD-21 are struck with this segment's PRs.
- The author has used the pages locally and approved them.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1K` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **When blind review locks.** At the first stage holding a gate being published (proposed), or at the exercise's first stage? The author's: ruling 35 says "at publish of stage".
- **When *Mark completed* is offered.** Once the stage's outcomes are released (proposed), or freely? The author's.
- **Revert after a gate opened.** Allowed with the gate staying fixed (proposed), or refused? The author's.
- **`close_check.py` reads only RRW's `guide/`:** this close is checked by hand, as AD1G's to AD1J's.

## Out of scope

- **Saving and auditing transitions** (AD2).
- **Exercise Closed and Archived** (AD3).
- **Sending gates and reading results** (AD5).
- **The register's other themes**, in their own slices.

## Doc impact

- `applydesk/spec/applications.md` — a stage's status and transitions; what a published stage locks on each page; the per-stage Publish card; the release guard.
- `applydesk/guide/todo_master.md` — the AD1K roadmap row (rung 1), deleted at close.
- `applydesk/guide/findings_2026-11-18_assessment.md` — AD-01 to AD-05, AD-20 and AD-21 struck at close.
- `applydesk/README.md` — this plan's row (rung 1), moved to the archive's index at close.
