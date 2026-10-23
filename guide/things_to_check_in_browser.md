# Things to check in a browser

Browser checks owed on merged changes that the test suite cannot settle:
layout, in-browser behavior and what a page shows. Every PR that owes one
adds a section here. Run them locally (`uvicorn`, fake auth). Tick a row
when it is checked; once every row in a section is ticked, delete the
section (git history keeps it), so this file lists only what is owed. A
section may point to upload files under `guide/browser_check_files/`;
delete them once no remaining section points to them.

**Some rows need more than a local run:** an Azure deployment (#2720,
P5) or the Rehydrate round trip (D28).

## Email dates in the session's zone (#2720)

- [ ] **The submitted time does too.** Preview the responses-received
  email for a reviewer who has submitted; `$submitted_at` reads in the
  session's zone. *Needs an Azure deployment; not checkable locally (author,
  2026-10-13).*

## Zip all follows the other cards (D28)

- [ ] **Rehydrate still takes it.** Give an instrument the short label
  `responses`, then download Extract Setup's Zip all and this Zip all.
  Rehydrate both zips on the lobby: it accepts them.

## Sign-in keeps its row when the email changes (P5)

These need real Easy Auth claims, so they are checks for an Azure
deployment, not a local run.

- [ ] **A changed email keeps the account.** Sign in as an operator, have
  the tenant change that account's primary email, and sign in again:
  the same sessions, flags and SMTP settings are there, and the
  sys-admin audit log shows `workspace.user_email_changed`.
- [ ] **An invite for the new address folds in.** Before that sign-in,
  invite the new address as an operator on Accounts Management: after
  it, there is one account, an operator, and the log shows
  `workspace.user_absorbed`.
- [ ] **An invited user's first sign-in binds them.** Invite a new
  address, then sign in as it: the log shows
  `workspace.user_principal_recorded`.

## Archived templates and the sort cookie (#3235)

Run order and files: `guide/browser_check_files/round_3/`.

- [ ] **An archived session's templates are read-only.** On an archived
  session's Email Template page every field is disabled, there are no
  Reset buttons and Save stays disabled, under the line "This session
  is archived, so its email templates can no longer be edited." The
  Responses received chip is disabled too.
- [ ] **A root-path sort cookie is expired.** On the lobby, in the
  browser console, run
  `document.cookie = "rrw-sort-lobby=" + encodeURIComponent(JSON.stringify([{key: "name", dir: "desc"}])) + "; Path=/"`
  and reload: the lobby is in its own order (newest first, or the sort
  you last chose), not Name descending, and `document.cookie` holds one
  `rrw-sort-lobby`.
- [ ] **A sort still sticks.** Sort the lobby by Code, reload: still by
  Code.

## A chosen empty file is read (#3236)

- [ ] **The held file doesn't stand in.** On a Reviewers page that has
  reviewers, upload `reviewers.csv` without ticking replace: the card
  says "Holding `reviewers.csv` from your last upload". Now choose
  `empty.csv` and Upload: the card refuses it ("CSV has no header row");
  the held file is not saved in its place.

## The Band 1 card reads a rule set as the engine does (#3237)

- [ ] **A Link with rules is set.** Session A's instrument card shows
  Who is being reviewed as "Filter using tags", not "Not set", though
  the file left it out of its touched Links.
- [ ] **A `0` is a value.** That rule reads Reviewee's tag 2 IS NOT
  with `0` in its value box, not an empty one.
- [ ] **The preview shows it.** Band 2's preview renders a sample row
  with the group's members.
- [ ] **The untagged group is nobody's own.** After Prepare session,
  the Assignments page's Self review cell reads "Include 2 self
  reviews" (Sam's Team A group), not 4: Rae's untagged group, which
  holds her own row, is not a self-review. Click the chip: Included
  drops from 10 to 8, and Rae's group stays in.
- [ ] **The import names what the card can't show.** Upload
  `settings_refused.csv` on Session A: the Settings slot refuses it,
  naming the combinator `ANY_OF` and the IS THE SAME AS in Who does
  the review, and nothing changes.
- [ ] **A disabled rule is hidden.** After `edit_rule_set.py round3-a
  disable`, reload the Instruments page: Who is being reviewed reads
  "All", with no rule, as the engine skips it.

## A rule set that can't load (#3238)

- [ ] **The Assignments page names it.** After `edit_rule_set.py
  round3-b unloadable`, Session B's Assignments page loads, with a red
  banner under the status table naming the instrument, the reason, and
  a link to its Instruments card.
- [ ] **Validate counts it an error.** The Validate page loads and
  lists `instruments.rule_set_unloadable` under Setup, as an error.
- [ ] **Save repairs it.** Unlock the instrument's card, set Who is
  being reviewed to All and Save: the banner and the error are gone.
