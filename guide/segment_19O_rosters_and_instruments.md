# Segment 19O — rosters and instruments

**Opened:** 2026-09-14 · **Theme:** operator-facing gaps on the roster and
instrument setup surfaces · **Related:** `spec/instruments.md`,
`spec/assignments.md`

**Items close independently**, so each carries its own `### Doc impact` and
`### Status`, and there is **no segment-level `## Doc impact`**.
`python3 tools/close_check.py 19O.1` reads Item 1's manifest.

---

## Item 2 — The self-review control's heading and live copy

### Opportunity

Item 1's checkbox shipped and the author found two faults on the rendered
page (screenshot, 2026-09-14).

**The copy does not follow the pill.** The label reads *"Exclude if the
**individual** reviewed is the reviewer"* while the Link 3 pill above it
reads **GROUP USING TAGS**. The mode word is rendered server-side from
`_link3_grouped` — the *persisted* `group_kind` — but the pill cycles
client-side in `newModelToggleUnitMode`, which rewrites the pill label, the
builder's dimming and the hidden `link3_mode` input and knows nothing about
the checkbox. So between cycling the pill and saving the card, the control
describes the opposite of what the operator has just selected. Every other
thing the pill governs updates live; this one does not.

**The control has no heading.** It sits under a `.col-divider` with no name,
so what the divider separates is left to inference. Item 1 chose the divider
precisely to say *this is a second thing* — a heading is the other half of
that sentence, and it was not written.

### Decision

**Heading `Self reviews`**, matching the unbold weight of the three Link
labels — the card's bold is reserved for its own title
(`spec/instruments.md` § *Instrument assignment rule + Unit of review*).

**The mode word is rewritten by the pill handler**, from a `data-` attribute
on the label so the two spellings live in one place. Rejected: recomputing
the copy from `link3_mode` on submit (the operator would still read the
wrong sentence while deciding), and dropping the mode word for something
mode-neutral — the author's ruling is that the copy names what is dropped,
and a group and an individual are different things to drop.

**Group copy is the author's wording** (2026-09-14): *"Exclude if the
reviewer is in the group being reviewed"* — not a substitution into the
individual sentence. *The reviewer is in the group* is the actual test on a
grouped instrument, and the Item 1 phrasing (*"the group reviewed is the
reviewer"*) says something that cannot happen.

### Semantics

- **Two whole sentences, not one with a swapped noun.** They differ in
  structure, so the handler swaps the sentence.
- **The `not_set` pill state reads as individual.** `link3_mode` already
  submits `individual` for `not_set`, so the copy follows the value that
  would be saved rather than inventing a third wording.
- **No behavior change.** Copy and a heading; the flag, its storage and its
  effect are Item 1's and untouched.

### Judgment calls — decided

- **Rewritten by the existing Link 3 handler, not a new listener**
  (2026-09-14). That handler already owns every live consequence of the
  pill; a second listener on the same event is a second thing to keep in
  step.

### Blast radius (measured)

Measured 2026-09-14 at `8fc0c172`.

```
grep -c "exclude_self_reviews" app/web/templates/operator/instruments_index.html   # 2
grep -rln "Exclude if the" app/ spec/ tests/ --include=*.py --include=*.html --include=*.md  # 3
```

### Status

**Closed 2026-09-14**, one PR, as planned. Intended versus done:

- **Both faults were as diagnosed**, and the cause of the first was the one
  named: the copy was server-rendered from the persisted `group_kind` while
  the pill cycles client-side.
- **A test of mine passed vacuously and the de-vacuuming exposed a second
  scoping bug.** The first copy assertion read the element's raw markup —
  which carries *both* sentences as `data-copy-*` attributes for the
  handler — so it held in either mode. Narrowed to the span's text, it then
  failed for an unrelated reason: it was reading the **first** instrument
  card on the page rather than this one, the same trap that produced a
  wrong-but-passing assertion in Item 1 rung 2. Every assertion in these
  tests now goes through one `_instrument_card` helper, with the reason in
  its docstring. *Scope first, assert second.*
- **Both fixes are mutation-checked**, each failing exactly the test that
  should catch it.
- **This item created one drift of its own and the close pass caught it.**
  `spec/assignments.md` § *Suppressing self-reviews* quoted the old
  *"individual / group reviewed is the reviewer"* wording — the phrasing
  this item replaced for describing something that cannot happen on a
  grouped instrument. *Doc impact* named only `spec/instruments.md`, so the
  second copy of the label went unedited. It now points at the spelling's
  owner instead of repeating it, which is why it can't drift again.
  **My own check for it was the wrong shape**: a single-line grep, against a
  quote that wraps across two lines.
- **The `_instrument_card` helper was subtly wrong** — its end bound matched
  the card's own `id="instrument-delete-N"` form, truncating the slice
  partway through the card it returns. Harmless for these three assertions
  and wrong for the next one; both bounds now anchor on the card's opening
  `class="card" id="instrument-N"`.

**Follow-up, 2026-09-14** — two behavior improvements the author asked for
after Item 2 merged, logged here rather than as a third item: they are the
same control and the same reasoning, and a plan per two-rule change is the
shape the skill warns against.

- **Hidden while any of the three Links is `Not set`**, and the stored flag
  cleared in that state. An instrument with an unset Link has no settled
  rule to except self-reviews *from*, and a flag left ticked behind a hidden
  control is live at the next Generate while being invisible on the page.
  Hidden as one unit — rule, heading, checkbox — because a lone divider
  under nothing reads as a rendering fault.
- **Cleared when Link 3 moves individual → group.** The two modes except
  different things; a tick agreed against *the individual reviewed is the
  reviewer* must not carry into *the reviewer is in the group being
  reviewed*, which drops every member row of that group. Re-ticking is one
  click; discovering a whole group went missing is not.

Both enforced **server-side on save** (`resolve_exclude_self_reviews`), with
the client clearing the box at the same moment so page and store agree — the
visible half and the durable half, neither alone.

**The reverse transition needs no rule, and the author said why**
(2026-09-14): the Link 3 pill cycles `not_set → individual → group →
not_set`, so it cannot reach individual *from* group without passing through
`not_set` — which hides the control and clears the box on the way past. The
symmetric case is already covered by the first rule, one step earlier.

That makes the cycle's shape load-bearing for the clearing rules'
completeness, so it is now pinned by a test rather than left as a fact
someone has to remember: a cycle that ever allows the direct move needs a
rule in `resolve_exclude_self_reviews`. *I had recorded this as an open
question; it was a question the UI had already answered.*

**The guarantee was partial until the close pass said so.** Session-config
import writes `exclude_self_reviews` straight from the CSV, and the
instrument rows carrying `band1_touched_links` arrive from a different part
of the same bundle — so an import could pair a ticked flag with an unset
Link, which the UI hides while the flag stays live at Generate. Invisible
*and* in force is the one state the hide rule exists to prevent, so the
first rule now runs at the end of the import apply as well
(`clear_unsettled_exclude_self_reviews`), where both halves are finally
visible. A whole-session clone needs no guard: it copies an existing pair
atomically rather than combining independent values.

**And one spec row Item 1 never reached.** `spec/settings_inventory.md`
still called the column *vestigial*, with *"every row is `False`"* — untrue
since rung 1, and directly contradicting `spec/roundtrip_coverage.md`, which
that item *did* correct. The same miss, one file further on: the Doc impact
enumerated the specs the behavior touches, not every spec that describes the
column.

**It broke five of Item 1's tests, and they were right to break.** Their
payload never sent the `*_touched` flags, so those instruments read as
`Not set` on all three Links and the flag now correctly clears. "All" and
"Not set" differ only by that bit, so the fixture had been describing an
unconfigured instrument while claiming to test a configured one. The helper
now sends them, with the reason in its docstring. All three rules are
mutation-checked.

### PR ladder

One PR: heading, both sentences, the handler rewrite, and its tests.

### Definition of done

- The heading `Self reviews` renders above the checkbox.
- Cycling the pill to *Group using tags* rewrites the copy without a save,
  asserted against the handler's own contract.
- A grouped instrument renders the group sentence on load; an individual or
  unset one renders the individual sentence.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19O.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

None.

### Out of scope

- **The Link 3 pill's own three-state cycle.** Unchanged.
- **Whether the control belongs in Link 3 at all.** Settled in Item 1 by the
  author: it is there for space, and the divider plus this heading say so.

### Doc impact

- `spec/instruments.md` — § *Self-review exclusion* gains the heading and both label spellings (Item 2).
- `spec/assignments.md` — § *Suppressing self-reviews* stops quoting the replaced wording and points at the spelling's owner (Item 2).
- `spec/settings_inventory.md` — the `exclude_self_reviews` row stops calling the column vestigial and states the import-time clear (Item 2 follow-up).

## Item 1 — Exclude self-reviews from the Link 3 column

### Opportunity

`spec/assignments.md` § *Self-review policy* names two supported ways to
suppress self-reviews. The first — *"Add a Link 2 (or Link 1) rule like
`reviewee.email IS DIFFERENT FROM reviewer.email`"* — **no operator can
reach.** `views/_instruments.py::new_model_usable_tags` returns
`tag1`/`tag2`/`tag3` for `reviewer` / `reviewee` / `pair_context` and no
email slot; the general Rule Builder that once offered the full grammar is
retired, route and template. The engine accepts `reviewer.email` and
`reviewee.email` (`ALLOWED_PREDICATE_FIELDS`); nothing authors them.
Found by Codex on #2381.

**It was designed away on a premise that no longer holds.** The 13A picker
omitted email deliberately — *"operator-authored rules don't reach for
email comparisons (the engine's `excludeSelfReviews` desugar handles that
case implicitly)"* (`app/web/views/_rule_builder.py`). Both halves then
went a day apart, in opposite directions: the picker retired **2026-05-25**
(`5aa0c9ed`), `excludeSelfReviews` was pinned `False` **2026-05-26**
(`8f8d336d`) — the same commit that wrote the policy naming the
now-unreachable rule. The only surviving affordance is post-generation:
materialize every self-review row, then deactivate it.

**But one objection is live, not archaeological**, and is the real reason
to answer rather than the retired comment above. `_band1.py` enforces it on
every Band 1 save (`:146-167`, and the seed at `:426-440`): *"The
per-instrument Self review toggle on the Assignments page is the sole
include / exclude surface; baking exclusion in at the rule-set level would
silently disable that toggle."*

### Decision

**A per-instrument flag, honored at materialization** — at the point in
`assignments/_generate.py:337-351` that already decides `pair_include`.

Read that branch precisely: `pair_include` is **not a skip**. It is the
value written to `Assignment.include` (`:450`), so today a self-review pair
on a session with `self_reviews_active=False` still gets a row. Honoring
the flag means **omitting the pair from `new_pairs`** — one `continue` —
which is a different edit with a consequence the skip framing hides, and
that consequence is in *Semantics*.

Why this is buildable where the banned flag is not: `_generate.py`
**already computes whole-group `is_self`** before that branch —
`self_review_groups` (`:314-332`) marks each group whose reviewer is one of
its own reviewees, built from the engine's full `result.pairs`. **Group
correctness is free**; nothing new expresses it.

**Answering `_band1.py`.** It is right that silently disabling a working
toggle is a regression. The toggle is not disabled here so much as *made
inapplicable*, and the cell must say so — "Excluded by rule" is the
objection's remedy, not a nicety. **If rung 4 slips, rung 3 must not
land.**

Rejected:

- **Email fields in the picker plus a pair predicate.** Pair-level, so on a
  group-scoped instrument it drops `(R, R)` and leaves the rest — worse than
  one member short, since `classify_self_review` identifies a self-review
  group *by finding that row* (`_self_review.py:122-128`), so the remainder
  stops counting as self-review at all.
- **`RuleSetOptions.excludeSelfReviews`, or the still-live
  `override_exclude_self_reviews` channel** (`_generate.py:304` →
  `engine.py:150-154`, resolving ahead of the pinned option). Both are the
  *desugar* stage, which carries both recorded hazards: it drops pairs
  **before** group composition (under-counting by one) and it is invisible.
  Honoring the flag after the fan-out avoids the first; rung 4 the second.

### Semantics

- **It sits in the Link 3 column for space, not because it belongs to the
  unit of review** (author, 2026-09-14). A **horizontal rule** below the
  Link 3 controls separates them, so the checkbox reads as a second thing
  in the same column rather than a third unit-of-review state. The rule is
  a `base.html` class, not an inline style — the column's existing 1px
  vertical separator (`--border-default`) is the sibling to match.
- **Default off**, and **takes effect at Generate** — Regenerate is the only
  write site for `Assignment` rows, so ticking the box leaves existing rows
  alone until the next Generate. The card says so.
- **Group mode drops the whole group**, individual mode the pair, both from
  the existing `is_self`.
- **Ticking the box after responses exist deletes them.** A pair dropped
  from `new_pairs` lands in `to_delete`, and `_materialise_one_instrument`
  deletes each row's `Response` rows before the row (`:434-438`). This needs
  no new guard: the diff already counts `responses_deleted` (`:369-378`) and
  the Prepare confirm card already spells it out
  (`next_action_card.html:89-97`). Rung 3 asserts it rather than adding to
  it.
- **A non-email reviewee identifier is never a self-review**
  (`is_self_review` returns `False` with no `@`), so the flag cannot drop an
  anonymous reviewee's row — the copy says *reviewed is the reviewer*, which
  is identity matching, not name matching.
- **The excluded rows read as excluded.** On Assignments → per-instrument
  status the **Self review** cell renders **"Excluded by rule"** in place of
  the count pill (author, 2026-09-14). Today it is a pill of
  `self_review_total` plus the include checkbox, the latter gated on
  `> 0` (`session_assignments.html:84-86`) — so a flagged instrument would
  otherwise read as a bare `0`, indistinguishable from a roster with no
  self-pairs. The checkbox needs no separate suppression; its guard already
  hides it. *None exist* and *none kept* must not share a rendering.

### Judgment calls — decided

- **Per-instrument, not per-session** (2026-09-14). The rule set and Link 3
  are both per-instrument; a session flag reinstates what 15B retired.
- **Reuse `SessionRuleSet.exclude_self_reviews`; add no column**
  (2026-09-14, corrected after reading the code). The column already exists
  (`app/db/models/session_rule_set.py:63`, `default=True`), is per-instrument
  in practice — Band 1 auto-manages one rule set per new-model instrument
  (`_band1.py:426`) — and already round-trips through session config IO
  (`_serialize.py:544`, `_apply_rule_set.py:47`) and the by-instrument
  extract (`by_instrument_extract.py:332`). The work is **removing the
  normalization**, not adding storage.
- **The checkbox writes no predicate** (2026-09-14). It is not sugar over a
  rule the operator could have written, so composing one would misdescribe
  it in the readback.
- **Turning the flag ON materializes an empty rule set; turning it OFF with
  no rule set is a no-op** (2026-09-14, rung 2). Band 1 only creates a
  `SessionRuleSet` once a Link 1 / Link 2 rule exists, so an untouched
  instrument has nowhere to store the flag. An empty rule set is
  output-identical to the synthetic Full Matrix schema, so this costs no
  assignment row — verified: the `revision_seed` difference is read only
  inside the quota-rule loop, which an empty rule set never enters. Not
  creating a row for an OFF write keeps untouched instruments clean, since
  `False` is the default and records nothing.
- **The checkbox label follows the Link 3 mode** (2026-09-14, rung 2):
  "individual" or "group", so the copy names what would actually be
  dropped.

### Blast radius (measured)

Measured 2026-09-14 at `8669849a`, before the first slice.

```
grep -rn "is_self_review(" app/ --include=*.py | grep -v "def " | wc -l      # 9
grep -rn "self_reviews_active" app/ --include=*.py --include=*.html | wc -l  # 21
grep -rln "_link3_\|link3_mode" app/web/templates | wc -l                    # 1
grep -rln -i "self-review\|self_review" spec/ docs/ | wc -l                  # 18
grep -rln "self_review\|self-review" tests/ --include=*.py | wc -l          # 51
```

Of the 18 spec/docs hits, the three this item commits to are in *Doc
impact*. The **51** test files are the figure to respect: self-review
classification is the engine's most cross-cut invariant, guarded by
`verify_self_review_classification` as a continuous gate.


*Corrected 2026-09-14 (`spec-writer` on `bb75e366`): first written as 10
and 106. The test command omitted `--include=*.py` and counted 55
`__pycache__/*.pyc` alongside the 51 real files — a guardrail is the wrong
place to overstate by double.*

### Status

**Closed 2026-09-14**, four rungs, four PRs. Intended versus done:

- **The mechanism landed as designed** and its load-bearing claim held under
  verification: `_diff_one_instrument` already computes whole-group `is_self`
  from the engine's full `result.pairs` before the `pair_include` branch, so
  honoring the flag there gives whole-group correctness for free, and a pair
  omitted from `new_pairs` is not re-added downstream.
- **Rung 1 was one deletion, not the two the ladder named, and the second
  would have been a bug.** Storage already existed
  (`SessionRuleSet.exclude_self_reviews`) and was being force-normalized to
  `False` on every Band 1 save — a heal for pre-#1452 rows that migration
  `d2e4f6a8c1b3` had already completed, so the re-write only discarded
  operator intent. But the ladder also said to drop the
  `exclude_self_reviews=False` seed: the mapped column is `default=True`, so
  that would have inverted the default for every new instrument, silent until
  rung 3. The seed stays.
- **Rung 2 found a hole in the storage decision.** Band 1 creates a rule set
  only once a Link rule exists, so an untouched instrument had nowhere to put
  the flag — and is the likeliest to want it. Turning it on materializes an
  empty rule set, verified output-identical to the synthetic Full Matrix
  schema; turning it off with no row is a no-op. Also: `base.html` is a
  generated-tool source, so the new `.col-divider` class desynced
  `tools/theme_*.html`.
- **Rung 4's premise was slightly wrong and the fix is better for it.** The
  plan assumed the Self review count is always `0` when the flag is set.
  Between ticking the box and the next Generate it is not, so the cell reads
  "Excluded by rule" only once the count is actually `0`; a
  flagged-but-not-yet-regenerated instrument keeps its real count and its
  toggle, which are still true and still actionable.
- **`spec/ui_elements.md` added to *Doc impact* at build.** The plan named the
  specs the behavior touches and missed the one the *primitive* touches. At
  close, `spec/roundtrip_coverage.md` joined it for the same reason — the
  column was described there as "vestigial", true until rung 3 made it govern
  generation.
- **The Band 2 preview diverged, was reported, and the author closed it.**
  `find_sample_in_scope_reviewee` built its schema from the live Link 1 /
  Link 2 fields and never read the column, so an instrument with the checkbox
  set could still preview a sample in which the reviewer reviews themselves.
  Found by the close pass and raised rather than fixed, since rung 3's scope
  rule forbids touching that function and closing the gap means deciding what
  the preview is *for*. **Author's ruling 2026-09-14: "the preview should
  follow the rule too."** Implemented the same way the generator does it — by
  filtering the engine's *output*, whole group at a time, never by flipping
  `excludeSelfReviews`, which would drop pairs before group composition is
  known and reintroduce the exact hazard the three layers exist to prevent.
  A grouped instrument whose only group is the reviewer's own now previews
  empty rather than showing a row Generate would not produce. **The first
  implementation keyed the groups wrongly** and the close pass reproduced
  it: it reused this function's reviewee-only boundary list, which is
  correct for the member-id partition and wrong here, so a
  pair-context-only boundary dropped the test to pair level while the
  generator still grouped — the preview offering a teammate Generate was
  about to exclude, which is the same class of divergence the ruling was
  meant to end. Both now call `group_key_for_pair` over the full boundary.
  *Two keyings of one concept is one too many.*

- **Two real defects came from the review bot after the close pass, and
  both were in the mechanism rather than the prose.** *(a)* Self-review
  groups were detected over `result.pairs` — the survivors — so a Link rule
  that filtered the `(R, R)` pair out of the fan-out left the group with no
  self-review marker at all, and the reviewer went on reviewing their own
  group with the checkbox set. Membership is a fact about the **roster**;
  the rules decide only which rows survive. Fixed at the root, which also
  fixes the same blind spot in the pre-existing `self_reviews_active` path.
  *(b)* "Excluded by rule" was driven by configuration alone, so a roster
  with no self-review candidate read as an exclusion that never happened —
  the same ambiguity the cell exists to remove, one step over. It now
  requires evidence (`InstrumentReconcileState.self_reviews_excluded`).
  Also: the dry-run's *eligible* figure and the audit event's pair count
  were still taken from the pre-exclusion fan-out, advertising rows Generate
  would never create.

**The defect pattern, stated because it repeated at every rung:** every error
was in prose *about* the code, never in reading what the code does. A
`server_default` cited on the wrong table, read off a grep hit's neighborhood
instead of its enclosing function. A test-file count doubled by `__pycache__`.
A "lands inert" claim contradicted by this plan's own judgment call two
sections above it. A spec drift reported in the prior session that was not
real. A rule set that could be created with no `.created` audit event. Four
`spec-writer` passes caught them; each was verified at `file:line` before
being fixed. *A row-scoped fix is not a claim-scoped fix.*

### PR ladder

1. **Unpin the existing flag.** No migration: drop the
   `exclude_self_reviews` re-normalization at `_band1.py:146-167` and the
   `exclude_self_reviews=False` seed at `:441`, so the column the model
   already carries stops being forced. Lands inert — nothing writes it yet
   and the engine still ignores it (`_session_rule_set_to_schema` hardcodes
   `excludeSelfReviews=False`). The PR body says what the column now means.
2. **The control.** Horizontal rule below the Link 3 controls, then the
   checkbox beneath it, reading and writing the column. Still no engine
   change; the PR body says so.
3. **Honor it at materialization.** The `_generate.py:337-351` loop omits
   the pair from `new_pairs` instead of writing `include=False`. Tests:
   individual, group, non-email identifier, a regenerate flipping the flag
   both ways, and the `responses_deleted` count on a tick-after-responses.
4. **Make the exclusion visible** — the "Excluded by rule" cell, per
   *Semantics*.

Rung 3 must not touch `RuleSetOptions`, `_session_rule_set_to_schema` or
`find_sample_in_scope_reviewee`. The three layers stay.

### Definition of done

- `SessionRuleSet.exclude_self_reviews` is no longer force-normalized, and
  a Band 1 save round-trips a `True` through config export/import
  unchanged.
- With it set, `replace_assignments` writes **no** self-review row: the
  `(R, R)` pair on an individual-scoped instrument, every member row of the
  group on a group-scoped one.
- `verify_self_review_classification` reports no drift after a regenerate
  with the flag set.
- A reviewee whose identifier is not an email is unaffected, asserted.
- The per-instrument **Self review** cell reads **"Excluded by rule"** when
  the flag is set, and a bare `0` when the roster simply has no self-pairs —
  asserted on both.
- `spec/assignments.md` § *Self-review policy* lists the shortcut and no
  longer names an affordance no operator can reach; its "enforced in three
  layers" paragraph is reconciled with the flag now being honored.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19O.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. ~~**How the excluded rows are shown.**~~ **Answered by the author
   2026-09-14: "Excluded by rule", replacing the count pill.** See
   *Semantics*.
2. ~~**Whether Link 3 is the right home**~~ **Answered by the author
   2026-09-14: yes, purely for space.** It is not a unit-of-review setting
   and is not presented as one — a horizontal rule separates it from the
   Link 3 controls above. See *Semantics*.

### Out of scope

- **Adding email to the Link 1 / Link 2 picker vocabulary.** Rejected above
  as a mechanism; out of scope as a change in its own right.
- **Restoring the general Rule Builder.** Retired at Wave 5 Gap 7 with the
  library tier; nothing here argues it back.
- **Changing `RuleSetOptions.excludeSelfReviews`.** The policy stands.

### Doc impact

- `spec/assignments.md` — § *Self-review policy* gains the shortcut as a supported affordance, drops the unreachable Link-rule claim, and reconciles its "enforced in three layers" paragraph (Item 1).
- `spec/instruments.md` — the Link 3 / *Unit of review* material gains the control and its interaction with Generate (Item 1).
- `spec/ui_elements.md` — §10 gains the `.col-divider` primitive the control is separated by (Item 1).
- `spec/roundtrip_coverage.md` — the `exclude_self_reviews` row stops calling the column vestigial (Item 1).
- `guide/deferred_consolidated.md` — the Part A entry is lifted into this plan and deleted (Item 1).
- `docs/status.md` — row when the item closes (Item 1).
