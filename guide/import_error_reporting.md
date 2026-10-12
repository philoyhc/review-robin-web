# Import error reporting

**Opened:** 2026-10-12 · **Theme:** showing an operator every problem an
upload had, where the page that refused it cannot · **Related:**
`spec/quick_setup_card_spec.md`, `spec/rehydrate.md`,
`spec/settings_inventory.md`

A standalone plan at the author's naming, not a `segment_*.md`, in the
shape of `guide/participant_info.md`: items close independently, each
with its own `### Doc impact` and `### Status`. `tools/close_check.py`
reads only `segment_*` files, so an item's `Doc impact` is checked by
hand at its close.

**Reuse is the brief** (author, 2026-10-12): Item 1 builds the report
once, for Quick Setup. Later items plug Rehydrate, Duplicate and
anything else into it, adding no new store or page.

**Deferred, unbuilt** (author, 2026-10-12). The banner's problem-type
summary shipped on its own (#2997). This plan is kept so the design is
ready when the work is lifted; the entry in `guide/deferred_consolidated.md`
("Every problem a refused upload had") holds its lift trigger. Nothing
here is queued in `guide/todo_master.md`.

---

## Item 1 — A refused upload's full problem list, one link away

### Opportunity

A refused Quick Setup file ends in a redirect to Session Home, and only
the query string survives the redirect. So the banner can say what
*kind* of problem the file has (`1c08ae3a`: "ReviewerEmail is blank (2
rows)", five lines at most) but never *which rows*. For those, it sends
the operator to the slot's Setup page to upload the file again. The
Setup pages can list every row only because they render the issues in
the upload's own response, without a redirect. A 5,000-row file's list
does not fit in a URL, so it has to be stored to cross the redirect.

The same gap recurs elsewhere: Create's Quick Setup (it redirects to the
new session's Home, so it is covered here); Rehydrate's
dropped-responses CSV, which already crosses its page via
`rehydrate_stashes` (`spec/rehydrate.md`); and a future Duplicate that
reports what it could not copy.

### Decision

**Pending the author's choice between two paths** (Open question 1).
The recommendation is Path A, with Path B's file one click away on the
page.

Both paths share one design. A refused upload stores an **issue report**
server-side and hands the redirect a **token**. The URL carries only the
token, never a row or a cell value, so the banner's no-values rule
(`1c08ae3a`) still holds.

- **Store.** A new table `issue_reports`. Each row holds a token, the
  operator, an optional session, a `kind` (`quick_setup` first), a JSON
  payload and a creation time. Reports are operator-scoped and expire
  after an hour, the same scope and TTL as `rehydrate_stashes`, and
  each new report deletes the expired ones.
- **Service.** `app/services/issue_reports.py`: <!-- path-ref-ok -->
  - `put(db, *, user, kind, title, sections, session=None) -> token`;
  - `get(db, *, token, user) -> IssueReport | None`;
  - `section_from_issues(heading, issues)`, which is how a consumer
    turns a `ValidationIssue` list into a section.
- **One adapter, two renderings.** `app/web/views/_issue_reports.py` <!-- path-ref-ok -->
  shapes the report once. The HTML page and the `.txt` file both read
  that shape, so they cannot disagree.
- **Routes**, in a new slice `app/web/routes_operator/_issue_reports.py`: <!-- path-ref-ok -->
  - `GET /operator/issue-reports/{token}`: the page;
  - `GET /operator/issue-reports/{token}.txt`: the same report as an
    attachment.

  These routes are not under `/sessions/{id}`, so a consumer that has
  no session yet (Rehydrate before commit) can use them.

**Path A — a barebones page in a new tab (recommended).** The banner
gains a link, `See every problem`, with `target="_blank"
rel="noopener"`. The page is a heading and a line saying which session,
which file and when. Each section lists its kinds of problem (the
banner's lines, uncapped), then a table: `Row` | `Column` | `Problem`,
errors before warnings. A Secondary `Download as text` button sits at
the top.

**Path B — an immediate text-file download.** A 303 cannot carry a
download (`app/web/routes_operator/_rehydrate.py` already says so). So
Session Home would have to:

1. see the token in its query;
2. start the `.txt` download from an inline script;
3. strip the token with `history.replaceState`, so a reload does not
   download the file again.

**Path B is not recommended**, because:

- A download that no click started is browser-dependent: Safari and
  Firefox may prompt or block it.
- Each retry adds `…(1).txt`, `…(2).txt` to Downloads.
- The operator still has to find the file and open it.
- With scripts off it does nothing, and only a browser test can see it
  work.

It needs the same store and routes as A, so it saves nothing.

**Rejected: reuse `rehydrate_stashes`.** It looks right: a token, the
operator, a blob, an hour. But its `get()` returns raw bytes for any
token the operator holds, so a report token would reach Rehydrate's
commit as a file set. Its purpose is also flag-gated and spec'd as
Rehydrate's. A new table costs one create/drop migration.

### Semantics

- **Expired, unknown or another operator's token** give the same 404
  page: "This problem report is no longer available. Reports last an
  hour; upload the file again to see its problems." It does not tell
  expired apart from someone else's, so a token reveals nothing.
- **The session is deleted:** its reports go with it (FK cascade).
- **The operator stops operating the session:** the report 404s like
  an expired one. `get()` re-checks access when the report names a
  session.
- **File-level issue** (no row, e.g. a missing column): `Row` reads
  `File`.
- **Submit-all** stops at its first failing slot
  (`quick_setup_submit_all`), so it makes one report, for that slot.
- **Settings slot:** `ApplyResult.errors` already carry a row, a field
  and a message, so they fill a section the same way
  (`settings_error_details` is the template). No other failure reason
  gets a report: `lifecycle` and `needs_confirm` have nothing to list.
- **Size:** at most 5,000 issues per report, the roster row cap. Past
  that, a closing line reads "…and N more".
- **Cell values:** shown in full on the page and in the file. These are
  the operator's own file, and the URL never carries them.
- **Reloading Session Home later:** the banner still renders from the
  query, and its link may have expired, which falls to the 404 page.
- **Text file:** UTF-8, one line per issue (`Row 4, ReviewerEmail:
  …`), named `<session code>-<slot>-problems.txt`.

### Judgment calls — decided

- **One table for every consumer, with a `kind` column.** The
  alternative was a table per feature, which is the duplication the
  brief rules out.
- **A JSON payload, not rows per issue.** A report is read whole and
  never queried, and `sa.JSON` is portable.
- **Sweep on put, not on a schedule.** `rehydrate_stash.sweep` has no
  caller in `app/`, and a store that sweeps only in a job nobody
  schedules never sweeps.
- **Keep the banner's problem summary** (`1c08ae3a`). The banner says
  what went wrong; the link shows where. Without the summary, the
  operator would have to open the page to learn anything.

### Blast radius (measured)

Taken 2026-10-12 at `1c08ae3a`: origin/main `2ad3ac92` plus the
problem-type commit (#2997). Re-take the counts when the work is lifted.

| What | Count | Command |
|---|---|---|
| `_SlotFailure(` sites | 20 | `grep -c '_SlotFailure(' app/web/routes_operator/_quick_setup.py` |
| `_quick_setup_error_query(` calls | 7 | `grep -c '_quick_setup_error_query(' app/web/routes_operator/_quick_setup.py` |
| Templates with the banner | 1 | `grep -rl quick_setup_error app/web/templates` |
| Test files on the error query | 10 | `grep -rl quick_setup_error tests --include=*.py` |
| Specs naming the error query | 4 | `grep -rl quick_setup_error spec` |
| `ValidationIssue(` sites feeding a section | 28 | `grep -c 'ValidationIssue(' app/services/csv_imports.py app/services/relationships.py` (22 + 6) |
| Callers of `rehydrate_stash.sweep` in `app/` | 0 | `grep -rn 'stash.sweep' app` |

New files: one model, one migration, one schema, one service, one
views module, one route slice (two routes), one template and one spec.

### PR ladder

The ladder assumes Path A. Under Path B, rung 2 scaffolds the download
trigger in place of the page, and rung 4 adds the inline script.

1. **This plan** (prose).
2. **Scaffold.** It lands:
   - the route slice and template, rendering a static placeholder
     report (real copy and layout, sample rows marked as a sample, an
     inert `Download as text`);
   - the banner's `See every problem` link on `parse` failures,
     pointing at the placeholder;
   - a skeleton `spec/issue_reports.md` naming the two routes, which <!-- path-ref-ok -->
     `tests/unit/test_spec_coverage.py` requires of a new routing
     module.

   It adds no table and no storage.
3. **Store.** The model, migration, schema and service (`put` / `get`
   / sweep-on-put / `section_from_issues`), with unit tests and the
   Postgres round-trip. No route reads it yet.
4. **Wire.** It lands:
   - Quick Setup's roster, relationships, observers and settings
     failures `put` a report, and the query gains `quick_setup_report`;
   - the page and `.txt` read the store, and the 404 page is added;
   - tests: access, expiry, cascade, cap, submit-all, Create, and a
     browser test that the link opens a new tab;
   - a browser-check section;
   - the cumulative `diff-reviewer` read, from rung 2's base.
5. **Close** (prose): run `spec-writer`, compact `Status`, update the
   README row.

### Definition of done

- A refused roster, relationships, observers or settings file on Quick
  Setup (Session Home or Create) shows `See every problem`, which opens
  every issue in a new tab.
- `/operator/issue-reports/{token}.txt` downloads the same lines.
- An expired, foreign or session-revoked token gives the 404 page;
  tested.
- No row number or cell value appears in any Session Home URL; tested.
- `alembic downgrade base && upgrade head` passes on Postgres (CI).
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted; answered open questions collapsed.

### Open questions

1. **Path A or Path B.** The author decides. The recommendation is A,
   with B's file as the page's `Download as text`.
2. **TTL of one hour.** The author decides. It matches
   `rehydrate_stashes`; longer means cell values sit in the database
   longer (`docs/backup_restore.md` "Import files").
3. ~~Ship `1c08ae3a` first.~~ Yes (author, 2026-10-12): it shipped as
   #2997, and the banner keeps its summary.

### Out of scope

- **Rehydrate** (a later item). Its findings already render in place,
  with no redirect. The gain there is the `.txt` and moving its
  dropped-responses CSV onto this store.
- **Duplicate** (a later item). A clone either succeeds or raises, so
  it reports nothing today. It joins once it has something to report,
  such as what it did not copy.
- **The Setup pages' own uploads.** They render every issue in place
  already.

### Doc impact

- `spec/issue_reports.md` — new. It covers the store and its TTL and <!-- path-ref-ok -->
  access rules, the page, the `.txt`, and how a consumer plugs in.
- `spec/README.md` — row for the new spec.
- `spec/quick_setup_card_spec.md` — "Result reporting": the `See every
  problem` link.
- `spec/settings_inventory.md` — the `?quick_setup_report` query
  parameter.
- `spec/architecture.md` — module map: the model, service, views
  module and route slice.
- `docs/database.md` — the `issue_reports` table.
- `docs/backup_restore.md` — "Import files" and "Data retention": a
  second short-lived store that quotes cell values.
- `docs/security_posture.md` — reports are operator-scoped and
  TTL-bound, and the URL carries a token only.
