# Round 3: the 2026-10-22 bug fixes

Files and a run order for the sections of
`guide/things_to_check_in_browser.md` headed #3235, #3236, #3237 and
#3238. Run locally (`uvicorn`, fake auth), from the repository root.

| File | What it is |
|---|---|
| `reviewers.csv` | Rae and Sam. |
| `reviewees.csv` | Rae and Dan untagged, Sam and Carol in Team A, Fay in Team B (`RevieweeTag1`). |
| `settings_card_reads.csv` | One group instrument grouped by reviewee tag 1. Who is being reviewed holds one rule, Reviewee's tag 2 IS NOT `0`, with the `0` stored as a number; the file's `band1_touched_links` leaves Link 2 out. |
| `settings_refused.csv` | The same, but Who does the review uses IS THE SAME AS and the rule set's combinator is `ANY_OF`. |
| `empty.csv` | An empty file. |
| `edit_rule_set.py` | Hand-edits a session's stored rule (its docstring says how). |

## Run order

1. **Session A** (`round3-a`): Create, with `reviewers.csv`,
   `reviewees.csv` and `settings_card_reads.csv` staged in Quick Setup.
   Run #3237's first three rows, then Prepare session and its fourth.
2. On Session A's Session Home, upload `settings_refused.csv` in Quick
   Setup's Settings slot: #3237's fifth row.
3. Run `edit_rule_set.py round3-a disable`: #3237's last row.
4. **Session B** (`round3-b`): Create as Session A. Run
   `edit_rule_set.py round3-b unloadable`, then #3238's rows.
5. Session B's Reviewers page: #3236's row.
6. The lobby: #3235's cookie rows.
7. Archive Session B (Extract data page, Archive card), then #3235's
   template rows on its Email Template page.

Delete this folder in the change that ticks the last of those rows.
