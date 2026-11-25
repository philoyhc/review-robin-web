# Segment 23J — A linked session set up before its rosters

**Opened:** 2026-11-25 · **Theme:** a linked application creates its Review Robin session when the gate is set up, then sends the rosters when they are known · **Related:** `spec/handoffs.md` (§6 create, §6a re-send), `spec/linked_sessions.md` (`rosters`), `applydesk/spec/applications.md` (the Review Robin card), `guide/archive/segment_23G_linked_custom_instrument.md`

## Opportunity

Apply Desk creates a gate's Review Robin session only at *Send to Review Robin*, and *Send* waits for the gate to be *Ready* (`applydesk/spec/applications.md`). *Ready* means:
- the stage is published;
- every entry is decided;
- every dossier is assigned, and approved under *Suggested*.

That is usually after applications close, and often just before the gate's start. Two things suffer:

- **A custom gate's instrument** (23G) can only be built in Review Robin between *Send* and the session opening. That covers the Familiarity question, the branches, the order and *Required*. This is design work, but it falls at the busiest moment of the exercise, beside approvals and invitations.
- **The operator has no way into the session** until it exists. *Open in Review Robin ↗* (the author's question, 2026-11-25) has nowhere to point before *Send*.

Review Robin refuses the earlier create today. `reviewers` and `reviewees` are required files (`handoffs.REQUIRED_FILES`). A roster with no rows is `422 invalid_setup`, reason `empty_roster` (`handoffs.check_rosters`). A cut-off create's replay also tells "the save happened" by the rosters being there (`handoffs.rosters_saved`, read by `handoffs.replayed`).

## Decision

The author's, 2026-11-25: **a linked session is set up first, populated later.**

1. **Set up in Review Robin** is a step on the gate's page, separate from sending rosters. Its create carries the settings and the instrument and no rosters, and makes the linked draft. Review Robin's receipt gives `session_home_url`, and the gate's Review Robin card shows **Open in Review Robin ↗** (a new tab) from then on.
2. **Send rosters** is today's *Send*, on a *Ready* gate. It is now a re-send (§6a) carrying the reviewers, reviewees and relationships. Re-sends already replace rosters and settings whole and keep a custom instrument's own work (23F, 23G).
3. **The draft cannot open without rosters.** An empty draft fails Validate, and a scheduled start activates only a prepared session (`spec/lifecycle.md`).
4. **Both gate types** take the same two steps: one lifecycle. Only custom strictly needs the early session.
5. **The step is manual**, not automatic on a gate's Save. A draft is made only for a gate the operator means to run.

Rejected:
- **Keep the create at *Send*** and only add the link afterwards. That leaves custom work squeezed into the days between *Ready* and the start, the problem this segment exists for.
- **A create automatic on every gate Save.** It would leave a draft in Review Robin for every gate tried and dropped, and make Process's Save a cross-app call.
- **A separate "settings-only" endpoint.** The create already parses settings and sets up the instrument; letting a linked create omit its rosters is one rule, not a second route.

## Semantics

- **A create without rosters** (`spec/handoffs.md` §6) is allowed only when the sender is a linked profile (`linked_apps`). The `reviewers` and `reviewees` files are then optional, or may be present with a header and no rows. A native create still needs both. The draft is made with its settings, its tag and its instrument (`set_up_instrument`, so a custom instrument starts with its held fields). The audit's context gains `rosters: false`.
- **Replay** of a create without rosters reads the completion record, not the rosters. Completed means `already_created`, as now. Not completed and recent means `transfer_in_progress`. Not completed and older means `transfer_incomplete`. `rosters_saved` keeps its meaning for a create that carried rosters.
- **The first roster send** is an ordinary re-send (§6a), guarded as now (`guard_update`: unopened, no responses). The rosters lock applies from creation, so the operator never edits rosters in Review Robin.
- **An empty draft** shows on Session Home and in the lobby as a draft, its rosters empty. Validate names the missing rosters (verified in rung 2, by a test). *Start* passes with nothing opened.
- **A gate dropped after set-up** has its empty draft removed (author, 2026-11-25). Review Robin gains **discard** (`POST …/handoffs/{transfer_id}/discard`), which Apply Desk calls when the gate is removed or its exercise discarded.
  - It deletes the linked draft only when the session is a draft, its rosters are empty and it has no responses, and the caller is the transfer's sender and still an operator of it. The session goes with its audit events, as a refused create's does.
  - Anything else is refused and nothing is deleted: `409 session_not_empty` once rosters have been sent, `session_opened` once the session has opened, `not_linked` after an Unlink. Such a session is the operator's to delete in Review Robin.
  - A discard of a transfer already discarded answers `already_discarded`, so a retry is safe.
  - The discard is audited as an operator's delete is: `session.deleted`, written with no session (`sessions.py` does the same), its snapshot naming the session, and `context` adding `transfer_id` and `source_app`.
- **Apply Desk's states** for a gate's link, in order:
  - *Not set up*;
  - *Set up* (the session exists, no rosters);
  - *Sent* (rosters sent, unopened);
  - then today's states: open, closed, detached, results in.

  *Not ready* and *Ready* keep reading the gate's own readiness to send rosters.

## Judgment calls — decided

- The rule is "a linked create may omit rosters", not a new flag in the bundle: the sender's profile already says it is linked.
- The link uses Review Robin's `session_home_url` as given, never a URL Apply Desk builds itself.
- One lifecycle for both gate types (author's recommendation accepted, 2026-11-25).
- A dropped gate's empty draft is removed by Apply Desk's discard call, not left for the operator (author, 2026-11-25). The call refuses anything but an empty, unopened, still-linked draft, so it can never delete work.
- *Set up* is offered only once the exercise is published, when the gate's page exists (rulings 60, 61; author, 2026-11-25).

## Blast radius (measured)

Taken 2026-11-25 at `d23dffcd2`.

| What | Count | Command |
|---|---|---|
| The roster rules in the handoff service | 3 (`REQUIRED_FILES`, `check_rosters`, `rosters_saved`) | `grep -n "REQUIRED_FILES\|def check_rosters\|def rosters_saved" app/services/handoffs.py` |
| Callers of `check_rosters` / `rosters_saved` | 1 / 2 | `grep -rn "check_rosters(\|rosters_saved(" app/` |
| Handoff service and route | 824 + 458 lines | `wc -l app/services/handoffs.py app/web/routes_operator/_handoffs.py` |
| Review Robin tests on `empty_roster` | 1 file, `tests/integration/test_handoffs.py` | `grep -rln 'empty_roster' tests/integration/test_handoff*.py` |
| Tests calling the handoff routes | 11 files | `grep -rln 'handoffs/' tests \| wc -l` |
| Specs naming `empty_roster` | 1, `spec/handoffs.md` | `grep -rln empty_roster spec docs` |
| Apply Desk: gate state and the Review Robin card | 9 files; `_rr_js.html` 276 lines; gate states *Not ready*, *Ready*, *Sent*, *Not sent* | `grep -rln "gate_state\|data-rr-" applydesk/templates applydesk/*.py` |
| Apply Desk tests on the card | 4 files (`test_rr_browser.py`, `test_handoff.py`, `test_pages.py`, `test_layout_browser.py`) | `grep -rln "_rr_js\|data-rr-" applydesk/tests --include=*.py` |

## Status

**Rung 2 (2026-11-25):**
- A linked sender may omit both roster files (`handoffs.carries_rosters`). One roster without the other is `invalid_package`, as is a `relationships` file without rosters. A header with no rows is still `empty_roster`.
- The create's audit `context` gains `rosters`.
- Replay needed no change. A completed set-up answers `already_created`; one cut off before its record is `transfer_in_progress`, then `transfer_incomplete`. Only the incomplete message no longer names rosters.
- **Taken beyond the ladder:** a re-send may also carry the settings alone, before the rosters, so Process edits after set-up reach the draft. The pipeline had no file to save and returned before the re-send's guard and record. Now, with no files, it runs them under the session lock (`quick_setup_pipeline.run_contents`).
- The cumulative read for rungs 2–5 runs from `8e2eb04ec`.

**Rung 3 (2026-11-25):**
- `POST /operator/handoffs/{transfer_id}/discard` takes an envelope with operation `reviewrobin.discard_draft_session` and no files (`handoffs.parse_discard`). It deletes the draft through `sessions.delete_session`. That writes `session.deleted` with no session, now with a `context`: the creating `transfer_id`, `source_app`, and the discard's own `discard_transfer_id`. `session.deleted` gains `context` in `EVENT_SCHEMAS`.
- Refusals: `not_linked` (unknown transfer, another application, or unlinked since), `not_authorized` (not the operator who set it up), `session_opened`, and `session_not_empty` (rosters or responses), each rechecked under the session lock.
- A retry answers `already_discarded` with the session code, read from that delete.
- A transfer cut off before completion may also be discarded: its draft is just as empty.

## PR ladder

1. **Plan**: this file, its queue entry and README row; Apply Desk's ruling 80 in `applydesk/guide/todo_master.md`, with AD6's row naming the stored `session_home_url`. Prose only.
2. **Review Robin: a linked create without rosters.** `REQUIRED_FILES` and `check_rosters` relax for a linked sender. Replay keys on the completion record. Audit context. Integration tests:
   - a create without rosters, then a roster re-send;
   - replay in its three cases;
   - Validate refusing the empty draft;
   - a native create still refused.

   Must not touch Apply Desk.
3. **Review Robin: discard.** The call deletes an empty linked draft for its sender, with its refusals, its replay and its audit. Integration tests cover each refusal, a retried discard, and a draft with rosters left whole. Must not touch Apply Desk.
4. **Apply Desk: the card's two steps, scaffold.** *Set up in Review Robin* and *Send rosters*, the link line's new state, and *Open in Review Robin ↗*. Inert, with each reason in its title. Must not touch Review Robin.
5. **Apply Desk: the steps wired, simulated in the tab** (as `_rr_js.html` sends today). Set-up keeps a sample `session_home_url`, and the link opens it in a new tab. *Send rosters* is today's *Send*, reading *Re-send* after. Removing a set-up gate on Process says its draft will be discarded. `diff-reviewer` reads 2–5.
6. **Close**, after the author's check.

Real sends, and storing `session_home_url` with the gate's transfer record, are AD6's and AD2F's (Out of scope).

## Definition of done

- A linked create without rosters makes a draft that cannot be validated or opened, and a roster re-send populates it (Review Robin tests).
- A native create without rosters is still refused (test).
- Replay of a create without rosters answers in its three cases (tests).
- Discard deletes an empty linked draft for its sender and refuses every other session, deleting nothing (tests).
- The gate's Review Robin card offers *Set up in Review Robin*, then *Send rosters*, and shows *Open in Review Robin ↗* (new tab) from set-up on (Apply Desk tests, Chromium).
- The author has used the two steps locally and approved them.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 23J` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **A gate dropped after set-up:** its empty draft is removed by Review Robin's discard call (author, 2026-11-25; Semantics).
- **Who else can open the link?** The session is created as the operator who sets it up. Whether Apply Desk's other exercise operators become its Review Robin operators is `guide/rrw_permissions_update.md`'s question, decided with AD6 (author, 2026-11-25). Until then the link may refuse them.
- ***Set up* in a draft exercise:** no, only once the exercise is published (author, 2026-11-25).

## Out of scope

- **Real sends from Apply Desk**, and storing `session_home_url` with the gate's transfer record: AD2F (the record) and AD6 (the calls), named in ruling 80.
- **Review Robin's operator model for co-operators:** `guide/rrw_permissions_update.md`.
- **Apply Desk's real discard call** when a gate is removed: AD6, with the other calls. This segment builds Review Robin's side and simulates Apply Desk's.

## Doc impact

- `spec/handoffs.md` — §6: a linked create may omit its rosters; replay of such a create; the audit context. §6a: the first roster send to an empty draft. A new section: discard, its conditions, refusals and audit.
- `spec/linked_sessions.md` — `rosters`: an empty linked draft, and Validate refusing it.
- `applydesk/spec/applications.md` — the Review Robin card's two steps, the *Set up* state and *Open in Review Robin ↗*; removing a set-up gate discards its draft.
- `applydesk/guide/todo_master.md` — ruling 80; AD6's row names the stored `session_home_url`.
- `guide/todo_master.md` — the queue entry (rung 1); deleted at close.
- `guide/README.md` — this plan's row (rung 1); moved to the archive's index at close.
