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

**Closed 2026-10-13.** Shipped as planned in #2999 (the checks as pure
functions) and #3000 (check everything, then save everything). The
author's browser check passed 2026-10-13. One cumulative `diff-reviewer`
read plus a `spec-writer` verify both found the same defect: a blocked
roster file was left out of the identity check, so its old roster could
refuse an earlier slot. It was fixed by passing the file in empty, with a
test. Decisions confirmed at build:

- A Relationships file refused at its save-time parse (a roster edited
  between the check and the lock) is reported as its `parse` problem,
  not raised as a 500. The plan said "raises".
- One correlation id per submit, rather than one per slot.
- **Deferred:** moving the pipeline from `_quick_setup.py` into a
  service. It is a refactor of its own.

The close `spec-writer` pass found `spec/quick_setup_card_spec.md`
"Slots" missing its Observers slot, and `spec/rrw_functional_spec.md`
silent on all-or-nothing. Both are fixed.

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
- `spec/rrw_functional_spec.md` — the Session Home Quick Setup card bullet: Submit checks every staged file, then saves all or none (Item 1; added at close).

---

## Item 2 — Observers on Home's card, and an upload turns its tab on

### Opportunity

Home's Quick Setup card shows the Observers slot only while
`observers_enabled` is on, while the New session card always shows it.
Relationships shows on both whatever `relationships_enabled` says. And
an Observers or Relationships file that saves while its toggle is off
leaves rows behind a hidden tab: Create already does this for observers
(author, 2026-10-12).

### Decision

The author's ruling, 2026-10-12:

- **Home always shows the Observers slot**, as New session does. Both
  cards then show the same five slots.
- **A Quick Setup upload that populates Observers or Relationships turns
  that toggle on**, if it was off. This applies on Home and on Create.

**Rejected:** showing each slot only while its toggle is on. That
needs a script on New session (its toggles sit in the same form), a
server rule for a file posted while its toggle is off, and a card whose
slot count changes. The upload-turns-it-on rule instead matches the
lock-on-data invariant `update_session` already enforces
(`spec/participant_model.md`), where a toggle can't be turned off while
its roster has rows.

### Semantics

- **Populates** means the file saved at least one row. A header-only
  file replaces the roster with nothing and leaves the toggle alone.
- **Inside the unit:** the toggles are set inside Item 1's
  `unit_of_work.atomic`, after the last slot (Settings included). So a
  refusal anywhere leaves them unchanged too, and a Settings file saying
  `observers_enabled=false` can't hide the rows that the same submit
  just saved.
- **Audit:** each change writes `session.feature_toggled` (the event the
  Session details toggle writes), with the change and the upload as its
  reason.
- **Validated sessions:** no extra demotion. The roster import in the
  same submit already demotes a validated session.
- **Not covered:** a Settings file alone turning a toggle off while rows
  exist. That is today's force-applied settings behavior, unchanged here.

### Judgment calls — decided

- **The toggle turns on and nothing else changes.** No banner or message
  says so: the tab simply appears.
- **The Home card's description always lists observers**, and its
  layout keeps one fixed five-slot split.

### Status

**Closed 2026-10-13.** Shipped as planned, as one build rung (#3002).
The author's browser check passed 2026-10-13. The rung's `diff-reviewer`
read found no code defect; its notes fixed three more stale "Observers
conditional" lines and moved the roster-to-toggle rule into `sessions`.
A Codex review moved the toggles' before-state read under the session
lock. The event records the submit's net change, so a Settings file and
an upload that meet log nothing. The close `spec-writer` pass added the
toggle note to `spec/csv_contracts.md`'s inbound-paths row.

### Blast radius (measured)

Taken 2026-10-12 at `7acfac1e`.

- `observers_enabled` appears 5 times in `app/web/views/_quick_setup.py`
  (`grep -c`): the Home slot gate and the description phrase.
- One template comment describes the conditional split
  (`app/web/templates/operator/partials/_quick_setup_card.html`).
- `tests/integration/test_quick_setup_observers_slot.py` asserts the
  hidden slot while observers are off; that test inverts.
- Live prose naming the conditional slot (`grep -rn "Observers conditional\|Observers slot when\|Observers when" spec README.md`, archive aside):
  `spec/quick_setup_card_spec.md` "Slots", `spec/session_home.md` (prose and lifecycle table),
  `spec/csv_contracts.md`, `spec/README.md`, `spec/rrw_functional_spec.md`, `README.md`.
- `session.feature_toggled` has 1 schema entry in `app/services/audit.py`.

### PR ladder

1. **This plan item** (prose).
2. **Build.** The Home slot is always shown, and the save unit turns the
   toggles on. Tests cover:
   - the slot showing with observers off;
   - each toggle turning on from Home and from Create;
   - a header-only file leaving the toggle off;
   - a refusal leaving the toggles unchanged;
   - a Settings file saying `false` in the same submit;
   - the audit event.

   Plus the spec, a browser-check section, and a `diff-reviewer` read
   on the rung's own diff, since it is the item's only build rung.
3. **Close**, with Item 1's close if they land together.

### Definition of done

- By test: Home's card has five slots whatever the toggles say. A
  Relationships or Observers upload that saves rows turns its toggle
  on, from Home and from Create, inside the unit.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

- None open (author, 2026-10-12; Decision).

### Out of scope

- Gating slots on their toggles (rejected above).
- Settings-only toggle changes over existing rows.

### Doc impact

- `spec/quick_setup_card_spec.md` — "Slots": Observers always renders on both variants; "Per-slot dispatch" or "Result reporting": an upload that populates Observers or Relationships turns its toggle on; "New-session variant": the Observers bullet (Item 2).
- `spec/participant_model.md` — the "Lock-on-data invariant": the converse, that a Quick Setup upload which populates a roster turns its flag on (Item 2).
- `spec/session_home.md` — the Quick Setup card: five slots whatever the toggles, in its prose and its lifecycle table (Item 2).
- `spec/csv_contracts.md` — the inbound-paths row for the Quick Setup slots (Item 2).
- `spec/README.md` — the `quick_setup_card_spec.md` row (Item 2).
- `spec/rrw_functional_spec.md` — the Session Home Quick Setup card bullet (Item 2).
- `spec/settings_inventory.md` — the `relationships_enabled` / `observers_enabled` rows: also turned on by an upload (Item 2).
- `README.md` — the Quick Setup card bullet (Item 2).

---

## Item 3 — The Setup pages' upload cards report problems the way Quick Setup does

### Opportunity

The two surfaces report the same refused file differently. On
`03_reviewers_problems.csv` (author's browser check, 2026-10-13):

- **Quick Setup's banner** groups the problems by kind, with a count for
  each, using `roster_problem_details` (`app/web/views/_quick_setup.py`).
  It shows "ReviewerEmail is blank (2 rows)" and "Status is not active
  or inactive (1 row)".
- **The Reviewers page's upload card** lists one line per row through
  `operator/partials/validation_results.html`. It shows "Row 2:
  `ReviewerEmail` ReviewerEmail is required" twice, then a line for
  Row 4. The field name prints twice, and a file with a hundred bad rows
  prints a hundred lines.

Quick Setup's banner is also misleading today. "The Reviewers Setup
page shows which rows" holds only if the operator uploads the same file
there again. A refused file is never saved, so nothing carries over.

### Decision

The author's rulings, 2026-10-13:

- **Both surfaces list the kinds of problem, with a count for each, and
  never a list of rows.** The Reviewers, Reviewees, Relationships and
  Observers upload cards render the same lines as Quick Setup, from the
  same helper.
- **Validate is left alone.** A refused file is never saved, so Validate
  never sees it. Validate computes its own issues from the saved session
  (`app/services/validation.py`). Today it shares only the template
  `validation_results.html`. The upload cards get their own partial, so
  that the Validate mode cannot change by accident.
- **Neither surface points at the other.** Quick Setup drops "the …
  Setup page shows which rows", and its no-detail fallback "Open the …
  Setup page for per-row error details" goes with it.

**Rejected:** listing the row numbers under each kind ("ReviewerEmail is
blank: rows 2, 3"). It grows with the file, which is the problem being
solved. Row numbers wait for `guide/import_error_reporting.md`'s full
problem list.

### Semantics

- **One helper, two callers.** The grouping (by `problem`, then the
  message for a file-level issue, then "`<field>` has a problem")
  moves out of `_quick_setup.py` into a views module both can import.
  Quick Setup keeps its redirect cap (`_capped`) on top. The page
  renders the lines uncapped: the number of kinds is bounded by the
  parser's own problem strings, not by the file.
- **The page card's shape:** an error banner inside the upload card,
  reading "Could not import reviewers. The file has these problems:"
  over the list, in place of the Issues card. The 400 re-render, the
  open Unlock panel and the file input are unchanged.
- **Which issues count:** blocking ones only, as in Quick Setup. Today
  the roster and relationship parsers raise no warnings
  (`grep -c 'Severity.warning'` over both is 0). If one ever does, it
  doesn't refuse the file and so has no banner to join.
- **Relationships** carries a parse refusal and its FK refusals ("…is
  not in the session's reviewers") through the same helper. Its
  `problem` strings already exist (6 of 6 issues).
- **Settings CSV uploads are out of scope.** Their errors are not
  per-row kinds (`instruments[1].name: name is required`), and Quick
  Setup already lists them as lines.

### Judgment calls — decided

- **No scaffold rung.** This changes how an existing card reports an
  error. It adds no page, card or navigation (`CLAUDE.md`, "Consequential
  UI lands scaffold-first").
- **One build rung.** The helper, the partial, both callers and the
  wording are one coherent change. Splitting them would ship a page that
  disagrees with Quick Setup for a rung.

### Blast radius (measured)

Taken 2026-10-13 at `626eb38e`.

- Upload routes that re-render with `issues`: 4
  (`grep -rn '"issues"' app/web/routes_operator/`, excluding Validate's
  and the two empty defaults). They are `_shared.py` (Reviewers and
  Reviewees), `_setup_relationships.py` and `_setup_observers.py`.
- `validation_results.html` is included by 5 templates
  (`grep -rn 'validation_results.html' app/web/templates`): the four
  Setup pages and Validate. Validate keeps it.
- `roster_problem_details` lives in `app/web/views/_quick_setup.py`, with
  one test file (`tests/integration/test_quick_setup_problem_types.py`).
- Issues carrying a `problem`: 16 of 23 `ValidationIssue(` sites in
  `csv_imports.py`, and 6 of 6 in `relationships.py`. The other seven
  are file-level issues, whose message stands as the line.
- Test files touching the four import routes and asserting error text
  (`grep -rlE '<route>/import' tests | xargs grep -lE 'Row [0-9]|is required|must be one of|issue-list|pill-error'`):
  6, an upper bound to read through at build.
- The wording: 2 strings in `_quick_setup.py` (lines 466 and 471); 1
  passage in `spec/quick_setup_card_spec.md` ("Failure").

### PR ladder

1. **This plan** (prose, with Items 1 and 2's close).
2. **Build:**
   - the shared helper and the upload-problems partial;
   - the four page cards and Quick Setup's banner reading it;
   - the wording change;
   - tests: each page shows kinds with counts and no "Row N"; a
     hundred-row file shows one line per kind; Validate's markup is
     unchanged; Quick Setup's banner no longer names the Setup page;
   - the specs and a browser-check section, with upload files in
     `guide/browser_check_files/`;
   - a `diff-reviewer` read on the rung, as the item's only build rung.

   It also strikes `guide/import_error_reporting.md`'s Out of scope line
   "The Setup pages' uploads already list every row".
3. **Close** (prose).

### Definition of done

- By test: each of the four upload cards shows a refused file's
  problems as kinds with counts, with no row numbers, and Quick Setup's
  banner shows the same lines without pointing at a Setup page.
  Validate's issue list renders as before.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

- None open (author, 2026-10-13; Decision).

### Out of scope

- Row numbers anywhere (`guide/import_error_reporting.md`, deferred).
- Settings CSV error lines (above).
- The Validate page.

### Doc impact

- `spec/quick_setup_card_spec.md` — "Result reporting" / "Failure": the banner no longer points at a Setup page, and the lines come from the helper the Setup pages share (Item 3).
- `spec/csv_contracts.md` — the "re-renders the page at **400** with the issue list" passage, now kinds with counts (Item 3).
- `spec/setup_pages.md` — the upload card's failure: kinds of problem with counts in the card, not the Validate-style issue list (Item 3).
