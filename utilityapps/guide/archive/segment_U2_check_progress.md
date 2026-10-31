# Segment U2 — The Email Address Checker counts down

**Opened:** 2026-10-31 · **Closed:** 2026-10-31 · **Theme:** the preview reads in the order its numbers add up, and *Check addresses* counts down as addresses are checked · **Related:** `utilityapps/spec/email_check.md` (the contract), `utilityapps/guide/archive/segment_U1_email_checker.md` (the build)

## Opportunity

The checker's first real-tenant run went through on 2026-10-31, the day of Cordware's interim release: a 158-row file previewed and checked. The author asked for two refinements.

- **The preview's counts don't add up as listed.** *Addresses to check* sits second and counts every row with an address, repeats included. Read top to bottom, the four numbers suggest a subtraction they don't support.
- **Nothing moves while the check runs.** *Check addresses* is one POST that answers only when every lookup is done: four at a time, inside a 120 s budget (`check.BUDGET`). On a file of a few hundred addresses the page sits blank for most of that time. A file too large for the budget ends in `ERROR` (`timeout`) rows, whatever the directory would have said.

## Decision

**Reorder the preview, and run the check from the page in batches** (author, 2026-10-31).

- **The preview, in order:** *Rows*, *Blank or not an address: kept, not checked*, *Repeats of an address already in the file: checked once*, *Addresses to check*. The last becomes the **distinct** addresses, the lookups the check will make, so the four now read as a subtraction: rows, less blanks, less repeats.
- **The countdown.**
  - A script on the preview page takes over *Check addresses*.
  - It sends the distinct addresses in small batches to a new JSON endpoint, `POST /email-check/lookup`, which looks each batch up and returns the outcomes.
  - After each batch, *Addresses to check* drops by the number just checked.
  - When the last batch is back, the page posts the file, the column and the collected outcomes to `/check`. The result page is built from them, with no second lookup.
- **Without the script,** *Check addresses* posts to `/check` exactly as now.

**Rejected:**
- *Streaming one response* with progress updates. Application Gateway and App Service may buffer it, so the countdown could arrive all at once in production. The 120 s budget would also stay.
- *A job kept on the server and polled.* It breaks "nothing is kept between steps", and on more than one instance a poll can land where the job isn't.

## Semantics

- **`POST /email-check/lookup`**:
  - Super-admin only, like every checker route.
  - Body: JSON `{"keys": [...]}`, `Content-Type: application/json` required. A plain form cannot send that cross-site without a preflight.
  - Takes 1–`BATCH_MAX` keys. Each must already be a lookup key (`csvio.lookup_key` returns it unchanged). Anything else is a `400`.
  - Answers `{"outcomes": {key: outcome}}`, `no-store`. Each batch runs under its own short budget.
  - With no delegated token it answers a JSON `503`, and the page shows the preview's directory alert.
- **A refused sign-in stops the run.** The first `unauthorized` or `forbidden` outcome stops the script sending batches. Every key not yet sent becomes `ERROR` with that kind, as `look_up_all` does in one request today.
- **`POST /email-check/check` with outcomes**:
  - It accepts an `outcomes` field (JSON) beside the carried file.
  - Outcomes are validated against the file: keys must be the file's keys, statuses in `STATUSES`, and fields bounded strings. Anything else is a `400`. A key the file has but the outcomes lack becomes `ERROR` (`incomplete`).
  - Present, the result is built from them. Absent, `/check` looks up as now, budget and all.
  - The carried-request limit rises to cover the outcomes field.
- **Trust.** The outcomes come from the super-admin's own browser and go only into the super-admin's own download. A forged outcome can only mislead its forger, so validation checks shape, not truth.
- **The log record** (`email_check.completed`) is written by `/check` in both paths, with the same counts.

## Judgment calls — decided

- **Batches run one at a time, five keys each** (`BATCH_MAX` 25 caps a request). That is close to today's four in flight, so Graph sees the same load. *Changed at build (2026-10-31):* one key per request, four in flight, so the count drops by one per address as asked, with the same load on Graph.
- **The script lives inline in `preview.html`,** as RRW's progressive-enhancement scripts do. No asset pipeline.
- **The batch budget is 60 s,** far above a single-key request. It bounds a stuck request well under the front end's limit.

## Blast radius (measured)

Taken 2026-10-31 at `92f4ed2`.

| What | Count | Command |
|---|---|---|
| Checker route decorators | 5 (`GET /`, `POST /preview`, `POST /check`, and the two `GET` redirects) | `grep -n "@router" utilityapps/email_check/routes.py` |
| Preview template rows | 4, reordered | `grep -c "<tr>" utilityapps/templates/email_check/preview.html` |
| Checker test files | 4 | `ls utilityapps/tests/test_email_check_*.py` |
| Spec sections touched | 3 ("Preview", "Check", "Result") | `grep -n "^## " utilityapps/spec/email_check.md` |

## Status

**Closed 2026-10-31, in three PRs:** plan `#3420`, rungs 2–3 together in `#3421` (rung 3 was built while rung 2 waited on CI), and this close.

Decision changed at build: one key per request, four in flight, rather than batches of five, so the count drops by one per address as asked (Judgment calls).

Reads:
- **`diff-reviewer`**, once, on `1a6cafd..56fecc1`'s first two commits. Nothing blocking; nine points. Fixed in `#3421`: an unpreviewed column, a network error dropping a refused sign-in's kind, any 503 taken as `no_graph`, carried error kinds unchecked before the log, the `incomplete` note, back/forward-cache restore, plan and spec wording. Kept as specified: one failed request stops the page.
- **Codex**, two findings, both fixed in `#3421`: the column could change mid-run, and the `no_graph` fallback did not post the column.
- **`spec-writer`** at the close: two refusals added to the spec's lists. One flag left on purpose: over-limit messages name the file's 1024 KiB limit even when the carried request, which also holds the outcomes, is what was too large. The file's own limit is what a user can act on.

Seen in production on 2026-10-31 (author): the countdown works on the real tenant, after Cordware imported and deployed it. Still unseen: Easy Auth's answer to a `fetch` once the session has expired.

## PR ladder

1. **This plan.** Prose only.
2. **The reorder.** The preview's rows in the new order, and *Addresses to check* as distinct keys (`len(Preview.keys)`). Tests and the spec's "Preview" table. Must not touch the check.
3. **The countdown.** Lands `/lookup`, `/check` with outcomes, the preview script and their tests. Must not change the no-script path. Last build rung, so `diff-reviewer` reads 2–3's cumulative diff.
4. **Close.** `spec-writer` on `email_check.md`, a browser check for the author, archive.

## Definition of done

- The preview lists the four counts in the order above, and *Addresses to check* = rows − blanks − repeats (test).
- With the script, a check of N distinct addresses makes N `/lookup` requests and one `/check` (read from the script; the browser check confirms). The result built from the collected outcomes equals the no-script path's for the same directory (test).
- `/lookup` refuses a non-super-admin, a non-JSON body, an empty or oversized batch, and a key that isn't a lookup key (tests).
- `/check` refuses outcomes that don't fit the file, and marks missing keys `ERROR` (`incomplete`) (tests).
- The author sees the countdown move on a real file.
- `utilityapps/spec/email_check.md` "Preview" and "Check" say what shipped.
- Plan moved to `utilityapps/guide/archive/`.

## Open questions

- None. The batch size can be tuned after the author's first runs on the real tenant.

## Out of scope

- Alias lookup (the spec's phase 2).
- Cancelling a running check. Leaving the page stops it, and nothing is kept.

## Doc impact

- `utilityapps/spec/email_check.md` — "Preview": the order and the distinct count (rung 2). "Check": the batched path, `/lookup`, `/check` with outcomes, the `incomplete` kind (rung 3).
