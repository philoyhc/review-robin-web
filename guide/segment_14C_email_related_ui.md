# Segment 14C — Email-related UI

**Opened:** 2026-11-01 · **Theme:** the operator-facing controls that
email sending needs, now that the send path is Microsoft Graph rather
than per-operator SMTP · **Related:**
`guide/archive/segment_14F_manual_email.md` (the send wiring; 14B, archived, before it),
`guide/email_and_scheduling.md` (where the choice of sender stands),
`spec/settings_inventory.md`, `spec/operator_ui_concept.md`

The UI half of email, split from 14B so the page can change before the
transport lands. Items close independently; the segment closes when the
author says no more are coming.

## Item 1 — Retire the per-operator SMTP cards

### Opportunity

`/operator/settings` asks every operator for an SMTP host, port,
encryption, login, app password and From display name, and offers a
confirm-gated **Clear all settings (SMTP)**. None of it can be used:
the author narrowed the choice of sender to **Graph as the operator**
or **Graph as a dedicated mailbox** (2026-11-01), institutional
Microsoft 365 tenants typically block basic SMTP AUTH and app passwords
under MFA (`guide/archive/segment_14B_email_infrastructure.md`), and nothing
reads the settings today ("Nothing in the app calls this yet",
`app/services/email_send.py`). The card tells operators to do work that
leads nowhere.

### Decision

- Remove the **Email send (SMTP)** card and the **Clear all settings
  (SMTP)** card from the page, and their two routes
  (`POST /operator/settings`, `POST /operator/settings/clear`).
- **Keep the storage**: the `smtp_*` columns on `users`,
  `SMTP_ENCRYPTION_KEY`, `operator_settings.save_email_settings` /
  `clear_email_settings` / `get_email_settings` and the SMTP transport.
  `spec/settings_inventory.md` says they exist, are unused here, and may
  serve a deployment outside Microsoft 365 (author, 2026-11-01: no
  column drop).
- The page keeps **Date & time** alone, half width, until Item 2's card
  joins it.

Rejected: *hide the cards behind a flag.* A flag no one sets is dead
code with a switch on it; the storage is enough to bring them back.

### Blast radius (measured)

Taken 2026-11-01 at `2577762`: one template
(`grep -rln smtp app/web/templates` → `operator/operator_settings.html`),
one route module (`app/web/routes_operator/_settings.py`, two handlers),
four test files (`grep -rln smtp tests` → `test_operator_settings.py`,
`test_bad_input_refused.py`, plus `test_email_send.py` and
`test_email_outbox_schema.py`, which test the kept service and transport
and stay), and nine live specs or docs naming the cards
(`grep -rlni smtp spec docs`, archives aside): `settings_inventory.md`,
`operator_ui_concept.md`, `operator_button_audit.md`,
`rrw_functional_spec.md`, `email_infra_options.md`, `README.md`,
`known_limitations.md`, `operations_runbook.md`, `deployment_dev.md`.

### Status

Done 2026-11-01 in one PR, as laddered. Decisions confirmed at build:

- The SMTP form's **Cancel** went with it; the back-link carries the
  return. The `return_to` round-trip test now rides the Date & time
  save.
- The service-level SMTP tests stay (`save_email_settings` /
  `clear_email_settings` / `get_email_settings`, called directly),
  since the storage is kept; `test_bad_input_refused.py`'s SMTP-port
  refusal went with its route.
- `README.md` and `docs/deployment_dev.md` described the page too and
  gained bullets; `spec/operator_ui_concept.md` never described the
  Settings page, so its bullet is waived.
- The composer's and Previews' **From** placeholder pointed at the
  retired card; both now say the sender is set when sending is switched
  on. The blast-radius grep was case-sensitive and missed them, and
  `spec/email_template_editor.md` and `spec/ui_elements.md`.
  `docs/known_limitations.md` needed nothing (its key mention holds).
- Reads: one `diff-reviewer` read. It found the From placeholder, two
  dropped service tests (O3 password-as-typed, O8 same password: ported
  to direct calls), the two missed specs, and stale comments (fixed).

### PR ladder

1. **One PR:** the template, the two routes, the tests, and the specs
   and docs that describe the cards.

### Definition of done

- `/operator/settings` shows no SMTP field or Clear card, and the two
  POST routes are gone (`tests/integration/test_operator_settings.py`).
- `spec/settings_inventory.md` lists the `smtp_*` columns as kept and
  unused, with why.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 14C.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 14C entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

None.

### Out of scope

- Dropping the columns or the key (author, 2026-11-01).
- Any send path: 14B.

### Doc impact

- `spec/settings_inventory.md` — the Settings page's surface without the SMTP cards; the `smtp_*` columns and `SMTP_ENCRYPTION_KEY` kept, unused, and why (Item 1).
- `spec/operator_ui_concept.md` — the Settings page as Date & time alone (Item 1). <!-- doc-impact-waived: the spec never describes the Settings page; its one SMTP line quotes the outbox page's copy, still true -->
- `spec/operator_button_audit.md` — the SMTP Save, Cancel and Clear rows retired (Item 1).
- `spec/rrw_functional_spec.md` — operator settings without SMTP (Item 1).
- `spec/email_infra_options.md` — no per-operator SMTP page; the transport stays for other deployments (Item 1).
- `docs/operations_runbook.md` — `SMTP_ENCRYPTION_KEY` no longer needed by a page (Item 1).
- ~~the dev slot's deployment notes — the same, in the App Settings table (Item 1)~~ (retired 2026-11-02; `docs/deployment.md` carries the line now)
- `README.md` — the Settings page's row and the SMTP-key setup paragraph (Item 1).
- `spec/email_template_editor.md` — the composer's From row no longer points at Settings (Item 1).
- `spec/ui_elements.md` — the retired SMTP form dropped as a `.page-grid` caller and a confirm-gate example (Item 1).
- `guide/todo_master.md` — the 14C entry (Item 1).

## Item 2 — An "Email settings" card

### Opportunity

Once sending works, operators will want a few per-operator choices
about it, and the page has room: Item 1 leaves Date & time alone at
half width. The first one the author named (2026-11-01): whether mail
sent from the operator's own account also leaves a copy in their Sent
Items (Graph `sendMail`'s `saveToSentItems`). Others will follow.

### Decision

- A half-width **Email settings** card beside Date & time (shipped
  under it: see Status), holding
  **toggles**, one per choice, each a two-state Toggle per
  `spec/ui_elements.md` §6.
- **Scaffold first** (`CLAUDE.md`, consequential UI): the card with its
  copy and layout and every toggle inert, before any is stored.
- First toggle: **Keep a copy in my Sent Items** (default off, author
  2026-11-05, though Graph's own default is on). It applies only to mail sent as the operator; the card says so
  when the deployment sends from a dedicated mailbox.
- Each toggle is stored when the send path that reads it exists (14F),
  as a per-operator preference beside `display_timezone`, so no column
  is added before it has a reader.

Rejected: *a toggle per setting on Session Home.* These are about the
operator's own mailbox, not a session.

### Semantics

- A toggle that the deployment's sender makes meaningless (Sent Items
  under a dedicated mailbox) is shown disabled with its reason, not
  hidden, so the card's shape does not change between deployments.

### Status

**Closed 2026-11-06.** Two rungs as planned. The card stacks **under**
Date & time, not beside it, because Unit (20D) took that slot. Three
Toggles, all off by default (author, 2026-11-05): Keep a copy in my
Sent Items, Send a copy to myself, Replies go to the session's Help
contact. Each is a boolean in `users.preferences`, posted to
`/operator/settings/email-preference` and audited
`operator.email_preference_set`; `email_dispatch.send_options_for`
reads them for per-row Send and Send reminder (the test send takes
Sent Items and Reply-to, not Bcc). Reply-to applies only when the Help
contact is an email address.

One read, at rung 2. It caught a Reply-to check that `parseaddr` let
through; it now uses `email_identity.looks_like_email`. It also caught
copy that claimed every send. The item waited on 14F rung 3a for its
Bcc reader. At the close, `spec-writer` added the Settings page to
`spec/operator_ui_concept.md` and the three Toggles to
`spec/operator_button_audit.md`; the other two specs were already
right. The report-email candidates went to Item 4.

### PR ladder

1. **Scaffold:** the card, its copy, the inert toggle(s). Must not touch
   a route or service.
2. **Wire** each toggle when 14F's send path reads it, one rung per
   toggle or a few together.

### Definition of done

- The card renders ~~at half width beside~~ under Date & time (Unit took
  the slot beside it); each toggle persists and changes what the send
  path does (tests per rung).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 14C.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 14C entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

1. ~~**Which other toggles?**~~ Bcc to myself and Reply-to the Help
   contact, beside Sent Items; all three off by default (author,
   2026-11-05). Was: candidates to put to the author: send a copy
   to myself (Bcc); use the session's Help contact as the Reply-to;
   send invitations from me or from the dedicated mailbox when both
   exist. Each needs its send-side behavior settled in 14F first. *Recommended
   (2026-11-05, with 14F's plan): the first two*, Bcc to myself and
   Reply-to the Help contact, read by 14F's transport; "from me or the
   dedicated mailbox" waits for a dedicated mailbox (14G).
2. **Where does a deployment-wide sender setting live** (the dedicated
   mailbox's address), if it is not an App Setting? Not on this card,
   which is per operator. *Recommended: an App Setting, decided in
   14G*, since only a dedicated mailbox needs it.

3. **Report emails** (filed 2026-11-02, author: "file the list in 14C for
   the settings ui for now"): which of the candidates below the card
   offers, and when. Author. *Recommended: none in 14F*; they are
   sends on a clock or on another person's action, so they follow 14G.

### Candidate toggles: report emails, operator to operator

Milestone reports an operator may opt into, one toggle each (or one per
group), all off by default; per operator, not per session. Mail goes as
the operator (ruling 2026-11-02), so what can send depends on what
triggers it: an operator's click carries a token; the clock and a
participant's action do not, so those wait for 14G.

| Group | Report | Trigger, and so when | To |
|---|---|---|---|
| A | Invitations sent: *n* of *N*, failures with reasons | operator's Send all (14F) | the operator who clicked |
| A | Reminders sent: *n* of *N* | operator's Remind (14F) | the same |
| A | Queued confirmations sent: *n* | operator's Send confirmations (14F) | the same |
| B | Lifecycle change by another owner: activated, reverted to draft, archived, unarchived, deleted | an operator's action (14F) | the other owners |
| B | Destructive data action by another owner: responses or rosters purged, responses cleared | the same | the other owners |
| B | Owner added or removed; responses released or release stopped | the same | the other owners |
| C | Scheduled activation done, or failed after retries | the clock (14E + 14G) | all owners |
| C | Deadline reached: *n* of *N* submitted | the same | all owners |
| C | Release window opened or ended | the same | all owners |
| C | A scheduled event or workflow run failed | the same | all owners |
| D | Every reviewer has submitted (close early?) | a reviewer's submit (14G) | all owners |
| D | Completion past 50 / 75 / 90 %, or a daily progress digest | the same | all owners |
| D | A submission recalled near the deadline | the same | all owners |
| D | Every reviewee has acknowledged results | a reviewee's action (14G) | all owners |
| D | Operator-side due actions ("reminders due today") | the clock (14G) | all owners |

- **Failures send at once** (persistent activation failure is the most
  valuable row: nobody is looking when it happens); the rest may batch
  into a daily digest.
- **Until 14G ships**, groups C and D render disabled with the
  deployment line the auto-send fields use (`guide/no_scheduling_fallback.md`).
  The scaffold lands after 14E (`guide/todo_master.md` order), so the
  clock exists by then: the line says *mail* on a clock waits, not the
  clock. Group C reads the clock's audit events, one per crossing
  (`guide/archive/segment_14E_clock.md`, judgment calls; 2026-11-04).
- Group A repeats what the page shows; it earns its place as a record, or
  when the operator leaves before a long send finishes.
- The last D row reverses the fallback note's proposed "no" to due
  prompts by email; the author decides.

### Out of scope

- The send path itself (14F; 14B, archived, before it) and the outbox page.
- Building the reports: A and B ride 14F's transport, C and D 14G's.
  This item lists and, later, stores the choices.

### Doc impact

- `spec/settings_inventory.md` — each stored toggle, its default and where it is kept (Item 2).
- `spec/operator_ui_concept.md` — the Email settings card on the Settings page (Item 2).
- `spec/operator_button_audit.md` — the card's toggles (Item 2).
- `spec/ui_elements.md` — §6 Toggle: used on the Email settings card too (Item 2).

## Item 3 — The default text as a draft to adopt

### Opportunity

Each of the composer's three templates (invitation, reminder, responses
received) shows its default subject and body as the boxes' placeholder
(`session_setupinvite.html`, `placeholder="{{ row.default }}"`). A
placeholder vanishes at the first keystroke, so an operator who wants
the default with one sentence changed has to retype it from memory, or
copy it from the Previews page (author, 2026-11-06, with a screenshot of
the Invitation email card).

### Decision

**Decided** (author, 2026-11-06): the default stays a grey placeholder, and the operator can
adopt it as a draft. In an empty box,
**→ (Right arrow) fills the box with the default text**, which is then
ordinary text to edit. Nothing changes until the operator presses the
key; a saved override, or any typed character, means there is nothing to
adopt. Leaving a box blank still means "use the default", as today.
Saving the adopted text, edited or not, stores it as an override like
any typed text: the operator's choice, which Reset undoes. *Rejected:* pre-filling every box with the default. That stores the
default as an override on the first Save, so a later change to the
default would never reach this session, and a blank box could no longer
mean "use the default".

### Open questions

- ~~How an operator finds the key~~: no hint; → on an empty box is
  ordinary keyboard behavior (author, 2026-11-06).
- ~~Tab as well as →~~: no, → only (author, 2026-11-06).
- ~~Which fields~~: subject and body only (author, 2026-11-06).

### Status

- 2026-11-06, the one rung: `data-adopt-default` on the composer's
  subject and body, and a keydown handler in its inline script. → with
  no modifier, in an empty box, fills the box with its placeholder,
  leaves the caret at the start and fires
  `input`, so Save turns on as for any edit. Browser tests in
  `tests/browser/test_adopt_default_draft.py`, over all three templates.
- Read once (`diff-reviewer`), with `spec-writer` at the close. Both
  found the spec claiming nothing is stored until the operator *edits*
  and saves, when saving the adopted default unchanged stores it as an
  override (`spec-writer` fixed the line; the Decision now says so). The
  read also found a caret-at-start check an empty box never fails,
  removed with its prose, and a test covering one template of three.

### PR ladder

1. The behavior in the composer's inline script, for the three
   templates' subject and body, and a browser test (`tests/browser/`) of
   → in an empty box of each template and in a box with text.

### Doc impact

- `spec/email_template_editor.md` — the default as a draft to adopt: → in an empty box, no hint, blank still meaning the default (Item 3).

## Item 4 — Report emails to the other owners

### Opportunity

Item 2's candidate list (above, "Candidate toggles: report emails")
names fifteen milestone reports an operator could opt into. Only one
group can send today. Mail goes as the operator who acts (ruling
2026-11-02), so a report needs an operator's click with its token behind
it. Group B, an owner's action reported to the session's *other* owners,
has exactly that. A's triggers are the bulk sends, which refuse until
14G Item 5. C and D fire on the clock or on a participant's action, so
they need scheduled email (author, 2026-11-06: B live; A, C and D
inactive).

### Decision

- **The card grows a "Report emails" section** under Item 2's three
  toggles. Each of group B's three rows is a live Toggle: lifecycle
  changes; destructive data actions; owners and release. Groups A, C and
  D are one inactive Toggle each, with the reason on the card: A waits
  on bulk sending (14G), C and D on scheduled email (14G). All are off
  by default, per operator.
- **A report goes from the acting owner's mailbox** to each *other*
  owner whose toggle for that row is on. It is sent after the action
  commits, through the same request mailer as per-row Send, and it never
  delays a refusal, undoes the action or blocks it. A failed send is
  recorded and the action stands.
- **Called from the routes**, after the service returns, through one
  service function, `owner_reports.report(...)`. The audit write is
  inside the action's transaction, and mail must follow the commit.
  *(Superseded at rung 3: the audit write notes, the commit promotes, a
  request dependency sends. See Status.)*
- **Recorded in the audit log**: `report.sent` (recipients counted, never
  listed) and `report.send_failed` (the error kind), each registered in
  `EVENT_SCHEMAS`. No outbox row: the outbox is participant mail.

Rejected: *send from the audit write* (`audit.write_event`). It would
mail before the commit, and couple the audit log to the mailer.
Rejected: *one toggle per report*, fifteen in all. The card reads as a
settings page, not a matrix. Group B's three rows are the author's own
table, and A, C and D stay one line each until they can send.

### Semantics

- **Which actions.** Lifecycle: `session.activated`,
  `session.reverted_to_draft`, `session.archived`, `session.unarchived`,
  `session.deleted`. Destructive: `session.responses_purged`,
  ~~`responses.cleared`~~ (a reviewer's own Clear all, so group D's;
  struck at the read), `session.rosters_purged` (added at the read),
  `responses.deleted_all`, and the four rosters' `*.deleted_all`. Owners and release: `session.owner_added`,
  `session.owner_removed`, `session.responses_released`,
  `session.responses_release_stopped`. The clock's own transitions (End
  closing a session, a scheduled activation) have no click behind them,
  so they belong to group C.
- **Who.** The session's owners at the moment of the action, less the
  actor; nothing when the actor is not an owner (added at the read). An owner who was just removed is told, since it concerns them.
  A deleted session's owners are read before the delete.
- **What.** Plain text: who did what, to which session (name and code),
  when (the session's zone), and a link to Session Home, except after a
  delete. The actor's Sent Items choice applies; Bcc and Reply-to do
  not, since they are about participant mail.
- **No mailer** (no token, a refused send): `report.send_failed` with its
  kind; the page shows no error, since the action succeeded.

### Judgment calls — decided

- The recipient's toggle decides, not the actor's: it is the recipient's
  inbox. (2026-11-06)
- One email per recipient per action, not a digest: digests need a
  clock (group C's territory). (2026-11-06)

### Blast radius (measured)

Taken 2026-11-06 at `49aa8daa`.

| What | Count | Command |
|---|---|---|
| Group B event types, all already in `EVENT_SCHEMAS` | 14 | `grep -oE '"session\.(activated\|reverted_to_draft\|archived\|unarchived\|deleted\|responses_purged\|owner_[a-z]+\|responses_release[a-z_]*)"' app/services/audit.py` plus the four `*.deleted_all` / `responses.cleared` |
| Email preference keys today | 3 | `email_save_to_sent_items`, `email_bcc_self`, `email_reply_to_help` in `app/services/operator_settings.py` |

### Status

- 2026-11-06. Main before rung 1: `f321b4b4` (#3691's merge; the base
  for rung 4's cumulative read). Rungs 1 (scaffold) and 2 (store) as
  planned.
- **Decision amended at rung 3: the hook is the audit write, the send is
  after the commit.** "Called from the routes" would have meant a call in
  each of the dozen routes reaching these actions (the lobby's bulk
  forms, the Workflow card, Session Home), easy to miss. Instead
  `audit.write_event` calls `owner_reports.note` for each reported event
  type, which decides the recipients inside the action's transaction; a
  SQLAlchemy `after_commit` listener promotes the notes (a rollback drops
  them), and an app-wide dependency, `app/web/owner_report_sender.py`,
  mails what committed once the route has answered. The plan's
  rejection of mailing *from* the audit write stands: nothing is mailed
  before the commit. `session.deleted` is written after the owner rows
  are gone, so `delete_session` keeps them first
  (`owner_reports.before_delete`).
- Rungs 3 and 4 shipped as one PR, since the read's fixes cut across
  both. The read (one, cumulative, at rung 4) found two highs: a
  reviewer's own Clear all (`responses.cleared`) would have mailed the
  owners from the reviewer's mailbox, so that event is struck and
  `note` requires the actor to own the session; and a savepoint's
  release fires `after_commit` (the session lock opens one on Postgres),
  so a note could be mailed before the real commit, and a savepoint
  rollback could drop the outer notes; both listeners now ignore nested
  transactions. Mediums fixed: the sender rolls back before recording,
  so it never commits a route's half-write; the body says when; Purge
  rosters is reported; a route that raises after committing still
  sends. The message names the owner added or removed, so a co-owner
  added at creation reads which one.
- Rung 4: the destructive row covers all four rosters'
  delete-all (`observers.deleted_all` and `relationships.deleted_all`
  beside the two the Semantics named), since each is "a roster deleted".

### PR ladder

1. **Scaffold:** the "Report emails" section with its six Toggles,
   inert, and the reasons on A, C and D. It must not touch a route or
   service.
2. **Store** group B's three choices: three preference keys and the
   existing `/operator/settings/email-preference` route, audited
   `operator.email_preference_set`. Tests per toggle.
3. **Send:** `owner_reports.report`, the two audit events, and the
   lifecycle row's five actions wired. Tests with the fake mailer:
   who receives, who does not, a failure recorded and the action
   standing.
4. **The destructive and the owners-and-release rows**, wired the same
   way. The last build rung, so it takes the cumulative `diff-reviewer`
   read.
5. **Close** (this item, then the segment).

### Definition of done

- The card shows six report Toggles. Group B's three persist and change
  who is mailed; A, C and D are inactive with their reasons.
- Each of the 14 actions mails each other owner who opted in, from the
  actor's mailbox, after the commit, and records `report.sent` or
  `report.send_failed`; a test per row.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 14C.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Open questions

None open; the author ruled B live, A, C and D inactive, and the item
shape (2026-11-06).

### Out of scope

- Groups A, C and D's sends: 14G Item 5 for A, the rest of 14G for C and
  D. Their toggles become live there.
- A report to the actor (A is that, and waits).

### Doc impact

- `spec/settings_inventory.md` — the three report preference keys, their defaults and the inactive three (Item 4).
- `spec/operator_ui_concept.md` — the Report emails section of the Email settings card (Item 4).
- `spec/operator_button_audit.md` — its six Toggles, three inactive (Item 4).
- `spec/architecture.md` — `report.sent` / `report.send_failed` in the audit-event table, and `owner_reports` in the module map (Item 4).
- `spec/email_infra_options.md` — owner reports as the second kind of mail sent as the operator (Item 4).
- `spec/session_owners.md` — what an owner is told when another owner acts (Item 4).
