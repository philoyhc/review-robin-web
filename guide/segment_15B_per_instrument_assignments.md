# Segment 15B — Per-instrument assignments

**Status:** Plan revised 2026-05-12. Previous draft (2026-05-09)
assumed `Assignment.context` was live, `AssignmentContext1-3`
was a future-possible slot, and manual-CSV assignment upload
was still a surface to extend. All three premises retired
during 15D / Segment 16 work:

- `Assignment.context` dropped in **15D PR 6b** (pair-context
  migrated to `relationships.tag_*`; assignment-context never
  shipped).
- `AssignmentContext1-3` is no longer a thing — not a deferred
  slice, not a future possibility. Logic-bearing per-assignment
  metadata, if it ever surfaces, is a brand-new design problem
  outside this segment.
- Manual-CSV assignment upload retired **2026-05-11** as a dev-
  only escape hatch. Per-instrument manual upload is therefore
  also moot — there is no manual-upload surface to extend.

This revision rewrites the segment around the surviving core:
**each instrument card carries its own assignment-rule selection
affordance.** The Assignments page becomes a per-instrument
preview / monitoring surface rather than the place rules are
applied. The Operations tab order swaps so Assignments sits
to the left of Validate (operators preview the materialised
pairs before validating them).

**Sizing:** ~6 PRs.
**Status:** **Plan locked, implementation deferred to start
immediately after Segment 15C ships.** The 2026-05-12 codebase
audit (this revision) confirmed that
`instruments.rule_set_id`'s FK target (`session_rule_sets`) is
not populated by any session-create path today. The seeded
RuleSets that 15B's operator surface must offer (Full Matrix,
etc.) live as code constants destined for `session_rule_sets`
materialisation, but the materialiser lives in 15C Slice 1
(workspace-seed migration). Without 15C, 15B has nothing to
pick from in the per-card picker and nothing for
`replace_assignments` to resolve. The decision to defer
(rather than fold a minimal auto-seed precursor into 15B) is
deliberate: 15C is the right home for that mechanism, and
deferring lets 15B inherit the full library / per-session-
copy contract rather than a half-version.
**Depends on:**
- 15A shipped (friendly-label resolver — already done).
- **15C shipped** — specifically Slice 1
  (`materialise_seed_rule_sets` on session create populates
  `session_rule_sets` with the workspace seeds) and Slice 4
  (Rule Builder picker reads from `session_rule_sets`, the
  same pool 15B's per-card picker will consume). See
  `guide/segment_15C_operator_libraries.md` for the contract.

---

## Goal

Let each `Instrument` carry its own RuleSet selection, so that
(for example) "the Manager survey" can materialise different
reviewer → reviewee pairings than "the Peer survey" in the same
session. Today every instrument shares the session's single
rule choice via the Assignments-page Rule Based card.

The operator's mental model lands as:

> "Each instrument owns its own assignment rule. I choose the
> rule on the instrument card. The Assignments page is where I
> *check* what the rules produced — not where I configure them."

---

## Schema audit (2026-05-12)

Verified ahead of the revision: **nothing schema-side is
missing.** No additions need to ride 13F. The data-layer
prerequisite — *populated* `session_rule_sets` rows — is a
behaviour gap, not a schema gap, and is owned by 15C Slice 1.

| What 15B needs | Status |
|---|---|
| `Assignment.instrument_id` non-null FK + `(session_id, reviewer_id, reviewee_id, instrument_id)` unique constraint | ✅ already on the model (`app/db/models/assignment.py:19-61`). |
| `instruments.rule_set_id` nullable FK → `session_rule_sets`, `ON DELETE SET NULL` | ✅ pre-positioned by 13D PR 4 (`app/db/models/instrument.py:68-84`). |
| `session_rule_sets` table | ✅ pre-positioned by 13D PR 2 (`app/db/models/session_rule_set.py`). |
| `session_rule_sets` *populated on session create* with workspace seeds (Full Matrix, etc.) | ❌ delivered by **15C Slice 1** — `materialise_seed_rule_sets`. Without this, every newly-created session has zero rows in `session_rule_sets` and 15B's per-card picker / Assignments-page Generate button have nothing to operate on. |
| `Assignment.context` JSON dropped | ✅ retired in 15D PR 6b. |

Per-instrument `Assignment` rows already exist in every multi-
instrument session — `replace_assignments` writes one row per
`(reviewer, reviewee, instrument)` triple today. Pre-15B rows
are byte-identical across instruments because the service
fans out the same pair list per instrument; 15B's only job is
to let those per-instrument rows *diverge* when the operator
picks different rules for different instruments.

**Settings CSV shape is already in place.** The session-config
serialiser at `app/services/session_config_io.py:340` emits
`instruments[N].rule_set_name` rows per instrument; the parser
at `app/services/session_config_io.py:1057-1058` routes the
value onto a per-instrument spec attribute. The only gap is
the apply phase, which hardcodes `rule_set_id=None` at
`app/services/session_config_io.py:1605` with an explicit
`# 15B target; pre-15B left NULL` comment. Slice 2 lights up
that apply path so per-instrument rule selection round-trips
through Settings CSV end-to-end.

---

## Migration & invariants

Three invariants this segment must preserve.

1. **Schema migration is a no-op.** Pre-15B data already looks
   like 15B data: N `Assignment` rows per `(reviewer, reviewee)`
   pair (one per instrument), and `instruments.rule_set_id`
   already exists as a nullable column. No Alembic migration
   ships in 15B. (Confirmed against `app/db/models/`.)

2. **Default instrument #1 always exists.**
   `services.instruments.ensure_default_instrument` (called from
   `replace_assignments`) already guarantees every session has
   at least one instrument. The single-instrument flow stays
   byte-identical: instrument #1 carries the single
   `rule_set_id` choice; the Assignments page renders without
   any per-instrument grouping chrome.

3. **Multi-instrument chrome only mounts when N > 1.** When
   `len(instruments) == 1`, the Assignments page and the
   Validate page render exactly as they do today — no per-
   instrument tabs, no breakdown rows, no "All Instruments"
   affordance. Operators who never add a second instrument
   should not see any new chrome.

4. **No Quick Setup affordance for assignments.** The Quick
   Setup card's Assignments slot retired in 15D PR 7a; this
   segment does **not** reintroduce it. Bulk-edit of per-
   instrument rules happens via the existing Settings CSV
   (Quick Setup Settings slot — already in place, end-to-end
   after Slice 2 lights up the apply path).

5. **Pinning a rule and materialising the pairs are
   separate operator actions.** The Instrument card's only
   job is to *pin* which rule applies to which instrument
   (persists `rule_set_id`). Materialising the pairs (the
   actual `replace_assignments` call) is **not triggered
   from the Instrument card** — it's the operator's explicit
   action on the **Assignments page** (Generate button, Slice
   3) or on the **Next Action card** on Session Home
   (Slice 4). This split exists because the rules-to-pairs
   step can be slow on large rosters and the operator should
   see a preview surface (Assignments page) before committing
   to it.

---

## Approach

### Slice 1 — Service-layer per-instrument scope (1 PR, ~200 LOC)

`replace_assignments` (`app/services/assignments.py:343-477`)
today loads every instrument in the session and fans out the
same `pairs` list per instrument. Replace that with explicit
per-instrument scope:

- Add `instrument_id: int | None = None` parameter.
- `instrument_id=None` materialises across every instrument
  that has a non-NULL `rule_set_id`. This is the path the
  Assignments-page "Generate" button (Slice 3) and the
  Next Action card "Generate assignments" button (Slice 4)
  both call. Instruments with NULL `rule_set_id` are skipped
  silently (they're "no rule pinned yet" — not an error).
- `instrument_id=<id>` materialises only that instrument's
  assignments. Reserved for the per-tab regenerate
  affordance the Assignments page may grow as a follow-up;
  not the primary path in 15B.

Also touched:
- `assignments.existing_count` /
  `assignments.delete_session_assignments` gain optional
  `instrument_id` filters.
- `monitoring.per_reviewer_coverage` — already iterates
  Assignment rows; confirm the instrument-scope flows through
  the pivot.
- Audit envelope already carries `instrument_id` in the
  `assignments.replaced` payload (per 11K's canonical schema);
  the field starts carrying real per-instrument variation.

No callers change shape — `instrument_id=None` is the
backwards-compatible default for the existing two call sites
(the legacy Assignments-page Rule Based card and the Quick
Setup card).

### Slice 2 — Per-instrument rule picker on the Instrument card (1 PR, ~400 LOC)

**The centerpiece.** Each instrument card on
`/operator/sessions/{id}/instruments` grows a half-width
**Assignment rule** sub-card at the bottom, sitting to the
**left of the existing Danger Zone sub-card**. The Edit /
Add-new-instrument action buttons relocate to a row below the
two sub-cards.

```
┌─ Manager survey ──────────────────────────────────────────┐
│ short label: ms                                           │
│                                                           │
│  ─ Display fields ─                                       │
│  …                                                        │
│  ─ Response fields ─                                      │
│  …                                                        │
│                                                           │
│  ┌─ Assignment rule (½) ─────┐  ┌─ Danger zone (½) ─────┐ │
│  │ [Full Matrix         ▾]   │  │ [Delete this          │ │
│  │ 42 eligible pairs found.  │  │  instrument]          │ │
│  │ [Open Rule Builder]       │  │                       │ │
│  └───────────────────────────┘  └───────────────────────┘ │
│                                                           │
│  [Edit]  [Add new instrument]                             │
└───────────────────────────────────────────────────────────┘
```

The picker sub-card contains **exactly three things**:

- **Rule picker** — a `<select>` listing every
  `session_rule_sets` row visible in this session (seeded
  RuleSets first, then the operator's personal copies, matching
  the order used by today's Assignments-page Rule Based card).
  Top option is a "— No rule —" sentinel that maps to
  `rule_set_id=NULL` on save.
- **Eligibility line** — "N eligible pairs found." Shows the
  count of pairs the currently-selected rule would produce
  when applied against the session's current rosters. Computed
  server-side using the same engine the Rule Builder preview
  uses; re-evaluated whenever the picker selection changes
  (small JS swap; same shape as the existing live-preview
  patterns on the Instruments page). Reads "no rule selected"
  when the sentinel option is active.
- **Open Rule Builder** — link-styled button that opens the
  existing Rule Builder page threaded with the instrument's
  current `rule_set_id` and `instrument_id`
  (`/operator/sessions/{id}/assignments/rule-based-editor?rule_set_id={...}&instrument_id={...}`).
  The Rule Builder's "back to assignments" link returns to the
  Instrument card, not to the Assignments page.

**All three are Secondary style. No Primary button on the
picker sub-card.** The Rule Builder button is the only button;
the picker and eligibility line are not buttons.

#### Edit-mode gating

The picker is **only accessible when the instrument card is
in edit mode**. Specifically:

- **Card locked** (default state): the picker `<select>` is
  disabled, the eligibility count is read-only, the Open Rule
  Builder button stays available (it's a navigation
  affordance, not a mutation). The picker shows the saved
  `rule_set_id`'s name; if NULL, it shows "— No rule —".
- **Card editing** (operator clicked Edit): the `<select>`
  becomes enabled, the eligibility line refreshes when the
  selection changes. Selection persists on **Save**, alongside
  every other inline-edit change on the card. Cancel reverts
  the picker to the saved value with no side effect.

Using the picker is part of the card's edit affordance — there
is no separate "save the picker" form. The existing
Save / Cancel buttons (which appear in place of Edit when the
card is editing) cover the picker write-through.

#### Save semantics — pin only, no generation

Saving an instrument card whose picker changed **only
persists `instruments.rule_set_id`**. It does **not** call
`replace_assignments`, does not delete or write any
`Assignment` rows, and does not change the materialised pair
set on the Assignments page. The card's job is to pin which
rule applies to which instrument; materialising the pairs is
the operator's explicit next action on the Assignments page
(Slice 3) or via the Next Action card on Session Home (Slice
4).

The audit envelope on Save carries an `instrument.rule_pinned`
event with `before` / `after` `rule_set_id` values (uses the
canonical `audit.changes(...)` envelope). The
`assignments.replaced` event continues to fire **only** from
the explicit generation surfaces in Slices 3 / 4.

**`instruments.rule_set_id` resolution semantics.** The column
is the single source of truth per instrument. NULL = "no rule
selected" — the initial state for every existing instrument
post-13D PR 4. Selecting "— No rule —" and Saving clears it
back to NULL; the next generation action then leaves this
instrument's `Assignment` rows empty (or deletes any stale
rows from a previous rule).

**Why this split.** Materialising pairs can be slow on large
rosters and creates a visible side-effect (existing reviewer
work disappears if Assignment rows are replaced). The
operator needs a moment between "I changed the rule" and "the
pairs are now different" to preview and decide. Pinning is
cheap and reversible; generation is what commits.

**No session-level default.** If 80% of operators want the
same rule on every instrument, the Settings CSV is the
release valve: they edit a single `instruments[N].rule_set_name`
value per row and re-apply through the existing Quick Setup
Settings slot — Slice 2's apply-path light-up makes that work
end-to-end without any new UI. A session-level
`default_rule_set_id` column is **not** introduced (avoids
inheritance ambiguity; revisit only if operator feedback asks).

**FK behaviour wired through to the UX:**

- **Delete instrument** (existing): the row's pointer dies
  with it. Session RuleSet copy untouched.
- **Delete a session RuleSet copy** (post-15C affordance):
  SQL `SET NULL` clears every `instruments.rule_set_id`
  pointing at it. **UX note for 15C:** the delete-confirm
  dialog lists every instrument that currently applies it
  ("Removing will clear this rule from N instrument(s): …").
- **Delete from the operator library** (15C affordance): does
  **not** touch any instrument pointer — instrument pointers
  target session copies, which survive library deletes via the
  `library_origin_id SET NULL` cascade (13D PR 2).

**Settings CSV apply path lights up in the same slice.** The
serialiser already emits `instruments[N].rule_set_name`; the
parser already lifts it onto a per-instrument spec. The
remaining work is at `session_config_io.py:1605`:

1. Resolve `spec.rule_set_name` → `session_rule_sets.id` via
   the `(session_id, name)` unique index added by 13A-2.
2. Pass that id into the `Instrument(...)` construction.
3. Unknown names → `_ParseError` with a clear message
   ("rule set 'foo' not found in this session — add it to
   the session's RuleSet pool first") raised at apply time,
   same shape as the existing `_VALID_GROUP_KINDS` validation.
4. Empty / NULL value → leave `rule_set_id=None` (the
   "no rule picked yet" state).

This makes Settings CSV the bulk-edit channel for per-
instrument rules: operators who want to set every instrument's
rule in one shot do it via the existing Quick Setup Settings
slot, not via per-card clicks. The per-card picker (this
slice's UI work) is for incremental adjustment.

### Slice 3 — Assignments page → preview + page-level Generate + tab reorder (1 PR, ~400 LOC)

Two paired changes that ship together.

**(a) Reshape the Assignments page.** Rule *selection* moves
off the page (it's now on Instrument cards, Slice 2). Rule
*application* — i.e. materialising the `Assignment` rows from
the rules pinned to each instrument — stays here as the
primary surface for it.

- **Remove the Rule Based card's picker.** No more RuleSet
  dropdown, no more "what-rule-is-this-session-using"
  question on this page. The legacy manual-CSV upload was
  retired 2026-05-11 and stays gone.
- **Add a page-level "Generate" affordance.** Single button
  at the top of the page (or in a small toolbar above the
  preview): "Generate assignments". Calls
  `replace_assignments(instrument_id=None)` per Slice 1 —
  materialises pairs for every instrument that has a rule
  pinned, skips instruments with NULL `rule_set_id`. Confirm
  dialog before running ("Replace assignments for N
  instrument(s)? Existing pairs will be deleted."). Disabled
  state when zero instruments have rules pinned, with a
  helpful nudge: "Pin rules on the Instruments page first"
  with a deep link.
- **Post-Generate report.** On the redirect back to the page
  after a successful Generate, a confirmation banner reports
  the materialised count per instrument ("Generated 42 pairs
  for *Manager survey*, 30 pairs for *Peer survey* (72 total).").
  Same surface the existing flash-message pipeline uses; copy
  reads the same per-instrument count from the
  `assignments.replaced` audit-event payload that Slice 1's
  service emits.
- **Keep the self-reviews Include toggle** — it's still the
  one bulk operation that makes sense here (it's a property
  of the rendered pair set, not the rule).
- **Per-instrument grouping** when `len(instruments) > 1`:
  the existing pairs preview table grows a tab strip (one tab
  per instrument, plus an "All instruments" tab that shows
  the union, read-only). Each tab renders a small read-only
  status block at the top:

  - **Rule:** the name of the rule pinned to this instrument
    (or "— No rule pinned —" with a deep link to the
    Instrument card if NULL).
  - **Eligible pairs:** the count the rule engine would
    produce if run *now* against the current rosters /
    relationships (preview mode — same number the Instrument
    card's sub-card displays, served by the same helper).
    Recomputes on every page load; reflects roster edits
    immediately, even before Generate runs.
  - **Generated:** the actual `Assignment` row count for this
    instrument plus the timestamp of the last
    `assignments.replaced` event ("42 pairs · last generated
    11:02 today"), or "Not generated yet" when zero rows
    exist or the staleness fingerprint diverges from the
    pinned-rules fingerprint.
  - **Edit on Instruments page** link deep-linking to the
    matching instrument card.

  The eligible-vs-generated split is the operator's hint that
  Generate is the act that commits — the eligible count
  changes the moment a rule pin or a roster changes; the
  generated count only changes when the operator clicks
  Generate. When the two diverge, the page also surfaces a
  small "Pairs may be stale" badge near the Generate button.
- **Single-instrument case** — the page renders the
  page-level Generate button + the same Rule / Eligible
  pairs / Generated status block (no tab strip, just the
  inline block above the table) + self-reviews toggle +
  pairs preview table.
- **Per-instrument sort.** Folds in the carved-from-13B-Part-2-PR-F
  per-instrument table sort: cookie name shape
  `rrw-sort-assignments-{session_id}-{instrument_id}` (one
  cookie per instrument tab). Wiring via the rrw-sort primitive
  shipped 2026-05-12; this slice just annotates the template +
  threads `decode_cookie_sort_spec` / `apply_cookie_sort`
  through the per-instrument render path. Tests follow the
  `test_assignments_sort.py` shape.

**(b) Swap Assignments and Validate in the Operations tab
strip.** Today: `Validate → Assignments → Previews → Invitations
→ Responses`. New: `Assignments → Validate → Previews →
Invitations → Responses`. The reasoning is that the operator's
flow becomes:

1. Set rules on the Instruments page.
2. Look at the Assignments page to confirm the materialised
   pairs are sensible (preview, no edit).
3. Run Validate to surface any issues.

Validate sitting *after* Assignments matches that flow — the
old order made more sense when Assignments was where the
operator did the work; now it's where they review the work.

Touched: `app/web/templates/operator/partials/session_top_nav.html`
(the `_ops_pages` array + the rendered order). Test surface:
`test_session_top_nav.py` (the existing chrome test pins tab
order; the swap is one assertion edit).

### Slice 4 — Next Action card surfaces "Generate assignments" (1 PR, ~150 LOC)

The Next Action card on Session Home (per `spec/session_home.md`)
already surfaces the next lifecycle move as its primary
button (Validate Setup → Activate Session → Pause Session).
This slice adds a new pre-Validate step:

**"Generate assignments"** appears as the primary next action
when:
- The session is in a pre-active lifecycle state (draft /
  configuring), **and**
- At least one instrument has a rule pinned
  (`rule_set_id IS NOT NULL`), **and**
- Either no `Assignment` rows exist yet, **or** the
  pinned-rules state has drifted from the materialised state
  (the next-action resolver computes a small staleness
  fingerprint — `(instrument_id, rule_set_id,
  rule_set_revision_id)` tuples — and shows the button when
  the fingerprint diverges from the audit log's last
  `assignments.replaced` event).

Clicking the button is equivalent to clicking Generate on the
Assignments page — same service call
(`replace_assignments(instrument_id=None)`), same confirm
dialog, same audit event. The button is **Primary** style
(it's the Next Action card's primary, by spec).

When zero instruments have rules pinned, the Next Action card
shows a *supporting* link ("Pin rules on the Instruments
page") in place of the primary button — the operator has to
go pin something before generation is meaningful.

Touched: `app/web/views/_session_home.py` (or wherever the
Next Action resolver lives — see `spec/session_home.md`),
`app/web/templates/operator/session_home.html` (or the
Next Action card partial). No new service code — Slice 1's
`replace_assignments` is the call site.

### Slice 5 — Validation per-instrument (1 PR, ~120 LOC)

`validate_session_setup` currently checks "every reviewer has
≥1 assignment". Generalise to per-instrument:

- New `ValidationRule` keyed
  `assignments.reviewer_missing_for_instrument` —
  surfaces "Alice is missing assignments for the Peer survey"
  when N > 1.
- Single-instrument case falls back to the existing
  `assignments.reviewer_missing` rule — same message text,
  no per-instrument breakdown.
- Existing "instrument has no assignments at all" surfacing
  also lights up per-instrument (when N > 1) as
  `assignments.instrument_empty`.

No schema change. No reviewer-surface template change —
that surface is already multi-instrument-aware from the
Segment 11D follow-on.

### Slice 6 — Reviewer dashboard per-instrument grouping (1 PR, ~150 LOC)

The reviewer dashboard (`/reviewer`) today shows one row per
session with a single per-session pill. On a 2-instrument
session a reviewer who's submitted instrument 1 but not
started instrument 2 sees `in progress` with no breakdown —
they have to open the surface to learn which instrument is
which.

- `app/web/templates/reviewer/dashboard.html` — per-session
  row expands to a stacked sub-row per instrument when
  `N > 1`. Each sub-row carries the instrument's short label
  + its own progress pill.
- Single-instrument sessions stay byte-identical (invariant #3).
- `app/web/routes_reviewer.py::dashboard` — context builder
  reads per-instrument state via the existing
  `responses_service.reviewer_session_state(...)` projection.
- New view-adapter shape (extension of the existing
  dashboard adapter).

No new audit events; no service mutations. Pure read-path
adapter + template change.

**Hard dependency: none.** Uses the existing per-instrument
projection. Could ship before any other slice in principle,
but ordered last because it's the smallest surface and easiest
to bump if something else slips.

---

## Risks + open questions

- **Existing data carries forward without divergence.** Pre-
  15B multi-instrument sessions have identical `Assignment`
  rows across instruments. After Slice 2 lands, those rows
  stay identical until the operator picks different rules per
  instrument. The audit log will show "no-op" assignment
  replays the first time an operator re-Generates on a single
  instrument without having changed its rule. Acceptable.

- **Seeded RuleSets, pre- and post-15C.** Today seeded
  RuleSets (Full Matrix, etc.) live in `operator_rule_sets`
  with copies materialised into `session_rule_sets` on session
  create. 15C may move the seeds into a code constant; the
  `instruments.rule_set_id` pointer always targets a
  `session_rule_sets` row regardless. No special-casing in
  this segment.

- **Email invitations.** Reviewer-scoped, not instrument-
  scoped. No change — reviewers receive one invitation per
  session regardless of how their assignments break down per
  instrument.

- **CSV export.** When the Extract Data flow exports
  assignments, per-instrument rows already export
  individually (one row per `Assignment`). No 12A change
  needed.

- **Empty Rule pool case.** If a session has no
  `session_rule_sets` rows at all (e.g. a fresh deployment
  before seeds materialise, or a session whose seed copies
  were all deleted), the per-instrument rule picker shows an
  empty `<select>` + a deep link to the Rule Builder ("Create
  a rule to assign"). Cover in Slice 2 tests.

---

## Critical files

- **Service layer.**
  `app/services/assignments.py` (Slice 1 — `replace_assignments`
  parameter + helpers),
  `app/services/session_config_io.py` (Slice 2 — apply-path
  light-up at line 1605, `rule_set_name` → `rule_set_id`
  resolution),
  `app/services/validation.py` (Slice 5),
  `app/services/instruments/_instrument_crud.py` (Slice 2 —
  rule-picker write-through).
- **Routes.**
  `app/web/routes_operator/_assignments.py` (Slice 3 — strip
  Rule Based card; preview-only render),
  `app/web/routes_operator/_instruments.py` (Slice 2 — the
  existing Save handler grows a `rule_set_id` write-through
  and an inline call to
  `replace_assignments(instrument_id=...)` when the picker
  changed; new GET endpoint returns the eligibility-count
  fragment for the picker's live refresh),
  `app/web/routes_operator/_rule_builder.py` (Slice 2 —
  thread `instrument_id` through Rule Builder URL),
  `app/web/routes_reviewer.py` (Slice 6 — dashboard handler).
- **View adapters.**
  `app/web/views/_assignments.py` (or wherever the
  Assignments-page adapter lives),
  `app/web/views/_instruments.py` (Slice 2 — per-card rule-
  picker context),
  `app/web/views/_validate.py` (Slice 5),
  `app/web/views/_dashboard.py` (Slice 6),
  `app/web/views/_session_home.py` (Slice 4 — Next Action
  resolver).
- **Templates.**
  `app/web/templates/operator/session_assignments.html`
  (Slice 3 — preview + page-level Generate reshape),
  `app/web/templates/operator/instruments_index.html`
  (Slice 2 — per-card rule sub-card),
  `app/web/templates/operator/partials/session_top_nav.html`
  (Slice 3 — tab order swap),
  `app/web/templates/operator/session_home.html` (Slice 4 —
  Next Action card "Generate assignments" affordance),
  `app/web/templates/operator/session_validate.html`
  (Slice 5),
  `app/web/templates/reviewer/dashboard.html` (Slice 6).
- **Schema dependency only:** `instruments.rule_set_id`
  pre-positioned by 13D PR 4; `session_rule_sets` table by
  13D PR 2. **No migration in 15B itself.**

---

## Verification

- `pytest -q` green on SQLite + `ci-postgres` after each slice.
- `ruff check .` green.
- New tests per slice:
  - **Slice 1** — `test_assignments_service.py` regression
    tests for `instrument_id=None` (apply to all) vs.
    per-instrument paths; audit-event payload assertions.
  - **Slice 2** — `test_instrument_rule_set_picker.py` —
    picker `<select>` disabled when card is locked, enabled
    in edit mode; Save persists `instruments.rule_set_id`
    only — does **not** touch the `Assignment` rows or fire
    `assignments.replaced` (the test pins this absence). The
    audit envelope on Save fires `instrument.rule_pinned`
    with `before` / `after` `rule_set_id`. Cancel reverts the
    picker cleanly. Eligibility line refreshes on picker
    change. Empty-pool case renders the "Create a rule" deep
    link via the Open Rule Builder button. Plus
    `test_session_config_io_rule_set.py` — Settings CSV
    apply path resolves `rule_set_name` → `rule_set_id`
    (happy path + unknown-name error + empty-value clears).
  - **Slice 3** — `test_assignments_page_generate.py` —
    page-level Generate button fans out across instruments
    with rules pinned, skips NULL ones, fires
    `assignments.replaced` per instrument; disabled state
    when no rules pinned; post-Generate banner reports the
    per-instrument materialised count. Plus
    `test_assignments_page_preview.py` — Rule Based card's
    picker gone; per-instrument status block reports Rule /
    Eligible / Generated independently; eligible count
    refreshes after a roster edit while the generated count
    stays put until Generate runs; "Pairs may be stale" badge
    surfaces when the two diverge. `test_session_top_nav.py`
    — Assignments tab sits left of Validate.
  - **Slice 4** — `test_session_home_next_action_generate.py`
    — Next Action card shows "Generate assignments" primary
    button when ≥1 instrument has a rule pinned and the
    materialised state is stale; supporting link shown when
    zero rules pinned; button disappears once generation has
    run and the staleness fingerprint matches.
  - **Slice 5** — `assignments.reviewer_missing_for_instrument`
    ValidationRule covered in `test_session_validate_page.py`.
  - **Slice 6** — `test_reviewer_dashboard_per_instrument.py`
    — single-instrument session renders one row + pill
    (byte-identical to pre-15B); multi-instrument session
    renders one sub-row per instrument.
- Manual smoke on the dev slot for Slices 2 / 3 / 4 —
  per-instrument rule selection persists (via per-card picker
  *and* via Settings CSV round-trip) without generation
  side-effects; Assignments-page Generate fans out correctly;
  Next Action card surfaces Generate at the right moment;
  reviewer surface honours the per-instrument scope.

---

## Spec / doc impact

When this segment kicks off, the following spec / doc surfaces
need updates to match the revised mental model:

- **`spec/operator_ui_concept.md`** — §5 currently says the
  Operations Assignments page carries the wired Rule Based
  card and that operators "pick a RuleSet, hit Generate"
  there. That stops being true after Slice 3 — the page is
  preview-only; the picker lives on Instrument cards. Tab-
  order diagram (the `OPERATIONS ▶ [Validate][Assignments]
  …` strip) updates to match Slice 3's swap.
- **`spec/rule_based_assignment.md`** — §7.1 (the "Rule Based
  card on the Assignments page") gets re-homed to "Rule Based
  block on the Instrument card". The Rule Builder UI itself
  (§7.2) doesn't change shape; just gains an `instrument_id`
  context param so its "back to assignments" link returns to
  the right Instrument card.
- **`spec/instruments.md`** — Section C (per-card layout)
  grows a new sub-section covering the half-width
  **Assignment rule** sub-card at the bottom of the card,
  paired with the existing Danger Zone sub-card. The
  sub-card carries the picker (Secondary), the
  "N eligible pairs found" line, and the Open Rule Builder
  button (Secondary); no Primary button on the sub-card. The
  Edit / Save / Cancel / Add-new-instrument action row
  relocates to a row below the two half-width sub-cards.
  Picker is gated by the card's edit-mode lock; **Save
  pins the selection only — does not materialise pairs.**
  Generation lives on the Assignments page and on the Next
  Action card.
- **`spec/operations_pages.md`** — Assignments-page contract
  flips from "place to generate assignments" to "place to
  preview the materialised pairs"; per-instrument tab strip
  spec lands here.
- **`spec/operator_button_audit.md`** — Section covering the
  Assignments page loses the Rule Based card's picker but
  gains a page-level Generate button (Primary; matches the
  pattern for other commit-style operations); Instruments-
  page section gains the per-card Assignment-rule sub-card's
  single button (Open Rule Builder, Secondary). No Primary
  button on the sub-card. Session Home section gains the
  Next Action card's "Generate assignments" affordance
  (Primary, conditional on staleness).
- **`spec/session_home.md`** — Next Action card spec gains a
  pre-Validate "Generate assignments" step in the lifecycle-
  next-action ladder (between configuring and Validate Setup);
  states the staleness condition that surfaces it.
- **`spec/settings_inventory.md`** — flip the
  `instruments.rule_set_id` row from "Inert until 15B Slice 2
  wires per-instrument selection" to wired; the Settings-CSV
  coverage line (currently flagged "resolved to
  `rule_set_name`") gains a note that the apply path is now
  live end-to-end.
- **`docs/status.md`** — chronological entry per slice ship.
- **`guide/todo_master.md`** — 15B moves from Upcoming to
  in-progress, then to Done when Slice 6 lands.
- Archive this file to `guide/archive/` when Slice 6 merges.
