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
the Response Type Definitions card lines 2888-3240).

Each gap carries a rough complexity (T = trivial, S = small, M
= medium, L = large) and notes any blocking dependency.

### Gap 1 — Pill selection → `InstrumentDisplayField.visible` (T) — shipped 2026-05-24 (PR #1395)

**Today.** Pill click toggles `band2_state.selected_display_keys`
but doesn't update `InstrumentDisplayField.visible`. Operator
sees the column drop from the new-model preview; the reviewer
still sees it on the actual surface.

**Close.** Mirror each pill toggle through the existing
`update_display_field` service
(`app/services/instruments/_display_fields.py:291`, with the
Name + Email locked-row guard at lines 308-315). One small
wiring change in `set_band2_state` (or a paired call in the
route).

### Gap 2 — Response fields → real `InstrumentResponseField` rows (M-L) — shipped 2026-05-25 (PRs #1418, #1431, #1432)

> Shipped end-to-end via the three-PR Wave 3 ladder. The DB is
> now the sole source of truth: `set_band2_state` dual-writes
> JSON entries to real `InstrumentResponseField` rows (PR i),
> reviewer-surface readers filter by `visible=true` (PR ii),
> the JSON write side retires entirely with response-column
> widths migrating to `instrument.column_widths["rf_<id>"]`
> (PR iii). Alembic migration `c3a7e9d8b154` back-fills any
> instrument that didn't re-save between PR i and PR iii.
> Reviewer surface ships matching `<col style="width: Npx">`
> so operator-set widths persist all the way through.

**Today (pre-Wave-3).** Band 3's Response Fields editor persists
rows to `band2_state.response_fields` JSON. No
`InstrumentResponseField` rows are created; no
`ResponseTypeDefinition` rows referenced. The reviewer surface
sees only the default response fields seeded by
`create_instrument`, not the operator's authored fields.

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

### Gap 3 — Sort priorities (T-S) — shipped 2026-05-24 (PR #1396)

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

### Gap 4 — Response field help text + visibility (S) — partially shipped 2026-05-24 (PRs #1408, #1409)

> The new-model card now surfaces both the visibility toggle
> and the help-text body via the in-card ✎/✓ editor pattern.
> What remains is the broader Band 3 UX decision (accordion vs
> dedicated pane vs always-visible — see Wave 3 design decision
> 13 in `guide/segment_18J_new_model_takeover.md`). The
> underlying columns + persistence are in place; once the
> remaining Band 3 UX choice is made, that work is the only
> piece left.


**Legacy.** Response Fields Help table — `help_text` textarea +
`help_text_visible` toggle per response field. Reviewer surface
renders help text inline below the input when visible.

**New-model status.** Each Band 3 row carries an "≡" toggle
button (PR #1408) that controls whether a half-width help card
renders above the preview table for that field. Each help card
carries an in-card ✎/✓ icon-button pair (PR #1409) that lets the
operator edit the help-text body inline; the body persists into
`band2_state.response_fields[*].help_text` (server-side clamp at
1000 chars). The chip-gating tweak in PR #1409 hides the card
when the response pill is deselected without flipping the "≡"
state. Reviewer-surface rendering of the help text waits for
Wave 3 (Gap 2 bridges JSON rows to real
`InstrumentResponseField` rows; the bridge code preserves both
flags).

**What's left.** The broader Band 3 UX decision (accordion vs
dedicated pane vs always-visible textarea) is the deferred Gap 4
piece. The plumbing is shipped.

### Gap 5 — Response field "required" flag (T) — shipped 2026-05-24 (PR #1397, metadata only)

> Reviewer-surface enforcement waits for Wave 3 (Gap 2 bridge);
> Wave 1 ships operator-authored metadata only.


**Legacy.** Required checkbox on each Response Fields row.

**New-model.** Not surfaced.

**Close.** Add a checkbox to each Band 3 row; wire to
`InstrumentResponseField.required`. Trivial once Gap 2 closes.

### Gap 6 — RTD library retirement (M, prereq for Gap 2 cheapness) — shipped 2026-05-24 (PRs #1399 → #1405)

> Landed across **eight PRs** as Segment 18J Wave 2 (originally
> scoped as one M-sized PR; the test-fixture cascade made that
> infeasible). Six `_inline_*` columns on
> `instrument_response_fields` carry every field's type + bounds.
> The `response_type_id` FK, the `before_insert` listener, the
> property fallback, the seeded RTD set, the
> `operator_response_type_definitions` table, and the entire
> cross-session library tier are all gone. The
> `response_type_definitions` table + the per-instrument RTD card
> still exist for operator-authored standalone RTDs — they retire
> with Gaps 8 + 9 in Wave 5.


**Today.** Two tiers — `operator_response_type_definitions` (per-
operator library) + `response_type_definitions` (per-session
copies, 10 seeded RTDs per session). Per-session card lets the
operator Edit / Delete / Save-to-library / Add-from-library
(template lines 2888-3240).

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

### Gap 7 — RuleSet library retirement (M) — partial progress 2026-05-25 (PRs #1434, #1435)

> **Foundation laid by Wave 4a.** PR #1434 makes
> `replace_assignments` synthesise Full Matrix for new-model
> instruments with NULL `rule_set_id` instead of skipping them,
> and PR #1435 introduces `instruments_service.is_configured()`
> which retires the rule-set-centric `has_unpinned` predicate
> for new-model rows. New-model instruments are now functionally
> decoupled from the `RuleSet` construct — retiring the library
> + Rule Builder page no longer requires migrating new-model
> data. Full retirement (seeded RuleSets, library tier,
> Rule Builder page, sidebar, `library_origin_id`) is queued
> for Wave 5.

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

### Gap 8 — "+Group instrument" button becomes redundant (T) — partially shipped 2026-05-25 (PR #1443)

> **UI half shipped.** PR #1443 retired the `+Group instrument`
> button from the per-instrument action row (also retired
> `Add instrument` in the same PR, and renamed `+New model` →
> `+Instrument`). The `/instruments/add-group` POST route still
> exists server-side; that and the legacy template branches
> retire alongside Gap 9 in Wave 6.

**Legacy.** The Instruments index had a dedicated `+Group
instrument` button that created an instrument with
`group_kind=GROUP_KIND_SENTINEL` so the per-instrument card
rendered the group-scoped variant.

**New-model.** Band 1 Link 3's Individual ↔ Grouped toggle
covers this. The button retired in Wave 4c; route retirement is
Wave 6.

### Gap 9 — Drop the `is_new_model` flag (T, last step)

Once new-model is the only flavour, the column is dead. Final
Alembic revision drops `is_new_model` and collapses every
template branch on it to a single shape. (The `+New model`
button retired ahead of Gap 9 in Wave 4c — PR #1443 renamed it
to `+Instrument` — so this gap's remaining UI work is just
collapsing the branches, not retiring a button.)

### Gap 10 — Preview group expansion is rule-unconstrained (T-S, correctness bug) — shipped 2026-05-24 (PR #1394)

**Today.** In Grouped mode, the Band 2 preview shows a sample
group's member names — but the **sample reviewee pick** is
rule-constrained (via `find_sample_in_scope_reviewee` →
`engine.evaluate`) while the **group expansion** is not.
`_new_model_band2_state` at `app/web/views/_instruments.py:456-464`
partitions *all active reviewees* by boundary-tag match against
the sample reviewee's key:

```python
group_members = [
    r
    for r in active_reviewees  # ← unfiltered roster
    if tuple(getattr(r, field, "") or "" for field in reviewee_boundary_fields)
    == sample_key
]
```

`active_reviewees` (lines 412-419) is a flat
`SELECT * FROM reviewees WHERE session_id=? AND status='active'`
with no engine intersection. So the preview can show member
names that Links 1+2 will exclude at Generate time: operator
sees Alice / Bob / Carol / Dan in tag A; only Alice + Bob
become assignees.

This contradicts the contract the Refresh button is meant to
honour — Refresh runs the engine so the operator can trust
the preview reflects the actual assignment-time result. The
sample-reviewee pick honours that; the member-list expansion
does not. The defect re-becomes more visible as Wave 1's
Gap 1 (pill → visible) and Gap 3 (sort badges) push the
preview to be the operator's main authoring surface.

**Close.** Have the engine-driven sample-pick path return
**both** the sample reviewee and the set of rule-surviving
reviewee IDs that share the sample's boundary key (an
intersection over `result.pairs` the engine already produces;
~zero extra cost). Persist the ID set into `band2_state`
(e.g. `sample_group_member_ids`) at Refresh time; the render
path filters `group_members` by that set. The Refresh-gated
contract — preview is honest as of the last Refresh,
potentially stale if Links 1+2 change without a Refresh —
is preserved.

Sequenced in **Segment 18J Wave 1** as PR ε (sibling to
PRs α-δ); no schema change, ~one engine call already on the
Refresh path, set-intersection cost negligible.

## Roadmap: smallest path to full takeover

Sequenced so each step is independently shippable and the
operator gains parity progressively:

1. **Gap 1** (pill → visible) + **Gap 3** (sort priorities) +
   **Gap 5** (required flag) + **Gap 10** (rule-constrained
   preview group expansion). All T-S, no schema delta. Once
   these land, the new-model card surfaces every per-display-
   field affordance the legacy card has and the preview is
   honest about group membership.
2. **Gap 6** (RTD library retirement) — **shipped 2026-05-24**
   as Segment 18J Wave 2 across PRs #1399 → #1405. The
   `instrument_response_fields` table now carries six
   `_inline_*` columns for every field's type + bounds; the
   `response_type_id` FK retired alongside the operator library
   tier. Gap 2 is now cheap as planned.
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
- A pilot operator authors a Links 1+2 rule and expects the
  Grouped-mode preview's member list to reflect it (Gap 10).
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

There are three independent cost layers, and the new-model
card pays more on every one of them than the legacy
individual / group cards. That asymmetry is what makes "Save
feels slower on the new card" perceivable even though the
underlying engine is identical.

**Layer 1 — Engine evaluation (shared with legacy cards).**
`GET /operator/sessions/{id}/instruments` calls
`build_instruments_context`, which in turn calls
`session_library.evaluate_session_rule_eligibility(...)` to
compute the **pinned-rule eligible-pair count per instrument**
(rendered on the legacy assignment-rule card and consulted by
the Validate page). The function stamps a content hash of
`(roster + rule definition)` against
`session_rule_sets.cached_eligibility_stamp` and re-runs
`engine.evaluate(...)` on cache miss. A group-scoped
instrument additionally hits
`evaluate_instrument_group_pair_counts` for the same
brute-force `O(N · M · rules)` walk.

`engine.evaluate` itself (`app/services/rules/engine.py`)
materialises the full `[(r, e) for r in reviewers for e in
reviewees]` list (1M tuples ≈ 30 MB), sorts it, then evaluates
each rule against every surviving pair. No tag-side indexes,
no short-circuit.

**Layer 2 — Per-new-model-card overhead (new-model only).**
For every new-model instrument on the page, the view-layer
helper `_new_model_band2_state`
(`app/web/views/_instruments.py:372`) runs a fresh
`SELECT * FROM reviewees WHERE session_id=? AND status='active'`
(lines 412-419), serialises the whole roster into a
`data-new-model-band2-roster` JSON attribute on the card's
root element, and the inline on-load JS loop
(`document.querySelectorAll('[data-new-model-band2]').forEach(window.newModelRefreshBand2)`
in `instruments_index.html`) re-runs the Band 2 preview
rebuild against that JSON for every card whether the page is
in view mode or edit mode. On a 1k roster the JSON blob is
~100KB; with `K` new-model cards on the page that's `K` round
trips to the DB and `K × 100KB` of HTML payload + `K` JS
rebuilds before the page is interactive. Legacy individual /
group cards do none of this — they render a static preview
table from server-computed view rows and ship no roster JSON.

**Layer 3 — Cache-invalidation cadence (new-model only).**
The new-model card edits rules **inline** (Band 1 Links 1-3
save through the same form Submit that drops the edit lock).
The legacy individual / group cards bounce out to the Rule
Builder page, edit, then return — meaning the Instruments
index typically renders with the rules-content-hash stamp
already warm. On the new-model card, the form Submit changes
`rules_json` for the embedded rule set ≥ 50% of the time
operators click Save, so
`session_library.evaluate_session_rule_eligibility(...)`
misses cache on the post-Save redirect and pays the full
engine cost again. Even a no-op Save would stay warm only if
the rules-content-hash comparison is bit-stable across the
round trip (worth verifying; see Rec E).

**Numerical sketch** on a 1k × 1k roster, `K` = number of
new-model cards on the page, ignoring the per-stage constant:

| Stage | Legacy (individual/group cards) | New-model cards |
|---|---|---|
| Server: engine eval per card | hot path, ~0ms (cache hit common) | cold after every rule edit, ~1-3s |
| Server: per-card roster SELECT + serialise | none | `K × ~50ms` + `K × 100KB` HTML |
| Network / HTML size | small | + `K × 100KB` |
| Client on-load: rebuild preview | none | `K` rebuilds against parsed JSON |

The Layer 1 cost is the headline number, but Layers 2-3 are
why the new-model card feels slower on top of an already-slow
engine. Layer 2 in particular grows linearly with the
number of new-model cards on the page, so it gets worse as
operators add instruments — exactly the wrong direction once
new-model takes over from the legacy cards.

### Recommendations

Sequenced from smallest lift to biggest payoff, framed against
the new-model card's actual needs.

#### Rec A — Drop the per-instrument eligible-pair count from the index render *(S)* — shipped 2026-05-24 (PR #1393, conditional-skip flavour)

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

#### Rec D — De-duplicate per-new-model-card roster work *(S-M)*

Layers 2 of the cost breakdown above is purely incidental:
every new-model card on the page re-fetches and re-ships the
same active-reviewee roster. Three sub-recs in increasing
order of payoff and effort:

- **D1: Single roster query per render — shipped 2026-05-24 (PR #1393).** Lift the
  `SELECT * FROM reviewees WHERE session_id=? AND status='active'`
  out of `_new_model_band2_state`
  (`app/web/views/_instruments.py:412-419`) into
  `build_instruments_context`, fetch once per request, and
  pass the materialised list (or a mapping by id) into each
  `_new_model_band2_state` call. Server CPU drops from
  `O(K)` queries to `O(1)`; round-trip latency on Save with
  a dozen new-model cards on the page drops by `K × ~50ms`.
  Smallest possible diff — purely a plumbing change in the
  view-shape adapter.

- **D2: Single roster JSON blob per page.** Today each card
  carries its own `data-new-model-band2-roster='…'` attribute
  with the same `K × 100KB` JSON. Lift the JSON onto a single
  page-level `<script type="application/json"
  id="new-model-roster-data">` block keyed by session id;
  rewrite the on-load JS in `instruments_index.html` to read
  from that single block when rebuilding each card's preview.
  HTML payload drops from `K × 100KB` to `1 × 100KB`. The
  on-load JS still iterates `K` cards but parses the JSON
  once. Moderate diff (touch template + the inline JS), but
  the network-time win is linear in `K`.

- **D3: Skip the on-load preview rebuild in view mode.** The
  inline JS loop at `instruments_index.html:2024` —
  `document.querySelectorAll('[data-new-model-band2]').forEach(...newModelRefreshBand2)`
  — unconditionally rebuilds every new-model card's preview
  table on page load. In view mode the server already
  rendered the correct preview table HTML; the JS rebuild
  is a no-op that re-runs filter logic against the roster
  JSON only to produce the same DOM. The card root does not
  currently expose an edit-mode data attribute (the Jinja
  `is_editing` flag drives `data-new-model-band2-editable`
  inside the wrapper, plus `inert aria-hidden="true"` when
  not editing — line 1242). Either add a
  `data-edit-mode="{{ 1 if is_editing else 0 }}"` attribute
  on the card root for the JS to read, or have the loop skip
  cards whose `[data-new-model-band2-editable]` child carries
  `inert`. On a `K`-card page in view mode this removes
  `K` JS rebuilds + the JSON parse entirely; page becomes
  interactive measurably sooner.

D1 is a few lines and worth doing alongside Rec A. D2 + D3
can land together as a follow-up once D1 proves the shape
out.

#### Rec E — Verify Band 1 no-op Save stays cache-warm *(T, safety net)*

If the operator opens the lock, makes no rule changes, and
clicks Save, the post-Save render should hit the
`session_rule_sets.cached_eligibility_stamp` cache. Whether
it actually does depends on whether the rules-content-hash
comparison is bit-stable across the Submit round trip
(JSON key ordering, whitespace, default-value normalisation).
Two parts:

- **Observability.** Add a counter / log line in
  `evaluate_session_rule_eligibility` distinguishing cache
  hit vs miss, and check post-deploy whether no-op Saves on
  the new-model card actually hit. If they don't, the rules
  serialiser is drifting — fix the comparison rather than
  the cache.
- **Drift check in tests.** Add a regression test that opens
  + closes the lock with no field changes and asserts the
  stamp value is unchanged. Cheap insurance against future
  edits to the rule-serialise path silently invalidating
  every no-op Save.

This doesn't fix the lag — it just makes sure operators who
*didn't* edit rules don't accidentally pay the engine cost
they shouldn't. Pair it with Rec A so even rule-edit Saves
return instantly.

### Sequencing

| # | Recommendation | Lift | Layer 1 (engine) | Layer 2 (per-card overhead) | Layer 3 (cache cadence) |
|---|---|---|---|---|---|
| A  | Drop per-instrument eligible-pair count from index render | S | **Cured on Save.** No engine on redirect path. | — | Layer 3 stops mattering on Save. |
| D1 | Single roster query per render | S | — | `K` queries → 1 query | — |
| D2 | Single roster JSON blob per page | S-M | — | `K × 100KB` → `1 × 100KB` payload | — |
| D3 | Skip on-load preview rebuild in view mode | S | — | Removes `K` JS rebuilds in view mode | — |
| B  | `find_first_n_pairs` engine fast path | M | **Cures Refresh.** Typically <100ms. | — | — |
| E  | Verify no-op Save stays cache-warm | T | Belt-and-braces if cache should hit. | — | Confirms warm path actually warm. |
| C  | Single-side predicate indexes (+ roster-upload cache) | L | Brings Rec B's worst case down. | — | — |

**Recommend landing A + D1 together as the first quick win**
— both are small diffs and together they cure the Save lag
that operators notice today (A removes the engine cost on
redirect; D1 removes the duplicated roster query). D2 + D3
are a natural second PR once D1 lands. B then targets Refresh
explicitly. E is a tiny safety-net commit any time. C stays
deferred until pilot rosters expose Rec B's worst case.
