# Segment AD1N — Apply Desk: a scratch exercise to set up end to end

**Opened:** 2026-11-19 · **Theme:** the first item of the UI review: *New exercise* makes a blank draft the operator sets up page by page, held in the server's memory for their browser and never saved, so the whole setup flow can be walked before AD2 · **Related:** `applydesk/guide/todo_master.md` (ruling 59; the UI review and AD2 roadmap rows), `applydesk/spec/applications.md` (the Operator Lobby, Exercise Home's Details, Form, Process, Panels, Emails)

## Opportunity

The author wants to know how an operator will work through Apply Desk to set up an exercise, before AD2 fixes what is stored (2026-11-19). Today they can't:
- *New exercise* on the Operator Lobby is disabled until AD3.
- The blank sample, *Graduate Travel Grant 2027*, is only a view. Form, Process, Panels and Details keep edits on the page, and lose them when the page is left.
- Every page renders from the fixed sample, so no page sees another's edits. Process never lists a question added on Form, and Emails never follows Process's ticks.

## Decision

1. **A scratch exercise lives in the server's memory, per browser** (ruling 59).
   - A browser gets an opaque `applydesk-scratch` cookie, HttpOnly, on the mount's path.
   - It keys an in-memory store of that browser's scratch exercises, at most five.
   - Nothing is written to disk. A restart, a deploy, or eight idle hours clears them.
   - The pages say so.
2. ***New exercise* asks for a name and creates a blank draft.** It is shaped like *Graduate Travel Grant 2027*: one stage holding the form, nothing else. The operator lands on its Home. The Lobby lists scratch exercises with a *Scratch* chip and a *Discard*.
3. **The sample's lookups read the scratch first.** A request-scoped context holds the browser's store, and `sample_data` and `stages` consult it before the fixed sample. So every page renders a scratch exercise without its route changing: `exercise`, `applications_of`, `form_snapshot`, `panels_of`, the pools, `plan_of`, `emails` and `sends`.
4. **Each Setup page's *Save* saves into the scratch**, posting the page's state as JSON. On a sample exercise, *Save* stays as it is.
   - Details, Form, Process (stages, gates, outcomes, rules, email ticks), Panels, and Emails (replacing its tab storage for a scratch exercise).
   - The server checks each post against the same shapes the sample uses, and refuses a malformed one with the reason.

**Alternative rejected:** keeping each page's edits in the tab (`sessionStorage`). It is cheaper, but no page could see another's edits, so the walkthrough would be page by page. That is the very thing to be tried.

## Semantics

- **Isolation:** one browser's scratch is invisible to another. A super-admin is one browser among others.
- **Identity:** scratch IDs use `ids.generate_public_id` with a marker the store recognizes, so a scratch ID can never collide with a sample one. A request naming another browser's scratch ID gets 404.
- **Limits:** five exercises per browser, each post at most 256 KiB, eight idle hours. Past a limit the page says so and refuses.
- **What a scratch exercise holds:** Details, the form's questions, the stages and their items, panels and their members, the email templates and ticks. It never holds applications, so Dossiers and Evaluations show their empty states (see Open questions).
- **Stage status (AD1K):** *Publish* and the reverts work on a scratch, so the locks that follow can be tried.

## Judgment calls — decided

- Cookie plus memory, not a file or SQLite: anything on disk would be the database AD2 decides.
- Cap and idle expiry so a deployed host can't be filled.
- The *Scratch* chip and a line on every scratch page name the limits.

## Blast radius (measured)

Taken 2026-11-19 at `a4b87fd4c`.

- Lookup call sites:
  - `grep -rn "plan_of(" applydesk --include=*.py | grep -v tests | wc -l` → 33;
  - `applications_of(` 8, `people_pools(` 8, `panel_pools(` 8, `panels_of(` 6;
  - `sample_data.exercise(` 3, `form_snapshot(` 2, `emails(` 3, `sends(` 3.
  - None changes, since the lookups consult the store.
- Pages whose *Save* gains a post:
  - `operator/_details.html`, `_form.html` (391 lines with `_form_cards`/`_form_draw`), `_process.html` (1,430), `_panels.html` (935), `_emails.html`.
  - `operator/exercises.html` for *New exercise*.
- New: `applydesk/scratch.py` and its routes; tests.

## PR ladder

1. **This plan**, with ruling 59. Prose only.
2. **The store and *New exercise*.** `scratch.py`, the request context, the lookups consulting it, *New exercise* and *Discard* on the Lobby, Details' *Save*. Includes a browser test from a blank draft to its Home.
3. **Form saves.** The question cards posted and read back; Process's form-answer rules see them.
4. **Process saves.** Stages, gates, outcomes, rules, the emails each item ticks, and *Publish* and the reverts on a scratch.
5. **Panels saves.** Panels and members; Process's evaluator sources see them.
6. **Emails saves.** The templates held in the scratch; the status row follows. This is the last build rung, so the cumulative cold read runs here.
7. **Close.**

## Definition of done

- *New exercise* → name → a blank draft's Home, listed on the Lobby with *Scratch*, then discarded (a browser test).
- A question saved on Form shows on Process's rule editor. A Process tick makes an email owed on Emails. A panel saved on Panels is a gate source on Process (browser tests).
- Another browser cannot see or open the scratch exercise (an integration test).
- Over five, the sixth *New exercise* is refused. An idle one expires (tests).
- `## Doc impact` section present and current
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `applydesk/guide/todo_master.md` entries deleted; plan moved to `applydesk/guide/archive/` + index row
- (`tools/close_check.py` reads only RRW's top-level `guide/`; the close is checked by hand.)

## Open questions

- **Test applications for a scratch exercise**, so Dossiers and Evaluations can be walked too (*Add sample applicants*?): the author decides once rung 2 is on screen.
- **Saving a sample exercise as a scratch copy**, to edit the model exercise without starting blank: the author decides.

## Out of scope

- Anything stored on disk, and identity or grants: AD2.
- An applicant's side of a scratch exercise (`/me`): with the test-application question above.

## Doc impact

- `applydesk/spec/applications.md` — the Operator Lobby (*New exercise*, *Scratch*, *Discard*); each Setup page's *Save* on a scratch exercise; the limits (rungs 2–6).
- `applydesk/guide/todo_master.md` — ruling 59 (rung 1); the UI review row (at close).
- `applydesk/guide/archive/README.md` — the plan's index row (at close).
