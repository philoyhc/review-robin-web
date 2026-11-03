# Segment 20H — Follow-ups from the 19Z walkthrough

**Opened:** 2026-11-03, at the author's request, from Part A of `guide/archive/walkthrough_19Z_rosters.md` (run locally the same day) · **Theme:** the consequential findings of that run, one item each · **Related:** `guide/archive/segment_19Z_roster_append.md`, `guide/deferred_consolidated.md`

Items close independently. Smaller fixes from the same run go to 20C. The segment closes when its six items have (Item 6 added 2026-11-03, from Part B).

## Item 1 — Refuse a second row on one directory account in the single-row forms

### Opportunity

On Reviewers, the Add form took `e0123456@example.edu` while Jane was on the roster as `jane.tan@example.edu`; only Validate's `reviewers.duplicate_account` warning flagged it (walkthrough A6). The two rows share one directory account, so sign-in reaches only the lowest-id row, and the other row's assignments can never be completed. Uploads already refuse this: append with "… is the same directory account as row N's" (`app/services/csv_imports/_modes.py`), merge as two rows for one person.

### Decision

**Refuse** (author, 2026-11-03), in the Add form and an address edit, on Reviewers, Reviewees and Observers: when the address resolves to an account already bound on the same roster, the form is refused with append's wording, naming the existing row so the operator edits it instead. This answers the single-row half of `guide/deferred_consolidated.md`, "Two rows in one roster bound to one account".

Rejected: *keep the warning alone.* It leaves a row nobody can complete, and the uploads already refuse the same case.

### Semantics

- A lookup that cannot bind (not found, ambiguous, not checked) matches no account, so the form is allowed, as an upload allows it.
- An inactive row still holds its account: adding a second row is refused; the operator reactivates or edits the first.
- The Validate warning stays, for a row bound later (a replace) and for rows that pre-date this.

### Blast radius (measured)

Taken 2026-11-03 at `49bb4a8c9`: the three create services and their update paths (`create_reviewer` / `update_reviewer` in `app/services/reviewers.py`, `create_reviewee` in `app/services/reviewees.py`, `create_observer` in `app/services/observers.py`; `grep -n "^def create_\|^def update_" app/services/reviewers.py app/services/reviewees.py app/services/observers.py`), each already taking `resolve_account`; the append refusal to share wording with (`app/services/csv_imports/_modes.py`).

### PR ladder

1. One PR: the shared check in the three services, the route messages, a test per roster for add and edit. Own read.

### Definition of done

- Adding or editing a row to an account already bound on the same roster is refused on all three rosters, by test.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20H.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

None.

### Doc impact

- `spec/setup_pages.md` — the single-row forms refuse a second row on one directory account (Item 1).
- `spec/validate_page.md` — the `*.duplicate_account` rules' remaining cases: rows bound by a replace, and older rows (Item 1).
- `guide/deferred_consolidated.md` — "Two rows in one roster bound to one account": the single-row half answered; replace remains (Item 1).

## Item 2 — An instrument's label shows the wrong number just after it is added

### Opportunity

After adding a second instrument, the Instruments page showed `Instrument_1` and `Instrument_4`; later, with nothing changed, `Instrument_1` and `Instrument_2`, as Assignments' Per-instrument status also did (walkthrough A5). The label is `Instrument_{session_seq}` (`_instrument_label`, `app/services/instruments/_state.py`), per-session since 19Q Item 6; before that it was `Instrument_{id}`, workspace-wide, and 4 fits the new instrument's `id`. So one path, at or just after creation, appears to render `id` or a `session_seq` not yet assigned.

### Decision

Reproduce first: add an instrument in a session of a workspace with instruments in other sessions, and read the label on the page the add returns to. Then fix the path that shows it, with a test. Rejected: *renumber labels to display position*, since `session_seq` is deliberately stable for the audit summaries it is written into.

### Blast radius (measured)

Taken 2026-11-03 at `49bb4a8c9`: the label's two forms, Python and SQL, pinned together by `tests/integration/test_instrument_session_seq.py`; the Instruments page reads `session_seq` for its palette (`app/web/templates/operator/instruments_index.html`). The failing path is not yet known.

### PR ladder

1. One PR: the reproduction as a failing test, then the fix. Own read.

### Definition of done

- A test adds an instrument beside other sessions' instruments and reads `Instrument_{session_seq}` on the page the add returns to.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20H.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

- If it does not reproduce: close as not reproduced, with the steps tried (author).

### Doc impact

- `spec/instruments.md` — nothing expected; named in case the fix shows the label rule needs a line (Item 2). <!-- doc-impact-waived: only if the fix leaves the rule as written -->

## Item 3 — The audit log: find events by facility

### Opportunity

Checking `reviewer.updated` events (walkthrough A4) meant scanning the session's audit log (author: "add a search/filter for event facility"). The page already has an Event type multi-select (`app/web/templates/operator/sys_admin_session_audit_log.html`), one entry per type, which is long and needs Ctrl/Cmd-click.

### Decision

To be ruled at the scaffold (open question): a text search over event types, or a facility filter, the part before the dot (`reviewer`, `instrument`, `session`), that selects every type in it. Scaffold first: the control, inert, beside the existing select.

### Blast radius (measured)

Taken 2026-11-03 at `49bb4a8c9`: one route (`sys_admin_session_audit_log` in `app/web/routes_operator/_sys_admin.py`) and its template; the filter form's view.

### PR ladder

1. Scaffold: the control, inert. 2. Wired, with tests. Last build rung: read.

### Definition of done

- The audit log narrows to one facility's events by the chosen control, by test.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20H.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

- Search box, facility filter, or both; and whether the multi-select stays (author, at rung 1).

### Doc impact

- `spec/operator_ui_concept.md` — the Sys Admin audit log's filter (Item 3).

## Item 4 — Banners on the roster Upload cards: placement and spacing

### Opportunity

The group-clear banner (`data-group-clear-banner`) renders below the ticks, beside Upload, and sits too close to the tick line above it (walkthrough A5, author). Banners elsewhere usually sit above what they gate (`spec/ui_elements.md` §5).

### Decision

Audit every banner on the four roster Upload cards (upload problems, group clear, response loss) against §5, then make placement and spacing one rule. Rejected: *move the group-clear banner alone*, which would fix one card's instance and leave the rule unwritten.

### Blast radius (measured)

Taken 2026-11-03 at `49bb4a8c9`: the group-clear banner in 4 templates (`grep -rln data-group-clear-banner app/web/templates`); the upload-problems partial (`app/web/templates/operator/partials/_upload_problems.html`).

### PR ladder

1. The audit, as a table in this item's `Status`. 2. The fix. Own read.

### Definition of done

- Every Upload-card banner follows the one rule, checked in a browser by the author.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20H.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

None.

### Doc impact

- `spec/ui_elements.md` — §5 states where a banner sits on a card and its spacing (Item 4).

## Item 5 — What the walkthrough could not reach

### Opportunity

Two of Part A's checks cannot be done from a browser:

- **A2, no JavaScript.** With rows on the roster, Upload renders `disabled` and only the page script enables it, so "Tick only one of replace, append or merge" cannot be reached. The route's refusal is tested (`tests/integration/test_roster_append_routes.py`, `tests/integration/test_roster_merge_routes.py`). As a side effect, no upload into a non-empty roster works without JavaScript, as with the delete buttons.
- **A5, Relationships.** A group instrument whose groups depend on relationships cannot be built today: Unit of review offers reviewee tags only (`spec/instruments.md` Link 3), and refuses Group while Who is being reviewed keeps pairs by a relationship tag. So the Relationships group-clear ask (`app/services/relationships.py`) serves only instruments saved before those rules; `tests/integration/test_relationship_group_clear_asks_first.py` covers it.

### Decision

Prose: say so where each is written. Keep Upload disabled without JavaScript, as the delete buttons are (recommended; open question). Keep the Relationships ask for stored instruments, and say that is all it serves. Rejected: *render Upload enabled and let the route enforce the tick*, which would make the roster card unlike every other gated button.

### PR ladder

1. One prose PR: the walkthrough's two bullets, and the spec lines below.

### Definition of done

- The walkthrough and specs say what each path is reachable from.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20H.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

- Keep Upload disabled without JavaScript (author).

### Doc impact

- `spec/setup_pages.md` — the Upload card needs JavaScript once the roster has rows (Item 5).
- `spec/instruments.md` — the Relationships group-clear ask serves only stored pair-context boundaries (Item 5).

## Item 6 — The roster upload counts down its directory check

### Opportunity

A 1,500-row replace on production took about 56 s with nothing on the page moving (walkthrough B4, 2026-11-03; author: "a count down similar to Email checker's … e.g., 'Directory check: NN more to go'"). The upload is one POST whose directory check (`directory_checks`, `app/services/csv_imports/_identity.py`) runs on the server under one 120 s budget (`directory_accounts.BUDGET`), so the page cannot know how far it has got.

### Decision

**Count down from the page, as the Email Address Checker does**, but keep the lookups the server's. The page sends the file's addresses in batches to a lookup endpoint, four in flight, and shows "Directory check: NN more to go" where the directory line sits (`_directory_check.html`). The server **caches each outcome it fetched**, per operator and session, for minutes; the upload then reads the cache and looks up only what is missing. Without the script, the upload works as today.

Rejected: *post the page's outcomes with the file*, as the Checker does (`utilityapps/spec/email_check.md`, "From the page, counting down"). The Checker trusts them because they only describe; here an outcome binds a row to an account that sign-in then admits, so an outcome the server did not fetch must not bind. Rejected: *an estimate from the row count* (about 37 ms a lookup). Cheap, but a guess, and it says nothing when lookups slow down.

### Semantics

- A refused sign-in in a batch stops the countdown and takes 20G's path (hold the file, ask to renew), not a save.
- A cached outcome older than the cache's life is looked up again; the cache never outlives the session's lock.
- A failed batch leaves its keys uncached; the upload looks them up, as today.

### Blast radius (measured)

Taken 2026-11-03 at `d57044884`: the check (`app/services/csv_imports/_identity.py`, `directory_checks`), its budget (`app/services/directory_accounts.py`, `BUDGET`), the three Upload cards that include `app/web/templates/operator/partials/_directory_check.html` (`grep -rln _directory_check.html app/web/templates`: Reviewers, Reviewees, Observers); the Checker's page script to borrow from (`utilityapps/templates/email_check/preview.html`).

### PR ladder

After 20G rung 1, which this shares a seam with.
1. Scaffold: the count line on the Upload card, inert. 2. The lookup endpoint and its cache, with tests. 3. The page script and the upload reading the cache; a browser test. Last build rung: cumulative read.

### Definition of done

- A browser test sees the count fall to zero and the upload finish without a second lookup of any cached address.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20H.6` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

- The cache's life (author, at rung 1). Relationships has no directory line today, so it takes no count.

### Doc impact

- `spec/setup_pages.md` — the Upload card's countdown and its no-script path (Item 6).

