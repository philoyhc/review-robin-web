# Findings — codebase assessment (2026-11-02)

**Found by:** the three reads run beside
`guide/codebase_assessment_02nov.md`: a spec-vs-code audit, a defect read
of the window's RRW changes, and a read of `residentialapps/`,
`utilityapps/` and `cordware/` · **Read at:** `2ffb0f42` (#3521) ·
**Open:** none. Every row was done in #3524 → {PR} by 2026-11-03, N2
struck as not reproduced; archived the same day.

The checklist the fixes work through (author, 2026-11-02: "there should
be a findings list that can serve as the checklist for fixes; this
should be SOP"). **Nothing in `app/` was edited by the reads**, and their
scratch tests were not kept: a fix PR writes its own test. Strike a row
when it is done, with the PR that did it, or mark it declined with the
reason. Retire the file to `guide/archive/` when no row is open.

**Ids:** **M** and **L** are defects, medium and low, as the assessment's
§6 numbers them · **D** is spec drift, as its §3 does · **N** is a gap
noted, not a defect. Ids restart per assessment. **Decides:** *code*
means the code is wrong against a spec that is right; *author* means a
choice between fixing the code and changing the contract; *spec* means
the spec is wrong. Line numbers are at `2ffb0f42`.

## 1. High

None.

## 2. Medium

- ~~**M1**~~ — **Done in #3525**: a row the directory gave no answer for keeps its earlier account unless the file binds that account elsewhere, counted as `directory_kept` (`spec/csv_contracts.md` §3.1; `tests/integration/test_directory_rosters.py`). **A Replace with an expired Graph token unbinds every row it
  re-adds.** `app/services/csv_imports.py` `_save`, with <!-- path-ref-ok -->
  `cordware/graph.py` `look_up_all`. Token renewal runs on page load, so
  a Replace submitted after the token lapses resolves nothing, and every
  row is saved without its directory account. A row given by sign-in
  name stops admitting a person whose mail differs; the only signal is
  the card's "not checked" count. *By reading; reproduced by the fix's
  test.* Code: a row the directory gave no answer for keeps its earlier
  binding.
- ~~**M2**~~ — **Done in #3524**: merge refuses it in its planning pass, as append does (`tests/integration/test_roster_merge.py`). **Merge binds an unbound row to an account another row holds.**
  `_merge_rows`, the branch binding a held row with no account. Append
  refuses this case and merge refuses it within one file, but not
  against the saved roster; the gates pick the lowest id, so the other
  row's assignments and answers drop out of the person's view.
  *Reproduced.* Code: refuse it as append does.

## 3. Low

- ~~**L1**~~ — **Done in #3542**: the count is compared by length,
  leading zeros stripped, before `int()`; a longer one reads as no tick,
  so the change asks again (`tests/unit/test_acknowledged_loss.py`).
- ~~**L2**~~ — **Done in #3534** (segment 20F): the sync reads the
  reviewee rows with `populate_existing`, so a Replace on SQLite never
  hands a removed person's reviewee to a new reviewer
  (`tests/integration/test_symmetric_review_mirror.py`).
- ~~**L3**~~ — **Done in #3537** (segment 20F): a Quick Setup submit-all
  that brings a symmetric Settings file and no Reviewees file into a
  session with roster rows says the reviewees were left as they were
  (`spec/quick_setup_card_spec.md`; `spec/csv_contracts.md`, the Zip all
  row).

## 4. Spec drift

All three were taken by 19Z's close (`guide/archive/segment_19Z_roster_append.md`), 2026-11-03.

- ~~**D-a. The CSV contract says rosters never merge.**~~ **Done at 19Z's close.**
  `spec/csv_contracts.md` ("Wipe-and-replace, never merge"; "A roster
  import is wipe-and-replace") against `save_reviewers`, `save_reviewees`,
  `save_observers` and `save_relationships`, which take `append` and
  `merge`. `spec/setup_pages.md` names neither tick. Spec.
- ~~**D-b. Three routes outside the permissions matrix.**~~ **Done at 19Z's close.** The two
  directory-search GETs in `app/web/routes_operator/_directory.py` and
  the sys-admin one in `_sys_admin.py` appear in no spec, including
  `spec/permissions.md`. Their gates are right. Spec.
- ~~**D-c. Graph search undocumented.**~~ **Done at 19Z's close.** `cordware/spec/identity.md`
  documents `find_users` but not `search_users` (`cordware/graph.py`,
  `SEARCH_TOP = 10`). Spec.

## 5. Noted

- ~~**N1**~~ — **Done in {PR}**: a test walks every route both
  applications build, through the included routers, and fails on any but
  `/health` without the gate (`residentialapps/tests/test_preview_gate.py`).
- ~~**N2**~~ — **Not reproduced**: `_cell` in
  `residentialapps/supportlogs/routes_records.py` has guarded the writer
  since 2026-10-30 (6fe14dd4), tested by
  `test_a_cell_that_opens_like_a_formula_stays_text`. The assessment
  read a stale line.
- ~~**N3**~~ — **Done in {PR}**: the README says what is built,
  placeholder screens on sample data behind the preview gate.
