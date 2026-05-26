# Segment 18H — Post-assessment update

> **Created 2026-05-19**, after the 2026-05-19 codebase assessment
> (`guide/codebase_assessment_19may.md`). A holding pen that
> (a) logs the post-assessment fix already shipped and
> (b) collects near-term refinement stubs whose detailed scope is
> drafted when each is picked up — the same shape as Segment 18E.

## Shipped

### Group-scoped instrument config round-trip fix — 2026-05-19

The 19may assessment's bug hunt found one HIGH defect: the
session-config CSV round-trip was broken for group-scoped
instruments. The serialiser (`session_config_io/_serialize.py`)
emits `Instrument.group_kind` verbatim — the runtime column
encoding: boundary codes (`r1`/`r2`/`r3` for reviewee tags,
`p1`/`p2`/`p3` for pair-context tags) or the `both` no-boundary
sentinel. But `_parse_group_kind` (`session_config_io/_apply.py`)
accepted only a `tag_1`/`tag_2`/`tag_3` vocabulary, so importing
any exported config containing a group-scoped instrument raised
`_ParseError`; a hand-authored `tag_N` would be stored verbatim
and then silently dropped by `decode_group_kind`, producing a
group instrument with an empty boundary.

**Fix (PR #1216).** `_parse_group_kind` now validates and
canonicalises the value through the `group_kind` codec
(`decode_group_kind` / `encode_group_kind`) and accepts the
sentinel — matching exactly what the serialiser emits. A
`serialize → apply` round-trip regression test for a group-scoped
instrument was added, and the stale unit tests were corrected to
the real code vocabulary. Suite green (1,912 passed), ruff clean.

### Relationship re-point defunct fix — 2026-05-19

The 19may assessment flagged a **suspected MEDIUM** defunct-safeguard
defect; investigation confirmed it. `update_relationship`
(`relationships.py`) applied the edit's `setattr` *before* calling
the group-response defunct safeguard, and the safeguard
(`responses.py`) read `relationship.reviewer_id` / `reviewee_id`
— i.e. the post-edit values. So re-pointing a relationship to a
different `(reviewer, reviewee)` pair under-defuncted two ways:

- a re-point **plus** a grouping pair-context tag change defuncted
  only the *new* pair, leaving the *old* pair's group-scoped
  `Response` rows mis-attributed;
- a **pure re-point** (no tag-field change) ran no defunct at all,
  even though the relationship's pair-context tags had moved off
  the old pair and onto the new one.

Reachable in the realistic correction path (revert a `ready`
session to `draft`, fix a relationship, re-activate — group
responses survive the revert). Data mis-attribution, not a crash.

**Fix (PR #1218).** `update_relationship` snapshots the pre-edit
pair before `setattr`. The safeguard — renamed
`defunct_group_responses_for_relationship_change` — now takes the
explicit set of affected `(reviewer, reviewee)` pairs (old + new)
and a `repointed` flag; on a re-point it widens the affected
instrument set to every pair-context-boundaried group instrument.
A regression test covers the pure-re-point case (both pairs
defuncted, an unrelated pair on the same instrument untouched).
Suite green (1,913 passed), ruff clean.

## Assessment follow-up findings

### Suspected LOW (`defunct_group_responses_for_tag_change` over-defunct) — closed, not a bug

The 19may assessment's third bug-hunt finding suspected
`defunct_group_responses_for_tag_change` of over-defuncting —
deleting group responses where the reviewee's tag change "does
not actually move it to a different group." Investigated
2026-05-19; **closed as not a defect.**

`changed_tag_fields` only ever contains tags whose value
genuinely changed (the caller diffs old vs new), and the
`affected_instrument_ids` filter selects only instruments whose
decoded boundary uses a changed tag. A group key is a tuple of
boundary-tag values, so a changed boundary tag *always* shifts
the tuple — there is no "collides to the same key" case on a
single reviewee's own tags. The function deletes exactly the
tag-changed reviewee's response copies on exactly the instruments
whose key shifted — the minimal correct set.

The one imprecision was the **docstring**, not the code: the
original wording ("lossless for the reviewer — survives on the
group's other member rows") held only when the old group kept
≥1 other member. Shipped alongside the rename in PR #1219:
`reconcile_group_responses_for_tag_change`
(`app/services/responses.py:585-606`) carries a fresh docstring
that describes the actual delete + re-fan behaviour without the
"lossless" claim.

### Representative-staleness on group join — confirmed and fixed

Investigating the suspected LOW surfaced a *different*, real
defect on the **destination** side of a reviewee tag change.
When a tag change moves a reviewee into an **already-answered**
group, that reviewee's `(reviewer, reviewee)` assignment has no
fanned response copy (its old copy was just — correctly —
defuncted; the new group's answer lives on the *other* members).
`_collapse_group_rows` (`routes_reviewer/_surface.py`) picks the
group's representative as strictly `members[0]` — the lowest
assignment id — with no preference for a member that holds
response data, and the representative's response `cells` are
inherited from that one assignment. So when the relocated
reviewee holds the lowest assignment id in the destination group,
that group renders with **blank inputs** — it looks unanswered —
and the per-group completion rollup, keyed off the same
representative, regresses to incomplete.

**Confirmed 2026-05-19** by reproduction: a group instrument
boundaried on `RevieweeTag1`; reviewer answers Team A and Team B;
moving Carol (lowest assignment id) from Team A into the answered
Team B makes Team B's row render blank — the reviewer's Team B
answer (stored on Dan's row) is no longer surfaced.

The answer data is **not lost** — it survives on the sibling
members — but in the window before the next save the reviewer
sees their answer apparently gone, and the completion rollup
regresses. Severity **LOW–MEDIUM**: a transient display +
completion regression, no data loss.

**Fix (PR #1219).** The root cause is a violated invariant — a
group-scoped instrument keeps *identical* answer copies on every
assignment in a group, and every reader (`_collapse_group_rows`,
`_state_from_assignments`, the extract) trusts that. The
tag-change / re-point safeguards already delete the *stale* copies
of a relocated reviewee/pair but never restored the copies for the
*new* group. Rather than teach each reader to tolerate a violated
invariant, the fix **restores it**: `defunct_group_responses_for_
tag_change` / `_for_relationship_change` are renamed
`reconcile_group_responses_for_*` and now, after deleting the
stale rows, **re-fan** — a new `_refan_group_responses` helper
copies each relocated assignment's new group's answer from a
sibling member that still holds it (an assignment whose new group
is genuinely unanswered is left empty). All read paths then work
unchanged. A regression test reproduces the original case (Carol
moved into an answered Team B → Team B still surfaces the answer).
Suite green (1,914 passed), ruff clean.

## Stubs

> Sketch-level only — each Part's detailed PR breakdown is drafted
> when it is picked up. Listed here so the refinements are tracked
> rather than lost.

### Part 1 — Rule builder refinement — shipped 2026-05-19

A polish + ergonomics pass on the **Rule Builder page**
(`/operator/sessions/{id}/assignments/rule-based-editor`),
driven incrementally from operator feedback rather than a
single up-front catalogue. Shipped so far:

- **Editor row layout (PR #1220).** The `field` / `operator` /
  `operand` controls of MATCH / FILTER rules, and the `scope` /
  `strategy` / `seed` controls of QUOTA rules, now sit side by
  side in a three-column grid (one-third width each) instead of
  stacking full-width — halving each rule row's vertical
  footprint.
- **Include / exclude as checkboxes (PR #1221).** The MATCH /
  FILTER kind dropdown is replaced by a pair of mutually
  exclusive `include` / `exclude pairs where` checkboxes after
  the `enabled` checkbox; ticking one unticks the other, with
  `include` ticked by default.

Both the server-rendered `_rule_builder_card.html` and the
client-side row builder / serialiser in
`_rule_based_editor_js.html` were updated together.

**Further refinements: closed defunct by Segment 18J Wave 4
(Gap 7).** The remaining open items below were predicated on
the Rule Builder child page + the RuleSet library tier
continuing to exist. Segment 18J Wave 4 retires both — Band 1's
inline editor on the new-model card becomes the canonical
authoring surface; the personal library, seeded RuleSets, the
"Save to / Add from library" affordances, the Available
RuleSets sidebar on the Instruments page, `library_origin_id`
provenance, and the Rule Builder child page itself all retire
together (`guide/archive/new_model_instruments_outstanding.md`
Gap 7; `guide/instrument_builder.md` Part 1b).

- ~~Seeded-vs-personal library affordances~~ — defunct (no
  library tier to distinguish).
- ~~Validation feedback~~ — defunct as Rule Builder polish;
  the operator's need for inline rule-edit validation transfers
  to Band 1's inline editor on the new-model card and is
  picked up as part of 18J Wave 4 rather than as Part 1
  follow-on.
- ~~RuleSet read-back~~ — defunct (the Rule Builder page is
  retired; per-instrument Band 1 already surfaces the pinned
  rules inline on the new-model card).

With these closed, **Part 1 is complete** — no further Rule
Builder polish is on the roadmap.

### Part 2 — Enhanced response export — shipped 2026-05-20

Scoped at pickup as a **per-instrument response export** instead
of the §22 anchor's "wide / pivoted layout" direction (rejected
on tradeoff grounds — wide is the *report* shape; long stays the
analysis baseline). The Zip-all bundle now contains one
``{code}_instrument_{n}.csv`` per instrument alongside the
unified ``responses.csv``:

- Same 21-column long-format shape as `responses.csv`, so an
  analyst can concatenate the per-instrument files and
  reconstruct the unified file.
- Single-instrument preamble (the instrument's field
  dictionary); positional `instrument_{n}` naming matches the
  unified file's vocabulary.
- Sorted ``(RevieweeName → ReviewerEmail → field.order)`` — the
  reviewee-centric reading order. Group-scoped instruments
  collapse the fan-out and post-sort by composed group identity
  so each group's rows cluster.

The unified `responses.csv` stays unchanged (cross-instrument
analyst file, reviewer-first sort). Per-cell aggregate
alternatives ("one row per reviewee with averaged ratings") were
considered and rejected as lossy and downstream's job.

Implementation: factored a `_response_row_tuple` helper out of
`serialize_responses`; new `serialize_responses_for_instrument`
shares it. Wired into `zip_bundle.py`; contract documented in
`spec/csv_contracts.md` §2.7. The bundle's
``session.bundle_extracted`` audit `counts` envelope gains a
single ``instrument_files`` key (the per-instrument file count)
so the envelope doesn't balloon by roster /  instrument size.

### Part 3 — Entity stats export — shipped 2026-05-19

> Redefined at pickup. The original Part 3 sketch was a
> session-level *metadata* export; the operator instead asked for
> per-entity **activity stats** CSVs. The metadata-export idea is
> not currently planned.

Two new analysis-facing CSVs — a Reviewer stats file and a
Reviewee stats file — bundled into the Zip-all download
(`build_session_bundle`). They are **bundle-only**: deliberately
not offered as individual downloads and with no importer, because
the round-trippable Reviewers / Reviewees CSVs keep that role and
adding stats columns to them would break the importer contract.

Each file is the plain roster shape plus aggregate
response-activity columns, every metric reported as a **Draft /
Submitted** pair (`submitted_at` unset vs set):

- Reviewer stats — reviewees reviewed, fields answered, required
  fields answered, total char count of `String`-typed responses.
- Reviewee stats — reviewers engaged, plus the same three field /
  char metrics.

Only responses with a non-empty value count. Group-scoped
instruments' fanned-out answers count once per group for the
field / char metrics on the reviewer side; both member reviewees
are still credited as reviewed. New module
`app/services/extracts/entity_stats_extract.py` (`build_entity_stats`),
wired into `zip_bundle.py`; contract documented in
`spec/csv_contracts.md` §2.6.

## Doc impact

When Parts ship:

- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.
- Per-Part spec docs as the scope settles —
  `spec/rule_based_assignment.md` (Part 1),
  `spec/csv_contracts.md` (Parts 2 / 3).
