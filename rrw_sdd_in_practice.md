# Review Robin Web — Spec-Driven Development in Practice

## 1. Introduction

Review Robin Web (RRW) is a web application for running structured institutional review cycles. `rrw_design_rationale.md` explains what it *is* and why it looks the way it does. This document is its companion on a different axis. It explains how RRW is *worked on*: the practice by which a single author, working through AI coding agents with no local dev loop, has landed some two thousand six hundred pull requests without the codebase taking the shape that AI-authored codebases are reported to take.

The practice has a name now. Through 2026 the term **spec-driven development** (SDD) went mainstream for the family of methods in which specifications are the durable source of truth and code is kept in agreement with them. RRW was doing a form of this before the term went mainstream. More usefully for a reader, it is doing a *particular* form of it, with rules about which direction authority runs and when, which the general term does not fix. This document states that form and records why each of its parts is the way it is. It also says plainly where the practice departs from what SDD prescribes and where it falls short of it.

It is not a how-to; `CONTRIBUTING.md`, `CLAUDE.md` and the `segment-plan` skill are that. It is not an audit either; `docs/practice-audit-2026-09-04.md` is that, and this document leans on its findings rather than repeating its evidence. It records the rationale for the practice, in the same register as the design rationale: where a choice could plausibly have gone another way, the point is to record why it went the way it did. `constitution.md` distills the six decisions that bind every change from Section 6, so change this document first.

The document is drafted with the help of Claude Code, with access to the repository. **The current-state numbers were taken on 2026-09-23 at `main` = `3559c7a7`**, and the appendix lists how to re-take them. A figure that describes a particular day is dated in the sentence that uses it; those are findings about that day, and they stay true when the codebase moves on.

---

## 2. Spec-driven development, as the term is used

Strip away the vendor framing and the 2026 usage covers a small family of shapes, distinguished by which direction authority runs between spec and code:

- **Spec-first.** The spec is written, the code is produced from it, and the spec is the input to every change. The tool shapes that popularized this are workflows for getting from a stated intent to reviewed code with the intent still legible. One is a requirements / design / tasks triple; another is a constitution / specify / plan / tasks / implement ladder.
- **Spec-anchored.** The spec is the durable contract; code evolves against it and both are maintained. Authority runs both ways, but the spec is where disputes are settled.
- **Spec-as-source.** The code is a build artifact, regenerated from the spec, and not edited by hand. This is the most radical shape and the least common in working codebases.
- **Spec-as-test.** The acceptance criteria are executable, so agreement between spec and code is checked rather than read.

Two claims sit under all four. The first is that **a spec catches architectural violations and contract drift that unit tests structurally cannot**. A test checks that the code does what the test author expected; a spec checks that it does what was *asked*; those are different questions. The second is that **the implementing role and the verifying role must be separate**, because a model checking its own output is not a check.

RRW's practice is best read as spec-anchored, with four qualifications:
- a phase rule about direction (6.1);
- mechanized checks wherever the repository itself states something a check can be derived from (6.3);
- separate readers where it does not (6.4);
- a human as the verifier of last resort where nothing else can look (6.6).

The rest of this document is the evidence for that reading and the reasoning behind each qualification.

---

## 3. Where the practice came from

The first day of the repository is unusually legible about intent. On 2026-04-27, before any application code, the commit sequence reads: `README.md` → `AGENTS.md` → `FUNCTIONAL_SPEC.md` → `TECH_STACK.md` → `ARCHITECTURE.md` → `pyproject.toml` → `main.py` → `test_health.py` → `ci.yml`. The agent-instruction file, the functional spec, the stack decision and the architecture note all precede the first route. That was spec-first in the literal sense, on day one.

It predates the term going mainstream. The tool shapes that later carried the name already existed, but the practice here was not taken from them. It was the same habit that produced Review Robin (VBA)'s documented, rerunnable workbook: write the rules down before acting on them, and keep the control surface visible.

The practice then changed shape twice, and both changes are instructive.

**The destination spec was retired.** The day-one `FUNCTIONAL_SPEC.md` described where the application was meant to end up. By 2026-05-11, two weeks and some eight hundred merges in, it was retired to `guide/archive/functional_spec.md` with a note that says exactly why: "its acceptance criteria, MVP list, and divergence notes all referred to a world that had already shipped (or been deliberately rescoped via segment plans)". A destination spec ages out of usefulness the moment the destination moves, which in AI-assisted development is daily.

It was replaced by a *contract* spec, `spec/rrw_functional_spec.md`, with a per-page spec set underneath it. The contract spec is technology-neutral and now 2,416 lines. Its header states that "the functional contract is stable; ship-state may move ahead of it", and it points at the sweep record that last read it against the code. The shift from *destination* to *contract* is the shift from spec-first to spec-anchored, and it happened because the first form stopped working.

**The specs moved into a three-layer document model.** On 2026-04-27 itself, `doc/` was renamed `guide/` and took the plans. On 2026-05-01 the root-level specs moved into `spec/` and `docs/`. That model (Section 4) is what the rest of the practice hangs off.

---

## 4. The three-layer document model

RRW keeps three documentation folders. Each has a README that states its question and indexes its contents, and each has an `archive/` subfolder with a hand-maintained index. The split is by *question answered*, not by audience or format:

| Folder | Answers | Authority | Today |
|---|---|---|---|
| `spec/` | *What is X supposed to look like and behave like?* | The contract. "When the code drifts from a spec, the spec is the canonical source — fix the code (or update the spec deliberately as part of a feature change, never silently)." | 40 live files, 24,362 lines; 5 archived |
| `docs/` | *How does X work today?* | Ship-state. `docs/status.md` is "authoritative for what does the code currently do". | 18 files |
| `guide/` | *What are we building next, and how?* | The plan. A segment plan is "the day-to-day source of truth for its own slices" while it is live. | 3 live segment plans; 107 archived, in a 173-row index |

Read those three authority statements together and they contradict each other: the spec is canonical, ship-state is authoritative, and the plan is the source of truth. The contradiction is resolved by *phase*, and stating that resolution is the most useful thing this document does (Section 6.1). In one line: **the plan leads while a segment is open, the spec is settled when it closes, and `docs/status.md` records that it did.**

Three features of the model carry more weight than they look:

- **Archives are records, not contracts.** Everything under an `archive/` is exempt from the prose gates (Section 6.3): its paths, pointers and labels are not checked. Two things there still are: the indexes that list archived documents, and the archived plans the index-currency checks read, including the `Blast radius` anchor on plans from Segment 19S on. It is kept for its reasoning, not for behavior. Specs can therefore be consolidated and retired freely without losing the reasoning behind them, and without a retired spec ever being mistaken for a live one. An archived spec's header names the spec that supersedes it.
- **The functional spec is an entry point, not a monolith.** Its §19 "Reading guide" maps each subject to the per-page or per-subsystem spec that carries the implementation-level contract (Section 6.2).
- **What is decided but not scheduled has one home.** `guide/deferred_consolidated.md` holds every scoped-but-unscheduled item, each with the trigger that would lift it back into a plan. A finding that is not acted on is recorded there rather than left in a closed plan's margins, where compaction would lose it.

---

## 5. The unit of work: the segment plan

Everything in RRW lands through a **segment**: a coherent scope with a plan in `guide/segment_*.md`, a PR ladder and a definition of done. Larger segments are divided into **items** that close independently, each with the same shape one heading level down. The plan is the practice's equivalent of the requirements / design / tasks triple, held in one file per segment. The shape is fixed by `guide/segment_plan_template.md` and the `segment-plan` skill (`.claude/skills/segment-plan/SKILL.md`):

> Opportunity → Decision (with the alternative rejected) → Semantics → Judgment calls — decided → Blast radius (measured) → PR ladder → Definition of done → Open questions → Out of scope → Doc impact → Status

Two sections are what the popular shapes lack:
- **Blast radius, measured.** The files, routes and tests the change will touch, counted before the first slice is cut, with the command that produced each count and the commit it was taken at. Since Segment 19S, `tests/unit/test_index_currency.py` checks the anchor.
- **Doc impact.** Which `spec/` and `docs/` files the segment will change, named at planning time, even though the spec edit lands last (Section 6.1). It is machine-read at the close.

Four things about how plans are used matter more than their shape:

- **Plan-to-build is hours, not weeks.** A plan is not a phase gate. It is the thinking, written down, so that the agent building slice 3 has the same intent as the one that built slice 1. 19C Item 1 was planned and shipped on the same day, 2026-08-20 (#2010).
- **Plans are revised by the build, and say so.** A `Status` block records what the ladder became and why; an amended `Decision` is annotated beside the original rather than rewritten over it. Segment 19S Item 10 is the fullest example. Its first ladder was struck once its second rung had been built (rung 1, #2581, closed unmerged), and a re-cut ladder shipped. After the item closed, the author changed the design twice more, and a second amendment records both. The plan still shows what was intended, what was done, and why they differ. That is the plan behaving as a spec-anchored artifact rather than a spec-first one.
- **Plans have a length budget, because the record of the build outgrew the build.** Across 19A–19M, plans ran 370 to 4,840 lines, and one item reached 951. Measured over one 377-line item, every section written at planning time came in under 50 lines, while `Status` ran 110 and a closed `Open questions` block 61. The skill now sets budgets: under ~250 lines for a plan and ~120 for an item. `Status` is compacted at the close into intended-versus-done, and an answered open question collapses to its answer.
- **Consequential UI lands scaffold-first.** A new page, card or navigation affordance lands in its own PR as a static placeholder: real copy and layout, inert controls. The surface is agreed on the placeholder, so the PRs that wire it carry no UI churn. It is the UI-shaped version of writing the contract before the implementation. It is also the practice's one foothold on the defect class nothing else reaches (Section 6.6): layout is agreed by a human at the one moment it is cheapest to change.

---

## 6. The core decisions

Each decision below is stated as *what was decided, why, and what it trades off*, with the evidence that it is actually followed rather than merely written down.

### 6.1 Plan on the way in, spec on the way out

**Decision.** Within a segment, the *plan* carries the intent and leads the code; the *spec* is updated at the close, to match what shipped. Segment 19A states the rule in one clause: "every shipped segment that locks a UI contract writes its spec on the way out."

The `spec-writer` agent's charter is the same rule from the other side:
- **At a close**, its job is to align the spec to what shipped, because the shipped behavior *is* the intended new contract.
- **Outside one**, the spec wins, and a divergence is reported rather than re-aligned. Its own phrasing, "if you cannot tell which mode you are in, you are in Mode B", puts the default on the reporting side.

**Why.** A spec edited slice by slice during a build describes a moving target and is wrong between every pair of slices. A spec written once at the close describes the settled contract and is right until the next segment opens it. The plan absorbs the in-flight ambiguity, since it is expected to be revised by the build, so the spec never has to. This is a deliberate departure from spec-first at PR granularity, and it is the most important thing to understand about how RRW's practice differs from the textbook.

**Evidence that it is followed.** Classifying each first-parent merge by the top-level folders it touches:
- Of the **2,583** merges, 1,573 touch `app/`. Of those, **336 (21%)** also touch a live spec in the same PR, while **475 (30%)** touch a live `guide/` document.
- Over the last 200 merges, the plan rate is **76%** and the spec rate **31%**.
- A further **246 merges (10%)** touch a live spec and no application code at all. These are the spec-on-the-way-out PRs.

The rise in the recent spec rate is the rule applied at a smaller grain, not the rule weakening. Items now close in days, and an item's close often lands its spec edits beside its last build rung.

The cleanest single case is the semantic-token migration (#2047 → #2062, 2026-08-23). Of its sixteen PRs, the first five touched only `guide/` (the plan), the next ten touched `app/` and no spec, and the sixteenth touched two specs and closed the item.

**Trade-off.** There is a window of spec drift inside every open segment, by design. During it, `spec/` describes the last settled state and `guide/` describes the intended next one, so a reader who consults only `spec/` mid-segment will be wrong about what is being built. Segments are short and the plan names its doc impact up front, so the window is narrow, but it is real.

**The rule is asymmetric at its exit.** A missing plan is *self-revealing*: an agent asked to build slice 3 with no plan has nothing to build from, and the gap surfaces before code lands. A missing spec edit is *silent*: the code works, the tests pass, `docs/status.md` records the ship, and nothing looks for the spec. When the audit took stock on 2026-09-04, two Tier-1 specs had been missing since 2026-05-11 without anything noticing.

The exit has since been made *checkable*, in two halves:
- **Declared impact is verified.** `tools/close_check.py <id>` reads a plan's `Doc impact` manifest and confirms that each committed path was edited inside the plan's window. It is run by whoever closes the segment, before archiving. Measured over the archived plans on 2026-09-05, when it landed: 85 of 101 live committed paths (84%) had been edited in window, and 11 of 32 plans had dropped at least one commitment. Every item of Segment 19S passed it at its close.
- **Undeclared surfaces are gated.** `tests/unit/test_spec_coverage.py` fails when a routing module has no governing spec at all.

Neither half makes the exit *mechanical*, and the distinction matters. The close check is not a CI gate, because a per-PR spec-sync gate would contradict this very rule. It asks only whether an edit happened, never whether it was right; that stays `spec-writer`'s job at the close, and the author's. So the rule is held by visibility on the way in and by convention *with a tool* on the way out. What neither covers is drift that goes unnoticed at the close (Section 6.5), or a spec that exists but says too little.

### 6.2 Two altitudes of spec

**Decision.** Keep a technology-neutral functional spec that describes intent in user and concept terms, and a per-page / per-subsystem spec set that names routes, services, data types and audit events. The functional spec points down, through its §19 reading guide; the per-page specs point up.

**Why.** A single spec at one altitude is either too abstract to check code against or too concrete to survive a refactor. Splitting the altitudes lets the functional contract stay stable while the per-page specs move with the surface. It is also the split a new reader needs: the functional spec is the entry point; the per-page spec is where a diff reviewer looks.

**Trade-off.** Two places to update, and **no live spec dates itself**. Each spec that once carried a currency date instead points at the sweep record that last read it end to end (Segment 19M). 19J.1 gave the reason when it did this to `spec/README.md` first: *a date nobody owns is what let §9.7 describe a card that never shipped*. The trade replaces a figure that rots quietly with one that rots visibly, since a sweep record carries its own date and its own scope. Currency is therefore *assumed* for every live spec, backed by the gates (6.3) and the sweeps (6.5). The assumption has been found false before: in three places by the practice audit, and in seventy-five more by 19M.

### 6.3 A convention becomes a failing test, not a paragraph

**Decision.** Where a convention can be derived from something the repository itself states, enforce it with a test that reads that thing, so the check cannot go stale when it changes. The source can be a code constant, the route table or the file tree. The main gates, by what they read:

- **Code constants.**
  - The `EVENT_SCHEMAS` audit-envelope allowlist: strict in tests, log-and-write-through in production.
  - `tests/unit/test_doc_conventions.py`, nine checks, most of them against code constants. Examples: every lifecycle table in a live spec agrees with `DISPLAY_LABELS`, and the retired button vocabulary is not prescribed in live prose.
  - `tests/unit/test_practice_kit.py`: the practice kit's manifest, the tree and the setup document agree.
- **The route table.** `tests/unit/test_spec_coverage.py` maps each of the 29 feature routing modules to the specs that govern them (`app/web/spec_registry.py`; three infrastructure modules are exempt) and fails on one that has none.
- **The file tree and the documents' own structure.**
  - `tests/unit/test_doc_references.py` checks that `CLAUDE.md` and `AGENTS.md` are byte-identical, and that every anchored path, every `§N` pointer and every cited pytest node id in live prose resolves.
  - `tests/unit/test_guide_indexes.py` requires a README row for every `guide/` document, live or archived.
  - `tests/unit/test_index_currency.py` checks five things, each within a stated scope:
    - every archived plan from Segment 16 on has its entry under `guide/todo_master.md` Done (the earlier era is ruled legacy);
    - the Done entries that declare a PR number run in PR order;
    - `docs/status.md`'s date matches its newest row;
    - no queued-work pointer names an archived plan;
    - from Segment 19S on, a `Blast radius` states when it was taken.
- **The stylesheet.** `tests/unit/test_generated_tools_are_current.py` and `tests/unit/test_contrast_audit.py` both read `base.html`'s inline stylesheet.

**Why.** The practice audit's decisive finding was not a stale word. `expired → "Closed"` landed on 2026-06-01, and three live specs still said "Expired" three months later. The contradiction had **survived a deliberate whole-folder documentation sweep** that re-read exactly those files. In the audit's words: "Vigilance is not failing here through carelessness. It is failing at the thing vigilance is structurally bad at."

The remedy was the `EVENT_SCHEMAS` idiom applied a second time: the rule lives in code, so drift fails the suite. It caught five live violations on its first run. The later gates follow the same idiom.

**A gate should be proved to catch what it claims.** Segment 19R produced four guards that passed while seeing less than they claimed. So an item that adds a guard can adopt an evidence bar in its definition of done. Before a guard is called complete, its fixture reaches the case, a mutation of the protected property fails, and its recognizer is exercised beyond the current examples. The bar is adopted item by item rather than as a standing rule, and it is left unenforced on purpose, because a check could only confirm that a mutation was *mentioned* (`docs/unenforced_conventions.md` §1.8). The first item to adopt it, 19S Item 2, was caught by it and by its cold read together: three of the four index checks first saw less than they claimed. One mutation was inert because `-` is a non-word character, so `19R-removed` still matched `^### Segment 19R\b`, and a live heading was quietly relying on that hole.

**Trade-off.** A gate checks only what is derivable. It verifies *agreement* where the repository states something to agree with; it cannot judge *adequacy*. The coverage gate shows the limit well. Neither of the two missing Tier-1 specs would have tripped it, because both surfaces *had* sections in `spec/operator_ui_concept.md` and lacked only a dedicated contract. It detects a surface with no spec, not a spec that says too little.

Not every convention should become a test. The audit rejected a British-spelling check because it cannot tell prose from identifiers and would need an allowlist that grows forever. `docs/unenforced_conventions.md` records each convention that is deliberately left to a reader, and why.

One more consequence is operational: **a green `ruff` is not evidence**. Most of these gates read no Python and run only under `pytest`, so a lint-only run passes all of them by not running them.

### 6.4 Separate readers

**Decision.** A change is read by something other than what wrote it. Two readers are checked-in agent definitions under `.claude/agents/`, read-only by construction and separate from whichever agent wrote the code:

- **`spec-writer`** updates `spec/` to match what shipped **at a close**, may write only under `spec/`, and must "flag drift … rather than silently rewriting". Outside a close it verifies and reports.
- **`diff-reviewer`** reads a PR diff cold, with no prior context, and checks it against the governing spec. Among other things, it reports claims in the commit message that the diff does not support and scope beyond the stated purpose, and it reports nothing at all if nothing is wrong. Its charter says "inventing findings to look thorough makes you worse than no reviewer". It carries no model pin, deliberately, because a reviewer should not be capped at a smaller model than the author.

A third reader is external: Codex, a different vendor's model, reviews pull requests automatically. Its own summary comment names the triggers as a PR opened for review or a draft marked ready. It commented on 159 pull requests opened since 2026-09-14, against 213 merged in that window. From June to 2026-09-13 the figures were 64 against 658. It reads most slices, not all of them.

**Why.** This is SDD's second core claim, that maker and checker must be separate, arrived at from RRW's own defect history. The audit classified the thirty most recent fix commits. Six (20%) were documentation corrections a spec reader would have caught. Nine (30%) were logic bugs, several "discovered by review-like activity rather than by the suite". One was a case-insensitive-email P0 found by a fresh reader who thought of the case, and fixed with 265 lines of new tests. Before the readers existed, "a diff goes from written to merged with nothing reading it". The readers close that gap for two of the three defect classes.

**Evidence that the reader catches the class it claims.** The test was retrospective. `diff-reviewer` was run cold, in a worktree at `9b9cc457` (2026-05-11, "Segment 16A PR 6: Accounts Management tab"), against that commit's diff and the specs as they stood that day, with no hint of what to look for. That commit made the sys-admin invite path match emails case-insensitively (`users.py:222`) while `deps.py:46` still matched exactly. Codex reported that inconsistency 25 days later as P0.2, and `ab043317` fixed it.

The reviewer's finding #6 reads, in part: "`invite` … dedupes case-insensitively, so it *permits* `Alice.Smith@example.edu` while Entra will present `alice.smith@example.edu`. On mismatch, `get_or_create_user` creates a second row … and the invited row is orphaned. The only test … uses identical casing." That is the defect, its mechanism and the test gap, from the diff alone. It came from checking the commit message's claim that the pre-seeded row "picks up the principal naturally".

One caveat: the checklist was written after the defect was known, so this shows the checklist *as written* finds it cold, not that one written blind would have.

**The cadence was measured into shape.** A reader works only when run, and the history of this decision is the history of finding out what "when run" costs.

- **Unrun.** From 2026-09-06 to 2026-09-14, 70 pull requests named `spec-writer` and none named `diff-reviewer`. The reader validated above had not read a diff since the arc that created it. `spec-writer`, chartered for the close, had become the per-rung reader by default. The two were then given separate cadences.
- **Per rung: effective and too dear.** The per-rung read ran from 2026-09-14, and a merge-history audit measured it four days later, recorded here on 2026-09-19 (`tools/pace_audit.py`).
  - **Cost.** A slice carrying a read took a median 49 minutes merge to merge, against 23 without. The median slice went from 25 minutes to 44, and in-PR iteration from about 8 minutes to 23. Codex was reading every slice in the same week, so both readers are in those figures.
  - **Catch.** Of 78 response commits, 58 changed code or tests and fixed live defects. The 20 that changed only prose described the author overclaiming in a plan or a close.
- **Per item: the ruling.** On the author's ruling of 2026-09-18, `diff-reviewer` reads once per item, on the item's cumulative diff. A code slice outside any ladder still takes its own read, and a prose-only slice takes none (`CLAUDE.md` "Where work runs"). Its first re-take, over #2460–#2492, had iteration back to about **10** minutes and slices carrying a read down from 69% to 30%. Under it, at `3559c7a7`, over 134 slices:
  - the median cycle is **31** minutes;
  - **44%** of slices carry a response to a read, from either the cold read or Codex;
  - a product slice with one takes **38** minutes against **27** without. A round of reading and responding therefore costs about 11 minutes, and the cold-read half of it is paid once per item rather than once per rung.

**What the cadence does not touch.** A whole-history audit on 2026-09-20 separated three step changes in the median slice:
- from **11** to **17** minutes between Segment 1 and 19C, as the suite grew and CI lengthened;
- to **22** on 2026-09-04, when the doc and test gates arrived;
- to **44** under the per-rung reads, with Codex also reading every slice, then down to about **30** under the per-item cadence.

Under all three sits *turn*, the time from the previous merge to a slice's first commit. That audit found turn a flat floor, a median of 8–10 minutes in every era, that barely scales with the slice's size. Re-taken at `3559c7a7`, the median under the per-item cadence is 8.2 minutes.

To split turn into the wait for an instruction and the build before the first commit, a campaign stamped slices' first commits with an `Instruction-Received` trailer. It ran over #2495–#2516, and its first reading, n=14, had *wait* at a median 3.5 minutes and *build* at 3.0. With the lost stamps recovered (below), the reading reversed. Today, across 37 stamped slices, *wait* is a median **1.9** minutes and *build* **5.8**. So the floor is mostly the agent's own work before it commits: loading context, reading the plan, running the gates. No cadence rule touches that, and none should.

The campaign had a lesson of its own. Git reads trailers only from a message's last block, so 21 of the first 37 stamps, written in a paragraph of their own, were silently discarded. Since 2026-09-22, `tools/pace_audit.py` has read the line anywhere in the message, which recovered them. Nothing catches a slice that omits the line. Stamping is therefore a campaign run when a figure is being re-taken, not a standing rule (`CLAUDE.md` "Where work runs").

**Trade-off.** Each round of reading costs about eleven minutes, and the cold read happens only because the agent runs it. A skipped read leaves no trace except that its item's `Status` records no findings, so the per-item record of reads and findings is how the next audit re-measures whether the cadence holds.

### 6.5 Periodic sweeps and snapshots, not continuous synchronization

**Decision.** Keep spec and code in agreement through scheduled sweeps and dated snapshots rather than a per-PR sync requirement.
- **Snapshots.** Nineteen dated codebase assessments have been written in the Claude Code lineage, and three whole-repository assessments in a separate Codex lineage. Each audits the functional areas against the code — "a route registered, a service function called, a test covering it — not against the spec's own claims". The current pair is `guide/codebase_assessment_22sep.md` and `guide/codex_assessment_21sep.md`.
- **Sweeps.** A whole-folder drift sweep is due every eight weeks or 500 merges, whichever comes first. `tools/close_check.py --stale` answers whether one is due.
- **Registers.** What an assessment surfaces but nobody owns goes into a register, each entry carrying the trigger that would promote it. Segment 19S Item 1 opened eight entries and disposed of all of them within a day.

**Why.** Per-PR sync would be a rule the practice already breaks by design (6.1). Sweeps fit the phase model: a segment closes, its spec is written on the way out, and periodically someone reads a whole folder against the whole codebase to catch what the closes missed.

The snapshots have paid. One fixed two real logic bugs with regression tests. The 2026-09-04 assessment caught its own area-classification error, where generated HTML had been counted as templates for a phantom +38%. It pinned the classification in `guide/assessment.json` so every later snapshot counts the same way. Two model lineages reading the same code disagree usefully, and a register keeps the disagreement from evaporating.

**Trade-off.** This is the mechanism that missed a one-word, three-place contradiction for three months. A sweep is only as good as the reader's attention on the day, and a reader re-reading a familiar file is the weakest reader there is. That is why 6.3 exists: the sweep finds what a person can find, and the gate finds what a person cannot. Neither replaces the other.

### 6.6 The human is the verifier of last resort — and there is no autonomous loop

**Decision.** End-to-end verification of anything the test suite cannot exercise is done by the author looking at it. That covers templates, redirects, layout, in-browser JS and real auth. It happens on the Azure dev slot after deploy. When the author cannot reach the dev slot, each check still owed is carried in `guide/post_azure_todo_checklist.md` until it can be made. A PR description must say what was not verified rather than claim that it was.

No agent runs unattended. An agent follows a pull request it opened through CI and review, under the instruction that opened it. It does not start new work on its own, and it does not merge; the author merges.

**Why.** Half of RRW's real defects live where no reader can see them. The audit's census put **fifteen of thirty** fix commits (50%) in the browser-only class: caption selectability, a 4 px misalignment, a keypress toggling a card, all "touching only templates and `tools/`". Against SDD's central claim that specs catch what unit tests cannot, this is the class *neither* catches, because a layout has no machine-checkable definition of done.

The practice has two partial answers. Scaffold-first (Section 5) puts a new surface in front of a person before it is wired. The agent can also drive a headless browser to measure a layout or take a screenshot and attach the measurement to the PR. Neither is a person looking. Scaffold-first applies only to new surfaces, and a measured layout is only as good as the question asked of it. So the gap is not "nothing looks at layout" but "nothing looks at layout *twice*".

The loop-engineering threshold for running autonomously is a machine-checkable definition of done, and work long enough for autonomy to matter. A solo project whose slices are sized to be reviewed in one sitting does not meet it, and the audit says so in as many words. The `diff-reviewer` says the same about itself: "You will not catch rendering, layout, or in-browser JS behaviour. Those need the Azure dev slot, not a reader."

**Trade-off.** The verifier is a person, and the practice's throughput is bounded by that person's attention. That is accepted deliberately as the right shape for the project's scale, not as an immature version of an autonomous one. It is also where the practice's answer is most partial: the browser-only class is "both the largest measured category of real defects here and the one no layer of the current practice catches".

### 6.7 The reasoning travels with the change

**Decision.** Commit messages and PR bodies carry the *reasoning* — what was found, what was measured, why the obvious alternative was not taken — and not only the change. Plans record what was intended and what was done. Dated documents such as audits and assessments are annotated rather than silently rewritten. The merge policy is written in `CONTRIBUTING.md` rather than enforced by branch protection, after measurement showed it was already followed: wait for the Postgres job when the diff touches `alembic/`, `app/db/` or any querying service; merge ahead of it for docs and dev tooling.

**Why.** The failure mode the vibe-coding literature names most sharply is "debugging code *nobody fully wrote or owns*". RRW's mitigation is that the intent is recoverable. The audit reconstructed a three-month-old drift's frequency evidence from commit messages alone, "precisely because of that". It is the same principle as the audit-event envelope on every mutating service (design rationale §6.7), applied to the codebase instead of the data: defensibility by construction. Writing the merge policy down rather than enforcing it comes from the same instinct. The audit found the judgment was sound, and one paragraph "survives a second contributor or a six-month gap" where branch protection would have added ceremony to a process that did not need it.

**Trade-off.** Long commit messages, long PR bodies, and an instruction file that grows. `CLAUDE.md` reached 266 lines before the audit's context-hygiene finding cut it to 183, by removing a fifty-module inventory that was duplicated in `spec/architecture.md` and *incomplete* there. It has since grown back to 297, largely with the rules of 6.4's cadence and the gates of 6.3. Reasoning written everywhere is written twice, and twice-written reasoning drifts; that is the same lesson as 6.3, one layer up. The plan budgets and `Status` compaction (Section 5) are the counter-pressure inside `guide/`. No equivalent budget yet holds the instruction file.

---

## 7. What RRW's practice deliberately is not

Scope discipline is part of the practice, so the exclusions are worth stating directly.

- **Not spec-as-source.** Code is edited by hand (by an agent, at the author's direction), and no spec is compiled into anything.
- **Not spec-first at PR granularity.** The spec co-change rate is 21% overall and 31% recently, and the phase rule (6.1) makes that a design rather than a lapse.
- **Not executable-spec.** The gates derive from what the repository states, not from acceptance criteria written as tests.
- **No branch protection.** It measured that the stratified merge policy was followed without it.
- **Spec adequacy is not gated.** `tests/unit/test_spec_coverage.py` fails when a routing module has no spec at all. It does not judge whether a spec says enough, and there is no per-PR spec-sync gate, which would contradict the phase rule.
- **No spelling check.** The check was rejected on evidence.
- **No security scanning in CI.** That is recorded as a candidate in `guide/deferred_consolidated.md`, not silently absent.
- **No autonomous loop** of any kind.

Most of these are chosen. The security scan is deferred with a stated reason, which is the practice's way of saying "not yet" without saying "never". The coverage gate was once in the same position, and it shipped, which is what "not yet" is supposed to turn into.

---

## 8. Measured against the claim

SDD's central claim is that specs catch what unit tests structurally cannot. Against RRW's own defect census (the practice audit's thirty most recent fix commits, 2026-05-16 → 2026-09-04):

| Defect class | Share | What catches it in RRW |
|---|---|---|
| Documentation drift: spec says one thing, code does another | 6 (20%) | The gates where the repository states something to derive a check from; `diff-reviewer` and `spec-writer` otherwise; the sweeps last |
| Logic bugs that landed with regression tests | 9 (30%) | The suite for the regression; a separate reader (`diff-reviewer` per item, Codex on most PRs, an assessment) for the discovery |
| Browser-only: layout, selection, keypress, template JS | 15 (50%) | The author, looking. Nothing else |

The claim holds for the first class and half-holds for the second. For the largest class it is simply not the relevant mechanism, and a practice that pretended otherwise would be worse for it.

The 2026 literature characterizes AI-authored code by its shape: churn up 41%, duplication up 4×, refactoring collapsed. RRW measures itself with `tools/code_metrics.py`.
- **Churn is 1.1×.** Of 83,416 deleted lines, 72.7% were under fourteen days old, against 68.0% of all lines in those files at that moment. Deletions are barely younger than the code around them, so recent work is not being rewritten specifically; the code is simply young. The ratio was 1.0× on 2026-09-04.
- **Duplication is 6.3%** at ten-line blocks for production code. The largest hits are the four sibling roster route slices, 34–47% duplicated against each other, which is the one real finding.

The codebase does not have the shape. Whether that is *because of* the practice is an inference; that the practice was in place while the codebase was built is a fact.

Where the practice is measurably behind:
- the browser-only class (6.6);
- a spec set that is reliably right only at the boundaries of segments and items (6.1);
- a separate reader whose running depends on the agent that runs it (6.4).

---

## 9. Where the practice sits now

Read against the four shapes in Section 2, RRW is **spec-anchored with a phase rule**: plans lead in, specs settle out, ship-state is recorded, and disputes are settled in `spec/`. It is **mechanized at the seams** where the repository states something a check can be derived from, it offers new gates an evidence bar of proof by mutation, adopted item by item, and it has shown it will retire a convention rather than mechanize it badly. It has **separate readers** on a cadence measured into shape: one cold read per item, and an external model reading most PRs. And it has a **human verifier** where nothing else can look, held deliberately rather than as a stopgap.

The practice audit's verdict was that RRW is "ahead on the thing that is hardest to retrofit and behind on the thing that is cheapest to fix". It was ahead because a spec set, a layered document model and a habit of writing reasoning down were there from the first commit and cannot be bolted on later. It was behind because the specific gates, the reviewer and the merge policy were each a file, and each was written in an afternoon once the evidence pointed at it.

The three weeks since then bear the asymmetry out. The gates multiplied and the reviewer's cadence was re-cut twice, each in a day or two, and each change was measured first. **The expensive part of spec-driven development is the culture of writing things down before and after acting on them, and that part has to be there on day one. The cheap part is the tooling, and it can wait for the evidence.**

---

## 10. The thesis in one paragraph

RRW practices a form of spec-driven development in which **plans carry intent into a segment, specs settle it on the way out, and ship-state records that they did**. That phase rule makes the spec reliably right at segment boundaries and the plan reliably right inside them, rather than pretending either is right always. Where a convention can be derived from something the repository states, the convention is a failing test, and an item that adds one can adopt the bar of showing it fails when the rule is broken. Where it cannot, a separate reader checks the diff against the spec. Where nothing can read — layout, selection, the browser — a person looks, and the practice says so instead of claiming otherwise. It runs no autonomous loop, because its definition of done is not machine-checkable for the defects that actually occur. It writes its reasoning down at every step, so that a codebase no one fully wrote is still one someone can fully explain. It was doing this before the term went mainstream, it measured itself against the term when the term arrived, and it kept the parts that held.

---

## Appendix — SDD prescription mapped to RRW practice

| What SDD prescribes | RRW's response | Evidence (re-takeable) |
|---|---|---|
| Specs are the source of truth | Yes, at segment boundaries; the plan is the source of truth inside a segment (§6.1) | `spec/README.md` authority statement; `guide/todo_master.md` "day-to-day source of truth for its own slices"; 19A "writes its spec on the way out" |
| Spec before code | On day one, literally; thereafter *plan* before code, *spec* after | First-day commit order 2026-04-27; spec co-change 21% (31% recent) against plan co-change 30% (76% recent) over first-parent merges; the #2047 → #2062 arc |
| Requirements / design / tasks | One plan per scope, items within it: Opportunity → Decision → Judgment calls → Blast radius (measured) → PR ladder → Definition of done → Doc impact → Status | `guide/segment_plan_template.md`; `.claude/skills/segment-plan/SKILL.md`; `guide/archive/segment_19S_post_assessment.md` Item 10 |
| Spec catches drift tests cannot | A gate derived from what the repository states, where it states something; elsewhere a separate reader; last, the sweeps | The gates in §6.3; `app/services/audit.py` `EVENT_SCHEMAS`; 6/30 fix commits were doc drift |
| Maker and checker separate | `spec-writer` (at a close; reports divergence otherwise), `diff-reviewer` (cold, report-only, no model pin, once per item) and Codex, automatic on most PRs. Validated retrospectively: run cold at `9b9cc457`, `diff-reviewer` found Codex's P0.2 (`ab043317`) 25 days early | `.claude/agents/`; `CLAUDE.md` "Where work runs"; `python3 tools/pace_audit.py --cut 2460`; the Codex search in the note below |
| Machine-checkable definition of done | For code and specs, yes: 4,800 tests on two dialects plus the gates. For UI, no: the author, looking | 15/30 fix commits browser-only; `CLAUDE.md` "Where work runs"; `guide/post_azure_todo_checklist.md` |
| Spec coverage enforced | For absence, yes: every routing module registered, every mapped spec a live file, the declared-debt baseline empty. Adequacy, no | `tests/unit/test_spec_coverage.py`; `app/web/spec_registry.py`; `constitution.md` II |
| Living spec, continuously synced | Periodic instead: 19 + 3 dated assessments in two model lineages, drift sweeps on a cadence, registers for what they surface | `guide/archive/codebase_assessment_*.md`; `tools/close_check.py --stale`; `docs/practice-audit-2026-09-04.md` §2 |
| Code as a generated artifact | No. Hand-edited by agents at the author's direction; specs are prose | — |
| Autonomous agent loops | No, on stated grounds: the definition of done is not machine-checkable for the defects that occur | `docs/practice-audit-2026-09-04.md` A.5 |
| The codebase should not take the AI-authored shape | Measured: churn 1.1×, duplication 6.3% at ≥10 lines | `python3 tools/code_metrics.py` (deterministic; a few minutes, most of it the churn walk) |

**Re-taking the numbers.** All the current-state figures above were taken at `3559c7a7`:

- **Spec folder size:** `ls spec/*.md | wc -l; cat spec/*.md | wc -l`.
- **Archive counts:** `ls guide/archive/segment_*.md | wc -l`.
- **Co-change rates:** classify each `git log origin/main --first-parent --merges` commit by the paths in `git diff --name-only <sha>^1 <sha>`. A live spec is under `spec/` but not `spec/archive/`; a live plan document is under `guide/` but not `guide/archive/`. The same classifier run at `376c9605` reproduces the 2026-09-04 percentages; its raw counts differ from that day's by at most three.
- **Test count:** `pytest --collect-only -q`.
- **Cadence figures:** `python3 tools/pace_audit.py --cut 2460`.
- **Churn and duplication:** `python3 tools/code_metrics.py`.
- **Codex coverage:** a GitHub search, `is:pr commenter:chatgpt-codex-connector[bot] created:>=2026-09-14` against `is:merged created:>=2026-09-14`, in `repo:philoyhc/review-robin-web`. It needs the API, because PR comments are not in git.
- **Defect census:** `docs/practice-audit-2026-09-04.md` §4 R2, as of that audit.
