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

- **No token** (~~fake auth, or~~ an expired one the page renewal missed;
  under fake auth `mailer_for` returns a `FakeMailer` that sends nothing,
  and the row reads `sent`, findings D12): the
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

Closed 2026-11-06. PRs #3644–#3668, plus the follow-ups (#3663) and
the M1/L1 fix (#3664) the build's own register raised.

**Intended vs done.** The Decision shipped as amended on 2026-11-05: no
bulk email (a bulk send waits for 14G's pacing), and instead a session
link to share. What the ladder became:

- **Rung 1** scaffolded the due prompt, the lobby's Due pill slot and an
  inert Send a test to me (main before rung 1: `79f86ee8`).
- **Rung 2** split in three. **2a** is the host's send primitive
  (`cordware.graph.mailer_for`, `FakeMailer` under fake auth), the Graph
  transport and `app/services/email_dispatch.py`; there is no retry on a
  `5xx` or a network failure, and a `429` waits once. **2b** wires Send a
  test to me: the template as edited, to the operator only, `[Test]`,
  recorded by `email.test_sent`. **2c** stores and reads 14C Item 2's
  three toggles (`send_options_for`).
- **Rungs 3–4** were re-cut as **3a–3d**: per-row Send and Send reminder
  dispatch through the operator's mailbox (`?email=…` on Invitations),
  and bulk is off behind `RRW_BULK_SEND`; the Share the session link card;
  `reviewers.last_opened_at` with `reviewer.opened`; the Extract data
  Timestamps chip.
- **Follow-ups** (#3663): per-row Send and Regenerate in a prepared
  session, revising B17 / F17; disabled buttons say why.
- **Rung 5** was re-cut once the offset fields proved disabled while
  scheduled email is off. **5a**: off, they are live as "Prompt to send …",
  validated (the lobby's End editor too). **5b** with **5c**:
  `app/services/due_actions.py`, the Workflow card's due lines with
  counts, **Mark as done** (`session.scheduled_*_handled`, consumed by
  `fired_offsets`, so 14G never sends a handled entry), and the lobby's Due
  pill (a due prompt, or a scheduled activation that gave up).

**Decisions confirmed at build:**
- A regenerate fails a still-queued row, so its dead link never goes out
  (Codex on #3651).
- Every last-opened stamp is audited, at most once per `ARRIVAL_GAP`
  (Codex on #3654).
- A refused per-row send restores the invitation's stamps only on a
  definite refusal (`email_dispatch.REFUSED_KINDS`), under the session
  lock, with `invitation.send_reverted`. A second Send on an invitation no
  longer pending is refused (findings M1, L1; Codex on #3664).
- Mark as done names the anchor and offset it was drawn from (Codex on
  #3668).
- Disabled bulk buttons stay visible, not hidden, at the author's ask.

**Reads.** One `diff-reviewer` read per item at its last build rung, plus
one for the M1/L1 fix. The cumulative read (base `79f86ee8`) found 3
medium and 6 low issues: the lobby's End editor skipped the offset check,
Doc impact lacked the specs the 5a ruling made stale, the refusal copy
named no handled entry, a docstring overclaimed, and tests were missing.
All were acted on except three: the lobby's per-row count (unmeasured),
one inline style, and raw ISO offsets in the due-line copy (the author's
call).

**The Guide.** Rung 6's "Running a session by hand" became edits to the
sections that already told it: the launch controls, *Give reviewers
access*, the Start/End paragraph and the offset fields (findings D2), not
a new section.

**Scope that moved.** The send-queued-confirmations button and the
responses-received backlog went to 14G (checklist item 9). Checklist item
10 is settled: a delegated send, which is what the tenant granted.

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
5. ~~**The prompts, wired**, from the offsets the operator set; a due
   reminder points to the card's Reminder message.~~ Re-cut 2026-11-06
   (the card's message boxes were cut at 3c; the offset fields were
   disabled while scheduled email is off):
   - **5a.** With scheduled email off, the two offset fields are live as
     prompts, labeled "Prompt to send invites / reminders", saved and
     validated as when on, each showing its due moment.
   - **5b.** The due-actions service; the Workflow card's due lines with
     counts, links to Invitations and the session link, and **Mark as
     done**, recorded where 14G's observers read it.
   - **5c.** The lobby's Due pill, including a persistent
     scheduled-activation failure. Last build rung: the cumulative read.
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
- `spec/lifecycle.md` — §8: the due-action prompts (auto-send disabled moved to 14E, 2026-11-04); §3.4 and the gate table: per-row Send and Regenerate take `require_validated_or_ready`, reminders stay `require_ready` (follow-up 1).
- `spec/operator_ui_concept.md` — the Invitations pattern: "All POST actions require `ready`" becomes the split above (follow-up 1).
- `spec/workflow_card.md` — the due prompts (the auto-send caption moved to 14E, 2026-11-04).
- `spec/email_template_editor.md` — what Send does now; the recorded / sent / failed states named once.
- `cordware/spec/identity.md` — "Graph": the host's send primitive beside the directory lookup.
- `docs/deployment.md` — `RRW_BULK_SEND` in the settings table, default off (2026-11-05; was waived when `RRW_SCHEDULED_SEND` moved to 14E).
- `spec/operations_pages.md` — the Share the session link card on Invitations; the bulk buttons disabled behind `RRW_BULK_SEND`.
- `spec/extract_data.md` — the participation report's columns (first opened, last saved, last submitted, eligible instruments).
- `spec/settings_inventory.md` — `reviewers.last_opened_at` in the Reviewers table, "Not settings: a reading" (rung 3d); the `invite_offsets` / `reminder_offsets` and `RRW_SCHEDULED_SEND` rows: off, prompts (rung 5a).
- `spec/session_home.md` — with scheduled email off, the two offset fields are live as prompts, validated, each with its due moment (rung 5a).
- `spec/sessions_overview.md` — the lobby's End editor checks reminder offsets whatever the flag; the Due pill and what raises it (rungs 5a, 5c).
- `spec/architecture.md` — `session.scheduled_invites_handled` / `_reminders_handled` and `invitation.send_reverted` in the audit-event table (rung 5b).
- `docs/deployment.md` — the `RRW_SCHEDULED_SEND` row: off, the offsets time prompts (rung 5a).
- `guide/post_azure_todo_checklist.md` — items 9 and 10 settled (at close).
