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

**Rung 4 (2026-11-25, scaffold):** on the gate page's Review Robin card:
- *Set up in Review Robin* comes before *Send rosters* (renamed from *Send to Review Robin*). It is disabled, with its reason in its title; the card's script leaves it so.
- The facts gain *In Review Robin*, an inert *Open in Review Robin ↗*.
- The Progress line says what each step does.

**Rung 5 (2026-11-25):** the steps are simulated in the tab, as sends are (`_rr_js.html`).
- **Set up** checks the session's name and code (and the other gates' codes, set-up ones included) and any field Review Robin would refuse; its pairs and readiness wait for the rosters. It is kept under `applydesk-rr-setup:<exercise>` with its transfer and link.
- **The link line** reads *Linked; set up, its rosters not yet sent*.
- **Open in Review Robin ↗** is live, in a new tab, once a gate is set up, sent or opened. The sample's stand-in for `session_home_url` is Review Robin's session list (`_rr_home`).
- **Send rosters** after a set-up sends to the set-up's transfer.
- **Process** asks before removing a gate set up but not sent.

**Cumulative read (1, at rung 5, on `8e2eb04ec..7ac0a8132`):** one high, five medium, four low; fixed in rung 5 unless noted.
- **High:** the settings-only re-send's unit, and discard, waited on the session lock on the event loop (findings Bc3). Both now run in the threadpool.
- **Medium:**
  - A create retried after its discard made a fresh draft; it is now `409 session_discarded`.
  - A discard during a create still running would have broken the create; it is now `transfer_in_progress` within `IN_PROGRESS`.
  - A roster with a header and no rows stays `empty_roster`. Semantics' "header and no rows" is superseded by Status rung 2, and a test pins it.
  - A settings-only re-send after the rosters keeps them; a test pins it.
  - Discard also removes instrument work built in Review Robin: the gate is the operator's to drop, and Process's confirm now says so. The judgment call "can never delete work" holds for rosters and responses only.
- **Low:**
  - *Set up* is Secondary, one Primary per region.
  - A discard that loses the lock race to another answers `already_discarded` or `not_linked`, not a 500.
  - A replayed discard checks its sender.
  - The unused `rr-open-off` class is gone.
  - Not fixed: a set-up record outlives a removed gate in the tab. It is harmless, since no page reads a gate that is gone.
  - Not fixed: a re-send racing a discard can still 500 on the lock, as a re-send racing an operator's delete already could.

**Rung 6 (2026-11-25):** `GET /operator/sessions/by-code/{code}` (`sessions.public_id_for_code`) redirects an operator of the session to its Session Home (307). Anyone else, or an unknown code, gets the uniform 404 (a sys-admin's exception came with rung 8's fixes). The URL crawl visits it. The cumulative read for rungs 6–8 runs from `540b669fb`.

**Rung 7 (2026-11-26, scaffold):** the gate card ends with *Create Review Robin session*, after *Remove the gate* and outside the gate's lock: a published stage's gate, locked for editing, is the one to set up.

**Rung 8 (2026-11-26):**
- *Create Review Robin session* is off, its reason in its title, until the exercise is published, the gate saved, and no field is one Review Robin would refuse. It is also off while the page has unsaved changes, as the gate is set up as saved.
- A click keeps the set-up in the store Evaluations uses (`applydesk-rr-setup:<exercise>`), with the gate's default name and code (ruling 56). It opens `…/reviewrobin/operator/sessions/by-code/<code>` in a new tab. The card then offers *Open Review Robin session ↗*, as it does for a gate already sent.
- Evaluations' *Open in Review Robin ↗* goes by the session's code: the one it was sent or set up with, else the sample's. `_rr_home` gives way to `_rr_by_code`.
- A replicated stage's gates start with the button off until saved.
- **Cumulative read (rungs 6–8, on `540b669fb..561021aa8`):** no high; one medium, seven low. Fixed in rung 8:
  - Doc impact gained `spec/session_home.md` (the route) and the Process button under `applydesk/spec/applications.md`.
  - By code, a sys-admin who is not an owner is sent on to Session Home's legible 403 and the adopt door, as `require_session_operator` answers. A refusal is logged as that gate logs one.
  - Ruling 80 and Out of scope no longer owe a stored `session_home_url`.
  - A replicated gate's button says the draft exercise's reason.
  - Left as they are: a code holding `/` misses the one-segment route (Apply Desk's codes never hold one; the URL crawl cannot format a `:path` route); `public_id_for_code`'s tuple; Process's link styled as a button, Evaluations' as a link in its facts list.

**Amended (author, 2026-11-25, after rung 5).** The gate card on Process gains *Create Review Robin session* at its end, active once the gate's set-up fields are complete; a click creates the session and opens its home in a new tab. *Open in Review Robin ↗* on Evaluations goes straight to that session's home by its code, which Apply Desk already knows. Review Robin gains a lookup by code for it (rung 6). Rungs 6–8 build this; the close moves to 9.

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
~~6. **Close**~~: moved to 9 (author, 2026-11-25, after rung 5).
6. **Review Robin: open a session by its code.** `GET /operator/sessions/by-code/{code}` redirects an operator of that session to its Session Home; anyone else, or an unknown code, gets the uniform 404. Apply Desk knows a gate's session code (ruling 56), so its links need no stored URL. Must not touch Apply Desk's code.
7. **Apply Desk: *Create Review Robin session* on the Process gate card, scaffold.** It sits at the end of the gate card and is inert, its reason in its title.
8. **Apply Desk: wired.** The button is active once the gate's set-up fields are complete. A click sets the gate up (as Evaluations' *Set up* does) and opens its session's home by code in a new tab. Once set up, the card offers *Open Review Robin session ↗* instead. Evaluations' *Open in Review Robin ↗* goes to the session by its code.
9. **Close**, after the author's check.

Real sends, and storing `session_home_url` with the gate's transfer record, are AD6's and AD2F's (Out of scope). Since the amendment the link goes by the session's code, so no stored URL is owed.

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

- **A gate dropped after set-up:** its empty draft is removed by Review Robin's discard call (author, 2026-11-25; Semantics). Discard also removes any custom instrument built there; that is accepted (author, 2026-11-26).
- **Who else can open the link?** The session is created as the operator who sets it up. Whether Apply Desk's other exercise operators become its Review Robin operators is `guide/rrw_permissions_update.md`'s question, decided with AD6 (author, 2026-11-25). Until then the link may refuse them.
- ***Set up* in a draft exercise:** no, only once the exercise is published (author, 2026-11-25).

## Out of scope

- **Real sends from Apply Desk**, and the gate's transfer record: AD2F (the record) and AD6 (the calls), named in ruling 80. A stored `session_home_url` is no longer owed: the link goes by code (amended, 2026-11-25).
- **Review Robin's operator model for co-operators:** `guide/rrw_permissions_update.md`.
- **Apply Desk's real discard call** when a gate is removed: AD6, with the other calls. This segment builds Review Robin's side and simulates Apply Desk's.

## Doc impact

- `spec/handoffs.md` — §6: a linked create may omit its rosters; replay of such a create; the audit context. §6a: the first roster send to an empty draft. A new section: discard, its conditions, refusals and audit.
- `spec/linked_sessions.md` — `rosters`: an empty linked draft, and Validate refusing it.
- `applydesk/spec/applications.md` — the Review Robin card's two steps, the *Set up* state and *Open in Review Robin ↗* by code; removing a set-up gate discards its draft; the Process gate card's *Create Review Robin session* (rungs 7–8).
- `applydesk/guide/todo_master.md` — ruling 80 and its amendment; AD6's row (the link by code).
- `spec/session_home.md` — `GET /operator/sessions/by-code/{code}`: the redirect, the uniform 404, and the sys-admin exception (rung 6).
- `guide/todo_master.md` — the queue entry (rung 1); deleted at close.
- `guide/README.md` — this plan's row (rung 1); moved to the archive's index at close.
