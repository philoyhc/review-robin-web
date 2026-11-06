# Review Robin Web — Spec-Driven Development in Practice

## 1. Introduction

Review Robin Web (RRW) is a web application for running structured institutional review cycles. `rrw_design_rationale.md` explains what it *is* and why it looks the way it does. This document is its companion on a different axis. It explains how RRW is *worked on*: the practice by which a single author, working through AI coding agents and checking each change in a browser, had landed some three thousand six hundred pull requests by 2026-11-06, and taken the application into institutional production on 2026-10-31, without the codebase taking the shape that AI-authored codebases are reported to take.

The practice has a name now. Through 2026 the term **spec-driven development** (SDD) went mainstream for the family of methods in which specifications are the durable source of truth and code is kept in agreement with them. RRW was doing a form of this before the term went mainstream. More usefully for a reader, it is doing a *particular* form of it, with rules about which direction authority runs and when, which the general term does not fix. This document states that form and records why each of its parts is the way it is. It also says plainly where the practice departs from what SDD prescribes and where it falls short of it.

RRW runs under the Cordware host, a small package in the same repository that mounts it at `/reviewrobin` and parses the Easy Auth identity, beside two smaller application packages. **This repository never deploys.** A private repository imports an allowlisted snapshot of one `main` commit whose CI is green, and a release dispatched by hand migrates and deploys it (`docs/deployment.md`). The practice described here carries over to the host and to that repository (`docs/archive/cordware_repository_strategy_v0.8.md` §2).

It is not a how-to; `CONTRIBUTING.md`, `CLAUDE.md` and the `segment-plan` skill are that. It is not an audit either; `docs/archive/practice-audit-2026-09-04.md` is that, and this document leans on its findings rather than repeating its evidence. It records the rationale for the practice, in the same register as the design rationale: where a choice could plausibly have gone another way, the point is to record why it went the way it did. `constitution.md` distills Section 6 into six articles that bind every change: five of its seven decisions, plus the rule §6.3's trade-off implies. So change this document first.

The document is drafted with the help of Claude Code, with access to the repository. **The current-state numbers were re-taken on 2026-11-06 at `main` = `c912ae53` (#3657)**, and the appendix lists how to re-take them. A figure that describes a particular day is dated in the sentence that uses it; those are findings about that day, and they stay true when the codebase moves on.

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
- mechanized checks wherever the repository itself, or the language, states something a check can be derived from (6.3);
- separate readers where it does not (6.4);
- a human as the verifier of last resort where nothing else can look (6.6).

The rest of this document is the evidence for that reading and the reasoning behind each qualification.

---

## 3. Where the practice came from

The first day of the repository is unusually legible about intent. On 2026-04-27, before any application code, the commit sequence reads: `README.md` → `AGENTS.md` → `FUNCTIONAL_SPEC.md` → `TECH_STACK.md` → `ARCHITECTURE.md` → `pyproject.toml` → `main.py` → `test_health.py` → `ci.yml`. The agent-instruction file, the functional spec, the stack decision and the architecture note all precede the first route. That was spec-first in the literal sense, on day one.

It predates the term going mainstream. The tool shapes that later carried the name already existed, but the practice here was not taken from them. It was the same habit that produced Review Robin (VBA)'s documented, rerunnable workbook: write the rules down before acting on them, and keep the control surface visible.

The practice then changed shape twice, and both changes are instructive.

**The destination spec was retired.** The day-one `FUNCTIONAL_SPEC.md` described where the application was meant to end up. By 2026-05-11, two weeks and some eight hundred merges in, it was retired to `guide/archive/functional_spec.md` with a note that says exactly why: "its acceptance criteria, MVP list, and divergence notes all referred to a world that had already shipped (or been deliberately rescoped via segment plans)". A destination spec ages out of usefulness the moment the destination moves, which in AI-assisted development is daily.

It was replaced by a *contract* spec, `spec/rrw_functional_spec.md`, with a per-page spec set underneath it. The contract spec is technology-neutral and ran to 2,565 lines on 2026-10-07. It carries no currency header of its own: `spec/README.md` gives its currency to the sweep records in `guide/` that read it against the code, because an "aligned as of" date moves only when someone remembers it. The shift from *destination* to *contract* is the shift from spec-first to spec-anchored, and it happened because the first form stopped working.

**The specs moved into a three-layer document model.** On 2026-04-27 itself, `doc/` was renamed `guide/` and took the plans. On 2026-05-01 the root-level specs moved into `spec/` and `docs/`. That model (Section 4) is what the rest of the practice hangs off.

---

## 4. The three-layer document model

RRW keeps three documentation folders. Each has a README that states its question and indexes its contents, and each has an `archive/` subfolder with a hand-maintained index: its own README in `spec/` and `guide/`, rows in `docs/README.md` for `docs/`. The split is by *question answered*, not by audience or format:

| Folder | Answers | Authority | At `c912ae53` (2026-11-06) |
|---|---|---|---|
| `spec/` | *What is X supposed to look like and behave like?* | The contract. "When the code drifts from a spec, the spec is the canonical source — fix the code (or update the spec deliberately as part of a feature change, never silently)." | 35 live files, 28,416 lines; 9 archived. The three packages keep their own `spec/` folders (8 files) |
| `docs/` | *How does X work today?* | Reference on the running system. Until 2026-10-05 the status file (now `docs/archive/status.md`) claimed to be "authoritative for what does the code currently do". | 11 live files; 13 archived |
| `guide/` | *What are we building next, and how?* | The plan. A segment plan is "the day-to-day source of truth for its own slices" while it is live. | 4 live segment plans; 141 archived, in a 245-row index |

Read those three authority statements together and they contradicted each other: the spec is canonical, ship-state is authoritative, and the plan is the source of truth. The contradiction is resolved by *phase*, and stating that resolution is the most useful thing this document does (Section 6.1). In one line: **the plan leads while a segment is open, the spec is settled when it closes, and the archived plan records that it did.**

Three features of the model carry more weight than they look:

- **Archives are records, not contracts.** Everything under an `archive/` is exempt from the prose gates (Section 6.3): its paths, pointers and labels are not checked. Two things there still are: the indexes that list archived documents, and the archived plans the index-currency checks read, including the `Blast radius` anchor on plans from Segment 19S on. It is kept for its reasoning, not for behavior. Specs can therefore be consolidated and retired freely without losing the reasoning behind them, and without a retired spec ever being mistaken for a live one. An archived spec's header names the spec that supersedes it.
- **The functional spec is an entry point, not a monolith.** Its §19 "Reading guide" maps each subject to the per-page or per-subsystem spec that carries the implementation-level contract (Section 6.2).
- **What is decided but not scheduled has one home.** `guide/deferred_consolidated.md` holds every scoped-but-unscheduled item, each with the trigger that would lift it back into a plan. What is *found* but not yet acted on has another: a findings register beside the assessment that found it (Section 6.5). Either way a finding is not left in a closed plan's margins, where compaction would lose it.

---

## 5. The unit of work: the segment plan

Everything in RRW lands through a **segment**: a coherent scope with a plan in `guide/segment_*.md`, a PR ladder and a definition of done. Larger segments are divided into **items** that close independently, each with the same shape one heading level down. The plan is the practice's equivalent of the requirements / design / tasks triple, held in one file per segment. The shape is fixed by `guide/segment_plan_template.md` and the `segment-plan` skill (`.claude/skills/segment-plan/SKILL.md`):

> Opportunity → Decision (with the alternative rejected) → Semantics → Judgment calls — decided → Blast radius (measured) → PR ladder → Definition of done → Open questions → Out of scope → Doc impact → Status

Two sections are what the popular shapes lack:
- **Blast radius, measured.** The files, routes and tests the change will touch, counted before the first slice is cut, with the command that produced each count and the commit it was taken at. Since Segment 19S, `tests/unit/test_index_currency.py` checks the anchor.
- **Doc impact.** Which `spec/` and `docs/` files the segment will change, named at planning time, even though the spec edit lands last (Section 6.1). It is machine-read at the close.

Four things about how plans are used matter more than their shape:

- **Plan-to-build is hours, not weeks.** A plan is not a phase gate. It is the thinking, written down, so that the agent building slice 3 has the same intent as the one that built slice 1. 19C Item 1 was planned and shipped on the same day, 2026-08-20 (#2010); segment 14F, planned on 2026-11-02, went from its scaffold to per-row email sending in seven PRs on 2026-11-05, and was on Azure that afternoon.
- **Plans are revised by the build, and say so.** A `Status` block records what the ladder became and why; an amended `Decision` is annotated beside the original rather than rewritten over it. Segment 19S Item 10 is the fullest example. Its first ladder was struck once its second rung had been built (rung 1, #2581, closed unmerged), and a re-cut ladder shipped. After the item closed, the author changed the design twice more, and a second amendment records both. The plan still shows what was intended, what was done, and why they differ. That is the plan behaving as a spec-anchored artifact rather than a spec-first one. 14F did the same mid-build: when the author ruled bulk email off until it could be paced (2026-11-05), the original rungs 3 and 4 were struck, rungs 3a–3d added, and bulk moved to 14G, all recorded beside the intent they replaced.
- **Plans have a length budget, because the record of the build outgrew the build.** Across 19A–19M, plans ran 370 to 4,840 lines, and one item reached 951. Measured over one 377-line item, every section written at planning time came in under 50 lines, while `Status` ran 110 and a closed `Open questions` block 61. The skill now sets budgets: under ~250 lines for a plan and ~120 for an item. `Status` is compacted at the close into intended-versus-done, and an answered open question collapses to its answer. The budget is a signal, not a check, and the four plans live on 2026-11-06 all run over it (272 to 351 lines) before any of them has compacted at a close.
- **Consequential UI lands scaffold-first.** A new page, card or navigation affordance lands in its own PR as a static placeholder: real copy and layout, inert controls. The surface is agreed on the placeholder, so the PRs that wire it carry no UI churn. It is the UI-shaped version of writing the contract before the implementation. It is also the practice's one foothold on the defect class nothing else reaches (Section 6.6): layout is agreed by a human at the one moment it is cheapest to change. 14F's Share the session link card shows the payoff: the author cut it from two message boxes to the link alone on the wired version, and the cut removed code rather than reworking it.

---

## 6. The core decisions

Each decision below is stated as *what was decided, why, and what it trades off*, with the evidence that it is actually followed rather than merely written down.

### 6.1 Plan on the way in, spec on the way out

**Decision.** Within a segment, the *plan* carries the intent and leads the code; the *spec* is updated at the close, to match what shipped. Segment 19A states the rule in one clause: "every shipped segment that locks a UI contract writes its spec on the way out."

The `spec-writer` agent's charter is the same rule from the other side:
- **At a close**, its job is to align the spec to what shipped, because the shipped behavior *is* the intended new contract.
- **Outside one**, the spec wins, and a divergence is reported rather than re-aligned. Its own phrasing, "if you cannot tell which mode you are in, you are in Mode B", puts the default on the reporting side.

**Why.** A spec edited slice by slice during a build describes a moving target and is wrong between every pair of slices. A spec written once at the close describes the settled contract and is right until the next segment opens it. The plan absorbs the in-flight ambiguity, since it is expected to be revised by the build, so the spec never has to. This is a deliberate departure from spec-first at PR granularity, and it is the most important thing to understand about how RRW's practice differs from the textbook.

**Evidence that it is followed.** Classifying each pull request on `main`'s first-parent line by the top-level folders it touches, at `c912ae53`:
- Of the **3,645** PRs, 2,121 touch `app/`. Of those, **670 (32%)** also touch a live spec in the same PR, while **969 (46%)** touch a live `guide/` document. On 2026-09-23, over 2,583, the rates were 21% and 30%.
- Over the last 200 PRs, the plan rate among the 102 that touch `app/` is **82%** and the spec rate **42%**.
- A further **351 PRs (10%)** touch a live spec and no application code at all. These are the spec-on-the-way-out PRs.

Both rates rose, and the plan rate rose further. That is the rule applied at a smaller grain, not the rule weakening. Items now close in hours, an item's close often lands its spec edits beside its last build rung, and nearly every build rung now writes its own line in its plan's `Status`.

The cleanest single case is the semantic-token migration (#2047 → #2062, 2026-08-23). Of its sixteen PRs, the first five touched only `guide/` (the plan), the next ten touched `app/` and no spec, and the sixteenth touched two specs and closed the item.

**Trade-off.** There is a window of spec drift inside every open segment, by design. During it, `spec/` describes the last settled state and `guide/` describes the intended next one, so a reader who consults only `spec/` mid-segment will be wrong about what is being built. Segments are short and the plan names its doc impact up front, so the window is usually narrow, but it is real, and a segment that changes something the whole corpus assumes widens it. 14F is the example. "No email is sent" was true for six months and stated in a dozen places; when per-row sending shipped on 2026-11-05 with the segment still open, the 2026-11-06 assessment found twelve drifts, four of them in spec files 14F's `Doc impact` had not named (`guide/findings_2026-11-06_assessment.md`, D1). The window was narrow in time and wide in reach.

**The rule is asymmetric at its exit.** A missing plan is *self-revealing*: an agent asked to build slice 3 with no plan has nothing to build from, and the gap surfaces before code lands. A missing spec edit is *silent*: the code works, the tests pass, the plan records the ship, and nothing looks for the spec. When the audit took stock on 2026-09-04, two Tier-1 specs had been missing since 2026-05-11 without anything noticing. It still happens: 22I's close (#3641) skipped its `spec-writer` pass, and Codex, not the closer, noticed.

The exit has since been made *checkable*, in two halves:
- **Declared impact is verified.** `tools/close_check.py <id>` reads a plan's `Doc impact` manifest and confirms that each committed path was edited inside the plan's window. It is run by whoever closes the segment, before archiving. Measured over the archived plans on 2026-09-05, when it landed: 85 of 101 live committed paths (84%) had been edited in window, and 11 of 32 plans had dropped at least one commitment. Every item of Segment 19S passed it at its close.
- **Undeclared surfaces are gated.** `tests/unit/test_spec_coverage.py` fails when a routing module has no governing spec at all.

Neither half makes the exit *mechanical*, and the distinction matters. The close check is not a CI gate, because a per-PR spec-sync gate would contradict this very rule. It asks only whether an edit happened, never whether it was right, and only for the files the plan named; that stays `spec-writer`'s job at the close, and the author's. So the rule is held by visibility on the way in and by convention *with a tool* on the way out. What neither covers is drift that goes unnoticed at the close (Section 6.5), a spec the plan did not name, or a spec that exists but says too little.

### 6.2 Two altitudes of spec

**Decision.** Keep a technology-neutral functional spec that describes intent in user and concept terms, and a per-page / per-subsystem spec set that names routes, services, data types and audit events. The functional spec points down, through its §19 reading guide; the per-page specs point up.

**Why.** A single spec at one altitude is either too abstract to check code against or too concrete to survive a refactor. Splitting the altitudes lets the functional contract stay stable while the per-page specs move with the surface. It is also the split a new reader needs: the functional spec is the entry point; the per-page spec is where a diff reviewer looks.

**Trade-off.** Two places to update, and **no live spec dates itself**. The specs that once carried a currency date dropped it, and `spec/README.md` gives currency to the dated sweep records that read the specs end to end (Segment 19M). 19J.1 gave the reason when it did this to `spec/README.md` first: *a date nobody owns is what let §9.7 describe a card that never shipped*. The trade replaces a figure that rots quietly with one that rots visibly, since a sweep record carries its own date and its own scope. Currency is therefore *assumed* for every live spec, backed by the gates (6.3) and the sweeps (6.5). The assumption has been found false before: in three places by the practice audit, in seventy-five more by 19M, and on 2026-11-06 in the functional spec's §§9.13 and 11.6, which a segment plan scoped to the per-page specs did not think to name (6.1).

### 6.3 A convention becomes a failing test, not a paragraph

**Decision.** Where a convention can be derived from something the repository itself states, enforce it with a test that reads that thing, so the check cannot go stale when it changes. The source can be a code constant, the route table or the file tree. The main gates, by what they read:

- **Code constants.**
  - The `EVENT_SCHEMAS` audit-envelope allowlist: strict in tests, log-and-write-through in production. It registered 173 event types at `c912ae53`.
  - `tests/unit/test_doc_conventions.py`, nine checks, most of them against code constants. Examples: every lifecycle table in a live spec agrees with `DISPLAY_LABELS`, and the retired button vocabulary is not prescribed in live prose.
  - `tests/unit/test_practice_kit.py`: the practice kit's manifest, the tree and the setup document agree.
- **The route table.** `tests/unit/test_spec_coverage.py` maps each of the 30 feature routing modules to the specs that govern them (`app/web/spec_registry.py`; three infrastructure modules are exempt) and fails on one that has none.
- **The file tree and the documents' own structure.**
  - `tests/unit/test_doc_references.py` checks that `CLAUDE.md` and `AGENTS.md` are byte-identical, and that every anchored path, every `§N` pointer and every cited pytest node id in live prose resolves.
  - `tests/unit/test_guide_indexes.py` requires a README row for every `guide/` document, live or archived.
  - `tests/unit/test_index_currency.py` checks two things, each within a stated scope (three more retired on 2026-10-05 with the lists they read: two over `guide/todo_master.md`'s Done list, one over the status file's date):
    - no queued-work pointer names an archived plan;
    - from Segment 19S on, a `Blast radius` states when it was taken.
- **The stylesheet.** `tests/unit/test_generated_tools_are_current.py` and `tests/unit/test_contrast_audit.py` both read `base.html`'s inline stylesheet.
- **The CI workflows.** `tests/unit/test_ci_shards.py` reads `.github/workflows/ci.yml`, `.github/workflows/ci-postgres.yml` and `pyproject.toml`'s `testpaths`. It fails when a test file falls out of every shard or lands in two: the derived-gate idiom applied to CI itself. `tools/ci_lanes.py` picks the lane a PR runs from the paths it touches (prose only, the residential package, or everything; Segment 22A), so the gates that read prose run on a prose PR in about a minute and the full suite runs on everything else.

**The language-level gates.** Segments 22C–22F and 22H (#3584–#3630, 2026-11-04 to 11-05) added gates that derive from the *language* rather than from something the repository states.
- **pyright.** Basic mode first, 307 errors to 0 (`guide/archive/segment_22C_pyright.md`, #3584–#3593). Then strict mode over every application package: 2,137 errors at its blast radius; one ruling allowed private uses (`reportPrivateUsage` off, because packages share `_helpers` by convention, 437 of them), and rung 1's config left 1,846, all fixed (`guide/archive/segment_22E_pyright_strict.md`, #3604–#3609). `# type: ignore` is disabled (`enableTypeIgnoreComments = false`, `guide/archive/segment_22F_pyright_followup.md`); the only suppression left is a reasoned `# pyright: ignore[rule]`, of which 26 remained on 2026-11-05, 2 in application code and 24 in tests, and 32 at `c912ae53` (`git grep -c "pyright: ignore" -- '*.py'`).
- **Formatting.** `ruff format`, whose first run rewrote 936 of 1,074 files (#3623) and whose check now covers every Python file (#3625), with ruff pinned exactly so the check agrees with the formatter that wrote the tree, and `E501` on (#3624), with one generated file exempt, `tools/theme_customizer.gen.py` (`guide/archive/segment_22H_format_and_suite_time.md`).

They are the same decision at a different source: a convention, "prefer explicit types", in `CLAUDE.md` from the start, became a failing check. The check reads the code, so it cannot drift from the code the way prose does; what it keeps by hand is its configuration, with the tool versions pinned exactly (22C, 22H). What they found, said plainly: six behavior defects in about 91k lines of application code (`git ls-files` over the four packages, less their tests). Four were in 22C: the observer collation's `<h2>None</h2>` for an unlabeled instrument, and three paths that raised where they should not have, or raised the wrong error. One was in 22E: a 500 in the email check, found by the item read. One was found in 22E and fixed in 22F: a malformed audit `scheduled_at` raised on Session Home (#3612). One structural pattern was in 22F: most of the old ignores hid an `object()` "unset" sentinel that `is not` cannot narrow, now one-member enums. Six defects in 91k lines is a low yield looking back. The gate's value is forward, on the agent output that arrives every day.

And they changed nothing else. The 2026-11-06 assessment's defect read compared the syntax trees of 143 files the window changed, with docstrings, annotations and imports stripped, and found no behavior change; the package read did the same for the three packages. The formatter's pass took 2,953 lines out of production code alone, which is why production grew by 73 lines across a window that shipped the clock, System Status and email sending.

The trade-off is two-sided. The four test roots keep 36 rule-offs between them and stay relaxed for good (22F). And a type checker can prove a plan wrong: pyright matches a Protocol against a model's declared `Mapped[int]`, not the `int` it yields, so 22C's planned Protocol fix did not work, and its Status records why.

**Why.** The practice audit's decisive finding was not a stale word. `expired → "Closed"` landed on 2026-06-01, and three live specs still said "Expired" three months later. The contradiction had **survived a deliberate whole-folder documentation sweep** that re-read exactly those files. In the audit's words: "Vigilance is not failing here through carelessness. It is failing at the thing vigilance is structurally bad at."

The remedy was the `EVENT_SCHEMAS` idiom applied a second time: the rule lives in code, so drift fails the suite. It caught five live violations on its first run. The later gates follow the same idiom.

**A gate should be proved to catch what it claims.** Segment 19R produced four guards that passed while seeing less than they claimed. So an item that adds a guard can adopt an evidence bar in its definition of done. Before a guard is called complete, its fixture reaches the case, a mutation of the protected property fails, and its recognizer is exercised beyond the current examples. The bar is adopted item by item rather than as a standing rule, and it is left unenforced on purpose, because a check could only confirm that a mutation was *mentioned* (`docs/unenforced_conventions.md` §1.8). The first item to adopt it, 19S Item 2, was caught by it and by its cold read together: three of the four index checks first saw less than they claimed. One mutation was inert because `-` is a non-word character, so `19R-removed` still matched `^### Segment 19R\b`, and a live heading was quietly relying on that hole.

**Trade-off.** A gate checks only what is derivable. It verifies *agreement* where the repository states something to agree with; it cannot judge *adequacy*. The coverage gate shows the limit well. Neither of the two missing Tier-1 specs would have tripped it, because both surfaces *had* sections in `spec/operator_ui_concept.md` and lacked only a dedicated contract. It detects a surface with no spec, not a spec that says too little, nor one that says something no longer true.

Not every convention should become a test. The audit rejected a British-spelling check because it cannot tell prose from identifiers and would need an allowlist that grows forever; when the author later set US spelling for new prose (2026-09-07), it was set as a tie-breaker that nothing enforces, for the same reason. `docs/unenforced_conventions.md` records each convention that is deliberately left to a reader, and why.

One more consequence is operational: **a green `ruff` is not evidence**. Most of these gates read no Python and run only under `pytest`, so a lint-only run passes all of them by not running them.

### 6.4 Separate readers

**Decision.** A change is read by something other than what wrote it. Two readers are checked-in agent definitions under `.claude/agents/`, separate from whichever agent wrote the code. Neither is confined by construction: both have `Bash`. `diff-reviewer` has no `Write` or `Edit` and is read-only by its charter ("You never edit: report, don't fix"); `spec-writer` has them and is held to `spec/` by its charter:

- **`spec-writer`** updates `spec/` to match what shipped **at a close**, may write only under `spec/`, and outside a close verifies and reports: its charter says "Do not re-align the spec to the code" and "Report it".
- **`diff-reviewer`** reads a PR diff cold, with no prior context, and checks it against the governing spec. Among other things, it reports claims in the commit message that the diff does not support and scope beyond the stated purpose, and it reports nothing at all if nothing is wrong. Its charter says "inventing findings to look thorough makes you worse than no reviewer". It carries no model pin, deliberately, because a reviewer should not be capped at a smaller model than the author.

A third reader is external: Codex, a different vendor's model, reviews pull requests automatically. Its own summary comment names the triggers as a PR opened for review or a draft marked ready. It commented on 159 pull requests opened between 2026-09-14 and 2026-09-23, against 213 merged in that window; from June to 2026-09-13 the figures were 64 against 658. Since then it has become a merge condition rather than a sometime reader: the agent marks each PR ready so that Codex reviews it, answers each finding on its thread with a fix or a traced reason not to, and merges only once Codex reports clean on the head. In segment 14F's seven code PRs it found four real defects before merge (a dropped Cc, a test send that discarded the operator's draft, a regenerate racing a queued send, an unaudited stamp) and one documented behavior the code did not keep.

A fourth reading is periodic: each codebase assessment (6.5) runs three reads by agents with no part in the window's builds, a spec-vs-code audit, a defect read with scratch tests, and a read of the non-RRW packages with a route fuzz. On 2026-11-06 that read found a medium defect the per-PR readers had all passed: a per-row send that Microsoft refuses still reads as sent (`guide/findings_2026-11-06_assessment.md`, M1). Each reader sees what its framing points it at, and the cold whole-window read is framed differently from any per-PR one.

**Why.** This is SDD's second core claim, that maker and checker must be separate, arrived at from RRW's own defect history. The audit classified the thirty most recent fix commits. Six (20%) were documentation corrections a spec reader would have caught. Nine (30%) were logic bugs, several "discovered by review-like activity rather than by the suite". One was a case-insensitive-email P0 found by a fresh reader who thought of the case, and fixed with 265 lines of new tests. Before the readers existed, "a diff goes from written to merged with nothing reading it". The readers close that gap for two of the three defect classes.

**Evidence that the reader catches the class it claims.** The test was retrospective. `diff-reviewer` was run cold, in a worktree at `9b9cc457` (2026-05-11, "Segment 16A PR 6: Accounts Management tab"), against that commit's diff and the specs as they stood that day, with no hint of what to look for. That commit made the sys-admin invite path match emails case-insensitively (`users.py:222`) while `deps.py:46` still matched exactly. Codex reported that inconsistency 25 days later as P0.2, and `ab043317` fixed it.

The reviewer's finding #6 reads, in part: "`invite` … dedupes case-insensitively, so it *permits* `Alice.Smith@example.edu` while Entra will present `alice.smith@example.edu`. On mismatch, `get_or_create_user` creates a second row … and the invited row is orphaned. The only test … uses identical casing." That is the defect, its mechanism and the test gap, from the diff alone. It came from checking the commit message's claim that the pre-seeded row "picks up the principal naturally".

One caveat: the checklist was written after the defect was known, so this shows the checklist *as written* finds it cold, not that one written blind would have.

**The cadence was measured into shape.** A reader works only when run, and the history of this decision is the history of finding out what "when run" costs.

- **Unrun.** From 2026-09-06 to 2026-09-14, 70 pull requests named `spec-writer` and none named `diff-reviewer`. The reader validated above had not read a diff since the arc that created it. `spec-writer`, chartered for the close, had become the per-rung reader by default. The two were then given separate cadences.
- **Per rung: effective and too dear.** The per-rung read ran from 2026-09-14, and a merge-history audit measured it four days later, recorded here on 2026-09-19 (`tools/pace_audit.py`).
  - **Cost.** A slice carrying a read took a median 49 minutes merge to merge, against 23 without. The median slice went from 25 minutes to 44, and in-PR iteration from about 8 minutes to 23. Codex was reading every slice in the same week, so both readers are in those figures.
  - **Catch.** Of 78 response commits, 58 changed code or tests and fixed live defects. The 20 that changed only prose described the author overclaiming in a plan or a close.
- **Per item: the ruling.** On the author's ruling of 2026-09-18, `diff-reviewer` reads once per item, on the item's cumulative diff. A code slice outside any ladder still takes its own read, and a prose-only slice takes none (`CLAUDE.md` "Where work runs"). Its first re-take, over #2460–#2492, had iteration back to about **10** minutes and slices carrying a read down from 69% to 30%. Under it, at `3559c7a7` (2026-09-23), over 134 slices:
  - the median cycle is **31** minutes;
  - **44%** of slices carry a response to a read, from either the cold read or Codex;
  - a product slice with one takes **38** minutes against **27** without. A round of reading and responding therefore costs about 11 minutes, and the cold-read half of it is paid once per item rather than once per rung.

**What the cadence does not touch.** A whole-history audit on 2026-09-20 separated three step changes in the median slice:
- from **11** to **17** minutes between Segment 1 and 19C, as the suite grew and CI lengthened;
- to **22** on 2026-09-04, when the doc and test gates arrived;
- to **44** under the per-rung reads, with Codex also reading every slice, then down to about **30** under the per-item cadence.

Under all three sits *turn*, the time from the previous merge to a slice's first commit. That audit found turn a flat floor, a median of 8–10 minutes in every era, that barely scales with the slice's size. Re-taken at `3559c7a7`, the median under the per-item cadence was 8.2 minutes.

To split turn into the wait for an instruction and the build before the first commit, a campaign stamped slices' first commits with an `Instruction-Received` trailer. It ran over #2495–#2516, and its first reading, n=14, had *wait* at a median 3.5 minutes and *build* at 3.0. With the lost stamps recovered (below), the reading reversed. Across 37 stamped slices, *wait* was a median **1.9** minutes and *build* **5.8**. So the floor is mostly the agent's own work before it commits: loading context, reading the plan, running the gates. No cadence rule touches that, and none should.

The campaign had a lesson of its own. Git reads trailers only from a message's last block, so 21 of the first 37 stamps, written in a paragraph of their own, were silently discarded. Since 2026-09-22, `tools/pace_audit.py` has read the line anywhere in the message, which recovered them. Nothing catches a slice that omits the line. Stamping is therefore a campaign run when a figure is being re-taken, not a standing rule (`CLAUDE.md` "Where work runs").

**The cadence figures had a blind spot from 2026-10-19 to 2026-11-06.** From #3150 on, PRs have reached `main` two ways: 319 as merge commits and 188 squash-merged by 2026-11-06, about half each in its last week (98 and 97), and 89 of the 91 in the 2026-11-06 assessment's window squash-merged. `tools/pace_audit.py` and `tools/code_metrics.py`'s churn walk read merge commits only (`git log --merges`), so neither saw a squash-merged PR. The merge method changed for reasons of its own, and nobody measured what it cost the measurement; re-taking this document's figures found it (findings 2026-11-06 N9). Both tools now count a squash commit whose subject ends `(#N)` as a PR. One part cannot be recovered: a squash merge keeps one commit and discards the branch's own, so a squash-merged PR's first commit, iteration and review-response commits are not in git. The pace audit marks them unknown, says how many PRs were squash-merged, and splits the cycle into turn, iteration and push-to-merge over the merge-committed PRs only. The figures in this section are dated before the switch.

Running the gates is part of that floor. The full suite measured 4–5 minutes a run on 4 cores (about 270 s in 22H, 287 s on 2026-11-05 in 22I Item 2, 246 s for 8,451 tests at `c912ae53`), so 22H cut what the gates cost locally by making the targeted loop a stated rule: the test files the change reaches between edits, the full run once before the push (`CLAUDE.md` "Where work runs"). Separately, 22H and 22I cut the CI wait after the push, which is merge-to-merge time rather than *build*. 22H split CI's `test` job, 6 m 42 s (#3620), into three shards of about 2 m 30 s (#3629). 22I split `CI - Postgres` into three shards as well, from 3 m 51 s–6 m 00 s as one job to 2 m 45 s in three shards (22I Item 1, #3634 and #3636). On `main` at `c912ae53` the two workflows took 2 m 34 s and 3 m 46 s; the longest job is one Postgres integration shard at 2 m 54 s of tests, against 1 m 38 s for its sibling, so the split by file letter has drifted out of balance. Since 2026-11-06 every codebase assessment records these figures (6.5).

**Trade-off.** Each round of reading costs time, and the cold read happens only because the agent runs it. A skipped read leaves no trace except that its item's `Status` records no findings, so the per-item record of reads and findings is how the next audit re-measures whether the cadence holds. Codex is the exception: as a merge condition it leaves a review on every PR, which is the one reader whose absence the history would show.

### 6.5 Periodic sweeps and snapshots, not continuous synchronization

**Decision.** Keep spec and code in agreement through scheduled sweeps and dated snapshots rather than a per-PR sync requirement.
- **Snapshots.** By 2026-11-06, twenty-five dated codebase assessments had been written in the Claude Code lineage, and four whole-repository assessments in a separate Codex lineage. Each audits the functional areas against the code — "a route registered, a service function called, a test covering it — not against the spec's own claims". Each measures the same things the same way: lines by area under the classification pinned in `guide/assessment.json`, duplication and churn from `tools/code_metrics.py`, and, since 2026-11-06, test runtime locally and per CI job. The current one is `guide/codebase_assessment_06nov.md`; the Codex lineage's last, `guide/archive/codex_assessment_30sep.md`, was archived on 2026-11-04 with no successor.
- **Registers.** Since 2026-11-02 every assessment files a findings register beside it, `guide/findings_<date>_assessment.md`: one row per defect, drift or gap, tagged by who decides it (the code, the author, or the spec), and struck by the PR that fixes it. The 2 November and 3 November registers were each worked off within a day (#3522–#3543, #3568–#3573) and archived with every row done, closed or ruled. The idea is older: Segment 19S Item 1 opened eight entries and disposed of all of them within a day.
- **Sweeps.** A whole-folder drift sweep is due every eight weeks or 500 merges, whichever comes first. `tools/close_check.py --stale` answers whether one is due.

**Why.** Per-PR sync would be a rule the practice already breaks by design (6.1). Sweeps fit the phase model: a segment closes, its spec is written on the way out, and periodically someone reads a whole folder against the whole codebase to catch what the closes missed. A register turns a snapshot from an opinion into a checklist: what it found cannot evaporate between snapshots, because the next one opens by settling the last one's moves.

The snapshots have paid. One fixed two real logic bugs with regression tests. The 2026-09-04 assessment caught its own area-classification error, where generated HTML had been counted as templates for a phantom +38%. It pinned the classification in `guide/assessment.json` so every later snapshot counts the same way; on 2026-11-06 the measurement reproduced the previous snapshot's file-by-file counts exactly before taking new ones. The 3 November snapshot's medium defect, a directory recheck that changed setup without sending a validated session back to draft, was found by its defect read and fixed the next morning (#3568). Two model lineages reading the same code disagree usefully, and a register keeps the disagreement from evaporating.

**Trade-off.** This is the mechanism that missed a one-word, three-place contradiction for three months. A sweep is only as good as the reader's attention on the day, and a reader re-reading a familiar file is the weakest reader there is. That is why 6.3 exists: the sweep finds what a person can find, and the gate finds what a person cannot. Neither replaces the other. A snapshot also finds a defect only after it has shipped: the 6 November one found a medium already live on Azure for a day.

### 6.6 The human is the verifier of last resort — and there is no autonomous loop

**Decision.** End-to-end verification of anything the test suite cannot exercise is done by the author looking at it. That covers templates, redirects, layout, in-browser JS and real auth. The author runs the app locally with fake auth and looks at each change in a browser. What only a deployment shows, real auth, the directory, mail and the network, has had one since 2026-10-31: the author dispatches a release and checks it there, and what is owed waits in `guide/things_to_check_in_browser.md` and `guide/post_azure_todo_checklist.md` until it is checked. 14F's first real sends were checked that way, on Azure, within a day of shipping. A PR description must say what was not verified rather than claim that it was.

No agent runs unattended. An agent follows a pull request it opened through CI and review, under the instruction that opened it. It does not start new work on its own, and it does not merge without the author's word: a PR merges when the author says so for it, or for the run of slices it belongs to ("merge when passing"), and then only once CI is green on the head and Codex is clean. A release to the deployment, and the import that precedes it, is the author's call each time, given in so many words. The one standing exception, ruled 2026-10-23, is a batch the author hands over by name as `babysit-merge`: there the agent merges each PR once its gates hold on the head, and the author's browser check follows the batch rather than each merge.

**Why.** Half of RRW's real defects live where no reader can see them. The audit's census put **fifteen of thirty** fix commits (50%) in the browser-only class: caption selectability, a 4 px misalignment, a keypress toggling a card, all "touching only templates and `tools/`". Against SDD's central claim that specs catch what unit tests cannot, this is the class *neither* catches, because a layout has no machine-checkable definition of done.

The practice has two partial answers. Scaffold-first (Section 5) puts a new surface in front of a person before it is wired. The agent can also drive a headless browser to measure a layout or take a screenshot, and attach the measurement or send the picture before the PR; on 2026-11-06 a mockup of a proposed layout, rendered from the real page, was how the author chose it. Neither is a person looking at the shipped page. Scaffold-first applies only to new surfaces, and a measured layout is only as good as the question asked of it. So the gap is not "nothing looks at layout" but "nothing looks at layout *twice*".

The loop-engineering threshold for running autonomously is a machine-checkable definition of done, and work long enough for autonomy to matter. A solo project whose slices are sized to be reviewed in one sitting does not meet it, and the audit says so in as many words. The `diff-reviewer` says the same about itself: "You will not catch rendering, layout, or in-browser JS behaviour. Those need a browser, not a reader."

**Trade-off.** The verifier is a person, and the practice's throughput is bounded by that person's attention. That is accepted deliberately as the right shape for the project's scale, not as an immature version of an autonomous one. It is also where the practice's answer is most partial: the browser-only class is "both the largest measured category of real defects here and the one no layer of the current practice catches". A deployment adds a second class with the same property: a refused send, a missing mail permission or a directory that answers slowly can be faked in a test but only met on Azure, and the author's check there is the only thing that meets it.

### 6.7 The reasoning travels with the change

**Decision.** Commit messages and PR bodies carry the *reasoning* — what was found, what was measured, why the obvious alternative was not taken — and not only the change. Plans record what was intended and what was done. Dated documents such as audits and assessments are annotated rather than silently rewritten. The merge policy is written in `CONTRIBUTING.md` rather than enforced by branch protection, after measurement showed it was already followed: wait for the Postgres job when the diff touches `alembic/`, `app/db/` or any querying service; merge ahead of it for docs and dev tooling. A reviewer's finding that is not fixed is answered on its thread with the path traced and the reason, so the decision not to act is itself on the record.

**Why.** The failure mode the vibe-coding literature names most sharply is "debugging code *nobody fully wrote or owns*". RRW's mitigation is that the intent is recoverable. The audit reconstructed a three-month-old drift's frequency evidence from commit messages alone, "precisely because of that". It is the same principle as the audit-event envelope on every mutating service (design rationale §6.7), applied to the codebase instead of the data: defensibility by construction. Writing the merge policy down rather than enforcing it comes from the same instinct. The audit found the judgment was sound, and one paragraph "survives a second contributor or a six-month gap" where branch protection would have added ceremony to a process that did not need it.

**Trade-off.** Long commit messages, long PR bodies, and an instruction file that grows. `CLAUDE.md` reached 266 lines before the audit's context-hygiene finding cut it to 183, by removing a fifty-module inventory that was duplicated in `spec/architecture.md` and *incomplete* there. It had grown back to 297 by 2026-09-23 and 337 by 2026-11-06, largely with the rules of 6.4's cadence, the gates of 6.3 and the targeted test loop. Reasoning written everywhere is written twice, and twice-written reasoning drifts; that is the same lesson as 6.3, one layer up. The plan budgets and `Status` compaction (Section 5) are the counter-pressure inside `guide/`. No equivalent budget yet holds the instruction file. And a squash merge keeps the PR's reasoning in one message but drops the commit-by-commit record of how the slice got there (6.4), which is reasoning of a different kind.

---

## 7. What RRW's practice deliberately is not

Scope discipline is part of the practice, so the exclusions are worth stating directly.

- **Not spec-as-source.** Code is edited by hand (by an agent, at the author's direction), and no spec is compiled into anything.
- **Not spec-first at PR granularity.** The spec co-change rate is 32% overall and 42% recently, and the phase rule (6.1) makes that a design rather than a lapse.
- **Not executable-spec.** The gates derive from what the repository states, or, for the type and format gates of §6.3, from the language itself, not from acceptance criteria written as tests.
- **No branch protection.** It measured that the stratified merge policy was followed without it.
- **Spec adequacy is not gated.** `tests/unit/test_spec_coverage.py` fails when a routing module has no spec at all. It does not judge whether a spec says enough, and there is no per-PR spec-sync gate, which would contradict the phase rule.
- **No spelling check.** The check was rejected on evidence.
- **No security scanning in CI.** That is recorded as a candidate in `guide/deferred_consolidated.md`, not silently absent.
- **No deployment from this repository.** It holds no cloud credential and no deploy workflow; a private repository imports a green commit and releases it.
- **No autonomous loop** of any kind.

Most of these are chosen. The security scan is deferred with a stated reason, which is the practice's way of saying "not yet" without saying "never". The coverage gate and the type checker were once in the same position, and both shipped, which is what "not yet" is supposed to turn into.

---

## 8. Measured against the claim

SDD's central claim is that specs catch what unit tests structurally cannot. Against RRW's own defect census (the practice audit's thirty most recent fix commits, 2026-05-16 → 2026-09-04):

| Defect class | Share | What catches it in RRW |
|---|---|---|
| Documentation drift: spec says one thing, code does another | 6 (20%) | The gates where the repository states something to derive a check from; `diff-reviewer` and `spec-writer` otherwise; the sweeps and assessments last |
| Logic bugs that landed with regression tests | 9 (30%) | The suite for the regression; a separate reader (`diff-reviewer` per item, Codex on every PR, an assessment's defect read) for the discovery |
| Browser-only: layout, selection, keypress, template JS | 15 (50%) | The author, looking. Nothing else |

The claim holds for the first class and half-holds for the second. For the largest class it is simply not the relevant mechanism, and a practice that pretended otherwise would be worse for it. The census has not been re-taken since; the 2026-11-06 register's rows read the same way (one logic defect a reader found after the fact, twelve drifts, none a regression the suite missed), but it is a register, not a census.

The 2026 literature characterizes AI-authored code by its shape: churn up 41%, duplication up 4×, refactoring collapsed. RRW measures itself with `tools/code_metrics.py`.
- **Churn is 1.2×** at `aab086fe` (2026-11-06), over all 3,648 PRs on `main`, 191 of them squash-merged. Of the deleted Python lines, 50.3% were under fourteen days old, against 40.8% of all lines in those files at that moment. The ratio was 1.0× on 2026-09-04 and 1.1× on 2026-09-23; over merge commits alone, the walk's reach until N9 was fixed, it read 1.3× at `c912ae53`. The squash-merged PRs pull it down, partly because they include the formatter's one pass (#3623), which deleted lines of every age. So recent work is rewritten a little more than its age alone explains. That matches a project that refines each surface in small passes after the author looks at it, and it is the figure to watch: the literature's AI shape starts here.
- **Duplication is 4.5%** at ten-line blocks for production code (`app/`), from 6.3% on 2026-09-23. The largest hits are still the sibling roster route slices, 26–32% of each in duplicated blocks, which is the one real finding; a formatter that breaks every long signature onto its own lines inflated their figure in the window it ran.

The codebase does not have the shape. Whether that is *because of* the practice is an inference; that the practice was in place while the codebase was built is a fact.

Where the practice is measurably behind:
- the browser-only class, and its deployment-only cousin (6.6);
- a spec set that is reliably right only at the boundaries of segments and items, and not across the whole corpus when one segment changes something the corpus assumed (6.1);
- a separate reader whose running depends on the agent that runs it (6.4);
- its own cadence figures: a squash-merged PR's turn and iteration are not in git, and most of the newest PRs were squash-merged (6.4).

---

## 9. Where the practice sits now

Read against the four shapes in Section 2, RRW is **spec-anchored with a phase rule**: plans lead in, specs settle out, the archived plan records the close, and disputes are settled in `spec/`. It is **mechanized at the seams** where the repository or the language states something a check can be derived from, it offers new gates an evidence bar of proof by mutation, adopted item by item, and it has shown it will retire a convention rather than mechanize it badly. It has **separate readers** on a cadence measured into shape: one cold read per item, an external model on every PR as a condition of merging, and a cold whole-window read at each assessment, whose findings become a checklist. And it has a **human verifier** where nothing else can look, held deliberately rather than as a stopgap, and now on a production deployment as well as a local run.

The practice audit's verdict was that RRW is "ahead on the thing that is hardest to retrofit and behind on the thing that is cheapest to fix". It was ahead because a spec set, a layered document model and a habit of writing reasoning down were there from the first commit and cannot be bolted on later. It was behind because the specific gates, the reviewer and the merge policy were each a file, and each was written in an afternoon once the evidence pointed at it.

The two months since then bear the asymmetry out. The gates multiplied and the reviewer's cadence was re-cut twice, each in a day or two, and each change was measured first. The language-level gates, the formatter and the CI split arrived within two days of the first build PR (#3584 on 2026-11-04 to #3636 on 11-05), each measured first: 307 errors to 0 (22C), 1,846 strict-mode errors fixed (22E), and a 6 m 42 s CI job to shards of about 2 m 30 s (22H). The application went into production on 2026-10-31 through a private import of one green commit, and 14F, built the following week, sent real email from it on the day its code merged. The cheap part kept arriving on evidence. What the window also shows is the cost of the cheap part's absence: a measurement nobody re-took (6.4) stopped working without anyone noticing, which is the audit's original lesson about vigilance, met again. **The expensive part of spec-driven development is the culture of writing things down before and after acting on them, and that part has to be there on day one. The cheap part is the tooling, and it can wait for the evidence, but only if someone keeps taking the evidence.**

---

## 10. The thesis in one paragraph

RRW practices a form of spec-driven development in which **plans carry intent into a segment, specs settle it on the way out, and the archived plan records that they did**. That phase rule makes the spec reliably right at segment boundaries and the plan reliably right inside them, rather than pretending either is right always. Where a convention can be derived from something the repository or the language states, the convention is a failing test, and an item that adds one can adopt the bar of showing it fails when the rule is broken. Where it cannot, a separate reader checks the diff against the spec, and periodically a cold reader checks the whole window and leaves a checklist. Where nothing can read — layout, selection, the browser, the live deployment — a person looks, and the practice says so instead of claiming otherwise. It runs no autonomous loop, because its definition of done is not machine-checkable for the defects that actually occur. It writes its reasoning down at every step, so that a codebase no one fully wrote is still one someone can fully explain. It was doing this before the term went mainstream, it measured itself against the term when the term arrived, and it kept the parts that held.

---

## Appendix — SDD prescription mapped to RRW practice

| What SDD prescribes | RRW's response | Evidence (re-takeable) |
|---|---|---|
| Specs are the source of truth | Yes, at segment boundaries; the plan is the source of truth inside a segment (§6.1) | `spec/README.md` authority statement; `guide/todo_master.md` "day-to-day source of truth for its own slices"; 19A "writes its spec on the way out" |
| Spec before code | On day one, literally; thereafter *plan* before code, *spec* after | First-day commit order 2026-04-27; spec co-change 32% (42% recent) against plan co-change 46% (82% recent) over first-parent PRs at `c912ae53`; the #2047 → #2062 arc |
| Requirements / design / tasks | One plan per scope, items within it: Opportunity → Decision → Judgment calls → Blast radius (measured) → PR ladder → Definition of done → Doc impact → Status | `guide/segment_plan_template.md`; `.claude/skills/segment-plan/SKILL.md`; `guide/archive/segment_19S_post_assessment.md` Item 10 |
| Spec catches drift tests cannot | A gate derived from what the repository states, where it states something; elsewhere a separate reader; last, the sweeps and assessments | The gates in §6.3; `app/services/audit.py` `EVENT_SCHEMAS`; 6/30 fix commits were doc drift; `guide/findings_2026-11-06_assessment.md` §4 |
| Maker and checker separate | `spec-writer` (at a close; reports divergence otherwise), `diff-reviewer` (cold, report-only, no model pin, once per item), Codex on every PR the agent opens, as a merge condition, and an assessment's cold whole-window reads. Validated retrospectively: run cold at `9b9cc457`, `diff-reviewer` found Codex's P0.2 (`ab043317`) 25 days early | `.claude/agents/`; `CLAUDE.md` "Where work runs"; `python3 tools/pace_audit.py --cut 2460` (turn and iteration from merge-committed PRs only); the Codex search in the note below |
| Machine-checkable definition of done | For code and specs, yes: 8,463 tests collected at `c912ae53` on two dialects plus the gates, with pyright strict and `ruff format` as gates (22C–22H). For UI and the live deployment, no: the author, looking | 15/30 fix commits browser-only; `CLAUDE.md` "Where work runs"; `guide/things_to_check_in_browser.md`; `pyright`; `ruff format --check .` |
| Spec coverage enforced | For absence, yes: every routing module registered, every mapped spec a live file, the declared-debt baseline empty. Adequacy, no | `tests/unit/test_spec_coverage.py`; `app/web/spec_registry.py`; `constitution.md` II |
| Living spec, continuously synced | Periodic instead: 25 + 4 dated assessments in two model lineages by 2026-11-06, each with a findings register since 2026-11-02, drift sweeps on a cadence | `guide/codebase_assessment_06nov.md`; `guide/archive/codebase_assessment_*.md`; `tools/close_check.py --stale`; `docs/archive/practice-audit-2026-09-04.md` §2 |
| Code as a generated artifact | No. Hand-edited by agents at the author's direction; specs are prose | — |
| Autonomous agent loops | No, on stated grounds: the definition of done is not machine-checkable for the defects that occur | `docs/archive/practice-audit-2026-09-04.md` A.5 |
| The codebase should not take the AI-authored shape | Measured: churn 1.2×, duplication 4.5% at ≥10 lines | `python3 tools/code_metrics.py` (deterministic; about six minutes, most of it the churn walk) |

**Re-taking the numbers.** The current-state figures above were taken at `c912ae53` on 2026-11-06, except the cadence figures of §6.4, which are dated where they are used and cannot currently be re-taken (below):

- **Spec folder size:** `ls spec/*.md | wc -l; cat spec/*.md | wc -l`.
- **Archive counts:** `ls guide/archive/segment_*.md | wc -l`.
- **Co-change rates:** classify each pull request on `git log origin/main --first-parent` by the paths in `git diff --name-only <sha>^1 <sha>`. A pull request is a merge commit, or, since #3150 (2026-10-19), a squash commit whose subject ends `(#N)`; `--merges` alone misses the squash-merged ones. A live spec is under `spec/` but not `spec/archive/`; a live plan document is under `guide/` but not `guide/archive/`. The same classifier, restricted to merge commits and run at `376c9605`, reproduces the 2026-09-04 percentages; its raw counts differ from that day's by at most three.
- **Test count:** `pytest --collect-only -q`.
- **Test runtime:** `pytest -n auto --durations=15` timed on the container, and the per-job step times of the `CI` and `CI - Postgres` runs on `main` at the pinned SHA (the codebase assessment records both).
- **Type and format gates:** `pyright; ruff format --check .; ruff check --select E501 .`.
- **Cadence figures:** `python3 tools/pace_audit.py --cut 2460`. It counts squash-merged PRs (since #3150) by their `(#N)` subject, but their turn and iteration are not in git, so those splits rest on the merge-committed PRs; the GitHub API's PR timeline would supply the rest.
- **Churn and duplication:** `python3 tools/code_metrics.py`. Its churn walk reads every PR, merge commit or squash commit, since 2026-11-06 (N9).
- **Codex coverage:** a GitHub search, `is:pr commenter:chatgpt-codex-connector[bot] created:>=2026-09-14` against `is:merged created:>=2026-09-14`, in `repo:philoyhc/review-robin-web`. It needs the API, because PR comments are not in git.
- **Defect census:** `docs/archive/practice-audit-2026-09-04.md` §4 R2, as of that audit.
