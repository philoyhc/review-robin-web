# Codebase assessment — 2026-09-18

**Snapshot:** `0f6ea387` on 2026-09-18, after 19Q Item 2 and the Codex
assessment's own merge. **The Claude Code lineage**, superseding
`guide/archive/codebase_assessment_11sep.md`.

**Read `guide/codex_assessment_18sep.md` first.** It is the cold read, taken
one commit earlier at `5ee6b6be`, and this assessment does not restate it. I
built most of the six days it assesses, so under `constitution.md` III I am
the maker, not a checker: what follows is deliberately the two things a maker
can supply that a cold reader cannot — a re-measurement of the checker's
numbers, and an account of where the build's own instruments were trusted
further than they earned.

## 1. Codex's numbers, re-measured

Every structural figure in `guide/codex_assessment_18sep.md` reproduces:

| Claim | Re-measured | Verdict |
| --- | --- | --- |
| 4,384 passed, 16 skipped, no xfails | same, `node` present so the inline-script test ran | ✓ |
| 188 routed endpoints | 188 | ✓ |
| 77 migrations | 77 | ✓ |
| 6.5% app duplication at ≥10-line blocks | 3,195 / 49,493 | ✓ |
| 13.6% test duplication | 13,167 / 97,169 | ✓ |
| Roster route modules the leading cluster at 34–47% | 47 / 42 / 34 / 34% | ✓ |
| `docs/status.md` still dated 12 September | dated 12 September, 1,264 lines | ✓ |

Its §3–§6 judgments I agree with and will not paraphrase. Its §7 I read
differently; see §3 below.

## 2. The churn instrument cannot report a bad result

Codex could not reproduce the churn measure and, correctly, made **no churn
claim**. It attributed that to its checkout. The cause is worth more than
the omission, because it also governs every future assessment in this
lineage.

`tools/code_metrics.py --churn-only` walks `git log origin/main
--first-parent --merges` and blames each deleted line against its parent.
**The agent sandbox clones shallow.** `git rev-parse
--is-shallow-repository` returned `true`; history reached back six days, to
2026-09-12. In that checkout the tool printed:

```
  all 130 merges on origin/main
  of which younger than 14 days     : 4,778  (100.0%)  <- churn
  in those files at that moment     : 198,085/198,085  (100.0%)
  ratio (churn / baseline)          : 1.0x
```

After `git fetch --unshallow` (one fetch; the walk then takes 1m46s):

```
  all 2,452 merges on origin/main
  of which younger than 14 days     : 58,683  (72.7%)  <- churn
  in those files at that moment     : 1,252,124/1,799,695  (69.6%)
  ratio (churn / baseline)          : 1.0x
```

Three things follow, in increasing order of seriousness.

- **The tool states a falsehood.** "all 130 merges on `origin/main`" — it
  is 130 of 2,452, 5.3%, and the phrasing is the one the docstring chose
  precisely to distinguish a full walk from `--churn-sample`. The tool
  never checks `--is-shallow-repository`.
- **Its components are degenerate, not merely wrong.** `git blame` cannot
  see past the graft, so every line dates to the boundary commit and both
  percentages are forced to 100.0%.
- **Therefore the ratio is pinned at 1.0x by arithmetic.** Numerator and
  denominator are the same forced 100%. In a shallow clone this instrument
  *cannot* return anything but the healthy value. It has no failing state.

And `guide/README.md`'s row for this lineage instructs exactly this
document to "record them every time" and to act "past a threshold — ... a
churn ratio meaningfully above ~1.5x". That threshold is unreachable in the
only environment where the tool is ever run: no workflow in
`.github/workflows/` invokes `code_metrics.py`, and none sets `fetch-depth`,
so it runs in an agent sandbox or nowhere.

The true figure is **72.7% against a 69.6% baseline, ratio 1.0x** — healthy,
and matching the 2026-09-04 baseline. The conclusion was never wrong. That
is the point: the instrument agreed with the truth for six days by
construction rather than by measurement, and nothing in its output invited
doubt at the level an assessment quotes.

This is the same failure mode `CLAUDE.md` already names for
`tests/integration/test_inline_scripts_parse.py` — *"worse than a hard
failure, because a sandbox without the tool reports success rather than an
error"* — and the same one 19O Item 6 and 19Q Item 2 hit repeatedly at the
test level. It is now established at the measurement level too. **The
recurring defect in this repository is not vacuous tests; it is instruments
that answer when they should refuse.**

## 3. Where I read the same evidence differently

Codex's §7 recommends following the compact-at-close rule **more
aggressively**. I have the measurement that says compaction, unaccompanied,
loses findings.

Closing 19Q Item 2 I compacted its `### Status` per the `segment-plan`
skill. Three findings in that block had no other home and were deleted: a
paragraph in `spec/operations_pages.md` wrong in both directions about the
invitation gate, five stale "ready-only" route annotations in
`docs/status.md`, and the open behavior question on State 4Err's Activate
button. They are recovered only because I went looking; they are now 19O
Item 7, with five others.

So the rule as written is right and its failure mode is specific:
**compaction with no register is deletion.** A finding survives a close only
if it lands somewhere a close does not compact —
`guide/deferred_consolidated.md` for scoped work, a standing register for
the rest. Compacting harder without that destination will lose more.

I also read the correction rate differently. Codex reads it as evidence the
cadence outruns what the repository can absorb, and its remedy is to stop
opening refinement segments. The corrections are real and I do not dispute
the count — but of the instances recorded across 19O.4, 19O.6 and 19Q.2,
they cluster in **newly written guards**, not in product code: a byte-shape
regex, a proximity threshold, a hand-maintained census, a vacuous identity
assertion, a mutant surviving on an empty-session fixture. The product
defects the same reads found were fewer and mostly real bugs worth having
caught (the send/table disagreement Codex singles out).

That points somewhere narrower than slowing down: **a new guard is the
highest-risk artifact in a slice, and is the thing that needs the cold
read.** The per-item cadence that landed in #2459 already concentrates the
read where code is; the addition I would make is that a slice whose main
product is a *test* should be read like a slice whose main product is a
route.

## 4. What I would add to Codex's next moves

Its four stand. Two additions, both small and both from §2:

1. **Make `code_metrics.py` refuse rather than answer.** Check
   `git rev-parse --is-shallow-repository`; on `true`, print the remedy
   (`git fetch --unshallow`) and exit non-zero for the churn half, leaving
   duplication — which reads the worktree and is unaffected — to run. One
   guard, and it retires a metric that currently cannot fail.
2. **Move `docs/status.md`'s top-of-file date with the work**, as Codex
   says, and treat its size (1,264 lines, rows through 18 September under a
   12 September heading) as the compaction target in §3's sense: with a
   register to catch what falls out.

I would not schedule anything else from this document. Its own §1 is a
confirmation pass, and a confirmation pass that generates work has
misunderstood its job.

## 5. Bottom line

I agree with Codex's governing recommendation without reservation: close
19Q Item 3, deploy, and let the pilot choose the next work. Nothing I
measured argues against it, and §2 is not a reason to delay a deployment —
it is a reason not to trust a number this lineage was told to quote.

The one thing I would put more weight on than the cold read could: the
repository's verification machinery is now large enough that **its
instruments need the same scepticism as its code, and they are not getting
it from the test suite** — by construction, since a green instrument and a
blind one look identical from outside. Every instance in the last six days
was caught by a person or by deliberately measuring, never by CI. That is
the standing risk, and it is the one that deployment does not reduce.
