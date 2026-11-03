# Segment 20I — Directory check follow-ups and refinements

**Opened:** 2026-11-03, at the author's request, from the browser checks of 20G's banners and 20H Item 6's countdown (locally and on production, 2026-11-03) · **Theme:** what those checks found, one item each; open for further refinements, as 20C was · **Related:** `guide/archive/segment_20H_walkthrough_19Z_followups.md`, `spec/setup_pages.md` ("The Upload card's directory-check line", "… countdown", "… banners")

Items close independently. The segment closes when the author says no more are coming.

**Ruled, not planned** (author, 2026-11-03): a not-checked count with a cause ("the directory refused this account's access", "the directory was busy") stays on the directory-check line, with no banner. The rows saved, so nothing is wrong with the upload; the cure is Item 1.

## Item 1 — Check a roster's unmatched addresses again, on demand

### Opportunity

A row saved without a directory account (not found, ambiguous, or not checked because the directory was busy, timed out or refused) stays unbound until the roster is uploaded again. In the checks, a busy directory left 2 rows unchecked and a refused account left 251. An operator who believes the directory is back has no way to retry short of re-uploading the file (author, 2026-11-03: "a routine, that can be triggered manually, to check through all the 'unverified' address rows").

### Decision

**A "Recheck N unmatched" button in the Upload card's actions row, left of Upload**, on Reviewers, Reviewees and Observers, with the **directory-check line and the countdown moved below the actions** (author, 2026-11-03). The card then reads in the order it is used: banners (stop and decide), the file and the ticks, the buttons, then what the last check found. The button is Secondary, as Upload is, and names the saved rows it acts on so it does not read as "retry the upload"; it ignores any chosen file and the ticks.

This **reverses 20G's placement** of the line ("under the card's banners and above the form", `spec/setup_pages.md`), back below the button as it sat before 20G; the banners stay in their stack under the intro.

- **What it checks:** every active row on that roster with an address and no `directory_object_id`, whatever import or form added it, not only the last import's.
- **How:** the page counts it down as an upload does (20H Item 6: `directory-keys`, then `directory-lookup`), and a POST binds each row whose answer the server fetched and kept; it never binds from the page's say-so. Without the script, the POST looks the addresses up on the server, within the budget.
- **What it changes:** a row found binds, as an upload binds it (`directory_accounts.columns`); not found and ambiguous stay unbound; the line is replaced by this check's counts; an audit event per roster with the counts.

Rejected: *the button beside the line, above the form* (this plan's first draft): the line read as a header for the controls rather than their result. Rejected: *a button on the roster table's toolbar.* The table is about rows, the Upload card about the directory, and the line it answers is on the card. Rejected: *a sweep on a clock* (14E). The operator knows when the directory is back; a clock would retry blindly.

### Semantics

- **Shown** when the roster has at least one active unbound row with an address, labeled with the count, "Recheck 251 unmatched" (author, 2026-11-03); absent otherwise, and the actions row is Upload alone.
- **States:** any but archived, activated sessions included (author, 2026-11-03: binding admits by account what the address already admits), though Reviewers' and Reviewees' single-row edits stop at activation.
- **A row that now resolves to an account another row holds** stays unbound, and the line counts it; 20H Item 1's rule, applied to a recheck.
- **An expired sign-in** takes the renew banner (20G), as an upload does.

### Blast radius (measured)

Taken 2026-11-03 at `215106150`: the directory line's partial (`app/web/templates/operator/partials/_directory_check.html`, one includer each on the three roster pages: `grep -rln _directory_check.html app/web/templates`); the countdown's partial (`partials/_directory_countdown.html`) and endpoints (`app/web/routes_operator/_directory.py`); the binding (`directory_accounts.rebind`, `app/services/directory_accounts.py`) and each roster's `rebind_resolve` (`app/services/reviewers.py`, `reviewees.py`, `observers.py`); the kept answers (`directory_lookups.known_for`).

### PR ladder

1. Scaffold: the line and the countdown moved below the actions row, and the button left of Upload, labeled with the count, inert; `tests/unit/test_upload_card_banners.py` and the card's order tests follow. 2. The service and route, with the server-side lookup and its audit event; tests. 3. The countdown driving it; a browser test. Last build rung: cumulative read.

### Definition of done

- On each of the three rosters, the action binds every unbound row the directory now finds and leaves the rest, by test; the line shows the recheck's counts.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20I.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 20I entry updated to drop this item; the entry itself goes only when the segment closes

### Status

**Closed 2026-11-03.** Intended vs done: as decided, in #3557 (scaffold) and #3558 (the recheck and its countdown; rung 3 joined rung 2). Beyond the plan: a found row on an account another row holds stays unbound, counted `directory_held`; a recheck reads only answers its own countdown fetched (`since`), and without the script asks for every address; a recheck with nothing unmatched writes no event; a binding recomputes self-review. Reviewers and Reviewees show the card only while editable, so an activated session's recheck is reachable on Observers alone; surfacing it elsewhere is the author's call. Reads: one cold read of the cumulative diff from `e554cc7e2` (five defects and four weak tests, all fixed) and Codex (one: the self-review recompute, fixed). `spec-writer` aligned `spec/setup_pages.md` and `spec/architecture.md`.

### Open questions

None; both answered at rung 1.

### Doc impact

- `spec/setup_pages.md` — "The Upload card's directory-check line" and "… countdown": both below the actions row (reversing 20G's placement); the recheck button left of Upload, when it shows, what it binds. "The Upload card's banners": the stack's order no longer has the line under it (Item 1).
- `spec/architecture.md` — the recheck's audit event in the detail schema (Item 1).

## Item 2 — The countdown asks in batches

### Opportunity

The countdown of a 1,500-row upload took about 85 s on production and 18 s locally, against about 56 s for the server-side check in 19Z's walkthrough (Part B). The page sends one key per request, four in flight (`partials/_directory_countdown.html`, `body: JSON.stringify({keys: [key]})`), so each address pays a round trip through the gateway; `directory-lookup` already takes up to 25 (`LOOKUP_BATCH_MAX`, `app/web/routes_operator/_directory.py`).

### Decision

Send batches of 10 keys and drop the count by each batch's size (two in flight as built; see Status). Rejected: *25 a batch*, which makes the count move in jumps of 25 on a small roster and holds a batch on its slowest key.

### PR ladder

1. One PR: the batch size in the script, the spec's countdown section, a browser test that the count falls and finishes. Own read.

### Definition of done

- A 1,500-row upload on production counts down in about the server-side time or less (the author's browser check).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20I.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 20I entry updated to drop this item; the entry itself goes only when the segment closes

### Status

**Closed 2026-11-03.** Intended vs done: as decided. `partials/_directory_countdown.html` sends batches of 10 (`batch`), the count falling by each batch's size; one failed key in a batch stops the count, as one failed lookup did. **Two in flight, not the decided four:** the server looks each batch up four at a time, so four batches would run sixteen directory calls at once against the Email Address Checker's four; two keeps it at eight (the item's cold read). Browser tests: 25 addresses go as 10, 10 and 5; a timing-out directory, or one failed middle key, stops within the first two batches. Reads: one cold read (the fan-out, a stale spec sentence, a test that checked only whole-batch failures; all fixed). The production timing is the author's check. `spec/setup_pages.md` "… countdown" updated in the same PR.

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

### Status

**Closed 2026-11-03.** Intended vs done: as decided, as a top margin rather than the intro's bottom margin: `base.html` gives `.form-help + .banner` a 16px top margin, which collapses with the intro's 12px. Any page whose intro is followed by a banner takes it, not only the Upload card. `tests/browser/test_upload_banner_spacing.py` measures 16px above the first banner and below the last (it fails without the rule). `spec/setup_pages.md` "The Upload card's banners" updated.

### Open questions

None.

### Doc impact

- `spec/setup_pages.md` — "The Upload card's banners": 16 px above the first banner (Item 3).
