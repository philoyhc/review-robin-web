# Segment 14F — Email by hand, as the operator

**Opened:** 2026-11-02, at the author's request · **Theme:** invitations, reminders and confirmations go out when an operator clicks, from the operator's own mailbox · **Related:** `guide/archive/segment_14E_clock.md`, `guide/no_scheduling_fallback.md`, `guide/email_and_scheduling.md`, `guide/archive/segment_14B_email_infrastructure.md` (superseded), `spec/email_infra_options.md`

## Opportunity

No email leaves Review Robin. Send, Send all and the reminder buttons
record a send and queue an outbox row that stays `queued`
(`app/services/invitations.py`); the transport stubs are not called
(`app/services/email_send.py`). The author ruled that everything goes out
from the operator's own mailbox (2026-11-02), and the tenant already
grants delegated `Mail.Send`, so sending on a click needs nothing from IT.
What sends on a clock waits on IT (14G).

## Decision

**Delegated Graph, on the operator's click.** The operator's token, which
Easy Auth already passes (`cordware/graph.py` reads it for the directory),
sends through `/me/sendMail` inside the request that clicked:

- per-row **Send** and **Send all** (invitations), **Remind** and **Remind
  incomplete**;
- a **Send queued confirmations** action for the responses-received rows
  that reviewers' submits queue;
- each send stamps its outbox row `sent` or `failed` with the reason, and
  writes `email.sent` / `email.send_failed`;
- a **Send a test to me** action in the email composer, sending the
  template as edited (author, 2026-11-05; was the Invitations page).

**While no mail goes on a clock** (`guide/no_scheduling_fallback.md`;
the first two parts moved to 14E rung 0, author 2026-11-04), the
two auto-send fields render disabled behind `RRW_SCHEDULED_SEND=off`
(values kept, the Settings CSV round-trips), the Workflow card drops
"System will dispatch automatically", and **due-action prompts** replace
the promise: Session Home says what is due ("Reminders due: 12 reviewers,
2 days before End") beside its button, and the lobby marks sessions with
an action due.

Rejected: *14B Part A's per-operator SMTP.* Institutional tenants block
basic SMTP AUTH under MFA, and 14C retired the SMTP cards. Rejected: *a
background queue for Send all* (14B Part C): a few hundred sends fit the
gateway's 120 s; revisit only if measured otherwise.

**Amended 2026-11-05 (author): no bulk email in 14F; share the link.**
A session of 1,500 reviewers is 1,500 messages, one per personal link. In
one request that runs far past the gateway's 120 s, and it meets the
mailbox's own sending limits (to be measured on Azure). So:

- **Bulk sending is built but off.** Send all, Remind incomplete, Send
  queued confirmations and the Workflow card's Send invites render
  disabled behind `RRW_BULK_SEND` (default off), with one line pointing
  to the session link. Turning it on, with paced, batched sending, is
  14G's. **Per-row Send and Remind stay live**: one message, one request.
- **The session link is the fallback.** Every session already has one
  stable link for every reviewer, `/me/sessions/{public_id}`
  (`spec/rrw_functional_spec.md` §7.2), gated at arrival by sign-in and
  the roster. A **Share the session link** card shows it with Copy, and
  the Invitation and Reminder templates rendered for everyone, with
  `$invite_url` as the link and `$reviewer_name` blank, in an editable,
  unsaved box with Copy message and Copy subject. The operator pastes
  them into their own channel, such as an LMS.
- **A stranger's arrival stays a bare 404** (author, 2026-11-05).
- **A participation report** replaces per-reviewer tracking by email:
  one CSV row per reviewer (name, email), with their eligible
  instruments, when first opened, when last saved, and when last
  submitted. Extract data's Reviewer response metadata is the first
  candidate. Its documented columns (`spec/extract_data.md`) carry
  counts but no times, so the build checks the code and adds the three
  times there, or builds the report beside it.

## Semantics

- **No token** (fake auth, or an expired one the page renewal missed): the
  send refuses, nothing is stamped, and the page says to reload; rows stay
  `queued`.
- **Partial failure in Send all:** each row stands alone; the page reports
  `n sent, m failed` and leaves the failed rows to retry.
- **A rotated token:** a queued row whose link a regenerate has rotated is
  never sent; Send sends the invitation's current link.
- **The backlog** of rows queued before this ships (checklist item 9):
  invitations and reminders not resent; confirmations sent only if
  queued after the go-live date, and not for a recalled or deleted
  submission (author, 2026-11-05).
- **From:** the operator's own address, as Graph sends it; nothing in the
  app sets it.
- **One send per row** (`guide/post_azure_todo_checklist.md`, added
  2026-11-05): the sender claims a row by flipping it `queued` →
  `sending` in a conditional update, and sends only a row it claimed. A
  resubmit rewrites a row still `queued`, and two clicks of Send all can
  overlap, so an unclaimed send could go twice. `sending` is already in
  `EMAIL_OUTBOX_STATUSES`; a row left `sending` by a request that died
  reads as such on the outbox, and is retried only by hand.

## Judgment calls — decided

- Sends run in the request, not in the background (2026-11-02).
- The auto-send fields are disabled, not removed (2026-11-02).
- **Interoperability, pre-positioned** (`guide/interoperability.md` §2,
  2026-11-04):
  - **Recorded, sent, failed** are named in one spec section, so a later
    status projection counts *invited* without guessing.
  - **The Graph send primitive goes in the host**, `cordware/graph.py`
    beside the directory lookup, for other apps to reuse; the outbox,
    batching and stamps stay RRW's. No token crosses apps.
  - Sends only on an operator's click; nothing sends on a session's
    creation.
- **The lobby's due-action marker includes a persistent scheduled
  activation failure** (2026-11-04): with 14E's clock it fails with
  nobody looking, and until 14G nothing mails it.
- **Device class** (`spec/visual_style_rrw.md`, "Device classes"): the
  operator pages this adds are desktop-oriented.

## Blast radius (measured)

Taken 2026-11-02 at `fffd4c28`; re-taken 2026-11-05 at `095336bf`
(after 22H's reformat), where only the first row moved.

| What | Count | Command |
|---|---|---|
| Send/remind services in `invitations.py` | 5, now 7 | `grep -n "^def send_\|^def queue_responses_received" app/services/invitations.py \| wc -l` |
| Operator send/remind routes in `_operations.py` | 4 | `grep -n "def invitations_send\|def invitations_remind" app/web/routes_operator/_operations.py \| wc -l` |
| Templates naming the auto-send offsets | 4 | `grep -rln "invite_offsets\|reminder_offsets" app/web/templates \| wc -l` |

## Status

- 2026-11-05, rung 1 (scaffold). Main before rung 1: `79f86ee8`, the
  base of the item's cumulative read at rung 5.
  - **The due prompt** is a placeholder signal line in the Workflow
    card's aside, shown once a session has invite or reminder offsets.
  - **The lobby's Due pill** has its slot in the status cell, fed by
    `views.lobby_due_session_ids`, which marks none until rung 5.
  - **Send a test to me** sits inert in the composer's Save row.
- 2026-11-05, rung 2 split in three: **2a** the host's send primitive
  (`cordware.graph.mailer_for`, `FakeMailer` under fake auth), the Graph
  transport and the dispatcher (`app/services/email_dispatch.py`), no UI;
  **2b** Send a test to me wired; **2c** 14C Item 2's toggles stored and
  read. 2a sends nothing on its own: no route calls it yet.
  - **No retry on a `5xx` or a network failure**, since Graph may have
    accepted the message; a `429` waits once. The outbox row reads
    `failed` and a person decides.
- 2026-11-05, rung 2b: **Send a test to me** submits the composer form
  to `/setup-invite/send-test` (`app/services/email_test_send.py`). It
  renders the template as edited, unsaved, overlaying the saved overrides
  with `set_committed_value` so nothing is marked dirty. Merge tags come
  from the roster's first reviewer, else a "Sample Reviewer" stand-in,
  and the link is a placeholder. It goes to the operator only, subject
  marked `[Test]`, with no Cc, Bcc or outbox row, and `email.test_sent`
  records it. It answers with the composer itself, not a redirect, with
  the draft still in its fields and Save live, so a test never loses
  unsaved edits (Codex on #3648). The result line is
  `views.send_test_notice`.
- 2026-11-05: the ladder is re-cut by the Decision's amendment (no bulk
  email; share the link). The original rungs 3 and 4 are struck below,
  and 3a–3d added.
- 2026-11-05, rung 3a, Codex on #3651: a Regenerate fails the
  invitation's still-queued rows, so a per-row send queued before it
  never goes out with the dead link (`email=superseded`).
- 2026-11-05, rung 3b: the **Share the session link** card sits on
  Invitations between the counters and the table, with the link, the
  invitation and reminder messages and five inert Copy buttons. The
  Workflow card's bulk-off line links to `#share-session-link`. Two
  lines that 3a made stale also changed: the composer's "sending is not
  switched on yet" and the Email settings card's.
- 2026-11-05, rung 3c: the card's link is
  `request.url_for("review_surface_default_position")`, absolute through
  the host's public origin as invitation links are.
  `email_templates.render_for_everyone` renders each template with that
  link as `$invite_url` and no reviewer, so a default body drops its
  greeting line; an override renders as written, and the operator edits
  a stray `$reviewer_name` in the box. Copy uses the Clipboard API, else
  `execCommand`, and a status line says which happened.
- 2026-11-05, rung 3a:
  - **Per-row sends.** Send and Send reminder dispatch the row they queue
    through `graph.mailer_for`, with `send_options_for`, and redirect to
    Invitations with `?email=sent|failed&kind=…`
    (`views.row_send_notice`). The mailer is built first, so with no
    token nothing is queued or rotated.
  - **Bulk off.** `RRW_BULK_SEND` (default off) disables the card's two
    bulk buttons, with a signal line, and the routes answer 409. The
    disabled buttons stay visible, departing from the card's
    hide-inactive rule, because the author asked for them inactive, not
    hidden.
  - **No send-queued-confirmations button exists yet**; 14G builds it.
  - **Copy.** The three places saying no email is delivered now say
    what Send does: the Invitations note, the status row's hover title
    (retired) and the Guide.
  - **Tests.** The suite's mailer is a `FakeMailer` (an autouse fixture
    in `tests/conftest.py`), since the suite runs without fake auth.

## PR ladder

1. **Scaffold:** ~~the disabled auto-send fields and their line, the
   Workflow caption~~ (moved to 14E rung 0, author 2026-11-04), the
   due-action prompts as static copy, and Send a test to me inert.
2. **The transport:** a delegated Graph `EmailTransport` and the dispatch
   helper, stamping rows; Send a test to me wired.
3. ~~**The buttons:** Send, Send all, Remind, Remind incomplete send through
   it.~~ Re-cut as 3a (author, 2026-11-05).
4. ~~**Confirmations:** Send queued confirmations, with the backlog rule.~~
   A bulk send: moved to 14G with the backlog rule (2026-11-05).

3a. **The per-row buttons, and bulk off.** Per-row Send and Remind send
    through the dispatcher with `send_options_for`. A missing token
    refuses with "reload the page", and a rotated link is never sent.
    Send all, Remind incomplete, Send queued confirmations and the
    Workflow card's Send invites render disabled behind `RRW_BULK_SEND`,
    with their line.
3b. **Share the session link, scaffold:** the card on the Invitations
    page (a link to it from the Workflow card) with copy and layout
    only, and its Copy buttons inert.
3c. **Share the session link, wired:** the absolute link (from
    `CORDWARE_PUBLIC_ORIGIN`), the templates rendered for everyone, and
    copy to the clipboard.
3d. **The participation report:** a **Timestamps** chip on Extract data's
    Reviewer response metadata adds LastOpened, LastSaved and
    LastSubmitted per reviewer (author, 2026-11-05). A last-opened stamp
    is set on every arrival, through the shared link or a personal one.
5. **The prompts, wired**, from the offsets the operator set; a due
   reminder points to the card's Reminder message. Last build rung: the
   cumulative read.
6. **Close.** Specs; checklist items 9 and 10 settled; the Guide's
   "Running a session by hand".

## Definition of done

- A click on Send delivers the invitation from the operator's mailbox, and
  its row reads `sent`; a refused send reads `failed` with its reason
  (a browser check on Azure, the author's).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 14F` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~The backlog rule above.~~ Adopted as written (author, 2026-11-05).
- ~~Where Send a test to me sits.~~ In the email composer, sending the
  template as edited with merge tags from a sample row (author,
  2026-11-05).
- ~~Which of 14C Item 2's toggles the send path reads.~~ All three on
  the card: Sent Items, a copy to myself (Bcc) and Reply-to the Help
  contact, **each off by default** (author, 2026-11-05).
- ~~A stranger at the session link: a bare 404, or a friendlier page?~~
  The 404 stays (author, 2026-11-05).
- ~~Where the Share the session link card lives.~~ The Invitations page,
  with a link from the Workflow card (author, 2026-11-05).
- ~~The participation report's form.~~ Reviewer response metadata gains
  one more toggle chip, **Timestamps**, adding when last opened, last
  saved and last submitted per reviewer (author, 2026-11-05). Its
  columns carry counts but no times today
  (`app/services/extracts/entity_metadata_extract.py`). "Last opened"
  needs a new stamp, since `Invitation.opened_at` records the first
  open only.

## Out of scope

- Mail on a clock: 14G, if IT grants a way.
- **Bulk sending** (Send all, Remind incomplete, Send queued
  confirmations, Workflow Send invites) and the backlog rule's sends:
  14G, which turns `RRW_BULK_SEND` on with paced, batched sending
  (2026-11-05).
- Reviewee and observer notifications and magic links (14B's appendix,
  W20 / W21).

## Doc impact

- `spec/email_infra_options.md` — delegated Graph as the transport in use; the backend options as alternatives.
- `spec/lifecycle.md` — §8: the due-action prompts (auto-send disabled moved to 14E, 2026-11-04).
- `spec/workflow_card.md` — the due prompts (the auto-send caption moved to 14E, 2026-11-04).
- `spec/email_template_editor.md` — what Send does now; the recorded / sent / failed states named once.
- `cordware/spec/identity.md` — "Graph": the host's send primitive beside the directory lookup.
- `docs/deployment.md` — `RRW_BULK_SEND` in the settings table, default off (2026-11-05; was waived when `RRW_SCHEDULED_SEND` moved to 14E).
- `spec/operations_pages.md` — the Share the session link card on Invitations; the bulk buttons disabled behind `RRW_BULK_SEND`.
- `spec/extract_data.md` — the participation report's columns (first opened, last saved, last submitted, eligible instruments).
- `guide/post_azure_todo_checklist.md` — items 9 and 10 settled (at close).
