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

Stored once per session, as a list of field keys. Rejected: a
per-instrument setting (the line is in the page header, above every
instrument), and Band 2's identity level (that decides what *others*
see of a reviewer; this is what the reviewer sees of themselves).

### Semantics

- **Storage.** A nullable JSON list on the `sessions` table (the
  `ReviewSession` model) of keys from
  `name`, `email`, `profile_link`, `tag_1`–`tag_3`. `NULL` means the
  default, `name`, `email`, `profile_link`; an empty list shows nothing
  after the pill.
- **Chips offered.** Name and Email always (both are required on
  import); Profile and each tag only while some reviewer row holds a
  value.
- **Save keeps what it cannot show.** A selected key with no chip on
  offer, whether stored or from the `NULL` default, is carried through
  Save unchanged: the card posts it as a hidden input. So `profile_link`
  stays selected while no reviewer has a profile, and shows once one
  does; an operator removes a key only by deselecting its chip.
- **The readout.** `Shown on surface:` lists the selected fields by
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
  `Shown on surface:` pills still say what the reviewer sees. A save never demotes a
  `validated` session: the setting is display-only.
- **Round trip.** The Settings CSV carries it as a `session.*` row;
  Duplicate copies it; an audit event records each change.

### Judgment calls — decided

- The two label renames land on all four roster pages, not only
  Reviewers: the readout row is one shape across them, and
  `tests/integration/test_roster_unlock_panel.py` pins its label as
  `{Noun} roster:` for all four. `Shown on surface:` is Reviewers only.
  (Confirmed by the author, 2026-10-11.)

- The line sits on the role chips' row, after the last chip: with only
  the `Reviewer` role (the common case) that is just after its pill, and
  it never splits the role chips of a reviewer who is also a reviewee.
- The card saves with a Save / Cancel pair, disabled until a chip
  changes, as the tag-labels editor beside it does.
- The summary, `/results` and `/collation` headers are out: the author
  named the reviewer surface and its preview.

### Blast radius (measured)

Taken 2026-10-11 at `7e329db5`.

- Model and migration: `app/db/models/review_session.py` gains one
  nullable JSON column; one Alembic revision (89 in `alembic/versions`).
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
- `spec/setup_pages.md` — the Reviewers Unlock panel's new card above `Upload Reviewers`; the roster card's readout labels (`Roster:`, `Populated:`) on all four pages and Reviewers' `Shown on surface:` readout.
- `spec/settings_inventory.md` — the new per-session setting, its default and its gate.
- `spec/csv_contracts.md` — the Settings CSV `session.*` row.
- `spec/roundtrip_coverage.md` — the new column round-trips.
- `guide/things_to_check_in_browser.md` — a section per code rung.
