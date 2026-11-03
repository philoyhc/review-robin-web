# Segment 20F — Symmetric review, held by more than convention

**Opened:** 2026-11-03, at the author's request (the larger follow-ups of
the 2026-11-02 assessment) · **Theme:** the Reviewees mirror can't drift
from the Reviewers roster unnoticed · **Related:**
`guide/archive/segment_20B_symmetric_review.md`,
`guide/archive/codebase_assessment_02nov.md` §5,
`guide/archive/findings_2026-11-02_assessment.md` (L2, L3),
`spec/architecture.md` "Symmetric review"

## Opportunity

Under `sessions.symmetric_review` the Reviewees roster mirrors the
Reviewers roster only because every reviewer-writing service calls
`symmetric_review.sync_reviewees_from_reviewers` before it commits: 10
call sites in 7 modules, by convention. Nothing fails if a new writer
forgets, and no check notices a reviewee that has drifted from its
reviewer (`guide/archive/codebase_assessment_02nov.md` §5). The defect read found
two edge cases on the same seam:

- **L2.** On SQLite, a Replace can hand a removed person's reviewee row,
  their results acknowledgement included, to a new reviewer: rows in
  memory miss `ON DELETE SET NULL`, and SQLite reuses ids. Postgres is
  unaffected, but the suite and local runs are not.
- **L3.** A symmetric session's setup bundle carries no `reviewees.csv`
  (by design), and imported into a non-empty session leaves its reviewees
  alone with no notice.

## Decision

**A check that catches drift, and a guard that catches a forgotten
writer, rather than a restructure.**

1. **A Validate rule, `reviewees.mirror_drift`** (error): under symmetric
   review, any reviewer without exactly one linked reviewee, any reviewee
   unlinked or linked to a missing reviewer, and any mirrored field
   (`symmetric_review.MIRRORED_FIELDS`) that differs. Validate already
   blocks Prepare on errors, so drift cannot reach a live session.
2. ~~**A test guard**: an integration test that walks every service
   function writing `Reviewer` rows (found by a source scan for
   `Reviewer(` construction, `.delete(` on reviewers and the bulk
   updates, against an allowlist) and fails on one that does not call the
   sync. The allowlist names each writer and why.~~ *At build (rung 3): a
   commit-time check of every symmetric mirror in the integration suite,
   since a source scan found 3 of the 10 writers (`## Status`).*
3. **L2:** `sync_reviewees_from_reviewers` ~~expires the session's reviewee
   rows~~ reads the reviewee rows with `populate_existing` (at build) before
   building `by_link`, so it reads the database's links.
4. **L3:** the setup-bundle import says, on its result page, that a
   symmetric bundle carries no reviewees and the session's are left as
   they are; `spec/csv_contracts.md` says so too.

Rejected: *one write path for reviewers* (route every reviewer write
through a single service entry). It is the structural fix, but it
reshapes eight writers and their tests for a mode one session in many
uses; the rule and the guard catch the same failure at a fraction of the
cost. Revisit if a third drift is found.

## Semantics

- The rule runs only while the mode is on; off, it reports nothing.
- Mirrored-field comparison is against what the sync would write for
  that reviewer, so the rule and the sync cannot disagree on a match.
- The rule's message names the reviewer and the field; its fix line
  points at a save on Reviewers, which re-runs the sync.
- ~~The test guard reads source, not behavior: it fails on a new writer
  until the writer calls the sync or joins the allowlist with a reason.~~
  *At build: it checks behavior, at each commit the integration suite makes,
  and a test that breaks a mirror on purpose marks itself
  `mirror_drift_expected`.*

## Judgment calls — decided

- An error, not a warning: a drifted mirror is a wrong roster (2026-11-03).

## Blast radius (measured)

Taken 2026-11-03 at `a2d95aff`.

| What | Count | Command |
|---|---|---|
| Sync call sites | 10 in 7 modules | `grep -rn "sync_reviewees_from_reviewers(" app --include=*.py \| grep -v "def " \| wc -l` |
| Validate rules today | 26 | `python -c "from app.services.validation import REGISTERED_RULES as R; print(len(R))"` |
| Symmetric-review test files | 3 | `ls tests/integration/test_symmetric_review_*.py \| wc -l` |

## Status

**Closed 2026-11-03.** PRs #3534 → #3537, then the close. Base for the
item's read: `803ff768`.

**Intended vs done.** All four decisions shipped; two changed form at
build:

- **L2** (#3534): the sync reads the reviewee rows with
  `populate_existing` rather than expiring them, so it reloads the
  links of exactly the rows it reads.
- **The rule** (#3535): `reviewees.mirror_drift`, registered after
  `reviewees.duplicate_account` (27 rules), its fix link Reviewers Setup.
  Codex found three gaps in that fix line, all fixed in the PR: an
  unchanged reviewer save skipped the sync; the repair then made wrote
  no audit row (now `reviewees.mirror_repaired`, from the counts the
  sync returns); and the sync never removed a second reviewee linked to
  one reviewer.
- **The guard** (#3536) checks behavior, not source. A scan for writers
  of `Reviewer` rows found 3 of the 10 sync callers, so the integration
  `db` fixture instead runs `tests/_mirror_guard.py` at every root
  commit and fails the test at teardown on a mirror out of step. Six
  tests break a mirror on purpose and are marked
  `mirror_drift_expected`. Removing each sync call in turn, the guard
  catches 8 of 10: `session_clone` is in step by construction, and the
  Settings apply's sync (self-fields and labels, which the guard does
  not compare) gained its own test. On Postgres the guard first fired on
  the savepoint the session lock releases mid-unit; it now checks only
  at the end of a committed root transaction.
- **L3** (#3537): the notice is on Quick Setup's submit-all, the one path
  that takes a bundle into an existing session:
  `?quick_setup_notice=kept_reviewees` and a dismissible `banner-info`.

**Reads.** Two `diff-reviewer` reads. Rungs 1–3 (cumulative): no code
defect; prose findings fixed (the guard's claim narrowed, the plan
annotated, the drift message names the reviewer). Rung 4: the condition
and copy right; four gaps fixed (scroll target, Dismiss, the URL-state
row, three no-notice tests). The build named two specs the plan had not,
now in `## Doc impact`. The close's `spec-writer` pass added two lines to
`spec/architecture.md` (the duplicate drop and `MirrorChanges`; the
unchanged-save repair and its audit event) and found the other four specs
current; its two flags (test machinery unspecified; the notice specified in
the card spec rather than the CSV contract) need no change. `close_check 20F` passed; its notes (Setup routes and
`_session_home` touched) are 20E's same-day splits and rung 4's query
param, documented in `spec/settings_inventory.md`.

## PR ladder

1. **L2.** The ~~expire~~ `populate_existing` read in `sync_reviewees_from_reviewers`, with the SQLite
   reproduction as its test. Must not touch Validate.
2. **The rule.** `reviewees.mirror_drift` registered and tested (drifted
   name, missing mirror, orphan reviewee, mode off).
3. **The guard.** ~~The source-scan test and its allowlist.~~ The commit-time mirror check. Last build rung
   for code: `diff-reviewer` on the cumulative diff since rung 1's base.
4. **L3.** The notice on the bundle import's result and its line in
   `spec/csv_contracts.md`. Its own read (template and route).
5. **Close.** Specs; the register's L2 and L3 struck.

## Definition of done

- A test drifts a mirrored field directly in the database and Validate
  reports `reviewees.mirror_drift`.
- ~~Removing a sync call from any listed writer fails the guard test.~~
  Removing any of the 10 sync calls fails a test, the guard's for 8 of them
  (rung 3, `## Status`); `session_clone`'s mirror is in step by
  construction.
- The L2 reproduction passes on SQLite.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20F` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~**L3's form.**~~ The notice (author, 2026-11-03: "L3 gets the
  notice").

## Out of scope

- One write path for reviewers (rejected above).
- Symmetric review's behavior otherwise (20B's contract stands).

## Doc impact

- `spec/validate_page.md` — the `reviewees.mirror_drift` rule (rung 2).
- `spec/architecture.md` — "Symmetric review": the rule and the guard beside the sync (rungs 2, 3).
- `spec/csv_contracts.md` — a symmetric bundle carries no reviewees, and the import says so (rung 4).
- `spec/quick_setup_card_spec.md` — the kept-reviewees notice on the card (rung 4).
- `spec/settings_inventory.md` — the `?quick_setup_notice=kept_reviewees` URL param (rung 4).
- `guide/archive/findings_2026-11-02_assessment.md` — L2 and L3 struck (at close).
- `guide/todo_master.md` — delete the segment's entry at close.
