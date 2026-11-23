# Segment AD2D — The form (version 1)

**Opened:** 2026-11-23 · **Theme:** an exercise's form, its questions with stable keys, moves into the database; Form's *Save* keeps it for every exercise, and rules and Extract name a question by its key · **Related:** `applydesk/guide/ad2_series.md`, `applydesk/guide/ad2_deferred_findings.md`, `applydesk/spec/applications.md` ("The Form page"), rulings 15, 19, 30, 68–71 and 79 (`applydesk/guide/todo_master.md`)

## Opportunity

- **Form keeps nothing an exercise can rely on.**
  - On a sample exercise, the page has no *Save*.
  - On a scratch exercise, *Save* writes into the browser's in-memory store, which a deploy, a restart or eight idle hours drops.
- **A question has no stable key** (AD-45).
  - Rules (ruling 30's form-answer condition), the sample's answers and Extract's columns all name a question by its **label**.
  - A rename therefore breaks every rule that reads the question. This is AD-62's last gap: AD2C keyed every other rule target.
- **The order from AD2C** (author, 2026-11-23): after AD2E's panels, the form is next. It is the second of three pages that leave the browser store.

## Decision

- **Tables**, keyed per exercise (ruling 37). Rows are retired, never deleted (ruling 74).
  - `form_card`: one row per card (field, section or page break), with:
    - its exercise and a `key`, unique per exercise and never reused (`q<n>`, minted by the server);
    - position, kind, type, label, help;
    - min, max, step, options, exclusive, the photo ratio, pool (a panel key or `institution`), required, shown;
    - `retired_at`.
  - `exercise.form_title`, `form_description` and `form_revision`, which is 0 until Form is first saved.
- **One Save replaces the form**, as Process and Panels do.
  - The page's snapshot is checked by today's rules (`_form`: kinds, types, lengths, toggles, a pool the exercise has).
  - It is written under the exercise's lock (`panels_store.lock`), guarded by `form_revision`.
  - Each card carries its key. The server mints new keys, so a page's placeholder key never reaches a row.
  - *+ New panel…* adopts as it does now (AD2E).
  - The save is audited as `exercise.form_saved`, with counts.
  - A sample's form is recorded at its first save. A scratch exercise's form moves to the database.
- **The readers read the store.** `sample_data.form_cards`, `form_heading` and `form_is_empty` read the stored form when there is one, else the sample's. `FormCard` gains `key`.
- **A question's key is its handle** (AD-45, AD-62).
  - A rule's form condition names the question's key, as every other condition names its target's key. The Process page's rule editor offers questions by key and shows their labels.
  - A rule naming a question the form drops is refused at save, as AD2C refuses other targets.
  - `list_questions`, the sample's answers and Extract's columns read by key; a column's header stays the label.
- **No new page or card:** Form already has its page *Save* on a scratch exercise, so it is shown for every exercise, with the revision it opened at. No scaffold rung.

**Rejected:**
- **One JSON form per exercise.** Rules, answers (AD4) and nominations name questions, and want keyed rows.
- **A `form_version` table now.** Nothing stores an application yet, so no version would be read. A version made at publication is the applications part's, beside the answers that need it.

## Semantics

- **Keys.** `q<n>`, counted per exercise past every key it has held, retired ones and the sample's included.
  - A sample's cards take `q1`… in order at the first save. Its rules, which name labels today, are read through the label until saved again (Judgment calls).
  - A removed question keeps its key, so a rule naming it is refused, not re-pointed.
- **Sections and page breaks** are cards with keys too, so the order is one list. Only a field can be named by a rule.
- **A published form** stays read-only (`locks.form_lock`); the server refuses a save to it.
- **Concurrent saves.** The second is refused (*changed since you opened it; reload*), and a save returns its new revision, as Panels' does.
- **Rename.** A rename keeps the key, so a rule follows it with no rewrite. This is the point of the segment.

## Judgment calls — decided

- No `form_version` yet; it lands with applications (Rejected, above).
- Sections and page breaks take keys, to keep one ordered list.
- AD-42, Institution-wide as a directory search, stays with this series' later part, beside nominations, which are its only reader that is not a picker.
- Rules stored since AD2C may name a question by its label. A form condition reads a key, else a label the form has (mapped to its card's key), and is written back by key at the next Process save. A data migration cannot do it, because a key exists only once the form is stored.

## Blast radius (measured)

Taken 2026-11-23 at `edf86c06c`.

| What | Count | Command |
|---|---|---|
| Modules calling the form readers | 4 (13 calls) | `grep -rn 'form_cards(\|form_heading(\|form_snapshot(\|list_questions(\|form_is_empty(' applydesk/*.py \| grep -v 'def \|sample_data.py'` |
| Scratch store reads and writes of the form | 4 | `grep -rn 'scratch.page([^)]*"form"\|save_page([^)]*"form"' applydesk/*.py` |
| Test files on Form or its save | 7 | `grep -rln '/form"\|/form'"'"'\|form_save\|applydeskFormSnapshot' applydesk/tests --include=*.py` |
| Rule code naming the form condition | 4 | `grep -rn '"form"' applydesk/rules.py applydesk/process_save.py` |

## PR ladder

1. **PR 1 — this plan.**
2. **PR 2 — the tables.**
   - `form_card` and the exercise's form columns, with a migration round-tripped on Postgres.
   - Nothing reads them yet.
3. **PR 3 — `form_store`.**
   - Loads into `FormCard` (with `key`) and the heading.
   - Saves with today's checks, keys, the lock, the revision guard and the audit.
   - Must not change a page.
4. **PR 4 — Form saves for every exercise.**
   - The readers read the store; the page carries each card's key and the revision.
   - *Save* is shown for every exercise, and the Placeholder line goes.
   - The scratch form path is deleted.
5. **PR 5 — questions by key.**
   - Rules' form condition, the editor, `list_questions`, the sample's answers and Extract read by key.
   - A rule naming a dropped question is refused.
   - Last build rung: the cumulative `diff-reviewer` read.
6. **PR 6 — close.**

## Definition of done

- **The tables** exist for form cards, with the exercise's form columns. The migration round-trips in `ci-postgres`.
- **A saved form:**
  - survives a restart;
  - is refused on a stale revision or once its stage is published;
  - keeps its keys through a rename (`applydesk/tests/test_form_store.py`).
- **Rules:** a rule naming a question by key follows a rename, and one naming a dropped question is refused (a test).
- The scratch form path is gone: `grep -rn 'page([^)]*"form"' applydesk --include=*.py` finds nothing.
- **The register:** AD-45 struck (its version part marked for the applications part); AD-62's form gap noted, each with its PR.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2D` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

None. The version, the applicant side and AD-42 are placed in Out of scope.

## Out of scope

- **Form versions, applications and their states, answers and nominations** (AD-38, AD-46, the version half of AD-45): this series' later part, AD2D's second segment, beside AD4's applicant side.
- **Who sees each field** (rulings 68, 71, 79): AD2V's views. Form's *Shown* toggle stays as it is.
- **Institution-wide as a directory search** (AD-42): with nominations, above.
- **Emails' templates:** AD2L, next in the order.

## Doc impact

- `applydesk/spec/applications.md` — "The Form page": *Save* for every exercise, its refusals and keys; rules' form condition by key; Extract's columns by key; the scratch-only lines go.
- `applydesk/spec/architecture.md` — the `form_card` table and the exercise's form columns, `form_store.py`, the `exercise.form_saved` event.
- `applydesk/guide/ad2_deferred_findings.md` — strike AD-45 (version half to the applications part) and note AD-62's form gap closed.
- `applydesk/guide/ad2_series.md` — AD2D's row: version 1 and its plan pointer, then its archived copy.
- `applydesk/guide/todo_master.md` — the roadmap's AD2 row names AD2D's plan while open (at close: removed).
- `applydesk/README.md` — the plan's index row, moved at close.
