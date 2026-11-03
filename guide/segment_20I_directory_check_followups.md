# Segment 20I — Directory check follow-ups and refinements

**Opened:** 2026-11-03, at the author's request, from the browser checks of 20G's banners and 20H Item 6's countdown (locally and on production, 2026-11-03) · **Theme:** what those checks found, one item each; open for further refinements, as 20C was · **Related:** `guide/archive/segment_20H_walkthrough_19Z_followups.md`, `spec/setup_pages.md` ("The Upload card's directory-check line", "… countdown", "… banners")

Items close independently. The segment closes when the author says no more are coming.

**Ruled, not planned** (author, 2026-11-03): a not-checked count with a cause ("the directory refused this account's access", "the directory was busy") stays on the directory-check line, with no banner. The rows saved, so nothing is wrong with the upload; the cure is Item 1.

## Item 1 — Check a roster's unmatched addresses again, on demand

### Opportunity

A row saved without a directory account (not found, ambiguous, or not checked because the directory was busy, timed out or refused) stays unbound until the roster is uploaded again. In the checks, a busy directory left 2 rows unchecked and a refused account left 251. An operator who believes the directory is back has no way to retry short of re-uploading the file (author, 2026-11-03: "a routine, that can be triggered manually, to check through all the 'unverified' address rows").

### Decision

**A "Check again" action on the Upload card, beside the directory-check line**, on Reviewers, Reviewees and Observers. The line already says how many addresses were not checked and why, so the action sits where the operator reads that.

- **What it checks:** every active row on that roster with an address and no `directory_object_id`, whatever import or form added it, not only the last import's.
- **How:** the page counts it down as an upload does (20H Item 6: `directory-keys`, then `directory-lookup`), and a POST binds each row whose answer the server fetched and kept; it never binds from the page's say-so. Without the script, the POST looks the addresses up on the server, within the budget.
- **What it changes:** a row found binds, as an upload binds it (`directory_accounts.rebind`); not found and ambiguous stay unbound; the line is replaced by this check's counts; an audit event per roster with the counts.

Rejected: *a button on the roster table's toolbar.* The table is about rows, the Upload card about the directory, and the line it answers is on the card. Rejected: *a sweep on a clock* (14E). The operator knows when the directory is back; a clock would retry blindly.

### Semantics

- **Shown** when the roster has at least one unbound row with an address, labeled with the count ("Check 251 unmatched addresses again").
- **States:** wherever the single-row edit is allowed, since binding is what an edit's address change does. Open question for activated sessions.
- **A row that now resolves to an account another row holds** stays unbound, and the line counts it; 20H Item 1's rule, applied to a recheck.
- **An expired sign-in** takes the renew banner (20G), as an upload does.

### Blast radius (measured)

Taken 2026-11-03 at `215106150`: the directory line's partial (`app/web/templates/operator/partials/_directory_check.html`, one includer each on the three roster pages: `grep -rln _directory_check.html app/web/templates`); the countdown's partial (`partials/_directory_countdown.html`) and endpoints (`app/web/routes_operator/_directory.py`); the binding (`directory_accounts.rebind`, `app/services/directory_accounts.py`) and each roster's `rebind_resolve` (`app/services/reviewers.py`, `reviewees.py`, `observers.py`); the kept answers (`directory_lookups.known_for`).

### PR ladder

1. Scaffold: the action under the line, labeled with the count, inert. 2. The service and route, with the server-side lookup and its audit event; tests. 3. The countdown driving it; a browser test. Last build rung: cumulative read.

### Definition of done

- On each of the three rosters, the action binds every unbound row the directory now finds and leaves the rest, by test; the line shows the recheck's counts.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20I.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 20I entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

- In an activated session, may the operator bind rows? Binding admits a person by account at sign-in, which the address already does; proposed yes. Author, at rung 1.
- Label: "Check again" or "Check unmatched addresses". Author, at the scaffold.

### Doc impact

- `spec/setup_pages.md` — "The Upload card's directory-check line": the recheck action, when it shows, what it binds (Item 1).
- `spec/architecture.md` — the recheck's audit event in the detail schema (Item 1).

## Item 2 — The countdown asks in batches

### Opportunity

The countdown of a 1,500-row upload took about 85 s on production and 18 s locally, against about 56 s for the server-side check in 19Z's walkthrough (Part B). The page sends one key per request, four in flight (`partials/_directory_countdown.html`, `body: JSON.stringify({keys: [key]})`), so each address pays a round trip through the gateway; `directory-lookup` already takes up to 25 (`LOOKUP_BATCH_MAX`, `app/web/routes_operator/_directory.py`).

### Decision

Send batches of 10 keys, four in flight, and drop the count by each batch's size. Rejected: *25 a batch*, which makes the count move in jumps of 25 on a small roster and holds a batch on its slowest key.

### PR ladder

1. One PR: the batch size in the script, the spec's countdown section, a browser test that the count falls and finishes. Own read.

### Definition of done

- A 1,500-row upload on production counts down in about the server-side time or less (the author's browser check).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20I.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 20I entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

None.

### Doc impact

- `spec/setup_pages.md` — "The Upload card's directory-check countdown": batches of 10 (Item 2).

## Item 3 — Even space around the Upload card's banners

### Opportunity

The first banner sits 12 px under the intro (the intro's `.form-help` margin) and the last 16 px above what follows (`.banner` margin), as `spec/setup_pages.md` "The Upload card's banners" says; it reads lopsided (author, 2026-11-03).

### Decision

16 px on both sides: the intro's margin when a banner follows it. Rejected: *12 px both sides*, which crowds the banner's own padding.

### PR ladder

1. One PR: the rule in `base.html`, the spec's sentence, `tests/unit/test_upload_card_banners.py` if it pins the gap. Own read.

### Definition of done

- The gap above the first banner equals the gap below the last (the author's browser check).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20I.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 20I entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

None.

### Doc impact

- `spec/setup_pages.md` — "The Upload card's banners": 16 px above the first banner (Item 3).
