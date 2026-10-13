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

The same refused file reads differently on the two surfaces
(`03_reviewers_problems.csv`, author's browser check, 2026-10-13):

- **Quick Setup's banner** groups by kind, with counts
  (`roster_problem_details`, `app/web/views/_quick_setup.py`):
  "ReviewerEmail is blank (2 rows)".
- **The Reviewers upload card** prints one line per row through
  `operator/partials/validation_results.html` ("Row 2: `ReviewerEmail`
  ReviewerEmail is required"), so a hundred bad rows print a hundred
  lines, each naming the field twice.

Quick Setup's "the Reviewers Setup page shows which rows" also misleads:
a refused file is never saved, so the page shows nothing.

### Decision

The author's rulings, 2026-10-13:

- **Kinds of problem with counts, never rows**, on Quick Setup and the
  Reviewers, Reviewees, Relationships and Observers upload cards, from one
  helper.
- **Validate is left alone.** It reports on the saved session
  (`app/services/validation.py`), which a refused file never reaches. The
  upload cards get their own partial, so Validate's template cannot change
  by accident.
- **Neither surface points at the other.** Quick Setup drops "the …
  Setup page shows which rows" and its "Open the … Setup page for per-row
  error details" fallback.

**Rejected:** row numbers under each kind ("rows 2, 3"). They grow with
the file, the problem being solved; they wait for
`guide/import_error_reporting.md`.

### Semantics

- **One helper, two callers.** The grouping (`problem`, else a
  file-level message, else "`<field>` has a problem") moves to a views
  module both import. Quick Setup keeps its redirect cap on top; the
  page renders uncapped, since kinds are bounded by the parsers' strings.
- **The card:** an error banner inside the upload card, "Could not
  import reviewers. The file has these problems:" over the lines, in
  place of the Issues card. The 400 re-render and open Unlock panel stay.
- **Blocking issues only**, as Quick Setup. The roster and relationship
  parsers raise no warnings today (`grep -c 'Severity.warning'` is 0).
- **Out:** Settings CSV errors, which are not per-row kinds and which
  Quick Setup already lists as lines.

### Judgment calls — decided

- **No scaffold rung:** an existing card's error changes; no page, card
  or navigation is added.
- **One build rung:** the helper, partial, callers and wording are one
  change; splitting them would ship a page disagreeing with Quick Setup.

### Status

**Closed 2026-10-13.** Shipped in #3006 as planned, plus §5a's scroll
target and a Secondary button back to the page, and one shared sentence
(`problems_sentence`). The author's browser check passed; at it, the
button was relabeled **Dismiss**, since nothing is pending to cancel
(`spec/ui_elements.md` §5a now says so). One `diff-reviewer` read found
no code defect; its prose findings were fixed, adding
`spec/ui_elements.md` to Doc impact. The close `spec-writer` pass, run with
the Dismiss sentence in place, found all four specs current. Left alone: the now-unincluded legacy branch of
`validation_results.html`, and (older) the unread `missing_confirm`, a
silent 400 when the Upload-gating script is off.

### Blast radius (measured)

Taken 2026-10-13 at `626eb38e`.

- Upload contexts passing `issues` (`grep -rn '"issues"' app/web/routes_operator/`):
  4, in `_shared.py`, `_setup_relationships.py`, `_setup_observers.py`,
  plus two empty defaults; Validate's is separate.
- `validation_results.html` includers
  (`grep -rn 'validation_results.html' app/web/templates`): 5, the four
  Setup pages and Validate.
- `ValidationIssue(` sites with a `problem`: 16 of 23 in
  `csv_imports.py` (the rest file-level), 6 of 6 in `relationships.py`.
- Tests on the four import routes asserting error text: at most 6
  (`grep -rlE '<kind>/import' tests | xargs grep -lE 'Row [0-9]|is required|issue-list'`).
- Wording: 2 strings in `_quick_setup.py`; 1 passage in
  `spec/quick_setup_card_spec.md` ("Failure").

### PR ladder

1. **This plan** (prose, with Items 1 and 2's close).
2. **Build:** the helper and partial, the four cards and Quick Setup on
   them, the wording, tests, specs, a browser-check section with upload
   files, the struck `guide/import_error_reporting.md` Out of scope line
   ("The Setup pages' uploads already list every row"), and a
   `diff-reviewer` read on the rung.
3. **Close** (prose).

### Definition of done

- By test: the four cards and Quick Setup show a refused file's kinds
  with counts and no rows; a hundred bad rows make one line; Quick Setup
  names no Setup page; Validate renders as before.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

- None open (author, 2026-10-13; Decision).

### Out of scope

- Row numbers anywhere; Settings CSV error lines; the Validate page.

### Doc impact

- `spec/quick_setup_card_spec.md` — "Result reporting" / "Failure": the banner no longer points at a Setup page, and the lines come from the helper the Setup pages share (Item 3).
- `spec/csv_contracts.md` — the "re-renders the page at **400** with the issue list" passage, now kinds with counts (Item 3).
- `spec/setup_pages.md` — the upload card's failure: kinds of problem with counts in the card, not the Validate-style issue list (Item 3).
- `spec/ui_elements.md` — the banner family's sub-elements gain `.banner-lead`; §5a's one exception, the upload-problems banner's Dismiss (Item 3; added at build and at close).
