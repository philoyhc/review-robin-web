# Interoperability: what it means for RRW

**Opened:** 2026-11-04, at the author's request. **Status:** pre-positioning,
not a build. The cross-app design is parked
(`cordware/docs/cordware_interoperability_consolidated_spec_v0.3.md`, with
its handoff), to be revisited when ApplyDesk or RA Lifecycle is further
along. This note says what that design asks of **RRW**: what built work it
leans on and must keep stable, and what the segments not yet built do now
so the handoff needs no rework later. It builds no interoperability.

**Rulings it rests on** (author, 2026-11-04; the spec's §13.1):

- **v1 sends rosters only.** Reviewers, Reviewees, Observers and
  Relationships (as pair context); no `settings.csv`. Instruments, fields
  and rules are built in RRW.
- **One operator in both apps.** Two apps interoperate only for a person
  who is an operator in both; no cross-app delegation.
- **Pre-position, don't build.** Unbuilt segments take the choices below;
  nothing adds a handoff route, table or manifest until the revisit.

## 1. Built work the handoff leans on

The receiver reuses RRW's own parsers and services (spec §6.3), so these
contracts become a second consumer's too. **Keep them stable; change one
only as a contract change, with its spec.**

| Area | What the handoff relies on | What it means now |
|---|---|---|
| Roster CSVs (`spec/csv_contracts.md`) | The v1 payload is these four files, through these parsers, at these caps (1 MiB, 5,000 rows a file) | A header rename or a new required column breaks a sender too. Additive optional columns are safe. |
| One person, two applications | The application ID goes in `RevieweeEmail` as an opaque identifier; a duplicate address in one file is a blocking error | Keep opaque identifiers first-class. Validate's `reviewees.unreachable_for_results` then fires on every row; the revisit decides whether a handoff session explains or suppresses it. |
| New session + Quick Setup (`spec/quick_setup_card_spec.md`) | Create, owner, setup and receipt in one transaction | Today New session commits before its files are checked, so a refused file leaves an empty draft. An atomic create also fixes that; it changes an existing page, so it is ruled at the revisit, not slipped into other work. |
| Directory check at import (`spec/setup_pages.md`) | A create resolves every address within RRW's 120 s budget | The countdown's `directory-keys` / `directory-lookup` and their 15-minute kept answers fit the spec's holding tab: count down there, then create. Keep them roster-generic, not tied to the Upload card. |
| `responses.csv` and Extract Data (`spec/extract_data.md`) | A result export with stable keys | `instrument_{n}` is positional and a field's `Version` resets after a clear, so `responses.csv` is not a result feed. `session_seq` + `field_key` is stable. Keep `responses.csv` as it is (manual parity, spec §3 invariant 6); a handoff export adds keys beside it. |
| Extract Setup and Rehydrate ZIPs (`spec/rehydrate.md`) | The nearest thing RRW has to a setup package | They carry no manifest. A handoff manifest is its own envelope; it does not change these bundles. |
| Lifecycle triggers (`spec/lifecycle.md` §8.3) | A status read that changes nothing (spec §3 invariant 5, scenario 6) | Timed changes fire on page views today, so a read-only status call would report stale state. **14E** removes the dependence. |
| Progress counts (`app/web/views/_progress.py`, `_workflow_card.py`) | Status counts with exact denominators (D4) | A status projection reuses these adapters rather than a second set of queries. Keep each count's definition named in one place. |
| JSON endpoints (`app/web/routes_operator/_directory.py`) | An error envelope and a CSRF posture for `/api/` routes | `_error()`'s `{"error": code}` with `no-store`, and a JSON-only body as the cross-site guard, are the precedent. RRW has no `/api/` routes yet. |
| Operator authorization (`spec/permissions.md`) | Each app checks its own operator, per session | `require_session_operator` is the gate; nothing accepts another app's role. |
| App-relative URLs (`app/web/urls.py`) | A receipt returns the destination's Session Home URL | Built through `urls`, never a root path, as every page does. |
| Audit (`spec/architecture.md`, `EVENT_SCHEMAS`) | Receipts and exports are audited | A handoff event registers like any other, source refs in `refs=` / `context=`. |
| Invitations and the outbox (`app/services/invitations.py`) | An *invited* count in status | `sent_at` is stamped when a send is **recorded**, before any mail moves. **14F** separates recorded, sent and failed. |

## 2. Pre-positioning in segments not yet built

Each plan carries its line as a judgment call; this is the list.

- **14E — the clock** (`guide/archive/segment_14E_clock.md`).
  - Fires only what an operator set (an activation time, a deadline);
    never acts on a session for being new, so a handoff-created draft
    stays untouched until its operator acts (spec §3 invariant 4).
  - Carries timed lifecycle changes only: no export, sync or other
    app's work rides it (spec §10.1).
  - The loop and its lock key are RRW's own, so another app's clock
    cannot collide with it.
- **22C — pyright** (`guide/archive/segment_22C_pyright.md`, closed).
  - A package added later (ApplyDesk, a handoff module) joins the gate
    when it is created.
  - The `sqlalchemy>=2.1` floor reaches production through the next
    Cordware import of `requirements.txt`; that import PR says so.
- **14F — email by hand** (`guide/archive/segment_14F_manual_email.md`).
  - **Recorded, sent, failed** are three states named in one spec
    section, so a status projection can count *invited* without
    guessing.
  - **The Graph send primitive goes in the host** (`cordware/graph.py`,
    beside the directory lookup): a host transport helper (spec §3 invariant 2)
    other apps can reuse. The outbox, batching and stamps stay RRW's.
    No token crosses apps (spec §7.1).
  - Sends only on an operator's click; a handoff never sends (spec §3 invariant 4).
- **14C Item 2 — the Email settings card**: per-operator settings, read
  by RRW only; nothing to pre-position.
- **14G — scheduled email** (planned when IT answers): an application
  `Mail.Send` permission on a shared mailbox is a host-level credential
  every mounted app could reach, against spec §3 invariant 2 and §7.1. Plan one
  mailbox and access policy per app, or record a ruling that a shared
  one is accepted.

## 3. For any new work meanwhile

- Change a CSV contract as a contract, with its spec: other apps will
  generate these files.
- Name a new identifier by something stable (a `session_seq`, a
  `field_key`, a public id), never a position.
- A GET changes nothing; keep new state changes off page views.
- A new JSON endpoint follows `_directory.py`'s envelope and posture.
- No import across packages (`cordware/tests/test_import_boundary.py`)
  and no table another app reads.

## 4. What the proof of concept settled (23A)

Segment 23A (`guide/archive/segment_23A_interop_poc.md`) built the
initiate step against mock rosters, before ApplyDesk; the contract is
`spec/handoffs.md`. For the revisit:

- **The browser-mediated, one-origin flow works.** A tab opened during the
  click, a same-origin JSON post and a receipt URL land the operator on
  the new Session Home, with no cross-app credential (interop spec §7.1).
  Verified in local Chromium; production after an import is the author's.
- **All or nothing without an atomic create.** The handoff route keeps
  New session's two commits and deletes the draft on a refusal, so New
  session's own behavior did not change (§1's row stays a ruling for
  the revisit).
- **Replay needs a completion record, not roster counts.** An operator
  may clear a roster after a handoff, so a replay reads
  `session.handoff_completed`, never deletes, and re-checks who may
  operate the session now. A table can replace the two audit events
  once a status projection needs one.
- **Routes:** `/operator/handoffs/…` rather than the interop spec's
  `/reviewrobin/api/v1/…`; ApplyDesk's segment settles the final paths.
- **Still open for the revisit:** `reviewees.unreachable_for_results`
  fires on every opaque application ID (§1); two concurrent first posts
  of one transfer can make two sessions; and two first requests from a
  brand-new user can race in `get_or_create_user` (`UNIQUE users.email`),
  which a sender's holding tab and post make likelier.

## 5. When the revisit comes

Start from the handoff's §3 reconciliation report against the `main` of
the day; §1 above answers part of it. Then a segment plan, whose
`Doc impact` names `cordware/spec/interoperability_and_orchestration.md`.
This note retires into it.
