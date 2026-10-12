# Quick Setup update

**Opened:** 2026-10-12 · **Theme:** how Quick Setup checks and applies
several files at once · **Related:** `spec/quick_setup_card_spec.md`,
`spec/csv_contracts.md` §3

A standalone plan at the author's naming, not a `segment_*.md`, in the
shape of `guide/participant_info.md`. Items close independently, each
with its own `### Doc impact` and `### Status`. `tools/close_check.py`
reads only `segment_*` files, so an item's `Doc impact` is checked by
hand at its close.

---

## Item 1 — Files uploaded together are checked together, and land together

### Opportunity

Submit-all and Create run the slots one at a time: Reviewers, then
Reviewees, Relationships, Observers, Settings. Each slot checks its
file and commits it before the next slot reads its own file. Two things
follow (author, 2026-10-12):

- **A rename across rosters cannot be uploaded at all.** Say `bob@x` is
  "Bob Smith" on both rosters, and both new files say "Robert Smith".
  The Reviewers file is checked against the current Reviewees, which
  still say "Bob Smith", so it is refused. The Reviewees file that
  would have agreed with it is never read.
- **A failure partway leaves a half-applied setup.** New reviewers
  committed beside old reviewees is a state the operator never asked
  for, and the banner names only the slot that failed.

### Decision

The author's rule, 2026-10-12:

- **One file:** it is checked against every existing roster except the
  one it replaces. This is already how it works
  (`check_cross_table_identity` excludes its own kind), and it doesn't
  change.
- **Several files:** they are checked against **each other**, and
  against the existing rosters that are **not** being replaced.
- **All or nothing:** every attached file is checked before any is
  saved, and the saves share one commit. One refused file leaves
  everything as it was.

**Rejected:** keeping the sequential dispatch and changing only the
identity rule. A Reviewees check would then have to see a Reviewers
file that is not yet saved, or else trust a commit that a later slot
could still undo. Checking everything first and saving everything in
one unit is the only order in which "checked against each other" means
the same thing as "saved together".

### Semantics

- **Who holds an email.** For each roster kind in the upload, the
  holders are:
  - the incoming rows of every *other* uploaded roster kind;
  - the existing rows of every roster kind *not* uploaded.

  A single-file upload reduces to today's rule exactly.
- **What is skipped and what conflicts.** Inactive rows, rows with no
  name, and non-email identifiers are skipped
  (`is_comparable_identity`), as today. Names compare exactly. A
  mailbox holding two names conflicts with any third.
- **Duplicates inside one file** are the parser's own check, as today.
- **A clash between two incoming files** is reported on the earlier
  slot in dispatch order. It gets a new `problem`: "ReviewerEmail is
  used under a different name in the uploaded Reviewees file". A clash
  with an existing roster keeps "…in another roster".
- **Relationships with rosters.** A `ReviewerEmail` must be on the
  incoming reviewers when a Reviewers file is attached, and on the
  current reviewers otherwise; `RevieweeEmail` likewise. The rows need
  real ids, so the file is parsed again after the rosters are flushed
  inside the unit. That second parse cannot disagree with the first,
  so a disagreement raises and rolls the unit back rather than being
  reported.
- **Order of the gates.** For each slot in dispatch order:
  1. lifecycle;
  2. parse, the identity check and the relationship check;
  3. the replacement tick and the response-loss acknowledgement.

  The first failure stops the submit, and nothing has been written.
- **Settings.** Its file-level and row-level errors are checked up
  front (`_read_settings_csv`). Errors that `apply_session_config`
  finds only while applying are known only then: Settings applies
  last, inside the unit, and its failure rolls back the rosters too,
  reported on the Settings slot.
- **A lifecycle race.** The session lock is taken at the first save.
  A `SessionStateConflict` anywhere in the unit rolls all of it back,
  with the `lifecycle` reason on the slot that hit it.
- **Create.** The session row is committed first and stays, as today.
  The uploads are all or nothing. The typed tags and staged owners are
  still written on the error path, outside the unit.
- **Audit.** Each roster still writes its own `*.imported` event, with
  the request's one correlation id. A rollback writes none of them. No
  new event type is added.

### Judgment calls — decided

- **The banner still reports one slot**, the first that fails. It holds
  one slot by design, and listing every slot's problems belongs to the
  deferred report page (`guide/import_error_reporting.md`).
- **The unit is the existing `unit_of_work.atomic`.** It already nests:
  `save_reviewers`, `save_reviewees` and `save_relationships` open their
  own, and `_save` commits through `unit_of_work.commit`. The one raw
  `db.commit()` in the path is `_apply_settings_upload`, which moves to
  `unit_of_work.commit`.
- **The per-slot routes run the same pipeline with one file**, so a
  single upload and a submit-all cannot drift apart.
- **The Setup pages' own uploads don't change.** They take one file,
  which is the rule already.

### Blast radius (measured)

Taken 2026-10-12 at `1c08ae3a` (#2997).

| What | Count | Command |
|---|---|---|
| `await _run_quick_setup_import(` | 5 | `grep -c 'await _run_quick_setup_import(' app/web/routes_operator/_quick_setup.py` |
| `await _run_quick_setup_relationships(` | 3 | same file, same form |
| `await _run_quick_setup_observers(` | 3 | same |
| `await _run_quick_setup_settings(` | 3 | same |
| `check_cross_table_identity(` call sites | 4 | `grep -rn 'check_cross_table_identity(' app --include=*.py \| grep -v 'def '` (two in `_quick_setup.py`, one each in `_shared.py` and `_setup_observers.py`) |
| Raw `db.commit()` in the slot path | 1 | `grep -n 'db.commit()' app/web/routes_operator/_quick_setup.py` |
| Test files posting to submit-all | 9 | `grep -rl 'quick-setup/submit-all' tests --include=*.py` |
| Test files sending Create's files | 9 | `grep -rlE 'reviewers_file\|reviewees_file' tests --include=*.py` |
| Test files on the identity rule | 5 | `grep -rl 'check_cross_table_identity\|different name\|names must match' tests --include=*.py` |
| Specs naming submit-all | 3 live | `grep -rl submit-all spec` (`csv_contracts`, `operator_button_audit`, `quick_setup_card_spec`) |

### PR ladder

1. **This plan** (prose).
2. **The checks, as pure functions.** No route calls them yet, so
   nothing changes for the operator. In `app/services/csv_imports.py`
   and `app/services/relationships.py`:
   - an identity check over an *incoming set*: the holders are the
     incoming rows of the other uploaded kinds plus the existing rosters
     not uploaded. Today's `check_cross_table_identity` becomes its
     one-file case and keeps its signature for the Setup pages;
   - a relationships check against the incoming rosters, falling back
     to the current ones;
   - the new cross-file `problem`.

   Unit tests cover every Semantics bullet above that a function owns.
   This rung must not touch the routes.
3. **Check everything, then save everything.** Submit-all, Create and
   the per-slot routes run every gate first, then every save inside one
   `unit_of_work.atomic`, using rung 2's checks.
   `_apply_settings_upload`'s commit moves to `unit_of_work.commit`.
   Integration tests cover:
   - the rename case;
   - a later slot's failure leaving earlier slots unsaved;
   - a Settings apply failure rolling back the rosters;
   - Create keeping its session, tags and owners;
   - the lifecycle race;
   - Relationships uploaded with Reviewers.

   The rung also updates the specs, adds a browser-check section, and
   runs the cumulative `diff-reviewer` read from rung 2's base.
4. **Close** (prose): run `spec-writer`, compact `Status`, update the
   README row.

Rung 2 lands first and on its own because rung 3 cannot be split
without a regression. Checking everything first under today's
identity rule would refuse a Reviewees file compared against the
reviewers it is about to sit beside. That is the case today's
sequential order happens to allow.

### Definition of done

- Reviewers and Reviewees uploaded together with a renamed `bob@x` both
  land, by test.
- Any slot refusing leaves every roster and the settings as they were,
  by test, on submit-all and on Create.
- A single-file upload refuses and accepts exactly what it did before,
  by the existing tests, unchanged.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

- None open. All or nothing, and the cross-file rule: the author,
  2026-10-12 (see Decision).

### Out of scope

- **Listing every failing slot's problems at once.** That is the
  deferred report page, `guide/import_error_reporting.md`.
- **The Setup pages' uploads.** They take one file, which is the rule
  already.
- **Rolling back Create's session row on an upload failure.** The
  operator would lose the form they filled in, and the Failure mode
  in `spec/quick_setup_card_spec.md` keeps the row deliberately.

### Doc impact

- `spec/quick_setup_card_spec.md` — the following change (Item 1):
  - "Per-slot dispatch": check everything, then save everything, in one
    unit;
  - "Result reporting": the closing paragraph, which says nothing is
    applied when a slot fails;
  - "Validation scope": files uploaded together;
  - "New-session variant": its Failure mode.
- `spec/csv_contracts.md` — §3.1 "Cross-roster identity": files uploaded
  together are checked against each other and not against the rosters
  they replace. Also the function table's entry for the incoming-set
  check, the Relationships notes on checking against incoming rosters,
  and the Create tag note ("bails out at an earlier Quick Setup slot")
  (Item 1).
