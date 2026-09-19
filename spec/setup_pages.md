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
table** of the session's current rows. Three of those four share
the **column-visibility pattern** described below — Observers
carries a single tag and no chips — and that pattern is a shared
primitive, used by six operator tables in all. This spec is its
canonical description, alongside the per-page idiosyncrasies.

**Observers page gate.** The Observers Setup page routes
(`app/web/routes_operator/_setup_observers.py`) are gated by
`require_observers_enabled_session` — the page returns 404 until
the operator enables observers via the **User interface settings**
card on the Create Session form or Edit Session Details page. When
`session.observers_enabled` is `True` the page offers the same CRUD
operations as Reviewees — per-row edit, add, bulk status flips,
delete, CSV import. (Its **layout** matched Reviewers' too until
19P.1 moved that page; the operations are what this names.)

**Assignments is not a Setup page.** It sits on the Operations row
and is not a per-entity Setup primitive: pair-level context lives on
the first-class `relationships` table and is authored on the
Relationships page above, while the Operations Assignments page is
the materialized-derivative surface where the operator runs the rule
engine. See `spec/operator_ui_concept.md` §5 and
`spec/assignments.md` for that page's contract.

For the cross-page chrome contract (two-row navigation, status
strip, lock cards, principles P1–P4), see
[`spec/operator_ui_concept.md`](operator_ui_concept.md). For the
Quick Setup card on Session Home that bulk-uploads into the same
import paths these pages expose, see
[`spec/quick_setup_card_spec.md`](quick_setup_card_spec.md).

## Shared body shape

Every Setup Page renders, top-to-bottom. **The four roster pages
interpose one more card**, and their real order is in § *The roster
card and the Unlock panel*: guidance, then the **roster card** carrying
the index and the Unlock panel, then the preview table. Items 4 and 6
below describe what that panel holds and what it replaced.

0. **Page guidance** (`partials/_page_guidance.html`).
   A `<details class="card page-guidance">` — a **half-width
   card**, not an inline band, on five of the six pages. **Reviewers
   renders it full width** at the top of the page since 19P.1
   (`.page-guidance-wide`), where one measure would otherwise run to
   ~150 characters, so its open body sets two columns. **Closed by default**, showing one
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

   Width comes from the column the page puts it in. **The one
   exception is the macro's only argument**, `full_width` (default
   `false`), which **all four roster pages** pass — Reviewers since
   19P.1, Observers 19P.2, Reviewees and Relationships 19P.3: each left
   `.card-columns` and so has no column to take width from. A card spanning the page and its prose being laid out
   for that span are separate things — at full width one measure runs
   past 150 characters, so the argument gives the body `column-count:
   2`. Nothing
   else is parameterized, and the summary wording still is not. Closed, the card is
   one line: `padding: 12px 16px` and `align-self: start`, so a
   stretching grid cannot inflate it to a neighbour's height.

   **Every half-width card above the preview table shares one
   `.card-columns`, not a row grid — and not two of them** (Reviewers
   excepted since 19P.1; see the table below and the Reviewers section). Two
   containers look identical while everything is closed and still lose
   the point: growth in the upper one pushes both columns of the lower
   one down. A full-width card (the Activated lock card) therefore
   cannot sit between the pairs; `.card-columns` has no spanning slot,
   so it goes above the container, where its "cannot edit" notice
   reads anyway. (The lock card renders in **every** non-editable
   state, not only `ready`.) `.card-columns` is `1fr 1fr` with `align-items: start`, and
   each child is a *column* that stacks its own cards — so opening the
   guidance pushes down only what is below it in its own column, and
   the other column neither moves nor stretches. That is the whole
   reason the primitive exists; `.page-grid` and `.bottom-grid` lay
   cards out in rows and would drag the neighbour's height along.

   | Page | Placement |
   |---|---|
   | The four roster pages | **Not in the container.** The guidance card leads the page at **full width**, above everything else — Reviewers since 19P.1, Observers 19P.2, Reviewees and Relationships 19P.3. On the three that have a tag-label editor, `.card-columns` renders **only** as that editor's fallback home, in the two states the Unlock panel cannot render in; see § *The roster card and the Unlock panel*. The rest of the time it is absent rather than empty, and it never holds the guidance. On Observers, which has no label slots, it is absent in every state. The lock card sits above it, as elsewhere. |
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

   **Every one of the six pages carries the card**, with real copy —
   none is exempt.

   **The copy contract.** The shipped words live in the six templates
   and nowhere else — reproducing them here would make every wording
   tweak a two-file edit, and a second copy drifts. What is specced is
   what an edit is *held to*:

   1. **One paragraph per question, and no paragraph without a
      question.** There is no paragraph ceiling, because a count is the
      wrong instrument: an operator opening a disclosure wants the
      things they were missing, not the page's manual. Each paragraph
      earns its place by answering one question a reader actually has
      (*what is this? who must have an email? what do the tags do?
      what does upload cost me?*), and the card ends when the questions
      do. Five paragraphs of that is shorter to read than two that
      bundle four subjects.
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
   | Reviewers | The email is mandatory and should be the institutional MS365 account they sign in with, not contact detail; upload **replaces** the roster and clears assignments; `inactive` is the non-destructive alternative to delete; and an empty roster blocks `draft → validated` (`reviewers.empty`, error severity); and an upload or a delete also destroys **every relationship involving the rows it removes** (19O.5) |
   | Reviewees | An email is **optional** when you are only collecting data about someone — and **required, tied to their institutional MS365 account**, the moment they must see responses or summaries, since that is what a sign-in is matched against (the gap surfaces only as `reviewees.unreachable_for_results` on Validate); an empty roster blocks `draft → validated` (`reviewees.empty`, error severity); and an upload or a delete also destroys **every relationship involving the rows it removes** (19O.5) |
   | Relationships | The page is **optional** — a session works without any — and earns its keep only for context *not already derivable from reviewer and reviewee tags*; its three tags are a real assignment-rule namespace (`pair_context.tagN` → `Relationship.tag_N`, `spec/assignments.md` "Predicate vocabulary"), so they can affect who reviews, or does not review, whom — **but only once populated**, since `views._instruments._new_model_usable_tags` offers a namespace + slot in the Band 1 dropdowns only when some row fills it; and **this roster depends on the other two** — every row names one reviewer and one reviewee, so replacing or emptying either of those rosters deletes the rows that referenced them, irreversibly, which is why it is set last and re-set after any change to them (19O.5) |
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
   for a label that does not exist. (The repo's prose convention —
   `CLAUDE.md` → Project conventions — happens to agree today; the
   rule holds whether it does or not, and is what to reason from if
   the two diverge.) Reviewers and Reviewees
   run the same way — *who they are* → *what identifies them* → *what
   the tags do* → *what upload costs* → the Guide link on its own line.
   The two pages are deliberately near-parallel: an operator reads them
   minutes apart, and the sentences that differ are then the ones
   carrying the difference.

1. **Chrome** (`session-nav-card` partial — two-row top nav with the
   Setup row highlighted).
2. **Status strip** (`session_setup_status_row` partial) — counts
   pills per entity.
3. **Lifecycle gate cards** (whenever the page's own gate says the
   session is locked — `not is_editable` everywhere except Observers,
   which passes `lock_when = is_archived`): the shared `card lock`
   (`operator/partials/_roster_lock_card.html`), which branches per
   locked state — `ready` and `expired` carry an inline Revert
   form, `archived` links Unarchive and carries no control. The
   three branches and their copy are specified in
   `spec/lifecycle.md` §5. Sits directly under the
   status strip, so the yellow card immediately follows the status
   info card — the same status-info-then-yellow-lock pattern the
   Instruments page uses. On all four roster pages the card below it
   is the **full-width guidance card**; moving the guidance out of a
   column changed its width, not its place in the order, so this
   card's neighbour and ordering are unchanged by 19P. **Not
   Assignments**: that page carries no yellow `.card.lock` at all —
   the Workflow card's stepper already states the lifecycle, per
   `spec/operator_ui_concept.md` P4.
4. **Friendly-label editor.** The inline editor card via
   `operator/partials/_field_labels_editor.html`. Reviewers +
   Relationships render a 3-cell row; Reviewees a 2-row stacked grid
   (identity + tags, 6 cells). Save + Cancel pair in Secondary style,
   both starting `disabled` until the form is dirty (inline JS toggles
   via an initial-value snapshot). POST handlers in the per-entity
   setup modules (`app/web/routes_operator/_setup_reviewers.py` /
   `_setup_reviewees.py` / `_setup_relationships.py`) upsert / clear
   via `app/services/field_labels.py`. Observers has no label slots and
   no editor.

   Gated by `is_editable`: in every locked state its inputs render
   `disabled` and the Save / Cancel pair is suppressed, and
   `POST …/field-labels` answers 409. The lifecycle-gate card above
   carries the way out for that state.

   **On the roster pages it lives in the Unlock panel**, with
   `.card-columns` as its fallback home in the two states the panel
   cannot render in — § *The roster card and the Unlock panel*.

5. **Preview table card** — all four roster pages. Always renders when
   the entity is non-empty (or when Add mode is active), regardless of
   lifecycle state. A **leftmost checkbox column** drives the **row
   expander** injected beneath the selection (a header select-all
   checkbox toggles every visible row). Column headers render the
   resolved friendly label via
   `operator/partials/_field_label_header.html`; when an override is
   set, the canonical name appears as `.field-label-canonical` muted
   subtext below the friendly label and the sort `↕` button. While a
   row is being edited (`?edit_id=`) or a blank Add row is active
   (`?add=1`), that row's cells render as inputs / pickers — see
   "Per-row Edit / Add / bulk actions".

   The card opens with the **two-pane toolbar** carrying the filter
   strip, and the selection-driven controls render in the expander.
   Both are specified in § *Roster controls and their route contracts*.

6. **Nothing below the preview table.** The `.bottom-grid` that held
   the Upload + Danger Zone pair is absent from every roster page:
   both cards are in the Unlock panel. The gate is unchanged — the
   panel takes the same `is_editable`-and-not-editing condition the
   grid took (Observers' predicate differs; see its section) — and the
   two cards' route contracts below are untouched by the move. CSV
   upload stays the bulk-create path; the row expander covers
   single-row authoring.

## The roster card and the Unlock panel

**All four roster pages have this shape**, and since 19P.3 none of them
differs in kind — Reviewers arrived at 19P.1, Observers at 19P.2,
Reviewees and Relationships at 19P.3. It is stated once here because
four near-identical copies is how the eight pointer bugs 19P.1
cataloged were made; where a page genuinely differs, its own section
says so and this one names the axis.

Top-to-bottom, every roster page renders: chrome, the status strip, the
**lock card** when locked, the **full-width guidance card**, the
**roster card**, the `.card-columns` holding the tag-label editor *when
the Unlock panel cannot render*, and the **preview table card**.
Nothing below the table.

**The roster card** (`.card.roster-card#roster-card`) always renders.
It carries the **roster index** — the roster count, and one pill per
populated column showing that column's resolved friendly label and how
many rows hold a value — and, when the panel can render, the **Unlock**
control. **The card is not gated with the panel**: the index is
informational in every lifecycle state, which a mutating control is
not, so an operator on a locked session still reads the roster size and
which columns arrived.

**The Unlock panel** (`#roster-unlock-panel`) holds, in two columns,
the cards the page used to spread across `.card-columns` and the
`.bottom-grid` below the table. Each card's own contract is unchanged
by the move — the label editor is the same shared partial, and the two
destructive cards answer the same routes under the same gates,
specified in § *The Danger Zone's `delete-all`* and § *The Upload
card's replace*.

- **Suppressed, not disabled, when the page's own gate says the session
  is locked**, and likewise in edit / add mode. A locked page must
  carry no `Save labels` and no live `Upload` anywhere, so the whole
  panel stands down rather than rendering disabled controls.
- **The tag-label editor therefore has two homes**, one include in two
  positions on the exact complement of that condition: inside the panel
  when the panel can render, and in `.card-columns` when it cannot.
  That complement is **two different states, and the editor behaves
  differently in each** — the partial reads `is_editable`, not the
  panel's condition. On a **locked** session it renders disabled with
  its buttons dropped, which is what forces the second home at all: a
  locked page must still let an operator *read* the labels, since the
  rule is about not offering a control the route will refuse rather
  than about hiding information, and the roster index does not cover it
  (it pills only the columns that hold data). In **edit / add mode on
  an editable session** the same fallback renders **live**, with
  working inputs and a working `Save labels` — correctly, because the
  route would accept it. So "the editor outside the panel is read-only"
  is false, and a guard asserting no `Save labels` outside
  `#roster-unlock-panel` fails on any add-mode render. This is the only
  tenant `.card-columns` has on a roster page, and the container
  renders only in these two states — not empty the rest of the time,
  absent.
- **The `Danger Zone` renders only when the roster has rows** — and for
  a reason worth stating, because the route does *not* refuse an empty
  one: it answers 303 and writes an audit row reading "Deleted all 0
  reviewers". `_delete_all` calls `invalidate_if_validated(...)` before
  it counts anything, so an ungated Delete-all knocks a `validated`
  session back to `draft` while deleting nothing at all.
- **It keeps the `danger-zone` class** and its amber framing inside the
  panel, as it had outside one.

**Where the four pages differ, inside this section's subject.** The
**panel** differs on three axes, all of them Observers':

| Axis | Reviewers / Reviewees / Relationships | Observers |
|---|---|---|
| Suppression predicate | `is_editable` | `not is_archived` — every mutating observers route takes `_require_not_archived`, so on `ready` and `expired` both tenants are live and hiding them would withhold controls the routes accept |
| Column contents | tag-label editor over the `Danger Zone` left, `Upload` right | `Upload` left, `Danger Zone` right — the order its `.bottom-grid` already had, kept because with no label editor the columns cannot correspond |
| The `Lock` control | beneath the `Upload` card, which its right column always holds | **follows the card, not the column**: its right column holds the `Danger Zone`, which renders only on a roster with rows, so on an **empty** roster `Lock` moves to the left column beneath `Upload`. The template marks whichever stack holds a card and the toggle reads the marker; it never names a column. Not an edge case — it is first use, and the state `delete-all` redirects into |

**Observers differs elsewhere on the page too**, and those are not
this table's subject — they are listed once in its own § *Body layout*
so a reader has one place to count them: no `Show columns:` chips, no
sortable headers, a literal-labeled index that lists its one tag slot
even at zero, a lock card passed the matching predicate, and no
`acknowledge_response_loss` cascade on its destructive routes (which
Relationships also lacks).

**The roster card differs on one further axis, and it is
Relationships'** — its index can be empty, where the other three
always list identity columns. That is the card rather than the panel,
so it is stated in § *The roster index* below rather than added to a
table about the panel's tenants.

### The panel's start-open contract

**This section owns the contract; `spec/settings_inventory.md` § *URL
state* owns the param.** That table is where `?unlocked=1` is inventoried
with the app's other URL state, and it points back here rather than
restating the rule.

The panel ships `hidden` and the Unlock control opens it, but the
server decides what the page *arrives* as, because a panel that always
shipped collapsed would shut itself on every save. One rule, stated
about the panel rather than about each control:

> Whenever a control inside the panel answers, the page comes back with
> the panel open.

Two mechanisms implement it, and both are required because the controls
answer differently. The ones that redirect (`Save labels`, `Delete all
…`) and a **successful** import carry `?unlocked=1` on the redirect. A
**failed** import does not redirect at all — the parse and confirm
failures re-render the page in place with a 400 and its issue list, and
that list renders *inside* the upload card — so that path sets the
panel's open state server-side instead. Leave it closed and a failed
import answers with a collapsed panel and no visible errors.

**Relationships has two such in-place paths where the others have
one**: a blocked CSV, and the `missing_confirm` replace state the other
pages have no equivalent of. Both set the panel open.

**Opening is sticky; staying open is not.** `?unlocked=1` is a query
param, so every navigation that does not carry it closes the panel —
Search, Clear, a page turn, `Add new`, and the expander's `Edit` all
do. That is intended: those navigate the table, and the panel is not
what they act on. What the contract guarantees is narrower than "the
panel stays open until Lock" — it is that **a control inside the panel
never closes the panel it was used from.** The **Lock** control is the
only thing that closes it deliberately.

### Reachable without JavaScript

The panel is opened by an inline handler, so each control renders a
`<noscript>` link beside it — `?unlocked=1#roster-card` to open and
`#roster-card` alone to close, so both land on the card rather than at
the top of the document. `?unlocked=1` is a real server-rendered state
(it is what the redirects above use), so this links to behavior that
already exists. It restores what these pages could do before the move
and no more.

Both confirm-gated buttons are enabled only by `base.html`'s
confirm-pairing script, so with JS off `Delete all …` (always gated)
and a **replace** import (gated whenever the roster has rows) are both
unreachable — exactly as they were before the move, since `Upload`
shipped `disabled` on a non-empty roster then too. What the fallback
restores is the **empty-roster import**, plus the ability to read every
card the panel holds. The pairing script itself was rewritten at 19P.1
(2b step 1, delegated capture-phase), which changed how the gate is
wired and not whether it needs JS.

### The roster index

One row of readouts in the roster card: the roster count, and one pill
per column showing its label and how many rows hold a value.

**Whole-roster counts** — a search or a page turn does not shrink them.

**The readouts mirror the columns the preview table renders.** Identity
columns always, optional columns (`Profile`, each tag slot) only where
populated — which is exactly when the table renders them, because both
read the same `col_data` flags.

**Labels come from the same place the table's headers do, which is not
one place.** A renamable column goes through `field_labels.resolve_pair`,
so an override shows in the chip and the `<th>` together. An identity
column is a literal, because `field_labels.upsert` refuses an identity
slot — the built-in default is the only string either surface can
render, and routing it through the resolver would suggest otherwise.
Observers is literals throughout: it has no labels editor at all.

**Relationships lists its pair-context tags and nothing else**, and is
the only page whose index can be empty. Its `reviewer_id` /
`reviewee_id` are non-nullable integer foreign keys: a readout answers
"how many rows carry a value in this column", and for a column that
cannot be without one the answer is the roster total by construction —
which the roster count beside it already states. So an empty
Relationships roster renders the index's `none yet` branch, and the
other three never can.

## Preview tables (shared toggle pattern)

**The preview-count line** renders at the **top-left of the
preview-table card**, above the table, whenever the cap or a filter
has trimmed the list (`.table-showing-hint`). It belongs with the rows
it counts, reading left-to-right with the page — in the
operator-actions strip it sat roughly 950px from them. An untrimmed
list renders no line: "Showing 6 of 6" is noise.

It appears on all **seven** pages that preview rows — the four roster
pages, Assignments, Invitations and Responses — through **one** view
helper (`app.web.views.preview_count_line`) and **one** partial
(`operator/partials/_preview_count_line.html`), never a per-page
variant.

### The row pager

**The 200-row cap is a page size, not a truncation.** Each of the four
roster pages renders the `.table-pager-cluster` (`spec/ui_elements.md`
§10) **twice** — on the column-chip line above the table, and again
below it, because a 200-row table is several screens tall. It is five
cells — `«` first, `‹` back, a range menu, `›` forward, `»` last — so
any page is one move away whatever the roster size. Ranges, not page
numbers (`201–400`). The menu's summary names the range the operator
is on, and that range appears inside as a marker carrying
`aria-current="page"` rather than a link back to itself.

**Every page is one move away, whatever the roster size** — which is
why the cluster carries `«` first and `»` last rather than a sliding
window of numbered ranges. A window bounds the control's *width* and
leaves its *reach* at two pages per click, so crossing a long roster
costs page loads linear in its length.

`?offset=` selects the page. It is **clamped, never rejected**: past
the end lands on the last page and a negative lands on the first, and
an offset inside a page snaps down to that page's boundary. A link
that was valid before someone deleted forty rows is not an error page.

**The pager is suppressed whenever a search or status filter is
active.** The operator's own partition of the roster wins, and a
second partition stacked on it is two mental models for one table. A
filtered view therefore keeps the **500 cap** it has always had, and
keeps truncating for real — which is why the count line still has a
withheld branch.

**The pager carries no selection.** Selection is page-local: the
checkboxes act on the rows in view, and carrying a hidden selection
across a page boundary is how an operator deletes something they
cannot see.

**Editing a row off the current page lands the operator on that row's
page**, rather than prepending the row to whatever page they were on
(which is what the cap-era code did, having nowhere else to put it).
A filtered view, and a row the filter itself excludes, keep the
prepend.

**The wording follows from that.** Where the pager renders, the
operator can reach every row and the sentence says nothing — the
ranges already state the position. So the count line stopped being the
table's caption and became **the filter's**:

| State | Line |
|---|---|
| Filter active, under the cap | `Showing 37 reviewers.` |
| Filter active, capped | `Showing 500 of 900 reviewers, 400 more not shown.` |
| No filter | *(nothing renders — the pager speaks)* |

A count of exactly one takes the singular (`Showing 1 reviewer.`): the
sentence now puts the noun against the count rather than against the
pool, and a search matching one person is the commonest case there is.

The roster denominator went with the change — `Showing 3 of 1,240
reviewers.` became `Showing 3 reviewers.` — and so did the word
`matching`, which existed to tell the roster and the matching set
apart and has nothing left to disambiguate once `of M` can only mean
the second. **A filter that happens to match every row is still a
filtered view** and still reports (`Showing 1,240 reviewers.`): the
sentence and the pager read the same flag, so they cannot disagree
about which mode the page is in.

**All seven pages page**, so no page carries an unfiltered
"showing first N of M" notice.

**A filter matching nothing renders no count line, on any of the
seven.** Each page gates its whole preview card on the row list and
falls through to a "No … match the current filter." message
(`session_reviewers.html`'s `{% if reviewers or add_mode %}` …
`{% elif total_row_count > 0 %}`, and the same shape on the other
six). The line lives inside that gate, so there is no table for it
to caption. **Relationships has a third branch below those two** — an
empty roster that cannot yet be filled, § *The table toolbar*; the
no-match branch itself is the same on all seven. This is the template's doing, not the helper's:
`preview_count_line(shown=0, pool=0, …, is_filtered=True)` returns
`Showing 0 reviewers.` if it is ever called.

In every branch **M is the pool the numerator was drawn from** —
always the matching set, since the unfiltered branches say nothing;
and the withheld clause
appears only when the cap actually bit. The noun is the page's
subject: `reviewers`, `reviewees`, `relationships`, `observers`,
`assignments`, and — because those tables are one row per person —
`reviewers` on Invitations and `reviewees` on Responses. Counts carry
thousands separators.

The Reviewers, Reviewees, and Relationships preview tables carry
a **column-visibility chip row** that lets the operator hide
optional columns. The mechanism is a shared primitive, documented
here, and **six** operator tables opt into it — these three plus
Operations Assignments, Invitations and Responses. The three
non-Setup surfaces are specified in `spec/operations_pages.md`;
everything below describes the pattern itself.

A page opts in with **markup only**. The table carries an `id` and
`data-rrw-col-toggles="<storage-key>"`; each chip row carries
`data-col-toggles-for="<table-id>"`; each chip carries
`data-col-toggle="<slot>"`. The key rides on the *table* rather
than the row because one table may have several rows of chips —
Assignments groups its nine slots into three rows against one key.

The pattern:

- A `Show columns:` chip row sits **inside the preview-table card**,
  immediately above the count line and the rows it governs — never in
  a card of its own a grid away. Each chip is
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
- **A chip exists iff its column holds data somewhere in the
  session's roster** — and so does the column. A slot with nothing
  in it renders neither: no chip, no `<th>`, no `<td>`.

  **The question is roster-wide, and must be answered by a query, not
  by scanning the rendered rows.** A surface that scans its own row
  list is wrong whenever the cap or a filter bites — the Setup rosters
  render a filtered, 200/500-capped list, and Assignments samples
  unfiltered but capped at `PAIR_PREVIEW_LIMIT` — so a tag populated
  only past the cap reads as "no data".

  **There is no struck "no data in this column" chip.** The chip and
  its column go together: a struck chip was what hid the empty
  column, so dropping the chip alone would leave the empty column
  *visible*.

  **`edit_mode` overrides the gate** on the three roster pages: an
  operator adding or editing a row sees every tag column and can type
  into an empty one, which is the only way a tag ever stops being
  empty. The Photo column has always worked this way.
- The Reviewees row also carries a chip for the **profile-link
  column** (`data-col-toggle="profile"`, cells `class="profile-col"`).
  Chip and column are gated on the same `col_data["profile"]`, so
  neither can appear without the other. **Reviewers does not
  have this chip**, though it renders the same `profile-col` cells:
  there, the column's visibility is a server-side decision only. The
  asymmetry is deliberate and survives the shared extraction
  unchanged.
- Operator choice persists per browser via `localStorage` under a
  per-table key, which the primitive reads from the table's
  `data-rrw-col-toggles` attribute:
  - Reviewers preview: `rrw-reviewer-tag-visibility`.
  - Reviewees preview: `rrw-reviewee-tag-visibility`.
  - Relationships preview: `rrw-relationship-tag-visibility`.
  - Operations Assignments: `rrw-assignment-col-visibility`.
  - Operations Invitations: `rrw-invitation-tag-visibility`.
  - Operations Responses: `rrw-response-tag-visibility`.

  **The keys are fixed.** Renaming one silently resets every
  operator's saved columns on that page, so the extraction changed
  none of the four that predated it, and
  `tests/unit/test_column_visibility_primitive.py` pins all six.
  Full inventory in `spec/settings_inventory.md`.
- Stored choice wins over the data-driven default. Stored "hide"
  keeps a populated column hidden; stored "show" reveals an
  explicitly-toggled-on column on next load. A stored entry naming
  a slot the page no longer renders is ignored — the primitive
  iterates chips and consults storage, never the reverse — so
  hiding a tag, importing a roster without it, then importing one
  with it again restores the saved state.
- The shared JS targets `[data-col-toggle]` and binds every chip it
  finds. There is no `is-disabled` state: **every chip rendered is a
  live one**.

**What is shared, and what is not.** The behavior is one
implementation in `base.html`, never a per-template copy. The
**markup and the scoped `<style>` block stay
per-template**: each page's column shape differs enough (Reviewees
adds the profile-link chip; Assignments renders three chip rows)
that a Jinja macro would need a sprawling parameter list to say
less than the markup already does. The primitive is deliberately
ignorant of slot vocabulary — it toggles `col-hidden-{slot}` on
the table, and the page's own CSS decides which cells that hides.

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
  resolved member **name**, which is the prominent identity text in
  the cell), `tag_1` / `tag_2` / `tag_3`, `status`, `updated_at`.

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

## Roster controls and their route contracts

**The `Operator actions` card renders on no roster page.** Reviewers
retired it at 19P.1, Observers at 19P.2, Reviewees and Relationships at
19P.3. Its three parts went to three homes, and the split is the point
of the move — each part now sits with what it acts on rather than a
grid away:

| Was, in the card | Is now |
|---|---|
| Search + filter strip | the right pane of the preview table's **two-pane toolbar** (`.table-card-toolbar.is-split`) |
| Action row (`filter-actions`) | the **row expander**, injected beneath the selection |
| Status row (`filter-confirm`) — selected-count + delete confirm | the **row expander**, with the buttons it gates |

The `Upload` + `Danger Zone` pair that sat below the table in a
`.bottom-grid` moved too, into the Unlock panel — § *The roster card
and the Unlock panel*.

**The route contracts in the four sub-sections below are unchanged by
any of it, and always were page-independent** — `confirm` /
`confirm_replace` / `acknowledge_response_loss`, the failure modes, the
three-state wording. They govern every roster page regardless of which
control surface reaches them, which is why they are stated here once
rather than copied into four page sections. The card is gone; what it
posted is not.

### The table toolbar

The preview-table card opens with a **two-pane toolbar**
(`.table-card-toolbar.is-split`): the left pane says what the table is
showing — the column chips, the pager cluster, the count line — and the
right pane carries the **filter strip**. The panes are bare: card
geometry without a card's border, fill or padding.

The strip is a **Status** filter (`all` / `active` / `inactive`) and a
search box backed by a `<datalist>` typeahead, then a `Clear` link (only
when a filter is active), `Add new`, and the `Search` submit last. What
the search matches and what the typeahead offers is § *Search matching
and suggestions* below.

**Relationships carries the same Status filter as the rest** — it has a
row `status` and ships the Inactivate / Activate buttons that set it —
and its search reaches both sides of the pair without being told which,
so there is no "Search by" side-picker.

The strip greys out (`.is-locked`) and stops accepting clicks while a
row is being edited or added, and `Add new` renders disabled in that
state — the same lock the retired card's strip took.

`Add` is labeled **`Add new`** on all four pages. The one-row
constraint that shortened it went with `Delete`, which is in the
expander.

**Relationships has one more gate than the other three, and it is not a
lifecycle gate.** A `Relationship` names one `Reviewer` and one
`Reviewee` through non-nullable foreign keys, so with either roster
empty there is no pair to make: `Add new` renders disabled, and an
upload is no way round it — every row of the CSV fails validation
naming the side that is missing (*"Unknown reviewer … import reviewers
first"* / *"Unknown reviewee … import reviewees first"*, checked in
that order). The page states that in
two places and both read one answer
(`views.relationship_prerequisites`), so they cannot disagree about
whether a relationship can be made:

- the disabled button's `title=`, which **names the roster that is
  actually empty** rather than both — an operator with a full Reviewers
  roster is not told to add a reviewer;
- the empty state, which for this reason has **three** branches where
  the other three pages have two: no match for the filter, nothing yet
  *and nothing possible yet* (naming the missing roster and linking to
  its page), and nothing yet (the ordinary "Upload a CSV or add a row to
  get started"). The second branch is the state a `delete-all` on either
  roster leaves behind, and before 19O.5 rung 4 the page rendered the
  third one there.

Both read every row, active or not: an inactive reviewer is still a
reviewer a relationship can name, and `create_relationship` checks
membership rather than status.

### The row expander

The selection-driven button row is a **row injected into the table**
beneath the selected row, not a card beside it. It carries the selected
count and the controls — `Edit`, `Inactivate`, `Activate`, `Delete` and
the delete confirm — rendered client-side from the current selection.

**The status pair is not a pure relocation.** The retired card rendered
`Inactivate` and `Activate` **both, always**; the expander renders only
what is actionable for the selection — `Inactivate` when every selected
row is active, `Activate` when every one is inactive, both when the
selection is mixed. Net-new at 19P.1 and deliberate.

It renders the selected count as **bare text rather than a pill** — a
sibling of the confirm label, not inside it: the expander's own
background and the info-pill background resolve to the same primitive
in both themes, so a pill anywhere in the expander is invisible. The
lobby renders the same fact the same way.

**The delete gate is two-stage.** A selection enables the checkbox;
ticking the checkbox enables `Delete`, through the app-wide
`data-delete-confirm` / `data-delete-btn` pairing in `base.html`. With
nothing selected **both** are inactive — a tickable box with nothing to
confirm invites confirming before selecting. Changing the selection
**clears** the tick rather than merely disabling it, because "these"
names the selection as it stood when the box was ticked.

**Entering edit or add mode** replaces the row's cells with inputs, and
the `Save` / `Cancel` pair renders in an **expander bar directly
beneath the edited row** — styled as that row's own expander — rather
than below a divider in a card. There is no divider and no editor card:
the row is the editor.

**The preview-count line does not belong to either surface.** It sits
at the top-left of the preview-table card, with the rows it counts
rather than ~950px to their right, where the operator-actions strip put
it. See § *Preview tables*.

### Deleting the selected rows

`POST /operator/sessions/{id}/{reviewers|reviewees|observers|relationships}/bulk-delete`
— the selection-driven sibling of `bulk-inactivate`, one route per
page, taking the same `<entity>_ids` list and the same `filter_status`
/ `filter_q` round-trip.

**Two gates, both re-checked server-side.** The strip's checkbox is a
convenience; these decide:

1. `confirm` must be exactly `"true"`, or **400** — the same refusal
   the Danger Zone's `delete-all` uses. The expander's checkbox is a
   convenience, and unlike the Danger Zone's it is **not** `required`:
   it shares `<noun>-bulk-form` with `Inactivate` and `Activate`
   (`spec/ui_elements.md` §6 *Delete-confirm standard*).
2. When the **selected rows** carry saved responses,
   `acknowledge_response_loss` must be `"true"`, or **400** naming the
   exact number. `delete-all` can only ask whether the *session* has
   responses; a selected delete knows which rows are going, so it
   counts theirs. Selecting a reviewer with no answers therefore
   deletes without an acknowledgement even on a session full of them.

**What a delete takes with it** is mostly the ORM cascade:
`Reviewer` / `Reviewee` → their `assignments` → those assignments'
`responses`, plus a reviewer's `invitations`. **The cascade is not
sufficient on its own.** `email_outbox` references both `reviewers` and
`invitations` with no `ON DELETE` and no cascade from either parent, so
every reviewer delete first unlinks those two columns via
`invitations.detach_outbox`; without it the database rejects the
cascaded invitation delete. The outbox rows themselves are kept — they
are the email audit log, and each carries its own `to_email`, `subject`,
`body` and `sent_at`, so a sent email survives the recipient's roster
row. A surviving row with `reviewer_id IS NULL` **and** `sent_at` set is
exactly that: sent, recipient since removed — `spec/email_infra_options.md`
"Audit log" owns the column-level detail. **Observers
and Relationships cascade to nothing** — no table references them — so
their delete can never lose a response, their gate never fires, and
their strip never offers the acknowledgement. A page that offered it
would be describing a loss that cannot happen.

**The confirmation names what goes**, on the pattern of the
Instruments page's *"Yes, delete Instrument_1 and its associated
assignments and reviewer responses."* — where the name is that
instrument's operator-facing handle, per `spec/instruments.md`. Three states, because a roster
whose rows carry assignments loses them even when nothing has been
answered:

| what the delete reaches | the label reads |
|---|---|
| assignments **and** responses | "Yes, delete these and their associated assignments and reviewer responses" |
| assignments only | "Yes, delete these and their associated assignments" |
| neither | "Yes, delete these" |

**A fourth clause since 19O.5, and it is scoped differently from the
three above.** A reviewer or reviewee delete also destroys every
relationship referencing it, through an `ondelete="CASCADE"` foreign
key with no ORM collection on either parent — so nothing in Python
observes it and the app said nothing about it. Where the selection
carries any, the label gains *"and the relationships involving them"*.

**It reads the selection; the three rows above read the session.**
`delete_discards_assignments` is a session-wide flag, so those clauses
fire for a selection carrying none — a pre-existing imprecision, left
as it is. The relationship clause cannot afford it: each `<tr>` carries
`data-relationships` and the expander's script sums the ticked rows, so
a selection touching no pair stays silent. This is the same principle
§ *Deleting the selected rows* already states about the count — *"the
confirmation therefore states the **selected** count and never the
match count"* — applied to a clause rather than a number, and the same
one `acknowledge_response_loss` enforces server-side.

**"involving", not "between".** Every relationship pairs a reviewer
*with a reviewee*, so on a page listing one roster "between them" reads
as relationships among the selected rows, which cannot exist.

Observers and Relationships are always the third row: nothing
references them, so neither delete can reach an assignment or a
response, and a label implying otherwise would be describing a loss
that cannot happen.

**The acknowledgement rides with the tick.** The expander has one
checkbox, so where responses exist a hidden
`acknowledge_response_loss` field accompanies it rather than a second
box appearing beside it. The route still requires both fields and
still refuses without the tick that carries them.

An id from another session is a **400** and deletes nothing, including
the valid ids in the same request — `roster_bulk.bulk_delete` raises
before it deletes, matching `bulk_set_status`. A validated session is
invalidated first, as every roster mutation does; a non-editable one
refuses.

**The redirect keeps the filters and carries no `selected=`.** Every
other bulk action re-checks the rows it acted on; these rows no longer
exist. It also keeps the pager offset and lands on
`#<noun>-table-card` rather than a row, for the same reason — the
rows it would have landed on are the ones it deleted. Services: `delete_selected` on each roster service, over
`app/services/roster_bulk.py`'s `bulk_delete`. Audit:
`reviewer.bulk_deleted` / `reviewee.*` / `observer.*` /
`relationship.*`, one event per call carrying `deleted`,
`cascaded_assignments` and `cascaded_responses` — plus
**`cascaded_relationships`** on the two that can reach one, Reviewers
and Reviewees (19O.5). It is **omitted rather than zero** on Observers
and Relationships: nothing references either, so a key reading 0 would
describe a cascade that cannot exist, exactly as their confirmations
never mention assignments. The same field rides
`{roster}.deleted_all` and `{roster}.imported`, a replace being a
delete-and-re-add.

**The whole selection surface is gated on the page's own predicate** —
`is_editable` (`draft` or `validated`) on three pages, which is what
`_require_editable` enforces on every route behind it; `not
is_archived` on Observers, whose routes take `_require_not_archived`
instead (§ *Observers page* § *Lifecycle gate*). In the locked states
the row checkboxes, the selection-driven buttons, the selected count,
the delete confirmation and the bulk form they post to are all absent;
the Status filter, the search box, the preview-count line and `Clear`
remain, because reading a finished roster is legitimate. On the three
`is_editable` pages, `ready` is open for receiving responses and
`expired` / `archived` are over. The route still answers 409 either
way — the page is a courtesy, not the guarantee. See
`spec/lifecycle.md` §5.

**Select-all takes the rendered window, not the match.** The header
checkbox toggles the rows on the page, and the page is capped at
200 / 500. A tag matching 600 rows renders 500 of them, so select-all
takes 500 and a delete leaves 100 behind **having looked complete** —
the sharp edge of the partition workflow the search exists to enable.
The confirmation therefore states the **selected** count and never the
match count. Two numbers say the rest, and on that same 600-row tag
they read: `Showing 500 of 600 reviewers, 100 more not shown.` above
the table — a filtered view carries no pager and so still truncates,
and the line says the window is not the match — against
`500 of 500 selected` in the row expander, meaning every rendered row
is picked. Both now sit inside the preview-table card — the count line
in the toolbar's left pane, the selected count in the expander beneath
the rows — and the selected count still states its own denominator,
because a bare `500 selected` a table's height below `Showing 500 of
600` is not read as the same sentence.

### The Danger Zone's `delete-all`

`POST /operator/sessions/{id}/{roster}/delete-all` deletes the whole
roster. **What a delete takes with it** — the cascade, and the
`email_outbox` unlink a reviewer delete needs on top of it — is stated
once under *Deleting the selected rows* above and governs this surface
identically. It carries the **same two gates and the same label rule** as
the selected-rows delete — the wording differs, since this one names
counts ("the existing 12 reviewers and their associated…") where the
strip says "these" — and the same single tick: `confirm` plus, where
the roster's rows carry responses, a hidden
`acknowledge_response_loss`.

**The hidden field is load-bearing.** The route has always required
the acknowledgement, so a template that does not send it makes
`delete-all` return **400 with no path forward from the page** on any
session carrying a response — and the Danger Zone must be able to
delete a roster that has responses.

**Observers' `delete-all` has no response-loss gate at all.** Nothing
references an observer, so the delete destroys no assignment and no
response — requiring an acknowledgement asked the operator to accept a
loss that cannot occur. Relationships never had the gate. The
requirement stands only where the cascade does, on Reviewers and
Reviewees.

The card itself is hidden whenever the session is not editable, and so
is the Upload card — both are tenants of the Unlock panel, which is
suppressed as a whole. Observers' predicate is not `is_editable` at
all; see its § *Lifecycle gate*. `spec/lifecycle.md` §5.

The list is **capped at 200 rows** (lifted to **500** when a
search or status filter is applied) — the cap is applied after
sort, so the visible window matches the operator's chosen order.
The preview-count line renders when the cap or filter trims the
list; see "Preview tables (shared toggle pattern)" for its four
branches.

### The Upload card's replace

`POST /operator/sessions/{id}/{roster}/import` replaces the whole
roster from a CSV. Replacing deletes the outgoing rows, so **what a
delete takes with it** — stated under *Deleting the selected rows*
above — governs this surface too. Where a roster already exists it carries the **same
two gates** as the two deletes above — `confirm_replace` must be
`"true"`, and on Reviewers and Reviewees an
`acknowledge_response_loss` where the session carries responses — and
the same single tick, with the acknowledgement riding as a hidden
field beside it.

**The confirmation names what the replace destroys**, in the same
states and the same order as `delete-all`:

> Yes, replace the existing `3 reviewers` and delete the
> `1 assignment` and `2 reviewer responses` and the
> `3 relationships` involving them.

**This gate supplies its own verb, where `delete-all` does not.**
`delete-all` opens *"delete the existing N reviewers"*, which governs
every clause after it. This one opens *"**replace** the existing N
reviewers"*, which governs none of them — the assignments, responses
and relationships are destroyed and nothing re-creates them. `delete`
is introduced by the assignment clause when there is one, so the
relationship clause supplies it only when there is not:

> Yes, replace the existing `3 reviewers` and delete the
> `3 relationships` involving them.

Without that conditional the sentence reads *"replace … and the 3
relationships"*, promising a roster that comes back. Found by a cold
read at 19O.5 rung 2, in the state it is most often seen: relationships
are normally uploaded before assignments are generated, so the
assignment clause that would have supplied the verb is usually absent.

The assignment clause appears when the roster's rows carry
assignments, the response clause when the session carries responses;
with neither, the label is the bare "Yes, replace the existing
3 reviewers." Both pages say **reviewer responses**, Reviewees
included: the answers are the reviewers' whichever roster is being
replaced.

**The response clause and its hidden field are load-bearing.** As
with `delete-all`, the route has always required the acknowledgement,
so an upload form that omits it makes the replace return **400 with no
path forward from the page** on any session carrying a response — and
that state is reached by the documented workflow, since editing a
started session means reverting it to `draft`, which is precisely
where the Upload card reappears.

**Observers' import has no response-loss gate**, for the reason its
`delete-all` has none: nothing references an observer, so replacing
that roster destroys no assignment and no response. It keeps its
`confirm_replace` tick, which guards the observer roster itself.
Relationships' import never had the gate.

**A parse-blocked upload re-renders the page from a context the
import handler builds itself**, key by key, rather than from the one
the GET route builds — so every key the confirmation label reads has
to be repeated there by hand. Omitting one fails silently rather than
loudly: Jinja's `Undefined` is falsy in `{% if %}`, so the label takes
its no-loss branch on that path alone. Check the second builder
whenever a key is added.

### Search matching and suggestions

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

**Two more surfaces follow these rules by a different mechanism.**
The Session Lobby and the Archived page filter *client-side* — they
hide rows already rendered rather than re-querying — and 19O Item 7
entry 15 brought their matching onto the per-column rules above:
substring on the two identity columns, whole value on tags. Their
contract is in `spec/sessions_overview.md`; two things differ and are
worth knowing here.

- **No `"Name (handle)"` label.** That form works on these seven
  because the server exact-matches the parenthesized handle when the
  input equals a label it offered. A client-side per-column filter
  cannot do that, so the label would be a suggestion matching nothing.
  Names and codes are offered as themselves.
- **The session cap counts sessions, not strings**, each contributing
  up to two options, so a capped session never keeps one spelling of
  its identity and loses the other. The per-person cap here has no
  equivalent problem: one label is one person.

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

## Per-row Edit / Add / bulk actions

**Selection.** The leftmost checkbox column is the sole selection
mechanism — rows carry no per-row action buttons. Button state:

| Selection | Edit | Inactivate / Activate | Add | Delete |
|---|---|---|---|---|
| 0 rows | disabled | disabled | enabled | disabled |
| 1 row | enabled | enabled | disabled | gated |
| ≥2 rows | disabled | enabled | disabled | gated |

**gated** = enabled only once the confirmation checkbox on the status
row is ticked, which the selection itself enables. It is the one
button on this row that a selection alone does not light up.

**Edit** (`?edit_id=<id>`) and **Add** (`?add=1`) are
server-rendered states — no client-side DOM surgery. The target
row's cells render as `<input>` / `<select>`; Add prepends a
blank row at the top of the table. The Save / Cancel pair renders in
an expander bar beneath the edited row, and the toolbar takes the lock
the retired card's strip took: the filter form greys out and stops
accepting clicks (`.is-locked`), and `Add new` renders disabled.
Editing a row's **status** to `inactive` /
`active` is the inactivate / reactivate path — there is no
separate per-row toggle. **Inactivate** / **Activate** flip the
`status` of every checkbox-selected row in one POST (reversible,
so no confirm checkbox).

After an Edit or a bulk action the redirect **preserves the row
selection** (`?selected=` query params re-check those rows) and
the **active search / status filter** (so the operator lands
back on the same filtered view, not the unfiltered list). CSV
bulk upload stays as the bulk-create path.

**Every roster page carries three more** — Reviewers since 19P.1,
Observers 19P.2, Reviewees and Relationships 19P.3. The redirect also preserves the **pager offset** (`offset=`),
lands on a **fragment**, and on a create carries **`focus=<id>`**, so a row action taken mid-table comes back to
that row rather than to the top of the document — measured at 821px of
jump before the anchor, and answering with page 1 after an action on
page 2, because no caller passed the offset. The fragment is the first
acted-on row (`#reviewer-row-<id>`), or the table card
(`#reviewers-table-card`) where the action leaves no row to land on —
a delete. (Each page names its own row: `#reviewer-row-<id>`,
`#reviewee-row-<id>`, `#relationship-row-<id>`, `#observer-row-<id>`,
and the corresponding `#<page>-table-card`.) A fragment that cannot resolve is ignored by the browser and
lands at the top again, so the page also ships a fallback script that
catches a missing target and falls back to the card. **Two cases reach
that script** — a row the active filter excludes, and a row moved by a
cookie-held sort. **Observers reaches only the first**: its table is
not sortable. A delete is handled a step earlier, by the route:
having no row to land on it sends `#reviewers-table-card` itself, so
the script never fires on it. `focus=` exists because the fragment cannot cover a create: rows list
by id, so a new row appends past the end and on any roster over one
page is not on the page the form was submitted from — the anchor would
name a row the response never rendered. **All it does is relocate the
pager window** so the created row's page is the one rendered; the
fragment then resolves and lands on it. It places no caret — the
response is a plain list, not an edit state. (Caret placement is a
separate mechanism on a different flow: `?add=1` renders a blank row
*as an edit state*, and the landing script focuses that row's first
field. After a create there is no input to focus.)

**What a create or an edit refuses.** Two identity guards, on
every roster, at both entry points:

1. **Within the roster** — the mailbox is already on another row
   of the same roster (`reviewers` / `reviewees` by
   `email_or_identifier` / `observers`). Long-standing.
2. **Across the rosters** — the mailbox is held in *another*
   roster under a **different name**
   (`csv_imports.cross_table_identity_conflict`). Same email +
   same name stays legal, and is the self-review case. **The Add
   and Edit forms did not consult this until 19Q Item 7**, so
   they wrote the row the CSV importer refused; the rule had one
   home and only the import path could reach it.

Either raises the roster's `*OperationError`, and the form
re-renders at **400** in place with the message — the same shape
the within-roster duplicate has always had.

An **edit** keys on the *resulting* pair rather than on what
changed, so renaming a row into disagreement with its mailbox's
other holder is caught. A consequence worth stating: on a session
that already holds a conflicting pair, editing any field of
either row — a tag, say — answers 400 about the identity the
operator did not touch. That is deliberate. The conflict is
reported on Validate, the fix is a rename either way, and a guard
that ignored untouched identities would let a row be edited
around its own unresolved conflict indefinitely.

Rows already in the session when these guards landed are not
rewritten. The three `*.cross_roster_identity` Validate rules
report them (`spec/validate_page.md` §3.2).

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

### Body shape (19P.1)

The shared shape, with nothing page-specific in it: see § *The roster
card and the Unlock panel*. This page is the one the other three were
measured against, so the shared section reads as its description with
Observers' three differences named beside it.

Its panel holds the tag-label editor over the `Danger Zone` on the
left, `Upload Reviewers` on the right, and `Lock` beneath the upload
card. The suppression predicate is `is_editable`.

### Preview table

| # | Column | Toggle? | Notes |
|---|---|---|---|
| 0 | (select) | — | Leftmost checkbox column — per-row select + header select-all; drives the **row expander** below |
| 1 | Name | — | `reviewer.name` |
| 2 | Email | — | `<code>{{ reviewer.email }}</code>` |
| 3 | Profile | — | Conditional: rendered only when at least one reviewer has `profile_link` **or** while a row is being edited (`edit_mode`). Cell renders `<a href="…" target="_blank">link</a>` when populated; input in edit mode. `class="profile-col"`. Uses the operator-renamable `("reviewer", "profile_link")` label (default "Profile"). **Not toggleable** — unlike the Reviewees Photo column, this one has no chip and no `col-hidden-profile` rule; its visibility is decided server-side only. The asymmetry with Reviewees is deliberate. |
| 4 | Tag1 | ✓ | `data-col-toggle="tag-1"` / `class="tag-col tag-col-1"` |
| 5 | Tag2 | ✓ | `data-col-toggle="tag-2"` / `class="tag-col tag-col-2"` |
| 6 | Tag3 | ✓ | `data-col-toggle="tag-3"` / `class="tag-col tag-col-3"` |
| 7 | Status | — | `reviewer.status` |
| 8 | Updated | — | `reviewer.updated_at` (`%Y-%m-%d %H:%M`) |

The `Show columns:` chip row sits in the preview-table card, above
the rows; see "Preview tables (shared toggle pattern)" above for
which chips render and for the persistence rules.

#### The toolbar and the row expander (19P.1)

Both are the shared surfaces — § *Roster controls and their route
contracts*. This page has nothing of its own in either beyond its
identifiers: the add row carries `id="reviewers-row-editor"`, and an
edited row is reached as `#reviewer-row-<id>`.

## Reviewees page (`session_reviewees.html`)

### Body shape (19P.3)

The shared shape — § *The roster card and the Unlock panel* — on the
same terms as Reviewers, with none of Observers' three differences: the
panel holds the tag-label editor over the `Danger Zone` on the left,
`Upload Reviewees` on the right, `Lock` beneath the upload card, and
the suppression predicate is `is_editable`.

CSV header copy lists `RevieweeName`, `RevieweeEmail` required;
`PhotoLink`, `RevieweeTag1..3`, `Status` optional.

*This section said "same shape as Reviewers" until 19P.1, then stated
the pre-move shape outright because Reviewers no longer had it. Both
readings are now obsolete: the shape is genuinely shared again, so it
is stated once and this section carries the page's own facts. A pointer
is only a bug when it points at a different shape.*

### Preview table

| # | Column | Toggle? | Notes |
|---|---|---|---|
| 0 | (select) | — | Leftmost checkbox column — per-row select + header select-all; drives the **row expander** below |
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

The home for **pair-level context** — the `relationships` table. One
row per `(reviewer, reviewee)` pair within a session, carrying three
`tag_N` slots consumed by the rule engine via the
`pair_context.tag1` / `pair_context.tag2` / `pair_context.tag3`
predicate field names, plus a per-row `active` / `inactive` status.

### Body shape (19P.3)

The shared shape — § *The roster card and the Unlock panel* — on the
same terms as Reviewers and Reviewees: tag-label editor over the
`Danger Zone` left, `Upload Relationships` right, `Lock` beneath the
upload card, suppression on `is_editable`.

**Two in-place 400 paths where the others have one**, both of which
set the panel open server-side: a blocked CSV, and the
`missing_confirm` replace state no other roster page has.

**Its roster index lists pair-context tags only**, and is the only one
of the four that can be empty — see § *The roster index*.

CSV header copy lists `ReviewerEmail`, `RevieweeEmail` required;
`PairContextTag1..3`, `Status` (`active` / `inactive`) optional,
defaulting to `active` when omitted. POSTs to
`/operator/sessions/{id}/relationships/import` via
`save_relationships(...)`.

### Preview table

| # | Column | Toggle? | Notes |
|---|---|---|---|
| 0 | (select) | — | Leftmost checkbox column — per-row select + header select-all; drives the **row expander** below |
| 1 | Reviewer | — | Resolved **name** stacked above `<code>email</code>`; sorts on name |
| 2 | Reviewee | — | Resolved **name** stacked above `<code>email_or_identifier</code>`; sorts on name |
| 3 | Tag1 | ✓ | `data-col-toggle="tag-1"` / `class="tag-col tag-col-1"` |
| 4 | Tag2 | ✓ | `data-col-toggle="tag-2"` / `class="tag-col tag-col-2"` |
| 5 | Tag3 | ✓ | `data-col-toggle="tag-3"` / `class="tag-col tag-col-3"` |
| 6 | Status | — | `<span class="pill pill-info\|pill-empty">active\|inactive</span>` per the canonical pill treatment |
| 7 | Updated | — | `relationship.updated_at` (`%Y-%m-%d %H:%M`) |

The `Show columns:` chip row sits in the preview-table card, above
the rows; same rules as Reviewers / Reviewees per the shared section
above.

The Status column is *not* toggleable — every relationship has a
status by design, and the pill treatment makes the value visually
distinct without needing an explicit hide affordance.

### Round-trip with the Relationships extract

The CSV column shape here is the inverse of
`app/services/extracts/relationships_extract.py` (8-column wide
CSV: `ReviewerEmail`, `RevieweeEmail`, `PairContextTag1..3`,
`Status` — same six columns the importer accepts). Round-trip is
byte-stable on the export's own output. The Extract Setup card on the
**Extract data** Operations tab carries the corresponding Download
button (`spec/session_home.md` §2).

## Observers page (`session_observers.html`)

The Observers page is the third participant-roster Setup page. Its
**model** mirrors Reviewers / Reviewees, more simply:
`email` is the required identity (NOT NULL, unique per session),
`display_name` is an optional human-facing label, and a single
`tag_1` is the only categorical axis (no `tag_2` / `tag_3`). The
page is **gate-hidden by default** — it is only reachable (and
only rendered in the Setup chrome navigation) when
`session.observers_enabled == True`.

### Body layout (19P.2)

The shared shape — § *The roster card and the Unlock panel* — and this
page is the one that supplies all three of that section's difference
axes. Restated here only as far as its own reasons go:

- **The suppression predicate is `not is_archived`**, not the others'
  `is_editable`. Every mutating observers route takes
  `_require_not_archived` (§ *Lifecycle gate* below), import and
  `delete-all` included, so on `ready` and `expired` both tenants are
  live and hiding them would withhold controls their own routes accept.
- **`Upload Observers` is on the left and the `Danger Zone` on the
  right** — the mirror of the other three, deliberately. They put
  `Upload` right because their left column carries a tag-label editor;
  this page has no label slots, so the columns cannot correspond, and
  the order kept is the one the `.bottom-grid` already had.
- **`Lock` follows the card, not the column** — the empty-roster case
  described in that section's table.
- **`.card-columns` is absent in every state**, not just most: with no
  label editor there is no fallback tenant, and the cohort editor moved
  into the row expander at 19P.2 rung 5.

**And elsewhere on the page, which the shared section's table
deliberately does not cover.** Counted here so a reader has one place
to count them:

- **No `Show columns:` chips.** One fixed tag slot, so there is nothing
  to toggle; `observer_column_state` returns an empty `col_data`. The
  toolbar's left pane renders empty on an unpaged roster, which is the
  intended shape rather than a gap to fill.
- **No sortable headers.** The table carries no `data-rrw-sortable` and
  `_list_observers` orders by id, so this page is not one of the sort
  affordance's adopters (`spec/operator_ui_concept.md` § *Page
  taxonomy*). It is also why the row-landing fallback script reaches
  **one** case here and two elsewhere — a row the filter excludes, and
  no cookie-held sort to move one.
- **Its index is literal-labeled and lists `Tag` even at zero** —
  § *The roster index* below.
- **No `acknowledge_response_loss` cascade**, because nothing
  references `observers`; Relationships is the same. § *Deleting the
  selected rows*.

**The lock card's condition is this page's too.**
`_roster_lock_card.html` defaults to `not is_editable`; Observers
passes `lock_when = is_archived` so the card cannot read *"cannot be
modified while the session is ongoing"* above a roster that is still
live. The card and the controls agree about which states are locked,
which is the rule — the predicate they agree *on* is the one this
page's routes enforce.

### The roster index

The shared rule — § *The roster index* — resolves differently here
because the table does. Reviewers hides an unpopulated tag column, so
its index lists identity plus only the *populated* tag slots. Observers
hides none: one fixed tag slot, no column chips, so the index lists all
three — `Name` / `Email` / `Tag` — and a zero is the point rather than
an omission. `Tag (0)` says the CSV carried no `ObserverTag1` column.

Labels come from this page's own headers, not a resolver: it has no
`_field_labels_editor`, so `Tag` is the literal `<th>` string and a
resolver call would invent a label the table never shows.

### Lifecycle gate

**Observers is the stated exception to the four-roster rule** (see
`spec/lifecycle.md` §5). Its roster stays editable to `archived`: all
**eight** mutating routes take `_require_not_archived` — `create`,
`update`, the two bulk status actions, `bulk-delete`, `delete-all`,
`import` and `cohort-rule` — so every one of them accepts on `ready`
and `expired`. Seven were relaxed at 19P.2; `cohort-rule` already read
that gate.

The reason is what an observer *is*. They never appear in assignments,
never produce responses, and no readiness rule references them — so
freezing their roster at Activate protects nothing, while refining who
sees what mid-session is a legitimate flow.

`import` and `delete-all` were relaxed with the rest rather than
separately: the template gates both with one condition, so
`delete-all` could not become reachable on `ready` without `Upload`
rendering beside it, and a rendered control the server refuses is the
silent failure the relaxation exists to remove.


### Preview table

| # | Column | Toggle? | Notes |
|---|---|---|---|
| 0 | (select) | — | Leftmost checkbox column — per-row select + header select-all; drives the **row expander** below |
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
nothing warns the operator. The page's guidance card states this, and
`tests/integration/test_page_guidance.py`
pins that sentence to this behaviour so a flipped default fails a test
rather than turning the copy into a lie.

The Observers page is the only Setup page with a per-observer
rule-builder surface (no equivalent on Reviewers / Reviewees).

**It lives in the row expander** (19P.2 rung 5), the left pane of the
two-column panel the page injects beneath the selected rows — not in a
card above the table. The editor is selection-driven, so a card a grid
away from the rows it acts on was the defect, not the layout; its own
empty state said *"Select observers in the table below…"* while
rendering above them. The right pane carries the selected count, the
delete confirm and the row actions.

It is **server-rendered once into an inert `<template>` and cloned** on
each rebuild, because the attribute dropdowns carry live per-session
tag labels — rebuilding those option lists in a script would put the
same list in two places. A `<template>`'s content is parsed but not
rendered and its controls are not form-associated, so the ids and
`form=` attributes inside it do not collide with the clone.

Layout mirrors Band 1 Link 2 on the
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
    by the schema but **dropped from the dropdown** since the
    pair-level join isn't implemented; a saved rule naming one
    degrades safely via `ensureStaleOption`.
  - Row 2: operand dropdown (Observer attrs only — Name /
    Email / Tag) **only shown for the two cross-attribute
    ops**; otherwise a text input (for the four literal ops)
    + the `X` remove-rule button (disabled on the first
    cell). Cross-roster `Reviewer:` / `Reviewee:` operands
    are accepted by the schema but dropped from the dropdown, the
    same pair-level deferral.
- `Save` sits **inline immediately after the last rule cell's `X`**,
  anchored to that `X` so it trails the list as rules are added rather
  than floating under it. It is a **secondary** button, sized to the
  controls it sits among, and `disabled` **until the rule is dirty** —
  not until an observer is checked, which the panel's existence already
  guarantees. `+` and `X` rebuild the cell list, so `Save` is re-placed
  after every mutation; `X` on the last cell destroys and recreates it,
  which is why anything bound to `Save` is bound where it is built.

**Multi-select pattern.** The editor applies to all selected
observers at once. When the selection has a single shared
saved rule (including all-unset), the editor loads that rule
into the dropdowns. When the selection's saved rules differ,
the editor opens at the default state with the message *"The
selected observers currently have different cohort rules.
Saving replaces them all with the rule above."* — after the rule
cells, and so after `Save`, which is now inline in the last of them.
Saving always overwrites every selected observer with whatever the
editor currently holds.

**An unsaved rule edit is guarded, not silently discarded** (19P.2 rung
5a). The panel is rebuilt wholesale on every selection change, so an
edit typed but not saved is lost by anything that touches the
selection — and nothing auto-saves, the only write being the explicit
POST. Four in-page paths ask *"Discard unsaved changes?"* and restore
the control on a decline: the row checkbox, select-all, `Edit`, and the
three panel submits. Every other way off the page raises the browser's
unload warning. The deliberate actions set a flag first, so `Save` does
not warn about the edit it is persisting. Same contract and the same
sentence as Instruments' lock-with-unsaved-edits
(`spec/instruments.md` § *Save / Lock interaction*,
`spec/operator_button_audit.md` row 57) — one wording an operator meets
on two pages.

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

**Gate.** The builder renders wherever the expander does — not
`archived`, and not while a row is being edited or added, there being
no selection surface to clone into. The two-tier arrangement this
section used to describe, where the editor outlived the Operator
actions card above it, is gone: 19P.2 rung 2 relaxed every mutating
route to `_require_not_archived`, so the whole expander takes the one
gate and the operator can mutate the roster mid-session too.

### CSV import

Route: `POST /operator/sessions/{id}/observers/import`. Parsed by
`csv_imports.parse_observer_csv` / `csv_imports.save_observers` in
`app/services/csv_imports.py`. CSV schema: `ObserverEmail`
required; `ObserverName`, `ObserverTag1` optional. Emits
`observers.imported` audit event on success.

Bulk delete: `POST /operator/sessions/{id}/observers/delete-all`
— emits `observers.deleted_all`.

## Out of scope for these pages

- **A row-local delete affordance (a ✕ on the row itself).** Deleting
  selected rows is in scope and documented under "Deleting the
  selected rows" above; a *second*, row-local affordance for the same
  act would need its own justification now that the selection
  mechanism carries it.
- **Cross-entity validation.** Surfaced via the dedicated Validate
  page; not rendered inline on these pages.
- **Assignments generation.** It lives on the Operations row — see
  `spec/operator_ui_concept.md` §5.

## Implementation pointers

- The shared visibility-toggle **behavior** lives in `base.html`;
  each template supplies only the HTML structure and its scoped
  `<style>`, naming its own storage key and CSS classes so pages
  don't collide. A page that
  re-implements the toggle instead of opting in fails
  `tests/unit/test_column_visibility_primitive.py`.
- **Which columns hold data** is answered by
  `app/services/_queries.py::tag_slot_presence` — three
  `slot_has_data` calls, so three indexed `LIMIT 1`s — and re-keyed
  to the page's own chip slot names by `views.chip_slots`. The route
  passes one `col_data` map; **no template computes the flag**.
  `reviewer_fields_with_data` /
  `reviewee_fields_with_data` in `app/services/assignments/` survive
  for the Instruments page's `display_source_presence`, which unions
  them; keep those in sync with any new optional column added to the
  model + CSV importer.
- **Lifecycle gating on the four roster pages is one predicate,
  `is_editable` — `draft` or `validated` — and nothing may use a
  narrower one.** The Upload + Danger Zone cards, the friendly-label
  editor and the whole selection surface render behind
  `{% if is_editable %}`; the `card lock` at the top of the body
  renders behind `{% if not is_editable %}`. Because both halves read
  the same flag, the explanation and the controls cannot disagree.

  **19P.1 moved three of those controls on Reviewers without changing
  the predicate.** The Unlock panel takes the same `is_editable` (plus
  "not mid-edit"), so the three cards inside it are gated exactly as
  they were in their old homes — the panel is *suppressed*, not
  rendered disabled, precisely so a locked page still carries no
  `Save labels`. The one addition is the label editor's second
  position, which renders on the complement so a locked page can still
  show the labels without offering the control.

  **`is_ready` is the wrong predicate here, and the failure mode is
  silent.** It is true only in `ready`, so a control keyed to it stays
  live on `expired` and `archived` while its route answers 409 or 303
  — a page offering a Save the server will refuse, with no yellow card
  to explain why. Every gate on these pages reads `is_editable` for
  that reason, template and route alike (`_save_field_labels` in
  `app/web/routes_operator/_shared.py`). What the operator meets in
  every locked state:

  | State | `POST …/field-labels` | Card locked | Save button |
  |---|---|---|---|
  | `draft` | 303 | no | yes |
  | `validated` | 303 | no | yes |
  | `ready` | 409 | yes | no |
  | `expired` | 409 | yes | no |
  | `archived` | 409 | yes | no |

  The page offers what its routes will accept and nothing else, in
  every state. Renaming labels on a finished session means reverting it
  to draft, which is what the card already says.

  The card's three branches — one per locked state, `archived`
  carrying no control — are specified in `spec/lifecycle.md` §5; all
  four pages render it from
  `operator/partials/_roster_lock_card.html`. The preview table
  renders unconditionally so the operator can read the current rows
  even while the session is Activated.

