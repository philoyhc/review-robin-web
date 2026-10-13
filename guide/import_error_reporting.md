# Import error reporting

**Opened:** 2026-10-12 · **Theme:** showing an operator every problem an
upload had, where the page that refused it cannot · **Related:**
`spec/quick_setup_card_spec.md`, `spec/rehydrate.md`,
`spec/settings_inventory.md`

A standalone plan at the author's naming, not a `segment_*.md`, in the
shape of `guide/archive/participant_info.md`: items close independently, each
with its own `### Doc impact` and `### Status`, checked by hand at close
(`tools/close_check.py` reads only `segment_*` files).

**Reuse is the brief** (author, 2026-10-12): Item 1 builds the report
once, for Quick Setup. Later items plug Rehydrate, Duplicate and
anything else into it, with no new store or page.

**Deferred, unbuilt** (author, 2026-10-12). The banner's summary of the
kinds of problem shipped on its own (#2997). This plan keeps the design
ready. Its lift trigger is in `guide/deferred_consolidated.md` ("Every
problem a refused upload had"), and nothing here is queued.

---

## Item 1 — A refused upload's full problem list, one link away

### Opportunity

A refused Quick Setup file redirects to Session Home, and only the query
string survives the redirect. So the banner can name the *kinds* of
problem (#2997) but never *which rows*. A 5,000-row file's list does not
fit in a URL, so it has to be stored to survive the redirect. Create's
Quick Setup lands on the same banner. Rehydrate already stores a
dropped-responses CSV for its page to hand out (`spec/rehydrate.md`).

### Decision

**Pending the author's choice of path** (Open question 1); A is
recommended. Both paths share one design: a refused upload stores an
**issue report** on the server and the redirect carries only its
**token**. So no row number or cell value ever reaches a URL.

- **Store.** A new table, `issue_reports`, with a token, the operator,
  an optional session, a `kind` (`quick_setup` first), a JSON payload
  and a creation time. Reports are visible only to the operator who
  uploaded, and last an hour, as `rehydrate_stashes` do. Each new
  report deletes the expired ones.
- **Service.** `issue_reports.put` / `get` / `section_from_issues` (the
  last turns a `ValidationIssue` list into a section).
- **One views adapter, two renderings.** The HTML page and the `.txt`
  read the same shape, so they cannot disagree.
- **Routes.** `GET /operator/issue-reports/{token}` and
  `/operator/issue-reports/{token}.txt`. They sit outside
  `/sessions/{id}`, so a consumer with no session yet (Rehydrate before
  its commit) can use them.

**Path A, a page in a new tab.** The banner gains `See every problem`.
The page gives the session, file and time, the kinds of problem
uncapped, a `Row` | `Column` | `Problem` table, and a Secondary
`Download as text` button.

**Path B, an immediate download.** A 303 cannot carry a file, so a
script on Session Home would start the `.txt` and strip the token. Not
recommended: some browsers block a download nobody clicked, retries
pile up as `…(1).txt`, it does nothing with scripts off, and it needs
the same store as A.

**Rejected: reusing `rehydrate_stashes`.** Its `get()` returns raw bytes
for any token the operator holds, so a report token could reach
Rehydrate's commit as if it were a file set.

### Semantics

- **An expired, unknown or other operator's token**, or a session the
  operator no longer runs, gets one 404 page that doesn't say which.
  Deleting the session deletes its reports.
- **A file-level issue** shows `File` as its row. **Submit-all** makes
  one report, for its first failing slot. **Settings** errors fill a
  section too. `lifecycle` and `needs_confirm` make no report.
- **At most 5,000 issues**, then "…and N more". Cell values are shown in
  full: they come from the operator's own file.
- **The `.txt`** is UTF-8, one line per issue, named
  `<session code>-<slot>-problems.txt`.

### Judgment calls — decided

- **One table with a `kind` column**, not one per feature. **A JSON
  payload**: a report is read whole and never queried.
- **Expired reports are deleted when a new one is stored**, not on a
  schedule. `rehydrate_stash.sweep` has no caller in `app/`.
- **The banner keeps its kinds-of-problem summary**: it says what went
  wrong, and the link shows where.

### Blast radius (measured)

Taken 2026-10-12 at `1c08ae3a` (#2997); re-take when lifted.

- `_quick_setup.py`: 20 `_SlotFailure(` sites and 7
  `_quick_setup_error_query(` calls (`grep -c`). `quick_setup_error`
  is named in 1 template, 10 test files and 4 specs (`grep -rl`).
- `ValidationIssue(` sites: 22 in `csv_imports.py`, 6 in
  `relationships.py`. `rehydrate_stash.sweep` has 0 callers in `app/`.
- New: one model, migration, schema, service, views module, route
  slice, template and spec.

### PR ladder

1. **This plan** (prose).
2. **Scaffold.** A placeholder page, the banner link, and a skeleton
   `spec/issue_reports.md` <!-- path-ref-ok --> (`tests/unit/test_spec_coverage.py`
   requires one for a new routing module). No storage yet.
3. **Store.** The model, migration, schema and service, with unit tests.
   No route reads it yet.
4. **Wire.** Quick Setup's failures store reports, and the page and the
   `.txt` read them. Tests, a browser-check section, and the cumulative
   `diff-reviewer` read.
5. **Close.**

Under Path B, rung 2 scaffolds the download trigger in place of the
page.

### Definition of done

- By test: a refused file's `See every problem` opens every issue, and
  the `.txt` holds the same lines. A bad token gets the 404 page, and
  no URL carries a row or a value. Postgres CI round-trips the
  migration.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

1. **Path A or Path B?** The author decides. A is recommended, with B's
   file as `Download as text`.
2. **Is a one-hour TTL right?** The author decides. Longer means cell
   values sit in the database longer.
3. ~~Ship the summary first?~~ Yes (author, 2026-10-12): it shipped as
   #2997.

### Out of scope

- Rehydrate and Duplicate are later items. Rehydrate's findings already
  render in place, and Duplicate has nothing to report yet.
- ~~The Setup pages' uploads already list every row.~~ No longer true:
  since `guide/archive/quick_setup_update.md` Item 3 they list kinds of problem,
  as Quick Setup does, so no surface shows rows until this plan lifts.

### Doc impact

- `spec/issue_reports.md` — new: the store, TTL and access, the page, the `.txt`, and how a consumer plugs in. <!-- path-ref-ok -->
- `spec/README.md` — row for the new spec.
- `spec/quick_setup_card_spec.md` — "Result reporting": the `See every problem` link.
- `spec/settings_inventory.md` — the `?quick_setup_report` query parameter.
- `spec/architecture.md` — module map: the model, service, views module and route slice.
- `docs/database.md` — the `issue_reports` table.
- `docs/backup_restore.md` — "Import files" and "Data retention": a second short-lived store that quotes cell values.
- `docs/security_posture.md` — reports are visible only to their operator, expire, and are reached by token only.
