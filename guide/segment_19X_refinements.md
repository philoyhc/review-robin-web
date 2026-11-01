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

## Item 8 — The date-time field's buttons are squares

### Opportunity

The author, 2026-10-20, on Item 6's field: "Make the button for calling
out the picker square? Same size as the one for X." Measured on New
session: the 📅 button 51 × 37 px, the ✕ 46 × 37, the box 36 tall; the
emoji is wider than ✕, and `body.ui-v2 .btn`'s 16px side padding wins
over the field's own.

### Decision

Both buttons become 2.25rem squares, stretched to the box's height
(36px), padding off, glyph centered, under a selector specific enough
to beat `body.ui-v2 .btn`. *(At build: the box takes the same explicit 2.25rem
height, `--dt-field-size`, since a stretched height built from a rem
font and 8px padding drifts from a rem width at a non-default browser
font size — Codex on #3167.)* Rejected: `aspect-ratio: 1` on a stretched
flex item — Chromium sized the width from the content, measured 19 and
14 px wide.

### Blast radius (measured)

Taken 2026-10-20 at `9fc6d187`: one CSS rule in `base.html`
(`.dt-field .dt-field-btn`), the regenerated `tools/theme_customizer.html`,
one spec paragraph.

### Status

**Closed 2026-10-20, in one PR.** Measured after: 36 × 36 on New
session, Session Home and the lobby expander, level with the box. A
browser test pins it. One `diff-reviewer` read: no defect; it found that
the rule's `display` outranked `.btn[hidden]` (latent off `ui-v2`;
`tests/unit/test_btn_hidden_hides.py` failed on it too), now restored by
the field's own `[hidden]` rule, and that §6's one-shape claim needed
this exception named (done). `spec-writer` at close: no divergence;
it added the pointer from §6 to the exception. Codex on #3167: the squares held only
at the default font size; the shared size fixes it, and the browser
test now runs at 13, 16 and 20px root sizes.

### PR ladder

1. **PR 1 — the rule**, a browser test, the spec line. Must not touch
   the field's markup or script.

### Definition of done

- Both buttons measure square and as tall as the box (browser test).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19X.8` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19X entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

- None.

### Out of scope

- Any other `.btn`.

### Doc impact

- `spec/ui_elements.md` — the date-time field's buttons are squares (Item 8).
- `guide/todo_master.md` — Item 8 in the 19X entry (Item 8).

## Item 9 — The lobby's counts leave archived sessions out

### Opportunity

The author, 2026-10-20, with a screenshot of a lobby holding 14
archived sessions and nothing else: the Sessions card read
`14 SESSIONS · 0 DRAFT · 0 ACTIVATED · 14 ARCHIVED`. Every count and
chip there should reflect the sessions the lobby lists, the Archived
pill aside. Only the total was wrong: draft and activated never count
archived sessions, and the tag chips come from the listed rows.

### Decision

`views.session_status_counts` takes `archived_in_total`; the lobby
passes `False`, so `N sessions` counts the non-archived sessions (a
closed one still counts there) while `N archived` keeps counting the
archive. Sessions Diagnostics keeps every session in its total, since
its table lists them all. Rejected: a second helper for the lobby —
the pills stay one shape on both pages.

### Blast radius (measured)

Taken 2026-10-20 at `5092e25d`: 2 callers of `session_status_counts`
(`grep -rn "session_status_counts(" app --include=*.py | grep -v def`);
3 test files naming the pills (`grep -rln "sessions</span>" tests
--include=*.py`, plus `test_lobby_first_run_card.py` for the
all-archived lobby).

### Status

**Closed 2026-10-20, in one PR.** As planned; the all-archived lobby now
reads `0 sessions · 0 draft · 0 activated · N archived`, and Diagnostics
is unchanged (its test still pins its total). One `diff-reviewer` read: no
defect in the code; it found the new spec paragraph splitting a lead-in
from its table (moved) and a test name that claimed the lobby's total
(renamed; it now pins both flags). `spec-writer` at close: no divergence.

### PR ladder

1. **PR 1 — the total.** The helper's flag, the lobby's call, tests,
   the spec paragraph. Must not touch Diagnostics' counts.

### Definition of done

- The lobby's `N sessions` excludes archived sessions; Diagnostics'
  does not (tests).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19X.9` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19X entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

- None.

### Out of scope

- Sessions Diagnostics' Sessions Overview (it lists every session).

### Doc impact

- `spec/sessions_overview.md` — what the Sessions card's pills count (Item 9).
- `guide/todo_master.md` — Item 9 in the 19X entry (Item 9).


## Item 10 — String answer boxes fit their text

### Opportunity

The author, 2026-10-22: the help-text boxes that grow with their text
(19Y Item 5) "proved the value of self expanding editboxes". On the
reviewer surface a String answer is still one of two fixed shapes
(`spec/reviewer-surface.md`, the render table):
- **`max_length` ≤ 100:** a one-line `<input type="text">`, where a long
  answer scrolls sideways out of sight;
- **over 100:** a `<textarea>` whose `rows` are guessed from half the
  maximum and the column's width (`views.textarea_rows_for`, clamped to
  2–8), plus a handle the reviewer drags when the guess is wrong.

### Decision

*The author accepted the recommendations, 2026-10-22 (Open questions).*
- **Every String answer is a `<textarea>` that fits its text.** Its
  height is its content's, above a floor, with no handle.
- **The floor, by `max_length`:**
  - **50 or fewer:** one line, matching the height of the row's number
    and list inputs.
  - **More than 50, or none set:** two lines.
- **When it refits:** on load (a saved or disabled answer shows whole),
  on each keystroke and paste, and when its width changes (a column
  drag, a window resize).
- **One shared fit.** The help boxes' fit (`fitHelpBox` in
  `operator/instruments_index.html`) moves to one `base.html` helper,
  which both boxes use.
- **Band 2's preview** draws the same floors, so the operator sees what
  the reviewer will.
- **`textarea_rows_for`, and its two JS ports, retire.**

Rejected:
- *A taller fixed box:* the guess is the problem, whatever its size.
- *Keeping the handle beside the fit:* the next keystroke would undo a
  drag, as the help boxes found.

### Semantics

- **A one-line box takes no line break** (Open question 1, answered). Enter inserts
  none, and a pasted break becomes a space, so its answer reads as the
  short answer its maximum implies. A two-line box keeps line breaks.
- **No ceiling** (Open question 2). The box grows to its whole answer, as
  the help boxes do, and `maxlength` bounds it.
- **Without JavaScript**, a box stays at its floor, scrolls, and keeps its
  native handle. The handle goes only when the script runs.
- **The column is unchanged** (Open question 3): `rs-textlong`'s 14em
  minimum still marks a String over 100. It sizes the column, not the box.
- **What is saved is unchanged.** Same names, same `maxlength`, the same
  server checks.

### Blast radius (measured)

Taken 2026-10-22 at `5395f19`.

| What | Count | Command |
|---|---|---|
| `textarea_rows_for` / `textareaRowsFor` sites | 22 in 10 files: `review_surface.html` 6, `instruments_index.html` 8, `views/_instruments.py` 2, `views/__init__.py` 2, two env globals, `base.html` 1; tests: `test_reviewer_view_helpers.py` 6, `test_instrument_builder_routes.py` 4, `test_reviewer_response_flow.py` 1 | `grep -rn "textarea_rows_for\|textareaRowsFor" app tests --include=*.py --include=*.html` |
| The 100-character split | 4 template sites (`review_surface.html` 403, 468, 507; `instruments_index.html` 3235); the column class's 3 more (`instruments_index.html` 2704, `_reviewer_summary.py` 480, `_reviewee_results.py` 573) stay | `grep -rn "> 100" app --include=*.py --include=*.html` |
| Browser tests on these boxes | 2: `test_preview_response_box.py` (no handle in the preview), `test_help_box_grows.py` (the fit being shared) | `ls tests/browser \| grep -E "preview_response\|help_box"` |
| Specs | `spec/reviewer-surface.md` (render table, "Textarea height derivation"), `spec/instruments.md` ("Preview row", "Help rows"), `spec/ui_elements.md` (the textarea resize rule) | `grep -rln "textarea_rows_for\|resize" spec` |

### Status

**Closed 2026-10-22, in #3220 (plan) and #3221 (build).** As planned, with
these confirmed at build:
- **The shared fit** is `base.html`'s `data-fit-box` script
  (`window.rrwFitBoxes` / `rrwUnfitBoxes`). It sets `data-fit-on`, and
  only then do the handle and scrollbar go.
- **A one-line box flattens only what is typed or pasted.** A stored
  answer shows as saved, breaks included. Enter is skipped inside an IME
  composition. The listener runs in the capture phase, so the branch
  check sees the flattened text.
- **Beyond the plan:** the server keeps a posted CRLF as LF
  (`parse_form_payload`), so its length check counts a line break once,
  as `maxlength` does. Before this, a box over 100 refused an answer at
  its limit, and 51–100 boxes now take breaks too.
- **One behavior change, per the ruling:** Enter in a short String
  answer no longer saves the page, as it did in the old text input.

**Reads:**
- **`diff-reviewer`**, one read: no high findings.
  - Acted on: the CRLF count (M2); the load-time flatten, branch-check
    order and IME Enter (L3, L4); stale comments and an unused export
    (L1, L2); and the missing tests, a one-line box's handle and the
    preview's one-line floor (L5).
  - M1, Enter no longer saving, is the ruling, recorded above.
- **`spec-writer`** at the close also corrected `spec/rrw_functional_spec.md`,
  now in `Doc impact`.

### PR ladder

1. **PR 1, this entry**, prose only.
2. **PR 2, the build:**
   - the shared fit;
   - every String a fitting textarea at its floor, on the surface and
     in the preview;
   - the formula retired;
   - tests and specs.

   One PR: the floors cannot ship without the fit. It must not change
   names, `maxlength`, server checks or `rs-textlong`.

### Definition of done

- On the reviewer surface a String answer of 50 or fewer characters
  starts one line high, any other starts two lines high, and each grows
  with its text, with no handle (browser test).
- A saved long answer shows whole on load (browser test).
- A one-line box takes no line break: Enter inserts none and a pasted
  multi-line value arrives with spaces, while a two-line box keeps its
  breaks (browser test).
- `grep -rn "textarea_rows_for\|textareaRowsFor" app tests` finds nothing.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19X.10` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19X entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

All four answered by the author, 2026-10-22, on the recommendation:
1. ~~A line break in a one-line box~~: none. Enter inserts nothing, and a
   pasted break becomes a space.
2. ~~A ceiling~~: none, as the help boxes have.
3. ~~`rs-textlong`'s threshold~~: stays at 100.
4. ~~A String with no `max_length`~~: two lines.

### Out of scope

- Integer, Decimal and List answers.
- Operator-side text boxes, other than the preview and the help boxes'
  shared fit.
- Read-only answer displays (`/summary`, results, collation), which show
  text rather than boxes.

### Doc impact

- `spec/reviewer-surface.md` — String answers are fitting textareas with a one- or two-line floor; "Textarea height derivation" retires (Item 10).
- `spec/instruments.md` — the preview's String box mirrors the floors; the help boxes' fit is shared (Item 10).
- `spec/ui_elements.md` — answer boxes fit their text, with no handle (Item 10).
- `spec/rrw_functional_spec.md` — cell rendering: a String answer box grows to fit its text, one or two lines to start (Item 10; found by `spec-writer` at the close).
- `guide/todo_master.md` — Item 10 in the 19X entry (Item 10).

## Item 11 — The reviewer surface's header loses its card

### Opportunity

The author, 2026-10-22, with a screenshot of the reviewer surface's top.
It stacks four parts (`spec/reviewer-surface.md`, the page's parts 3–4):
- **a title row:** the session name, then `Deadline: …`;
- **a role row:** the `Reviewer` pill, then the reviewer's own line
  (name · email · Profile);
- **an overview card** (`.card.rs-status-panel`), a bordered card
  holding:
  - the session description;
  - the session-closed banner;
  - the `Draft` / `Saved but not submitted` / `Submitted` rollup pill;
  - one pill per instrument (`#1 Group Team Review: not started`).

The card is the page's heaviest element, and it holds little more than
pills.

### Decision

*The author accepted the recommendations, 2026-10-22 (Open questions).*
Two rows and no card:
1. **The title row:** the session name, then the rollup pill (`Draft`
   in the screenshot), then `Deadline: …` when there is a deadline.
2. **The participant row:**
   - the reviewer's own line (name · email · Profile, when set);
   - the role pill or pills;
   - a `|` separator;
   - the instrument status pills.

The card's other contents keep their place under the rows, without a
card:
- the session description, as a paragraph;
- the session-closed banner, as a banner.

Rejected: *keeping the card for the description alone*, since one
paragraph needs no border.

### Semantics

- **No instrument pills** (no assignments) means no `|` either. The
  separator is `aria-hidden`.
- **No deadline** means the title row ends at the pill.
- **The operator preview** (`preview_mode`) renders the same template,
  with its static `Reviewer` pill, so it follows.
- **On a narrow window** each row wraps on its own: the separator stays
  with the instrument pills, and the rows never merge.
- **The help contact** (`Questions? Contact …`) stays on the title row,
  after the deadline (Open question 2).

### Blast radius (measured)

Taken 2026-10-22 at `5395f19`.

| What | Count | Command |
|---|---|---|
| Templates | `reviewer/review_surface.html` (header and card); `reviewer/_role_chips.html` (row order, shared by `summary.html`, `pre_open.html`, `results.html` and `collation.html`); `results.html` and `collation.html` keep a description-only `rs-status-panel` card | `grep -rln "_role_chips.html\|rs-status-panel" app/web/templates` |
| CSS | `base.html`'s `.rs-page-header`, `.rs-status-panel` and `.rs-role-nav` rules | `grep -n "rs-page-header\|rs-status-panel\|rs-role-nav" app/web/templates/base.html` |
| Tests naming these classes | 8 integration files, 46 references (`test_me_surface_role_chips.py` 17, `test_reviewer_self_info.py` 10) | `grep -rc "rs-status-panel\|rs-page-status-pills\|rs-role-nav\|rs-self-info" tests` |
| Specs | `spec/reviewer-surface.md` (the page's parts 3–4, "Overview card", the role-navigator markup); `spec/visual_style_rrw.md` (status cards) | `grep -rln "rs-status-panel\|overview card\|rs-role-nav" spec` |

### Status

**Closed 2026-10-22, in #3220 (plan) and #3222 (build).** As planned, with
these confirmed at build:
- **The participant row is `_role_chips.html`** on every participant
  page: the own line, then the role pills, then (the reviewer surface
  only, as `role_row_statuses`) `|` and the instrument pills, wrapping as
  one group. The pills render only where the role row does, which every
  reviewer-surface render has, the preview included.
- **The instrument pills are spans in the row**, no longer a list.
- **The help contact** ends the title row whether or not there is a
  deadline, so with no deadline the row ends at the contact, not the pill.
- **`.rs-session-description` is now a page-level rule** in `base.html`,
  shared by the reviewer surface, results and collation.

**Reads:**
- **`diff-reviewer`**, one read: no high findings.
  - Acted on: a no-assignments test (M1); the no-link and own-line checks
    on the new order (M2, L2); exact description tests on results and
    collation (L1); a deadline relative to now (L4); a stale comment (L6).
  - L3 (pills follow the role row) and L5 (spans, not a list) stay, as
    recorded above.
- **`spec-writer`** at the close: `spec/reviewer-surface.md`,
  `spec/participant_model.md`, `spec/visual_style_rrw.md`; no flags
  changed a decision.

### PR ladder

1. **PR 1, this entry**, prose only, with Item 10.
2. **PR 2, the build:**
   - the two rows;
   - the card's removal;
   - the shared row's order on every participant page;
   - the description-only cards on results and collation;
   - tests and specs.

   Must not change a pill's wording or color, or the role chips' links.

### Definition of done

- The reviewer surface renders no `.rs-status-panel`. Its title row
  holds the name, the rollup pill and the deadline; its participant row
  holds the own line, the role pills, `|` and the instrument pills, in
  that order (integration test).
- With no assignments there is no `|`; with no deadline there is no
  `Deadline:` (integration test).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19X.11` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19X entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

All four answered by the author, 2026-10-22, on the recommendation:
1. ~~The own line before the role pills on the other participant
   pages~~: yes, in the shared partial, on every page.
2. ~~The help contact~~: it stays on the title row, after the deadline.
3. ~~The description-only cards on results and collation~~: they lose
   their card too.
4. ~~The rollup pill's wording~~: unchanged.

### Out of scope

- Each instrument's progress pills above its table, and the per-field
  constraints.
- The chrome above the page (the top bar).

### Doc impact

- `spec/reviewer-surface.md` — the page's header as two rows; the overview card retired; the role row's order on every participant page (Item 11).
- `spec/participant_model.md` — results and collation: the description without a card; the own line before the role pills (Item 11).
- `spec/visual_style_rrw.md` — the status-card example no longer names the reviewer surface (Item 11).
- `guide/todo_master.md` — Item 11 in the 19X entry (Item 11).

## Item 12 — The participant row's `|` goes when the pills wrap

### Opportunity

The author's browser check of Item 11, 2026-10-22, with screenshots: at
a narrower window the instrument pills wrap below the role pills, and
the `|` that led them starts the new line, where it separates nothing.

### Decision

When the status group wraps below the role pills, a script in
`reviewer/_role_chips.html` marks it `.rs-role-nav-statuses-wrapped`.
That hides the `|` and gives the group the whole line (`flex-basis:
100%`), so losing the `|` cannot let it fit back up. It re-checks
whenever the row's size changes. Without script the `|` stays, as in
Item 11.

Rejected: *a CSS-only clip*, offsetting the row so a line-leading `|`
falls outside an `overflow: hidden` edge. It would also clip the focus
rings of the Profile link and the role chips.

### Blast radius (measured)

Taken 2026-10-22 at `6fd5e6a`: one partial
(`reviewer/_role_chips.html`), two `base.html` rules and their
generated mirror in `tools/theme_customizer.html`, one spec
(`grep -rln "rs-role-nav-sep" app spec` → `_role_chips.html`,
`base.html`, `spec/reviewer-surface.md`).

### PR ladder

1. **One PR:** the plan entry, the script and rules, a browser test, and
   the spec.

### Definition of done

- At a wide window the `|` shows; at a narrow one the pills sit on their
  own line without it; widening brings it back
  (`tests/browser/test_role_row_separator.py`).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19X.12` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19X entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

None.

### Out of scope

- The own line or role pills wrapping inside the row; only the `|`
  changes.

### Status

**Closed 2026-10-22, in one PR.** As planned; the observer re-checks a
frame later, so the row never resizes inside its own callback.

**Reads:**
- **`diff-reviewer`**, one read: no high findings.
  - Acted on: the in-callback resize, which raised a ResizeObserver loop
    error on widening (M1); this Status (M2); tests for the band where
    the pills fit only without the `|`, a narrow window on load, and no
    script (L3, L4); the blast radius's generated mirror (L5).
- **`spec-writer`** at the close: two wording fixes to
  `spec/reviewer-surface.md`, no flags.

### Doc impact

- `spec/reviewer-surface.md` — the `|` drops when the pills wrap below the role pills; the `.rs-role-nav-statuses-wrapped` rules (Item 12).
- `guide/todo_master.md` — Items 10–12 in the 19X entry (Item 12).

## Item 13 — The session description moves up to the session name

### Opportunity

The author, 2026-10-22, after the browser check of Item 12: the
description sits under the participant row, away from the session name
it describes. "Session name and description should be closer to each
other."

### Decision

The description (`p.rs-session-description`) renders directly under the
title row, above the participant row, on all three participant pages:
the reviewer surface, `/results` and `/collation`. Since Item 11 they
share one header shape, so they move together. The session-closed banner
stays under the participant row. No CSS changes: the gaps between the
three stay as they were.

Rejected: *moving it on the reviewer surface alone*. That would split a
header shape the three pages share.

### Blast radius (measured)

Taken 2026-10-22 at `e548ce6`: three templates
(`grep -rln "rs-session-description" app/web/templates/reviewer` →
`review_surface.html`, `results.html`, `collation.html`), two test files
that pin the order, one spec (`spec/reviewer-surface.md` §3–4 and the
CSS list; `spec/participant_model.md` does not place the description).

### PR ladder

1. **One PR:** the plan entry, the three templates, the tests and the
   spec.

### Definition of done

- On all three pages, the description comes after the title row and
  before the participant row (integration tests in
  `tests/integration/test_segment_11d_followon_pr_beta.py` and
  `tests/integration/test_me_results_collation_placeholders.py`).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19X.13` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19X entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

None.

### Out of scope

- The spacing between the rows, unchanged.

### Status

**Closed 2026-10-22, in one PR.** As planned, plus a test that the
description follows the title row directly and the closed banner stays
under the participant row.

**Reads:**
- **`diff-reviewer`**, one read: no high findings.
  - Acted on: this Status (M1); the banner and directly-under test (L2);
    stale comments in `test_segment_11d_pr_c.py`, `results.html`,
    `_role_chips.html` and the spec's role-strip section (L4–L6).
  - L3, a preview-mode order test, not added: the template has no
    preview branch around the description.
- **`spec-writer`** at the close: one stale line in
  `spec/reviewer-surface.md`'s role-strip section; flagged a stale
  `base.html` comment and doubled blank lines, both fixed.

### Doc impact

- `spec/reviewer-surface.md` — the page header as title row, description, participant row; the closed banner alone under them; the `.rs-session-description` CSS entry (Item 13).
- `guide/todo_master.md` — Items 10–13 in the 19X entry (Item 13).

## Item 14 — Accounts › Invite: no selection, and several at once

### Opportunity

The author, 2026-11-01, using the directory picker (19Z) on Azure: an
invite selects the new row, which moves the table off what the admin was
looking at, and the box takes one person at a time. "Upon inviting
someone, the person's row is automatically selected in the table: don't
do that. Secondly, allow comma separated invitations … after a comma,
directory search should activate again."

### Decision

- **No selection.** An invite lands on the table as the admin left it
  (no `?selected=`).
- **A comma-separated list.** `users.invite_list` splits it
  (`split_invite_list`) and invites each entry as `invite` does, each
  committed on its own, so one refusal stops none of the rest. At most
  50 (`INVITE_LIST_MAX`): each entry is a directory lookup the admin
  waits for, and over 50 invites none (`too_many`).
- **The banner.** One entry keeps today's redirect and banners. Several
  land with `?invited=<n>` and one `invite_refused=<code>:<address>` per
  refusal; the page counts them and names each refused address with a
  reason from its own table (`views.invite_refusals`), never echoing the
  code.
- **The picker.** The search reads what follows the last comma, and each
  option's value keeps what comes before it, since a datalist pick
  replaces the box's whole value.

Rejected: *all or nothing*. A list with one typo would invite no one,
and the admin would retype the rest.

### Semantics

- A piece with no `@` joins the piece after it, so `Tan, Jane
  <jane@x.edu>` stays one entry; blank pieces are dropped. *(At build:
  only when the two read as one `Name <address>`; otherwise the word is
  its own entry, refused.)*
- A duplicate inside the list is refused as `duplicate` on its second
  appearance, as on its own.

### Blast radius (measured)

Taken 2026-11-01 at `45da761`: one route (`_sys_admin.invite_user`) and
the page route's banner parameters; one template
(`sys_admin_users.html`); one service (`users`), one view (`_accounts`);
six test files posting the invite (`grep -rln "users/invite" tests/`);
three specs naming the card (`grep -rln "Invite by email\|users/invite"
spec/`), of which `operator_ui_concept.md` and `permissions.md` state
the behavior that changes.

### PR ladder

1. **One PR:** the plan entry, the service, route and template, the
   tests and the two specs.

### Definition of done

- An invite lands without `selected` (`tests/integration/test_sys_admin_users.py`).
- A list invites each entry, names the refused, and caps at 50
  (`tests/integration/test_invite_list.py`); after a comma the picker
  searches again and a pick keeps the list
  (`tests/browser/test_invite_directory_picker.py`).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19X.14` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19X entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

None.

### Status

Open, one PR. One `diff-reviewer` read of `45da761..ec8fef3`; acted on in the same PR:
- **A stray word sank the address after it** (`a@x, Arun, c@x` lost `c@x`): a no-`@` piece now joins the next only when the two read as one `Name <address>` (Semantics amended).
- **Fifty lookups, each with its own 120 s budget**, could outrun the front end: the directory is asked about the list at once (`directory_accounts.resolve`, one budget), and only about addresses past `invite`'s cheap refusals, as a lone invite is.
- **The picker assumed one space after a comma**, which hid matches: it keeps the spacing as typed.
- The audit events share the request's correlation id; the specs name the list's `invite_unchecked=<n>`; the banner's cap reads `INVITE_LIST_MAX`; a duplicate inside a list is tested.
- Recorded, not changed: the banner's counts and addresses come from the URL, so a crafted link can show a false summary (no markup: escaped, codes never echoed), as the single invite's `invite_error` banner already can.

### Out of scope

- The roster rows and help-contact pickers (19Z): one person per box.

### Doc impact

- `spec/operator_ui_concept.md` — Accounts: an invite takes one address or several, comma-separated, and selects no row; the list's banner (Item 14).
- `spec/permissions.md` — the Invite row: a list of at most 50, `too_many`, one `workspace.user_invited` per row; the list's redirect parameters (Item 14).
- `guide/todo_master.md` — Item 14 in the 19X entry (Item 14).
