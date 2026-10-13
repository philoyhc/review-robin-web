# Quick Setup browser checks: files and run order

The upload files for three sections of `guide/things_to_check_in_browser.md`:

- "Quick Setup names the kind of problem"
- "Quick Setup checks files together and saves all or none"
- "Quick Setup shows Observers, and an upload turns its tab on"

**Delete this folder in the same change that deletes the last of those
sections.**

Every step below was driven through the app with the test client on
2026-10-13, and each gave the result shown. What the client can't see is
the page itself: the banner layout, the tabs and the Session details
toggle. Those are the parts to check by eye.

Run it locally (`uvicorn`, fake auth), in order. Steps 1–9 use one
session; steps 10 and 11 each create their own.

**Submitting from Session Home.** On Session Home's Quick Setup card,
choose each listed file in its slot. If the card shows the replacement
box, tick it. Then press Submit.

## Session A

Create a session named `QS check`, with no files and both the
Relationships and Observers boxes unticked. Open its Session Home.

| # | Upload | Expect | Ticks |
|---|---|---|---|
| 1 | Reviewers `01_reviewers_baseline.csv` + Reviewees `02_reviewees_baseline.csv` | No banner. Both rosters have "Bob Smith" (bob@example.edu). | — (setup) |
| 2 | Reviewers `03_reviewers_problems.csv` | Banner: "Could not import reviewers. The file has these problems; the Reviewers Setup page shows which rows:" over "ReviewerEmail is blank (2 rows)" and "Status is not active or inactive (1 row)". No row is named. | *Names the kind*: Roster |
| 3 | Reviewers `04_reviewers_missing_column.csv` | The banner's one line is "Missing required column: ReviewerEmail". | *Names the kind*: Missing column |
| 4 | Reviewers `05_reviewers_robert.csv` **alone** | Refused: "ReviewerEmail is already used under a different name in another roster (1 row)". The rosters still read Bob. | — (extra: the rule for one file) |
| 5 | Reviewers `05_reviewers_robert.csv` + Reviewees `06_reviewees_robert.csv` | No banner. Both rosters read "Robert Smith". | *All or none*: A rename across rosters |
| 6 | Reviewers `05_reviewers_robert.csv` + Reviewees `02_reviewees_baseline.csv` | The Reviewers banner reads "ReviewerEmail is used under a different name in the uploaded Reviewees file (1 row)". Neither roster changed. | *All or none*: Two uploads that disagree |
| 7 | Reviewers `07_reviewers_new.csv` + Reviewees `08_reviewees_blank_email.csv` | Reviewees banner: "RevieweeEmail is blank (1 row)". The Reviewers page still lists Alice Chan, Carmen Diaz and Robert Smith, not Hana or Ivan. | *All or none*: A late refusal saves nothing |
| 8 | Look at the card before uploading | Five slots, with Observers between Relationships and Session settings. | *Observers*: The slot is there |
| 9 | Observers `09_observers.csv` | No banner. Setup now has an Observers tab. Session details shows the observers toggle on and held there. | *Observers*: Observers turn on |
| 10 | Reviewers `01_reviewers_baseline.csv` + Reviewees `02_reviewees_baseline.csv` + Relationships `10_relationships.csv` | No banner. A Relationships tab appears, listing 4 relationships. | *Observers*: Relationships turn on |

Step 10 runs on Session A, whose relationships are still off at that
point. It also renames "Robert" back to "Bob".

## Create checks

| # | On New session | Expect | Ticks |
|---|---|---|---|
| 11 | Name `QS create`, tag `qs-check`. Stage Reviewers `07_reviewers_new.csv` + Reviewees `08_reviewees_blank_email.csv`, then Create | You land on its Session Home with the Reviewees banner. The session has the tag `qs-check`, and its Reviewers roster is empty. | *All or none*: Create |
| 12 | Name `QS obs`, Observers box **unticked**. Stage Observers `09_observers.csv`, then Create | No banner. The new session has an Observers tab. | *Observers*: Create |

## The files

| File | Content |
|---|---|
| `01_reviewers_baseline.csv` | Bob Smith, Alice Chan, Carmen Diaz |
| `02_reviewees_baseline.csv` | Bob Smith, Dev Patel, Erin Walsh |
| `03_reviewers_problems.csv` | 1 good row, 2 blank emails, 1 Status `maybe` |
| `04_reviewers_missing_column.csv` | `Email` where `ReviewerEmail` should be |
| `05_reviewers_robert.csv` | 01, with Bob renamed Robert |
| `06_reviewees_robert.csv` | 02, with Bob renamed Robert |
| `07_reviewers_new.csv` | Hana Kim, Ivan Petrov: a valid file, different people |
| `08_reviewees_blank_email.csv` | Jade Lin, plus Kai Moore with no email |
| `09_observers.csv` | Lena Ortiz |
| `10_relationships.csv` | 4 pairs over 01 and 02, none of them a self-review |
