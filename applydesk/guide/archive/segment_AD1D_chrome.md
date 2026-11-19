# Segment AD1D — ApplyDesk: the exercise's chrome and Workflow card

**Opened:** 2026-11-13 · **Theme:** an exercise's pages laid out as the operator's workflow: Home, a Setup row, an Operations row, and a Workflow card that steps through the timeline one item at a time; the pages as scaffolds, nothing saved · **Related:** `applydesk/guide/todo_master.md` (rulings 13, 14), `applydesk/guide/archive/segment_AD1C_applications.md` (the Applications page), `spec/operator_ui_concept.md` (Review Robin's chrome, which this follows)

## Opportunity

An exercise has seven tabs in one row (Home, Setup, Form, Applications, Panels, Review, Reports), laid down in AD1 before the evaluation model existed. With Forms (AD1B) and Applications (AD1C) firmed up, the author walked the operator's workflow on 2026-11-13: create the exercise; set up the form, gates and their panels, emails, on a timeline; open the form; watch applications come in; send each gate and take its results back; decide and release each outcome; close and archive. Steps 1–5 are setup, 6–10 operations, as in Review Robin. The single row does not show that split, and three tabs (Setup, Panels, Review) no longer match what they will hold.

## Decision

**Review Robin's chrome, with ApplyDesk's pages** (author, 2026-11-13; ruling 14; mock-up `applydesk/docs/chrome/home.png`):

```
┌────────┬─ SETUP ▶      [Process][Form][Gates][Emails]
│  Home  │
└────────┴─ OPERATIONS ▶ [Applications][Evaluations][Extract data]
```

1. **Home**: the exercise's details, the Workflow card, owners, the danger zone (close and archive).
2. **Setup**: **Process** (rounds, gates placed in them, outcomes — *stages since ruling 15* — dates, every rule, what a release does), **Form** (AD1B), **Gates** (one card per gate: its panel roster, what the panel sees, how it is run, its result's measure), **Emails** (*since ruling 16, every template Process makes owed, to applicants and panel evaluators*; the one place the templates to applicants are kept: the receipt, reminders before the form closes, a notice per outcome; Process says which steps send one, and when).
3. **Operations**: **Applications** (AD1C, the control surface), **Evaluations** (each gate's progress and results from Review Robin), **Extract data**.
4. **Styled as Review Robin's** (author, 2026-11-13): a card under the breadcrumb (*Exercises / name*); *Exercise Home* double-height on the left; uppercase row labels with a triangle; in ApplyDesk's rose rather than Review Robin's blue and green (author: the favicon's color), the Setup row a stronger rose, the Operations row a paler one, the tabs sharing each row's width; the active tab white with its row's underline.
5. **A status row** inside that card, under the tabs, on every page: the exercise's state, then the form, gates, outcomes and emails at a glance.
6. **The Workflow card** on Home and every Operations page: the timeline as a stepper, each item with its state; the one due next carries its action; one not ready says why.

**Rejected:**
- **One tab per gate**: the chrome would change length with each exercise; one Gates tab with a card per gate keeps it stable, as Review Robin's Instruments page does.
- **Panels as its own tab**: a roster means something only for its gate; it is a card on the gate, with *Copy from* another gate for reuse.
- **A gate's entry rule on its Gates card**: every rule reads the flow (status, last submitted, earlier outcomes), so all rules sit on Process.
- **"Timeline" or "Process flow"** as the tab's name: *Timeline* undersells the rules, *Process flow* is long for a tab.
- **One lifecycle that locks Setup**, as Review Robin's does: the form opens while later gates are still being set up.

## Semantics

- **Each item has its own state** (ruling 14): the form *Draft → Open → Closed*; a gate *Not ready → Ready → Sent → Results in*; an outcome *Pending → Decided → Released*; then the exercise *Closed*, *Archived*.
- **Locking is per item**: the form's questions lock when it opens; a gate's setup locks when it is sent; an outcome's rule locks when it is released. Anything not yet live stays editable, so a later gate is set up just in time.
- **The Workflow card's order is the timeline's**: each round's (*stage's*, ruling 15) form, gates and outcomes in their set order, then close; the form sits where its stage does (rung 5). *Next* is the earliest item not yet done; an item can be acted on only when the ones it reads are done.
- **No Validate tab**: an item checks itself when it is about to go live, and what blocks it shows on its step ("Not ready: no email for this outcome").
- **Lifecycle states don't hide pages**: a Setup page whose item is live shows it locked; an Operations page before anything is live shows its actions disabled.
- **Old addresses**: `/setup`, `/panels`, `/review` and `/reports` are placeholders nothing depends on; they go, and their content moves to the page that now owns it.

## Judgment calls — decided

- **The Workflow card reads `applydesk/stages.py`** (then `rounds.py`) for the model exercise, so it agrees with Applications; the other exercises get a shorter timeline from their own sample.
- **Steps are columns, grouped by stage** (by round before ruling 15), as the Applications table's headers are: the same groups in the same order on both.
- **The status row replaces the heading's chips** (state, stage) on exercise pages, and the page's `h1` is the page's name (the exercise's on Home), the exercise's name moving to the breadcrumb (*Exercises / name / page*, as Review Robin's). Review Robin's Setup and Operations pages carry no `h1`; ApplyDesk keeps one, as its pages always have (a deliberate difference). The lobby keeps its chips.

## Blast radius (measured)

Taken 2026-11-13 at `bf44ce575`.

| What | Count | Command |
|---|---|---|
| Modules building the tabs | 2 | `grep -rln "exercise_tabs" applydesk --include=*.py` |
| Operator sections in `SECTIONS` | 6 | `sed -n 19,26p applydesk/routes_operator.py` |
| Operator templates | 14 | `ls applydesk/templates/applydesk/operator/ \| wc -l` |
| Page tests | 32 | `grep -c "def test" applydesk/tests/test_pages.py` |
| Test files naming a retired section | 4 | `grep -rln "panels\|/review\|reports\|/setup" applydesk/tests --include=*.py` |

## Status

Closed 2026-11-19. Rungs 1–6 shipped. The Workflow card (rung 3) was removed on 2026-11-15 (author: derivative of the other pages, it can wait), so Decision item 6 and its Definition of done line record what was built, not what stands.

- **Diverging from the Decision**: Gates folded into Process and Panels came back in its slot (ruling 20), so the Setup row is Process, Form, Panels, Emails; Applications became Dossiers (ruling 25); rounds became stages (ruling 15), the form's stage `Stage.form`. The Workflow card's steps stay as `workflow.steps`, a contract the spec records under "The Process page"; the lobby's *Stage* column reads `workflow.current_stage`.
- **Decisions confirmed at build**: the status row replaces the heading's chips; the `h1` is the page's name and the exercise's name moves to the breadcrumb, keeping an `h1` where Review Robin has none (a deliberate difference); an outcome is optional and the form's stage may sit anywhere (rung 5).
- **Reads**: rungs 1–3 cumulative (`bf44ce575..`), 13 findings, none blocking; rung 4, 8 findings; rung 5, 6 findings; all fixed.
- **Close**: checked by hand; `spec-writer` not run.

## PR ladder

1. **Plan** (this file), ruling 14, the mock-ups, the README and roadmap rows.
2. **The chrome scaffold.** The two rows and the Home anchor; the status row; the routes `process`, `gates`, `emails`, `evaluations`, `extract`, each a placeholder with its cards as static copy (Gates takes Panels' content, Extract data takes Reports'); `setup`, `panels`, `review`, `reports` removed. Tests: the rows and their order, each page renders, the old addresses 404. Must not touch the Form or Applications pages' bodies.
3. **The Workflow card, static.** Drawn from the sample's timeline on Home and the Operations pages, each step's state and line, the next item marked, a not-ready reason; its buttons inert. Tests: the steps follow the sample in order; *Next* is the right one. Last build rung: `diff-reviewer` reads the cumulative diff.
4. **Iteration rungs**, as the author's browser checks ask.
5. **Close.**

## Definition of done

- The chrome shows Home, then Setup (Process, Form, Gates, Emails), then Operations (Applications, Evaluations, Extract data), on every exercise page (test).
- `/setup`, `/panels`, `/review`, `/reports` are 404 under an exercise (test).
- The Workflow card on Home and each Operations page lists the model exercise's form, gates, outcomes and close in timeline order, with *Next* on Gate 3 (test).
- The author has used the pages locally and approved them.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1D` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~**What each Workflow step's action does**~~: inert, then the card was removed.
- ~~**Outcome emails**~~: kept on Emails, Process setting which steps send one (ruling 16).
- **What a gate before the form evaluates**: open, in `applydesk/guide/todo_master.md` "Open decisions".
- ~~**`close_check.py` reads only RRW's `guide/`**~~: checked by hand (Status).

## Out of scope

- **Building out Process, Gates, Emails, Evaluations and Extract data**: each is its own segment after this one (roadmap), Process first since Applications already reads its rules.
- **Saving anything**, and the real link to Review Robin: AD2 and AD6.
- **The lobby** (the exercises list): unchanged, but for its Stage column, worked out since rung 4 (ruling 15).

## Doc impact

- `applydesk/spec/applications.md` — "The URL map": the operator pages renamed and regrouped (rung 2).
- `applydesk/guide/archive/segment_AD1_skeleton.md` — its URL map's operator rows follow (rung 2).
- `applydesk/guide/todo_master.md` — ruling 14 and the roadmap rows (rung 1); this row deleted at close. Ruling 15 and the AD1E roadmap row (rung 4).
- `applydesk/README.md` — this plan's and the mock-ups' rows (rung 1), moved to the archive's index at close.
