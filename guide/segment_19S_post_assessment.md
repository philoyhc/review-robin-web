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
promoted, rehomed or closed with its reason. **Item 2 is the first
thing promoted out of it** — E4's gateable half.

**Entry tags are stable.** `E1`–`E8` never renumber; a promoted entry
keeps its tag and gains the item number beside it (E4 → Item 2).

---

## Item 1 — the register of what the two end-of-window reads surfaced

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

#### E1 — Prepare inserts one ORM object per pair

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

#### E2 — the bench headline is a dated fact, not a standing one

`guide/app_responsiveness.md` is written around *it was not a database
problem* — SQL under 9% of any slow page. 19R.3 moved the counting into
SQL and Invitations is now ~84% SQL, so the headline inverted inside
the same window that wrote it. `guide/codebase_assessment_22sep.md` §8
move 3: re-take the bench, not the code, and ask the next performance
question of real data. **Trigger:** deployment concluded with
representative data — the synthetic bench cannot answer it.

#### E3 — the ≥1,000 LOC watchlist lives only in a document that archives

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

#### E5 — the prose about the work is wrong more often than the work

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

#### E6 — a new guard has no evidence bar

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

#### E7 — plans overrun their own length budget

`guide/codex_assessment_21sep.md` §7: 19R's plan closed at **1,541
lines for eight items**, against the `segment-plan` skill's ~120 per
item and ~250 per segment, and doc/spec/guide now totals 170,163 lines.
The skill already names the cause — `Status` and answered open
questions growing after the thinking is done — and already sets the
budget and the compaction rule
(`.claude/skills/segment-plan/SKILL.md`, "Length"). What is missing is
anything that notices, and 19R's items each compacted at their own
close and still landed here. **This file is itself past that ~250**, on
eight entries and two items with no `Status` yet, and **Item 2 came in
at ~160 against the ~120 item budget after two deliberate trim
passes** — so the budget's stated cause is not what got either there,
which is a data point for whatever E7 becomes. **Trigger:** same as E4, and it shares E4's
objection — measuring this means judging prose.

#### E8 — two findings 19R recorded, did not fix, and has now archived

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

### Open questions

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
