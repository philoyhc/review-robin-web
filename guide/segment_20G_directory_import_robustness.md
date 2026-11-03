# Segment 20G — The import's directory check, sturdier

**Opened:** 2026-11-03, at the author's request (the larger follow-ups of
the 2026-11-02 assessment) · **Theme:** a roster upload whose directory
check fails says why and can try again, and matching uses its indexes ·
**Related:** `guide/codebase_assessment_02nov.md` §5,
`guide/archive/findings_2026-11-02_assessment.md` (M1, done in #3525),
`cordware/spec/identity.md` "Graph", `spec/csv_contracts.md` §3.1

## Opportunity

M1's fix (#3525) stopped a failed check from unbinding rows a replace
re-adds. Three weaknesses at the same seam remain
(`guide/codebase_assessment_02nov.md` §5):

- **A sign-in failure is final for that upload.** The browser renews the
  delegated Graph token on page load, once 45 minutes have passed, and
  the directory pickers renew and retry on "unauthorized"
  (`cordwareRenewGraph`, `app/web/templates/base.html`). The roster
  upload does neither: an expired token checks nothing, new rows save
  unbound, and the card only counts "not checked". `look_up_all` already
  knows why (`Outcome.error_kind`, and it stops the run on a sign-in
  kind), but the import keeps counts only.
- **The lookup runs on the request path,** under a 120 s budget
  (`directory_accounts.BUDGET`) after the session lock's 5 s wait. Its
  cost at a real roster's size against real Graph is unmeasured.
- **Matching bypasses the indexes.** `participants.py` compares
  `func.lower(directory_object_id)` and `users.py`
  `func.lower(func.trim(external_principal_id))`, so the indexes on those
  columns (`app/db/models/reviewer.py` and its siblings, `user.py`) are
  not used. Object ids are stored as Graph returns them, not normalized.

## Decision

1. **A sign-in failure holds the file and asks to renew.** When the
   check stops on a sign-in kind (`cordware.graph.SIGN_IN_KINDS`), the
   upload saves nothing. It holds the file (19W's hold) and re-renders
   the card: "Your sign-in to the directory had expired. Renew and
   upload again", with a button that calls `cordwareRenewGraph()` and
   resubmits the held file. Any other failure (throttling, outage,
   budget) saves as today, M1 keeping earlier accounts, and the card
   names the kind.
2. **Measure before moving the lookup off the request.** A bench in
   `tools/bench_roster_scale.py` times `directory_check` for 200, 1,000
   and 2,000 addresses against a fake directory with Graph's measured
   latency, and the author takes one real timing on the deployment. A
   background check is planned only if the real timing threatens the
   front end's limit.
3. **Normalize at write, compare plainly.** Every write of
   `directory_object_id` and `external_principal_id` stores
   `normalize_object_id(value)`. A migration lower-cases and trims the
   stored values. The queries drop `func.lower` / `func.trim`, so the
   indexes are used.

Rejected: *retry the lookup server-side after renewing.* The server
cannot renew a delegated token; only the browser's `/.auth/refresh` can.
Rejected: *a background job for every import now.* There is no clock yet
(14E), and no measurement says the request path is too slow.

## Semantics

- **What counts as sign-in:** ~~`SIGN_IN_KINDS` as `look_up_all` uses it
  (`unauthorized`, `forbidden`), plus no token at all, which renewing can
  also cure. With fake auth nothing is looked up, so nothing asks to
  renew.~~ *At rung 3's read (author, 2026-11-03): `unauthorized` only.
  Renewing cures neither no token (the token store off, or a sign-in
  without Graph) nor `forbidden` (consent or scope), so those save as
  any other failure does and the card names why. The local fake
  directory looks addresses up; its `denied@` answers `forbidden`.*
- **Append and merge** hold and ask the same way; nothing is written.
- **Quick Setup** refuses the whole submit with the same ask (it is
  all-or-nothing already); **rehydrate**, which saves into a new session,
  does the same.
- **Migration:** values that differ only by case or whitespace collapse
  to one. A unique constraint on these columns does not exist, so nothing
  collides. Downgrade is a no-op (the original case is not kept).

## Judgment calls — decided

- Hold and ask, rather than save unbound and warn: a sign-in failure is
  the one failure the operator can fix in a click (2026-11-03).

## Blast radius (measured)

Taken 2026-11-03 at `a2d95aff`.

| What | Count | Command |
|---|---|---|
| Upload routes running a directory check | 3 | `grep -rln "csv_imports.directory_check" app/web --include=*.py \| wc -l` (`_shared.py`, `_setup_observers.py`, `_quick_setup.py`) |
| Multi-roster checks outside `csv_imports` (rehydrate) | 1 | `grep -rn "directory_checks(" app --include=*.py \| grep -v "def \|csv_imports.py" \| wc -l` |
| Case-folded matching on object ids | 3 | `grep -rnE "func.lower\((model\.)?directory_object_id\|func.trim\(User.external_principal_id" app --include=*.py \| wc -l` |
| Indexed columns concerned | 4 | `grep -rn "directory_object_id\|external_principal_id" app/db/models/*.py \| grep -c index=True` |

## Status

**2026-11-03, rung 1.** Started at the author's word ("complete the
remaining items on the register first, then 20G"). Main before rung 1:
`1f2dba51`, the base for the read at rung 3. `DirectoryCheck.stopped`
carries `directory_accounts.sign_in_stop`: `no_token` when there was an
address but no token, else the first `SIGN_IN_KINDS` kind among the
roster's own outcomes; any other failure is not a sign-in stop. The local
fake directory's `denied@example.edu` answers `forbidden`, so a local run
can show the renew state.

**Rung 2, the scaffold.** `operator/partials/_directory_renew.html`: a
`banner-warning` on the Reviewers, Reviewees and Observers upload cards
(inside the form then, in the banner stack since #3546), and above the slots on Quick Setup's card
(`QuickSetupContext.directory_renew`), with "Nothing was saved", an inert
*Renew sign-in and upload* (Primary) and a Dismiss that ends the hold.
Relationships has no directory check. Nothing sets the flag yet.

**Between rungs 2 and 3, the banner audit** (author, 2026-11-03: "make an
audit of all the banners that appear in these upload cards"): every
upload-card banner now stacks under the card's intro, problems, renew,
group clear (#3546); the group-clear ask had touched the tick fieldset.

**Rung 3, wired.** The roster routes, Observers, Quick Setup's submit-all
(reason `views.DIRECTORY_SIGN_IN`, one of `_ASKS`) and rehydrate
(`RehydrateSignInStopped`, the stash kept) refuse on a sign-in stop and
hold; the button renews through `cordwareRenewGraph()` and submits the
named form again, a failed renewal saying to sign out and in. M1's
keep-the-account path is now reached by an outage or throttling only.
The integration suite's default directory is `FakeDirectory`
(`conftest.py`), so "no token" is something a test asks for; two tests'
counts changed with it.

**Rung 3's read** (rungs 1–3, cumulative since `1f2dba51`): no blocking
defect. Its design finding went to the author, who ruled that only an
expired token (`unauthorized`) holds; no token and `forbidden` save. The
plan's "the card names the kind" had no rung: the import now records
`directory_unchecked` and the directory-check line names it. Also fixed:
Quick Setup's per-slot routes (which hold nothing) show a slot banner to
reload rather than a renew button with nothing behind it; stale comments,
the fixture's advice, and the specs (`csv_contracts.md` §3.1,
`setup_pages.md`, `quick_setup_card_spec.md`, `rehydrate.md`, and
`cordware/spec/identity.md`'s "What it does not cover").

## PR ladder

1. **The check records why.** `DirectoryCheck` gains the stop kind from
   `look_up_all`. No behavior change. Must not touch a template.
2. **Hold and ask, scaffold.** The card's renew-and-upload state, its
   copy, and an inert button (scaffold first, `CLAUDE.md`).
3. **Hold and ask, wired.** The routes refuse on a sign-in stop, hold the
   file, and the button renews and resubmits; Quick Setup likewise. Last
   build rung of items 1–3: `diff-reviewer` on the cumulative diff.
4. **Normalized ids.** The write paths, the migration and the plain
   queries, with a Postgres check that the index is used. Its own read.
5. **The bench.** `tools/bench_roster_scale.py` gains the directory case,
   and the plan records its figures and the author's real timing.
6. **Close.**

## Definition of done

- An upload with an expired token saves nothing, holds the file and
  offers renew-and-upload. One click re-imports with a fresh token (a
  test with a refusing fake; the browser check is the author's).
- `grep -rn "func.lower(.*directory_object_id" app` finds nothing, and
  the migration round-trips on Postgres (`ci-postgres`).
- The bench's figures and one real timing are in `## Status`.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20G` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~**Renew automatically?**~~ A button (author, 2026-11-03, at the
  scaffold).
- **The budget:** keep 120 s, or lower it once the bench reports? After
  rung 5. Author.
- **The real timing — taken** (author, 2026-11-03, 19Z walkthrough
  B4): 1,500 addresses replaced on production in about 56 s, every
  lookup done (23 by mail, 12 by sign-in name, 1,465 not found), about
  37 ms a lookup. Decision 2's one real timing; well inside 120 s.
- **A progress count?** (author, 2026-11-03) Planned as 20H Item 6
  (`guide/segment_20H_walkthrough_19Z_followups.md`), after this plan's
  rung 1, with which it shares a seam.

## Out of scope

- A background directory check (only if rung 5's timing calls for it).
- Re-resolving existing rosters in bulk (`spec/csv_contracts.md` §3.1
  says there is none).

## Doc impact

- `spec/setup_pages.md` — the Upload card's renew-and-upload state (rungs 2–3).
- `spec/csv_contracts.md` — §3.1: a sign-in stop saves nothing and holds the file (rung 3).
- `spec/quick_setup_card_spec.md` — the sign-in stop holds the submit and shows the renew banner (rung 3).
- `spec/rehydrate.md` — a sign-in stop keeps the stash and asks to renew (rung 3).
- `cordware/spec/identity.md` — an upload's `unauthorized` is now asked to renew (rung 3).
- `cordware/spec/identity.md` — object ids stored normalized; matching without case folding (rung 4).
- `docs/performance.md` — the directory check's bench figures (rung 5).
- `guide/todo_master.md` — delete the segment's entry at close.
