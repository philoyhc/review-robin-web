# Segment 19X — Refinements from browser runs

**Opened:** 2026-10-19 · **Theme:** small follow-ups the author's browser
runs turn up, one item each · **Related:**
`guide/things_to_check_in_browser.md`, `spec/setup_pages.md`,
`spec/ui_elements.md`

A standing home for refinements too small for a segment of their own
(author, 2026-10-19: "give it a generic name to hold multiple follow up
refinement items"). Items close independently; add one per finding. The
segment closes when the author says no more are coming.

## Item 1 — Delete all keeps its tick when the group-clear banner shows

### Opportunity

The round-2 run, step 19: on Relationships, the Danger Zone's
`Yes, delete the existing … relationships` tick comes back **unticked**
when Delete all is refused for clearing group answers. The operator
ticked it to get there; the upload card's replace tick already renders
ticked after the same ask (`spec/setup_pages.md` § *A chosen file
survives an ask*, "The replace tick"). The author's screenshot,
2026-10-19.

### Decision

Render the delete tick checked when the page answers a `delete_all`
group-clear ask. `base.html`'s confirm-pairing script syncs every
`data-delete-confirm` on load, so the paired `Delete all relationships`
button arrives enabled; the banner's `Yes, clear them` is still unticked
and the route still refuses without it. Rejected: leaving the tick and
enabling the button — the button's state would no longer follow its
tick.

### Blast radius (measured)

Taken 2026-10-19 at `8ae50337`.

| What | Count | Command |
|---|---|---|
| Templates with a `delete_all` group-clear banner | 1 | `grep -rln 'surface == "delete_all"' app/web/templates` |
| Routes rendering it | 1 | `grep -rn 'surface="delete_all"' app/web/routes_operator` |
| Tests on the delete-all ask | 1 | `grep -ln "delete-all" tests/integration/test_relationship_group_clear_asks_first.py` |

### Status

**Closed 2026-10-19, as planned, in one PR.** Driven in Chromium: after
the ask the tick is ticked and `Delete all relationships` live; with
`Yes, clear them` ticked the delete goes through. One `diff-reviewer`
read: three prose findings (the run order's step 19, a test comment, the
group-clear table's row), all fixed, plus an import-ask guard that the
Danger Zone's tick stays unticked. `spec-writer` at close: no divergence.

### PR ladder

1. **PR 1 — the tick.** `session_relationships.html` and a test in
   `test_relationship_group_clear_asks_first.py`; the spec line; a
   browser-check row. Must not touch the route.

### Definition of done

- The ask's page renders `data-delete-confirm="delete-all"` checked; a
  page without the ask renders it unchecked (test).
- `spec/setup_pages.md` § *The Danger Zone's `delete-all`* says so.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19X.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19X entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

- None.

### Out of scope

- The other rosters' Delete all: none asks about group answers.

### Doc impact

- `spec/setup_pages.md` — § *The Danger Zone's `delete-all`*: after a group-clear ask the delete tick renders ticked (Item 1).
- `guide/things_to_check_in_browser.md` — a row for the tick (Item 1).
- `guide/todo_master.md` — drop Item 1 from the 19X entry when it closes (Item 1).

## Item 2 — A Quick Setup banner lands just above the card

### Opportunity

A refused Quick Setup submit re-renders Session Home with the slot's
banner, but the page stays at the top unless the refused slot is
Reviewers. Measured in Chromium on 2026-10-19 (viewport 1400×800): a
refused Reviewers file scrolls to its banner; a refused Settings file
leaves `scrollY` at 0 with the card 989px down. `base.html` scrolls the
**first** `.banner-scroll-target` on the page, and the card renders one
per slot, hidden unless that slot was refused, so for any slot after
the first it scrolls a hidden element and nothing moves.
`session_detail.html`'s scroll-seat restore makes the same
first-match check. The author asked for the reload to land "one line
above quick setup card's top border".

### Decision

1. `base.html` scrolls the first **shown** `.banner-scroll-target`, not
   the first in the document; `session_detail.html`'s seat restore
   checks the same.
2. A banner may name a landing other than itself: the script scrolls the
   banner's closest `[data-banner-landing]` ancestor when there is one.
   The Quick Setup card carries it, with a `scroll-margin-top` of one
   line, so the card's top border sits a line below the viewport's top
   and every slot's banner is in view under it.

Rejected: scrolling the banner itself, as today. It works once (1) is
fixed, but lands mid-card with the card's heading and the slots above
the refused one out of view, which is what the author asked to change.

### Blast radius (measured)

Taken 2026-10-19 at `8ae50337`.

| What | Count | Command |
|---|---|---|
| Templates using `banner-scroll-target` | 10 | `grep -rln "banner-scroll-target" app/web/templates` |
| Scripts that pick the banner (`base.html`, `session_detail.html`; `instruments_index.html`'s has no Quick Setup card) | 3 | `grep -rn "querySelector('.banner-scroll-target')\|querySelector(\".banner-scroll-target\")" app/web/templates` |
| Tests naming the class | 3 | `grep -rln "banner-scroll-target" tests --include=*.py` |

### PR ladder

1. **PR 1 — the landing.** Both scripts, the card's attribute, the CSS
   margin, a browser test (a refused Settings file lands with the card's
   top a line below the viewport); the spec; a browser-check row. Must
   not touch the banners' markup beyond the attribute.

### Definition of done

- A browser test refuses a Settings file on Session Home and finds the
  card's top between 0 and one line below the viewport's top.
- `spec/ui_elements.md` §5a *Auto-scroll on display* names the first
  shown banner and the landing attribute.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19X.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19X entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

- None.

### Status

**Closed 2026-10-19, in one PR.** Scope moved: the Owners card opts in as
a landing too. The `diff-reviewer` read measured its banner, which sits
after the Quick Setup card on Session Home, scrolling itself and cropping
the card's heading once the first match no longer stopped on a hidden
Quick Setup banner; it has a browser test of its own. The landing holds
as far as the page can scroll, so on a window taller than the rest of
the page the card shows lower down; the spec and rows say so. The read's
other findings were wording (two stale "scrolled to the banner" rows, a
§5a reason) and are fixed. `spec-writer` at close: no divergence; two
sentences made exact (the New session page carries the Quick Setup
landing; the script runs once the document has parsed).

### Out of scope

- Other pages' banners: they keep scrolling to themselves; only a card
  that opts in with the attribute lands elsewhere.

### Doc impact

- `spec/ui_elements.md` — §5a *Auto-scroll on display*: the first shown banner, and `data-banner-landing` (Item 2).
- `guide/things_to_check_in_browser.md` — a row for the landing (Item 2).
- `guide/todo_master.md` — drop Item 2 from the 19X entry when it closes (Item 2).

## Item 3 — Relationships' Delete all names the group answers on its tick

### Opportunity

The author's browser check of Item 1, 2026-10-19: Delete all went
through with no banner, and the author asked that Relationships' Danger
Zone "just follow Reviewers and Reviewees", whose one tick names what
goes ("Yes, delete the existing 5 reviewees and their associated 30
assignments and 5 reviewer responses"). Relationships named only the
relationships, and found out about the group answers it clears after
the operator pressed the button.

### Decision

The tick names the answers up front: "Yes, delete the existing 12
relationships and the 4 reviewer responses on the groups they form",
the clause only when the count is above 0, and the count rides with the
tick as a hidden `acknowledge_response_loss`, as on Reviewees. The page
counts with `relationships.delete_all_group_loss`, which runs the delete
in a savepoint and rolls it back. The route is unchanged: the Item 1 ask
stays for a count that moved after the page rendered. Rejected: a pure
count without the dry run — which groups clear is decided by the
regrouping (`clear_changed_groups`), and a second copy of that rule
would drift from it.

### Blast radius (measured)

Taken 2026-10-19 at `6d84b80d`.

| What | Count | Command |
|---|---|---|
| Templates with a Delete all tick (only Relationships changes) | 4 | `grep -rln 'data-delete-confirm="delete-all"' app/web/templates` |
| Routes rendering the Relationships page | 1 | `grep -rn "def _render_relationships_page" app/web/routes_operator` |
| Specs naming `delete-all` | 7 | `grep -rln "delete-all" spec` |

### Status

**Closed 2026-10-19, in one PR.** Driven in Chromium on the round-2
`R groups` setup: the tick reads "… 12 relationships and the 4 reviewer
responses on the groups they form", and one tick deletes with no
banner. Planned, built and closed in the same PR. One `diff-reviewer`
read: the dry run leaks nothing and no path sends two counts; it found
the count also ran on row-editor renders (now skipped), two spec lines
to sharpen, and run-order steps 19 and 21 and a checklist row still
describing the ask; all fixed. Judgment call: on Postgres the dry run's
DELETE takes the session's relationship row locks for the length of the
GET, so a page load can wait on a concurrent import; accepted for a
single-operator Setup page. `spec-writer` at close: one word (the
banner's tick carries the field). The Item 2 checklist section went in the
same PR, the author having cleared it.

### PR ladder

1. **PR 1 — the named tick.** The service count, the page's context,
   the template's clause and hidden field, tests, the two specs, a
   browser-check row. Must not touch the route.

### Definition of done

- The page names the count and sends it; the page's own form deletes
  without an ask; a page with nothing to clear names only the
  relationships; a moved count still asks (tests).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19X.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19X entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

- None.

### Out of scope

- Reviewers and Reviewees: already name their losses.

### Doc impact

- `spec/setup_pages.md` — § *The Danger Zone's `delete-all`*: Relationships' tick names the group answers; the group-clear table's delete-all row is the moved-count case (Item 3).
- `spec/lifecycle.md` — §3.2's route table: delete-all's refusal is the moved-count case (Item 3).
- `guide/things_to_check_in_browser.md` — the Item 1 section becomes Item 3's row (Item 3).
- `guide/todo_master.md` — Item 3 in the 19X entry (Item 3).

## Item 4 — An instrument nobody in view takes part in shows only its line

### Opportunity

The author's screenshot, 2026-10-20: on an observer's `/collation`, an
instrument whose cohort takes in no one renders the full table, with "0
Reviewers in cohort", "0 Reviewees in cohort", every statistic "—", and
under it "No one in your view takes part in this instrument, so there
is nothing to download." The author: the table is dispensable there;
show just the explanation line. (A Summarized instrument showed its
"Only the summary above is shown" note there instead of that line.)

### Decision

When the cohort takes in no assignment (`cohort_has_rows` false), the
card shows its heading, description and the line, and no table; in any
identification mode, since an empty cohort has nothing to summarize
either. Rejected: keeping the table with a note above it — every cell
in it is empty by construction.

### Blast radius (measured)

Taken 2026-10-20 at `5d0b6a07`.

| What | Count | Command |
|---|---|---|
| Templates reading `cohort_has_rows` | 1 | `grep -rln "cohort_has_rows" app/web/templates` |
| Tests on the line | 1 | `grep -rln "data-collation-nothing-to-download" tests` |
| Specs describing the table's rows | 3 | `grep -rln "Row 3 conditional" spec` |

### Status

**Closed 2026-10-20, in one PR.** As planned; a Summarized
instrument with an empty cohort now shows the same line rather than its
summary-only note (pinned by a test). One `diff-reviewer` read: it
confirmed the Download button and the non-empty Summarized case are
unchanged, and found two stale view docstrings (comment-only edits to
the view), `spec/visibility_policy.md`'s observer row, a wrong test
count here, and a checklist row whose one setup could not show both
cases; all fixed. `spec/audience_and_identity_model.md` describes the
3-row table only in general terms and stays as is. `spec-writer` at
close: both spec rows now say "in any identification mode" and that the
heading and description stay.

### PR ladder

1. **PR 1 — the line alone.** `reviewer/collation.html`, the test in
   `test_observer_collation_body.py`, the spec line, a browser-check
   row. Must not touch the view.

### Definition of done

- An empty cohort's card renders the line and no table (test).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19X.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19X entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

- None.

### Out of scope

- The reviewee `/results` page: it renders only sections with values.

### Doc impact

- `spec/participant_model.md` — §4's observer collation row: an empty cohort shows only the line (Item 4).
- `spec/visibility_policy.md` — the Observer `/collation` body row: an empty cohort shows only the line (Item 4).
- `guide/things_to_check_in_browser.md` — a row for the line (Item 4).
- `guide/todo_master.md` — Item 4 in the 19X entry (Item 4).

## Item 5 — A Create with staged files lands at the top of Session Home

### Opportunity

The author, 2026-10-20: after Create, Session Home's address "sometimes"
gains a fragment such as `#quick-setup-settings`. It is every Create
that staged a file: the success redirect named the last slot that ran
(`#quick-setup-<slot>`, Settings whenever a settings file was staged), so the page
opened scrolled to the bottom of the Quick Setup card. A refused file
lands on its slot (`?quick_setup_error=…#quick-setup-<slot>`) and a
bare Create on `?editing=1#session-config`.

### Decision

A Create whose staged files all applied lands at the top of Home with
no fragment (the author's pick of three, 2026-10-20). Unchanged: the
refused-file landing (the banner is there), the bare Create (the
details card is what comes next) and Home's own Submit (the operator is
working in the card). Rejected: `#quick-setup`, the card's top — the
new session as a whole is what Create made.

### Blast radius (measured)

Taken 2026-10-20 at `ea454951`.

| What | Count | Command |
|---|---|---|
| Redirects in the Create module (only `create_session`'s success one changes) | 5 | `grep -c 'RedirectResponse(' app/web/routes_operator/_quick_setup.py` |
| Test files posting a Create, most as fixtures | 209 | `grep -rlzP --include=*.py 'post\(\s*"/operator/sessions"\s*,' tests/integration \| wc -l` |
| Specs on the New-session variant | 2 | `grep -rln "Create session submits the uploads\|New-session variant" spec` |

### Status

**Closed 2026-10-20, in one PR.** As planned. No test pinned the old
fragment; the Create-with-files test now pins the bare Home address.
One `diff-reviewer` read: nothing depends on the old fragment (no
browser test stages files on Create; the slot-fragment asserts are all
Home's Submit); it found two blast-radius counts that did not measure
what they said (re-taken above), this Status, and
`spec/operator_ui_concept.md`'s Create landing, which also missed the
bare Create's `?editing=1#session-config` (stale since 18R); all fixed.
`spec-writer` at close: no divergence.

### PR ladder

1. **PR 1 — the landing.** `create_session`'s success redirect, the
   test, the spec sentence, a browser-check row. Must not touch Home's
   Submit or the refusal path.

### Definition of done

- A Create with staged files that apply redirects to Home's bare
  address (test).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19X.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19X entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

- None.

### Out of scope

- Other redirects to Home that carry a fragment (Owners, the details
  card, a Quick Setup Dismiss): each lands on the card it acted on.

### Doc impact

- `spec/quick_setup_card_spec.md` — § *New-session variant*, Submission semantics: a successful Create lands at Home's top (Item 5).
- `spec/operator_ui_concept.md` — the Create form's landing: Home's top with files, the details card without (Item 5).
- `guide/things_to_check_in_browser.md` — a row for the landing (Item 5).
- `guide/todo_master.md` — Item 5 in the 19X entry (Item 5).

## Item 6 — Date-time boxes take 24-hour text, with a picker and a clear

### Opportunity

The author, 2026-10-20: Session Home's locked details card shows times
in 24-hour form (every display does: `format_datetime`,
`%Y-%m-%d %H:%M`, the audit log included), but the edit boxes, and the
New session page's, show AM/PM. And a box empties only segment by
segment (year, month, day, hour…), though a whole value pastes in. Both
come from the browser's native `datetime-local` control, which follows
the computer's regional time format and has no clear-all; HTML cannot
set either.

### Decision

The author's pick of three, 2026-10-20: each of the 9 boxes becomes one
shared control, a text box reading `YYYY-MM-DD HH:MM` (24-hour, as the
displays), so paste, select-all and delete work as in any field; beside
it a calendar button that opens the browser's own picker (a visually
hidden native `datetime-local`, opened with `showPicker()`, its choice
written into the text box) and a ✕ that clears it. One Jinja macro, one
script in `base.html`, one CSS class. Rejected: keeping the native box
and adding ✕ (AM/PM stays wherever the region is 12-hour), and a
date-picker library (no front-end dependencies, `CLAUDE.md`).

### Semantics

- **Format.** The box renders and submits `YYYY-MM-DD HH:MM`; the
  server accepts `T` or a space between date and time (`fromisoformat`
  does) and compares a box with its seeded text after normalizing the
  separator, so Session Home's "box unchanged" rule (`tz_converted`,
  findings L8) holds.
- **Bad text.** Unparseable text answers as an unparseable
  `datetime-local` does today (the route's 4xx); the box's `pattern`
  flags it before submit.
- **Empty** clears the field, as now. Seconds are not accepted.
  *(At build: the box's `pattern` alone did not make that true — a
  direct POST, or the lobby's script-posted End, reached
  `fromisoformat`, which reads seconds, a bare date or an offset; so
  `parse_local_datetime` now refuses any other shape.)*
- **Without script** the text box still types and submits; the picker
  and ✕ render hidden and the script reveals them.
- **Ordering.** Create's Start ≤ End ≤ Release-from ≤ Release-until
  check moves from `min`/`max` (native boxes only) to
  `setCustomValidity` on the text boxes; the server's
  `validate_schedule_ordering` stays the gate.
- **The picker's pop-up** is the browser's and may still show AM/PM;
  what it writes into the box is 24-hour.

### Blast radius (measured)

Taken 2026-10-20 at `642a8827`.

| What | Count | Command |
|---|---|---|
| Date-time inputs (`base.html`'s style selectors aside, 9 boxes in 3 templates) | 13 | `grep -rn 'type="datetime-local"' app/web/templates --include=*.html \| wc -l` |
| `format_datetime_local` callers | 14 | `grep -rn 'format_datetime_local' app --include=*.py --include=*.html \| grep -v 'def format_datetime_local' \| wc -l` |
| `parse_local_datetime` callers | 5 | `grep -rn 'parse_local_datetime(' app --include=*.py \| grep -v 'def parse_local_datetime' \| wc -l` |
| Test files naming either | 9 | `grep -rln --include=*.py 'datetime-local\|format_datetime_local\|parse_local_datetime' tests \| wc -l` |
| Specs naming `datetime-local` | 7 | `grep -rln 'datetime-local' spec docs \| wc -l` |

### Status

**Closed 2026-10-20, in two PRs as laddered** (rung 1 #3163, Session
Home; rung 2, Create, the lobby's End, specs). All nine boxes are the
`datetime_field` macro; no bare `datetime-local` renders
(`tests/integration/test_datetime_fields.py`).

One cumulative `diff-reviewer` read, at rung 2, on `c6912062..`. It
found, all fixed in rung 2:
- **High:** a picked value stayed in the hidden picker, under the
  `min`/`max` the ordering check moves, and blocked Create's submit on
  an invisible control after a zone change or a retype. The picker now
  carries `form=""` and empties once its choice is written.
- **Medium:** the server read any `fromisoformat` shape (above); and
  the "picker fill" browser test the ladder named was missing.
- **Low:** the picker's 1px CSS lost to the text-input rules
  (specificity raised); the lobby End's `pattern` could block the list
  form's Archive / Delete (the box carries `form=""`); the buttons'
  names now carry the field's label.

Also at build: the Create check mirrors the server pair by pair
(`validate_schedule_ordering`, in its words) rather than the old
nearest-filled-box bounds; a field added after load wires through
`window.rrwDateTimeFields`. Rung 1's first push compared an aware
Postgres instant with a naive one (`ci-postgres` red; fixed).
`spec-writer` at close aligned all seven Doc impact specs, with no
code divergence.

### PR ladder

1. **PR 1 — the control, on Session Home.** The macro, script and CSS;
   the box format and the separator-tolerant parse and comparison;
   Session Home's 4 boxes and the timezone-conversion script; unit,
   integration and browser tests (paste, clear, picker fill, a zone
   change, an unchanged Save). Must not touch Create or the lobby.
2. **PR 2 — Create and the lobby.** New session's 4 boxes with the
   ordering check on `setCustomValidity`, and the lobby expander's End;
   the specs; browser-check rows; close.

### Definition of done

- Every one of the 9 boxes is the shared control; no
  `type="datetime-local"` remains outside it (grep).
- A box seeded and saved unchanged stores nothing new; a pasted value
  saves; ✕ clears (tests).
- `spec/ui_elements.md` names the control.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19X.6` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19X entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

- None.

### Out of scope

- The audit log's date filters (`type="date"`, no time): no AM/PM.

### Doc impact

- `spec/ui_elements.md` — the date-time field: text box, picker, ✕ (Item 6).
- `spec/session_home.md` — the details card's date boxes (Item 6).
- `spec/operator_ui_concept.md` — the New session form's date fields (Item 6).
- `spec/sessions_overview.md` — the lobby expander's End (Item 6).
- `spec/lifecycle.md` — the ordering chain's client check (Item 6).
- `spec/participant_model.md` — the release-window field rows (Item 6).
- `spec/settings_inventory.md` — the release-window rows' editor (Item 6).
- `guide/things_to_check_in_browser.md` — rows for each surface (Item 6).
- `guide/todo_master.md` — Item 6 in the 19X entry (Item 6).

## Item 7 — Arriving on a page carries no fragment

### Opportunity

The author, 2026-10-20, after Item 5: a Create with nothing staged
still lands on `?editing=1#session-config`; "are there other fragments
like this? Let's be thorough." An inventory found two kinds. *Arrival*
fragments only dress the address of a page reached from elsewhere:
`?editing=1#session-config` from a bare Create, the lobby's Duplicate,
Validate's "Fix on Session details" and the retired `/edit` bookmark;
`#quick-setup-<slot>` from a Create whose staged file is refused.
*Stay-in-place* fragments return the operator to what they just acted
on (roster rows, instruments, the Owners card, Home's own Quick Setup
Submit, pagers).

### Decision

The author's ruling, 2026-10-20: drop the arrival fragments and keep
the stay-in-place ones, and keep Validate's row-level Fix anchors
(`#reviewer-row-N`, `#instrument-N`: pointing at the row is the link's
purpose). Session Home's Save already lands without one (19U Item 4).
Rejected: replacing every stay-in-place fragment with a scroll restore
as well — several PRs for no reported problem.

### Semantics

- `?editing=1` alone opens the details card in edit mode; the page
  opens at its top, the details card under the Workflow card.
- A refused file on Create lands on `?quick_setup_error=…` alone; Home's
  banner script scrolls to the shown banner on load.
- Unchanged: the Guide links' `#guide-…` (a judgment call below), and
  every stay-in-place fragment.

### Judgment calls — decided

- The Guide links keep `#guide-…` (2026-10-20): each points at the
  section its text names on a long page, as a Fix row anchor does.
- Assignments' "Edit on Instruments page" keeps `#instrument-N`
  (2026-10-20, found by the read): it names one instrument, as a Fix
  row anchor does.

### Blast radius (measured)

Taken 2026-10-20 at `6af85064`.

| What | Count | Command |
|---|---|---|
| Arrival redirects to `#session-config` | 4 | `grep -rn '#session-config"' app --include=*.py \| wc -l` |
| Create's refusal slot fragment | 1 | `grep -rn 'query}#quick-setup' app --include=*.py \| wc -l` |
| Test files pinning either | 8 | `grep -rlzP --include=*.py 'editing=1#session-config\|refused"\s*\n\s*"#quick-setup' tests \| wc -l` |
| Specs naming `editing=1#session-config` | 6 | `grep -rl 'editing=1#session-config' spec \| wc -l` |

### Status

**Closed 2026-10-20, in one PR.** As planned: five redirects lost their
fragment; Validate's rules assert no `fix_url` carries one; a browser
test pins both Create landings. One `diff-reviewer` read: no defect in
the change; it found one arrival fragment the inventory missed,
Assignments' "Edit on Instruments page" (kept, judgment call above);
that the Save seat check no longer tells an arrival from Save's own
landing (the 15 s freshness still does; comment updated, cosmetic); a
stale test comment; and that without script a refused Create no longer
scrolls to its banner (the plan accepts the script). `spec-writer` at
close aligned all six specs, with no code divergence.

### PR ladder

1. **PR 1 — the landings.** The five redirects, their tests, a browser
   test, the specs, a browser-check row. Must not touch a stay-in-place
   fragment.

### Definition of done

- No redirect or link that opens a page from elsewhere carries a
  fragment, the anchors that name one row, instrument or Guide section
  aside (grep; tests).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19X.7` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19X entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

- None.

### Out of scope

- Stay-in-place fragments (the author's ruling above).

### Doc impact

- `spec/session_home.md` — the `/edit` redirect and the arrivals (Item 7).
- `spec/operator_ui_concept.md` — Create's landings and the `/edit` redirect (Item 7).
- `spec/quick_setup_card_spec.md` — the New-session variant's landings (Item 7).
- `spec/visual_style_rrw.md` — the `/edit` redirect (Item 7).
- `spec/settings_inventory.md` — the details card's address (Item 7).
- `spec/operator_button_audit.md` — the details card's address (Item 7).
- `guide/things_to_check_in_browser.md` — a row (Item 7).
- `guide/todo_master.md` — Item 7 in the 19X entry (Item 7).
