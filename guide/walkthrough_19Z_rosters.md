# Walkthrough — roster uploads: replace, append, merge (19Z, with 21F)

**Written:** 2026-10-31 · **For:** the author's end-to-end check of segment 19Z (append, merge, the duplicate-account warning) on top of 21F (addresses resolved through the directory) · **Plan:** `guide/segment_19Z_roster_append.md` · Retire this file once both parts are ticked; the close records the result.

The basic browser check passed (author, 2026-10-31). This walks the rest in two runs:

- **Part A, local** (`uvicorn`, fake auth). It covers the cards, the asks, the refusals and the merge rules, with the invented accounts in `cordware/graph.py` (`FAKE_USERS`). Fake auth signs in as nobody's account, so nothing here proves who a bound row admits.
- **Part B, the real tenant** (Cordware, a deployment at or after `8b5de13`). It covers what only real Graph and real sign-ins show: a roster given by sign-in name admitting its person, mail going to the directory address, lookup time on a large file. Part B's files come from the author's own list of addresses (§B1).

**Real addresses never enter this repository.** It is public. Keep Part B's files and notes in a private folder (the Cordware repository, or local disk), and record results here only as ticks and counts.

---

## Part A — local

Start from a fresh session (Add new session, no files). The directory is `FakeDirectory`, so these addresses resolve as stated:

| Address | Resolves to |
|---|---|
| `jane.tan@example.edu` | Jane Tan, by mail |
| `e0123456@example.edu` | Jane Tan, by sign-in name (UPN) |
| `arun.kumar@example.edu` | Arun Kumar (mail and UPN are one) |
| `lab01@example.edu` | Lab Account, no mail |
| `office@example.edu` | **Ambiguous**: Wei Ling's mail and Office Desk's UPN |
| `throttled@example.edu` | a lookup error (not checked) |
| anything else `@example.edu` | not found |

### A1. Replace, and the directory line

- [ ] Upload Reviewers: Jane by mail, Arun, Lab, `office@`, `throttled@`, and two not-found rows. The Setup page's line reads 2 matched by mail (Jane, Arun), 1 by sign-in name (Lab, an account with no mail), 2 not found, 1 ambiguous, 1 not checked. Checked against `cordware/graph.py` on 2026-10-31.
- [ ] Upload Reviewees the same way, plus an anonymous identifier (`STU-0001`). The identifier is not counted.
- [ ] With a roster present, the card shows both lines; with an empty roster (a new session), neither.
- [ ] Matched addresses read as pills (case kept, tooltip "Matched to a directory account"): Jane, Arun and Lab on Reviewers; not-found, ambiguous, not-checked rows and `STU-0001` stay plain. The same holds on Relationships, Assignments, Invitations, Responses and the two drill-ins.

### A2. The ticks

- [ ] Nothing ticked: Upload is disabled.
- [ ] Tick each of replace, append and merge in turn: each unticks the others, and Upload enables.
- [ ] Untick the ticked one: Upload disables again.
- [ ] Without JavaScript (DevTools, disable it): tick two, upload. The card asks "Tick only one of replace, append or merge", keeps the file, and comes back with nothing ticked.

### A3. Append

Before this, Prepare assignments and save a response or two on the reviewer surface, so there is something an append must keep.

- [ ] Append two new reviewers. They are added; every existing reviewer, assignment and response is still there; the Assignments page reads stale.
- [ ] Append a file holding an address already on the roster, in another case (`JANE.TAN@…`). The file is refused, naming the row as already on the roster; nothing is added.
- [ ] Append `e0123456@example.edu` while Jane is on the roster by mail. It is refused as a directory account already on the roster.
- [ ] Append to Relationships: a new pair is added; a pair already there refuses the file.
- [ ] The Setup page's directory line counts only the appended rows.

### A4. Merge

Use a Reviewers file with a `ReviewerTag1` column and a `Status` column.

- [ ] A row already on the roster with a new tag and name: updated. The address is unchanged.
- [ ] A row with a blank tag cell: its tag is kept.
- [ ] A row with a blank Status cell, for someone inactive: still inactive. A row with `inactive`: now inactive.
- [ ] A file with no Status column: nobody's status changes.
- [ ] A new address: added. A roster row absent from the file: kept.
- [ ] `e0123456@example.edu` named in a merge while Jane is on the roster by mail: Jane's row is updated, and still reads `jane.tan@`.
- [ ] A merge file naming both `jane.tan@` and `e0123456@`: refused, two rows for one person.
- [ ] Rename Jane through her UPN while she is also a reviewee named Jane: refused, names must match.
- [ ] The sys-admin audit log shows a `reviewer.updated` per changed row, and the import counts added / updated / unchanged.

### A5. Merge that would clear group answers

Needs a group instrument grouped by a reviewee tag, with saved answers.

- [ ] Merge Reviewees moving one person into another answered group. The card asks with the count and a "Yes, clear them" tick in a red banner; the merge tick is still ticked; the file is held.
- [ ] Tick "Yes, clear them" and Upload with no file chosen. The merge goes through; the joined group's answers are cleared, the left group's kept.
- [ ] Dismiss instead: the hold ends, nothing changes.
- [ ] The same on Relationships, with a pair-context tag.

### A6. The duplicate-account warning

- [ ] On Reviewers, with Jane by mail, use the single-row Add form to add `e0123456@example.edu`. It is allowed (another address). Validate shows one warning naming both addresses; Validate still passes.
- [ ] Deactivate one of the two: the warning goes.

---

## Part B — the real tenant

**Before starting:** the Cordware deployment carries `8b5de13` or later (21F and 19Z together); you sign in as an operator with directory access (the Setup line reads counts, not "weren't checked"); and two or three colleagues, or test accounts, can sign in as participants.

### B1. Building the test set from the address list

1. **Classify the list.** Paste the 100+ addresses into the Email Address Checker on Cordware and download its result. Each row comes back with a status: `OK` (resolved by mail), `USE_PRIMARY` (a sign-in name; the mail is given), `FOUND_NO_PRIMARY` (an account with no mail), `NOT_FOUND`, `AMBIGUOUS`, or `ERROR`.
2. **Pick cohorts** from the result. Rough sizes for a 100-address list:

   | Cohort | Size | From | Used for |
   |---|---|---|---|
   | **M** — by mail | ~40 | `OK` rows | the base rosters |
   | **U** — by sign-in name | ~30 | `USE_PRIMARY` rows; note each one's mail | base rosters given by UPN; mail to the directory address |
   | **P** — people listed both ways | 5 | from U: you know both the UPN and the mail | append / merge account matches, the duplicate warning |
   | **N** — not found | 5 | `NOT_FOUND` rows, or made-up addresses at the institution's domain | the unbound path |
   | **X** — external | 3 | addresses outside the tenant | unbound, mail as written |
   | **A** — ambiguous / no mail | any found | `AMBIGUOUS`, `FOUND_NO_PRIMARY` | the refusals and the no-mail recipient |
   | **S** — sign-in testers | 2–3 | people who will actually sign in, at least one from U | B3 |

   Include the testers (S) in the rosters by sign-in name where you can, since that is the case 21F exists for.
3. **Build the files** in a spreadsheet, one tab each, saved as UTF-8 CSV:

   | File | Rows | Purpose |
   |---|---|---|
   | `R0_reviewers.csv` | M (20) + U (15) + N (2) + X (1) | base reviewers |
   | `E0_reviewees.csv` | M (20) + U (15) + 2 anonymous IDs, with `RevieweeTag1` teams | base reviewees; some people on both rosters |
   | `O0_observers.csv` | 5 from M/U | base observers |
   | `L0_relationships.csv` | pairs among R0 × E0 | base relationships |
   | `R1_append.csv` | 10 new from M/U | a clean append |
   | `R1_append_dup.csv` | R1 + one R0 address in another case | refused: already on the roster |
   | `R1_append_acct.csv` | the **mail** of a P person who is in R0 by UPN | refused: account already on the roster |
   | `R2_merge.csv` | 15 R0 rows (tags changed, some blank cells, a `Status` column with blanks and one `inactive`) + 5 new | the merge rules |
   | `R2_merge_acct.csv` | a P person's **mail** with a changed tag, while R0 holds their UPN | updates the UPN row, keeps the UPN |
   | `R2_merge_twice.csv` | one P person by both UPN and mail | refused: one person twice |
   | `E1_merge_groups.csv` | one reviewee moved to another answered team | the group-clear ask |
   | `R_large.csv` (optional) | the whole list, padded with made-up not-found addresses to 1,500 | lookup time (B4) |

4. **Keep a key**: a private sheet listing each person's cohort, UPN and mail, so a result can be read back against it.

### B2. Upload, append, merge

Repeat A1, A3 and A4 with the B1 files. In addition:

- [ ] After R0, the Setup line's counts match the checker's classification of R0 (by mail = M rows, by sign-in name = U rows, not found = N + X).
- [ ] The pills on Reviewers count M + U; the N and X rows stay plain.
- [ ] `R1_append_acct.csv` is refused as a directory account already on the roster.
- [ ] `R2_merge_acct.csv` updates the P person's UPN row; it still reads the UPN.
- [ ] Validate after adding a P person's mail by the Add form, while R0 holds their UPN: one duplicate-account warning.

### B3. Signing in

- [ ] A tester listed only by **sign-in name** signs in and reaches their reviewer surface (the rows' accounts admit them).
- [ ] A tester listed by mail reaches theirs too.
- [ ] A tester on the roster as a not-found row (made up) cannot reach anything — expected.
- [ ] Their `/me` page lists exactly the sessions they are on.

### B4. Mail and timing

- [ ] An invitation to a reviewer listed by sign-in name arrives at their mail address (the Outbox shows the directory mail, not the UPN).
- [ ] (Optional) `R_large.csv` as a replace: note the time to the redirect and the Setup line's "not checked" count. Under about 0.25 s a lookup, 1,500 rows finish within the 120-second budget; beyond it the tail reads "not checked" and the upload still succeeds.

### B5. Recording

Tick the rows here and add one line per part: the date, the deployment's commit, and anything that differed. No addresses, names or account IDs, only counts. Anything that needs a fix becomes a 19X item or a 19Z follow-up before 19Z closes.
