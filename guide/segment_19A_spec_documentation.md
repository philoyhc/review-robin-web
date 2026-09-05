# Segment 19A — Spec documentation

> **Stub created 2026-05-11** as part of the Stage 4 guide/
> reorg. **Renamed 19 → 19A on 2026-08-19** when the code-level
> consistency remediation split off into its own sibling,
> **Segment 19B** (`guide/archive/segment_19B_consistency.md`). 19A keeps
> the **documentation-hygiene** charter (spec/ + docs/ currency +
> coverage-gap closure); 19B carries the code-level "same
> functionality, divergent call paths" fixes from
> `guide/archive/consistency_audit.md`.

**Parts 2 and 4 remain sketch-level; Item 3 (Part 3) is planned in full
below** (converted 2026-09-05 from an externally drafted implementation
spec, after review). Detailed PR breakdowns for Part 2 get drafted when
it is picked up.

## Status (started 2026-08-19)

Segment 19A is **in progress** and **broadened from spec-only to spec/ +
docs/ hygiene** — the two folders' currency sweeps run under one segment.
Shipped so far:

- **spec/ drift sweep** (`guide/archive/spec_sweep_18Aug.md`, 2026-08-18) —
  all §A unfinished-work + §B currency-debt items **resolved** (in 18R
  Item 3 and the `rrw_functional_spec.md` + `architecture.md` revision).
- **docs/ audit** (`guide/archive/docs_sweep_19Aug.md`, 2026-08-19) — all
  four buckets **executed**: `docs/rehydrate.md` → `spec/rehydrate.md`
  (revise-into-spec); `docs/` consolidate (cli_setup_notes → cli_setup;
  authentication → security_posture; codespace_setup → local_setup;
  azure_github_setup reconciled) + retire (imports.md, cli_setup_notes.md);
  and the update-in-place batch (revoke-UI / conftest / status-header
  fixes). `docs/` went 20 → 16 files.

- **Part 1 — Tier-1 spec coverage-gap closure** (`spec/permissions.md`,
  `spec/email_template_editor.md`) — **shipped 2026-09-05**, four months
  after the 2026-05-11 sweep flagged them. Writing them surfaced and
  fixed five spec-vs-code drifts in neighbouring files (each listed in
  the new specs' "Drift noted" sections).

- **Part 3 — planned in full as Item 3 below (2026-09-05) and ✅ shipped the same day** (PRs #2109 → #2111): the spec-coverage gate and `tools/close_check.py`. Item 3 closes in place; 19A stays live for Part 2.
  The externally drafted "segment close check and spec coverage gate"
  spec, reviewed against the repo and converted to the item shape with
  the review's corrections folded in.

**Still open:** Part 2 (sweep cadence — sketch).

## Goal

A **spec-hygiene segment** dedicated to keeping `spec/` —
the canonical "what is this thing supposed to look like /
behave like?" layer — internally consistent, fully covering
the codebase, and free of drift against the implementation.

Distinct from **Segment 20** (operator polish + documentation),
which produces operator- + developer-facing **prose docs**
(`docs/`, README, Start Here page, runbooks). 19A is about
the `spec/` folder itself — the design-intent contracts that
the templates, services, and tests are supposed to match.

## Why a dedicated spec segment

`spec/` already absorbs spec content per-segment (every
shipped segment that locks a UI contract writes its spec on
the way out). What's missing is a **periodic cross-cutting
sweep** that:

- Confirms each spec file still describes the code accurately.
- Identifies new surfaces shipped without a spec home.
- Compresses redundancies across sibling specs.
- Promotes informative filenames over generic ones.
- Updates the `spec/README.md` taxonomy.

The 2026-05-09 → 2026-05-11 sprint did one such sweep
(`guide/archive/spec_sweep_11may.md` — 25 files / 10,224 LOC of
spec touched across F1-F8 drift fixes, C1-C5 consolidation,
S1-S5 style touch-ups, plus the three new Tier-1 specs:
`lifecycle.md`, `csv_contracts.md`, `validate_page.md`).
That sweep is the prototype for what 19A codifies as a
recurring concern.

## Scope (sketch)

### Part 1 — Initial spec coverage gap closure

**Goal.** The set of Tier-1 specs identified in
`guide/archive/spec_sweep_11may.md` "Done vs Remaining" that
remain unwritten as of 2026-05-11:

- **#4 Email Template editor** → `spec/email_template_editor.md`.
- **#5 Permissions / authorization** → `spec/permissions.md`.

Plus the Tier-2 partial-coverage candidates flagged in the
same doc (Relationships Setup deep-dive, Operations
Assignments dedicated section, Operator Settings spec).

Per the sweep doc's tier framing, these are the items the
2026-05-11 sweep didn't get to but identified as worth a
dedicated spec. Part 1 of 19A picks them up.

### Part 2 — Periodic drift audit cadence

**Goal.** Establish a **cadenced** spec sweep — every N
weeks (or every K segments shipped, whichever comes first)
— that surfaces drift before it accretes.

Likely shape:

- A new `guide/spec_sweep_template.md` checklist that drives
  each sweep (the 2026-05-11 sweep doc is a one-off; the
  template is reusable).
- A `guide/spec_audit_YYYY-MM-DD.md` naming convention for
  each sweep's working notes (matches the
  `codebase_assessment_*.md` cadence on the codebase side).
- Sweep entry points: which spec files to grep for which
  tells, how to identify orphan surfaces, how to identify
  generic filenames.
- Output: a per-sweep PR (or PR sequence) carrying the
  drift fixes + consolidation + style touch-ups.

### Part 3 — Spec-coverage gate (post-MVP)

> **Superseded 2026-09-05 by Item 3 below**, which plans this in full
> (and adds the segment close check the sketch did not anticipate).
> Sketch kept as written.

**Goal.** Tooling support — a test or lint pass that catches
new operator routes / templates / models without a spec
home.

Likely shape (deferred — confirm need before scoping):

- A test that maps every operator route in
  `app/web/routes_operator/` to a `spec/` file (via a small
  manual registry or convention-based lookup).
- A CI gate that fails when a new route lands without a
  spec mapping.
- Lighter touch: a `pytest` warning that surfaces missing
  spec coverage without failing the build.

May not be worth the maintenance burden — revisit when
operator-route fan-out makes the manual review of
spec coverage unsustainable.

### Part 4 — Spec rendering / cross-reference UX (post-MVP)

**Goal.** Beyond the markdown files themselves, give
contributors a navigable surface for the spec corpus.

Likely shape (deferred):

- Static-site generation from `spec/` (e.g. via mkdocs)
  with auto-rendered cross-references between specs.
- Per-spec "this references" / "this is referenced by"
  back-links.
- A "what changed in spec since version X" diff view.

Plausibly out of scope forever for a citizen project — the
flat-file markdown is fine in practice. Recorded here as a
maybe-future direction.

## Hard dependencies

- **None.** Part 1 can start any time. Parts 2 / 3 / 4 are
  process / tooling work that fits into the cadence
  whenever it's picked up.

## Out of scope

- **`docs/` content** — operator runbook, deployment guide,
  troubleshooting, etc. That's Segment 20.
- **README / CLAUDE.md / AGENTS.md** — those are the
  outermost framing; their content is maintained per-segment
  (Stage-1 of every reorg PR touches them as needed) rather
  than under a dedicated segment.
- **Code documentation** (docstrings, inline comments).
  Maintained per-PR; not a 19A concern.

## Doc impact — segment sketch (2026-05-11; superseded)

> Renamed 2026-09-05. This segment's parts close independently, so from
> Item 3 onward the machine-read manifest is the **item-level**
> `### Doc impact` inside each item block, and this file deliberately
> has no segment-level `## Doc impact` (one shape per file — see
> `.claude/skills/segment-plan/SKILL.md`). Part 1's bullets below were
> honoured in #2101 (`spec/README.md` rows, `docs/status.md` row). The
> Part 2 bullet moves into Item 2 when Part 2 is planned.

When parts ship:

- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.
- `spec/README.md` taxonomy refreshed as new specs land in
  Part 1.
- `guide/README.md` mentions the cadence convention (Part 2).
- `guide/archive/spec_sweep_11may.md` (the closed 2026-05-11
  sweep proposal) is already retired to `guide/archive/`; its
  "Done vs Remaining" list is the input for Part 1.

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Sweep cadence.** Every N weeks vs every K segments?
  Lean "every codebase_assessment cadence" since the two
  rhyme — pair each codebase_assessment with a spec sweep.
- **Tier-1 vs Tier-2 / 3 priorities.** Already established
  in `guide/archive/spec_sweep_11may.md` — adopt as the default
  tiering for future sweeps.
- **Where to register new specs.** New `spec/<name>.md`
  files land via the segment that first locks the contract;
  Segment 19A picks up the cross-cutting hygiene work, not
  the per-segment authoring.
- **Naming conventions.** Sweep §C5 retired "assumptions" /
  generic filenames; future spec adds should pre-emptively
  pick informative names rather than waiting for a sweep
  to rename them.

---

## Item 3 — Segment close check and spec coverage gate

**Opened:** 2026-09-05 · **Theme:** make the phase rule's exit *checkable*
· **Related:** `rrw_sdd_in_practice.md` §6.1 / §6.3, `constitution.md`
Articles I–II, `docs/practice-audit-2026-09-04.md` §4 R1,
`guide/segment_plan_template.md`, `.claude/skills/segment-plan/SKILL.md`.
Supersedes the Part 3 sketch above. Converted from an externally drafted
implementation spec after review against the repository; every number
below was produced by a command on 2026-09-05 at `fd4c5240`, and the
review's corrections are recorded under *Judgment calls*.

### Opportunity

The phase rule — plan on the way in, spec on the way out — is held by
*visibility* on the way in and by *convention* on the way out
(`rrw_sdd_in_practice.md` §6.1 as revised in #2100). Every plan's
definition of done *asserts* that the spec was updated; nothing checks
it. Measured over the 32 archived plans that carry a non-empty
`## Doc impact`: they committed **110** `spec/` / `docs/` paths, of which
**94 (85 %)** were edited within the plan's window; **19 of 32** plans
honoured every commitment; **8** committed paths no longer exist at the
stated location (a spec renamed or archived mid-segment). The convention
mostly holds — and 13 plans dropped at least one commitment silently,
with nothing to notice.

Separately, no check can detect a routing surface that has **no spec at
all**. That is a narrower failure than the one that motivated the
original draft: the two Tier-1 specs that stayed missing for four months
(`spec/permissions.md`, `spec/email_template_editor.md`, closed in
#2101) were surfaces that *did* have governing sections in
`spec/operator_ui_concept.md` and lacked a *dedicated* contract — a
distinction no module-keyed presence check can make. The gate is still
worth having, because it is cheap and it derives from a code fact
(Article II); its claim is stated honestly below.

### Decision

Two mechanisms, neither an agent, both operating at segment boundaries:

1. **`tools/close_check.py <id>`** — reads the plan's `Doc impact` at the
   level being closed, verifies each committed path exists and was edited
   within the segment's window or carries a reasoned waiver, and reports.
   Exit `0` pass (warnings allowed) · `1` a check failed · `2` usage or
   resolution error. It edits nothing and calls no LLM.
2. **`app/web/spec_registry.py` + `tests/unit/test_spec_coverage.py`** —
   a registry keyed by *routing module* mapping to live spec paths,
   enumerated at runtime from `create_app().routes`; three tests in the
   `EVENT_SCHEMAS` / `test_doc_conventions.py` idiom (set equality with
   the registry; every mapped path a live file; the `PENDING` set exactly
   equal to `EXPECTED_PENDING`, which starts **empty**).

**Rejected, with reasons.** *Per-PR spec sync* — contradicts §6.1; both
mechanisms run at the boundary the rule already uses. *A separate
manifest file* — a second place to state what the plan's `Doc impact`
already states (§6.7, Article V). *A per-route registry* — 157 operator
route decorators against ~30 route-bearing modules; modules already
partition the surface the way the per-page specs do. *A
`DISPLAY_LABELS` ↔ `RETIRED_TERMS` coupling check (the draft's D7/C5)* —
dropped; see *Judgment calls*.

### Semantics

- **Manifest.** Every backticked path matching `spec/**/*.md` or
  `docs/**/*.md` under the `Doc impact` heading at the closing level;
  trailing `§n` / anchors stripped; deduplicated. Root-level and `guide/`
  paths listed there are for the human and are not checked (judgment
  call below).
- **Level.** `19A` reads `## Doc impact`; `19A.3` reads `### Doc impact`
  under `## Item 3`. A file carrying both shapes fails C1 ("pick one").
  A segment id whose file has item-level manifests runs every item and
  passes only if all pass; it does not union them.
- **Window.** Start = the first commit in which the `Doc impact` heading
  appears at that level in the plan (`git log --format=%H --reverse
  -S'### Doc impact' -- <plan>`) — the moment the commitment was made.
  End = `HEAD`, or in `--archived` mode the commit that added the
  archived path. Start is computed on the **pre-archive** path
  (`guide/<name>`); never `--follow --reverse`, which returns the
  archive-move commit for a renamed file (measured: start = end, 0 of 110
  paths "touched").
- **Honoured.** At least one non-merge commit touching the path in
  `(start, end]`. A one-character edit passes; whether the edit was
  *correct* is `spec-writer`'s job at close and the human's.
- **Waiver.** `<!-- doc-impact-waived: <reason> -->` on the bullet's own
  line. Reported as waived; an empty reason fails (C4). Mirrors the
  `retired-term-ok` escape idiom.
- **Checks, in order.** C1 heading present at level, one shape · C2 every
  committed path exists and is not under an `archive/` · C3 every
  un-waived path modified in window (report last-modified date for each
  miss) · C4 every waiver reasoned · C6 a `Status` block exists at the
  closing level — **warn only** in v1. There is no C5.
- **Report.** Human-readable to stderr, one line per check, a summary
  line, and an informational *coverage note* cross-referencing the
  segment's touched routing modules against the registry — does not
  affect exit status in v1. `--json` adds a machine-readable copy on
  stdout.
- **`--archived`.** Runs every `guide/archive/segment_*.md`; report only,
  exit 0 regardless. Plans without a `Doc impact` heading are reported,
  not failed.
- **Coverage enumeration.** `{route.endpoint.__module__ for route in
  create_app().routes}` minus `INFRASTRUCTURE_MODULES`
  (`app.web.routes_health`; `app.main` — the `/` and `/operator`
  redirects; `app.web.routes_auth` — identity diagnostics). Assert **set
  equality** with `SPEC_COVERAGE.keys()` — a registered module that no
  longer routes is drift too. Every mapped path: exists, under `spec/` or
  `docs/`, not under any `archive/`. Modules mapping to `SPEC_PENDING`
  must equal `EXPECTED_PENDING` exactly; the failure message
  distinguishes "new debt added" from "debt closed but not removed".
- **Runtime.** Deterministic; no network; under five seconds for one
  segment, under ten for `--archived`.

### Judgment calls — decided

- **2026-09-05 — the draft's D7 / C5 is dropped.** It required
  `RETIRED_TERMS` to change whenever `DISPLAY_LABELS` changed, citing the
  `expired → "Closed"` drift. That drift is already caught mechanically by
  `test_lifecycle_tables_match_the_display_label_mapping`, which derives
  from `DISPLAY_LABELS` directly; `RETIRED_TERMS` is the retired *button*
  vocabulary, for which no constant exists. C5 would fail every legitimate
  label change and add nothing.
- **2026-09-05 — the gate's claim is "a routing module with no spec at
  all".** Not "a surface without a dedicated spec": the two Tier-1 gaps
  had `operator_ui_concept.md` sections and would have passed. Stated in
  the Opportunity so the next reader does not over-credit it.
- **2026-09-05 — `EXPECTED_PENDING` starts empty.** The draft seeded it
  with the two Tier-1 specs (and mis-mapped one — the editor lives in
  `_setup_invite.py`, not `_instruments.py`); both shipped in #2101.
  Empty is the correct strict-mode baseline.
- **2026-09-05 — window start is the appearance of the `Doc impact`
  heading, not the plan file's first commit.** Plans are often stubbed
  months early (`segment_14B_email_infrastructure.md`: first commit
  2026-05-11) or renamed (19 → 19A hides the May stub from `--follow`);
  either makes "first commit of the file" unsound. Archived windows are
  short in practice (median 2 days, max 12), so this is a live-plan
  problem, not an archive one.
- **2026-09-05 — registry lives in `app/web/spec_registry.py`**, not in
  the test. The idiom: the rule lives in code so it cannot go stale
  independently of the code (`DISPLAY_LABELS`, `EVENT_SCHEMAS`). A module
  under `app/web/` that ships no behaviour is documentation-as-constant,
  and that is the point.
- **2026-09-05 — root-level and `guide/` paths are outside the manifest
  regex.** `rrw_sdd_in_practice.md`, `constitution.md`, `CLAUDE.md` and
  `guide/*` are named in `Doc impact` sections for the human; the script
  checks `spec/` + `docs/` only, because "spec on the way out" is what it
  verifies. Widen the regex only if root docs become a recurring
  commitment.
- **2026-09-05 — this file switches to item-level manifests.** The
  sketch-era segment-level `## Doc impact` is renamed to a history note so
  the file has one shape; Item 3 carries `### Doc impact`; Part 2 becomes
  Item 2 with its own when planned.
- **2026-09-05 — "checkable", not "mechanised".** A script a human runs
  before archiving is convention with a tool. The §6.1 / Article II
  update says the exit becomes *checkable* for declared impact and
  *gated* for undeclared surfaces; it does not claim the exit is now
  mechanised, because §2 of the draft (rightly) rules out a per-PR gate.
- **2026-09-05 — `tools/_harness_common.py` is theme tooling** (CSS /
  token parsing), not git helpers; `close_check.py` is a standalone
  stdlib script in the style of `tools/code_metrics.py`.

### Blast radius (measured)

| What | Count | Command |
|---|---|---|
| Segment plans, live + archived | 95 | `ls guide/segment_*.md guide/archive/segment_*.md \| wc -l` |
| Plans with `## Doc impact` | 36 | `grep -l "^## Doc impact" guide/segment_*.md guide/archive/segment_*.md \| wc -l` |
| Plans with `### Doc impact` / with both shapes | 1 / 1 | same, `^### Doc impact`; intersection |
| Archived plans with a non-empty `## Doc impact` | 32 | Python over the section's backticked `spec/`/`docs/` paths |
| Committed paths / edited in window / plans fully honoured / paths missing today | 110 / 94 (85 %) / 19 of 32 / 8 | window `[first commit of guide/<name>, commit adding the archived path]`; `git log <start>..<end> -- <path>` |
| Archived window length | median 2 d, max 12 d | as above |
| Operator route decorators / route-bearing operator modules | 157 / 20 | `grep -h "@router\.\(get\|post\)" app/web/routes_operator/_*.py \| wc -l`; `grep -l … \| wc -l` |
| Reviewer route-bearing modules / other route files | 6 / 4 (`routes_about`, `routes_auth`, `routes_health`, `app/main.py`) | `grep -rl "@router\.\(get\|post\)" app/web/routes_reviewer/ \| wc -l`; `grep -l "@router\.\|@app\." app/web/routes_*.py app/main.py` |
| Existing derived gates | 3 checks (+ `EVENT_SCHEMAS`) | `grep -c "^def test_" tests/unit/test_doc_conventions.py` |
| `spec/architecture.md` "Route conventions" section | present (line 99) | `grep -n "Route conventions" spec/architecture.md` |
| Close / archive guidance | in `guide/README.md`; **none** in `CLAUDE.md` | `grep -n -i archive CLAUDE.md guide/README.md` |

### PR ladder

1. **PR 1 — registry + tests.** Lands `app/web/spec_registry.py`
   (`SPEC_COVERAGE`, `SPEC_PENDING`, `EXPECTED_PENDING = ()`,
   `INFRASTRUCTURE_MODULES`) seeded for every route-bearing module (~30:
   20 operator, 6 reviewer, `routes_about`, and the three infrastructure
   entries), and `tests/unit/test_spec_coverage.py` with the three tests.
   PR body records every module whose mapping was a judgement call
   (`routes_about` in particular). Must not touch `tools/` or any doc
   other than the one `spec/architecture.md` sentence.
2. **PR 2 — `tools/close_check.py`.** C1–C4 + C6, `--archived`, `--json`,
   the report shape; `tools/README.md` row. Runs `--archived` once and
   records the baseline in the PR body against the 85 % / 19-of-32
   measured here. Must not touch `app/` or `tests/`.
3. **PR 3 — process docs.** `guide/README.md` close sentence ("before
   archiving a plan, `close_check.py <id>` exits 0"); the *pending*
   markers removed from `guide/segment_plan_template.md` and the
   `segment-plan` skill; `rrw_sdd_in_practice.md` §6.1 trade-off and §7
   in "checkable" wording; `constitution.md` Article II's "Nothing here
   mechanises the exit of I" reviewed — kept if still true, amended if
   not; `docs/status.md` row; `guide/todo_master.md`. Docs only; may
   merge ahead of CI per `CONTRIBUTING.md`.

### Definition of done

- `tests/unit/test_spec_coverage.py` green on both dialects;
  `EXPECTED_PENDING == ()`; every route-bearing module registered.
- `python3 tools/close_check.py 19A.3` exits 0 against this item;
  `--archived` completes in under ten seconds and reports the honour rate.
- The `--archived` baseline appears in PR 2's body and in the
  `docs/status.md` row.
- `spec/architecture.md` "Route conventions" states that new routing
  modules must be registered in `app/web/spec_registry.py`.
- `rrw_sdd_in_practice.md` §6.1 says the exit is checkable for declared
  impact and gated for undeclared surfaces; §7 no longer lists the
  coverage gate as deferred.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19A.3` exits 0
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added; this item closes in place (19A stays live for Part 2)

### Open questions

- Should `--archived` become a periodic test asserting the honour rate
  does not fall? Leaning no — it would make history a gate. Decide after
  two or three closes have run against the check.
- Promote C6 (Status block) from warn to fail? After the template has
  been in force for three closes. Decided by the honour rate then.
- Orphan-spec test (every live per-page spec referenced by ≥1 module,
  with a `CROSS_CUTTING` allowlist)? Not v1; the allowlist would need to
  be sized on evidence and the failure mode it addresses has not been
  observed here.
- `routes_about` mapping: `spec/operator_ui_concept.md` (its §"Entry"
  paragraph) or `INFRASTRUCTURE_MODULES`? Decided at seeding, recorded in
  PR 1's body.

### Out of scope

- A new agent, or any LLM call from the script — `spec-writer` is invoked
  by the close *convention*, not by code.
- Per-PR spec synchronisation — contradicts §6.1.
- A coverage percentage, dashboard or badge — pass/fail and a plain report.
- The draft's D7 / C5 vocabulary-rename check — dropped (judgment call).
- The orphan-spec test — open question, not v1.
- Part 2 (sweep cadence template + dated sweep notes) — its own item.
- Moving a plan to `guide/archive/`, or editing any file — the script
  reports; the human acts.

### Doc impact

- `spec/architecture.md` — "Route conventions": one sentence, new routing
  modules must be registered in `app/web/spec_registry.py` (PR 1).
- `docs/status.md` — row when the item lands, carrying the `--archived`
  baseline (PR 3).
- *(for the human — outside the script's `spec/` + `docs/` regex)*
  `rrw_sdd_in_practice.md` §6.1 / §7; `constitution.md` Article II
  (review); `guide/README.md` close sentence; `guide/segment_plan_template.md`
  and `.claude/skills/segment-plan/SKILL.md` (remove the *pending*
  markers); `tools/README.md` row; `guide/todo_master.md` (PR 3).

### Status

**2026-09-05 — the ladder ran as planned: PR 1 (#2109) registry + tests,
PR 2 (#2110) `tools/close_check.py`, PR 3 (this) the process docs.** No
rung was dropped, merged or reordered. Three things the build found that
the plan had wrong or did not anticipate:

- **The plan's route enumeration does not work on this FastAPI.** The
  Semantics specify `{route.endpoint.__module__ for route in
  create_app().routes}`. FastAPI 0.141 keeps `include_router` results as
  lazy `_IncludedRouter` wrappers instead of flattening them, so that
  expression yields **2** modules, not 30 — and a test written to the
  plan would have passed vacuously against an almost-empty set.
  `spec_registry.routing_modules()` walks the table recursively and
  raises below a 100-route floor, so a future framework change fails by
  name rather than as a confusing set diff.

- **Heading matching had to become asymmetric, and the plan is the
  reason.** `Doc impact` is matched **exactly**; `Status` tolerates a
  suffix. Prefix-matching `Doc impact` would break this very file: its
  retired sketch manifest is `## Doc impact — segment sketch (2026-05-11;
  superseded)`, so read by prefix the file carries two shapes and fails
  its own C1. Suffixing a heading is now the documented way to retire a
  manifest without deleting it (`guide/README.md`,
  `guide/segment_plan_template.md`, the `segment-plan` skill).

- **Correction to this plan's Blast radius: the recorded 94/110 (85%)
  and 19-of-32 are inflated.** That measurement counted a *merge commit*
  as honouring a path. Investigated across all four paths where it
  matters: in each, the merge has a parent that predates the window and
  is byte-identical to the merge on that path — the merge was bringing
  already-landed `main` content into a feature branch, not editing a
  spec. Three are in 18B (specs edited by the 15D/15F sweeps on
  2026-05-15, before 18B's plan existed) and one in 18H. So the
  non-merge rule the Semantics specify is *correct*, not one of two
  defensible readings, and merge-inclusive would report a false pass in
  the one direction this check cannot afford. Checked for the opposite
  risk too — git's default history simplification can hide a real edit
  behind a merge — by comparing `git log` against `--full-history` on
  all 101 live committed paths: **they agree on every one.** The
  authoritative baseline is now the script's:

  | Measure | 2026-09-05 |
  |---|---|
  | Live committed paths honoured | 85 / 101 (84%) |
  | Plans fully honoured | 21 of 32 |
  | Committed paths that no longer exist | 8 |
  | Archived plans with no manifest | 58 of 90 |
  | `--archived` runtime | 3.0 s |

  Two of those differ from the plan for reasons other than merges:
  missing paths now sit outside the honour denominator (they are C2's
  business, not C3's), which is why fully-honoured reads 21 rather than
  19; and the script counts 109 committed paths against the recorded
  110, a one-path gap not attributable to any definitional lever tested
  (window start, merge handling, extraction form, dedupe). The original
  was a one-off script; this one is the reproducible definition.

Decisions confirmed at build:

- The nine judgment calls above stand unchanged, including the dropped
  D7/C5 and `EXPECTED_PENDING = ()`.
- **`routes_about` maps to a spec, not `INFRASTRUCTURE_MODULES`** (the
  item's fourth open question): `spec/operator_ui_concept.md` carries a
  dedicated `### /about — About` contract section.
- Four candidate mappings were dropped for failing their own evidence
  check — `csv_contracts` for `_quick_setup`, `visibility_policy` for
  `_instruments`, `reconciling_regeneration` for `_assignments`, and
  `role_navigator` for `_dashboard`. The seeding rule that produced
  them is recorded in `app/web/spec_registry.py`.
- C6 stays warn-only: only **15 of 90** archived plans carry a `Status`
  block, which is the measurement the item's second open question asked
  for. Revisit after three closes under the current template.
- The window-start worry does not bite on the archive: heading-appearance
  and file-first starts give an identical 89/109. It remains a live-plan
  concern, as the plan predicted.
- **`spec-writer` pass at close (PR 3) found one real flag, accepted.**
  The "Spec registration" paragraph PR 1 added to
  `spec/architecture.md` named two of the registry's three sanctioned
  outcomes, omitting `SPEC_PENDING` + `EXPECTED_PENDING`. Left as
  written it pushed a reader shipping a surface ahead of its spec
  toward `INFRASTRUCTURE_MODULES` — precisely the misuse the registry's
  own comment warns against. The paragraph now states all three, plus
  the live-file requirement. A second, optional flag (no drift found in
  the layering module map; `spec_registry.py` needs no entry there,
  since it ships no routes and is treated exactly as `deps.py` and the
  other `app/web/` helpers are) needed no action.
