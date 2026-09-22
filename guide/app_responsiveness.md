# App responsiveness at roster scale — where the time actually goes

**Investigation only — not planned, not scoped, no lift trigger.** Asked
2026-09-20: on a large session (1,000 reviewers, 1,000 reviewees) the
Assignments, Invitations and Responses pages take a while to load, Session
Home takes longer than it used to, and the Workflow actions are slow. *Is
there still room to optimize?*

There is, and the room is not where the question implies. **This is not a
database problem.** SQL is never more than 9% of any *slow* page measured
below, no index is missing, and adding one would change nothing. Five of the six
slow pages are slow for a single shared reason, and it is the same reason
on all five.

## The bench, re-set 2026-09-21 — 200 × 200 full matrix

**The upper bound is 200 reviewers each reviewing 200 reviewees**
(author's ruling, 2026-09-21). A hundred people to review is not crazy;
the conditions under which a *thousand* are each asked to do it are
rare. Everything below this section is the 2026-09-20 investigation,
measured at 1,000 × 1,000 before segment 19R landed — read it for
*where the time went and why*, and read this section for *what it costs
at the size the app is built for*.

**A correction first, because it changes the numbers.** The first
attempt at this re-take used `pin-rule`, which applies
`reviewer.tag1 same_as reviewee.tag1` and keeps **a tenth** of the
matrix. A "100 × 100" fixture built that way gives each reviewer ten
reviewees, not a hundred — an order of magnitude lighter than the
workload under discussion, and the conclusions drawn from it were
correspondingly wrong (Codex, PR #2529). The fixtures below pin no
rule, so every instrument defaults to Full Matrix and each reviewer
reviews everyone.

| | **the bench** | half it | the old stress fixture |
|---|---:|---:|---:|
| roster | **200 × 200** | 100 × 100 | 1,000 × 1,000 |
| rule | **full matrix** | full matrix | tag cohort |
| reviewees per reviewer | **200** | 100 | 100 |
| assignment rows | **80,000** | 20,000 | 200,000 |
| Session Home | **441 ms** | 213 ms | 716 ms |
| Assignments | **389 ms** | 228 ms | 719 ms |
| Invitations | **646 ms** | 264 ms | 1,401 ms |
| Responses | **693 ms** | 273 ms | 1,467 ms |
| Validate | **482 ms** | 238 ms | 1,126 ms |
| Setup: reviewers | **196 ms** | 75 ms | 266 ms |
| Lobby, 1,003 sessions | **96 ms** | 107 ms | 117 ms |
| **Prepare** | **20.0 s** | **5.7 s** | 74.8 s |
| **Activate** | **0.7 s** | — | 12.1 s |

**Every page is under 700 ms at the upper bound**, so 19R Item 3's
"under a second" target — recorded as missed, because it was measured
at 1,000 × 1,000 — is met where it matters. The query counts are why it
holds: **78 on Invitations at 20,000 rows, 80,000 and 200,000 alike**,
flat in the roster as `spec/operations_pages.md` claims.

**The composition has inverted, and the document's headline with it.**
Below, "this is not a database problem" — SQL never more than 9% of any
slow page. At the bench it is **84% of Invitations** (540 ms of 646 ms)
and 83% of Responses. Nothing regressed; 19R moved the counting *into*
SQL and the Python it replaced is gone. But the sentence is a 2026-09-20
fact, not a standing one, and the next page-time question at this scale
is a query question.

**Prepare is the one thing that is not comfortable**, and Finding 4
stands as written. **20 seconds at the upper bound** is a click with no
feedback, and the 5.7 s at half the roster shows it climbing steeply —
80,000 rows is not where the per-object constant stops mattering. An
earlier draft of this section claimed the finding was overstated; that
was drawn from the tenth-of-the-matrix fixture and is withdrawn.

**Two costs do not scale with the roster at all**, and on a small
session they dominate:

- **The lobby is ~1,590 KB at every size** — 1,003 filler sessions,
  independent of the session being viewed. It is the largest response
  the app sends and 81 ms of its 96 ms is Python. Finding 5's
  compression case is unaffected by the re-set and still unactioned.
- **79–112 queries per session page at every size** — Session Home 79,
  Assignments 92, Validate 112, identical at 20,000 rows and at
  200,000. Fixed cost, not roster cost. **Attributed in Finding 6**:
  the readiness report reloads the session once per check. 19R Item 5.

Method: `tools/bench_roster_scale.py seed --code FM100 / FM200` with
**no `pin-rule`**, `post --path /workflow/prepare`, then `bench --runs
4`; Activate measured after the page bench, and confirmed real by the
session reaching `ready` rather than the Validate warnings detour. The
1,000 × 1,000 column is the pre-existing `BENCH1` cohort fixture
re-benched in the same run, except Prepare and Activate which are the
2026-09-20 figures; its Setup relationships / observers pages 404
because those features are off on that older fixture.

## Later candidates

Moved here from segment 19R's plan on 2026-09-21 — now
`guide/archive/segment_19R_optimization_and_bugfixes.md` — so the
segment carried only its own items and the measurements stay with the
evidence.

**They stay candidates.** At 19R's close both end-of-window reads asked
that the existence of a measured candidate not be turned into a queue,
so one is promoted to an item only when pilot scale or an operator
report crosses its stated trigger. Prepare's insert is the exception
under discussion, logged as entry **E1** of
`guide/segment_19S_post_assessment.md`.

- **Bulk-insert the generated pairs.** `assignments/_generate.py` adds
  one `Assignment()` per pair. **20.0 s at the bench**, 74.8 s at
  1,000 × 1,000 — see Finding 4. A click rather than a page, so it
  needs progress feedback or a background job as much as it needs
  speed.
- ~~**Find out what the 79–112 fixed queries per session page are.**~~
  *Answered 2026-09-21 — Finding 6. The readiness report reloads the
  session once per check, and Validate builds the whole report twice.
  Scoped as **19R Item 5**, so it is no longer a candidate.*
- **Turn on compression.** No compression middleware exists: the lobby
  ships ~1,590 KB where gzip would send 95 KB (16.5×), the roster pages
  6–7× — see Finding 5. One middleware line, **after** checking what
  the dev slot's front end already sends
  (`curl -sI -H 'Accept-Encoding: gzip'`), which this container cannot
  see.
- **Precompute the pair sort key.** Sorting the pair list drops from
  0.87 s to 0.31 s at 1,000 × 1,000 when the normalized email is
  computed once per person. Only worth doing inside a wider engine
  change.

---

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

# the two axes in "The two axes that turned out fine"
python3 tools/bench_roster_scale.py seed-lobby --sessions 500
python3 tools/bench_roster_scale.py bench --session 3 --only Lobby
python3 tools/bench_roster_scale.py seed --code BENCH5K \
    --reviewers 5000 --reviewees 5000 --per-reviewer 1
python3 tools/bench_roster_scale.py bench --session N --only "Setup:"
```

The browser-side figures come from driving the same fixture with the
container's Chromium against a local `uvicorn` started with
`ALLOW_FAKE_AUTH=true` and `FAKE_AUTH_EMAIL` set to the bench operator —
ad-hoc, not part of the tool.

**Two states, because the lifecycle state changes the answer.**

- **A — `draft`, never generated.** 1,000 reviewers × 1,000 reviewees, 2
  instruments × 3 response fields, 5 reviewees per reviewer per instrument:
  10,000 assignment rows, 1,000 invitations, 18,000 response rows.
- **B — `validated`, after Prepare.** The same rosters with one
  `MATCH reviewer.tag1 same_as reviewee.tag1` rule pinned on both
  instruments and Prepare run: **200,000** assignment rows.

State B is the realistic **lifecycle state** — an operator who has
clicked Prepare and is deciding whether to Activate sits in it. It is
not a claim that 1,000 × 1,000 is a realistic session *design*; the
bench is 200 × 200 full matrix, set above.

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

The obvious fix is the one this function has already applied twice: pass
the session-wide data in — the assignments are *already loaded* in
`per_reviewer_progress` before the loop starts. **Measuring it says that
is not enough.** Removing the N+1 takes the query count from 2,080 to 78
and leaves the page as slow as it was, because the 400,000 ORM objects
are still built either way. R2 below is the recommendation that follows
from that, and this finding is why it is worth stating separately: a
query count is not a cost.

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

**Re-set 2026-09-21: this stands.** At the bench — 200 × 200 full
matrix, 80,000 rows — Prepare is **20.0 s**, and 5.7 s at half that
roster. A draft of the section above briefly claimed the finding was
overstated; that was measured on a fixture keeping a tenth of the
matrix and is withdrawn.

## Finding 5 — nothing is compressed

`app/main.py` installs no compression middleware, so every response goes
out as plain text however the client asks for it:

```bash
curl -s -D - -o /dev/null -H "Accept-Encoding: gzip, br" \
  http://127.0.0.1:8099/operator/sessions | grep -i content-
# content-length: 1622603      (no content-encoding line at all)
```

What that costs, measured by piping the same responses through `gzip -9`:

| page | as sent | gzipped | ratio |
|---|---|---|---|
| Lobby, 1,003 sessions | 1,584 KB | **95 KB** | 16.5× |
| Setup reviewers, 5,000-row roster | 520 KB | 77 KB | 6.7× |
| Assignments | 562 KB | 74 KB | 7.6× |

This is the one finding in this document that is cheap, global, and
independent of everything else: server-rendered HTML with a 1,000-row
table is the most compressible payload there is, and the lobby's 16.5×
is the whole page weight problem. Whether the deployed front end adds
its own `Content-Encoding` is a dev-slot question this container cannot
answer — one `curl -sI -H 'Accept-Encoding: gzip'` against the dev slot
settles it, and if it does not, the middleware is a one-line change.

## Finding 6 — the readiness report reloaded the session once per check

**Actioned and closed 2026-09-21 by 19R Item 5.** Everything below the
next block is the diagnosis as it stood before the fix; the line
numbers and the `rule.check(db, review_session)` call shape it quotes
are history, not current code.

| page | queries before | after | from the report |
|---|---:|---:|---:|
| Session Home | 79 | **53** | 17 (32%) |
| Assignments | 92 | **66** | 17 (26%) |
| Validate | 112 | **43** | 17 (40%) |

One report run went from **43 queries / 21 distinct** to **17 / 14**,
and the double build on Validate is gone. The three repeats that
remain are `assignments.staleness_by_instrument` re-reading inside its
own engine — deliberately left, with the reasoning in the plan.
Wall-clock on the same fixture, incidentally rather than as the goal:
Session Home 213 ms → **137 ms**, Validate 238 ms → **103 ms**.

Both halves are now enforced rather than merely done:
`tests/integration/test_readiness_report_cost.py` fails if the report
issues one of its own queries twice or builds twice on a page, and
`test_validation_issue_parity.py` pins the issue list rule for rule
against a golden captured from the pre-refactor module. Re-measured on
the same `FM100` fixture; the contract is in `spec/validate_page.md`
§3.1 / §5.1.

---

Added 2026-09-21, answering the open question the bench re-set raised:
*what are the 79–112 queries every session page issues regardless of
roster size?* Measured on `FM100` (`validated`, 20,000 rows) — the
counts are flat in the roster but **not** in the lifecycle state, so
these are the `validated` figures, which is the state an operator sits
in while deciding to Activate.

| page | queries | from `validation.validate_session_setup` |
|---|---:|---:|
| Session Home | 79 | **43 (54%)** |
| Assignments | 92 | **43 (46%)** |
| Validate | 112 | **86 (76%)** |

**Validate's 86 is 43 × 2: it builds the report twice per render.**
`_operations.py:187` runs it for the page body, then
`_operations.py:221` calls `build_workflow_card_context`, which runs it
again at `_workflow_card.py:122`. Nothing passes the first result to
the second.

**Inside one run, 22 of the 43 queries are exact repeats** — identical
SQL *and* identical bound parameters, inside one transaction. On
Validate it is 65 of 86. `validate_session_setup` is a clean
orchestrator over 22 registered rules:

```python
for rule in REGISTERED_RULES:
    for issue in rule.check(db, review_session):   # pre-19R.5 shape
```

…and **each `check` loads for itself whatever it needs.** Eleven
identical `SELECT … FROM instruments WHERE session_id = ?` on Session
Home come from eleven unrelated call sites, eight of them separate
checks in the same report run:

```
build_workflow_card_context > validate_session_setup
  > _check_instruments_no_fields                        <- loads instruments
  > _check_new_model_no_visible_response_fields         <- loads instruments
  > _check_assignments_reviewer_missing                 <- loads instruments
  > _check_assignments_reviewer_missing_for_instrument  <- loads instruments
  > _check_assignments_instrument_empty                 <- loads instruments
  > _check_instruments_no_display_fields                <- loads instruments
  > _check_instruments_stale_generated                  <- loads instruments
  > _check_instruments_zero_included                    <- loads instruments
```

The rosters repeat the same way: `_identity_holders_by_email` pulls the
full reviewer list 5×, reviewees 4×, observers 4× in one report run.

**This is cheap per query and that is why it survived.** 79 queries cost
97 ms of SQL on Session Home — every one is a fast indexed read, so no
profile ever pointed at it and the flat count never grew with the
roster. It shows up now only because 19R removed the costs that were
hiding it.

**The reason to fix it is not primarily speed.** Twenty-two checks each
deciding independently what "the session's instruments" means is how
two of them come to disagree after someone edits one. A single set of
inputs loaded per run buys consistency; the query count is the
symptom that made it visible. Scoped as **19R Item 5**, and shipped —
see the block at the top of this finding.

## The two axes that turned out fine — measured, not assumed

### The lobby scales with sessions, and it scales well

The lobby renders every non-archived session with no pager and no cap —
the property `guide/roster_search_filter.md` turns on. Its axis is session
count, not roster size, so it gets its own fixture
(`bench_roster_scale.py seed-lobby`) of near-empty sessions:

| sessions owned | lobby | queries | HTML |
|---|---|---|---|
| 3 | 11 ms | 4 | 260 KB |
| 13 | 12 ms | 4 | 276 KB |
| 53 | 18 ms | 4 | 331 KB |
| 203 | 24 ms | 4 | 538 KB |
| 503 | 45 ms | 4 | 934 KB |
| 1,003 | 85 ms | 4 | 1,584 KB |

**Four queries at every size**, and server time grows linearly at roughly
70 µs per session. Nothing here needs fixing. What grows is the page.

In real Chromium (`--executable-path /opt/pw-browsers/chromium-1194/…`),
at 1,003 sessions / 805 rendered rows / 18,200 DOM nodes: a cold load is
**811 ms** end to end, `domInteractive` at 398 ms, and **one keystroke in
the Filter box costs 5 ms**. The client-side filter that
`roster_search_filter.md` declined to extend to the rosters is, on its own
page, essentially free — 805 rows filtered to 80 within a frame. The
lobby's only real exposure is the 1.58 MB it sends to get there, which is
finding 5.

### The roster pages hold up, including filtered and deep-paged

All four Setup rosters, `draft`, two roster sizes — 1,000 rows and 5,000,
the latter being `csv_imports.MAX_ROWS`, the import ceiling:

| page | 1,000 rows | 5,000 rows | queries | HTML at 5,000 |
|---|---|---|---|---|
| Setup: reviewers | 195 ms | 341 ms | 28 | 520 KB |
| …page 5 (`?offset=800`) | 184 ms | 327 ms | 28 | 520 KB |
| …`?q=` one match | 181 ms | 350 ms | 28 | 278 KB |
| …`?q=Team 3` (500 matches) | 192 ms | 370 ms | 28 | 864 KB |
| Setup: reviewees | 218 ms | 353 ms | 28 | 508 KB |
| Setup: relationships | 243 ms | 555 ms | 21 | 537 KB |
| Setup: observers | 89 ms | 106 ms | 29 | 488 KB |

Three things worth reading off that table:

- **The query count is flat** — 21–29 whatever the roster size, and paging
  and filtering do not add any. The N+1 of finding 2 is not here.
- **Cost still tracks roster size, not page size.** Every row is loaded,
  sorted and filtered before the 200-row window is cut
  (`app/web/routes_operator/_shared.py` says so in its own docstring), so
  a page showing 200 rows gets ~1.7× slower between a 1,000-row roster and
  a 5,000-row one. At the import ceiling that is still 341 ms, so the
  shape is fine at the sizes the CSV contract allows.
- **A filtered view renders up to 500 rows** (`_SETUP_FILTERED_CAP`), which
  is why `?q=Team 3` is the heaviest cell in the table at 864 KB — 2.5× the
  default page. In Chromium that page is 702 ms end to end versus 268 ms
  for the unfiltered 200 rows.

Where a roster page *did* get slow — 110 ms → 2.0 s between state A and
state B — nothing about the roster changed. That is finding 3's
`_count_assignments` walking 200,000 rows.

**And SQL, everywhere**: 0.5%–9% of page time on every *slow* page in
this document. On the fast ones it is a larger share of a much smaller
number — 44% of the observers page's 106 ms — which is the same point
from the other end. A page is fast here exactly when it is not doing
Python work per row.

## Recommendations

**Three changes take every page in this document under a second.** Each
was measured, not projected: the hot path was stubbed and the same
benchmark re-run on the same fixture — state B, 1,000 × 1,000, 200,000
assignment rows, `validated`.

| page | today | R1 alone | R2 alone | R1 + R2 + R3 |
|---|---|---|---|---|
| Session Home | 14.1 s | 3.7 s | 15.2 s | **0.49 s** |
| Assignments | 23.2 s | 1.7 s | 23.6 s | **0.52 s** |
| Invitations | 20.8 s | 9.0 s | 12.3 s | **0.56 s** |
| Responses | 24.9 s | 13.1 s | 11.4 s | **0.42 s** |
| Validate | 26.5 s | 1.8 s | 23.9 s | **0.71 s** |
| Setup: reviewers | 2.4 s | 2.0 s | 1.9 s | **0.27 s** |

**Read these as ceilings, not promises.** A stub is a cache that always
hits and a rollup that costs nothing after the first call; a real
implementation pays a miss sometimes and pays for its aggregate query.
What the table establishes is that the prize is 30–50×, and that no two
of the three substitute for each other — R1 alone leaves Responses at
13 s, R2 alone leaves Assignments untouched.

### R1 — cache the staleness verdict instead of recomputing it per render

**What.** Persist each instrument's verdict against a content hash of its
inputs — the rosters, the relationships, the pinned rule's definition, the
instrument's pin and the self-review setting — and recompute only on a
mismatch at read.

**Where.** `assignments.staleness_by_instrument`. The shape to copy is
already in the codebase and already solves the part that looks hard:
`instruments.cached_group_pair_count` / `cached_group_pair_stamp` cache a
pair count against exactly such a hash, so nothing has to remember to
invalidate on a roster edit, a rule edit or a re-pin.

One trap for whoever picks this up: *18J Rec C*'s wire-up note in
`guide/deferred_consolidated.md` offers to mirror "the existing
`cached_eligibility_stamp` pattern". Those columns do not exist — Wave 5
PR 5.2 dropped them with the library tier, as
`app/db/models/session_rule_set.py` records. The group-pair cache is the
surviving precedent.

**Worth.** Validate 26.5 s → 1.8 s, Assignments 23.2 s → 1.7 s, Session
Home 14.1 s → 3.7 s. Nothing else in this document comes close.

**Risk — the real one.** The verdict is a *correctness* signal: it tells
an operator their generated rows no longer match their rules. A cache that
wrongly says "fresh" is worse than a page that takes 20 seconds to say
"stale", because the operator reads the silence as an answer — the same
failure `app/services/validation.py` already records this rule having had
once. So the hash has to cover every input the engine reads, and the
safe direction on a hash miss or a hash-shape change is *recompute*.

**Verify.** A test that mutates each input in turn — add a reviewer, edit
a relationship, change the rule, re-pin the instrument, flip self-reviews
— and asserts the verdict changes. That test is the deliverable as much
as the cache is.

### R2 — roll progress up in SQL instead of over every ORM row

**What.** `monitoring.per_reviewer_progress` and `per_reviewee_coverage`
load every `Assignment` and every `Response` in the session as ORM objects
and count them in Python. Replace the row loads with `GROUP BY`
aggregates.

**The measurement that picks this over the obvious alternative.** With R1
and R3 applied, a single Responses render still constructs **408,027** ORM
instances, and the rollup logic itself (`_state_from_assignments`) is only
1.17 s of it. Removing the 2,000-query N+1 of finding 2 — the fix that
looks obvious, and the one this document first proposed — leaves all of
that in place: in the simulation the query count fell to 78 and the page
did not get faster. The queries were never where the time was.

**Worth.** Responses 24.9 s → 11.4 s on its own; with R1 and R3, 0.42 s.

**Risk.** The group-scoped contract (Segment 13C): a group-scoped
instrument counts **once per group**, not once per member. That is what
resists a plain `GROUP BY`, and it is where a rewrite will get it wrong.
Land `per_reviewee_coverage` first — it is the simpler of the two — and
keep the Python implementation next to the SQL one until a parity test
over a fixture that includes group-scoped instruments passes on both.

### R3 — count with `count()`

**What.** The five `len(db.execute(...).all())` sites, plus
`responses.session_response_count`, whose caller in
`app/web/views/_quick_setup.py` only needs `> 0` and can take an `EXISTS`.

**Worth.** Setup reviewers 2.4 s → 0.27 s. That page runs no engine and no
rollup, so this is R3 measured on its own.

**Risk.** Almost none — these are one-line changes with the same
semantics. `session_response_count` is the one that needs care, because
its full form deduplicates group fan-out; the `> 0` caller does not.

**Do this one first.** It is hours, not days, and it is the only one of
the three that needs no design.

### Secondary, in descending order

4. **Bulk-insert the generated pairs.** `app/services/assignments/_generate.py`
   adds one `Assignment()` per pair. Prepare measured 74.8 s for 200,000
   rows, 17.4 s of it SQL — so most of the minute is ORM object churn a
   Core `insert()` with a list of dicts would not do. Unlike R1–R3 this
   one is a click, not a page, so the bar is different: it needs progress
   feedback or a background job as much as it needs speed.
5. **Turn on compression.** One middleware line, worth 1.49 MB on the
   lobby alone and 6–16× on every page here. Confirm first what the dev
   slot's front end already sends (`curl -sI -H 'Accept-Encoding: gzip'`),
   since this container cannot see it. It is the only item that helps
   every page and every roster size at once.
6. **Precompute the pair sort key.** Sorting the 1M-pair list drops from
   0.87 s to 0.31 s when the normalized email is computed once per person
   rather than once per pair. Only worth doing inside a wider engine
   change: on its own it removes a twelfth of what R1 removes entirely.

### Sequencing, if any of this is adopted

R3, then R1, then R2 — cheapest first, and each is independently
shippable. R5 rides alongside whenever the dev-slot check comes back. R4
is its own question because it is a workflow action rather than a page.
This document remains an investigation: adopting any of it means a
segment plan, where the ladder and the doc impact get written properly.

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

1. ~~**Is a 1,000-person session real?**~~ *Answered by the author
   2026-09-21: **100 × 100 is the likely upper limit**. A hundred people
   to review is not crazy; the conditions under which a thousand are
   each asked to do it are rare. The pilot's own sessions are 154. The
   bench above is set at 200 × 200 full matrix on that basis, and
   `guide/roster_search_filter.md` — which left the same question open —
   can take the same answer.*
2. **Is the staleness verdict worth its price on every page?** It is
   displayed on Assignments and Validate. The other four pages build the
   card, and pay the engine walk, to render a summary count.
3. **Should the `validated` state cost less than the others?** It is the
   state an operator sits in while deciding to Activate, and it is the only
   state that runs validation inline on six pages.
4. **What does the deployed front end do with a long Prepare POST?** A
   dev-slot question; this container cannot answer it. Still open at the
   re-set: Prepare is **20 s at the bench**, not the 3.1 s an earlier
   draft claimed from the wrong fixture.
5. ~~**What are the 79–112 queries that every session page issues
   regardless of size?**~~ *Answered 2026-09-21: `validate_session_setup`
   is 54% of Session Home, 46% of Assignments and 76% of Validate,
   because each of its 22 checks loads the rosters and instruments it
   needs for itself, and Validate runs the whole report twice. Finding 6;
   scoped as 19R Item 5.*

## Out of scope

- Any fix. This is an investigation; nothing here is scheduled.
- The reviewer-facing surfaces and the participant pages — the report was
  about the operator surfaces, and only those were measured.
- Browser-side cost beyond the two spot checks above; no profiling of
  layout, paint or the sort / column-chip handlers.
