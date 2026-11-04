# Segment 22E — Pyright strict mode, package by package

**Opened:** 2026-11-04, filed at the author's request as 22C's second
follow-up · **Theme:** from "no wrong types" to "no unknown types" ·
**Related:** `guide/archive/segment_22C_pyright.md` (the basic-mode gate this
tightens), `guide/archive/segment_22D_pyright_tests.md`

## Opportunity

22C's gate is pyright's `basic` mode: it rejects a wrong type, but not a
missing one. An unannotated parameter, an untyped `dict`, a value read
off `Any` all pass, and each one is a place the checker stops checking.
`CLAUDE.md` asks for explicit types; strict mode is the rule that holds
code to it. Measured over application code, strict mode finds **2,137
errors in 153 files**, nearly all of them unknown or partially unknown
types and private-name use across modules, not wrong behavior.

## Decision

**Strict per package, smallest first, through pyright's `strict = [...]`
list**, so a package joins strict mode only when it is clean and stays
there: `cordware` (30), `utilityapps` (46), `residentialapps` (216),
then `app` by subpackage (`app/db`, `app/schemas`, `app/services`,
`app/web`).

Rejected: *flip the whole codebase to strict with per-file
`# pyright: basic` opt-outs.* 150 opt-out comments is a baseline written
into the code. Rejected: *strict for new files only.* Most edits land in
old files, which would never tighten.

## Semantics

- **`reportPrivateUsage` (437)** mostly flags the codebase's own
  convention: services import `_helpers` from sibling modules inside one
  package. Decide once, in rung 1, whether that convention stands (the
  rule turned off, with the reason) or the helpers are re-exported
  without the underscore. Not both, and not per file.
- **Unknown types from libraries** (Jinja, some SQLAlchemy expressions)
  get a typed wrapper at the boundary, not a `cast` at each use.
- **`reportUnusedFunction` (91)** may flag route handlers registered by
  decorator; confirm before deleting anything.
- **No behavior changes.** A fix that changes behavior is named and
  tested, as in 22C.

## Judgment calls — decided

- `cordware` first: 30 errors in 3 files, and it is the host every app
  depends on (2026-11-04).
- **Private names:** the convention stands; `reportPrivateUsage` is off
  everywhere (author, 2026-11-04).

## Blast radius (measured)

Taken 2026-11-04 at `9b45a9c1`, pyright 1.1.414, `typeCheckingMode =
"strict"` over 22C's application-code scope.

| What | Count | Command |
|---|---|---|
| Errors, strict | 2,137 in 153 files | `pyright --outputjson` with `typeCheckingMode = "strict"` |
| By package | `app/web` 955 (55 files), `app/services` 877 (75), `residentialapps` 216 (10), `utilityapps` 46 (4), `cordware` 30 (3), `app/db` 8, `app/schemas` 4, `app/main.py` 1 | `Counter` over the path |
| By rule | `reportUnknownVariableType` 443, `reportPrivateUsage` 437, `reportUnknownMemberType` 401, `reportUnknownArgumentType` 341, `reportArgumentType` 101, `reportUnknownParameterType` 99, `reportUnusedFunction` 91, `reportMissingTypeArgument` 59 | `Counter` over `rule` |
| Python files per package | `app` 245, `cordware` 9, `residentialapps` 29, `utilityapps` 9 | `find <pkg> -name "*.py" -not -path "*/tests/*" \| wc -l` |

## Status — closed 2026-11-04

**Intended:** a `strict = [...]` list grown package by package until it
named every application package. **Done:** every application package
passes strict mode, in #3604–#3609; 2,137 errors at the blast radius
(437 of them the private uses the ruling allowed), 1,846 fixed.

**Diverged from the Decision and the ladder:**

- **No `strict` list.** Strict mode only raises a rule's level, so a
  listed file reports private use whatever the config says (pyright's
  `getStrictModeNotOverriddenRules` exempts one rule, not this one).
  `typeCheckingMode` is `strict` at the top with `reportPrivateUsage`
  off; each root in `executionEnvironments` turned off only the strict
  rules it still failed, and a package joined when its table went. A
  strict rule a package already passed was enforced from rung 1. Only
  the four test roots keep tables. List/dict/set inference stays basic at
  the top level: not a diagnostic, and installed libraries take it too
  (strict, Jinja's `globals` fails 37 calls; CI caught it, since its
  libraries sit outside the repository).
- Rungs 5 and 6 landed as one PR (#3608), and `app/services` and
  `app/web` were each built by four helpers in parallel, combined per PR.

**Decisions confirmed at build:**

- Library and stored JSON is narrowed with `isinstance`, then `cast` once
  (`_json_dict` / `_json_list`-style helpers); Jinja's untyped
  `Environment.globals` goes through a `Protocol`-typed helper; no
  library needed an ignore.
- **A package-private `_helper` imported by a sibling module is listed in
  its defining module's `__all__`** (pyright counts it as used), which is
  how the private-name ruling meets `reportUnusedFunction`.
- Checks are kept on untrusted input and made honest in type; removed only
  where unreachable (each named in its PR). `reorder_instruments` keeps
  its list check, so its `Sequence` parameter admits a tuple it refuses.
- Two `pyright: ignore[reportUnusedFunction]` keep the monitoring
  rollup's parity oracles, which only tests call; two old
  `# type: ignore` went.

**Behavior changes, named and tested:** a carried email-check outcome
with an unhashable `match_type` was a 500 and is now refused
(`utilityapps`, rung 3, found by the item read). `working_set` in the
Residential sample asserts its students exist rather than carrying
`None` into a `list[Student]` (sample data only).

**Left for 22F:** five JSON-narrowing helpers and three Jinja-namespace
wrappers that could each be one; `set_band2_state`'s docstring says
`None` clears the state, the code keeps it; a truthy non-string audit
`scheduled_at` still raises in `build_scheduled_activation_caption`;
`relationships.py` still calls the deprecated `Result.tuples()`.

**Reads:** one cumulative `diff-reviewer` read (rung 7, from `f45dd46d`):
one medium (the unnamed email-check fix above, then named and tested),
the rest low. Codex: one finding (the inference flags, #3604), fixed.
`spec-writer`: not run, since `Doc impact` names no `spec/` path.
`close_check` notes 18 touched modules whose specs are unnamed: the
changes are types only, so no contract moved.

## PR ladder

1. **The private-name ruling** (Semantics), recorded here, and the
   `strict` list introduced empty.
2. **`cordware`** joins strict.
3. **`utilityapps`.**
4. **`residentialapps`.**
5. **`app/db` and `app/schemas`.**
6. **`app/services`**, one PR per subpackage where large.
7. **`app/web`**, the same.
8. **Close.**

## Definition of done

- Every application package is in `strict`, and `pyright` exits 0. *(Built as strict at the top level with no application table left: `## Status`.)*
- `## Doc impact` section present and current
- `python3 tools/close_check.py 22E` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~The private-name convention~~: kept, the rule off (author, 2026-11-04).
- ~~Strict for tests~~: carried to 22F for the author; meanwhile the test
  roots keep their tables (2026-11-04).

## Out of scope

- Test code: `guide/archive/segment_22D_pyright_tests.md`.

## Doc impact

- `pyproject.toml` — `[tool.pyright]` strict at the top, `reportPrivateUsage` off, a per-root table of the strict rules each root still fails, shrinking per rung (rungs 1–7).
- `README.md` — pyright's mode (at close).
- `CLAUDE.md` — "Common commands": pyright runs strict on application code (at close); `AGENTS.md` copied.
- `AGENTS.md` — the twin, copied from `CLAUDE.md` (at close).
- `guide/todo_master.md` — delete the segment's entry at close.
