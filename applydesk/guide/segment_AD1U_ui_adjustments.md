# Segment AD1U — UI adjustments

**Opened:** 2026-11-23 · **Theme:** small adjustments to the pages' look, each its own item · **Related:** `applydesk/spec/applications.md`, `applydesk/templates/applydesk/base.html`

A standing segment (the author, 2026-11-23): it stays open while Apply Desk's
pages are built, and takes each small UI adjustment the author asks for as an
item. Items close on their own, so `Doc impact` and `Status` sit in each item.
The segment itself closes when the author retires it; an item's close
leaves the file here.

## Opportunity

Small adjustments to the pages come up between segments. One plan each would
cost more than the change, and folding them into an unrelated segment hides
them. A standing home keeps each one recorded and reviewable.

## Decision

Each adjustment is an item, and lands as one PR unless it needs a scaffold
first. An item that grows past a small change (a new page, a stored setting, a
spec contract of its own) gets its own segment instead.

Rejected: a register of adjustments with no plan. A register records what is
wrong; an item also records what was decided, and closes with the spec.

## Item 1 — Admin takes the operator pages' layout

### Opportunity

Admin's pages (`/admin/exercises`, `/admin/operators`, `/admin/system`) sit in
the participant's centred 1232 px column. Every operator page uses a fixed
40 px left margin and runs up to 1400 px wide. Moving between an exercise and
Admin moves the bar, the title and the cards (the author's screenshots,
2026-11-23).

### Decision

Admin takes the operator pages' layout: the `op` body class, set where
`operator_page` is decided (`applydesk/web.py`), for `/admin/…` as well as
`/operator/…`. Admin keeps no breadcrumb; its *Back to the exercise* link
stays.

Rejected: Admin's own wide class. It would be one more layout to keep in step,
for pages that are operator work surfaces too.

### Semantics

- Only the path decides: a non-operator never reaches `/admin`, so no other
  page's layout changes.
- Below 640 px, Admin takes the operator pages' 16 px gutters, as they do.

### Blast radius (measured)

Taken 2026-11-23 at `da8cf86d7`.

| What | Count | Command |
|---|---|---|
| Where the layout is chosen | 1 (`applydesk/web.py`) | `grep -rn "operator_page" applydesk/*.py` |
| Admin templates | 4 | `ls applydesk/templates/applydesk/admin` |
| Layout test | 1 (`test_mounts.py`) | `grep -rn '<body class=' applydesk/tests` |
| Spec lines | 1 (`applications.md`, "Layout") | `grep -n "1400 px" applydesk/spec/applications.md` |

### Status

- **2026-11-23, rung 2:** `operator_page` covers `/admin`
  (`applydesk/web.py`); `test_admin_takes_the_operator_pages_layout` fails
  without it. The browser check is owed
  (`applydesk/guide/things_to_check_in_browser.md`).

### PR ladder

1. **This plan.**
2. **The change:** `operator_page` covers `/admin`; `test_mounts.py` checks
   Admin's body class. Must not touch the Admin pages' content.
3. **Close:** the spec's "Layout" line names Admin; Status compacted.

### Definition of done

- Every Admin tab renders `<body class="op">` (`test_mounts.py`).
- `### Doc impact` section present and current
- `python3 tools/close_check.py AD1U.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

None.

### Out of scope

- Admin's cards and table widths inside the page: unchanged.

### Doc impact

- `applydesk/spec/applications.md` — "Layout": the operator's layout covers `/admin/…` too.
- `applydesk/guide/things_to_check_in_browser.md` — a section for Admin's layout, until the author checks it.

## Item 2 — Wide tables scroll inside their card on a phone

### Opportunity

At 390px, Panels' table and Admin → Exercises Diagnostics' table run past
their card and the page scrolls sideways (859px and 712px wide; the headless
sitting 1, 2026-11-23).

### Decision

Each sits in a horizontally scrolling wrapper, as Review Robin's wide tables
do, so the table scrolls and the page does not. Rejected: hiding columns at
narrow widths, which loses data the operator needs.

### Status

- **2026-11-23:** planned with Items 3 and 4.
- **2026-11-23, build:** both tables were already in a scrolling
  `.table-wrap`; the page widened through each table's visually hidden
  header label (absolute), placed outside the wrap. `.table-wrap` is now
  `position: relative`, so the label is clipped with its table. Rejected as in Decision, and no markup changed.

### PR ladder

1. **The change:** the two tables wrapped; a browser test that neither page
   scrolls sideways at 390px.

### Definition of done

- Panels and Exercises Diagnostics do not scroll sideways at 390px (a
  browser test).
- `### Doc impact` section present and current
- `python3 tools/close_check.py AD1U.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

None.

### Doc impact

- `applydesk/guide/things_to_check_in_browser.md` — a row for the two tables at 390px.

## Item 3 — No "nothing is saved" banner where things are saved

### Opportunity

The Lobby, Home and Process still carry *Placeholder. Sample data: what you
do here works on screen, but nothing is saved, and a reload restores the
sample.* Since AD2B and AD2C they save: the Lobby's panel, Home's Details and
Owners card, and Process. The banner now says the opposite of what happens.

### Decision

The banner goes from those three pages; the pages still on sample data keep
it, and a scratch exercise keeps its own note. Rejected: rewording it there,
since nothing on those pages is still sample-only enough to need a line.

### Status

- **2026-11-23:** planned with Items 2 and 4.
- **2026-11-23, the change:** `_placeholder.html` takes a `saves` flag, set
  by `exercises.html`, `home.html` and `section.html` (Process only);
  `test_pages.py` (`_SAVES`) fails if the line shows on those pages or goes
  from the rest.

### PR ladder

1. **The change:** `_placeholder.html` says nothing on the Lobby, Home and
   Process; `test_pages.py` holds which pages carry it.

### Definition of done

- The Lobby, Home and Process carry no *Placeholder* line; Form, Panels,
  Emails, Dossiers, Evaluations and Extract still do (`test_pages.py`).
- `### Doc impact` section present and current
- `python3 tools/close_check.py AD1U.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

None.

### Doc impact

- `applydesk/spec/applications.md` — the placeholder line (AD-06) is not shown on the Lobby, Home or Process.

## Item 4 — The Archive's rows link to the exercise, as Review Robin's

### Opportunity

Review Robin's Archive links each session's name to its Home
(`app/web/templates/operator/sessions_archived.html`); Apply Desk's lists the
name as plain text, so an archived exercise's Home is reachable only by URL.

### Decision

The name links to the exercise's Home, which already reads *Archived:
read-only* with a link back to restore it (the author, 2026-11-23: follow
Review Robin).

### Status

- **2026-11-23:** planned with Items 2 and 3.
- **2026-11-23, the change:** `exercises_archived.html` links the name;
  `test_archive.py::test_an_archived_row_names_the_exercise_and_links_to_its_home`
  fails without it.

### PR ladder

1. **The change:** the link; a test that an archived row links to its Home.

### Definition of done

- An archived row's name links to the exercise's Home (a test).
- `### Doc impact` section present and current
- `python3 tools/close_check.py AD1U.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

None.

### Doc impact

- `applydesk/spec/applications.md` — "The Archive": a row's name opens the exercise's Home.

## Item 5 — Add buttons read `+Noun`, as Review Robin's

### Opportunity

Apply Desk's add buttons read `+ Stage`, `+ Gate`, `+ Candidates` and the rest,
with a space; Review Robin's read `+Shape` and `+Instrument`, without one. The
open decision *Back to Review Robin (AD1P)* asked which way to go.

### Decision

Apply Desk follows Review Robin: `+Noun`, no space (the author, 2026-11-26).
Settles the open decision's `+ Noun` half. Rejected: changing Review Robin's,
the older and larger set.

### Status

- **2026-11-26, the change:** every `+ Noun` label in Apply Desk's templates,
  their scripts, its spec and the tests that name them, 27 files; the full
  Apply Desk and unit suites pass. The cold read found the rule editor's
  *+Condition* and *+Else if*, the spec's own `+Noun` line and a
  line-wrapped *+New panel…* missed; fixed in the same PR.

### PR ladder

1. **The change:** the labels, the spec's wording and the tests.

### Definition of done

- No Apply Desk template or spec writes a label as `+ Noun`
  (`grep -rnE '"\+ [A-Z]|>\+ [A-Z]|\*\+ [A-Za-z]' applydesk/templates applydesk/spec`
  finds nothing).
- `### Doc impact` section present and current
- `python3 tools/close_check.py AD1U.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

None.

### Doc impact

- `applydesk/spec/applications.md` — every add button's label as `+Noun`.
