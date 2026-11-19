# Segment AD1M — Apply Desk: Layer B, gates to Review Robin (simulated)

**Opened:** 2026-11-19 · **Theme:** Layer B of "What a linked Review Robin gate needs": Send, Re-send, Status, Results, link state, Invite and remind on Evaluations, built on sample data and kept in the tab, with the bundle Apply Desk would post built for real · **Related:** `applydesk/guide/todo_master.md` (rulings 24, 29, 43, 48, 55–57; the Layer B roadmap row; "What a linked Review Robin gate needs"), `applydesk/spec/applications.md` ("The Evaluations page"), `spec/handoffs.md`

## Opportunity

Every Review Robin action in Apply Desk is a disabled button. `operator/_gate_state.html` draws *Send to Review Robin* and *Pull results* with "comes with AD6" titles, on Evaluations' Gates table and on the gate page's head. So an operator cannot try the step the whole exercise builds towards: sending a gate, watching it, and getting its results back.

The parts are in place:
- AD1G and AD1H settled the pairs;
- AD1K settled a gate's states (`workflow.gate_state`, `gate_opened`);
- 23F settled Review Robin's side of the link (`spec/handoffs.md` §6a, `spec/linked_sessions.md`).

What is missing is the operator's half. The bundle Apply Desk would post has never been built either, so nothing yet checks that Apply Desk's sample can become the rosters Review Robin accepts.

## Decision

1. **Simulated in the tab** (ruling 55). Each action changes the gate as Review Robin would answer, kept in `sessionStorage` like the gate page's pairs. Nothing reaches Review Robin until AD2 can store a transfer record and AD6 makes the calls. The pages say so.
2. **The bundle is built for real** (`applydesk/handoff.py`), as pure functions over the sample. It covers reviewers, reviewees, relationships and the settings rows, as "What a linked Review Robin gate needs" C lists. The gate page shows what would be sent and offers each file to download. AD6 posts these same files.
3. **A Review Robin card on the gate page** carries the gate's link. Evaluations' Gates table keeps one action per row and links to it. The card holds:
   - the session's name and code (ruling 56);
   - the link state;
   - the last send;
   - *What is sent*;
   - Status (each evaluator's completion);
   - *Invite* and *Remind*.
4. **States** run *Not ready* → *Ready* → *Sent* → *Sent* with progress (opened) → *Results in*, or *Detached*. A sent gate whose bundle has changed since it was sent reads *Changed since sent*, and offers *Re-send* while its session is unopened (ruling 29).
5. **A gate concludes when the operator pulls its final results** (ruling 57). *Pull results* reads progress while the session is open. Once Review Robin's session is closed, *Pull final results* writes the results by dossier and marks the gate *Results in*.
6. **A confidential gate sends the Dossier ID** with the name redacted (ruling 43, already settled). The builders apply it, and *What is sent* shows it.

**Alternative rejected:** real calls now, by building a minimal transfer table ahead of AD2. It would fix a persistence shape before AD2 plans it, and it would need the real endpoint's auth and host in the loop before the operator's flow is settled. The simulation settles the flow, and AD6 swaps the tab's record for the stored one.

## Semantics

- **Session name and code** (ruling 56) are derived and editable:
  - name: *exercise name — gate label*;
  - code: *public ID*`-g`*n*.
  - Both are editable until the session opens, within Review Robin's limits (name 1–255 characters, code 1–64).
  - A code another gate of this exercise uses is refused in the tab, as Review Robin's `409 session_code_conflict` would be.
- **Changed since sent:** each send records a digest of the bundle. The page compares it with the bundle as it now stands. The tab's own unsaved pair changes do not count, because they are not saved (AD2); the card says so.
- **Refusals** are shown with their reason, by the codes `spec/handoffs.md` names:
  - `session_opened` (re-send after opening);
  - `session_code_conflict`;
  - `invalid_setup` (a gate not *Ready*).
  - `session_has_responses` and `not_linked` cannot arise in the sample. They are listed and not drawn.
- **Opened gates come from the sample** (`workflow._GATES`), never from the tab. A gate sent in the tab stays unopened, because only Review Robin opens a session.
- **Detached:** after an Unlink in Review Robin, a gate shows *Detached*. It offers no re-send and no pull, and keeps what was last pulled.
- **Invite and remind:**
  - *Invite* emails each paired evaluator a link to Review Robin's `/me`.
  - *Remind* emails those not done.
  - Both show the email they would send. Its text is fixed until AD7 adds the templates to Emails.
  - The card records when each was last done, and who it went to.
- **Other pages read the sample.** Dossiers, Home, the lobbies and Process keep the sample's gate states, as the gate page's pair changes count only on the gate page until AD2 (AD1G).

## Judgment calls — decided

- The card sits on the gate page, not Evaluations: Evaluations stays a table of every gate, each linking to its page.
- *Status* is part of the card, not a separate button: reading progress is what *Pull results* does while the session is open.
- Invite and remind text is fixed here: templates for them are an Emails change, AD7's.
- A Suggested gate whose only lack is approvals sends once the tab has approved every dossier (2026-11-19): approvals live in the tab until AD2 and change no file, and no sample gate is otherwise *Ready*.
- A tab that has added or removed pairs cannot send (2026-11-19): the files are the pairs as saved, so sending would misstate them.

## Blast radius (measured)

Taken 2026-11-19 at `9b6006bea`.

- Templates: `operator/_gate_state.html` (the chip and action macros), `operator/_evaluations.html` (Gates table), `operator/gate_evaluations.html` (head; the new card); `base.html` for new classes.
- Python:
  - `grep -rn "gate_state(\|gate_sent(\|gate_opened(" applydesk --include=*.py | grep -v tests | wc -l` → 21 call sites;
  - `workflow.py` and `routes_operator.py` change;
  - `applydesk/handoff.py` is new.
- Tests: `grep -rln "gate_state\|gate_sent\|gate_opened" applydesk/tests | wc -l` → 7 files; a new `test_handoff.py` and a browser test.
- Specs: `applydesk/spec/applications.md` "The Evaluations page"; `spec/handoffs.md` cited, not changed.

## PR ladder

1. **This plan**, with rulings 55–57 in `todo_master.md`. Prose only.
2. **Scaffold.** The gate page's Review Robin card, every part as a static placeholder in its real layout. Evaluations' row action links to it. Must not wire any action.
3. **The bundle.** `applydesk/handoff.py`'s builders, confidential gates included, with unit tests. *What is sent* shows counts and offers each CSV from a download route.
4. **Send and re-send in the tab.** The session name and code, *Send*, *Re-send* and *Changed since sent*, the refusals, and the head's chip following. Includes a browser test.
5. **Status, results, link state, invite and remind.** *Pull results* and *Pull final results* (ruling 57), *Detached*, *Invite* and *Remind* with their preview, and a browser test. This is the item's last build rung, so the cumulative cold read runs here.
6. **Close.** `spec-writer` on "The Evaluations page", Status compacted, the roadmap row deleted, the plan archived.

## Definition of done

- The card shows the name, code, link state, last send, *What is sent*, Status, *Invite* and *Remind* on every gate page (a page test).
- The builders' files are the CSVs Quick Setup takes (`spec/csv_contracts.md`) inside `spec/handoffs.md` §4's envelope. A confidential gate's files hold no applicant name or application ID (`test_handoff.py`).
- *Send* on a *Ready* gate makes it *Sent* in the tab. A pair change saved in the sample makes it *Changed since sent* and offers *Re-send* (a browser test).
- A taken code is refused with `session_code_conflict`'s reason (a browser test).
- *Pull final results* on a closed session marks the gate *Results in* (a browser test).
- `## Doc impact` section present and current
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `applydesk/guide/todo_master.md` entries deleted; plan moved to `applydesk/guide/archive/` + index row
- (`tools/close_check.py` reads only RRW's top-level `guide/`; the close is checked by hand, as AD1L's was.)

## Open questions

- **Sample gates for the later states**: answered (author, 2026-11-19): the second exercise (`k7mfr3pq8z`) gains *Second reading*, closed in Review Robin and not yet pulled (*Closed*), and *Moderation*, detached (*Detached*); both count as opened.

- **How a detached gate concludes**: open (the cold read). `locks` and `timeline` count only *Results in* as complete, so a detached gate keeps its stage, and the exercise, from completing. The author decides; nothing is built for it here.

## Out of scope

- Real calls, the transfer record, retry and replay: AD2 and AD6.
- Results written into Dossiers' columns and dossier parts (rulings 21, 26): AD6. Here they show on the card.
- Invitation and reminder templates on Emails, and sending any email: AD7.
- How Apply Desk's operators line up with Review Robin's: open in "What a linked Review Robin gate needs".

## Doc impact

- `applydesk/spec/applications.md` — "The Evaluations page": the Review Robin card, the states and *Changed since sent*, Send, Re-send, Pull results, Detached, Invite and Remind, simulated in the tab (rungs 2–5).
- `applydesk/guide/todo_master.md` — rulings 55–57 (rung 1); delete the Layer B roadmap row and the settled "Rulings to settle" lines (at close).
- `applydesk/guide/archive/README.md` — the plan's index row (at close).
