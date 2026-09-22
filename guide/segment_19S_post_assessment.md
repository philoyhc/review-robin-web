# Segment 19S — the post-assessment register

**Opened:** 2026-09-22 · **Theme:** one home for what the end-of-window
reads surfaced and nothing else owns · **Related:**
`guide/codebase_assessment_22sep.md`, `guide/codex_assessment_21sep.md`

**A register, not a queue.** Entries are **logged, not scheduled**. Each
one names what was surfaced, points at the evidence rather than copying
it, and carries the trigger that would promote it to a built item. An
entry that is never promoted is not a failure of this file; losing the
finding would have been.

**Items close independently.** A promoted entry gets the full shape at
`###` level with its own `### Doc impact` / `### Status`, as in 19R —
so there is **no segment-level `## Doc impact`**, and
`python3 tools/close_check.py 19S.<n>` reads that item's. `Semantics`,
`Blast radius` and a `PR ladder` are absent rather than blank because
each belongs to a promoted item and is measured then, not guessed now.

**Entry tags are stable.** `E1`–`E8` never renumber; a promoted entry
keeps its tag and gains an item number beside it.

---

## Opportunity

Two independent reads closed the 19M–19R window:
`guide/codebase_assessment_22sep.md` and, from a fresh context,
`guide/codex_assessment_21sep.md`. Between them they surfaced seven
things that are **real, evidenced, and homeless** — not defects (there
are no known open bugs at `ed8a69e7`), not blocked work (that is
`guide/post_azure_todo_checklist.md`), not deferred scope (that is
`guide/deferred_consolidated.md`), and not the measured performance
candidates (those live with their measurements in
`guide/app_responsiveness.md`).

**An eighth arrived at 19R's own close** — not from either read, but
from the `spec-writer` pass that close is required to run, which
re-found two divergences 19R had recorded and deliberately not fixed.
Their only record was about to archive with the plan, which is the
argument for this file in one move.

Homeless findings have been lost here before. 19O opened its Item 7
register precisely because three findings had already been lost to a
`Status` compaction, and 19R's Item 6 found nine wrong passages in six
files describing one rule. The failure mode is not that a finding is
rejected; it is that nobody decides, and the only record of it archives
with a dated snapshot.

## Decision

**A register whose entries are explicitly unscheduled**, each with its
evidence cited by pointer and its own promotion trigger. Promotion is
the author's call against that trigger.

Both reads warned against the obvious alternative — **opening items
now** — and that is what is rejected. The codex read puts it directly:
*a measurement is not automatically a backlog item*, and *do not add
another item merely because the file is already open*. 19R was closed
the same day for being exactly that kind of container. A register
answers the warning without paying its price: the finding survives, and
nothing is committed to by writing it down.

The second alternative, **filing each entry straight into
`guide/deferred_consolidated.md`**, is rejected because that ledger is
for *scoped* work with a lift trigger. Most entries below are not
scoped and two (E5, E7) have no design at all, so recording them as
deferred scope would overstate how well they are understood.

## Judgment calls — decided

- **A register, not rows in `guide/todo_master.md`** (2026-09-22) —
  that file's `## Upcoming` is a committed sequence, and committing is
  the thing both reads asked not to do.
- **Evidence by pointer, never copied** (2026-09-22) — a copied figure
  is a second place to go stale, which is E5's whole subject.
- **Entries keep their tag on promotion** (2026-09-22) — so an entry
  referenced from a `Status` block or a PR body does not have to be
  chased when the list grows.
- **Seven at open is what the two reads carried, not a target**
  (2026-09-22) — a further entry arriving from a later read is
  admitted, and E8 arrived from this close's own `spec-writer` pass
  before the file was first committed; work arriving from anywhere else
  gets its own bounded plan, which is 19R's closing lesson.

## Entries

### E1 — Prepare inserts one ORM object per pair

20 s at the 200 × 200 / 80,000-row bench, 5.7 s at half the roster, so
it is climbing steeply — and it is a click with no feedback, on the
critical path of every session. Evidence:
`guide/app_responsiveness.md` Finding 4.

**The two reads disagree on timing, not on substance.**
`guide/codebase_assessment_22sep.md` §8 ranks it move 2 — *fix Prepare
before the pilot, not after* — while `guide/codex_assessment_21sep.md`
§8 says keep it a measured candidate and promote it only when pilot
scale crosses its trigger. **Trigger:** the author choosing between
those two readings, or a known pilot roster size.

### E2 — the bench headline is a dated fact, not a standing one

`guide/app_responsiveness.md` is written around *it was not a database
problem* — SQL under 9% of any slow page. 19R.3 moved the counting into
SQL and Invitations is now ~84% SQL, so the headline inverted inside
the same window that wrote it. `guide/codebase_assessment_22sep.md` §8
move 3: re-take the bench, not the code, and ask the next performance
question of real data. **Trigger:** deployment concluded with
representative data — the synthetic bench cannot answer it.

### E3 — the ≥1,000 LOC watchlist lives only in a document that archives

Twelve modules ≥ 1,000 LOC, and `guide/codebase_assessment_22sep.md`
§9 carries the tripwires: `app/services/validation.py` at 1,300 (+346)
is the new largest with no queued split, `app/services/session_lifecycle.py`
at 1,107 is **93 LOC** from its ~1,200 tripwire, and
`app/web/routes_operator/_instruments.py` at 1,279 is **121** from
~1,400. `app/services/csv_imports.py`, `app/web/routes_operator/_operations.py`
and `app/services/instruments/_band1.py` (+363, the window's largest
mover) are on the same list.

A dated snapshot retires to `guide/archive/` when the next one
supersedes it, so those numbers leave live prose while the modules stay.
`guide/codex_assessment_21sep.md` §8 move 4 offers a rule instead — let
the next failure choose the seam — which is a rule, not a record. **The
entry's question is whether the tripwires need a live home**, not
whether to split anything. **Trigger:** a module crossing its tripwire,
or the next assessment, whichever comes first.

### E4 — the hand-maintained indexes drift, and nothing gates them

`guide/codebase_assessment_22sep.md` §5: `docs/status.md`'s summary
line ran **two items behind**, missed by two consecutive closes and
caught by a cold read.

**Found a second time at 19R's close, in a second index.**
`guide/todo_master.md` still carried 19R under `## Upcoming` as an open
segment with Item 5 in progress — four items stale — and retiring that
row showed `## Done` has **no entry for 19P or 19Q**, both closed and
archived days earlier, and that its own sort rule (*by first PR number
ascending*) has drifted far enough that 19I (#2230) sits below 19O
(#2382). The mechanical gates cannot see any of it: they check that a
path resolves and a `§N` exists, not whether a count is current.

**The two `guide/todo_master.md` gaps are fixed** (2026-09-22, on the
author's instruction, in their own slice rather than in the close):
19P and 19Q have `## Done` entries written from their archived plans,
and the section is sorted — nine blocks relocated, fifteen at a new
index once the knock-on is counted, **fourteen of the fifteen
byte-identical** and the fifteenth deliberately edited; the rule's own
blind spot is now stated where the rule lives, since a heading declaring
no PR cannot be placed by it. **That summary was wrong in its first
draft** and is itself an E5 instance: it claimed nine and claimed every
moved block unchanged, from a check run mid-edit whose own output had
named the exception. The fix also found a
**third** E4 instance a line from the second: 19O's entry ended *"the
segment stays open"* under a heading reading `✅ closed`.

**The entry stays open, because the gate does not exist.** Three
instances in two indexes were each caught by a person reading, and a
gate here would have to judge whether prose is *current* — which
`constitution.md` VI retires rather than mechanises badly, exactly why
19R.7 retired a standing rule nobody checked. **Trigger:** a fourth
instance, or the author asking for a gate.

### E5 — the prose about the work is wrong more often than the work

Across 19R alone: nine wrong descriptions of one rule in six files
(19R.6); a blast-radius grep whose scope excluded the directories the
item was about, twice (19R.6); a denominator computed with
`--since=<bare date>`, taking its time-of-day from the current clock —
the exact bug `tools/pace_audit.py` has a helper to prevent (19R.7);
and a close claiming a cold read had run *before* the change, in the
same commit whose body said it was still running (19R.8). Every one was
caught by a reader or a gate, none by the author of the prose.

`guide/codebase_assessment_22sep.md` §5 logs it with *no plan, and I
am not sure what one would look like*; `guide/codex_assessment_21sep.md`
§5 reads the same pattern as claims written faster than their premises
are verified. **Logged with no design. Trigger:** a proposal specific
enough to test.

### E6 — a new guard has no evidence bar

`guide/codex_assessment_21sep.md` §5 proposes three pieces of evidence
before a guard is called complete: **the fixture reaches the case, a
mutation of the protected property fails, and the recognizer is tested
outside its current production examples.**

19R produced four counterexamples, each a guard that passed while
seeing less than it claimed — the upload-route recognizer wrong three
times (19R.4) and the no-duplicate query guard passing having
recognised nothing (19R.5). Candidate home: `CLAUDE.md` "Where work
runs", or `constitution.md`. **Trigger:** the author's call, weighed
against 19R.7's lesson that a standing rule nothing checks is worse
than no rule.

### E7 — plans overrun their own length budget

`guide/codex_assessment_21sep.md` §7: 19R's plan closed at **1,541
lines for eight items**, against the `segment-plan` skill's ~120 per
item and ~250 per segment, and doc/spec/guide now totals 170,163 lines.
The skill already names the cause — `Status` and answered open
questions growing after the thinking is done — and already sets the
budget and the compaction rule
(`.claude/skills/segment-plan/SKILL.md`, "Length"). What is missing is
anything that notices, and 19R's items each compacted at their own
close and still landed here. **This file opens just past that ~250
itself**, on eight entries and no `Status` at all — so the budget's
stated cause is not what got it there, which is a data point for
whatever E7 becomes. **Trigger:** same as E4, and it shares E4's
objection — measuring this means judging prose.

### E8 — two findings 19R recorded, did not fix, and has now archived

19R Item 4 closed with *two findings recorded, not fixed*, both
pre-existing and deliberately not bundled into a defect fix. Re-found
independently by this close's `spec-writer` pass, and verified here:

- **`spec/csv_contracts.md` §3.2 documents a signature the code does not
  have.** The spec spells
  `parse_relationship_csv(content, *, reviewer_emails, reviewee_identifiers)`;
  `app/services/relationships.py:49` takes
  `(content, *, reviewers: list[Reviewer], reviewees: list[Reviewee])` —
  different names *and* different types, strings against ORM rows. A
  caller written to the spec fails. **Deciding it is the usual
  fix-the-code-or-change-the-contract choice**, which is the author's,
  not a close's (`rrw_sdd_in_practice.md` §4).
- **`_rehydrate.rehydrate_commit` is invisible to 19R.4's upload gate.**
  That gate asks *does this endpoint take an upload*, not *does it save
  a roster*, so the rehydrate path is correct today and ungated —
  recorded there as "its own item".

**The entry is the archiving, not the two findings.** Both were properly
recorded; the record just left live prose, and
`guide/README.md` names `findings_<YYYY-MM-DD>_<scope>.md` for exactly
this case. **Trigger:** none needed for the first — it is a one-line
adjudication whenever the author reaches it; the second is a bounded
item whenever the gate is next touched.

## Open questions

- Does E1 follow the 22 September read (fix before the pilot) or the
  Codex read (wait for pilot scale)? **Decided by:** the author.
- Do E3's tripwires need a live home, or does `guide/codex_assessment_21sep.md`
  §8 move 4's rule replace them? **Decided by:** the author, or the
  first module to cross one.
- Does E8's first half get a `findings_<date>_<scope>.md` file of its
  own, or is an entry here enough? **Decided by:** the author — the
  two forms differ in who is expected to read them.
- Is a register that never promotes an entry still doing its job?
  **Decided by:** this segment's own close, which has to say what became
  of each entry.

## Out of scope

- **Email dispatch.** Nothing sends; Segment 14B owns it, blocked on
  institutional Azure provisioning. Not a finding.
- **Operational risk** — real Easy Auth claims, backup/restore, App
  Insights, Postgres networking, transfer compression
  (`guide/codex_assessment_21sep.md` §6). They need the environment,
  not a plan; `guide/post_azure_todo_checklist.md` owns them.
- **The measured candidates** beyond E1 — page furniture, compression,
  the pair sort key. They stay in `guide/app_responsiveness.md` with
  their measurements, deliberately not promoted into a queue.
- **The projected-floor overrun** (`guide/codebase_assessment_22sep.md`
  §7): the assessment's method reporting on itself, and §7 already says
  the floor is not a forecast.
- **The ⏸ compliance rows** — Rehydrate, blob storage, theming. Each
  has a home (`guide/deferred_consolidated.md`,
  `guide/segment_18Q_blob.md`).
- **Splitting any module.** E3 is about where the tripwires live.

## Definition of done

- Every entry is either promoted to an item, moved to a named home with
  the pointer recorded here, or closed with the reason it was not
  taken — no entry left merely unread.
- Each promoted item carries its own `### Doc impact` and `### Status`.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19S.<n>` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row
