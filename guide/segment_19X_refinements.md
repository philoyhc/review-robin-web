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

**2026-10-19, build.** One rung as planned, and the Owners card opts in
too: the read found its banner, which sits after the Quick Setup card on
Session Home, scrolled itself and cropped the card's heading once the
first-match no longer stopped on a hidden Quick Setup banner. The
landing holds as far as the page can scroll; on a window taller than the
rest of the page the card shows lower down.

### Out of scope

- Other pages' banners: they keep scrolling to themselves; only a card
  that opts in with the attribute lands elsewhere.

### Doc impact

- `spec/ui_elements.md` — §5a *Auto-scroll on display*: the first shown banner, and `data-banner-landing` (Item 2).
- `guide/things_to_check_in_browser.md` — a row for the landing (Item 2).
- `guide/todo_master.md` — drop Item 2 from the 19X entry when it closes (Item 2).
