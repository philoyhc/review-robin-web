# Segment 23H — The practice's reach: gates, readers and measures over the packages

Planned in Cordware while Apply Desk ran (parked 2026-11-20), from
Cordware's review of this practice against Apply Desk (its
guide/rrw_sdd_practice_review.md, follow-ups F1–F8), and moved here when
the author gave the word to build. The phone work in
`guide/rrw_mobile_responsive.md` is separate.

**Opened:** 2026-11-20 · **Theme:** make the practice reach
the application packages it now runs in, and re-take its measures ·
**Related:** `rrw_sdd_in_practice.md`, `constitution.md`, `CLAUDE.md`,
`tools/close_check.py`, `applydesk/guide/todo_master.md`

## Opportunity

`rrw_sdd_in_practice.md` was last re-taken on 2026-11-06. Since then,
620 PRs have merged, most of them Apply Desk's AD1–AD1P, built in
`applydesk/` with its own `spec/`, `guide/` and `docs/`. The practice held there,
but some of its machinery stops at RRW's root folders. Cordware's review
(§3–§4) gives the evidence for eight gaps, F1–F8:
- closes that skipped `close_check`, four of which now fail;
- prose gates and `spec-writer` blind to package folders;
- an unrecorded read cadence;
- rulings that the practice document does not describe;
- measurement tools that miscount packages;
- an overdue sweep and assessment;
- a stale browser-only test list.

The Blast radius below re-counts each.

## Decision

**One segment, with each follow-up a rung or two, in dependency
order.**
- Fix what is wrong first (F1).
- Then make the tools see the packages (F6, F2), and write down how
  readers and rulings work there (F3–F5).
- Re-take the measures last (F7), so the new assessment counts with
  fixed tools.

**The package gates extend the existing tests rather than copy them.**
One `APP_DIRS` list, `close_check`'s, is imported by each gate, so a
new package is added once.

**Rejected:** a per-package copy of each gate. It is quicker to land,
but four copies of a doc-reference test would drift exactly as §6.3
warns. A new package would also need four edits, and the next package
would miss one.

**Rejected:** folding F7 into this segment's close. An assessment is a
cold whole-window read by agents with no part in the build (§6.4).
Taken by the segment that changed the tools, it would be the builder
checking itself.

## Semantics

- **Package-relative paths (F2a).** Package prose writes paths both
  ways: 287 Residential references resolve from the repo root, and 6
  only from the package; Apply Desk has 63 and 14.
  - **Rule:** a backticked path resolves from the repo root first, then
    from its own package. Only a path that does neither fails.
  - **Why:** the register's convention ("`spec/` … relative to
    `applydesk/`") is already written, and rewriting 20 references
    churns live documents.
- **Cross-repo paths.** Some dangling references name Cordware's own
  files (`docs/cordware_azure_progress_runner_2026-10-29.md`,
  `spec/importer.md`).
  - **Rule:** a reference written `cordware:docs/…` is exempt, and the
    gate counts and reports it.
  - **Rejected:** an allowlist, since it grows (constitution VI).
- **Dated documents stay exempt.** Package findings registers and
  handover documents (`*_v0.N*.md`, `findings_*`) join `DATED_DOC`, as
  root assessments are exempt today.
- **Guide indexes (F2b).** A package `guide/` needs a `README.md` row
  per document, as RRW's does. Today only `applydesk/guide/archive/`
  has a README; three packages have no `guide/README.md`.
  *(Amended at rung 4: each package's top-level `README.md` already
  indexes its `guide/` with `guide/<file>.md` rows, so it is the index,
  and a package `guide/archive/README.md`, where one exists, indexes the
  archive. See Judgment calls.)*
- **Spec coverage (F2c).** A package route module maps to a spec in its
  own `spec/` folder.
  - A module not yet mapped goes into a declared-debt baseline, as
    `app/web/spec_registry.py` started.
  - The baseline only shrinks, and the gate fails on a new unmapped
    module.
- **Read cadence (F4), ruled by the author 2026-11-20: one read per
  closing unit.**
  - **A segment with no items:** one cumulative `diff-reviewer` read
    of the segment, at its last build rung. Its rungs are not read on
    their own. This covers all 17 Apply Desk plans, none of which has
    items.
  - **A segment whose items close independently:** one read per item,
    as ruled 2026-09-18. 30 of RRW's 155 archived plans have items
    (19S had 10, one ran to 18). Each item merges and is often deployed
    on its own, so a segment-level read would come after deployment,
    over a diff too large to read cold.
  - **A cap:** past about 1,500 changed lines, read at a rung boundary
    and start a new base.
  - **No read for author iteration rungs:** a rung that only adjusts
    layout or copy after the author's browser check takes none, since
    `diff-reviewer` cannot see layout. This is what drove AD1B to 5
    reads and AD1F to 11. A rung that changes logic or tests still
    counts toward the closing unit's read.
  - **Recording:** the closing unit's `Status` records its reads and
    what they found, per segment or per item.
- **Rulings (F5), ruled by the author 2026-11-20: folded into the
  spec in the end, but standing while major building runs.**
  - **While a phase of major building runs,** rulings may stand in a
    layer of their own, `todo_master` or beside it. A ruling settles a
    decision across segments, and a plan cites it by number.
  - **Folding happens at a major juncture,** not at a segment's or an
    item's close:
    - each ruling goes into the spec it governs, or is recorded as
      retired;
    - the standing list then empties.

    The first juncture for Apply Desk is the end of its UI prototyping
    phase: AD1 to AD2, when pages start to persist.
  - **A segment close** still writes into the spec what its build
    shipped. It cites the rulings it relied on, but does not move or
    delete them.
  - **The v0.6b functional spec is archived eventually,** with a
    superseded-by header naming `applications.md` and the rulings. There
    is no hurry; it fits naturally at the first folding juncture.

## Judgment calls — decided

- Package `APP_DIRS` stays the single source; `cordware/` is not a
  package for these gates, since it has no `guide/`. (2026-11-20)
- Rungs that edit `applydesk/` files (F1 annotations, F2a fixes, F5)
  wait for a gap between Apply Desk segments, or are handed to the
  Apply Desk session, to avoid colliding with its live plan.
  (2026-11-20)
- F1's correction is one dated note in `applydesk/guide/archive/README.md`,
  not 17 annotations: every closed Apply Desk plan, AD1 to AD1Q, carries
  the line "`close_check.py` reads only RRW's `guide/`" (the re-take
  found 17, not the 3 Cordware's review counted), and the index is where
  a reader of those plans starts. (2026-11-20)
- A package's `guide/` is indexed by its top-level `README.md`, not by a
  new `guide/README.md`: the package READMEs already carry those rows,
  and a second index would say it twice. (2026-11-20, rung 4)
- One helper, `tests/unit/_packages.py`, reads `APP_DIRS` for every unit
  gate. It ships in the practice kit beside the gates that import it.
  (2026-11-20, rung 4)
- F8's list becomes derived: a test reads the tree's `*_browser.py`
  files and `CLAUDE.md`'s list, rather than relying on someone
  remembering. (2026-11-20)

## Blast radius (measured)

Taken 2026-11-20 at `881edab4b` (RRW `main`, after AD1Q's close), when the
plan moved here from Cordware.

| What | Count | Command |
|---|---|---|
| Package plans by `close_check`: pass / fail | 20 / 4 (AD1G, AD1H, AD1K C3; 1B C2) | `python3 tools/close_check.py <id>` per plan in `*/guide/{,archive/}segment_*.md` |
| Closed AD plans saying "`close_check.py` reads only RRW's `guide/`" | 17 of 17 (AD1–AD1Q) | `grep -l "reads only RRW" applydesk/guide/archive/*.md` |
| Package live prose files (spec / docs / guide) | applydesk 2/2/2, residentialapps 4/9/12, utilityapps 2/4/1 | `ls <pkg>/{spec,docs,guide}/*.md` |
| Backticked paths in package prose: repo / package-relative / dangling | AD 52/14/4, Res 287/6/6, Util 38/0/6 | a scratch script over `<pkg>/{spec,docs,guide}/*.md` with `PATH_REF` widened |
| Package `guide/README.md` present | 0 of 3 (only `applydesk/guide/archive/README.md`) | `ls <pkg>/guide/README.md` |
| Package route modules without a spec mapping | 26 (AD 4, Res 16, Util 6) | `git ls-files <pkg> \| grep routes` |
| Gates to extend | 4 tests + 1 registry (1,687 lines) | `wc -l tests/unit/test_{doc_references,guide_indexes,index_currency,spec_coverage}.py app/web/spec_registry.py` |
| Reader and skill files | `.claude/agents/spec-writer.md` (145), `.claude/skills/segment-plan/SKILL.md` (142) | `wc -l` |
| Measurement tools | `tools/pace_audit.py` (378; `category()` at line 78), `guide/assessment.json` (no `applydesk` area) | `grep -n` |
| Browser-only test files / listed in `CLAUDE.md` | 20 / 7 | `git ls-files '*_browser.py'`; the `CLAUDE.md` list |
| `CLAUDE.md` length | 341 lines | `wc -l CLAUDE.md` |
| Sweep trigger | 670 merges of 500, last 2026-10-22 | `python3 tools/close_check.py --stale` |
| Rulings | 65 in `applydesk/guide/todo_master.md` (772 lines) | numbered entries in its Rulings section |

## Status

- **Rung 1 (2026-11-20).** Of the four failures, three are one tool
  artifact:
  - **AD1G, AD1H and AD1K (C3).** Each close PR archived the plan first
    and landed its spec edits after it (AD1G: archive `d399da1f0`, spec
    `ccce9f902`–`ed6bf0b6f`, 13:14–13:45 on 2026-11-17). C3's window
    ends at the archive commit, so it never sees the edits. The fix is
    to end the window at the merge that carried the archive into
    `main`; it moves to rung 2, as the plan foresaw.
  - **1B (C2).** Not a close: Residential's 1B is live and paused, and
    its `residentialapps/spec/organization_and_rosters.md` is a new spec
    promised "as items 4 and 5 ship". The Definition of done now counts
    closed plans only.
  - **The correction** is one dated note in
    `applydesk/guide/archive/README.md` (Judgment calls).
- **Rung 2 (2026-11-20).**
  - **`close_check`:** an archived plan's window now ends at the merge
    that carried the archive into `main` (`carrying_merge`). AD1G, AD1H
    and AD1K pass, all seventeen closed Apply Desk plans pass, and
    `--archived` moves from 985/993 to 988/993 honoured, with no other
    plan changed.
  - **`pace_audit`:** package code, templates and tests count as product
    (`PACKAGES`; product PRs since #3820: 25 → 167). A slice committed
    before the previous merge has an unknown turn, not a negative one:
    121 of 232, which the report now names.
  - **`guide/assessment.json`:** an `applydesk` area.
  - **Mutations:** each change, reverted, fails its new tests.
  - **Item read base:** `abdee8b3b`, `main` before this rung.
- **Rung 3 (2026-11-20).** The path gate reads each package's `spec/`,
  `docs/` and `guide/`, with `APP_DIRS` taken from `close_check`.
  - **Exemptions:** `DATED_DOC` widened to `findings_` registers and
    `_vN.N` handovers. Of the 16 dangling references the Blast radius
    counted, that exempts 10 (Apply Desk's register, Utilities' two
    handovers); one more sits in Residential's 1B plan, a `segment_`
    file already exempt.
  - **What it caught:** six references.
    - Four of Residential's, on three lines, name Cordware's private
      records and now read `cordware:docs/…` and `cordware:guide/…`.
    - Two forward references to specs still to be written take the
      inline marker: one in Residential's `todo_master`, and one in RRW's
      own `guide/interoperability.md` that `PATH_REF`'s package prefix
      newly sees.
  - **Conventions:** recorded as `docs/unenforced_conventions.md` §1.13.
  - **Mutation:** a broken `applydesk/` path fails the gate.
- **Rung 4 (2026-11-20).** `test_guide_indexes.py` checks each package's
  `guide/` against its README, and its archive against
  `guide/archive/README.md` where one exists.
  - **What it caught:** three unindexed documents, now given rows:
    Residential's `segment_1D_support_logs.md` and `1D_unit_scoping.md`,
    and Utilities' archived `segment_U2_check_progress.md`.
  - **G5 over package plans:** `test_index_currency.py` holds every
    package plan's Blast radius to an anchor. All 24 already carried one.
    G4 does not apply, since no package `todo_master` uses `**Plan:**`
    pointers.
  - **One loader:** the three gates take `APP_DIRS` from
    `tests/unit/_packages.py`, added to the practice kit and
    `new_project_practices_setup.md`.
  - **Mutations:** an unanchored package Blast radius fails G5, and a
    package with a `guide/` that the gate skipped fails its guard.
- **Rung 5 (2026-11-20).** Each package keeps a `spec_registry.py`
  mapping its routing modules to its own specs, with health routes as
  infrastructure. `tests/unit/test_package_spec_coverage.py` walks the
  Cordware host's route table against all three registries, in both
  directions, with a guard that every package is seen.
  - **Coverage:** all 26 modules mapped; no declared debt.
    - Apply Desk's three page modules go to `applydesk/spec/applications.md`.
    - Residential's go to `residentialops_ui.md` or `supportlogs_ui.md`.
    - Utilities' go to `email_check.md` or `utilities.md`, which has a
      section per proof of concept.
  - **Mutations:** an unregistered module fails, and so does a mapping
    to a missing spec.
- **Rung 6 (2026-11-20).** `spec-writer`'s charter writes a package's
  `spec/` at that package's closes; the skill and `CLAUDE.md` say a
  package plan closes like a root one, both tools run. Prose; no read.

## PR ladder

Prose rungs take no read. Code rungs (2, 3, 4, 5, 9) are one item for
`diff-reviewer`, read cumulatively at rung 9 from the `main` SHA before
rung 2, recorded in rung 2's PR.

1. **F1: settle the failing closes.** Run `close_check` on AD1G, AD1H,
   AD1K and 1B. For each failure, either fix the plan or spec, or waive
   it with a reason. One dated correction in
   `applydesk/guide/archive/README.md` says the tool has read Apply
   Desk's plans since 2026-11-02, with the results (Judgment calls). If
   C3's window is at fault, the tool fix moves to rung 2. Prose.
2. **F6: measurement sees packages.**
   - `pace_audit.category()` treats `<pkg>/` code, templates and tests
     as product.
   - Turn is measured from the later of the previous merge and the
     slice's first commit, or reported as unknown when the commit
     predates it; the docstring says which.
   - `guide/assessment.json` gains an `applydesk` area.
   - Tests in `tests/unit/test_pace_audit.py` (or the nearest).
3. **F2a: the doc-reference gate reads package prose.**
   - `LIVE_PROSE` takes `<pkg>/{spec,docs,guide}/*.md`, and `PATH_REF`
     takes package prefixes.
   - It resolves repo-first, then package (Semantics).
   - It honours the `cordware:` prefix, and widens `DATED_DOC`.
   - Fix the 16 dangling references in the same rung.
   - Mutation: break one `applydesk/` path, and the test fails.
4. **F2b: guide indexes for packages.**
   - A `guide/README.md` for each package, with a row per document.
   - `test_guide_indexes.py` and `test_index_currency.py` parametrized
     over the root and `APP_DIRS`.
   - Mutation: a new unindexed package plan fails.
5. **F2c: spec coverage for package routes.**
   - A registry per package, or `spec_registry.py` widened, mapping
     each of the 26 modules, with any unmapped in a declared baseline.
   - Mutation: a new unregistered route module fails.
6. **F3: `spec-writer` and the skill for package plans.**
   - The charter's write scope becomes `spec/` and `<pkg>/spec/`, for
     that package's closes.
   - The skill's close steps name `close_check` and `spec-writer` for
     package plans.
   - `CLAUDE.md` "Where work runs" says the same.

   Prose.
7. **F4: record the read-cadence ruling** (Semantics, ruled
   2026-11-20).
   - `CLAUDE.md` "Where work runs": the per-item rules become per
     closing unit, with the size cap and the iteration-rung exemption;
     `AGENTS.md` is copied.
   - `rrw_sdd_in_practice.md` §6.4 adds the ruling as the cadence's
     third cut, with Apply Desk's read counts as its evidence.
   - Constitution III gains a dated annotation, as the 2026-09-18
     change did.
   - The segment-plan skill's close step says the closing unit's
     `Status` records its reads.

   Prose.
8. **F5: write down the rulings policy** (Semantics, ruled
   2026-11-20).
   - `rrw_sdd_in_practice.md` §4 and §6.1 gain the rulings layer:
     standing during major building, folded into the spec at a major
     juncture.
   - Constitution I gains a dated annotation saying the same.
   - `applydesk/guide/todo_master.md`'s Rulings heading names its first
     folding juncture, the end of the UI prototyping phase (AD1 → AD2).

   The fold itself, and archiving v0.6b, belong to that juncture, not to
   this segment. Prose; coordinate with the Apply Desk session.
9. **F8: derive the browser-only list.**
   - A unit test fails when a `*_browser.py` file is missing from
     `CLAUDE.md`'s tool-gated list, or listed but absent.
   - Fix the list (7 → 20).
   - Note `CLAUDE.md`'s length (341) in §6.7.

   Last code rung: the item's cumulative read.
10. **Close.**
    - `spec-writer` over the Doc impact files;
    - `close_check 23H`;
    - Status compacted;
    - the plan archived.

    F7 follows as its own work (Decision).

**After the close (F7, not this segment):**
- a whole-folder sweep, which resets `--stale`;
- a codebase assessment with its findings register, counting
  `applydesk` for the first time;
- then the practice document's figures re-taken at that assessment's
  SHA, with Apply Desk's evidence added to §5 (scaffold at application
  scale) and §6.4 (reads recorded per close).

## Definition of done

- `python3 tools/close_check.py <id>` passes, or waives with a reason,
  for every closed package plan (19 at the re-take). An open plan's
  commitments to files not yet written are not failures (Status, rung 1).
- `tests/unit/test_doc_references.py`, `test_guide_indexes.py`,
  `test_index_currency.py` and `test_spec_coverage.py` read every
  `APP_DIRS` package, each with a recorded mutation that fails it.
- `.claude/agents/spec-writer.md` names `<pkg>/spec/` in scope, and the
  segment-plan skill's close names both tools for package plans.
- `CLAUDE.md` records the per-closing-unit read cadence (cap and iteration exemption included), and its browser-only list
  is derived-tested (20 files at the re-take).
- `rrw_sdd_in_practice.md` §4/§6.1 and constitution I describe rulings
  as the author ruled (standing while building, folded at a major
  juncture), and Apply Desk's Rulings heading names its first juncture.
- `python3 tools/pace_audit.py --cut 3820 --since 2026-11-06` shows
  package code PRs as product and no negative turn; `guide/assessment.json`
  has an `applydesk` area.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 23H` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

1. ~~Read cadence~~: one read per closing unit, with a size cap and no
   read for author iteration rungs (author, 2026-11-20; Semantics).
2. ~~Rulings~~: standing while major building runs, folded into the
   spec at a major juncture; v0.6b archived eventually, with no hurry
   (author, 2026-11-20; Semantics).
3. ~~Spec coverage shape~~: a registry per package
   (`<pkg>/spec_registry.py`), so no package depends on `app/`; one test
   reads them all (rung 5 builder, 2026-11-20).
4. ~~When to start~~: at a gap between Apply Desk segments, all rungs
   in one run, on the author's explicit word (author, 2026-11-20).

## Out of scope

- **F7's sweep and assessment:** separate work, after the close
  (Decision).
- **Cordware's own guide/:** it has none of RRW's tooling, and closes
  by hand.
- **Folding Apply Desk's rulings, and archiving v0.6b:** at the end of
  its UI prototyping phase (AD1 → AD2), not here (Semantics, F5).
- **The phone work:** `guide/rrw_mobile_responsive.md`.

## Doc impact

- `rrw_sdd_in_practice.md` — §4 and §6.1 gain rulings (rung 8); §6.4 the read-cadence ruling (rung 7); §6.7 the `CLAUDE.md` length (rung 9).
- `constitution.md` — Article I gains a dated annotation on the rulings layer (rung 8); Article III gains a dated annotation for the per-closing-unit cadence (rung 7).
- `CLAUDE.md` — "Where work runs": package closes run both tools (rung 6), the cadence ruling (rung 7), the derived browser-only list (rung 9); `AGENTS.md` copied.
- `.claude/agents/spec-writer.md` — write scope includes `<pkg>/spec/` (rung 6).
- `.claude/skills/segment-plan/SKILL.md` — close steps for package plans (rung 6); a closing unit's `Status` records its reads (rung 7).
- `tools/pace_audit.py` — package code as product; turn for stacked slices (rung 2).
- `guide/assessment.json` — an `applydesk` area (rung 2).
- `docs/unenforced_conventions.md` — the `cordware:` prefix and package-relative resolution recorded (rung 3).
- `applydesk/guide/archive/README.md` — one dated correction: `close_check` has read Apply Desk's plans since 2026-11-02, with each failing close's result (rung 1).
- `applydesk/guide/todo_master.md` — its Rulings heading names the first folding juncture, AD1 → AD2 (rung 8).
- `new_project_practices_setup.md` — the kit table gains `tests/unit/_packages.py` (rung 4).
- `guide/todo_master.md` — delete the 23H entry (at close).
