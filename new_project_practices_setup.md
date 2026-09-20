# New-project practice setup

> **Provenance.** Exported from `<source>` at `<commit>`; step 3 fills both
> slots. Brackets still showing means this is either the original, in
> `philoyhc/review-robin-web`, or a copy whose step 3 was skipped. Once
> filled, diff this file against that commit to see what the source has
> fixed since.

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

If you are the person setting a project up rather than the agent running
it, the next section is the whole of your part.

This replaces the 2026-09-04 checklist of the same name. That version was
read by a person and predated the constitution, the plan skill, the close
check, the pace audit and the doc gates; its five day-one items survive
as steps 1, 3, 5 and 7 below, and the one it dropped is named in step 7.

## Humans: read this first

Steps 1 to 7 are the agent's. This section is yours, and everything in it
is something no agent can do for you.

**Before the session**

1. **Create the new repository on GitHub with an initial commit** — a
   README or a `.gitignore` is enough. An empty repository has no default
   branch, so the first branch an agent pushes silently becomes it, and
   there is nothing to open a pull request against. Unpicking that costs
   a throwaway root commit and a rebase. Measured on the first project
   set up from this kit.
2. **Set the repository up while you are there.** Agents cannot change
   repository settings — default branch, branch protection, installed
   apps — so decide them now. Codex review is one of those settings
   rather than a file; see "Deliberately not copied". Leave branch
   protection off until you have measured the merge policy being broken
   (`CONTRIBUTING.md`).
3. **Attach both repositories to the session**, the new one and the
   source. The kit is copied from the source, never reconstructed, and an
   agent may be refused permission to execute a script out of a checkout
   the session has not attached — step 1 carries the fallback for when
   that happens. A session that can see only the new repository has to
   stop and ask you for the other.
4. **Say "run `new_project_practices_setup.md`".** Steps 1 to 6 are then
   the agent's: export, adapt, add what the kit cannot carry, run the
   gates, commit, push, open a draft pull request.

**While it runs**

There is one case where the agent must stop and ask: the source
repository is not reachable. Everything else it decides and records. Two
things are worth telling it up front rather than correcting afterwards:
whether the project will use Postgres, since without it the workflow and
its merge-policy paragraph are deleted rather than adapted, and any
convention the project has already settled, which belongs in the rewritten
Project conventions.

**Afterwards, and from then on**

- **You merge.** No agent merges and nothing runs unattended
  (`constitution.md` IV). The agent opens drafts; the call is yours.
- **You decide when to wait for the slow CI job.** `CONTRIBUTING.md` sets
  the policy and leaves the gate to you.
- **You verify what the suite cannot see** — layout, rendering,
  in-browser behavior, real authentication — on an environment you can
  open. A change that touches any of those says so in its description
  instead of claiming it was verified.

**The one task in step 7 that is only yours**

Setting the palette. Open `tools/theme_customizer.html` in a browser, no
server needed, design the light and dark themes with live repaint, then
Export JSON and hand it back to be ported into `base.html`. You also
decide whether a contrast shortfall is fixed or shipped. An agent can
measure a contrast ratio; it cannot decide that a color is right.

## 0. Preconditions

- The new repository exists, is cloned, and is the working directory.
  It should carry a first commit — the section above says why. It still
  runs on an empty one, but say so in the first PR body, because the
  branch you push becomes the default. It must not already carry a
  `CLAUDE.md` you were told to keep.
- The source repository `philoyhc/review-robin-web` is reachable — cloned
  beside the new one, or attached to the session. If it is not, **ask**
  for it; the kit is copied from it, not reconstructed.
- `python3` is 3.12 or later and `git` is present. Nothing else is needed
  to run the kit; the gates need the dev install in step 6.

## 1. Export the kit

From the new repository's root, with `SRC` the source checkout:

```bash
git -C "$SRC" rev-parse --short HEAD    # note it down; step 3 asks for it
python3 "$SRC/tools/practice_kit.py" --export .
```

It copies every `verbatim` and `adapt` file in the table below, generates
the skeletons, appends whichever of the seven `.gitignore` harness lines
are missing, and prints one line per entry. The `deferred` rows wait for
step 7: the `app` group imports the application and would fail test
collection in an empty repository; the `theme` group reads `base.html`'s
stylesheet and is exported together with a starter `base.html` the kit
builds. It never overwrites a file that exists; `--force` does. `--list`
prints the table without copying. The table is derived from the tool's manifest and a test in the
source repository keeps them identical, so if they disagree the tool is
right.

If the sandbox refuses to run a script out of the source checkout — an
agent session may only execute code from a repository attached to it —
reproduce the export by hand instead of skipping it. The export is a
manifest-driven copy: `MANIFEST` names every row, `SKELETONS` holds the
generated texts verbatim, and the seven `.gitignore` harness lines are
appended if missing. Then run `--list` from the new tree and check it
against the table below. Either way, record the source's commit before you
move on. If the source is attached to the session rather than cloned and
`git rev-parse` is not available, write down what you do have — the
repository and the date — and say in the Provenance line that it is not a
commit.

| Path | Tier | Needs | Note |
|---|---|---|---|
| `CLAUDE.md` | adapt | — | rewrite Project conventions + Architecture + Where to look; keep Where work runs; cp to AGENTS.md |
| `constitution.md` | adapt | — | keep the six articles; drop the dated annotations; re-point 'derived from' |
| `CONTRIBUTING.md` | adapt | — | fill the merge-policy paragraph's <slow job> and <paths> for the new CI |
| `.gitignore` | skeleton | — | the harness lines only — .claude/* negations plus the hook's build products; appended if absent |
| `.claude/agents/diff-reviewer.md` | adapt | — | project name in line 1, check 4's seams (routes_operator/_shared.py, base.html), the Azure dev slot in the last paragraph |
| `.claude/agents/spec-writer.md` | adapt | — | cites this project's specs and close procedure; re-point once your spec/ has a second file |
| `.claude/skills/segment-plan/SKILL.md` | verbatim | — | the plan / item / close procedure |
| `.claude/hooks/session-start.sh` | adapt | — | builds the 3.12 venv the pre-PR gate needs; retarget the node-warning comment at your own JS-parsing test |
| `.claude/settings.json` | verbatim | — | registers the SessionStart hook; project-relative, so it needs no edit |
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
| `new_project_practices_setup.md` | adapt | — | the procedure; set the Provenance line, and mark the paths that stay in the source |

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
  name; keep the upgrade / downgrade-base / upgrade round-trip, and the
  `pytest` step that runs the whole suite against that server — it is
  what makes the SQLite default safe to keep (step 4). An empty tree has
  no chain to round-trip and the job goes red on the first PR, so guard
  the two Alembic steps on `alembic.ini` existing: the job is green until
  the first migration and binds from it on. Assert the round-trip's
  *reverse* direction too, between `downgrade base` and the second
  `upgrade head`: with `IF NOT EXISTS` up and `IF EXISTS` down, a
  downgrade that dropped nothing still exits 0.
- **`tests/unit/test_doc_references.py`** is verbatim and is the first
  gate that will go red, on purpose: it resolves every backticked repo
  path in live prose, and the kit ships prose that points at files that
  stayed in the source. Expect around 130 dangling pointers on a first
  export, from five places: every `CLAUDE.md` section you have not
  rewritten yet, `CONTRIBUTING.md`'s pointer to the practice audit,
  `spec/README.md`'s pointer to the route registry, this document's
  "Deliberately not copied" section, and — much the largest group — this
  document's own kit table and step 7 prose, whose `deferred` rows name
  the `app/` and theme files no new tree holds before step 7. Fix the
  ones that should point at something of yours; mark the deliberate ones
  with the test's inline escape, the `path-ref-ok` HTML comment, on the
  line (the test's docstring shows it). Around forty markers is normal
  and most of them land in this document. Leave them accurate rather
  than tidy: the same test fails a marker whose path has come to exist,
  so step 7 will name each one to drop as it lands the file it covered.
  That red-then-green is the gate's first proof that it runs.
  `tests/unit/test_doc_conventions.py` is **not** copied: its checks
  derive from this app's constants and stylesheet, and it is the
  template for step 7.
- **Deleting a kit file** — `ci-postgres.yml` when there is no Postgres,
  say — also deletes its row from `MANIFEST` in `tools/practice_kit.py`
  and replaces the table in this document with `--list` output, or
  `tests/unit/test_practice_kit.py` fails on the missing path and then
  on the table. `--list` renders the manifest notes as they are, so a
  regenerated table drops any `path-ref-ok` markers the old one carried
  in its Note cells — the path gate names them, but re-add them rather
  than wondering.
- **`app/web/spec_registry.py`** with **`tests/unit/test_spec_coverage.py`.**
  Empty the module-to-spec table, set `_MINIMUM_ROUTES` to the number of
  routes the new app registers today, and let the baseline set of pending
  modules be whatever the first run reports. The gate then fails on the
  first routing module added without a spec, which is its job.
- **`tools/README.md`.** Delete the rows and sections for tools that were
  not copied. The kit's own row stays.
- **`new_project_practices_setup.md`.** Fill the Provenance blockquote's
  two slots with the source and the commit step 1 had you note down.
  Nothing checks it, deliberately, so an unfilled one survives to the
  next reader, who then cannot tell which version of the procedure this
  project inherited.

## 4. Add what the kit cannot carry

- `pyproject.toml`: a `dev` extra with `pytest`, `pytest-xdist`, `httpx`
  and `ruff`, and `[tool.ruff]` with `line-length = 100` and
  `target-version = "py312"`. The workflows and the gates assume these.
- The two-dialect test arrangement, below, if the project has Postgres.
  The kit's own tests do not need a database, so nothing in it forces
  this; write it anyway. A project that deleted `ci-postgres.yml` in step
  3 has one dialect and skips the arrangement — but still owes traps 3
  and 4, which are properties of SQLite rather than of running two
  dialects.
- `README.md`: one paragraph pointing at `CLAUDE.md` and `constitution.md`.

### The two-dialect test arrangement

Three files, and six traps that are each silent until something real
depends on them.

**The shape.** One database URL in the settings module, `DATABASE_URL`
winning and local SQLite as the fallback. One engine builder that every
path calls — the app, `alembic/env.py` and the conftest — so what SQLite
needs is applied once rather than remembered three times. Then a
session-scoped `engine` fixture in `tests/conftest.py` — and **the
suite resolves its own URL, in this order**: `TEST_DATABASE_URL`, then
`DATABASE_URL`, then an in-memory default of its own. Not the settings
URL: with `DATABASE_URL` unset that is the application's *file-backed*
fallback, so the suite would build and drop schema in the developer's
own database rather than in memory. Having resolved it, write it back to
the settings object, so a no-argument engine built anywhere in the app
reaches the database the fixtures built and not the file.

The fixture then forks on the URL: in-memory SQLite builds its schema
from `Base.metadata.create_all`, and Postgres applies the full Alembic
chain.
`.github/workflows/ci-postgres.yml` runs the same suite on the second,
so the migration chain and dialect divergence are covered on every PR
without either costing the default run.

**Land it before the first model, not with it.** The first project built
from this kit deferred the conftest to "with the first model" and had to
bring it forward — which left that slice writing fixtures and a model at
once, and meant six defects were found in the harness by readers rather
than by the model that would have tripped over them.

**The traps**, each measured on a real Postgres and a real SQLite, with
the symptom it produces:

1. **SQLite does not ignore a schema-qualified name.** It reads one as
   an attached database: `sqlite3.OperationalError: unknown database
   core`. Any project whose models declare a schema needs a
   `schema_translate_map` collapsing them to `None` on that dialect only
   — defined in one module the conftest *and* the Alembic environment
   import, never copied into both.
2. **Two schemas then cannot share a table name.** Translated to one
   namespace, `leave.approval_decision` and `events.approval_decision`
   both compile to `approval_decision`: `table approval_decision already
   exists`. Attaching one database per schema preserves the names and
   makes SQLAlchemy's SQLite dialect **silently omit every cross-schema
   foreign key from the DDL** — the orphan insert is accepted with
   `PRAGMA foreign_keys=ON`. Neither is free. Decide which before
   designing such a pair, and gate the collision meanwhile so it fails
   at design time rather than inside a fixture.
3. **`check_same_thread=False` does not share an in-memory database.**
   SQLAlchemy picks `SingletonThreadPool` for `:memory:`, so a second
   thread — a `TestClient`, a background task — opens a *new, empty* one
   and finds no tables. `StaticPool` is what shares it.
4. **SQLite ships foreign keys off.** Without `PRAGMA foreign_keys=ON`
   on every connection, an `ON DELETE CASCADE` does nothing. Note which
   test that fools, because it is not the obvious one: a test asserting
   the child row is gone **fails**, loudly. What passes is every test
   that deletes a parent and asserts only that the *parent* is gone —
   while the database quietly accumulates orphans, and an integrity
   constraint the schema declares is enforced nowhere. Measured both
   ways.
5. **Offline `--sql` cannot translate.** `schema_translate_map` is a
   connection execution option and offline mode has no connection;
   Alembic has no equivalent. So `alembic upgrade head --sql` against
   SQLite prints DDL that dialect cannot run, with no error. Refuse it
   there and name the fix.
6. **The Postgres path is destructive, and single-process.** It drops
   and rebuilds the schema, so each xdist worker would drop it out from
   under the others — refuse `-n` there. And once a Postgres
   `DATABASE_URL` is exported (trap 5 makes that the normal local
   state), the next bare `pytest` in that shell reaches the drop; refuse
   a non-local host unless a separate `TEST_DATABASE_URL` named it.

Only 1 and 2 need more than one schema. **3 to 6 apply to any project on
this stack**, including a single-schema one — including this one, whose
`tests/conftest.py` builds its in-memory engine on `SingletonThreadPool`.
Trap 3 is latent rather than biting there: `TestClient` does run the app
in another thread, but the app never opens its own connection, because
`tests/integration/conftest.py` overrides `get_db` with a session made in
the test thread. Drop that override and the trap is live. Which is the
point — these are all arrangements that work until the day something
ordinary changes.

Pin each property with a **pair** of tests: the helper's engine against a
plain one. A single assertion that the engine behaves correctly passes
just as well when the helper stopped being called.

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

Two tests skip themselves rather than pass, and that is expected.
`test_theme_group_builds_a_starter_base_template` and
`test_a_kit_built_project_can_be_the_source_for_the_next`, both in
`tests/unit/test_practice_kit.py`, export the theme group by slicing
`app/web/templates/base.html`, which step 7 creates. The kit's own guard
keys on the group having landed rather than on that one file, so they
stay skipped if you write your own template first — the hand-merge step 7
describes. Step 7 turns them back on; leave them alone until then.

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
  Design each theme, then **Export JSON**. The download is
  `{ primitives, semantic: { light, dark } }`: port `primitives` into the
  primitives block of `base.html`'s `:root`, `semantic.light` into the
  semantic block that follows it, and `semantic.dark` into
  `:root[data-theme="dark"]`, one token per line, 1:1. Regenerate both
  pages, run `pytest tests/unit/test_contrast_audit.py`: every
  foreground/background pair the stylesheet forms must clear AA (4.5:1),
  and a pair that does not is fixed, or recorded in one of two places.
  `ACCEPTED_BELOW_AA` in `tools/_harness_common.py` is for a transient
  dip only — a hover state whose `resting_bg` pair clears AA — and the
  test checks that resting pair, so an entry without one fails. A
  genuine shortfall you decide to ship goes in `OPEN_SHORTFALLS` in the
  test, with its measured ratio and a known-limitations entry. The
  customizer's Contrast panel lists the same pairs, worst first, so a
  shortfall is visible before the test says so. Re-catalogue the changed
  tokens in `spec/color_tokens.md`.
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
