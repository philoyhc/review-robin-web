# Segment 19R — Optimization and bugfixes

Opened 2026-09-21 off `guide/app_responsiveness.md`, which measured the
operator surfaces on a 1,000 × 1,000 roster and found five of six slow
pages slow for one shared reason. That document is the evidence base for
Items 1–3; this one is the build.

**Named for both halves** (2026-09-21, after Item 4 landed): the segment
opened as *Optimization*, and the first thing added to it was a defect.
Rather than keep filing fixes under a name that excludes them, the
segment is the open container for this round of operator-surface work —
performance and correctness both.

**Items close independently**, so each carries its own `### Doc impact`
and `### Status` and there is no segment-level manifest —
`python3 tools/close_check.py 19R.1` reads Item 1's. The archive half of
the last definition-of-done line applies only when the segment's final
item closes; an item close leaves this file in `guide/`.

**The segment stays open.** Items 1–4 closed 2026-09-21: Items 1–3
were the three changes measured to take every page under a second, and
Item 4 was a defect found while they were being planned. **Item 5 is
open** — the bench re-set that followed those closes left one cost
unexplained, and `guide/app_responsiveness.md` Finding 6 attributes it.
Further items land the same way, as measurement or a report turns them
up; that document also holds the later candidates already measured but
not scheduled.

**Re-take any number here with** `python3 tools/bench_roster_scale.py`
(`tools/README.md` has the recipe). Items 1–4's figures are from state B
of that document — 1,000 reviewers × 1,000 reviewees, 200,000
assignment rows, `validated` — which was the bench when they were
measured. **The bench moved on 2026-09-21** to 200 × 200 full matrix;
Item 5 and anything after it use that. `guide/app_responsiveness.md`
has both and says which is which.

---

## Item 1 — R3: count by counting

### Opportunity

Five call sites answer *how many rows* by fetching every id and calling
`len()` on the list:

```bash
grep -rn "len(db.execute(" app/            # 5 hits
```

At 200,000 assignment rows that is 200,000 rows on the wire for one
integer. `csv_imports._count_assignments` alone is **1.17 s of the Setup
reviewers page's 2.4 s** — a roster page that went 110 ms → 2.4 s while
nothing about the roster changed. A sixth site is worse in kind:
`responses._core.session_response_count` loads every `Assignment` as an
ORM object to decide whether any instrument is group-scoped, and its
caller in `app/web/views/_quick_setup.py` only asks whether the result
is `> 0`.

Measured ceiling for this item alone: **Setup reviewers 2.4 s → 0.27 s.**
That page runs neither the engine (Item 2) nor the rollups (Item 3), so
nothing else in this segment removes its cost.

### Decision

Replace the five with `select(func.count())`, and give the `> 0` caller
an `EXISTS` rather than a count of anything.

*Alternative rejected:* leave them and let Items 2–3 carry the segment.
Rejected because the Setup pages are untouched by either, and this is the
cheapest change here — hours, no design, no schema.

### Semantics

- `len(select(Model.id).all())` and `select(func.count(Model.id))` agree
  exactly for these five: no joins, no `DISTINCT`, no limit. Empty
  session → `0` either way.
- `responses._core.session_response_count` is **not** a plain count: it
  deduplicates group fan-out, counting one cell per
  `(reviewer, instrument, group_key, response_field)`. That path stays.
  Only the `> 0` caller changes, to a query that can stop at the first
  row.
- A caller that relied on the fetched rows warming the identity map
  would silently lose that. Rung 1 reads all twelve `existing_count`
  callers before changing any of them.

### Judgment calls — decided

- **`EXISTS`, not `COUNT(*) > 0`** for the boolean caller (2026-09-21):
  the answer is a boolean and the query should be allowed to stop.
- **The name collision stays** (2026-09-21): `session_lifecycle` also has
  a `session_response_count`, and it already uses `func.count()`. Two
  functions, one name, different contracts — a readability problem, not a
  performance one, and renaming a public helper is not this item's job.

### Blast radius (measured)

| what | count | command |
|---|---|---|
| `len(db.execute(` sites | 5 | `grep -rn "len(db.execute(" app/` |
| `existing_count(` callers | 12 | `grep -rn "existing_count(" app/ --include=*.py \| grep -v "def "` |
| `_count_assignments(` callers | 4 | same shape |
| `count_pairs(` callers | 1 | same shape |
| `responses.session_response_count` callers | 6 | `grep -rn "session_response_count(" app/ --include=*.py \| grep -v "def \|__init__\|session_lifecycle"` |

No schema change, no template change.

### Status

**Closed 2026-09-21. Three rungs exactly as planned** — the five plain
counters (#2515), the `> 0` caller (#2516), this close.

**The ceiling held.** `bench --session 3 --only "Setup:" --runs 3` on
`Bench BENCH1` (200,000 assignments): Setup reviewers **2.4 s → 277 ms**
against a projected 0.27 s, Session Home on a 10,000-assignment draft
237 ms → 85 ms. The reviewers page is SQL-bound now, 236 ms of the 277,
and that is the counting itself — one `count(id) WHERE session_id = 3`
is a 21 ms parallel index scan. Nothing further is worth doing there.

**Three things the plan got wrong**, all from the cold read:

- Ladder rung 2 promised `_quick_setup` an `EXISTS` helper;
  `session_lifecycle.session_has_responses` already was one.
- `Blast radius` says **6** callers of
  `responses.session_response_count`; there were **3**. Its `grep -v`
  named the module `session_lifecycle` while every call site reads
  `lifecycle.session_response_count(` — the import alias — so it
  filtered nothing and counted the twin's callers as this one's. The
  collision the judgment call above left alone defeated the measurement
  of its own twin.
- The four new `session_id` count predicates could have gone through a
  `session_scoped_count` beside `_queries.session_scoped`; copied
  instead, and worth writing at the site that needs a fifth.

**Reads: one `diff-reviewer`**, at rung 2 over the cumulative diff
(`abd2948f..HEAD`), five findings — the three above, plus two fixed in
`c6742898` (a count of eight that was seven; a `count_pairs` test gap
asserting `0 == 0`). Codex found nothing on either code rung. Three
mutants survived rung 1's first pass, all because the fixture held one
session. The last two `Doc impact` bullets were added at this close.

### PR ladder

1. **The five plain counters.** `csv_imports` (×2), `relationships`,
   `assignments/_coverage` (×2) → `func.count()`, after reading every
   caller. Must not touch `session_response_count`.
2. **The `> 0` caller.** `_quick_setup` gets an `EXISTS` helper; the
   dedupe path in `responses._core.session_response_count` is left
   exactly as it is.
3. **Close.** `Status`, `docs/status.md` row, close check.

### Definition of done

- `grep -rn "len(db.execute(" app/` returns nothing.
- A test asserts each changed helper returns what the old form returned,
  including on an empty session.
- `python3 tools/bench_roster_scale.py bench --session N --only "Setup:"`
  shows the reviewers page under 0.5 s on a 200,000-row fixture.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19R.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- Does any `existing_count` caller depend on the rows being loaded as a
  side effect? **No** — all twelve read at rung 1; every one consumes
  only the integer, so none kept its fetch.

### Out of scope

- Renaming either `session_response_count` (judgment call above).
- The group-dedupe path itself — that is Item 3's territory.

### Doc impact

- `docs/status.md` — row when the item lands (Item 1).
- `guide/todo_master.md` — mark Item 1 shipped in the 19R queue entry (Item 1; added at the close).
- `guide/README.md` — the `app_responsiveness.md` index row still read "Investigation only — not planned" and carried an over-broad "under 9% of every page"; both corrected (Item 1; added at the close).

---

## Item 2 — R1: cache the staleness verdict

### Opportunity

`assignments.staleness_by_instrument` answers *would regenerating change
which pairs exist?* by running the rules engine once per instrument on
every render — on Assignments and Validate always, and on four more
pages whenever the session is `validated`, through the shared workflow
card (six builder call sites:
`grep -rn "build_workflow_card_context(" app/web/routes_operator/`).

The engine's floor at 1,000 × 1,000 is **2.29 s per instrument** and a
*narrower* rule costs **more** (3.52 s), because the million-pair list
is built and sorted before any rule is consulted; `app_responsiveness.md`
has the measurement. Ceilings: **Validate 26.5 s → 1.8 s, Assignments
23.2 s → 1.7 s, Session Home 14.1 s → 3.7 s.**

### Decision

Persist the whole **`InstrumentReconcileState`** — the verdict *and* the
`eligible` / `self_reviews_excluded` counts it carries — against a
**content hash of what the verdict is derived from**, recomputing on a
mismatch at read. Same shape as
`instruments.cached_group_pair_count` / `cached_group_pair_stamp`.

**A verdict-only cache would not work** (Codex P1 on #2514):
`app/web/views/_assignments.py` renders `state.eligible` and reads
`self_reviews_excluded`, so it would leave the engine running on the
page this item exists to fix.

*Alternatives rejected:* **18J Rec C** makes the walk cheaper but still
per render — deferred as the follow-on if the cache misses often.
**Stop building the card on the four pages that only render a summary
count** removes a feature rather than a cost.

### Semantics

- **The hash covers every input the engine reads**: both rosters
  including `status`, the relationships rows, the pinned rule's
  definition, the instrument's `rule_set_id`, `group_kind`, and the
  session's self-review setting. Anything left out is a wrong "fresh".
- **And the materialized rows, which are no engine input at all**
  (Codex P1 on #2514). The verdict is a *diff* against the instrument's
  existing `Assignment` rows, so Generate or delete-all changes the
  answer while every engine input holds still — a cached `stale=True`
  would outlive the regenerate that made it fresh. Hence
  `replace_assignments` writes the new state through, having just
  computed the diff, **and** the stamp carries a component of the row
  set that no write leaves unchanged, so an unforeseen path invalidates
  rather than lies. Row count plus `max(id)` is one such component; the
  build picks the form against that requirement.
- **A miss recomputes**, and so does an unreadable stamp; a version
  prefix makes a shape change a miss rather than a silent hit.
- **Never serve a stale "fresh".** It is the operator's only notice that
  generated rows no longer match their rules, and
  `app/services/validation.py` records this rule having once been a
  no-op that "*reports a clean bill on exactly the thing it exists to
  catch*". Never-generated is still not stale, as today.

### Judgment calls — decided

- **Columns on `instruments`, not a new table** (2026-09-21): the
  verdict is per instrument, as the precedent beside it is.
- **Hash the inputs, not the result** (2026-09-21): hashing the fan-out
  means computing it, which is the cost being removed.
- **`reconcile_impact` does not share the cache** (2026-09-21): a
  different question, on a confirmation path, not a render.

### Blast radius (measured)

| what | count | command |
|---|---|---|
| app call sites of `staleness_by_instrument` | 2 | `grep -rn "staleness_by_instrument" app/ --include=*.py` |
| pages reaching it through the card | 6 | `grep -rn "build_workflow_card_context(" app/web/routes_operator/` |
| test files naming it | 1 | `grep -rln "staleness_by_instrument" tests/` |
| migration | 1 | new columns on `instruments`, plus the write-through in `replace_assignments` |

### Status

**Closed 2026-09-21. Four rungs as planned** — columns (#2518), stamp
(#2519), wiring (#2520), this close. Nothing struck.

**Measured on `Bench BENCH1`** (1,000 x 1,000, 200,000 rows), cold vs
warm: Session Home **11.9 s -> 0.67 s**, Assignments **13.1 s ->
0.67 s**, Validate **14.0 s -> 0.99 s**; the helper itself 10.95 s ->
0.056 s, same verdict. Against a definition of done of 2 s. Invitations
(20.6 -> 8.4 s) and Responses (24.8 -> 12.0 s) keep their 2,000-query
N+1 — Item 3, now the dominant cost on both.

**The shape that changed: the read path flushes and never commits.** A
guard that would make committing safe cannot be written — `write_event`
ends in `db.flush()`, so a handler that has emitted an audit event has
work `db.new` / `db.dirty` can no longer see. And since `get_db` only
closes and `deps.py` commits before the view, **no plain GET persists a
warm**: the read-through warms within a request, and the cache is
durable only where the write-through put it. After any invalidating
edit every render recomputes until the next Generate, so the figures
above are the post-Generate state.

**Four columns, not the two `Decision` implied** — the state is three
values and a stamp — and `String(80)`, not the precedent's `String(64)`,
for the version prefix.

**Five things this item asserted turned out to be readings**, which is
Item 1's lesson again and the segment's:

- `SessionRuleSet.seed` was missing from the digest (Codex P1, #2519).
  The boundary — "everything `_session_rule_set_to_schema` reads" — was
  right; the field list was built from the constructor's named
  arguments, and `seed` rides in the `options=` block below them. It is
  the `fallback_seed` for a `RANDOM` quota, so a change selects a
  different pair set with every other input equal.
- "Committing would commit a half-finished promotion" was backwards:
  `_workflow_card.py` validates *before* it promotes, and
  `mark_validated` commits, carrying the warm.
- "A guard that never fired, because autoflush emptied `db.new`" was
  true of the test session only; the app uses `autoflush=False`.
- The column-coverage gate covers `SessionRuleSet` alone, not every
  model the diff reads.
- `count` + `max(id)` is a **Postgres-only** invalidator: SQLite reuses
  ids freed from the top, so delete-then-insert can return both figures
  over a different row set. No live bug, but SQLite is the dev and unit
  dialect. Recorded in `docs/database.md`.

**Reads: one `diff-reviewer`** over the cumulative diff
(`6ed3040e..HEAD`) at rung 3, plus Codex per rung. The cold read traced
every roster, rule, group-key and self-review input and found **no
second stamp gap** — the four wrong readings above are what it found
instead. Both over-coverage calls were confirmed: roster `status` is
over-coverage, `Relationship.status` is not.

**Doc impact grew by two at rung 3** (`spec/assignments.md`,
`spec/architecture.md`) and the close found the
`guide/deferred_consolidated.md` bullet had named **Rec C** for a
`cached_eligibility_stamp` note that is **Rec E**'s. Rec E is retired:
every name in it — the helper, the columns, `session_library.py` — went
in Wave 5. Rec C is re-aimed at this cache instead.

**The `spec-writer` close pass found three of its own**, all acted on:
the requalified "cannot disagree" claim existed in a **third** place,
`spec/validate_page.md`'s rule row — the one a reader reaches from the
rule's own Fix link, and the one with no cache explanation beneath it;
the stamp-coverage sentence read as exhaustive while omitting the
caller's self-review override; and "`reconcile_impact` runs on a
confirmation path rather than a render" was wrong — it runs inside
`build_workflow_card_context` too, gated on the `prepare_confirm`
query parameter. *Gated rather than unconditional* is the real
distinction, and it is what the file says now.

**Pre-existing, found en route, for whoever gets there first:**
`spec/instruments.md` calls `instruments.stale_generated` "inert by
design", which 19N reversed; `validation.py`'s docstring for that rule
contradicts both the code and `spec/assignments.md`, and carries the
unqualified "cannot disagree" claim as well; and
`app/web/views/_assignments.py`'s module docstring still points at
`session_library.evaluate_session_rule_eligibility`, retired in Wave 5.
(A `preview.py` listed under `app/services/rules/` that never existed
was dropped here, since the close was editing that line.)

### PR ladder

1. **Migration + columns**, no reader and no writer; round-trips on
   Postgres in `ci-postgres`.
2. **The stamp helper** with its own unit tests: same inputs → same
   stamp, one test per input that changes it.
3. **Wire the read-through** in `staleness_by_instrument` and the
   write-through in `replace_assignments`; rung 2's tests become the
   guard.
4. **Close.**

### Definition of done

- A test mutates each hashed input in turn — add a reviewer, edit a
  relationship, change the rule, re-pin the instrument, flip
  self-reviews — and asserts the verdict is recomputed.
- A test regenerates a stale instrument and asserts the next read says
  fresh, with no engine run between.
- A cache hit supplies `eligible` and `self_reviews_excluded` without an
  engine run.
- `bench --session N` shows Validate and Assignments under 2 s on the
  200,000-row fixture.
- `alembic downgrade base && alembic upgrade head` passes on Postgres.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19R.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- Should a cache miss be observable to an operator, or stay invisible?
  **Invisible**, at the default — nothing in the build argued otherwise,
  and the bench is the evidence that hits happen, which is what an
  observability counter would have been for.

### Out of scope

- Any change to the engine itself — 18J Recs B and C stay deferred.
- Caching the validation report as a whole.

### Doc impact

- `spec/reconciling_regeneration.md` — the staleness verdict is now
  cached against a content stamp; say what invalidates it, and requalify
  two sentences the cache makes conditional: the shared-diff "cannot
  disagree" claim, and "the engine evaluation is in-memory and cheap",
  which is the opposite of this item's `Opportunity` (Item 2).
- `spec/assignments.md` — its "Staleness" section owns this contract and
  says the preview and the verdict "share the engine's diff, so they
  cannot disagree"; `reconcile_impact` still always walks it while
  `staleness_by_instrument` may not (Item 2; added at rung 3 by the cold
  read).
- `spec/architecture.md` — the `app/services/assignments/` module map
  gains `_reconcile_cache.py` (Item 2; added at rung 3 by the cold
  read).
- `spec/validate_page.md` — the `instruments.stale_generated` row
  carried the same unqualified "cannot disagree" claim, and is the one
  place a reader arrives at from the rule's own Fix link (Item 2; added
  at the close by `spec-writer`).
- `docs/database.md` — the four new `instruments` columns (Item 2).
- `guide/deferred_consolidated.md` — 18J Rec C's lift trigger and its
  stale `cached_eligibility_stamp` wire-up note (Item 2).
- `docs/status.md` — row when the item lands (Item 2).

---

## Item 3 — R2: roll per-person progress up in SQL

### Opportunity

`monitoring.per_reviewer_progress` and `per_reviewee_coverage` load every
`Assignment` and every `Response` in the session as ORM objects and count
them in Python. With Items 1 and 2 applied, a single Responses render
still constructs **408,027** ORM instances, while the rollup logic
itself (`_state_from_assignments`) is 1.17 s of it.

**The obvious fix is not this one.** Removing the 2,000-query N+1 those
pages carry takes the query count to 78 and leaves the page as slow as it
was: the queries were never where the time is. `guide/app_responsiveness.md`
records that measurement, because it is the one that picks this item's
shape.

Measured ceilings: **Responses 24.9 s → 11.4 s on its own; 0.42 s with
Items 1 and 2.**

### Decision

Compute both rollups as aggregate queries. Land `per_reviewee_coverage`
first — it is the simpler shape — and keep today's Python implementation
alongside as the parity oracle until a test says the two agree.

*Alternative rejected:* hoist the two per-reviewer lookups out of the
loop, which is what finding 2 of the investigation first proposed. Its
own numbers do not support it.

### Semantics

- **A group-scoped instrument counts once per group**, not once per
  member (Segment 13C). This is the part that resists a plain `GROUP BY`
  and the part a rewrite will get wrong.
- `include=False` rows stay excluded, as today.
- "Complete" keeps its current definition — every required field with a
  non-empty value and a `submitted_at` — and the pill states keep their
  current thresholds. This item changes where the arithmetic happens,
  not what it says.
- The reminder scheduler (`scheduled_events/_reminders.py`) calls
  `per_reviewer_progress` outside any request, so the new form may not
  assume a request-scoped cache.

### Judgment calls — decided

- **Coverage before progress** (2026-09-21): one side at a time, and the
  reviewee side has no invitation join.
- **Parity test as the gate, not review** (2026-09-21): the Python form
  stays in the tree until the test passes on a fixture that includes a
  group-scoped instrument.

### Blast radius (measured)

| what | count | command |
|---|---|---|
| app call sites | 7 | `grep -rn "per_reviewer_progress(\|per_reviewee_coverage(" app/ --include=*.py \| grep -v "def "` |
| test files naming either, or `reviewer_session_state` | 7 | `grep -rln "per_reviewer_progress\|per_reviewee_coverage\|reviewer_session_state" tests/ --include=*.py` |
| non-request caller | 1 | `app/services/scheduled_events/_reminders.py` |

### Status

**Closed 2026-09-21. Four rungs as planned** — the parity oracle
(#2522), `per_reviewee_coverage` (#2523), `per_reviewer_progress`
(#2524), this close. Nothing struck.

**Measured, and the definition of done is not met.** Invitations
**8.4 s → 1.36 s**, Responses **8.6 s → 1.52 s**; queries 2,079 → 78
and 2,074 → 73; ORM instances per render 408,027 → ~9,000. The target
was under 1 s. The rollup is 0.69 s and Session Home — same chrome, no
rollup — is 0.65 s, which is the 1.36 s: neither half alone gets there,
and the page furniture is a later item's.

**`per_reviewer_progress` is a hybrid, split by instrument kind** —
the answer to the open question below. `RollupParts` exists for the
addition: a pill cannot be summed, because `not started` does not say
whether the required fields were met.

**`per_reviewee_coverage` needed no hybrid, and `Semantics` was wrong
about why.** It calls the group dedupe "the part that resists a plain
`GROUP BY`" — true of the reviewer side; this rollup has never deduped
groups, it counts assignments. `Semantics` is also too narrow on
"complete": required fields plus a `submitted_at` is the reviewee side
only. Neither definition changed here.

**Three asymmetries between the rollups are now pinned**, none
obviously intended, all three pre-existing: an inactive reviewer,
a draft, and a `required` field that is not `visible` each count on one
side and not the other. Each is its own item if it should change; the
directions and the reasons are in `spec/operations_pages.md`, not here.

**The oracles outlive the close.** Both promised to go "until the item
closes"; the parity file parametrizes both, so deleting either deletes
half the cases holding the rewrite to the old answer. Kept, with the
docstrings rewritten to say they go when something better holds that
line, not on a date. Sixteen mutations against them, all caught, four
only after the fixture grew to carry the case; two more against the
mixed-fixture guards in `test_monitoring_prefetch.py`.

**Two `diff-reviewer` reads** — rung 3's over the item's cumulative
diff (`46482b64..HEAD`), and rung 4's own (`9a505099..HEAD`, since the
close reopened `tests/`) — plus Codex on each PR. Between them,
**three behavioral defects, all with one shape**: a guard whose
fixture could not reach the case it was trusted to cover. The reviewer
side lost `_instrument_fields_by_id`'s `visible` filter, so an
un-pinned chip's field read as outstanding and both reminder loops
would have kept emailing a reviewer who had answered everything shown;
the grouped fallback still prefetched the whole session; and its query
had dropped `joinedload(Assignment.reviewee)`. The ORM-row guard's
docstring *said* its fixture had no group-scoped instrument — that
sentence was the defect, written down and not read as one. `_mixed`
now carries both kinds.

**The close's own lesson is one slip made four times**: a truth about
the per-reviewee-instrument path written as a claim about the rollup
as a whole, caught twice by the close's readers and twice more by
Codex, each time with the correct qualifier already sitting in a
commit message or three lines down the same section. Rung 4's read
also turned up eleven prose findings, two of which became `Doc impact`
bullets this section did not have.

**The budget table in `spec/operations_pages.md` was re-taken, not
edited.** All three pages are flat in the roster now — 49 / 35 / 30,
unchanged from 25 × 25 to 200 × 200, against a table that ran to 434.
The pre-19R commit measured 49 for Assignments too, never the 43 the
spec printed, which is why the section now says flatness is the
contract and the figures are the reading.

### PR ladder

1. **The parity harness.** A fixture with a group-scoped instrument and a
   test that asserts two implementations agree, with only the Python one
   present. Proves the oracle before anything depends on it.
2. **`per_reviewee_coverage` in SQL**, behind the parity test.
3. **`per_reviewer_progress` in SQL**, same treatment.
4. **Close.**

### Definition of done

- The parity test passes with both implementations, on a fixture that
  includes a group-scoped instrument and an inactive row.
- `tests/integration/test_monitoring_prefetch.py` gains the non-regression
  half for this change — the pages do not scale with assignment count —
  in the shape that file already uses for the 19K.3 prefetch.
- `bench --session N` shows Invitations and Responses under 1 s on the
  200,000-row fixture with Items 1 and 2 landed.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19R.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- Can the group dedupe be expressed in one query, or does it need a
  hybrid? *A hybrid, split by instrument kind: SQL's `TRIM` does not
  reproduce Python's `strip()` in the group key. Bounded by
  group-scoped assignments, not by group count as rung 2 first said —
  so an all-group session at roster scale gains nothing, which the
  code states.*

### Out of scope

- The reviewer-facing surfaces' own rollups, unless the parity work makes
  them free.
- Changing what "complete" means.

### Doc impact

- `spec/operations_pages.md` — the Progress and coverage columns are now
  computed by aggregate query; the contract they render is unchanged.
  "What these pages cost to render" also needs re-taking: its "every
  rollup reads the session's response rows in one query" and the
  per-roster query budget under it are both false once the rollups stop
  reading rows at all (Item 3).
- `spec/instruments.md` — the list of surfaces that filter response
  fields by `visible.is_(True)` gains the operator-side reviewer
  rollup, and names the reviewee rollup as the exception (Item 3).
- `guide/todo_master.md` — mark Items 2 and 3 shipped, and retire the
  "under a second (30-50x)" projection the measurements did not reach
  (Item 3).
- `docs/status.md` — row when the item lands (Item 3).

---

## Item 4 — the quick-setup upload cards drop friendly labels

**A defect, not an optimization** — and the reason the segment carries
both words in its name. It depends on nothing in Items 1–3 and can land
in any order against them.

### Opportunity

Reported 2026-09-21: the upload card on **Create new session** did not
register the tag friendly labels, though the per-roster cards on
Reviewers and Reviewees do. Reproduced through the real routes — eight
uploads, each asserting `field_labels.resolve` after the import:

| upload path | friendly label |
|---|---|
| the three roster cards — `/reviewers/import`, `/reviewees/import`, `/relationships/import` | **kept** |
| Create new session (`POST /operator/sessions`) | **dropped** |
| `quick-setup/reviewers`, `/reviewees`, `/relationships` | **dropped** |
| `quick-setup/submit-all` | **dropped** |

Observers are excluded by design: `parse_observer_csv` discards the
captured map and `save_observers` has no parameter for it (19C Item 1).

**The spec already says this should work**, so the code is what is
wrong: `spec/csv_contracts.md` lists the Quick Setup roster slots as
*"same as per-page Upload — Quick Setup is a thin shell over the
per-entity primitives"*, and documents `field_labels_captured` as
reconciling the header's labels "upsert present, clear absent".

**The loss is not recoverable elsewhere**: 19C Item 1 retired
`field_labels.*` from the settings bundle precisely because roster
headers carry them, so a quick-setup upload leaves the operator
retyping every label and the extract → edit → re-upload round trip
stops being one.

### Decision

Pass `field_labels_captured=result.field_labels` at the two quick-setup
save sites, matching what `app/web/routes_operator/_shared.py` and
`app/web/routes_operator/_setup_relationships.py` already do.

*Alternative rejected:* make the argument keyword-only with no default.
It would have prevented this, but it reshapes a service signature that
`session_rehydrate` and the observers path also use — observers having
nothing to pass by design. Rung 2's gate catches the same class without
that.

### Semantics

- **"Upsert present, clear absent" now applies here too.** A bare
  `ReviewerTag1` header on a quick-setup upload will clear an override
  the operator had set, exactly as the card already does — a behavior
  change beyond "labels now register", and the half worth review.
- Observers stay as they are: no capture, no parameter, no change.
- The item changes **who calls** `field_labels.apply_import`, not what
  it does: whatever the card does for a header shape, the quick-setup
  path must now do identically.

### Judgment calls — decided

- **Fix at the two helpers, not the six routes** (2026-09-21):
  `_run_quick_setup_import` and `_run_quick_setup_relationships` are the
  single save sites behind every affected route.
- **No change to `save_*` signatures** (2026-09-21) — see above.

### Blast radius (measured)

| what | count | command |
|---|---|---|
| quick-setup save sites missing the argument | 2 | `grep -n "save_fn(" app/web/routes_operator/_quick_setup.py` and the `save_relationships(` call below it |
| routes reaching them | 5 | create-session, three per-slot (reviewers / reviewees / relationships), submit-all — **not** the observers slot, which reaches `_run_quick_setup_observers` and is out of scope |
| call sites already correct | 2 | `grep -rn "field_labels_captured" app/web/routes_operator/` |

No schema change, no migration, no template change.

### Status

**Closed 2026-09-21. Three rungs as planned** — the fix and its matrix
(#2526), the gate (#2527), this close. Nothing struck.

**The fix is two arguments** at the two save sites behind five upload
routes. Against the pre-fix tree: **6 failed, 4,602 passed**, every
failure in the new test file. That silence was the defect — a 303 and
a populated roster, and nothing noticed the labels going.

**The gate asks the router, not a list.** Twelve POST endpoints take an
`UploadFile`; each must be exercised by the matrix or carry a written
reason. A matrix can only enumerate the paths known when it was
written, which is the blind spot that let five routes break at once.

**Its own eyesight was wrong three times, each caught by a reader.**
Annotation source text (an aliased import or subclass invisible), the
module basename as key (`_shared.py` exists under two packages), and
one level of `get_args` (`list[UploadFile] | None`, Codex). Each time
the twelve real endpoints happened not to use the missed shape, so the
gate stayed green while seeing less than it claimed — the failure it
exists to prevent, wearing its own face. Shown, not argued: with the
one-level check and a real optional-batch route injected, the gate
passes and the route is invisible. The recogniser is pinned directly
now, seven upload shapes against five non-uploads.

**A claim is worth the command that proves it — the segment's lesson,
a fourth time.** Two of three blast-radius rows were wrong, one
feeding a definition-of-done line. And a first test run that looked
like a second bug was my own wrong lookup key:
`_VALID_SOURCE_FIELDS` keys pair-context slots `"1"`, not `"tag_1"`,
and the wrong key returns a fallback that reads exactly like a dropped
label. The card was never broken; the test file says so where the next
reader will hit it.

**Two findings recorded, not fixed.** The gate asks "takes an upload",
not "saves a roster", so `_rehydrate.rehydrate_commit` is invisible to
it — correct today, ungated, its own item. And
`spec/csv_contracts.md` spells `parse_relationship_csv`'s parameters
differently from the code: pre-existing, not bundled.

**`spec/csv_contracts.md` needed no edit, which is what carrying it
unwaived was for** — §1a, the §6 Quick Setup row and §5a were all
already right, and the code was what was wrong. Waived with that
reason. The `spec-writer` pass that confirmed it also found rung 2's
spec fix half-done: I corrected the create-session dispatch paragraph
and left the identical stale text in the submit-all one, the busier
path. Both corrected.

### PR ladder

1. **The fix and the test that pins it.** Both arguments, plus a test
   over every upload entry point — the cards green before and after, the
   five quick-setup paths red before and green after.
2. **The gate.** A test enumerating the roster upload entry points that
   fails when one saves without reconciling labels, so the next one
   added cannot repeat this.
3. **Close.**

### Definition of done

- Every upload entry point in the rung-1 test keeps the label.
- `grep -rn "field_labels_captured" app/web/routes_operator/` shows four
  call sites, not two.
- A bare-header quick-setup upload clears an existing override, matching
  the card.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19R.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- Is rung 2's gate worth its weight, or does rung 1's test over every
  entry point cover it? *Built at the author's direction. It does not
  overlap: the matrix asserts behavior on paths someone listed, the
  gate asserts that the router exposes no upload endpoint nobody
  listed. Twelve endpoints found, seven covered by the matrix, one by
  the create-session test, four exempt with reasons.*

### Out of scope

- Observers' labels — there are none by design.
- The settings-bundle path: `field_labels.*` was deliberately retired
  from it (19C Item 1) and stays retired.

### Doc impact

- `spec/quick_setup_card_spec.md` — **both** dispatch paragraphs named
  `_handle_quick_setup_import` (a route wrapper neither handler calls)
  and the save primitives as if reached directly. Corrected to the four
  `_run_quick_setup_*` helpers, which is what makes "fix the helper,
  reach every route" true (Item 4).
- `docs/status.md` — row when the item lands (Item 4).
- `guide/todo_master.md` — mark Item 4 shipped, so the 19R roadmap
  entry reads the same way Items 1–3 now do (Item 4).
- `spec/csv_contracts.md` — carried unwaived on purpose, and waived at
  the close: the build found the contract already correct on every
  point — §1a's "upsert present, clear absent", the Quick Setup row at
  §6, and §5a's prediction that an unedited template renames the tag
  columns — so the code was what was wrong (Item 4).
  <!-- doc-impact-waived: verified correct at the close; the item made the code match the contract rather than changing it. -->

---

## Item 5 — the readiness report reloads the session once per check

### Opportunity

`guide/app_responsiveness.md` **Finding 6** has the measurement and the
call paths. In one sentence: `validation.validate_session_setup` is
54% / 46% / 76% of Session Home, Assignments and Validate, because its
22 checks each load for themselves whatever they need and Validate
builds the whole report twice.

**The reason to fix it is consistency, not speed.** These are fast
indexed reads — 79 queries cost 97 ms — and will never be why a page
feels slow. What is worth fixing is twenty-two checks each deciding
independently what "the session's instruments" means, which is how two
of them come to disagree after someone edits one.

### Decision

Thread a per-run inputs object through `ValidationRule.check`, loaded
once by the orchestrator; checks read from it instead of querying. On
Validate, pass the already-computed issues into
`build_workflow_card_context` rather than letting it recompute.

*Alternative rejected:* a request-scoped memo cache under the existing
queries — no signature changes, same repeats removed, but it buys the
count without the consistency. Twenty-two checks would still each be
entitled to their own definition of the session, and the next one added
would still write its own load.

### Semantics

- **The issue list must not change** — same rules, same order, same
  `rule_key` / `fix_url` / `fix_anchor` stamping. The orchestrator's
  public signature stays; it has 6 callers and 8 test files.
- **The report is all-or-nothing per render, not a lifecycle-selected
  subset.** `build_workflow_card_context` runs it only under
  `validated_just_ran or is_validated`; on a `ready` session it runs
  **zero** checks, which is why that page measures 35 queries.
  `validate_session_setup` itself always iterates all 22 rules. A
  parity test that assumed a smaller subset on `ready` would be
  asserting a behavior that does not exist.
- **Inputs are loaded once per report run**, never cached across runs:
  a check must not see a roster older than the request that asked.
  Validate's second build goes away by passing the result, not by
  caching it.
- `scheduled_events/_activation.py:85` calls the orchestrator outside a
  request, so the inputs object may not assume a request scope.

### Judgment calls — decided

- **Inputs object over a memo cache** (2026-09-21) — see `Decision`.
- **Measured on `validated`** (2026-09-21): the state an operator sits
  in while deciding to Activate, and the only one where the report runs.

### Blast radius (measured)

| what | count | command |
|---|---|---|
| registered rules / check functions | 22 / 22 | `grep -c 'ValidationRule(' app/services/validation.py`; `grep -c '^def _check_' app/services/validation.py` |
| callers of the orchestrator | 6 | `grep -rn "validation.validate_session_setup(db" app/ --include=*.py` |
| test files naming it | 8 | `grep -rln "validate_session_setup" tests/ --include=*.py` |
| the double build | 1 page | `_operations.py:187` + `_workflow_card.py:122` |

No schema change, no migration, no template change.

### Status

**Landed as the ladder said; one Definition-of-done line was narrowed,
deliberately.** "No exact-repeat query in one run" now reads "none of
the report's own". Three repeats survive, all `staleness_by_instrument`
re-reading inside its own `_load_reconcile_inputs`; handing that engine
rosters the report already holds was rejected, because it caches each
verdict and flushes and its value is that it cannot drift from what
Generate would do. A second test pins the exception to the
`staleness_by_instrument` **call**: allowing its whole package let a
check call an assignments helper twice with neither test objecting
(Codex, #2533). Figures in `guide/app_responsiveness.md` Finding 6.

**`spec/validate_page.md` was carried unwaived against the expectation
of no change, and the build found otherwise** — §7's recipe documented
the two-argument `check`, so a rule written to the spec would have
raised `TypeError`. That is what carrying a bullet unwaived is for.
`spec/workflow_card.md` was a second one the plan had not named, found
by `spec-writer` at the close; both are in `Doc impact`.

**One cold read, two Codex reviews, two CI failures — every one found
a test rather than the code.** The read's own differential over six
shapes the fixtures miss came back byte-identical. `docs/status.md`
carries what each caught; two findings that are **not** this item's are
in `guide/findings_2026-09-21_validate_rules.md`.

### PR ladder

1. **Stop Validate building the report twice.** One call site, no
   signature change, the largest single win (112 → ~69), independent of
   the rest.
2. **The inputs object, loaded once and threaded through `check`.**
   It must carry **everything two checks both load**, measured rather
   than guessed — on the bench fixture that is the instrument list, the
   three roster lists, the roster non-empty probes, the per-instrument
   response-field and display-field presence, and
   `included_count_per_instrument`. The last three are per-instrument,
   so their repeat count grows with instrument count, not roster size.
   A parity test pins the issue list unchanged.
3. **The guard.** A test asserting the report issues no duplicate
   (statement, params) pair in one run, so the next check added cannot
   quietly reintroduce its own load. It goes after rung 2 because it
   fails until every repeated input above is covered — if rung 2 lands
   short, this is what says so.
4. **Close.**

### Definition of done

- ~~The readiness report issues **no exact-repeat query** in one
  run — 9 statements repeat today, 22 queries of 43.~~ Narrowed at
  rung 3: the report issues no exact repeat **of its own**, and the
  three that remain are the assignments engine's. Reason in `Status`;
  both halves are asserted in
  `tests/integration/test_readiness_report_cost.py`.
- Validate builds the report **once**.
- `validate_session_setup` returns the identical issue list, rule for
  rule, on every fixture the existing validation tests carry.
- Page query counts re-measured and Finding 6 annotated with the result.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19R.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- ~~Is Validate's second build load-bearing?~~ **No** — two call
  sites that did not know about each other, with nothing between them
  mutating the session and the card's one write path gated on a flag
  the Validate route never passes (rung 1).

### Out of scope

- **Which** checks run, and in what state. This item changes what a
  check costs, never the readiness verdict.
- The fixed queries outside the report — `session_status_pills` is 11
  per page, `build_setup_rows` 4. Same shape, smaller, and measurable
  again once the report stops dominating.

### Doc impact

- `guide/app_responsiveness.md` — annotate Finding 6 with the
  post-change counts; it is the evidence this item answers (Item 5).
- `spec/validate_page.md` — **the edit, not the waiver.** Carried
  unwaived on purpose against the expectation of no change; the build
  found otherwise. §5.1 and §7's "Adding a new rule" recipe still
  document `check(db, review_session)`, so a rule written to the spec
  today raises `TypeError` on its first run. Both, and the rule-shape
  line, take the third argument and name `ValidationInputs` (Item 5).
- `spec/workflow_card.md` — its signature listing for
  `build_workflow_card_context` gains the `issues` argument rung 1
  added, and points at `spec/validate_page.md` §5.1 for the
  hand-off-not-a-cache contract rather than restating it (Item 5;
  added at the close, found by `spec-writer`).
- `docs/status.md` — row when the item lands (Item 5).

---

## Item 6 — two rule-registry documents that stopped matching the registry

### Opportunity

`guide/findings_2026-09-21_validate_rules.md`, opened by the
`spec-writer` pass at Item 5's close. Two documents describe the
validation rule registry and neither matches it.

- `spec/validate_page.md` §3.2 lists `reviewees.unreachable_for_results`
  22nd of 22; `REGISTERED_RULES` has it 7th. The other 21 rows are in
  registry order, so this is an append where the code inserted.
  Registration order **is** a contract: §2.4 derives source order from
  it and `tests/integration/test_validation_issue_parity.py`'s golden
  is keyed on it, so a reader using the table to predict issue order
  gets it wrong. Predates 19R; the rule landed in W8.
- `spec/instruments.md` says `instruments.stale_generated` "raises no
  findings; it is inert by design". That is `instruments.no_rule_pinned`,
  described correctly in the same list's last bullet. The staleness check has
  been live since 19N — its own docstring narrates the Wave 5 PR 5.1 →
  19N window when it was not, which is the state this prose still
  describes as current.

### Decision

Fix both documents; change no code and add no gate.

*Alternative rejected* for the first: declare in §3.2 that the table
is not declaration-order. That would document a falsehood about the
other 21 rows, which are in registry order exactly.

*Alternative noted, not taken*: a test deriving §3.2's key column from
`REGISTERED_RULES`, which is the constant-derived shape
`tests/unit/test_doc_conventions.py` already uses and would have
caught this at W8. Left out because the author asked for the two
fixes; it remains available and is recorded here so the option is not
lost with the findings file.

### Semantics

- **No behavior changes.** Every edit is prose about code that is
  already correct — in each case the description was stale, not the
  implementation. ~~and no code changes~~: rung 2 added a test, rung
  3 rewrote a docstring and rung 4 rewrote four more across both
  trees, so the item touches `app/` and `tests/` while changing
  nothing either executes.
- **The `stale_generated` description stays conditional.** 19R Item 2
  requalified the "cannot disagree with Generate" claim as holding
  under the cache's stamp conditions; the replacement bullet says so
  and points at `spec/assignments.md` § *Staleness* rather than
  restoring the flat claim.

### Judgment calls — decided

- **One item rather than a plan-free PR** (2026-09-21, author's
  ruling): both edits touch live spec contracts, so the close's
  machinery — `close_check`, `spec-writer`, a `docs/status.md` row —
  is worth the overhead.

### Blast radius (measured)

| what | count | command |
|---|---|---|
| table rows vs registry | 22 vs 22, one misplaced | `diff <(grep -n 'key="' app/services/validation.py \| sed 's/.*key="\([^"]*\)".*/\1/') <(table key column)` |
| other prose naming the rule | 1 file | `grep -rln "stale_generated" spec/ docs/ guide/` |

**The second row was wrong twice over, and wrong in the item's own
way.** Its grep scoped out `app/` and `tests/`, where three of the
five bad descriptions lived — including the docstring on the function
itself, which is the whole of rung 3. It also never said what it was
counting. Left as measured rather than silently revised, per the
segment-plan rule; corrected here:

| what | count | command |
|---|---|---|
| files mentioning the key, as the row's grep scoped it | 12 | `grep -rl "stale_generated" spec/ docs/ guide/ \| wc -l` |
| …with `app/` and `tests/` added | 19 | `grep -rl "stale_generated" spec/ docs/ guide/ app/ tests/ --include='*.md' --include='*.py' \| wc -l` |
| **passages stating what the rule does, and wrong** | **5, in 4 files** at the time of measuring; **9, in 6 files** once rung 4's own read swept `app/` and `tests/` for the family rather than for the key | the files named in `Status`; the rest either assert the key without describing it, or describe it correctly |

Mentioning the key and describing the rule are different questions,
and the original row measured neither deliberately.

No schema, no migration, no template. Rungs 2, 3 and 4 touch `tests/`
and `app/`, none executably — rung 4 both trees.

**Four of the nine are invisible to any `stale_generated` grep**, which
is why the corrected table above is still not the last word: three test
and view docstrings describe the rule without naming its key, and
`_assignments.py`'s `is_stale` carries the flat "cannot disagree"
claim without naming the rule at all. Searching for the key finds
files; searching for the *claim* (`cannot disagree`, `no_rule_pinned`,
count-versus-count phrasing) is what found these.

### Status

**The ladder grew from one rung to four, each added by the author
after the previous landed** — the gate rung 1 deferred, then the third
description rung 2's read surfaced, then the fourth and the
exhaustiveness nit rung 3's read surfaced. Struck rather than
rewritten: `Out of scope` (the gate) and `Semantics`' "no code
changes" (rungs 2–4 touch `tests/` and `app/`, none executably).

**Nine wrong descriptions of one rule, in six files** — five found
by rung 4, four more by the read rung 4 owed. `spec/instruments.md`
called it inert, which is `no_rule_pinned`; its own docstring said the
`why` names three situations where it names two, claimed
never-generated is flagged where the engine's
`stale=bool(diff.existing_rows) and …` denies it, and carried the flat
"cannot disagree" claim 19R Item 2 made conditional — that sentence
needed requalifying **twice more** in this item, once in rung 1's own
draft; `test_validation_15E_rules.py` described the retired
count-versus-count, pinned-only basis and credited a test's silence to
unpinning; and `compute_staleness` claimed the view field and the rule
"share this one definition" when neither uses it. That helper is the
source the rest reproduced, it is **exported, tested and uncalled**,
and retiring it is deferred rather than decided.

**Rung 4's read caught rung 4 writing the sixth.** Fixing the
exhaustiveness nit, I wrote that the diff "also reads `group_kind` and
the session's self-review setting". It does read both, and only one
can move the verdict: `self_reviews_active` sets a pair's `include`
flag, while the diff is a difference of pair *keys*. The lever is the
instrument's `group_kind`, and only while the **pinned rule set**
excludes self-reviews — which is situation 1, so `group_kind` carries
the non-exhaustiveness alone. The phrasing came from
`_reconcile_cache`'s stamp inputs, which are deliberately a superset
of the verdict's determinants; reading a cache key as a causal list is
the specific mistake. It had already reached `docs/status.md` and a
commit message. Three more followed once the sweep went after the
*claim* rather than the key: two test docstrings still crediting
`instruments.no_rule_pinned` with carrying a signal it has not carried
since Wave 5 PR 5.3, and `_assignments.py`'s `is_stale` still making
the flat "cannot disagree" claim — the fourth and final survivor of
the sentence this item requalified three times.

**The specs needed no edit, which is worth recording as a negative.**
The read flagged the docstring's non-exhaustiveness as putting code
prose at odds with three spec passages stating the two situations
unqualified. They do not: `spec/validate_page.md` §3.2,
`spec/instruments.md` and `spec/assignments.md` § *Staleness* each
lead with the general criterion and put the two after a dash as
illustrations — the shape the docstring now takes. No `Doc impact`
bullet is owed.

**The blast radius failed in the item's own way.** Its grep scoped out
`app/` and `tests/`, which is where three of the five lived. Left as
measured per the segment-plan rule; the row above carries the
correction and the definition the original lacked.

**Four reviews, four different classes of finding.** `spec-writer`
corroborated rung 1 from the parity golden. Codex caught British
spelling in new prose, then this `Status` accumulating twice. The
rung-2 read found the gate passing *while recognizing nothing*
off-path and its row pattern stricter than its two siblings; the
rung-3 read verified the docstring on all four claims and caught this
plan instead; the rung-4 read — owed because rung 4 reopened `app/`
and `tests/` after the item's read — caught the new wrong sentence and
the three the key-based sweep could never have seen. Nothing any of
them raised is outstanding.

### PR ladder

1. **Both edits, and the close.** One slice: the findings file names
   exactly what to change, and neither edit can break the other.
2. **The gate** — added 2026-09-21 on the author's instruction, after
   rung 1 had landed. Same PR; see `Status`.
3. **The third description** — added 2026-09-21 on the author's
   instruction, after rung 2's cold read surfaced it. Same PR.
4. **The fourth and fifth** — added 2026-09-21 on the author's
   instruction, after rung 3's read surfaced the fourth and the fix
   for it surfaced the fifth.

### Definition of done

- §3.2's key column equals `[r.key for r in REGISTERED_RULES]`, in
  order, verified by diffing the two lists.
- `spec/instruments.md` describes `stale_generated` as the live check
  it is, without restoring the unconditional "cannot disagree" claim.
- `guide/findings_2026-09-21_validate_rules.md` retired to
  `guide/archive/` with its rows marked actioned, and both README
  index rows updated.
- A test in `tests/unit/test_doc_conventions.py` derives §3.2's key
  column from `REGISTERED_RULES` and fails on order, on membership,
  and on the table moving — each under a name that says which.
- `_check_instruments_stale_generated`'s docstring describes the rule
  the code implements: the criterion in both its halves, the two
  situations its `why` names given as the operator-facing examples
  they are, the cache qualification rather than the flat claim, and
  never-generated excluded.
- No passage in `app/` or `tests/` still describes `stale_generated`
  on the retired count-versus-count or pinned-only basis, credits
  `instruments.no_rule_pinned` with carrying a signal, or makes the
  flat "cannot disagree with Generate" claim: `grep -rn "disagree with
  what Generate" app/` returns nothing. (`_generate.py`'s "cannot
  drift from what Generate actually does" is a different claim, about
  deriving the verdict from the same function, and its own docstring
  requalifies it for the cache.)
- `compute_staleness`'s docstring says what it is — a helper with no
  caller in `app/`, whose basis differs from the rule's in three
  named ways — rather than claiming a shared definition.
- `spec/validate_page.md` §7 tells a rule author to add the §3.2 row,
  since the gate now makes that a CI failure rather than an oversight.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19R.6` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- None. Both fixes were adjudicated by the author before the item
  opened.

### Out of scope

- ~~The §3.2 order gate — see `Decision`.~~ Asked for by the author
  after rung 1 landed and built as rung 2; the `Decision` entry stands
  as the reasoning it was deferred on.
- Any behavior change to either rule. Both are correct as implemented.

### Doc impact

- `spec/validate_page.md` — move §3.2's
  `reviewees.unreachable_for_results` row to registry position 7,
  after `reviewees.duplicate_id` (Item 6).
- `spec/instruments.md` — replace the `instruments.stale_generated`
  bullet, which describes `instruments.no_rule_pinned`'s inertness,
  with the live check's behavior (Item 6).
- `spec/validate_page.md` — §7's "Adding a new rule" recipe gains the
  step for §3.2's table row, which rung 2's gate turns from an
  oversight into a CI failure (Item 6; added at the close by the cold
  read).
- `guide/README.md` — drop the retired findings row (Item 6).
- `guide/archive/README.md` — add the retired findings row (Item 6).
- `docs/status.md` — row when the item lands (Item 6).

---

## Item 7 — the `Instruction-Received` stamp is a campaign described as a standing rule

### Opportunity

`CLAUDE.md` "Where work runs" says **"The first command of a slice is
`date -u +%FT%TZ`"** and `rrw_sdd_in_practice.md` §6.4 says a slice's
first commit **"now carries"** the trailer. Measured on merge history
since 2026-09-04: **16 of 450 slices carry it (3.6%)**, all consecutive
(`#2495`–`#2516`), and none of the last 20. Two live passages in the
present tense describe behavior the repository stopped having on
`#2517`, and nothing catches it — `CLAUDE.md` says so itself ("No gate
checks it").

Worse, **§6.4 never records what the instrument measured.** It calls
the split "the next thing to instrument — done the same day", records
the instrumenting, and stops. The answer exists only in tool output:

```
$ python3 tools/pace_audit.py --cut 2460
== AFTER (PR >= #2460): 77 PRs
  turn p25 5.8  med 8.4  p75 12.8 | fit: fixed 9.5 min + 1.47 min per 100 LOC
  turn split on Instruction-Received (n=14): wait med 3.5 mean 9.5 | build med 3.0 mean 3.3
```

That result **qualifies §6.4's own claim**. §6.4 says of the 10–14
minute fitted floor: *"That floor is the instruction loop and the
context a slice loads, **not the build**."* Build is median 3.0 against
a turn median of 8.4 — a minority, around a third, not "not the build".
A claim the document asserts and its own instrument partly contradicts,
sitting unrecorded.

This is Item 6's defect class in the file that states the conventions.

### Decision

**Record the result; retire the standing instruction; keep the
instrument.** §6.4 gains the measured split and the qualification it
forces. `CLAUDE.md` / `AGENTS.md` describe a sampling campaign — stamp
when a figure is being re-taken, with `#2495`–`#2516` named as the
campaign that produced the current one — instead of a per-slice rule.
`tools/pace_audit.py` is not touched: its trailer support costs nothing
idle and `tests/unit/test_pace_audit.py` already covers both the
reported and the "needs 3" paths.

**Rejected: resume blanket stamping.** More `n` will not move
`wait ≈ build ≈ 3 min`, and a standing instruction that 96% of slices
ignore teaches every agent reading `CLAUDE.md` that its bullets are
aspirational — a compounding cost against a precision gain nobody
needs.

**Rejected: delete the trailer from `pace_audit.py` too.**
`constitution.md` VI is *retire rather than mechanise badly*; the thing
mechanised badly is the standing instruction, not the tool. The next
practice audit may want a fresh sample and should not have to rebuild
the reader.

### Semantics

- **Prose only.** No behavior change, no gate change, no tool change.
  Nothing under `app/`, `tests/` or `alembic/`.
- **`abe393cf` is not fixed.** This slice's own first commit is
  unstamped and stays that way; it is in merged history and rewriting
  it buys nothing.
- **The twins.** `CLAUDE.md` and `AGENTS.md` are byte-identical and
  `tests/unit/test_doc_references.py` enforces it — `cp` one to the
  other before committing.
- **`new_project_practices_setup.md:422`** carries the instruction into
  *new* projects, so leaving it propagates the standing-rule framing to
  repos that have never run the campaign. It changes with the others.

### Judgment calls — decided

- **Record the figure in §6.4 rather than in a new `guide/` artefact**
  (2026-09-21) — §6.4 is where the question was posed and where the
  *Re-take with* line already lives; a second home splits the answer
  from the method.
- **Name the campaign's PR range in `CLAUDE.md`, not just in §6.4**
  (2026-09-21) — an agent reading the conventions needs to know the
  stamp is dormant, not that it was once taken.

### Blast radius (measured)

| what | count | command |
|---|---|---|
| slices merged since 2026-09-04 | 450 | `git rev-list --merges --since=2026-09-04 origin/main` |
| …carrying the trailer on their first commit | **16** (3.6%), `#2495`–`#2516` consecutive | per-merge `git log -1 --format='%(trailers:key=Instruction-Received,valueonly)'` on `git rev-list --reverse $sha^1..$sha^2 \| head -1` |
| files naming the trailer | 7 | `grep -rln "Instruction-Received" --include='*.md' --include='*.py' .` |
| …of those, this item edits | **4** — `rrw_sdd_in_practice.md`, `CLAUDE.md`, `AGENTS.md`, `new_project_practices_setup.md` | the other 3 are `tools/pace_audit.py`, `tools/README.md`, `tests/unit/test_pace_audit.py`, all of which stay |

No code, no schema, no migration, no template, no test.

### Status

**The premise was half wrong, and the build found it in the first
command.** `Opportunity` said the stamp was carried by 16 of 450 slices,
"all consecutive (`#2495`–`#2516`), and none of the last 20" — read as
a campaign that ran and stopped. Re-measured at build over 464 slices:
**37 wrote the line and 16 parse.** Git reads only a commit message's
last block as trailers, so the 21 written in a paragraph of their own,
above `Co-Authored-By`, are **silently discarded** — present in the
text, absent to every reader. The practice did not stop at `#2516`; its
*recording* broke, and nobody could tell, because nothing checks
either failure.

Found the way it had to be found: the two slices that opened this item
(#2537, #2538) both stamped, and neither parsed. The rule's own author
tripped the failure twice in one afternoon while writing about it.

**The Decision survives and is better supported.** It rested on a rule
96% unfollowed; it is now a rule ~92% unwritten *and* silently
droppable when it is written. Recording the result, retiring the
standing instruction and keeping the tool all still follow. What
changes is the framing in every document: not "the campaign ended" but
"the campaign ran, and more than half its samples never reached the
reader".

**One opportunity surfaced and deliberately not taken.** A reader that
matched `Instruction-Received:` anywhere in the message rather than as
a git trailer would recover all 21 lost stamps and roughly double the
sample at zero ongoing cost. `Out of scope` forbids touching
`tools/pace_audit.py`, so it is named in §6.4 and left for the author
rather than folded in — widening a one-rung item on the strength of its
own finding is how a rung becomes a segment.

**The verification pass caught the denominator, in the failure mode
the tool documents.** The first measurement said 451 and the figure
reached three documents before `spec-writer` re-derived it as **464**.
Cause: `git log --since=2026-09-04` fills the missing time of day with
the *current clock*, so a bare date counts from whenever the command
ran — which is exactly why `tools/pace_audit.py` carries `since_arg`,
whose comment records "25 merges lost and recovered across three runs"
on 2026-09-20. The item about an unmeasured practice mis-measured it,
using the wrong form of the command the tool exists to get right. The
numerators were exact throughout; only the denominator moved, and the
conclusion is unchanged at 8.0% rather than 8.2%.

**Also carried: why 16 parse but the split is n=14.** `pace_audit`
additionally requires a stamp's timestamp to fall between the previous
merge and the first commit, which drops two. No document explained the
gap; §6.4 now does.

**`Definition of done` was written against the wrong numbers** and is
annotated rather than rewritten: its "n=14" and "`#2495`–`#2516`" lines
still hold (the parsed sample is unchanged), but the documents now say
more than those lines asked for.

### PR ladder

1. **All four documents, and the close.** One slice: the figure and the
   reframing are the same edit, and splitting them would leave one file
   asserting a practice another has just retired.

### Definition of done

- `rrw_sdd_in_practice.md` §6.4 states the measured split (`wait` med
  3.5 / `build` med 3.0, n=14, `--cut 2460`) and qualifies its own
  "not the build" sentence against it.
- §6.4 no longer says a slice's first commit "now carries" the trailer.
- `CLAUDE.md` and `AGENTS.md` describe the stamp as a campaign, name
  `#2495`–`#2516`, and are byte-identical
  (`tests/unit/test_doc_references.py` passes).
- `new_project_practices_setup.md` matches the new framing.
- Every one of the four documents that tells a reader to stamp also
  tells them the trailer goes in the message's **final block** — the
  failure that lost 21 of 37 stamps (see `Status`).
- `tools/pace_audit.py` and `tests/unit/test_pace_audit.py` are
  unchanged; `pytest tests/unit/test_pace_audit.py` still passes.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19R.7` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- ~~Re-run the campaign at a cadence, or only when a figure is being
  re-taken?~~ **Only when a figure is being re-taken**, the plan's
  assumed default, unchallenged at build. `CLAUDE.md` says so.

### Out of scope

- Any change to `tools/pace_audit.py`, including dropping the trailer
  reader. The instrument stays; see `Decision`.
- Re-stamping or rewriting `abe393cf` or any other merged commit.
- Re-taking the other §6.4 figures. This item records one that was
  already measured and never written down.

### Doc impact

- `rrw_sdd_in_practice.md` — §6.4 records the measured `wait`/`build`
  split and qualifies the "not the build" claim; the "now carries"
  sentence becomes a campaign record (Item 7).
- `CLAUDE.md` — "Where work runs": the stamp bullet becomes a campaign
  description naming `#2495`–`#2516`, not a per-slice instruction
  (Item 7).
- `AGENTS.md` — byte-identical twin of the above (Item 7).
- `new_project_practices_setup.md` — the trailer instruction it seeds
  into new projects matches the new framing (Item 7).
- `docs/status.md` — row when the item lands (Item 7).

---

## Item 8 — retire `compute_staleness`

### Opportunity

`assignments.compute_staleness` is a one-line predicate with **no
caller in `app/`**. It was the shared definition behind
`InstrumentStatusBlock.is_stale` and `instruments.stale_generated`;
both moved to `staleness_by_instrument` (19N), which diffs pair sets
rather than comparing counts, does not gate on pinning, and does not
flag a never-generated instrument — the opposite of this helper on all
three points.

Item 6 established that it is **the source the wrong descriptions kept
reproducing**: of the nine wrong passages that item fixed, the
count-versus-count and pinned-only framings all trace to this function
still sitting in the package, exported and tested, reading like the
live definition. Its own docstring now says so in 18 lines — longer
than the function, the tests and the export combined.

Item 6 left it deferred as "a public-surface removal". That framing was
wrong: this is an internal package export in a monolith with no
published API and no consumer.

### Decision

**Delete the function, its re-export and its four unit tests.** The
descriptions Item 6 corrected stay corrected because there is no longer
a second definition to drift back toward.

**Rejected: keep it and mark it deprecated.** A deprecation comment is
a fifth description of the same rule, in the place that produced the
other four. The docstring already explains at length why nothing calls
it; the honest end of that paragraph is a deletion.

### Semantics

- **No behavior change.** Nothing in `app/` calls it, so no code path
  changes. The four unit tests assert the dead predicate's arithmetic
  and go with it.
- **No spec change.** `grep -rn "compute_staleness" spec/` returns
  nothing; it was never a documented contract.
- **No doc gate fires.** `tests/unit/test_doc_references.py`'s
  `PATH_REF` matches backticked *repo paths*, not symbol names, so
  deleting a function trips nothing. (Deleting a whole routing module
  would trip `tests/unit/test_spec_coverage.py`; a single function does
  not.)
- **Historical prose stays.** `docs/status.md`, the archived plans and
  `guide/archive/sweep_2026-09-13_spec_history.md` narrate what was
  true when written and are not edited.

### Judgment calls — decided

- **A PR body, not a plan** (2026-09-21) — by the `segment-plan`
  skill's own "When not to write a plan" test this is one PR touching
  no schema, no spec contract and no user-facing surface. It is logged
  as an item only because the author asked for it in the segment's
  sequence; the reasoning above is the whole of it.
- **`test_assignment_staleness.py:5` keeps its mention** (2026-09-21) —
  it narrates why the per-rule eligibility helper retired, which is
  history, not a live claim.

### Blast radius (measured)

| what | count | command |
|---|---|---|
| callers in `app/` | **0** | `grep -rn "compute_staleness" app/ --include='*.py'` — 3 hits: the definition and the import/`__all__` pair |
| the function | 21 lines (18 of them the docstring rung 4 rewrote) | `awk '/^def compute_staleness/,/^    return rule_id/' app/services/assignments/_coverage.py` |
| the re-export | 2 lines | `app/services/assignments/__init__.py:36,89` |
| unit tests | 4 functions, 23 lines | `tests/unit/test_validation_15E_rules.py:120-142` |
| live prose to update | 2 module-docstring bullets | `tests/unit/test_validation_15E_rules.py:23,28` |
| specs naming it | **0** | `grep -rn "compute_staleness" spec/` |

Net ~45 lines deleted across 3 files. No schema, no migration, no
route, no template, no spec.

### PR ladder

1. **The deletion, and the close.** One slice.

### Definition of done

- `grep -rn "compute_staleness" app/` returns nothing.
- `tests/unit/test_validation_15E_rules.py` no longer tests the helper,
  and its module docstring no longer points a reader at it.
- `pytest -n auto` green and `ruff check .` clean, with `node` present.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19R.8` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

None. Item 6 established the facts; this item acts on them.

### Out of scope

- `staleness_by_instrument`, `InstrumentStatusBlock.is_stale` and
  `instruments.stale_generated`. All three are correct and stay.
- Editing historical prose in `docs/status.md` or `guide/archive/`.

### Doc impact

- `docs/status.md` — row when the item lands (Item 8).

---

## ~~Item 9 — a session cannot be tagged when it is created~~

**Moved to `guide/deferred_consolidated.md` Part C, 2026-09-21, unbuilt**
— the author's call: *"it's not absolutely essential."* Opened and
designed against a mock-up the same day; the entry there carries the
measurements, the settled three-change design, the Owners staged-write
constraint and the deferred Session Home half, so nothing is lost. No
`Doc impact` and no `Status`: the item never had a rung, so
`close_check.py 19R.9` has nothing to check and is not run.

---

## Later candidates

Moved to `guide/app_responsiveness.md` 2026-09-21, so this plan carries
only its own items and each candidate sits with the measurement that
motivates it.
