# Segment 19X — Refinements from browser runs

**Opened:** 2026-10-19 · **Theme:** small follow-ups the author's browser
runs turn up, one item each · **Related:**
`guide/browser_check_files/round_2/README.md`, `spec/setup_pages.md`,
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
single-operator Setup page. The Item 2 checklist section went in the
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
