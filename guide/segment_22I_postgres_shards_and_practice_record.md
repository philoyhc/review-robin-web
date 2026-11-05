# Segment 22I — Postgres shards, a stale figure, and the practice record

**Opened:** 2026-11-05 · **Theme:** finish the CI wait 22H moved, and let
`rrw_sdd_in_practice.md` record what 22C–22H did to the practice ·
**Related:** `guide/archive/segment_22H_format_and_suite_time.md`,
`guide/archive/segment_22C_pyright.md`,
`guide/archive/segment_22E_pyright_strict.md`,
`guide/archive/segment_22F_pyright_followup.md`, `rrw_sdd_in_practice.md`

Handed off from a read at `095336b` (22H's close) and re-checked at
`a321b04b` on 2026-11-05. Three items, each closing on its own; land them
in order, because Item 3 cites Item 1's measured result.

## Opportunity

**Item 1.** 22H split `ci.yml`'s `test` job into three shards of about
2 m 30 s each, down from 6 m 42 s. That left `CI - Postgres` as the PR's
longest check. It is one serial job: install, the two alembic steps, then
`pytest -n auto --ignore=tests/browser`. Its wall time varies by run:
3 m 51 s on #3631, 4 m 07 s on #3620 and 6 m 00 s on #3629. Nearly all of
that is pytest: on #3631 the step took 3 m 15 s, and the two alembic
steps together took 3 s. `CONTRIBUTING.md` and the `babysit-merge` skill
require it green for every database-reaching PR, so its wait sits on the
critical path of most merges.

**Item 2.** `CLAUDE.md` "Common commands" still says the full suite takes
172 s (2026-10-02). 22H measured about 270 s for 8,361 tests on 4 cores,
and its loop paragraph in "Where work runs" says 4–5 minutes. The two
figures sit about a hundred lines apart in the same file. No gate reads
either one, so this is the kind of drift §6.5 of the practice document
warns about.

**Item 3.** `rrw_sdd_in_practice.md` is the practice's own record.
- §6.3 lists the gates by what they read.
- §6.4 attributes the *build* floor partly to running the gates.
- §7 says the gates derive from what the repository states.
- §9 closes on "the cheap part is the tooling, and it can wait for the
  evidence".
- The Appendix counts 4,800 tests on 2026-09-23.

Segments 22C–22H (2026-11-01 to 11-05, #3584–#3630) added a class of gate
the document doesn't describe, gates that derive from the language:
pyright strict, `ruff format` and `E501`. They also re-cut the wait §6.4
measures. The document mentions none of it:
`grep -ci "pyright\|ruff format\|shard" rrw_sdd_in_practice.md` is 0.

## Decision

**Item 1.** `.github/workflows/ci-postgres.yml`'s `postgres` job becomes a
two-entry matrix, `fail-fast: false`, named `postgres (<shard>)`. Each
entry has its own `postgres:16` service.
- `unit`: `tests cordware/tests residentialapps/tests utilityapps/tests --ignore=tests/integration --ignore=tests/browser`,
  plus the two alembic steps.
- `integration`: `tests/integration`.

The shards don't depend on the alembic steps. `tests/conftest.py`'s
Postgres path drops the schema and runs `alembic upgrade head` itself,
once per worker database. The workflow's own alembic steps check the
migration chain; they don't prepare pytest's database.

Rejected:
- **A separate `migrations` job:** the two steps take about 3 s, and a job
  costs its own setup.
- **Running the round-trip in both shards:** twice the work for no extra
  signal.
- **Three shards mirroring `ci.yml`:** this workflow has no browser tests,
  so the third shard would be empty.

**Item 2.** Replace the figure with a measured one, dated, and nothing
else. Rejected: deleting the figure, since a reader sizing a wait wants
one; and a gate, since checking the figure would mean running the suite.

**Item 3.** Four bounded edits to `rrw_sdd_in_practice.md`, each in the
section that owns the matter, plus Appendix rows. No new section: the
language-level gates are §6.3's decision applied to a different source,
not a new decision. Rejected: a new §6.8, which would restate §6.3 and
§6.4; and leaving the record to the archived plans alone, since archives
are records, not the practice's statement of itself (§4).

## Judgment calls — decided

- **Item 1 keeps the workflow name** `CI - Postgres`, which
  `CONTRIBUTING.md` and the `babysit-merge` skill require. "Green" comes
  to mean both shards. Neither document names the job (checked with
  grep).
- **Item 1 extends `tests/unit/test_ci_shards.py`** to read both workflow
  files, rather than adding a test file. The invariant is the same; only
  the expected set differs, by `tests/browser`.
- **Item 3 takes a `diff-reviewer` read for overclaim**, although it is
  prose-only and the cadence rule exempts prose. The document makes
  measured claims about the practice, and the 2026-09-18 ruling found
  that reads overclaim mainly in prose. Its findings go in Status.
- **Item 3 re-takes only the figures it cites.** The Appendix's other
  figures (co-change, churn, cadence) keep their `3559c7a7` anchor.

## Semantics

- **Item 1 changes which jobs exist, not what runs.** The two shards
  together must collect exactly what today's `--ignore=tests/browser`
  run does, and the alembic steps run once, unchanged. A test that
  passes in the single job but fails in a shard has a cross-file
  ordering dependency. That is a finding, not a sharding matter; 22H saw
  none in `ci.yml`.
- **Item 3 adds claims to a record of measured claims.** Every number in
  the new prose must trace to an archived plan's Status or Blast radius,
  or to a command in the Appendix. An adjective without a figure is an
  overclaim here.

## Blast radius (measured)

Taken 2026-11-05 at `a321b04b`, except where a row says otherwise.

| What | Count | Command or source |
|---|---|---|
| `CI - Postgres` wall | 3 m 51 s (#3631), 4 m 07 s (#3620), 6 m 00 s (#3629) | the PRs' check runs |
| Its steps on #3631 | pytest 3 m 15 s; alembic upgrade and round-trip 3 s | the job's step times |
| Documents naming `CI - Postgres` | 2 | `grep -rln "CI - Postgres" --include=*.md . \| grep -v archive` |
| Prose calling it one job | `CLAUDE.md` "Database"; `docs/database.md` | `grep -n "ci-postgres" CLAUDE.md docs/database.md` |
| `tools/` reading the workflow | `tools/practice_kit.py`, by filename only | `grep -rn "postgres" tools/*.py` |
| Stale figure in `CLAUDE.md` | 1 (line 85) | `grep -n "172 s" CLAUDE.md` |
| `rrw_sdd_in_practice.md` | 324 lines; 0 mentions | `grep -ci "pyright\|ruff format\|shard" rrw_sdd_in_practice.md` |
| `# pyright: ignore` left | 26: 7 in application code, 19 in tests | `grep -rn "pyright: ignore" <roots> --include=*.py \| wc -l` |
| Application Python | 90,646 lines | `git ls-files` over the four packages, less `tests/`, `\| xargs cat \| wc -l` |
| Rule-offs in the test roots | 36 (13 + 9 + 7 + 7) | `[[tool.pyright.executionEnvironments]]` in `pyproject.toml` |

## Item 1 — `CI - Postgres` in two shards

### PR ladder

1. **The split (one PR: CI and one test).**
   - **The matrix,** as the Decision says. The alembic steps run under
     `if: matrix.shard.name == 'unit'`.
   - **The run step** becomes `pytest -n auto -q $PYTEST_ARGS`, with the
     `# shellcheck disable=SC2086` line, as `ci.yml` has it.
     `TEST_DATABASE_URL` is set as today. One added comment line says the
     shards build their own schema.
   - **`tests/unit/test_ci_shards.py`** is parametrized over both
     workflows. For `ci-postgres.yml` the expected set is the testpaths
     set less `tests/browser`. I'll check the test bites by dropping
     `cordware/tests` from the unit shard locally; it must fail and name
     that root.
   - **`CLAUDE.md` "Database" and `docs/database.md`** describe the job as
     shards; then `cp CLAUDE.md AGENTS.md`.
   - **Timings:** measure the PR's own run and put both shards' times in
     the PR body against the three figures above. If the shards differ by
     more than 2×, move `tests/db` to the shorter one and say so.
2. **Close.**

### Definition of done

- Both shards are green on the PR, and their times are in the PR body.
- `tests/unit/test_ci_shards.py` passes on both workflows, and fails on
  the planted omission.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 22I.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Doc impact

- `CLAUDE.md` — "Database": the `ci-postgres` check runs as two shards.
- `AGENTS.md` — the twin, copied from `CLAUDE.md`.
- `docs/database.md` — the CI lines name the shards.
- `guide/todo_master.md` — the segment's entry, edited at each item's close.

## Item 2 — the stale figure

### PR ladder

1. **The figure (prose only, no read).** Re-take it in the container with
   `time pytest -n auto` (it has 4 cores) and write that figure, the
   count and the date into `CLAUDE.md` "Common commands" in place of
   172 s. Then `cp CLAUDE.md AGENTS.md`. Nothing else goes in this PR.
2. **Close.**

### Definition of done

- `grep -n "172 s" CLAUDE.md AGENTS.md` finds nothing, and the new
  figure carries its date.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 22I.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Doc impact

- `CLAUDE.md` — "Common commands": the suite's measured time.
- `AGENTS.md` — the twin.

## Item 3 — the practice record

### PR ladder

1. **The edits (prose only, with the read above).** Every backticked path
   must resolve, because `tests/unit/test_doc_references.py` reads this
   file. Write in the document's register: decision, why, trade-off, and
   a figure beside its command. US spelling.
   - **(a) §6.3, after the gate list:** a paragraph, **The language-level
     gates.**
     - **What they are:**
       - pyright, from 307 errors in basic mode to 0 (22C, #3584–#3593);
       - strict mode: 2,137 errors at its blast radius, 437 of them
         private uses that the `reportPrivateUsage` ruling allowed, and
         1,846 fixed (22E, #3604–#3609);
       - `enableTypeIgnoreComments = false`, with 26 reasoned
         `# pyright: ignore` comments left (7 in application code, 19 in
         tests);
       - `ruff format` over 936 files, with an exact pin, and `E501` with
         one generated file exempt (22H).
     - **Why it is the same decision:** "prefer explicit types", a
       convention in `CLAUDE.md`, became a failing check. The check reads
       the code, so it can't go stale.
     - **What they found, said plainly:**
       - five behavior defects in about 91k lines of application code:
         four in 22C (the observer collation's `<h2>None</h2>`, and three
         paths that raised the wrong error or none), and one in 22E (a
         500 in the email check, found by the item read);
       - one structural pattern in 22F: the ignores hid an `object()`
         sentinel, now one-member enums.

       That is a low yield looking back; the gate's value is forward, on
       new agent output.
     - **The trade-off:**
       - the four test roots keep 36 rule-offs, and stay relaxed for good
         (22F);
       - pyright matched a Protocol against a model's `Mapped[int]`, so
         22C's planned Protocol fix failed. 22C's Status records it: a
         Decision proved wrong, with the reason kept.
     - **The gate list** gains `tests/unit/test_ci_shards.py`: it reads
       both workflows and `pyproject.toml`, and fails when a test file
       falls out of CI.
   - **(b) §6.4, "What the cadence does not touch", after the
     `Instruction-Received` paragraph:** two or three sentences.
     - The build floor was put partly down to running the gates.
     - 22H made the targeted loop a rule and cut CI's `test` job to three
       shards; 22I Item 1 cut `CI - Postgres`, cited with its measured
       times.
     - No `tools/pace_audit.py` re-take has been made since, so whether
       *build* moved is not known; the next practice audit should take
       it.
   - **(c) §9, third paragraph:** "the three weeks since then" becomes
     dated. Add one sentence: the language-level gates, the formatter and
     the CI split arrived within days once chosen, each measured first
     (307 → 0, 2,137 → 0, 6 m 42 s → about 2 m 30 s). That bears out the
     paragraph's own claim a third time.
   - **(d) §7, "Not executable-spec":** add one clause. The gates derive
     from what the repository states, or, for §6.3's type and format
     gates, from the language itself, not from acceptance criteria.
   - **Appendix:**
     - "Machine-checkable definition of done": the test count, re-taken
       and dated, plus "pyright strict and `ruff format` as gates
       (22C–22H)".
     - The anchor sentence keeps `3559c7a7`, with one added sentence
       giving this PR's base for the test count and the new gates.
     - "Re-taking the numbers" gains a bullet: `pyright`,
       `ruff format --check .`, `ruff check --select E501 .`.
2. **Close.**

### Definition of done

- `pytest tests/unit` is green.
- The `diff-reviewer` read for overclaim is done, and its findings are in
  Status.
- Every figure in the new prose sits beside the plan or command that
  produced it.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 22I.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Doc impact

- `rrw_sdd_in_practice.md` — §6.3, §6.4, §7, §9 and the Appendix.
- `guide/todo_master.md` — delete the segment's entry at the last close.

## Open questions

- ~~Does anything in `tools/` read `ci-postgres.yml` by job name?~~ No.
  `tools/practice_kit.py` names the file only (re-checked 2026-11-05).
- **Where `tests/db` goes:** the unit or the integration shard. It is
  decided on the measured split at Item 1, not in advance.

## Out of scope

- Re-taking §6.4's cadence figures (`tools/pace_audit.py`): the next
  practice audit.
- Splitting `ci-postgres` further, or caching its install: only if
  Item 1's split leaves it the longest check by more than a minute.
