# New-model instruments — outstanding work for full takeover

The new-model instrument card (the flavour gated on
`instruments.is_new_model`) has grown from a concept-test shell
into a near-complete operator surface. This doc tracks **how far
it is from replacing the legacy individual + group instrument
cards outright**, and what would need to retire / consolidate
once it does.

Scope of "full takeover":

1. Every operator-facing affordance on the legacy individual +
   group cards exists on the new-model card (or is consciously
   retired).
2. The reviewer surface + assignment engine read identical
   per-instrument state regardless of card flavour.
3. The RuleSet library (`operator_rule_sets` +
   `rule_set_revisions`) and RTD library
   (`operator_response_type_definitions`) are either retired or
   coexist intentionally.
4. The `is_new_model` flag column can be dropped.

## What the new-model card already does (parity)

| Operator surface | Storage | Read-path |
|---|---|---|
| Identity (name, short_label, description) | `instruments.{name, short_label, description}` | Reviewer surface heading + Setup pages — same as legacy. |
| Band 1 Link 1 + 2 (assignment rules) | `session_rule_sets.rules_json` via `instruments.rule_set_id` | Assignment engine (`app/services/rules/engine.py`) — same as legacy. |
| Band 1 Link 3 (unit of review) | `instruments.group_kind` | Reviewer surface group-row composition + group-pair-count cache — same shape as the legacy group-instrument variant. |
| Band 2 display-field order (pill drag) | `instrument_display_fields.order` | Reviewer surface column order — same as legacy. |
| Band 2 column widths (display + identity) | `instruments.column_widths` JSON | Reviewer surface table renders `<col>` widths + opts into `table-layout: fixed` when widths are set. |
| Band 2 pill selection / response-field rows / preview-sample reviewee / response-field column widths | `instruments.band2_state` JSON (`selected_display_keys` / `response_fields[*]` / `sample_reviewee_name`) | **New-model card preview only — see Gap 1 + Gap 2 below for the reviewer-surface bridge.** |
| Lifecycle (Edit / Save / Cancel / Open / Close / Show-when-closed / Replicate / Delete) | Standard `instruments` columns | Standard action row at the bottom of every card flavour. |

## Gap inventory — what the new-model card doesn't do yet

Cross-referenced against the legacy individual + group cards
(`app/web/templates/operator/instruments_index.html` — non-
`is_new_model` branches), the RuleSet library
(`app/services/rules/seeds.py`, `app/services/rules/session_library.py`,
`app/web/routes_operator/_rule_builder.py`), and the RTD library
(`app/services/instruments/_rtds.py`,
`app/web/routes_operator/_response_types.py`,
the Response Type Definitions card lines 2877-3196).

Each gap carries a rough complexity (T = trivial, S = small, M
= medium, L = large) and notes any blocking dependency.

### Gap 1 — Pill selection → `InstrumentDisplayField.visible` (T)

**Today.** Pill click toggles `band2_state.selected_display_keys`
but doesn't update `InstrumentDisplayField.visible`. Operator
sees the column drop from the new-model preview; the reviewer
still sees it on the actual surface.

**Close.** Mirror each pill toggle through the existing
`set_display_field_visibility` service (with the Name + Email
locked-row guard already in place there). One small wiring
change in `set_band2_state` (or a paired call in the route).

### Gap 2 — Response fields → real `InstrumentResponseField` rows (M-L)

**Today.** Band 3's Response Fields editor persists rows to
`band2_state.response_fields` JSON. No `InstrumentResponseField`
rows are created; no `ResponseTypeDefinition` rows referenced.
The reviewer surface sees only the default response fields
seeded by `create_instrument`, not the operator's authored
fields.

**Close.** Each Band 3 ✓ creates / updates a real
`InstrumentResponseField` pointing at an RTD. Two flavours of
RTD wiring:

- **Pre-RTD-retirement (today's schema):** auto-create a
  per-instrument `ResponseTypeDefinition` row on each ✓ save,
  carrying the bounds (`min` / `max` / `step` / `max_length`).
  Per-instrument RTD bloat is the cost.
- **Post-RTD-retirement** (see Gap 6 below + `guide/instrument_builder.md`
  §D-RTD + §1d): inline `data_type` + bounds directly onto
  `instrument_response_fields`. No per-instrument RTD rows at
  all for numerical / string types; List types stay as
  session-level RTDs.

Cascade-aware delete needed for X on a row when responses already
exist. The pill's `selected` flag needs either a new
`InstrumentResponseField.visible`-style column or a "if it's in
the table, it's shown" contract.

### Gap 3 — Sort priorities (T-S)

**Legacy.** Sort cell on each Display Fields row — tri-state
click button cycling unsorted → asc → desc → unsorted, persisting
to `instruments.sort_display_fields` JSON (Segment 13B). Reviewer
surface default sort honours this.

**New-model.** No sort UI today; the preview pills are
drag-orderable but don't expose sort priorities.

**Close.** Either add a sort badge to each Band 2 pill (click to
cycle, badge shows priority number) or move sort to a separate
control. The underlying `instruments.sort_display_fields` JSON
+ `instruments_service.set_sort_display_fields` already exist
unchanged.

### Gap 4 — Response field help text + visibility (S)

**Legacy.** Response Fields Help table — `help_text` textarea +
`help_text_visible` toggle per response field. Reviewer surface
renders help text inline below the input when visible.

**New-model.** Not surfaced. Band 3 Response Fields rows only
have name / data_type / bounds.

**Close.** Either an expandable accordion per row in Band 3, or
a dedicated help editor. Wires to the existing
`InstrumentResponseField.help_text` + `.help_text_visible`
columns once Gap 2 lands (response fields become real DB rows
first).

### Gap 5 — Response field "required" flag (T)

**Legacy.** Required checkbox on each Response Fields row.

**New-model.** Not surfaced.

**Close.** Add a checkbox to each Band 3 row; wire to
`InstrumentResponseField.required`. Trivial once Gap 2 closes.

### Gap 6 — RTD library retirement (M, prereq for Gap 2 cheapness)

**Today.** Two tiers — `operator_response_type_definitions` (per-
operator library) + `response_type_definitions` (per-session
copies, 10 seeded RTDs per session). Per-session card lets the
operator Edit / Delete / Save-to-library / Add-from-library
(template lines 2877-3196).

**Plan.** `guide/instrument_builder.md` §D-RTD + §1d sketches
the retirement:

- **Inline** numerical + string types' bounds onto
  `instrument_response_fields` directly. Drop the corresponding
  seeded RTDs.
- **Keep** List-type RTDs as a small per-session catalog (the
  shared option-list still has reuse value across instruments).
- **Retire** `operator_response_type_definitions` entirely.
- Personal-library copy-in retires too. Session replication
  carries any per-session List RTDs along with the clone.

Migration: backfill bounds inline onto every referencing
`instrument_response_fields` row, then drop the numerical /
string seeded RTDs.

### Gap 7 — RuleSet library retirement (M)

**Today.** Two tiers — `operator_rule_sets` (library) +
`session_rule_sets` (per-session copies, 5 seeded RuleSets per
session: `Full Matrix` / `Intra-group peer review` /
`Cross-group peer review` / `Same group, different role` /
`Three reviewers per reviewee`). Rule Builder child page
(`app/web/routes_operator/_rule_builder.py`) is the editor; the
per-instrument card's Assignment Rule section pins a session
copy via `instrument.rule_set_id`.

**Plan.** `guide/instrument_builder.md` Part 1b sketches the
retirement:

- Band 1's inline rule editor (already shipped on new-model)
  becomes the canonical authoring surface.
- Retire seeded RuleSets, the personal library, "Save to /
  Add from library" affordances, the Available RuleSets sidebar
  on the Instruments page, and `library_origin_id` provenance.
- Retire the Rule Builder child page entirely.
- Replace with one-shot "Insert starter ▾" templates (no
  provenance, no library row).

The new-model card already authors rules inline through
`session_rule_sets.rules_json`, so the engine path is unchanged
— what retires is the library tier + the separate editor page.

### Gap 8 — "+Group instrument" button becomes redundant (T)

**Legacy.** The Instruments index has a dedicated "+Group
instrument" button that creates an instrument with
`group_kind=GROUP_KIND_SENTINEL` so the per-instrument card
renders the group-scoped variant.

**New-model.** Band 1 Link 3's Individual ↔ Grouped toggle
already covers this. The "+Group instrument" button retires once
new-model is the default.

### Gap 9 — Drop the `is_new_model` flag (T, last step)

Once new-model is the only flavour, the column is dead. Final
Alembic revision drops `is_new_model` and the `+New model`
button. Template branches on `is_new_model` collapse to a single
shape.

## Roadmap: smallest path to full takeover

Sequenced so each step is independently shippable and the
operator gains parity progressively:

1. **Gap 1** (pill → visible) + **Gap 3** (sort priorities) +
   **Gap 5** (required flag). All T-S, no schema delta. Once
   these land, the new-model card surfaces every per-display-
   field affordance the legacy card has.
2. **Gap 6** (RTD library retirement). Schema delta on
   `instrument_response_fields` + data migration. Lands before
   Gap 2 so Gap 2 doesn't have to author the bloat workaround.
3. **Gap 2** (response fields → real DB rows). Now cheap because
   bounds inline onto `instrument_response_fields` directly. +
   **Gap 4** (help text) rides along since the columns exist.
4. **Gap 7** (RuleSet library retirement). Independent of
   anything else once Band 1's inline editor is the canonical
   path.
5. **Gap 8** (retire +Group button) + **Gap 9** (drop
   `is_new_model`). Cleanup. The legacy template branches +
   routes + buttons retire in the same PR.

Estimated effort: roughly 6-10 medium PRs for steps 1-3, 3-5
medium PRs for step 4, 1-2 small PRs for step 5. Total
~10-17 PRs spread across a small handful of segments.

## When this matters

The card is usable end-to-end today **for design feedback** —
operators can author rules, pick unit of review, lay out
columns, design response shapes, all visibly in the preview.

The gaps become blocking when:

- A pilot operator wants a reviewer to actually fill in a Band
  3 response field (Gap 2).
- A pilot operator wants pill deselect to truly hide a column
  on the reviewer surface (Gap 1).
- The team wants to stop maintaining two card flavours +
  library subsystems and consolidate (Gaps 6 + 7 + 9).

Until then, the new-model card is best framed as a
concept-test surface that runs alongside the legacy cards,
with the gaps documented above as the price of running both.

## Performance: scaling Save + Refresh preview to large rosters

On a 1k × 1k roster (~1M candidate `(reviewer, reviewee)`
pairs), both the post-Save page render and the ↻ Refresh
preview click lag in the 1-3s range. The Refresh latency is
expected — it explicitly runs the rule engine — but the Save
lag is incidental: the redirect-rerender pays the same engine
cost via the per-instrument eligibility cache invalidation.

### Where the cost actually lives

`GET /operator/sessions/{id}/instruments` calls
`build_instruments_context`, which in turn calls
`session_library.evaluate_session_rule_eligibility(...)` to
compute the **pinned-rule eligible-pair count per instrument**
(rendered on the legacy assignment-rule card and consulted by
the Validate page). The function stamps a content hash of
`(roster + rule definition)` against
`session_rule_sets.cached_eligibility_stamp` and re-runs
`engine.evaluate(...)` on cache miss. Any rule edit changes
the hash, so the first render after Save always pays the full
~1-3s/instrument cost. A group-scoped instrument additionally
hits `evaluate_instrument_group_pair_counts` for the same
brute-force `O(N · M · rules)` walk.

`engine.evaluate` itself (`app/services/rules/engine.py`)
materialises the full `[(r, e) for r in reviewers for e in
reviewees]` list (1M tuples ≈ 30 MB), sorts it, then evaluates
each rule against every surviving pair. No tag-side indexes,
no short-circuit.

### Recommendations

Sequenced from smallest lift to biggest payoff, framed against
the new-model card's actual needs.

#### Rec A — Drop the per-instrument eligible-pair count from the index render *(S)*

The new-model card does not need to display a pair count. The
legacy individual + group cards render it in the Assignment
Rule card (`spec/rule_based_assignment.md` §7.1) and the
Validate page consults it for a staleness rule — but neither
of those is on the path the operator hits after clicking
Save.

Move the eligibility-count fetch off the
`build_instruments_context` hot path. Two flavours:

- **Conditional skip.** Only call `evaluate_session_rule_eligibility`
  for instruments whose flavour actually renders a count. For
  new-model instruments (which don't), skip entirely. The
  legacy cards keep their counts unchanged. Smallest possible
  diff; lets the legacy + new-model cards coexist with
  different performance profiles.
- **Full lazy / async.** Render the index page with a
  "Counting…" placeholder badge per pinned rule set; a small
  inline JS fetch hits a new count endpoint that runs the
  engine and fills in the badge. The Save → redirect → render
  no longer blocks on the engine at all. Bigger change but
  benefits every flavour and decouples the index render from
  the engine entirely.

Either flavour makes Save feel instant on 1k × 1k rosters.
No engine work changes; no schema change; the
`cached_eligible_pair_count` mechanism stays in place for the
surfaces that still want a count.

Eligibility for new-model preview still needs the engine
(Rec B) — Rec A is purely about getting the cost off the
Save flow.

#### Rec B — Engine fast path: "find first N in-scope pairs" *(M)*

The new-model card's actual need from the engine is a small
sample for the Band 2 preview, not a count and not the full
pair list:

- **Individual mode:** one `(sample_reviewer, sample_reviewee)`
  pair surviving Link 1 + Link 2 + cross-side ops.
- **Group mode:** up to `GROUP_MEMBER_NAME_LIMIT` (=10)
  reviewees in the sample group, plus the boundary-tag values.

Today the Refresh-preview route
(`app/web/routes_operator/_instruments.py::instrument_preview_sample`
→ `find_sample_in_scope_reviewee`) calls `engine.evaluate(...)`
and then takes `result.pairs[0]`. That throws away ~999,999
pairs of work.

Add a `find_first_n_pairs(rule_set, *, reviewers, reviewees,
limit, pair_context_lookup)` entry point next to `evaluate` in
`app/services/rules/engine.py`. Same predicate vocabulary, but:

- Iterates `(reviewer, reviewee)` pairs lazily (generator,
  not materialised list).
- Short-circuits the moment `limit` matches are accumulated.
- Skips the candidates sort + quota assignment (preview
  doesn't need a deterministic ordering of the full result).
- For Refresh on Individual mode: `limit=1`. Typical case:
  first reviewer × first reviewee passes — returns in
  microseconds. Worst case (very narrow rules): walks the
  full 1M pairs, same as today.
- For Refresh on Group mode: server picks one sample reviewer,
  walks their reviewees until `limit=10` (or the reviewer is
  exhausted), returns the partition. Typically << 1000
  predicate evaluations.

`find_sample_in_scope_reviewee` swaps over to
`find_first_n_pairs(limit=1)`. Refresh preview on 1k × 1k
drops from 1-3s to typically <100ms; only narrow / no-match
rules hit the worst case.

#### Rec C — Single-side predicate indexes (L, optional)

Only worth doing if Rec B's worst case still bites on real
rosters. Pre-compute a `(side, tag_slot, value) → id_set` dict
at evaluation start (cheap, `O(N + M)`). For single-side
`equals` / `not_equals` / `in` / `not_in` / `is_empty` /
`is_not_empty` rules, intersect / subtract id sets before
materialising any pair. Cross-side `same_as` / `different_from`
still iterate per pair but over a much smaller surviving
set.

This is where roster-upload-time caching could meaningfully
contribute — the index lives on a new
`sessions.roster_index_json` column populated at import (or
lazily on first eval and invalidated on roster edit, mirroring
the existing `cached_eligibility_stamp` pattern). With the
index, the brute-force `O(N · M)` step collapses to
`O(K · L · cross_side_rules)` where `K` and `L` are the
post-filter subset sizes.

Defer until Rec B's worst case is observed in practice. For
the broad-rule cases pilot operators are likely to author,
Rec B alone should keep latencies well under 100ms even on
1k × 1k.

### Sequencing

| # | Recommendation | Lift | Impact on Save lag | Impact on Refresh lag |
|---|---|---|---|---|
| A | Drop per-instrument eligible-pair count from index render | S | **Cured.** Save returns instantly; no engine on the redirect path. | None — Refresh still hits the engine. |
| B | `find_first_n_pairs` engine fast path | M | None directly (Rec A already cured Save). | **Cured.** Refresh typically <100ms; worst case = today. |
| C | Single-side predicate indexes (+ roster-upload cache) | L | None directly. | Brings Rec B's worst case down to interactive. Also speeds the real Assignments-page Generate. |

Recommend landing A first as a one-PR quick win, B as a follow-up,
and reserving C for if pilot rosters expose the narrow-rule worst
case.
