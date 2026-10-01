# Post-assessment register — 1 October

**Opened:** 2026-10-01, on the browser-test plan's close
(`guide/archive/browser_test.md`) · **Related:**
`guide/codebase_assessment_30sep.md` §5 and §8,
`guide/codex_assessment_30sep.md` §8.

The most important immediate work, logged in one place on the author's
instruction. **A register, not a plan:** each entry says what is wrong,
where, and how to tell it is done. An entry the author picks up becomes its
own PR, or a plan if it needs one (the `segment-plan` skill's "When not to
write a plan"). Entries are struck when done, not deleted, with the PR that
did it.

Counts taken 2026-10-01 at `c4b084c0`.

## E1 — Create can't submit without JavaScript

**What is wrong.** `app/web/templates/operator/session_new.html` renders
Create session with `disabled` and `aria-disabled="true"`, and only its
inline script enables it once Name and Code are filled. With JavaScript off,
Create can't submit at all. This has been true since `9cfb70e1`
(2026-05-22). Found by `guide/archive/browser_test.md` rung 5, while
automating `guide/post_azure_todo_checklist.md` item 5's "Create is
unchanged … Off" row.

**The records disagree with it.** `spec/session_owners.md` describes a
no-JS Create: its "Without JavaScript" paragraph says the picker's one
address "submits with **Create session**", and its behavior table's
Without JavaScript row says the same for Create. A comment in
`session_new.html` describes the same path.

**Do.** Render the button enabled and let the script disable it, so the
page degrades rather than locks. The server already refuses a missing Name
or Code. Add a no-JS Create test to `tests/browser/test_tags_and_create.py`
that stages nothing, submits, and lands on Session Home.

**Done when.** The no-JS test passes. Item 5's Off row is checked by that
test. `spec/session_owners.md` and the template comment describe what ships.
One code PR.

## E2 — "A refused parent keeps the text": test it, reword the row

**What is wrong.** `guide/post_azure_todo_checklist.md` item 6's row says to
type an out-of-range parent value "in that preview" and Save. Neither half
can happen:

- **The operator preview can't save at all.** It renders a `<div>`, not a
  form (`app/web/templates/reviewer/review_surface.html:203`).
- **On the reviewer surface, the browser refuses first.** The number input
  carries `min`/`max`, so Chromium's own validation stops an out-of-range
  Save. An off-grid value meets the inline step check
  (`setCustomValidity`). `maxlength` and the List `<select>` cover String
  and List fields.

The server's held answer ("Kept until {parent} is fixed.",
`app/services/responses/_core.py`) is real and covered at the service level
by `tests/integration/test_response_field_branching_rule.py`. A browser
reaches it only past those checks:

- **An Integer parent with Step cleared.** No `data-rs-step` means no
  script check, and the input uses `step="any"`, so 2.5 reaches the server,
  which refuses any non-whole Integer.
- **JavaScript off,** for any off-grid value.

**Do.**
1. Confirm in the builder that an Integer field's Step can be left blank.
2. Add a reviewer test to `tests/browser/test_reviewer_branching.py`: an
   Integer parent with no Step, 2.5 in the parent and text in its governed
   field, Save. Both come back with their text, and the governed one reads
   "Kept until … is fixed.".
3. Reword the checklist row to that sequence, on the reviewer surface
   rather than the preview.

If step 1 finds Step can't be blank, the row reduces to the no-JS case; say
so in the PR.

**Done when.** The test passes, the row describes something a person can do,
and `guide/archive/browser_test.md`'s "not automated" list is overtaken by
this entry. One code PR.

## E3 — A comprehensive code-vs-spec sweep

**Why now.** The corpus sweep is due by merges:
`python3 tools/close_check.py --stale` reports 615 merges since the last
one, against a trigger of 500 (`guide/sweep_2026-09-05_spec-docs.md`,
26 days of 56 elapsed). Since that sweep `app/` changed in 199 files
(+26,808 / −6,550), and 19T rebuilt the Instruments page, the reviewer
surface and the instrument model under `guide/advanced_instruments.md`.
Both assessments found specs a state behind that survived item closes
(`guide/codebase_assessment_30sep.md` §5, "The records went stale faster
than the work, again"). This sweep reads every spec against the code, not
against its own plan.

**Scope.** The 39 live specs in `spec/` (25,119 lines with the README), the
19 top-level `docs/`, and the root practice documents. Every spec is read
against the code it describes: routes, services, templates and CSV
contracts. Also folded in: `guide/codex_assessment_30sep.md` §8 move 6,
roadmap stubs naming already-closed segments.

**How.** By `guide/sweep_template.md` (entry points 1–5, one line per file),
recorded as a dated corpus sweep in `guide/`. Divergences the sweep does
not fix go to a dated findings register, because a sweeper may not quietly
rewrite a spec to match the code (`rrw_sdd_in_practice.md` §4). The reading
can be split by area across `spec-writer` passes in verify mode, which
report rather than re-align. The fixes ship afterwards, as ordinary PRs.

**Done when.** The sweep record exists with `<!-- sweep-scope: corpus -->`,
`--stale` reads "not due", and every finding is either fixed or carried in
the register with who decides it.

## E4 — Prepare's 13 seconds, without feedback

**What is wrong.** Prepare takes about 13 s at 200 × 200 with nothing on
screen while it runs (`guide/codebase_assessment_30sep.md` §5; measured in
`guide/app_responsiveness.md`). 19S Item 3 halved it from 26.7 s.
The assessment leaves open whether it wants another pass or a progress
indicator.

**Do.** The author decides which. A progress indicator is the smaller
change; another pass would remove the third materialization and is
measured with `tools/bench_roster_scale.py`.

**Done when.** That decision is recorded in `guide/app_responsiveness.md`,
and whichever was chosen has shipped or been scheduled.

## Not here

- **The NUS deployment and email.** These are external and blocked
  (`docs/nus_azure_status_v7.md`, Segment 14B). Nothing in this register
  shortens them.
- **The builder-script extraction.** This waits for its trigger
  (`guide/codebase_assessment_30sep.md` §8 move 3).
- **Freezing instrument scope.** This is a rule for future requests, not a
  task (§8 move 2).
- **Hand checks the browser tests left.** These are listed in
  `guide/archive/browser_test.md`'s `Status`. They stay hand checks, except
  where E1 and E2 overtake them.

## Order

E1 and E2 first: each is one small code PR, and each closes a checklist row
that cannot pass as written. E3 next, since it is due and large; it should
start after E1 and E2 so their spec edits are in the tree it reads. E4 waits
on the author's ruling.
