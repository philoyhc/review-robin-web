# Participant info

**Opened:** 2026-10-11 · **Theme:** what a participant is shown about
themselves, as the roster holds it · **Related:**
`spec/reviewer-surface.md`, `spec/setup_pages.md`,
`spec/settings_inventory.md`

A standalone plan at the author's naming, not a `segment_*.md`, in the
shape of `guide/profilelink_updates.md`: items close independently, each
with its own `### Doc impact` and `### Status`. `tools/close_check.py`
reads only `segment_*` files, so an item's `Doc impact` is checked by
hand at its close.

**Order** (author, 2026-10-11): reviewers first. Reviewees and observers
are later items, if the author asks for them.

---

## Item 1 — A reviewer sees their own roster entry

### Opportunity

A reviewer never sees the attributes the roster holds for them, beyond
the email they sign in with: not their name, their `ProfileLink`, or
their three tags. So a reviewer cannot check that what the operator
imported about them is right, though the operator's Reviewers page,
extract and Band 2 identity level all use it (author, 2026-10-11).

### Decision

The author's ruling, 2026-10-11:

- **Where it shows.** On the reviewer surface and its operator preview,
  inline after the `Reviewer` pill beneath the session name and
  deadline: the selected fields of the signed-in reviewer's own row.
  For a reviewer who holds other roles too, it follows the last role
  pill rather than splitting them (see Judgment calls).
- **What shows by default.** Name, email and profile. Tags can be
  shown but start off; a reviewer seeing their own tags is useful for
  checking them, not a default.
- **Where the operator chooses.** A half-width card in the Reviewers
  page's Unlock panel, **above `Upload Reviewers`** in the right
  column, headed **Reviewer information shown on surface**. Beneath
  the header, one selector chip per field that has data in the roster:
  Name, Email, Profile selected by default; Tag 1–3, under their
  friendly labels, unselected.
- **What the roster card reports** (author, 2026-10-11, answering the
  open question on locked sessions). The roster card's readout row, in
  every state, ends with **Shown on surface:** and a pill per selected
  field, on the same line as the others. The row's two labels shorten:
  `Reviewers roster:` → `Roster:`, `Populated columns:` → `Populated:`.
- **Amended** (author, 2026-10-12, on a mock-up): `Populated:` gives way
  to a muted `|`, so the column pills run on from the roster count, which
  reads `<Noun> (N)` like them (`Reviewers (3)`), on all four pages;
  `Shown on surface:` becomes **Reviewers see:**, and the card's heading
  **What reviewers see of their own entry**.

Stored once per session, as a list of field keys. Rejected: a
per-instrument setting (the line is in the page header, above every
instrument), and Band 2's identity level (that decides what *others*
see of a reviewer; this is what the reviewer sees of themselves).

### Semantics

- **Storage.** A nullable JSON list on the `sessions` table (the
  `ReviewSession` model) of keys from
  `name`, `email`, `profile_link`, `tag_1`–`tag_3`. `NULL` means the
  default, `name`, `email`, `profile_link`; an empty list shows nothing
  after the pill. **One migration for all three participants** (author,
  2026-10-12): it adds a column each for reviewers, reviewees and
  observers. Only the reviewers' is read and written in this item; the
  other two stay `NULL` until their items give them a control and a
  reader, and decide what `NULL` means for them.
- **Chips offered.** Name and Email always (both are required on
  import); Profile and each tag only while some reviewer row holds a
  value.
- **Saving the default records it.** A save is a no-op only when the
  stored list already equals the selection; with nothing stored, saving
  even the default writes it, so a later change to the default does not
  move the session. The audit event's old value is what was stored
  (`null` while unset).
- **Save keeps what it cannot show.** A selected key with no chip on
  offer, whether stored or from the `NULL` default, is carried through
  Save unchanged: the card posts it as a hidden input. So `profile_link`
  stays selected while no reviewer has a profile, and shows once one
  does; an operator removes a key only by deselecting its chip.
- **The readout.** `Reviewers see:` lists the selected fields by
  label (a tag under its friendly label), in roster order; with none
  selected it reads `none`, as the index's empty branch does.
- **The line.** Selected fields in roster order, separated as the
  header's other muted text is; a field empty on this reviewer's row is
  skipped. Profile follows `_partials/profile_value.html` (link, `•••`
  or nothing). A tag renders as `<label>: <value>`, the label being the
  slot's friendly label or its default.
- **Preview.** `preview_mode` suppresses the role chips today; the
  preview gains a static `Reviewer` pill and the line for the previewed
  reviewer, so the operator sees what that reviewer sees.
- **Gate.** The card lives in the Unlock panel, so it renders only while
  `is_editable` and no row is edited or added; its route answers 409
  otherwise, as `_save_field_labels` does. Locked, the readout row's
  `Reviewers see:` pills still say what the reviewer sees. A save never demotes a
  `validated` session: the setting is display-only.
- **Round trip.** The Settings CSV carries it as a `session.*` row;
  Duplicate copies it; an audit event records each change.

### Judgment calls — decided

- The two label renames land on all four roster pages, not only
  Reviewers: the readout row is one shape across them, and
  the roster-unlock tests pin its label (`Roster:`) and count pill on
  each page. `Reviewers see:` is Reviewers only.
  (Confirmed by the author, 2026-10-11.)

- The line sits on the role chips' row, after the last chip: with only
  the `Reviewer` role (the common case) that is just after its pill, and
  it never splits the role chips of a reviewer who is also a reviewee.
- The card saves with a Save / Cancel pair, disabled until a chip
  changes, as the tag-labels editor beside it does.
- With no column pills (Relationships with no pair-context tags) the
  readout row stops at the count: no `|`, and no `none yet` that would
  seem to describe the roster.
- The line's fields are joined by a muted ` · `: inline text with no
  separator would run a name into an email.
- The summary, `/results` and `/collation` headers are out: the author
  named the reviewer surface and its preview.

### Blast radius (measured)

Taken 2026-10-11 at `7e329db5`.

- Model and migration: `app/db/models/review_session.py` gains three
  nullable JSON columns, one per participant; one Alembic revision (89
  in `alembic/versions`).
- Readers: `app/web/templates/reviewer/review_surface.html` (the header,
  ~line 80, and the role-chips include, ~line 94),
  `app/web/routes_reviewer/_surface/_routes.py` and
  `app/web/routes_operator/_preview_surface.py` (the context).
- Card and route: `app/web/templates/operator/session_reviewers.html`
  (the Unlock panel's right stack, ~line 351) and a save route in
  `app/web/routes_operator/_setup_reviewers.py`, beside
  `/reviewers/field-labels`.
- Writers: `app/services/session_config_io/` (`_serialize.py`,
  `_apply_parse.py`, `_apply_session.py`), `app/services/session_clone.py`
  (~line 137), `app/services/audit.py` (`EVENT_SCHEMAS`).
- Readout labels: `grep -rln 'roster:</span>\|Populated columns' app/web/templates tests --include=*.html --include=*.py`
  → 6 (the four roster templates, `test_roster_unlock_panel.py`,
  `test_observers_unlock_panel.py`); `spec/setup_pages.md` names
  `Populated columns` once.
- Tests: `grep -rln "rs-role-nav" tests | wc -l` → 2;
  `grep -rln "preview_surface\|preview_mode" tests | wc -l` → 13.

### Status — closed 2026-10-12

Shipped as laddered, in three rungs (#2976 plan, #2978 scaffold, #2979
storage and the live card); the author's browser check passed
2026-10-12.

- **Diverged from the plan:** on a mock-up (2026-10-12) `Populated:`
  became a `|`, the count `<Noun> (N)` on all four pages, `Shown on
  surface:` became `Reviewers see:` (Decision amendment). With no column
  pill the row stops at the count (Judgment calls).
- **Built:** `app/services/participant_info.py` (keys, default,
  normalize, effective selection, the save and its
  `session.reviewer_self_fields_set` event); migration `c4a8e2f6d1b3`
  adds a JSON column per participant to `sessions`, only the
  reviewers' read; `POST /reviewers/self-fields` (409 locked, 422
  unknown key); the Settings CSV row (blank the default, `[]` nothing);
  Duplicate copies all three; `views.reviewer_self_card_context`
  answers the card and readout for the GET and the failed-import
  re-render alike.
- **Reads:** one cumulative `diff-reviewer` read on `f97e6219..`, two
  reads of its fixes, two of the readout revision and one of the Codex
  fix — six, all on rung 3. They found: the audit's old value must be
  what was stored; the no-op must compare with the stored list, so a
  save repairs a hand-edited value; a non-list stored value reads as the
  default; kept keys belong in `views`; stale `none yet` prose and an
  untested Relationships-with-tags row. Codex found the failed-import
  re-render rendering the card with no chips.
- **`spec-writer` at close:** no divergence; one edit, the
  `.rs-self-info` CSS bullet in `spec/reviewer-surface.md`.

### PR ladder

1. **This plan.** Prose only.
2. **Scaffold.** The card in the Unlock panel, inert: header, chips at
   their defaults, Save / Cancel disabled. The readout row's two renames
   on all four roster pages and its `Shown on surface:` pills at the
   default. The surface and preview line showing the default fields,
   which is what `NULL` will mean, so no page shows a choice it later
   ignores. Specs untouched until rung 3.
3. **Storage and the live card.** Column, migration, service and audit
   event, the save route, the Settings CSV row, Duplicate, the line
   reading the stored list, specs, a browser-check section. The item's
   last build rung: a `diff-reviewer` read on the cumulative diff from
   rung 2's base, and a `spec-writer` verify.

### Definition of done

- A reviewer's surface and its preview show the selected fields of that
  reviewer's own row after the role pills, by test; with nothing
  stored, name, email and profile; tags only when selected.
- The card offers a chip only for a field with data, keeps a selected
  key it cannot offer, saves the
  selection, and answers 409 on a locked session, by test.
- The selection round-trips through the Settings CSV and Duplicate, by
  test; Postgres CI runs the migration both ways.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

- None open. Locked sessions: the roster card's readout row shows the
  selection in every state (author, 2026-10-11; see Decision).

### Out of scope

- What reviewees and observers see of themselves: later items.
- Any change to what others see of a reviewer (Band 2's identity
  level, `guide/profilelink_updates.md` Item 2).

### Doc impact

- `spec/reviewer-surface.md` — the header line after the role pills, and the preview's static pill.
- `spec/setup_pages.md` — the Reviewers Unlock panel's new card above `Upload Reviewers`; the roster card's readout row (`Roster:`, the `<Noun> (N)` count, a `|`, the column pills) on all four pages and Reviewers' `Reviewers see:` readout.
- `spec/settings_inventory.md` — the new per-session setting, its default and its gate.
- `spec/csv_contracts.md` — the Settings CSV `session.*` row.
- `spec/roundtrip_coverage.md` — the new column round-trips.
- `guide/things_to_check_in_browser.md` — a section per code rung.

---

## Item 2 — The Unlock panels' card order

### Opportunity

On the Item 1 browser check (author, 2026-10-12) the Unlock panels'
column order no longer matched how an operator works through them, and
on Observers `Lock` sat under the left column, mid-card, rather than at
the card's corner.

### Decision

The author's ruling, 2026-10-12, on all four roster pages:

- **Reviewers.** Left: `What reviewers see of their own entry`, then
  `Upload Reviewers`. Right: tag labels, then `Danger Zone`.
- **Reviewees** follows Reviewers: left `Upload Reviewees`; right tag
  labels, then `Danger Zone`.
- **Relationships.** Left `Upload`; right tag labels (then `Danger
  Zone`).
- **Observers.** Left `Upload Observers`; right `Danger Zone`, under
  `What observers see` once a later item adds it.
- **`Lock` at the bottom right of the whole card**, on every page: a
  row of its own at the panel's foot, flush right.

Rejected: `Lock` beneath the right column's last card (19P.1's rule).
The right column now ends wherever its cards do — on an empty Observers
roster it holds none — so "under the column" is not the card's corner.

### Semantics

- `Upload` is left on all four pages, so Observers stops being the
  mirror of the other three, and `Lock` stops following a card: the
  toggle moves it to the panel's foot, never into a column, and the
  `data-lock-home` marker retires.
- Narrow (≤ 800px) the columns stack left then right, then `Lock`.
- The server-rendered open panel (`?unlocked=1`, a failed import)
  renders `Lock` in the same place the toggle puts it.

### Judgment calls — decided

- "Reviewees page to follow" read as *follows Reviewers' order*:
  Reviewees has no self card yet, so it is Upload left, labels over
  Danger Zone right.
- `Lock` at the foot on all four pages, not only Observers: after the
  reorder Reviewers' right column is the shorter one, so the old rule
  would leave `Lock` mid-card there too.

### Blast radius (measured)

Taken 2026-10-12 at `1fa68b24`.

- Templates: the four `app/web/templates/operator/session_*.html` roster
  pages and `base.html` (`.unlock-right > .roster-card-actions`):
  `grep -rln "unlock-right\|data-lock-home\|roster-card-actions" app/web/templates`
  → 5.
- Tests: `grep -rln "unlock-right\|data-lock-home\|unlock-stack\|roster-card-actions" tests --include=*.py`
  → 4.
- Spec: `spec/setup_pages.md` § *The roster card and the Unlock panel*
  (the column-contents and `Lock` rows) and § *Observers page*;
  `spec/ui_elements.md` (`.unlock-panel` row).

### PR ladder

1. **This plan**, with Item 1's close. Prose only.
2. **The reorder.** The four templates, the `Lock` row's CSS and
   toggle, tests, the two specs, a browser-check section. One rung,
   read on its own diff.

### Definition of done

- Each page's panel renders its cards in the Decision's order and
  `Lock` after both columns, by test, open on load and after the toggle.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

- None open.

### Out of scope

- `What reviewees see` and `What observers see`: later items, which
  place their cards by this Decision.

### Status

- Rung 2 (2026-10-12): the four templates reordered; `Lock` is the
  panel's last child, `.unlock-panel > .roster-card-actions` spanning
  both columns, and the toggle appends it to the panel;
  `data-lock-home` retired. `tests/integration/_unlock_panel.py` holds
  the one "Lock at the panel's foot" check the four pages share.
- Reads: two `diff-reviewer` reads and one `spec-writer` verify. The
  first read and the verify both
  found the old placement in four specs the plan had not named (they
  joined `Doc impact`) and stale comments in templates and tests; the
  read also had the shared check pin `Lock` as the panel's direct last
  child, and the scaffold test file reuse its div-balancer.
  The second read, of those fixes, found nothing new.

### Doc impact

- `spec/setup_pages.md` — the Unlock panel's column contents on all four pages and `Lock` at the panel's foot; Observers no longer the mirror.
- `spec/ui_elements.md` — the `.unlock-panel` row: the `Lock` row at the foot.
- `spec/operator_button_audit.md` — the rows naming a panel column (#39, #41, #43, #45, #178, #179, #269).
- `spec/visual_style_rrw.md` — the roster pages' arrangement example.
- `spec/rrw_functional_spec.md` — Observers' panel no longer mirrored.
- `spec/operator_ui_concept.md` — Observers' differences: no mirrored columns.
- `guide/things_to_check_in_browser.md` — a section for the reorder.
