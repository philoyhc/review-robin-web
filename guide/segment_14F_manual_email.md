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

## PR ladder

1. **Scaffold:** ~~the disabled auto-send fields and their line, the
   Workflow caption~~ (moved to 14E rung 0, author 2026-11-04), the
   due-action prompts as static copy, and Send a test to me inert.
2. **The transport:** a delegated Graph `EmailTransport` and the dispatch
   helper, stamping rows; Send a test to me wired.
3. **The buttons:** Send, Send all, Remind, Remind incomplete send through
   it.
4. **Confirmations:** Send queued confirmations, with the backlog rule.
5. **The prompts, wired**, from the offsets the operator set. Last build
   rung: the cumulative read.
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

## Out of scope

- Mail on a clock: 14G, if IT grants a way.
- A background send queue (14B Part C), unless measured.
- Reviewee and observer notifications and magic links (14B's appendix,
  W20 / W21).

## Doc impact

- `spec/email_infra_options.md` — delegated Graph as the transport in use; the backend options as alternatives.
- `spec/lifecycle.md` — §8: the due-action prompts (auto-send disabled moved to 14E, 2026-11-04).
- `spec/workflow_card.md` — the due prompts (the auto-send caption moved to 14E, 2026-11-04).
- `spec/email_template_editor.md` — what Send does now; the recorded / sent / failed states named once.
- `cordware/spec/identity.md` — "Graph": the host's send primitive beside the directory lookup.
- `docs/deployment.md` — the setting in its table. <!-- doc-impact-waived: RRW_SCHEDULED_SEND moved to 14E rung 0 (author, 2026-11-04); 14F adds no setting -->
- `guide/post_azure_todo_checklist.md` — items 9 and 10 settled (at close).
