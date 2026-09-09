# Setup Pages — UI spec

Per-session **Setup Pages** are the per-entity import + edit
surfaces reachable from the chrome's Setup row:

| Page | URL | Template |
|---|---|---|
| Reviewers | `/operator/sessions/{id}/reviewers` | `session_reviewers.html` |
| Reviewees | `/operator/sessions/{id}/reviewees` | `session_reviewees.html` |
| Relationships | `/operator/sessions/{id}/relationships` | `session_relationships.html` |
| Observers | `/operator/sessions/{id}/observers` | `session_observers.html` |
| Instruments | `/operator/sessions/{id}/instruments` | `instruments_index.html` |
| Email Template | `/operator/sessions/{id}/setup-invite` | `session_setupinvite.html` |

Each Setup Page follows the same shell (chrome + Setup row +
status strip + a body of cards). The Reviewers, Reviewees,
Relationships, and Observers pages additionally render a **preview
table** of the session's current rows that all share a common
visibility-toggle pattern; this spec covers that shared pattern
alongside the per-page idiosyncrasies.

**Observers page gate.** The Observers Setup page routes
(`app/web/routes_operator/_setup_observers.py`) are gated by
`require_observers_enabled_session` — the page returns 404 until
the operator enables observers via the **User interface settings**
card on the Create Session form or Edit Session Details page. When
`session.observers_enabled` is `True` the page renders with the
same CRUD shape as Reviewers / Reviewees.

**Assignments retired from Setup row in Segment 15D PR 6a.** The
page moved to the Operations row and is no longer a per-entity
Setup primitive — pair-level context (formerly the
`PairContext1/2/3` / `AssignmentContext1/2/3` JSON columns) lives
on the first-class `relationships` table now, and the Operations
Assignments page is the materialised-derivative surface where the
operator runs the rule engine. See `spec/operator_ui_concept.md`
§5 and `spec/assignments.md` for the post-15D Operations
Assignments page contract.

For the cross-page chrome contract (two-row navigation, status
strip, lock cards, principles P1–P4), see
[`spec/operator_ui_concept.md`](operator_ui_concept.md). For the
Quick Setup card on Session Home that bulk-uploads into the same
import paths these pages expose, see
[`spec/quick_setup_card_spec.md`](quick_setup_card_spec.md).

## Shared body shape

Every Setup Page renders, top-to-bottom:

0. **Page guidance** (`partials/_page_guidance.html` — Segment 19E
   rung 6). A `<details class="card page-guidance">` — a **half-width
   card**, not an inline band. **Closed by default**, showing one
   line: the summary `What this page is for`, set in **card-header
   type** (`--fs-h2`, weight 600 — the summary *is* this card's
   heading, so it reads as one and starts flush with every other card
   heading on the page), followed by the **same solid triangle the
   collapsible instrument cards use** (`.instrument-card-toggle-icon`,
   U+25BE) with the same rotate-180-when-open convention — down closed,
   up expanded. One disclosure glyph across the app, so an operator
   learns it once. The glyph sits **after** the text rather than before
   it: leading with it would indent the heading out of line with its
   neighbours. The native marker is suppressed both ways engines need
   (`list-style: none` and `::-webkit-details-marker`). Open, the card
   grows downwards in place.

   It fills with the shared `--card-help-*` tokens
   (`spec/color_tokens.md`), the same set `.rs-help-card` uses — which
   is why the theme customizer's facet is named `Help card` rather than
   after either caller.

   Width comes from the column the page puts it in, never from the
   macro — the macro takes no arguments. Closed, the card is
   one line: `padding: 12px 16px` and `align-self: start`, so a
   stretching grid cannot inflate it to a neighbour's height.

   **Every half-width card above the preview table shares one
   `.card-columns`, not a row grid — and not two of them.** Two
   containers look identical while everything is closed and still lose
   the point: growth in the upper one pushes both columns of the lower
   one down. A full-width card (the Activated lock card) therefore
   cannot sit between the pairs; `.card-columns` has no spanning slot,
   so it goes above the container, where its "cannot edit" notice
   reads anyway. `.card-columns` is `1fr 1fr` with `align-items: start`, and
   each child is a *column* that stacks its own cards — so opening the
   guidance pushes down only what is below it in its own column, and
   the other column neither moves nor stretches. That is the whole
   reason the primitive exists; `.page-grid` and `.bottom-grid` lay
   cards out in rows and would drag the neighbour's height along.

   | Page | Placement |
   |---|---|
   | Reviewers / Reviewees / Relationships | `.card-columns` — **every** card above the preview table: guidance then the tag-label editor on the left, `Fields with data` then `Operator actions` on the right. The Activated lock card sits above the container, not between the pairs. |
   | Observers | `.card-columns` — guidance leads the **left** column with `Cohort match rule` beneath it; `Operator actions` alone in the right |
   | Email Template | `.card-columns` — composer left; guidance then `Merge tags` right |
   | Instruments | `.card-columns` — guidance left, `Session deadline` right; the `Expand all` / `Collapse all` toggles moved into the deadline card to free the slot |

   The summary wording is
   fixed in the macro rather than passed per page, because it is a
   repeated affordance and an operator learns a control faster when
   it reads identically everywhere; a page needing different wording
   is a finding about the scaffold. Body content is supplied by each
   page through `{% call %}`.

   The prose is **short and links to `/guide` rather than restating
   it** — each Guide section card carries `id="guide-<section key>"`,
   derived from the key `app/web/views/_guide.py` gates on, so a
   renamed section breaks a test rather than becoming a dead link.
   Links carry `?return_to=<this page>`, which the Setup-page paths
   satisfy under `app/web/return_to.py`'s allowlist.

   Distinct from the per-form `.form-help` text, which stays: that is
   mechanics for one field, this is purpose for the page. Also
   distinct from the `.banner` family, specced behaviourally as
   *transient* page-level feedback — persistent explanation is not
   that.

   **Rollout status.** All six pages carry the card with real copy —
   Email Template's landed at rung 6a, the other five at rung 6b.

   **The copy contract.** The shipped words live in the six templates
   and nowhere else — reproducing them here would make every wording
   tweak a two-file edit, and a second copy drifts. What is specced is
   what an edit is *held to*:

   1. **One paragraph per question, and no paragraph without a
      question.** Written as a two-paragraph ceiling; the roster pages
      overran it at the author's 2026-09-07 pass and the rule was the
      thing that gave, not the copy. What the ceiling was protecting is
      still right and is what this rule now says: an operator opening a
      disclosure wants the things they were missing, not the page's
      manual, so each paragraph earns its place by answering one
      question a reader actually has (*what is this? who must have an
      email? what do the tags do? what does upload cost me?*) and the
      card ends when the questions do. Five paragraphs of that is
      shorter to read than two that bundle four subjects.
   2. **Say what the page's own controls do not.** A card labelled
      "Upload Reviewers" already says it uploads reviewers. Each page's
      guidance earns its place by carrying one fact the page is
      otherwise silent about, listed in the table below;
      `test_every_setup_page_states_its_own_invisible_fact` pins each
      one, so a rewrite that loses the fact fails rather than merely
      reading differently.
   3. **Link to the Guide; never restate it**, and put the link **at
      the end** — a link mid-card invites the reader out before they
      have finished. Five pages point at `#guide-create_and_set_up`;
      Email Template points at `#guide-give_access`. One Guide card
      serving five pages holds only because each body links after
      making its own point; the day a body needs to send an operator to
      a *particular* explanation, the fix is splitting that Guide card,
      not lengthening the guidance.
   4. **Guide vocabulary, verbatim** — "Prepare", "Activate",
      "Validated", "instrument", "assignment" — so an operator moving
      between the two does not have to translate.
   5. **No layout references.** "The card on the right" survives
      exactly until someone moves the card; name things by their label.
      **One sanctioned exception:** Email Template's "the merge tags on
      the right", because that card has no label an operator could
      match on beyond its `Merge tags` heading, and "on the right" is
      how they will look for it. Recorded as an exception so it is not
      read as licence.

   | Page | The fact its card must carry |
   |---|---|
   | Reviewers | The email is mandatory and should be the institutional MS365 account they sign in with, not contact detail; upload **replaces** the roster and clears assignments; `inactive` is the non-destructive alternative to delete; and an empty roster blocks `draft → validated` (`reviewers.empty`, error severity) |
   | Reviewees | An email is **optional** when you are only collecting data about someone — and **required, tied to their institutional MS365 account**, the moment they must see responses or summaries, since that is what a sign-in is matched against (the gap surfaces only as `reviewees.unreachable_for_results` on Validate); an empty roster blocks `draft → validated` (`reviewees.empty`, error severity) |
   | Relationships | The page is **optional** — a session works without any — and earns its keep only for context *not already derivable from reviewer and reviewee tags*; its three tags are a real assignment-rule namespace (`pair_context.tagN` → `Relationship.tag_N`, `spec/assignments.md` "Predicate vocabulary"), so they can affect who reviews, or does not review, whom — **but only once populated**, since `views._instruments._new_model_usable_tags` offers a namespace + slot in the Band 1 dropdowns only when some row fills it |
   | Observers | The page is **optional** — a session works without any; the cohort rule grants sight rather than narrowing it, so an observer with no rule sees **nothing** (see "Cohort match rule editor" below); and what they see of each response is a **per-instrument** Band 3 policy, not a setting on this page |
   | Instruments | The instrument carries the assignment rule, and pairs materialise at Prepare rather than as the rule is edited; a session **must keep at least one** (`routes_operator/_instruments.py` refuses the last delete) |
   | Email Template | Sending is not switched on (Segment 14B), and no part of reviewer access depends on it |

   **The three "must have at least one" sentences do not describe the same
   mechanism, and the cards say so.** Instruments is a **hard guard** — the
   route refuses the last delete outright (`Cannot delete the last
   instrument`), so the card states it flatly. Reviewers and Reviewees are
   **not** guarded: an operator can empty either roster in Draft and the app
   allows it. What they cannot do is leave Draft — `reviewers.empty` and
   `reviewees.empty` are error-severity rules, and
   `session_lifecycle.mark_validated` refuses the transition while any error
   stands. So those two cards add *"to proceed. Validation will block you"* —
   which names the thing the operator will actually meet (a blocking issue on
   Validate) rather than the lifecycle state it gates, and leaves no reader
   expecting a delete to be refused.

   Instruments runs *what an instrument is* → *when you want another* →
   *what each one controls*: the order the questions arrive in, and the
   order that keeps the Guide link at the end.

   **Mode names are quoted from the app, not translated.** The
   Observers card writes `Anonymized` / `Summarized` with the app's own
   US spellings, because those are the words on the Band 3 policy
   control an operator is being sent to
   (`app/services/visibility_policies.py`, `spec/visibility_policy.md`).
   Rule 4 settles it independently of whatever the surrounding prose
   convention is: a card that says "anonymised" sends a reader looking
   for a label that does not exist. (The repo's prose convention is US
   spelling as of 2026-09-07 — `CLAUDE.md` → Project conventions — so
   the two now agree, but this rule held while they disagreed and is
   what to reason from if they ever diverge again.) Reviewers and Reviewees
   run the same way — *who they are* → *what identifies them* → *what
   the tags do* → *what upload costs* → the Guide link on its own line.
   The two pages are deliberately near-parallel: an operator reads them
   minutes apart, and the sentences that differ are then the ones
   carrying the difference.

   Drafted in `guide/archive/page_help_text.md`, retired 2026-09-06 —
   read it for why each sentence was chosen, not for what the app says.

1. **Chrome** (`session-nav-card` partial — two-row top nav with the
   Setup row highlighted).
2. **Status strip** (`session_setup_status_row` partial) — counts
   pills per entity.
3. **"Fields with data" pill row** — badge per CSV column that has
   at least one populated value (`reviewer_fields_with_data` /
   `reviewee_fields_with_data` in `app/services/assignments/`;
   `relationships.fields_with_data` in
   `app/services/relationships.py`). Drives operator awareness of
   which optional fields the latest import populated. The raw CSV
   column names are mapped through `views.friendly_fields_with_data`
   so that **a pill reads what this page's preview table heads that
   column**. Three sources, in order (Segment 19H Item 5, 2026-09-09):
   a **per-page** label for a column the renamable slots cannot name
   correctly; then the session's field-label config for one of the 12
   in-scope field-label slots — **nine of them operator-renamable**,
   with the three reviewee-identity slots (`RevieweeName`,
   `RevieweeEmail`, `PhotoLink`) resolving to a fixed builtin default
   since renaming them was retired 2026-05-31 (`spec/settings_inventory.md`
   `field_label_overrides`) — which is the same label the preview header
   and the `Show columns:` chip render; then
   the canonical CSV name for anything else (`Status` on
   Relationships, whose preview header is also `Status`).

   The per-page layer exists because two columns fall outside the
   slots in opposite ways. `ReviewerName` / `ReviewerEmail` have no
   slot at all, and rendered as raw CSV names beside preview columns
   headed `Name` and `Email`; they now read **`Name`** and **`Email`**.
   `RevieweeEmail` does have a slot, and on Relationships resolved to
   the reviewee page's `Email` beside a column headed `Reviewee`; on
   that page the two identifier pills now read **`Reviewer`** and
   **`Reviewee`**, matching its fixed headers. So one CSV column has
   two correct pill texts depending on the page, which is why the
   surface is a required parameter rather than a global map — and why
   it indexes rather than defaults: a page that omits it raises instead
   of quietly rendering CSV column names again.
4. **Lifecycle gate cards** (when the session is Activated): a
   `card lock` carrying "The {entity} cannot be modified while the
   session is ongoing. Revert the session to draft if you wish to
   modify anything." with an inline Revert form. Sits **above**
   the friendly-label editor so the yellow card immediately
   follows the status info card — the same status-info-then-
   yellow-lock pattern the Instruments and Assignments pages use.
5. **Friendly-label editor (left) + Operator actions card
   (right)** — a half-width `bottom-grid` pair.
   - The **friendly-label editor** (Segment 15A Slice 3) is the
     inline editor card via
     `operator/partials/_field_labels_editor.html`. Reviewers +
     Relationships render a 3-cell row; Reviewees a 2-row stacked
     grid (identity + tags, 6 cells). Save + Cancel pair in
     Secondary style, both starting `disabled` until the form is
     dirty (inline JS toggles via an initial-value snapshot).
     POST handlers in the per-entity setup modules
     (`app/web/routes_operator/_setup_reviewers.py` /
     `_setup_reviewees.py` / `_setup_relationships.py`) upsert /
     clear via `app/services/field_labels.py`.
   - The **Operator actions card** (Segment 15F) is the per-row
     authoring surface — search / status filter strip + a
     selection-driven button row (Edit · Inactivate · Activate ·
     Add · Delete). See "Operator actions card" below.
   - The **friendly-label editor** is gated by `is_ready`: when
     the session is Activated its inputs render `disabled` and
     the Save/Cancel pair is suppressed; the lifecycle-gate card
     above carries the "revert to draft" prompt for that state.
   - The **operator-actions button row** is gated by
     `is_editable` (Segment 19I Item 3) and is **absent**, not
     inert, outside `draft` / `validated`. It used to render
     always and merely ship `disabled`, which is why the earlier
     wording said "inert"; it is now not rendered at all. See
     `spec/lifecycle.md` §5.
6. **Preview table card** — Reviewers / Reviewees / Relationships.
   Always renders when the entity is non-empty (or when Add mode
   is active), regardless of lifecycle state. A **leftmost
   checkbox column** drives the operator-actions selection (a
   header select-all checkbox toggles every visible row). Column
   headers render the resolved friendly label via
   `operator/partials/_field_label_header.html`; when an override
   is set, the canonical name appears as `.field-label-canonical`
   muted subtext below the friendly label and the sort `↕`
   button. While a row is being edited (`?edit_id=`) or a blank
   Add row is active (`?add=1`), that row's cells render as
   inputs / pickers — see "Per-row Edit / Add / bulk actions".
7. **Body grid** — Upload + Danger Zone cards. Hidden when the
   session is Activated *or* while a row is being edited / added.
   Placed **after** the preview table so the operator's eye lands
   on the data they're managing first; the upload-CSV +
   delete-all destructive actions sit below the table as a
   deliberate de-prioritised cluster. CSV upload stays the
   bulk-create path; the Operator actions card covers single-row
   authoring.

## Preview tables (shared toggle pattern)

**The "Showing N of M" hint** renders at the **top-left of the
preview-table card**, above the table, whenever the cap or a filter
has trimmed the list (`.table-showing-hint`; Segment 19I Item 4). It
lived flush right in the operator-actions strip until then, roughly
950px from the rows it describes; here it reads left-to-right with the
page and sits with what it counts. An untrimmed list renders no hint —
"Showing 6 of 6" is noise. It appears on all four roster pages.

The Reviewers, Reviewees, and Relationships preview tables share
a **column-visibility chip row** that lets the operator hide
optional columns. The pattern (Segment 18E Part 1):

- A `Show columns:` chip row sits in the top "Fields with data"
  card, directly below the `Fields with data:` line. Each chip is
  a `<span class="pill … tag-chip" data-col-toggle="<slot>"
  role="button" tabindex="0">` carrying the column's **friendly
  label** (the operator-set field label, falling back to the
  default — same label the header renders). The chips reuse the
  Sessions-lobby tag-filter chip styling (`.pill` + `.tag-chip` +
  `.is-selected`); the inline JS binds both `click` and
  `keydown` (Enter / Space).
- Optional tag / context columns always render in the DOM (so
  empty columns can be revealed). Clicking a chip toggles
  per-column visibility via a CSS class on the table (e.g.
  `col-hidden-tag-1` → `display: none` for cells with class
  `tag-col-1`). The chip flips between filled (`is-selected`,
  column shown) and plain pill (column hidden), with `aria-pressed`
  tracking the state.
- Each chip defaults to **selected iff that column has at least
  one populated value** in the current preview rows.
- **Empty columns render a disabled chip** (`pill-empty
  tag-chip is-disabled`, struck through, `aria-disabled="true"
  title="No data in this column"`, no `role="button"`). The
  operator can't toggle an empty column on, and stored "show"
  preferences carried over from a load when the column had data
  are ignored — the chip stays unselected and the column stays
  hidden until the next import populates it.
- The Reviewees row also carries a chip for the **profile-link
  column** (`data-col-toggle="profile"`, cells `class="profile-col"`).
  That column is server-rendered only when some row has a link, so
  its chip never reaches the disabled state.
- Operator choice persists per browser via `localStorage` under a
  per-page key:
  - Reviewers preview: `rrw-reviewer-tag-visibility`.
  - Reviewees preview: `rrw-reviewee-tag-visibility`.
  - Relationships preview: `rrw-relationship-tag-visibility`.
- Stored choice wins over the data-driven default for live chips.
  Stored "hide" keeps a populated column hidden; stored "show"
  reveals an explicitly-toggled-on column on next load. Disabled
  chips ignore storage entirely (see above).
- The inline JS targets `[data-col-toggle]` and early-returns on
  the `is-disabled` chip class so listeners aren't bound and
  storage isn't applied.

The pattern is intentionally not extracted into a Jinja macro —
each page's column shape differs enough (Reviewees adds the
profile-link chip) that the inline JS + scoped `<style>` block per
template is more legible than a macro with a sprawling parameter
list.

## Sortable headers (shared affordance)

All three preview tables — Reviewers, Reviewees, Relationships
— **opt into the shared sort primitive** that
`spec/sort_by_reviewee.md` documents. Each table:

- Carries a `<table data-rrw-sortable="rrw-sort-{surface}-{session_id}">`
  marker. Surface tokens: `reviewers` / `reviewees` /
  `relationships`.
- Wraps its data rows in `<tbody class="rrw-rows">`.
- Renders every sortable header with `class="rrw-sortable"` +
  `data-sort-key="..."` + a child `<button class="rrw-sort-btn">`
  carrying the `↕` / `1↑` / `2↓` badge.

Cookie persistence is per-(browser, session, table) — see
`spec/settings_inventory.md` §7 for the cookie shape. Sort state
survives reloads on the same browser; clearing all cookies
returns to insertion order. The route layer reads the cookie at
render time so the initial HTML lands sorted (no JS-reorder
flicker on first paint).

Sortable columns per table:

- **Reviewers:** `name`, `email`, `tag_1` / `tag_2` / `tag_3`,
  `status`, `updated_at`.
- **Reviewees:** `name`, `email_or_identifier`, `tag_1` /
  `tag_2` / `tag_3`, `status`, `updated_at`. (The Photo column
  stays non-sortable — it renders a link, not a comparable
  value.)
- **Relationships:** `reviewer` / `reviewee` (both sort on the
  resolved member **name** — the prominent identity text since
  Segment 15F), `tag_1` / `tag_2` / `tag_3`, `status`,
  `updated_at`.

The right-end **Updated** column shows each row's `updated_at`
timestamp (`%Y-%m-%d %H:%M`); sorting it descending surfaces the
most recently added / edited rows. Freshly inserted rows carry
`updated_at == created_at`; a per-row edit bumps it. The
server-rendered Add / Edit rows show `—` in this cell (no
committed value yet).

Sortable affordance and visibility-toggle affordance are
orthogonal — toggling a column's visibility doesn't affect its
sort state, and a sort spec referencing a hidden column still
applies (the column data is still present in the DOM).

## Operator actions card (Segment 15F)

The right half of the `bottom-grid` pair (friendly-label editor
on the left). It is the per-row authoring surface — operators no
longer round-trip a CSV bulk-replace to fix one name, retire one
person, or add one row. Top-to-bottom:

1. **Search + filter strip.** One shape on all four pages
   (Segment 19I): a **Status** filter (`all` / `active` /
   `inactive`) and a search box backed by a `<datalist>`
   typeahead. Relationships carried a **Search by** dropdown
   (Reviewer / Reviewee) instead of the Status filter until 19I;
   it is retired — the page has had a row `status` since 15D and
   ships the Inactivate / Activate buttons that set it, so the
   filter was missing rather than unwarranted, and the search now
   reaches both sides of the pair without being told which. What
   the search matches and what the typeahead offers is the
   "Search matching and suggestions" contract below.
2. **Action row** (`filter-actions`) — an optional **Clear**
   link, then the selection-driven **Edit**, **Inactivate**,
   **Activate**, **Add** and **Delete** controls, and finally
   the **Search** submit last. Controls only: the status items
   moved to row 3 in Segment 19I. Buttons enable / disable from
   the checkbox selection (see below). The row greys out
   (`is-locked`) while a row is being edited / added; a focused
   **Save / Cancel** pair renders below a divider in that
   state.

   `Add` was `Add new row` until 19I and shortened to make room
   for `Delete`, which carries the **Destructive** role
   (outline red, `spec/ui_elements.md` §6) and sits between
   `Add` and `Search`.
3. **Status row** (`filter-confirm`) — the **selected-count
   pill** and the delete **confirmation checkbox** (`Yes, delete
   these`), inline and flush right beneath the controls
   (Segment 19I). The gate sits with the count because it is
   *about* the count: "3 of 4 selected · ☐ Yes, delete these" is
   a sentence, where the same checkbox on the button row would be
   a control with no stated object.

   The **"Showing N of M"** hint shared this row until Item 4 and
   now sits at the top-left of the preview-table card instead —
   with the rows it counts rather than ~950px to their right. See
   "Preview tables" below.

   **The pill reads `N of M selected`**, where `M` is the
   **rendered window**, not the roster. It gained that denominator
   with the hint's move (Item 4): the two numbers are what make
   the cap-versus-match gap visible, and the pill now carries half
   of it on its own. `M` is the window because that is what
   select-all can reach — see the caveat under "Deleting the
   selected rows".

   **The delete gate is two-stage.** A selection enables the
   checkbox; ticking the checkbox enables `Delete`, through the
   app-wide `data-delete-confirm` / `data-delete-btn` pairing in
   `base.html`. With nothing selected **both** are inactive — a
   tickable box with nothing to confirm invites confirming
   before selecting. Changing the selection **clears** the tick
   rather than merely disabling it, because "these" names the
   selection as it stood when the box was ticked.

   Its own class rather than a change to `.filter-actions`,
   which seven templates share: the three non-roster users
   (Assignments, Invitations, Responses) keep the single-row
   shape.

### Deleting the selected rows (Segment 19I)

`POST /operator/sessions/{id}/{reviewers|reviewees|observers|relationships}/bulk-delete`
— the selection-driven sibling of `bulk-inactivate`, one route per
page, taking the same `<entity>_ids` list and the same `filter_status`
/ `filter_q` round-trip.

**Two gates, both re-checked server-side.** The strip's checkbox is a
convenience; these decide:

1. `confirm` must be exactly `"true"`, or **400** — the same refusal
   the Danger Zone's `delete-all` uses.
2. When the **selected rows** carry saved responses,
   `acknowledge_response_loss` must be `"true"`, or **400** naming the
   exact number. `delete-all` can only ask whether the *session* has
   responses; a selected delete knows which rows are going, so it
   counts theirs. Selecting a reviewer with no answers therefore
   deletes without an acknowledgement even on a session full of them.

**What a delete takes with it** is inherited from the ORM cascade, not
reimplemented: `Reviewer` / `Reviewee` → their `assignments` → those
assignments' `responses`, plus a reviewer's `invitations`. **Observers
and Relationships cascade to nothing** — no table references them — so
their delete can never lose a response, their gate never fires, and
their strip never offers the acknowledgement. A page that offered it
would be describing a loss that cannot happen.

**The confirmation names what goes**, modelled on the Instruments
page's *"Yes, delete Instrument #1 and its associated assignments and
reviewer responses."* (Segment 19I Item 3). Three states, because a
roster whose rows carry assignments loses them even when nothing has
been answered:

| what the delete reaches | the label reads |
|---|---|
| assignments **and** responses | "Yes, delete these and their associated assignments and reviewer responses" |
| assignments only | "Yes, delete these and their associated assignments" |
| neither | "Yes, delete these" |

Observers and Relationships are always the third row: nothing
references them, so neither delete can reach an assignment or a
response, and a label implying otherwise would be describing a loss
that cannot happen.

**The acknowledgement rides with the tick.** The strip has one
checkbox, so where responses exist a hidden
`acknowledge_response_loss` field accompanies it rather than a second
box appearing on a row sized for one. The route still requires both
fields and still refuses without the tick that carries them.

An id from another session is a **400** and deletes nothing, including
the valid ids in the same request — `roster_bulk.bulk_delete` raises
before it deletes, matching `bulk_set_status`. A validated session is
invalidated first, as every roster mutation does; a non-editable one
refuses.

**The redirect keeps the filters and carries no `selected=`.** Every
other bulk action re-checks the rows it acted on; these rows no longer
exist. Services: `delete_selected` on each roster service, over
`app/services/roster_bulk.py`'s `bulk_delete`. Audit:
`reviewer.bulk_deleted` / `reviewee.*` / `observer.*` /
`relationship.*`, one event per call carrying `deleted`,
`cascaded_assignments` and `cascaded_responses`.

**The whole selection surface is gated on `is_editable`**
(Segment 19I Item 3) — `draft` or `validated`, which is what
`_require_editable` enforces on every route behind it. On `ready`,
`expired` and `archived` the row checkboxes, the selection-driven
buttons, the selected-count pill, the delete confirmation and the
bulk form they post to are all absent; the Status filter, the search
box, `Showing N of M` and Clear remain, because reading a finished
roster is legitimate. `ready` is open for receiving responses;
`expired` and `archived` are over. The route still answers 409 either
way — the page is a courtesy, not the guarantee. See
`spec/lifecycle.md` §5.

**Select-all takes the rendered window, not the match.** The header
checkbox toggles the rows on the page, and the page is capped at
200 / 500. A tag matching 600 rows renders 500 of them, so select-all
takes 500 and a delete leaves 100 behind **having looked complete** —
the sharp edge of the partition workflow the search exists to enable.
The confirmation therefore states the **selected** count and never the
match count. Two numbers say the rest, and on that same 600-row tag
they read: `Showing 500 of 600` above the table — the window is not
the match — against `500 of 500 selected` in the status row — every
rendered row is picked. Until Item 4 the hint sat in the status row
beside the gate and carried that job by adjacency; it now sits with
the table, and the pill states its own denominator, so the pairing
survives the move across two cards.

### The Danger Zone's `delete-all` (Segment 19I Item 3)

`POST /operator/sessions/{id}/{roster}/delete-all` deletes the whole
roster. It carries the **same two gates and the same three-state rule** as
the selected-rows delete — the wording differs, since this one names
counts ("the existing 12 reviewers and their associated…") where the
strip says "these" — and the same single tick: `confirm` plus, where
the roster's rows carry responses, a hidden
`acknowledge_response_loss`.

**That hidden field is a fix, not a convenience.** The route has
required the acknowledgement since it was written and **no roster
template ever sent it**, so on any session carrying a response
`delete-all` returned **400 with no path forward from the page**. The
Danger Zone must be able to delete a roster that has responses; it now
can.

**Observers' `delete-all` has no response-loss gate at all.** Nothing
references an observer, so the delete destroys no assignment and no
response — requiring an acknowledgement asked the operator to accept a
loss that cannot occur. Relationships never had the gate. The
requirement stands only where the cascade does, on Reviewers and
Reviewees.

The card itself is hidden whenever the session is not editable, with
the Upload card beside it — `spec/lifecycle.md` §5.

The list is **capped at 200 rows** (lifted to **500** when a
search or status filter is applied) — the cap is applied after
sort, so the visible window matches the operator's chosen order.
A "Showing N of M" hint renders when the cap or filter trims the
list.

### The Upload card's replace (Segment 19I Item 5)

`POST /operator/sessions/{id}/{roster}/import` replaces the whole
roster from a CSV. Where a roster already exists it carries the **same
two gates** as the two deletes above — `confirm_replace` must be
`"true"`, and on Reviewers and Reviewees an
`acknowledge_response_loss` where the session carries responses — and
the same single tick, with the acknowledgement riding as a hidden
field beside it.

**The confirmation names what the replace destroys**, in the same
three states and the same order as `delete-all`:

> Yes, replace the existing `3 reviewers` and delete the
> `1 assignment` and `2 reviewer responses`.

The assignment clause appears when the roster's rows carry
assignments, the response clause when the session carries responses;
with neither, the label is the bare "Yes, replace the existing
3 reviewers." Both pages say **reviewer responses**, Reviewees
included: the answers are the reviewers' whichever roster is being
replaced.

**The response clause and its hidden field are the fix, not a
convenience.** As with `delete-all`, the route had required the
acknowledgement since it was written and **no upload form ever sent
it**, so on any session carrying a response the replace returned
**400 with no path forward from the page** — reached by the documented
workflow, since editing a started session means reverting it to
`draft`, which is precisely where the Upload card reappears.

**Observers' import has no response-loss gate**, for the reason its
`delete-all` has none: nothing references an observer, so replacing
that roster destroys no assignment and no response. It keeps its
`confirm_replace` tick, which guards the observer roster itself.
Relationships' import never had the gate.

A parse-blocked upload re-renders the page from the same context, so
the label survives the error rather than losing its clause.

### Search matching and suggestions (Segment 19I)

**What the search box matches — per column, unioned.** A row is
kept when *any* of its columns matches:

| Column | Rule |
|---|---|
| Name — Reviewers / Reviewees `name`, Observers `display_name` (blank when unset) | substring, case-insensitive |
| Handle — Reviewers / Observers `email`, Reviewees `email_or_identifier` | substring, case-insensitive |
| Tag slots — `tag_1..3`; Observers have `tag_1` only | **whole value**, case- and surrounding-whitespace-insensitive |

Relationships applies the name and handle rules to **both sides**
of the pair, and the tag rule to the *row's own* pair-context
tags. Pair-context tags belong to the relationship rather than to
either member, so there is no side to attribute them to; matching
both removes the question rather than answering it. A row whose
reviewer or reviewee FK does not resolve is matched on the side
that does.

The rule is stated per column rather than per input on purpose.
An input-level rule ("exact if the input equals some tag value,
else substring") makes one input mean different things on
different rosters: searching `Ethan` would stop returning every
Ethan-by-name the moment any row acquired a tag of exactly
`Ethan`. Whole-value on tags is what keeps `Team A` from dragging
in `Team A2`; substring on names is what makes a partial name
useful. Prefix matching is not a middle ground, since `Team A` is
a prefix of `Team A2`.

**Picking a person from the typeahead.** When the input is
*exactly* one of the `"Name (handle)"` labels the page offered,
the parenthesized handle is exact-matched instead — otherwise
picking `Ana Lim (ana@example.edu)` would also return
`ana2@example.edu`. On Relationships that exact match is checked
against **either** side of the pair, as the substring rules are.
The trigger is "equals an offered label", not "ends in
parentheses": punctuation cannot tell a label from a tag value
like `Group (B)`, and a reviewee handle need not contain `@`. The
check runs against the **uncapped** label set, so a label past
the suggestion cap that an operator types from memory is still
recognized.

**What the typeahead offers.** The distinct **tag values** first,
then the `"Name (handle)"` people labels sorted
case-insensitively:

- One option per distinct *value*, not per row — a 1,000-row
  roster across 55 groups contributes 55 options.
- Built from the **unfiltered, uncapped** roster, so the list can
  name a partition whose rows currently fall past the display
  cap; picking it brings them into the window. This is the
  large-roster case the strip exists for.
- Tags lead because browsers filter a `<datalist>` in document
  order, so the partition values stay visible when both halves
  match.
- Two caps, kept separate so a long roster cannot crowd the tags
  out: `SEARCH_TAG_OPTIONS_CAP` (200) on the tag half,
  `REVIEWERS_DATALIST_CAP` (200) on the people half.

Relationships ships **one** merged list carrying both sides'
people and the pair-context tag values, not one list per
dimension. (The Edit / Add row's reviewer and reviewee pickers
are separate datalists with their own contract — see
"Relationships pickers" below.)

Status counts as a filter everywhere it appears: it lifts the cap
to 500 and it makes the **Clear** link render, so an operator who
narrows to Inactive has a one-click way back.

Predicates and option builders: `app/web/views/_filters.py`
(`filter_reviewers_rows` / `filter_reviewees_rows` /
`filter_observers_rows` / `filter_relationships_rows` and the
matching `*_search_options`).

## Per-row Edit / Add / bulk actions (Segment 15F)

**Selection.** The leftmost checkbox column is the sole selection
mechanism — rows carry no per-row action buttons. Button state:

| Selection | Edit | Inactivate / Activate | Add | Delete |
|---|---|---|---|---|
| 0 rows | disabled | disabled | enabled | disabled |
| 1 row | enabled | enabled | disabled | gated |
| ≥2 rows | disabled | enabled | disabled | gated |

**gated** = enabled only once the confirmation checkbox on the status
row is ticked, which the selection itself enables (Segment 19I). It is
the one button on this row that a selection alone does not light up.

**Edit** (`?edit_id=<id>`) and **Add** (`?add=1`) are
server-rendered states — no client-side DOM surgery. The target
row's cells render as `<input>` / `<select>`; Add prepends a
blank row at the top of the table. The Operator actions card
swaps its filter strip + button row for the focused Save /
Cancel pair. Editing a row's **status** to `inactive` /
`active` is the inactivate / reactivate path — there is no
separate per-row toggle. **Inactivate** / **Activate** flip the
`status` of every checkbox-selected row in one POST (reversible,
so no confirm checkbox).

After an Edit or a bulk action the redirect **preserves the row
selection** (`?selected=` query params re-check those rows) and
the **active search / status filter** (so the operator lands
back on the same filtered view, not the unfiltered list). CSV
bulk upload stays as the bulk-create path.

**Relationships pickers.** The Relationships Edit / Add rows
choose reviewer + reviewee via **name-or-email search-box
pickers** — a text `<input>` backed by a `<datalist>` of
`"Name (handle)"` options (inactive members suffixed
`— inactive`), not a native `<select>`. This scales past
1,000-row rosters; the submitted label resolves back to a roster
id server-side. Add is disabled with a hint when either roster
is empty — a pairwise relationship needs both sides.

Mutating service modules: `app/services/reviewers.py` /
`reviewees.py` / `observers.py` and the per-row mutators on
`relationships.py`.
Audit events: `reviewer.created` / `.updated` /
`.bulk_inactivated` / `.bulk_reactivated` and the parallel
`reviewee.*` / `relationship.*` / `observer.*` families
(all registered in `EVENT_SCHEMAS` in `app/services/audit.py`).

## Reviewers page (`session_reviewers.html`)

### Body grid (after the preview table, when not Activated)

Two-column `bottom-grid` placed **below** the preview table so
the operator's eye lands on the data first; the upload + delete-
all destructive actions cluster as a deliberate de-prioritised
section beneath:

- **Left:** `Upload Reviewers` card. Required CSV columns
  `ReviewerName`, `ReviewerEmail`; optional `ReviewerTag1..3`. POSTs
  to `/operator/sessions/{id}/reviewers/import`. When existing rows
  are present, surfaces a "Yes, replace the existing N reviewers
  (and delete K assignments)" confirm checkbox.
- **Right:** `Danger Zone` card with "Delete all reviewers". Only
  rendered when at least one reviewer exists.

### Preview table

| # | Column | Toggle? | Notes |
|---|---|---|---|
| 0 | (select) | — | Leftmost checkbox column — per-row select + header select-all; drives the Operator actions card |
| 1 | Name | — | `reviewer.name` |
| 2 | Email | — | `<code>{{ reviewer.email }}</code>` |
| 3 | Profile | ✓ | Conditional: rendered only when at least one reviewer has `profile_link` **or** while a row is being edited (`edit_mode`). Cell renders `<a href="…" target="_blank">link</a>` when populated; input in edit mode. `class="profile-col"`. Uses the operator-renamable `("reviewer", "profile_link")` label (default "Profile"). W11, PR #1756. |
| 4 | Tag1 | ✓ | `data-col-toggle="tag-1"` / `class="tag-col tag-col-1"` |
| 5 | Tag2 | ✓ | `data-col-toggle="tag-2"` / `class="tag-col tag-col-2"` |
| 6 | Tag3 | ✓ | `data-col-toggle="tag-3"` / `class="tag-col tag-col-3"` |
| 7 | Status | — | `reviewer.status` |
| 8 | Updated | — | `reviewer.updated_at` (`%Y-%m-%d %H:%M`) |

The `Show columns:` chip row sits in the top "Fields with data"
card; see "Preview tables (shared toggle pattern)" above for
default-state and persistence rules.

## Reviewees page (`session_reviewees.html`)

### Body grid (when not Activated)

Same two-column shape as Reviewers — Upload card on the left,
Danger Zone on the right. CSV header copy lists `RevieweeName`,
`RevieweeEmail` required; `PhotoLink`, `RevieweeTag1..3` optional.

### Preview table

| # | Column | Toggle? | Notes |
|---|---|---|---|
| 0 | (select) | — | Leftmost checkbox column — per-row select + header select-all; drives the Operator actions card |
| 1 | Name | — | `reviewee.name` |
| 2 | Email / Identifier | — | `<code>{{ reviewee.email_or_identifier }}</code>` |
| 3 | Photo | ✓ | Conditional: rendered only when at least one reviewee has `profile_link`. Cell renders `<a href="…" target="_blank">link</a>`. `data-col-toggle="profile"` / `class="profile-col"` |
| 4 | Tag1 | ✓ | `data-col-toggle="tag-1"` / `class="tag-col tag-col-1"` |
| 5 | Tag2 | ✓ | `data-col-toggle="tag-2"` / `class="tag-col tag-col-2"` |
| 6 | Tag3 | ✓ | `data-col-toggle="tag-3"` / `class="tag-col tag-col-3"` |
| 7 | Status | — | `reviewee.status` |
| 8 | Updated | — | `reviewee.updated_at` (`%Y-%m-%d %H:%M`) |

Whether the Photo column renders at all is governed by whether any
reviewee has a populated `profile_link` in the current preview
rows; when it renders, its `Show columns:` chip can hide / show it
like the tag columns. Position 3 sits between the identity columns
and the toggleable tag columns so the canonical column order is
consistent across reviewers / reviewees.

## Relationships page (`session_relationships.html`)

The home for **pair-level context** — the `relationships` table
seeded in Segment 13E PR 2 and lit up by this Setup page in
Segment 15D PR 2. One row per `(reviewer, reviewee)` pair within
a session, carrying three `tag_N` slots consumed by the rule
engine via the `pair_context.tag1` / `pair_context.tag2` /
`pair_context.tag3` predicate field names (15D PR 3 / PR 4)
plus a per-row `active` / `inactive` status.

### Body grid (when not Activated)

Same two-column shape as Reviewers / Reviewees — Upload card on
the left, Danger Zone on the right. CSV header copy lists
`ReviewerEmail`, `RevieweeEmail` required; `PairContextTag1..3`,
`Status` (`active` / `inactive`) optional. Defaults to `active`
when `Status` is omitted. POSTs to
`/operator/sessions/{id}/relationships/import` via
`save_relationships(...)`.

### Stats card

Single-line "Fields with data" card above the body grid:

> Fields with data: {pill, pill, …}

Mirrors the Reviewers / Reviewees stats card shape exactly — the
per-entity row count is **not** repeated here, since the chrome
status strip already carries it. Fields-with-data labels come
from `relationships.fields_with_data(...)` in
`app/services/relationships.py`.

### Preview table

| # | Column | Toggle? | Notes |
|---|---|---|---|
| 0 | (select) | — | Leftmost checkbox column — per-row select + header select-all; drives the Operator actions card |
| 1 | Reviewer | — | Resolved **name** stacked above `<code>email</code>`; sorts on name |
| 2 | Reviewee | — | Resolved **name** stacked above `<code>email_or_identifier</code>`; sorts on name |
| 3 | Tag1 | ✓ | `data-col-toggle="tag-1"` / `class="tag-col tag-col-1"` |
| 4 | Tag2 | ✓ | `data-col-toggle="tag-2"` / `class="tag-col tag-col-2"` |
| 5 | Tag3 | ✓ | `data-col-toggle="tag-3"` / `class="tag-col tag-col-3"` |
| 6 | Status | — | `<span class="pill pill-info\|pill-empty">active\|inactive</span>` per the canonical pill treatment (post-15 cleanup polish #768) |
| 7 | Updated | — | `relationship.updated_at` (`%Y-%m-%d %H:%M`) |

The `Show columns:` chip row sits in the top "Fields with data"
card; same default-state and persistence rules as Reviewers /
Reviewees per the shared section above.

The Status column is *not* toggleable — every relationship has a
status by design, and the pill treatment makes the value visually
distinct without needing an explicit hide affordance.

### Round-trip with the Relationships extract

The CSV column shape here is the inverse of
`app/services/extracts/relationships_extract.py` (8-column wide
CSV: `ReviewerEmail`, `RevieweeEmail`, `PairContextTag1..3`,
`Status` — same six columns the importer accepts). Round-trip is
byte-stable on the export's own output. The Extract Data card on
Session Home carries the corresponding Download button.

## Observers page (`session_observers.html`)

The Observers page is the third participant-roster Setup page. It
mirrors the Reviewers / Reviewees shape with a simpler model:
`email` is the required identity (NOT NULL, unique per session),
`display_name` is an optional human-facing label, and a single
`tag_1` is the only categorical axis (no `tag_2` / `tag_3`). The
page is **gate-hidden by default** — it is only reachable (and
only rendered in the Setup chrome navigation) when
`session.observers_enabled == True`.

### Body layout

The Observers page renders, top-to-bottom:

1. Chrome (`session-nav-card` partial with `Observers` highlighted
   in the Setup row).
2. Status strip (`session_setup_status_row` partial).
3. Yellow **lock card** (when the session is Activated) with the
   standard "revert to draft" Revert form.
4. **Cohort match rule editor (left) + Operator actions card
   (right)** — a `.bottom-grid` pair. Layout differs from
   Reviewers / Reviewees because the Observers page carries
   the per-observer rule-builder surface (no equivalent
   elsewhere).
   - **Cohort match rule editor**: see the dedicated section
     below. Visible whenever the session isn't `archived`
     (looser gate than the Operator actions card so the
     editor stays live mid-session). Hidden by default;
     the JS reveals it when ≥1 observer is checked.
   - **Operator actions card**: the shared search + filter
     strip — status filter (`all` / `active` / `inactive`) plus
     the tag-aware search box, over Observers' single `tag_1`
     slot — and the selection-driven
     Edit / Inactivate / Activate / Add-new-row button row.
     Same 200-row (500-when-filtered) cap. Same
     selection-preservation post-action redirect contract.
     Hidden whenever the session is not `is_editable` (Segment
     19I Item 3; `is_ready` until then) so the bulk roster
     actions can't fire once setup is closed. Its **checkboxes**
     keep the looser `not is_archived` gate — they drive the
     cohort rule editor.
   - When only one of the two should render (e.g. during
     `ready` only the cohort editor stays live), the other
     slot is an empty spacer so the grid stays half-and-half.
5. **Preview table** — always renders when observers exist (or
   when Add mode is active).
6. **Upload card (left) + Danger Zone (right)** — a
   `.bottom-grid` pair below the table, mirroring the
   Reviewers / Reviewees layout. Hidden whenever the session is
   not `is_editable` (Segment 19I Item 3; `is_ready` until then) or
   while a row is being edited / added.
   - **Upload card** (`#upload-csv`): CSV file in UTF-8, max
     5 000 rows. Required column: `ObserverEmail`. Optional
     columns: `ObserverName`, `ObserverTag1`. Destructive
     replace path (existing rows are wiped on import).
   - **Danger Zone card**: "Delete all observers". Only
     rendered when at least one observer exists.

There is no friendly-label editor (observers have no renamable
label slots) and no "Fields with data" pill row above the table —
the tag schema is fixed at one slot.

### Preview table

| # | Column | Toggle? | Notes |
|---|---|---|---|
| 0 | (select) | — | Leftmost checkbox column — per-row select + header select-all |
| 1 | Email | — | `observer.email` in `<code>` |
| 2 | Name | — | `observer.display_name`; `—` when null |
| 3 | Tag | — | `observer.tag_1`; `—` when null |
| 4 | Status | — | `observer.status` |
| 5 | Cohort | — | Friendly summary of `observer.cohort_rule` (e.g. `Reviewer: Mentor IS THE SAME AS Observer: Email + 1 more`); `—` when no rule saved |
| 6 | Updated | — | `observer.updated_at` (`%Y-%m-%d %H:%M`) |

### Cohort match rule editor

**The rule is what grants sight, not what narrows it.** An observer
whose `cohort_rule` is null or carries an empty `rules` list matches
**no** assignments — `observer_cohort.observer_has_rule` returns
`False`, `materialize_cohort_assignments` short-circuits to
`EMPTY_COHORT`, and the collation surface renders its empty-cohort
message rather than a section list. So an observer saved without a rule
is silently blind: the roster shows them `—` in the Cohort column and
nothing warns the operator. The page's guidance card states this
(Segment 19E rung 6b); `tests/integration/test_page_guidance.py`
pins that sentence to this behaviour so a flipped default fails a test
rather than turning the copy into a lie.

The Observers page is the only Setup page with a per-observer
rule-builder surface (no equivalent on Reviewers / Reviewees).
The editor reveals **inside the Operator actions card**, below
the filter / action button row, **when at least one observer
row is checked**. Layout mirrors Band 1 Link 2 on the
Instruments page (`new_model_rule_list("link2", …)` in
`instruments_index.html`):

- Left column (`+` add-rule + `AND` / `OR` combinator toggle).
- 3px vertical rule.
- One or more rule cells stacked. Each cell is two rows:
  - Row 1: cross-roster attribute dropdown (Reviewer /
    Reviewee tags — live tags only, friendly labels) +
    operator-cycle button (`IS THE SAME AS` /
    `IS DIFFERENT FROM` / `IS` / `IS NOT` / `CONTAINS` /
    `DOES NOT CONTAIN`). `pair_context.*` tags are accepted
    by the schema but dropped from the dropdown (PR #1812)
    since the pair-level join isn't implemented; legacy
    saved rules degrade safely via `ensureStaleOption`.
  - Row 2: operand dropdown (Observer attrs only — Name /
    Email / Tag 1) **only shown for the two cross-attribute
    ops**; otherwise a text input (for the four literal ops)
    + the `X` remove-rule button (disabled on the first
    cell). Cross-roster `Reviewer:` / `Reviewee:` operands
    are accepted by the schema but dropped from the dropdown
    (PR #1813), same pair-level deferral.
- Bottom-right: a primary `Save` button. `disabled` when no
  observer is checked; otherwise submits the editor state to
  every selected observer.

**Multi-select pattern.** The editor applies to all selected
observers at once. When the selection has a single shared
saved rule (including all-unset), the editor loads that rule
into the dropdowns. When the selection's saved rules differ,
the editor opens at the default state with the message *"The
selected observers currently have different cohort rules.
Saving replaces them all with the rule above."* — sitting
between the rule cells and the Save button. Saving always
overwrites every selected observer with whatever the editor
currently holds.

Storage: `observers.cohort_rule` (`sa.JSON()`, nullable). The
payload validates through
`app.schemas.observer_cohort_rule.CohortRuleSet` —
`combinator` (`AND` / `OR`) plus a list of per-cell
`{field, op, operand_tag, operand_value}` dicts. `NULL` =
operator hasn't authored a rule yet; an explicitly-saved
empty `{"combinator": "AND", "rules": []}` is distinct. See
`guide/archive/observers.md` "Match-axis schema — decided" for the
storage rationale.

Route: `POST /operator/sessions/{id}/observers/cohort-rule`,
gated on `require_observers_enabled_session` +
`_require_not_archived` — looser than the bulk-status routes
(`_require_editable`, draft + validated only) because cohort
rules govern observer visibility, not response data or roster
shape, so mid-session refinement (during `ready` / `expired`)
is the legitimate flow. Only `archived` is a hard stop.
Emits one `observer.cohort_rule_assigned` audit event per
affected observer (`refs={"observer_id": id}` +
`snapshot={"cohort_rule": …}`).

**Card layout.** The cohort editor renders as its own card,
visible whenever the session isn't `archived` (i.e. through
`draft` / `validated` / `ready` / `expired`). The bulk
Operator actions card above it still follows the standard
lock pattern — it hides once the session reaches `ready`.
Mid-session, the operator can refine cohort rules but can't
mutate the roster.

### CSV import

Route: `POST /operator/sessions/{id}/observers/import`. Parsed by
`csv_imports.parse_observer_csv` / `csv_imports.save_observers` in
`app/services/csv_imports.py`. CSV schema: `ObserverEmail`
required; `ObserverName`, `ObserverTag1` optional. Emits
`observers.imported` audit event on success.

Bulk delete: `POST /operator/sessions/{id}/observers/delete-all`
— emits `observers.deleted_all`.

## Out of scope for these pages

- **A row-local delete affordance (a ✕ on the row itself).**
  Superseded in part by Segment 19I: deleting one or several
  **selected** rows is no longer out of scope and is documented under
  "Deleting the selected rows" above. What remains out of scope is a
  *second*, row-local affordance for the same act, which would need
  its own justification now that the selection mechanism carries it.
- **Cross-entity validation.** Surfaced via the dedicated Validate
  page; not rendered inline on these pages.
- **Paging.** The 200-row (500-when-filtered) cap + the search /
  status filter cover the long-list case; there is no pager.
- **Assignments generation.** Moved to the Operations row in
  Segment 15D PR 6a — see `spec/operator_ui_concept.md` §5.

Per-row inline Edit / Add / bulk inactivate-reactivate and the
search / status filter strip — previously listed here as
deferred — **shipped in Segment 15F** (2026-05-15); see
"Operator actions card" and "Per-row Edit / Add / bulk actions"
above.

## Implementation pointers

- The shared visibility-toggle pattern lives inline per template
  (HTML structure + `<style>` + `<script>`). Each page picks its
  own `STORAGE_KEY` and CSS class names so they don't collide.
- Per-entity row counts and the raw "fields with data" CSV column
  names come from the helpers in `app/services/assignments/`
  (`reviewer_fields_with_data`, `reviewee_fields_with_data`) and
  `app/services/relationships.py`
  (`fields_with_data`) — keep them in sync with any new optional
  column added to the model + CSV importer. The route then runs
  the raw list through `views.friendly_fields_with_data`
  (`app/web/views/_setup.py`), passing the page's own required
  `surface` keyword, to resolve each column through the three-source
  order in "Shared body shape" item 3 before the pills render.
- Lifecycle gating is the existing pattern: a `card lock` at the
  top of the body when `is_ready`, and the Upload + Danger Zone
  cards conditionally rendered behind `{% if is_editable %}` on the
  four roster pages — `{% if not is_ready %}` until Segment 19I Item
  3, which is what left them rendering on `expired` and `archived`
  where both routes answered 409. The lock card itself is still keyed
  to `is_ready` alone, which is the known gap recorded in
  `spec/lifecycle.md` §5. The
  preview table renders unconditionally so the operator can read
  the current rows even while the session is Activated.
