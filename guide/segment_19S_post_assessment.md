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
which is what made the entry closable: 52 of the 67 pre-16 archived
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

## Item 2 — gate the four index invariants a reader keeps catching by hand — ✅ **closed 2026-09-22**

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
| pre-16, excluded by the ruling | **67**, of which **52** are unmentioned in `## Done` | the same scan, filter removed |
| `**Plan:**` pointers under `## Upcoming` (G4's subject) | **3**, all live | `grep -o '\*\*Plan:\*\* `[^`]*`' guide/todo_master.md` |
| archived paths cited under `## Upcoming` in other prose | **1** (19P) | the same region, any backticked `guide/archive/` path |
| `docs/status.md` `As of` vs newest row | equal (both 2026-09-22) | the date scan in rung 1 |
| new production code | **0** | the item adds tests and prose only |

No schema, no migration, no route, no template, no `app/` change.

### Status

**Closed 2026-09-22. Intended four checks and a mutation each; shipped
four checks, 23 tests and seven mutations**, because three of the four
saw less than they claimed until a mutation said so. Suite 4,639 →
4,662. `tests/unit/test_index_currency.py`, no `app/` change. The ladder
held: rung 1 touched neither `guide/todo_master.md` nor `docs/status.md`,
and rung 2 added no checks.

**The finding is that the item's own subject was in it.** Three of the
four checks or their guards were vacuous when first written — §1.8's
evidence bar, adopted by this item, is what surfaced each:

- **G1's mutation was inert**, and the hole had a live instance. ``-``
  is a non-word character, so ``19R-removed`` still matched
  ``^### Segment 19R\b`` — and ``### Segment 12C-1`` was already
  answering for a ``12C`` whose plan has no heading of its own.
  `id_pattern` uses ``(?![\w-])`` now.
- **G3's mutation was inert twice** — first inserting its row where
  ``max(rows)`` and ``rows[0]`` agree, then appending after a ``---``
  rule that occurs 18 times in the file, so ``replace(..., 1)`` put the
  row outside the table. It splices by offset now.
- **The plan-pointer recogniser matched this repo's prose about its own
  pointers** — ``\s*`` let the sentence *about* a `**Plan:**` pointer
  produce a capture — and that false positive is what satisfied G4's
  floor, so the floor passed while every real pointer could have been
  reformatted away. ``\s+`` now, and the floor asserts each capture's
  *shape*.
- **The floors absorbed a narrowing.** At a floor of 30, tightening
  `_PR_REF` to four digits dropped 16 three-digit headings out of G2's
  subject and still left 33. Floors sit just below the measured counts.

**Seven mutations, all caught** — G3's `max`, G2's running maximum, a
narrowed `_PR_REF`, the id boundary, the pointer's whitespace, and a
no-op G1 and G4 — against a mutated copy of the module.

**Two published figures were wrong and are corrected in this item**: the
pre-16 plans unmentioned under `## Done` were *34* and are **52 of 67**
by G1's own criterion, and the headings declaring no PR number were *33,
all predating the convention* and are **35, not all of which do**. Both
had been repeated into `docs/status.md`.

**Reads: one**, on rung 1, the item's last build rung (`CLAUDE.md`, "Two
cold readers"). Ten findings; the three that made a check vacuous were
what the read was worth, and each is the class 19R produced four of.
`spec-writer` was not run: `## Doc impact` names no `spec/` path, and
the item's subject is `guide/` and `docs/` index prose.

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
  four fails under a mutation of what it protects** — the mutations
  recorded in `### Status`.
- G1 **with the pre-16 filter removed** reports the 52 unmentioned
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
  `Status`? **Open at close, with no instance yet**: all 39 modern
  archived plans have a `## Done` entry, so G1 has never had to refuse
  one. **Decided by:** the first such plan. Recommendation unchanged — a
  marker in the plan, since §2's bar forbids a list inside the test.

### Out of scope

- **Pre-16 `## Done` coverage** — legacy, author's ruling 2026-09-22.
  52 plans unmentioned; the era used grouped headings.
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
  path half it already records; §1.8's quote of this item's definition
  of done drops the *four* it now contradicts (Item 2).
- `guide/todo_master.md` — the `## Done` maintenance note says the
  per-plan entry and the sort are checked (Item 2).
- `docs/status.md` — row when the item lands (Item 2).

---

## Item 3 — Prepare builds one ORM object per pair, three times over — ✅ **closed 2026-09-22**

**Promoted from Item 1 entry E1** on the author's ruling, 2026-09-22.
**Widened to the recompute pass** on the author's ruling, 2026-09-22,
after the trace below found the insert was a third of the cost at best.

### Opportunity

Prepare measures **20.0 s** at the 200 × 200 / 80,000-row bench and
**5.7 s** at half that roster, so the cost climbs steeply rather than
linearly; at the old 200,000-row bench it was **74.8 s of which only
17.4 s was SQL** — about a minute of Python building ORM objects.
`guide/app_responsiveness.md` Finding 4 has the figures and the
2026-09-21 re-set that re-confirmed them.

A click that blocks that long with no feedback is indistinguishable
from a hang, the operator's natural response is to click again, and it
is on the critical path of **every** session. The two end-of-window
reads disagreed on timing, not substance; the author ruled by promoting
it.

### Decision

Two changes, one rung each.

1. **The insert** — replace the per-pair `db.add(Assignment(...))` in
   `_materialise_one_instrument` (`app/services/assignments/_generate.py`)
   with a **Core bulk insert** of the same rows, keeping the
   `db.flush()` that follows. **The precedent is three lines above it**:
   the delete half already uses bulk Core —
   `db.execute(delete(Assignment).where(...))`, PR #1065 — while the
   insert half stayed ORM.
2. **The recompute pass** — `recompute_self_review_classification`
   re-materializes the same set as full entities one line later. It
   drops to a **column-tuple select plus one bulk `update`** for the
   rows whose flag changed. **Built as the ORM-enabled bulk UPDATE by
   primary key, not a Core one**, and the distinction is load-bearing:
   only the ORM form writes through to already-loaded entities, which
   is what lets the entity-shaped verify pass stay as it is.

**Rejected: `bulk_save_objects` / `add_all`** — both still construct one
Python object per pair, which is the cost Finding 4 measures.
**Rejected here: a progress indicator or a background job** — either
makes a 20 s wait *legible* rather than shorter, and whether one is
still wanted is not knowable until the cost is re-measured.

**Deferred, not rejected: the verify pass.** Author's ruling — the
third materialisation stays for now; being read-only makes it both the
cheaper one to move and the safer one to leave.

### Semantics

Compacted at close; the corrections these bullets went through are in
`Status`. Line numbers deliberately removed — this item moved every one
of them, which is the hazard.

- **The insert was one of three full materializations** (traced
  2026-09-22): the insert itself, `recompute_self_review_classification`
  once per instrument, and the identical select in
  `verify_self_review_classification`. Rungs 1 and 2 took the first two;
  the third is deferred.
- **The recompute writes, so the projection needs the stored flag.** It
  compares `is_self_review` to the freshly computed value and counts
  only differences, so without the stored flag the `changed` count
  callers read cannot be reproduced. **Seven slots**: `id`,
  `instrument_id`, `reviewer_id`, `reviewee_id`, the `Reviewee`,
  `is_self_review`, `Reviewer.email`. (`Blast radius`'s six counts
  *`Assignment`* attributes — a different thing, and this bullet
  conflated them until the close.)
- **The `Reviewee` has to stay an entity**; the rest can be columns.
  `_group_key_by_assignment` reads `assignment.reviewee` and the
  boundary spec names its fields dynamically. It costs little: the ORM
  dedupes by primary key, so a session's reviewee count bounds the
  instances however many rows join to them — asserted, 3 for 6 rows.
- **`group_keys` needed no variant, only the honest type.** Those five
  attributes — `id`, `instrument_id`, `reviewer_id`, `reviewee_id`,
  `reviewee` — are *all* it reads, so the projection goes through the
  existing function. `GroupKeyable`, a `Protocol` naming the five, now
  annotates it; `Assignment` and `AssignmentPair` both satisfy it
  structurally. Nothing enforces it — the repo runs no type checker.
- **The existing verify pass is an oracle for misclassification, not
  for absence.** It raises `AssertionError` in a test env on drift, so
  a wrong classification fails every regenerate test; but it finds no
  drift in zero rows, so it would not notice the insert writing
  nothing. Both rungs carry their own discriminating test as a result.
- **`is_self_review` is omitted at the insert site**, and the two Core
  insert forms do not differ on it: both compile the column's
  Python-side `default=False` in, and neither supplies `created_at`,
  which has only a `server_default`. The executemany form is kept for
  taking per-row dicts.
- **`include` and `created_by_mode` are per row**, so the payload is a
  list of dicts with per-row values, not one shared default.
- **An empty `diff.to_insert` must issue no statement**, and the guard
  is stronger than defensive: an empty parameter list compiles a
  *single-row* insert of nothing but the defaults and fails the
  `NOT NULL` on `session_id`.
- **Both dialects, and the audit envelope is unchanged.** Executemany
  behaves on Postgres and SQLite alike but `rowcount` does not, so the
  audit event's `counts` keeps coming from the diff, which computes it
  before the insert either way. Verified on both in CI.

### Judgment calls — decided

- **Core `insert()` over `bulk_save_objects`** (2026-09-22) — the
  measured cost is object construction, not only the unit of work.
- **Widen to the recompute pass, defer the verify pass** (author's
  ruling, 2026-09-22, on the trace in `Semantics`). Without the
  recompute rung the item's own Opportunity is not met, and rung 3
  would report a small figure as the expected outcome.
- **The item is still not all of Prepare** (2026-09-22) — Validate and
  Invite are separately measured and untouched.
- **No progress UI here** (2026-09-22) — making a wait legible is a
  different change from making it shorter, and the second may remove the
  need for the first.

### Blast radius (measured)

Taken 2026-09-22 at `ac5d3b7`; the row counts are a 200 × 200
single-instrument full matrix.

| what | count | command |
|---|---|---|
| the insert site | **1** | `grep -rn "Assignment(" app/ --include='*.py'` — 2 hits, the other is the model class |
| full materialisations of the assignment set per regenerate | **3** (insert, recompute per instrument, verify once) | the three call sites cited in `Semantics` |
| objects built per pass at the bench | **80,000** | 200 × 200 |
| entity attributes the two passes actually read | **6** (`id`, `instrument_id`, `reviewer_id`, `reviewee_id`, `reviewee`, `is_self_review`) | the trace in `Semantics` |
| `replace_assignments`: call sites in `app/` / test files that **call** it / that merely name it | **5** / **11** / **16** | `git grep -l "replace_assignments(" -- tests`, and without the paren |
| schema change | **none** | the columns are untouched; no migration |

**The bench was re-taken here, and this paragraph used to say it could
not be.** It read: *the bench is not re-takeable here* — on the evidence
that `pg_isready` answers *no response* on 5432 and that
`tools/bench_roster_scale.py` refuses a non-loopback `DATABASE_URL`.
Both facts are true and the conclusion drawn from them was wrong:
`postgresql-16` is installed in the container, so `initdb` +
`pg_ctl -o '-p 5433'` — the recipe in the bench tool's own docstring —
gives a loopback cluster, and rung 3 measured a real before / after on
it. **What was actually checked was whether a cluster was already
running**, not whether one could be started. Figures in
`guide/app_responsiveness.md` Finding 4.

### PR ladder

1. **Rung 1 — the bulk insert, flush property first.** ✅ done
   2026-09-22. Lands a test that the post-insert self-review verify
   pass sees every inserted row, *then* the Core insert under it.
   **Must not touch** Validate, Invite, the recompute pass, or the diff
   computation. **Cumulative-diff base for the item's cold read:
   `05145da`** (the `main` commit rung 1 branched from — the read runs
   at rung 2 per `CLAUDE.md`'s per-item cadence).
2. **Rung 2 — the recompute pass.** ✅ done 2026-09-22.
   `recompute_self_review_classification` drops to a column-tuple
   select and an ORM bulk `update`; `group_keys` gains the
   `GroupKeyable` protocol rather than the planned variant (see
   `Semantics`). The classification rule and the verify pass are
   unchanged — the rule moved to `classify_self_review_pairs` with
   `classify_self_review` as the entity adapter over it, so it is
   still stated once.
3. **Rung 3 — re-take Finding 4, or disclose that it could not be
   re-taken.** ✅ done 2026-09-22 — **re-taken**, and the plan's claim
   that it could not be is corrected in `Blast radius`. `guide/app_responsiveness.md` Finding 4 gains the
   post-fix figure beside its 20.0 s; with no loopback Postgres
   available, the item's `Status` says so and names the dev slot rather
   than quoting an unmeasured improvement. **Must not change code.**

### Definition of done

- The self-review verify pass is covered by a test that **fails** if the
  inserted rows are invisible to it — demonstrated by a mutation, per
  `docs/unenforced_conventions.md` §1.8.
- `diff.to_insert` empty issues no insert statement, asserted.
- `is_self_review` lands `False` on a Core-inserted row and is then
  recomputed, asserted.
- The rewritten recompute returns the **same `changed` count and the
  same classification** as the entity version on a group-scoped
  instrument, asserted — the count needs the stored flag in the
  projection, the classification needs the `Reviewee`.
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

- ~~Do either of the self-review passes rely on the ORM identity map
  rather than on the flush?~~ *Answered 2026-09-22, and in both
  directions. The **read** side does: the group path's
  `assignment.reviewee` resolved from the identity map, which is why
  the projection passes the reviewee explicitly. The **write** side
  does too, and the plan had it backwards — the recompute's bulk
  `UPDATE` must write through to loaded entities or the entity-shaped
  verify pass reports drift that is not there, which the ORM-enabled
  form does and a Core one would not.*

### Status

**✅ closed 2026-09-22**, three rungs. Intended: replace the per-pair
ORM insert. Done: that, plus the recompute pass — two of the three
materializations gone, the verify pass deferred — and **Prepare
measured 26.7 s → 13.1 s**, 2.0×, with the insert 9.9 s of the 13.6 s
and the recompute 3.7 s (`guide/app_responsiveness.md` Finding 4).

**The item's figures corrected the plan four times**, which is the
thing worth keeping:

- **The bench was re-takeable here** — see `Blast radius`, which used
  to say it was not.
- **The insert was the larger half**, not the "third of the cost at
  best" the widening was argued from. The widening still earned its
  3.7 s; the premise was wrong.
- **The two insert forms do not differ** on the omitted default, and
  the correction that said they differ on `created_at` was wrong too
  — see `Semantics`.
- **The identity map needed writing through, not expiring** — see
  `Open questions`.

**Reads: one `diff-reviewer` over `git diff 05145da..HEAD`, one
`spec-writer`, and between them they found the item's worst defect.**
Rung 2 shipped asserting *"one statement, not one per row — the point
of the change"*, and the pre-19S unit of work **also** emitted one
executemany `UPDATE`: all six tests passed against a full revert of
both rungs. The same gap was true of rung 1 by design (its three were
written to pass before the insert changed) but nothing then owned the
change. Both rungs now carry a discriminating test counting **entity
construction** — mapper `init` for the insert, ORM `load` for the
recompute — 4 → 0 objects and 6 `Assignment` + 2 `Reviewer` loads → 0,
each failing on revert with the expected figure in the message. That
is `docs/unenforced_conventions.md` §1.8's own 19R.5 precedent
recurring: a test that passed having recognized nothing.

Also from the reads, and not fixed here: **16 docstring references
across 11 files cite `guide/self_review_consolidate.md`**, archived to
`guide/archive/`. `tests/unit/test_doc_references.py` covers `.md`
prose, not Python docstrings — the same class as **Item 8** one layer
down, and a sweep rather than this PR's business.

**Length: 267 lines against the ~120 budget**, after compacting
`Semantics` by 41 and `Status` at close. Recorded rather than fixed
further, and `docs/unenforced_conventions.md` §1.9 is why: the
remaining bulk is `Decision`, `Blast radius`, the ladder and the
definition of done, and cutting those to hit a soft target is the
failure that entry names — the cheapest way to satisfy a length limit
is to move the reasoning out of sight. Third item this segment to
overrun, which is itself §1.9's point.

### Out of scope

- **The verify pass** — deferred by the same ruling that widened this
  item; read-only, so it moves on its own later.
- **Progress feedback or a background job for Prepare** — a different
  change, and possibly unnecessary after this one.
- **Validate and Invite**, Prepare's other two phases.
- **The other measured candidates** in `guide/app_responsiveness.md`
  (compression, the pair sort key, page furniture). They stay
  candidates.

### Doc impact

- `guide/app_responsiveness.md` — Finding 4 gains the post-fix figure,
  or the disclosure that it could not be re-taken here (Item 3).
- `spec/assignments.md` — § *Self-review policy* names the canonical
  computation surface and the individual-scoped arm's inner test; the
  refactor moved both (Item 3). **Added mid-item**, after two
  independent reads found the same drift and pointed out that a spec
  the plan does not name is a spec the close does not look at.
- `spec/rrw_functional_spec.md` — the same sentence one altitude up
  (Item 3).
- `docs/status.md` — row when the item lands (Item 3).

---

## Item 4 — spell out what `spec/csv_contracts.md` §3.2 actually describes — ✅ **closed 2026-09-22**

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

### Status

**2026-09-22 — rung 1 landed; the output is a register, and the
section turned out to be wrong in more places than it was right.**
`guide/findings_2026-09-22_csv_contracts.md` — **112 lines** at close,
73 when first written: the eight `Semantics` answers with the code
location that settles each, then **ten divergences** (four
spec-vs-code, five spec-silent, one code-internal) and three code
observations. Rung 1 itself changed no spec and no code.

**Every answer was run, not read** — a throwaway probe built a
two-reviewer / two-reviewee roster in memory and called
`parse_relationship_csv` on twelve CSVs, one per question. That is the
item's own subject applied to itself: §3.2's description was never
checked, and the cheapest way to produce another unchecked description
would have been to read the code and paraphrase it.

**The finding that matters most is not the stale signature**: the save
policy is **all-or-nothing and undocumented**. `Severity.error` is
blocking and all three callers gate on `result.is_blocked`, so one bad
row rejects the whole file — measured, a two-row CSV with one unknown
reviewer returns `rows=1, blocked=True` and saves neither.

**Rung 1 first filed that as a contradiction and it is not**, on a
reviewer's correction: §3.2's table is headed *Per-row validation* over
a column headed *Detection*, so *"per-row error"* describes where an
error is attached and the parser does exactly that. The section is
**silent** on what the import then does. The register is five
spec-silent rows against four spec-vs-code and one code-internal, and
the corrected row forces no behavior question — partial import would be
a new product decision, not the resolution of a divergence.

**Three claims in the section are right**, and the register says so:
the *"already-loaded session rosters"* prose, the required / optional
column lists, and the `seed_display_fields_from_assignments` note
including its explanation of the name.

**The register is ten rows, not eight, and the last two came from a
checker.** A `spec-writer` verification pass over the finished register
— a reader who did not write it, `constitution.md` III — confirmed all
eight and still found:

- **Row 9, a live bug the probe missed.** `seen_pairs[…] = index` is
  written **before** the `Status` check, so a first row with a bad
  status is dropped *and* keeps its pair key; a later valid row for the
  same pair is then rejected as *"Duplicate pair … also on row 1"* and
  the pair reaches `ParseResult` from neither. Measured after the
  report: two rows, first `Status=bogus`, second valid ⇒ `rows=0`. The
  twelve-case probe missed it because **no case combined two failure
  modes in one file** — a coverage shape, not an oversight in any one
  case.
- **Row 10, a false claim outside §3.2 and inside its subject.** §5's
  primitives table says `_parse_email` is used on the Relationships
  importer's columns. It is not — `relationships.py` has **0**
  occurrences — so that importer does **no email-format validation**,
  and a typo is reported as *"Unknown reviewer"*.

It corrected three asides inside rows 1–8 as well: §3.1 does **not**
repeat §3.2's *lowercase* claim, the `W8` label belongs to
`spec/validate_page.md` rather than `spec/participant_model.md`, and an
`is_blocked` citation pointed at the class rather than the property.

**Four of the register's own line citations were wrong on first
writing** and were corrected before the first commit, caught by
printing every cited line rather than re-reading the file.

**2026-09-22 — rung 2a: the one code disposition, on the author's
instruction to do rung 2.** Row 9's fix — the `seen_pairs` write moved
to just before `parsed.append`, so only a row that passes every check
reserves its pair. **Test written to fail first**: `rows=0` before the
fix, `rows=1` with a single `Status` issue on row 1 after, and
`test_parse_duplicate_pair` unchanged so a genuine duplicate still
errors. Suite 4,662 → 4,663. The dead `if status_raw == ""` branch went
with it, because rung 2a was rewriting that exact block — not as a
sweep.

**The rung split was not in the plan** and is recorded rather than
quietly taken: rung 1 could not know a bug would fall out, and
`CLAUDE.md` forbids bundling an unrelated bug fix with other work, so
the one code disposition landed alone and the nine prose ones follow as
2b.

**The cold read on the item's cumulative diff found nine things, and
one of them was material.** `diff-reviewer`, run at this rung because
rung 1 and 2b are prose and this is the item's only build rung:

- **The fix falsified a §3.2 sentence and the rung had claimed it did
  not.** *"Same pair twice → second occurrence rejected"* is now
  conditionally false — when the first occurrence fails a later check,
  the **second** is the one kept. §3.2's duplicate rule is edited here,
  in the rung that changed the behavior, rather than deferred to 2b.
- **The fix's comment claimed data loss that cannot happen.** Every
  issue is blocking and all three callers refuse the whole file, so no
  import ever lost a pair; the defect was the misleading message and
  the `prior_index` invariant. Comment, test docstring and register all
  overstated it — the same parser-versus-import conflation the rung-1
  review had already corrected once.
- **Three call sites, not two.** `session_rehydrate.py:601` parses and
  gates at `:605`. The register said *"both callers"* throughout.
- **One test assertion was weaker than it read**, indexing `issues[0]`
  where it meant the whole list; on the pre-fix code that index held the
  `Status` issue too, so it would have passed a revert. Now stated over
  the list, and the test is renamed to the file's `test_parse_*`
  convention. Revert-resistance re-proved by reverting the fix in place.
- **Three register citations went stale in the rung that moved the
  lines** — the same class rung 1's own commit message boasted of
  catching, re-broken one rung later.
- **The register still said its rows were "left standing"** while this
  rung actioned two, and its code-observation preamble said none was in
  scope while one was taken. Both reworded, and the neighbour that was
  *not* taken now says why.
- **"73 lines" and "eight divergences" were stale in two live
  documents** — true at `8a2adea`, false after the register grew to
  **112** and ten rows in `dda459f`, which edited both documents and
  left the figures.

**2026-09-22 — rung 2b closed the item: all ten rows dispositioned,
nine of them spec edits.** §3.2 gained the real parse and save
signatures, `reviewees.email_or_identifier` and the non-email fold,
case-insensitive `Status`, three new paragraphs — *a row yields at most
one issue*, *per-row detection, all-or-nothing save*, *roster status is
not checked* — and §5's `_parse_email` row lost its false claim about
this importer. **No second code change fell out**: row 9 was the only
one, and rung 2a took it.

**Row 7 is documented, not decided.** §3.2 now states that an
`inactive` member imports, and says explicitly that whether it *should*
is an open product question — so the spec records behavior without
converting an unexamined default into stated intent.

**Intended vs done.** Intended: an investigation then an adjudication,
two rungs. Done: three rungs, ten rows not eight, one code fix, and
**five separate review passes** — a Codex review on rung 1, a
`spec-writer` verification of the register, a `diff-reviewer` cold read
of the cumulative diff, a second Codex review, and a `spec-writer`
verification of 2b's own edits.

**What the reads found, because this is the figure the practice audit
wants.** Rung 1's Codex pass: one reclassification (row 4 was not a
contradiction). The register's `spec-writer` pass: **two new findings**,
one of them a live bug, plus three corrected asides. The cumulative
cold read: **nine findings**, including that rung 2a's fix falsified a
§3.2 sentence the PR body claimed it did not, and that the fix's own
comment alleged data loss that cannot occur. The second Codex pass:
**two**, both introduced by the commit before it. **2b's own
`spec-writer` pass: one false claim I had just written** — that
reviewees *and observers* skip `_parse_email` for a non-email cell,
where observers pass `strict=True` and reject it — plus two flags it
was right to raise: the §5 row's own `_parse_email` signature was two
keyword-only parameters short (pre-existing, in a row 2b was editing
anyway, so it was fixed here on the same "already in this line" logic
the dead branch took), and `spec/participant_model.md`'s vocabulary is
*"confidential / opaque identifiers"*, which `CLAUDE.md`'s
quote-the-control rule wants quoted rather than paraphrased. Every
finding was verified before action; none was taken on trust.

**The item's own recurring defect was citation staleness — three
incidents.** Four wrong line numbers in rung 1, three re-broken by rung
2a when it moved those lines, and a test node ID left pointing at a
pre-rename name. The third is the only mechanically checkable one, and
it is **recorded as a candidate rather than built here**: a gate reading
pytest node IDs out of live prose and asserting each collects needs no
allowlist and would be green from its first commit, which is
`docs/unenforced_conventions.md` §2's bar.

### PR ladder

1. **Rung 1 — the investigation.** ✅ **Done 2026-09-22.** Answers every `Semantics` question
   with the code's behavior and its location, recorded either in this
   item or, if the list of divergences runs long, in a
   `guide/findings_<date>_csv_contracts.md` register — the form
   `guide/README.md` defines for *found and left standing*. **Changes no
   spec and no code.**
2. **Rung 2 — the adjudication**, split once rung 1 turned up a bug.
   `CLAUDE.md` forbids bundling an unrelated bug fix with other work,
   and rung 1 could not have known one would fall out.
   - **2a — the one code disposition.** ✅ **Done 2026-09-22.** Row 9's
     fix plus its test, the dead branch in the same block, **and
     §3.2's duplicate rule** — the sentence the fix falsified, edited
     in the rung that changed the behavior rather than deferred. An
     earlier draft of this line said *"no spec edit"*, which the cold
     read disproved.
   - **2b — the nine remaining dispositions.** ✅ **Done 2026-09-22.**
     §3.2 rewritten and one §5 row corrected; **every one a spec edit**,
     no second code change. Row 7 documented as an open *product*
     question rather than as intent.

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

- ~~Does the investigation's output live in this item or in a dated
  findings register?~~ **Answered by the count, 2026-09-22: a
  register.** Eight answers plus eight divergences plus three code
  observations is not the handful that belongs inline —
  `guide/findings_2026-09-22_csv_contracts.md`.

### Out of scope

- **The other roster importers** (`parse_reviewer_csv` and siblings).
  §3.2 is the section with a demonstrated divergence; widening to all of
  §3 would make this the sweep it is deliberately not.
- **The upload-gate blind spot** (E8's second half), disposed of
  separately by the comment on `rehydrate_commit`.

### Doc impact

- `guide/findings_2026-09-22_csv_contracts.md` — the register rung 1
  produced: the eight answers, eight divergences, three code
  observations (Item 4).
- `spec/csv_contracts.md` — **§3.2 aligned to the code** (signatures,
  the identifier column, `Status` case, and three paragraphs on
  one-issue-per-row, all-or-nothing save and unchecked roster status)
  **and §5's `_parse_email` row corrected**, per rungs 2a and 2b
  (Item 4).
- `docs/status.md` — row when the item lands (Item 4).

---

## Item 5 — a `Blast radius` row records a number, not when it was true — ✅ **closed 2026-09-22**

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

Over every live and archived plan. **Each row states its own vintage**,
because two were re-measured when rung 1 pinned the definition and two
were not — which is the defect this item is about, so the table shows
it rather than hiding it under one header:

| what | count | taken at |
|---|---:|---|
| `Blast radius` sections | **100** | `840a2c0` |
| sections stating when they were measured | **67** (67%) | `840a2c0` |
| rows citing a re-runnable command | **171** of 175 | `b8aeaa8`, **not re-derived** |
| runnable exactly as written | **162** | `b8aeaa8`, **not re-derived** |

**The anchor figure is a correction, and the definition is why it
moved.** The table said **45 of 98 (46%)** when the item was planned.
No reading of *"stating a sha or date"* reproduces 45 — a sha anywhere
gives 66, a date anywhere 50, either anywhere 75, a date in the opening
lines 41 — so the old number is not re-derivable and is replaced rather
than reconciled. The new one moved twice more as rung 1 pinned the rule
in code: **69** under *sha-or-date in the opening two lines*, then
**67** once a date had to share its line with *taken* or *measured*
(cold read, 2026-09-22 — a bare prose date is not a measurement point).
**67 of 100 is the figure the check itself computes**, which is the only
one that can be re-derived.

**The denominator moved too, and not only by growth.** 98 → 100 nets
four new sections against `guide/segment_plan_template.md`'s two
leaving the population when `_PLAN_NAME` began excluding it. So the two
denominators are not the same measurement, and the correction is not a
pure numerator change.

The gap is **33 sections, not 53**. It strengthens the decision rather
than weakening it: the convention is already observed in two thirds of
the corpus, so the check codifies practice instead of imposing it.

**The blocker is not runnability — it is the missing anchor.** 162 rows
could be re-run at `b8aeaa8`, but in **33 of 100** sections a differing
answer is indistinguishable from the tree having legitimately moved,
because the row never said *when* its number was true. A re-run against those is
noise, and a noisy check is the shape `constitution.md` VI says gets
argued with, raised, then disabled.

### Decision

**Build the prerequisite, not the re-run.** A `Blast radius` section
states the commit or date it was measured at, and a check enforces that
on sections landing from the cutoff onward.

**Rejected: re-running the commands now.** On 33 of 100 sections nothing
says *when*, so the check would report the passage of time as drift —
and the two E5 instances a re-run would have caught were both *within* a
slice, where the anchor is what makes the comparison possible.

**Rejected: conceding the class to `docs/unenforced_conventions.md`
§1**, which is for rules that *should not* be mechanised. The
measurement says this half can be, cheaply, and a rule nobody has
written belongs in §2 — this item is that writing.

**Scoped by a segment cutoff, not an allowlist** (author's ruling,
2026-09-22), which is the shape already accepted for Item 2's G1: the
legacy half is excluded by one comparison, not by a list of 93
exceptions. A *date* cutoff was the alternative and is circular — see
`Semantics`.

### Semantics

- **An anchor is a backticked 7–40 character hex sha, or an ISO date on
  a line that also says *taken* or *measured***, within the section's
  first two non-blank lines. Both forms are already in use — the
  sections above write *"Taken 2026-09-22 at `92f7aff`"*. **The verb
  requirement came from the cold read**: a bare ISO date passes as an
  anchor while stating no measurement point, and **344 of the corpus's
  3,109 sections (11%)** open with exactly that shape. **0** `Blast
  radius` sections do, so it is pinned on the shape rather than on an
  instance.
- **What the scan cannot see, per §1.6's own habit** — a heading at `#`
  or `####`; an anchor written into the heading text; an anchor past two
  non-blank lines; a non-ISO date; an unbackticked sha; a plan filename
  with no leading digits. **0** instances of each today, and the list is
  in the module beside the constant.
- **The cutoff is a segment comparison** (author's ruling,
  2026-09-22), `ANCHOR_REQUIRED_FROM = (19, "S")`, sorted as
  ``(leading number, remainder)`` so ``19R`` < ``19S`` < ``20``. A
  *date* cutoff was the alternative and is circular: deciding whether a
  section is in scope would need to know when it landed, and a section
  carries no date until this convention gives it one — `git log` per
  section, for a question the filename answers.
- **19S, not the next segment.** All **7** of 19S's sections already
  carry an anchor, so the check covers real sections from its first
  commit. A cutoff one segment later would have covered **0** —
  green, and vacuous, which is what §1.6 concedes and §1.8 catches.
  **93** legacy sections are excluded, **33** of them unanchored, so
  the exclusion is load-bearing rather than decorative.
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
- **A segment cutoff, not a date and not an allowlist** (author's
  ruling, 2026-09-22) — one tuple comparison on the filename. A date
  needed `git log` per section to answer what the filename already
  answers; a list of the 93 legacy sections would breach §2's bar.
- **The check joins Item 2's module** (2026-09-22) — same subject, *is
  this hand-written claim checkable*, and a second module would split
  one gate list across two docstrings.
- **The process half is not in scope** (2026-09-22) — *did the read run*
  is §1.7's, already conceded; *is this feasible* and *what is left*
  have no other side at all.

### Blast radius (measured)

Taken 2026-09-22 at `840a2c0`. The corpus figures are in
`Opportunity`; what this item *touched* is two prose files and one test
module — `grep -n "Blast radius" .claude/skills/segment-plan/SKILL.md
guide/segment_plan_template.md` — with **0** production LOC. At the
cutoff the check covers **7** sections across **110** plans scanned
(live and archived), and excludes **93** legacy ones, **33** of them
unanchored.

### Status

**2026-09-22 — rung 1 landed, and the cold read found nine things
worth fixing in it.** `tests/unit/test_index_currency.py` gains **G5**
and 9 tests, 23 → **32** in the module; suite 4,663 → **4,672**. Two
prose files carry the convention. **0** production LOC.
`close_check 19S.5` exits 0.

**The cutoff's value is the design, and it is in `Semantics`.** What
belongs here instead is that the plan predicted G5 would cover **0**
sections and it covers **7** — a guard passing by seeing nothing is
what §1.6 concedes and §1.8 catches, in the item that cites both.

**Five mutations, all caught**, two of them added by the cold read:

| mutation | tests red |
|---|---:|
| a recogniser that can never fail | 4 |
| a heading pattern that matches nothing | 4 |
| a cutoff past every plan, so the scope empties | 2 |
| `#{2,3}` narrowed to `###`, dropping the 3 segment-level sections | 1 |
| a bare prose date accepted as an anchor | 2 |

**The last two are the read's.** The total-count floor **absorbed** the
`###` narrowing — 97 of 100 clears any plausible total — so the two
heading levels are now pinned separately. And `_ANCHOR` accepted any
ISO date in the opening lines, a shape **344 of 3,109 sections (11%)**
exhibit; a date now has to share its line with *taken* or *measured*.

**Seven more, all acted on.** The module docstring still said *four
invariants*. `unanchored_sections` took paths and did its own I/O,
breaking the module's stated design and forcing a `tempfile` round-trip
— it takes `(name, text)` pairs now, like its four siblings, and the
mutation runs in memory. `segment_id(...) or "0"` was the silent
fallback `plan_sort_key`'s own docstring forbids. `## Decision` still
specified a *date* cutoff three paragraphs from the bullet that had
been corrected to a segment one, and the superseded **53** survived in
four more places. §1.6 was cited five times without its own habit
discharged, so the blind spots are now listed beside the constant. And
the convention had gone into the section *table* while the plan
committed it to *"Measuring blast radius"* — it is in both now, rather
than the `Doc impact` bullet being edited to match what was done.

**The anchored figure moved twice more, and that is the definition
being pinned rather than flailing**: 30 unanchored under a loose
four-line window, 31 at two non-blank lines, **33** once a date needed
its verb. `Opportunity` publishes 67 of 100 with **per-row vintage**,
because two of its four rows were re-measured and two were not — the
item's own subject, so the table states it.

**2026-09-22 — rung 2 answered: the re-run does not get built**, and
the anchored corpus is what says so. `docs/unenforced_conventions.md`
**§1.10** carries it. Of the 33 in-scope rows, **3** are
machine-comparable, **21** carry a qualified value with no single number
to compare, and **9** have a bare value behind a *prose* command cell.

**Two criteria fail independently, and a review caught the first draft
conflating them.** Only the 21 are uncomparable by nature — *"67, of
which 52 are unmentioned"*, *"8, of which 1 is button markup"* — where
the qualifier is what makes the figure true. The 9 would become
comparable under a command-cell convention, costing no qualifier, so
**the ceiling is 12 of 33** and that ceiling, not the qualifier
argument, is what the coverage objection amounts to.

**The rung still found a live error, which is the argument it cuts
against itself.** Of the then-four comparable rows, **1 was wrong at its
own anchor**: Item 7 published *"datalists in the lobby template: 1"*
against a command yielding **2**, and the template is byte-identical
between that anchor and `a62d40c` — a **mis-measurement, not drift**
(elements counted, lines commanded). Corrected in Item 7's table. So
the re-run's hit rate on its own 4 rows is 1 in 4, and the decision is
*still* no, on the ground the hit rate does not touch: it would
**execute shell out of a freely-edited markdown cell** in CI, and a plan
file is not an execution surface. Against HEAD it would also re-create
the drift-versus-staleness ambiguity rung 1 existed to remove.

**Correcting Item 7's row is what moved 4 to 3** — the fixed row now
carries a qualified value, so this rung's own fix changed the figure it
was first published beside. Recorded because it is the item's subject
happening to the item.

**What rung 1 bought is the cheap manual check**, not a gate: the
error above was found by checking out the anchor and re-running, which
was impossible before G5 and is how §1.10 says to use it.

### PR ladder

1. **Rung 1 — the anchor, and the check that keeps it.** ✅ **Done
   2026-09-22.** The convention in the `segment-plan` skill and the
   blank template; **G5** beside Item 2's G1–G4, green from its first
   commit because 19S's seven sections were already anchored. No
   anchor was back-filled onto any existing section.
2. **Rung 2 — decide the re-run on the anchored corpus.** ✅ **Done
   2026-09-22: no.** The answer and its measurement are
   `docs/unenforced_conventions.md` **§1.10**. The re-run was not
   built.

### Definition of done

- The check fails a `Blast radius` section landing after the cutoff with
  no anchor, demonstrated by a mutation per
  `docs/unenforced_conventions.md` §1.8.
- It passes the **93** legacy sections untouched, asserted rather than
  assumed.
- `.claude/skills/segment-plan/SKILL.md` and
  `guide/segment_plan_template.md` both ask for the anchor.
- Rung 2's answer is written down — `docs/unenforced_conventions.md`
  §1.10, as a §1 entry rather than a built check.
- `pytest -n auto` green and `ruff check .` clean, with `node` present.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19S.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- ~~Does the re-run ever get built?~~ **Answered 2026-09-22: no**, on
  the anchored corpus rather than a guess — `docs/unenforced_conventions.md`
  §1.10 carries the measurement. **3 of 33** rows are machine-comparable,
  **21** carry a qualified value that has no single number to compare,
  and **9** would become comparable under a command-cell convention —
  so the ceiling is 12 of 33.
- ~~What is the cutoff, and in what unit?~~ **Answered 2026-09-22 by
  the author's ruling: a segment comparison**, now
  `ANCHOR_REQUIRED_FROM = (19, "S")` — see `Semantics` for why a date
  cutoff was circular. The question existed at all because rung 1's plan
  named the cutoff six times and defined it nowhere, found when the
  author asked what the item still needed.

### Out of scope

- **E5's process half** — *did the read run* (§1.7's already), *is this
  feasible*, *what is left to do*. No other side to compare against.
- **Back-filling anchors** onto the 93 legacy sections, 33 of which
  have none.
- **The four classes already homed** — §1.4, §1.5, §1.6.

### Doc impact

- `tests/unit/test_index_currency.py` — **G5** joins G1–G4: an
  in-scope `Blast radius` section states its anchor (Item 5).
- `.claude/skills/segment-plan/SKILL.md` — **"Measuring blast radius"**
  asks for the commit or date the numbers were taken at, and the
  section-table row names the check. Both, because a plan author
  follows the how-to section and a reader checks the table (Item 5).
- `guide/segment_plan_template.md` — the blank `Blast radius` block
  carries the anchor line (Item 5).
- `CLAUDE.md` / `AGENTS.md` — the *"A green `ruff` is not evidence"*
  entry for `tests/unit/test_index_currency.py` names G5 alongside
  G1–G4, so a contributor editing a `Blast radius` section knows a gate
  reads it (Item 5).
- `docs/unenforced_conventions.md` — **§1.10** records rung 2's answer:
  the re-run is not built, with the 4-of-33 measurement behind it
  (Item 5).
- `docs/status.md` — row when the item lands (Item 5).

---

## Item 6 — a session can be tagged when it is created — ✅ **closed 2026-09-22**

**Logged 2026-09-22 on the author's instruction**, superseding one
third of `guide/deferred_consolidated.md`'s *Tags, Owners and a
typeahead* entry (19R Item 9, moved there unbuilt).

### Opportunity

`session_new.html` carried **0** tag mentions, so a session was born
untagged and the operator went back to the lobby to classify it.
Nothing was missing underneath: `set_tags` is the whole write path, the
audit events are emitted, and tags already reached a new session
through the settings CSV. The gap was UI over a path that worked end to
end.

### Decision

One card below User interface settings holding one comma-delimited
input, written with `set_tags` after `sessions.create_session` returns
an id.

**Rejected: reusing `POST /sessions/{id}/lobby-edit`** — it needs a
session id this page has none of. **Rejected: leaning on the settings
CSV** — it already works; the gap is the operator not uploading one.

### Semantics

**The rule shipped into `spec/csv_contracts.md` § *Settings CSV — apply
precedence* and `spec/settings_inventory.md` §10 at the close**, which
is where it lives for a reader who has never seen this plan. What stays
here is why it was decided this way.

- **Ordering is the mechanism, and it is the analogy the other fields
  already use** (author's ruling, 2026-09-22: *follow the analogy of
  other fields where the form overrides the CSV update*). The box's
  `set_tags` runs after the settings block, so a bundle's
  `session_tags[]` rows are discarded when the box is non-empty —
  whole-field, not merged.
- **Rejected: making `_apply_session_tags` fill-blanks**, the literal
  per-field rule and the tidier home.
  `tests/unit/test_apply_session_config.py::test_round_trip_carries_session_tags`
  pins the opposite (18P PR D2), and the applier is shared with
  `POST /sessions/{id}/import-config` on an **existing** session.
- **Empty box writes nothing**, so a bundle's tags apply unopposed. The
  same empty string means *clear* on the lobby's row expander; both
  meanings are written down, because one helper serving both would
  silently pick one.
- **Bad input is silently skipped, matching the lobby**, and no
  lifecycle gate applies — the session does not exist yet, which is why
  Create was the easy surface and Session Home (Item 9) is not.

### Judgment calls — decided

- **The author's slot over the superseded plan's**, and **tags only**;
  Owners was a different size of work (2026-09-22; it is now Item 9).
- **Scaffold first**, per `CLAUDE.md` for a new card (2026-09-22).
- **The form wins over the settings CSV by precedent, and by ordering
  rather than by changing the applier** (author's ruling, 2026-09-22).

### Blast radius (measured)

Taken 2026-09-22 at `0ca204b`, re-taken at the close.

| what | count | command |
|---|---|---|
| tag mentions on the page | **0** | `grep -c -i tag app/web/templates/operator/session_new.html` |
| the write path | **1** function, `set_tags` | `grep -n "^def " app/services/session_tags.py` |
| `vocabulary()` call sites | **2**, both the lobby's views | `grep -rn "vocabulary(" app/ --include='*.py'` |
| lines with an inline `style=` | **9** at the close, 8 at the anchor | the same `grep` — rung 1 added the ninth, the card's `<h3 style="margin-top: 0;">` |
| of those, **button** markup | **0** | the line the pre-close figure called button markup is the `.btn-pair` **wrapper's** margin |

**That last row corrects the superseded entry's *"8 inline-styled
buttons"* twice over** — seven are layout wrappers and an `h3`, and the
eighth is a wrapper too. So **rung 3's `.btn` ride-along was zero pairs,
not one**.

### PR ladder

1. **Rung 1 — the scaffold.** ✅ The card in place, input inert.
   **Cumulative-diff base for the item's cold read: `c329180`.**
2. **Rung 2 — the write.** ✅ `set_tags` after the settings-CSV block.
   `_apply_session_tags` and its pinned round-trip test byte-identical.
3. **Rung 3 — the `.btn` pair on this page.** ✅ **Nothing to migrate**;
   see `Status`.

### Definition of done

All met. A tag typed on Create persists; a create carrying both a typed
tag and a settings CSV keeps the typed tag and only it, for both bundle
shapes; an empty box leaves a bundle's tags alone and emits no
`session.tag_added`; `test_round_trip_carries_session_tags` passes
untouched; `pytest -n auto` green and `ruff check .` clean with `node`
present; the card verified on the dev slot; `close_check 19S.6` exits 0
with its one note adjudicated; `spec-writer` and `diff-reviewer` both
run. **The archive move is the segment's, not this item's** — 19S stays
open on Items 7 and 9.

### Open questions

None. ~~Box or settings CSV wins, and by what mechanism?~~ Both
answered 2026-09-22 and carried into `Semantics` and the two specs
above: the form wins, by ordering.

### Status

**Closed 2026-09-22, three rungs** (#2561 → #2562 → #2563 → #2564).
Intended: a Tags box written after the settings CSV, then the page's
`.btn` pair. Done, plus two things the plan did not schedule — a
bundled P1 and a spec-level rewrite of what "the form wins" means.
**Rung 3 was a no-op as scheduled**; its real content was the doc
impact, and the precedence rule it wrote down had never been stated
anywhere — it lived only in `_apply_session_metadata`.

**A P1 that predates the item rides here, disclosed.**
`apply_session_config` flushes and never commits and `get_db` closes
without committing, so all three callers of `_run_quick_setup_settings`
returned success over discarded work. Rung 2 made it *conditional* — a
typed tag's own commit saved the import as a side effect, so the loss
showed only when the box was blank. Verified on `main` against a
file-backed SQLite read through a second session.

**The suite could not have caught it**, and the three attempts that
measured nothing are in the test's docstring in the order the next
person will reach for them. The one that works spies on
`Session.commit` as a **class** attribute.

**The item's lesson is one mistake made three times, each time by the
author of the rule against it.** `docs/unenforced_conventions.md`
§1.11 says a mutation set must mutate the helpers *and* the change.
Twenty mutations ran here and three of them lied:

- `_create`'s status assertion guards nothing. Kept as a **diagnostic**
  so a rejected create reads as such, and the docstring says so.
- `_card()` returned the page's tail, then — after the first fix —
  fell back to the same tail whenever no *later* card existed, which is
  the live case. **The mutation that should have caught the second also
  removed the opening-tag `rfind`, so it failed for an unrelated reason
  and read as caught.** Found by Codex; the helper depth-scans to the
  card's closing tag now and the guard asserts **balance**, which no
  fallback satisfies. Four mutations, all caught.
- The test's first CSV used `str` and a bare `help_contact` where the
  exporter writes `string` and `session.help_contact`, so the bundle
  applied **nothing** and the ordering tests passed while measuring
  nothing. The empty-box case is the control that catches that.

**Dev slot, 2026-09-22.** The two cards rendered flush; the `<h3>`
became the field's label (`aria-labelledby`) and the duplicate
`<label>` went.

**The item's last open decision, ruled 2026-09-23: the failed-upload
write stays.** A create whose Quick Setup half fails keeps the typed
tag rather than discarding it, which is what shipped and what
`spec/quick_setup_card_spec.md`'s failure mode already states. Nothing
left open.

**Reads: one `diff-reviewer` over `git diff c329180..HEAD` and one
`spec-writer`, both at rung 3, plus Codex on the PR.** All three found
real defects, and the one the first two agreed on was in prose that
rung had just written — `sessions_overview.md` claiming all three tag
write surfaces go through `set_tags`, where `bulk-tags` uses `add_tag`
/ `remove_tag`, contradicting its own bullet three lines above.
`spec-writer` also caught "fill-blanks means the form wins" holding
only for the two `required` fields. `diff-reviewer` caught the dev-slot
gap fix adding an app-wide `.bottom-grid .card + .card` rule where
`spec/ui_elements.md` §10 already names `.bottom-left` — a rule that
would have double-spaced the cards *inside* one — and four specs
governing the page saying nothing about the card.

**Adjudicated, not acted on**: `<p class="muted">` where §8 names
`.form-help`, left because it matches the neighbouring card and the dev
slot was signed off on it; and the card's inline
`style="margin-top: 0;"`, which wants a `.card h3` rule in `base.html`
— 6 instances across 4 templates, unverifiable here. **This record is
217 lines against the ~120 budget**, down from the 299 Codex measured:
`Doc impact` is 32 of them and is machine-read, so it does not
compress, and `Status` is most of the rest — the three-lied-mutations
record, which is the item's whole lesson. Counted, not estimated, at
this commit; the first draft of this sentence guessed 150 and then
195, which on this item of all items is the joke telling itself.

### Out of scope

- **Owners on Create** and **Session Home's config card** — both now
  **Item 9**, carrying the two blockers recorded here.
- **Typeahead** — Item 7.
- **The absent-section wipe on an existing-session re-import.** With no
  section-presence flag, a bundle carrying no `session_tags[]` rows is
  indistinguishable from one asking for none, so `import-config` clears
  the session's tags. Ordering makes Create immune; fixing that route
  is a candidate entry of its own.

### Doc impact

- `spec/sessions_overview.md` — the tag write surfaces it lists gain
  Create (Item 6).
- `guide/deferred_consolidated.md` — the superseded entry marked as
  superseded in part (Item 6).
- `spec/csv_contracts.md` — the apply precedence, the tag section's
  wipe-on-absence, the Create-page ordering, and why the force-apply
  path needs no ordering re-check. Audited 2026-09-22: none of it was
  stated anywhere, so the rule lived only in `_apply_session.py`
  (Item 6).
- `spec/settings_inventory.md` — §10 gains the same rule from the
  settings side, with the field lists (Item 6).
- `spec/quick_setup_card_spec.md` — the new-session variant's
  submission semantics gain the tag write ordered after the Settings
  slot, and its **failure mode** gains the typed tag surviving a
  bailed-out create (Item 6, from the cold read).
- `spec/operator_ui_concept.md` — the `/operator/sessions/new` per-page
  contract enumerates its cards, and gains this one plus the
  `.bottom-left` column that spaces the pair (Item 6, from the cold
  read).
- `spec/rrw_functional_spec.md` §9.2 — the Create form's field list
  gains session tags (Item 6, from the cold read).
- `spec/roundtrip_coverage.md` — the session-tag row is no longer an
  unconditional ✅: the Create page's box overrides a bundle uploaded
  with it. The `spec/` index makes this file authoritative over
  `spec/settings_inventory.md` §10, so the rule cannot live only there
  (Item 6, from the cold read).
- `docs/status.md` — row when the item lands (Item 6).

---

## Item 7 — typeahead on the tag boxes

**Logged 2026-09-22 on the author's instruction**, separately from Item
6, which builds the box this one would complete. Depends on Item 6 for
the Create surface to exist. **Sequenced after Item 9** (author's
ruling, 2026-09-23): typeahead covers **all three** tag editors — the
lobby, Create, and Session Home's details card — and the third is Item
9's to build. The analysis below predates that and speaks of two.

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
| datalists in the lobby template | **1** element, **2** matching lines | `grep -n "datalist" app/web/templates/operator/sessions_list.html` — the opening and closing tag; an earlier draft published **1** against a line-counting command (19S Item 5 rung 2) |
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

---

## Item 8 — a pytest node id cited in live prose resolves — ✅ **closed 2026-09-22**

**Logged 2026-09-22 on the author's instruction**, out of Item 4's own
defect record rather than out of the assessment: that item produced
**three** citation-staleness incidents, and this is the one of the three
with a clean derivation.

### Opportunity

`tests/unit/test_doc_references.py` already fails on a backticked repo
path in live prose that names nothing, and on a `§N` pointer to a
section that does not exist. It does **not** check a citation of the
form `` `tests/…py::test_name` `` — so prose can point at a test that
was renamed or deleted, and the reader who tries to run the cited proof
gets a collection error instead.

**It is not hypothetical, and it is not only Item 4's.** Measured
2026-09-22 at `9b32a9f`:

| corpus | citations | resolve |
|---|---:|---|
| live prose (the 72 files `LIVE_PROSE` already covers) | **7** | 7 |
| `guide/archive/` | **3** | **0** |

**That "7" was "2" until the cold read.** The first build anchored the
file half on `tests/`, inheriting `PATH_REF`'s refusal of a bare
filename — and the repo's **majority** convention for a test citation is
the bare filename (`docs/security_posture.md`'s gate table, 4 of them).
So the gate saw 2 of 7 and the plan published the 2 as a property of
the corpus when it was a property of the pattern: a `§1.6` miss, in the
item that cites §1.6. The pattern now takes both shapes; the bare one
resolves by a single `tests/**/<name>` glob, where two matches fail
loudly rather than guess, which is why the shorthand is safe here and
is not for a bare *path*.

All three archived citations are stale — one in 19F's plan, two in
`guide/archive/unfinished_business.md`. Archived prose is history and
stays exempt, but those three are the evidence that the failure mode
recurs across segments rather than being one rename today.

**Item 4's instance was in live prose**, which is what makes this
worth a check: `guide/findings_2026-09-22_csv_contracts.md` is not
matched by `DATED_DOC` (`findings_` is absent from it), so the register
citing a pre-rename test name **would have failed this gate** before a
reviewer found it by reading.

### Decision

Extend `tests/unit/test_doc_references.py` with one check: every
`` `tests/<path>.py::<name>` `` in `LIVE_PROSE` names a test that
exists. Same module because it is the same subject — *a citation in
live prose resolves* — and a second module would split one gate list
across two docstrings, the reasoning Item 5 used for joining Item 2's.

**Rejected: `pytest --collect-only` per citation.** It is the
authoritative answer and the wrong instrument: it costs a subprocess per
hit and turns an unrelated collection error anywhere in the suite into
this check's failure.

**Rejected: a new module.** See above; and `LIVE_PROSE`, `DATED_DOC`
and the live-line filter are already there to reuse.

### Semantics

- **Resolution is by definition name, read from the file.** A test
  exists when its file exists and declares `def <name>(` or
  `async def <name>(` — sufficient today because the suite has **0**
  class-based tests (`grep -c "^class Test" tests/`), which is the
  assumption to re-check if one ever lands.
- **Parametrised ids are out of shape, not out of scope.** No citation
  anywhere carries a `[case]` suffix today (**0**), so the check need
  not strip one; if one appears it should fail loudly rather than be
  silently tolerated, since a wrong case id is the same defect.
- **`guide/archive/` stays exempt**, as it is for paths: an archived
  plan records what was true, and its three stale citations are correct
  history. This is the concession, stated rather than discovered.
- **The residual, named because §1.6 asks what a scan cannot see.**
  `DATED_DOC` excludes `segment_*.md`, and one live citation sits in
  `guide/segment_19S_post_assessment.md` — so a node id in a *live
  segment plan* is unchecked. Widening `LIVE_PROSE` is a change to a
  corpus three other checks share, which is not this item's to make.
- **Green from its first commit**, which is `docs/unenforced_conventions.md`
  §2's bar: both live citations resolve at `9b32a9f`. The check arrives
  as a guard, not as a cleanup.

### Judgment calls — decided

- **Definition-name lookup over `--collect-only`** (2026-09-22) — the
  cheap instrument that cannot be broken by an unrelated collection
  error.
- **Item 4's module, not a new one** (2026-09-22) — same subject as the
  path and `§N` checks it sits beside.
- **Two citations is thin and the item says so** (2026-09-22) — the
  case is the demonstrated instance plus the three archived ones, not
  the size of today's corpus. §1.6's vacuity concession is why the
  count is published rather than implied.

### Blast radius (measured)

Taken 2026-09-22 at `9b32a9f`.

| what | count | command |
|---|---|---|
| node-id citations in `LIVE_PROSE` | **7** (2 anchored, 5 bare) | the scan in `Opportunity` |
| backticked `::` citations in `LIVE_PROSE` that are **not** test node ids | **43** | the same scan — `module.py::symbol` naming app code, a different convention and out of scope |
| stale citations in `guide/archive/` | **3** of 3 | the same scan, archive corpus |
| class-based tests in the suite | **0** | `grep -c "^class Test" tests/ -r` |
| parametrised node-id citations, any corpus | **0** | the same scan, `\[` in the name |
| `tests/unit/test_doc_references.py` | **316** lines, **5** test functions (3 subjects: twins, paths, `§N`) | `grep -c "" …` / `grep -c "^def test_" …` — the plan said "4 checks"; re-measured at the build |
| production LOC | **0** | the item adds a test only |

### PR ladder

1. **Rung 1 — the check.** ✅ done 2026-09-22. One test in
   `tests/unit/test_doc_references.py`, plus a mutation proving it
   fails on a renamed citation and a live floor asserting the scan sees
   the citations that exist. **Must not** widen `LIVE_PROSE` or touch
   the path / `§N` checks — **the constraint bound**, and decided the
   escape question; see `Status`.

### Definition of done

- The check **fails under a mutation** of what it protects — a citation
  renamed to a test that does not exist — per
  `docs/unenforced_conventions.md` §1.8, and the mutation is recorded in
  `### Status`.
- A **live floor** asserts the scan finds the citations that are
  there, so a recogniser that matches nothing cannot pass.
- The archive exemption is asserted, not assumed: the three stale
  archived citations do **not** fail the suite.
- `pytest -n auto` green and `ruff check .` clean, with `node` present.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19S.8` exits 0; any warning adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added

### Open questions

- Should a node id in a **live segment plan** be checked? `DATED_DOC`
  excludes it today and one such citation exists — re-confirmed at the
  build, still exactly one, in this file. **Left open deliberately**, as
  the recommendation said: widening `LIVE_PROSE` changes a corpus three
  checks share, and this item is scoped not to. **Decided by:** the
  author, or the first stale instance there.

### Status

**✅ closed 2026-09-22**, one rung, 0 production LOC. Intended: one check
that a cited pytest node id names a test that exists. Done, plus three
supporting tests — a floor, a recogniser exercised outside its live
examples, and the archive exemption asserted rather than assumed.

**Every `Blast radius` figure re-took at the build** — 3 archived
citations all stale, 0 parametrised ids, 0 class-based tests — and
**two were wrong**. The module is **5** test functions, not the "4
checks" the plan counted. And the live corpus is **7** citations, not
2: the 2 was what the first pattern could see, not what is there. Both
corrected above.

**The escape question was not in the plan, and mutation answered it.**
The path check has an inline marker (`<!-- path-ref-ok -->`) and a
section marker, and reusing both looked free. It is not:
`test_no_inline_path_marker_outlives_the_reference_it_covers` computes
coverage from *path* references alone, so a marker placed over a broken
**node id** reads as covering nothing and turns the suite red — the
remedy this check's own failure message offered would itself have
failed. Teaching that check about node ids means editing a check the
ladder scopes out, and minting a second marker with zero uses is
mechanism ahead of need. So: the **section** escape is honoured (M5
below proves it), there is **no inline escape**, and the failure message
says so. The first citation that needs one is the argument for adding it.

That also caught a second defect of my own: the floor asserted every
live citation *resolves*, which contradicts the section escape — a
legal escaped citation would have failed it. A floor that contradicts
its own escape gets deleted the first time someone uses the escape.

**Mutations run** (`docs/unenforced_conventions.md` §1.8):

| mutation | caught by |
|---|---|
| M1 cited test renamed | the check |
| M2 cited test *file* renamed | the check |
| M3 recogniser matches nothing | floor + recogniser + archive |
| M4 resolver broken open (always returns OK) | recogniser + archive |
| M5 broken citation in a section-escaped register | **stays green**, by design |

M4 is the one worth keeping: the archive test's `assert stale` doubles
as a guard against a resolver that never reports failure, which is the
way this check would most plausibly rot.

**The residual §1.6 asks for**: a node id inside a section-escaped dated
register — `docs/status.md`'s timeline, `guide/todo_master.md`'s
`## Done` — is unchecked, and so is one in a live segment plan. Both are
stated where they can be read, and the second is left open above.

**Reads: one `diff-reviewer`, and it found two defects in the gate plus
eight smaller things.** Recorded here because a close that says only
*a read was run* records the cadence and not the outcome.

The two that mattered:

- **The gate saw 2 of 7 citations.** `NODE_REF` anchored the file half
  on `tests/`, and the bare filename is the repo's majority convention.
  Corrected above; coverage is 7 of 7 resolvable, still green from the
  first commit.
- **The floor did not floor the scan.** It re-implemented the pattern
  walk instead of calling `_node_refs`, so gutting that helper to
  `return []` left all nine tests green **with a genuinely broken
  citation in the repo** — verified, then fixed by having `_node_refs`
  return every citation rather than only failures. That is §1.8's own
  19R.5 instance reproduced *inside the item that cites it*, which is
  the thing worth carrying forward: the M1–M5 set tested the check and
  never tested the scan under it.

The rest: the resolver's `^\s*def` resolved nested defs, class methods
and `def`s written inside strings — all silent false passes, now
column-0 anchored and visibly failing; its docstring's class-method
caveat named the wrong mechanism (such an id is not *matched*, not
*loosely resolved*); parametrised ids with `.`, `/` or a space were
silently skipped where the plan said they must fail loudly; the module's
own header still said *"Three checks"*, in the file whose job is doc
currency; `tools/practice_kit.py` exports this module verbatim and two
new tests could not pass in a fresh repo (they skip now, verified by
running the export); and the section escape's cost — it opts a whole
section out of the *path* gate too — was unstated.

**Codex then found the half the cold read missed.** Its two P2 findings
were against the pre-fix commit and one was already closed — the
parametrised ids with spaces, slashes and colons it flagged are matched
and rejected as of that push. The other was not, and the cold read had
only found half of it: anchoring `def` at column 0 fixed *where* the
definition sits but nothing checked *what it is called*, so a column-0
helper resolved — `tests/…::override_get_current_user` passed the gate
while `pytest --collect-only` on it exits 4. The name must now start
with `test`, pytest's `python_functions` default and not overridden
here. Node-id syntax means *a thing pytest collects*, so a name that
cannot be one is a broken citation.

Mutations now **eight**: M6 the gutted scan, M7 a renamed bare-filename
citation, M8 a column-0 non-test def cited as a node id.

### Out of scope

- **The other two staleness classes Item 4 produced** — wrong `file:line`
  numbers. A line number has no derivation that survives an edit
  anywhere above it, which is why only this class became an item.
- **Widening `LIVE_PROSE`** — see the open question.
- **`guide/archive/`** — its three stale citations are history.

### Doc impact

- `tests/unit/test_doc_references.py` — the node-id check joins the
  path and `§N` checks (Item 8).
- `CLAUDE.md` / `AGENTS.md` — the *"A green `ruff` is not evidence"*
  entry for that module names what it now covers (Item 8).
- `docs/status.md` — row when the item lands (Item 8).

---

## Item 9 — Owners on Create, and Tags on Session Home

**Logged 2026-09-22 on the author's instruction**, in two parts. Both were
`Out of scope` on Item 6 and deferred before it; this item promotes
them out, emptying `guide/deferred_consolidated.md`'s *Tags, Owners
and a typeahead* entry of all but the button relocation.

### Opportunity

Item 6 put a Tags card on Create and stopped there, and both templates
say what that left: Create carries **0** owner mentions — a session is
born with exactly one owner and the operator goes to Session Home to
add a second — and Session Home carries **0** tag mentions, on the card
that edits every other session-level attribute.

**Nothing is missing underneath, on either side.** `add_owner` /
`remove_owner` are the whole owner write path and commit for
themselves exactly as `set_tags` does, and `session.owner_added` is
already emitted. The gap is UI over paths that work end to end — which
is what Item 6 was, and why this is one item and not a segment.

### Decision

**Part A — an Owners card below Tags on Create.** The right-hand
column becomes User interface settings → Tags → Owners at no CSS cost:
Item 6's rung 3 made that cell a `.bottom-left`, so its `gap` spaces a
third card for free.

**Part B — a Tags card below User interface settings on Session
Home's details card**, in that page's matching `.bottom-left` column,
above the Save / Cancel / Lock cluster. **It is a field of the details
card that happens to render in its own card**, exactly as the UI
toggles are: same dual-mode convention, same `form="config-save-{{
session.id }}"`, same edit window. No second mechanism and no second
save (author's ruling, 2026-09-23). The consequence is deliberate: tags
are editable here in **2 of 5** lifecycle states, and **the lobby stays
the any-state tag surface** — a division of labour, not a
contradiction.

**Locked, it renders like every other field there** — a
`.config-value` div, `data-display-only`, holding the tags
comma-joined, em dash when there are none, as `help_contact` and
`description` do; edit mode swaps in the `data-edit-only` input on the
same string. **The `<h3>` is the label**, as on Create's Tags card
(corrected at rung 1: the plan said a `<label for=…>`, on the premise
the field sits among fields — it sits in its own card, where a label
under the heading repeats it, which the author rejected on Create).

**Rejected for Part A: reusing `POST /sessions/{id}/owners/add`.** It
needs a session id this page has not got — the finding the deferred
entry preserved. Rows stage in the form and apply after
`create_session` returns, the ordering Tags already uses.

### Semantics

- **Saving the details card rewrites the case of every tag on the
  session, and no spec says so.** Measured 2026-09-23: `normalize_tag`
  lowercases and **`_apply_session_tags` does not call it**, inserting
  the CSV's value raw — so a bundle importing `Pilot` stores `Pilot`
  while every typed tag is lowercased. Part B round-trips through
  `set_tags`, so the first save of an otherwise untouched card turns
  `Pilot` into `pilot`. Pre-existing, made *visible* by Part B, and the
  same asymmetry that would put two entries in Item 7's vocabulary. It
  also strands the tag: `remove_tag("Pilot")` looks for `pilot` and
  returns `False`, so the lobby cannot delete it (probed). **Resolved
  2026-09-23, author's ruling: tags are lower case everywhere** — the
  importer calls `normalize_tag`, trim and length check included, in
  rung 1, the first code the asymmetry would bite.
- **Empty box means the opposite on the two surfaces, deliberately.**
  On Create it writes *nothing* — `set_tags` with an empty set is a
  replace that would drop what a settings CSV just applied. On Session
  Home it means *clear*, matching the lobby, because there is a set to
  edit. `spec/csv_contracts.md` § *Settings CSV — apply precedence*
  states both; Part B is the first code to depend on it.
- **Part B does not touch `_apply_session_config_form`.** That helper
  takes exactly the 13 non-tag fields, and Item 6 ruled tags are
  written beside the config work, not through it. The tag write is a
  second call in `POST /sessions/{id}/config`.
- **Part A inherits `add_owner`'s two rejections** with nowhere yet to
  put them: `not_in_workspace` (target not on the operator allowlist)
  and `already_owner` — which self-add always is, the creator being
  owner #1 from `sessions.py`. And **`workspace_operator_candidates`
  needs a session** to exclude current owners; on Create the list is
  every workspace operator but the creator, a narrower query the
  service gains rather than a new service.

### Judgment calls — decided

- **One box of emails, not a staged add/remove table** (2026-09-22) —
  nothing exists to remove before the session does, and the table is
  what made the deferred entry call Owners "a staged mini-editor". The
  table stays on Session Home, which is where a session has owners.
- **Tags between UI settings and the button cluster, not after it**
  (2026-09-22) — the cluster is the column's last child by convention.
- **Two parts, one item** (2026-09-22) — they share a rule (the
  empty-box split above) and neither is a segment's worth alone.
- **Part B rides the details card's edit window** (author's ruling,
  2026-09-23) — `Decision` carries it.
- **Owners' card takes a `<p class="muted">` subtitle, like the two
  above it** (author's ruling, 2026-09-23). `spec/ui_elements.md` §8
  read as forbidding it; measurement found the subtitle pattern in ten
  places against 32 `.form-help` uses, with only the latter written
  down. §8 carries the carve-out now, so Part A inherits the answer.

### Blast radius (measured)

Taken 2026-09-22 at `d4b1ba9`.

| What | Count | Command |
|---|---|---|
| owner mentions on Create | **0** | `grep -c -i owner app/web/templates/operator/session_new.html` |
| tag mentions on Session Home | **0** | `grep -c -i tag app/web/templates/operator/session_detail.html` |
| `add_owner` / `remove_owner` call sites | **3** (2 routes + sys-admin) | `grep -rn "add_owner(\|remove_owner(" app/ --include='*.py'` |
| `set_tags` call sites | **2** | `grep -rn "set_tags(" app/ --include='*.py'` |
| `workspace_operator_candidates` call sites | **1** | the same `grep` |
| `.bottom-left` columns on the two pages | **2** / **4** | `grep -c "bottom-left" <each template>` |
| lifecycle states the config card gates against | **2 of 5** | `config_editing` at `app/web/routes_operator/_session_home.py` |

### PR ladder

1. **Rung 1 — Part B's scaffold.** ✅ 2026-09-23. The card in place,
   showing real tags when locked, its input inert. **Cumulative-diff
   base for the item's cold read: `7022022`.**
2. **Rung 2 — Part B's write, plus the settings-CSV importer
   normalizing tags.** ✅ 2026-09-23 — both halves in one rung, as
   required.
3. **Rung 3 — Part A's scaffold**: the Owners card inert, no write.
4. **Rung 4 — Part A's write**: staged rows applied after
   `create_session`, with the two rejections surfaced — **plus one
   correlation id for the whole create** (author's ruling, 2026-09-23).
   `request_correlation_id()` mints a fresh id per call, and the Create
   route calls it for the session, each Quick Setup slot and the tag
   write; the owner writes this rung adds would make it worse. Session
   Home's save was fixed the same way in rung 2 (#2569, Codex).

Re-cut at rung 1 from three rungs to four: `CLAUDE.md` lands a new
card as its own slice, and Item 6 did the same.

### Definition of done

- A tag typed on Session Home's details card persists and **an
  emptied box clears the set**, both asserted through the route.
- **A settings CSV importing `Pilot` stores `pilot`**, and the lobby can
  then remove it — asserted through the route, with the revert
  mutation run (`docs/unenforced_conventions.md` §1.11).
- **Every audit event one create produces shares one correlation id**
  — session, uploads, tags and owners — asserted through the route.
- A co-owner named on Create owns the created session, and
  `not_in_workspace` / `already_owner` each reach the operator rather
  than failing silently — all asserted through the route.
- **Each new card's gap to the card above it measured in Chromium**,
  not asserted from the CSS (author's instruction, 2026-09-23): dump
  the rendered page from the test client and read
  `getBoundingClientRect()` at 1280 and 700px, as
  `tools/css_parity_check.py` does. Then the dev slot.
- `pytest -n auto` green, `ruff check .` clean, `node` present.
- `tools/close_check.py 19S.9` exits 0; `spec-writer` run; `Status`
  compacted; `docs/status.md` row.

### Open questions

None. ~~Does the Session Home Tags box escape the card's
`config_editing` gate?~~ Answered *no* on 2026-09-23, against my
recommendation; `Decision` carries the ruling and `Semantics` the one
thing it does not reach. Rung 1 is unblocked.

### Status

**Rung 1 done, 2026-09-23** — Part B's scaffold. The Tags card sits
below User interface settings in the details card's right-hand
`.bottom-left`, above the Save / Cancel / Lock cluster; locked it shows
the tags as a `.config-value`, em dash when none; unlocked, an input
prefilled with the same string. **Inert**: no `name`, no `form=`, and a
`POST …/config` carrying `tags=` leaves the tags alone — with a rename
in the same request as the control, since a rejected save would also
leave them alone. Seven tests, **six mutations, all caught**: `name`
added, `form=` added, the route context emptied, `_card` widened to the
page tail, the `_tag` helper degenerated, and the route wiring `tags=`
early.

**Spacing measured in Chromium** at 1280 and 700px, display and edit
mode: UI settings → Tags **20px**, Tags → Save cluster **20px**, and the
Create page's pair unchanged at 20px. No CSS change; the column's `gap`
does it.

**Rung 2 done, 2026-09-23** — the Tags field saves with the details
card, and the settings-CSV importer normalizes. Rung 1's two inertness
tests are **inverted rather than deleted**. The write runs after the
config apply, so a save the card rejects (a 422, tested with a bad
timezone) writes no tags either; an emptied box clears; an untouched
box emits no tag events, because `set_tags` diffs.

**One thing the plan did not foresee: absent reads as empty.** The
first draft left tags alone when the request carried no `tags` field,
and its own test caught that it also left them alone when the box was
*emptied* — FastAPI hands an absent form value and an empty one to an
optional parameter identically, both `None`. Telling them apart needs a
marker field. The route already takes the card's whole state (its two
checkboxes read absent as off) and the card's form always sends the
field, so the tags follow the same convention: absent or empty clears.
A test pins it.

**The importer**: `normalize_tag` on each `session_tags[]` value —
lowercased, trimmed, duplicates collapsed, blanks skipped. An over-long
value is now a **parse error** refusing the bundle, where it used to
reach a 64-character column raw; skipping it silently, as the lobby
does, was the alternative, and a file the operator can fix earns a
message instead. Through the routes: a bundle importing `Pilot` stores
`pilot`, and the lobby's bulk remove then deletes it.

**Nine mutations, eight caught first time.** The survivor was a helper:
a tag-event counter stuck at zero passed the "untouched box emits
nothing" test by comparing 0 with 0. The test now asserts the setup's
two events first. The rest: importer reverted, over-long tag skipped
instead of rejected, route write reverted, write moved before the
config apply, `name=` dropped, and the `_save`, `_tags_of` and
`_tag_rows` helpers each degenerated.

### Out of scope

- **Typeahead on either new box** — Item 7, open on its own fork.
- **The Create page's button relocation**, the deferred entry's last
  unbuilt change, independent of both parts.
- **Owner *removal* on Create** — see the judgment call.
- **Capitalized tags already stored** stay until something rewrites
  them. **No migration** (author's ruling, 2026-09-23).

### Doc impact

- `spec/ui_elements.md` — §8 gains the card-subtitle carve-out and
  the one-field-card case it decides (Item 9, ruled before the build).
- `spec/operator_ui_concept.md` — the `/operator/sessions/new` card
  list gains Owners; Session Home's details card gains Tags (Item 9).
- `spec/sessions_overview.md` — the tag write surfaces become four;
  its "third write surface" bullet is false from rung 2 until the close
  rewrites it (Item 9).
- `spec/csv_contracts.md` — the settings CSV's tag section states that
  import normalizes, as every typed surface already does (Item 9).
- `spec/roundtrip_coverage.md` — the session-tag row notes import
  lowercases, so a legacy capitalized tag comes back lower case
  (Item 9).
- `spec/session_home.md` — the details card gains a Tags field that
  shares the card's edit window and `config-save` form, and renders as
  a `.config-value` when locked. Say also that an emptied box clears
  (the Create page's writes nothing), and that this surface is
  draft/validated only through `_require_editable` while the lobby
  edits tags in any state (Item 9).
- `guide/deferred_consolidated.md` — the entry narrows to the button
  relocation alone (Item 9).
- `docs/status.md` — row when the item lands (Item 9).
