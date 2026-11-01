# Segment 14C — Email-related UI

**Opened:** 2026-11-01 · **Theme:** the operator-facing controls that
email sending needs, now that the send path is Microsoft Graph rather
than per-operator SMTP · **Related:**
`guide/segment_14B_email_infrastructure.md` (the send wiring),
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
under MFA (`guide/segment_14B_email_infrastructure.md`), and nothing
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
- `spec/operator_ui_concept.md` — the Settings page as Date & time alone (Item 1).
- `spec/operator_button_audit.md` — the SMTP Save, Cancel and Clear rows retired (Item 1).
- `spec/rrw_functional_spec.md` — operator settings without SMTP (Item 1).
- `spec/email_infra_options.md` — no per-operator SMTP page; the transport stays for other deployments (Item 1).
- `docs/operations_runbook.md` — `SMTP_ENCRYPTION_KEY` no longer needed by a page (Item 1).
- `guide/todo_master.md` — the 14C entry (Item 1).

## Item 2 — An "Email settings" card

### Opportunity

Once sending works, operators will want a few per-operator choices
about it, and the page has room: Item 1 leaves Date & time alone at
half width. The first one the author named (2026-11-01): whether mail
sent from the operator's own account also leaves a copy in their Sent
Items (Graph `sendMail`'s `saveToSentItems`). Others will follow.

### Decision

- A half-width **Email settings** card beside Date & time, holding
  **toggles**, one per choice, each a two-state Toggle per
  `spec/ui_elements.md` §6.
- **Scaffold first** (`CLAUDE.md`, consequential UI): the card with its
  copy and layout and every toggle inert, before any is stored.
- First toggle: **Keep a copy in my Sent Items** (default on, as Graph's
  is). It applies only to mail sent as the operator; the card says so
  when the deployment sends from a dedicated mailbox.
- Each toggle is stored when the send path that reads it exists (14B),
  as a per-operator preference beside `display_timezone`, so no column
  is added before it has a reader.

Rejected: *a toggle per setting on Session Home.* These are about the
operator's own mailbox, not a session.

### Semantics

- A toggle that the deployment's sender makes meaningless (Sent Items
  under a dedicated mailbox) is shown disabled with its reason, not
  hidden, so the card's shape does not change between deployments.

### PR ladder

1. **Scaffold:** the card, its copy, the inert toggle(s). Must not touch
   a route or service.
2. **Wire** each toggle when 14B's send path reads it, one rung per
   toggle or a few together.

### Definition of done

- The card renders at half width beside Date & time; each toggle
  persists and changes what the send path does (tests per rung).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 14C.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 14C entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

1. **Which other toggles?** Candidates to put to the author: send a copy
   to myself (Bcc); use the session's Help contact as the Reply-to;
   send invitations from me or from the dedicated mailbox when both
   exist. Each needs its send-side behavior settled in 14B first.
2. **Where does a deployment-wide sender setting live** (the dedicated
   mailbox's address), if it is not an App Setting? Not on this card,
   which is per operator.

### Out of scope

- The send path itself (14B) and the outbox page (14B Part E).

### Doc impact

- `spec/settings_inventory.md` — each stored toggle, its default and where it is kept (Item 2).
- `spec/operator_ui_concept.md` — the Email settings card on the Settings page (Item 2).
- `spec/operator_button_audit.md` — the card's toggles (Item 2).
