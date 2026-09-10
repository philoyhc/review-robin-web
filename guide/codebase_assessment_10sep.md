# Codebase assessment — 2026-09-10

**As of:** the two-segment refinement arc closing. Segments **19I** (roster
search and row deletion) and **19H** (additional refinements) both closed and
archived today. **Segment 19J** opened the same day for this document's own
§8 and closed all three of its items before the day was out; it is the only
live segment.

> **Updated 2026-09-10, end of day** to reflect Segment 19J — **tables and SHA
> re-taken together**, per the rule that a stale SHA silently decouples the
> numbers from the tree. 19J touched **no `app/` code**, so production,
> templates and migrations are unmoved and every §2 production figure below
> stands as first written; `docs` and `tooling` moved, and the window grew from
> 67 merges to 73. The sections 19J's items settle carry their own struck-and-
> corrected notes rather than being silently rewritten: §3's ⚠ row (19J.1), §5's
> spec entry (19J.1) and `close_check` entry (19J.3), §7's projection term
> (19J.2), §9's watchlist tail (19J.3), and §8's three moves.

Since the 08sep snapshot:

- **Segment 19I — roster search and row deletion** (PRs #2230 → #2276,
  2026-09-09 → 09-10) — thirteen items, twelve closed and one withdrawn. The
  four Setup roster pages plus Assignments gained a rationalized filter strip,
  tag-aware search, scaffold-first row deletion, one shared preview-count
  sentence across **seven** pages, and a column-visibility facility extracted
  to one `base.html` primitive and rolled onto Invitations and Responses.
- **Segment 19H — additional refinements** (PRs #2219 → #2278, 2026-09-08 →
  09-10) — seven items. Two stale-pill / untrue-warning repairs, the Guide's
  screencaps as light/dark pairs, the missing `Cache-Control` header, pills
  naming the wrong columns, and the roster lock card brought onto the same
  predicate as the controls it explains.

All shipped 2026-09-08 → 2026-09-10 (73 merge commits, 116 non-merge, over
3 calendar days, PRs #2215 → #2285). Numbers taken on
`claude/read-only-repo-s3r5u5` at `5df1b77c`. Single-author project with an agent in the loop; the human author
runs no local Python, so the agent's container and CI are the only gates before
the Azure dev slot.

A standalone snapshot; `guide/archive/codebase_assessment_08sep.md` archives alongside
it. Authoritative ship-state lives in `docs/status.md`; the functional spec
audited against is `spec/rrw_functional_spec.md` plus the per-surface specs.

---

## 1. What's in the box

An operator builds a review session, uploads three rosters, defines instruments
in three bands, generates assignments from a rule, validates, activates,
watches responses arrive, and extracts shaped data — a server-rendered FastAPI
+ Jinja monolith over SQLAlchemy 2.x, with Azure Easy Auth supplying identity
and a strict route → service → model split plus a view-adapter seam.

**New since the 08sep snapshot:** no new surface. This window added **one**
production module (`app/web/views/_preview_counts.py`, 88 LOC) and two template
partials, and spent the rest making surfaces that already existed behave the
way their specs said they did. That is a change of character worth stating
plainly: 08sep's window was 59% new modules, this one is 5%.

What changed inside the existing surfaces:

- **The four roster Setup pages** (Reviewers / Reviewees / Relationships /
  Observers) — `search_by` retired in favour of one search matching names by
  substring and tags whole-value; `bulk-delete` per page behind a Danger Zone
  that works; row checkboxes, selection controls and the lock card all moved
  onto `is_editable`; the `Show columns:` chips relocated into the preview-table
  card with a **roster-wide** has-data flag; the *Fields with data* card
  retired.
- **Assignments** — brought up to the roster pages' facility: tag-aware search,
  a status filter, typeahead, and an operator-actions card that stopped
  contradicting its own routes.
- **Invitations and Responses** — gained tag columns, show/hide chips, sortable
  headers and tag-aware search, which is what motivated extracting the
  column-visibility JS (duplicated byte-for-byte across four templates) into one
  `base.html` primitive.
- **The Guide** — sixteen screencaps now ship as light/dark pairs, and the
  static mount sends `Cache-Control: no-cache`.

Surfaces unchanged since the prior snapshot: the reviewer `/me/` surface,
reviewee results, observer collation, Rehydrate, extracts, the sys-admin tier,
the email-template editor, light/dark mode and the token system.

---

## 2. Size (LOC)

LOC = physical lines over git-tracked files. Areas are pinned by
`guide/assessment.json` (written 2026-09-04); the classification is unchanged
this window, so every delta below shares its denominator with 08sep.

| Area | Files | LOC | Δ LOC from 08sep |
| --- | --- | --- | --- |
| `docs` | 242 (236 prior) | **141,114** | +14,107 (+11.1%) |
| `tests` | 291 (269 prior) | **99,817** | +6,700 (+7.2%) |
| `production` | 204 (203 prior) | **58,724** | +1,602 (+2.8%) |
| `templates` | 63 (61 prior) | **24,508** | +872 (+3.7%) |
| `tooling` | 14 (9 prior) | **11,781** | +163 (+1.4%) |
| `migrations` | 77 | **6,772** | unchanged |

**`production` is the number to read twice.** It is identical before and after
19J — that segment swept a spec, measured a projection and carved a dev tool,
and touched **not one line under `app/`**. The +1,602 is 19I and 19H's alone.
`tooling` gains 5 files for +163 lines: `tools/close_check.py` became a shim
over a five-module package (19J.3), which is a carve, not growth.

**Migrations unchanged is the number to notice.** Three days, twenty items, two
segments, and **no schema change at all** — every behaviour in this window came
from routes, services, views and templates over the existing model. That is
what a refinement arc should look like from the database's side, and it is the
first window in this series where the migration count held completely still.

### Biggest production files

| LOC | File | Δ |
| --- | --- | --- |
| 1,264 | `app/web/routes_operator/_instruments.py` | +17 |
| 1,106 | `app/services/session_lifecycle.py` | +19 |
| 1,044 | `app/services/instruments/_instrument_crud.py` | unchanged |
| 1,009 | `app/web/views/_instruments.py` | +28 |
| 1,000 | `app/services/csv_imports.py` | unchanged |
| 984 | `app/web/routes_operator/_quick_setup.py` | unchanged |
| 978 | `app/services/audit.py` | +11 |
| 974 | `app/services/responses/_core.py` | unchanged |
| 964 | `app/services/instruments/_response_fields.py` | unchanged |
| 954 | `app/services/validation.py` | unchanged |

**A fifth consecutive flat window at the top.** Five of the ten are
byte-identical to 08sep and the largest single gain is +28. No file crossed a
tripwire, and none is a candidate for a split (§9).

### Where the window's growth landed

Production, +1,602 across 12 files with meaningful change:

| Δ | File | What |
| --- | --- | --- |
| +261 | `app/web/views/_filters.py` | the shared filter-strip adapter, extended to Assignments |
| +150 | `app/web/routes_operator/_operations.py` | Invitations + Responses tag columns, sort, search |
| +132 | `app/services/assignments/_coverage.py` | tag-aware search + status filter |
| +130 | `app/web/routes_operator/_shared.py` | roster context keys, the revert allowlist |
| +129 | `app/services/roster_bulk.py` | bulk delete |
| +117 | `app/web/routes_operator/_assignments.py` | the Assignments strip |
| +88 | `app/web/views/_preview_counts.py` | **the window's one new module** |

**94% of production growth went into existing files**, inverting 08sep's
pattern. This is not drift: the work was making five pages behave alike, and
the natural home for that is the module each page already shares. Two of the
three extractions this window went the other way — `_preview_counts.py` and the
`base.html` column-visibility primitive both *removed* duplication rather than
adding a module beside it.

Templates, +872: `base.html` +228 (the column-visibility primitive, the
`.chip-group` and `.table-scroll` primitives), then the six preview pages at
+63 to +86 each. Two new partials, `_preview_count_line.html` and
`_roster_lock_card.html`, each replacing markup duplicated across four to seven
templates.

Docs, **+14,107**, and the shape is the same at both ends of the day. Of the
first +8,324, **6,654 is two segment plans** (19I at 4,840 lines, 19H at 1,814)
that both archived; live prose grew ~1,100 — `spec/setup_pages.md` +446,
`spec/assignments.md` +201, `spec/lifecycle.md` +136, plus `docs/status.md` and
`guide/todo_master.md`. 19J then added ~5,800 more, again mostly a plan, a
record, and this document's own amendments:
`guide/segment_19J_assessment_moves.md` (824),
`guide/sweep_2026-09-10_rrw_functional_spec.md` (515), and +584 here —
against **+110 net** of live spec prose, which is what fifteen corrections to
`spec/rrw_functional_spec.md` and a rewritten `spec/README.md` row come to once
struck text is counted against added. **The planning artefacts are ~80% of the docs delta at both counts, and
they are historical the moment their segment closes** — which is the intended
shape: plan on the way in, spec on the way out.

That ratio is worth stating plainly rather than as a virtue: **this project
writes roughly eight lines about the work for every line of live prose the work
changes.** Whether that is discipline or overhead is not something the number
settles, and §5 carries it as a weakness rather than a strength.

Tests, +6,700 across 22 new files, all integration or unit tests for this
window's behaviour. The 8 lines 19J added are one comment explaining why a
monkeypatch target moved.

### Package shape

| Package | Files | LOC |
| --- | --- | --- |
| `app/services` | 96 | 31,799 |
| `app/web/routes_operator` | 22 | 11,682 |
| `app/web/views` | 22 | 8,195 |
| `app/web/routes_reviewer` | 12 | 2,561 |
| `app/db/models` | 21 | 1,604 |
| `app/auth` | 3 | 206 |

`app/web/views` — the fourth seam — is now 8,195 LOC over 22 files, averaging
373. It is the fastest-growing package proportionally this window (+261 in one
file), which is the seam working as designed: filter-strip and preview-count
shaping is view-shape logic and belongs there rather than in a service or a
template.

### Duplication

| Corpus | Files | Code lines | ≥10-line blocks | ≥25-line blocks |
| --- | --- | --- | --- | --- |
| `app/` | 203 | 47,778 | 3,129 (6.5%) | 478 (1.0%) |
| `tests/` | 291 | 80,805 | 12,650 (15.7%) | 3,019 (3.7%) |

Most-duplicated production files, ≥10-line blocks:
`_setup_reviewers.py` 258/518 (**50%**), `_setup_reviewees.py` 258/533 (48%),
`_quick_setup.py` 194/823 (24%), `_instruments.py` 182/1,060 (17%),
`_setup_relationships.py` 178/657 (27%).

The Reviewers/Reviewees pair at ~50% is the standing figure and it is
**structural, not accidental**: the two pages are near-identical by design and
already share `_shared.py` for the parts that can be shared. The residue is
per-entity column lists and per-entity CSV plumbing, which a shared abstraction
would parameterize rather than eliminate. Filed as an observation, not a
proposal — the same reading as 08sep.

### Churn

Deleted Python lines within 14 days of being written: **54,484 of 73,780
(73.8%)**, against a baseline of 74.0% for all lines in those files at that
moment — a ratio of **1.0×**, walked over all 2,269 merges on `origin/main`.
Age-blind: the code is simply young, and recent work is not being specifically
rewritten. Unchanged from 08sep.

---

## 3. Functional-spec compliance

Rows are checked against code, not against the specs' self-description.
`tests/unit/test_spec_coverage.py` continues to assert set equality between the
live route table and `SPEC_COVERAGE` ∪ `INFRASTRUCTURE_MODULES` — **29 mapped
modules over 22 distinct spec paths, plus 3 infrastructure modules (32
first-party routing modules)**, identical to 08sep, because no new routing
module landed this window.

**Four rows changed.** Three are refinements of shipped rows; one is a new ⚠.

| Functional area | Spec | Code status |
| --- | --- | --- |
| Session lifecycle (5 live states) | `spec/lifecycle.md` | ✓ shipped — `app/services/session_lifecycle.py` |
| Sessions lobby + Session Home | `spec/sessions_overview.md`, `spec/session_home.md` | ✓ shipped |
| Quick Setup card | `spec/quick_setup_card_spec.md` | ✓ shipped — `_quick_setup.py` |
| **Setup pages (5)** | **`spec/setup_pages.md`** | **✓ shipped; the four roster pages' filter strip, row deletion, preview-count line and column chips all landed 2026-09-09/10 (19I Items 1–4, 10–12)** |
| **Lifecycle gating on the roster pages** | **`spec/lifecycle.md` §5, `spec/setup_pages.md`** | **✓ shipped 2026-09-10 (19I.3, 19H.6, 19H.7) — every setup-mutation control *and* the lock card explaining them now answer `is_editable`; the card branches per locked state, `archived` carrying no control** |
| Setup-page guidance disclosure | `spec/setup_pages.md` §"Shared body shape" item 0 | ✓ shipped 2026-09-06 |
| Roster CSV + friendly tag labels | `spec/csv_contracts.md` | ✓ shipped 2026-08-20 |
| CSV template sets (starter + demo) | `spec/csv_contracts.md` | ✓ shipped 2026-09-06 |
| **Assignment engine + Assignments page** | **`spec/assignments.md`** | **✓ shipped; the page's strip brought to the roster standard 2026-09-09 (19I Items 7–9) — tag-aware search, status filter, typeahead** |
| Instruments (Bands 1/2/3) | `spec/instruments.md` | ✓ shipped — `instruments/` (9 modules) |
| Validate page | `spec/validate_page.md` | ✓ shipped — `validation.py` |
| Reviewer surface `/me/` | `spec/reviewer-surface.md` | ✓ shipped — `routes_reviewer/` |
| Reviewee results (3 modes) | `spec/visibility_policy.md`, `spec/participant_model.md` | ✓ shipped; gate tightened 2026-09-08 (19F) |
| Observer collation + cohorts | `spec/participant_model.md` | ✓ shipped |
| **In-app operator Guide** | **`spec/operator_ui_concept.md`, `spec/ui_elements.md`** | **✓ shipped 2026-09-07; screencaps now ship as light/dark pairs (19H.3) and the static mount sends `Cache-Control: no-cache` (19H.4, `spec/architecture.md`)** |
| Session-id enumeration closed | `spec/permissions.md`, `docs/security_posture.md` | ✓ shipped 2026-09-08 (19F PR 1) |
| Visibility-cell integrity | `spec/visibility_policy.md` §3.1 | ✓ shipped 2026-09-08 |
| Extracts + Extract data tab | `spec/csv_contracts.md`, `spec/extract_data.md` | ✓ shipped |
| Rehydrate | `spec/rehydrate.md` | ✓ shipped — `session_rehydrate.py` |
| Audit events + envelope schema | `spec/architecture.md` | ✓ shipped — `EVENT_SCHEMAS` strict gate |
| Sys-admin + three-tier roles | `spec/permissions.md`, `docs/security_posture.md` | ✓ shipped |
| Light/dark mode | `spec/visual_style_rrw.md` | ✓ shipped 2026-08-21 |
| Two-tier semantic colour tokens | `spec/color_tokens.md` | ✓ shipped 2026-08-23 |
| Theme customizer (developer) | `guide/theme_customizer.md` | ✓ v1.1 shipped 2026-09-06 |
| Email template editor | `spec/email_template_editor.md` | ✓ shipped 2026-09-05 |
| **Assignments "Self-reviews card"** | **`spec/rrw_functional_spec.md` §9.7** | **✅ resolved 2026-09-10 (19J.1).** Was ⚠ drift: the spec listed a *session-wide self-reviews-active toggle* card that does not exist. The sweep found the truth is two-layered rather than absent — `review_session.self_reviews_active` **is** real and is read by `_generate.py:346` to seed every self-review pair's `include` at generation, while the operator flips those assignments **per instrument** on the Assignments page. The card bullet is deleted and §9.7 / §10.3 / §5.9 name the real surfaces. **This was the only ⚠ row in the table** |
| Operator theming (in-app tweaker) | `guide/theme_customizer.md` Stretch | ⏸ planned — `guide/deferred_consolidated.md` Part A |
| Email dispatch / invitations | `guide/segment_14B_email_infrastructure.md` | ⛔ blocked — SMTP backend + outbox rows exist, no live dispatch caller. Gated on institutional Azure provisioning |
| Blob storage | `spec/blob_storage.md`, `guide/segment_18Q_blob.md` | ⏸ planned — awaiting institutional storage account |
| Technical-support contact (global) | none — stub in `guide/todo_master.md` | ⏸ planned; unhomed 2026-09-08 |
| Operator button audit §§4–5 | `spec/operator_button_audit.md` | ✓ resolved 2026-09-08 (19G.2) |

**Two claims verified rather than carried forward.** The Assignments
*Search-by* dropdown, which 19I.1 retired on the four roster pages, is **still
live on Assignments** with exactly the `All / Reviewers / Reviewees` options
`spec/rrw_functional_spec.md` §9.7 names — checked against
`session_assignments.html:193` and `_SEARCH_BY_VALUES`, because the same
paragraph carries the drift row above and one wrong sentence in a paragraph is
not evidence about its neighbours. And `Cache-Control: no-cache` is documented
at `spec/architecture.md:121`, so 19H.4's four lines are specced rather than
silent.

**Doc-drift work this window.** Every item close ran `spec-writer` over its
doc-impact files. **Five of 19H's seven items had it find drift the item's own
sweep had missed**, twice including a claim the item had *just written*. 19H.6's
found three at once: a fourth stale passage its own grep could not match (the
pattern read `lock card`, the text read `card lock`), an undeclared spec
carrying the claim in four more places, and its own new sentence overstating the
code — which became **19H.7 and shipped the same day**. That is the close audit
paying for itself, and it is the strongest evidence in this window that the
`spec-writer` step is load-bearing rather than ceremonial.

---

## 4. Strengths

- **The window's growth is consolidation, and the numbers say so.** One new
  production module in three days; two new template partials, each replacing
  markup duplicated across four to seven files; and the two largest extractions
  (`_preview_counts.py`, the `base.html` column-visibility primitive) both
  removed duplication rather than adding a module beside it. 94% of production
  growth landed in existing shared modules because that is where "make five
  pages behave alike" belongs.
- **No schema change at all.** Twenty items over two segments, and `migrations`
  held at 77 files / 6,772 LOC. The model was adequate to everything this
  window wanted.
- **Mutation testing became the default, not the exception.** Every behavioural
  change in 19H.6 and 19H.7 was checked by breaking the code and watching the
  suite fail — the gate back to `is_ready` (28 failures), a revert form on
  `archived` (4), one page rendering another's noun (1), a context losing a key
  (9), a gate that rejects everything (9). The last of those is the one worth
  naming: it proves a *widening* did not become a blanket, which no positive
  test does.
- **The segment shape held under load.** 19H opened with an explicit admission
  rule and close trigger; it took seven items, closed on both triggers at once,
  and the single admission that did not fit the rule (19H.6, found by building
  rather than by using) was **written into that item's Judgment calls** rather
  than waved through. 19C's failure — a standing home with no trigger, nineteen
  days, a plan nobody read — has not recurred in the four segments since.
- **Both indexes are current and were made so deliberately.** `docs/status.md`
  and `guide/todo_master.md` each carry every item of both segments, and the
  19H roadmap entry was rewritten from a two-item stub after it was noticed
  stale. No live segment, no open item, nothing half-recorded.

---

## 5. Weaknesses

- **The first measurement was wrong in four of twenty items, and each would
  have shipped the wrong fix.** 19H.1's plan said one template renders the
  setup-status partial; fifteen do. 19H.4's cache probe was wrong **twice, in
  opposite directions** — first apparently refuting the caching account
  (because heuristic freshness is a fraction of the age since `Last-Modified`
  and the served files were seconds old), then reporting the opposite because
  it sampled `naturalWidth` before a lazy image re-decoded. 19H.5 shipped a
  test for a scenario that **cannot happen**. 19H.6's plan rejected a shared
  partial on a cost estimated from prose rather than from the markup, which
  proved byte-identical across 23 lines but for two tokens. **Cost:** four
  rounds of rework inside items, none escaping to a merged PR. **Plan:** none
  proposed — the failure mode is measurement design, and the mitigation that
  actually worked each time was *measure again, differently*, which is not
  something a check can enforce. Filed, not planned.
- **Negative substring assertions held vacuously seven times in one segment.**
  19I found `"tag-col-3" not in body` matching the page's own
  `col-hidden-tag-3` CSS; `"is-disabled" not in body` matching the `base.html`
  comment *written to explain the retirement being checked*; `"Bravo" not in
  body` matching a search `<datalist>`; and four table slices taken with
  `body.index("</table>")`, which finds the page's **first** close tag and so
  ran backwards. **Cost:** seven assertions that read correctly and tested
  nothing, all found by mutation rather than by review. **Partial mitigation
  shipped:** `tests/integration/test_roster_lock_card.py` introduced a
  depth-counting slice so every assertion about a card is made against ~800
  bytes rather than a 177 KB page. That is one file's answer, not the
  codebase's. **Plan:** none — `docs/unenforced_conventions.md` §1.6 already
  records the class; a lint for it would have to understand what each string
  means.
- ~~**`spec/rrw_functional_spec.md` is the least-audited live spec, and it has
  drifted.** It is described in `spec/README.md` as "aligned with the system as
  of 2026-08-18" — 23 days stale — and it is the canonical entry point for new
  readers.~~ **Amended 2026-09-10, and both halves were wrong.** Segment 19J.1
  measured before sweeping: **nine edits and 1,106 changed lines** since the date
  that index line claims alignment to. The file is neither least-audited nor
  stale. What is true is narrower and worse — every one of those nine edits was
  made by a segment revising **the sections its own work touched**, and none read
  the document through, so **piecemeal currency reads as whole-document
  currency** over an index date no edit ever moves. The sweep proved it from
  inside the file: 19F's reviewee-gate change is described correctly in §10.9 and
  incorrectly in §4.4 and §17, and the correct one is the section 19F PR 6
  happened to open. **Cost, now measured:** 15 findings across 14 sections; 94 of
  108 sections were current. **Closed** — swept, fixed, and `spec/README.md`'s
  hand-kept date replaced by a pointer to the sweep record. The original claim is
  struck rather than deleted because the *class* it named was real; only its
  diagnosis was wrong.
- ~~**`tools/close_check.py` crossed 1,000 LOC** … sharing `REPO`, `_git` and
  `last_touched_ever` and nothing else … a fourth repetition should come with
  either a split or a decision to stop mentioning it.~~ **Closed 2026-09-10 as
  Segment 19J Item 3 — split.** Two corrections to what three snapshots
  recorded. The halves never shared `last_touched_ever`: its only call site is
  inside `check_manifest`. And there were **three** jobs, not two — the
  `--archived` baseline report is a third, though measuring showed it is a
  *driver* over the close check (it calls five of its functions) rather than a
  peer. Genuinely shared: `REPO`, `_git`, `Unresolvable`. That is lower coupling
  than the reason given three times for not splitting, which is what settled
  it. Now a 36-line shim over `close_check/` — `_shared` 37, `_manifest` 683,
  `_archive` 85, `_sweep` 126, `__init__` carrying the reasoning docstring and
  `main`. The invocation string is frozen because every archived plan's
  Definition of done names it.
- **The docs corpus is 141,114 LOC against 58,724 of production — 2.4:1**
  (2.3:1 before 19J, which added ~5,800 docs lines and no production). Two
  segment plans totalling 6,654 lines both archived today, which is the shape
  working. But 19I's plan reached **4,840 lines**, past what a reader holds end
  to end, and its own close record says so. The mitigation that worked was
  closing the segment when its theme ran out rather than when the queue
  emptied. **Plan:** none beyond that precedent; no check can measure whether a
  plan is still readable.

---

## 6. Bugs and regressions

**No known open bugs at `5df1b77c`** — **re-established at the end-of-day
amendment, not carried over from `e0f86bf1`**, because "no known bugs" is a
claim and a moved SHA invalidates the checking behind it. Here is what it rests
on:
both CI tracks green on the merged head of every PR in the window; `ruff check
.` clean; **3,595 passed, 16 skipped** (unchanged across 19J, which added no
tests — its 8 test lines are one explanatory comment); all 16 skips read and attributed (15
Wave 5 legacy-card retirements, one fixture shape — none masking a defect); **0
`xfail` markers** anywhere in `tests/`; **0 `TODO`/`FIXME`/`XXX` comments** in
`app/`; **0 open issues** on the repository; and `docs/known_limitations.md`
reviewed against the window's changes with nothing to add.

**Eight defects were found and fixed in this window**, all by using the app or
by measuring it rather than by a failing test:

- **A finished session could still lose its instruments** (19I.6). The
  Instruments page gated on `not is_ready`, which protected the surface while
  the session was *collecting* and stopped protecting it the moment collection
  **ended** — so on `expired` and `archived` the page rendered live Delete
  buttons, the routes permitted the delete, and the `Instrument` → `assignments`
  → `responses` cascade took **submitted answers** with it. The most serious
  defect in the window by a distance.
- **The roster pages offered controls their routes refused** (19I.3) — row
  checkboxes and a live Delete on `expired`/`archived` behind routes answering
  409.
- **A replace an operator could not make** (19I.5).
- **The has-data chips read the rendered page, not the roster** (19I.12) — so a
  tagged row outside the first 200, or excluded by a filter, made its column
  unreachable. Proved by rendering the same 250-row roster from a `git
  worktree` at `origin/main` and from the branch against one SQLite file.
- **Two setup pills went stale after a reload-free Save** (19H.1).
- **The Lock warning promised edits would be lost** and the code neither
  reverted nor saved them (19H.2).
- **Replaced screencaps never reached a reader** (19H.4) — no `Cache-Control`
  on the static mount.
- **The revert on two roster lock cards landed on Session Home** (19H.6).
  `session_relationships.html` and `session_observers.html` had always posted
  `return_to` slugs the route's allowlist did not contain. Invisible because a
  303 to a real page looks like success; 3,529 tests had not noticed.

**One defect this window created and closed the same day.** 19H.6 put the lock
card on `expired` and `archived`; the friendly-label editor had been gated on
`is_ready` alone since Segment 15A, so the page then rendered a card saying the
roster could not be modified above a live **Save labels** button whose route
answered 303. 19H.7 moved the editor's gate. Worth recording as a class: **a
gate nobody questions stays invisible until something adjacent starts asserting
its opposite.**

---

## 7. Estimated size upon completion

Current: **58,724** production, **24,508** templates, **99,817** tests,
**11,781** tooling.

| Remaining work | Production LOC | Templates | Depends on |
| --- | --- | --- | --- |
| Segment 14B — email dispatch, reminders, invitations | +900–1,400 | +200–400 | institutional Azure provisioning |
| Segment 20 — operator polish + documentation | +200–500 | +300–600 | institutional Azure deployment concluded |
| Blob storage (18Q) seam + first consumers | +400–700 | +50–150 | institutional storage account |
| Operator theming (Stretch) | +150–300 | +100–200 | customizer editor core (shipped) |
| Technical-support contact (global) | +30–60 | +20–50 | nothing (unblocked) |

**Projected feature-complete v1: ~60.4–61.7k production, ~25.2–25.9k
templates.**

**Reconcile against 08sep — and the reconciliation is the finding.** That
snapshot projected **~58.8–60.1k production**. Production is now **58,724**,
inside that range, with **all five work items still outstanding and no new
scope discovered**. This is the *second consecutive window* where the projection
was overtaken by growth that was not feature work: 08sep said the same thing
about 05sep, attributing it to 19E's surface arriving unmodelled. This window
has no such excuse — it shipped **one new module** and still added 1,602
production lines.

~~The honest reading is that **the projection method models remaining features
and does not model refinement** … a refinement allowance of roughly +1.5k per
active week is the missing term. The next snapshot should either carry that
allowance or record why it did not.~~

**Measured 2026-09-10 as Segment 19J Item 2, and the answer is that there is
no term to carry.** That paragraph asserted a figure under a skill whose first
rule is that every number comes from a command — the one number in this
document reasoned rather than computed. Computed now, over the five deltas the
six sidecars support:

| window | class | Δ production | merges | PRs | non-merge commits | days |
|---|---|---:|---:|---:|---:|---:|
| 17aug→19aug | refinement | +229 | 26 | 26 | 28 | 1 |
| 19aug→04sep | refinement | +110 | 91 | 91 | 108 | 16 |
| 04sep→05sep | refinement | +200 | 23 | 23 | 31 | 1 |
| 05sep→08sep | **feature** | +1,418 | 98 | 96 | 136 | 3 |
| 08sep→10sep | refinement | +1,602 | 73 | 71 | 116 | 2 |

Windows are classified by the plan's own test — did the window's segments ship
a new route or a new page — applied mechanically rather than by recollection:
`git diff --name-status <since>..<head>` for files added under
`app/web/routes*` and `app/web/templates/*.html`. Exactly one window qualifies:
05sep→08sep added `routes_guide.py`, `routes_templates.py` and `guide.html`.
The two templates added in the last window are partials (`_preview_count_line`,
`_roster_lock_card`), not pages.

**No unit stabilises the rate.** Across the four refinement windows:

| unit | min | max | spread |
|---|---:|---:|---:|
| per merge | 1.2 | 21.9 | **18×** |
| per PR | 1.2 | 22.6 | **19×** |
| per non-merge commit | 1.0 | 13.8 | **14×** |
| per production-touching commit | 4.1 | 66.7 | **16×** |
| per calendar day | 6.9 | 801 | **117×** |
| **per active week — the asserted unit** | **48** | **5,607** | **117×** |

*(Re-taken with the window at `5df1b77c`. The end-of-day amendment extended
the last window from 67 merges to 73, so its per-merge and per-PR rates fell
from 23.9 and 24.6 — an instance of the same hazard the header note names:
re-taking a window silently changes every rate derived from it, and the
arithmetic has to be re-run rather than assumed to survive. **Every conclusion
does survive**; the spreads move by at most two points. `Δ production` is
unchanged because 19J touched no `app/` code.)*

The asserted 1,500 sits near the median (1,603) and inside a range spanning
117×, which is the definition of a figure that cannot carry a projection.

**Two things the measurement corrected, beyond the number.**

1. **The feature/refinement split does not explain the variance**, and it was
   the fix this section proposed. The feature window is *mid-range* on every
   unit (14.5 per merge, against 1.2–21.9 for refinement windows), and the
   largest window in the set is a refinement window. Sorting windows by kind
   does not sort them by growth.
2. **Net production LOC is a residual, which is why it is unstable.** Gross
   production churn against net growth, same five windows: 1,736→229 (0.13),
   1,754→110 (**0.06**), 224→200 (**0.89**), 3,342→1,418 (0.42),
   4,476→1,602 (0.36). A window that rewrites in place and a window that adds
   look nothing alike, and the projection is built on the difference of two
   numbers an order of magnitude larger than it.

**What §7 does instead.** The per-item table above stays, and it is a
**floor**: it models the work that has been named and nothing else. There is no
allowance line, because a rate that varies 117× is not an allowance — it is a
statement that the next window could add 100 lines or 1,600 and history does
not distinguish the cases in advance. Future snapshots should reconcile against
the floor and **say by how much it was overtaken**, which is a measurement, in
place of projecting a total that pretends to model the overtaking. Two
consecutive snapshots were overtaken; a third that is overtaken is not a
surprise to be explained away but the expected result of projecting named work
only.

**The open question in the plan — whether this belongs in the
`codebase-assessment` skill — is answered no.** The mechanism generalises, but
the skill lives outside this repository and changing it is the author's call,
not a side effect of an item that measured one project's five windows.

Nothing was cut. Excludes anything past v1.

---

## 8. Bottom line

Three days, two segments, twenty items, and **not one new user-facing surface**
— this was a window spent making five pages that had grown apart behave alike,
and making the lock cards that explain them tell the truth. The structural
numbers are unusually good: no schema change, a fifth flat window at the top of
the biggest-file table, one new production module, and two extractions that
each removed more duplication than they added.

The thread worth naming is **the first measurement is often wrong, and the
practice has started to assume it.** Four items this window would have shipped
the wrong fix on their first measurement — a blast radius off by fourteen
templates, a cache probe wrong twice in opposite directions, a test for an
impossible scenario, a cost estimated from prose instead of markup. None
escaped to a merged PR, and the reason is not review: it is that measuring
again, differently, has become the default move, and mutation testing became
routine rather than exceptional. The corollary is that **an assertion is only as
strong as the string it matches** — seven held vacuously in 19I alone, each
found by breaking the code rather than by reading the test.

The close audit earned its keep more visibly than in any prior window: five of
19H's seven items had `spec-writer` find drift their own sweep had missed, and
19H.6's audit found the sentence that became 19H.7 and shipped the same day.

**Recommended next moves.**

1. ~~**Sweep `spec/rrw_functional_spec.md` against the code.**~~ **Done
   2026-09-10 as Segment 19J.1** (`guide/sweep_2026-09-10_rrw_functional_spec.md`).
   15 findings, 14 sections, all fixed; the ⚠ row in §3 closes. See the amended
   §5 entry for what the measurement corrected about this move's own premise.
2. ~~**Carry the refinement allowance into the next projection, or refute it.**~~
   **Refuted 2026-09-10 as Segment 19J.2.** There is no term: every candidate
   unit spreads 14× to 117× across the four refinement windows, and the
   feature/refinement split this move proposed as the model **does not explain
   the variance** — the feature window is mid-range on every unit and the
   largest window is a refinement window. §7 carries the arithmetic and now
   states a floor instead of a projection.
3. ~~**Decide `tools/close_check.py`.**~~ **Split 2026-09-10 as Segment
   19J.3** — into `_shared` / `_manifest` / `_archive` / `_sweep` under a
   36-line shim that freezes the invocation string, with all 22 CLI output
   streams byte-identical. The coupling three snapshots declined to act on was
   three names, and one of the three "jobs" turned out to be a driver over
   another rather than a peer.

**All three moves closed the day they were recommended**, which is not a
boast: it is the argument for capping the list at three. A ranked backlog
would still be a backlog.

**What the next snapshot should recommend instead** is left deliberately
empty here. Three moves were named, three were done, and the findings they
produced (below, and in `guide/segment_19J_assessment_moves.md`) are the
input to the next snapshot's §8 — not to this one's.

---

## 9. Proposed file splits — watchlist

**No split is queued, and the top of the table is flat for a fifth consecutive
window.**

- **`app/web/routes_operator/_instruments.py` (1,264 LOC, +17).** Fifth flat
  window; still below the 17aug high of 1,317. The seam if it grows: carve the
  `/save` payload-parsing blocks into a `_save.py` sibling, leaving the thin
  route in place. Revisit past ~1,400 — **136 LOC away**.
- **`app/services/session_lifecycle.py` (1,106 LOC, +19).** Still no natural
  seam; the state machine is cohesive and splitting it would scatter the
  transition table. **Now 94 LOC from its ~1,200 tripwire** — the first entry on
  this list to come within 150, which is the distance at which the prior
  snapshot said none was. Watch actively; do not plan.
- **`app/services/instruments/_instrument_crud.py` (1,044 LOC, unchanged).**
  Three concerns in one module (lifecycle, group/unit-of-review,
  column-widths); past ~1,200 the column-widths helpers are the cleanest carve.
  156 LOC away.

**Watchlist tripwire: ~1,400 for `_instruments.py`, ~1,200 for the other two.**
One is now inside 150 LOC of its tripwire, which was not true at 08sep.

`tools/close_check.py` was **1,000 LOC (+137)** — **split 2026-09-10** (19J.3).
The decision this section called overdue was taken, and the two costs it
produced are recorded in the item's `Status`: the carve broke a
single-patch-point test seam (`from X import NAME` binds a copy per module),
and it created a `.pyc` cache a single-file script never had — which served
stale code within twenty minutes of existing, because Python's
`(mtime, size)` invalidation cannot see a same-size edit inside one
filesystem second.
