# Segment 19W — A chosen file survives an ask

**Opened:** 2026-10-19 · **Theme:** after an upload asks a question, the
operator answers it without choosing the file again · **Related:**
`guide/checklist_followup_oct19.md` item 3, `spec/setup_pages.md`,
`spec/quick_setup_card_spec.md`

## Opportunity

Several uploads refuse with a question instead of an error:

- a replace sent without its tick;
- a relationships replace that would clear group answers (step 47 of the
  2026-10-19 browser run);
- a Settings file that would delete instruments (S4, step 54).

Each re-renders its card with a tick to answer. But the server rendered
the page again, and a browser cannot refill a file input on a page the
server renders. So the operator must choose the same file again before
the tick does anything. The S4 banner says so: "Choose the file again,
tick the replace box below again, then Submit." On Quick Setup a refusal
also drops every other slot's file staged in the same Submit. The author
wants the file to stay chosen, so the operator can tick and upload, or
dismiss outright.

## Decision

**Hold the file on the server, under a token, while the ask is open**:
option (c) of `guide/checklist_followup_oct19.md`, the author's ruling
of 2026-10-19.

- **Storage:** a new table, `held_uploads`, one row per held file. It is
  modeled on `rehydrate_stashes` (`app/services/rehydrate_stash.py`),
  which already bridges one operator's click-through across App Service
  instances.
- **When a file is held:** a refusal that is an ask holds the files of
  that submit. The page then names each held file in place of its empty
  input and carries the token in a hidden field.
- **The next submit:** it takes the held file for any slot left empty.
  A newly chosen file wins over the held one.
- **Ending a hold:** a successful save deletes the hold, and so does
  Dismiss.

**Rejected:**

- **Reusing `rehydrate_stashes`.** Its rows are scoped to the operator
  only, and its payload is one opaque bundle. A hold must be scoped to
  the session as well, and needs a row per slot so a held slot can be
  replaced on its own.
- **Echoing the bytes in a hidden field, and swapping the banner in
  with `fetch`.** These were options (a) and (b), and the author chose
  (c).

## Semantics

- **What counts as an ask.** A refusal that the same file plus a tick
  can answer:
  - a missing `confirm_replace`, on the Setup cards and Quick Setup;
  - a group-clear count, on the Relationships import;
  - the S4 deletion count, on the Settings slot;
  - a missing response-loss ack, on the Reviewers and Reviewees import.
    The page sends this one itself, so only a stale tab hits it.

  A plain refusal (parse, size, row cap, lifecycle) holds nothing,
  because resending the file cannot succeed.
- **Scope.** A held row belongs to one operator and one session. It is
  found only by its token together with both of those. Anyone else
  presenting the token is treated as having no hold; that is not an
  error. Deleting the session or the user deletes its holds (`CASCADE`).
- **Lifetime.** One hour from when it was held, the same as
  `rehydrate_stash.STASH_TTL`. An expired hold reads as absent, and the
  card shows "The held file expired; choose it again". Each new hold
  first sweeps expired rows, so nothing needs a scheduler.
- **Size.** A hold is capped at `csv_imports.MAX_BYTES` (1 MiB) per
  file. The Settings slot has no cap of its own today, so a larger
  Settings file is simply not held. The ask still shows, and the file is
  chosen again as now.
- **Quick Setup.** One token covers every slot of the refused submit.
  Each slot shows either its held file's name or its empty input.
  Choosing a file for a slot replaces only that slot's hold.
- **Dismiss.** It becomes a POST that deletes the token's rows and then
  redirects to the page. This replaces Item 1's in-place hide for a
  banner that holds files. A banner with nothing held keeps the link.
- **Same ask, new answer.** The re-offered ticks keep their current
  meaning. The count ticks still carry the count, so the server refuses
  afresh when a resubmit finds a different count. The held bytes are
  parsed again on every submit; a hold is never trusted as
  already-checked.

## Judgment calls — decided

- **No audit event for a hold or a discard.** It is transient and saves
  nothing; the import it leads to is audited as now.
- **No scaffold rung.** This changes existing cards and adds no page,
  card or navigation, so `CLAUDE.md`'s scaffold-first rule does not
  apply.
- **The Create page is out.** It cannot ask (`_quick_setup.py:352-361`
  runs with `replacing=False`), so it never holds a file.

## Blast radius (measured)

Taken 2026-10-19 at `9b6e0afa`.

| What | Count | Command |
|---|---|---|
| Routes that read an upload | 4 (`_shared.py:871`, `_setup_relationships.py:114`, `_setup_observers.py:901`, `_quick_setup.py:501`) | `grep -rn "await file.read()\|await upload.read()" app/web/routes_operator/` |
| Files naming `missing_confirm` | 20 references | `grep -rn "missing_confirm" app/ \| wc -l` |
| Templates including `_upload_problems.html` | 4 | `grep -rln "_upload_problems.html" app/web/templates \| wc -l` |
| Files on the S4 path | 3 app, 4 tests | `grep -rln "deletes_instruments\|acknowledge_instrument_deletion" app/ tests/` |
| Specs and docs naming `confirm_replace` or "chosen again" | 7 live (`spec/operator_button_audit.md`, `spec/assignments.md`, `spec/csv_contracts.md`, `spec/setup_pages.md`, `spec/workflow_card.md`, `spec/quick_setup_card_spec.md`, `docs/security_posture.md`) | `grep -rln "Choose the file again\|chosen again\|confirm_replace" spec/ docs/` |
| Tests naming `confirm_replace` | 30 | `grep -rln "confirm_replace" tests/ \| wc -l` |

## Status

**2026-10-19, rung 2.** The storage landed as planned. Of the docs this
rung named, only `docs/backup_restore.md` states what happens to an
upload, so it took the change. `spec/architecture.md`,
`docs/database.md` and `docs/security_posture.md` are waived in `Doc
impact`: none lists tables or retained data.

**2026-10-19, rung 3.** The four Setup cards hold the file on each ask,
as planned. Things the plan did not spell out:

- The import routes take the file as optional: an empty input arrives
  as `None`.
- A plain refusal ends any hold in play, so a hold never outlives a
  file the operator has replaced.
- Dismiss posts the card's own form to `…/import/dismiss` through
  `formaction`, so there is no nested form.
- The Danger Zone's group-clear banner got the link Dismiss it lacked.

## PR ladder

1. **This plan.** Prose only.
2. **Storage.**
   - Lands: the `HeldUpload` model, the migration (off head
     `d2f7a3c9b5e4`), and `app/services/held_uploads.py` with `hold`,
     `take`, `discard` and `sweep`, plus unit tests.
   - Does not touch: any route or template.
3. **The Setup cards.**
   - Lands, for Reviewers, Reviewees, Relationships and Observers: the
     ask holds the file, the card names it with the token, the route
     takes the held file, and Dismiss posts a discard. The Relationships
     group-clear banners gain the Dismiss that `spec/ui_elements.md` §5a
     asks for; it is missing today (cold read of #3144). Tests, plus a
     browser test of tick-and-upload.
   - Does not touch: Quick Setup.
4. **Quick Setup on Home.**
   - Lands: holds per slot under one token, each slot shown held, the
     S4 sentence rewritten without "Choose the file again", and Dismiss
     posting a discard. Tests and specs.
   - The cumulative `diff-reviewer` read runs here, from `9b6e0afa`.
5. **Close.**

## Definition of done

- Re-running steps 47 and 54 of the browser run, the operator ticks and
  submits without choosing a file; Dismiss leaves nothing held. Both are
  checked by browser tests.
- Holding the files of a refused submit, then saving them on a second
  submit, gives the same rows as uploading the same files directly.
  Checked by integration tests.
- Another operator or another session presenting the token gets no file,
  and an hour-old hold reads as expired. Checked by unit tests.
- `alembic upgrade head` and `downgrade base` pass on Postgres
  (`ci-postgres`).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19W` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entry deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~Keep the replace tick ticked on a resubmit?~~ **Yes** (author,
  2026-10-19): after an S4 or group-clear ask the replace tick renders
  ticked again; after a missing-replace ask it renders unticked.

## Out of scope

- **The Create page:** it cannot ask; see Judgment calls.
- **Rehydrate:** it has its own stash.
- **Possible bug, filed separately rather than fixed here:**
  `rehydrate_validate` stashes with a flush and never commits
  (`_rehydrate.py:137-159`), so the stash may not survive the request.
  It sits behind a flag that is off.
- **A byte cap on the Settings import:** a separate change, if wanted.

## Doc impact

- `spec/setup_pages.md` — the upload cards: an ask holds the file; the held name, the token, Dismiss as a discard (rung 3).
- `spec/quick_setup_card_spec.md` — Quick Setup's held slots, the S4 sentence, Dismiss (rung 4).
- `spec/ui_elements.md` — §5a: an upload banner's Dismiss discards a hold (rungs 3–4).
- `docs/backup_restore.md` — "Import files": an upload that asks holds its files in `held_uploads`, its scope, cap, lifetime and deletion (rung 2).
- `spec/architecture.md` — the `held_uploads` table and `app/services/held_uploads.py` in the module map (rung 2). <!-- doc-impact-waived: the module map lists route modules, not services or tables; rehydrate_stashes is not in it either (rung 2, 2026-10-19) -->
- `docs/database.md` — the `held_uploads` table (rung 2). <!-- doc-impact-waived: the doc carries no table inventory to add a row to (rung 2, 2026-10-19) -->
- `docs/security_posture.md` — held uploads: operator and session scope, the one-hour lifetime (rung 2). <!-- doc-impact-waived: it carries no data-at-rest section; docs/backup_restore.md "Import files" is where retained uploads are stated (rung 2, 2026-10-19) -->
