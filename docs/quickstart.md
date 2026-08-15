# Review Robin — Quickstart

A short, practical walkthrough for a colleague running their first review
with Review Robin. It follows one session end-to-end: create it, set it up,
launch it, watch responses come in, and share the results.

> **About the screenshots.** This guide has marked slots for screen
> captures — each looks like the callout below. Replace every one with an
> image (suggested filename in `code font`); the captions say exactly what
> to capture. Until then they read as "insert a picture here."
>
> 📷 **Screenshot —** `example.png` — *what the picture should show.*

---

## 1. What Review Robin does

Review Robin runs **structured review sessions**: a group of **reviewers**
fill in a form about a group of **reviewees**, and the app collects,
organises, and shares the results. You (the **operator**) decide who
reviews whom, what questions they answer, and who gets to see the outcome.

A few words you'll see throughout:

| Term | Meaning |
|---|---|
| **Session** | One review round — its own people, form, dates, and results. |
| **Operator** | You: the person who sets up and runs the session. |
| **Reviewer** | Someone who fills in the form. |
| **Reviewee** | Someone who is being reviewed. |
| **Instrument** | The form itself — the set of questions reviewers answer. |
| **Assignment** | One reviewer-reviews-one-reviewee pairing. |
| **Observer** *(optional)* | Someone who may view collated results without reviewing. |

---

## 2. Before you start

- Review Robin runs as a **hosted web app on your institution's Azure** —
  there's nothing to install. You'll be given its **web address**; open it
  in a browser.
- **Sign in** with your institutional Microsoft account — the app uses your
  organisation's single sign-on, so there's no separate password to create.
  The first time you sign in, your operator account is created automatically.
- You'll land on the **Sessions** list (your lobby). If it's empty, that's
  expected — you haven't made a session yet.

> 📷 **Screenshot —** `01-sign-in.png` — *the institutional sign-in screen
> (or the moment just after sign-in).*

> 📷 **Screenshot —** `02-empty-lobby.png` — *the empty Sessions lobby for a
> first-time user, showing the `Add new` button.*

---

## 3. Create a session

1. On the Sessions lobby, click **Add new**.
2. Give it a **name** (e.g. "Spring Peer Review") and a short **code** (a
   unique handle, e.g. `spring-2026`).
3. Optionally set a **deadline** and a description.
4. Save. You'll be taken to the session's **Session Home**.

New sessions start in **Draft** — nothing is live yet, and you can change
anything freely.

> 📷 **Screenshot —** `03-create-session.png` — *the Create Session form
> filled in with a sample name, code, and deadline.*

> 📷 **Screenshot —** `04-session-home-draft.png` — *Session Home for a
> brand-new Draft session, with the **Workflow** card at the top.*

The **Workflow** card at the top of every session page is your control
panel: it always shows the single most useful next action for the session's
current state. You'll return to it to validate, activate, and release
results.

---

## 4. Set up the session

Setup happens on the **Setup** pages (linked from Session Home): **Reviewers**,
**Reviewees**, **Instruments**, and — if you enable them — **Relationships**
and **Observers**. The **Quick Setup** card on Session Home is the fast path
for the common pieces.

### 4a. Add reviewers and reviewees

**Use CSV uploads.** Unless you're dealing with only a handful of people,
strongly prefer importing a spreadsheet over typing rows one at a time —
it's faster, far less error-prone, and it's the shape institutional rosters
usually already come in. Each CSV just needs a **name** column and an
**email** column.

> ⚠️ **The emails must be the institutional emails people will sign in
> with.** The app matches each person to their roster row by their
> signed-in email, so an address that doesn't match means they won't see
> their review. Getting the emails right here is the single most important
> setup step.

The quickest path, once you have the two CSVs ready, is the **Quick Setup**
card on Session Home — it takes your **Reviewers** and **Reviewees** CSVs
(and, if you use them, Relationships and a Settings file) in one place. Having
the CSVs on hand is exactly what makes Quick Setup worthwhile.

1. Prepare a **reviewers CSV** and a **reviewees CSV** (name + email columns).
2. Upload both via **Quick Setup** on Session Home — or, to work
   page-by-page, use the **Reviewers** and **Reviewees** setup pages' upload
   cards.

> 📷 **Screenshot —** `05-quick-setup.png` — *the Quick Setup card on Session
> Home with the Reviewers and Reviewees CSV slots.*

> 📷 **Screenshot —** `05a-reviewers-setup.png` — *the Reviewers setup page
> after a CSV import, showing the roster and the upload card.*

> Only a handful of people? You can type them straight into the Reviewers /
> Reviewees pages instead. Either way: reviewers and reviewees can overlap
> (people can review each other), and any row can be marked **inactive** to
> exclude someone without deleting them.

### 4b. Build the form (Instruments)

Open the **Instruments** page. Each session starts with a default
instrument you can rename and shape:

- **Response fields** are the questions reviewers answer (ratings, text,
  etc.) — add, edit, reorder, or remove them.
- **Display fields** are read-only context shown to the reviewer (e.g. the
  reviewee's name or profile link).
- Use **Preview** to see the form exactly as a reviewer will.

> 📷 **Screenshot —** `06-instrument-editor.png` — *the Instruments page
> with a couple of response fields defined.*

> 📷 **Screenshot —** `07-instrument-preview.png` — *the live Preview of the
> reviewer form.*

### 4c. Decide who reviews whom (Assignments)

Open the **Assignments** page (under Operations). The **Assignment Rule**
generates the reviewer-reviewee pairings for you:

1. Choose/confirm the rule (the default pairs everyone with everyone
   eligible).
2. Click to **generate** the assignment pairs.
3. Review the **Assignment pairs** table below; adjust the **Self-reviews**
   toggle if you don't want people reviewing themselves.

> 📷 **Screenshot —** `08-assignments.png` — *the Assignments page after
> generating pairs, showing the Assignment Rule card and the pairs table.*

### 4d. (Optional) visibility, relationships, observers

- On each instrument you can set **who sees the responses and in what form**
  (Raw / Anonymized / Summarized), for reviewers, reviewees, and observers.
- If your review needs **pair context** (tags describing each pairing) turn
  on **Relationships**; if some people should **view results without
  reviewing**, turn on **Observers**. Both are off by default.

> 📷 **Screenshot —** `09-visibility.png` — *the per-instrument visibility
> settings (the audience × timing grid).*

---

## 5. Check and launch

1. Back on Session Home, use the Workflow card's **Validate** action. This
   runs a pre-flight check and lists anything missing or risky.
2. Fix any blocking issues (warnings are fine to proceed past). The session
   moves to **Validated**.
3. When you're ready, click **Activate**. The session becomes **Activated**
   and instruments open for responses.

> 📷 **Screenshot —** `10-validate.png` — *the Validate page showing a clean
> (or nearly clean) pre-flight result.*

> 📷 **Screenshot —** `11-activated.png` — *Session Home once the session is
> Activated, with the status badge/pill.*

> Before launching, the **Previews** page lets you see the exact form any
> specific reviewer will see when they sign in — a good final sanity check.

---

## 6. Give reviewers access

Automated email invitations and one-click **magic links aren't switched on
yet** — but you don't need them to run a review. Because access is based on
the roster, you simply **share the app's link yourself** and let people sign
in:

1. Make sure the session is **Activated** (Section 5) and your reviewers are
   on the roster with the **emails they'll sign in with** (Section 4a).
2. **Broadcast the Review Robin web address** to your participants through
   your own channel — an LMS announcement, a class email, or a course page.
3. Each person opens the link, **signs in with their institutional
   account**, and immediately sees the review(s) that apply to them on their
   dashboard. No invitation or code needed — the app recognises them by
   their sign-in email.

That's the whole handoff: **share the link → they log in → they see their
reviews.**

> 📷 **Screenshot —** `12-reviewer-dashboard.png` — *a signed-in reviewer's
> dashboard (`/me`) listing the review(s) that apply to them.*

> **Coming later:** when email + magic-link invitations ship, this step
> becomes a one-click "generate + send invitations" (with reminders) from the
> Workflow card. The review runs perfectly well without them today — the
> shared-link route above is all you need.

---

## 7. Watch progress

- The **Invitations** page shows, per reviewer, how far through the form
  each person is (its email/reminder columns simply sit idle until email is
  switched on).
- The **Responses** page flips the view: per **reviewee**, how much coverage
  they've received (Complete / Adequate / At risk / No responses).

> 📷 **Screenshot —** `13-responses-coverage.png` — *the Responses coverage
> page classifying reviewees by completeness.*

---

## 8. Close, release, and share results

When responses are in:

1. Use the Workflow card to **Close** the session (stops accepting new
   responses) and, when you're ready, **Release responses**.
2. **Reviewees** can then see their results at their own `/me` page, in the
   form you allowed (Raw / Anonymized / Summarized).
3. **Observers**, if enabled, see collated results on their collation page.

> 📷 **Screenshot —** `14-release.png` — *the Workflow card showing the
> Release-responses / Close actions.*

> 📷 **Screenshot —** `15-reviewee-results.png` — *a reviewee's results view
> (use anonymized/summarized sample data for the capture).*

### Export the data

The **Extract Data** card on Session Home downloads CSVs of everything —
reviewers, reviewees, relationships, settings, and the full responses table
— for analysis or archiving.

> 📷 **Screenshot —** `16-extract-data.png` — *the Extract Data card with
> its per-CSV download buttons.*

---

## 9. What your reviewers experience

So you know what you're asking people to do:

1. They open the **Review Robin link** you shared and **sign in** with their
   institutional account.
2. Their **dashboard** lists the review(s) that apply to them; they click in
   to a **review form** listing the reviewees assigned to them and the
   questions to answer.
3. They **Save** as they go and **Submit** when finished. They can revisit
   until the session closes.

> 📷 **Screenshot —** `17-reviewer-surface.png` — *the reviewer's form (the
> `/me` review surface) with a couple of reviewees listed.*

---

## 10. Tips & troubleshooting

- **Import with CSVs.** For anything beyond a handful of people, upload
  reviewer/reviewee spreadsheets rather than typing rows — and it's what lets
  you use the one-shot **Quick Setup** card.
- **Roster emails must match sign-in emails.** People are recognised by the
  institutional email they log in with, so the roster addresses have to be
  those exact emails.
- **No emails needed to launch.** Email + magic-link invitations aren't on
  yet; just share the app link (e.g. via your LMS) and signed-in participants
  see their own reviews.
- **Everything's editable in Draft.** Set up freely before validating.
- **Validate early.** The pre-flight catches missing pieces before you share
  the link.
- **Made a mistake after activating?** The Workflow card's **Revert** action
  returns a session to Draft so you can fix and re-launch.
- **Inactive vs delete.** Mark a person inactive to exclude them while
  keeping their history; delete only removes them entirely.
- **Reruns.** To repeat a review, you can duplicate a session, or rebuild
  one from its exported CSVs (**Rehydrate**, from the lobby).

---

## Getting help

- Your session's **Validate** page explains most setup problems in plain
  language.
- For anything else, contact your Review Robin administrator.

<!--
Screenshot checklist (replace each 📷 callout above with an image):
  01-sign-in.png            02-empty-lobby.png         03-create-session.png
  04-session-home-draft.png 05-quick-setup.png         05a-reviewers-setup.png
  06-instrument-editor.png  07-instrument-preview.png  08-assignments.png
  09-visibility.png         10-validate.png            11-activated.png
  12-reviewer-dashboard.png 13-responses-coverage.png  14-release.png
  15-reviewee-results.png   16-extract-data.png        17-reviewer-surface.png
Suggested location: docs/images/quickstart/<name>.png
-->
