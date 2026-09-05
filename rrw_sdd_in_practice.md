# Review Robin Web — Spec-Driven Development in Practice

## 1. Introduction

Review Robin Web (RRW) is a web application for running structured institutional review cycles. `rrw_design_rationale.md` explains what it *is* and why it looks the way it does. This document is its companion on a different axis: it explains how RRW is *worked on* — the practice by which a single author, working through AI coding agents with no local dev loop, has landed some two thousand pull requests without the codebase taking the shape that AI-authored codebases are reported to take.

The practice has a name now. Through 2026 the term **spec-driven development** (SDD) went mainstream for the family of methods in which specifications are the durable source of truth and code is the thing kept in agreement with them. RRW was doing a form of this before the term went mainstream, and — more usefully for a reader — it is doing a *particular* form of it, with rules about which direction authority runs and when, that the general term does not fix. This document states that form, records why each of its parts is the way it is, and says plainly where it departs from what SDD prescribes and where it falls short of it.

It is not a how-to; `CONTRIBUTING.md` and `CLAUDE.md` are that. It is not an audit; `docs/practice-audit-2026-09-04.md` is that, and this document leans on its findings rather than repeating its evidence. It presents the rationale for the practice, in the same register as the design rationale: where a choice could plausibly have gone another way, the point is to record why it went the way it did.

The document is drafted with the help of Claude Code, with access to the repository. Every number in it was produced by a command run against the repository on 2026-09-04 at `main` = `376c9605`; the ones that are easy to re-take are listed with their method in the appendix.

**Revised 2026-09-05** after external review. Section 6.1's trade-off now states the exit asymmetry in one place; Sections 5 and 6.6 name scaffold-first as the partial answer to the browser-only class; Section 6.4 records a retrospective test of the reviewer against the 2026-05-11 email-case commit; "before the term arrived" tightened to "before the term went mainstream" (Sections 1, 3). No number changed.

---

## 2. Spec-driven development, as the term is used

Strip the vendor framing away and the 2026 usage covers a small family of shapes, distinguished by which direction authority runs between spec and code:

- **Spec-first.** The spec is written, the code is produced from it, and the spec is the input to every change. The tool shapes that popularised this — a requirements / design / tasks triple, or a constitution / specify / plan / tasks / implement ladder — are workflows for getting from a stated intent to reviewed code with the intent still legible.
- **Spec-anchored.** The spec is the durable contract; code evolves against it and both are maintained. Authority is bidirectional but the spec is where disputes are settled.
- **Spec-as-source.** The code is a build artefact, regenerated from the spec, and not edited by hand. The most radical shape and the least common in working codebases.
- **Spec-as-test.** The acceptance criteria are executable, so agreement between spec and code is checked rather than read.

Two claims sit under all four. The first is that **a spec catches architectural violations and contract drift that unit tests structurally cannot** — a test checks that the code does what the test author expected, a spec checks that it does what was *asked*, and those are different questions. The second is that **the implementing role and the verifying role must be separate** — a model checking its own output is not a check.

RRW's practice is best read as spec-anchored, with a phase rule about direction (Section 6.1), mechanised at the seams where a code constant exists to derive a check from (6.3), with a separate reader where it does not (6.4), and with a human as the verifier of last resort where nothing else can look (6.6). The rest of this document is the evidence for that sentence and the reasoning behind each clause.

---

## 3. Where the practice came from

The first day of the repository is unusually legible about intent. On 2026-04-27, before any application code, the commit sequence reads: `README.md` → `AGENTS.md` → `FUNCTIONAL_SPEC.md` → `TECH_STACK.md` → `ARCHITECTURE.md` → `pyproject.toml` → `main.py` → `test_health.py` → `ci.yml`. The agent-instruction file, the functional spec, the stack decision and the architecture note all precede the first route. This was spec-first in the literal sense, on day one, and it predates the term going mainstream — the tool shapes that later carried the name already existed, but the practice here was not taken from them. It was the same habit that produced Review Robin (VBA)'s documented, rerunnable workbook: write the rules down before acting on them, and keep the control surface visible.

The practice then changed shape twice, and both changes are instructive.

**The destination spec was retired.** The day-one `FUNCTIONAL_SPEC.md` was a forward-looking description of where the application was meant to end up. By 2026-05-11 — two weeks and some eight hundred merges in — it was retired to `guide/archive/functional_spec.md` with a note that says exactly why: "its acceptance criteria, MVP list, and divergence notes all referred to a world that had already shipped (or been deliberately rescoped via segment plans)". A destination spec ages out of usefulness the moment the destination moves, which in AI-assisted development is daily. What replaced it was a *contract* spec — `spec/rrw_functional_spec.md`, technology-neutral, 2,214 lines, carrying its own currency date ("aligned with the system as of 2026-08-18; the functional contract is stable; ship-state may move ahead") — plus a per-page spec set underneath it. The shift from *destination* to *contract* is the shift from spec-first to spec-anchored, and it happened because the first form stopped working.

**The specs moved into a three-layer document model.** On 2026-04-27 itself, `doc/` was renamed `guide/` and took the plans; on 2026-05-01 the root-level specs were moved into `spec/` and `docs/`. That model (Section 4) is what the rest of the practice hangs off.

---

## 4. The three-layer document model

RRW keeps three documentation folders, each with a README that states its question and indexes its contents, and each with an `archive/` subfolder whose README is a hand-maintained index. The split is by *question answered*, not by audience or format:

| Folder | Answers | Authority | Today |
|---|---|---|---|
| `spec/` | *What is X supposed to look like and behave like?* | The contract. "When the code drifts from a spec, the spec is the canonical source — fix the code (or update the spec deliberately as part of a feature change, never silently)." | 36 live files, 18,483 lines; 5 archived |
| `docs/` | *How does X work today?* | Ship-state. `docs/status.md` is "authoritative for what does the code currently do". | 17 files |
| `guide/` | *What are we building next, and how?* | The plan. A segment plan is "the day-to-day source of truth for its own slices" while it is live. | 5 live segment plans; 90 archived, in a 132-row index |

Read those three authority statements together and they contradict each other: the spec is canonical, ship-state is authoritative, the plan is the source of truth. The contradiction is resolved by *phase*, and stating that resolution is the most useful thing this document does — see Section 6.1. In one line: **the plan leads while a segment is open, the spec is settled when it closes, and `docs/status.md` records that it did.**

Two features of the model carry more weight than they look:

- **Archives are records, not contracts.** Everything under an `archive/` is excluded from the documentation gates (Section 6.3) and is kept for rationale, not for behaviour. This lets specs be consolidated and retired freely — five have been — without losing the reasoning that went into them, and without a retired spec ever being mistaken for a live one. The archived spec's header names the current spec that supersedes it.
- **The functional spec is an entry point, not a monolith.** Its §19 "Reading guide" maps each subject to the per-page or per-subsystem spec that carries the implementation-level contract. Two altitudes, deliberately: the functional spec changes rarely and describes intent in user terms; the per-page specs change with the surface and name routes, services and audit events.

---

## 5. The unit of work: the segment plan

Everything in RRW lands through a **segment** — a coherent scope with a plan in `guide/segment_*.md`, a PR ladder, and a definition of done. The plan is the practice's equivalent of the requirements / design / tasks triple, held in one file per segment, with two additions the popular shapes lack. A mature item (19C Item 1 is the reference) runs:

> Opportunity → Decision (converged design) → Semantics, per mechanism → Judgment calls — decided → Scope / blast radius (measured) → PR ladder (each slice independently shippable) → Definition of done → Open questions → Doc impact

The additions are **blast radius, measured** — the files and behaviours the change will touch, counted before the first slice is cut — and **doc impact**, which names in advance which `spec/` files the segment will change and what it will change in them. The definition of done routinely ends with a line of the form "`spec/csv_contracts.md` / `roundtrip_coverage.md` / `settings_inventory.md` updated; full suite + `ruff` green". The spec commitment is made at planning time even though the spec edit lands last (Section 6.1).

Three things about how plans are used matter more than their shape:

- **Plan-to-build is hours, not weeks.** 19C Item 1 was planned and shipped on the same day (plan committed and #2010 merged, both 2026-08-20). Plans are not a phase gate; they are the thinking, written down so the agent building slice 3 has the same intent as the one that built slice 1.
- **Plans are revised by the build, and say so.** The 19C Item 1 plan carries a four-rung PR ladder and, above it, a status block reading "the PR ladder below collapsed to one PR — intermediate slices would have left a dual-carrier state, which is exactly what this item removes … Decisions confirmed at build: …". The plan records what was intended, what was done, and why they differ. This is the plan behaving as a spec-anchored artefact rather than a spec-first one.
- **Consequential UI lands scaffold-first** (convention dated 2026-08-15). A new page, card or navigation affordance lands as a static placeholder — real copy and layout, inert controls — in its own PR before any behaviour is wired. The surface is agreed on the placeholder; the wiring PRs then carry no UI churn. It is the UI-shaped version of writing the contract before the implementation — and it is also the practice's one foothold on the defect class nothing else reaches (Section 6.6): the placeholder is looked at on the dev slot before anything is wired to it, so layout is agreed by a human at the one moment it is cheapest to change.

---

## 6. The core decisions

Each decision below is stated as *what was decided, why, and what it trades off*, with the evidence that it is actually followed rather than merely written down.

### 6.1 Plan on the way in, spec on the way out

**Decision.** Within a segment, the *plan* carries the intent and leads the code; the *spec* is updated at the close, to match what shipped. Segment 19A states the rule in one clause: "every shipped segment that locks a UI contract writes its spec on the way out." The `spec-writer` agent's charter is the same rule from the other side: its job is to write specs "to match the code … so the specs never drift from reality".

**Why.** A spec edited slice-by-slice during a build describes a moving target and is wrong between every pair of slices. A spec written once at the close describes the settled contract and is right until the next segment opens it. The plan absorbs the in-flight ambiguity — it is expected to be revised by the build — so that the spec never has to. This is a deliberate departure from spec-first at PR granularity, and it is the single most important thing to understand about how RRW's practice differs from the textbook.

**Evidence that it is followed, not just stated.** Across all 2,088 first-parent merges, 1,298 touch `app/`; of those, only **185 (14%)** also touch a live spec in the same PR, while **261 (20%)** touch a plan in `guide/`. Over the last 200 merges the plan co-change rate rises to **51%** and the spec rate to **20%**. Separately, **193 merges (9%)** touch `spec/` and no application code at all — the spec-on-the-way-out PRs. The cleanest single case is the semantic-token migration (#2047 → #2062, 2026-08-23): sixteen PRs, of which the first five touched only `guide/` (the plan), the next ten touched `app/` and no spec, and the sixteenth touched two specs and closed the item.

**Trade-off, stated plainly.** There is a window of spec drift inside every open segment, by design. During it, `spec/` describes the last settled state and `guide/` describes the intended next one; a reader who consults only `spec/` mid-segment will be wrong about what is being built. Segments are short (days, not months) and the plan names its doc impact up front, so the window is narrow — but it is real.

The rule is also **asymmetric at its exit**, and the paragraph above should not be read as if a mechanism sat there. Neither end is mechanised: nothing blocks a PR that has no plan, and nothing blocks a segment closing without its spec edit — the definition of done is a line in a markdown file. The difference is in what happens when the rule is broken. A missing plan is *self-revealing*: an agent asked to build slice 3 with no plan has nothing to build from, and the gap surfaces before code lands. A missing spec edit is *silent*: the code works, the tests pass, `docs/status.md` records the ship, and nothing looks for the spec. The 193 spec-only merges are evidence that the exit is usually taken; the two Tier-1 specs missing since 2026-05-11 (Section 6.3) are evidence that when it is not, nothing notices. So the honest statement is that the phase rule is held by *visibility* on the way in and by *convention* on the way out — and the one thing that would make the exit mechanical, a route-to-spec coverage gate, is deferred (Section 7). What none of this covers is Section 6.5's cost: drift that is *not* noticed at the close survives it.

### 6.2 Two altitudes of spec

**Decision.** Keep a technology-neutral functional spec that describes intent in user and concept terms, and a per-page / per-subsystem spec set that names routes, services, data types and audit events. The functional spec points down (§19 reading guide); the per-page specs point up.

**Why.** A single spec at one altitude is either too abstract to check code against or too concrete to survive a refactor. Splitting the altitudes lets the functional contract stay stable — it carries a currency date and expects "ship-state may move ahead" — while the per-page specs move with the surface. It is also the split a new reader needs: the functional spec is the stated entry point; the per-page spec is where a diff reviewer looks.

**Trade-off.** Two places to update, and only the functional spec dates itself: **4 of 36** live spec files carry a currency line. The others are assumed current because the gates (6.3) and the sweeps (6.5) would have caught otherwise — an assumption the practice audit found to be false in three places (6.3).

### 6.3 A convention becomes a failing test, not a paragraph

**Decision.** Where a convention can be derived from a code constant, enforce it with a test that reads the constant, so the check cannot go stale when the constant changes. RRW has four such gates: the `EVENT_SCHEMAS` audit-envelope allowlist (strict mode in tests, log-and-write-through in production), and the three checks in `tests/unit/test_doc_conventions.py` — every lifecycle table in a live spec must agree with `DISPLAY_LABELS`; the retired pre-19B button vocabulary must not be *prescribed* in live prose (with line- and file-level escape markers for historical references); and `CLAUDE.md` / `AGENTS.md` must be byte-identical.

**Why.** The practice audit's decisive finding was not a stale word. It was that `expired → "Closed"` landed 2026-06-01, three live specs still said "Expired" three months later, and the contradiction had **survived a deliberate whole-folder documentation sweep** that re-read exactly those files. In the audit's words: "Vigilance is not failing here through carelessness. It is failing at the thing vigilance is structurally bad at." The remedy is the `EVENT_SCHEMAS` idiom applied a second time — the rule lives in code, so drift fails the suite — and it caught five live violations on its first run. The failure messages name the remedy, including the one case where the mapping rather than the prose is what changed.

**Trade-off.** The gate checks only what is derivable. It verifies *agreement* between spec and code where a constant exists to agree with; it cannot detect *absence*. Two Tier-1 specs flagged as missing on 2026-05-11 — `spec/permissions.md` and `spec/email_template_editor.md` — are still missing on 2026-09-04, invisible to every automated check. The obvious extension, a coverage gate mapping every operator route to a spec file, is scoped in Segment 19A Part 3 and deliberately deferred ("confirm need before scoping"). The audit also *rejected* the other obvious extension, a British-spelling check, because it cannot distinguish prose from identifiers and would need an allowlist that grows forever. Not every convention should become a test; the ones that should are the ones with a code constant behind them.

### 6.4 A separate reader

**Decision.** Two checked-in agent definitions under `.claude/agents/`, read-only by construction and separate from whichever agent wrote the code. `spec-writer` updates `spec/` to match the code after a change, may write only under `spec/`, and must "flag drift … rather than silently rewriting". `diff-reviewer` reads a PR diff cold, with no prior context, checks it against the governing spec, reports claims in the commit message the diff does not support, reports scope beyond the stated purpose, and reports nothing if nothing is wrong — "inventing findings to look thorough makes you worse than no reviewer". It carries no model pin, deliberately: a reviewer should not be capped at a smaller model than the author.

**Why.** This is SDD's second core claim — maker and checker must be separate — arrived at from RRW's own defect history. The audit classified the thirty most recent fix commits: six (20%) were documentation corrections a spec reader would have caught; nine (30%) were logic bugs, several "discovered by review-like activity rather than by the suite" — a case-insensitive-email P0 found by a fresh reader who thought of the case, fixed with 265 lines of new tests. Between the periodic assessments and the one external review campaign, "a diff goes from written to merged with nothing reading it". The reviewer closes that gap for two of the three defect classes.

**Evidence that it catches the class it claims.** Two runs, on unequal targets. The first, on the practice audit's own PRs, found five claim-versus-reality defects (fixed in `5d017eb9`), including a commit message that claimed three milestones came from a file that contained none of them — real, but the documentation class, and a soft target. The second was a retrospective test on the class that matters. The reviewer was run cold, in a worktree checked out at `9b9cc457` (2026-05-11, "Segment 16A PR 6: Accounts Management tab"), against that commit's diff and the specs *as they stood that day*, with no hint of what to look for. That commit made the sys-admin invite path match emails case-insensitively (`users.py:222`) while `deps.py:46` still matched exactly — the inconsistency Codex reported 25 days later as P0.2 and `ab043317` fixed with 265 lines of new tests. The reviewer's finding #6 reads, in part: "`invite` … dedupes case-insensitively, so it *permits* `Alice.Smith@example.edu` while Entra will present `alice.smith@example.edu`. On mismatch, `get_or_create_user` creates a second row … and the invited row is orphaned. The only test … uses identical casing." That is the defect, its mechanism, and the test gap, from the diff alone. It arrived through step 2 rather than step 4: the commit message asserted that the pre-seeded row "picks up the principal naturally", and the reviewer checked the assertion. The same step also caught "19 new integration tests" against a file with seventeen.

Two caveats belong beside that result. The reviewer's checklist was written after this defect was known, so the test shows the checklist *as written* finds it cold — not that a checklist written blind would have. And the same run produced ten further findings against the segment plan and the specs of the day (missing pagination the plan called for, an unplanned invite-by-email feature bundled into a toggles PR, a `chrome-link` class that styles nothing on that page) which this document has not verified.

**Trade-off.** The reader works when run, and "when run" is the honest qualifier. Both agents are invoked on request, not by a hook; six commit messages name `spec-writer` and five name `diff-reviewer`. A reader that is not run is a paragraph — and a reader that is run returns twelve findings on a thousand-line PR, which is a reading cost the author pays every time. Making the pass routine is the open item; making it cheap enough to *stay* routine is the constraint on how.

### 6.5 Periodic sweeps and snapshots, not continuous synchronisation

**Decision.** Keep spec and code in agreement by scheduled whole-folder sweeps and dated snapshots rather than by a per-PR sync requirement. Thirteen dated codebase assessments have been written (twelve archived, 2026-05-09 → 2026-08-19, plus the current 2026-09-04 one), each auditing every functional area against the code — "a route registered, a service function called, a test covering it — not against the spec's own claims". Two whole-`spec/` sweeps (2026-05-11: 25 files, 10,224 lines touched; 2026-08-18) and a `docs/` sweep (2026-08-19) have run. Segment 19A exists to make the sweep a cadence rather than an event.

**Why.** Per-PR sync at 14% co-change would be a rule the practice already breaks (6.1). Sweeps fit the phase model: a segment closes, the spec is written on the way out, and periodically someone reads the whole folder against the whole codebase to catch what the close missed. The assessments in particular have paid: one fixed two real logic bugs with regression tests; the 2026-09-04 one caught its own area-classification error (generated HTML counted as templates, a phantom +38%) and pinned the classification in `guide/assessment.json` so every future snapshot counts the same way.

**Trade-off.** This is the mechanism that missed a single-word, three-place contradiction for three months. Sweeps are only as good as the reader's attention on the day, and a reader re-reading a familiar file is the weakest reader there is. That is why 6.3 exists: the sweep finds what a human can find, and the gate finds what a human cannot. Neither replaces the other.

### 6.6 The human is the verifier of last resort — and there is no autonomous loop

**Decision.** End-to-end verification of anything the test suite cannot exercise — templates, redirects, layout, in-browser JS, real auth — happens on the Azure dev slot after deploy, by the author looking at it. A PR description must say so rather than claim verification. Nothing in the practice runs unattended: no autonomous loop, no cron, no agent that merges.

**Why.** Half of RRW's real defects live where no reader can see them. The audit's census put **fifteen of thirty** fix commits (50%) in the browser-only class — caption selectability, a 4 px misalignment, a keypress toggling a card — "touching only templates and `tools/`". Against SDD's central claim that specs catch what unit tests cannot, this is the class *neither* catches: there is no machine-checkable definition of done for a layout. The practice has one partial answer, and it sits upstream rather than downstream: scaffold-first (Section 5) puts the layout in front of a human on the dev slot *before* it is wired, so the surface is agreed at the one moment it is cheap to change. It does not catch regressions after wiring — the 4 px misalignment and the keypress toggle both arrived in code that was already wired — and it applies to new surfaces, not to changes to existing ones. So the gap begins not at "nothing looks at layout" but at "nothing looks at layout *twice*". The loop-engineering threshold for running autonomously — a machine-checkable definition of done, and long enough to matter — is not met by a solo project whose slices are sized to be reviewed in one sitting, and the audit says so in as many words. The `diff-reviewer` says the same thing about itself: "You will not catch rendering, layout, or in-browser JS behaviour. Those need the Azure dev slot, not a reader."

**Trade-off.** The verifier is a person, and the practice's throughput is bounded by that person's attention. This is accepted deliberately as the right shape for the project's scale, not as an immature version of an autonomous one. It is also the place where the practice has only a partial answer: the browser-only defect class is "both the largest measured category of real defects here and the one no layer of the current practice catches". The gap is filed (`5eebec53`, the template-JS runtime-test gap), not closed.

### 6.7 The reasoning travels with the change

**Decision.** Commit messages and PR bodies carry the *reasoning* — what was found, what was measured, why the obvious alternative was not taken — not only the change. Plans record what was intended and what was done. Dated documents (audits, assessments) are annotated with dated correction notes rather than silently rewritten. The merge policy — wait for the Postgres job when the diff touches `alembic/`, `app/db/` or any querying service; merge ahead of it for docs and dev tooling — is written in `CONTRIBUTING.md` rather than enforced by branch protection, after measurement showed it was already followed.

**Why.** The failure mode the vibe-coding literature names most sharply is "debugging code *nobody fully wrote or owns*". RRW's mitigation is that the intent is recoverable: the audit reconstructed a three-month-old drift's frequency evidence from commit messages alone, "precisely because of that". It is the same principle as the audit-event envelope on every mutating service (design rationale §6.7), applied to the codebase instead of the data: defensibility by construction. Writing the merge policy down rather than enforcing it is the same instinct — the substantive finding was that judgement was sound; one paragraph "survives a second contributor or a six-month gap" where branch protection would have added ceremony to a process that did not need it.

**Trade-off.** Long commit messages, long PR bodies, and a `CLAUDE.md` that grew to 266 lines before the audit's context-hygiene finding cut it to 183 by removing a fifty-module inventory that was both duplicated in `spec/architecture.md` and *incomplete*. Reasoning that is written everywhere is written twice, and twice-written reasoning drifts — the same lesson as 6.3, one layer up.

---

## 7. What RRW's practice deliberately is not

Scope discipline is part of the practice, so the exclusions are worth stating directly.

It is **not spec-as-source**: code is edited by hand (by an agent, at the author's direction), and no spec is compiled into anything. It is **not spec-first at PR granularity**: 14% co-change is the measured rate, and the phase rule (6.1) makes that a design rather than a lapse. It is **not executable-spec**: the gates derive from code constants, not from acceptance criteria written as tests. It does **not use branch protection**, having measured that the stratified merge policy was followed without it. It does **not gate spec coverage** in CI — the route-to-spec registry is scoped and deferred. It does **not check spelling**, having rejected the check on evidence. It does **not run security scanning** in CI — documented as a candidate future item in `guide/deferred_consolidated.md`, not silently absent. And it runs **no autonomous loop** of any kind.

Most of these are chosen. Two — the coverage gate and the security scan — are deferred with a stated reason, which is the practice's way of saying "not yet" without saying "never".

---

## 8. Measured against the claim

SDD's central claim is that specs catch what unit tests structurally cannot. Against RRW's own defect census (thirty most recent fix commits, 2026-05-16 → 2026-09-04):

| Defect class | Share | What catches it in RRW |
|---|---|---|
| Documentation drift — spec says one thing, code does another | 6 (20%) | `test_doc_conventions.py` where a constant exists; `diff-reviewer` step 5 otherwise; the sweeps last |
| Logic bugs that landed with regression tests | 9 (30%) | The suite for the regression; a fresh reader (`diff-reviewer`, an assessment, an external review) for the discovery |
| Browser-only — layout, selection, keypress, template JS | 15 (50%) | The author, on the Azure dev slot. Nothing else |

The claim holds for the first class and half-holds for the second. For the largest class it is simply not the relevant mechanism, and a practice that pretended otherwise would be worse for it.

On the codebase-shape metrics the 2026 literature uses to characterise AI-authored code — churn up 41%, duplication up 4×, refactoring collapsed — RRW measured itself in September 2026 with `tools/code_metrics.py` and found **churn 1.0×** (74.3% of 71,862 deleted lines were under fourteen days old, but so were 77.0% of all lines in those files at that moment: deletions are age-blind, marginally *older* than ambient), **duplication 6.5%** at ten-line blocks for production code (the ≥6 row is boilerplate; the one real hit is two sibling roster slices ~47% duplicated against each other), and a median surviving-line age of **109 days**. The codebase does not have the shape. Whether that is *because of* the practice is an inference; that the practice was in place while the codebase was built is a fact.

Where the practice is measurably behind: the browser-only class (6.6); two specs missing for four months (6.3); spec coverage unguarded; and a spec co-change rate that means `spec/` is reliably right only at segment boundaries.

---

## 9. Where the practice sits now

Read against the four shapes in Section 2, RRW is **spec-anchored with a phase rule**: plans lead in, specs settle out, ship-state is recorded, and the disputes are settled in `spec/`. It is **mechanised at the seams** where a code constant exists to derive a check from, and it has shown it will retire a convention rather than mechanise it badly. It has a **separate reader** that works when run. And it has a **human verifier** where nothing else can look, held deliberately rather than as a stopgap.

The practice audit's verdict was that RRW is "ahead on the thing that is hardest to retrofit and behind on the thing that is cheapest to fix" — ahead because a spec set, a layered document model and a habit of writing reasoning down were there from the first commit and cannot be bolted on later; behind because the specific gates, the reviewer and the merge policy were each a file, and were each written in an afternoon once the evidence pointed at them. That asymmetry is the practical lesson: **the expensive part of spec-driven development is the culture of writing things down before and after acting on them, and that part has to be there on day one. The cheap part is the tooling, and it can wait for the evidence.**

---

## 10. The thesis in one paragraph

RRW practises a form of spec-driven development in which **plans carry intent into a segment, specs settle it on the way out, and ship-state records that they did** — a phase rule that makes the spec reliably right at segment boundaries and the plan reliably right inside them, rather than pretending either is right always. Where a convention has a code constant behind it, the convention is a failing test; where it does not, a separate reader checks the diff against the spec; where nothing can read — layout, selection, the browser — a person looks, and the practice says so instead of claiming otherwise. It runs no autonomous loop, because its definition of done is not machine-checkable for the defects that actually occur, and it writes its reasoning down at every step so that a codebase no one fully wrote is still one someone can fully explain. It was doing this before the term went mainstream, it measured itself against the term when the term arrived, and it kept the parts that held.

---

## Appendix — SDD prescription mapped to RRW practice

| What SDD prescribes | RRW's response | Evidence (re-takeable) |
|---|---|---|
| Specs are the source of truth | Yes, at segment boundaries; the plan is the source of truth inside a segment (§6.1) | `spec/README.md` authority statement; `guide/todo_master.md` "day-to-day source of truth for its own slices"; 19A "writes its spec on the way out" |
| Spec before code | On day one, literally; thereafter *plan* before code, *spec* after | First-day commit order 2026-04-27; 14% spec co-change vs 20% (51% recent) plan co-change over first-parent merges; #2047 → #2062 arc shape |
| Requirements / design / tasks | One segment-plan file per scope: Opportunity → Decision → Judgment calls → Blast radius (measured) → PR ladder → Definition of done → Doc impact | `guide/segment_19C_refinements.md` Item 1 |
| Spec catches drift tests cannot | Where a code constant exists, a test derived from it does (four gates); elsewhere `diff-reviewer`; last, the sweeps | `tests/unit/test_doc_conventions.py` (3 checks); `app/services/audit.py` `EVENT_SCHEMAS`; 6/30 fix commits were doc drift |
| Maker and checker separate | `spec-writer` (writes spec to match code) + `diff-reviewer` (reads diff cold against spec; report-only; no model pin). Validated retrospectively: run cold at `9b9cc457` it found Codex's P0.2 (`ab043317`) 25 days early | `.claude/agents/`; 6 + 5 commit messages naming them; §6.4 |
| Machine-checkable definition of done | For code and specs, yes: 2,700 tests on two dialects + the gates. For UI, no — the author on the dev slot | 15/30 fix commits browser-only; `CLAUDE.md` "Where work runs" |
| Spec coverage enforced | Not yet — route-to-spec registry scoped (19A Part 3) and deferred; two Tier-1 specs missing since 2026-05-11 | `guide/segment_19A_spec_documentation.md`; `guide/codebase_assessment_04sep.md` §8 |
| Living spec, continuously synced | Periodic instead: 13 dated assessments, 2 spec sweeps, 1 docs sweep; a sweep missed a 3-month drift → gate (§6.3) | `guide/archive/codebase_assessment_*.md` (12) + current; `docs/practice-audit-2026-09-04.md` §2 |
| Code as a generated artefact | No. Hand-edited by agents at the author's direction; specs are prose | — |
| Autonomous agent loops | No, on stated grounds: definition of done not machine-checkable for the defects that occur | `docs/practice-audit-2026-09-04.md` A.5 |
| The codebase should not take the AI-authored shape | Measured: churn 1.0×, duplication 6.5% at ≥10 lines, median line age 109 days | `python3 tools/code_metrics.py` (deterministic, ~80s) |

**Re-taking the numbers.** Spec folder size: `ls spec/*.md | wc -l; cat spec/*.md | wc -l`. Archive counts: `ls guide/archive/segment_*.md | wc -l`. Co-change rates: classify each `git log origin/main --first-parent --merges` commit by the top-level folders in `git diff --name-only <sha>^1 <sha>`, excluding `spec/archive/`. First-day order: `git log --reverse --format="%ad %h %s" --date=short | head -20`. Defect census: `docs/practice-audit-2026-09-04.md` §4 R2. Churn and duplication: `tools/code_metrics.py`. All taken at `376c9605`.
