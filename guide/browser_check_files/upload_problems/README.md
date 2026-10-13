# Upload problems: files and run order

For "The Setup pages' upload cards report problems as Quick Setup does"
in `guide/things_to_check_in_browser.md` (quick_setup_update Item 3).
Delete this folder with that section.

Run locally (`uvicorn`, fake auth) on a new session, `UP check`, code
`up-check`, with Relationships and Observers ticked. On each Setup page,
open the upload card (Unlock if asked), choose the file, and Upload.

| # | Page and file | Expect |
|---|---|---|
| 1 | Reviewers, `01_reviewers_problems.csv` | A red banner inside the upload card: "Could not import reviewers. The file has these problems:" over "ReviewerEmail is blank (2 rows)" and "Status is not active or inactive (1 row)". No "Row 2", no Issues box, no ERROR tags. |
| 2 | Reviewers, `02_reviewers_hundred_blank.csv` | One line: "ReviewerEmail is blank (100 rows)". |
| 3 | Reviewees, `03_reviewees_blank.csv` | "Could not import reviewees…" over "RevieweeEmail is blank (2 rows)". |
| 4 | Relationships, `04_relationships_unknown.csv` | "ReviewerEmail is not on the Reviewers roster (import reviewers first) (1 row)". |
| 5 | Observers, `05_observers_blank.csv` | "ObserverEmail is blank (1 row)". |
| 6 | Session Home, Quick Setup, Reviewers slot, `01_reviewers_problems.csv`, Submit | The same two lines under "Could not import reviewers. The file has these problems:", with no mention of a Setup page. |
| 7 | Validate | Unchanged: its issue list still shows ERROR tags and rows where it did. |
