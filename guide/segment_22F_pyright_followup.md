# Segment 22F — Pyright follow-up

**Opened:** 2026-11-04, from the leftovers of 22C–22E (author reserved
22F for them) · **Theme:** close the last holes in the type gate ·
**Related:** `guide/archive/segment_22E_pyright_strict.md` (§ Status lists
what this inherits), `guide/archive/segment_22D_pyright_tests.md`

## Opportunity

22E made every application package pass strict mode, but pyright still
honours `# type: ignore`: 62 such comments in application code hide
errors strict mode cannot see, and while any remain,
`enableTypeIgnoreComments` must stay on, so a new one can hide anything.
22E also left two small defects found while typing (a page that errors on
a malformed audit row, a docstring that contradicts its code), duplicated
helpers its parallel builds produced, and one deprecated SQLAlchemy call.

## Decision

The author's rulings (2026-11-04, on the recommendations put to them):

1. **The 62 `# type: ignore` comments are fixed**, and the last rung turns
   `enableTypeIgnoreComments` off, so a type-ignore comment hides nothing.
2. **The test trees stay relaxed** for good: their `executionEnvironments`
   tables keep the strict rules they fail. Rejected: full strict for
   tests, about 23,000 errors from loose fixtures and stand-ins, for
   little gain over tests that run.
3. **A non-string audit `context.scheduled_at` reads as "unknown"** on the
   workflow card, as an unparseable string already does, rather than
   raising. Rejected: keep raising; a bad audit row should not take
   Session Home down.
4. **`set_band2_state`'s docstring is corrected** to say `None` keeps the
   stored state, as the code does. Rejected: change the code to clear;
   no caller passes `None`, so describing the behavior changes nothing.

Clean-ups, no ruling needed: one JSON-narrowing module for the five
copies; one Jinja-namespace helper for the three; drop
`relationships.py`'s deprecated `Result.tuples()`.

## Semantics

- **No behavior change** except ruling 3, which is named and tested.
- **The roster services' `proposed` dicts** (43 of the 62 ignores) take a
  `TypedDict`, so each field assignment type-checks; the dict's runtime
  shape and the audit `changes(...)` it feeds are unchanged.
- **Shared helpers keep one value type.** JSON helpers return
  `dict[str, object]` / `list[object]` unless a caller needs `Any`; the
  Jinja helper sets globals and filters with the same names as today.
- **The setting's switch is last**: `enableTypeIgnoreComments = false`
  lands only when no `# type: ignore` is left anywhere, tests included.

## Judgment calls — decided

- Rulings 3 and 4 and the `.tuples()` drop share a PR: each is a line or
  two, and 3 carries the only test (2026-11-04).

## Blast radius (measured)

Taken 2026-11-04 at `2ed1de42`.

| What | Count | Command |
|---|---|---|
| `# type: ignore` in application code | 62 in 14 files (`reviewers` 15, `reviewees` 15, `observers` 13, `relationships` 8, the rest 1–2) | `grep -rn "# type: ignore" app cordware residentialapps utilityapps --include=*.py \| grep -v /tests/` |
| By code | `arg-type` 57, `attr-defined` 4, `union-attr` 1 | the same, counted by bracket |
| JSON-narrowing copies | 5 files | `grep -rln "def _json_dict\|def _json_list\|def _json_object\|def json_object\|def json_list\|def _stored_list" app` |
| Jinja-namespace wrappers | 3 files (`urls.py`, both `routes_*/_shared.py`) | `grep -rln "_JinjaNamespaces\|_TemplateEnv\|def add_globals" app --include=*.py` |
| `Result.tuples()` | 1 (`app/services/relationships.py`) | `grep -rn "\.tuples()" app` |

## Status

- **Rung 2** (base `095844ef`): ruling 3, the workflow card reads a
  non-string `scheduled_at` as unknown
  (`test_caption_skipped_reads_a_non_string_time_as_unknown`, which fails
  three ways on the old code); ruling 4, `set_band2_state`'s docstring
  says `None` keeps the stored state; `relationships.py` reads rows
  without `Result.tuples()`.

## PR ladder

1. **Plan and rulings** (this file). Prose only.
2. **Small fixes:** ruling 3 with its test, ruling 4, the `.tuples()` drop.
3. **Shared helpers:** one JSON module, one Jinja helper; the copies go.
4. **The roster services' ignores:** `TypedDict` for `proposed` in
   `reviewers`, `reviewees`, `observers` (43).
5. **The rest of the ignores** (19), then `enableTypeIgnoreComments =
   false`.
6. **Close.**

## Definition of done

- No `# type: ignore` in the repository, `enableTypeIgnoreComments` is
  false, and `pyright` exits 0.
- `build_scheduled_activation_caption` reads a non-string `scheduled_at`
  as "unknown", pinned by a test.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 22F` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

None.

## Out of scope

- Strict mode for test code: ruled out (Decision 2).
- Any type work that changes behavior beyond ruling 3.

## Doc impact

- `pyproject.toml` — `[tool.pyright]` `enableTypeIgnoreComments = false` (rung 5).
- `CLAUDE.md` — "Common commands": a `# type: ignore` hides nothing (at close); `AGENTS.md` copied.
- `AGENTS.md` — the twin, copied from `CLAUDE.md` (at close).
- `guide/todo_master.md` — the 22F entry points at this plan (rung 1); deleted at close.
