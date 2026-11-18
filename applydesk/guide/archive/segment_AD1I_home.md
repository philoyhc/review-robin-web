# Segment AD1I — Apply Desk: Exercise Home, the timeline and Details

**Opened:** 2026-11-17 · **Theme:** Home rebuilt as a two-column page: a graphical timeline by stages that the applicant's page shares, beside a Details card unlocked to edit; nothing saved · **Related:** `applydesk/guide/todo_master.md` (rulings 14, 15, 28; the owed help contact and timezone editing), `applydesk/docs/home/`, `applydesk/spec/applications.md` ("Exercise Home")

## Opportunity

Home (`applydesk/templates/applydesk/operator/home.html`) is a stack of fact cards from AD1D: *Details*, *Who may apply*, *Review*, then *Where it stands*, *Counts* and *Next step*, with the summary as a lede. Nothing on it shows the exercise's shape, the stages Process lays out, or where today falls in them; the applicant's page (`applydesk/templates/applydesk/me/exercise.html`) shows three dates in a list. The details cannot be edited anywhere, which AD1G's carried rungs left owed for the help contact and timezone (`applydesk/guide/todo_master.md`).

## Decision

The author's, 2026-11-17, on two mock-ups (`applydesk/docs/home/`):

1. **Two columns**: the timeline two-thirds wide on the left, Details one-third on the right; one column on a phone, Details below.
2. **The timeline by stages, drawn**, from Process: each stage's name and dates, its gates as plain steps, its outcomes with their release or expected date, the form's close as a milestone, today marked. Nothing operator-only shows (panels, rules, pairs, modes), so **the same partial is the applicant page's timeline**.
3. **Two layouts, the viewer's to flip**: *Horizontal* (v1: a track whose stages take their share of the days, then a column per stage) and *Vertical* (v2: a date gutter, a spine through each stage's node, its items beside it), a switch on the card for anyone viewing it, operator or applicant, kept in their browser. It starts **Vertical on a phone or past four stages**, Horizontal otherwise; a viewer's own choice then holds.
4. **Details**, locked until *Unlock*, as Dossiers' table (ruling 23): Name, Exercise Code, **Description** (was *Summary*), Help contact, Timezone, Who may apply, Blind review. Unlocked, each is a field with a line saying where it is used; *Lock* keeps the changes, *Discard changes* drops them; *Unsaved changes* and the leave warning as Form's and Process's.
5. **The old cards go**: *Where it stands* and *Counts* fold into the status row (author) and the timeline (dates); **Next step** becomes a line under the timeline, said from where today falls (author).

Rejected: **the layout as the exercise's setting**, chosen by the operator for applicants: the author made it each viewer's, as Review Robin's table sorts are; an exercise's shape still picks the starting layout. **One fixed layout**: the vertical one holds more stages and items without compressing them, the horizontal one reads at a glance; neither serves every exercise.

## Decision amended (author, 2026-11-17, at the rung 2 check)

The horizontal layout is **one graphic, equal widths**: the bar's segments are the stages' column heads, one per stage, equal in width so each sits over its own column; the current one fills to today. The proportional track, its date scale and the separate row of numbered dots go (they said the same thing twice). A stage's length is its dates, under its name. Mock-up: `applydesk/docs/home/` (v3: three and five stages and a phone).

## Decision amended again (author, 2026-11-17, at the rung 5 check)

1. **The timeline in two parts**: above a rule, what participants may see (the partial the applicant's page draws); below it, the operator's: per stage, the form's state and counts, each gate's state, mode, evaluators, pairs and progress (linking to its Evaluations page), each outcome's state and counts (linking to Dossiers). The columns align across the rule (Horizontal); Vertical puts the operator's part on the right of each stage. Mock-ups `applydesk/docs/home/` (v4).
2. **Cards side by side share a height only when theirs are close**, as Review Robin's `is-equal-height` pairs: a short card beside a much taller one keeps its own height (author).

## Semantics

- **Stage state**: *Done* when its last date has passed (the Applications stage reads *Closed*), *Now* when today falls within it, *Next* otherwise; a stage with no dates is *Next* and says its dates are not set. Today is the sample's (17 Nov 2026) until AD2.
- ~~**Proportion** (Horizontal): a stage's share of the days~~: equal widths (Decision amended). Today's place in the current stage is its share of that stage's days, in either layout.
- **Items**: the form as *You · Apply online*, and its close as a milestone; each gate as a *Step* in Process's order, named by its name (a gate with no name: *A step*); each outcome by name with *released <date>* or *expected <expected outcome>*; outcome values listed only once released.
- **Shown to applicants**: Process's per-stage *Shown to applicants* is not modelled yet (a static box); until it is, every stage shows. A hidden stage, when it is, is left out of the applicant's timeline and marked on the operator's.
- **The switch**: `localStorage` `applydesk-timeline` (`h` / `v`), one choice for every exercise; storage blocked, the starting rule applies.
- **Next step**: from today's stage and the exercise's state, e.g. *Now: Interviews. Next: Selection, expected December 2026; Gate 3's pairs are approved on Evaluations*; a draft says what setup is missing (today's *Next step* list, `sample_data.setup_missing`).
- **Status row** gains what *Counts* held: *Applications: 100 submitted · 3 drafts*; panels are Panels' to count.
- **Details unlocked**: an Exercise Code that clashes with another exercise's is refused, saying whose; an empty Name is refused; the timezone from a short list (the operator settings' default first). A published exercise's Code and Who may apply are fixed (the Lock refuses them), as published changes wait for G2.

## Judgment calls — decided

- The timeline is a view adapter (`applydesk/timeline.py`), not the template's arithmetic: both pages and the tests read one shape.
- The switch is a two-option segmented control (*Horizontal* / *Vertical*), as Light / Dark in the header.
- *Description* renames the field everywhere it is shown (lede, Details, `setup_missing`), not the Python attribute until AD2 (`Exercise.summary`).

## Blast radius (measured)

Taken 2026-11-17 at `696b14d9b`.

- Templates: `operator/home.html` (48 lines, replaced), `operator/_details.html` (replaced by the Details card), `me/exercise.html` (its Timeline card); `grep -rln "Where it stands\|Next step\|_details.html\|#details" applydesk/templates` → 2 files.
- Tests: `applydesk/tests/test_pages.py` (the `#details` links, lines 489–491; Home's facts); `grep -rln "Where it stands\|Counts" applydesk/tests` → 1.
- Code: `routes_operator.exercise_home`, `workflow.status_row`, `sample_data.setup_missing`; new `applydesk/timeline.py`.
- Spec: `applydesk/spec/applications.md` "Exercise Home" (line 178).

## Status

Closed 2026-11-18 after the author's browser check. Rungs 1–5 and 5a shipped as the ladder says, with the two amendments above; each rung's cold-read fixes are in its PR.

- **Diverging from Semantics**: a draft's missing setup stays a *Publish* card under the columns, and its Next step line says what a draft's timeline is; the lede goes from Home (the description is in Details) but stays on the applicant's page; a stage holding the form reads *Closed* when done; Home goes to one column under 900px, the phone breakpoint (639px) deciding only the starting layout and where the operator's part sits.
- **Decisions confirmed at build**: today and the state chips show on the applicant's timeline too; an outcome's operator row takes Dossiers' tally and the Workflow card's *Released* / *Pending*; cards stay blocks when stretched; *Go to Evaluations* is `timeline.gate_running`'s; Lock's changes stay in the card until AD2.
- **Reads**: three `diff-reviewer` reads (rung 2's, rungs 2–5 cumulative, rung 5a's); no blocker; their fixes landed in the rung read.
- **Left**: a sample's canned gate progress beside counted pairs (`k7mfr3pq8z`), until AD2; *Shown to applicants* per stage not modelled (every stage shows).

## PR ladder

1. **Plan** (this file), the two mock-ups in `applydesk/docs/home/`, the README rows, the roadmap row.
2. **Scaffold**: Home in two columns; the timeline (`applydesk/timeline.py`) drawn Horizontal from the sample; Details locked with an inert *Unlock*; the old cards gone, the status row's applications line, the Next step line. Server-rendered; no switch.
3. **The two layouts**: Vertical, the switch, the starting rule, kept per viewer. Chromium tests.
4. **Details unlocked**: edit in place, *Lock* / *Discard changes*, the unsaved marker and leave warning, the refusals. Chromium tests.
5. **The applicant's timeline**: `me/exercise.html` uses the partial, nothing operator-only in it (tests on what it must not show). `diff-reviewer` reads 2–5.
5a. *(added at the rung 5 check)* **The operator's part and equal heights** (Decision amended again). Its own `diff-reviewer` read.
6. **Close**, after the author's browser check.

## Definition of done

- Home is two columns: the timeline and Details (tests, Chromium tests).
- The timeline draws every stage, its steps and outcomes, today, in either layout; the switch and the starting rule hold (Chromium tests).
- Details edits in the browser behind *Unlock*, refusing what Semantics says (Chromium tests).
- The applicant's page shows the same timeline and nothing operator-only (tests).
- The author has used the pages locally and approved them.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1I` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~Today and the state chips on the applicant's timeline~~: shown (author, rung 5 check).
- **A stage hidden from applicants**: later, with Process's *Shown to applicants*; every stage shows until then.
- ~~`close_check.py` reads only RRW's `guide/`~~: this close checked by hand, as AD1G's and AD1H's.

## Out of scope

- **Saving** any of it (AD2); the sample's details change on screen only.
- **Extract data**: its own segment, after this.
- **Publishing a changed exercise** (G2).

## Doc impact

- `applydesk/spec/applications.md` — "Exercise Home": the two columns, the timeline and its layouts, its operator's part (rung 5a), equal heights when close, Details unlocked, the Next step line; the URL map's Home line; the applicant's exercise page's timeline (at close).
- `applydesk/guide/todo_master.md` — the AD1I roadmap row and the owed help contact and timezone editing (rung 1); deleted at close.
- `applydesk/README.md` — this plan's row and `docs/home/` (rung 1), the plan's row moved to the archive's index at close.
