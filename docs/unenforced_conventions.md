# Conventions deliberately left unenforced

**The list `constitution.md` VI promises.** Article VI says a rule that
cannot be checked cleanly *"is dropped, or left as guidance, and the
decision is recorded"*, and its trade-off asks that the resulting list be
*"short, written down, and revisited when a constant appears that would
make one derivable"*. Until 2026-09-08 no such list existed, so every
concession looked identical to an oversight.

Two sections, because they need opposite treatment. **§1 is the list
proper** — rules that stay guidance, each with the reason a check would
be worse than the paragraph. **§2 is the revisit queue** — rules that
*could* be derived today, kept separate so they do not quietly acquire
the dignity of a decision. A rule in §2 is a task nobody has done; a rule
in §1 is a task nobody should do.

Every "verified" line below was re-run against the tree on the date
given, not carried forward from the audit that first found it. A list of
unenforced conventions whose claims have themselves gone stale would be
the joke it sounds like.

---

## 1. Deliberately unenforced

### 1.1 A template must render a lifecycle status through `lifecycle_label`

- **Written down at** `spec/session_home.md` §"Lifecycle state
  vocabulary"; the docstring of `app/services/lifecycle_display.py`.
- **Enforced in code, not in templates.** `DISPLAY_LABELS` is pinned by
  `tests/unit/test_lifecycle_display.py`, and the *specs* stating the
  mapping are pinned by `tests/unit/test_doc_conventions.py`. Neither
  reaches a template that simply declines to use the filter.
- **Why not.** A check would have to parse Jinja and know which
  variables in which templates carry a lifecycle enum. That list is a
  registry maintained by hand — a growing allowlist, which is the shape
  VI disqualifies.
- **What would change this.** A constant naming the lifecycle-bearing
  context keys, if one ever exists for another reason. Inventing one
  solely to enable the check is the tail wagging the dog.
- **Verified 2026-09-08.** Replacing `| lifecycle_label` with
  `| capitalize` in `app/web/templates/operator/sys_admin_sessions.html`
  leaves **2940 passed, 16 skipped** and `ruff` clean.

### 1.2 Route handlers stay thin — no SQL, no business rules

- **Written down at** `CLAUDE.md` "Architecture at a glance" §1;
  `spec/architecture.md`.
- **Why not, and the honest part:** a naive check fails on the tree as
  it stands. **17 of the routing modules contain `select(`**
  (`app/web/routes_operator/`, `app/web/routes_reviewer/`,
  `app/web/routes_*.py`, 2026-09-08). Whether each of those is inside a
  handler or in a module-local helper is exactly the judgement a grep
  cannot make, and a check that fails on 17 files the day it lands is
  the *"argued with, raised, then disabled"* sequence VI describes.
- **What would change this.** Not a constant — a cleanup. If the SQL
  moves into services, the check becomes a one-line grep with nothing to
  argue about, and this entry moves to §2.
- **Not a licence.** The convention still governs review; it is the
  *gate* that is absent, not the rule.

### 1.3 US spelling in new or rewritten prose

- **Written down at** `CLAUDE.md` "Project conventions" (author,
  2026-09-07).
- **Why not.** The entry disqualifies itself in as many words: *"Nothing
  enforces it, deliberately: a check failing on ~440 existing lines
  would be switched off within a day."* Live prose measured at the time
  was **439 British against 438 US** — a dead heat, so this is a
  tie-breaker for new writing rather than a campaign against old.
- **What would change this.** Nothing. The rule is a default, and a
  default that fires is no longer a default.

### 1.4 Prose that describes behaviour, with no document or constant on the other side

- **Written down at** `guide/archive/segment_19G_post_assessment.md` Item 1
  (class **D**).
- **The instance.** `spec/permissions.md` stated the session-id
  enumeration threat model **backwards** — found by a human-directed
  audit, fixed in `4ed5455f`.
- **Why not.** There is nothing to compare against. The claim is about
  what the application does; only reading the code or the running app
  settles it.
- **What covers it instead.** Article III's cold reader and Article IV's
  human verifier. Neither is a gate, and that is the concession.

### 1.5 Prose that summarises another document

- **Written down at** `guide/archive/segment_19G_post_assessment.md` Item 1
  (class **B**), where the mechanism was **proposed and rejected**.
- **The instance.** Three files summarising `spec/session_home.md`
  described a page retired three weeks earlier.
- **The rejected mechanism**, recorded here so it is not re-proposed
  from scratch: *a registry of which documents summarise which, flagged
  when the source changes.* It needs a hand-maintained registry (a
  growing allowlist); its signal fires on every edit to a hot source
  like `spec/architecture.md`; and clearing it needs a human judgement
  with nowhere to record "checked, still agrees". It would have caught
  one of the four drift instances that prompted the question.
- **What covers it instead.** A habit, not a gate: *a change that
  retires a page, section or file greps for what points at it, in the
  same change.* The file-level half of that **is** now enforced —
  `tests/unit/test_doc_references.py` fails on a path reference naming
  nothing (19G.1 rung 2; moved to its own module 2026-09-20). The section-level half is not.

### 1.6 A measurement that certifies a corpus must state what it could not see

- **Written down at** `guide/archive/segment_19G_post_assessment.md` Items 5 and
  7, where the rule was learned the expensive way.
- **The instance.** 19G.5 measured the `§N` cross-reference corpus,
  repointed six broken references and reported **125 references, 0
  unresolved**. The zero was checked for vacuity — a deliberately bad
  reference was injected and the measurement caught it — and the corpus
  was still not clean. The scan read **line by line**, and 7 of the 132
  references wrap across a line break. One of those seven was broken,
  had been introduced by 19G.1 three items earlier, and was invisible to
  the very pass built to find it. It surfaced two items later, while
  building the check.
- **Why not.** The rule is about the *shape* of an instrument, and the
  instrument is written fresh each time for whatever is being measured.
  There is no artefact to compare against and nothing stable to grep
  for: a check would have to understand what the measurement was trying
  to see, which is the judgement being asked for in the first place.
- **The distinction that matters, and the reason this is written down
  rather than assumed.** *Vacuity* and *coverage* are different
  questions, and passing the first says nothing about the second.
  Injecting a bad case proves the measurement **can** fail. It does not
  prove the measurement **looked everywhere**. A scan that never sees a
  region reports zero findings there and passes every vacuity check ever
  devised.
- **What covers it instead.** A habit: when a measurement reports a
  clean corpus, state the population it scanned and the shape it would
  miss — "132 references, line-local scan, wrapped ones not counted" —
  and prefer a whole-text scan to a line-local one wherever a construct
  can wrap. Article III's cold reader is the only backstop, and this is
  precisely the kind of claim a cold reader takes at face value, because
  the number looks like evidence.

### 1.7 The two cold readers run at their stated cadences

- **Written down at** `CLAUDE.md` / `AGENTS.md` "Where work runs";
  `constitution.md` III; `rrw_sdd_in_practice.md` §6.4.
- **The instance.** Article III has required a separate reader since
  2026-09-04. Measured **2026-09-14**: `diff-reviewer` had never run on a
  real slice outside the arc that created it — 0 pull requests and 0
  commit messages name it since 2026-09-06, against 70 and 33 for
  `spec-writer`. The article was not being broken deliberately; nothing
  observed whether it was being followed at all, and `spec-writer`,
  chartered *at a close*, silently took the per-rung seat instead. The
  cadences are now separate and stated; this entry records that nothing
  checks them.
- **Why not.** A check would have to establish that a *subagent was
  invoked* before a push. Nothing in the tree records that: the run
  leaves no artefact, and the only durable trace is whether the author
  chose to mention it in a commit message or PR body. Deriving the rule
  from that trace enforces **the mention**, not the reading — and a gate
  that can be satisfied by typing a name is worse than the paragraph,
  which is exactly VI's disqualifying shape. A per-PR gate would also
  contradict Article I for the `spec-writer` half (§6.5).
- **What would change this.** Nothing in the code; there is no constant
  behind it, and II says the rule therefore stays prose. What can change
  is the *measurement*: the counts above are re-takeable by the commands
  in §6.4's annotation, so a later audit can ask the question again
  cheaply. **That audit is the enforcement** — this is the one entry in
  §1 whose subject is a practice rather than a property of the tree, and
  the reason it is here is that the last four months of it went
  unobserved.

### 1.8 A new guard states the three things that make it evidence

- **Written down at** `guide/segment_19S_post_assessment.md` Item 1
  entry **E6**, proposed by `guide/codex_assessment_21sep.md` §5; adopted
  per-item at 19S.2 rather than as a standing rule.
- **The rule.** Before a guard is called complete: the fixture reaches
  the case, a mutation of the protected property fails, and the
  recogniser is exercised outside its current production examples.
- **The instance.** Segment 19R produced **four** guards that passed
  while seeing less than they claimed. The upload-route recogniser was
  wrong three times — matching annotation source text, keying endpoints
  on a basename that exists under two packages, expanding one level of
  `get_args` so `list[UploadFile] | None` was invisible — and each time
  the twelve real endpoints happened not to use the missed shape, so it
  stayed green (19R.4). The no-duplicate query guard **passed having
  recognised nothing**, demonstrated by running the pre-refactor module
  against it and watching it go green (19R.5).
- **Why not.** A check would have to establish that a *mutation was
  tried*, and nothing in the tree records that. Mutation testing as a
  gate is the wrong size for this repo — it would run the suite once per
  mutant — and the cheap proxy, requiring a commit message or PR body to
  name the mutations, enforces **the mention** rather than the mutating.
  That is §1.7's disqualifying shape exactly, and Article VI's.
- **What covers it instead.** The definition of done of any item adding
  a guard, which is where 19S.2 put it: *each of the four checks fails
  under a mutation of what it protects, the four mutations recorded in
  `### Status`*. Per-item, verifiable in the item, and worthless if
  nobody writes it — which is the concession.

### 1.9 A plan stays inside its length budget

- **Written down at** `.claude/skills/segment-plan/SKILL.md` "Length"
  (~250 lines a segment, ~120 an item); raised as
  `guide/segment_19S_post_assessment.md` Item 1 entry **E7**, from
  `guide/codex_assessment_21sep.md` §7.
- **The instance.** 19R's plan closed at **1,541 lines for eight items**.
  Its items each compacted at their own close and it still landed there.
  19S, written after the budget was raised as a finding, opens past the
  ~250 and its Item 2 came in at ~160 against ~120 after two deliberate
  trim passes. Its Items 3 and 4, added 2026-09-22, came in at ~146 and
  ~129 — so three consecutive items overran while the convention sat
  here, each written by someone who had just read it.
- **Why not — and this one is not about feasibility.** `wc -l` over
  `guide/segment_*.md` is a check anyone could write in a line. Two
  things disqualify it. It would be **red from its first commit**, so it
  fails §2's bar and would arrive as a cleanup rather than a guard. And
  the budget is stated as *"a signal, not a limit to game: past it, ask
  what a reader in six months needs and cut the rest"* — mechanising a
  signal converts it into a limit, and the cheapest way to satisfy a
  line-count limit is to move the reasoning somewhere the limit does not
  look. A gate that is best satisfied by hiding the content is worse
  than the paragraph.
- **What covers it instead.** The skill's own compaction rules at close,
  and the author noticing. Nothing measures whether either happened,
  which is why the overruns above are recorded here rather than claimed
  as fixed.

---

## 2. Enforceable but not enforced — the revisit queue

None of these needs an allowlist, and each would pass on the current
tree, so a check would be green from its first commit. They are here
because nobody has written them, which is a different fact from a
decision not to.

### 2.1 No `sqlalchemy.dialects.postgresql` imports in `app/db/models/`

- **Written down at** `CLAUDE.md`, three times; `spec/architecture.md`
  §"Three-layer split" item 3; `guide/deferred_consolidated.md`
  (Postgres-native types are deferred infrastructure).
- **The check.** A grep over `app/db/models/*.py` for the module path.
  No judgement, no allowlist, no ambiguity.
- **Why it matters that nothing checks it.** `ruff` catches only an
  *unused* such import (`F401`), and SQLite's tolerance is what catches
  some of the rest — a dialect accident, not enforcement.
- **Verified 2026-09-08.** A `from sqlalchemy.dialects.postgresql import
  VARCHAR` in `app/db/models/review_session.py`, actually used as a
  column type so `F401` cannot fire, leaves `ruff` clean and **2940
  passed, 16 skipped**.

### 2.2 No slice-to-slice imports in `app/web/routes_operator/`

- **Written down at** `CLAUDE.md` "Architecture at a glance" §1: slices
  import only from `_shared.py` and from outside the package.
- **The check.** Walk the package's import statements; fail on one slice
  importing another. Derivable from the file layout alone.
- **Verified 2026-09-08.** **20 slices, 0 violations.** The package holds
  22 `.py` files: the 20 slices `__init__.py` registers, plus
  `_shared.py` — which the convention names as the one legal import
  target and so is not itself a slice — plus `__init__.py`. The
  convention is being followed by hand today, which is the best moment
  to pin it: before the first violation makes the check a cleanup.

### 2.3 The Provenance line in `new_project_practices_setup.md`

- **Written down at** that document's own step 3, and the blockquote
  under its title carries two `<slot>`s for a reader to fill.
- **The check.** `tools/practice_kit.py` ships to every project the kit
  sets up, so a `PROVENANCE_DEFAULT` constant holding the shipped text,
  plus a test that the local document's blockquote differs from it,
  would fire in exactly the repositories that need it. The awkward part
  is real but small: the test has to pass here, where the blockquote *is*
  the default, so it needs a way to tell the source from a copy.
- **Why it is not written yet.** The clean version is for the export to
  stamp the line as it copies, which makes the constant exact and the
  test trivial. That is a change to the tool, and it was kept out of the
  slice that added the line. Until then a check would enforce a
  convention whose input nothing produces.
- **What would change this.** The export stamping it. Then this entry
  moves out of the queue and the test follows.
- **Verified 2026-09-20.** The one downstream copy,
  `philoyhc/nuscrm`, filled it by hand in the same session, so the
  convention has been followed once and broken zero times — the same
  "pin it before the first violation" moment as §2.2.

---

## What this file is not

**Not a backlog.** §2 is three entries and should stay small; if it
grows, that is a signal the practice is accumulating rules faster than
checks. (It said *two* until 2026-09-22, having missed §2.3's arrival —
the growth its own sentence calls a signal went unrecorded, which is the
class `guide/segment_19S_post_assessment.md` Item 2 gates for two
hand-maintained indexes and §1.5 leaves to a habit for the rest.)

**Not a replacement for `docs/practice-audit-2026-09-04.md` §2.** That
audit is a record of what was true on its date and is not rewritten —
see the dated note at its head for what has changed since. This file is
the live view; the audit is the snapshot that prompted it.

**Not the structural limits of the practice.** Article I's spec-drift
window, Article II's blindness to what a spec *contains*, Article III's
reader running only when run, and Article IV's browser-only defect class
are trade-offs of the rules themselves, recorded in `constitution.md`
next to each. They are not conventions anyone chose to leave unchecked.
