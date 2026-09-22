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

## Item 3 — Prepare builds one ORM object per pair, three times over

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
   re-materialises the same set as full entities one line later. It
   drops to a **column-tuple select plus a Core bulk `update`** for the
   rows whose flag changed.

**Rejected: `bulk_save_objects` / `add_all`** — both still construct one
Python object per pair, which is the cost Finding 4 measures.
**Rejected here: a progress indicator or a background job** — either
makes a 20 s wait *legible* rather than shorter, and whether one is
still wanted is not knowable until the cost is re-measured.

**Deferred, not rejected: the verify pass.** Author's ruling — the
third materialisation stays for now; being read-only makes it both the
cheaper one to move and the safer one to leave.

### Semantics

- **The insert is one of three full materialisations** (traced
  2026-09-22). The assignment set is built as Python objects at the
  insert (`_generate.py:528`), again by
  `recompute_self_review_classification`'s whole-session
  `select(Assignment, Reviewer, Reviewee)` once per instrument
  (`_generate.py:557`), and again by the identical select in
  `verify_self_review_classification` (`_generate.py:1084`). **This is
  why the item was widened**: rung 1 alone removes a third at best, and
  the rows are rebuilt as entities one line later.
- **The recompute pass writes, so column tuples need a write path.** It
  **compares** `assignment.is_self_review` to the freshly computed value
  and only counts and assigns on a difference (`_self_review.py:203`).
  With no entity there is nothing to mutate, so the changed rows go back
  as one Core `update` keyed by id — and **the stored flag must be in
  the projection**, or the `changed` count callers read cannot be
  reproduced. That is the whole contract: a projection of
  `id`, `instrument_id`, `reviewer_id`, `reviewee_id`, the `Reviewee`
  and `is_self_review`.
- **The `group_keys` coupling is one attribute, and it is the trap.**
  `_group_key_by_assignment` reads `assignment.reviewee`
  (`app/services/responses/_group_reconciliation.py:123`) — a
  many-to-one lazy load that resolves from the identity map **only
  because the same query loaded every `Reviewee`**. Column tuples remove
  that attribute, so the reviewee is passed explicitly;
  `classify_self_review` already holds it. `group_keys` needs a variant
  taking ids + reviewees. Everything else it reads is `id`,
  `instrument_id`, `reviewer_id` and `reviewee_id`
  (`_group_reconciliation.py:122`).
- **The existing verify pass is rung 2's oracle.** It recomputes
  independently and **raises `AssertionError` in a test env** on drift
  (`_generate.py:1088`), so every test that regenerates assignments
  already fails if the rewritten recompute classifies differently. Rung
  2 adds cases, not an oracle.
- **The flush is load-bearing and stays.** A Core insert leaves no
  identity-map entries, so the passes after it must keep seeing the rows
  through the flush — the property rung 1 establishes **before**
  changing the insert.
- **`is_self_review` is omitted at the insert site**, relying on the
  column's Python-side `default=False` — so rung 1 names the Core form:
  `db.execute(insert(Assignment), [dicts])` applies Python-side
  defaults, a multi-VALUES `insert().values([…])` does not behave
  identically.
- **`include` is per row** (`pair_include` from the diff), so the
  payload is a list of dicts with per-row values, not one shared
  default. `created_by_mode` likewise carries the enum's value per row.
- **An empty `diff.to_insert` must issue no statement.** A Core
  `insert()` handed an empty list is an error on some dialects rather
  than a no-op.
- **Both dialects, and the audit envelope is unchanged.** Executemany
  behaves on Postgres and SQLite alike but `rowcount` does not, so the
  audit event's `counts` keeps coming from the diff, which computes it
  before the insert either way.

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

**The bench is not re-takeable here** — re-checked 2026-09-22:
`pg_isready` answers *no response* on 5432 (client present, no cluster),
and `tools/bench_roster_scale.py` refuses a non-loopback `DATABASE_URL`
by design. Rung 3 discloses rather than assuming a figure.

### PR ladder

1. **Rung 1 — the bulk insert, flush property first.** Lands a test
   that the post-insert self-review verify pass sees every inserted row,
   *then* the Core insert under it. **Must not touch** Validate, Invite,
   the recompute pass, or the diff computation.
2. **Rung 2 — the recompute pass.** `group_keys` gains its
   ids-and-reviewees variant, `recompute_self_review_classification`
   drops to a column-tuple select and a Core bulk `update`. **Must not
   change** the classification rule or the verify pass — the existing
   in-test `AssertionError` on drift is the oracle.
3. **Rung 3 — re-take Finding 4, or disclose that it could not be
   re-taken.** `guide/app_responsiveness.md` Finding 4 gains the
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

- Do either of the self-review passes rely on the ORM identity map
  rather than on the flush? **Partly answered by the trace**: the
  group path's `assignment.reviewee` resolves *from* the identity map
  today, which is why rung 2 must pass the reviewee explicitly. Whether
  anything else does is settled by rung 1's test, written before the
  insert changes.

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
**§1.10** carries it. **4 of 33** in-scope rows are machine-comparable:
13 have a bare `**N**`, 13 have one self-contained command, 4 have
both.

**The 29 are qualified, not sloppy** — *"67, of which 52 are
unmentioned"*, *"8, of which 1 is button markup"*, *"5 / 11 / 16"*.
The qualifier is what makes the figure true and what makes it
uncomparable, so raising coverage means forcing bare integers and
trading the qualifier away. Article VI's own disqualifier.

**The rung still found a live error, which is the argument it cuts
against itself.** Of the 4 comparable rows, **1 was wrong at its own
anchor**: Item 7 published *"datalists in the lobby template: 1"*
against a command yielding **2**, and the template is byte-identical
between that anchor and `a62d40c` — a **mis-measurement, not drift**
(elements counted, lines commanded). Corrected in Item 7's table. So
the re-run's hit rate on its own 4 rows is 1 in 4, and the decision is
*still* no, on two grounds the hit rate does not touch: it would
**execute shell out of a freely-edited markdown cell** in CI, and
against HEAD it re-creates the very drift-versus-staleness ambiguity
rung 1 existed to remove.

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
  §1.10 carries the measurement. **4 of 33** rows are machine-comparable,
  and the other 29 are qualified rather than sloppy.
- **What is the cutoff, and in what unit?** Named six times above and
  **defined nowhere** — found 2026-09-22 when the author asked what the
  item still needed. Rung 1 cannot be built without it, because
  *"sections landing on or after the cutoff"* needs a way to tell when
  a section landed, and a section carries no date until this item gives
  it one. **Decided by:** the author. Recommendation: **a segment-number
  comparison on the plan file**, not a date on the section — the shape
  Item 2's `LEGACY_BEFORE_SEGMENT` already set, derivable from the
  filename with no git archaeology and no allowlist. A date cutoff would
  need `git log` per section to answer the same question.

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

**Owners stays deferred**, as the superseded entry itself recommends:
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

- **Ordering is the mechanism, and it is the analogy the other fields
  already use** (author's ruling, 2026-09-22: *follow the analogy of
  other fields where the form overrides the CSV update*). `POST
  /sessions` parses the form, calls `sessions.create_session`, then
  dispatches the staged Quick Setup uploads, of which the settings CSV
  is the **last** — so the box's `set_tags` call goes **after** that
  block, and a settings CSV's `session_tags[]` rows are discarded when
  the box is non-empty. That is what form-wins means for the other five
  fields too: whole-field, not merged.
- **The precedence itself is precedent, not invention.**
  `_apply_session_metadata` resolves each field by one of two rules —
  *fill-blanks* for `name`, `code`, `description`, `deadline`,
  `help_contact`, so the form wins (its docstring names this flow), and
  *force-apply* for the other twelve keys it writes, where the CSV wins
  because they are *"session config, not operator-typed identity"*. All
  13 Create form fields overlap the CSV: the same 5 form-wins, and 8 of
  the twelve CSV-wins (the other four are not on the form). A typed tag
  is operator-typed.
- **Rejected: making `_apply_session_tags` fill-blanks**, which is the
  literal per-field rule and would have been the tidier home for it.
  `tests/unit/test_apply_session_config.py::test_round_trip_carries_session_tags`
  pins the opposite — *"the destination pre-seeds a stale tag that must
  be dropped"* (18P PR D2) — and `_run_quick_setup_settings` is shared
  by three flows, one of them `POST /sessions/{id}/import-config` on an
  **existing** session. Ordering delivers the ruling without touching
  either.
- **Empty box writes nothing**: no `set_tags` call, so a settings CSV's
  tags apply unopposed and no audit event is emitted.
- **Bad input is silently skipped, matching the lobby.** `set_tags`
  catches `normalize_tag`'s `ValueError` per tag and drops that one, so
  an over-long tag disappears without an error. Both surfaces share the
  service; Create gains no error affordance the lobby lacks.
- **Partial failure follows the handler's existing per-block shape.**
  The session is created and committed before the tag write, exactly as
  it is before every other Quick Setup block, and `set_tags` commits on
  its own; a DB error there leaves a created session with no tags and
  redirects with the block's error flag.
- **Comma-delimited, matching the lobby's `name="tags"`**, so one habit
  works on both surfaces. `normalize_tag` decides the stored form and a
  repeated tag collapses.
- **No lifecycle gate applies** — the session does not exist yet, which
  is why Create is the easy surface and Session Home is not (the
  superseded entry records that blocker and it stays out).
- **The force-apply path re-runs no ordering check, and that is safe —
  traced 2026-09-22, not assumed.** The route validates End ≥ Start and
  Release-from ≥ End before create; the CSV force-applies the same
  datetimes afterwards unchecked, and no Validate rule covers ordering.
  **Every consumer guards itself** — the release window stays shut
  unless the session `is_expired` whatever the anchors say (**19F PR
  2a**, motivated by exactly this path), scheduled activation fires
  only from `validated`, and past-deadline reminders are skipped with
  an audit event. So the check is an interactive-path courtesy, not a
  correctness boundary; the spec edit says so rather than leaving a
  reader to infer a hole.

### Judgment calls — decided

- **The author's slot over the superseded plan's** (2026-09-22).
- **Tags only; Owners stays deferred** (2026-09-22) — a different size
  of work, as that entry says itself.
- **Scaffold first** (2026-09-22) — `CLAUDE.md` requires it for a new
  card, so the inert card is rung 1 and the write is rung 2.
- **The form wins over the settings CSV, by precedent rather than by
  invention** (2026-09-22) — following the identity-versus-config split
  already implemented rather than adding a second philosophy.
- **And it wins by ordering, not by changing the applier** (author's
  ruling, 2026-09-22, *follow the analogy of other fields*) — the
  write goes after the settings block; `Semantics` has what that rules
  out and why.

### Blast radius (measured)

Taken 2026-09-22 at `0ca204b`.

| what | count | command |
|---|---|---|
| tag mentions on the page | **0** | `grep -c -i tag app/web/templates/operator/session_new.html` |
| the write path | **1** function, `set_tags` | `grep -n "^def " app/services/session_tags.py` |
| `vocabulary()` call sites | **2**, both the lobby's views | `grep -rn "vocabulary(" app/ --include='*.py'` |
| lines with an inline `style=` | **8**, of which **1** is button markup (`.btn-pair`, line 121) | `grep -n 'style="[^"]*"' app/web/templates/operator/session_new.html` |

**That last row corrects the superseded entry's *"8 inline-styled
buttons"***: seven are layout wrappers and an `h3`, so rung 3's `.btn`
ride-along is one pair.

### PR ladder

1. **Rung 1 — the scaffold.** The half-width card in place with real
   copy and an inert input. **Must not** write anything.
2. **Rung 2 — the write.** `set_tags` after the settings-CSV block, per
   the ordering in `Semantics`. **Must not** change
   `_apply_session_tags`, and **must not** add typeahead — that is
   Item 7.
3. **Rung 3 — the `.btn` pair on this page**, per `CLAUDE.md`'s
   convention, asking first if either button does not fit a canonical
   role.

### Definition of done

- A session created with tags in the box has them, asserted through the
  route rather than the service.
- **A create carrying both a typed tag and a settings CSV keeps the
  typed tag and only it**, asserted through the route for both CSV
  shapes: no `session_tags[]` rows (the case the wipe would silently
  lose) and rows carrying other tags (the case the ordering decides).
- **An empty box with a settings CSV carrying tags keeps the CSV's**,
  asserted — the other half of the rule.
- `test_round_trip_carries_session_tags` still passes untouched.
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

- ~~**Box or settings CSV wins** when a create carries both, and by
  what mechanism?~~ **Both answered 2026-09-22** — the form wins, on
  the rule already in `_apply_session_metadata`, and it wins by
  ordering the write after the settings block. `Semantics` carries the
  reasoning and what it rules out. Nothing is left open.

### Out of scope

- **Owners on Create** — a staged mini-editor, still deferred.
- **Session Home's config card**, whose `config_editing` gate would make
  tags editable in 2 of 5 lifecycle states where the lobby edits them in
  any — the superseded entry's recorded blocker.
- **Typeahead** — Item 7.
- **The absent-section wipe on an existing-session re-import.** With no
  section-presence flag, a settings CSV carrying no `session_tags[]`
  rows is indistinguishable from one asking for none, so
  `POST /sessions/{id}/import-config` clears the session's tags. The
  ordering above makes Create immune; fixing it for that route is a
  candidate entry of its own, not a rung here.

### Doc impact

- `spec/sessions_overview.md` — the tag write surfaces it lists gain
  Create (Item 6).
- `guide/deferred_consolidated.md` — the superseded entry marked as
  superseded in part, with Owners and Session Home still deferred
  (Item 6).
- `spec/csv_contracts.md` — the settings CSV's apply semantics state
  the two rules (fill-blanks for operator-typed identity, force-apply
  for config), the tag section's wipe-on-absence, **the Create-page
  ordering that puts the typed box after the CSV**, **and why the
  force-apply path needs no ordering re-check** (each consumer guards;
  see `Semantics`). Audited 2026-09-22: neither that spec nor
  `spec/settings_inventory.md` states any of it, so the rule lives only
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

## Item 8 — a pytest node id cited in live prose resolves

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
| live prose (the 72 files `LIVE_PROSE` already covers) | **2** | 2 |
| `guide/archive/` | **3** | **0** |

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
| node-id citations in `LIVE_PROSE` | **2** | the scan in `Opportunity` |
| stale citations in `guide/archive/` | **3** of 3 | the same scan, archive corpus |
| class-based tests in the suite | **0** | `grep -c "^class Test" tests/ -r` |
| parametrised node-id citations, any corpus | **0** | the same scan, `\[` in the name |
| `tests/unit/test_doc_references.py` | **~320** lines, 4 checks today | `grep -c "" tests/unit/test_doc_references.py` |
| production LOC | **0** | the item adds a test only |

### PR ladder

1. **Rung 1 — the check.** One test in
   `tests/unit/test_doc_references.py`, plus a mutation proving it
   fails on a renamed citation and a live floor asserting the scan sees
   the citations that exist. **Must not** widen `LIVE_PROSE` or touch
   the path / `§N` checks.

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
  excludes it today and one such citation exists. **Decided by:** the
  author, or the first stale instance there. Recommendation: leave it,
  since widening `LIVE_PROSE` changes a corpus three checks share.

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
