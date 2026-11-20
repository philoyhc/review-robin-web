# Segment AD1O — Apply Desk: from a gate's setup to Review Robin, and a whole panel as a source

**Opened:** 2026-11-20 · **Theme:** two touch-ups to a gate's cards on Process, from the author's walkthrough of a scratch exercise · **Related:** `applydesk/guide/todo_master.md` (rulings 60–62), `applydesk/spec/applications.md` (Process's gate cards; The Evaluations page)

## Opportunity

Walking a gate's setup on Process (2026-11-20), the author found two gaps:
- A gate set up on Process has no way to its Review Robin card, which lives on its Evaluations page. The operator must leave, find Evaluations, then the gate.
- A panel source asks for a Min and a Max per dossier. When every member of a panel should evaluate every dossier (the model exercise's current RAs), the operator must count the panel and type its size twice, and retype it whenever a member joins or leaves.

## Decision

1. **Item 1 — a link from the *Gate* card to the gate's Review Robin card** (ruling 61). The card ends with *Review Robin card →*, to `…/evaluations/gate_<n>#ev-rr`. Where that page does not exist yet, the line says why instead of linking: a gate not yet saved, or an exercise still a draft (today's rule; ruling 60 lifts it with AD2).
2. **Item 2 — *All* on a panel source** (ruling 62). A Toggle (`spec/ui_elements.md` §6) after Min and Max. On, the source gives each dossier every member of its panel. Min and Max are disabled and show the panel's size, which follows the panel. `Source` gains `all_members: bool`; one helper, `stages.source_bounds`, resolves a source's min and max (the panel's size when *All* is on). `total_bounds`, `fill`, the summaries, the problems and the handoff all read the bounds through it. Nominated sources have no *All*.

**Alternative rejected:** for item 2, writing the panel's size into Min and Max when *All* is turned on. It is simpler, but the numbers go stale as soon as the panel changes, which is the very retyping the author wants gone.

## Semantics

- **An empty panel under *All*** gives 0 to 0, and the Total check flags it as today.
- **A sent gate** keeps its sources (ruling 24), *All* included: the toggle is disabled with the rest.
- **A sample gate** naming only a panel (`sources_of`'s fallback) reads as one source with *All* on, which is what its min = max = size meant.
- **Save** (a scratch exercise, `process_save`) keeps `all_members`; an *All* source's Min and Max are stored as sent and ignored.

## Judgment calls — decided

- The link line sits in the *Gate* card, after its rule, not in the item's head, so the head stays a summary.
- *All* is a Toggle, not a third value in Min or Max: the boxes stay numbers.

## Blast radius (measured)

Taken 2026-11-20 at `a5597a84b`.
- `stages` callers outside tests: `sources_of(` 10, `sources_summary(` 5, `fill(` 5, `total_bounds(` 4, `total_problem(` 3, `source_problems(` 3, `source_label(` 3, `sources_warn(` 2.
- Templates: `operator/_process_cards.html` (the *Gate* card, `source_row`) and `operator/_process.html` (`sourcesOf`, `srcBounds`, `drawSources`).
- Tests constructing `Source(`: `test_locks.py`, `test_fill.py`, `test_evaluations_browser.py`, `_fellowship.py`, `test_pages.py`.

## PR ladder

1. **This plan**, with rulings 60–62. Prose only.
2. **Item 1: the link.** The *Gate* card's line, `gate_page_url` beside `gate_state`, and tests (a linked gate; a draft exercise's reason; a new gate's reason).
3. **Item 2: *All*.** `Source.all_members`, `source_bounds` and its callers, the toggle, the page script, `process_save`, and tests (bounds, fill, summary, a browser toggle). This is the last build rung, so the cumulative cold read runs here.
4. **Close.**

## Definition of done

- A saved gate of a published exercise links from its *Gate* card to its Review Robin card; a draft's or a new gate's says why (tests).
- *All* on a panel source disables Min and Max and fills each dossier with the whole panel; the Total bounds follow the panel's size (tests, one in a browser).
- `## Doc impact` section present and current
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `applydesk/guide/todo_master.md` entries deleted; plan moved to `applydesk/guide/archive/` + index row
- (`tools/close_check.py` reads only RRW's top-level `guide/`; the close is checked by hand.)

## Open questions

- None.

## Out of scope

- Evaluations open before publication (ruling 60): AD2/AD3.
- *All* for a nominated source: a candidate's nominees are already all of whom they named.

## Doc impact

- `applydesk/spec/applications.md` — Process's *Gate* card link (item 1); a panel source's *All* (item 2).
- `applydesk/guide/todo_master.md` — rulings 60–62 (rung 1).
- `applydesk/guide/archive/README.md` — the plan's index row (at close).
