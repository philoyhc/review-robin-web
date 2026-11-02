# Pyright adoption for review-robin-web

Baseline taken 2026-11-01 at `b8bba7f` (merge of #3452). A brief for an
agent session: what was found, what to change, in what order. Read
`CLAUDE.md` first; its conventions (small PRs, `diff-reviewer` per item,
doc gates in `tests/unit/`) bind every slice below.

## Why

Nothing in the repo enforces the "prefer explicit types" convention.
`ruff` runs on its default rule set (pyflakes + pycodestyle errors only),
and no type checker runs anywhere — not in the session-start hook, not in
`ci.yml`, not in the `babysit-merge` gate. A compiler-style reject on
every agent edit is the cheapest feedback loop a Python codebase can
add, and this one is already most of the way there: models are
SQLAlchemy 2.x `Mapped[]` throughout, and ~95% of `def`s in `app/` carry
return annotations.

## Baseline numbers

Run with pyright 1.1.414, `typeCheckingMode = "basic"`, `pythonVersion =
"3.12"`. (Taken under a 3.13 interpreter with 3.12 semantics pinned —
re-take once under the project `.venv` and expect small deltas.)

| Scope | Files | Errors | Time |
|---|---|---|---|
| `app/`, `cordware/`, `residentialapps/`, `utilityapps/` | 312 | **349** | 20 s |
| `tests/` | 587 | 1,859 | 33 s |

By package (app scope): `app/services` 166 · `app/web` 82 ·
`residentialapps/tests` 40 · `utilityapps/tests` 22 · `cordware/tests` 13
· `residentialapps/residentialops` 12 · `utilityapps/email_check` 9 ·
`residentialapps/supportlogs` 4 · `utilityapps/main.py` 1.

By rule: `reportArgumentType` 220 · `reportAttributeAccessIssue` 80 ·
`reportOptionalMemberAccess` 29 · `reportCallIssue` 6 · everything else
≤ 5.

The 349 are not noise. They fall into five clusters, listed below in the
order to fix them (cheapest and widest first).

## Clusters

### A. Two Protocol mismatches — 39 errors, two definitions to fix

`list[Assignment]` is passed where `Sequence[GroupKeyable]` is declared
(18), and `list[InstrumentResponseField]` where `Iterable[BranchField]`
is declared (16), plus a few neighbours. Either the Protocol declares a
member the concrete class lacks or spells it differently, or the
Protocol should be `Sequence[Assignment]`. Find the two Protocol
definitions, reconcile, done.

Top files: `app/services/responses/_core.py` (11),
`app/web/routes_reviewer/_surface/_context.py` (7),
`app/services/extracts/by_instrument_extract.py` (3),
`app/services/monitoring.py` (3).

### B. `Row` / `Result` / `Select` unpacking leaking `object` — 117 errors

`session.execute(select(User))` yields `Result[tuple[User]]`; code then
unpacks as if it were `User`. Also `Select[User]` returned where the
annotation says `Select[tuple[User]]`. Fix by using `session.scalars()`
/ `.scalar_one()` / `.scalar_one_or_none()` for single-entity selects,
and by annotating multi-column selects explicitly. A handful are
`TypeEngine[Any].length` (3) — narrow to `sa.String` before reading
`.length`.

Top files: `app/web/routes_operator/_setup_relationships.py` (19),
`app/services/users.py` (16), `app/services/assignments/_generate.py`
(12), `app/services/session_config_io/_apply_parse.py` (12),
`utilityapps/tests/test_email_check_check.py` (11),
`app/services/session_purge.py` (10), `app/services/instruments/_band1.py`
(9), `app/web/views/_audit_log.py` (7).

### C. `X | None` passed where `X` is required — 86 errors

Route-level and service-level lookups that return `Optional` and are
used unnarrowed. **Each of these is a candidate latent bug**: decide per
site whether the value really cannot be `None` (then narrow with an
assert / early 404 via the existing deps) or whether it can (then the
caller has a real bug). Do not blanket-`assert`; read each one.

Top files: `residentialapps/tests/test_leave_admin.py` (12),
`residentialapps/tests/test_leave_staff.py` (7),
`utilityapps/email_check/check.py` (6), `app/services/relationships.py`
(4), `app/services/responses/_branching.py` (4),
`app/services/instruments/_pagination.py` (3),
`app/web/routes_operator/_quick_setup.py` (3).

### D. `LogRecord` attribute access — 13 errors, one class

Tests (and `utilityapps/email_check`) read custom attributes off
`logging.LogRecord`. Define a small `TypedDict` or a `LogRecord` subclass
with the extra fields, or use `getattr` with a default at the read
sites. Files: `utilityapps/tests/test_email_check_check.py` (5),
`cordware/tests/test_graph.py` (3), `cordware/tests/test_logging.py` (2),
one each in `test_identity.py` and the two `test_mounts.py`.

### E. Residue — 94 errors, read individually

Mixed: `sorted(key=str.lower)` over `str | None` keys
(`app/services/account_listing.py:289`); `dict[tuple[int,int],
Relationship]` vs a looser declared parameter type in `_generate.py` /
`_band1.py` (fix the parameter annotation, 3 sites); `dict[int, Reviewee
| Reviewer]` vs `dict[int, object]` (invariance — use `Mapping`);
`session_rehydrate.py` (11), `residentialops/sample_leave.py` (9),
`_setup_observers.py` (6). Expect a few to be `# pyright: ignore[rule]`
with a one-line reason, but default to fixing.

## Slices

Land as separate PRs in this order. Each code slice takes a
`diff-reviewer` read per `CLAUDE.md`.

1. **Config only.** Add to `pyproject.toml`:

   ```toml
   [tool.pyright]
   include = ["app", "cordware", "residentialapps", "utilityapps"]
   exclude = [".venv", "**/__pycache__"]
   pythonVersion = "3.12"
   typeCheckingMode = "basic"
   ```

   Add `"pyright>=1.1.400"` to `[project.optional-dependencies].dev`.
   Update `README.md` (dependency change) and the "Common commands"
   block in `CLAUDE.md` + `AGENTS.md` with `pyright` beside `ruff check
   .`. **Do not add it to CI yet** — the count is not zero.

2. **Cluster A** (Protocols).
3. **Cluster B** (Row/Select), possibly split: services first, routes
   second.
4. **Cluster C** (Optional narrowing). Note in the PR body any site
   where narrowing changed behaviour (a new 404, a new raise).
5. **Clusters D + E**.
6. **Gate.** When `pyright` exits 0 on the app scope:
   - `ci.yml`: add a `Type check` step (`run: pyright`) after `Lint` in
     the `test` and `residential` jobs. Not in `prose`.
   - `CLAUDE.md` / `AGENTS.md` "Where work runs": add `pyright` to the
     pre-PR gate sentence next to `pytest -n auto` and `ruff check .`.
   - `.claude/skills/babysit-merge`: add it to whatever check list the
     skill reads.
   - `tools/ci_lanes.py`: confirm the full lane is the one that runs it
     (it should be, as a sibling of ruff).

7. **Tests, later, as a ratchet.** 1,859 errors, dominated by
   `reportOptionalMemberAccess` (492) and `reportOptionalSubscript`
   (286) on fixtures typed `Foo | None`. Two options; pick one in its
   own plan:
   - add `tests` to `include` with
     `reportOptionalMemberAccess = false` and
     `reportOptionalSubscript = false` scoped via a
     `tests/pyrightconfig.json` override, and ratchet those two rules <!-- path-ref-ok -->
     back on per directory (`tests/unit/` first); or
   - leave `tests/` out of the gate entirely and accept that test
     code is checked only by running it.

8. **Strict mode, per package, after 6.** `cordware/` first (16 files),
   then `app/services`, then `app/web`. Use `strict = ["cordware"]` in
   `[tool.pyright]` rather than flipping the global mode.

## Adjacent, not blocking

`ruff` is on defaults. A one-session change to

```toml
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]
```

with `ruff check --fix` would add import sorting, bugbear footguns,
pyupgrade and simplify. Expect a large mechanical diff; land it as its
own prose-free slice with no other change, after slice 1 and before
slice 2 so the type-fix diffs are not polluted by reformatting.

## Re-taking the baseline

```bash
pip install -e .[dev]
pyright --outputjson > /tmp/pyright.json
python3 -c "import json,collections;d=json.load(open('/tmp/pyright.json'));print(d['summary']);print(collections.Counter(x.get('rule') for x in d['generalDiagnostics'] if x['severity']=='error').most_common())"
```

Record the summary line in this file's header when you do.
