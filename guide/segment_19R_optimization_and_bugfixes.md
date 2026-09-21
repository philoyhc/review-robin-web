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

**The segment stays open.** Items 1–3 are the three changes that were
measured to take every page under a second; Item 4 is a defect found
while they were being planned. Further items land as measurement or a
report turns them up — `## Later candidates` at the end holds the
optimization moves already measured but not scheduled.

**Re-take any number here with** `python3 tools/bench_roster_scale.py`
(`tools/README.md` has the recipe). Every figure below is from state B
of that document: 1,000 reviewers × 1,000 reviewees, two instruments,
200,000 assignment rows, session `validated`.

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

**Rung 1 landed 2026-09-21** — `tests/integration/test_monitoring_rollup_parity.py`,
12 cases, no app change. The harness is two implementation lists, one
per rollup; rungs 2 and 3 append the SQL form and every case becomes a
parity test with no new test code.

**What the oracle pins that a naive `GROUP BY` would get wrong**: the
dedupe key is `(instrument, group_key)`, not the group alone;
`last_response_at` is a max over two nestings, rows-of-an-assignment
then assignments-of-a-reviewee; the reviewee side requires
`submitted_at`; the invitation join carries `last_reminder_at`, without
which `summary_counts` undercounts and both reminder loops skip everyone
(Codex P2); and both `ORDER BY`s matter, because the operations routes
paginate whatever order they are handed (Codex P2). Thirteen mutations,
all caught — four of them only after the fixture grew to carry the case,
which is what the fixture's own comments record.

**Two asymmetries between the rollups are now pinned**, neither
obviously intended, both shipped: an inactive reviewer is dropped by the
reviewer rollup and still counted by the reviewee one, and a draft is a
completion to the reviewer rollup but not to the reviewee one. If either
should change, that is its own item.

**Expectations are hand-derived, not captured.** Two disagreed with the
code on the first pass and the code was right both times: SQLite drops a
`DateTime(timezone=True)` offset, so the oracle compares instants in
UTC — which would otherwise have bitten rung 2 from the Postgres side.

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
  hybrid (aggregate per `(instrument, group_key)`, then fold in Python)?
  *Decided at rung 2 by the parity harness; the hybrid is acceptable —
  it is bounded by group count, not by assignment count.*

### Out of scope

- The reviewer-facing surfaces' own rollups, unless the parity work makes
  them free.
- Changing what "complete" means.

### Doc impact

- `spec/operations_pages.md` — the Progress and coverage columns are now
  computed by aggregate query; the contract they render is unchanged
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
| routes reaching them | 6 | create-session, four per-slot, submit-all |
| call sites already correct | 3 | `grep -rn "field_labels_captured" app/web/routes_operator/` |

No schema change, no migration, no template change.

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
- `grep -rn "field_labels_captured" app/web/routes_operator/` shows five
  call sites, not three.
- A bare-header quick-setup upload clears an existing override, matching
  the card.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19R.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- Is rung 2's gate worth its weight, or does rung 1's test over every
  entry point cover it? *The author decides after rung 1; the argument
  for the gate is that this defect is what "a new entry point forgot"
  looks like.*

### Out of scope

- Observers' labels — there are none by design.
- The settings-bundle path: `field_labels.*` was deliberately retired
  from it (19C Item 1) and stays retired.

### Doc impact

- `docs/status.md` — row when the item lands (Item 4).
- `spec/csv_contracts.md` — carried unwaived on purpose. No change is
  expected, since the contract already states the Quick Setup slots
  behave as the per-page uploads do. If the build finds otherwise this
  bullet becomes the edit; if not, the close waives it with that reason.
  Either way the close says which (Item 4).

---

## Later candidates

Measured in `guide/app_responsiveness.md`, not scheduled. Each becomes an
item when someone picks it up; none blocks Items 1–3.

- **Bulk-insert the generated pairs.** Prepare blocks **74.8 s** for
  200,000 rows, 17.4 s of it SQL, adding one `Assignment()` per pair. A
  click rather than a page, so it needs progress feedback or a background
  job as much as it needs speed.
- **Turn on compression.** No compression middleware exists: the lobby
  ships 1,584 KB where gzip would send 95 KB (16.5×), the roster pages
  6–7×. One middleware line — **after** checking what the dev slot's
  front end already sends (`curl -sI -H 'Accept-Encoding: gzip'`), which
  the agent's container cannot see.
- **Precompute the pair sort key.** Sorting the million-pair list drops
  from 0.87 s to 0.31 s when the normalized email is computed once per
  person. Only worth doing inside a wider engine change.
- **Anything the next measurement finds.** The tool is committed;
  re-running it after these items is how Item 4 gets written.
