# Participant surface check

**Audited:** 2026-10-15 at `a7cb9143` (main) · **Asked for by:** the author ·
**Scope:** every page, message and email a reviewer, reviewee or observer
can see *outside* the review surface, the reviewer summary, the reviewee
results page and the observer collation page.

Three read-only passes split the work: entry and navigation (`/me`, the
invite landing, the operator bounce, shared chrome, About, Guide, the
sign-in pages); gates, refusals, error pages and the pre-open page; and
outbound email. I re-read the highest-impact claims (P1, P2, M8) against
the code before writing them down. **This audit changes nothing.** Each
finding names a likely fix and who decides; act from §2.

## 1. What a participant can see

| Surface | Reached by | Roles | What it shows |
|---|---|---|---|
| `/me` dashboard | sign-in, `/`, any operator URL | all | "Your reviews": one row per session with role pills, Start, End, Timezone, Session status and Reviewer status. With no rows: "You have no pending reviews (email)." |
| Invite landing `/me/invite/{token}` | email link | reviewer | Redirects to the surface on a match. Shows the mismatch page (403) for another account, and the 404 error page for an unknown or rotated token. |
| Pre-open page | invite link or bookmark while draft, validated or archived | reviewer | "{name} — opens later" (draft or validated) or "{name} — closed" (archived), with a "Your reviewer dashboard" button. |
| Error page (`app/web/templates/error.html`) | any refusal | all | "Error N", a headline, a message and "Go back". It has no app chrome. |
| About, Guide | top-bar links | all | About: what the app is and how access works. Guide: only the participant's own role cards. |
| Sign-in details `/auth/me/debug` | the mismatch page's "Sign-in details" | all | Parsed identity plus every raw Entra claim. |
| Emails | operator Send, scheduled offsets, Submit | reviewer only | Invitation, reminder, responses received. None is transmitted yet (§3). |

Every refusal on the participant routes is a bare 404 by design (19F,
`app/web/deps.py`), except these:

- **Session no longer accepting:** Save, Submit and Clear answer 403.
- **Recall outside `ready`:** 403.
- **Invite mismatch:** 403.
- **Not fully submitted:** `/summary` and `/summary.csv` redirect to `/me`.
- **Operator URLs:** `/operator/*` redirects to `/me`.

No participant path reaches a 409.

## 2. Findings

Ranked. **Decides:** *fix* means the code contradicts the spec or itself,
so the change is a bug fix. *author* means a copy or behavior choice.
A struck ID is done; its **Decides** cell names the PR.

### High

| ID | Finding | Where | Likely fix | Decides |
|---|---|---|---|---|
| ~~P1~~ | **Session names leak to any signed-in user.** `resolve_return_to` looks up `ReviewSession.name` for `/me/sessions/{n}` and `/operator/sessions/{n}/…` with no permission check. So `/about?return_to=/me/sessions/7` (or `/guide`, `/auth/me/debug`) reads "← Back to {session name}" for any id. This defeats 19F's "cannot infer anything" rule, and `tests/unit/test_return_to.py` asserts the name but not the authorization. | `app/web/return_to.py` | Resolve the name only when the viewer can see that session; otherwise fall back to the default label. | fix · **done** in #3061 |
| ~~P2~~ | **The error page is a dead end.** "Go back" is `history.back(); return false;`, so in a tab opened from an email it does nothing, and the `/` fallback never runs. There is no `/me` link, no sign-out and no help contact. Worst case: the invite 404 ("This invitation link is invalid or has expired.") and gate 404s reached from bookmarks. | `app/web/templates/error.html` | Make the link go to `/me` (or `/`) and use history only when there is some. | author · **done** in #3064: a real link (`/me`, Sessions on operator pages, Sign out on a 401); "Go back" only after an in-app page |
| ~~P3~~ | **A session that closes mid-edit throws away what the reviewer typed.** Save, Submit and Clear answer 403 "Access denied" / "No longer accepting responses" on the standalone error page. The same text also covers a reviewer with no assignments ("no longer", when they never could) and a session reverted to draft ("not yet"). | `app/web/routes_reviewer/_surface/_context.py` | Re-render the surface read-only with its closed banner; give each cause its own wording. | author · **done** in #3066 |
| P4 | **Reviewees and observers have no way in and no way back.** No email reaches them (§3). A reviewee's `/me` row appears only while the release window is open and silently vanishes after `responses_release_until`, leaving "You have no pending reviews". "My Reviews" counts reviewer rows only, so `/results` and `/collation` have no link back to `/me`. Neither does a single-session reviewer's closed surface. | `app/web/routes_reviewer/_shared.py`, `app/web/templates/reviewer/_top_bar.html` | Show a link back to `/me` on every participant page, whatever the count: widening the counter alone leaves a one-session reviewee or observer at 1, below the "more than 1" rule. Decide how reviewees learn the window opened (blocked on email, §3). | author · link back **done** in #3065 ("Your reviews" on every participant page); telling reviewees their window opened waits on email |

### Medium

| ID | Finding | Where | Likely fix | Decides |
|---|---|---|---|---|
| ~~M1~~ | **Recall after the deadline strands the reviewer.** Recall is offered while `ready` even after the deadline. The confirm dialog promises "return to the form to edit", but the surface is read-only by then and Submit is refused, so the reviewer is left "Saved but not submitted". This is deliberate per the route docstring, but the participant is never told. | `app/web/routes_reviewer/_summary.py`, `_surface/_routes.py` | Hide Recall once the deadline passes, or warn that resubmitting won't be possible. | author · **done** in #3066: hidden, and the route refuses it |
| ~~M2~~ | **The Recall refusal shows raw internals:** "Recall is only allowed while the session is ready; session status is 'expired'." That is a raw enum (operators see "Activated" / "Closed") in Python `repr` quotes, under "Access denied". | `_surface/_routes.py` | Write participant wording without the status value. | fix · **done** in #3062 |
| ~~M3~~ | **Pre-open copy is wrong or thin.** "The session operator has prepared the review…" also shows in `draft`, including after a revert from `ready`. The page omits the scheduled activation time that "Check back closer to the response window" implies, and omits the help contact. The archived variant says "has archived the review". | `app/web/templates/reviewer/pre_open.html` | Split draft from validated; show the activation time and help contact; reword "archived". | author · **done** in #3068: one "not currently open" wording, scheduled opening (prepared only), help contact |
| ~~M4~~ | **One archived session gets three different answers.** `/1` says "closed". `/summary` still renders, but its banner blames "the operator's visibility setting". `/collation` renders and blames Band 3 or the release window. The observer link is grayed on `/me`, but the URL still works. | `summary.html`, `collation.html`, `_collation.py` | Give archived sessions one wording everywhere, and refuse collation as its CSV already does. | author · **done** in #3068: `/summary`, `/summary.csv` and `/collation` answer 404 once archived; `/me` reads "Finished" |
| ~~M5~~ | **Collation empty states use operator vocabulary**: "Band 3", "the Observers Setup page", "cohorts". | `app/web/templates/reviewer/collation.html` | Write participant copy. | fix · **done** in #3062 |
| ~~M6~~ | **The dashboard's status column contradicts itself.** Past the deadline on a `ready` session, observer-only rows say "open" while reviewer rows say "closed" and End is red. Archived rows read "not opened" plus "archived". A zero-assignment reviewer reads "closed" with "0/0". Start keeps a stale date after a revert to draft. The surface says "No assignments are visible to you in this session yet." even when closed. | `app/web/routes_reviewer/_dashboard.py`, `dashboard.html`, `review_surface.html` | Use one status rule for every role, with an archived label of its own. | author · **done** in #3068: Not open yet / Open / Available / Closed / Finished; "Nothing assigned to you"; no stale Start; no "yet" on a closed surface |
| ~~M7~~ | **Two dashboard columns are always empty.** "View responses" and "Until" always show "—", and the template comment promising them is stale. | `dashboard.html`; `spec/reviewer-surface.md` | Fill them or drop them. | author · **done** in #3068: dropped |
| ~~M8~~ | **Operator chrome shows on About, Guide and Sign-in details.** A "Settings" link shows for every user (it isn't gated to operators) and bounces participants silently to `/me`. The operator brand shows. The Guide shows "(version )" because its template env never sets `app_version`. Sign-in details reads "Signed in as " with no name. "← Back to Sessions" goes to `/operator/sessions` from every participant path except `/me`. | `app/web/templates/base.html`, `routes_guide.py`, `routes_auth.py`, `return_to.py` | Gate Settings on operators; set the version; give participant paths a `/me` default. | fix · **done** in #3062; the operator brand **done** in #3069 (participants get their own top bar on About, Guide and Sign-in details) |
| ~~M9~~ | **The invite mismatch page has three problems.** It shows the invited address to whoever holds a forwarded link. Its "Sign-in details" button goes to the raw-claims debug page. "Sign out and sign back in" usually re-selects the same SSO account (a UPN vs mail-alias mismatch), so the reviewer loops. It says "contact the session operator" without showing `help_contact`, though `session` is in its context. | `reviewer/invite_mismatch.html`, `_invite.py` | Mask the address, drop the debug link, show the help contact. | author · **done** in #3069: partly masked, no debug link, alias case named, help contact |
| ~~M10~~ | **Revisiting a POST URL errors.** After a refused Submit or a Save with errors, the address bar holds `/submit?page=N` or `/{n}/save`. Pressing Enter or re-logging in gives 422 "Bad request" or 405 "Something went wrong". | `_surface/_routes.py` | Redirect a GET on these paths to the page. | fix · **done** in #3063 |
| ~~M11~~ | **Silent bounces.** `/summary` and `/summary.csv` redirect to `/me` with no message when the reviewer isn't fully submitted, so a CSV click lands on the dashboard. Operator URLs do the same. | `_summary.py`, `app/main.py` | Add a one-line notice on `/me`. | author · **done** in #3069: `?notice=summary` / `?notice=organizers` |
| ~~M12~~ | **The invite 404 says "has expired", but invitations don't expire.** Every send, reminder fallback or Regenerate rotates the token and kills older email links. | `_invite.py`, `app/services/invitations.py` | Say "this link has been replaced; use the latest email or sign in at …". | author · **done** in #3069 |
| ~~M13~~ | **The observer CSV link can 404.** The link shows for every raw or anonymized mode, but the route refuses when the cohort has no assignments, so the browser shows a failed download. | `app/web/views/_observer_collation.py`, `_collation.py` | Hide the link when the cohort is empty. | fix · **done** in #3063 |
| ~~M14~~ | **401 copy is developer text**: "Something went wrong" / "Not authenticated" or "Authenticated identity has no email claim". Easy Auth normally masks this in production. | `app/web/error_handlers.py` | Add a 401 entry to `_ERROR_COPY`. | fix · **done** in #3062 |

### Low

| ID | Finding | Where |
|---|---|---|
| ~~L1~~ | **The dashboard has five names**: "Your reviews", "My Reviews", "My reviews", "your reviews" and "Your reviewer dashboard". (The top bar's "My Reviews" is now "Your reviews", #3065.) The last goes to observers and reviewees too. ~~Its empty state, "You have no pending reviews", is wrong for observers, lapsed reviewees and strangers, and offers no next step~~ (done in #3064). (**done** in #3069: every link to `/me` now reads "Your reviews".) | `dashboard.html`, `_top_bar.html`, `pre_open.html`, `summary.html`, `invite_mismatch.html` |
| ~~L2~~ | **The brand varies**: "Review Robin" (reviewer chrome), "… — Review Robin Web" (titles), "· Review Robin" (error page). The mismatch title has no suffix at all. (**done** in #3070: every participant title and the error page end "— Review Robin Web".) | `error.html`, `invite_mismatch.html` |
| ~~L3~~ | **Operator jargon on participant pages**: "session operator", "the operator", "operator allowlist" and "Sessions lobby" (About), and a Guide subtitle about running sessions. "Operator" is defined only in the operator-only terms table. (**done** in #3070: About and the participant Guide subtitle no longer use operator words; pre-open was done in #3068.) | `about.html`, `guide.html`, `pre_open.html` |
| ~~L4~~ | **Guide participant cards.** The observer card says results come "once the operator releases responses", but Summarized can be granted while the review is ongoing. The reviewer card says "revisit until the session closes", but reviewers can revisit read-only afterwards. "anonymised/summarised" (UK) sits against the app's "Anonymized". (**done** in #3070.) | `app/web/templates/guide.html` |
| L5 | **Email copy.** Invitation and reminder omit the deadline and help contact. Dates carry no zone label. Only responses-received greets by name. "sign in with your work email" differs from About's "MS365 account". A responses-received override that uses `$help_contact` with none set sends "Contact .". An invitation override without `$invite_url` turns every later reminder into a fresh invitation. | `app/services/email_templates.py`, `invitations.py` |
| L6 | **Small defects.** The Timezone hover reads "UTC UTC". Dashboard rows reorder whenever an operator edits a session (`updated_at`). The observer CSV filename has no session and starts with an email address. ~~"confirm checkbox required" is raw text~~ (done in #3062). The template zips are reachable by participants (harmless). Two routes pass a `breadcrumbs` context nobody renders. | `dashboard.html`, `_collation.py`, `_surface/_routes.py`, `app/web/routes_templates.py` |

## Rulings (author, 2026-10-15)

- **`/me` is the fallback** for anyone signed in, with or without a
  role. P2's error page, P3's refusals and P4's link back all lead there.
- **The empty `/me` reads the same for everyone:** "There's nothing
  here for you right now. You're signed in as {address}. If you expected
  to see a review here, check that it was sent to this address, or
  contact the person running it." plus an About link. It is true for
  everyone who reaches it (a stranger, a reviewee with no current grant,
  a deactivated roster row) and implies nothing is waiting.
- **"Your reviews" is the dashboard's one name**: the error page's "Go to
  your reviews", the back link's "Back to your reviews", and P4's
  top-bar link (part of L1).

Second pass, same day:

- **P3 (a):** a refused Save / Submit / Clear renders the page again,
  read-only, naming its cause, with what was typed listed to copy.
- **M1 (a):** Recall is hidden once the deadline passes.
- **M3 (b), (c):** show the scheduled start time and the help contact;
  draft, validated and archived all say the review is "not currently
  open" rather than splitting their copy.
- **M6:** one role-aware status rule, labeled Not open yet / Open /
  Available / Closed / Finished. "Available" is closed to responses but
  viewable by that role now; "Closed" is closed with nothing to view
  right now, and can become Available when a release window opens.
- **M4 (a):** once a session is archived it is off limits: `/summary`
  and `/collation` are refused, as the observer CSV already is.
- **M7 (b):** drop "View responses" and "Until".
- **M8:** About, Guide and Sign-in details take the participant top
  bar for a participant.
- **M9:** all four fixes; the invited address partly masked.
- **M11, M12:** as recommended — a one-line notice on `/me`; "this
  link has been replaced" wording.

## 3. Context, not findings

These are already known and tracked; listed here because a participant would
meet them.

- **No email is transmitted yet.**
  - Invitation and reminder rows are stamped `sent` with no transport.
  - Responses-received rows stay `queued` forever.
  - Operators are told so on the Invitations page.
  - Wiring a transport is `guide/post_azure_todo_checklist.md` work.
  - Reviewees and observers have no email kind at all (`spec/participant_model.md`, "Blocked on email infrastructure").
- **Scheduled invitations and reminders fire only when an operator opens Session Home.** Reminders are skipped once the deadline has passed. This is carried in `guide/post_azure_todo_checklist.md`.
- **Invitation links are built from the operator's request host.** Behind Azure's TLS front end they may come out `http://`. Unverified until deploy.
- **Draft and validated sessions are listed on `/me`** for reviewers and observers, and an observer's collation link is live in draft. This matches 19F's decisions. Confirm it is still wanted.

## 4. Suggested order

1. **P1 alone**, as a fix PR. It is the only finding that exposes data across sessions.
2. **The fix-tagged findings in two PRs:**
   - chrome and copy: M2, M5, M8, M14;
   - surface mechanics: M10, M13.
3. **A rulings pass on the author-tagged findings, P2 to M12.** Several share one decision: what a participant sees when the answer is "no", and where it leads. That is P2, P3, M4, M11 and M12. One wording pass could settle them together.
4. **L1 to L6** ride whichever later PR touches the same file.
