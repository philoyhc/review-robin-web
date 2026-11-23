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
