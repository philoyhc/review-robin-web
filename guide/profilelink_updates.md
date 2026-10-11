# ProfileLink updates

**Opened:** 2026-10-11 · **Theme:** a reviewer's `ProfileLink`, which is
imported, edited and exported but shown almost nowhere · **Related:**
`spec/setup_pages.md`, `spec/csv_contracts.md`, `spec/participant_model.md`

A standalone plan at the author's naming, not a `segment_*.md`, in the
shape of `guide/ux_refinements.md`: items close independently, each with
its own `### Doc impact` and `### Status`. `tools/close_check.py` reads
only `segment_*` files, so an item's `Doc impact` is checked by hand at
its close.

**Where it stands.** `reviewer.profile_link` is imported from
`reviewers.csv`'s `ProfileLink` column, set by the Reviewers page's Add
and Edit forms, and exported by the Reviewers extract. The Reviewers
table renders a Profile column when some reviewer has one, but unlike
Reviewees gives it no column chip; and no participant surface shows a
reviewer's link, since display fields come only from the reviewee and
pair-context rosters. `spec/csv_contracts.md` says the reviewer's link
is "rendered as a clickable link on the reviewer surface", which is true
only of the reviewee's.

---

## Item 1 — The Reviewers page's Profile column chip

### Opportunity

On Reviewees, the Profile column has a "Show columns:" chip like each
tag column. On Reviewers it renders on the same rule (some row has
data, or a row is being edited) but has no chip, so an operator can't
hide it; `spec/setup_pages.md` calls the asymmetry deliberate. The
author ruled it should match Reviewees (2026-10-11).

### Decision

Reviewers takes the Reviewees chip as is: `data-col-toggle="profile"`
on a chip gated by `col_data["profile"]`, and a
`#reviewers-table.col-hidden-profile .profile-col` rule beside the tag
ones, so the shared `[data-col-toggle]` primitive in `base.html` hides
and restores it and remembers the choice. Rejected: a server-side
toggle, which the tag columns don't use and would split one behavior in
two.

### Semantics

- No reviewer with a link: no chip and no column, as now; edit mode
  still shows the column so a link can be typed.
- The chip row appears when the Profile chip is its only chip.

### Blast radius (measured)

Taken 2026-10-11 at `e8dcd994`.

- `app/web/templates/operator/session_reviewers.html`: the chip row and
  the scoped `<style>` block (`grep -n col-hidden`).
- `tests/integration/test_import_routes.py`: one new test beside the
  Reviewees one.
- `spec/setup_pages.md` (three places: the chip bullet, the shared-
  markup note, the Reviewers column table) and `spec/csv_contracts.md`
  (the `reviewers.csv` `ProfileLink` row).

### Status

Built as planned, in one rung. Two `diff-reviewer` reads. The first and
the `spec-writer` verify both found the `rrw-reviewer-tag-visibility`
row in `spec/settings_inventory.md` still listing tags only (fixed, and
added to `Doc impact`); the first also found a negative test half that
couldn't see a failed import (tightened). The second read the fixes and
found nothing blocking.

### PR ladder

1. **The chip.** Template, test, specs, a browser-check section. One
   code slice; takes a `diff-reviewer` read and, touching `spec/`, a
   `spec-writer` verify.

### Definition of done

- A Reviewers page with a reviewer link shows a Profile chip that hides
  and restores the column; without one, neither appears.
- `spec/setup_pages.md` no longer calls the asymmetry deliberate.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

- None.

### Out of scope

- Who sees a reviewer's link outside the operator pages: Item 2.

### Doc impact

- `spec/setup_pages.md` — the chip bullet and the shared-markup note name Reviewers; the Reviewers Profile column is toggleable.
- `spec/csv_contracts.md` — the `reviewers.csv` `ProfileLink` row says where the link shows (the Reviewers page and extract), not the reviewer surface.
- `spec/settings_inventory.md` — the `rrw-reviewer-tag-visibility` row lists Profile among the columns it remembers.
- `guide/things_to_check_in_browser.md` — a section for the PR.

---

## Item 2 — How much of a reviewer Raw results identify

### Opportunity

A reviewer's link reaches no participant, and Raw is all or nothing on
who the reviewer is: a reviewee's `/me/sessions/{id}/results` names the
reviewer with name and email, and an observer's Raw download carries
`ReviewerName` and `ReviewerEmail`. The author ruled (2026-10-11) that
the link must not show by default, and that the operator chooses how
much of the reviewer Raw reveals.

### Decision

On Band 2's "Who can see what you wrote" card, when the Reviewees or
Observers **Responses released** cell is Raw, a second chip appears to
its right and cycles:

- `Name only`
- `Name, email`
- `Name, email, profile` (offered only when some reviewer in the
  session has a `ProfileLink`)

The level is stored per `(instrument, audience)` on the
`instrument_view_policies` row beside the after-release mode, so it
travels wherever the mode does: Save, the Settings CSV, Replicate and
Duplicate. Rejected: one session-wide switch (Raw is per instrument and
per audience, and the level belongs with it), and a reviewer-side
display field (display fields have no reviewer source, and a field
would need adding per instrument).

### Semantics

- No row, or no level stored: `Name, email`, which is Raw today, so
  existing sessions don't change.
- Anonymized, Summarized or off: no chip; a stored level is kept and
  ignored, so cycling back to Raw restores it.
- Reviewees: `Name only` drops the email line from the identity cell;
  the profile level adds the reviewer's link under the email as the
  operator pages' `link` anchor (`target="_blank" rel="noopener"`),
  when that reviewer has one.
- Observers' Raw download: `Name only` blanks `ReviewerEmail` and the
  three reviewer tag columns, which can identify as surely as an email
  (the headers stay; Codex on #2961); the other two levels keep the
  tags, as Raw does today. The profile level adds a `ReviewerProfileLink` column
  after `ReviewerEmail`, in the observer's download only. Operator
  extracts are unchanged.
- No reviewer has a link: the cycle skips the third state; a stored
  third state still renders (so it can be cycled off) and shows no link.
- The locked card and the reviewer surface's copy of it show the level
  as a plain pill after the mode, since the card tells the reviewer
  what others see. The Observers row stays operator-only.
- Reviewers Session ongoing and Responses released: no chip. A
  reviewer seeing their own work is not identified to anyone.

### Judgment calls — decided

- The default is `Name, email`, not `Name only`: today's Raw, so the
  migration changes nothing anyone sees.
- The observer CSV gains its column only at the profile level, so the
  operator's extracts and every other level keep their header.
- The reviewer's copy of the card shows the level as a plain pill, and
  the level covers the reviewer's identity only, not the reviewee's in
  the observer download (both confirmed by the author, 2026-10-11).

### Blast radius (measured)

Taken 2026-10-11 at `e8dcd994`.

- Model and migration: `app/db/models/instrument_view_policy.py` gains
  one nullable column; one Alembic revision (88 in `alembic/versions`).
- `app/services/visibility_policies.py`: validation, upsert, audit
  (`instrument.view_policy_set` changes), and a reader for the level.
- Writers: the card's Save in `app/web/routes_operator/_instruments.py`
  (two `upsert_many` sites, lines ~703 and ~911); the Settings CSV in
  `app/services/session_config_io/` (`_serialize.py`, `_apply_parse.py`,
  `_apply_instrument.py`); `copy_view_policies` in
  `app/services/instruments/_instrument_crud.py`, which Replicate and
  `app/services/session_clone.py` call.
- UI: `app/web/templates/operator/instruments_index.html` (the card,
  lines ~1620-1700, and its cycle JS), `app/web/views/_instruments.py`,
  `app/web/templates/reviewer/review_surface.html` (line ~257).
- Readers: `app/web/views/_reviewee_results.py` (line ~670),
  `app/web/templates/reviewer/results.html` (line ~146),
  `app/web/routes_reviewer/_collation.py` and
  `app/services/extracts/by_instrument_extract.py` (the reviewer block,
  line ~510).
- Tests: `grep -rln "view_polic\|visibility_policies" tests/` gives 22
  files; the ones touched are the policy routes, resolver, Settings CSV
  cells, Replicate and clone, reviewee results body, and the observer
  CSV.

### Status

- Rung 1 (2026-10-11), base `73e7291a`: the inert pill in the editor
  and the locked table, shown only beside a Raw cell. It needed a
  `body.ui-v2 .pill[hidden]` rule in `base.html`, since `.pill`'s
  `display` outranked `hidden`, as `.btn`'s once did.

### PR ladder

1. **Scaffold.** The level chip on the card and the locked pill, inert,
   showing `Name, email`. No storage. Lands the shape for a browser look.
2. **Storage and readers.** Column, migration, service, Settings CSV
   round trip, copies, and both readers (reviewee identity cell,
   observer download). Only the Settings CSV can set a level, so the
   readers honor every level before any control offers one.
3. **The live chip.** The card's chip cycles and Save persists it; the
   locked and reviewer-surface pills show the stored level. Never a
   control whose choice the participant pages ignore (Codex on #2961).
   The item's last build rung: a `diff-reviewer` read on the cumulative
   diff from rung 1's base, and a `spec-writer` verify.

### Definition of done

- Each level renders as Semantics says on the reviewee page and in the
  observer download, by test; `Name only` shows no email or reviewer
  tag, and Anonymized and Summarized never show an email or a link.
- The level round-trips through Save, the Settings CSV, Replicate and
  Duplicate, by test; Postgres CI runs the migration both ways.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

- None open. The author ruled the default (no link), the chip's place
  and its three states on 2026-10-11.

### Out of scope

- A reviewee's identity as the observer sees it (`RevieweeName` /
  `RevieweeEmail`): the chip is about who wrote the response.
- The operator's own extracts, which always carry everything.

### Doc impact

- `spec/visibility_policy.md` — the identity level: where it is stored, which cells carry it, its default, and that only Raw reads it.
- `spec/instruments.md` — the Band 2 card's level chip and its locked pill.
- `spec/participant_model.md` — the `raw` bullet reads the level for the identity column; the observer download's columns per level.
- `spec/csv_contracts.md` — the Settings CSV `view_policies[<audience>]` attribute, and the reviewer `ProfileLink` row naming where it now shows.
- `spec/settings_inventory.md` — the new persisted setting under the per-instrument visibility policy.
- `spec/roundtrip_coverage.md` — the new column round-trips.
- `guide/things_to_check_in_browser.md` — a section per rung.
