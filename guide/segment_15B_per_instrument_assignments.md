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

**Sizing:** ~5 PRs.
**Depends on:** 15A shipped (friendly-label resolver — already
done). No other hard dependency.
**Doesn't depend on 15C.** 15C splits RuleSets into a two-tier
operator-library / per-session-copy model; that ships
independently. 15B reads / writes `instruments.rule_set_id`
which points at `session_rule_sets` regardless of whether
the row arrived via library-copy (post-15C) or via the seeded-
RuleSet auto-materialisation that exists today.

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
missing.** No additions need to ride 13F.

| What 15B needs | Status |
|---|---|
| `Assignment.instrument_id` non-null FK + `(session_id, reviewer_id, reviewee_id, instrument_id)` unique constraint | ✅ already on the model (`app/db/models/assignment.py:19-61`). |
| `instruments.rule_set_id` nullable FK → `session_rule_sets`, `ON DELETE SET NULL` | ✅ pre-positioned by 13D PR 4 (`app/db/models/instrument.py:68-84`). |
| `session_rule_sets` table | ✅ pre-positioned by 13D PR 2 (`app/db/models/session_rule_set.py`). |
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

4. **No Quick Setup affordance.** The Quick Setup card's
   Assignments slot retired in 15D PR 7a; this segment does
   **not** reintroduce it. Generate lives on the per-
   instrument card (Slice 2); bulk-edit of per-instrument
   rules happens via the existing Settings CSV (Quick Setup
   Settings slot — already in place, end-to-end after Slice 2
   lights up the apply path).

---

## Approach

### Slice 1 — Service-layer per-instrument scope (1 PR, ~200 LOC)

`replace_assignments` (`app/services/assignments.py:343-477`)
today loads every instrument in the session and fans out the
same `pairs` list per instrument. Replace that with explicit
per-instrument scope:

- Add `instrument_id: int | None = None` parameter.
- `instrument_id=None` keeps current behaviour — replace
  assignments across every instrument. Retained for the
  legacy callers that survive Slice 3 (today's Assignments-
  page Rule Based card, removed in Slice 3) and as a safety
  net during the transition; no live operator surface calls
  this path after Slice 3 ships.
- `instrument_id=<id>` replaces only that instrument's
  assignments. The Instrument-card Generate button (Slice 2)
  is the only operator-facing caller post-15B.

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
`/operator/sessions/{id}/instruments` grows a small block
above the Display / Response fields that owns the rule
selection for *that instrument*:

```
┌─ Manager survey ───────────────────────────────────────┐
│ short label: ms                                        │
│                                                        │
│  Assignment rule                                       │
│  ┌──────────────────────────────┐ [Edit rule]          │
│  │ Full Matrix          ▾       │ [Generate]           │
│  └──────────────────────────────┘                      │
│  Current assignments: 42 pairs (last generated 11:02). │
│                                                        │
│  ─ Display fields ─                                    │
│  …                                                     │
│  ─ Response fields ─                                   │
│  …                                                     │
└────────────────────────────────────────────────────────┘
```

- **Rule picker** — `<select>` listing every
  `session_rule_sets` row visible in this session (seeded
  RuleSets first, then the operator's personal copies, matching
  the order used by today's Assignments-page Rule Based card).
  Writes through to `instruments.rule_set_id` on submit.
- **Edit rule** — link to the existing Rule Builder page,
  threaded with the instrument's current
  `rule_set_id`. (`/operator/sessions/{id}/assignments/rule-based-editor?rule_set_id={...}&instrument_id={...}`.)
- **Generate** — calls `replace_assignments(instrument_id=...)`
  per Slice 1. Replaces only that instrument's
  `Assignment` rows. Audit envelope carries the per-instrument
  `instrument_id` field.
- **Status line** — "Current assignments: N pairs (last
  generated HH:MM)" or "No assignments generated yet" when the
  row count is zero. Reads from `assignments.existing_count`
  (Slice 1 helper).

**`instruments.rule_set_id` resolution semantics.** The column
is the single source of truth per instrument. NULL = "no rule
picked yet" — the initial state for every existing instrument
post-13D PR 4. Picking a rule writes the row id; "Reset" (a
new affordance — small link inside the rule block) sets it
back to NULL and deletes that instrument's `Assignment` rows.

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

### Slice 3 — Assignments page → preview-only + tab reorder (1 PR, ~350 LOC)

Two paired changes that ship together.

**(a) Strip rule-application affordances from the Assignments
page.** The page becomes purely a preview / monitoring surface:

- **Remove the Rule Based card.** Rule selection now lives on
  the Instrument cards (Slice 2). The Assignments page no
  longer carries a RuleSet picker, no Generate button, no
  "what-rule-is-this-session-using" question. The legacy
  manual-CSV upload was retired in 2026-05-11 and stays gone.
- **Keep the self-reviews Include toggle** — it's still the
  one bulk operation that makes sense here (it's a property
  of the rendered pair set, not the rule).
- **Per-instrument grouping** when `len(instruments) > 1`:
  the existing pairs preview table grows a tab strip (one tab
  per instrument, plus an "All instruments" tab that shows
  the union, read-only). Each tab renders the rule-set
  currently in effect for that instrument as a small read-only
  header ("Rule: Full Matrix · 42 pairs · Edit on Instruments
  page"). The "Edit on Instruments page" link deep-links to
  the matching instrument card.
- **Single-instrument case** — the page renders byte-identical
  to today minus the Rule Based card: just the self-reviews
  toggle + the pairs preview table. No tabs, no breakdown.
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

### Slice 4 — Validation per-instrument (1 PR, ~120 LOC)

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

### Slice 5 — Reviewer dashboard per-instrument grouping (1 PR, ~150 LOC)

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
  `app/services/validation.py` (Slice 4),
  `app/services/instruments/_instrument_crud.py` (Slice 2 —
  rule-picker write-through).
- **Routes.**
  `app/web/routes_operator/_assignments.py` (Slice 3 — strip
  Rule Based card; preview-only render),
  `app/web/routes_operator/_instruments.py` (Slice 2 — rule
  picker / Generate POST handlers),
  `app/web/routes_operator/_rule_builder.py` (Slice 2 —
  thread `instrument_id` through Rule Builder URL),
  `app/web/routes_reviewer.py` (Slice 5 — dashboard handler).
- **View adapters.**
  `app/web/views/_assignments.py` (or wherever the
  Assignments-page adapter lives),
  `app/web/views/_instruments.py` (Slice 2 — per-card rule-
  picker context),
  `app/web/views/_validate.py` (Slice 4),
  `app/web/views/_dashboard.py` (Slice 5).
- **Templates.**
  `app/web/templates/operator/session_assignments.html`
  (Slice 3 — preview-only reshape),
  `app/web/templates/operator/instruments_index.html`
  (Slice 2 — per-card rule block),
  `app/web/templates/operator/partials/session_top_nav.html`
  (Slice 3 — tab order swap),
  `app/web/templates/operator/session_validate.html`
  (Slice 4),
  `app/web/templates/reviewer/dashboard.html` (Slice 5).
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
    selecting a rule writes `instruments.rule_set_id`;
    Generate writes per-instrument `Assignment` rows; Reset
    clears both. Empty-pool case renders the "Create a rule"
    deep link. Plus `test_session_config_io_rule_set.py` —
    Settings CSV apply path resolves `rule_set_name` →
    `rule_set_id` (happy path + unknown-name error +
    empty-value clears).
  - **Slice 3** — `test_assignments_page_preview_only.py` —
    Rule Based card gone, preview table renders, tabs mount
    when N > 1, single-instrument case stays
    byte-identical. `test_session_top_nav.py` — Assignments
    tab sits left of Validate.
  - **Slice 4** — `assignments.reviewer_missing_for_instrument`
    ValidationRule covered in `test_session_validate_page.py`.
  - **Slice 5** — `test_reviewer_dashboard_per_instrument.py`
    — single-instrument session renders one row + pill
    (byte-identical to pre-15B); multi-instrument session
    renders one sub-row per instrument.
- Manual smoke on the dev slot for Slices 2 / 3 —
  per-instrument rule selection persists (via per-card picker
  *and* via Settings CSV round-trip), Assignments-page tabs
  render correctly, reviewer surface honours the per-
  instrument scope.

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
- **`spec/instruments.md`** — Section C ("Action row" /
  per-card layout) grows a new sub-section above Display
  Fields covering the per-instrument rule block (picker +
  Edit + Generate + status line).
- **`spec/operations_pages.md`** — Assignments-page contract
  flips from "place to generate assignments" to "place to
  preview the materialised pairs"; per-instrument tab strip
  spec lands here.
- **`spec/operator_button_audit.md`** — Section covering the
  Assignments page loses the Rule Based card's buttons;
  Instruments-page section gains the per-card rule block
  buttons (Generate, Edit rule, Reset).
- **`spec/settings_inventory.md`** — flip the
  `instruments.rule_set_id` row from "Inert until 15B Slice 2
  wires per-instrument selection" to wired; the Settings-CSV
  coverage line (currently flagged "resolved to
  `rule_set_name`") gains a note that the apply path is now
  live end-to-end.
- **`docs/status.md`** — chronological entry per slice ship.
- **`guide/todo_master.md`** — 15B moves from Upcoming to
  in-progress, then to Done when Slice 5 lands.
- Archive this file to `guide/archive/` when Slice 5 merges.
