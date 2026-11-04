# Segment 22E — Pyright strict mode, package by package

**Opened:** 2026-11-04, filed at the author's request as 22C's second
follow-up · **Theme:** from "no wrong types" to "no unknown types" ·
**Related:** `guide/archive/segment_22C_pyright.md` (the basic-mode gate this
tightens), `guide/segment_22D_pyright_tests.md`

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

## Blast radius (measured)

Taken 2026-11-04 at `9b45a9c1`, pyright 1.1.414, `typeCheckingMode =
"strict"` over 22C's application-code scope.

| What | Count | Command |
|---|---|---|
| Errors, strict | 2,137 in 153 files | `pyright --outputjson` with `typeCheckingMode = "strict"` |
| By package | `app/web` 955 (55 files), `app/services` 877 (75), `residentialapps` 216 (10), `utilityapps` 46 (4), `cordware` 30 (3), `app/db` 8, `app/schemas` 4, `app/main.py` 1 | `Counter` over the path |
| By rule | `reportUnknownVariableType` 443, `reportPrivateUsage` 437, `reportUnknownMemberType` 401, `reportUnknownArgumentType` 341, `reportArgumentType` 101, `reportUnknownParameterType` 99, `reportUnusedFunction` 91, `reportMissingTypeArgument` 59 | `Counter` over `rule` |
| Python files per package | `app` 245, `cordware` 9, `residentialapps` 29, `utilityapps` 9 | `find <pkg> -name "*.py" -not -path "*/tests/*" \| wc -l` |

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

- Every application package is in `strict`, and `pyright` exits 0.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 22E` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **The private-name convention** (Semantics): keep it and turn the rule
  off, or rename across packages? Author, at rung 1.
- **Strict for tests** once 22D gates them? Probably never: tests lean on
  loose fixtures by design. Author, at this plan's close.

## Out of scope

- Test code: `guide/segment_22D_pyright_tests.md`.

## Doc impact

- `pyproject.toml` — `[tool.pyright]` `strict` list grows per rung (rungs 1–7).
- `CLAUDE.md` — "Common commands": pyright runs strict on the listed packages (at close); `AGENTS.md` copied.
- `AGENTS.md` — the twin, copied from `CLAUDE.md` (at close).
- `guide/todo_master.md` — delete the segment's entry at close.
