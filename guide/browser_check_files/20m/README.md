# 20M: where display fields sit

Files and a run order for the section of
`guide/things_to_check_in_browser.md` headed 20M. Run locally
(`uvicorn`, fake auth as `operator@example.edu`), from the repository
root.

| File | What it is |
|---|---|
| `reviewers.csv` | You, `operator@example.edu`, as the one reviewer. |
| `reviewees.csv` | Eight reviewees tagged Tutor / Group / Team. TW01 (tutor Zoe Tan) has Team 1, Team 2 and Hana Ito with no Team; TW45 (tutor Ahmed Shah) has Team 1 and Team 2. `ProfileLink` is a web link for five, `Room 4B` / `Room 2A` (not links) for two, blank for two. |

## Run order

1. **Create a session** (`20m-check`) with both files staged in Quick
   Setup.
2. **Instrument 1, individual.** Band 1: Who does the review and Who
   is being reviewed both *All*. Band 3: select Name, Email, Profile,
   Tutor, Group, Team. Add one response field. Save. Run the *Profile*
   and *Individual layouts* rows on the Instruments page.
3. **Instrument 2, group-scoped.** Add a second instrument. Band 1:
   *All* and *All*, Unit of review grouped by Group AND Team. Band 3:
   select Tutor, Group, Team in that order. Add one response field.
   Save. Run the *Group layouts* rows on the Instruments page.
4. **Prepare and start** the session, then open your review page for
   it (`/reviewrobin/me/sessions/<id>/1`). Run the reviewer-surface
   rows. Edits from here on reopen the instruments: unlock, change,
   Save, prepare and start again, and reload the review page.

Delete this folder in the change that ticks the last of those rows.
