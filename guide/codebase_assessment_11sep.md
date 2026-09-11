# Codebase assessment — 2026-09-11

**As of** Segment 19J closed and archived at **ten items**, all closed — the
segment that opened for the 10sep snapshot's three recommended moves and
finished as a seven-item refinement arc on the operator's roster tables. The
row pager it rebuilt is the one surface a reader should picture when dating
this snapshot: on 2026-09-10 a roster page had no pager at all, and on
2026-09-11 it has one that reaches any page in a single move.

**Since the prior snapshot** (2026-09-10, PRs #2286–#2312, 27 merges):

- **19J.4 — navigation busy indicator** (#2287), built on 19J.2's benchmark.
- **19J.5 — row pagination on all seven roster-bearing tables** (#2288–#2292),
  four rungs, with the Assignments pair sort moved into SQL.
- **19J.6 — session-nav hover standardised** (#2293–#2294).
- **19J.7 — pills rationalized; an accent edge now means "you can act on this"**
  (#2295–#2298).
- **19J.8 / the in-place-swap assessment / 19J.9 — the pager becomes navigable**
  (#2299–#2310): a landing anchor, a measured decision *not* to swap the table
  in place, then a five-cell cluster replacing the range strip.
- **19J.10 and the close** (#2311–#2312): what the reserved shade's scope
  actually is, then the segment archived.

**Numbers taken at `7f4b3d42`** on `main`: 27 merge commits, 42 non-merge
commits, 2026-09-10 → 2026-09-11 (2 calendar days). Counting is physical lines
over git-tracked files, areas fixed by the committed `guide/assessment.json`,
so every delta below shares a denominator with the 10sep snapshot.

**This document stands alone.** It supersedes and archives alongside
`guide/archive/codebase_assessment_10sep.md`. Authority for ship state is
`docs/status.md`; the functional spec audited against is
`spec/rrw_functional_spec.md` plus the per-surface specs named in §3.

**Development context**, because it makes the cadence legible: one author
directing AI agents, no local dev loop (no Python, alembic or database on the
author's machine — the agent's container is the pre-PR gate and the Azure dev
slot is where UI is verified), pre-deployment, institutional Azure provisioning
outstanding. Twenty-seven merges in two days is one person's working day here,
not a team's sprint.

---

## 1. What's in the box

A server-rendered FastAPI + Jinja monolith for running structured peer review.
An **operator** creates a session, uploads rosters of **reviewers** and
**reviewees** (optionally **relationships** and **observers**), builds one or
more **instruments** — the review form, its response fields, and the rule
deciding who reviews whom — then generates **assignments** from those rules,
validates the setup, previews what each reviewer will see, sends
**invitations**, and moves the session through a five-state **lifecycle**.
Reviewers fill in their assigned forms at `/me/`; reviewees see their own
results and observers see cohort **collations**, each gated by a
three-way **visibility policy** that resolves per audience and per phase.
Everything mutating writes an **audit event** against a validated envelope
schema, and the whole set can be **extracted** to CSV or **rehydrated** into a
fresh session.

**New since the prior snapshot.**

- **A navigation busy indicator, once in the chrome** (19J.4, #2287). One 3px
  indeterminate bar plus a `role="status"` region in `base.html`, armed ~200 ms
  after a same-origin link click or form submit and cleared on `pageshow`;
  inherited by all 34 templates with no per-page markup. Built because
  benchmarking found Invitations and Responses are N+1 — **40,433 and 80,432
  queries at 200×200** — and the indicator is explicitly *not* that fix, which
  the plan records so the two are never confused. The build corrected its own
  blast radius: a link returning `Content-Disposition: attachment` never
  replaces the page, so twelve such anchors across five templates now carry the
  `download` attribute the script reads, with a unit test scanning every
  template so the thirteenth cannot ship without it.
- **Row pagination on all seven roster-bearing tables** (19J.5, #2288–#2292).
  `app/web/views/_pager.py` (new, 122 LOC) turns the old 200-row cap into a page
  size; `?offset=` clamps rather than 404s; `_shared._setup_row_window` is the
  one implementation the four Setup pages share. Editing a row off the current
  page now lands the operator on that row's page. **The Assignments sort moved
  into SQL** (`_coverage.py`, +195 — the window's largest production change),
  and needed an explicit `COLLATE "C"`: measured on Postgres 16, a locale-aware
  collation orders seven test names differently from the Python sort the app had
  always used, and Azure Postgres commonly is locale-aware. A dialect-compilation
  guard asserts the collation is emitted whatever locale a server carries,
  because the SQLite suite is structurally blind to that class of bug.
- **The accent shade reserved for things that act** (19J.7, #2295–#2298). One
  rounded-pill vocabulary had served two jobs — stating a fact and offering a
  click — with `cursor: pointer` the only separator, which is invisible until
  the pointer is on it, absent on touch, and absent from every screenshot. Now
  every chip that acts carries an accent **edge**, `--lifecycle-validated-fg`
  is off the reserved pair, and `tests/unit/test_reserved_shade.py` resolves
  tokens (not class names) and fails if anything static reaches it.
- **The pager becomes navigable** (19J.8 → 19J.9, #2299–#2310). A page turn
  first gained a `#<noun>-table-card` fragment so it lands on the table rather
  than the document top. Then the range strip was replaced outright: its reach
  was **two pages per click whatever the roster size**, so crossing a roster
  cost a number of page loads linear in its length — 5 clicks to row 2,400 of
  5,861, **50 to the middle of a 40,000-row table**. The replacement is
  `operator/partials/_pager_cluster.html`: `«` first, `‹` back, a `<details>`
  range menu, `›` forward, `»` last. Every cell is an anchor, so the pager needs
  no script to navigate; one delegated `document` listener closes the menu.
- **In-place page turns assessed and declined** (#2302, #2303). A measured
  assessment (`guide/inplace_pagination_assessment.md`) rather than a plan,
  written because 19J.8 rejected the swap on the phrase "several times the
  work". Then settled as *not worth solving* on the operator's intent rather
  than on cost, and recorded in `guide/deferred_consolidated.md` Part C.

**Unchanged this window:** the reviewer surface `/me/`, the reviewee results and
observer collation surfaces, instruments, validation, extracts, rehydrate,
audit, permissions, the email template editor, and every migration. The window
was operator-side and almost entirely about one table control.

## 2. Size (LOC)

Physical lines, git-tracked files, areas fixed by `guide/assessment.json`.

| Area | Files | LOC | Δ LOC from prior |
| --- | --- | --- | --- |
| `docs` | 244 (242 prior) | **144,454** | +3,340 (+2.4%) |
| `tests` | 304 (291 prior) | **102,666** | +2,849 (+2.9%) |
| `production` | 205 (204 prior) | **59,386** | +662 (+1.1%) |
| `templates` | 64 (63 prior) | **25,141** | +633 (+2.6%) |
| `tooling` | 14 | **11,781** | unchanged |
| `migrations` | 77 | **6,772** | unchanged |

**Test-to-production ratio: 1.73×**, from 1.70× at 10sep. Rising, and the
window is why: 13 new test files against one new production module. My read is
that this is a refinement window's signature rather than a quality trend —
pagination, colour and a table control are all things you can only pin by
writing assertions, so the ratio moves without the architecture changing.

**Suite: 3,723 passed, 16 skipped**, `ruff check .` clean, both CI tracks green
(`test` on SQLite, `postgres` on a `postgres:16` service container with the full
Alembic round-trip). Up from 3,595 at 10sep — **+128 tests in two days**. All 16
skips are legacy-card retirements from Wave 5 PR 5.3, unchanged in count and
reason since the prior snapshot; **0 xfail**.

**Biggest production files**

| LOC | File | Δ |
| --- | --- | --- |
| 1,264 | `app/web/routes_operator/_instruments.py` | unchanged |
| 1,106 | `app/services/session_lifecycle.py` | unchanged |
| 1,044 | `app/services/instruments/_instrument_crud.py` | unchanged |
| 1,038 | `app/web/routes_operator/_operations.py` | **+102** |
| 1,009 | `app/web/views/_instruments.py` | unchanged |
| 1,000 | `app/services/csv_imports.py` | unchanged |
| 984 | `app/web/routes_operator/_quick_setup.py` | unchanged |
| 978 | `app/services/audit.py` | unchanged |
| 974 | `app/services/responses/_core.py` | unchanged |
| 964 | `app/services/instruments/_response_fields.py` | unchanged |

The shape is a **plateau, not a long tail**: ten files between 964 and 1,264,
and the top three are flat for a **sixth consecutive window**. The one mover is
`_operations.py` (+102, paging Invitations and Responses), which crosses 1,000
and joins the plateau rather than standing out of it. §9 carries the watchlist.

**Where the window's growth landed.** Production grew +662 across eleven files,
and the distribution is the diagnostic part: **+195 to `_coverage.py`** (the SQL
sort), **+122 as one new module** (`_pager.py`), **+102 to `_operations.py`**,
and the remaining +243 spread thin across six route modules passing two new
context keys each. Templates grew +633, of which **+475 is `base.html` alone** —
the pager cluster's rules, the busy indicator, and the outside-click script. That
is the architecture working as documented (`CLAUDE.md`: the base owns inline CSS
for the entire app, no stylesheet, no build step) and also the clearest instance
of the single-seam cost named in §5.

**Package shape**, unchanged this window except where noted: `app/services` 96
modules, `app/web/views` 23 (**+1**, `_pager.py`), `app/web/routes_operator` 22,
`app/web/routes_reviewer` 12, `app/db/models` 21.

## 3. Functional-spec compliance

Every row checked against the code at `7f4b3d42`, not against the spec's
self-description. **Bold rows changed this window.**

| Functional area | Spec | Code status |
| --- | --- | --- |
| Session lifecycle (5 live states) | `spec/lifecycle.md` | ✓ shipped — `app/services/session_lifecycle.py` |
| Sessions lobby + Session Home | `spec/sessions_overview.md`, `spec/session_home.md` | ✓ shipped |
| Quick Setup card | `spec/quick_setup_card_spec.md` | ✓ shipped — `_quick_setup.py` |
| **Setup pages (5)** | **`spec/setup_pages.md`** | **✓ shipped; the four roster pages now page at 200 via `?offset=` (19J.5, 2026-09-11) — verified: `_shared._setup_row_window` + `views.build_pager`** |
| **Row pager on the seven roster tables** | **`spec/ui_elements.md` §10, `spec/setup_pages.md`, `spec/operations_pages.md`, `spec/assignments.md`** | **✓ shipped 2026-09-11 (19J.5 / .8 / .9) — verified: `_pager_cluster.html` included at 14 sites across 7 templates, 7 distinct `pager_anchor` values, 0 references to the retired strip** |
| **Navigation busy indicator** | **`spec/ui_elements.md` §1** | **✓ shipped 2026-09-11 (19J.4) — verified: `data-rrw-busy-bar` in `base.html`, delegated listeners; arming itself is dev-slot-verified, not suite-covered** |
| **Accent-shade reservation** | **`spec/color_tokens.md` "Deliberate couplings"** | **✓ shipped 2026-09-11 (19J.7), scope settled 19J.10 — verified: `test_reserved_shade.py` green over resolved tokens** |
| Lifecycle gating on the roster pages | `spec/lifecycle.md` §5, `spec/setup_pages.md` | ✓ shipped 2026-09-10 (19I.3, 19H.5) |
| Setup-page guidance disclosure | `spec/setup_pages.md` §"Shared body shape" item 0 | ✓ shipped 2026-09-06 |
| Roster CSV + friendly tag labels | `spec/csv_contracts.md` | ✓ shipped 2026-08-20 |
| CSV template sets (starter + demo) | `spec/csv_contracts.md` | ✓ shipped 2026-09-06 |
| **Assignment engine + Assignments page** | **`spec/assignments.md`** | **✓ shipped; paged 2026-09-11 and the pair sort moved into SQL with an explicit `COLLATE "C"` — verified: `_pair_sort_order` in `_coverage.py`, dialect guard green** |
| Instruments (Bands 1/2/3) | `spec/instruments.md` | ✓ shipped — `instruments/` (9 modules) |
| Validate page | `spec/validate_page.md` | ✓ shipped — `validation.py` |
| Reviewer surface `/me/` | `spec/reviewer-surface.md` | ✓ shipped — `routes_reviewer/` (12 modules) |
| Reviewee results (3 modes) | `spec/visibility_policy.md`, `spec/participant_model.md` | ✓ shipped; gate tightened 2026-09-08 (19F) |
| Observer collation + cohorts | `spec/participant_model.md` | ✓ shipped |
| **Operations pages (Invitations / Responses)** | **`spec/operations_pages.md`** | **✓ shipped; both page at 200 unfiltered since 2026-09-11, a filtered view stays uncapped by decision — verified in `_operations.py`** |
| In-app operator Guide | `spec/operator_ui_concept.md`, `spec/ui_elements.md` | ✓ shipped 2026-09-07; 16 surfaces as light/dark screencap pairs (32 files), all 32 re-checked 2026-09-11 and none stale |
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
| Operator theming (in-app tweaker) | `guide/theme_customizer.md` Stretch | ⏸ planned — `guide/deferred_consolidated.md` Part A |
| Email dispatch / invitations | `guide/segment_14B_email_infrastructure.md` | ⛔ blocked — SMTP backend + outbox rows exist, no live send |
| Blob storage | `spec/blob_storage.md`, `guide/segment_18Q_blob.md` | ⏸ planned — awaiting institutional storage account |
| **In-place table page turns** | **`guide/inplace_pagination_assessment.md`** | **⏸ off-roadmap by decision 2026-09-11 — `guide/deferred_consolidated.md` Part C, with the trigger that would move it back** |
| Technical-support contact (global) | none — stub in `guide/todo_master.md` | ⏸ planned; unhomed since 2026-09-08 |

**No ⚠ drift rows.** The 10sep table's only one (the Assignments "Self-reviews
card") closed with 19J.1's sweep. One instance of drift *appeared and closed
inside this window*: 19J.9 retired the range strip on 2026-09-11 and the specs
went on describing it for several hours, across five files — `ui_elements.md`
§7/§10, `setup_pages.md` (twice), `operations_pages.md`, and
`assignments.md`. Two of those five were found by a `spec-writer` check acting
as reviewer, not by the author of the edits. That is the maker ≠ checker rule
in `constitution.md` paying for itself, and it is also the honest reason this
table's rows are worth re-verifying rather than copying forward.

## 4. Strengths

- **The plateau held under a sixth consecutive window.** Ten production files
  sit between 964 and 1,264 LOC and the top three did not move, while the window
  added a new table control across seven pages, a chrome-level indicator and a
  colour rule. Growth landed as **one new 122-LOC module plus thin additions to
  existing seams** rather than accumulating on the largest files — the +195 to
  `_coverage.py` went to a 703-LOC module, not to one of the top ten.
- **Scaffold-first is load-bearing, not ceremony.** `CLAUDE.md` requires a new
  navigation affordance to land inert before it is wired. 19J.9 did that, and
  the scaffold rung is where the placement question was settled by looking —
  and where a rule that had been dead since rung 1 surfaced, because raising a
  `font-size` on a selector that was losing a specificity tie is what made the
  loss visible.
- **Guards are written to fail, then checked that they can.** Every new guard in
  the window was mutation-tested — six mutations at 19J.9 rung 1, seven at rung
  2, five on the pager cleanup, two on the outside-click handler. One guard's
  receiver probe was found to have a hole *by the mutation it existed to catch*
  passing, and was widened. A test that cannot fail certifies nothing, and this
  codebase now checks that routinely rather than assuming it.
- **Dialect divergence is tested where CI is blind to it.** The SQLite suite
  cannot see a collation bug. Rung 4 stood up an ICU-collated Postgres 16 in the
  sandbox, measured the divergence on seven names, and left behind a
  dialect-compilation guard that asserts the `COLLATE "C"` is emitted whatever
  locale a server carries.
- **Decisions get measured before they get made.** The in-place-swap question
  was answered with a page-turn cost table (413KB, 21ms at 556 rows, 116ms at
  5,000), a count of which script blocks survive a DOM swap, and a count of the markup
  that would need extracting first (928 lines across seven templates). **The
  script-block count in that assessment was wrong and is corrected there
  2026-09-11** — see §5. The answer was "don't" — and the numbers are what make that
  re-decidable later.

## 5. Weaknesses

- **`base.html` absorbed +475 lines this window and is the single largest
  structural risk.** The architecture is explicit that the base owns inline CSS
  for the whole app with no stylesheet and no build step, and that choice has
  held well — but every visual change in the window landed in one file, and it
  is now where a reader must go to understand the pager, the busy indicator, the
  chip vocabulary and the theme. **Cost:** specificity collisions that are
  invisible until a value changes. One such rule was dead for two rungs
  (`body.ui-v2 .table-pager-step` losing to `body.ui-v2 .btn-icon` on source
  order, both (0,2,1)) and nobody could see it, because its declarations matched
  what the winner already set. **Plan:** none. Filed here; the file is not on §9
  because it is not a production module and the split the architecture forbids
  is exactly a stylesheet.
- **Invitations and Responses are N+1, measured and unfixed.** 40,433 and 80,432
  queries at 200×200. Pagination cut the HTML those pages emit but not the work
  behind it — every row is still built before any slice happens. **Cost:**
  seconds of wall time on a large roster, which is what 19J.4's indicator exists
  to narrate rather than remove. **Plan:** named in 19J.4's Out of scope and
  nowhere else. This is the most deferred decision in the codebase and the one I
  would expect to be forced by a real pilot roster.
- ~~**Four of five table-relevant script blocks in `base.html` bind to elements
  at load.**~~ **Corrected 2026-09-11, after this document first said it: it is
  one block, not four.** Re-measured by reading each of the eight inline blocks
  rather than by matching the word `DOMContentLoaded`, the only one binding to
  elements inside the table card is the column-chip block (127 lines). The
  321-line sort block binds nothing — its headers call `rrwSortHeaderClick`
  through an inline `onclick` attribute, so the handler arrives with any
  re-rendered markup; its one listener is a `DOMContentLoaded` badge repaint
  that a swap would re-call. The delete-confirm block binds in the Operator
  actions and lock cards, and the theme toggle is chrome — neither is
  table-relevant. **Cost:** correspondingly smaller than stated — re-rendering
  a table card costs one block of re-homing plus one function call, not ~500
  lines. **Plan:** Segment 19K Item 2, opened on the corrected measurement.
  **Recorded here rather than silently fixed**, because the figure was carried
  from another document instead of re-derived, which is precisely the failure
  the skill behind this series exists to prevent, and it survived into a
  recommended next move.
- **`close_check` cannot see `guide/` commitments, and it bit twice in one
  segment.** The tool tracks `spec/` and `docs/` paths only, so a `Doc impact`
  bullet naming a `guide/` file is unchecked: 19J.7's screencap-retake row and
  19J.8's `deferred_consolidated.md` entry both went unhonoured without failing
  anything, and both were caught by a human reading the manifest at close. A
  related gap: C3's window for a *new* item starts at the segment's date rather
  than the item's, so a fresh item can pass on a sibling's edits. **Plan:**
  recorded in the archived plan and `todo_master.md`; not scheduled, and see §8.
- **`app/services/session_lifecycle.py` is 94 LOC from its watchlist tripwire**
  and has been for two windows. It did not move this window, which is the only
  reason it is not §9's first entry.

## 6. Bugs and regressions

**No known open bugs at `7f4b3d42`.** What that claim rests on: the full suite
green (3,723 passed / 16 skipped, all skips legacy-card retirements), `ruff`
clean, **0 TODO/FIXME in `app/`**, **0 xfail** in `tests/`, both CI tracks green
including the Alembic round-trip on Postgres 16, and `docs/known_limitations.md`
re-read at this SHA.

Worth remembering from the window:

- **A locale-aware `ORDER BY` would have silently reordered every sorted table.**
  Moving the Assignments sort into SQL was a correctness change, not a
  performance one: under an ICU `en-US` collation seven names order
  `_edge | alpha | ana lim | Ana Lim | Bravo | charlie | Delta`; under `C` they
  order as the app has always rendered them, because the sort ran in Python. All
  eight ordering tests pass on SQLite with the collation removed, so CI's main
  track could not have caught it.
- **A dead CSS rule survived two rungs** because its declarations coincided with
  what the winning rule already set. Found by asking for a bigger glyph.
- **A regex guard passed on the mutation it existed to catch.** The
  outside-click test asserted every listener is registered on `document` via
  `(\w+)\.addEventListener`, which does not match `menus[0].addEventListener`
  because `]` is not a word character — so the offending receiver dropped out of
  the match set. It now matches any receiver expression *and* asserts the match
  count equals the number of registrations.
- **An empty-roster page renders no table at all**, which broke two test drafts
  mid-window. Not a product bug; recorded because it is the shape of fixture
  assumption that keeps costing time.

## 7. Estimated size upon completion

**Current:** production 59,386, templates 25,141.

| Remaining work | Production LOC | Templates | Depends on |
| --- | --- | --- | --- |
| Segment 14B — email dispatch, reminders, invitations | +900–1,400 | +200–400 | institutional Azure provisioning |
| Segment 20 — operator polish + documentation | +200–500 | +300–600 | institutional Azure deployment concluded |
| Blob storage (18Q) seam + first consumers | +400–700 | +50–150 | institutional storage account |
| Operator theming (Stretch) | +150–300 | +100–200 | customizer editor core (shipped) |
| Technical-support contact (global) | +30–60 | +20–50 | nothing (unblocked) |
| **Projected floor** | **61,066–62,346** | **25,811–26,441** | |

**Reconciliation.** The 10sep snapshot stopped projecting a total and started
stating a **floor** — the named work and nothing else — after 19J.2 measured
that no per-unit refinement allowance exists (every candidate unit spreads 14×
to 117× across the refinement windows). This is the first snapshot to test that
change, and it behaves as intended: the floor moved from ~58.8–60.1k to
61.1–62.3k purely because the current total moved, and **the window's +662 was
overtaken-by rather than predicted-by the floor** — which is the measurement the
10sep snapshot said future snapshots should make in place of a projection.

So, stating it plainly: **the floor was overtaken by +662 production LOC in two
days by work no item list contained on 2026-09-10.** Seven of 19J's ten items
did not exist when the segment opened. The floor is honest about being a floor;
it is not a forecast, and this window is the second consecutive demonstration
that the gap between them is where most of the code comes from.

Excludes anything past v1.

## 8. Bottom line

The codebase is in good shape and moved sideways rather than outward this
window: +1.1% production for a refinement arc that rebuilt one table control
across seven pages, with the top of the file-size table flat for a sixth
consecutive window and the test ratio up to 1.73×. Segment 19J closed complete
at ten items — three it opened for, seven that its own findings produced — and
the archive is `guide/archive/segment_19J_assessment_moves.md`. The one live
thread is that **no segment is in flight**: `todo_master.md` marks none live,
and the three plans still in `guide/` — `segment_14B_email_infrastructure.md`,
`segment_18Q_blob.md`, `segment_20_operator_polish_and_documentation.md` — are
all for work blocked on institutional provisioning or an undecided product
question, not work in progress.

**Recommended next moves** — three, ordered:

1. **Fix `close_check`'s `guide/` blindness.** It is the smallest of the three
   and it is first because it is a *checker* defect: two commitments went
   unhonoured in one segment without failing anything, and the only reason both
   were caught is that a person read the manifests at close. Every future
   segment's `Doc impact` inherits the gap. The same change should address C3's
   window starting at the segment's date rather than the item's (§5).
2. **Convert the column-chip script block in `base.html` to delegation.**
   ~~The four element-bound blocks~~ — **one block, 127 lines**, corrected
   2026-09-11 (§5). Named as worth doing regardless by the swap assessment and
   by Part C, it commits to nothing and it is what makes a re-rendered table
   card survivable. It stays second despite shrinking: it is still the only
   item here that *unblocks* something rather than tidying, and it is now
   cheap enough that the argument for doing it is stronger, not weaker.
   Opened as Segment 19K Item 2.
3. **Decide whether the Invitations / Responses N+1 gets an item.** It is
   measured (40,433 / 80,432 queries at 200×200), it is the most deferred
   decision in the codebase, and it currently lives only in one item's Out of
   scope. It is third not because it matters least but because a real pilot
   roster will price it better than an estimate can — the move is to *decide*,
   which may legitimately be "not yet, and here is the trigger".

**Settling the prior snapshot's proposals.** The 10sep §8 recommended three
moves and all three shipped the day they were recommended, as Segments 19J.1
(the `rrw_functional_spec.md` sweep), 19J.2 (the refinement allowance, refuted)
and 19J.3 (the `close_check.py` split). It then deliberately left the *next*
recommendations empty, saying the findings of those three should be the input
to this snapshot's §8 — and they are: move 1 above is a direct consequence of
19J.3 having carved the tool that then turned out to have a blind spot.

## 9. Proposed file splits — watchlist

**No split is queued, and the top of the table is flat for a sixth consecutive
window.**

- **`app/web/routes_operator/_instruments.py` (1,264 LOC, unchanged).** Sixth
  flat window; still below the 17aug high of 1,317. The seam if it grows: carve
  the `/save` payload-parsing blocks into a `_save.py` sibling, leaving the thin
  route in place. Revisit past ~1,400 — **136 LOC away**.
- **`app/services/session_lifecycle.py` (1,106 LOC, unchanged).** Still no
  natural seam; the state machine is cohesive and splitting it would scatter the
  transition table. **94 LOC from its ~1,200 tripwire**, unchanged from 10sep —
  a second consecutive window inside 150. Watch actively; do not plan.
- **`app/services/instruments/_instrument_crud.py` (1,044 LOC, unchanged).**
  Three concerns in one module (lifecycle, group/unit-of-review, column-widths);
  past ~1,200 the column-widths helpers are the cleanest carve. 156 LOC away.
- **`app/web/routes_operator/_operations.py` (1,038 LOC, +102).** **New to this
  list.** The window's only mover among the large files, crossing 1,000 when
  Invitations and Responses were paged. It is a two-page route module and the
  seam is obvious if needed — split by page — so it is watchlisted rather than
  worried about. 162 LOC from the ~1,200 class tripwire.

**Watchlist tripwire: ~1,400 for `_instruments.py`, ~1,200 for the other three.**

`base.html` is **not** on this list despite absorbing +475 lines this window,
and that is a judgement worth stating rather than leaving implicit: it is a
template, not a production module, and the only split available to it is a
separate stylesheet, which `CLAUDE.md` rules out by design. It is filed as a
weakness (§5) instead, which is the honest place for a risk with no sanctioned
remedy.
