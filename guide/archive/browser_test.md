# Browser tests — the hand checks, made repeatable

**Opened:** 2026-10-01 · **Theme:** committed browser tests that run in CI
on every PR, so a builder sequence the author has checked stays checked ·
**Related:** `guide/post_azure_todo_checklist.md` items 5 and 6 (the rows
these tests come from), `guide/codebase_assessment_30sep.md` §5 and §8
move 1 (the case for it).

A standalone plan rather than a `segment_*.md`, at the author's naming.
`tools/close_check.py` reads segment ids, so this plan closes by its own
definition of done rather than by that tool.

## Opportunity

The author checks every change in a browser against a local run. Nothing
repeats those checks. The Instruments builder is client-side staging
before one save, in one inline script inside
`app/web/templates/operator/instruments_index.html` (7,202 lines). The
suite proves the posted payload and that the script parses, not that a
click sequence produces it. So an edit to that script can break a sequence
the author already approved, and only the next hand check would notice.

Evidence the class is real: headless Chromium, driven by hand during 19T,
found three defects on main in Item 1 alone. Of thirty fix commits counted
by the 2026-09-04 audit, fifteen were browser-only
(`rrw_sdd_in_practice.md` §6.6). Every one of those Chromium drives was a
throwaway script: 151 of them in one session's scratchpad, gone with the
container.

## Decision

Python Playwright tests under `tests/browser/`, run by `pytest` like the
rest of the suite, **required in CI** on every PR (author, 2026-10-01).

- **A live server, not a rendered snapshot.** A session-scoped fixture
  migrates a temporary SQLite file, starts `uvicorn app.main:app` on a free
  port with `ALLOW_FAKE_AUTH=true`, and tears it down. The browser talks
  to it over HTTP, so a Save reaches the server and a reload proves it
  persisted.
- **Seeding through the app's own routes**, over HTTP, the way
  `tests/integration/test_instrument_builder_routes.py`'s `_make_session`
  and `_populate_rosters` use the `TestClient`. Each test makes its own
  session with a unique code, so tests share a server but not data.
- **Assertions on the DOM and on the server's state**, and waits on
  conditions (`expect(...).to_be_visible()`), never fixed delays.
- **Skipped locally when the tool is missing; failed in CI.** Without
  `playwright` or a Chromium build the tests skip and say so in the skip
  reason. `RRW_REQUIRE_BROWSER=1`, set in `ci.yml`, turns that skip into a
  failure, so CI can't pass a browser suite by not running it.

**Rejected: sandbox-only, like `tools/css_parity_check.py`.** It adds no
dependency, but it runs only when an agent remembers to run it. It would
also add a second silent skip to a suite whose `CLAUDE.md` calls
`test_inline_scripts_parse.py` "the suite's only tool-gated skip".
**Rejected: Node Playwright.** The 151 scratch scripts were Node, but the
suite, its fixtures and CI are Python, and a second test runner is a second
thing to keep green.

## Semantics

- **Version pin.** `playwright==1.56.*` matches the sandbox's preinstalled
  `chromium-1194` (`/opt/pw-browsers`, the Node 1.56.1 install's build), so
  the sandbox needs no download. CI runs `python -m playwright install
  --with-deps chromium`, which fetches the same build. A version bump is a
  deliberate change, made in both places together.
- **xdist.** `pytest -n auto` gives each worker that collects a browser test
  its own server and browser; workers that collect none start nothing.
- **Fake auth only.** The tests sign in as the fake operator. Real Easy
  Auth stays a deployment check (`CLAUDE.md`, "Where work runs").
- **SQLite only.** `ci-postgres.yml` doesn't run them; the live app on
  Postgres is a deployment check too.
- **Not a layout test.** Pixel widths and "reads right" are the author's.
  A test asserts behavior: a row appears, a button disables, a value
  persists.

## Judgment calls — decided

- One file per surface (`test_builder_rows.py`, `test_builder_branching.py`,
  `test_owners_card.py`, `test_tag_typeahead.py`), not one per checklist
  row: rows share setup.
- The checklist rows stay in `guide/post_azure_todo_checklist.md` as the
  record of what the author checked; a test cites the row it covers in its
  docstring rather than the checklist citing tests. *(Reversed 2026-10-16:
  the rows moved to this file's appendix once settled.)*

## Blast radius (measured)

Taken 2026-10-01 at `85f8f92d`.

| What | Count | Command |
|---|---|---|
| Checklist rows, item 5 (owners, tags) | 12 | `awk '/^## 5\./,/^## 6\./' guide/post_azure_todo_checklist.md \| grep -c "^\| [^C-]"` |
| Checklist rows, item 6 (builder) | 40 | `awk '/^## 6\./,0' guide/post_azure_todo_checklist.md \| grep -c "^\| [^C-]"` |
| `<script` blocks in the builder template | 12 | `grep -c "<script" app/web/templates/operator/instruments_index.html` |
| Existing tool-gated skips | 1 | `test_inline_scripts_parse.py`'s `pytestmark = pytest.mark.skipif(` |
| CI `test` job today | 2 min 19 s | #2704's run, 02:54:32 → 02:56:51 |
| Smoke run (live server, one page, sandbox) | 7.3 s total, 2.6 s browser | scratch `pw_smoke.py`, 2026-10-01 |

Files the build touches: `pyproject.toml` (dev dependency),
`.github/workflows/ci.yml` (browser install, `RRW_REQUIRE_BROWSER=1`),
`tests/browser/` (new), `README.md` (tooling changed), `CLAUDE.md` /
`AGENTS.md` (the tool-gated-skip sentence), `docs/local_setup.md` (running
them locally). `.claude/hooks/session-start.sh` already runs
`pip install -e ".[dev]"` every session, so the sandbox picks the dependency
up with no change there.

## Status

Closed 2026-10-01, PRs #2706 → #2710 and this close. **34 tests** in
`tests/browser/`, run by `pytest -n auto` in the sandbox and required in
CI's `test` job; about 25 s of browser time per run.

**What the ladder became.** Rungs 1–5 landed as planned, one PR each: the
harness and one Save-and-reload test (2); 14 builder-row tests (3); 6
builder branching and 2 reviewer branch-row tests (4); 11 Owners-card,
typeahead and Create tests (5). Every test from rung 3 on names its
checklist row in its docstring; rung 2's Save round trip is the harness's
smoke test and repeats no single row. The tag file is `test_tags_and_create.py`, not
`test_tag_typeahead.py`, because Create's Owners card shares its setup.

**Divergences from the plan:**
- **A missing `playwright` is an import error, not a skip**: it is a dev
  dependency like `pytest`, so only a missing Chromium skips, and fails
  under `RRW_REQUIRE_BROWSER=1` (checked with `PLAYWRIGHT_BROWSERS_PATH`
  pointed at nothing: 34 skipped, or 34 errors with the variable set).
- **`ci-postgres.yml` passes `--ignore=tests/browser`**, an exclusion said
  out loud rather than a skip.
- **`.claude/hooks/session-start.sh` changed**, against Blast radius: it
  warns when no Chromium is found, as it does for `node`.
- **People other than the fake operator** sign in through the Easy Auth
  headers, which `app/auth/identity.py` reads first; colleagues come from
  `OPERATOR_EMAILS`. A full matrix is pinned through the server's database,
  as `tests/integration/_full_matrix.py` does.
- **The browser is module-scoped**, with a session-scoped launch check
  owning skip-or-fail. Session-scoped, it kept sync Playwright's event loop
  running in each xdist worker, and a later `asyncio.run()` on that worker
  failed (`test_session_new_tags_card.py`, found by CI on #2710).

**CI cost:** the Chromium install step takes 21 s; the `test` job went from
2 min 19 s (#2704) to 2 min 29 s at rung 2 (#2707) and 2 min 42 s with all
34 tests (#2710's head, `9a2a5d12`).

**Rows not automated, with the reason:**
- *The hide-confirm on a field with saved responses* — an activated
  session's card won't unlock.
- *A refused parent keeps the text* — the number input carries `max`, so
  Chromium's own validation stops the Save before the server can refuse it.
- *Create is unchanged, JavaScript off* — Create can't submit at all
  without script: its button renders `disabled` (since `9cfb70e1`,
  2026-05-22), while `spec/session_owners.md` and a `session_new.html`
  comment still describe that path. A defect, not a test gap.
- *The datalist popup* (headless draws none), *Owners above the Danger
  Zone* (layout), and the parts of rows tested only in part: relocking via
  another session's Home, Quick Setup's lock unaffected, the details card
  staying locked when Activated, and the lobby's two typeahead boxes.

The refused parent and the no-JS Create were raised with the author and
were unanswered at the close.

**Reads:** two `diff-reviewer` reads. The cumulative read at rung 4
(`df7a5942..b8f35a33`) found seven issues, all fixed: two tests claimed more
than they checked, a port race under xdist, a server that might not stop, a
silent migration failure, fake-auth keys a developer's `.env` could
override, and a redundant click. Rung 5's own read found seven, all fixed,
mostly tests asserting less than their row. Template breakages were used
to check that tests fail: two at rung 3, four at rung 5. Codex found one
more at rung 5: the lock test had checked a Remove button that was already
disabled for another reason.

## PR ladder

1. **This plan.** Prose only.
2. **The harness and one test.** `tests/browser/conftest.py` (server,
   browser, seeding helpers, the skip-or-fail rule), one test (unlock an
   instrument, rename a field, Save, reload, the name persisted), the
   dependency, the CI step, and the README, `CLAUDE.md` and
   `docs/local_setup.md` edits. Settles the CI cost on something small. Must
   not touch `app/`.
3. **The builder rows.** Item 6's rows a headless browser settles: "+",
   default names, the preview following a row, Active and ▲ ▼, R and ≡ alone,
   a new field saved twice, order persisting, the last row kept, Cancel,
   Delete's checkbox, Name and Email fixed, visibility in the card.
4. **Branching.** ⑂, join and detach, List conditions, the Active cascade,
   two levels, range conditions, and the reviewer-side branch rows (closed
   cell, refused parent, required only while open). **Expected last build
   rung: `diff-reviewer` reads the cumulative diff from the base SHA rung 2
   records.**
5. **Owners and tags.** Item 5's rows: the lock, Add owner and Remove saving
   at once, the last owner, the self-remove confirm, relocking, Create
   unchanged, and the typeahead's filtering and Enter in Chromium (not the
   popup, which headless doesn't draw). Reopens `tests/`, so it takes its
   own read.
6. **Close.** Definition of done checked, `docs/status.md` row.

## Definition of done

- `tests/browser/` exists and `pytest -n auto` runs it in the sandbox with
  no skip.
- `ci.yml` installs Chromium and sets `RRW_REQUIRE_BROWSER=1`; a PR run
  shows the browser tests passing, and removing the browser makes the job
  fail rather than skip.
- Every item 5 and item 6 row a headless browser can settle has a test
  naming it in its docstring; the rows it can't are listed in this plan's
  `Status` with the reason.
- The CI `test` job's added time is recorded in `Status`.
- `README.md`, `CLAUDE.md` / `AGENTS.md` and `docs/local_setup.md` describe
  the new tests and how to run them.
- `## Doc impact` section present and current.
- `spec-writer` not needed: no `spec/` change is planned.
- `## Status` compacted to intended vs done; answered open questions
  collapsed.
- `docs/status.md` row added; plan moved to `guide/archive/` + index row.

## Open questions

- **Does a layout measurement ever become a test?** Not ruled; shipped as
  proposed: none does.
- **Run them on the `postgres:16` job too?** Not ruled; shipped as
  proposed: excluded, by `--ignore` (Status).

## Out of scope

- **Visual regression** (screenshot diffs): brittle against intended change,
  and the author's eye is the check.
- **Safari and screen readers**: `guide/deferred_consolidated.md` Part C.
- **Real Easy Auth, the network, the deployed configuration**: deployment
  checks, `guide/post_azure_todo_checklist.md`.
- **The builder-script extraction**: waits for its trigger
  (`guide/codebase_assessment_30sep.md` §8 move 3), and goes better after
  this lands.

## Doc impact

- `README.md` — the browser tests, their dependency, and how CI runs them (rung 2).
- `CLAUDE.md` — "Where work runs": the tool-gated skip sentence names the browser tests and `RRW_REQUIRE_BROWSER` (rung 2); `AGENTS.md` copied.
- `docs/local_setup.md` — running the browser tests locally, including `playwright install chromium` (rung 2).
- `docs/status.md` — a row at the close.
- `.claude/hooks/session-start.sh` — warn when no Chromium is found (rung 2).

## Appendix — the rows the author checked

Moved here on 2026-10-16 from `guide/post_azure_todo_checklist.md`
items 5 and 6, once settled: the judgment call above kept them in that
checklist "as the record", and the checklist's own rule sends settled
items out. The browser tests cite these rows by item number.

### 5. Verify Session Home's Owners card and the tag typeahead in a browser

**Status:** **checked locally by the author, 2026-10-01**, in a browser
against the app on `localhost` with fake auth. The two rows that name
more than that, the keyboard pick in **Safari** and **a screen reader**,
need no deployment either, so they moved to
`guide/deferred_consolidated.md` Part C rather than waiting here.

**What.** Segment 19S Item 10 gave Session Home's Owners card a card
of its own, where each Add owner and Remove saves at once
(`spec/session_owners.md`; its Lock / Unlock retired 2026-10-09,
`guide/archive/operator_pages_enhancements.md` Item 1), and Item 7 put a typeahead on
the four tag boxes. The suite pins their markup; headless Chromium
drove the scripts, but draws no datalist popup.

**Done when** each has been seen, in a real browser:

| Check | How | Passes when |
|---|---|---|
| The card is live | Open Session Home | The Owners card has no Lock / Unlock; the picker, Add owner and another owner's Remove work at once |
| Add owner saves at once | Session Home → Owners card: pick an operator, **Add owner** | The page reloads at the card with them in the table and gone from the picker; no banner |
| Remove asks, then saves at once | Click **Remove** on another owner's row | The browser's confirm names them; **Cancel** posts nothing. Confirming reloads with that row gone and them back in the picker |
| The last owner cannot go | On a one-owner session | That row's Remove is disabled |
| Removing yourself asks | Click Remove on your own row | The browser's confirm names losing access; **Cancel** posts nothing. Confirming lands on the sessions lobby |
| Any lifecycle state | Repeat the first row on an Activated session | It saves; the details card stays locked |
| Without JavaScript | Disable JavaScript, reload Session Home | Add owner and every Remove still work (plain forms); every Remove skips the confirm |
| Owners sits above the Danger Zone | Session Home, wide and narrow windows | Owners starts level with Quick Setup and the Danger Zone follows it in the right column; narrowed, the order is Quick Setup → Owners → Danger Zone |
| Create is unchanged | Create new session → Owners, JavaScript on and off | On: Add owner stages a row and a staged row's Remove takes it out again, with no confirm; Create session saves what remains. Off: no Add owner; the picker's one address is saved with Create session. *(Off could not pass before #2714, 2026-10-01: Create rendered disabled without script; now `test_create_without_javascript_saves_the_typed_owner` repeats it.)* |
| The tag popup, after each comma | The lobby's row and bulk expanders, Create's Tags card, Session Home's Tags field: type `a` then `pilot, e` | A popup of your existing tags each time, completing only the tag after the last comma, never offering one already in the box |
| The keyboard picks | In each box, arrow to a suggestion and press Enter — **Safari as well as Chromium** | Enter takes the suggestion. In the lobby's expanders it must never submit the form (#2579: Enter in the lobby form does nothing) |
| A screen reader | VoiceOver or NVDA on one box | The suggestions are announced as a list |

**Where this came from.** `guide/archive/segment_19S_post_assessment.md` Item 10
and Item 7, both closed with this check owed; each `### Status` points
here. Settling a row is a dated line there, not a reopening.

### 6. Verify the Instruments response-field rows, action row and small fixes in a browser

**Status:** **checked locally by the author, 2026-10-01**, in a browser
against the app on `localhost` with fake auth. Nothing in the table
needs a deployment.

**What.** Segment 19T Items 1 and 2 reworked Band 3's response-field rows:
- a "+" on each row;
- the last row kept;
- ✓ enabled only when the row differs from its pill;
- R and ≡ saved by Save alone;
- row-ordered ✓, Save and pill drag;
- the 2 : 3 split.

Item 9 then retired ✓ and the response pills: the rows became a table with
an Active checkbox and ▲ ▼, a valid row reaches the preview by itself,
added fields default to a muted "Field N", and Band 3 splits 15 : 85 (1 : 4 until Item 12A).

They also stopped an open card (`?editing`) from disabling the action row.
Item 3 made the Name and Email pills static labels, kept Delete's confirm
checkbox from dirtying the card, and made Band 2's "Who can see what you
wrote" card repaint on a Band 3 Visibility edit. Item 6 put a `*` on the
Required pill, refused fractional Integer bounds and printed Decimal
bounds as entered. Item 7 moved the visibility editor into Band 2's "Who
can see what you wrote" card. Item 8 moved display fields from Band 2's
pills to a table in Band 3's left column. Item 10 added branching: ⑂ or
↰ puts optional governed fields under a number or List field, shown on
the reviewer surface only while the parent's answer meets a condition. Item 12
added ranges to a number's condition: within or outside two ends,
inclusive or exclusive.
The suite pins the markup, and headless Chromium drove the rows on a
rendered page; the author checked them in a browser.

**Done when** each has been seen in a browser, card unlocked:

| Check | How | Passes when |
|---|---|---|
| The rows | Open an instrument card, one with a branch | One row per saved field in a table. A plain field or a parent reads Active, "+", ⑂, ↰, name, type, bounds, R, ≡, ▲, ▼, X; a governed row shifts one column right before the name (the bar, Active, "+", ↳) and has no ⑂. A rule sits under each plain field and under each branch as a whole — the parent, its condition row and its governed rows share one. X is red; "+", ⑂ and ↰ / ↳ are one width; Band 3 splits 15 : 85 |
| "+" inserts below | "+" on the first of two rows | A row appears between them, its name box showing a grayed "Field N", cursor in it; the preview gains the column |
| Default names | In that row press →; clear the name; type "Rating" then clear it | → turns "Field N" into normal text; cleared, it shows grayed again; after Save and a reload a kept "Field N" reads as normal text |
| The preview follows the row | Type a name; switch the row to Integer and set Max below Min | The preview follows the name at once; the bad Max marks the row amber with the reason on hover, and the preview keeps the last valid shape |
| Active and ▲ ▼ | Untick Active on a field with responses; ▲ on the second row | The "hide this field?" confirm names Active, and cancelling keeps the tick; ▲ swaps the rows and the preview columns, and Save keeps the order |
| R and ≡ alone | Toggle R on a saved field, nothing else | Save enables; after Save and a reload, the field's required state stuck |
| A new field saves twice | "+", Save, rename it, Save again, reload | One field with the new name, not two |
| Order persists | Insert a row between two, name it, Save, reload | It sits between them |
| The last row stays | Delete rows down to one | That row's X is disabled |
| Cancel removes a new row | "+", then Cancel and confirm | The new row is gone |
| An open card doesn't lock the row | Edit, Cancel (URL now `?editing=`), then Lock | Replicate, +Instrument and +Page break stay live; the URL loses `?editing` |
| Delete's checkbox is clean | Tick the Delete confirm box on a clean card | Save stays off; Delete leaves without a "Leave site?" prompt |
| Name and Email are fixed | Click Name's and Email's checkboxes in Band 3's display-field table | They stay ticked and never toggle, with no ▲ ▼; they sit first and second in the preview |
| Email on group rows | Switch Unit to Group, then back | Email dims with "Not shown on group rows", then returns |
| Visibility preview repaints | Cycle You's "Responses released" in Band 2's card, Save, Lock, reload | The locked card shows the new mode and still reads the same after the reload |
| The Required pill's `*` | Open an instrument card with a required field; open the reviewer preview | Both pills read "*Required items completed", legible in capitals beside the `*` headers |
| Integer steps are whole | On an Integer row, set Step 0.5 | The row turns amber with "Integer fields take whole-number Min, Max and Step. Choose Decimal for steps like 0.5." on hover; Save refuses it naming the field; switched to Decimal, the amber clears |
| Integer Step defaults to 1 | Add a field, make it Integer, name it, set Min 1 and Max 5, leave Step blank; Save; reload; open the reviewer preview | Before Save the Step box shows the muted "Step"; after Save it reads 1, and still does after the reload; the constraint line reads "1-5, steps of 1" |
| Decimal bounds as entered | Decimal row 0–1, Step 0.25, Save; open the reviewer preview | The line above the table reads "0-1, steps of 0.25" |
| Display fields table | Unlock an instrument; untick Tag 1, move Tag 2 up with ▲, drag a preview column edge; Save; reload | Band 2 has no display pills; Band 3's left column lists Name and Email ticked and fixed, then the rest as compact rows with name pills. The preview drops Tag 1 and reorders at once; after Save and reload the order, selection and width hold, and the reviewer preview matches. On a group-scoped instrument Email is unticked and fixed |
| A long display label, unlocked | Give a tag a long label; unlock an instrument | In Band 3's left fifth the row's ▲ ▼ stay reachable, scrolling with the table if the label widens it |
| Visibility pills when locked | Lock an instrument card | "Who can see what you wrote" shows each mode as a pill, like the editor's fixed cells; a long display-field label scrolls inside Band 3's left column rather than widening it |
| Visibility in the card | Unlock an instrument; cycle Reviewees' "Responses released" and Observers' "Session ongoing"; Save; Lock | Unlocked, the card shows You (reviewer) / Reviewees / Observers with the note, and Band 3 has no Visibility table. After Save and Lock, the locked card shows the new Reviewees mode and no Observers row; a reload keeps both changes |
| A branch with ⑂ | ⑂ on an Integer row; type 4 in the condition | A condition row ("If the above [=] [4] then [Show the below]", the last a select whose other option is "Require the below (else, optional)") and one grayed "Field N" appear under a broad, pale bar; the condition is amber until a value is typed; the parent's X is off and String is disabled in its type select |
| Join and detach | ↰ on a plain row just below the branch; then ↳ on it | ↰ makes it the branch's last field; ↳ puts it directly below the branch; ↳ on a branch's only field removes the condition too |
| List conditions | A List parent with a branch; pick "is not"; name an option the list lacks | The operator offers "is" and "is not"; the missing option turns the condition amber, naming it |
| Active cascades | Untick a parent's Active, then tick it | Its branch's rows untick and their Active boxes go off; ticking the parent restores them |
| The branch for a reviewer | Save a branched instrument; open the reviewer preview; answer the parent under, then over, the condition | The governed cell is muted and disabled, titled "Opens when …", and opens as the answer meets the condition; text typed there greys, not clears, when the branch closes, and Save deletes it if it's still closed |
| A refused parent keeps the text | With JavaScript off, as a reviewer, save the parent with its branch open; then type 2.5 in the Integer parent and a governed answer; Save | Both come back with their text; the parent reads "Must be a whole number." and the governed one "Kept until … is fixed."; neither was saved. (With script on, the browser refuses 2.5 before Save posts; the operator preview has no Save.) |
| A locked branch | Give a governed field a response; reopen the card | The condition, the branch's "+"s and its fields' X and ↳ are off |
| The export's condition | Download the by-instrument bundle for a branched instrument | The governed field's metadata carries a "Shown when" row ("Rating ≥ 4") |
| A required governed field | Press R on a governed row; Save. Then untick R on every field outside the branch; Save | The first saves, with R pressed. The second is refused, naming the governed field: "…can be required only when the instrument has an active required field outside any branch." In the preview, the "*Required items completed" count doesn't include it |
| Required only while open | As a reviewer, answer the parent under, then over, the condition; submit with the governed field empty each time | Under: it submits; the field's label doesn't say "(required)". Over: the label says "(required)", the pill's total grows by one, and Submit lists the field as missing. Invitations and Responses count the reviewer complete in the first case and not in the second |
| A Require branch | On a branch's condition pick "Require the below (else, optional)"; Save; as a reviewer, answer the parent under, then over, the condition, leaving the governed field empty | In the builder, the governed rows' R grays out, titled "Required while the condition holds", keeping how it was pressed (back to Show restores it); the preview's governed column is no longer muted, gains "*", and counts in "All items" but not "Required items". For the reviewer the governed cell is always open: under, it submits empty; over, its label says "(required)" and Submit lists it as missing. Downloaded by instrument, its metadata reads "Required when". With a governed response saved, the select is off |
| Two levels of branching | On a branch's Integer field press ⑂; name the new field; then ↰ on the plain row below the group, ↳ on it, ▼ on the level-1 parent, and untick its Active; Save; answer as a reviewer | The new condition row and field sit one column further right with their own bar, the name column never moving; ↰ joins the level-2 branch and ↳ steps it back to level 1; ▼ carries the level-1 field's branch with it; unticking it hides its branch. Save keeps the chain; a third level is refused by name. For the reviewer, closing the top field closes the whole chain even if the middle answer still meets its own condition. With a level-2 field answered, both conditions above it lock |
| Range conditions | On a numeric parent's condition, open the operator select; pick "is within (inclusive)"; type 2 and 4; then "is outside (exclusive)"; then "is more than (inclusive)" | Ten spelled-out operators; a range shows a second box after "to", amber until both ends are numbers with the low below the high; the hint reads "Opens when Rating ≥ 2 and ≤ 4", then "Rating < 2 or > 4"; a single-value operator hides and clears the second box. After Save, the reviewer preview opens the branch at 2 and 4 for within (inclusive) and only below 2 or above 4 for outside (exclusive) |
| Item 12A's table adjustments | Open a card with a numeric branch and one with a List branch (or switch a parent between Integer and List); widen and narrow the window | Join reads ↰ and detach ↳; a number condition's boxes stay as wide as the parent's Min box; every Active checkbox sits centered in its cell; after ↰ / ↳ there's a gap two buttons wide before the name; the condition's operator lines up with the name boxes, same width, "If the above" right-aligned just before it; the first value box starts under the type column, with the same gap after the operator as between name and type; on a narrow card, hovering the operator or a long name shows it in full (not while the row is amber; a range shows no symbol; a locked branch adds its reason); on a List parent the operator shrinks to "is not" with its box, the List box's width, and "then [Show the below]" right beside it; display fields take 15% of Band 3; below about a 1390px window the response-field table scrolls sideways while editing, its boxes keeping their size, and scrolling reaches R, ▲ ▼ and X; a locked card's two tables scroll too, as does Band 2's preview once its columns are dragged wider than the card (unlock, drag, Save, lock), their controls still locked, and tabbing through a locked card reaches none of the bands' controls (a scroll box may take focus to scroll); below about a 1330px window Band 1 scrolls sideways (locked too) rather than spilling past its dividers, and a Link 2 rule set to "IS DIFFERENT FROM" fits at any width; on a List parent set to "is not", picking a Quick fill preset keeps "is not" |
| Band 1's buttons keep their size | Unlock an instrument; look at Band 1's rule and unit rows and Band 2's refresh | The "+", AND / OR, THE SAME, operator and X buttons are the size they were before #2659, lined up with their selects |
| Full-size sample rosters | Guide → Sample session → full-size download; upload both files in Quick Setup on a new session | 154 reviewers and reviewees, tag columns Tutor / Group / Team, a Profile column on Reviewees |
| The instrument intro's two columns | As a reviewer, open a session whose instrument has help text on two or more fields, then one with none; narrow the window below 800px. On the Instruments page, lock and unlock the card | On both surfaces the left column is the name card over "Who can see what you wrote", the right every help card in field order, each card its own height; no card moves on resize, typing, Lock or Unlock. With no help text the right half is empty. Below 800px one column: name, visibility, help cards |
| Band 2's name card as the reviewer's | On a one-instrument session set a short label and no description; lock the card; compare with the reviewer's view. Then add a description, Save, Lock; then clear both, Save, Lock | Band 2 reads "Group Peer Review" with no "#1:" and no blank line under it, the reviewer's height; after Save and Lock the new title and description show; with neither, the locked card is not drawn. With two instruments both surfaces read "#2: …" |
| Item 16's small fixes | Open the Band 2 preview and a reviewer table with a Profile and a number column; drag a column to save a width, then open that instrument's reviewer summary and a reviewee's results; open a group-scoped instrument's reviewer table; open Settings at full width and below 800px; click into the App password box; Tab onto a roster's Upload CSV file input | Profile and number columns start at their label's width, not a sliver, on the preview, the reviewer table, the summary and the results, with or without a saved width; the status column is "Status" wide on the group table and once any width is saved; Settings has the SMTP card alone on the left and Date & time over Clear all settings on the right, stacking with a gap when narrow; the password box matches its neighbors; the file input shows the app's focus ring |

**Where this came from.** `guide/archive/segment_19T_advanced_instruments.md` Items 1–4, 6–14, 12A, 16 and 17,
each closed with this check owed. Settling a row is a dated line
there, not a reopening.
