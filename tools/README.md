# tools/

Standalone developer / design tooling — scripts that operate *on* the repo
but aren't part of the app or its test suite.

| Path | What it is | Run |
|---|---|---|
| `close_check.py` | Segment close check (read-only) — verifies a plan's `Doc impact` commitments were kept. [Detail](#close_checkpy) | `python3 tools/close_check.py 19A.3` |
| `code_metrics.py` | Duplication + churn metrics (read-only) for `guide/codebase_assessment_*.md`. [Detail](#code_metricspy) | `python3 tools/code_metrics.py` |
| `theme_preview.gen.py` → `theme_preview.html` | Theme-preview harness (read-only) — lifts `app/web/templates/base.html`'s real `<style>` and renders a component gallery + token swatch grid. **Open the HTML in a browser**, no server; the toolbar flips Light / Dark. Regenerate after any `base.html` style change. | `python3 tools/theme_preview.gen.py` |
| `theme_customizer.gen.py` → `theme_customizer.html` | Theme customizer — the same gallery with every colour token editable, live repaint, and the palette's WCAG audit. [Detail](#theme_customizergenpy) | `python3 tools/theme_customizer.gen.py` |
| `theme_variants.gen.py` | Border-contrast report, plus the machinery for a theme variant when one is needed. [Detail](#theme_variantsgenpy) | `python3 tools/theme_variants.gen.py` |
| `css_parity_check.py` | CSS-refactor parity check (read-only) — renders every page carrying a shared CSS shape, reads the computed styles Chromium resolves, and diffs two snapshots. Proves a refactor changed nothing, which the suite cannot: it has no layout engine, so which rule *wins* is invisible to it. **Needs `node` + `playwright` + a Chromium binary, none of them repo dependencies**; set `RRW_NODE_ROOT` and `RRW_CHROMIUM`. Unlike the other entries here it **does** lean on the suite — it drives the normally-skipped `tests/integration/test_css_parity_dump.py` (via `RRW_PARITY_DUMP`) so the pages it samples are real template output. Exit codes follow `close_check.py`: 0 no differences, 1 differences found, 2 could not check. Samples every page at **two viewports** (1280 and 700), since a rule inside a media query is invisible at a width where that query is inactive. Not in CI. | `python3 tools/css_parity_check.py --out /tmp/before` |
| `pace_audit.py` | Pace audit (read-only) — elapsed time per merged slice from merge history, split BEFORE / AFTER a cut PR number; the method behind `rrw_sdd_in_practice.md` §6.4 (2026-09-19). [Detail](#pace_auditpy) | `python3 tools/pace_audit.py --cut 2460` |
| `practice_kit.py` | Practice kit — the manifest of files a new repository inherits from this one, with `--list` (the table `new_project_practices_setup.md` carries) and `--export DEST`. [Detail](#practice_kitpy) | `python3 tools/practice_kit.py --list` |
| `_harness_common.py` | Shared helpers for the two generators — the `base.html` `<style>` lift, the `:root` / `:root[data-theme="dark"]` token parse, the harness CSS, the gallery markup. Not a generator; imported by both. | — |

---

## `close_check.py`

Read-only. Before a plan is archived, it asks whether the `Doc impact`
commitments that plan made were actually kept. It **reports**; a person acts —
nothing is edited or moved, and it asks whether an edit *happened*, never
whether it was *right*. That judgement is `spec-writer`'s at close.

Stdlib + `git`. Exit **0** pass / **1** check failed / **2** usage.

### The checks

| | Checks | Fails? |
|---|---|---|
| **C1** | one manifest shape per file — segment-level or item-level, never both | yes |
| **C2** | every committed path exists and is live | yes |
| **C3** | every un-waived path was modified inside the segment's window | yes |
| **C4** | every waiver carries a reason | yes |
| **C5** | `guide/` paths — counted and listed, never verified (`NOTED`) | **never** |
| **C6** | a `Status` block is present | warns |
| **C7** | a `cites:` names a path its own bullet contains | yes |

**C5 can never fail by design.** A `guide/` commitment is usually a checklist
row no diff can confirm was the right one, and a plan file legitimately moves
into `guide/archive/` when its segment closes — so "exists and is live" is the
wrong question to ask of it.

**C7 exists so the escape cannot outlive its reason.** Two manifests had been
worked around by dropping a path's backticks to hide it from the matcher, which
distorts the prose to satisfy the checker.

### The window

From the commit that **added** the `Doc impact` heading to `HEAD` — or, for an
archived plan, to the commit that archived it. The moment the commitment was
made, not the plan file's first commit, which is often months earlier.

**That start commit counts.** A plan landing its manifest and the doc edit it
names in one commit has kept the commitment in one commit rather than two;
excluding it was `git log A..B` arithmetic rather than a rule, and it had cost 6
of 22 C3 failures across the corpus.

On a **segment-level** manifest — one window spanning every item — a bullet
tagged `(Item n)` is dated from that item's own `## Item n` heading instead, so
a newer item's commitment cannot be satisfied by an older item's edit. Without
this, C3 read a silent `PASS` on 19C with three Item 7 commitments outstanding.

An edit inside the segment window but *before* its item's heading **warns**
rather than fails: items are sometimes logged after their work lands, and
nothing in the timestamps tells that apart from another item's edit. The script
names both readings and a person resolves it — which is why the
definition-of-done line reads *"exits 0; any warning adjudicated"*. **Read the
warnings; the exit code alone does not close the loop.**

### What counts as a commitment

- **`Doc impact` is matched exactly**, so suffixing the heading
  (`## Doc impact — superseded`) retires a manifest without deleting it.
- A **`spec/` or `docs/`** path counts **anywhere** in a bullet, because bullets
  legitimately commit to several specs after the dash — a head-only rule loses
  seven such commitments. A bullet that merely *cites* a path marks it
  `<!-- cites: spec/x.md -->`, comma-separated for several.
- A **root-level document** (`constitution.md`, `CLAUDE.md`), a bare filename
  used as folder shorthand, or a path under `app/`, `tests/`, `tools/`,
  `alembic/`, `.github/` or `.claude/` counts in the **leading position only**.
  Measured across every plan, 3 of the 16 such paths lead their bullet and the
  other 13 are citations naming a code path as the *content* of a spec edit, so
  matching anywhere would invent 13 commitments nobody made.
- Those code paths are **verified** like a `spec/` path rather than merely
  counted like a `guide/` one: they do not legitimately move, so "was this
  edited in the window" is the right question for them.
- A committed **directory** counts (`.github/workflows/`,
  `app/services/assignments/`), so C2 asks whether the path *exists*, not
  whether it is a file.

Until these last rules landed, every such path was silently dropped — including
`tools/README.md`, this file, the only live document describing the check.

### `--archived`

Reports across every archived plan (~11s, always exits 0), reading **every**
`Doc impact` level in each: the segment-level manifest if there is one,
otherwise every item's, each with that item's own window. The corpus baseline is
**259/274 (95%)**. Reading only the top level hid most of the archive's item
manifests and understated the very baseline this flag exists to report, which is
what the extra `git log` calls buy.

`--json` adds a machine-readable copy on stdout.

### `--stale` and the sweep cadence

Answers the other cadence's question. It lists every live `spec/` + `docs/` +
root practice doc by days since last edit, marks the ones untouched since the
last sweep, and with `--since <date>` reports whether a sweep is due — **8
weeks or 500 merges, whichever comes first**. Report-only, exits 0.

Its file set is deliberately wider than the manifest regex: that regex bounds
what a plan may *commit* to, this bounds what a reader must *read*.

**The cadence is reset only by a *corpus* sweep** — one that read `spec/` +
`docs/` + root as a whole. Every dated sweep declares which it is with
`<!-- sweep-scope: corpus -->` or `<!-- sweep-scope: partial -->`; an unmarked
one raises rather than being guessed at, and `guide/sweep_template.md` ships the
marker set to an invalid placeholder so forgetting to choose is loud. Without
the distinction a single-file sweep resets the clock, which runs it from the
wrong event and compounds with every later partial sweep.

**What it cannot check** is a marker set dishonestly — no tool can verify a
declaration against what a person actually read. It removes the accidental case
and leaves the deliberate one to authorship.

**Staleness is a reading prompt, never a finding.** A spec untouched for months
may be perfectly correct, and `spec/blob_storage.md` is a deliberate stub.

---

## `code_metrics.py`

Read-only. The two standard quantitative items for
`guide/codebase_assessment_*.md`. Stdlib + `git` only; ~80s for both metrics,
~2s with `--dup-only`.

**Duplication** is reported as a curve across block sizes (≥6 / 10 / 15 / 25
lines), because a single number is meaningless without it. Read the **≥10** row
as the headline.

**Churn** is the share of deleted lines younger than N days *against the ambient
age of the same files at that moment* — a fast-moving repo makes everything
young, and the raw figure misleads without that baseline. Churn walks the
**full** merge history so the number is deterministic and comparable between
snapshots. `--churn-sample N` is a faster, sample-dependent look for iterating
on the tool and **must not be quoted**.

---

## `theme_customizer.gen.py`

The `theme_preview` gallery with every colour token **editable** and live
repaint. Design a light + dark palette (edit each separately via the toggle),
then **Export JSON** — a coding agent ports its flat `tokens` map 1:1 into
`base.html`'s `:root` blocks. Controls: Load defaults / Re-read `base.html`…
(file-picker) / Save-as named library (`localStorage`) / Delete / Export +
Import JSON.

Design reasoning lives in `guide/archive/theme_customizer.md`; this is Plan A,
manual-editor slice. Seed-and-derive lands later.

### Token inspection reads both directions

Click a preview element for the token that paints it, or click a **primitive**
for every semantic token that resolves to it — listed **per theme**, because
`semL` and `semD` target near-disjoint sets (74 of 80 primitives are reached in
exactly one theme, so an active-theme readout would say "nothing targets this"
for most of them).

Resolution, not direct targeting: a primitive reached only through a coupled
semantic (`--a: var(--b); --b: var(--prim)`) is still in use.

A primitive no semantic reaches **in either theme** shows as a **red chip** in
the Primitives grid — colour only, no badge, since a word in the chip's flow was
wide enough to widen the card; the inspector names the condition in words when
that chip is selected. Recomputed from the live model, so a remap can strand or
rescue one mid-session. Today exactly one primitive is unreferenced,
`--violet-bright`, added deliberately as the marker's live case
(`spec/color_tokens.md`) — *a marker that highlights nothing cannot be seen to
work.* The marker's red is a literal, not a token: diagnostic chrome must not be
editable out of visibility by the palette it reports on.

### Contrast panel — the palette's WCAG audit surface

Lists **every** foreground/background pair the palette forms — 73 today,
grouped by the foreground's cluster, worst first. A ratio under **AA normal
(4.5:1)** is marked: **solid red** for an *open* shortfall, a **dashed edge**
for one recorded as *accepted* (`ACCEPTED_BELOW_AA` — the transient hover dips
whose controls are legible at rest), with live counts per group and overall.

An accepted pair is never hidden, only muted: *a panel that stops showing what
it has excused is how an excuse outlives its reason.* Acceptance is per theme,
since the same pair can be a transient dip in light and an open failure in dark.
The badge keeps its three states (`AA` at 4.5:1 and above, `3:1` between, `✗`
below), so the working floor the tool once gated on stays visible without being
mistaken for compliance. A trailing grey figure gives the ratio **as shipped**
in light, so an edit's effect reads beside its baseline; hover a row for the
token names and which source found the pair.

**The pairs are derived from `base.html`, not listed.**
`hc.collect_contrast_pairs` finds them in rules that set both halves, in
`--x-fg` / `--x-bg` name siblings, in text × surface, and in one hand-kept map
for the two foregrounds no convention predicts. It replaced a hand-kept list of
12 that was missing 62 of the palette's pairs, one of them carrying a live AA
failure — and that list had *also* still named `--text-dim` after the token was
retired. Those are the two ways a hand-kept list decays, a few commits apart.
Eleven of the twelve survive verbatim among the 73; the twelfth paired
`--btn-destructive-fg` with `--surface-page`, an approximation the rule-derived
pair supersedes, and the two resolve identically in both themes anyway.

A pair can be reachable by more than one source (31 of the 73 are); the tooltip
names the first that found it, rules before names before surfaces. That is
provenance, not exclusivity.

`tests/unit/test_contrast_audit.py` calls the same function, enforces the same
set, records the pairs that fall short — and asserts **this generated page**
carries a row for each, so the panel cannot quietly under-report. Flagging is
recomputed in the browser from the live model, so a remap moves it.

### Documents loaded from outside the build are merged, never substituted

A saved library, Revert, or Import JSON is merged **over** the build's defaults.
Replacing lost every token added since the document was written — a library
saved before `--violet-bright` landed re-exported 79 of 80 primitives, and the
gap surfaced only because someone diffed the file. Missing keys keep their
default, the document's keys win, keys the build does not know are kept, and the
status line reports both counts.

---

## `theme_variants.gen.py`

A run reads `base.html` and prints the shipped border's contrast in both themes
plus — while both themes share one border primitive — the best floor any single
value could reach on that hue (`max_shared_floor()`). `--check` suppresses
writing.

That ceiling settled the question: `--slate-dim` reaches 4.286:1 light /
4.312:1 dark against a 4.291:1 ceiling, so there is no better shared value to
find, and beating it needs two per-theme primitives this tool cannot express.

**`VARIANTS` is empty, so a run writes nothing.** Append to it to build a
`{version, primitives, semantic}` document for the customizer's **Import JSON**.

The three `beyond-*` variants and `theme_customizer_beyond.html` are
**retired**: they explored giving inputs and cards their own fill, the route
lost on the numbers (1.238:1 light / 1.145:1 dark), and previewing it needed a
second 2.6 MB customizer carrying two tokens `base.html` deliberately does not
have — which read as a facility rather than a closed experiment. The reasoning
is in prose in `guide/segment_19C_refinements.md` Item 8.

---

## `pace_audit.py`

Read-only. Stdlib + `git`; needs a full history (`git fetch --unshallow
origin main` on a session clone). Reads every merge to `main` since
`--since`, splits them at `--cut` (the first PR number under a changed
rule) and prints, for BEFORE, the last BEFORE stretch from `--recent`,
and AFTER: the within-session merge-to-merge cycle and its split into
turn / in-PR iteration / push-to-merge, the share of PRs carrying a
review-response commit, product and prose-only slices separately, the
cycle by code-size bucket, and code+test lines per hour.

**A gap over three hours is dropped**, so the author's scheduling does
not enter; what remains is the loop between one merge and the next.
`turn` includes the time an instruction took to write and is a ceiling
on build time, not a measure of it. PR-opened → merged needs `--prs`, a
JSONL of `number` / `created_at` / `merged_at` from the GitHub API,
because PR timestamps are not in git.

**Turn splits only where the trailer exists.** A slice whose first commit
carries `Instruction-Received: <UTC>` (`CLAUDE.md` "Where work runs")
has its turn split into *wait* (previous merge → instruction) and *build*
(instruction → first commit); the line prints once three slices carry it.
Fix commits answering a reader or CI do not carry the trailer and are not
read for it.

Written for the 2026-09-19 re-measurement of the reader cadence; the
numbers it produced are in `rrw_sdd_in_practice.md` §6.4. Not in CI.

---

## `practice_kit.py`

Read-only here; writes only into `--export DEST`. `MANIFEST` is the
constant: every file the practice consists of, in four tiers — *verbatim*
(copied, needs at most a project name), *adapt* (copied, with a named edit
the setup document spells out), *skeleton* (generated empty but
well-formed, because this repo's version is its own history) and
*deferred*, in two groups exported on request — `--include-deferred app`
(imports the application) and `--include-deferred theme` (reads
`base.html`; builds a starter `base.html` from this one's head and
stylesheet, with a `body.ui-v2` carrying the theme toggle). Export never
overwrites an existing file; `--force` does. `tests/unit/test_practice_kit.py`
asserts every copied path exists, every skeleton has a generator, the
export lands every entry, the generated `guide/README.md` satisfies the
guide-index gate, and the table in `new_project_practices_setup.md` equals
the manifest — regenerate that table with `--list` when the manifest
changes. Not in CI beyond the suite.
