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

The one imprecision is the **docstring**, not the code: "lossless
for the reviewer — survives on the group's other member rows"
holds only when the old group keeps ≥1 other member; if the
reviewee was the sole member, the answer is destroyed — but
correctly, since that group has ceased to exist. A docstring
tweak would make that honest; the behaviour is right.

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

**Fix (PR #1220).** The root cause is a violated invariant — a
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

### Part 1 — Rule builder refinement

Polish + ergonomics pass on the **Rule Builder page**
(`/operator/sessions/{id}/assignments/rule-based-editor`) and the
Rule Based card on the Assignments page. The rule-authoring
surface has accreted across Segment 13A / 13A-1 / 15B / 15C;
this Part is a deliberate work-through of its rough edges —
predicate / quota editor usability, the seeded-vs-personal
library affordances, validation feedback, and how an
operator-authored RuleSet reads back when re-opened.

**Scope: TBD at pickup.** Catalogue the rough edges first; the
Part list follows from that.

### Part 2 — Enhanced response export

Further enhancement of the Responses extract
(`app/services/extracts/responses_extract.py`). Segment 18D
already restructured it for downstream analysis (a per-instrument
preamble, a field dictionary, positional `instrument_{n}`
naming). This Part is the next iteration — candidate directions
to assess at scoping: a wide / pivoted layout option alongside
the current long format, richer per-cell provenance, group-scoped
instrument representation, and export-time filtering. The §22
functional-spec line "long-format and wide-format export
options" is the anchor.

**Scope: TBD at pickup.** Confirm which directions are wanted
before drafting Parts.

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
