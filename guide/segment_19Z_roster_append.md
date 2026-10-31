# Segment 19Z — Append to a roster

**Opened:** 2026-10-31 · **Theme:** a roster page's upload card can add a file's rows to the roster already there, rather than only replace it · **Related:** `spec/setup_pages.md` (the Upload card), `spec/csv_contracts.md` §3 (the four roster importers), `guide/archive/segment_21F_directory_rosters.md` (the directory check every roster write runs)

## Opportunity

Every roster upload replaces the roster. `csv_imports.save_reviewers`, `save_reviewees` and `save_observers`, and `relationships.save_relationships`, delete every existing row and insert the file's. Once a roster holds anything, the Upload card asks for the replace tick ("Yes, replace the existing 154 reviewers"). An operator with a late batch has two choices:
- add each person by hand with the single-row Add form;
- rebuild the whole file, which deletes every assignment and every response on the replaced rows.

Neither fits 20 latecomers on a 1,500-row roster. The author asked for an append option on the four roster pages' Upload cards (2026-10-31).

## Decision

**A second tick on the Upload card, "Yes, append to the existing reviewers", beside the replace tick** (author, 2026-10-31). Both ticks are **unticked by default**, since each is a deliberate confirmation. They are **mutually exclusive**: ticking one unticks the other, and both may be unticked. With a roster present, Upload needs one of them ticked:
- **Replace** keeps today's wipe-and-insert.
- **Append** inserts the file's rows and leaves every existing row, assignment and response alone.

The four cards are Reviewers, Reviewees, Relationships and Observers. An empty roster shows neither tick, as today; an upload into it is simply the roster.

- **Append is all-or-nothing, as replace is.** Any blocking issue refuses the file, and nothing is written.
- **The services gain a mode**, not a second save path. `_save` and `save_relationships` take `append: bool`. Append skips the delete and the cascade counts, and runs the same validation, directory check, label save and audit event.

**Rejected:**
- *A Replace / Append radio pair, Replace preselected.* Ruled first, then withdrawn the same day (author, 2026-10-31). A preselected destructive choice is not a confirmation, and two exclusive ticks match the rest of the app's confirm ticks.
- *Merge (upsert by address).* Updating an existing row's name or tags from the file is a third mode with its own rules: which columns a blank cell clears, and whether a status change is meant. Out of scope.
- *Append from Quick Setup.* Quick Setup fills a new or empty session. Out of scope.

## Semantics

- **The ticks.** Replace keeps `confirm_replace=true`; Append posts its own field, `append=true`. A script on the card makes them exclusive. On the server, neither tick keeps today's ask, and the upload is held. Both ticks (only a direct POST, or no script) is refused with its own message. Upload stays disabled until one is ticked, as the replace tick's delete-confirm pairing does today. Replace's label still names every loss (rows, assignments, responses, relationships).
- **A row already in the roster: refused** (author, 2026-10-31). A row whose folded address matches an existing row in the same roster is a blocking issue on that row: *"ReviewerEmail is already on the roster (row N of the file)"*. That covers `ReviewerEmail` and `ObserverEmail`, a reviewee's `email_or_identifier`, and a relationship's resolved pair. This is the within-file duplicate rule, extended to the rows already saved. The rule today is in `spec/csv_contracts.md` §3.1: the second occurrence in a file is an error, and a name that disagrees is a different error.
- **Cross-roster identity** is checked against every roster, including this one's existing rows. Replace leaves out the roster it replaces (`_identity_holders(exclude=…)`); append leaves out nothing.
- **Directory check (21F).** Only the appended rows' addresses are looked up, and the import's `directory_*` counts cover only them. The Setup page's line reads "the last import", which stays true.
- **Two rows on one account: refused on append** (author, 2026-10-31). An appended row whose address resolves to an account already bound on the roster is a blocking issue: *"ReviewerEmail is the same directory account as row N's"*. The directory check runs before the save, so the file is refused before anything is written. A row the directory could not check matches no account, so this check cannot catch it. The deferred entry in `guide/deferred_consolidated.md` ("Two rows in one roster bound to one account") narrows to replace and the single-row forms.
- **Friendly labels.** A header's `<Column>.<label>` suffixes are upserted. Labels the file does not carry are kept, not cleared as replace clears them.
- **Status.** Appended rows default to `active`, as on replace.
- **Assignments and responses** are untouched. The new rows have no assignments until the next Prepare. The reconcile stamp's roster digest moves, so the Assignments page reports stale, as for any roster edit.
- **Relationships.** An appended pair names reviewers and reviewees already on their rosters, as today. Appending can change a pair-context group, so the existing ask about clearing group answers (findings S1) applies unchanged.
- **Lifecycle.** The same editable states as replace (`lifecycle.require_editable`). A validated session drops to draft, as on any roster write (`invalidate_if_validated`).
- **Audit.** The same `*.imported` event, with `context={"mode": "append"}` and the added-row count. Replace's cascade counts are omitted, not zeroed, under the same rule as `cascaded_relationships`. `EVENT_SCHEMAS` already allows `context` on these events.

## Judgment calls — decided

- **Refuse, not skip, a row already on the roster** (author, 2026-10-31). A silent skip hides a typo'd name. Refusing names the row, and the operator removes it from the file.
- **The exclusivity script and Upload's gating land with the wiring** (2026-10-31). In the scaffold, Append is disabled, so the replace tick's delete-confirm pairing alone gates Upload, exactly as before.
- **Held upload unchanged.** An append that asks (a group-answer loss on Relationships) holds the file as replace does. The ask carries the append tick.

## Blast radius (measured)

Taken 2026-10-31 at `02636177`.

| What | Count | Command |
|---|---|---|
| Upload-card templates with the replace tick | 4 (`session_reviewers.html`, `session_reviewees.html`, `session_relationships.html`, `session_observers.html`) | `grep -rln "Yes, replace the existing" app/web/templates` |
| Setup routes wiring a roster save | 4 | `grep -rn "save_fn=\|csv_imports.save_observers,\|relationships_service.save_relationships," app/web/routes_operator/_setup_*.py \| wc -l` |
| `confirm_replace` sites in operator routes | 44 | `grep -rn "confirm_replace" app/web/routes_operator/*.py \| wc -l` |
| Save services | 4 (`save_reviewers`, `save_reviewees`, `save_observers`, `save_relationships`) | `grep -n "def save_reviewers\|def save_reviewees\|def save_observers" app/services/csv_imports.py; grep -n "def save_relationships" app/services/relationships.py` |
| Test files using `confirm_replace` | 33 | `grep -rl "confirm_replace" tests --include=*.py \| wc -l` |
| Specs and docs naming replace semantics | 10 live (`spec/` 9, `docs/security_posture.md`) | `grep -rlni "wipe-and-replace\|replace the existing\|confirm_replace" spec docs` |

## Status

Open. Plan `#3433`; rung 2 `#3434` (copy `#3435`), rung 3 `#3436`, rungs 4–5 `#3437`. Rung 5 rode with rung 4 so it was not left unpushed in the container.

The one `diff-reviewer` read of `02636177..3f540f2` found nothing that deletes, cascades, or writes before a refusal. Its findings were handled in `#3437`:
- **Diverged from Semantics: cross-roster identity.** The name check still leaves out the appended roster's own rows, as on replace. Any row whose address is already on that roster is refused as "already on the roster" whatever its name, so the only difference is which message is shown.
- **Refusal wording.** The account refusal names the existing row's roster, not its row number: *"… is the same directory account as a reviewer already on the roster."* The spec follows the code.
- **The deferred two-rows entry narrows less than Semantics says.** `append_conflicts` compares appended rows with existing ones, so two file rows on one account still pass, on append as on replace.
- **An append onto an empty roster is saved as a plain upload**, as the Decision says. Only a direct POST can send one.
- **One ask sentence** names both ticks. No card is left with the replace tick alone.
- **Tests added:** a Relationships append that meets the group-clear ask; an append looks up only the file's addresses.
- **Specs the build touched beyond Doc impact:** `spec/ui_elements.md`, `spec/operator_button_audit.md`, `spec/extract_data.md`. Bullets added.

## PR ladder

1. **This plan.** Prose only.
2. **Scaffold.** The append tick on the four cards, beside the replace tick, with its copy and layout. Both are unticked. Append is drawn but disabled, and marked as not yet available. Iterate the wording on the page. Must not touch any route or service.
3. **The append mode in the services.** `append=True` through `_save` and `save_relationships`, the already-on-the-roster check, label upsert, the audit `context`, and tests at the service level. Must not touch any route.
4. **Wire Reviewers, Reviewees and Observers.** The exclusivity script, and Upload enabled by either tick. `_handle_import` and the observers import read `append`, refuse both ticks, and hold the file through an ask. The ask's sentence names both ticks. Route tests cover: append keeps every assignment and response; a row already on the roster refuses; both ticks refuse; neither tick asks.
5. **Wire Relationships.** The same, with the group-answer ask. This is the last build rung, so `diff-reviewer` reads rungs 2–5.
6. **Close.** `spec-writer` on the doc-impact specs, then the author's browser check of each card.

## Definition of done

- With a roster present, each of the four cards offers a replace tick and an append tick, both unticked. Ticking one unticks the other, and both ticks posted together are refused (tests).
- An append keeps every existing row, assignment, response and friendly label, and adds the file's rows (tests).
- A file row already on the roster refuses the file and names the row; so does an appended row bound to an account already on the roster (tests).
- ~~The cross-roster name check covers this roster's existing rows on append (test).~~ It doesn't need to: an address already on the roster is refused whatever its name (`## Status`).
- On append, only the appended rows' addresses are looked up, and the counts cover only them (test).
- The audit event records `mode: append` (test).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19Z` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~A file row already on the roster~~: refused (author, 2026-10-31).
- ~~Two ticks or a radio pair~~: two mutually exclusive ticks, neither ticked by default (author, 2026-10-31, after first ruling a radio pair).
- ~~Two rows on one account on append~~: refused (author, 2026-10-31).

## Out of scope

- **Merge / upsert** of existing rows from a file. Rejected above.
- **Append from Quick Setup** or the New session page. Those fill empty rosters.
- **Append after activation.** Append uses replace's editable states. Adding people to a live session is the single-row Add form's job.

## Doc impact

- `spec/setup_pages.md` — the Upload card's Append tick, exclusivity and copy, for the four roster pages.
- `spec/csv_contracts.md` — §3: append mode for the four importers, the already-on-the-roster rule, cross-roster identity on append, label upsert, and the audit `context`.
- `spec/assignments.md` — an append leaves assignments in place and marks them stale.
- `docs/security_posture.md` — the replace tick's description gains its Append counterpart.
- `spec/ui_elements.md` — "Delete-confirm standard": the replace tick is no longer `required`; a key may sit on more than one box (the pairing opens its button while any is ticked); the `data-exclusive-tick` group.
- `spec/operator_button_audit.md` — the Upload rows open on either tick; the second shared confirm-checkbox script (`data-exclusive-tick`).
- `spec/extract_data.md` — the pairing's unique-key note, which a shared Upload key now qualifies.
- `guide/todo_master.md` — the queue entry, deleted at close.
