# Apply Desk — removed help lines

A running tab of the explanatory lines taken off Apply Desk's pages. They come off so the pages read lean, but some carried something an operator or a participant may still need. The author will decide later how such help is shown: a help panel, a tooltip, an *About this page*, or the Guide.

**Adding to it.** Any change that removes or shortens help text on a page adds its rows here in the same PR. Each row gives:
- where the text sat (the template, and the control or card);
- the text, verbatim;
- what it told the reader;
- the PR.

Remove a row only when its point is shown again somewhere, and say where.

## Carried information (decide how to show)

| Where | Removed text | What it told the reader | PR |
|---|---|---|---|
| `operator/_details.html`, *Who may apply*: Invitation only | "Invitation only hides the exercise from everyone not on its list, direct links included." | Invitation only also blocks direct links, not just the listing. Shown nowhere else. | #4102 |
| `operator/_details.html`, *Review*: Blind review | "On, evaluators' dossiers redact the applicant's name and identifiers, and Review Robin receives each Dossier ID in place of its application ID (ruling 43)." | What blind review redacts, and that Review Robin sees Dossier IDs, not application IDs. The edit-mode hint still mentions the redaction; the Dossier ID swap is shown nowhere else. | #4102 |
| `operator/_panels.html`, intro | "Apply Desk keeps every panel and what each person may view; to Review Robin they are ordinary reviewers." | Panels and their visibility live in Apply Desk; Review Robin sees plain reviewers. | #4102 |
| `operator/_extract.html`, intro | "…a card per file; Dossiers and each gate's page show the data itself." | Extract only exports; the data is read on Dossiers and the gate pages. | #4102 |
| `operator/_extract.html`, *Alias key* card | "…Keep it apart from the files above; downloads will be logged from AD2." | Alias-key downloads are to be logged once stored. | #4102 |
| `operator/_evaluations.html`, intro | "Each gate's mode, counts and load; its pairs, 200 at a time, on its page." (now "Each gate's pairs are on its page.") | Evaluations shows each gate's mode, counts and load, and the gate page shows its pairs 200 at a time. | #4102 |
| `operator/_evaluations.html`, the dossier link line | "…each dossier with a link to its page here, which is what evaluators open from Review Robin, and its Dossier ID in place of its application ID (ruling 43)." (now "…which evaluators open from Review Robin, and by its Dossier ID.") | The Dossier ID replaces the application ID in what Review Robin gets. | #4102 |
| `operator/form_preview.html` | "Nothing typed here is kept." | A preview keeps nothing typed. The banner above still says so. | #4102 |
| `operator/_emails.html`, kept-in-tab note | "A template you save is kept in this tab: nothing is saved until AD2, and until then the status row's Emails, Home and Dossiers' Released read the sample's templates." (now "…kept in this tab only: the status row's Emails, Home and Dossiers' Released still read the sample's templates.") | Saving waits for the store (AD2). | #4102 |

## Citations only (nothing lost)

#4102 also cut citations from text that otherwise stays, so these need no new home:
- ruling numbers: rulings 9, 29, 43 and 57;
- segment and stage names: AD2, AD4, AD6 and AD7, as "until AD2", "comes with AD4" and so on;
- the gate label "(G2)".

Where a control was waiting on a stage, its title now says "… is not built yet". The full list, old text and new, is in #4102's description, and in `git show 0d2e01282 -- applydesk/templates`.
