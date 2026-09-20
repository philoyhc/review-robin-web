# App responsiveness at roster scale — where the time actually goes

**Investigation only — not planned, not scoped, no lift trigger.** Asked
2026-09-20: on a large session (1,000 reviewers, 1,000 reviewees) the
Assignments, Invitations and Responses pages take a while to load, Session
Home takes longer than it used to, and the Workflow actions are slow. *Is
there still room to optimize?*

There is, and the room is not where the question implies. **This is not a
database problem.** SQL is never more than 9% of any page measured below,
no index is missing, and adding one would change nothing. Five of the six
slow pages are slow for a single shared reason, and it is the same reason
on all five.

## How these numbers were taken

`tools/bench_roster_scale.py`, against a local `postgres:16` cluster with
`alembic upgrade head` applied — not the suite's in-memory SQLite, so the
planner, the indexes and the per-statement cost are real.

```bash
python3 tools/bench_roster_scale.py seed --code BENCH1     # state A
python3 tools/bench_roster_scale.py bench --session 3 --runs 1
python3 tools/bench_roster_scale.py pin-rule --session 3   # → state B
python3 tools/bench_roster_scale.py post --session 3 --path /workflow/prepare
python3 tools/bench_roster_scale.py bench --session 3 --runs 1
```

**Two states, because the lifecycle state changes the answer.**

- **A — `draft`, never generated.** 1,000 reviewers × 1,000 reviewees, 2
  instruments × 3 response fields, 5 reviewees per reviewer per instrument:
  10,000 assignment rows, 1,000 invitations, 18,000 response rows.
- **B — `validated`, after Prepare.** The same rosters with one
  `MATCH reviewer.tag1 same_as reviewee.tag1` rule pinned on both
  instruments and Prepare run: **200,000** assignment rows.

State B is the realistic one. An operator who has clicked Prepare and is
deciding whether to Activate sits in it.

**What these numbers are not.** Wall-clock is this container's CPU, one
connection, no network between app and database. Azure adds a hop per
query, which makes finding 2 worse and leaves findings 1, 3 and 4 exactly
where they are — they are Python-bound. Read the SQL / Python split and
the query count, not the milliseconds.

## The measurements

**State A** — `draft`, 10,000 assignment rows, no rule pinned:

| page | total | SQL | Python | queries | HTML |
|---|---|---|---|---|---|
| Lobby | 11 ms | 2 ms | 9 ms | 4 | 257 KB |
| Session Home | 347 ms | 62 ms | 285 ms | 38 | 279 KB |
| Assignments | **10.6 s** | 108 ms | 10.5 s | 50 | 547 KB |
| Invitations | 3.1 s | 1.6 s | 1.4 s | **2,036** | 751 KB |
| Responses | 3.6 s | 1.7 s | 2.0 s | **2,034** | 516 KB |
| Validate | **10.4 s** | 89 ms | 10.3 s | 70 | 235 KB |
| Setup: reviewers | 110 ms | 50 ms | 60 ms | 28 | 514 KB |
| Setup: reviewees | 113 ms | 51 ms | 62 ms | 28 | 501 KB |

**State B** — `validated`, 200,000 assignment rows, one rule pinned:

| page | total | SQL | Python | queries | HTML |
|---|---|---|---|---|---|
| Lobby | 11 ms | 2 ms | 9 ms | 4 | 257 KB |
| Session Home | **14.8 s** | 650 ms | 14.1 s | 82 | 280 KB |
| Assignments | **25.0 s** | 726 ms | 24.3 s | 94 | 817 KB |
| Invitations | **20.6 s** | 1.9 s | 18.7 s | **2,080** | 752 KB |
| Responses | **24.6 s** | 1.9 s | 22.7 s | **2,078** | 509 KB |
| Validate | **26.1 s** | 824 ms | 25.3 s | 113 | 233 KB |
| Setup: reviewers | 2.0 s | 234 ms | 1.8 s | 28 | 513 KB |
| Setup: reviewees | 2.1 s | 243 ms | 1.9 s | 28 | 501 KB |

And the two Workflow actions, same state:

| action | total | SQL | queries |
|---|---|---|---|
| `POST /workflow/prepare` | **74.8 s** | 17.4 s | 282 |
| `POST /workflow/activate` | 12.1 s | 0.3 s | 48 |

## Finding 1 — the rules engine runs on page load, and a narrower rule costs more

`assignments.staleness_by_instrument` (`app/services/assignments/_generate.py`)
answers *would regenerating change which pairs exist?* by running the engine
once per instrument and diffing its fan-out against the stored rows. Its
docstring is explicit that this is deliberate: the verdict is the engine's
own diff, so it cannot drift from what Generate would do. That is a good
reason, and it is charged on every render:

- **Assignments** calls it directly, in every state
  (`app/web/views/_assignments.py`).
- **Validate** reaches it through the staleness rule in
  `app/services/validation.py`.
- The **shared workflow card** runs the whole validation report inline
  whenever the session is `validated` (`app/web/views/_workflow_card.py`).
  Six pages build that card — Session Home, Assignments, Validate,
  Invitations, Responses and Extract Data
  (`grep -rn "build_workflow_card_context(" app/web/routes_operator/`).

So in `validated`, six pages each pay a full engine walk per instrument.
That is the step from state A to state B for Session Home: 347 ms → 14.8 s,
with 82 queries. Nothing queried more; the page started running the engine.

**The cost does not depend on the rule.** `app/services/rules/engine.py`
materializes the entire cartesian product and sorts it *before* any rule is
consulted, then tests every pair. Medians over 5 runs on the seeded rosters:

| rule set | time | pairs kept |
|---|---|---|
| Full Matrix (no rules) | 2.29 s | 1,000,000 |
| one `MATCH` keeping a tenth | **3.52 s** | 100,000 |

A narrow rule is *slower* than no rule, because narrowing is work done
after the million-pair list exists. At two instruments that is the ~10 s
floor in state A's Assignments and Validate rows, and it is a floor: no
rule an operator can author gets under it.

Two supporting figures from `profile --path /assignments` at state A:
**12,000,003** calls to `normalize_email` and 4,000,000 to `_pair_sort_key`
in one page render.

## Finding 2 — Invitations and Responses issue two queries per reviewer

`monitoring.per_reviewer_progress` loops over every reviewer. It already
hoists two things out of that loop — the group keys and the response rows —
and says in its own comments why. Two lookups stayed inside, in
`responses.reviewer_session_state` (`app/services/responses/_core.py`):
`_reviewer_assignments` and `_instrument_fields_by_id`. At 1,000 reviewers
that is 1,000 + 1,000 queries, on both pages, in both states.

Locally that is ~1.7 s of SQL. On Azure, where each round trip crosses a
network, it is the finding that degrades most. The Python side is worse
than the SQL: the per-reviewer reload re-materializes assignment rows the
function already holds — **415,024** ORM instance constructions in one
Invitations render at state B.

The fix is the one this function has already applied twice: pass the
session-wide data in. The assignments are *already loaded* in
`per_reviewer_progress` before the loop starts.

## Finding 3 — five counts are answered by fetching the rows

```bash
grep -rn "len(db.execute(" app/            # 5 hits
```

`len(db.execute(select(Model.id)).all())` asks Postgres for every id and
counts them in Python. At 200,000 assignment rows that is 200,000 rows on
the wire for one integer. `csv_imports._count_assignments` is 1.17 s of the
Setup reviewers page's 2.0 s at state B — the whole of why a roster page
that was 110 ms became 2 s, and nothing about the *roster* changed.

A sixth site is worse in kind: `responses.session_response_count` loads
every `Assignment` as an ORM object to decide whether any instrument is
group-scoped, and in the common case then runs a `COUNT` anyway — while its
caller in `app/web/views/_quick_setup.py` only asks whether the result is
`> 0`.

## Finding 4 — Prepare inserts 200,000 rows one ORM object at a time

`app/services/assignments/_generate.py` adds one `Assignment()` per pair
inside the insert loop. Prepare (Generate + Validate + Invite) measured
**74.8 s**, of which 17.4 s was SQL — so roughly a minute of it is Python
building ORM objects and the unit of work flushing them.

A single click that blocks for 75 seconds with no progress feedback is
indistinguishable from a hang, and the operator's natural response —
clicking again — is the worst available move. Whether a request that long
survives the deployed front end is a question for the dev slot, not for
this container.

## What is not slow

- **The lobby**: 11 ms, 4 queries, unchanged between states. Its cost
  scales with the number of sessions, not roster size — a different axis,
  not measured here.
- **The Setup rosters in state A**: 110 ms. The 200-row page cap is doing
  exactly its job (`guide/roster_search_filter.md` documents that cap and
  why it exists).
- **SQL, everywhere**: 0.5%–9% of page time. Every slow page is slow in
  Python.

## The room that is left, in order of what it is worth

1. **Stop running the engine to render a page.** Worth ~10 s per page per
   two instruments, on six pages, and effectively all of Validate.
   Everything below is worth less than this, and this one changes whether
   the others matter.

   The shape to copy is already in the codebase and already solves the part
   that looks hard. `instruments.cached_group_pair_count` /
   `cached_group_pair_stamp` cache a pair count against a **content hash of
   the roster, the pinned rule's definition and `group_kind`**, recomputing
   on a mismatch at read — so nothing has to remember to invalidate on a
   roster edit, a rule edit or a re-pin. A staleness verdict wants the same
   stamp over the same inputs.

   One trap for whoever picks this up: *18J Rec C*'s wire-up note in
   `guide/deferred_consolidated.md` offers to mirror "the existing
   `cached_eligibility_stamp` pattern". Those columns do not exist — Wave 5
   PR 5.2 dropped them with the library tier, as
   `app/db/models/session_rule_set.py` records. The group-pair cache is the
   surviving precedent.
2. **Hoist the two per-reviewer lookups** (finding 2). Worth 2,000 queries
   and ~400,000 ORM objects per render, on two pages. Small, local, and the
   same function already does it twice — the cheapest real win here.
3. **Count with `count()`** (finding 3). Five one-line changes, plus one
   real fix in `session_response_count`.
4. **Bulk-insert the generated pairs** (finding 4). Worth part of 75 s.
5. **Precompute the pair sort key.** Measured in isolation: sorting the
   1M-pair list drops from 0.87 s to 0.31 s when the normalized email is
   computed once per person instead of once per pair. Only worth doing
   inside a wider engine change — on its own it removes a twelfth of the
   cost that item 1 removes entirely.

**The relationship to work already scoped.** `guide/deferred_consolidated.md`
carries *18J Rec B — Engine fast path* and *18J Rec C — Single-side
predicate indexes*, both parked with the lift trigger "a pilot deployment
scales past mid-three-digit reviewer / reviewee counts … or a synthetic
benchmark on a representative roster confirms the cost model's projection."
**This is that benchmark, and it confirms the projection.** But it also
re-aims the two: Rec B's lazy generator short-circuits once `limit` matches
accumulate, which serves the preview path and does *not* serve staleness,
which needs the whole set. Rec C — intersecting id sets before materializing
pairs — is the one that helps here, and the measurement above (narrow rule
slower than no rule) is the argument for it.

## Open questions

1. **Is a 1,000-person session real?** The same question
   `guide/roster_search_filter.md` leaves open, and the same answer decides
   both. The pilot's own sessions are 154.
2. **Is the staleness verdict worth its price on every page?** It is
   displayed on Assignments and Validate. The other four pages build the
   card, and pay the engine walk, to render a summary count.
3. **Should the `validated` state cost less than the others?** It is the
   state an operator sits in while deciding to Activate, and it is the only
   state that runs validation inline on six pages.
4. **What does the deployed front end do with a 75-second POST?** A dev-slot
   question; this container cannot answer it.

## Out of scope

- Any fix. This is an investigation; nothing here is scheduled.
- The reviewer-facing surfaces and the participant pages — the report was
  about the operator surfaces, and only those were measured.
- The lobby's own scaling axis (many sessions rather than many people).
