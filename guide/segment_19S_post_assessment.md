# Segment 19S — the post-assessment register

**Opened:** 2026-09-22 · **Theme:** one home for what the end-of-window
reads surfaced and nothing else owns · **Related:**
`guide/codebase_assessment_22sep.md`, `guide/codex_assessment_21sep.md`

**A register, not a queue.** Entries are **logged, not scheduled**. Each
one names what was surfaced, points at the evidence rather than copying
it, and carries the trigger that would promote it to a built item. An
entry that is never promoted is not a failure of this file; losing the
finding would have been.

**Items close independently**, each with its own `### Doc impact` and
`### Status`, as in 19R — so there is **no segment-level `## Doc
impact`** and `python3 tools/close_check.py 19S.1` reads Item 1's.

**Item 1 is the register itself** (author's framing, 2026-09-22): the
eight entries are one unit of work, closed when every entry has been
promoted, rehomed or closed with its reason. **Items 2–4 are what has
been promoted out of it** so far.

**Entry tags are stable.** `E1`–`E8` never renumber; a promoted entry
keeps its tag and gains the item number beside it — **E4 → Item 2**
(the gateable half), **E1 → Item 3**, **E8's first half → Item 4**.

---

## Item 1 — the register of what the two end-of-window reads surfaced — ✅ **closed 2026-09-22**

### Opportunity

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

### Decision

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

### Judgment calls — decided

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

### Entries

#### E1 — Prepare inserts one ORM object per pair — ➡ **promoted to Item 3, 2026-09-22**

20 s at the 200 × 200 / 80,000-row bench, 5.7 s at half the roster, so
it is climbing steeply — and it is a click with no feedback, on the
critical path of every session. Evidence:
`guide/app_responsiveness.md` Finding 4.

**The two reads disagreed on timing, not on substance**, and the author
ruled by promoting it: `guide/codebase_assessment_22sep.md` §8 ranked it
move 2 (*fix Prepare before the pilot, not after*) against
`guide/codex_assessment_21sep.md` §8 move 3's *hold it as a measured
candidate*. **Item 3** carries the design, the measured blast radius and
the two rungs; this entry is closed as promoted, not as done.

#### E2 — the bench headline is a dated fact, not a standing one — ✅ **closed 2026-09-22**

**Closed by linking, not by writing the caveat** — the caveat was
already there. `guide/app_responsiveness.md` opens on *"this is not a
database problem"* (SQL under 9% of any slow page), and its re-set bench
section, 45 lines down, already said *"The composition has inverted, and
the document's headline with it"* with the figures: **84% of Invitations**
(540 ms of 646 ms) and 83% of Responses, because 19R.3 moved the counting
into SQL. **The entry was the gap between the claim and its own
correction**, not a missing measurement, so the fix is a forward pointer
at the headline. A reader who stops at the opening claim now cannot miss
it.

**The re-take stays owed and unscheduled**, which is what E2 could not
close: `guide/codebase_assessment_22sep.md` §8 move 3 asks the next
performance question of **real** data, and the synthetic bench cannot
answer it. That sits with **E1**'s trigger — deployment with
representative rosters — not with this entry, whose subject was the
stale headline.

#### E3 — the ≥1,000 LOC watchlist lives only in a document that archives — ⬜ **retired 2026-09-22**

**Retired on the author's ruling**: the list *"is not really a tripwire
but just part of the judgment of codebase assessments."* That dissolves
the entry's own question rather than answering it — the entry asked
whether the tripwires need a live home, and the ruling is that they are
not tripwires. A figure that exists to prompt a human reading a
judgement-based document does not need to outlive the document, and
`guide/README.md`'s `codebase_assessment_*` row already says the
quantitative rows are *"reading prompts for a human in a document that
is already judgement-based — deliberately not a CI gate, which is the
form that gets argued with, raised, then disabled."*

**What the ruling gives up, recorded so it is a choice and not an
oversight**: when `guide/codebase_assessment_22sep.md` is superseded,
§9's numbers — `app/services/validation.py` at 1,300,
`app/services/session_lifecycle.py` **93 LOC** from its ~1,200 note,
`app/web/routes_operator/_instruments.py` **121** from ~1,400 — leave
live prose. The next assessment re-measures them from the tree, which is
what makes that acceptable: nothing is lost that a fresh read does not
re-derive. `guide/codex_assessment_21sep.md` §8 move 4's rule — *let the
next failure choose the seam* — is what governs instead.

#### E4 — the hand-maintained indexes drift, and nothing gates them — ✅ **closed 2026-09-22**

**Closed by splitting it**, which is what three instances made possible:
the **gateable** half is **Item 2** below, and the **ungateable** half
already has a live home in `docs/unenforced_conventions.md` §1.5, where
the registry mechanism for *prose that summarises another document* is
recorded as **proposed and rejected** (19G.1). So closing this entry
does not archive the finding — the objection that would otherwise apply
(E3, E8).

**The three instances, all fixed.** `docs/status.md`'s summary line ran
**two items behind**, missed by two consecutive closes and caught by a
cold read (`guide/codebase_assessment_22sep.md` §5). `guide/todo_master.md`
then carried 19R under `## Upcoming` as an open segment with Item 5 in
progress while `## Done` had **no entry for 19P or 19Q**, and its own
sort rule (*by first PR number ascending*) had drifted far enough that
19I (#2230) sat below 19O (#2382) — the tail maintained newest-first
for six consecutive segments. Fixed 2026-09-22: both entries written,
nine blocks relocated, the rule's blind spot stated where the rule
lives. The fix then found the **third**, a line from the second: 19O's
entry ended *"the segment stays open"* under a heading reading
`✅ closed`.

**And the account of that fix was itself wrong** — three figures in
`docs/status.md`, caught by Codex on review and by re-measurement. That
is an **E5** instance, recorded there, and it is why Item 2's definition
of done demands a mutation per check rather than a passing run.

**Pre-16 is legacy and out of scope** (author's ruling, 2026-09-22),
which is what made the entry closable: 34 of the 67 pre-16 archived
plans are not mentioned in `## Done` at all, and without the ruling
"fully current" had no test.

#### E5 — the prose about the work is wrong more often than the work — ➡ **promoted to Item 5, 2026-09-22**

Seven instances across 19R and 2026-09-22, every one caught by a reader,
a gate or a re-measurement rather than by whoever wrote the prose. The
list and its sources stay in `guide/codebase_assessment_22sep.md` §5 and
`guide/codex_assessment_21sep.md` §5; **Item 5** carries what to do about
it.

**The entry is promoted narrower than its title, and the classification
is why.** Against 19G Item 1's taxonomy — which sorts prose drift by
*what the prose disagrees with* — four of the seven already have live
homes (`docs/unenforced_conventions.md` §1.4, §1.5 and §1.6), and the
residue splits: claims that **cite their own command** have something to
compare against, and claims about the **process** do not. Item 5 takes
the first half. The three instances from 2026-09-22 are recorded there
too — including the one committed in the slice that closed E7, and the
one in this segment's own `rehydrate_commit` docstring, caught cold.

#### E6 — a new guard has no evidence bar — ✅ **closed 2026-09-22**

**Rehomed to `docs/unenforced_conventions.md` §1.8**, which is the
register `constitution.md` VI promises for a rule that stays guidance.
The bar is `guide/codex_assessment_21sep.md` §5's three pieces: the
fixture reaches the case, a mutation of the protected property fails,
and the recogniser is exercised outside its production examples.

**Not made a standing rule**, which was the entry's own open question.
A check would have to establish that a *mutation was tried*, and nothing
in the tree records that; the cheap proxy — requiring a commit message
to name the mutations — enforces the mention rather than the mutating,
which is §1.7's disqualifying shape and 19R.7's lesson in one. So it
lives per-item instead, and **Item 2 is the first to carry it**: its
definition of done demands a mutation per check with the four recorded
in `### Status`.

**19R's four counterexamples are recorded in §1.8**, not left in this
entry, so they survive the segment: three wrong upload recognisers
(19R.4) and a query guard that passed having recognised nothing (19R.5).

#### E7 — plans overrun their own length budget — ✅ **closed 2026-09-22**

**Rehomed to `docs/unenforced_conventions.md` §1.9**, with the reason
corrected on the way. This entry had said measuring it *"means judging
prose"*, sharing E4's objection. **That was wrong**: `wc -l` over
`guide/segment_*.md` is a one-line check. Two other things disqualify
it, and §1.9 says so rather than claiming infeasibility — it would be
**red from its first commit**, so it fails §2's bar and would arrive as
a cleanup rather than a guard; and the budget is stated as *"a signal,
not a limit to game"*, where mechanising a signal converts it into a
limit whose cheapest satisfaction is moving the reasoning somewhere the
limit does not look.

**The overruns are recorded there as instances, not as fixed**: 19R at
1,541 lines for eight items, and this file past ~250 with Item 2 at ~160
against ~120 after two trim passes. A register whose own entry overran
its budget is the honest evidence for whatever this becomes.

#### E8 — two findings 19R recorded, did not fix, and has now archived — ✅ **closed 2026-09-22**

Both halves are disposed of, which is what the entry asked for — its
subject was the archiving, not the findings.

- **`spec/csv_contracts.md` §3.2's stale signature → Item 4.** The
  author's ruling: spelling out the section's current behavior is **its
  own investigation**, not the two-line rename it looks like. Reading it
  for that item found why: the prose beside the wrong signature is
  *correct*, and the four per-row rules beside it have never been
  checked against the code at all.
- **`_rehydrate.rehydrate_commit`'s invisibility to 19R.4's upload gate
  → a comment at the code**, on the author's instruction. That endpoint
  writes all three rosters from a *stashed* file set and takes a
  `token`, not an `UploadFile`, so the gate cannot see it — it asks
  *does this take an upload*, not *does this save a roster*. Rather than
  widen the gate, the function now says rehydrate ships **disabled**
  (`rehydrate_enabled: bool = False`) and is unexercised on real data,
  **and why it is correct anyway**: `session_rehydrate` passes
  `field_labels_captured` for all three rosters, so the flag is not what
  makes it safe and turning the flag on would leave a live ungated
  save path rather than introduce a defect.

  **The cold read on this slice caught three false claims in that
  comment's first draft**, and the worst of them is **E5's** own failure
  mode: the sentence *"dropped with a warning nobody surfaces"* was
  copied from the neighbouring `_require_rehydrate_enabled` docstring
  instead of read off the code — which surfaces drops as a counted
  audit figure and a downloadable CSV, as `spec/rehydrate.md` §9 says
  twice. The neighbour had been stale since 19N's own slices 3a/3b
  closed `SC-40`, and is fixed here too, since leaving the source of the
  defect in place while fixing the copy is not a fix. The other two: the
  comment credited the **flag** with the endpoint's correctness, and it
  wrote *"twelve-endpoint matrix"* — a figure
  `tests/integration/test_upload_paths_keep_friendly_labels.py`
  **deliberately refuses to assert**, because *"a figure self-stales"*.

### Open questions

All four answered, collapsed at the close.

- **E1 follows the 22 September read** — promoted to Item 3 rather than
  held as a measured candidate (author, 2026-09-22).
- **E3's tripwires get no live home**: they are not tripwires. Retired
  on the author's ruling that the ≥1,000 LOC list is part of an
  assessment's judgment, with `guide/codex_assessment_21sep.md` §8
  move 4's rule governing instead.
- **E8's first half got an item, not a findings file** — Item 4, on the
  author's ruling that spelling out §3.2's current behavior is its own
  investigation.
- **The register promoted four of eight**, so the question of whether one
  that never promotes is doing its job did not arise. What the close can
  say instead is narrower and more useful: **no entry closed by being
  declared finished** — each was promoted, rehomed to a live register,
  or retired with a reason.

### Status

**Closed 2026-09-22, the day it opened, at eight entries and no
mechanism built.** Intended: one home for what the two end-of-window
reads surfaced, entries logged and explicitly unscheduled. Done: that,
plus **four promotions the register was not expected to produce** —
Items 2–5 all came out of it, so the file that was written to avoid
becoming a queue produced most of the segment's work anyway. The
difference is that each promotion was the author's call against a named
trigger, which is what the register was for.

**Dispositions**, all 2026-09-22: **E2** closed by a pointer (the caveat
was already 45 lines below the claim); **E4** split — gateable half to
Item 2, residue to `docs/unenforced_conventions.md` §1.5; **E6** and
**E7** rehomed to that register as §1.8 and §1.9; **E3** retired as not
a tripwire; **E1**, **E5** and **E8**'s first half promoted to Items 3,
5 and 4; **E8**'s second half answered by a docstring.

Decisions confirmed at build:

- **Rehoming beats gating, where a live register already concedes the
  class.** Three entries (E4's residue, E6, E7) ended in
  `docs/unenforced_conventions.md` §1, which is what
  `constitution.md` VI's list is for. The guard held: nothing was
  rehomed whose answer was not genuinely *deliberately unenforced*.
- **Two entries' stated reasons were wrong, and measurement found both.**
  E7 claimed a length check would mean judging prose — `wc -l` is a
  one-liner, and the real objection is that it would be red from its
  first commit. E5 claimed the commands in a `Blast radius` table were
  not re-runnable — 162 of 171 run exactly as written, and the missing
  piece is the **anchor**, with only 45 of 98 sections stating when they
  were measured. Both corrections are recorded where the claim was made.
- **The register produced three new E5 instances while being worked**, one
  of them in this segment's own `rehydrate_commit` docstring, caught by
  the cold read. They are Item 5's opening evidence, which is a better
  starting position than E5's *"no plan, and I am not sure what one
  would look like."*

**`spec-writer` at this close has nothing to verify**, and that is
recorded rather than performed: Item 1's manifest names
`docs/status.md` and `guide/todo_master.md` and no `spec/` path, because
a register of findings changes no surface contract. The pass is owed by
Items 2–6, each of which names its own.

### Out of scope

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

### Definition of done

- Every entry is either promoted to an item, moved to a named home with
  the pointer recorded here, or closed with the reason it was not
  taken — no entry left merely unread.
- Each promoted item carries its own `### Doc impact` and `### Status`.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19S.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Doc impact

- `docs/status.md` — a row per entry as it is promoted, rehomed or
  closed, and the segment summary line kept current (Item 1).
- `guide/todo_master.md` — the `## Upcoming` queue entry for this
  segment, listing the entries and what each is waiting on (Item 1).


---

## Item 2 — gate the four index invariants a reader keeps catching by hand

### Opportunity

E4 above has the three instances and their dates. What they share is
that no gate could see them: `tests/unit/test_doc_references.py` asks
whether a path resolves and whether a `§N` exists, and nothing asks
whether a count is **current**.

Four of the invariants behind those instances are checkable without
judging prose, need no allowlist, and **all four pass on the current
tree** — which is exactly `docs/unenforced_conventions.md` §2's bar for
a check worth writing. Three of the four also have a demonstrated
instance from this week, which §2's own entries do not.

### Decision

One new module, `tests/unit/test_index_currency.py`, holding four
checks:

- **G1** — every archived plan whose segment number is **≥ 16** has at
  least one `### Segment <id>` heading in `guide/todo_master.md`'s
  `## Done`. *(Would have caught 19P and 19Q.)*
- **G2** — `## Done` headings that declare a PR number run ascending by
  the lowest each declares. *(Would have caught six segments of
  newest-first drift.)*
- **G3** — `docs/status.md`'s `**As of:**` date equals the newest date
  in its project-timeline table. *(Would have caught the summary line
  two items behind.)*
- **G4** — every `**Plan:**` pointer under `## Upcoming` resolves into
  `guide/`, not `guide/archive/`.

**Rejected: spreading them across `tests/unit/test_guide_indexes.py`
and `tests/unit/test_doc_conventions.py`** (three would fit the first,
G3 the second). Neither module's stated subject is *is this
hand-maintained claim current*, so `CLAUDE.md`'s gate list would
describe neither accurately — which is how a check gets lost.

**Rejected: gating the ungateable half.** Whether *"eight items"* or
*"the segment stays open"* is current is prose judgement, and
`docs/unenforced_conventions.md` §1.5 records that mechanism as
proposed and **rejected** at 19G.1. E4's residue stays there.

### Semantics

- **A plan may have several `## Done` headings, and a heading may cover
  several plans.** Measured: id `18R` matches both *Segment 18R* and
  *Segment 18R Part 2*. G1 asks for **at least one**, never exactly one.
- **Pre-16 is out of scope by ruling, as a filter not an allowlist** —
  G1 keys on the leading segment number, so the ruling costs one
  comparison; a list of 67 legacy plans would breach §2's bar.
- **A plan archived unbuilt** would fail G1 while being correct. No
  16+ instance today; the escape belongs in the plan file, not the
  test (Open questions).
- **G2 ties pass** — the comparison is non-strict — and **G2 reads the
  heading only**, so a foreign *"superseded by #NNNN"* in a heading
  would false-fire. **0 instances today**; the convention it assumes is
  that foreign refs sit in the body.
- **G3 takes the maximum row date**, so a row inserted out of order
  cannot hide a stale header; a future-dated row fails, correctly.
- **G4 keys on `**Plan:**` lines only**, because the one archived plan
  cited under `## Upcoming` (19P, as a stub's source) is body prose and
  must stay legal. A **dangling** path is already
  `test_doc_references`'s; G4 catches only the *repointed but still
  queued* case that check cannot see.

### Judgment calls — decided

- **One module, not four tests in two files** (2026-09-22) — the four
  share one subject, and a check filed under someone else's docstring
  is the one nobody re-reads.
- **The legacy ruling is a numeric filter** (2026-09-22) — expressible
  in one comparison, so it costs no allowlist.
- **Each check gets a mutation test** (2026-09-22) — adopting **E6**'s
  proposed bar on the first guard written since it was logged: the
  fixture reaches the case, a mutation of the protected property fails,
  and the recogniser is exercised outside its production examples. E4's
  own fix produced a false verification summary, so a passing run is
  not evidence here.

### Blast radius (measured)

All figures taken 2026-09-22 at `92f7aff`.

| what | count | command |
|---|---|---|
| `## Done` headings | **84** | `awk '/^## Done/{d=1} /^## Upcoming/{d=0} d && /^### /' guide/todo_master.md \| wc -l` |
| of those declaring a PR (G2's subject) | **49** | as above, filtered on `#\d{2,5}` |
| G2 violations today | **0** | the ordering scan in this item's rung 1 |
| archived plans: all eras / ≥ 16 (G1's subject) | **106** / **39**, of which **0** miss a `## Done` heading | `ls guide/archive/segment_*.md`, filtered on the leading number |
| pre-16, excluded by the ruling | **67**, of which **34** are unmentioned in `## Done` | the same scan, filter removed |
| `**Plan:**` pointers under `## Upcoming` (G4's subject) | **3**, all live | `grep -o '\*\*Plan:\*\* `[^`]*`' guide/todo_master.md` |
| archived paths cited under `## Upcoming` in other prose | **1** (19P) | the same region, any backticked `guide/archive/` path |
| `docs/status.md` `As of` vs newest row | equal (both 2026-09-22) | the date scan in rung 1 |
| new production code | **0** | the item adds tests and prose only |

No schema, no migration, no route, no template, no `app/` change.

### PR ladder

1. **Rung 1 — the module.** Lands `tests/unit/test_index_currency.py`
   with the four checks and a mutation test for each. **Must not touch**
   `guide/todo_master.md` or `docs/status.md` content: a check that
   edits its own subject to go green is not a check.
2. **Rung 2 — the doc alignment, and the close.** `CLAUDE.md` and
   `AGENTS.md` name the module in the *"A green `ruff` is not evidence"*
   list; `docs/unenforced_conventions.md` §1.5 gains a line that the
   index-currency half is now enforced, as it already carries for the
   file-level path half; `guide/todo_master.md`'s `## Done` maintenance
   note says the two invariants are checked rather than merely asked
   for. **Must not add checks.**

### Definition of done

- `pytest tests/unit/test_index_currency.py` green, and **each of the
  four fails under a mutation of what it protects** — the four
  mutations recorded in `### Status`.
- G1 **with the pre-16 filter removed** reports the 34 unmentioned
  legacy plans, proving the filter is load-bearing rather than
  decorative.
- `cmp -s CLAUDE.md AGENTS.md` exits 0 and both name the module.
- `pytest -n auto` green and `ruff check .` clean, with `node` present.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19S.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- Where does the escape for a plan **archived unbuilt** live — a marker
  line in the plan file, or a waiver recorded in the closing item's
  `Status`? **Decided by:** the author, or the first such plan.
  Recommendation: a marker in the plan, since §2's bar forbids a list
  inside the test.

### Out of scope

- **Pre-16 `## Done` coverage** — legacy, author's ruling 2026-09-22.
  34 plans unmentioned; the era used grouped headings.
- **Judging whether a summary's content is current** —
  `docs/unenforced_conventions.md` §1.5, mechanism already rejected.
- **`guide/archive/README.md`'s `~Lines` column** — that file says it is
  approximate and not kept in lockstep, so it is not drift.
- **E7's length budget** — same prose-judging objection; it stays an
  entry.

### Doc impact

- `tests/unit/test_index_currency.py` — new module, the four checks and
  their mutation tests (Item 2).
- `CLAUDE.md` — the *"A green `ruff` is not evidence"* list names the
  new module (Item 2).
- `AGENTS.md` — the byte-identical twin of the above (Item 2).
- `docs/unenforced_conventions.md` — §1.5's *"What covers it instead"*
  gains the index-currency half as enforced, mirroring the file-level
  path half it already records (Item 2).
- `guide/todo_master.md` — the `## Done` maintenance note says the
  per-plan entry and the sort are checked (Item 2).
- `docs/status.md` — row when the item lands (Item 2).

---

## Item 3 — Prepare inserts one ORM object per pair

**Promoted from Item 1 entry E1** on the author's ruling, 2026-09-22.

### Opportunity

Prepare (Generate + Validate + Invite) measures **20.0 s** at the bench
— 200 × 200 full matrix, 80,000 rows — and **5.7 s** at half that
roster, so the cost climbs steeply rather than linearly. At the old
1,000 × 1,000 / 200,000-row bench it was **74.8 s of which only 17.4 s
was SQL**: about a minute of Python building ORM objects and the unit of
work flushing them. Evidence: `guide/app_responsiveness.md` Finding 4,
which the 2026-09-21 re-set re-confirmed rather than softened.

A single click that blocks that long with no feedback is
indistinguishable from a hang, and the operator's natural response —
clicking again — is the worst available move. It is on the critical path
of **every** session.

**The two reads disagreed on timing, not substance**, and the author has
ruled by promoting it: `guide/codebase_assessment_22sep.md` §8 ranked it
move 2 (*fix Prepare before the pilot, not after*), while
`guide/codex_assessment_21sep.md` §8 move 3 would have held it as a
measured candidate until pilot scale crossed its trigger.

### Decision

Replace the per-pair `db.add(Assignment(...))` in
`_materialise_one_instrument` (`app/services/assignments/_generate.py`)
with a **Core bulk insert** of the same rows, keeping the `db.flush()`
that follows it. **The precedent is in the same function**: its delete
half already uses bulk Core — `db.execute(delete(Assignment).where(...))`,
PR #1065 — while the insert half stayed ORM.

**Rejected: `bulk_save_objects` / `add_all`.** Both still construct one
Python object per pair, and object construction is what Finding 4
measures; they would cut the unit-of-work overhead and keep the cost.

**Rejected for this item: a progress indicator or a background job.**
Either makes a 20 s wait *legible* rather than shorter, and whether one
is still wanted is not knowable until the insert cost is re-measured.

### Semantics

- **The flush is load-bearing and stays.** `_materialise_one_instrument`
  calls `recompute_self_review_classification` after its insert/delete,
  and `replace_assignments` then runs
  `verify_self_review_classification`, which **re-queries the rows**. A
  Core insert leaves no ORM identity-map entries, so those two passes
  must keep seeing the rows through the flush — the property rung 1
  establishes **before** changing the insert, not after.
- **`include` is per row** (`pair_include` from the diff), so the
  payload is a list of dicts with per-row values, not one shared
  default. `created_by_mode` likewise carries the enum's value per row.
- **An empty `diff.to_insert` must issue no statement.** A Core
  `insert()` handed an empty list is an error on some dialects rather
  than a no-op.
- **Both dialects.** The bench is Postgres and the suite is SQLite;
  executemany behaves on both, but `rowcount` does not, so any count the
  audit event reports comes from the payload length — the diff already
  has it, computed before the insert either way.
- **The audit envelope is unchanged.** `counts` comes from the diff, not
  from the insert's return.

### Judgment calls — decided

- **Core `insert()` over `bulk_save_objects`** (2026-09-22) — the
  measured cost is object construction, not only the unit of work.
- **The item is the insert, not Prepare** (2026-09-22) — Validate and
  Invite are separately measured and untouched, so a Prepare figure that
  improves by less than the insert's share is the expected outcome, not
  a miss.
- **No progress UI here** (2026-09-22) — making a wait legible is a
  different change from making it shorter, and the second may remove the
  need for the first.

### Blast radius (measured)

Taken 2026-09-22 at `92f7aff`.

| what | count | command |
|---|---|---|
| the insert site | **1** | `grep -rn "Assignment(" app/ --include='*.py'` — 2 hits, the other is the model class |
| `_generate.py` | **1,119** lines | `wc -l app/services/assignments/_generate.py` |
| call sites of `replace_assignments` in `app/` | **5** | `grep -rn "replace_assignments(" app/ --include='*.py' \| wc -l` |
| modules naming it | **11** | `grep -rln "replace_assignments" app/ --include='*.py'` |
| test files exercising it | **32** | `grep -rln "replace_assignments" tests/ \| wc -l` |
| schema change | **none** | the columns are untouched; no migration |

**The bench may not be re-takeable here.** `pg_isready` in the build
container answers *no response* on 5432 (the `psql` client is present,
a running cluster is not), and `tools/bench_roster_scale.py` refuses any
non-loopback `DATABASE_URL` by design. Rung 2 says what to do about
that rather than assuming a figure.

### PR ladder

1. **Rung 1 — the bulk insert, flush property first.** Lands a test
   that the post-insert self-review verify pass sees every inserted row,
   *then* the Core insert under it. **Must not touch** Validate, Invite,
   or the diff computation.
2. **Rung 2 — re-take Finding 4, or disclose that it could not be
   re-taken.** `guide/app_responsiveness.md` Finding 4 gains the
   post-fix figure beside its 20.0 s; if no loopback Postgres is
   available, the item's `Status` says so and names the dev slot, rather
   than quoting an unmeasured improvement. **Must not change code.**

### Definition of done

- The self-review verify pass is covered by a test that **fails** if the
  inserted rows are invisible to it — demonstrated by a mutation, per
  `docs/unenforced_conventions.md` §1.8.
- `diff.to_insert` empty issues no insert statement, asserted.
- Prepare re-measured at 200 × 200 and recorded in Finding 4 — **or**
  `### Status` states that no cluster was available and the figure is
  owed from the dev slot.
- `pytest -n auto` green and `ruff check .` clean, with `node` present.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19S.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- Do either of the self-review passes rely on the ORM identity map
  rather than on the flush? **Decided by:** rung 1's test, written
  before the insert changes.

### Out of scope

- **Progress feedback or a background job for Prepare** — a different
  change, and possibly unnecessary after this one.
- **Validate and Invite**, Prepare's other two phases.
- **The other measured candidates** in `guide/app_responsiveness.md`
  (compression, the pair sort key, page furniture). They stay
  candidates.

### Doc impact

- `guide/app_responsiveness.md` — Finding 4 gains the post-fix figure,
  or the disclosure that it could not be re-taken here (Item 3).
- `docs/status.md` — row when the item lands (Item 3).

---

## Item 4 — spell out what `spec/csv_contracts.md` §3.2 actually describes

**Promoted from Item 1 entry E8's first half** on the author's ruling,
2026-09-22: this is **its own investigation**, not a two-line fix.

### Opportunity

19R Item 4 recorded, and 19R's closing `spec-writer` pass independently
re-found, that §3.2 opens on a signature the code does not have —
`parse_relationship_csv(content, *, reviewer_emails, reviewee_identifiers)`
against `app/services/relationships.py:49`'s
`(content, *, reviewers: list[Reviewer], reviewees: list[Reviewee])`.
Different names **and** different types, strings against ORM rows, so a
caller written to the spec raises `TypeError`.

**Reading it more closely is what made this an investigation rather than
a rename.** The prose beside that signature — *"resolves the two FK
columns against the already-loaded session rosters"* — is **consistent
with the code**, which does take loaded rosters. So the section is not
simply wrong: its signature line is stale while its description is
right, and nobody has checked the **four per-row rules** in its table,
the Save paragraph, or the `ParseResult` shape against the code at all.
Fixing the visible line would close the cheapest divergence and leave
the unexamined ones — which is exactly the shape 19R Item 6 found
**nine** times in six files.

### Decision

**Write down what the code does, first; adjudicate after.** The
deliverable of rung 1 is the current behavior of the Relationships
import path, stated per question, with the code location that answers
it. Only then does each divergence get a fix-the-code-or-change-the-
contract call, which is the author's under `rrw_sdd_in_practice.md` §4.

**Rejected: correcting the signature names now.** It would retire the
one divergence a reader can see for free, and leave a section whose
remaining claims have never been checked — while making the section
*look* freshly verified, which is worse than leaving it visibly stale.

### Semantics — the questions rung 1 must answer

Each needs the code's answer and the line that gives it, not a
restatement of the spec:

- What the two FK columns resolve **against**, and whether resolution is
  by email / identifier string or by roster row.
- An **unknown** reviewer or reviewee value.
- A **blank** cell, and a whitespace-only cell.
- A **duplicate** pair within one file — the table says the second
  occurrence is rejected; which one survives, and is the rejection
  reported per row?
- A **case difference**, against `normalize_email`'s `str.lower` fold
  (19N Item 2) rather than against a casefold assumption.
- A row naming a reviewer or reviewee that exists but is **`inactive`**.
- The `Status` column's accepted values, against `ROSTER_STATUSES` /
  `normalise_status` rather than against the table's *"lowercase"*
  claim.
- What the caller receives: the `ParseResult` shape — defined in
  `app/services/csv_imports.py`, **not** in `relationships.py` — and
  which errors are per-row against fatal.

### Judgment calls — decided

- **Behavior first, adjudication second** (2026-09-22) — the author's
  framing, and the reason the item exists instead of a patch.
- **The register entry stays closed** (2026-09-22) — E8 is disposed of
  by this item plus the rehydrate comment; a finding promoted to an item
  does not need to stay open in two places.

### Blast radius (measured)

Taken 2026-09-22 at `92f7aff`.

| what | count | command |
|---|---|---|
| `spec/csv_contracts.md` | **742** lines; §3.2 is ~30 of them | `grep -c "" spec/csv_contracts.md` |
| `app/services/relationships.py` | the parse + save pair | `grep -n "def parse_relationship_csv\\|def save_relationships" app/services/relationships.py` |
| `ParseResult`'s home | `app/services/csv_imports.py:36` | `grep -rn "class ParseResult" app/ --include='*.py'` |
| upload routes reaching this path | **7** matrix cases; the gate asserts **no total**, by design | `grep -n "^UPLOAD_PATHS" tests/integration/test_upload_paths_keep_friendly_labels.py` |

No code change is in scope for rung 1; rung 2's size is unknown until
rung 1 reports, which is the point of splitting them.

### PR ladder

1. **Rung 1 — the investigation.** Answers every `Semantics` question
   with the code's behavior and its location, recorded either in this
   item or, if the list of divergences runs long, in a
   `guide/findings_<date>_csv_contracts.md` register — the form
   `guide/README.md` defines for *found and left standing*. **Changes no
   spec and no code.**
2. **Rung 2 — the adjudication.** Per divergence, spec or code, on the
   author's call; the edits land here. **Must not** re-open questions
   rung 1 answered.

### Definition of done

- Every `Semantics` question has a written answer naming the code
  location that settles it.
- Each divergence carries an explicit disposition: spec edited, code
  edited, or recorded as deliberate with the reason.
- `spec/csv_contracts.md` §3.2's signature line matches
  `app/services/relationships.py`, or the section says why it does not.
- `pytest -n auto` green and `ruff check .` clean, with `node` present.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19S.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- Does the investigation's output live in this item or in a dated
  findings register? **Decided by:** rung 1, on the count — a handful of
  answers belong here; a long list belongs in its own file, as 19M's did.

### Out of scope

- **The other roster importers** (`parse_reviewer_csv` and siblings).
  §3.2 is the section with a demonstrated divergence; widening to all of
  §3 would make this the sweep it is deliberately not.
- **The upload-gate blind spot** (E8's second half), disposed of
  separately by the comment on `rehydrate_commit`.

### Doc impact

- `spec/csv_contracts.md` — §3.2 aligned to the code, or each retained
  claim explained, per rung 2's adjudication (Item 4).
- `docs/status.md` — row when the item lands (Item 4).

---

## Item 5 — a `Blast radius` row records a number, not when it was true

**Promoted from Item 1 entry E5** on the author's ruling, 2026-09-22 —
the entry the 22 September read logged with *"no plan, and I am not sure
what one would look like."* This item is narrower than that entry,
deliberately: it takes the one half of it that measurement shows is
derivable.

### Opportunity

E5's seven instances, classified against 19G Item 1's taxonomy (which
sorts prose drift by *what the prose disagrees with*), are four already
homed — class **D** at `docs/unenforced_conventions.md` §1.4, class
**B** at §1.5, two at §1.6 — and a residue that splits. Claims about
the **process** (*did the read run*, *is this feasible*, *what is left*)
have no other side in the tree, and §1.7 concedes the first already.
Claims that **cite their own command** do have one: the command is
written down, in a column the convention already asks for.

**Measured 2026-09-22 at `b8aeaa8`**, over every live and archived plan:

| what | count |
|---|---:|
| `Blast radius` sections | **98** |
| rows citing a re-runnable command | **171** of 175 |
| runnable exactly as written | **162** |
| sections stating a sha or date to measure against | **45** (46%) |

**The blocker is not runnability — it is the missing anchor.** 162 rows
could be re-run today, but in 53 of 98 sections a differing answer is
indistinguishable from the tree having legitimately moved, because the
row never said *when* its number was true. A re-run against those is
noise, and a noisy check is the shape `constitution.md` VI says gets
argued with, raised, then disabled.

### Decision

**Build the prerequisite, not the re-run.** A `Blast radius` section
states the commit or date it was measured at, and a check enforces that
on sections landing from the cutoff onward.

**Rejected: re-running the commands now.** On 53 of 98 sections nothing
says *when*, so the check would report the passage of time as drift —
and the two E5 instances a re-run would have caught were both *within* a
slice, where the anchor is what makes the comparison possible.

**Rejected: conceding the class to `docs/unenforced_conventions.md`
§1**, which is for rules that *should not* be mechanised. The
measurement says this half can be, cheaply, and a rule nobody has
written belongs in §2 — this item is that writing.

**Scoped by a date cutoff, not an allowlist**, which is the shape the
author already accepted for Item 2's G1: the legacy half is excluded by
one comparison, not by a list of 53 exceptions.

### Semantics

- **An anchor is a 7–40 character hex sha or an ISO date** in the
  section's opening lines. Both forms are already in use — Items 3 and
  4 above write *"Taken 2026-09-22 at `92f7aff`"*.
- **Only sections whose heading lands on or after the cutoff are
  checked.** Before it, 53 sections have no anchor and back-filling one
  would mean inventing a date — the defect this item is about.
- **A template command stays legal** — nine rows carry a
  `<placeholder>` and record *how* a number was taken, which is worth
  more than one that happens to run. The anchor is the requirement, not
  runnability. Sections sit at `##` or `###`; the check reads either, as
  `close_check.py` does.
- **The honest limit, so the item does not overclaim**: an anchor makes
  a *later* comparison possible. It does not make the original number
  true, and on its own it would have caught **none** of E5's seven.

### Judgment calls — decided

- **Anchor before re-run** (2026-09-22) — the measurement inverted the
  expected order: the commands are re-runnable, the comparison point is
  what is missing.
- **A date cutoff, not an allowlist** (2026-09-22) — one comparison,
  per Item 2's accepted precedent; a list of 53 legacy sections would
  breach §2's bar.
- **The check joins Item 2's module** (2026-09-22) — same subject, *is
  this hand-written claim checkable*, and a second module would split
  one gate list across two docstrings.
- **The process half is not in scope** (2026-09-22) — *did the read run*
  is §1.7's, already conceded; *is this feasible* and *what is left*
  have no other side at all.

### Blast radius (measured)

Taken 2026-09-22 at `b8aeaa8`. The corpus figures are in `Opportunity`;
what this item would *touch* is two prose files and one test module —
`grep -n "Blast radius" .claude/skills/segment-plan/SKILL.md
guide/segment_plan_template.md` — with **0** production LOC. At the
cutoff the check covers **0** sections, rising as plans land, and
excludes the **53** unanchored legacy ones.

### PR ladder

1. **Rung 1 — the anchor, and the check that keeps it.** The convention
   in the `segment-plan` skill and the blank template; the check beside
   Item 2's, green from its first commit because it covers nothing yet.
   **Must not** back-fill an anchor onto any existing section.
2. **Rung 2 — decide the re-run on the anchored corpus, and record the
   answer either way.** Once anchored sections exist, ask whether
   re-running their commands at close is worth building; a negative
   answer becomes a `docs/unenforced_conventions.md` §1 entry with this
   item's measurement behind it, which is more than E5 had. **Must not**
   build the re-run without that answer.

### Definition of done

- The check fails a `Blast radius` section landing after the cutoff with
  no anchor, demonstrated by a mutation per
  `docs/unenforced_conventions.md` §1.8.
- It passes the 53 legacy sections untouched, asserted rather than
  assumed.
- `.claude/skills/segment-plan/SKILL.md` and
  `guide/segment_plan_template.md` both ask for the anchor.
- Rung 2's answer is written down — as a built check or as a §1 entry.
- `pytest -n auto` green and `ruff check .` clean, with `node` present.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19S.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- Does the re-run ever get built? **Decided by:** rung 2, against the
  anchored corpus rather than against this item's guess.

### Out of scope

- **E5's process half** — *did the read run* (§1.7's already), *is this
  feasible*, *what is left to do*. No other side to compare against.
- **Back-filling anchors** onto the 53 legacy sections.
- **The four classes already homed** — §1.4, §1.5, §1.6.

### Doc impact

- `.claude/skills/segment-plan/SKILL.md` — "Measuring blast radius"
  asks for the commit or date the numbers were taken at (Item 5).
- `guide/segment_plan_template.md` — the blank `Blast radius` block
  carries the anchor line (Item 5).
- `docs/status.md` — row when the item lands (Item 5).

---

## Item 6 — a session can be tagged when it is created

**Logged 2026-09-22 on the author's instruction**, and it **supersedes
the more ambitious plan**: `guide/deferred_consolidated.md`'s *Tags,
Owners and a typeahead on the Create page* (19R Item 9, moved there
unbuilt) carried three changes plus typeahead. This is one of them.

### Opportunity

`app/web/templates/operator/session_new.html` carries **0** tag
mentions, so a session is born untagged and the operator goes back to
the lobby to classify it. Every tag write surface is on the lobby: the
`bulk-tags` toolbar action and the row expander's
`POST /sessions/{id}/lobby-edit`.

**Nothing is missing underneath.** `set_tags` is the whole write path,
the audit events are emitted, and tags already reach a new session
through the settings CSV (`_apply_session_tags`, 18P PR D2). The gap is
UI over a path that works end to end.

**The placement is the author's, not the superseded plan's**, which put
Tags in the *left* column below Description and gave this slot to
Owners. **Owners stays deferred**, as that entry itself recommends:
*"Tags is one input and one `set_tags` call; Owners is a staged
mini-editor."*

### Decision

One half-width card below User interface settings, holding one
comma-delimited text input, written with `set_tags` **after**
`sessions.create_session` returns an id.

**Rejected: reusing the lobby's write route.**
`POST /sessions/{id}/lobby-edit` needs a session id and this page has
none — the same constraint that made Owners a staged editor.
**Rejected: leaning on the settings CSV instead.** It already works;
the gap is the operator who is not uploading one.

### Semantics

- **Ordering is forced**: `set_tags` needs the id, so tags apply after
  create. A failed tag write must not leave a session created and
  silently untagged — rung 2 decides between one transaction and a
  reported partial.
- **The box and the settings CSV can both carry tags, and the existing
  rule decides it.** Audited 2026-09-22: `POST /sessions` parses the
  form, calls `sessions.create_session`, **then** applies the CSV, and
  `_apply_session_metadata` resolves each field by one of **two rules**:
  *fill-blanks* for `name`, `code`, `description`, `deadline`,
  `help_contact`, so **the form wins** — its docstring names this flow,
  *"on Create New Session, operator-typed fields are non-empty so the
  snapshot fills in only the blanks"* — and *force-apply* for the eight
  scheduling / toggle / timezone fields, where **the CSV wins** because
  they are *"session config, not operator-typed identity"*. **All 13
  Create form fields overlap the CSV**, 5 form-wins and 8 CSV-wins, and
  a typed tag is operator-typed.
- **But tags cannot just follow that rule, because their applier is
  wipe-and-replace.** `_apply_session_tags` deletes every existing tag
  not in the CSV, runs on **every** apply, and `_ParsedConfig.session_tags`
  is a bare `list[str]` with **no section-presence flag** — so a bundle
  with no `session_tags[]` rows is indistinguishable from one asking for
  none, and **wipes the session's tags**. That is deliberate for the
  round-trip (*"mirroring the other list sections"*) and fatal for a
  form box applied before it. Rung 2 therefore either writes the box's
  tags **after** `apply_session_config`, or merges them into the plan
  before it — whichever it picks, the form's tags survive a settings
  CSV that carries none.
- **Comma-delimited, matching the lobby's `name="tags"`**, so one habit
  works on both surfaces.
- `normalize_tag` decides the stored form; a repeated tag collapses; an
  empty box writes nothing and emits **no** audit event.
- **No lifecycle gate applies** — the session does not exist yet, which
  is why Create is the easy surface and Session Home is not (the
  superseded entry records that blocker and it stays out).
- **The force-apply path does not re-run the interactive ordering
  check, and that is safe — traced 2026-09-22, not assumed.** The route
  calls `scheduled_events.validate_schedule_ordering` (End ≥ Start;
  Release-from ≥ End) before create; the CSV force-applies the same
  datetimes afterwards with no re-check, and no Validate rule covers
  ordering. **Every downstream consumer guards itself**, each for its
  own reason: `is_response_release_window_open` returns `False` unless
  the session `is_expired`, **whatever the anchors say** — added at
  **19F PR 2a** precisely because *"every path that sets them without
  the button opened the window in a state the UI would never offer"*,
  naming a **backdated anchor on Quick Setup** as one of its two
  motivating cases, which is this path; a `responses_release_until`
  before its anchor leaves the window permanently shut rather than
  early-open; scheduled activation fires only from `validated` and
  otherwise takes a one-shot skip with
  `session.scheduled_activation_skipped`; and reminders past the
  deadline are skipped with an audit event
  (`scheduled_events/_reminders.py`). So the ordering check is an
  **interactive-path courtesy** — a field-level error instead of an odd
  schedule — not a correctness boundary, and the spec edit this item
  owes says so rather than leaving a reader to infer a hole.

### Judgment calls — decided

- **The author's slot over the superseded plan's** (2026-09-22).
- **Tags only; Owners stays deferred** (2026-09-22) — a different size
  of work, as that entry says itself.
- **Scaffold first** (2026-09-22) — `CLAUDE.md` requires it for a new
  card, so the inert card is rung 1 and the write is rung 2.
- **The form wins over the settings CSV, by precedent rather than by
  invention** (2026-09-22) — following the identity-versus-config split
  already implemented rather than adding a second philosophy. The cost
  is that tags need the ordering worked out, since their applier wipes.

### Blast radius (measured)

Taken 2026-09-22 at `0ca204b`.

| what | count | command |
|---|---|---|
| tag mentions on the page | **0** | `grep -c -i tag app/web/templates/operator/session_new.html` |
| the write path | **1** function, `set_tags` | `grep -n "^def " app/services/session_tags.py` |
| `vocabulary()` call sites | **2**, both the lobby's views | `grep -rn "vocabulary(" app/ --include='*.py'` |
| lines with an inline `style=` | **8**, of which **1** is button markup (`.btn-pair`, line 121) | `grep -n 'style="[^"]*"' app/web/templates/operator/session_new.html` |

**That last row corrects the superseded entry's *"8 inline-styled
buttons"***: the other seven are `page-grid` / `fill-col` wrappers and
an `h3`, so the `.btn` ride-along is one pair, not eight.

### PR ladder

1. **Rung 1 — the scaffold.** The half-width card in place with real
   copy and an inert input. **Must not** write anything.
2. **Rung 2 — the write.** `set_tags` after create, the CSV precedence
   answered, the partial-failure behaviour decided. **Must not** add
   typeahead — that is Item 7.
3. **Rung 3 — the `.btn` pair on this page**, per `CLAUDE.md`'s
   convention, asking first if either button does not fit a canonical
   role.

### Definition of done

- A session created with tags in the box has them, asserted through the
  route rather than the service.
- **A create carrying both a typed tag and a settings CSV with no
  `session_tags[]` rows keeps the typed tag**, asserted through the
  route — the case the wipe-and-replace applier would silently lose.
- An empty box emits no `session.tag_added` event, asserted.
- `pytest -n auto` green and `ruff check .` clean, with `node` present.
- The card is verified on the dev slot, since layout is not testable
  here — stated in the PR body per `CLAUDE.md`.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19S.6` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- ~~**Box or settings CSV wins** when a create carries both?~~
  **Answered 2026-09-22 by audit, not by decision: the form wins**, on
  the rule already in `_apply_session_metadata` — operator-typed fields
  are fill-blanks and a typed tag is operator-typed. The audit is in
  `Semantics`; what it leaves rung 2 is *mechanism*, not precedence,
  because the tag applier's wipe-and-replace means ordering has to be
  chosen deliberately.

### Out of scope

- **Owners on Create** — a staged mini-editor, still deferred.
- **Session Home's config card**, whose `config_editing` gate would make
  tags editable in 2 of 5 lifecycle states where the lobby edits them in
  any — the superseded entry's recorded blocker.
- **Typeahead** — Item 7.

### Doc impact

- `spec/sessions_overview.md` — the tag write surfaces it lists gain
  Create (Item 6).
- `guide/deferred_consolidated.md` — the superseded entry marked as
  superseded in part, with Owners and Session Home still deferred
  (Item 6).
- `spec/csv_contracts.md` — the settings CSV's apply semantics state
  the two rules (fill-blanks for operator-typed identity, force-apply
  for config), the tag section's wipe-on-absence, **and why the
  force-apply path needs no ordering re-check** (each consumer guards;
  see `Semantics`). Audited 2026-09-22 and found **undocumented**:
  `grep -i "precedence\|wins"` over `spec/csv_contracts.md` and
  `spec/settings_inventory.md` returns nothing, so the rule lives only
  in `_apply_session.py` (Item 6).
- `docs/status.md` — row when the item lands (Item 6).

---

## Item 7 — typeahead on the two tag boxes

**Logged 2026-09-22 on the author's instruction**, separately from Item
6, which builds the box this one would complete. Depends on Item 6 for
the Create surface to exist.

### Opportunity

Two boxes, two different problems, and **the lobby's is not the one it
looks like**.

**On the lobby the machinery is already there and unused.**
`app/web/routes_operator/_lobby.py:101` computes
`lobby_tags = session_tags.vocabulary(db, session_ids)`, and
`sessions_list.html:68-76` already feeds it to
`<datalist id="lobby-filter-options">` for the **filter** box. The row
expander's tag input at `:285` carries no `list=` — so the vocabulary
is in scope, one attribute away.

**But that one attribute would be wrong.** The input is `name="tags"`
and takes a **comma-separated list**, while a native `<datalist>`
completes the *whole field value*, not the token after the last comma.
Pointed at the existing list it would offer to replace `alpha, beta`
with `gamma`. So the lobby needs either a **UX change** (one tag per
input) or a **progressive-enhancement script** doing per-token
completion — which `CLAUDE.md` permits and the lobby's expanders
already use.

**On Create there is no vocabulary at all.** `vocabulary(db,
session_ids)` is scoped to the sessions on screen and both its callers
are the lobby's two views; Create has no list. Suggestions there need
the operator's own tags — a new query shape, not a new service.

### Decision

**Price the fork, then build the choice.** Rung 1 prices (a) a native
`datalist` with a one-tag-per-input UX on both surfaces against (b) one
shared per-token script keeping the comma box, each against both
surfaces and the existing expander script. Rung 2 builds what the author
picks.

**Rejected: building (b) directly.** The inline-script budget is
deliberate; whether a second script earns its place is a call, not an
assumption. **Rejected: shipping (a) on the lobby alone** — the two
boxes would then disagree about whether a comma means anything, which is
the inconsistency Item 6 chose its delimiter to avoid.

### Semantics — what rung 1 must answer

- **Create's vocabulary scope**: the operator's own sessions — owned or
  visible, archived included or not — and its cost at the lobby's
  measured **1,003** sessions.
- Whether the lobby's existing datalist is reusable or needs a second id
  (the filter's vocabulary and a tag editor's may differ once archived
  sessions are in play).
- That per-token completion is **impossible with a bare `<datalist>`**,
  stated with the reason rather than discovered in rung 2.
- **Normalization must agree with storage**: suggestions come from
  `vocabulary`, values are stored through `normalize_tag`; if they fold
  differently the operator is offered a tag they cannot create.
- The **empty vocabulary** — a first session, no tags anywhere.
- Keyboard and screen-reader behaviour, which only the dev slot settles.

### Judgment calls — decided

- **Both surfaces or neither** (2026-09-22) — one habit, per Item 6's
  delimiter reasoning.
- **Price before building** (2026-09-22) — the cheap-looking option is
  wrong for the reason above, which is exactly the kind of thing a
  pricing rung catches.
- **The lobby's filter typeahead is the precedent to match, not to
  duplicate** (2026-09-22).

### Blast radius (measured)

Taken 2026-09-22 at `0ca204b`.

| what | count | command |
|---|---|---|
| `vocabulary()` call sites | **2**, both `_lobby.py` | `grep -rn "vocabulary(" app/ --include='*.py'` |
| datalists in the lobby template | **1** | `grep -n "datalist" app/web/templates/operator/sessions_list.html` |
| the expander tag input's `list=` | **absent** | `sed -n '283,287p' app/web/templates/operator/sessions_list.html` |
| templates already using `datalist` | **14** | `grep -rln "datalist" app/web/templates/` |

### PR ladder

1. **Rung 1 — price the fork.** Both options against both surfaces,
   with the vocabulary query measured rather than assumed. **Writes no
   feature code.**
2. **Rung 2 — build the choice**, both surfaces together. **Must not**
   land on one surface only.

### Definition of done

- Rung 1's pricing is written down per option, including the query cost
  at 1,003 sessions.
- The chosen mechanism works on **both** boxes, asserted where testable.
- Suggestions and stored values agree under `normalize_tag`, asserted.
- `pytest -n auto` green and `ruff check .` clean, with `node` present;
  any inline script parses (`test_inline_scripts_parse.py`).
- Keyboard behaviour verified on the dev slot and said so in the PR body.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19S.7` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- **Native datalist with one-tag-per-input, or a per-token script?**
  **Decided by:** the author, on rung 1's pricing.
- **What scope is Create's vocabulary?** **Decided by:** rung 1, on the
  measured cost.

### Out of scope

- **The roster and Assignments typeaheads** (19I Items 7–9). Working,
  server-side, and a different surface.
- **Session Home**, which has no tag box to complete (Item 6's blocker).
- **Building the Create box** — Item 6.

### Doc impact

- `spec/sessions_overview.md` — its lobby drawing names
  *[filter box + typeahead]*; a second typeahead in the row expander
  belongs in it (Item 7).
- `docs/status.md` — row when the item lands (Item 7).
