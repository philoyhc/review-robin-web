# Segment 19T — Odds and ends

**Opened:** 2026-09-24 · **Theme:** small operator-UI adjustments the author
logs one at a time; items close independently · **Related:**
`spec/instruments.md`, `guide/archive/segment_19S_post_assessment.md`

A holding segment for small, unrelated adjustments, each an item with its own
`Doc impact` and `Status`. It closes when every item has.

---

## Item 1 — Instruments: the ✓ button, the blank row, the Band 3 split

**Logged 2026-09-24 on the author's instruction.**

### Opportunity

The Band 3 response-field rows on the Instruments page carry a ✓ whose job
is unclear. Its tooltip says "Save this response field to the pills +
preview", yet it saves nothing (`spec/instruments.md`: "Pure UX — nothing
persists across reload until the card-wide bulk Save runs").

Its enabled state is not tied to that job. A row with a pill greys ✓ out
until `data-row-pending` is set, and *any* keystroke sets that flag and
nothing but ✓ clears it (`instruments_index.html`,
`newModelRfRecomputeActionStates`). So a row typed and typed back offers ✓
with nothing to push.

Two smaller frictions sit beside it:
- **A blank row.** The template always renders a trailing empty "starter"
  row after the populated ones (`spec/instruments.md` Band 3), so the list
  never ends where the fields do.
- **The Band 3 split.** Visibility and Response fields split the band 1:1
  (`grid-template-columns: 1fr 1fr`), though the response-field rows carry
  far more controls.

### Decision

1. **✓ does two things and nothing else**:
   - on a row with no pill, it creates the field's pill in Band 2 and adds
     its column to the reviewer-surface preview;
   - on a row whose preview-bearing attributes differ from its pill, it
     updates the pill and the preview.

   It is **enabled only when a row meets one of those** and disabled
   otherwise. Toggling **R** (required) or **≡** (help text) never needs ✓,
   because both already update the preview live. **Save alone persists**;
   ✓'s tooltip stops saying "Save".
2. **No standing blank row.** The template renders only populated rows.
   **"+"** adds a blank row. **Cancel** (discard without saving) removes it,
   because the discard reload re-renders from persisted state. Deleting the
   last row leaves no rows rather than a blank one.
3. **Band 3 splits 2 : 3**: Visibility 2/5, Response fields 3/5
   (`grid-template-columns: 2fr 3fr`).

**Rejected: keeping the sticky pending flag and only renaming the tooltip.**
The flag answers "was this row touched", not "does this row differ from its
pill", which is the author's rule. A comparison is the only thing that greys
✓ again when an edit is typed back.

**Amendment (2026-09-24, the author, after rung 2).** It supersedes point 2's
single "+" and its last-row rule:
- **A "+" on every row** inserts a blank row directly below that row. It
  heads the row, before the name field, and X is the red `destructive`
  button, as in Band 1 (the author, after rung 2b). The single "+" under
  the list goes.
- **The last row cannot be deleted**: X is inactive while one row is left.
  So a card with no saved fields renders one blank row, or it would have
  no "+" at all.
- **Order follows the rows.** ✓ on a row inserted between A and B puts
  its pill between theirs (A, C, B), and Save persists the rows in row
  order. Today Save writes pill order and appends un-ticked rows last,
  and dragging a response pill leaves its row where it was. So a
  response-pill drag now also moves its row. The author accepts rows that
  catch up only on reload; the move is here because Save now reads row
  order, so without it Save would undo a drag.

### Semantics

- **"Differs"** compares the row's current values with what its pill and
  the preview show. Which attributes the pill carries versus which the
  preview reads from the row is measured in rung 2 (Open questions). R and ≡
  are excluded, since they already propagate on click.
- **A blank or invalid row** keeps ✓ disabled, as today: no name, or
  `newModelRfValidateShape` fails.
- **Zero rows.** (Superseded by the amendment: a card with none renders
  one blank row.) "+" must work with no row to clone. Today it clones the
  first row, so it will build from a `<template>` instead.
- **A "+" row left blank at Save** is already dropped: `serializeRow`
  returns `null` for a nameless row.
- **Cancel's enablement.** "+" is in the card's dirty-marking click list,
  so adding a row enables Cancel, and Cancel's reload removes the row.
- **Narrow widths.** The Band 3 grid has no media query today; 2 : 3 changes
  only the ratio.

### Judgment calls — decided

- ✓ keeps staging into `band2_state_snapshot` and marking the card dirty.
  That is not persisting, and Save still owns the write (2026-09-24).
- ~~Deleting the last row removes it outright.~~ Superseded by the
  amendment: the last row stays (2026-09-24).

### Blast radius (measured)

Taken 2026-09-24 at `b705245d`.

- **Template:** one file, `app/web/templates/operator/instruments_index.html`.
  - 41 references to `newModelRf` (`grep -c 'newModelRf'`);
  - the Band 3 grid at the `data-new-model-band3` div;
  - the trailing row under `Trailing empty row`;
  - `newModelRfAddRow`, `newModelRfDeleteRow` and
    `newModelRfRecomputeActionStates`.
- **Tests:** one file cites the row markup,
  `tests/integration/test_instrument_builder_routes.py`, with 5
  `data-new-model-rf-row` markers
  (`grep -rln 'data-new-model-rf-\|newModelRf' tests`).
- **Spec:** `spec/instruments.md`, three places: the band table, the
  "trailing empty starter row" sentence, and the ✓ row of the button table
  (`grep -n 'starter row\|✓\*\* button\|Visibility, Response fields'`).

### Status

**Closed 2026-09-24** (#2598, #2599, #2600, #2601; the capture in #2602).
The item's diff base was `de83af9d`, main before rung 1.

**What the ladder became.** Rungs 1 and 2 shipped as planned. The
author's amendment added rung 2b (per-row "+", the last row kept,
row-ordered ✓, Save and drag), then a follow-up moved "+" to the head of
the row and made X red. The close took Item 2's close with it.

**Decisions confirmed at build:**
- The open question: the preview read the name from the pill but type
  and bounds from the live row on every rebuild. So the pill now carries
  the pushed shape (`data-rf-*`), the preview reads it, and ✓ compares
  the row with it.
- A pill that ✓ creates starts selected, so its column joins the preview.
- The amber marker means "differs from the pill", valid or not.
- A successful Save syncs every paired pill to its row, since Save persists
  rows as typed and doesn't reload.
- R and ≡ stage for Save; ✓ is never needed for them.

**Defects on main, found in Chromium and fixed:**
- ✓ and X called `saveBand2State` from outside its closure, so X never
  removed a row that had a pill. They now reach it through
  `window.newModelStageBand2State`.
- R and ≡ alone never enabled Save.
- The first keystroke left ✓ off.

**Reads.** Three `diff-reviewer` reads:
- the cumulative read at rung 2 found Save-without-✓ staleness, the stale
  Guide capture and the marker, all fixed;
- rung 2b's read found stale prose;
- the "+" / X read found no defects, and its §6 note went to Doc impact.

### PR ladder

1. **The blank row and the split.** Drop the trailing row. "+" builds from
   a `<template>`. X on the last row removes it. Band 3 goes to
   `2fr 3fr`. Tests pin: no blank row renders, "+" works from zero rows,
   and the grid ratio. It must not touch ✓.
2. **✓ by comparison.** Measure the pill- versus row-borne attributes, then
   replace the pending flag with a comparison and reword the tooltip.
   Tests pin the enable rule's markup; Chromium drives the behavior. This
   is the item's last build rung, so `diff-reviewer` reads the cumulative
   diff from `b705245d`.
2b. **The amendment** (added 2026-09-24). Per-row "+", the last row kept,
   row-ordered ✓ and Save, and a pill drag that moves its row. It reopens
   `app/`, so it takes its own `diff-reviewer` read on its diff.
3. **Close.** `spec/instruments.md`, the browser checks, a `docs/status.md`
   row and `spec-writer`.

### Definition of done

- ~~No trailing blank row renders; "+" adds one from zero rows.~~ Only
  saved rows render, or one blank row when there are none. Each row's "+"
  inserts below it, and Cancel's reload removes an unsaved row.
- X is inactive on the only row left.
- ✓ places a new pill in row order; Save persists row order; a response-pill
  drag moves its row.
- ✓ is enabled only for a named, valid row with no pill or with
  preview-bearing values that differ from its pill; R and ≡ never enable it.
- Band 3 renders `grid-template-columns: 2fr 3fr`.
- `spec/instruments.md` states all of the above.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19T.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- ~~Which attributes does the preview read from the pill, and which from
  the row?~~ The name from the pill; type and bounds from the row, until
  rung 2 moved them onto the pill (Status).

### Out of scope

- What ✓ does to persistence: Save's job, unchanged.
- The reviewer surface itself; only the builder's preview is touched.

### Doc impact

- `spec/instruments.md` — Band 3: no starter row except one blank row at
  zero fields; a "+" per row, at its head, inserting below; X in the red
  `destructive` role and inactive on the last row; the
  ✓ row's two purposes and enable rule; R / ≡ enabling Save; ✓, Save and a
  pill drag following row order; the 2 : 3 split (Item 1).
- `guide/post_azure_todo_checklist.md` — browser checks for the ✓ enable
  rule, a row's "+" and Cancel, the last row, row order through ✓ / Save /
  drag, R / ≡ alone enabling Save, and the split (Item 1).
- `app/web/static/guide/instrument-card-fields-and-visibility.png` — retaken
  with its `-dark` twin on the dev slot: the capture shows the 1 : 1 split
  and the blank row (Item 1).
- `spec/ui_elements.md` — §6's note puts a field builder's row delete / add
  on `.btn-icon.danger` / `.action`, but Band 1's X and now Band 3's are
  `btn destructive`: reconcile the note with the author's ruling (Item 1).
- `docs/status.md` — row when the item closes (Item 1).

---

## Item 2 — Instruments: `?editing` no longer locks the action rows

**Logged 2026-09-24 on the author's report.**

### Opportunity

With `?editing=<id>` in the URL, every card's Replicate, Delete,
+Instrument and +Page break, and the page-break ×, render disabled. The
tooltips say "Save or cancel … first", but neither gets the page out of
that state:
- Save is a fetch, with no reload;
- Cancel's discard reload re-adds `?editing` to keep the card unlocked;
- the in-page Lock leaves the URL alone.

The rule comes from 10D Slice 5 (`11c5a730`, 2026-05-02), when edit mode
was only the server's `?editing` and a form post silently lost unsaved
edits. It also held a mutual lock against the Response Type Definitions
row editor, which has since retired. 18R Item 2 then added the client lock
layer and the nav-away guard, but kept the rule. An in-page Unlock
never sets `?editing`, so the same unlocked card disables nothing that
way. `spec/instruments.md` states the rule for Replicate and +Instrument
("another instrument is being edited").

### Decision

**An open card no longer disables anything.** The disable conditions keep
only their other reasons: a session that can't be edited, the only
instrument, and the page-break placement rules. The nav-away guard
(`beforeunload` on a dirty card, 18R Item 2 PR 2) already warns before
these form posts discard unsaved edits. **Lock strips `?editing`** from
the URL with `history.replaceState`, so a reload lands locked.

**Rejected: disabling the four in-page while any card is unlocked.** That
keeps a rule the leave-page guard already covers, and it disables work
on clean cards too.

### Semantics

- A dirty card and a form post: the `beforeunload` confirm fires. Only the
  discard reload (Cancel, a dirty Lock) sets the intentional-nav flag. Save
  is a fetch and never leaves the page.
- The page-wide "one unlocked card" rule (Unlock on a second card) is
  untouched.

### Blast radius (measured)

Taken 2026-09-24 at `cdbc6c96`.
- `is_some_instrument_editing`: 1 view key (`app/web/views/_instruments.py`)
  and 3 template uses in `instruments_index.html`: the action-row disable,
  its title, and the page-break ×
  (`grep -rn is_some_instrument_editing app/`).
- `spec/instruments.md`: the Replicate / +Instrument disable lists
  (`grep -n "being edited" spec/instruments.md`);
  `spec/operator_button_audit.md` rows 54–55, "edit lock"
  (`grep -n "edit lock\|edit-lock" spec/operator_button_audit.md`). The
  second was missed at logging and found by the item's read.
- No test pins the rule (`grep -rn "open instrument edit" tests/`).

### PR ladder

1. **The fix.** Drop the editing condition and the view key; Lock strips
   `?editing`. Tests pin the enabled buttons under `?editing` and the
   strip. It takes a `diff-reviewer` read.
2. **Close**, together with Item 1's.

### Definition of done

- Under `?editing=<id>`, Replicate, Delete, +Instrument, +Page break and
  the page-break × render enabled, unless one of their other reasons
  applies.
- Lock leaves the URL without `?editing`.
- `spec/instruments.md` drops "another instrument is being edited".
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19T.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- None.

### Status

**Closed 2026-09-24** (#2603, closed with Item 1). It shipped as planned:
the fix and the log landed together. One `diff-reviewer` read found no
defect in the change. It found three gaps, all fixed in #2603:
- the test's +Page break check passed without the fix, and now pins it;
- `spec/operator_button_audit.md` was missing from Doc impact;
- the nav-guard comment and Semantics wrongly said Save sets the
  intentional-nav flag.

`spec-writer` at close raised two flags, both adjudicated:
- `spec/operator_button_audit.md` row 57 still described Lock as `?editing`
  and a disabled `<button>` under an edit lock. The close restated it.
- The spec never gave the page-break × an editing condition, so the Doc
  impact claim was dropped.

### Out of scope

- The legacy no-JS routes that redirect to `?editing`. They now only keep a
  card open.
- Ticking a card's Delete confirm checkbox marks the card dirty, because the
  tracker listens for `change` card-wide. So Delete on a clean card still
  gets the leave-page prompt. This predates the item; the read flagged it
  (2026-09-24).

### Doc impact

- `spec/instruments.md` — Replicate / +Instrument / Delete lose the "another
  instrument is being edited" condition; Lock strips `?editing` (Item 2).
- `spec/operator_button_audit.md` — the Replicate and Delete rows lose their
  "edit lock" gating; row 57 (Lock / Unlock) restated (Item 2).
- `guide/post_azure_todo_checklist.md` — browser check: Cancel, then Lock,
  leaves the action row live (Item 2).
- `docs/status.md` — row when the item closes (Item 2).

---

## Item 3 — Small fixes register

**Opened 2026-09-24 on the author's instruction.** A register item for
one-line fixes too small for an item of their own. It stays open for more
entries and closes when the author says. Each entry has the defect, the
fix and its PR, and the checks the ladder owes are the same per entry: a
test, a `diff-reviewer` read on any code, and Doc impact.

### Entry 1 — the Delete confirm checkbox dirtied the card

- **Defect.** The dirty tracker listens for `input` / `change` card-wide,
  and the Delete confirm checkbox sits inside the card. Ticking it enabled
  Save and Cancel with nothing to save. It also made Delete, a form post,
  trip the `beforeunload` "Leave site?" prompt on a clean card. Unticking
  didn't clear it. Found by Item 2's read. It predates 19T.
- **Fix.** The tracker's `input` / `change` handler skips targets inside
  `[data-delete-confirm]`. Chromium: ticking leaves the card clean with
  Delete live; a row edit still dirties it.

### Entry 2 — the Name and Email pills could be unselected

- **Defect** (the author, 2026-09-24). Name and Email are locked display
  fields: the server refuses to hide them. Their Band 2 pills still
  toggled, so unselecting one dropped its preview column and enabled
  Save for a change the server ignored.
- **Fix** (#2609). The view marks them `locked`, and they render as
  static `pill pill-count` labels — no `tag-chip` edge, role, tab stop,
  `aria-pressed` or click handler, per Codex's review and
  `spec/ui_elements.md` "Label or control". `data-locked-on` carries the
  selection, and `selectedPills` and the Save stager both read it. The
  tooltip names the slot: "Always shown — pinned first" (Name) / "pinned
  second" (Email).
- **The author's ruling:** individually scoped, Name and Email are both
  always shown; group-scoped, Email is not. The reviewer surface already
  agrees (a group row is a tag line plus member names,
  `_group_collapse.py`), so `refreshPillStates` switches Email off in
  grouped mode, with a "Not shown on group rows" tooltip, and back on in
  Individual.
- **Reads (4):** the first found grouped mode stranding Email unselected
  behind the lock (the static label retires it); the second, the
  chip-edge scan reading only the attributes before the marker; the last
  two, test gaps only. Chromium checked each step.

### Entry 3 — Band 2's visibility preview went stale on a Band 3 edit

- **Defect** (the author, 2026-09-25). Band 2's "Who can see what you
  wrote" card is rendered once from saved policy rows. A Band 3
  Visibility cycle wrote only a hidden input, and neither Save (a fetch)
  nor Lock reloads, so the card kept the old modes until a reload.
- **Fix** (#2610). Each row carries its `audience`, each mode cell a
  `data-new-model-vp-preview-cell` key, and `newModelCycleVisibilityCell`
  repaints the matching cell with the same labels; a test pins the page's
  and the server's label maps equal. Cancel's reload restores it;
  Observers aren't on the card. Chromium: You / Reviewees cycles repaint
  and dirty the card; Observers and other cards are untouched. Its read
  found no defect.
- **Found alongside:** `spec/visibility_policy.md` describes the reviewer
  card as three rows labeled "Summarized responses"; the code renders two
  labeled "Anonymized summaries". A Doc impact bullet.

### Blast radius (measured)

Taken 2026-09-24 at `48b21d05`: entry 1 — one listener pair in
`instruments_index.html` (`grep -n "addEventListener('change', markDirty" …`).

Taken 2026-09-24 at `eb4bdf23`: entry 2 — the display-pill markup, its
toggle, `refreshPillStates` and the two selection readers in
`instruments_index.html`; the Band 2 field dict; 2 locked sources
(`grep -n "_LOCKED_DISPLAY_SOURCES" app/services/instruments/_display_fields.py`).

Taken 2026-09-25 at `65f0595b`: entry 3 — the card's mode cells and
`newModelCycleVisibilityCell`; `build_reviewer_visibility_rows`, 2
callers (`grep -rn "build_reviewer_visibility_rows(" app/`).

### Definition of done

- Every entry has its fix merged and a test that fails without it.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19T.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- None.

### Status

**Closed 2026-09-25** on the author's instruction, with three entries
(#2605, #2609, #2610 and this close). Each has a test that fails without
its fix. **Reads: six**, one per code push after the first: entry 1's
found nothing; entry 2's four found a stranded Email in grouped mode, a
chip-edge scan that could not see `data-locked`, and two test gaps;
entry 3's found stale prose and a label-map gap. Codex found entry 2's
locked pills still presented as controls, and entry 3's item over its
line budget. **Scope that moved:** the author's ruling split Email by
instrument scope, and entry 3 found `spec/visibility_policy.md`'s reviewer
card stale. Browser checks are owed in
`guide/post_azure_todo_checklist.md` item 6.

### Doc impact

- `spec/instruments.md` — Save-when-dirty: the Delete confirm checkbox
  doesn't count as an edit (Item 3, entry 1); the Name and Email pills
  render as static labels, always selected (Item 3, entry 2).
- `spec/ui_elements.md` — "Label or control": `.tag-chip` covers every
  clickable Band 2 pill, not the locked Name / Email labels (Item 3,
  entry 2).
- `spec/visibility_policy.md` — the "Band 2 preview" row: the card
  repaints live from Band 3's Visibility cycle; the reviewer-surface
  card row: two rows (You / Reviewees), and `summarized` reads
  "Anonymized summaries" (Item 3, entry 3).
- `docs/status.md` — row when the item closes (Item 3).


---

## Item 4 — A full-size sample roster download

**Logged 2026-09-25 on the author's instruction.**

### Opportunity

The Guide's only sample data is the six-student demo session. The author
had a 154-person roster generated earlier to exercise the app at a real
class size, but it was never kept in the repo.

### Decision (author, 2026-09-25)

- **A second download beside the demo**, not a replacement: "download the
  full-size sample rosters" in the Guide's Sample session card, served at
  `/templates/full.zip`.
- **Two files**, `reviewers.csv` and `reviewees.csv`: the same 154 people
  in each, `operator@example.edu` among them.
- **Tags:** Tutor (mock names), Group (`TW01`–`TW11`), Team (`Team 1`–
  `Team 33`), labelled on all three columns. Only reviewees carry a
  photo link, a placeholder on `example.edu`.
- **No relationships, observers or rule, and no pairing guidance** in the
  Guide. A session built from them pairs everyone with everyone until the
  operator sets a rule.

**Rejected:** replacing the demo. Its walkthrough and round-trip test
depend on a six-person session, and Full Matrix on 154 people is 23,716
assignments.

### Semantics

- **Generated, not stored**, like the other two sets
  (`app/services/setup_templates.py`): the headers are the extracts' own
  tuples, and the rows come from fixed name lists with no randomness, so
  the file is the same on every request.
- **Eleven groups of fourteen**, each split into teams of 5 / 5 / 4.
  Teams are numbered across the class, so a team names its group. Six
  tutors each take two groups, except the last, who takes one.
- **Each set now brings its own labels** (`TemplateSet.labels`, default
  `LABELS`). The starter and demo sets keep Tag 3 bare, as before.

### Blast radius (measured)

Taken 2026-09-25 at `39122e06`:
- `app/services/setup_templates.py` (the set) and
  `app/web/routes_templates.py` (one route);
- `app/web/templates/guide.html`, one paragraph in the Sample session
  card;
- `tests/unit/test_setup_templates.py`: three set-wide tests assumed
  every set had four files and the shared labels;
  `tests/integration/test_setup_template_download.py`: new route, parse
  and Guide tests.

### Definition of done

- The download parses with no issues: 154 rows per file, and three
  labels captured.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19T.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- None.

### Status

**Closed 2026-09-25** on the author's instruction (#2613 and this close),
as decided. One `diff-reviewer` read found no functional defect: stale
set-count prose, an overclaim about the operator row (it is the default
`FAKE_AUTH_EMAIL`, so it stands in for the operator only under local
fake auth), two specs missing from Doc impact, and two test gaps, all
fixed. Codex found nothing. The Quick Setup upload is owed on the dev
slot (`guide/post_azure_todo_checklist.md` item 6).

### Doc impact

- `spec/csv_contracts.md` — §5a: a third set, the full-size rosters, and
  its route; §6's surface mapping gains the Guide's full download
  (Item 4).
- `spec/operator_ui_concept.md` — the "Sample session card" paragraph
  offers the full download beside the demo (Item 4).
- `docs/status.md` — row when the item closes (Item 4).

---

## Item 5 — The roster CSV column `PhotoLink` becomes `ProfileLink`

**Logged 2026-09-25 on the author's instruction.**

### Opportunity

The link column is `profile_link` in the schema and "Profile" / "Profile
link" on every screen, but the roster CSV header still reads `PhotoLink`,
the one name that assumes the link is a photo.

### Decision (author, 2026-09-25)

- **Exports and templates write `ProfileLink`**, on both rosters and in the
  entity-stats extract.
- **The importer accepts both names, indefinitely**, so operators' files
  and bundles exported before the rename still import. A non-blank
  `ProfileLink` wins when a file carries both.
- **The sample data follows**: the full-size set writes `ProfileLink`, and
  its placeholder links move from `/photos/<name>.jpg` to
  `/profiles/<name>`.

**Rejected:** a cutoff for `PhotoLink`. Reading it costs one line; refusing
it would break old files for no gain.

### Semantics

- No schema change and no migration: only the header name moves.
- **The one break is outside the app**: anything reading an exported CSV
  by the `PhotoLink` header, such as a spreadsheet formula or a script.
- Found alongside: `_CSV_COL_TO_SOURCE` and `display_source_presence` have
  no live callers. They are renamed rather than deleted, which is out of
  scope here.

### Blast radius (measured)

Taken 2026-09-25 at `10ddf970` (`grep -rn "PhotoLink" app/`, 13 lines, 8
files):
- the importer (`csv_imports.py`, 2 reads) and three extract headers;
- the setup templates, `_CSV_COL_TO_SOURCE`, the coverage list, and the
  Reviewees upload card's column help;
- 8 test files, 16 lines; 5 specs.

### Definition of done

- A test pins the legacy header importing, and one pins `ProfileLink`
  winning over it.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19T.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- None.

### Status

**Closed 2026-09-25** on the author's instruction (#2615 and this close),
as decided. One `diff-reviewer` read found no defect: every roster
import path (Setup, Quick Setup, rehydrate) runs through the two parsers
and gets the fallback. It found the Reviewers upload card never listing
the link column, though the importer read it (now listed), plus stale
test names and line references (fixed). Codex found nothing.

### Doc impact

- `spec/csv_contracts.md` — §2.1 / §2.2 headers, §3.1's optional
  columns (with the legacy alias), and §5a's sample set (Item 5).
- `spec/rehydrate.md` — the roster header lines (Item 5).
- `spec/setup_pages.md` — both upload cards' optional columns: Reviewees
  renamed, Reviewers now listing `ProfileLink` (Item 5).
- `spec/rrw_functional_spec.md` — the roster CSV headers (Item 5).
- `docs/status.md` — row when the item closes (Item 5).

---

## Item 6 — Small fixes register, second batch

**Opened 2026-09-25 on the author's instruction**, with Item 3's shape: one
entry per defect, each with its own PR, test and `diff-reviewer` read. It
closes when the author says.

### Entry 1 — the Required pill doesn't name its marker

- **Defect** (the author, 2026-09-25). Required response fields carry a
  `*` on their column header, but the pill counting them reads "Required
  items completed", so nothing ties the two together.
- **Fix.** The pill reads "*Required items completed" in all three places
  it renders: Band 2's preview (the server render and the JS rebuild) and
  the reviewer surface, which the operator's reviewer preview shares.
  "All items completed" is unchanged.

### Entry 2 — a fractional step on an Integer field shows as 0

- **Defect** (the author, 2026-09-25). An Integer field saved with Step
  0.5 shows "(1-5, steps of 0)" above the reviewer table. The
  `validation` block casts its bounds with `int`, so 0.5 becomes 0, and
  the reviewer can enter only whole numbers anyway. Found alongside: a
  Decimal field's summary rounds to one place, so a step of 0.25 reads
  "0.2" and a max of 4.75 reads "4.8".
- **The author's ruling:** reject it. ✓ and Save refuse an Integer field
  whose Min, Max or Step is not a whole number, and name Decimal as the
  type for steps like 0.5. Decimal summaries print their bounds as
  entered.
- **Fix.** `_integer_bounds_error` in `_band2.py` refuses the save (422,
  naming the field), and `newModelRfValidateShape` gates ✓ with the same
  words, checked after the existing rules on both sides. One exemption,
  on both sides: a stored field with responses and unchanged bounds,
  since those bounds are locked and refusing them would block every Save
  of the card. A stored field without responses meets the rule on its
  next Save. The two summary helpers in `views/_instruments.py` print
  Decimal bounds through `_format_band2_bound`, unrounded and without a
  trailing `.0` or scientific notation: "1-5, steps of 0.5", "0-1, steps
  of 0.25", as the Band 2 preview already did.
- **Not covered:** a Settings CSV import writes bounds without any shape
  check (Max below Min passes too); that predates 19T.

### Blast radius (measured)

Taken 2026-09-25 at `ed0ce1a6`: entry 1 — 3 renders of the pill
(`grep -rn "Required items completed" app/web/templates`), 4 test
assertions in 2 files (`grep -rn "Required items completed" tests/`), 2
lines of `spec/reviewer-surface.md`.

Taken 2026-09-25 at `3a7bf069`: entry 2 — 1 server validator and its
client mirror, 5 hits
(`grep -rn --include=*.py --include=*.html "_validate_response_field_shape\|newModelRfValidateShape(" app/`);
2 summary helpers (`grep -n "steps of" app/web/views/_instruments.py`);
their tests in 2 files (`grep -rln --include=*.py "steps of" tests/`).

### Definition of done

- Every entry has its fix merged and a test that fails without it.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19T.6` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- None.

### Status

**Closed 2026-09-25** on the author's instruction, with two entries
(#2620, #2621 and this close). Each has a test that fails without its fix.
**Reads: three**, one on entry 1 and two on entry 2. Entry 1's found no
code defect, only plan gaps. Entry 2's first narrowed the server's
exemption to fields with responses, aligned the check order and kept small
steps out of scientific notation. The second extended Codex's non-finite
refusal, a 500 on "nan" or "inf", from Integer and Decimal to every type:
a String Min of "nan" crashed from the UI too. **Scope that moved:** the
non-finite refusal, which the ruling didn't name. **Owed:** the Guide's
`instrument-card-preview` capture shows the pill without its `*`; the
author retakes it with `guide/advanced_instruments.md` Items 4–5's
captures. Browser checks are in `guide/post_azure_todo_checklist.md`
item 6.

### Doc impact

- `spec/reviewer-surface.md` — "Above the table" and "Visible progress":
  the pill reads `*Required items completed`, echoing the header marker
  (Item 6, entry 1).
- `spec/instruments.md` — "Inline bounds": an Integer field takes
  whole-number Min, Max and Step, except a stored field with responses
  whose bounds are unchanged; on every type a non-finite bound ("nan",
  "inf") is refused as not a number (Item 6, entry 2).
- `spec/reviewer-surface.md` — the constraint line and placeholder print
  Decimal bounds as entered (Item 6, entry 2).
- `docs/status.md` — row when the item closes (Item 6).

---

## Item 7 — Visibility edited in Band 2's card

**Opened 2026-09-26 on the author's instruction**: `guide/advanced_instruments.md`
Item 4, built ahead of its Item 3 because it doesn't touch the pills. The
design record holds the rulings. This block holds the build.

### Opportunity

Visibility is set in Band 3's table and previewed in Band 2's "Who can see
what you wrote (other than admin)" card. That is one setting in two places,
which 19T Item 3 entry 3 had to patch with a live repaint.

### Decision (the author, 2026-09-25, taking the recommendations)

The card is both the preview and the editor. **Locked**, it is the
reviewer's card. **Unlocked**, the cells that can change are cycle chips,
the fixed cells stay labels, and the rows read "You (reviewer)",
"Reviewees" and, below a thin divider, "Observers", with the note
"Observers are shown here for setup only; reviewers don't see this row."
Band 3's Visibility table retires. **Rejected:** keeping Band 3's table with
the repaint (one setting in two places), and Observers on the locked card
(no longer the reviewer's view).

**Band 3 keeps its `2fr 3fr` split for now** (the author, 2026-09-26). Its
left column stays empty until Item 5's display-field table fills it, and
the `1fr 2fr` re-split waits for Item 5.

### Semantics

- **No server change.** The six hidden inputs keep `form="dfsave-<id>"` and
  move into the card, and `/save` reads them wherever they sit.
- **The lock swap is the description box's.** The editor is
  `data-unlock-only` and the reviewer's table `data-lock-only`, so a locked
  card shows no Observers row and no chips.
- ~~**Entry 3's repaint retires**, because the card is now the editor.~~
  **It stays** (build, 2026-09-26): the locked table is separate markup,
  rendered once from saved state, and Save doesn't reload, so without the
  repaint a Save then Lock would show the old modes. A cycle writes its
  hidden input, repaints the locked table's cell, and dirties the card
  through the existing card-wide click listener. Cancel's reload restores
  the saved modes.
- **The cycle sets don't change:** You (reviewer) is fixed at Raw while the
  session runs, and after release cycles —, Raw, Anonymized summaries.
  Reviewees are fixed at — while it runs, and cycle all four after release.
  Observers cycle — and Anonymized summaries while it runs, and all four
  after release.

### Blast radius (measured)

Taken 2026-09-26 at `13ba5ec4`:
- 38 template lines name the editor
  (`grep -c 'data-new-model-vp-\|newModelCycleVisibilityCell\|b3_mode_cycle\|b3_static_pill' app/web/templates/operator/instruments_index.html`);
- 4 test files
  (`grep -rln --include=*.py 'data-new-model-vp-\|newModelCycleVisibilityCell\|b3_mode_cycle\|b3_static_pill\|Who can see what you wrote' tests/`);
- 4 specs name Band 3's editor or the card
  (`grep -rln "Who can see what you wrote\|Band 3.*Visibility\|Visibility.*Band 3" spec/`);
- the Guide's visibility paragraph and two instrument captures
  (`grep -n -i "visibility" app/web/templates/guide.html`).

### PR ladder

1. **Scaffold** (this rung): the plan, and the unlocked card's layout with
   labels in place of chips. Band 3's table stays the working editor.
2. **Wire:** the chips and hidden inputs in the card, and Band 3's table
   ~~, entry 3's repaint~~ and the scaffold labels removed (the repaint
   stays; see Semantics). The Guide paragraph is
   updated. This is the item's last build rung, so the item's one
   `diff-reviewer` read happens here, over the cumulative diff from
   `13ba5ec4`.
3. **Close.**

### Definition of done

- A locked card shows the reviewer's two rows. An unlocked card cycles the
  four live cells, and Save persists them.
- Band 3 has no Visibility table, and the card holds the only
  `data-new-model-vp-form`.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19T.7` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- None.

### Status

**Closed 2026-09-26** on the author's instruction (#2623 scaffold, #2624
wire, and this close). The ladder ran as planned, with two changes:
- **Entry 3's repaint stays** (Semantics): the locked table is separate
  markup, and Save doesn't reload it.
- **Codex's one finding on #2623**, the Observers divider as an inline
  style, rode rung 2 on the author's instruction. It became `row-group-start`
  in `base.html`.

**The close's `spec-writer` pass** found four more specs naming Band 3's
editor beyond the planned five; they are in Doc impact and fixed here.

**Reads: one**, the item's cumulative read over `13ba5ec4..HEAD`. It found
no regression in Save, lock, Cancel or the dirty tracker, and the editor
keeps Band 3's guard (an inert lock region unless editing). Rung 2 fixed
what it found:
- the sys-admin audit card sent operators to "Band 3's editor";
- two assertions passed on unrelated page text;
- the hidden inputs rendered only when the reviewer's rows existed;
- the Guide paragraph sat under the wrong figure.

**Found, not fixed:** the cycle chips don't answer Enter or Space, and each
chip is announced only by its mode. Both gaps predate the move. **Owed:**
browser checks in `guide/post_azure_todo_checklist.md` item 6, and the
author's retake of the Guide's two instrument captures.

### Doc impact

- `spec/instruments.md` — Band 2's card is the visibility editor when
  unlocked, and Band 3's "Visibility + Response fields" loses its
  Visibility half (Item 7).
- `spec/visibility_policy.md` — the Band 3 editor and Band 2 preview rows
  become one card (Item 7).
- `spec/operator_ui_concept.md` — the visibility grid audit's "Band 3
  editor" becomes the instrument card's visibility editor (Item 7).
- `spec/permissions.md` — the same wording in the sys-admin row (Item 7).
- `spec/ui_elements.md` — §10: `row-group-start`, the heavier rule above a
  row that starts a new group (Item 7).
- `guide/advanced_instruments.md` — Item 4 points to this item as built
  (Item 7).
- `spec/rrw_functional_spec.md` — §9.6's Band 2 / Band 3 summary and
  §5.16's default note move the visibility editor to the card (Item 7;
  found by the close's `spec-writer` pass).
- `spec/rehydrate.md` — the import's validation table is the visibility
  editor's, not "the Band 3 editor's" (Item 7; the same pass).
- `spec/roundtrip_coverage.md` — "the Band 3 grid" becomes the visibility
  grid (Item 7; the same pass).
- `docs/status.md` — row when the item closes (Item 7).

---

## Item 8 — Display fields as a Band 3 table

**Opened 2026-09-26 on the author's instruction**: `guide/advanced_instruments.md`
Item 5, straight after Item 7 into the column it freed. The design record
holds the rulings and semantics. This block holds the build.

### Opportunity

Display fields are chosen with Band 2's pills and ordered by dragging them.
Item 7 left Band 3's left column empty beside Response fields.

### Decision (the author, 2026-09-25 and 2026-09-26)

**A headerless table in Band 3's left column**, one row per display field:
an Active checkbox, the field's session-wide label, and up / down buttons.
Name and Email have a checkbox that shows their state and can't be changed,
and no arrows. Changes show in Band 2's preview at once and persist only
through the card's Save. Band 2's display pills retire once the table
works. **Band 3 keeps its `2fr 3fr` split for now** (the author,
2026-09-26); the design record's `1fr 2fr` re-split is deferred.
*(Rung 4 made it `1fr 2fr` on the author's later ruling; see `Status`.)*
**Rejected:** pills above Response fields in Band 3 (the design record's
first draft, superseded by the column Item 7 freed).

### Semantics

The design record's Item 5 "Semantics" apply unchanged. For this rung: the
rows follow `_band2.fields`, the pills' own order and source. On a
group-scoped instrument (`group_kind` set), the fields a group row can't
show render unticked, Email included.

### Blast radius (measured)

Taken 2026-09-26 at `20f8eb3a`:
- 28 template lines read the display pills
  (`grep -c 'data-locked\|data-display-field-id\|selectedPills\|refreshPillStates\|newModelBand2Drag' app/web/templates/operator/instruments_index.html`);
- 2 test files name the Band 2 pills
  (`grep -rln --include=*.py "data-new-model-band2-pill\|data-locked" tests/`);
- the specs the design record names: `spec/instruments.md` and
  `spec/ui_elements.md`;
- the Guide's pill sentence and instrument captures.

### PR ladder

1. **Scaffold** (this rung): the plan, and the table with every control
   disabled. Band 2's pills stay the working editor.
2. **Wire:** checkboxes and arrows live, repainting the preview and
   dirtying the card, with Save persisting through the existing display
   order and selection.
3. **Retire** Band 2's display pills; the item's cumulative
   `diff-reviewer` read runs here, from the main commit rung 1 was cut
   from.
4. ~~**Close.**~~ Became the author's adjustments (`Status`); the close
   is rung 5.

### Definition of done

- Band 3's table sets display-field order and selection, live in the
  preview and saved by Save, and Band 2 has no display pills.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19T.8` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- **Open at close, the author's to decide:** should the reviewer's own "Who
  can see what you wrote" card show its modes as pills too, as the
  operator's locked card does since rung 4? Until then the two differ in
  style only; `spec/visibility_policy.md` records the difference.

### Status

**Closed 2026-09-26** on the author's instruction (#2626 scaffold, #2627
wire, #2628 retire, #2629 adjustments, and this close). The ladder ran as
planned, plus one rung:
- **Rung 2 wired the table onto the pills**, which stayed the model until
  rung 3 retired them. The rows are now the model: order is display order,
  a checkbox is selection, each row carries the field's data, and every
  former pill reader (preview, group-mode refresh, widths, the Save
  stager, the order stager, the sample refresh) reads them through
  `dfRows`. Band 2 keeps only the response pills.
- **Rung 4, the author's adjustments** before the close: the locked
  Visibility card shows its modes as display-only pills, the display-field
  table is compact (`table-compact`) with display-only name pills, and
  Band 3 re-splits to one third / two thirds, which the Decision had
  deferred. The left track is `minmax(0, 1fr)`, so a long label scrolls
  in its column (Codex, #2629).

**Reads: two.** The item's cumulative read (rung 3, over
`323c5157..HEAD`) found no correctness defect; rung 3 fixed the untested
server-rendered tick, the Guide still naming the pills, dead code, the
empty-state count and inline styles. Rung 4 reopened `app/` and took its
own: no defect; it tightened the pill test and raised the open question
above. **Codex** found two more: the Guide saying Email always shows, and
the unshrinkable grid track. Both fixed.

**Owed:** browser checks in `guide/post_azure_todo_checklist.md` item 6,
and the author's retake of the Guide's instrument captures and their alt
text.

### Doc impact

- `spec/instruments.md` — Band 3's left column holds the display-field
  table, and Band 2's chip row loses its display pills (Item 8).
- `spec/ui_elements.md` — "Label or control": the locked Name / Email
  pills give way to the table's disabled checkboxes (Item 8).
- `spec/instruments.md` — also Band 3's `1fr 2fr` split, the compact
  display-field rows with display-only name pills, and the locked
  Visibility table's mode pills (Item 8).
- `spec/ui_elements.md` — also the `table-compact` class (Item 8).
- `spec/visibility_policy.md` — the operator's locked card shows the
  reviewer's rows as mode pills, where the reviewer's card is plain text
  (Item 8).
- `guide/advanced_instruments.md` — Item 5 and the header point to this
  item as the build (Item 8).
- `app/web/templates/guide.html` — the preview paragraph sends display
  fields to the table; the author retakes the instrument captures, and
  their alt text follows the retake (Item 8).
- `spec/instruments.md` — also the tooltips: "Always shown — pinned first"
  and "Not shown on group rows", without the field name (Item 8).
- `docs/status.md` — row when the item closes (Item 8).

## Item 9 — Response fields as a Band 3 table; the response pills retire

**Opened 2026-09-26 on the author's instruction**: `guide/advanced_instruments.md`
Item 3, after Item 8. The design record holds the 2026-09-24 rulings and
the semantics. This block holds the build and the author's 2026-09-26
layout rulings, reached over five mock-ups.

### Opportunity

Band 2's response pills duplicate the Band 3 rows: each carries the
field's on/off, its order, the preview column's label, width and help
text, the R / ≡ mirrors, the shape ✓ pushed, and the response count
behind the "hide this field?" confirm. Save already reads row order (Item
1). Branching (design record Item 1) would have to keep the two in step.

### Decision (the author, 2026-09-24 and 2026-09-26)

The design record's Decision stands, with the 2026-09-26 layout rulings:
- **Response fields become a table**, like Item 8's display-field table
  but taller: one `<tbody>` per field with a 1px rule under it and no rule
  inside it, so a branch (design record Item 1) can later join its
  parent's `<tbody>` as one ruled group.
- **Each row reads:** Active checkbox, +, an empty ⑂ column, name, type,
  bounds, R, ≡, ▲, ▼, X. The ⑂ column is held now so branching doesn't
  shift the row. Its button and the rest of the branch layout are design
  record Item 1's, where the 2026-09-26 mock-ups are recorded: a governed
  row puts its checkbox in the + column and its + in the ⑂ column, so
  **every row aligns from the name onward**, parent and governed alike.
- **▲ ▼ are full-size square buttons**, ▲ then ▼, like the row's other
  buttons, not the record's half-height stack; the right column has room.
- **The Active checkbox** is bound to `visible`; unticking a field with
  responses keeps today's confirm; an inactive row is not dimmed.
- **✓ and the response pills retire.** The preview reads the rows.

**Rejected:** a rule under each flex row. It draws the lines, but a
branch needs rows grouped under one rule, and a table lines the name and
bound boxes up in columns.

### Semantics

The design record's Item 3 "Semantics" apply. For the table (since rung
5): a field is a `<tr data-new-model-rf-row>`, which carries its state,
inside a group `<tbody data-new-model-rf-group>`; the "+" template clones
a group. See "Pre-positioning", point 1.

### Pre-positioning for Items 1 and 2 (the author, 2026-09-26)

Built so branching (design record Item 1) and required governed fields
(Item 2) add to this item rather than rework it:
1. **A group is a `<tbody data-new-model-rf-group>` and a field is its
   `<tr data-new-model-rf-row>`**, which carries the field's state (rung 5;
   rungs 1–4 put the state on the `<tbody>`). A branch adds its governed
   `<tr>`s to its parent's group, and the rule under the group separates
   groups, not fields.
2. **The ⑂ column is held** just after + (rung 1), so a governed row can
   shift one column and still align from the name onward.
3. **▲ ▼ move a group**, not a row (rung 3; by group since rung 5), and "+"
   inserts a new group after the pressed row's: a parent will carry its
   branch unchanged. Moving a governed `<tr>` within its group is Item 1's.
4. **One reader for field state**, `rfRows(card)` (rung 2), as `dfRows` is
   for display fields: the preview, the stager, the widths, the help
   cards and the counts read rows through it, in document order. The
   structural handlers (▲ ▼, X, "+", the recompute's arrow and X states)
   work on groups (`newModelRfGroupSibling`). Item 1 adds a row's parent
   to the state rows carry.
5. **Active and R states computed in one place**, the row recompute
   (`newModelRfRecomputeActionStates`), per row (rungs 2–3): Item 1 makes
   R inactive inside a branch and cascades a parent's Active there, and
   Item 2 lifts the R rule there.
6. **The stager sends rows in row order** (rung 3). It does not send row
   keys, and `set_band2_state` would drop them: Item 1 adds a row key and
   a parent reference to the payload and the service, so a branch can
   name a parent the same Save creates.
The record's service-layer pre-positioning for Item 2 (one branch-open
function, the applicable-fields helper) belongs to Item 1's build.

### Blast radius (measured)

Taken 2026-09-26 at `134953aa`:
- `app/web/templates/operator/instruments_index.html`: 29 lines name a
  row (`grep -c 'data-new-model-rf-row'`), 26 a response pill
  (`grep -c 'data-new-model-band2-pill'`), 8 ✓
  (`grep -c 'newModelRfSaveRow\|data-new-model-rf-save'`);
- 2 test files name the rows, the pills or ✓
  (`grep -rln --include=*.py "data-new-model-rf-row\|data-new-model-band2-pill\|data-new-model-rf-save\|newModelRfSaveRow" tests/`);
- the specs: `spec/instruments.md`, `spec/operator_button_audit.md`,
  `spec/ui_elements.md`;
- the Guide's instrument captures and preview paragraph.

### PR ladder

1. **Scaffold** (this rung): the plan, and the rows as the table, with
   the Active checkbox and ▲ ▼ rendered but disabled, and the ⑂ column
   empty. The pills and ✓ stay the working editor.
2. **Rows carry the pill state** (label, width, help text, response
   count, `visible`) and the preview reads them. No visible change.
3. **Wire** the Active checkbox and ▲ ▼: live in the preview, staged for
   Save, the confirm on a field with responses.
4. **Retire** the response pills and ✓; the item's cumulative
   `diff-reviewer` read runs here, from `134953aa`.
5. ~~**Close.**~~ Became acting on the read, since rung 4 merged first.
6. Default labels (the author's ruling); the close is rung 7, after the
   author's on-screen check.

### Definition of done

- Band 3's response-field table sets order and on/off, live in the
  preview and saved by Save; Band 2 has no pills and the rows no ✓.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19T.9` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- ~~Item 8's display-field arrows as short outlined buttons?~~ **Yes**
  (the author, 2026-09-26): `btn secondary btn-short`, built in rung 3.

### Status

**Open.** Rung 1 is this PR: the plan, the author's branching layout in
the design record's Item 1, and the table. It also rewords Band 2's
header comment, which still described display-field chips (flagged by
Item 8's close pass). Rung 1 is #2631.

**Rung 2 moves the pill state onto the rows.** A row carries its field's
committed state: `data-committed` (saved or ✓'d), `data-selected`, the
name and shape last ✓'d (`data-label`, `data-rf-*`), width, help text and
response count; R and ≡ are read off the row's buttons. Every reader goes
through `rfRows`: the preview's selection, help cards, constraints and
progress counts, the width writer and collector, the stager, the pill
click's confirm, and Save's re-commit. ✓ commits a row
(`newModelRfCommitRow`, was `newModelRfSyncPill`), and its comparison is
the row against its own committed state
(`newModelRfRowDiffersFromCommitted`). The pills are a control that
mirrors its row, carrying only what the click and drag read. Rung 2 is
#2632.

**Rung 3 wires the Active checkbox and ▲ ▼.** The checkbox and the pill
share one setter (`rfSetSelected`), with the "hide this field?" confirm;
cancelling puts the tick back. Before a row's first ✓ its checkbox is
ticked and fixed, since ✓ adds the field selected. ▲ ▼ move the row's
`<tbody>`, then the pills follow the rows and the order is staged; a pill
drag re-runs the recompute, which owns both controls' states. **On the
author's ruling** the display-field table's ▲ ▼ became outlined buttons
too, in a short size (`btn-short`, `base.html`: 19px inside the 32px
rows). Codex (#2633): a named row never ✓'d was saved hidden but kept a
ticked, fixed Active checkbox until a reload; Save now commits every
named row as saved, so it shows unticked at once. Rung 3 is #2633.

**Rung 4 retires the response pills and ✓.** Band 2 loses its chip row
and the drag handlers. A row commits by itself (`newModelRfMaybeCommit`,
on every keystroke and type change) whenever its live name and shape are
valid and differ from what it last committed, so a half-typed bound never
reaches the preview. An invalid row keeps its last committed shape in the
preview and is marked amber, with the reason as its tooltip. A new row
starts selected, its Active checkbox live. The "hide this field?" confirm
now points to Active. **Found at build:** the marker's amber left edge had
not drawn since rung 1, because a `<tbody>` draws no box-shadow; it now
sits on the row's cells. The in-app Guide's two instrument paragraphs
describe the tables, not the pills and ✓. Rung 4 is #2634, merged before
the item's read returned.

**Rung 5 acts on the item's read** (over `134953aa..HEAD`; no defect that
loses or corrupts saved data):
- **The field moves to a `<tr>`** inside a group `<tbody>`, as
  pre-positioning point 1 now says; the read found the state on the
  `<tbody>` would have made Item 1 move it across every reader.
- Points 4 and 6 overclaimed and are reworded to what the code does.
- A cancelled "hide this field?" confirm no longer marks the card dirty
  (the card's dirty listener skips the Active checkbox; its setter stages).
- A Quick fill preset's passing `preset:` value is never committed.
- The marker's tooltip says what the preview shows meanwhile.
- A new row the client finds invalid but the server accepts stays
  uncommitted after Save instead of committing the rejected text.
- ▲ ▼ keep focus on a live arrow; dead help-edit-mode code, the rows'
  inline button padding and stale comments (and `_band2.py`'s docstring)
  go; stale test names and a vacuous test loop are fixed.

Rung 5 is #2635.

**Rung 6: on the author's ruling, every added response field gets a
default label**, the next "Field N" no row uses (`newModelRfDefaultLabel`).
Clearing a name puts the row's default back, whether the box loses focus
or Save runs first (`newModelRfSaveName`, which reads it without writing
the page; the box restores on `blur`, since a typed-then-deleted name fires
no `change`), so Save never drops a field for
want of a name: only X deletes. "+" commits the new field at once, its
name selected. A saved field's cleared name gets the next free "Field N";
a stored default another row has since taken is replaced. This replaces
rung 5's handling of a row saved with its name cleared. The rung's read
found three more, fixed in the rung:
- a labelled starter row on a card with no fields was saved as a field
  nobody wrote, and met the setup gates; it is a blank, unlabelled
  placeholder again, not a field until the operator types in it;
- Save returned no ids, so a new field's next reload-free Save sent it
  id-less and recreated it under a new id and key (and lost its width);
  Save now returns `response_field_ids` in order, and the rows it sent
  take them;
- this Status block had folded rung 5's notes into rung 6.

Codex (#2636): Save's success handler committed the untouched placeholder
(an empty name passes shape validation), so the next Save stored it as a
"Field N"; it now skips any row Save did not send.

The author's follow-up rulings (in #2636): the default shows **muted, as
the empty box's placeholder**, until a name is typed, and clearing a name
always brings it back that way. Taking the default with → or Enter, or
typing it, makes it a typed name in normal style. The box stays empty, so
the row goes by its default everywhere a name is read
(`newModelRfSaveName`: the preview, the marker, the auto-commit and the
stager), and `newModelRfSyncDefaults` re-assigns defaults on each name
edit, committing any row whose default moved. This supersedes the
`blur` restore and the selected name above. A saved label reloads as a
typed name, since nothing records that it was a default. As before, a
new row lives only on the page (the card turns unsaved; Cancel drops it)
until a successful Save.

### Doc impact

- `spec/instruments.md` — Band 3's response-field table, the Active
  checkbox and ▲ ▼; the pills' per-field visibility section and the ✓ row
  retire (Item 9).
- `spec/operator_button_audit.md` — ✓ retires; the Active checkbox and
  ▲ ▼ join the row; the display-field arrows become Secondary (Item 9).
- `spec/ui_elements.md` — the response-field table's grouped rules
  (`rf-table`) and the short button size (`btn-short`) in §10, and §6's
  `.btn-icon` row, which no longer covers either table's ▲ ▼ (Item 9).
- `spec/instruments.md` — also the display-field table's ▲ ▼ as
  `btn secondary btn-short`, not `.btn-icon` (Item 9).
- `guide/advanced_instruments.md` — Item 3 and the header point to this
  item as the build, and record the 2026-09-26 layout rulings (Item 9).
- `app/web/templates/guide.html` — the preview paragraph; the author
  retakes the instrument captures (Item 9).
- `docs/status.md` — row when the item closes (Item 9).
