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

## Decision — amendment: upsert (author, 2026-10-31)

After append shipped (`#3437`), the author asked for upsert too, ruled "go with the defaults" on all fourteen questions, and took the recommendation on matching (2026-10-31).

**A third tick, "merge", sharing append's line** on the four cards (author, 2026-10-31):

> `[ ] Yes, replace the existing N reviewers …`
> `[ ] Yes, append to, [ ] merge with the existing roster.`

None is shown on an empty roster. All three are mutually exclusive, none is ticked by default, and Upload stays disabled until one is. Merge is the upsert: a file row already on the roster updates that row, and any other row is added, as in append. Rows absent from the file are kept.

**And a Validate warning for two rows on one directory account,** on each person roster. It lifts the deferred entry's Validate half into this segment, so a second row for one person is flagged however it arrived (upsert, append, replace or the Add form), as long as both rows are bound to the account.

**Rejected:** *looking up the roster's unbound rows on an upsert*, to catch an existing row the directory never resolved. It can double the lookup on a 1,500-row roster inside one 120-second budget. The cost is a gap: an existing row the directory never resolved, matched by a file address for the same person, is added as a second row that nothing flags (Codex, `#3438`).

**Item: matched addresses as pills** (author, 2026-10-31, after production went live on RRW `920f5c7`). In the three roster tables and the Assignments table, an address bound to a directory account reads as the plain display pill (`pill pill-count`), its case kept, with a "Matched to a directory account" tooltip. Any other address stays plain code. One macro, `operator/partials/_roster_address.html`, renders all five cells. Widened the same day (author): the Relationships table, the Invitations and Responses tables, and their per-reviewer / per-reviewee drill-ins take the same macro, eleven cells in all.

**Item: accounts verified in the directory** (author, 2026-10-31, after production). Someone who cannot sign in to the institution cannot be an operator or a sys-admin, yet Accounts › Invite takes any address. Owners are drawn only from existing operators (`session_owners.add_owner`), so the invite is the one gate.

- **The invite looks the address up** (21F's `look_up_all`, on the inviting admin's delegated token). An account that resolves to one person is created with its Entra object ID in `external_principal_id`, the column sign-in matches first (`users.find_signed_in_user`), so whoever signs in as that person finds the account, whichever of their addresses they use. The address is kept as written.
- **Refused:** not found, ambiguous, and an object ID another account already holds (one person, one account; else sign-in would pick between two rows). That last refusal also keeps sign-in's absorb safe: `users._absorbable` reads a blank principal as "never signed in", so a bound invite is never folded into another row, and none can exist for the same person.
- **Verified** reads as an account with a non-blank `external_principal_id`: one bound at invite, or one that has signed in. The Accounts table, Session Home's Owners card and New session's owners picker show a verified address as the roster pill (`_roster_address.html`, "Matched to a directory account"); others stay plain code. No migration and no backfill: an account unbound today binds itself at its first sign-in, as it does now.


- **Matching.** A row matches by its folded address; on Relationships, by its resolved pair. A new address is a new row, and an address change stays a single-row edit. A file row whose address resolves to a directory account bound on the roster updates that bound row and **keeps its stored address**, since matching and mail already follow the account. An unresolved file address, or an unbound existing row, can't be matched by account, so the row is added. The Validate warning names the pair only when both rows are bound. An unbound existing row stays unflagged until something binds it: re-uploading the roster with replace, or editing its address (Codex, `#3438`).
- **Blank cells and absent columns keep the existing value.** A file can carry only the columns it changes; nothing is cleared by an upsert. Observers' cohort rule is a column like any other.
- **Status** changes only where the Status column is present. Deactivating a reviewer or reviewee excludes their assignments, as the single-row edit does.
- **A name change applies** if it passes the cross-roster name check, which on upsert compares against every roster with the updated row's own old name set aside. A failure refuses the file, naming the row.
- **A tag change that redraws an answered group** asks first, holding the file, as Relationships' group-clear ask does: the same count-carrying tick and the same refusal-then-re-offer.
- **Two file rows for one person** (a folded address, or one directory account) refuse the file, as the within-file duplicate rule does.
- **Labels** in the header are upserted and none cleared, as on append.
- **Audit.** The `*.imported` event counts `new`, `updated` and `unchanged`, with `context.mode = "upsert"`. Each updated row also writes its `*.updated` event with the `changes` envelope, so a row's history stays row by row.
- **Where.** The four roster cards only; Quick Setup and rehydrate are unchanged, as with append.
- **The Validate warning** (`reviewers.duplicate_account`, `reviewees.duplicate_account`, `observers.duplicate_account`): soft, so it never blocks Validate. It lists two or more active rows bound to one `directory_object_id`.

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

- **A local run's invite checks nothing** (accounts item, 2026-10-31): its directory is the five fake people and the accounts invited there are made up, so refusing them would stop local work; the refusals are tested with the fake directory injected.

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

Upsert rungs (2026-10-31): rung 7 rode with the amendment (`#3438`), rung 8 `#3439`, rungs 9–10 `#3440`. The one `diff-reviewer` read of `a384197c..bae148ed` found nothing that deletes or cascades on a merge. Codex (`#3440`) and the read found these, all handled in `#3440`:
- **A rename through an account match** is checked at the row's kept address, before any row is touched. The route's check covers only the file's addresses.
- **A reviewer merge recomputes self-review**, since a binding it adds can make a pair one person.
- **Status is per cell, not per column.** A blank Status cell keeps the stored status (`*ImportRow.status_given`). The column test alone wrote `active` over `inactive`.
- **Two file rows landing on one existing row** (one by address, one by account) refuse the merge.
- **The cohort rule** is compared with `same_cohort_rule`, as the row editor does. It is still logged in `observer.updated`, not in `observer.cohort_rule_assigned`.
- Recorded, not changed:
  - Two rows at one address in one roster: a merge updates the lower one, and Validate's `duplicate_email` already flags the pair.
  - A bound row matched by address whose address now resolves to another account keeps its binding, where replace would rebind it.

**Walkthrough** (2026-10-31): the author's basic browser check passed; the full check is `guide/walkthrough_19Z_rosters.md` (local, then the real tenant). The close waits on it.

## PR ladder

1. **This plan.** Prose only.
2. **Scaffold.** The append tick on the four cards, beside the replace tick, with its copy and layout. Both are unticked. Append is drawn but disabled, and marked as not yet available. Iterate the wording on the page. Must not touch any route or service.
3. **The append mode in the services.** `append=True` through `_save` and `save_relationships`, the already-on-the-roster check, label upsert, the audit `context`, and tests at the service level. Must not touch any route.
4. **Wire Reviewers, Reviewees and Observers.** The exclusivity script, and Upload enabled by either tick. `_handle_import` and the observers import read `append`, refuse both ticks, and hold the file through an ask. The ask's sentence names both ticks. Route tests cover: append keeps every assignment and response; a row already on the roster refuses; both ticks refuse; neither tick asks.
5. **Wire Relationships.** The same, with the group-answer ask. This is the last build rung, so `diff-reviewer` reads rungs 2–5.
6. ~~**Close.**~~ Moved to rung 10 by the upsert amendment.
7. **The Validate warning.** The three `*.duplicate_account` soft rules, with tests. Must not touch the upload cards.
8. **Upsert scaffold.** The merge tick on append's line on the four cards ("Yes, append to, [ ] merge with the existing roster."), drawn and disabled, in the same exclusive group. Wording settled on the page.
9. **Upsert in the services.** `mode="upsert"` through `_save` and `save_relationships`: matching (address, pair, account), blank-keeps, Status only when its column is present, the name check, per-row `*.updated` events, and the counts. Service tests. Must not touch a route.
10. **Wire upsert on the four cards, then close.** Wiring, the tag-change group-clear ask on the person rosters, route tests; the cumulative `diff-reviewer` read of rungs 7–10 (base: `main` before rung 7). Then the close: `spec-writer` on the doc-impact specs, and the author's browser check of each card.
11. **Matched addresses as pills** (the item above). Must not touch a route or service.
12. **Pills on Relationships, Invitations and Responses** (the widening). Same macro; must not touch a route or service.
13. **Accounts: this item's plan.** Prose only.
14. **Verify on invite.** `users.invite` takes the lookup's outcome: binds the object ID, refuses the three cases; the route hands in the directory; the invite card names a refusal. Service and route tests. Must not touch the pills.
15. **Verified accounts as pills.** The Accounts table, Owners card and New session owners picker take the pill. Must not touch a service. *(At build, 2026-10-31: the Accounts and Owners rows are service-built, so each row shape gained a display-only `verified` field; no behavior changed.)* *(Widened the same day, author: on Accounts the verified account's name takes the pill too, a `<span>` in the body font, `account_name`.)*

## Definition of done

- With a roster present, each of the four cards offers a replace tick and an append tick, both unticked. Ticking one unticks the other, and both ticks posted together are refused (tests).
- An append keeps every existing row, assignment, response and friendly label, and adds the file's rows (tests).
- A file row already on the roster refuses the file and names the row; so does an appended row bound to an account already on the roster (tests).
- ~~The cross-roster name check covers this roster's existing rows on append (test).~~ It doesn't need to: an address already on the roster is refused whatever its name (`## Status`).
- On append, only the appended rows' addresses are looked up, and the counts cover only them (test).
- The audit event records `mode: append` (test).
- Each card offers a merge tick on append's line, exclusive with the other two and hidden on an empty roster (tests).
- An upsert updates matched rows (by address, pair, or bound account, keeping the stored address), adds the rest, keeps absent rows, and leaves blank cells and absent columns as they were (tests).
- An upsert's Status, name and tag changes behave as Semantics — upsert says, the tag change asking first (tests).
- Validate warns, without blocking, on two active rows bound to one account in a roster (tests).
- A bound address is a display pill in the roster, Relationships, Assignments, Invitations and Responses tables and the two drill-ins; an unbound one is plain code (tests).
- An invite binds a resolved address's object ID and refuses not found, ambiguous and an account already held (tests); a verified account's address is a pill on Accounts, the Owners card and the New session picker, and its name a pill on Accounts (tests).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19Z` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~A file row already on the roster~~: refused (author, 2026-10-31).
- ~~Two ticks or a radio pair~~: two mutually exclusive ticks, neither ticked by default (author, 2026-10-31, after first ruling a radio pair).
- ~~Two rows on one account on append~~: refused (author, 2026-10-31).
- ~~An invite whose lookup could not run~~: created unverified and plain, the card saying it was not checked; the person binds at first sign-in (author, 2026-10-31).
- ~~Sign-in as verification~~: an account that has signed in counts as verified (author, 2026-10-31).

## Out of scope

- ~~**Merge / upsert** of existing rows from a file. Rejected above.~~ Taken in by the 2026-10-31 amendment.
- **Append from Quick Setup** or the New session page. Those fill empty rosters.
- **Append after activation.** Append uses replace's editable states. Adding people to a live session is the single-row Add form's job.

## Doc impact

- `spec/setup_pages.md` — the Upload card's Append and Upsert ticks, exclusivity and copy, for the four roster pages; the roster and Relationships tables show a bound address as a pill.
- `spec/csv_contracts.md` — §3: append and upsert modes for the four importers, the already-on-the-roster rule, matching on upsert, blank-keeps, label upsert, and the audit `context`.
- `spec/assignments.md` — an append leaves assignments in place and marks them stale; the table's address cells show a bound address as a pill.
- `docs/security_posture.md` — the replace tick's description gains its Append counterpart.
- `spec/ui_elements.md` — "Delete-confirm standard": the replace tick is no longer `required`; a key may sit on more than one box (the pairing opens its button while any is ticked); the `data-exclusive-tick` group; §9 gains the `pill-address` modifier (a pill that keeps its text's case and size: on a roster or account `<code>` address, and on a verified account's name `<span>` in the body font).
- `spec/operator_button_audit.md` — the Upload rows open on either tick; the second shared confirm-checkbox script (`data-exclusive-tick`).
- `spec/extract_data.md` — the pairing's unique-key note, which a shared Upload key now qualifies.
- `spec/validate_page.md` — the three `*.duplicate_account` soft rules (upsert amendment).
- `spec/operations_pages.md` — the Invitations and Responses tables and their drill-ins show a bound address as a pill (pills item, widened).
- `spec/architecture.md` — "Audit-event detail schema": the `*.imported` counts `new` / `kept` (append) and `new` / `updated` / `unchanged` (upsert) with `context.mode`, and the per-row `*.updated` events a merge writes.
- `guide/deferred_consolidated.md` — "Two rows in one roster bound to one account": its Validate half shipped; the entry narrows to refusing at upload (at close).
- `spec/permissions.md` — an invite is checked against the directory: bound on a match, refused when not found, ambiguous or already held, the three codes and the "not checked" notice joining the Invite errors; a bound invite is never absorbed at sign-in (`get_or_create_user`, the absorb sentences), and the principal match is case-insensitive (accounts item).
- `spec/settings_inventory.md` — `users.external_principal_id` can also be set by a verified invite (accounts item).
- `spec/session_owners.md` — the Owners card and the New session picker show a verified owner's address as a pill (accounts item).
- `spec/operator_ui_concept.md` — Accounts Management: a verified account's address and name read as pills (accounts item).
- `guide/todo_master.md` — the queue entry, deleted at close.
