# Things to check in a browser

Browser checks owed on merged changes that the test suite cannot settle:
layout, in-browser behavior and what a page shows. Every PR that owes one
adds a section here. Run them locally (`uvicorn`, fake auth). Tick a row
when it is checked; once every row in a section is ticked, delete the
section (git history keeps it), so this file lists only what is owed. A
section may point to upload files under `guide/browser_check_files/`;
delete them once no remaining section points to them.

A run order for every section below, with upload files, is in
`guide/browser_check_files/checklist/README.md` (2026-10-13). Delete it
with the last section it covers.

## Email dates in the session's zone (#2720)

- [x] **The deadline reads in the session's zone.** On a session whose
  display zone is not UTC (Singapore, say) with a 17:00 deadline, preview
  the invitation email. `$deadline` should read 17:00, not 09:00.
- [ ] **The submitted time does too.** Preview the responses-received
  email for a reviewer who has submitted; `$submitted_at` reads in the
  same zone. *Needs an Azure deployment; not checkable locally (author,
  2026-10-13).*

## A submit queues the confirmation email (G4)

- [x] **On by default.** As a reviewer, submit on an Activated session.
  In Admin → Sessions, open that session's outbox: one
  responses-received row for that reviewer, status `queued`, its body
  naming the submit time.
- [x] **A second submit refreshes it.** Recall and resubmit: still one
  queued row for that reviewer, not two.
- [ ] **Off sends nothing.** On the session's Email Template page,
  choose Responses received, click the chip to "Don't send response
  confirmation" and save.
  Another reviewer's submit adds no row, and the submit itself still
  succeeds.

## A failing scheduled send no longer breaks Session Home (B20)

- [ ] **Session Home loads.** Nothing in the UI can force a send to
  fail, so this is a smoke check: open Session Home for a session with
  scheduled invites or reminders set and past due. It loads, and Admin →
  Sessions shows the audit log with either the fired events or, if
  something failed, one `session.scheduled_event_failed` row per
  failing trigger, however many times the page is reloaded.

## Zip all follows the other cards (D28)

- [x] **Card order.** On Extract data, the left column holds Reviewer
  response metadata above Reviewee response metadata. The right column
  holds By instrument above Extract all data. The intro reads "Use
  **Zip all** to download a complete set of response data, plus
  whichever files are selected below, as each card configures them."
- [x] **Same files as the cards.** On By instrument, turn off one
  instrument and Include metadata. On Reviewer response metadata, cycle
  Self-review to Exclude. Download each card's own file, then the intro's
  Zip all. The zip holds `…_responses.csv` and the same files under the
  same names, and each opens identical to its card's download.
- [x] **Chips leave cards out.** Turn off the intro's Reviewee response
  metadata and Data shaper chips. Zip all no longer holds the reviewee
  metadata file or any shape files. No stats or `…_instrument_1.csv`
  files appear in any case.
- [ ] **Rehydrate still takes it.** Give an instrument the short label
  `responses`, then download Extract Setup's Zip all and this Zip all.
  Rehydrate both zips on the lobby: it accepts them.

## Back links name only sessions you can see (P1)

- [ ] **A stranger sees the default.** Signed in as someone with no role
  on a session, open `/about?return_to=/me/sessions/<id>` for that
  session's id. The back link reads "← Back to your reviews" (or "← Back
  to Sessions" if you are an operator), never the session's name.
- [ ] **An owner still sees the name.** As the session's owner, open
  About from inside that session. The back link names the session.

## Participant chrome and copy (M2, M5, M8, M14)

- [ ] **No Settings link for a participant.** Signed in as a reviewer who
  is not an operator, open About. The top bar shows no Settings link,
  and the back link reads "← Back to your reviews" and goes to `/me`.
- [ ] **The Guide shows its version.** As the same reviewer, open the
  Guide. The top bar reads "(version …)" with a number in it.
- [ ] **Sign-in details names you.** From the invite mismatch page, follow
  "Sign-in details". The top bar reads "Signed in as" with your name.
- [ ] **Collation empty states read as a participant's.** As an observer
  with no cohort rule, open the collation page: "You haven't been given
  anyone to observe in this review yet." With a rule on a draft session:
  "There are no results for you to see right now."

## Revisited POST addresses and the empty-cohort download (M10, M13)

- [ ] **Enter on a refused Submit's address lands on the form.** As a
  reviewer, press Submit with a required field empty. With the address
  bar showing `…/submit?page=…`, click into it and press Enter. You land
  back on the page you pressed Submit on, not an error page.
- [ ] **No download for an empty cohort.** As an observer whose cohort
  rule matches nobody, on an instrument released to observers as Raw,
  open the collation page. Row 3 reads "No one in your view takes part
  in this instrument, so there is nothing to download", with no
  Download CSV button.

## The /me fallback: error page link and empty dashboard (P2)

- [ ] **The error page always has a way out.** Open a bookmark-style URL
  for a session you're not on, e.g. `/me/sessions/999999/results`, in a
  new tab. The page shows "Go to your reviews" and no "Go back"; the
  link lands on `/me`.
- [ ] **"Go back" appears after an in-app page.** Click through to the
  same URL from another page of the app in the same tab. "Go back" shows
  beside "Go to your reviews" and returns to that page. Both links sit
  centered under the message. Ctrl-click (open in new tab) the same link
  instead: the new tab shows "Go back" too, and it works. On a
  deployment, open the URL signed out in a fresh tab: after the sign-in
  redirect, no "Go back" shows.
- [ ] **The empty dashboard.** Signed in as someone with no role, `/me`
  reads "There's nothing here for you right now.", names your address,
  and links to About.

## "Your reviews" on every participant page (P4)

- [ ] **One session is enough.** As a reviewer on a single session, open
  the review form. The top bar shows "Your reviews", and it goes to
  `/me`.
- [ ] **Reviewees and observers too.** On a reviewee's results page and
  an observer's collation page, the top bar shows "Your reviews".
- [ ] **Not on the dashboard itself.** On `/me`, the link is absent.

## A refused write keeps what was typed (P3) and Recall after the deadline (M1)

- [ ] **Closed mid-edit.** As a reviewer, type into a few cells,
  including a multi-line text answer, then (as the operator, in another
  window) close the session. Press Save. The review page comes back
  read-only with an amber card: "This review has closed, so your last
  changes weren't saved." Under it, what you typed, line breaks kept,
  and you can select and copy it.
- [ ] **Past the deadline.** Same, but let the deadline pass instead.
  The card names the deadline and its zone. Press Submit instead of
  Save: it says "so your answers weren't submitted".
- [ ] **Reverted to draft.** Same, but revert the session to draft. The
  page you land on reads "This review is not currently open.", with the
  refusal card at the top saying the same.
- [ ] **Recall is gone past the deadline.** Submit everything, open the
  summary: "Recall my submission" shows. Let the deadline pass (session
  still Activated) and reload: the button is gone.

## `/me` status, the not-open page, archived sessions (M3, M4, M6, M7)

- [ ] **Status labels.** On `/me`, rows read "Not open yet" (draft or
  prepared), "Open" (Activated, before the deadline), "Closed" or
  "Available" after it. Archived sessions are not listed (see "Archived
  sessions are off limits" below). There are no "View responses" or
  "Until" columns.
- [ ] **Available.** As an observer on a closed session with a release
  window open and Band 3 granting observers, the row reads "Available".
  As a reviewer past the deadline who saved an answer, likewise.
- [ ] **Nothing assigned.** A reviewer whose assignments are all
  excluded reads "Nothing assigned to you", not "0/0".
- [ ] **Start after a revert.** Revert an Activated session to draft:
  its row's Start goes back to "—".
- [ ] **Not open page.** Open a draft and a prepared session's review
  link: each reads "This review is not currently open." A prepared
  session with a scheduled start shows "Scheduled to open"; set a help
  contact and it shows on both.
- [ ] **Archived is off limits.** On an archived session, the summary,
  its CSV and an observer's collation page each show the error page.

## Shared pages, the mismatch page and `/me` notices (M8, M9, M11, M12)

- [ ] **Participant top bar on shared pages.** Signed in as a
  participant, open About, Guide and Sign-in details (`/auth/me/debug`):
  each shows "Review Robin" with "Your reviews", not the operator bar
  with its version. As an operator, the operator bar stays.
- [ ] **Mismatch page.** Follow someone else's invitation link: the
  invited address shows as `r•••@example.edu`, there is no "Sign-in
  details" button, the alias sentence reads sensibly, and a help contact
  shows when the session has one.
- [ ] **Notices on `/me`.** Open a summary before submitting everything:
  `/me` says the summary is available once every review is submitted.
  As a participant, open an operator URL: `/me` says that page is for the
  people who run reviews.
- [ ] **Old invitation link.** Send an invitation twice and open the
  first email's link: the page says it has been replaced by a newer one.

## Participant titles and wording (L2, L3, L4)

- [ ] **Titles.** The tab title on the review surface, the mismatch page,
  Sign-in details and any error page ends "— Review Robin Web".
- [ ] **About.** Signed in as a participant, About describes the app
  without "operator" and says someone who runs reviews lands on the
  Sessions page.
- [ ] **Guide.** As a participant, the Guide subtitle reads "What to
  expect in the reviews you take part in." The reviewer card mentions
  "Recall my submission", reading answers until the review closes, and
  after that only if the people running it allow it; the observer card says a summary
  can show while the review is still open. As an operator, the subtitle is unchanged.

## Email copy (L5)

- [ ] **Default invitation and reminder.** On Invitations, open a
  reviewer's preview: each email greets the reviewer by name, gives the
  deadline with its zone (e.g. "(GMT+8 Asia/Singapore)"), says to sign
  in with the institutional MS365 account, and ends with the help
  contact. Clear the help contact and the deadline: those lines go,
  with no "Contact ." or "by .".
- [ ] **Override fallbacks.** Override the reminder body with
  "Ask $help_contact" on a session with no help contact: the preview
  reads "Ask the person running this review". Override the invitation
  body with text that has no `$invite_url`: the preview still ends with
  "Open this link: …".

## Small participant defects (L6)

- [ ] **Timezone hover.** On `/me`, hover the Timezone chip of a UTC
  session: it reads "UTC", not "UTC UTC". A GMT+8 session reads
  "GMT+8 Asia/Singapore".
- [ ] **Row order.** With two sessions on `/me`, edit the older one as
  an operator: the rows keep their order (newest-created first).
- [ ] **Observer CSV name.** Download an observer's per-instrument CSV:
  the file is named after the session code, not the observer's address.

## Archived sessions are off limits to participants

- [ ] **Gone from `/me`.** As a reviewer and observer on a session,
  archive it as the operator and reload `/me`: the row is gone (with no
  other sessions, the empty "nothing here for you" text shows).
- [ ] **Every page refuses.** On that archived session, the review link
  (`/me/sessions/{id}/1`), the summary, its CSV, the collation page and
  the invitation link from the email each show the error page, naming no
  session.
- [ ] **Guide and back links.** With no other session, the Guide link is
  gone from the top bar and `/guide` sends you to About; About's back
  link opened with `?return_to=/me/sessions/{id}` reads "Back to your
  reviews", not the session's name.
- [ ] **Operators unchanged.** As the operator, the archived session's
  pages still open from the Archived list.

## Audit log: zone toggle and Severity row

- [ ] **Settings zone by default.** With a non-UTC timezone in
  Settings (e.g. Asia/Singapore), open Admin → Sessions Diagnostics →
  a session's Audit log: "Display times in" shows a solid `GMT+8
  Asia/Singapore` chip before Download CSV; the When column and the
  From / To labels read `(GMT+8)`, and the times are local.
- [ ] **UTC by click.** Click the chip: it reads `UTC`, the times shift
  back by the offset, and the labels read `(UTC)`. Apply a filter, page
  to Older events and Clear: the page stays in UTC. Click the chip again
  to return.
- [ ] **Days follow the zone.** Pick an event logged between 00:00 and
  08:00 Singapore time; set From and To to that local day: it shows.
  Switch to UTC with the same dates: it drops out (it falls on the day
  before in UTC).
- [ ] **CSV.** Download CSV in either zone: the rows match the page, and
  the CreatedAt column is UTC (`+00:00`).
- [ ] **UTC in Settings.** With Settings set to UTC (or `Etc/UTC`), the
  chip is a plain `UTC` pill with no link.
- [ ] **Daylight-saving zone.** With Settings set to America/New_York,
  the When column and the From / To labels read `(America/New_York)`,
  not an offset; Europe/London likewise, and it keeps its chip.
- [ ] **Severity row.** Above the event-type list, one line reads `Event
  type | Severity` followed by the info / warning / error chips;
  the right column no longer has a Severity block. "Event type" and
  "Severity" read the same size as "Actor email", and sit about as far
  above the event-type list as "Actor email" does above its box.
  Narrow the window: the line wraps cleanly.
- [ ] **Two columns.** Under the title and description: Event type /
  Severity, the list and its hint on the left; Actor email, From / To
  and the Apply filters button (Clear beside it once a filter is on)
  on the right, the buttons just under the dates. The table starts a
  little below the taller column.

## Audit log Severity chips

- [ ] **Chips, not checkboxes.** After `Event type | Severity`, three
  chips: `INFO`, `WARNING`, `ERROR`, each in its pale status tint with
  the blue chip edge. Click one: info turns solid blue, warning solid dark
  amber, error solid red, each with white text. Apply filters: the table
  narrows and the chips you picked stay on.
- [ ] **Dark mode.** Switch to dark: off chips are the dark status
  tints; on, warning is bright amber and error light red, with dark text
  (as the blue chip turns light blue with dark text).
- [ ] **Keyboard.** Tab to a chip: a focus ring shows; Space toggles it.
- [ ] **Guide.** About → Guide, "Reading the controls": the new "On or
  off, in a status color" row has a Warning (on) and an Error (off) chip;
  both switch on a click.

## Validate severity chips

- [ ] **Three chips, all on.** Validate setup on a session with issues:
  after *Show:*, `Errors (N)`, `Warnings (N)`, `Info (N)` in their solid
  status colors (red, dark amber, blue), and no *All issues* chip. The
  issue list holds every issue.
- [ ] **A click filters at once.** Turn Warnings off: the page reloads
  with no button press, scrolled to the chip strip, Warnings goes to its pale amber tint, its count
  stays, and the warnings leave the list. Turn every chip off: the list
  reads *No issues shown. Turn a severity chip on to see them.*
- [ ] **Remembered.** With Info off, go to Reviewers and back to
  Validate (or open another session's Validate): Info is still off.
- [ ] **Activate banner.** On a Prepared session with warnings, press
  Activate to reach the acknowledgment banner, then toggle a chip: the
  banner stays, and the page scrolls to it rather than to the chips.
- [ ] **Dark mode and keyboard.** In dark, on chips are bright with dark
  text; Tab to a chip shows a focus ring, Space toggles it.
- [ ] **Guide screencap.** About → Guide, the Validate figure still shows
  the old four chips; retake `validate-page.png` and its dark twin when
  convenient.
