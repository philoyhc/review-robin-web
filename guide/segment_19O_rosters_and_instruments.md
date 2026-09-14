# Segment 19O — rosters and instruments

**Opened:** 2026-09-14 · **Theme:** operator-facing gaps on the roster and
instrument setup surfaces · **Related:** `spec/instruments.md`,
`spec/assignments.md`

**Items close independently**, so each carries its own `### Doc impact` and
`### Status`, and there is **no segment-level `## Doc impact`**.
`python3 tools/close_check.py 19O.1` reads Item 1's manifest.

---

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
(`5aa0c9ed`), and `excludeSelfReviews` was pinned `False` **2026-05-26**
(`8f8d336d`) — the same commit that wrote the policy naming the
now-unreachable rule. So the only surviving affordance is post-generation:
materialize every self-review row, then deactivate it. Busywork when the
operator never wanted them.

### Decision

**A per-instrument flag, honored at materialization** — at the point in
`assignments/_generate.py` that already decides `pair_include`. A pair
classified as a self-review is **skipped** rather than written with
`include=False`.

Why this is buildable where the banned flag is not: `_generate.py`
**already computes whole-group `is_self`** before that branch —
`self_review_groups` marks each group whose reviewer is one of its own
reviewees. **Group correctness is free**; nothing new expresses it.

Rejected:

- **Email fields in the picker plus a pair predicate.** Pair-level, so on a
  group-scoped instrument it drops `(R, R)` and leaves the rest — and worse
  than one member short, since `classify_self_review` identifies a
  self-review group *by finding that row*, so the remainder stops counting
  as self-review at all.
- **Restoring `RuleSetOptions.excludeSelfReviews`.** Its two recorded
  hazards belong to the desugar stage: it dropped pairs *before* group
  composition (hence under-counting by one), and it was invisible. The
  first cannot happen here; the second is this item's real work.

### Semantics

- **Default off**, and **takes effect at Generate** — Regenerate is the only
  write site for `Assignment` rows, so ticking the box leaves existing rows
  alone until the next Generate. The card says so.
- **Group mode drops the whole group**, individual mode the pair, both from
  the existing `is_self`.
- **A non-email reviewee identifier is never a self-review**
  (`is_self_review` returns `False` with no `@`), so the flag cannot drop an
  anonymous reviewee's row — the copy says *reviewed is the reviewer*, which
  is identity matching, not name matching.
- **The excluded rows read as excluded** — the live half of the policy's
  objection, since a row never written cannot be inspected or toggled. On
  Assignments → per-instrument status, the **Self review** cell renders
  **"Excluded by rule"** in place of the count pill (author, 2026-09-14).
  Today that cell is a pill of `self_review_total` plus, **only when the
  total is above zero**, the include checkbox — so an instrument with the
  flag set would otherwise read as a bare `0`, indistinguishable from one
  whose roster simply has no self-pairs. The checkbox needs no separate
  suppression: its `> 0` guard already hides it. *None exist* and *none
  kept* are different facts and must not share a rendering.

### Judgment calls — decided

- **Per-instrument, not per-session** (2026-09-14). The rule set and Link 3
  are both per-instrument; a session flag reinstates what 15B retired.
- **A column on `instruments`, not a key in `band1_state`** (2026-09-14).
  `band1_state` is the card's UI scratch JSON; the engine reads columns.
- **The checkbox writes no predicate** (2026-09-14). It is not sugar over a
  rule the operator could have written, so composing one would misdescribe
  it in the readback.

### Blast radius (measured)

Measured 2026-09-14 at `8669849a`, before the first slice.

```
grep -rn "is_self_review(" app/ --include=*.py | grep -v "def " | wc -l      # 10
grep -rn "self_reviews_active" app/ --include=*.py --include=*.html | wc -l  # 21
grep -rln "_link3_\|link3_mode" app/web/templates | wc -l                    # 1
grep -rln -i "self-review\|self_review" spec/ docs/ | wc -l                  # 18
grep -rln "self_review\|self-review" tests/ | wc -l                          # 106
```

Of the 18 spec/docs hits, the three this item commits to are in *Doc
impact*. The 106 test files are the figure to respect: self-review
classification is the engine's most cross-cut invariant, guarded by
`verify_self_review_classification` as a continuous gate.

### PR ladder

1. **Storage + save path.** Column on `instruments` + Alembic migration
   (round-trips on Postgres), written by the Link 3 save path beside
   `set_unit_of_review`. Lands inert.
2. **The control.** Checkbox at the bottom of the Link 3 column, reading and
   writing the column. Still no engine change; the PR body says so.
3. **Honor it at materialization.** The `_generate.py` branch skips instead
   of writing `include=False`. Tests: individual, group, non-email
   identifier, and a regenerate flipping the flag both ways.
4. **Make the exclusion visible** — the "Excluded by rule" cell, per
   *Semantics*.

Rung 3 must not touch `RuleSetOptions`, `_session_rule_set_to_schema` or
`find_sample_in_scope_reviewee`. The three layers stay.

### Definition of done

- A per-instrument flag exists, defaults off, and survives the Alembic
  round-trip on Postgres (`ci-postgres`).
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
  longer names an affordance no operator can reach.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19O.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. ~~**How the excluded rows are shown.**~~ **Answered by the author
   2026-09-14: "Excluded by rule", replacing the count pill.** See
   *Semantics*.
2. **Whether Link 3 is the right home** for a rule that is not itself a
   unit-of-review setting — it sits there because the individual/group noun
   follows that mode. *Decides: the author, on the rung 2 scaffold.*

### Out of scope

- **Adding email to the Link 1 / Link 2 picker vocabulary.** Rejected above
  as a mechanism; out of scope as a change in its own right.
- **Restoring the general Rule Builder.** Retired at Wave 5 Gap 7 with the
  library tier; nothing here argues it back.
- **Changing `RuleSetOptions.excludeSelfReviews`.** The policy stands.

### Doc impact

- `spec/assignments.md` — § *Self-review policy* gains the shortcut as a supported affordance, drops the unreachable Link-rule claim, and corrects `reviewee.email_or_identifier` to `reviewee.email` (Item 1).
- `spec/instruments.md` — the Link 3 / *Unit of review* material gains the control and its interaction with Generate (Item 1).
- `guide/deferred_consolidated.md` — the Part A entry is lifted into this plan and deleted (Item 1).
- `docs/status.md` — row when the item closes (Item 1).
