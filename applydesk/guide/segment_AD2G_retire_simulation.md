# Segment AD2G — Retire the simulation

**Opened:** 2026-11-23 · **Theme:** every exercise is an ordinary database exercise; the browser's scratch store goes, and test exercises are seeded · **Related:** `applydesk/guide/ad2_series.md` (AD2G), rulings 59, 73, 74 and 75 (`applydesk/guide/todo_master.md`), finding S10 (`applydesk/guide/archive/findings_2026-11-20.md`) and AD-125 (`applydesk/guide/ad2_deferred_findings.md`)

Two items, each closing on its own, in the order the series file gives. **Item 1** is the first part: the scratch store removed, with *New exercise* and *Duplicate* making ordinary exercises and test exercises seeded instead. **Item 2** is request-scoped loading, SQL paging and the sample-data path off production. Item 2 is planned here when Item 1 closes, and absorbs the read costs noted at the AD2D and AD2L closes.

## Item 1 — Ordinary exercises, seeded

### Opportunity

- **The scratch store is a shell around a row.**
  - Since AD2A rung 4, *New exercise* makes an `exercise` row with its Owner (`gate.own_new_exercise`).
  - Since AD2B–AD2L, every Setup page of a scratch exercise saves to the database.
  - Even so, `applydesk/scratch.py` still decides whether the exercise exists. It holds the exercise in process memory for one browser cookie, at most five, and drops it after eight idle hours or on any restart or deploy.
  - After that, its row lives on with nothing reading it, and its Owner can never reach it again.
- **It is the last simulation a tester trips on.**
  - The Lobby shows a scratch exercise to one browser only, so a co-operator added on Panels never sees it.
  - A deploy silently loses a morning's setup.
  - The Lobby's note ("kept in this server's memory… never saved") is now false for everything but the shell.
- **Production refuses it** (finding S10, ruled 2026-11-20): until the store caps what one client makes, checks a body's size before reading it, and prunes off the request path, it does not ship. Removing it answers all three.
- **Testers still need exercises.** The samples are seeded only on localhost (ruling 74), and a blank exercise has to be made by hand each time.

### Decision

- **An exercise is a live `exercise` row the viewer operates.** `sample_data.exercise(id)` and `exercises()` read:
  - the fixed samples, as now;
  - and every row that is not a sample, built from the row (`exercises.from_row`: a blank Draft named by the row, its *Created* the row's `created_at`).

  The grant gate (`gate.operates`) decides who sees it, as for a sample. A co-operator now sees it too.
- **"Scratch" becomes "not a sample".**
  - `sample_data.is_sample(id)` replaces `scratch.is_scratch`.
  - Its readers keep their meaning: a blank form (`_blank_form`), blank emails (`_blank_emails`), and no sample applications.
- **The scratch store is removed:**
  - `applydesk/scratch.py`, its middleware and its cookie;
  - the Lobby's five-exercise limit;
  - *Discard*, which is retired: *Delete* on the Lobby panel does it, Owner-only;
  - the scratch tag and note on the Lobby and the pages.

  The 256 KiB body check stays, as `web.MAX_BODY`.
- ***New exercise* and *Duplicate*** make the row and its Owner in one transaction, as `own_new_exercise` does now, then open its Home.
  - **Cap:** one person may have created at most **50** live exercises. Archive or delete to make more. The cap is counted under the allowlist row's lock, and answers S10's "caps what one client can make".
- **The seed** (`python -m applydesk.seed`, local only, ruling 74) gains:
  - `--reset`, which empties Apply Desk's local database (Alembic `downgrade base`, then `upgrade head`) before seeding;
  - `--blank N`, which adds N blank drafts owned by the seed's Owner.
- **No samples on Azure** (author, 2026-11-23): ruling 74 stands. Azure testers make blank exercises with *New exercise*; the samples stay seeds for localhost and tests.

**Rejected:**
- **A `scratch` flag on the row**, keeping the shell's meaning. Nothing differs once the pages persist, and a flag would need its own lifecycle (expiry, promotion).
- **A per-browser limit kept as a per-person limit of 5.** A tester's drafts are legitimate exercises now; 50 bounds abuse without making testers archive constantly.

### Semantics

- **A row with no name** (`name` NULL: made before AD2B recorded names, or by a failed create) shows as *Untitled exercise*. Its Owner can name it on Details.
- **A deleted or archived row** leaves the Lobby as any exercise does (AD2B). The Archive now shows ordinary exercises, not only samples and this browser's scratch ones.
- **Rows left behind by past scratch exercises** appear in their Owner's Lobby after rung 2: they are real drafts that were unreachable. The Owner deletes what they do not want. Nothing migrates.
- **The cap** counts rows with `created_by_id` = the person, `deleted_at` NULL and `archived_at` NULL. A sample's seeded rows have no `created_by_id`, so they never count.
- **`--reset` outside `APP_ENV=local`** is refused as the seed is. On Postgres locally it downgrades and upgrades the `applydesk` chain only, never RRW's.

### Judgment calls — decided

- `is_sample` reads the fixed `EXERCISES` tuple, not a database column: samples are code, and Item 2 moves them off production.
- *Discard* is retired rather than kept as an Owner-less delete. Its only reason was a scratch exercise reachable from one browser (cordware#223).
- `_scratch_save_js.html` is renamed `_page_save_js.html`, since every exercise's pages save to the database now.

### Blast radius (measured)

Taken 2026-11-23 at `31fecbe33`.

| What | Count | Command |
|---|---|---|
| `scratch.` uses outside `scratch.py` | 37, in 9 modules | `grep -rn "scratch\." applydesk/*.py \| grep -v "^applydesk/scratch.py" \| wc -l` |
| Templates mentioning scratch | 7 | `grep -rln "scratch" applydesk/templates \| wc -l` |
| Test files mentioning scratch | 8 (`test_scratch.py` 1,145 lines, `test_scratch_browser.py` 268) | `grep -rln "scratch" applydesk/tests --include=*.py` |
| Spec lines mentioning scratch | 26, in 3 specs | `grep -rn "scratch" applydesk/spec/*.md \| wc -l` |
| Readers of the sample list | 9 | `grep -rn "sample_data\.exercises()\|sample_data\.EXERCISES" applydesk/*.py \| wc -l` |

### Status

**Closed 2026-11-23.** Intended versus done:

- **The ladder held.** #4185 was the plan. #4186 was rung 2 (rows are exercises), #4187 rung 3 (the store removed), #4188 rung 4 (the seed's flags), then the close. Rungs 5–6 were struck: no samples on Azure, so ruling 74 stands.
- **One cold read, at rung 4 rather than rung 3**, because rung 4 also changed code. It covered rungs 2–4 from `09c3e18d0`, and its findings were fixed on the rung each belonged to:
  - Home's Details code list carried every operator's draft names. It now carries only the viewer's own, and a code clash names no other exercise.
  - Lookups inside a transaction opened a second connection; `sample_data.sample` reads a sample with no query.
  - A fresh ordinary row was recorded as a sample on its first change: it was renamed and audited.
  - Duplicate made a blocking lookup on the event loop.
  - The cap's lock was `FOR UPDATE`; it is now `FOR NO KEY UPDATE`, taken after the allowlist check.
  - `--reset` trusted `APP_ENV` alone; it now needs a SQLite or localhost URL.
  - Codex on #4188: `--reset` by downgrade failed on data the old constraints forbid (two Owners stop `ad2m2`); it now drops Apply Desk's own tables and upgrades to head.
  - Weak cap and co-operator tests were strengthened.
- **Found while building:**
  - The seed walked `sample_data.exercises()`, which now lists ordinary rows too; it walks the samples only.
  - Semantics said seeded samples have no `created_by_id`. They have one (the seed's person), so the cap excludes the samples by ID.
- **Decisions confirmed at build:**
  - *New exercise* records the name on the row.
  - The Lobby panel takes 500 ticked rows (`MOST_TICKED`).
  - The Archive's refusal is shown by its key's text.
- **Left for later:**
  - The Lobby, Archive and Home still read every ordinary row before filtering by grant: Item 2's paging.
  - `--reset` is tested on SQLite only.
- **Owed:** the author's browser check of *New exercise*, the Lobby, Home's Details, and Form, Process and Panels saves.

### PR ladder

1. **Plan** (this file), with the todo_master pointer. Prose only.
2. **Rows are exercises.**
   - Lands: `exercises.from_row`; `sample_data.exercise` / `exercises` read non-sample rows; `is_sample`; the Lobby, Archive, Diagnostics and Home read them.
   - Scratch exercises keep working (their rows are now what is read), so the store is redundant but still there.
   - Must not touch: creation and the store.
3. **The store removed.**
   - Lands: *New exercise* and *Duplicate* on rows alone, with the 50 cap; `scratch.py`, its middleware, cookie, *Discard* and the scratch copy deleted; `web.MAX_BODY`; the save script renamed.
   - Tests: `test_scratch.py` and `test_scratch_browser.py` become `test_new_exercise.py` and `test_new_exercise_browser.py`.
   - **Last build rung:** `diff-reviewer` on the cumulative diff from rung 2's base.
4. **The seed:** `--reset` and `--blank N`, `applydesk/README.md`'s local steps.
5. ~~Admin scaffold: *Load sample exercises*~~ — struck: no samples on Azure (author, 2026-11-23).
6. ~~Load wired~~ — struck, as rung 5.
7. **Close:** `spec-writer` on `applydesk/spec/`, S10's follow-up deleted, Item 1's status compacted.

### Definition of done

- `grep -rn "scratch" applydesk --include=*.py --include=*.html` finds no store, cookie or *Discard* (comments citing AD1N's history aside).
- A new exercise survives a restart and appears in a co-operator's Lobby (`applydesk/tests/test_new_exercise.py`).
- The 51st live exercise one person creates is refused with the cap's message.
- `python -m applydesk.seed --reset --blank 3` on a local SQLite file leaves the samples plus three blank drafts.
- The S10 follow-up ("the store that replaces the scratch store caps…") is deleted from `applydesk/guide/todo_master.md`.
- `### Doc impact` section present and current
- `python3 tools/close_check.py AD2G.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

- ~~Samples on Azure~~ — no; ruling 74 stands (author, 2026-11-23).
- ~~The cap~~ — 50 live exercises per creator (author, 2026-11-23).

### Out of scope

- Request-scoped loading, SQL paging, and taking the samples off production: Item 2.
- Applicants' `/me` pages reading ordinary exercises: they have no applications until AD4.
- Dossiers and pairs for ordinary exercises: AD2F and AD2P.

### Doc impact

- `applydesk/spec/applications.md` — the Lobby's *New exercise*, *Duplicate*, cap and *Discard*'s retirement; the scratch note removed (Item 1).
- `applydesk/spec/architecture.md` — the module map without `scratch.py`; `exercises.from_row`; `sample_data.is_sample`; the seed's flags (Item 1).
- `applydesk/spec/permissions.md` — a co-operator sees a new exercise; *Discard*'s Owner-less exception removed (Item 1).
- `applydesk/README.md` — the seed's `--reset` and `--blank` (Item 1).
- `applydesk/guide/todo_master.md` — the S10 follow-up deleted, and the roadmap row marks Item 1 closed (Item 1).
