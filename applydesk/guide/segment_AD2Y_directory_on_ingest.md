# Segment AD2Y — The directory on ingest

**Opened:** 2026-11-28 · **Theme:** every person Apply Desk takes in is looked up in the directory, as Review Robin's rosters are, not only the one a search picks or a sign-in binds · **Related:** `applydesk/guide/ad2_series.md`, `applydesk/spec/applications.md`, `applydesk/spec/architecture.md`, `cordware/spec/identity.md`

## Opportunity

- **Most of what Apply Desk takes in skips the directory.**
  - *Create dossiers*' and *Invitees*' CSV (`candidates.read_csv`) store each row on record or pending: "the directory is searched one person at a time, from the search, not per CSV row" (its docstring).
  - *Panels*' save stores each member the same way (`panels_store._on_record`).
  - Only the search's add (`people.from_directory`) and a sign-in (`people.resolve`) bind a person.
- **So addresses are unchecked.** A list uploaded from elsewhere keeps every address unchecked: a typo, a UPN in place of the mail, or a leaver all go through unseen. The Dossiers table's pill (#4283) shows which addresses are bound.
- **Panels' typeahead is not the directory.** It offers the sample institution's people (`people.institution.members`, "the sample institution until AD4"), and its "found in the directory" check reads that list.
- **Review Robin already does this.** Its rosters look each address up at upload (`cordware.graph.look_up_all`, classified by `classify`). An address not found is kept, unmatched and counted. A *Recheck* asks again later (segment 20I Item 1).

## Decision

- **One Apply Desk service, `applydesk/directory_check.py`**, over Cordware's `look_up_all` and `classify`. It turns a set of addresses into bound people:
  - Each found address (by mail, or by UPN with or without a mail) goes through `people.from_directory`.
  - An address not found, or ambiguous, stays pending. The person is kept, as Review Robin keeps the row (author, 2026-11-28).
  - It returns counts: by mail, by UPN, not found, ambiguous, not checked, and why not checked.
  - Apply Desk cannot import Review Robin, so it reimplements the shape of `directory_accounts.resolve` here. Cordware owns the lookup.
- **Every upload uses it.**
  - Create dossiers' CSV, Invitees' CSV and Panels' CSV look each distinct address up when the file is saved.
  - The reply names the counts. The page shows them in one line, worded as Review Robin's Upload card words them.
  - An expired sign-in holds the upload and asks the operator to sign in again. Any other failure saves, counted as not checked.
- **The typeahead is the directory** (author, 2026-11-28).
  - Panels' add-member box searches as Create dossiers' and Invitees' do (`directory.search`).
  - A person picked there is already found, so only an upload needs the lookup.
  - The sample-institution list and its client-side check go.
- **A *Recheck*** on each list (Create dossiers' entries on Dossiers, Invitees, Panels' roster) asks again for its pending people. It binds the ones now found and is audited (author, 2026-11-28).

**Rejected:**
- **Refusing a row the directory does not find.** Review Robin keeps it and counts it, and so does this segment (author, 2026-11-28). Panels' CSV note "People not found in the directory are left out" is reworded to match.
- **Checking each address as it is typed.** The typeahead is a directory search, so typing already finds a directory person, and a per-keystroke lookup adds nothing.
- **Sharing Review Robin's `directory_accounts`.** The import boundary forbids it (`cordware/tests/test_import_boundary.py`). Cordware already holds the part both share.

## Semantics

- **Matching.** Each address is looked up once per upload, folded with `people.email_key`. A UPN match binds the account, and the person's address becomes the account's mail when it has one. That is the address mail goes to, as with Review Robin's `recipient()`.
- **Two rows, one account.** Two addresses in one file that resolve to one account are one person. Create dossiers counts them against the per-person cap; Invitees and Panels keep one. They are not refused: Apply Desk keys people, not rows.
- **An existing pending person** found now is bound in place (`_attach` binds the pending row). Their entries, invitations and memberships stay with them.
- **No directory** (no token, the directory refused): the upload saves, every address is counted as not checked, and *Recheck* can finish the job later. An expired sign-in (`unauthorized`) saves nothing.
- **Budget.** The lookup runs inside the save with Review Robin's 120 s budget and 4 workers. Addresses it does not reach count as not checked.
- **Local runs.** `directory.for_request`'s fake directory already holds `local_directory.PEOPLE`, so the seed's Create dossiers CSV comes out bound with no seed change.

## Judgment calls — decided

- **Synchronous at save, no countdown** in version 1. Review Robin's pre-save countdown (20H Item 6) exists for 2,000-row rosters on a live Graph. Apply Desk's lists are smaller, and *Recheck* covers a lookup that runs out of budget (2026-11-28).
- **Recheck lands wired, with no scaffold.** It is one button on an existing card, beside the upload, not a new card or page (2026-11-28).

## Blast radius (measured)

Taken 2026-11-28 at `3ec4683da`.

| What | Count | Command |
|---|---|---|
| Non-test lines naming the CSV readers | 6 | `grep -rn "read_csv(\|import_csv(" applydesk --include=*.py \| grep -v /tests/ \| wc -l` |
| Non-test lines naming the on-record-or-pending helper | 6 | `grep -rn "_on_record(" applydesk --include=*.py \| grep -v /tests/ \| wc -l` |
| Uses of the sample institution in Panels | 3 | `grep -rn "people.institution" applydesk --include=*.py --include=*.html \| grep -v /tests/ \| wc -l` |
| Non-test lines looking an address up | 2 | `grep -rn "find_users(" applydesk --include=*.py \| grep -v /tests/ \| wc -l` |
| Test files on the CSVs, Panels' save or the pill | 10 | `grep -rln "read_csv\|import_csv\|panels_store.save\|pl-addr\|data-verified" applydesk/tests \| wc -l` |
| Specs naming the directory | 2 | `grep -rln "directory" applydesk/spec` |

## Status

- Rung 2: `look_up` (asks and counts, no database) and `bind` (stores the found, in the caller's transaction), so a caller refuses an expired sign-in before writing anything. No audit event of its own: `people.from_directory` audits each binding, and the upload's counts go on its own event at rung 3, *Recheck*'s at rung 5.

## PR ladder

1. **Plan** (this file), its README row, and the AD2 series row. Prose only.
2. **The service.** `directory_check.py` with its counts, and audit events registered in `EVENT_SCHEMAS`. Tests use `FakeDirectory`, including its failing addresses. Must not touch: any page.
3. **Create dossiers' and Invitees' CSV use it.** The reply's counts, the page's directory line, and the expired sign-in hold. Must not touch: Panels.
4. **Panels.** The typeahead searches the directory (a `panels/search` route like `candidates/search`). The CSV is looked up at save. The sample-institution list and its client-side check go, and the CSV note is reworded.
5. **Recheck** on Dossiers (Create dossiers' entries), Invitees and Panels: a route per list over one service function, audited.
   - **Last build rung:** `diff-reviewer` on the cumulative diff from rung 2's base.
6. **Close:** `spec-writer` on the specs below, Status compacted, and the plan archived.

## Definition of done

- A Create dossiers or Invitees CSV of local-directory addresses saves them bound, and an unknown address pending and counted (test).
- An expired sign-in saves nothing and says so (test: a directory that answers `unauthorized`).
- Panels' typeahead returns directory people, and `people.institution` is no longer read by Panels (test and grep).
- *Recheck* binds a pending person the directory now finds and audits it (test).
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2Y` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **Recheck's place on Dossiers:** in the Create dossiers add row, or in the page's bulk bar. Decided at rung 5's browser check by the author.

## Out of scope

- A pre-save countdown for large lists (Review Robin's 20H Item 6). Revisit if uploads time out.
- The Form's *Select people* question's pool, which is AD2D's institution-wide search.
- Mail sending to the bound address, which is AD7's.

## Doc impact

- `applydesk/spec/applications.md` — Create dossiers', Invitees' and Panels' uploads look addresses up; the directory line; *Recheck*; Panels' typeahead is the directory.
- `applydesk/spec/architecture.md` — the `directory_check.py` row; `candidates.py`, `panels_store.py` and `directory.py` rows; the audit events.
- `applydesk/guide/ad2_series.md` — the AD2Y row.
- `applydesk/README.md` — the plan's row.
