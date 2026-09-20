# New-project practice setup

A procedure for an agent linked to a **fresh repository** on the same
stack as this one — Python 3.12, FastAPI, SQLAlchemy 2, Alembic, pytest,
ruff, GitHub Actions. It copies this repository's working practice across
and adapts it to the new environment. What it carries is the practice's
**machinery** — the instruction file, the constitution, the two readers,
the plan procedure, the gates, the tools — not this project's specs,
history or code.

Drop this file into the agent's instructions, or into the new repo's root,
and say "run it". It is written to be executed top to bottom in one
session. Where a step says *ask*, stop and ask; everything else is the
agent's call.

This replaces the 2026-09-04 checklist of the same name. That version was
read by a person and predated the constitution, the plan skill, the close
check, the pace audit and the doc gates; its five day-one items survive
as steps 1, 3, 5 and 7 below, and the one it dropped is named in step 7.

## 0. Preconditions

- The new repository exists, is cloned, and is the working directory.
  It may be empty or carry a first commit; it must not already carry a
  `CLAUDE.md` you were told to keep.
- The source repository `philoyhc/review-robin-web` is reachable — cloned
  beside the new one, or attached to the session. If it is not, **ask**
  for it; the kit is copied from it, not reconstructed.
- `python3` is 3.12 or later and `git` is present. Nothing else is needed
  to run the kit; the gates need the dev install in step 6.

## 1. Export the kit

From the new repository's root, with `SRC` the source checkout:

```bash
python3 "$SRC/tools/practice_kit.py" --export .
```

It copies every `verbatim` and `adapt` file in the table below, generates
the skeletons, appends whichever of the three `.gitignore` harness lines
are missing, and prints one line per entry. The `deferred` rows wait for
step 7: the `app` group imports the application and would fail test
collection in an empty repository; the `theme` group reads `base.html`'s
stylesheet and is exported together with a starter `base.html` the kit
builds. It never overwrites a file that exists; `--force` does. `--list`
prints the table without copying. The table is derived from the tool's manifest and a test in the
source repository keeps them identical, so if they disagree the tool is
right.

| Path | Tier | Needs | Note |
|---|---|---|---|
| `CLAUDE.md` | adapt | — | rewrite Project conventions + Architecture + Where to look; keep Where work runs; cp to AGENTS.md |
| `constitution.md` | adapt | — | keep the six articles; drop the dated annotations; re-point 'derived from' |
| `CONTRIBUTING.md` | adapt | — | fill the merge-policy paragraph's <slow job> and <paths> for the new CI |
| `.gitignore` | skeleton | — | the .claude/* negation lines only; appended if absent |
| `.claude/agents/diff-reviewer.md` | adapt | — | project name in line 1, check 4's seams (routes_operator/_shared.py, base.html), the Azure dev slot in the last paragraph |
| `.claude/agents/spec-writer.md` | adapt | — | cites this project's specs and close procedure; re-point once your spec/ has a second file |
| `.claude/skills/segment-plan/SKILL.md` | verbatim | — | the plan / item / close procedure |
| `guide/segment_plan_template.md` | verbatim | — | the shape every plan copies |
| `guide/sweep_template.md` | verbatim | — | the shape every spec/docs sweep copies |
| `guide/README.md` | skeleton | — | index with the documented shapes the guide-index gate reads |
| `guide/archive/README.md` | skeleton | — | index the archive gate reads; one row per file, no patterns |
| `guide/todo_master.md` | skeleton | — | Done / Upcoming roadmap |
| `guide/deferred_consolidated.md` | skeleton | — | everything scoped but not scheduled |
| `spec/README.md` | skeleton | — | index of the surface contracts |
| `docs/README.md` | skeleton | — | index of the operational docs |
| `docs/status.md` | skeleton | — | implementation state; first row is this setup |
| `docs/unenforced_conventions.md` | skeleton | — | constitution VI's short list; starts empty |
| `.github/workflows/ci.yml` | verbatim | — | ruff + pytest -n auto on 3.12 |
| `.github/workflows/ci-postgres.yml` | adapt | — | DB user / password / name; the alembic round-trip stays |
| `tests/unit/test_doc_references.py` | verbatim | — | the twins, path-reference and section-reference gates; read only the tree |
| `tests/unit/test_guide_indexes.py` | verbatim | — | the guide-index gate; reads the skeleton READMEs |
| `tests/unit/__init__.py` | skeleton | — | makes tests/unit a package; the contrast audit imports its helper relatively |
| `app/web/spec_registry.py` | deferred | app | imports the app; export with --include-deferred once app/main.py exists, then empty the table and lower _MINIMUM_ROUTES |
| `tests/unit/test_spec_coverage.py` | deferred | app | pairs with spec_registry; imports the app, so it cannot collect before one exists |
| `app/web/templates/base.html` | deferred | theme | BUILT, not copied: the source's head through </style> (no-flash theme script, both :root blocks, every component class), a body.ui-v2 with the theme toggle and its script, a content block; rename the title, favicon and storage key |
| `tools/_harness_common.py` | deferred | theme | the stylesheet lift, token parse and contrast pairs; ACCEPTED_BELOW_AA is the inherited palette's list |
| `tools/theme_preview.gen.py` | deferred | theme | regenerate tools/theme_preview.html after export and commit it |
| `tools/theme_customizer.gen.py` | deferred | theme | regenerate tools/theme_customizer.html after export and commit it |
| `tools/theme_variants.gen.py` | deferred | theme | border-contrast report; runs as is |
| `tests/unit/_base_css.py` | deferred | theme | parsing helpers the contrast audit imports |
| `tests/unit/test_generated_tools_are_current.py` | deferred | theme | fails until the two pages are regenerated and committed |
| `tests/unit/test_contrast_audit.py` | deferred | theme | 13 of its 14 pass on the inherited stylesheet; test_the_muted_token_absorbed_the_retired_one asserts this project's template counts |
| `spec/color_tokens.md` | deferred | theme | the inherited palette's catalogue; it cites specs, an archived plan and a test that stay in the source, so the path gate goes red again on export |
| `tools/close_check.py` | verbatim | — | close check entry point |
| `tools/close_check/__init__.py` | verbatim | — | close check package |
| `tools/close_check/_shared.py` | verbatim | — | close check package |
| `tools/close_check/_manifest.py` | verbatim | — | close check package |
| `tools/close_check/_archive.py` | verbatim | — | close check package |
| `tools/close_check/_sweep.py` | verbatim | — | close check package |
| `tests/unit/test_close_check.py` | verbatim | — | builds its own repo; runs on an empty guide/ |
| `tests/unit/test_close_check_archived.py` | verbatim | — | builds its own repo; passes on an empty archive |
| `tools/pace_audit.py` | verbatim | — | merge-history pace audit; needs full history |
| `tests/unit/test_pace_audit.py` | verbatim | — | builds its own repo |
| `tools/practice_kit.py` | verbatim | — | this tool, so the next project can inherit from yours |
| `tests/unit/test_practice_kit.py` | verbatim | — | keeps the manifest, the tree and the setup document in step |
| `tools/README.md` | adapt | — | keep the rows and sections for the tools you copied |
| `new_project_practices_setup.md` | verbatim | — | the procedure; a new project re-derives it from its own kit |

## 2. Read before adapting

Read, in the new tree, in this order: `constitution.md`, then
`CLAUDE.md`, then `.claude/skills/segment-plan/SKILL.md`. Read
`rrw_sdd_in_practice.md` **in the source** — it is the rationale for
every article and is deliberately not copied, because it is this
project's history. The new project writes its own when it has one.

## 3. Adapt, file by file

Work the `adapt` rows in table order. The note on each row is the edit;
these are the details that matter.

- **`CLAUDE.md`.** Keep the header note, "Working approach", "Common
  commands" (fix the app module and DB file names) and "Where work runs".
  Rewrite "Project conventions" down to the stack bullets plus whatever
  the new project has decided; delete the button-role, visibility-mode
  and Easy Auth bullets, which name this app's constants. Rewrite
  "Architecture at a glance" for the new app or reduce it to the
  three-layer rule and a pointer. Regenerate "Where to look" from the
  skeleton indexes. In "Where work runs", the install bullet, the stamp
  bullet and the two-readers bullet are the practice and stay, and the
  dated ruling text may be cut to its four rules; the two gate bullets
  keep their shape but name this project's tests — of the tests they
  cite, only `tests/unit/test_doc_references.py` and
  `tests/unit/test_guide_indexes.py` come with the kit, so the
  inline-scripts, generated-tools, contrast-audit and spec-coverage
  lines go until you have those gates. Then `cp CLAUDE.md AGENTS.md` —
  the twins test is in the kit.
- **`constitution.md`.** The six articles are the practice. Delete the
  dated annotations under III; change "derived from
  `rrw_sdd_in_practice.md` §6" to say the derivation is owed, so the
  first practice audit writes it.
- **`CONTRIBUTING.md`.** The merge-policy paragraph is the point of the
  file. Fill its slow job and the paths only that job covers; for this
  stack that is `ci-postgres` and `alembic/` plus anything issuing
  queries, unless the new project has no Postgres, in which case delete
  the paragraph and the workflow together.
- **`.claude/agents/diff-reviewer.md`.** Check 4 names this app's seams.
  Replace them with the new app's, or with the generic form the
  2026-09-04 checklist carried: "a module importing across a boundary its
  neighbours respect, a hand-rolled thing the codebase has a helper for".
- **`.claude/agents/spec-writer.md`.** Leave as is until `spec/` has a
  second file; then re-point the paths it cites.
- **`.github/workflows/ci-postgres.yml`.** Database user, password and
  name; keep the upgrade / downgrade-base / upgrade round-trip.
- **`tests/unit/test_doc_references.py`** is verbatim and is the first
  gate that will go red, on purpose: it resolves every backticked repo
  path in live prose, and the kit ships prose that points at files that
  stayed in the source — this document's "Deliberately not copied"
  section, `CONTRIBUTING.md`'s pointer to the practice audit, and every
  `CLAUDE.md` section you have not rewritten yet. Fix the ones that
  should point at something of yours; mark the deliberate ones with the
  test's inline escape, the `path-ref-ok` HTML comment, on the line (the
  test's docstring shows it). That red-then-green is the gate's
  first proof that it runs. `tests/unit/test_doc_conventions.py` is
  **not** copied: its checks derive from this app's constants and
  stylesheet, and it is the template for step 7.
- **Deleting a kit file** — `ci-postgres.yml` when there is no Postgres,
  say — also deletes its row from `MANIFEST` in `tools/practice_kit.py`
  and replaces the table in this document with `--list` output, or
  `tests/unit/test_practice_kit.py` fails on the missing path and then
  on the table.
- **`app/web/spec_registry.py`** with **`tests/unit/test_spec_coverage.py`.**
  Empty the module-to-spec table, set `_MINIMUM_ROUTES` to the number of
  routes the new app registers today, and let the baseline set of pending
  modules be whatever the first run reports. The gate then fails on the
  first routing module added without a spec, which is its job.
- **`tools/README.md`.** Delete the rows and sections for tools that were
  not copied. The kit's own row stays.

## 4. Add what the kit cannot carry

- `pyproject.toml`: a `dev` extra with `pytest`, `pytest-xdist`, `httpx`
  and `ruff`, and `[tool.ruff]` with `line-length = 100` and
  `target-version = "py312"`. The workflows and the gates assume these.
- A pytest `conftest` that builds the app's in-memory database from the
  ORM metadata, if the new app has one; the kit's tests do not need it.
- `README.md`: one paragraph pointing at `CLAUDE.md` and `constitution.md`.

## 5. Verify, before the first commit

```bash
pip install -e '.[dev]'
ruff check .
pytest -n auto
python3 tools/close_check.py --stale
python3 tools/practice_kit.py --list
```

Green once step 3 is complete is the expected result; the one gate that
reads prose will have gone red during step 3 and told you what to fix.
If it did not, mutation-test it: add a backticked path to `docs/status.md`
that does not exist, run `pytest tests/unit/test_doc_references.py`,
watch it fail naming the file and line, and remove it. A gate that cannot
go red has not been installed.

If the suite could not run at all, say so in the first PR body and name
what did.

## 6. Record, and the first commit

- Fill the `<date>` placeholders in `docs/status.md`.
- The first commit's first command was `date -u +%FT%TZ` (step 0 was the
  moment to run it; if you did not, run it now and say so). Carry the
  value as the `Instruction-Received:` trailer, per `CLAUDE.md` "Where
  work runs".
- After the commit, `python3 tools/pace_audit.py --cut 1`: it reads the
  merge history, so it has nothing to read before one exists, and on a
  clone with no remote yet it falls back to local `main`.
- Push, open a draft PR, and mark it ready only after reading the
  gates' output, not just their exit code.

## 7. From the second slice on

The practice is now the new repository's, and its own documents govern.
Three things the old checklist put on day one still hold and are the
first things a new project reaches for:

- **Write the merge policy before it becomes a habit** (step 3,
  `CONTRIBUTING.md`). Do not add branch protection until you have
  measured the policy being broken.
- **The diff reviewer reads from the first PR**, once per item under the
  cadence in `CLAUDE.md`; retrofitting it later means its first read is
  against a surface it has no history with.
- **The first time a code constant is described in prose, derive a test
  from the constant** — the template is the source's
  `tests/unit/test_doc_conventions.py`. A checker for a convention
  nobody wrote down, or one that needs a growing allowlist, is not
  written; it goes in `docs/unenforced_conventions.md` instead
  (constitution VI).
- **When `app/main.py` exists**, export the `app` group —
  `python3 "$SRC/tools/practice_kit.py" --export . --include-deferred app`
  — and adapt the pair: empty the module-to-spec table in
  `app/web/spec_registry.py`, set `_MINIMUM_ROUTES` to the routes the app
  registers today, and let `tests/unit/test_spec_coverage.py`'s baseline
  be whatever its first run reports. From then on a routing module added
  without a spec fails the gate, which is its job.
- **Before the app's first page**, export the `theme` group —
  `--include-deferred theme`. It builds `app/web/templates/base.html`
  from the source: the no-flash theme script, both `:root` token blocks
  and every component class, then a `body.ui-v2` (the scope the v2
  primitives are written under) carrying the light/dark toggle and the
  script that writes the saved choice, and a `content` block. The new
  project starts from this design system with both themes reachable
  from the page. It will not overwrite a `base.html` that exists; if you
  already wrote one, export the group into a scratch directory and merge
  its head and body by hand. Rename the title, the favicon and the
  storage key (`rrw-theme`, in both scripts). Then regenerate the two
  pages and commit them — `python3 tools/theme_preview.gen.py` and
  `python3 tools/theme_customizer.gen.py` — because
  `tests/unit/test_generated_tools_are_current.py` compares the committed
  page to a fresh run. Of the group's seventeen tests (fourteen in the
  contrast audit, three on the generated pages), sixteen pass as
  exported; the one that does not,
  `test_the_muted_token_absorbed_the_retired_one`, counts a token's uses
  across this project's templates and asserts this project's numbers —
  delete it until you have templates of your own, then re-derive it.
  `spec/color_tokens.md` catalogues the palette you inherited and is
  your catalogue now, but it cites two visual-style specs, an archived
  plan, a known-limitations page and a test that stayed in the source,
  so the path gate goes red again on export: cut those references or
  mark them, as in step 3.
- **Then set the palette**, which is what the customizer is for. Open
  `tools/theme_customizer.html` in a browser (no server); the toolbar
  flips light and dark, and every token is editable with live repaint.
  Design each theme, then **Export JSON** and port its flat `tokens` map
  1:1 into `base.html`'s `:root` and `:root[data-theme="dark"]` blocks.
  Regenerate both pages, run `pytest tests/unit/test_contrast_audit.py`:
  every foreground/background pair the stylesheet forms must clear AA
  (4.5:1) or be recorded, with its reason, in `ACCEPTED_BELOW_AA` in
  `tools/_harness_common.py` — the customizer's Contrast panel lists the
  same pairs, worst first, so a shortfall is visible before the test
  says so. Re-catalogue the changed tokens in `spec/color_tokens.md`.
  The Primitives grid marks any primitive no semantic token reaches;
  retire it or use it, never leave it. The full control set and the
  reasoning behind the panel are in `tools/README.md` under
  `theme_customizer.gen.py`.
- **When a deploy workflow arrives, make it depend on the test job**, not
  merely run after it. The old checklist put this on day one; a kit
  cannot carry a deploy it has not seen, so it is the first thing to
  check when one is written.

## Deliberately not copied

- `rrw_sdd_in_practice.md`, `docs/practice-audit-2026-09-04.md`, the
  assessments, sweeps and `docs/status_history.md` — this project's
  record, read for rationale, never transplanted.
- `spec/` and `app/` — the product, not the practice. `spec_registry.py`
  is the one exception, because it is the gate's mechanism.
- `tools/code_metrics.py` — needs a merge history to measure.
- The two generated theme pages, `tools/theme_preview.html` and
  `tools/theme_customizer.html` — regenerated in the new repository from
  its own `base.html`, never copied (the `theme` group above).
- The `docs/` operational documents — deployment, security posture,
  runbook — each describes an environment the new project has not
  chosen yet.
- Codex review — a GitHub App setting on the repository, not a file;
  enable it from the Codex settings if wanted, and note that it runs on
  every mark-ready.
