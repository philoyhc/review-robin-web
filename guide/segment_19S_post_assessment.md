# Segment 19S — Post-assessment follow-ups

**Opened:** 2026-09-22 · **Theme:** the items surfaced by
`guide/codebase_assessment_22sep.md` · **Related:**
`guide/codebase_assessment_22sep.md`, `guide/codex_assessment_21sep.md`,
`guide/app_responsiveness.md`

**Bounded, not a standing home.** Scope is the finite list below, drawn
from one dated assessment and written before the segment opened. Work
that is not one of these entries, or a patch arising from one, gets its
own segment. That guard is why this file is allowed more than one item:
19C died of being a home for whatever came next, and 19G survived by
naming its list first.

**Close it when the list is empty, or at the next assessment snapshot,
whichever comes first.** If this segment admits anything that did not
come out of the 22 September assessment or its own work, the shape has
outlived its use and the rest gets its own segment.

**This is an opening register, not a plan.** Every entry below is one
or two lines and a pointer. Nothing here is scheduled, sized or
designed. An entry becomes `## Item <n>` with the full shape —
`Opportunity`, `Decision`, `Semantics`, a measured `Blast radius`, a
ladder — **when the author picks it up**, and not before; writing eight
plans for work that may never be chosen is the cost this shape exists
to avoid. Items will close independently, so each will carry its own
`### Doc impact` and `### Status` and there is no segment-level
`## Doc impact`.

**The first recommended move is already done.** §8's move 1 was "close
Segment 19R and deploy". 19R closed 2026-09-22; deployment is the
author's, not a code item, and has no entry here.

## Candidate entries

Ordered as the assessment ranks them, not by size.

1. **Prepare takes 20 seconds at the bench.** `guide/app_responsiveness.md`
   Finding 4, measured at 200 × 200 / 80,000 rows, 5.7 s at half the
   roster — climbing steeply because Prepare inserts one ORM object per
   pair. A click with no feedback, on every session's critical path.
   §8 move 2. The assessment's one unambiguous "fix before the pilot".

2. **Re-take the bench against real data, not the code.**
   `guide/app_responsiveness.md`'s headline inverted once already this
   month — "not a database problem" became 84% SQL on Invitations,
   because 19R moved the counting into SQL. That sentence is a
   2026-09-20 fact, not a standing one. §8 move 3, and it is explicitly
   *after* deployment.

3. **`app/services/validation.py` at 1,300 LOC has no queued split.**
   New largest production module, +346 in one window. The seam is
   already there: the 22 `_check_*` functions are a registry, so they
   carve into a `_rules/` sub-package leaving the orchestrator and
   `REGISTERED_RULES` in place. §9 says revisit past ~1,450.

4. **`app/services/session_lifecycle.py` is 93 LOC from its tripwire**
   (1,107 against ~1,200), a third consecutive window inside 100, and
   still has no natural seam — the state machine is cohesive and
   splitting it would scatter the transition table. §9: watch actively,
   do not plan. An entry so the next reader knows it was looked at.

5. **Nothing gates `docs/status.md`'s summary counter.** It drifted two
   items behind before a cold read caught it — a line each closing slice
   is supposed to maintain, missed by two consecutive closes. §5. A
   `tests/unit/test_doc_conventions.py` check derived from the 19-row
   count would close it; whether that is worth mechanising is the
   question, given `constitution.md` VI.

6. **The prose about the work has been wrong more often than the work.**
   §5, and the assessment records no plan for it: nine wrong
   descriptions of one rule in six files, a blast-radius grep scoped
   wrong twice, a denominator taken with `--since=<bare date>`, and a
   close claiming a review had happened before it had. Every one caught
   by a reader or a gate, none by the author. This entry exists to be
   argued with — it may be that the readers *are* the answer and there
   is nothing to build.

7. **The roster route modules duplicate at 47 / 42 / 35 / 34 / 28%.**
   `_setup_reviewers.py`, `_setup_reviewees.py`, `_setup_observers.py`,
   `_setup_relationships.py`, `_quick_setup.py` — five near-identical
   CRUD surfaces differing only in their entity, and 19P gave them one
   UI idiom without consolidating the route modules. §2 calls it
   deliberate and below the threshold for acting. The obvious extraction
   if anyone ever wants one.

8. **`app/services/csv_imports.py` (1,246, +246) and
   `app/services/instruments/_band1.py` (1,066, +363).** §9 watchlist,
   neither at a tripwire. `csv_imports` carves per entity but would need
   a `_headers.py` first; `_band1`'s +363 in one window is the rate to
   watch rather than the level.

## Out of scope

- **Email dispatch (Segment 14B).** The gap between "ready" and
  "shippable", and blocked on institutional Azure provisioning — not a
  code item and not this segment's.
- **Rehydrate, blob storage, operator theming.** Deferred with their own
  homes: `spec/rehydrate.md` gated off, `guide/segment_18Q_blob.md`,
  `guide/deferred_consolidated.md` Part A.
- **Anything in `guide/app_responsiveness.md`'s "Later candidates".**
  Measured, deliberately not a queue — entry 2 above is the trigger that
  decides which of them, if any, ever become entries here.
