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

**All three items closed 2026-10-11**, with the author's browser check.
The Items 2–3 close's `spec-writer` pass found every doc-impact spec
current, #2972's wider Responses released column included; Item 1's is
recorded in its `Status`.

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

### Status — closed 2026-10-11

Built as planned, in one rung (#2962). Two `diff-reviewer` reads. The first and
the `spec-writer` verify both found the `rrw-reviewer-tag-visibility`
row in `spec/settings_inventory.md` still listing tags only (fixed, and
added to `Doc impact`); the first also found a negative test half that
couldn't see a failed import (tightened). The second read the fixes and
found nothing blocking. The close's `spec-writer` pass found all three
doc-impact specs current, `spec/csv_contracts.md`'s `ProfileLink` row
included after Items 2 and 3; it changed nothing.

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

(Relabelled `Reviewer name only` / `Reviewer name, email` / `Reviewer
name, email, profile` on 2026-10-12, at the author's word; the levels
are unchanged.)

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

### Status — closed 2026-10-11

Shipped as laddered in three rungs (#2964–#2966), from base `73e7291a`.

- **Built as planned**, with one addition: `body.ui-v2 .pill[hidden]` in
  `base.html`, since `.pill`'s `display` outranked `hidden`.
- **Decided at build:** `upsert_policy` keeps a stored level unless one
  is passed; on the card's Save an absent input keeps the level and an
  empty one clears it; a corrupt stored level goes out empty and is
  dropped on copy.
- **Reads:** one cumulative `diff-reviewer` read and a read of its
  fixes. They found a `Name only` download still sorting namesakes by
  their hidden emails (fixed), observer tests reaching Raw through a
  cell the product forbids (moved to the released cell), and prose gaps.
  Codex found the corrupt-level Save block. `spec-writer` wrote the
  specs at rung 3, adding `spec/reviewer-surface.md` to `Doc impact`.
- **After:** #2972 widened the Responses released column while the pill
  shows, on the card and the reviewer surface.

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
- `spec/reviewer-surface.md` — the visibility card's line points at the identity pill (added at the close).
- `guide/things_to_check_in_browser.md` — a section per rung.

---

## Item 3 — A profile value that is not a web address

### Opportunity

A `ProfileLink` is any string up to 2,000 characters: nothing checks
its scheme on import or edit. Every renderer puts it straight into an
`href` — the operator rosters' `link`, the reviewer surface's, the
summary's and the reviewee results' `View`, the reviewer card's
`link` (Item 2) and the Band 2 preview. A plain string (`AB1234`,
`www.example.edu/rae`) becomes a relative link to an app path that
answers 404 or 422, and a `javascript:` value runs on click, since no
CSP header is set (traced 2026-10-11).

### Decision

The author's ruling, 2026-10-11: a value that starts `http://` or
`https://` stays a link; any other non-empty value renders a muted
`•••` whose hover (`title`) shows the value; an empty one stays empty. The same rule on every surface
that renders the value, operator rosters included. Downloads carry the
value whole: the observer CSV's `ReviewerProfileLink` already does at
the profile level, and the roster extracts are the operator's.

So the field can hold an id that is not a link. Whether it shows at
all stays where it is — the reviewee's under the instrument's display
fields, the reviewer's under Item 2's level — and where it shows, the
value may be read: it is in the download anyway.

Rejected: the em dash — Anonymized uses it on `/results` for a hidden
cell, and elsewhere it reads as nothing. Rejected: rendering the text
itself — the profile columns are sized for `View`
(`profile_column_ch_width`) under `white-space: nowrap`, so a long id
would spill into the next cell. Rejected: a Validate warning
for non-link values — an id is a legitimate use, so the warning would
be noise.

### Semantics

- **Link test.** The value starts `http://` or `https://`, case
  insensitive, with a host character after the `//`. One helper; the
  preview's JS mirrors it.
- **Stored data.** Nothing changes on import, edit or export; the rule
  is render-only, so a value turns into a link when it is corrected.
- **Sort.** Unchanged: the reviewer surface sorts on the stored value.
- **`Name, email, profile`.** Still offered when any reviewer has a
  non-empty value: the CSV carries text values too.

### Blast radius (measured)

Taken 2026-10-11 at `e5794301`.

- Renderers (`grep -rn 'href="{{' app/web/templates | grep profile`,
  plus the reviewer surface's display cells): 7 — `session_reviewees.html:848`,
  `session_reviewers.html:1030`, `review_surface.html:433`,
  `summary.html:136`, `results.html:146`, `results.html:156`, and the
  preview's `isProfile` branch in `instruments_index.html` (~2411).
- Specs naming the render: `spec/reviewer-surface.md` (§ display cells),
  `spec/participant_model.md` (`raw` bullet), `spec/setup_pages.md`
  (both rosters' Profile row), `spec/csv_contracts.md` (both
  `ProfileLink` rows).
- Tests naming the field: `grep -rln "profile_link\|ProfileLink\|is_profile_link" tests | wc -l` → 69.

### Status — closed 2026-10-11

Shipped as laddered: the plan (#2968), then the rule in one code rung
(#2969).

- **Built as planned.** `views.is_web_link` and
  `_partials/profile_value.html` on the six template renderers, and the
  preview's `isWebLink` / `profileCell`.
- **Decided at build:** both sides match the unstripped value, ASCII
  only, so `httpſ://` and a leading-space value never link.
- **Reads:** one `diff-reviewer` read, which found those two matching
  gaps, and a read of the fixes, which found Python and JS agreeing on
  every BMP code point. `spec-writer` verified the specs and added the
  `spec/settings_inventory.md` rows to `Doc impact`.

### PR ladder

1. **This plan.** Prose only.
2. **The rule.** The helper, a Jinja global, the seven renderers, the
   specs, a test per surface for a link, a non-link and an empty value,
   and a browser-check section. One code rung, so it takes its own
   `diff-reviewer` read.

### Definition of done

- Each of the seven renderers shows a link for an `http(s)` value, the
  `•••` carrying the value as its `title` for any other value and
  nothing for an empty one, by test;
  no rendered `href` carries a non-`http(s)` profile value.
- The observer CSV carries a text value whole at the profile level, by
  test.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

- None open. The author ruled on 2026-10-11: the `•••` marker, its
  hover showing the value on every surface, no validation, and the CSV
  carrying the value whole.

### Out of scope

- Refusing or correcting a non-link value on import or edit.
- A CSP header: a wider change than one field.

### Doc impact

- `spec/reviewer-surface.md` — the display-cell render: link, marker or empty.
- `spec/participant_model.md` — the `raw` bullet's profile anchor follows the same rule.
- `spec/setup_pages.md` — both rosters' Profile cell.
- `spec/csv_contracts.md` — both `ProfileLink` rows say what a non-link value shows.
- `spec/settings_inventory.md` — both `profile_link` rows: any string, only an address links (added at rung 2).
- `guide/things_to_check_in_browser.md` — a section for rung 2.
