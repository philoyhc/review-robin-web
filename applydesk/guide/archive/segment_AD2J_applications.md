# Segment AD2J — Applications

**Opened:** 2026-11-26 · **Closed:** 2026-11-26 · **Theme:** applications move from code into the database, before AD2F's dossiers point at them · **Related:** `applydesk/guide/ad2_series.md`, `applydesk/guide/ad2_deferred_findings.md` (AD-38), `applydesk/spec/applications.md`, rulings 45, 49, 70, 73, 74 and 81 (`applydesk/guide/todo_master.md`)

## Opportunity

- **AD2F has nothing to point at.** Ruling 81 mints a form dossier at submit or at the form's close, from an application. Applications are still code: `sample_data.APPLICATIONS`, 108 frozen rows (104 on the model exercise), each carrying the `dossier_id` AD2F is to take away. The author put applications first (2026-11-26).
- **State is a string and a date is display text** (AD-38). `state` is `Draft`, `Submitted` or `Withdrawn`; `submitted` is `"3 Sep 2026"`, set even for drafts and the withdrawn, and `stages.submitted_rank` parses it back with `strptime`. There is no `withdrawn_at`, and no person behind the applicant, only a name and an address.

## Decision

- **One table, `application`**, keyed per exercise:
  - `public_id` (unique, ten characters, ruling 7), its exercise, and the applicant as a `person` FK (ruling 73), bound or pending by address as Candidates' are;
  - `title`; `state` (`draft`, `submitted`, `withdrawn`); `submitted_at` and `withdrawn_at`, each NULL until it happens; `withdraw_reason`;
  - `form_revision`, the exercise's `form_revision` when it was submitted (AD-45's version half, as a number: see Judgment calls).
- **The seed writes the samples' applications**, as it writes their exercises (AD2G): `seed.seed` adds each sample application once, its applicant made pending by address. Production holds none until AD4 lets applicants submit (ruling 74).
- **The readers read the store.** A new `applications` service returns the `sample_data.Application` dataclass from rows (`from_row`), so `stages`, `extract`, `workflow`, `handoff`, `lookups` and `routes_operator` keep their shapes. `sample_data.applications_of`, `application` and `by_dossier` delegate to it.
- **`submitted` becomes a datetime.** `submitted_rank` and `last_submitted` compare `submitted_at`; Extract and Dossiers show it through the one date helper.
- **The dossier ID stays where it is for now.** The dataclass's `dossier_id` is read from the sample by public ID until AD2F's `dossier` table replaces it. An ordinary exercise has no applications, so it never asks.

**Rejected:**
- **Applications and dossiers in one segment.** It is the size the four-way split was made to avoid (author, 2026-11-26).
- **A string link from AD2F's dossier to the sample application**, turned into an FK later: a migration and a rewrite for nothing (author, 2026-11-26).
- **An `application_transition` table** (the 2026-11-18 sketch): each transition is an audit event in Review Robin's envelope (ruling 74), which already records who and when.

## Semantics

- **States.** `draft` has no `submitted_at`. `submitted` has one. `withdrawn` keeps its `submitted_at` and adds `withdrawn_at`; a draft cannot be withdrawn. Nothing is deleted (ruling 74).
- **The applicant.** One `person` per address across exercises; two applications by one person to one exercise are two rows (ruling 26: two dossiers). Display name and address are read from the person, not copied.
- **Seeding twice** adds nothing: a sample application already on record is left alone, as exercises are.
- **`/me`.** The applicant's own list (`sample_data.MINE`) stays the samples' until AD4's portal signs applicants in: it is the demo of a page AD4 builds.
- **Sorting and ranking.** "Last N submitted" ranks by `submitted_at`, newest first, ties by public ID, as the parsed date did with its day granularity.

## Judgment calls — decided

- **`form_revision` as a number, not a `form_version` snapshot** (2026-11-26): no applicant submits before AD4, which owns versioning a published form (G2, AD3); the number is enough to say which form an application answered.
- **Answers and nominations stay generated** (2026-11-26): AD-46 is AD4's, with the form that writes them.
- **Operator *Return to draft* and applicant *Withdraw* are not wired** (2026-11-26): the state is stored, the actions come with AD4 (applicant) and AD2H (the Dossiers grid's per-row actions).

## Blast radius (measured)

Taken 2026-11-26 at `9cb7d4967`.

| What | Count | Command |
|---|---|---|
| Modules reading applications | 6 (`stages`, `extract`, `workflow`, `routes_operator`, `lookups`, `handoff`) | `grep -rln "applications_of\|by_dossier\|sample_data.Application" applydesk --include=*.py \| grep -v /tests/` |
| Readers of `.submitted` | 2 (`stages.py:1129`, `extract.py:229`) | `grep -rn "\.submitted\b" applydesk --include=*.py \| grep -v /tests/` |
| Sample applications | 108 (104 model exercise; 103 submitted, 4 draft, 1 withdrawn) | `python -c "from applydesk import sample_data as s; print(len(s.APPLICATIONS))"` |
| Test files naming applications | 20 | `grep -rln "applications_of\|by_dossier\|APPLICATIONS\|\.submitted\b" applydesk/tests \| wc -l` |
| Specs | 3 (`applications.md`, `architecture.md`, `permissions.md`) | `grep -rli application applydesk/spec/*.md` |

## Status

**Closed 2026-11-26.** Intended versus done:

- **The ladder held:** #4238 the plan, #4239 rung 2 (the table and the seed), #4240 rung 3 (the readers), then the close.
- **One cold read**, at rung 3, on the cumulative diff from `9ce697102`. Its findings, fixed in #4240:
  - *Last applications* (`last_submitted`) took the last row in creation order and the rule's *last N* (`submitted_rank`) the day, so the two could name different applications. Both rank by time in UTC, ties by public ID; a draft by its started time.
  - The model exercise's pages failed on a database migrated but not seeded; its rows are empty instead.
  - A submitted sample now records the exercise's form revision.
- **Diverged from the plan, decided at build:**
  - The row keeps the applicant's name as given (`name`): a pending person has none, as Panels' roster entry keeps its own.
  - `started_at` added: the day a draft was last touched, which *Last applications* falls back on.
  - `/me` reads the store, with the samples' IDs (`MINE`, `MY_REVIEWS`) until AD4.
  - `people.pending_many` makes the applicants in one query and one flush: per address, the seed cost 0.15 s on every test.
  - The samples' applicants are pending people, so on localhost they sit under Workspace users' *Unused*, as candidates and panel members do.
  - Review Robin's handoff test seeds Apply Desk's database, since the bundles it sends read stored applications.
- **Left for later:** the immutable form version, answers and nominations (AD4); *Withdraw* and *Return to draft* as actions (AD4, AD2H); the allowance per applicant (AD4).

## PR ladder

1. **Plan** (this file), the series row and the order. Prose only.
2. **The table and the seed.**
   - Lands: `Application` model, migration `ad2j1_applications`, the seed writing the samples' applications with pending applicants, audited as `application.seeded` with counts.
   - Must not touch: any reader.
3. **The readers.**
   - Lands: `applications.py` (`of`, `get`, `by_dossier`, `from_row`); `sample_data`'s three functions delegate; `submitted_rank`, `last_submitted` and Extract read `submitted_at`.
   - Tests: the ranking across a day boundary; a withdrawn application's dates; an ordinary exercise with none.
   - **Last build rung:** `diff-reviewer` on the cumulative diff from rung 2's base.
4. **Close:** `spec-writer` on `applydesk/spec/applications.md` and `architecture.md`; AD-38 struck; Status compacted; the plan archived.

## Definition of done

- `application` round-trips on SQLite and Postgres 16 (`ci-postgres.yml`).
- `python -m applydesk.seed` writes 108 applications; a second run writes none.
- No reader imports `sample_data.APPLICATIONS` (`grep -rn "APPLICATIONS" applydesk --include=*.py | grep -v /tests/` names only `sample_data.py`).
- `stages.submitted_rank` no longer calls `strptime`.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2J` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~Applicants' pending persons on a shared database~~: none reach Azure; the seed runs only locally (ruling 74).

## Out of scope

- Answers, nominations and the immutable form version: AD4, with the applicant form.
- Withdraw and *Return to draft* as actions: AD4 and AD2H.
- The dossier and its ID: AD2F (ruling 81).

## Doc impact

- `applydesk/spec/applications.md` — Dossiers and Extract read stored applications; the submitted date's format.
- `applydesk/spec/architecture.md` — the `application` table and the `applications` service in the module map.
- `applydesk/guide/ad2_deferred_findings.md` — AD-38 struck with the PRs that cleared it (at close).
- `applydesk/guide/ad2_series.md` — the AD2J row closed (at close).
