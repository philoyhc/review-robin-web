# Quick Setup update

**Opened:** 2026-10-12 · **Theme:** how Quick Setup checks and applies
several files at once · **Related:** `spec/quick_setup_card_spec.md`,
`spec/csv_contracts.md` §3

A standalone plan at the author's naming, not a `segment_*.md`, in the
shape of `guide/participant_info.md`: items close independently, each
with its own `### Doc impact` and `### Status`, checked by hand at close
(`tools/close_check.py` reads only `segment_*` files).

---

## Item 1 — Files uploaded together are checked together, and land together

### Opportunity

Submit-all and Create run the slots one at a time (Reviewers,
Reviewees, Relationships, Observers, Settings). Each slot commits
before the next slot's file is read. Two problems follow (author,
2026-10-12):

- **A rename across rosters can't be uploaded.** Take `bob@x`, who is
  "Bob Smith" on both rosters, with both new files saying "Robert
  Smith". The Reviewers file is refused against the current Reviewees,
  and the Reviewees file that agrees with it is never read.
- **A failure partway through leaves a half-applied setup.** New
  reviewers end up committed beside old reviewees.

### Decision

The author's rule, 2026-10-12:

- **One file** is checked against every existing roster except the one
  it replaces. This is what happens now, and it stays.
- **Several files** are checked against **each other**, and against the
  existing rosters they **don't** replace.
- **All or nothing.** Every attached file is checked before any is
  saved, and the saves share one commit.

**Rejected:** keeping the slot-by-slot dispatch and changing only the
identity rule. A later slot would then check against an earlier file
that is either unsaved or committed and still undoable.

### Semantics

- **Holders.** For each uploaded roster kind, the holders of an email
  are the incoming rows of the *other* uploaded kinds, plus the existing
  rows of every kind *not* uploaded. A single file reduces to today's
  rule exactly. As today, rows are skipped only if their identifier is
  not an email or their name is empty (`is_comparable_identity`). Status
  doesn't matter: an inactive row is compared like any other. Names
  compare exactly.
- **A clash between two incoming files** is reported on the earlier
  slot in dispatch order, with a new `problem`: "ReviewerEmail is used
  under a different name in the uploaded Reviewees file". A clash with
  an existing roster keeps "…in another roster".
- **Relationships.** Each email must be on the incoming roster when that
  roster's file is attached, and on the current roster otherwise. After
  the rosters are flushed inside the unit, the file is parsed again to
  pick up real ids. If that parse disagrees with the first, it raises
  and rolls everything back.
- **Gates.** Each slot in dispatch order goes through lifecycle, then
  parse, identity and relationships, then the tick and the
  response-loss acknowledgement. The first failure stops the submit
  with nothing written.
- **Settings** has its file-level and row-level errors checked up front
  (`_read_settings_csv`). It applies last, inside the unit, so an error
  `apply_session_config` finds only while applying rolls the rosters
  back too.
- **A lifecycle race** (`SessionStateConflict`) rolls back the whole
  unit, with the `lifecycle` reason shown on the slot that hit it.
- **Create** keeps its session row, as now. Its tags and owners are
  still written on the error path, outside the unit.
- **Audit:** each roster still writes its own `*.imported` event, and a
  rollback writes none.

### Judgment calls — decided

- **The banner still reports one slot**, the first that fails. Listing
  every slot is the deferred report page (`guide/import_error_reporting.md`).
- **The unit is the existing `unit_of_work.atomic`**, which already
  nests. The one raw `db.commit()` on the path, in
  `_apply_settings_upload`, moves to `unit_of_work.commit`.
- **The per-slot routes run the same pipeline with one file.**
- **A Relationships email missing from an uploaded roster file says so**
  ("…is not in the uploaded Reviewers file"), rather than "import
  reviewers first", which would be wrong with that file attached
  (rung 2, 2026-10-12).

### Status

Open, 2026-10-12. Rung 2 is #2999; rung 3 is built and read
(cumulative `diff-reviewer` from `19a4e26d`, plus a `spec-writer`
verify). Both reads found one defect, the same one: a blocked roster
file left out of the identity check let its old roster refuse an
earlier slot. It was fixed by passing the file in empty, with a test.
Decisions confirmed at build:

- A Relationships file refused at its save-time parse (a roster edited
  between the check and the lock) is reported as its `parse` problem,
  not raised as a 500. The plan said "raises".
- One correlation id per submit, rather than one per slot.
- **Deferred:** moving the pipeline from `_quick_setup.py` into a
  service. It continues the retired helpers' placement, and the move is
  a refactor of its own (cold read, rung 3).

### Blast radius (measured)

Taken 2026-10-12 at `1c08ae3a` (#2997).

- Slot-helper calls in `app/web/routes_operator/_quick_setup.py`
  (`grep -c 'await <helper>('`): import 5, relationships 3, observers 3,
  settings 3. Raw `db.commit()` there: 1.
- `check_cross_table_identity(` call sites: 4
  (`grep -rn 'check_cross_table_identity(' app --include=*.py`).
- Test files (`grep -rl … tests --include=*.py`): submit-all 9, Create's
  roster files 9, the identity rule 5.

### PR ladder

1. **This plan** (prose).
2. **The checks, as pure functions.** No route calls them yet. They
   cover the incoming-set identity check (today's
   `check_cross_table_identity` becomes its one-file case, with its
   signature kept), the relationships check against incoming rosters,
   and the new `problem`. Unit tests cover each Semantics bullet a
   function owns. This rung doesn't touch routes. It lands first
   because rung 3 can't be split without a regression: checking
   everything first under today's rule would refuse a Reviewees file
   checked against the reviewers it is about to replace.
3. **Check everything, then save everything** in submit-all, Create and
   the per-slot routes, in one `unit_of_work.atomic`. Tests cover the
   rename, a later failure leaving earlier slots unsaved, a Settings
   apply failure, Create, the lifecycle race, and Relationships with
   Reviewers. Plus the specs, a browser-check section, and the
   cumulative `diff-reviewer` read from rung 2's base.
4. **Close** (prose): run `spec-writer`, compact `Status`, update the
   README row.

### Definition of done

- By test: the rename lands when both files are uploaded together, and
  any refusal leaves every roster and the settings unchanged, on
  submit-all and on Create. The existing single-file tests pass
  unchanged.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

- None open (author, 2026-10-12; Decision).

### Out of scope

- Listing every failing slot at once (the deferred report page); the
  Setup pages' uploads (one file, already the rule); rolling back
  Create's session row (kept deliberately, per the spec's Failure mode).

### Doc impact

- `spec/quick_setup_card_spec.md` — "Per-slot dispatch": check everything, then save everything, in one unit; "Result reporting": its closing paragraph (nothing applies when a slot fails); "Validation scope": files uploaded together; "New-session variant": its Failure mode (Item 1).
- `spec/csv_contracts.md` — §3.1 "Cross-roster identity": files uploaded together are checked against each other, not against the rosters they replace; also the function table's incoming-set entry, the Relationships notes on incoming rosters, and the Create tag note "bails out at an earlier Quick Setup slot" (Item 1).
