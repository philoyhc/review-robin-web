# Segment AD2E — Panels (version 1)

**Opened:** 2026-11-23 · **Theme:** an exercise's panels and the Panels roster move into the database; Panels' *Save* keeps them for every exercise, and the panels Form and Process make join them · **Related:** `applydesk/guide/ad2_series.md`, `applydesk/guide/ad2_deferred_findings.md`, `applydesk/spec/applications.md` ("The Panels page"), rulings 4, 19, 20, 22, 23, 39 and 74 (`applydesk/guide/todo_master.md`)

## Opportunity

- **Panels keeps nothing an exercise can rely on.**
  - On a sample exercise, the page has no *Save*.
  - On a scratch exercise, *Save* writes into the browser's in-memory store (`applydesk/scratch_panels.py`). A deploy, a restart or eight idle hours drops it.
  - Process refuses a panel made on a sample's Process "until panels are stored" (AD2C).
- **The model has four shapes for one concept** (AD-50): `Panel`, `Member`, `Evaluator` and `Assessor`. A per-membership note is merged per person. Retiring is page-only. No cap is held by the server.
- **People search is ASCII-only on SQLite** (AD-127). The members box and the directory search compare `lower(display_name)`, so "émile" misses "Émile" locally.
- **The browser store goes once Form, Panels and Emails are stored** (author, 2026-11-23). This is the first of the three.

## Decision

- **Tables,** each keyed per exercise (ruling 37). Rows are retired, never deleted (ruling 74).
  - `panel`:
    - its exercise, a `key` unique per exercise and never reused (`panel-<n>`, minted by the server);
    - a name, unique among the exercise's live panels, case-insensitively;
    - position and `retired_at`.
  - `roster_entry`: one row per person on the Panels table, someone on no panel included.
    - The exercise, a person FK, the name as typed, the note, position and `retired_at`.
    - The note belongs to the person's row, as the page shows it, not to each membership (AD-50).
  - `panel_member`: the panel, the roster entry and `retired_at`. One live row per pair.
  - `person.display_name_key`: the casefolded name, as `email_key` is, searched by the directory and the allowlist (AD-127).
- **One Save replaces the roster** (ruling 23).
  - The page's snapshot is checked and written in one transaction under the exercise's row lock, guarded by `exercise.panels_revision`, as Process's save is.
  - It applies today's checks (`scratch_panels.build`):
    - distinct names, and no name that is a CSV column;
    - a distinct address per row;
    - ticks naming the page's panels;
    - no retiring a panel a Form question or a gate uses.
  - Existing keys are kept and the server mints new ones. A panel the page made (`made-1`, `new-1`) never reaches a row.
  - Each address is matched to a person on record, else made pending (`people.pending`), as Candidates' CSV is.
  - The save is audited as `exercise.panels_saved`, with counts.
- **Caps are the server's:** at most 50 panels and 2,000 people per exercise, the page's own limits today.
- ***+ New panel…* on Form and Process** adopts into the database with the page's save, for every exercise. Process's refusal on a sample goes.
- **The readers read the store.** `sample_data.panels_of`, `roster`, `people_pools` and `panel_pools` read the stored panels when there are any, else the sample's. Pages keep their dataclasses, which `panels_store` builds.
- **Samples:** a sample exercise's panels are recorded at its first save, as AD2C records its timeline. The seed writes no panels.
- **No new page or card:** Panels already has its page *Save* on a scratch exercise, so it is shown for every exercise. No scaffold rung.

**Rejected:**
- **One JSON roster per exercise.** It is simpler to save, but Form's questions, gates' sources and AD2F's pairs name panels and people, and want keyed rows to point at.
- **The note on each membership.** The page edits one note per person; per-panel notes would need a column per panel to show.
- **Gate sources as an FK to `panel`.** `gate_source.ref` keeps the panel's key. Keys are never reused within an exercise, so the key is stable, and AD2C's tables are left as they are.

## Semantics

- **Keys.** `panel-<n>`, with a counter per exercise past every key it has held. A retired panel keeps its key, so a question or gate naming it reads as missing rather than reaching a new panel.
- **Names.** Up to 80 characters; distinct among live panels, case-insensitively; not `Name`, `Email` or `Note`.
- **Retiring.** It is refused while a Form question or a gate uses the panel, as today. Retiring keeps the panel's members on their roster rows.
- **People.**
  - An address is listed once per exercise.
  - A row unticked from every panel stays on the roster.
  - A row removed from the table retires its entry and its memberships.
  - Re-adding someone revives their entry.
- **Concurrent saves.** The second is refused (*changed since you opened it; reload*). Nothing merges.
- **An opened gate's roster.** The page still asks before removing a member of a panel an opened gate uses. Keeping the roster a gate opened with is AD2F's, with pairs.
- **Directory.** The page's red "not found" and the CSV's leaving-out are unchanged. The server does not refuse an address the directory lacks; it is made pending, as Candidates' is.

## Judgment calls — decided

- The caps stay at the page's 50 panels and 2,000 people, not the functional spec's 5 × 200, which no exercise has needed. The author can lower them.
- The note sits on the roster row (one per person), not the membership.
- `gate_source.ref` keeps the panel key, not an FK.
- AD-42 (Institution-wide as a directory search) goes to AD2D: it is the Select people question's pool.
- AD-50's "drop `Assessor` and `Evaluator`" goes to AD2F: pairs replace them.

## Blast radius (measured)

Taken 2026-11-23 at `4f911c6cd`.

| What | Count | Command |
|---|---|---|
| Modules calling the panel readers | 7 (20 calls) | `grep -rln 'panels_of(\|sample_data.roster(\|panel_pools(\|people_pools(' applydesk/*.py \| grep -v sample_data.py` |
| Modules importing `scratch_panels` | 3 | `grep -rln scratch_panels applydesk --include=*.py \| grep -v tests` |
| Test files on Panels or its save | 8 | `grep -rln '/panels\|scratch_panels\|panels_of' applydesk/tests --include=*.py` |
| Templates naming a panel | 20 | `grep -rln -i panel applydesk/templates` |
| Name searches on `lower(display_name)` | 2 | `grep -rn 'lower(Person.display_name)' applydesk/*.py` |

## Status

- **2026-11-23, rung 2:**
  - The tables, `exercise.panels_revision` and `person.display_name_key` (`ad2e1panels`, backfilled with Python's casefold).
  - The model keeps the key in step with the name (`Person._name_key`); the one bulk update that writes a name, binding a pending person, sets it too.
  - `directory.search` and the allowlist's filter match the key. `test_a_name_search_reads_past_ascii` fails on the old `lower()`.
- **2026-11-23, rung 3:** `panels_store` loads, saves and adopts, nothing calling it yet (`applydesk/tests/test_panels_store.py`).
  - A save starts from the stored roster, else the sample's, so a sample's keys are kept.
  - Names park on placeholders before they are written, so two panels may swap names in one save.
  - Two addresses that turn out to be one person are refused.
  - Each save or adoption is audited as `exercise.panels_saved`.

## PR ladder

1. **PR 1 — this plan,** with the AD2 order in `applydesk/guide/todo_master.md` and the series file.
2. **PR 2 — the tables.**
   - `panel`, `roster_entry`, `panel_member` and `person.display_name_key` (backfilled), with a migration round-tripped on Postgres.
   - Nothing reads them yet, except the two name searches, which move to `display_name_key` (AD-127).
3. **PR 3 — `panels_store`.**
   - Loads into the pages' `Panel` and `Member` and the roster.
   - Saves with today's checks, keys, the revision guard, the caps and the audit; adopts a page's new panels.
   - Must not change a page.
4. **PR 4 — Panels saves for every exercise.**
   - The readers read the store; Panels' *Save* is shown for every exercise.
   - Form's and Process's *+ New panel…* adopt into the database, and Process's refusal on a sample goes.
   - A scratch exercise's panels move to the database, and `applydesk/scratch_panels.py` is deleted, with its spec lines.
   - Last build rung: the cumulative `diff-reviewer` read.
5. **PR 5 — close.**

## Definition of done

- **The tables** exist for panels, roster entries and memberships, with `person.display_name_key`. The migration round-trips in `ci-postgres`.
- **A saved Panels:**
  - survives a restart;
  - is refused on a stale revision, past a cap, or when it retires a panel in use;
  - keeps its keys (`applydesk/tests/test_panels_store.py`).
- **A panel made** on Form or Process is stored with that page's save, on a sample too.
- **Search:** "émile" finds "Émile" on SQLite (a test).
- `applydesk/scratch_panels.py` is gone; `grep -rn scratch_panels applydesk` finds nothing.
- **The register:** AD-127 struck; AD-50 marked *Partly* (the shapes and the caps here; `Assessor` and `Evaluator` with AD2F), each with its PR.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2E` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

1. ~~The caps~~: 50 panels and 2,000 people, the page's own (author, 2026-11-23).

## Out of scope

- **Institution-wide as a directory search** (AD-42): AD2D, with the Select people question.
- **Dropping `Assessor` and `Evaluator`; the roster an opened gate keeps:** AD2F, with pairs.
- **Form's questions and Emails' templates:** AD2D and the emails segment, next in the order.
- **Retiring the browser store itself:** after those, as AD2G's first part.

## Doc impact

- `applydesk/spec/applications.md` — "The Panels page": *Save* for every exercise, its refusals (stale, caps, a panel in use), keys minted by the server, addresses matched or made pending; *+ New panel…* stored with Form's and Process's save; the scratch-only lines go.
- `applydesk/spec/architecture.md` — the `panel`, `roster_entry` and `panel_member` tables, `person.display_name_key`, `panels_store.py`, the `exercise.panels_saved` event; `scratch_panels.py`'s row removed.
- `applydesk/guide/ad2_deferred_findings.md` — strike AD-127; AD-50 *Partly*; AD-42 marked for AD2D (plan PR).
- `applydesk/guide/ad2_series.md` — the order (plan PR); AD2E's row: its findings as placed, and its plan pointer, then its archived copy.
- `applydesk/guide/todo_master.md` — the AD2 order (plan PR); the roadmap's AD2 row names AD2E's plan while open (at close: removed).
- `applydesk/README.md` — the plan's index row, moved at close.
