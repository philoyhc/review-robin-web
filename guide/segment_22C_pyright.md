# Segment 22C — A type checker: pyright

**Opened:** 2026-11-02, from the author's brief (placed as
`guide/pyright_adoption_plan.md` in `#3520`, revised into this plan the <!-- path-ref-ok -->
same day) · **Theme:** a compiler-style reject on every edit, gated in CI
once the app code is clean · **Related:**
`guide/archive/segment_22A_ci_lanes.md` (the lanes the gate joins),
`CONTRIBUTING.md` (what gates a merge), `.claude/skills/babysit-merge/SKILL.md`

## Opportunity

Nothing enforces `CLAUDE.md`'s "prefer explicit types". `ruff` runs its
default rules (pyflakes and pycodestyle errors only), and no type checker
runs anywhere: not in the session-start hook, not in `ci.yml`, not in the
`babysit-merge` gate. The code is most of the way there already: models
are SQLAlchemy 2.x `Mapped[]` throughout, and about 95% of `def`s in
`app/` carry return annotations. A checker is the cheapest feedback loop
an agent's edits can get.

Pyright 1.1.414 in `basic` mode, `pythonVersion = "3.12"`, under the
project `.venv` (SQLAlchemy 2.1.5) finds **289 errors in 70 files** of
application code (`app/`, `cordware/`, `residentialapps/`, `utilityapps/`,
less their `tests/` folders), in about 40 s. Test code adds 1,964 more:
1,879 under `tests/` and 85 in the three packages' own `tests/`.

## Decision

**Pyright, basic mode, gating application code only**, fixed cluster by
cluster before the gate goes on, so the gate starts at zero and stays
there. Test code and strict mode come later, each in its own plan.

- **Scope:** `include` the four packages and `exclude` every `tests/`
  folder, so "the gate" means one thing: the code that ships. The
  author's brief included the packages' own `tests/` but not `tests/`;
  either all test code is gated or none (2026-11-02).
- **Versions pinned:** `pyright==1.1.414` in the `dev` extra, and the
  SQLAlchemy floor raised to `>=2.1` in `pyproject.toml` and
  `requirements.txt`. Error counts move with both: 2.1 types `Select`
  and `Result` differently from 2.0, and a gate has to give the same
  answer on every machine.
- **Lint rules widened first** (split into 2a and 2b, and `E` kept to
  ruff's default subset: `## Status`): `ruff`'s `select` grows to
  `E, F, I, B, UP, SIM` in its own rung, before the type fixes, so their
  diffs are not mixed with reformatting.

Rejected: *mypy.* Slower, and its SQLAlchemy support was a plugin now
retired; pyright reads 2.x `Mapped[]` natively. Rejected: *gating now
with a baseline file of known errors.* 289 errors in 70 files is a
handful of PRs, and a baseline file is a second list to keep in step.

## Semantics

The five clusters, in the order the ladder fixes them. Counts are
approximate where a diagnostic could sit in two clusters; the command in
`## Blast radius` re-takes them.

- **A. Two Protocols declare writable attributes (39).** *(The fix below did
  not work; what was built is in `## Status`, rung 3.)* `GroupKeyable`
  (`app/services/responses/_group_reconciliation.py`) and `BranchField`
  (`app/services/responses/_branching.py`) state their fields as plain
  attributes. A writable Protocol member is invariant, and a model's
  `Mapped[int]` is not `int`, so `Assignment` and
  `InstrumentResponseField` fail to match (`"id" is invariant because it
  is mutable`). **Fix:** declare each member as a read-only `@property`.
  Not `Sequence[Assignment]`: `GroupKeyable` exists so the
  `AssignmentPair` projection shares `group_keys` (19S Item 3).
- **B. SQLAlchemy 2.0 spellings under 2.1 (about 50).**
  `Select[tuple[User]]` is the 2.0 form; under 2.1 it makes `.scalars()`
  yield `tuple[User]` (`_batch_lock` in `app/services/users.py`,
  `_eligibility_lock` in `app/services/session_owners.py`): annotate
  `Select[User]`. `.rowcount` on a bare `Result` (12) needs
  `CursorResult`. Unpacking `Row` as an entity, and
  `TypeEngine[Any].length` (narrow to `sa.String` first), are the rest.
- **C. `X | None` used where `X` is required (about 85).** Each is a
  candidate latent bug: narrow where the value cannot be `None` (an
  early 404 through the existing deps, or an assert with its reason), and
  fix the caller where it can. Never a blanket assert. A narrowing that
  changes behavior (a new 404, a new raise) is named in its PR body.
- **D. `LogRecord` extra attributes.** All 13 sit in test code, so this
  cluster moves out of scope, with the tests.
- **E. The residue (about 115), read one by one.** `sorted(key=str.lower)`
  over optional keys, invariance (`dict[int, Reviewee | Reviewer]` passed
  as `dict[int, object]`: take a `Mapping`), loose parameter annotations
  in `_generate.py` and `_band1.py`, and the larger files
  (`session_rehydrate.py`, `residentialops/sample_leave.py`,
  `_setup_observers.py`). A `# pyright: ignore[rule]` carries a one-line
  reason; fixing is the default.

## Judgment calls — decided

- Basic mode, not strict, for the first gate: strict on 289 errors' worth of
  existing code is a rewrite (2026-11-02).
- Test code excluded from the first gate; it is checked by running it
  until its own plan (2026-11-02).
- One `diff-reviewer` read for the fix rungs together, as one item
  (`CLAUDE.md` "Where work runs"), not one per rung as the brief had it;
  the ruff rung takes its own (2026-11-02).
- **Interoperability, pre-positioned** (`guide/interoperability.md` §2,
  2026-11-04): a package added later (ApplyDesk, a handoff module) joins
  the gate when it is created; and the `sqlalchemy>=2.1` floor reaches
  production through the next Cordware import of `requirements.txt`, so
  that import's PR says so.

## Blast radius (measured)

Taken 2026-11-02 at `3df7a365`, pyright 1.1.414, SQLAlchemy 2.1.5; the
first two rows and the by-package row re-taken at rung 1 (2026-11-04,
`e9555785`). Under an activated `.venv`: without one, pyright reads
whatever `python` is on PATH and reports the missing imports too (622).

| What | Count | Command |
|---|---|---|
| Errors, application code | 307 in 78 files (289 in 70 on 2026-11-02, before 14E) | `pyright --outputjson` with the rung 1 config |
| Errors, the four packages with their `tests/` (the brief's scope) | 395 in 97 files (374 on 2026-11-02) | the same, without the `tests` exclude |
| Errors, `tests/` | 1,879 in 599 files | `include = ["tests"]` |
| By package (application code) | `app/services` 195, `app/web` 86, `residentialapps` 16, `utilityapps` 10 (2026-11-04) | `collections.Counter` over the file paths |
| Docs naming the lint command | 7 | `grep -rln "ruff check" --include=*.md . \| grep -v "archive\|\.venv"` (README, CLAUDE/AGENTS, CONTRIBUTING, `docs/local_setup.md`, the skill, `new_project_practices_setup.md`) |
| `ci.yml` jobs running `ruff check .` | 2 (`test`, `residential`) | `grep -n "ruff check" .github/workflows/ci.yml` |
| `cordware/` application files (strict, later) | 9 | `find cordware -name "*.py" -not -path "*/tests/*" \| wc -l` |

To re-take, under the project `.venv`:

```bash
pyright --outputjson > /tmp/pyright.json
python3 -c "import json,collections;d=json.load(open('/tmp/pyright.json'));print(d['summary']);print(collections.Counter(x.get('rule') for x in d['generalDiagnostics'] if x['severity']=='error').most_common())"
```

## Status

- **Rung 1** merged 2026-11-04 (`#3584`): config, pins, docs, the hook.
  One read: the blast-radius rows, the hook's guard and comment, README's
  dev-dependency note; all fixed in the PR.
- **Rung 2 split in two** (author, 2026-11-04): **2a** `I` and `UP`
  (mechanical, `ruff check --fix`), then **2b** `B` and `SIM`
  (judgment). Decisions confirmed at build:
  - `E` stays ruff's default subset (`E4`, `E7`, `E9`), through
    `extend-select`: the whole family adds `E501`, 1,471 long lines with
    no formatter to fix them.
  - `UP042` (`StrEnum`) ignored: it changes what `str()` and `format()`
    give for a member, which templates and audit details render.
  - 2a (`#3585`) leaves pyright at 307 errors. Its read: `alembic`
    made third-party to isort, and the migration template brought up to
    the new rules.
  - **2b:** `B008` exempts FastAPI's parameter calls and the two frozen
    option dataclasses in `zip_bundle.py` (`extend-immutable-calls`), so
    663 findings fell to 90. Ignored: `B905` (`zip(strict=True)` raises
    where a short input truncates today: a behavior change at 42 sites),
    `SIM108` (ternaries, a style call), and after the read `SIM300` and
    `SIM905` (their fixes made tests read worse). The 40 left were
    fixed, by `--fix` or by hand: `raise … from None` where a domain
    error becomes an HTTP 400 or a CLI error, and loop variables bound
    where a closure reads them.
- **Item 2** (rungs 3–6) is read once, cumulatively from `2f9961be`.
- **Rung 3, cluster A:** the read-only `@property` fix does not work.
  `GroupKeyable` already had properties, and pyright 1.1.414 still
  rejects a model whose attributes are `Mapped[int]`: it matches a
  protocol against the declared `Mapped[...]` type, not the descriptor's
  `int`. Built instead: each protocol (now `_GroupKeyShape`,
  `_BranchFieldShape`) is kept for the plain shapes (`AssignmentPair`,
  the Settings import's `_PlannedField`), and the public name is that
  protocol `|` the model. 307 → 268 errors, the 39 counted.
- **Rung 4, cluster B:** 268 → 217 (51). Two helpers carry it:
  `app.db.session.rowcount()` (a DML result's `CursorResult.rowcount`;
  12 sites) and `app.db.base.column_length()` (a `String` column's
  declared length; 3). `Select[tuple[User]]` became `Select[User]` (two
  lock queries, about 30 errors downstream); `Model.__table__.delete()` /
  `.update()` became `delete(cast(Table, …))`; the audit filter is
  generic over its `Select`; `classify_self_review` takes a `Row` or a
  tuple (`Result.tuples()` is deprecated in 2.1).
- **Rungs 5–6 re-cut by package, not cluster** (2026-11-04): after B,
  clusters C and E interleave in the same files (a `None` argument beside
  an invariant `dict`), so a cluster rung would reopen every file twice.
  **5a** `residentialapps` + `utilityapps` (26), **5b** `app/web` (73),
  **6** `app/services` (118), the last build rung and the read.
- **Rung 5a:** 217 → 191. One behavior change: the leave sample's
  `by_precinct` falls back to this week when given a start with no end,
  where it raised `TypeError`.
- **Rung 5b:** 191 → 108 (`app/web` clean; 10 more in `app/services`
  from shared types). `ParseResult` is generic over its row type, which
  cleared 21 errors at their source. **One bug found:** a lone
  instrument with neither short label nor description showed the
  observer collation an `<h2>None</h2>`; the heading is now left out,
  with a test.
- **Rung 6:** 108 → **0**. The rules engine's pairs are cast back to the
  roster types at its two callers (it returns the rows it was given)
  rather than made generic through ~20 internal signatures;
  `write_event`'s `context` and three lookup parameters take a
  `Mapping`. Two paths that raised now behave, each with a test: a
  validated session flipped with no actor (the page-break helpers
  default one to `None`) records an unattributed `session.invalidated`;
  a quota inside a composite raises `ValueError` naming it.
  Item 2's cumulative read (`2f9961be..HEAD`): no blocking defect; two
  narrowings that had changed behavior were put back exactly
  (`_digits`, the IN operand), the `BranchField` alias made lazy, and
  `spec/assignments.md`'s composite-children line left for the close's
  `spec-writer`. Rung 7 must run pyright with the venv's Python: without
  it every import is missing (439 errors).
- **Rung 7, the gate:** `run: pyright` after `Lint` in `ci.yml`'s
  `test` and `residential` jobs (setup-python's interpreter is on PATH,
  so imports resolve without a `venv` key); `pyright` named in the
  pre-PR gate (`CLAUDE.md` / `AGENTS.md`), `CONTRIBUTING.md`'s checklist
  and lane notes, the `babysit-merge` skill, `README.md` and
  `docs/local_setup.md`.

## PR ladder

1. **Config and pins.** `[tool.pyright]` in `pyproject.toml`
   (`include` the four packages, `exclude` `.venv`, `**/__pycache__`,
   `**/tests`; `pythonVersion = "3.12"`; `typeCheckingMode = "basic"`);
   `pyright==1.1.414` in the `dev` extra; `sqlalchemy>=2.1` in
   `pyproject.toml` and `requirements.txt`. `README.md`, `CLAUDE.md`
   and `AGENTS.md` ("Common commands") and `docs/local_setup.md` gain
   `pyright` beside `ruff check .`. The session-start hook runs
   `pyright --version` once, so the Node download it does on first use
   (only where no `node` is on PATH) happens at session start, not
   mid-gate. Not in CI yet. Code: its own
   read (it touches `.claude/hooks/`).
2. **Ruff rules widened** (built as 2a and 2b, `## Status`). `[tool.ruff.lint] select = ["E", "F", "I",
   "B", "UP", "SIM"]` and `ruff check --fix`, then the findings `--fix`
   leaves, by hand. Nothing else in the PR. Its own read, of the config
   and the hand fixes; the mechanical diff is summarized per rule in the
   PR body.
3. **Cluster A**, the two Protocols. Item 2 starts here: record the main
   SHA in this PR's body for the cumulative read.
4. **Cluster B**, services, then routes if it splits.
5. **Cluster C**, one PR per package if it is large; behavior changes
   listed in each body.
6. **Cluster E.** The last build rung of Item 2: `diff-reviewer` on the
   cumulative diff since rung 3's base.
7. **The gate.** When `pyright` exits 0: a `Type check` step
   (`run: pyright`) after `Lint` in the `test` and `residential` jobs of
   `ci.yml`, not in `prose` (`tools/ci_lanes.py` needs no change: only
   the lanes that lint run it); `pyright` added to the pre-PR gate in
   `CLAUDE.md` and `AGENTS.md` ("Where work runs"), in `CONTRIBUTING.md`'s
   checklist and lane notes, and in the `babysit-merge` skill. `actionlint`
   is not run in this repository; CI's own run is the check.
8. **Close.** Plan compacted and archived; the two later plans filed.

## Definition of done

- `pyright` exits 0 on `main` with the rung 1 config (CI's `Type check`
  step on the closing PR).
- `ci.yml`'s `test` and `residential` jobs run `pyright`; `prose` does not.
- `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md` and the `babysit-merge`
  skill name `pyright` in the pre-PR gate; the twins are identical.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 22C` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~Rung 2's rule set~~: two steps, `I` and `UP` then `B` and `SIM`
  (author, 2026-11-04).
- **Tests:** gate them later with the two optional-access rules relaxed
  and ratcheted back per directory (`tests/unit/` first), or leave test
  code to running it? Its own plan; author.
- **Strict mode** after the gate, per package (`strict = ["cordware"]`
  first, then `app/services`, then `app/web`)? Its own plan; author.

## Out of scope

- Test code (1,964 errors, mostly `reportOptionalMemberAccess` and
  `reportOptionalSubscript` on fixtures typed `Foo | None`), with cluster
  D: the open question above.
- Strict mode: the open question above.
- Changing any behavior except where a cluster C narrowing does, named in
  its PR body.

## Doc impact

- `pyproject.toml` — `[tool.pyright]`, the pins, `[tool.ruff.lint]` (rungs 1, 2).
- `requirements.txt` — the SQLAlchemy floor (rung 1).
- `README.md` — `pyright` among the commands and the dev dependencies (rung 1).
- `CLAUDE.md` — "Common commands" (rung 1) and the pre-PR gate in "Where work runs" (rung 7); `AGENTS.md` copied.
- `AGENTS.md` — the twin, copied from `CLAUDE.md` (rungs 1, 7).
- `docs/local_setup.md` — `pyright` beside `ruff check .` (rung 1).
- `.claude/hooks/session-start.sh` — warm pyright's Node download (rung 1).
- `.github/workflows/ci.yml` — the `Type check` step (rung 7).
- `CONTRIBUTING.md` — the checklist and lane notes (rung 7).
- `.claude/skills/babysit-merge/SKILL.md` — `pyright` in Stage 1 (rung 7).
- `guide/todo_master.md` — delete the segment's entry at close.
