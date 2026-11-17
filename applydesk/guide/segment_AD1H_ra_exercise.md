# Segment AD1H — Apply Desk: the RA model exercise, richer rules and a page per gate

**Opened:** 2026-11-17 · **Theme:** the model exercise rebuilt as a residential assistants' recruitment (ruling 30), the rules it needs, and Evaluations scaled to a gate of 3,000 pairs; nothing saved · **Related:** `applydesk/guide/todo_master.md` (rulings 13, 21, 27, 29, 30), `applydesk/guide/segment_AD1G_evaluators.md` (paused at rung 6b for this), `applydesk/spec/applications.md`

## Opportunity

The model exercise (`wa9juxbc2t`, an undergraduate research fellowship) was built page by page and tests nothing at scale: its largest gate has 92 dossiers and 2 evaluators each. The author's real case (2026-11-17) is a residential assistants' recruitment where one gate pairs **30 peer reviewers with every one of 100 applicants**: about 3,000 pairs, which Evaluations' one card per gate (AD1G rung 5) cannot show. Its rules also outrun the engine (`stages.Rule`: conditions all of which must hold, one value then, one otherwise):

- Shortlisting has **three** values, current RAs to re-appointment and new applicants to interview, so it needs **branches** and a condition on a **form answer**;
- Selection takes **the best 20** interview scores, plus everyone in re-appointment;
- Gate 1's score runs 0–5 where **0 is *Don't know***, which a plain mean counts as the worst score.

## Decision

**Rebuild the model exercise as the author's RA recruitment, mid Stage 3; give rules ordered branches, a form-answer condition and a best-N condition; let a mean ignore 0; give each gate its own page under Evaluations, paged.** Ruling 30 records it.

1. **The exercise**, *Recruitment and Selection of Residential Assistants* (same public ID, so its URLs hold):
   - **Stage 1, Applications**: the form's usual fields, *Currently an RA?* among them; one application per applicant; 100 submitted, 20 of them current RAs. No nominations (author: dropped for this sample).
   - **Stage 2, Review**: **Gate 1 *Peer review***, panel *Current RAs* (30), every member reviewing every applicant but themselves; fields *Score* 0–5 required (*0 = Don't know enough about this candidate*), *Comment* optional; result *Mean score, ignoring 0*. **Gate 2 *Office checks***, panel *Office staff* (5), every member reviewing every applicant; fields *Concerns* (*No concerns*, *Minor concerns*, *Major concerns*) required, *Comment* optional; result *Share choosing Major concerns*. **Outcome *Shortlisting***: mean ≥ 3.5 and no one choosing *Major concerns* → *Re-appointment* for a current RA, *Interview* for a new applicant; else *Not shortlisted*. Applied as a proposal, the operator approving (as now). Decided and released: 15 to re-appointment, 40 to interview.
   - **Stage 3, Interviews**: **Gate 3 *Staff interview***, panel *Residential staff* (13), two interviewers per applicant, load spread, *Suggested, then approved*; fields *Score* and *Comment*, both required. Entered: the 40; **not yet sent**, its pairs being approved (ruling 29's mid-stage). **Outcome *Selection***: *Selected* for re-appointment, and the best 20 by interview mean; else *Not selected*. Pending. The pool is 35; the final 30 by allocation, offline.
2. **Rules** (`stages.Rule`, Process's rule editor, Dossiers' *Apply rules*):
   - **branches**: *if … then A; else if … then B; … else Z*, the first branch whose conditions all hold deciding; a one-branch rule reads as today;
   - **a form answer** (`("form", question, "is", value)`), on a *List* question of the form;
   - **the best N** (`("top", "gate.result", "le", "20")`): among the dossiers this branch reaches, the N with the highest result; ties at the cut all go in, and say so.
3. **A mean ignoring 0**: a numeric result's option, *ignoring 0*, for a scale whose 0 means *no view*; its note counts the scores taken (*3.9 from 26 of 30*).
4. **A page per gate under Evaluations**, `…/exercises/<id>/evaluations/gate_<n>`: Evaluations keeps its Gates table and, per gate, a short card (mode, counts, the load line) linking to it; the page holds the assignments table, **200 rows a page** with a pager as Review Robin's rosters (`app/web/templates/operator/partials/_pager_cluster.html`), and a filter by candidate or evaluator. AD1G rung 6b wires the operations there.

**Rejected:**
- **Keeping two-valued rules and deciding the rest by hand.** The author wants the app to suggest each decision (2026-11-17); hand-set columns would hide the rules the sample exists to exercise.
- **A second exercise beside the fellowship.** The fellowship's shape is AD1C–AD1G's scaffolding, not a case anyone runs; one model exercise keeps the pages and their tests honest.
- **Every pair in the card, collapsed.** 3,000 rows in one page's DOM is slow to draw and useless to scan; the gate page pages them.
- **Sorting the best N on Dossiers by hand.** A ranking is what the operator would otherwise do in a spreadsheet; the rule proposes it, the operator approves.

## Semantics

- **Branches** are tried in order; the first whose conditions all hold gives its value; none holding gives *else*. An unfinished result makes the rule wait (no proposal), as today.
- **A form answer** reads the application as submitted; a question renamed or removed on Form leaves the condition a problem on the Outline.
- **Best N** ranks among the dossiers reaching that branch with a finished result; fewer than N takes them all; a tie at the cut takes every tied dossier (the proposal says *21 at the cut of 20: tied*).
- **Ignoring 0**: a dossier whose every score is 0 has no result (*No view from 30*), and a rule waits on it.
- **The gate page** reads the same `stages.assignments` as the card; paging and the filter are the page's query string, so a link keeps them. A page past the last clamps to the last.
- **Self-review**: a panel member never gets their own application (`stages.fill`'s candidate rule, by email); Gate 1's 20 current RAs get 29 reviewers, the rest 30, so its Total is 29–30.

## Judgment calls — decided

- **Same public ID** (`wa9juxbc2t`): the author's URL names it; every link and bookmark holds.
- **Branch values are the outcome's values**; a gate's entry rule keeps *Entered* / *Not entered* and may branch too.
- **A few drafts and one withdrawal** stay in the sample beyond the 100 submitted, so Applications still shows those states; none is entered at a gate.
- **The fellowship's two written applications** (*Aisha Bello*, *Kenji Russo*) and their assessors go with it; the other sample exercises keep theirs.

## Blast radius (measured)

Taken 2026-11-17 at `4c2efddba`.

| What | Count | Command |
|---|---|---|
| The model and sample | 1,087, 842 lines | `wc -l applydesk/stages.py applydesk/sample_data.py` |
| Lines reading a rule's `when`, `then`, `otherwise` outside tests | 37 in 6 files | `grep -rn "\.when\b\|\.then\b\|\.otherwise\b\|otherwise" applydesk --include=*.py --include=*.html \| grep -v tests \| wc -l` |
| Test files naming the model exercise | 21 | `grep -rln "wa9juxbc2t\|URF-2027\|Undergraduate" applydesk/tests --include=*.py \| wc -l` |
| Apply Desk tests | 274 functions | `grep -c "def test" applydesk/tests/*.py` |
| Evaluations' template | 79 lines | `wc -l applydesk/templates/applydesk/operator/_evaluations.html` |

## Status

- **Rung 2 built** (2026-11-17): `stages.Rule` gains `more`, further branches after the first (`Rule.branches`); `rule_text` reads them (*…; else if … → B, else Z*), and the `form` and `top` conditions; `rule_json` adds `more` only when there are some, so Process's editor reads a one-branch rule as before. Dossiers' *Apply rules* takes the branches in order, a form answer from each row's answers (`sample_data.answers`, a choose-one *List* question's option, seeded), and the best N: ranked among the dossiers the branch reaches whose other conditions hold, a hand-set or decided cell ranked too though only the cells the options allow are proposed; one not entered at the gate takes no place; the branch waits while any of them lacks a result; ties at the cut all taken, the proposal saying so.
- **Rung 3 built** (2026-11-17): Process's rule editor in branches: *+ Else if* adds one (a blank condition, the first value), *Remove branch* drops it, a branch whose last condition goes is dropped; each branch its own *+ Condition* and *Then*, the rule one *Otherwise*. A form answer (either column; the form's choose-one *List* questions, `sample_data.list_questions`) and the best N (an outcome's; its numeric results in scope, *How many*) as kinds; the Outline names a question no longer on the form, an answer not among its options, a best N not a whole number or ranking by a result that is not one. A replica's rules rename their gate keys in every branch.
- **Reads, rungs 2–3**: `diff-reviewer` on `9f9cc1faa..433b15858`, three faults in the best N, all fixed in rung 2's PR: a ranking went ahead without a dossier whose other condition there, or an earlier branch, could not be judged yet (either might outrank the rest); one not entered at the gate was named as waiting; the tie note's wording. Rung 3 took the test gaps it named (a tie, a ranking that waits, *Remove branch* and its focus, a replica's branched rule) and labels a later branch's controls with its number. Parity of the new kinds' rule lines rides on rung 6's sample, whose rules branch.
- **Rung 4 built** (2026-11-17): `GateResult.ignore_zero`, offered on a mean or median (*Ignoring 0 (no view)*, beside *Derived as*); the summary reads *Mean, ignoring 0* on the server and in the script; `stages.averaged` gives the value and how many it took, all 0s giving none. The note on Dossiers (*3.9 from 26 of 30*) comes with the sample (rung 6).

## PR ladder

1. **Plan** (this file), ruling 30, its README row, the roadmap row; AD1G's Status notes the pause.
2. **Rules: the model.** `stages.Rule` as branches; the `form` and `top` conditions; `rule_text`, `rule_json` and Dossiers' *Apply rules* reading them; the server's tests. The current sample's rules unchanged in effect. Must not change Process's editor.
3. **Rules: the editor.** Process's rule editor adds and removes branches and offers the two conditions; the Outline's problems for them. Chromium tests. `diff-reviewer` reads 2–3.
4. **A mean ignoring 0**: the result option on Process, the derivation, its note. Chromium tests.
5. **The gate page, scaffold.** The route, Evaluations' short cards linking to it, the table paged 200 with its pager and filter, on the current sample; operations inert.
6. **The RA exercise.** The sample replaced as the Decision lays it out: exercise, applications, form, panels, stages and rules, rows mid Stage 3, gate states, emails, responses; every test that named the fellowship moved to it. May split in two (people and form; stages and rows) if the diff reads better so. `diff-reviewer` reads 4–6.
7. **Close**, after the author's browser check. AD1G resumes at rung 6b on the gate page.

## Definition of done

- The model exercise is the RA recruitment, mid Stage 3, with the counts the Decision gives (tests).
- A rule branches, reads a form answer and takes the best N, on Process and in *Apply rules* (tests, Chromium tests).
- A mean may ignore 0 (tests).
- Each gate has its page, paged 200 and filtered (tests, Chromium tests).
- The author has used the pages locally and approved them.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1H` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **The form's usual fields**: the plan proposes name and email from sign-in, then *Preferred name*, *Matriculation number*, *Year of study*, *Faculty*, *Currently an RA?*, *Residence*, *Why you want to be an RA*, *Relevant experience*, *Photo*; the author's at the rung 6 check.
- **Ties at the best-N cut**: all tied go in, proposed; the author's at the rung 3 check.
- **`close_check.py` reads only RRW's `guide/`**: this close is checked by hand, as AD1F's and AD1G's.

## Out of scope

- **AD1G rung 6b**, the operations on the gate page: AD1G's, after this.
- **Allocation** of the final 30 from the 35 (offline, the author).
- **Sending and saving** (AD6, AD2).

## Doc impact

- `applydesk/spec/applications.md` — "The Process page": a rule's branches and its form-answer and best-N conditions; a result's *ignoring 0*; "The Evaluations page": the gate page, its pager and filter; the model exercise named where the spec cites it (at close).
- `applydesk/guide/todo_master.md` — ruling 30 and the AD1H roadmap row (rung 1); the row deleted at close.
- `applydesk/README.md` — this plan's row (rung 1), moved to the archive's index at close.
