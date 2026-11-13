# Segment AD1 — ApplyDesk: skeleton and URL map

**Opened:** 2026-11-12 · **Theme:** the `applydesk/` package mounted under Cordware at `/applydesk`, and its URL map stood up as placeholder pages before any data exists · **Related:** `applydesk/guide/todo_master.md` (rulings 1–8, the MVP roadmap), `applydesk/docs/applydesk_functional_spec_v0.6b_agent_handoff.md` (§10, §15.4 slice 1), `residentialapps/guide/archive/segment_1A_package_and_mounts.md` (the same step for Residential)

## Opportunity

`applydesk/` holds only prose, and Cordware's importer excludes it. Nothing can render an ApplyDesk page, pass the import boundaries or run in CI until the package exists and is mounted. The rulings of 2026-11-12 settle the page structure enough to draw it: operators under `/operator/exercises`, participants under `/me` (ruling 8), exercises named by a 10-character ID (ruling 7), and reviewers reading applications on a profile page that can be blind (rulings 5 and 6).

## Decision

**Two items, in order; the segment closes as a whole.**

1. **Package and mount**, as Residential's 1A: the package, its factory, the registry entry with an icon, health, packaging and the boundary tests. No database, no identity work, no pages beyond `health`.
2. **The URL map as placeholders**: every page of the map below on sample data, with real copy and layout, the shared top bar (`docs/header_chrome.md`) and inert controls. It is iterated in the browser until the author approves it; that approval is item 2's gate, as 1B's item 1 was Residential's.

**Rejected:**
- **A database in AD1.** The schema follows the pages, and AD2 owns the database and identity. The placeholders need sample data only.
- **A dedicated CI lane.** `tools/ci_lanes.py` already lists `applydesk/` in `APP_DIRS`, so an ApplyDesk code change runs the full lane. A narrower lane, like `residential`, waits until the full one costs too much.

## The URL map

Paths are under `/applydesk`. Path parameters: `<id>` is an exercise's public ID, `<app>` an application's, `<file>` an application file's (ruling 13; a profile page's until AD1C). Item 2 builds every row as a placeholder.

| Path | Page | Who reaches it (when wired) |
|---|---|---|
| `/` | Landing: links to *My ApplyDesk* and, for an operator, *Exercises* | Anyone signed in |
| `/health` | Health, `200` signed out | Anyone |
| `/operator/exercises` | Exercises lobby: the operator's exercises by state; New exercise | Operators |
| `/operator/exercises/<id>` | Exercise Home: stage, state, counts, the next step; the timeline with the current stage marked (iteration 5) | The exercise's operators |
| ~~`/operator/exercises/<id>/settings`~~ | Became Setup (iteration 5) | |
| ~~`/operator/exercises/<id>/setup`~~ | Became Process; its details moved to Home (AD1D) | |
| `/operator/exercises/<id>/process` | Rounds, gates and outcomes with their rules and emails; the timeline (AD1D) | 〃 |
| `/operator/exercises/<id>/form` | The application form builder (iteration 5); from AD1B, cards that move on screen (`applydesk/guide/archive/segment_AD1B_form_builder.md`) | 〃 |
| `/operator/exercises/<id>/applications` | Applications by state; generate applicant profiles; import outcomes (iteration 5); from AD1C, the control surface of rounds, gates and outcomes, generating application files | 〃 |
| ~~`/operator/exercises/<id>/assessors`~~ | Became Panels (iteration 5) | |
| ~~`/operator/exercises/<id>/panels`~~ | Into Gates (AD1D) | |
| `/operator/exercises/<id>/gates` | One card per gate with its panel; the reviewer pool (AD1D) | 〃 |
| `/operator/exercises/<id>/emails` | The templates to applicants (AD1D) | 〃 |
| ~~`/operator/exercises/<id>/review`~~ | Became Evaluations (AD1D) | |
| `/operator/exercises/<id>/evaluations` | Each gate's state and progress in Review Robin, results back (AD1D) | 〃 |
| ~~`/operator/exercises/<id>/timeline`~~ | Into Setup and Home; outcomes into Applications (iteration 5) | |
| ~~`/operator/exercises/<id>/export`~~ | Became Reports (iteration 5) | |
| ~~`/operator/exercises/<id>/reports`~~ | Became Extract data (AD1D) | |
| `/operator/exercises/<id>/extract` | Every evaluation response collated; the data export (AD1D) | 〃 |
| `/me` | My ApplyDesk: my applications, exercises open to me, application files I may read | Anyone signed in |
| `/me/exercises/<id>` | An exercise as an applicant sees it: details, timeline, Apply | Eligible applicants |
| `/me/exercises/<id>/applications/<app>` | My application: draft or submitted | Its applicant |
| `/me/exercises/<id>/files/<file>` | The application file (ruling 13; the profile page's path until AD1C): the *Shown to reviewers* section; in a blind exercise, the applicant's name and identifiers redacted | Assessors asked to review that application (ruling 9); the exercise's operators (author, 2026-11-12) |

## Semantics

- **Health without sign-in:** `/applydesk/health` answers `200` with no database, as RRW's does. Excluding it from Easy Auth in Azure is a private deployment step, not this segment's.
- **Running alone:** `CORDWARE_APPS=applydesk` starts, and so does ApplyDesk beside every other application.
- **Boundaries** (spec §10.1): `applydesk` never imports `app`, `residentialapps` or `utilityapps`, and nothing imports `applydesk`, except the host's registry, which names its factory as a string.
- **Exercise IDs:** 10 symbols from RRW's alphabet (`23456789abcdefghjkmnpqrstuvwxyz`, no look-alikes), drawn at random. The sample data uses IDs of that shape, and a route refuses any other shape with a 404, as RRW's `get_by_public_id` does.
- **File IDs are not application IDs.** A reviewer's URL names the application file (a profile page's until AD1C), never the application, so a blind profile's address carries nothing an applicant's own pages use.
- **Placeholders answer only locally, or a previewer**, as Residential's preview gate does (`residentialapps/spec/applications.md`). Deployed, nobody else reaches a page until it is wired.

## Judgment calls — decided

- **ApplyDesk keeps its own copy of the ID alphabet** rather than importing RRW's. Ruling 7 makes it a shared convention, not shared code, and the boundary forbids the import.
- **Participant paths sit under `/me`** whatever the role: an applicant's application and an assessor's application file share the namespace, as RRW's reviewer and reviewee pages do.
- **The landing page follows the shared header's landing pattern** (`docs/header_chrome.md`), not a page of its own design.

## Blast radius (measured)

Taken 2026-11-12 at `9bf80d5`.

| What | Count | Command |
|---|---|---|
| ApplyDesk code today | 0 files outside `docs/`, `guide/`, `README` | `git ls-files applydesk \| grep -v -e /docs/ -e /guide/ -e README \| wc -l` |
| Host registry entries to add | 1, in `cordware/main.py` `REGISTRY` (4 today) | `grep -n "AppEntry(" cordware/main.py` |
| Boundary-test lines naming `applydesk` | 0 | `grep -c applydesk cordware/tests/test_import_boundary.py` |
| Packaging | `applydesk*` absent from `packages.find` | `grep -n include pyproject.toml` |
| CI lanes | `applydesk/` already in `APP_DIRS` | `grep -n APP_DIRS tools/ci_lanes.py` |

## Status

Building. Base `573ffa3` (`main` before rung 2) for the cumulative read.
- Rung 2 (#3818): item 1 as planned; the favicon is the author's ApplyDesk icon (2026-11-02, kept in Cordware's favicon sources), a white sheet with a tick on rose `#be123c`.
- Rung 3: the gate admits the platform super-admin only when deployed, not a preview list as Residential's: ApplyDesk is not shipped, so it needs none yet. One template serves the seven operator sections, each a partial.
- **Read:** one `diff-reviewer` read of `573ffa3..` at rung 3. Fixed: the application and profile IDs were looked up before their shape was checked (now `applydesk/lookups.py`, shape first, and the route modules no longer import each other); Return to draft and Withdraw take Outline-amber; disabled buttons at 0.85 opacity, as Residential's; the tests now render the blind and draft exercises' pages, hold links to `url()` by mounting under another prefix, and call health with no identity; `/me` marks an invitation-only exercise; `docs/header_chrome.md` and the doc impact caught up. Sound as read: the gate, the blind profile, the registry and packaging.
- **Iteration rung 4** (author's browser check on Azure, 2026-11-12): the lobby shows an *Exercise Code* column, the operator's short code as an RRW session's, not the public ID; Home and Settings show the code too. Withdraw is Destructive (outline red): an applicant cannot undo it.
- **Iteration rung 5** (author, 2026-11-12): the operator's tabs are Home, Setup, Form, Applications, Panels and Reports, with Review kept as a seventh tab, between Panels and Reports (the author's chosen order). Home shows the timeline, the current stage marked; Setup holds the timeline's setup (milestones, announcements); Form adds a preview; Applications generates applicant profiles and imports outcomes; Panels holds three rosters, assessment panels, the reviewer pool applicants choose from, and interviewers; Reports collates every evaluation response, Review Robin's included, beside the data export. Settings, Assessors, Timeline and Export are gone; their paths are `404`. Its read, then the author: operators open every profile (author), so the list links it; profiles are made by *Generate*, not on submission; the form carries the pool's question; finished stages say *Done*; unset dates read *not set*; ruling 11 records the tabs and Panels.
- **Iteration rung 6** (author, 2026-11-12): a fourth sample exercise, *Graduate Travel Grant 2027* (`n5wg8tjr3e`), as just created: a name and nothing else. Home's Next step lists what a draft still lacks (Exercise Code, Summary, Dates, Who may apply, Application form), each linking to the tab that sets it, and a draft with nothing missing reads *Ready to publish*; the lobby, Home, Setup, Form and Review show empty or not-yet states. Its read: the applicant pages still read the global form constants, unreachable for a draft (they list and open only published exercises); switching them to `form_of` waits for its own slice.

## PR ladder

1. **Plan and rulings** (this file and `applydesk/guide/todo_master.md`).
2. **Item 1 — package and mount.** `applydesk/main.py` (`create_app`), `/health`, the registry entry and its `app_icons` entry, `packages.find`, the boundary tests, ApplyDesk's first tests, and drafts of `applydesk/spec/applications.md` and `applydesk/spec/architecture.md`. Record `main`'s SHA before this rung as the read's base.
3. **Item 2 — the URL map as placeholders.** Every row above, with sample data, the top bar, the preview gate and the shape-checked IDs; tests that every path answers locally and refuses a malformed ID. Last build rung: `diff-reviewer` reads the cumulative diff from rung 2's base.
4. **Iteration rungs**, as the author's browser checks ask, until item 2 is approved.
5. **Close.**

## Definition of done

- `CORDWARE_APPS=applydesk` starts alone and beside every other application; `/applydesk/health` answers `200` signed out.
- `cordware/tests/test_import_boundary.py` holds ApplyDesk's boundaries.
- Every path in the URL map renders its placeholder locally; a malformed exercise ID gets a 404.
- The author has approved the placeholders in a browser.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **`close_check.py` reads only RRW's `guide/`**, as Residential found at 1A. Check AD1's close by hand, as 1A was, unless the tool has learned the other folders by then (author).

## Out of scope

- The database, models, identity binding and operator grants: AD2.
- Anything wired: AD3 onward (`applydesk/guide/todo_master.md`, the roadmap).
- Cordware's import rules and `deployment/apps.toml` for `applydesk/`: classified in the first import that carries ApplyDesk code, in the private repository.

## Doc impact

- `applydesk/spec/applications.md` — new: registry entry, health, running alone, the URL map and who reaches each page (items 1–2).
- `applydesk/spec/architecture.md` — new: package layout, import boundaries, packaging, tests and CI (item 1).
- `cordware/spec/host.md` — the `applydesk` registry entry and its health path (item 1).
- `applydesk/README.md` — new: the package's index, as Residential's (item 1).
- `docs/header_chrome.md` — §3's ApplyDesk row and §8: the bar built (item 2).
- `residentialapps/spec/applications.md`, `residentialapps/spec/architecture.md`, `utilityapps/spec/utilities.md` — the registry order and boundaries with ApplyDesk in them (item 1).
- `applydesk/guide/todo_master.md` — the AD1 row, deleted at close.
