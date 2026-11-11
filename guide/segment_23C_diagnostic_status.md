# Segment 23C — Interoperability proof of concept: status as Review Robin reports it

**Opened:** 2026-11-11 · **Theme:** the handoff status carries what Review Robin itself shows about a session, for the diagnostic Utilities tool · **Related:** `guide/archive/segment_23B_interop_return.md`, `spec/handoffs.md` §10

## Opportunity

23B's status is a trimmed projection, and on production it misleads (author, 2026-11-11):

- **Two rosters of four.** It counts reviewers and reviewees, not relationship pairs or observers.
- **"1 instrument" when none is set up.** It counts instruments without asking whether they are set up, though Review Robin validates no session until each one is.
- **"0 complete of 24".** The 24 are an untouched rule's full-matrix stand-in, which Review Robin would not activate.

The Utilities tool is diagnostic. Its status should carry what Review Robin reports about the session, not a summary of it (author, 2026-11-11).

## Decision

**Status v3 reports Review Robin's own readings, unfiltered, each labelled for what it is.** It reuses the functions Review Robin's pages read, rather than new counts:

1. **The status row** (`views.session_status_pills`, shown on every session page): the four rosters, assignments, instruments and how many are set up, the invitations state, and responses as drafts and submitted.
2. **Schedule:** the `display_timezone`, `deadline`, `scheduled_activate_at`, `activated_at`, `responses_release_at` and `responses_release_until`, as stored.
3. **Validation** (`validation.validate_session_setup`, the Validate page's run): would the session validate now? Each issue gives its rule key, severity and message. It is read only, with nothing stamped.
4. **Instruments:** each one's `InstrumentSeq`, label, set up or not, scope (per reviewee or group), and assignment count.
5. **Progress** (`monitoring`): the reviewer summary (assigned, invited, opened, submitted, incomplete) and the assignments' completion. It is always reported, with `provisional: true` and the reason while any instrument is not set up, rather than withheld.
6. **Per person** (Monitoring's own tables): each reviewer's progress state and counts, and each reviewee's coverage state.

The page shows each section as Review Robin labels it.

**Rejected:**
- **Withholding progress until instruments are set up.** That was drafted after the author's first note, and is parked as `wip-status-v2`. A diagnostic hides nothing; it labels.
- **A new set of counts.** A number the sender sees should be the one Review Robin's page shows.

## Semantics

- **Composition is a view.** `session_status_pills` lives in `app/web/views/`, which services may not import, so the status is assembled by a view adapter (`app/web/views/_handoffs.py`) over services and views. The route stays thin.
- **Read only.** No lifecycle step, no validation stamp, no audit, as 23B.
- **Schema:** `status_schema_version` 3. The 23B sender is the only consumer and moves in the same ladder.
- **Who may read** is unchanged: keyed by transfer, the session operator now (`spec/handoffs.md` §10). Per-person rows carry participants' emails, as the Monitoring page does, to someone who may already see that page.

## Judgment calls — decided

- Per-person rows are included: the tool is diagnostic and its reader is the session's operator.
- Validation reports every issue, warnings included, by rule key: the sender maps none of them.

## Blast radius (measured)

Taken 2026-11-11 at `e7e290b`.

| What | Count | Command |
|---|---|---|
| Files calling the status row it reuses | 12 | `grep -rln "session_status_pills(" app \| wc -l` |
| Functions in the handoff service today | 18 | `grep -c "^def " app/services/handoffs.py` |
| The validation run it reads | 1 (`validate_session_setup`, `app/services/validation/_registry.py:474`) | `grep -n "def validate_session_setup" app/services/validation/_registry.py` |
| View adapter modules, to gain `_handoffs.py` | 35 | `ls app/web/views/ \| grep -c "^_"` |

## PR ladder

1. **Plan** (this file).
2. **Status v3.** The view adapter, the route, `spec/handoffs.md` §10, and tests for each section, including `provisional` while an instrument is not set up. Not touched: the page.
3. **The page.** It shows each section as Review Robin labels it, with per-person rows in collapsed tables. This is the last build rung: `diff-reviewer` reads the cumulative diff.
4. **Close.**

## Definition of done

- On `/utilities/interop-poc/`, **Refresh status** for a fresh handoff shows:
  - the four rosters;
  - "0 of 1 instruments set up";
  - the validation issues;
  - progress marked provisional.

  Once the instrument is set up and assignments are generated, progress is no longer provisional. Verified on localhost and production by the author.
- `tests/integration/test_handoffs.py` covers every section.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 23C` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

None.

## Out of scope

- **The CSVs.** `results.csv` and `completion.csv` are unchanged.
- **Anything that writes.** Generating assignments or validating stays in Review Robin.

## Doc impact

- `spec/handoffs.md` — §10's status: version 3, its sections, `provisional`.
- `utilityapps/spec/utilities.md` — what **Refresh status** shows.
- `guide/todo_master.md` — the queue entry, deleted at close.
